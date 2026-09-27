from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationSerializer


class DeviceTokenView(APIView):
    """
    API Đăng ký và Hủy đăng ký thiết bị nhận Push Notification qua Firebase:
    - POST: Đăng ký FCM Token khi mở app hoặc login.
    - DELETE: Hủy kích hoạt FCM Token khi logout.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        platform = serializer.validated_data.get('platform', 'android')

        # Cập nhật hoặc tạo mới token liên kết với user hiện tại
        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'platform': platform,
                'is_active': True
            }
        )

        return Response({
            'message': 'Đăng ký thiết bị nhận thông báo thành công.',
            'platform': device.platform
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        token = request.data.get('token')
        if not token:
            return Response({
                'code': 'VALIDATION_ERROR',
                'message': 'Thiếu tham số token cần xóa.',
                'field_errors': {'token': ['Vui lòng cung cấp FCM token.']}
            }, status=status.HTTP_400_BAD_REQUEST)

        DeviceToken.objects.filter(token=token, user=request.user).update(is_active=False)
        return Response({
            'message': 'Đã hủy kích hoạt thông báo cho thiết bị này.'
        }, status=status.HTTP_200_OK)


class NotificationListView(generics.ListAPIView):
    """
    API Lấy danh sách hộp thư thông báo in-app của người dùng hiện tại (kèm phân trang).
    Endpoint: GET /api/v1/notifications/
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class MarkNotificationReadView(APIView):
    """
    API Đánh dấu đã đọc thông báo:
    - POST /notifications/{id}/read/
    - POST /notifications/read-all/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        if pk == 'all' or pk is None and request.path.endswith('read-all/'):
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            return Response({'message': 'Đã đánh dấu đọc tất cả thông báo.'}, status=status.HTTP_200_OK)

        try:
            notification = Notification.objects.get(id=pk, user=request.user)
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            return Response({'message': 'Đã đánh dấu đọc thông báo.'}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({
                'code': 'NOT_FOUND',
                'message': 'Không tìm thấy thông báo.',
                'field_errors': {}
            }, status=status.HTTP_404_NOT_FOUND)
