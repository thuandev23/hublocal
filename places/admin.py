from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    Place, PlaceVerification, Tip, TrustTier,
    SavedPlace, PlaceReport, ReportTypeChoices
)


class TipInline(admin.TabularInline):
    model = Tip
    extra = 0
    fields = ('user', 'content', 'updated_at')
    readonly_fields = ('updated_at',)


class PlaceVerificationInline(admin.TabularInline):
    model = PlaceVerification
    extra = 0
    fields = ('user', 'created_at')
    readonly_fields = ('created_at',)


class PlaceReportInline(admin.TabularInline):
    model = PlaceReport
    extra = 0
    fields = ('user', 'report_type', 'description', 'status', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        'get_cover_thumbnail',
        'name',
        'category',
        'district',
        'get_gps',
        'get_trust_badge',
        'get_stats',
        'updated_at'
    )
    list_filter = ('category', 'trust_tier', 'district', 'status')
    search_fields = ('name', 'address', 'phone_number')
    readonly_fields = (
        'verified_count',
        'trust_tier',
        'last_verified_at',
        'google_scraped_at',
        'imported_at',
        'created_at',
        'updated_at',
        'get_cover_preview'
    )
    inlines = [TipInline, PlaceVerificationInline, PlaceReportInline]
    actions = ['recalculate_metrics_action', 'mark_as_open_action', 'mark_as_closed_action']

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'category', 'status', 'district', 'district_code', 'address', 'phone_number')
        }),
        ('Hình ảnh địa điểm', {
            'fields': ('cover_image', 'get_cover_preview', 'photos')
        }),
        ('Tọa độ địa lý (GPS)', {
            'fields': ('latitude', 'longitude'),
        }),
        ('Dữ liệu nguồn Google Maps (Tham khảo)', {
            'fields': ('google_maps_url', 'google_rating', 'google_review_count', 'google_scraped_at', 'imported_at'),
            'classes': ('collapse',)
        }),
        ('Chỉ số tín nhiệm (Auto)', {
            'fields': ('trust_tier', 'verified_count', 'last_verified_at', 'created_at', 'updated_at')
        }),
    )

    def get_cover_thumbnail(self, obj):
        img_url = obj.cover_image
        if not img_url and isinstance(obj.photos, list) and len(obj.photos) > 0:
            first = obj.photos[0]
            img_url = first.get('url') if isinstance(first, dict) else first

        if img_url:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);" />',
                img_url
            )
        return mark_safe('<span style="color: #9CA3AF; font-size: 11px;">Không có ảnh</span>')
    get_cover_thumbnail.short_description = "Ảnh"

    def get_cover_preview(self, obj):
        img_url = obj.cover_image
        if not img_url and isinstance(obj.photos, list) and len(obj.photos) > 0:
            first = obj.photos[0]
            img_url = first.get('url') if isinstance(first, dict) else first

        if img_url:
            return format_html('<img src="{}" style="max-height: 200px; border-radius: 8px;" />', img_url)
        return "Chưa có ảnh bìa"
    get_cover_preview.short_description = "Xem trước ảnh bìa"

    def get_gps(self, obj):
        if obj.latitude and obj.longitude:
            return f"{obj.latitude:.4f}, {obj.longitude:.4f}"
        return "-"
    get_gps.short_description = "Tọa độ GPS"

    def get_trust_badge(self, obj):
        if obj.trust_tier == TrustTier.TIER_2_HIGH_TRUST:
            return format_html('<span style="color: #059669; font-weight: bold; background-color: #D1FAE5; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">⭐ Tier 2 ({} Locals)</span>', obj.verified_count)
        elif obj.trust_tier == TrustTier.TIER_1_VERIFIED:
            return mark_safe('<span style="color: #2563EB; font-weight: bold; background-color: #DBEAFE; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">✓ Tier 1 (1-2 Locals)</span>')
        return mark_safe('<span style="color: #6B7280; background-color: #F3F4F6; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">Tier 0</span>')
    get_trust_badge.short_description = "Huy hiệu Tín nhiệm"

    def get_stats(self, obj):
        tips_count = getattr(obj, 'tips_count_annotated', obj.tips.count())
        saved_count = getattr(obj, 'saved_count_annotated', obj.saved_by.count())
        return format_html(
            '<span title="Số lượt xác thực">🛡️ <strong>{}</strong></span> | '
            '<span title="Số mẹo">💡 <strong>{}</strong></span> | '
            '<span title="Số lượt lưu">📌 <strong>{}</strong></span>',
            obj.verified_count,
            tips_count,
            saved_count
        )
    get_stats.short_description = "Tương tác (Local/Mẹo/Lưu)"

    @admin.action(description="🔄 Tính toán lại chỉ số tín nhiệm và lượt xác thực")
    def recalculate_metrics_action(self, request, queryset):
        for place in queryset:
            place.recalculate_trust_metrics()
            place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at'])
        self.message_user(request, f"Đã tính toán lại dữ liệu cho {queryset.count()} địa điểm.", messages.SUCCESS)

    @admin.action(description="🟢 Đánh dấu Đang hoạt động (OPEN)")
    def mark_as_open_action(self, request, queryset):
        count = queryset.update(status='OPEN')
        self.message_user(request, f"Đã cập nhật {count} địa điểm thành Đang hoạt động.", messages.SUCCESS)

    @admin.action(description="🔴 Đánh dấu Ngừng hoạt động (PERM_CLOSED)")
    def mark_as_closed_action(self, request, queryset):
        count = queryset.update(status='PERM_CLOSED')
        self.message_user(request, f"Đã cập nhật {count} địa điểm thành Ngừng hoạt động.", messages.WARNING)


@admin.register(PlaceVerification)
class PlaceVerificationAdmin(admin.ModelAdmin):
    list_display = ('place', 'user', 'created_at')
    list_filter = ('place__district', 'created_at')
    search_fields = ('place__name', 'user__username', 'user__phone_number')


@admin.register(Tip)
class TipAdmin(admin.ModelAdmin):
    list_display = ('place', 'user', 'short_content', 'updated_at')
    list_filter = ('place__district', 'updated_at')
    search_fields = ('place__name', 'user__username', 'content')

    def short_content(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
    short_content.short_description = "Nội dung mẹo"


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ('user', 'place', 'get_place_district', 'created_at')
    list_filter = ('place__district', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'place__name')

    def get_place_district(self, obj):
        return obj.place.district
    get_place_district.short_description = "Quận"


@admin.register(PlaceReport)
class PlaceReportAdmin(admin.ModelAdmin):
    list_display = (
        'place',
        'user',
        'get_report_type_badge',
        'short_description',
        'get_status_badge',
        'created_at'
    )
    list_filter = ('status', 'report_type', 'place__district', 'created_at')
    search_fields = ('place__name', 'user__username', 'description')
    actions = ['mark_resolved_action', 'mark_dismissed_action']

    def get_report_type_badge(self, obj):
        colors = {
            ReportTypeChoices.CLOSED: '#EF4444',
            ReportTypeChoices.WRONG_INFO: '#F59E0B',
            ReportTypeChoices.SPAM: '#8B5CF6',
            ReportTypeChoices.OTHER: '#6B7280',
        }
        color = colors.get(obj.report_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 11px;">{}</span>',
            color,
            obj.get_report_type_display()
        )
    get_report_type_badge.short_description = "Loại phản ánh"

    def short_description(self, obj):
        if not obj.description:
            return "-"
        return obj.description[:70] + '...' if len(obj.description) > 70 else obj.description
    short_description.short_description = "Chi tiết"

    def get_status_badge(self, obj):
        if obj.status == 'RESOLVED':
            return mark_safe('<span style="color: #059669; font-weight: bold; background-color: #D1FAE5; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">✓ Đã xử lý</span>')
        elif obj.status == 'DISMISSED':
            return mark_safe('<span style="color: #6B7280; background-color: #F3F4F6; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">✕ Bác bỏ</span>')
        return mark_safe('<span style="color: #D97706; font-weight: bold; background-color: #FEF3C7; padding: 3px 8px; border-radius: 9999px; font-size: 11px;">⏳ Chờ xử lý</span>')
    get_status_badge.short_description = "Trạng thái xử lý"

    @admin.action(description="✅ Đánh dấu Đã xác minh & Xử lý (RESOLVED)")
    def mark_resolved_action(self, request, queryset):
        count = queryset.update(status='RESOLVED')
        self.message_user(request, f"Đã đánh dấu {count} phản ánh thành Đã xử lý.", messages.SUCCESS)

    @admin.action(description="✕ Đánh dấu Bác bỏ / Không chính xác (DISMISSED)")
    def mark_dismissed_action(self, request, queryset):
        count = queryset.update(status='DISMISSED')
        self.message_user(request, f"Đã bác bỏ {count} phản ánh.", messages.INFO)
