from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Hồ sơ cư dân"
    verbose_name_plural = "Hồ sơ cư dân"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ('username', 'phone_number', 'first_name', 'last_name', 'get_district', 'get_local_status', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'profile__is_local_verified', 'profile__residing_district')
    search_fields = ('username', 'phone_number', 'first_name', 'last_name')

    def get_district(self, obj):
        return getattr(obj.profile, 'residing_district', '-')
    get_district.short_description = "Khu vực"

    def get_local_status(self, obj):
        return getattr(obj.profile, 'is_local_verified', False)
    get_local_status.short_description = "Local Verified"
    get_local_status.boolean = True


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'residing_district', 'residing_months', 'is_local_verified', 'created_at')
    list_filter = ('is_local_verified', 'residing_district')
    search_fields = ('user__username', 'user__phone_number', 'residing_district')
