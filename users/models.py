from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User Model mở rộng từ AbstractUser.
    Hỗ trợ định danh số điện thoại phục vụ việc xác thực cư dân local tại Việt Nam.
    """
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Số điện thoại"
    )

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Danh sách người dùng"

    def __str__(self):
        return self.phone_number or self.username


class VerificationStatus(models.TextChoices):
    UNVERIFIED = 'unverified', 'Chưa gửi xác thực'
    PENDING = 'pending', 'Đang chờ xác minh'
    VERIFIED = 'verified', 'Đã xác thực cư dân'
    REJECTED = 'rejected', 'Bị từ chối xác thực'


class UserProfile(models.Model):
    """
    Hồ sơ cư dân địa phương HubLocal.
    Quy tắc nghiệp vụ:
    - Tuyệt đối không tự động cấp huy hiệu 'Local Verified' chỉ bằng việc tự khai thời gian sinh sống.
    - Quy trình xác thực thông qua trạng thái rõ ràng: unverified -> pending -> verified / rejected.
    - Chỉ tài khoản ở trạng thái 'verified' mới được gắn cờ is_local_verified và có quyền xác thực địa điểm.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Tài khoản"
    )
    residing_district = models.CharField(
        max_length=100,
        default='Thủ Đức',
        db_index=True,
        verbose_name="Quận/Khu vực cư trú"
    )
    residing_months = models.PositiveIntegerField(
        default=0,
        verbose_name="Thời gian cư trú tự khai (tháng)"
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,
        verbose_name="Trạng thái xác thực"
    )
    is_local_verified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Đã xác thực Local"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm xác nhận local"
    )
    verification_rejected_reason = models.TextField(
        blank=True,
        default='',
        verbose_name="Lý do từ chối xác thực"
    )
    has_seen_verification_modal = models.BooleanField(
        default=False,
        verbose_name="Đã xem pop-up chúc mừng xác thực"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Hồ sơ cư dân"
        verbose_name_plural = "Danh sách hồ sơ cư dân"

    def save(self, *args, **kwargs):
        # Đảm bảo cờ boolean is_local_verified luôn đồng bộ nghiêm ngặt với verification_status
        self.is_local_verified = (self.verification_status == VerificationStatus.VERIFIED)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.residing_district} ({self.get_verification_status_display()})"

