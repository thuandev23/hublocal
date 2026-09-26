from django.db import models
from django.conf import settings
from django.utils import timezone


class CategoryChoices(models.TextChoices):
    EAT_DRINK = 'EAT_DRINK', 'Ăn uống'
    PLAY_ENTERTAINMENT = 'PLAY', 'Vui chơi'
    SERVICES = 'SERVICES', 'Dịch vụ'


class TrustTier(models.IntegerChoices):
    TIER_0_UNVERIFIED = 0, 'Chưa có xác thực local'
    TIER_1_VERIFIED = 1, '1-2 local xác thực (icon check)'
    TIER_2_HIGH_TRUST = 2, '3+ local xác thực (hiển thị số)'


class Place(models.Model):
    """
    Địa điểm địa phương được quản lý bởi hệ thống HubLocal.
    Tối ưu truy vấn bằng Composite Index và Denormalized Trust Tier.
    """
    name = models.CharField(max_length=255, db_index=True, verbose_name="Tên địa điểm")
    category = models.CharField(
        max_length=50,
        choices=CategoryChoices.choices,
        db_index=True,
        verbose_name="Danh mục"
    )
    district = models.CharField(
        max_length=100,
        default='Thủ Đức',
        db_index=True,
        verbose_name="Quận/Khu vực"
    )
    address = models.CharField(max_length=500, verbose_name="Địa chỉ")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Vĩ độ (Lat)"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name="Kinh độ (Lng)"
    )
    cover_image = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name="Link ảnh bìa"
    )

    # Thông tin nguồn Google Maps (Dữ liệu tham khảo - tách biệt với HubLocal Trust)
    google_place_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Google Place ID"
    )
    google_maps_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name="Link Google Maps gốc"
    )
    google_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="Điểm Google Maps"
    )
    google_review_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Số lượng review trên Google"
    )
    google_reviews = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Review từ Google (Dữ liệu thô tham khảo)"
    )
    google_scraped_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm thu thập từ Google"
    )
    imported_at = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name="Thời điểm nhập vào HubLocal"
    )

    # Denormalized fields để tăng tốc độ truy vấn đọc lớn
    verified_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Số lượng local xác thực"
    )
    trust_tier = models.PositiveSmallIntegerField(
        choices=TrustTier.choices,
        default=TrustTier.TIER_0_UNVERIFIED,
        db_index=True,
        verbose_name="Huy hiệu tín nhiệm"
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Xác thực gần nhất"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Địa điểm"
        verbose_name_plural = "Danh sách địa điểm"
        ordering = ['-verified_count', '-last_verified_at', '-id']
        indexes = [
            models.Index(
                fields=['district', 'category', '-verified_count'],
                name='place_dist_cat_ver_idx'
            ),
        ]

    def recalculate_trust_metrics(self):
        """
        Tính toán lại số lượng local xác nhận và phân tầng huy hiệu:
        - 0 local -> Tier 0 (Không badge)
        - 1-2 local -> Tier 1 (Icon check nhỏ)
        - >=3 local -> Tier 2 (Badge kèm số)
        """
        count = self.verifications.count()
        self.verified_count = count
        if count == 0:
            self.trust_tier = TrustTier.TIER_0_UNVERIFIED
        elif 1 <= count <= 2:
            self.trust_tier = TrustTier.TIER_1_VERIFIED
        else:
            self.trust_tier = TrustTier.TIER_2_HIGH_TRUST

        latest_verification = self.verifications.order_by('-created_at').first()
        if latest_verification:
            self.last_verified_at = latest_verification.created_at

    def __str__(self):
        return f"{self.name} ({self.get_category_display()} - {self.district})"


class PlaceVerification(models.Model):
    """
    Bản ghi xác thực: 1 cư dân local (cư trú >= 6 tháng) nhấn nút "Tôi cũng biết chỗ này".
    Ràng buộc Unique ngăn chặn spam.
    """
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name="Địa điểm"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='place_verifications',
        verbose_name="Cư dân xác thực"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian xác thực")

    class Meta:
        verbose_name = "Lượt xác thực local"
        verbose_name_plural = "Danh sách lượt xác thực"
        constraints = [
            models.UniqueConstraint(
                fields=['place', 'user'],
                name='unique_user_place_verification'
            )
        ]

    def __str__(self):
        return f"{self.user} xác thực {self.place.name}"


class Tip(models.Model):
    """
    Mẹo từ cư dân local cho địa điểm.
    Mỗi local chỉ có tối đa 1 mẹo trên 1 địa điểm và có toàn quyền chỉnh sửa mẹo của mình.
    """
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='tips',
        verbose_name="Địa điểm"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tips',
        verbose_name="Tác giả"
    )
    content = models.TextField(
        verbose_name="Mẹo từ local (ngắn gọn, thiết thực, món nên thử, giờ vắng...)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Cập nhật lần cuối")

    class Meta:
        verbose_name = "Mẹo địa phương"
        verbose_name_plural = "Danh sách mẹo"
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['place', 'user'],
                name='unique_user_place_tip'
            )
        ]

    def __str__(self):
        return f"Mẹo của {self.user} tại {self.place.name}"
