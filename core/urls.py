"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="HubLocal API Documentation",
        default_version='v1',
        description="Hệ thống API khám phá địa điểm được xác thực bởi cư dân địa phương (Thủ Đức, TP.HCM)",
        contact=openapi.Contact(email="contact@hublocal.vn"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Django Admin Dashboard
    path('admin/', admin.site.urls),

    # Swagger / OpenAPI documentation
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # API v1 routes
    path('api/v1/', include('users.urls', namespace='users')),
    path('api/v1/', include('places.urls', namespace='places')),
    path('api/v1/notifications/', include('notifications.urls', namespace='notifications')),
]
