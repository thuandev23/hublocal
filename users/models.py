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


class UserProfile(models.Model):
    """
    Hồ sơ cư dân địa phương.
    Ngưỡng xác thực: Cư trú tối thiểu 6 tháng (residing_months >= 6) tại khu vực (mặc định: Thủ Đức).
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
        verbose_name="Thời gian cư trú (tháng)"
    )
    is_local_verified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Đã xác thực Local"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Hồ sơ cư dân"
        verbose_name_plural = "Danh sách hồ sơ cư dân"

    def save(self, *args, **kwargs):
        # Tự động cập nhật cờ xác thực local theo quy chuẩn >= 6 tháng
        if self.residing_months >= 6:
            self.is_local_verified = True
        else:
            self.is_local_verified = False
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Local Verified" if self.is_local_verified else "Chưa xác thực"
        return f"{self.user} - {self.residing_district} ({status})"
