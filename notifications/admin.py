from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import DeviceToken, Notification, PlatformChoices
from .services import send_push_notification


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'get_platform_badge',
        'token_preview',
        'get_active_badge',
        'created_at',
        'updated_at'
    )
    list_filter = ('platform', 'is_active', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'token')
    actions = ['activate_tokens_action', 'deactivate_tokens_action']

    def get_platform_badge(self, obj):
        if obj.platform == PlatformChoices.ANDROID:
            return mark_safe('<span style="color: #10B981; font-weight: bold;">🤖 Android</span>')
        elif obj.platform == PlatformChoices.IOS:
            return mark_safe('<span style="color: #6366F1; font-weight: bold;">🍎 iOS</span>')
        return mark_safe('<span style="color: #3B82F6;">🌐 Web</span>')
    get_platform_badge.short_description = "Hệ điều hành"

    def token_preview(self, obj):
        return f"{obj.token[:14]}...{obj.token[-8:]}" if len(obj.token) > 22 else obj.token
    token_preview.short_description = "FCM Token"

    def get_active_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #10B981; font-weight: bold;">● Đang hoạt động</span>')
        return mark_safe('<span style="color: #9CA3AF;">✕ Đã tắt</span>')
    get_active_badge.short_description = "Trạng thái"

    @admin.action(description="Kích hoạt lại các thiết bị đã chọn")
    def activate_tokens_action(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Đã kích hoạt {updated} thiết bị.", messages.SUCCESS)

    @admin.action(description="Vô hiệu hóa các thiết bị đã chọn")
    def deactivate_tokens_action(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Đã hủy kích hoạt {updated} thiết bị.", messages.INFO)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'title',
        'get_body_preview',
        'get_type_badge',
        'get_read_badge',
        'created_at'
    )
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'title', 'body')
    readonly_fields = ('created_at',)
    actions = ['resend_notification_action', 'mark_as_read_action']

    def get_body_preview(self, obj):
        return obj.body[:80] + '...' if len(obj.body) > 80 else obj.body
    get_body_preview.short_description = "Nội dung"

    def get_type_badge(self, obj):
        noti_type = obj.data.get('type', 'SYSTEM') if isinstance(obj.data, dict) else 'SYSTEM'
        color_map = {
            'VERIFICATION_APPROVED': '#10B981',
            'VERIFICATION_REJECTED': '#EF4444',
            'PLACE_TIER_UPGRADED': '#F59E0B',
            'SYSTEM': '#6366F1',
        }
        color = color_map.get(noti_type, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 10px; font-weight: bold;">{}</span>',
            color,
            noti_type
        )
    get_type_badge.short_description = "Phân loại"

    def get_read_badge(self, obj):
        if obj.is_read:
            return mark_safe('<span style="color: #6B7280;">✓ Đã đọc</span>')
        return mark_safe('<span style="color: #EF4444; font-weight: bold;">● Chưa đọc</span>')
    get_read_badge.short_description = "Đã đọc"

    @admin.action(description="📤 Gửi lại Push Notification cho các thông báo đã chọn")
    def resend_notification_action(self, request, queryset):
        success_count = 0
        for noti in queryset:
            send_push_notification(
                user=noti.user,
                title=noti.title,
                body=noti.body,
                data=noti.data
            )
            success_count += 1
        self.message_user(request, f"Đã gửi lại thành công {success_count} thông báo Push.", messages.SUCCESS)

    @admin.action(description="Đánh dấu đã đọc")
    def mark_as_read_action(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"Đã đánh dấu đã đọc {updated} thông báo.", messages.SUCCESS)
