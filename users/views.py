from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserProfile
from .serializers import (
    RegisterSerializer,
    UserDetailSerializer,
    UserProfileSerializer,
    LocalVerificationSubmitSerializer,
    LogoutSerializer
)


class RegisterView(generics.CreateAPIView):
    """
    API Đăng ký tài khoản người dùng và khởi tạo hồ sơ cư dân.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Tạo JWT token tự động sau khi đăng ký
        refresh = RefreshToken.for_user(user)
        user_data = UserDetailSerializer(user).data

        return Response({
            'user': user_data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'message': 'Đăng ký tài khoản thành công.'
        }, status=status.HTTP_201_CREATED)


class MeView(generics.RetrieveAPIView):
    """
    API Lấy thông tin tài khoản hiện tại, profile, trạng thái xác thực và quyền hạn.
    Endpoint: GET /api/v1/auth/me/
    """
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if hasattr(user, 'profile'):
            user.profile.refresh_from_db()
        return user


class LogoutView(generics.GenericAPIView):
    """
    API Đăng xuất và thu hồi Refresh Token (Blacklist).
    Endpoint: POST /api/v1/auth/logout/
    """
    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
            return Response({
                'message': 'Đăng xuất thành công, phiên làm việc đã được đóng an toàn.'
            }, status=status.HTTP_200_OK)
        except Exception:
            return Response({
                'code': 'INVALID_TOKEN',
                'message': 'Token không hợp lệ hoặc đã hết hạn.',
                'field_errors': {'refresh': ['Token không hợp lệ hoặc đã nằm trong blacklist.']}
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API Lấy và cập nhật thông tin hồ sơ của chính người dùng đang đăng nhập.
    """
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class SubmitLocalVerificationView(generics.GenericAPIView):
    """
    API Màn hình 3: Gửi hồ sơ xác minh cư dân Local (SĐT, Khu vực, Số tháng sống).
    Hệ thống ghi nhận trạng thái 'pending' để xác minh độc lập, không tự cấp badge.
    """
    serializer_class = LocalVerificationSubmitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.update_profile(request.user)

        return Response({
            'verification_status': profile.verification_status,
            'verification_status_display': profile.get_verification_status_display(),
            'is_local_verified': profile.is_local_verified,
            'residing_district': profile.residing_district,
            'residing_months': profile.residing_months,
            'message': 'Hồ sơ xác minh cư dân đã được tiếp nhận và chuyển sang trạng thái chờ duyệt. HubLocal tuyệt đối không cấp huy hiệu tự động để bảo đảm uy tín của cộng đồng.'
        }, status=status.HTTP_200_OK)


class AcknowledgeCelebrationView(generics.GenericAPIView):
    """
    API Đánh dấu người dùng đã xem Pop-up vinh danh xác thực cư dân thành công (tránh hiện lặp lại).
    Endpoint: POST /api/v1/auth/ack-celebration/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.has_seen_verification_modal = True
        profile.save(update_fields=['has_seen_verification_modal', 'updated_at'])
        return Response({
            'success': True,
            'show_celebration_modal': False,
            'message': 'Đã ghi nhận đã xem màn hình vinh danh.'
        }, status=status.HTTP_200_OK)


