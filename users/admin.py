from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User, UserProfile, VerificationStatus


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Hồ sơ cư dân"
    verbose_name_plural = "Hồ sơ cư dân"
    fields = (
        'residing_district',
        'residing_months',
        'verification_status',
        'is_local_verified',
        'verified_at',
        'verification_rejected_reason',
        'has_seen_verification_modal',
    )
    readonly_fields = ('is_local_verified', 'created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = (
        'username',
        'phone_number',
        'get_full_name_custom',
        'get_district',
        'get_verification_status_badge',
        'is_staff',
        'date_joined'
    )
    list_filter = (
        'profile__verification_status',
        'profile__is_local_verified',
        'profile__residing_district',
        'is_staff',
        'is_active'
    )
    search_fields = ('username', 'phone_number', 'first_name', 'last_name', 'email')
    actions = ['approve_user_residents_action', 'reject_user_residents_action']

    def get_full_name_custom(self, obj):
        name = f"{obj.last_name} {obj.first_name}".strip()
        return name if name else "-"
    get_full_name_custom.short_description = "Họ và tên"

    def get_district(self, obj):
        return getattr(obj.profile, 'residing_district', '-')
    get_district.short_description = "Khu vực"

    def get_verification_status_badge(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile:
            return mark_safe('<span style="color: #9CA3AF;">Chưa có hồ sơ</span>')
        return profile_badge_html(profile.verification_status)
    get_verification_status_badge.short_description = "Xác thực cư dân"

    @admin.action(description="✅ Phê duyệt cư dân cho các tài khoản đã chọn")
    def approve_user_residents_action(self, request, queryset):
        count = 0
        for user in queryset.select_related('profile'):
            profile = getattr(user, 'profile', None)
            if profile and profile.verification_status != VerificationStatus.VERIFIED:
                profile.verification_status = VerificationStatus.VERIFIED
                profile.verified_at = timezone.now()
                profile.verification_rejected_reason = ''
                profile.has_seen_verification_modal = False
                profile.save()
                count += 1
        self.message_user(request, f"Đã phê duyệt và gửi thông báo tới {count} cư dân thành công.", messages.SUCCESS)

    @admin.action(description="❌ Từ chối xác thực cư dân cho các tài khoản đã chọn")
    def reject_user_residents_action(self, request, queryset):
        count = 0
        for user in queryset.select_related('profile'):
            profile = getattr(user, 'profile', None)
            if profile and profile.verification_status != VerificationStatus.REJECTED:
                profile.verification_status = VerificationStatus.REJECTED
                profile.verification_rejected_reason = "Hồ sơ chưa đáp ứng đầy đủ yêu cầu xác minh cư dân địa phương."
                profile.save()
                count += 1
        self.message_user(request, f"Đã từ chối xác thực cho {count} tài khoản.", messages.WARNING)


def profile_badge_html(status):
    """Tạo badge trạng thái xác thực cư dân trực quan, thẩm mỹ."""
    if status == VerificationStatus.VERIFIED:
        return mark_safe(
            '<span style="background-color: #D1FAE5; color: #065F46; padding: 3px 10px; border-radius: 9999px; font-weight: 600; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;">'
            '● Đã xác thực</span>'
        )
    elif status == VerificationStatus.PENDING:
        return mark_safe(
            '<span style="background-color: #FEF3C7; color: #92400E; padding: 3px 10px; border-radius: 9999px; font-weight: 600; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;">'
            '⏳ Chờ phê duyệt</span>'
        )
    elif status == VerificationStatus.REJECTED:
        return mark_safe(
            '<span style="background-color: #FEE2E2; color: #991B1B; padding: 3px 10px; border-radius: 9999px; font-weight: 600; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;">'
            '✕ Bị từ chối</span>'
        )
    return mark_safe(
        '<span style="background-color: #F3F4F6; color: #4B5563; padding: 3px 10px; border-radius: 9999px; font-weight: 500; font-size: 11px;">'
        'Chưa gửi xác thực</span>'
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'get_user_info',
        'residing_district',
        'get_residing_time',
        'get_status_badge',
        'quick_actions',
        'verified_at',
        'created_at'
    )
    list_filter = (
        'verification_status',
        'residing_district',
        'is_local_verified',
        'created_at'
    )
    search_fields = (
        'user__username',
        'user__phone_number',
        'user__first_name',
        'user__last_name',
        'residing_district'
    )
    readonly_fields = ('is_local_verified', 'created_at', 'updated_at')
    actions = [
        'approve_residents_action',
        'reject_residents_action',
        'revoke_residents_action'
    ]

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('user', 'residing_district', 'residing_months')
        }),
        ('Trạng thái xác minh cư dân', {
            'fields': (
                'verification_status',
                'is_local_verified',
                'verified_at',
                'verification_rejected_reason',
                'has_seen_verification_modal'
            )
        }),
        ('Thời gian hệ thống', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user_info(self, obj):
        name = f"{obj.user.last_name} {obj.user.first_name}".strip()
        phone = obj.user.phone_number or "Không có SĐT"
        display_name = f"{name} ({obj.user.username})" if name else obj.user.username
        return format_html('<strong>{}</strong><br><small style="color: #6B7280;">📱 {}</small>', display_name, phone)
    get_user_info.short_description = "Cư dân"

    def get_residing_time(self, obj):
        if obj.residing_months >= 12:
            years = obj.residing_months // 12
            months = obj.residing_months % 12
            if months > 0:
                return f"{years} năm {months} tháng"
            return f"{years} năm"
        return f"{obj.residing_months} tháng"
    get_residing_time.short_description = "Thời gian cư trú"

    def get_status_badge(self, obj):
        return profile_badge_html(obj.verification_status)
    get_status_badge.short_description = "Trạng thái xác thực"

    def quick_actions(self, obj):
        """Cung cấp nút bấm duyệt hoặc từ chối nhanh 1-click ngay trên danh sách."""
        if obj.verification_status == VerificationStatus.PENDING:
            approve_url = reverse('admin:userprofile-approve', args=[obj.pk])
            reject_url = reverse('admin:userprofile-reject', args=[obj.pk])
            return format_html(
                '<a class="button" style="background-color: #10B981; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold; margin-right: 4px;" href="{}">Duyệt</a>'
                '<a class="button" style="background-color: #EF4444; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; font-weight: bold;" href="{}">Từ chối</a>',
                approve_url,
                reject_url
            )
        elif obj.verification_status == VerificationStatus.VERIFIED:
            revoke_url = reverse('admin:userprofile-revoke', args=[obj.pk])
            return format_html(
                '<a class="button" style="background-color: #6B7280; color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; font-size: 11px;" href="{}">Hủy duyệt</a>',
                revoke_url
            )
        elif obj.verification_status == VerificationStatus.REJECTED:
            approve_url = reverse('admin:userprofile-approve', args=[obj.pk])
            return format_html(
                '<a class="button" style="background-color: #3B82F6; color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; font-size: 11px;" href="{}">Duyệt lại</a>',
                approve_url
            )
        return "-"
    quick_actions.short_description = "Thao tác nhanh"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:profile_id>/approve/',
                self.admin_site.admin_view(self.process_approve),
                name='userprofile-approve'
            ),
            path(
                '<int:profile_id>/reject/',
                self.admin_site.admin_view(self.process_reject),
                name='userprofile-reject'
            ),
            path(
                '<int:profile_id>/revoke/',
                self.admin_site.admin_view(self.process_revoke),
                name='userprofile-revoke'
            ),
        ]
        return custom_urls + urls

    def process_approve(self, request, profile_id):
        profile = get_object_or_404(UserProfile, pk=profile_id)
        profile.verification_status = VerificationStatus.VERIFIED
        profile.verified_at = timezone.now()
        profile.verification_rejected_reason = ''
        profile.has_seen_verification_modal = False
        profile.save()
        self.message_user(
            request,
            f"✅ Đã phê duyệt cư dân {profile.user.username} ({profile.residing_district}) và kích hoạt thông báo Push.",
            messages.SUCCESS
        )
        return redirect(request.META.get('HTTP_REFERER', 'admin:users_userprofile_changelist'))

    def process_reject(self, request, profile_id):
        profile = get_object_or_404(UserProfile, pk=profile_id)
        profile.verification_status = VerificationStatus.REJECTED
        profile.verification_rejected_reason = "Thông tin cư trú chưa đủ tin cậy hoặc hình ảnh xác minh chưa rõ ràng."
        profile.save()
        self.message_user(
            request,
            f"❌ Đã từ chối xác thực cư dân {profile.user.username}.",
            messages.WARNING
        )
        return redirect(request.META.get('HTTP_REFERER', 'admin:users_userprofile_changelist'))

    def process_revoke(self, request, profile_id):
        profile = get_object_or_404(UserProfile, pk=profile_id)
        profile.verification_status = VerificationStatus.UNVERIFIED
        profile.save()
        self.message_user(
            request,
            f"🔄 Đã thu hồi quyền cư dân của {profile.user.username}.",
            messages.INFO
        )
        return redirect(request.META.get('HTTP_REFERER', 'admin:users_userprofile_changelist'))

    @admin.action(description="✅ Phê duyệt các hồ sơ cư dân đã chọn (Gửi Push Notification)")
    def approve_residents_action(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.verification_status != VerificationStatus.VERIFIED:
                profile.verification_status = VerificationStatus.VERIFIED
                profile.verified_at = timezone.now()
                profile.verification_rejected_reason = ''
                profile.has_seen_verification_modal = False
                profile.save()
                count += 1
        self.message_user(request, f"Đã phê duyệt {count} hồ sơ cư dân thành công.", messages.SUCCESS)

    @admin.action(description="❌ Từ chối các hồ sơ cư dân đã chọn (Gửi Push Notification)")
    def reject_residents_action(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.verification_status != VerificationStatus.REJECTED:
                profile.verification_status = VerificationStatus.REJECTED
                profile.verification_rejected_reason = "Thông tin cư trú chưa đáp ứng tiêu chuẩn cộng đồng HubLocal."
                profile.save()
                count += 1
        self.message_user(request, f"Đã từ chối {count} hồ sơ cư dân.", messages.WARNING)

    @admin.action(description="🔄 Thu hồi quyền cư dân (Chuyển về Chưa gửi xác thực)")
    def revoke_residents_action(self, request, queryset):
        count = 0
        for profile in queryset:
            profile.verification_status = VerificationStatus.UNVERIFIED
            profile.save()
            count += 1
        self.message_user(request, f"Đã thu hồi quyền cư dân của {count} tài khoản.", messages.INFO)
