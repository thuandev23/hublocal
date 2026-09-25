from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserProfile
from .serializers import (
    RegisterSerializer,
    UserDetailSerializer,
    UserProfileSerializer,
    LocalVerificationSubmitSerializer
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
    API Màn hình 3: Gửi thông tin xác thực trở thành Local (SĐT, Khu vực, Số tháng sống).
    Tự động cấp trạng thái Local nếu cư trú >= 6 tháng.
    """
    serializer_class = LocalVerificationSubmitSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.update_profile(request.user)

        return Response({
            'is_local_verified': profile.is_local_verified,
            'residing_district': profile.residing_district,
            'residing_months': profile.residing_months,
            'message': 'Chúc mừng bạn đã đạt chứng nhận Local Verified!' if profile.is_local_verified else 'Hồ sơ đã được cập nhật. Cần thời gian cư trú tối thiểu 6 tháng để nhận huy hiệu Local.'
        }, status=status.HTTP_200_OK)
