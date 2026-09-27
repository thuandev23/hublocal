from rest_framework import serializers
from .models import DeviceToken, Notification, PlatformChoices


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['token', 'platform']

    def validate_platform(self, value):
        if value not in PlatformChoices.values:
            raise serializers.ValidationError(f"Platform không hợp lệ. Chọn một trong: {PlatformChoices.values}")
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'data', 'is_read', 'created_at']
        read_only_fields = ['id', 'title', 'body', 'data', 'created_at']
