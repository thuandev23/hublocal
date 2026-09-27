from django.db import models
from django.conf import settings
from django.utils import timezone


class CategoryChoices(models.TextChoices):
    EAT_DRINK = 'EAT_DRINK', 'Ăn uống'
    PLAY_ENTERTAINMENT = 'PLAY', 'Vui chơi'
    SERVICES = 'SERVICES', 'Dịch vụ'


class PlaceStatus(models.TextChoices):
    OPEN = 'OPEN', 'Đang hoạt động'
    TEMP_CLOSED = 'TEMP_CLOSED', 'Tạm thời đóng cửa'
    PERM_CLOSED = 'PERM_CLOSED', 'Đã ngừng hoạt động'


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
    district_code = models.CharField(
        max_length=50,
        default='THU_DUC',
        db_index=True,
        verbose_name="Mã quận chuẩn hóa"
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
    thumbnail_image = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name="Link ảnh thu nhỏ"
    )
    photos = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Danh sách link ảnh album (Google Maps)"
    )

    # Trạng thái hoạt động thực tế
    status = models.CharField(
        max_length=20,
        choices=PlaceStatus.choices,
        default=PlaceStatus.OPEN,
        db_index=True,
        verbose_name="Trạng thái hoạt động"
    )

    # Thông tin khoảng giá (Không tạo giá mẫu; null nếu chưa rõ)
    min_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Giá tối thiểu (VNĐ)"
    )
    max_price = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="Giá tối đa (VNĐ)"
    )
    price_currency = models.CharField(
        max_length=10,
        default='VND',
        verbose_name="Đơn vị tiền tệ"
    )
    price_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm cập nhật giá"
    )

    # Giờ hoạt động
    opening_hours_text = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Giờ mở cửa hiển thị"
    )
    opening_hours_structured = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Cấu trúc giờ mở cửa tuần"
    )

    # Nguồn dữ liệu
    data_source = models.CharField(
        max_length=50,
        default='google_maps',
        verbose_name="Nguồn dữ liệu gốc"
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


class SavedPlace(models.Model):
    """
    Bản ghi địa điểm được người dùng lưu lại (Bookmarks/Favorites).
    Ràng buộc Unique ngăn chặn duplicate.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_places',
        verbose_name="Người dùng"
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='saved_by',
        verbose_name="Địa điểm"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm lưu")

    class Meta:
        verbose_name = "Địa điểm đã lưu"
        verbose_name_plural = "Danh sách địa điểm đã lưu"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'place'],
                name='unique_user_saved_place'
            )
        ]

    def __str__(self):
        return f"{self.user} đã lưu {self.place.name}"


class ReportTypeChoices(models.TextChoices):
    CLOSED = 'CLOSED', 'Quán đã đóng cửa / Ngừng hoạt động'
    WRONG_INFO = 'WRONG_INFO', 'Sai lệch thông tin (Địa chỉ, số điện thoại, giá)'
    SPAM = 'SPAM', 'Nội dung spam, quảng cáo rác hoặc trùng lặp'
    OTHER = 'OTHER', 'Vấn đề khác'


class PlaceReport(models.Model):
    """
    Phản ánh và báo cáo sai lệch thông tin từ người dùng cho địa điểm.
    """
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name="Địa điểm bị báo cáo"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='place_reports',
        verbose_name="Người báo cáo"
    )
    report_type = models.CharField(
        max_length=30,
        choices=ReportTypeChoices.choices,
        default=ReportTypeChoices.WRONG_INFO,
        verbose_name="Loại phản ánh"
    )
    description = models.TextField(
        blank=True,
        default='',
        verbose_name="Chi tiết phản ánh"
    )
    status = models.CharField(
        max_length=20,
        default='PENDING',
        choices=[
            ('PENDING', 'Đang xử lý'),
            ('RESOLVED', 'Đã xác minh và cập nhật'),
            ('DISMISSED', 'Bác bỏ / Không chính xác'),
        ],
        db_index=True,
        verbose_name="Trạng thái xử lý"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian báo cáo")

    class Meta:
        verbose_name = "Báo cáo sai lệch địa điểm"
        verbose_name_plural = "Danh sách báo cáo địa điểm"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} báo cáo {self.place.name} ({self.get_report_type_display()})"

