from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Place, PlaceVerification, Tip, TrustTier


class TipInline(admin.TabularInline):
    model = Tip
    extra = 1
    fields = ('user', 'content', 'updated_at')
    readonly_fields = ('updated_at',)


class PlaceVerificationInline(admin.TabularInline):
    model = PlaceVerification
    extra = 1
    fields = ('user', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'district',
        'get_gps',
        'get_trust_badge',
        'verified_count',
        'updated_at'
    )
    list_filter = ('category', 'trust_tier', 'district')
    search_fields = ('name', 'address')
    readonly_fields = ('verified_count', 'trust_tier', 'last_verified_at', 'google_scraped_at', 'imported_at', 'created_at', 'updated_at')
    inlines = [TipInline, PlaceVerificationInline]
    actions = ['recalculate_metrics_action']

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'category', 'district', 'address', 'cover_image')
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

    def get_gps(self, obj):
        if obj.latitude and obj.longitude:
            return f"{obj.latitude:.4f}, {obj.longitude:.4f}"
        return "-"
    get_gps.short_description = "Tọa độ GPS"

    def get_trust_badge(self, obj):
        if obj.trust_tier == TrustTier.TIER_2_HIGH_TRUST:
            return format_html('<span style="color: #10B981; font-weight: bold;">⭐ Tier 2 ({} Locals)</span>', obj.verified_count)
        elif obj.trust_tier == TrustTier.TIER_1_VERIFIED:
            return mark_safe('<span style="color: #3B82F6; font-weight: bold;">✓ Tier 1 (1-2 Locals)</span>')
        return mark_safe('<span style="color: #9CA3AF;">Tier 0 (Chưa xác thực)</span>')

    get_trust_badge.short_description = "Huy hiệu Tín nhiệm"

    @admin.action(description="Tính toán lại chỉ số tín nhiệm và lượt xác thực")
    def recalculate_metrics_action(self, request, queryset):
        for place in queryset:
            place.recalculate_trust_metrics()
            place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at'])
        self.message_user(request, f"Đã tính toán lại dữ liệu cho {queryset.count()} địa điểm.")


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
