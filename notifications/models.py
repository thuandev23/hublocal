from django.db import models
from django.conf import settings


class PlatformChoices(models.TextChoices):
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'
    WEB = 'web', 'Web'


class DeviceToken(models.Model):
    """
    Lưu trữ FCM Device Registration Token của các thiết bị di động (Flutter).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        verbose_name="Người dùng"
    )
    token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="FCM Token"
    )
    platform = models.CharField(
        max_length=20,
        choices=PlatformChoices.choices,
        default=PlatformChoices.ANDROID,
        verbose_name="Hệ điều hành thiết bị"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Trạng thái kích hoạt"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng ký")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Device Token FCM"
        verbose_name_plural = "Danh sách Device Tokens"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user} - {self.platform} ({self.token[:12]}...)"


class Notification(models.Model):
    """
    Hộp thư thông báo trong ứng dụng (In-app Notification History).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Người nhận"
    )
    title = models.CharField(max_length=255, verbose_name="Tiêu đề")
    body = models.TextField(verbose_name="Nội dung thông báo")
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Dữ liệu kèm theo (Payload)"
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Đã đọc"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Thời gian gửi")

    class Meta:
        verbose_name = "Thông báo"
        verbose_name_plural = "Hộp thư thông báo"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.user}"
