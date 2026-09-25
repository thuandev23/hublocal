from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PlaceVerification, Tip


def sync_place_metrics(place_id):
    from .models import Place
    try:
        place = Place.objects.get(id=place_id)
        place.recalculate_trust_metrics()
        place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at', 'updated_at'])
    except Place.DoesNotExist:
        pass


@receiver(post_save, sender=PlaceVerification)
def on_verification_saved(sender, instance, created, **kwargs):
    if created:
        place_id = instance.place_id
        transaction.on_commit(lambda: sync_place_metrics(place_id))


@receiver(post_delete, sender=PlaceVerification)
def on_verification_deleted(sender, instance, **kwargs):
    place_id = instance.place_id
    transaction.on_commit(lambda: sync_place_metrics(place_id))


@receiver(post_save, sender=Tip)
def on_tip_saved(sender, instance, created, **kwargs):
    """
    Nếu local đăng tip mới và chưa từng nhấn xác thực, tự động thêm xác thực cho địa điểm.
    """
    if created:
        user = instance.user
        # Kiểm tra xem user có phải cư dân local xác thực hay không
        is_local = getattr(getattr(user, 'profile', None), 'is_local_verified', False)
        if is_local:
            PlaceVerification.objects.get_or_create(place=instance.place, user=user)
        else:
            # Vẫn cập nhật thời gian place
            instance.place.save(update_fields=['updated_at'])
