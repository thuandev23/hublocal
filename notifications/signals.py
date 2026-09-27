import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from users.models import UserProfile, VerificationStatus
from places.models import Place, TrustTier
from .services import send_push_notification

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=UserProfile)
def track_verification_status_change(sender, instance, **kwargs):
    """
    Theo dõi sự thay đổi trạng thái xác minh trước khi lưu vào DB.
    """
    if instance.pk:
        try:
            old_profile = UserProfile.objects.get(pk=instance.pk)
            instance._old_verification_status = old_profile.verification_status
        except UserProfile.DoesNotExist:
            instance._old_verification_status = None
    else:
        instance._old_verification_status = None


@receiver(post_save, sender=UserProfile)
def notify_user_on_verification_approval(sender, instance, created, **kwargs):
    """
    Kịch bản 1: Tự động gửi Push Notification ngay khi tài khoản được duyệt trở thành Local Verified.
    """
    old_status = getattr(instance, '_old_verification_status', None)
    current_status = instance.verification_status

    if current_status == VerificationStatus.VERIFIED and old_status != VerificationStatus.VERIFIED:
        logger.info(f"Kích hoạt thông báo duyệt cư dân thành công cho {instance.user}")
        send_push_notification(
            user=instance.user,
            title="🎉 Hồ sơ cư dân của bạn đã được duyệt!",
            body=f"Chúc mừng bạn đã trở thành Cư dân chính thức tại {instance.residing_district}. Hãy bảo chứng cho những quán quen của bạn ngay hôm nay!",
            data={
                "type": "VERIFICATION_APPROVED",
                "district": instance.residing_district,
            }
        )
    elif current_status == VerificationStatus.REJECTED and old_status != VerificationStatus.REJECTED:
        reason = instance.verification_rejected_reason or "Thông tin cư trú chưa đáp ứng tiêu chuẩn cộng đồng HubLocal."
        logger.info(f"Kích hoạt thông báo từ chối xác thực cư dân cho {instance.user}")
        send_push_notification(
            user=instance.user,
            title="⚠️ Yêu cầu xác thực cư dân chưa được duyệt",
            body=f"Yêu cầu xác minh tại {instance.residing_district} chưa được duyệt. Lý do: {reason}",
            data={
                "type": "VERIFICATION_REJECTED",
                "district": instance.residing_district,
                "reason": reason,
            }
        )


@receiver(pre_save, sender=Place)
def track_place_tier_change(sender, instance, **kwargs):
    """
    Theo dõi sự thay đổi bậc tín nhiệm của địa điểm.
    """
    if instance.pk:
        try:
            old_place = Place.objects.get(pk=instance.pk)
            instance._old_trust_tier = old_place.trust_tier
        except Place.DoesNotExist:
            instance._old_trust_tier = None
    else:
        instance._old_trust_tier = None


@receiver(post_save, sender=Place)
def notify_verifiers_on_tier2_upgrade(sender, instance, created, **kwargs):
    """
    Kịch bản 2: Khi một địa điểm thăng hạng lên Tier 2 (High Trust),
    gửi thông báo vinh danh tới tất cả các cư dân đã tham gia xác nhận địa điểm này!
    """
    old_tier = getattr(instance, '_old_trust_tier', None)
    current_tier = instance.trust_tier

    if current_tier == TrustTier.TIER_2_HIGH_TRUST and old_tier != TrustTier.TIER_2_HIGH_TRUST:
        verifications = instance.verifications.select_related('user').all()
        for ver in verifications:
            send_push_notification(
                user=ver.user,
                title="⭐ Quán quen của bạn đã thăng hạng!",
                body=f"Quán [{instance.name}] bạn từng xác nhận vừa đạt cấp độ Tín nhiệm cao nhờ sự đóng góp của bạn!",
                data={
                    "type": "PLACE_TIER_UPGRADED",
                    "place_id": str(instance.id),
                    "place_name": instance.name,
                }
            )
