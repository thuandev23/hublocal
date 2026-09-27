from django.urls import path
from .views import (
    DeviceTokenView,
    NotificationListView,
    MarkNotificationReadView,
)

app_name = 'notifications'

urlpatterns = [
    path('devices/', DeviceTokenView.as_view(), name='device_tokens'),
    path('', NotificationListView.as_view(), name='list'),
    path('<int:pk>/read/', MarkNotificationReadView.as_view(), name='mark_read'),
    path('read-all/', MarkNotificationReadView.as_view(), name='mark_read_all'),
]
