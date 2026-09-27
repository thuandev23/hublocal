from rest_framework import serializers
from .models import User, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    verification_status_display = serializers.CharField(source='get_verification_status_display', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'residing_district',
            'residing_months',
            'verification_status',
            'verification_status_display',
            'is_local_verified',
            'verified_at',
            'verification_rejected_reason',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'verification_status',
            'verification_status_display',
            'is_local_verified',
            'verified_at',
            'verification_rejected_reason',
            'created_at',
            'updated_at'
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number', 'first_name', 'last_name', 'profile', 'permissions']
        read_only_fields = ['id', 'permissions']

    def get_permissions(self, obj):
        profile = getattr(obj, 'profile', None)
        is_verified = bool(profile and profile.is_local_verified)
        return {
            'can_verify_places': is_verified,
            'can_add_tips': True,  # Mọi user đã xác thực tài khoản đều được đóng góp tip
        }


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    phone_number = serializers.CharField(required=True)
    residing_district = serializers.CharField(required=False, default='Thủ Đức')
    residing_months = serializers.IntegerField(required=False, default=0, min_value=0)

    class Meta:
        model = User
        fields = [
            'username',
            'phone_number',
            'password',
            'first_name',
            'last_name',
            'residing_district',
            'residing_months'
        ]

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Số điện thoại này đã được đăng ký.")
        return value

    def create(self, validated_data):
        residing_district = validated_data.pop('residing_district', 'Thủ Đức')
        residing_months = validated_data.pop('residing_months', 0)
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        UserProfile.objects.create(
            user=user,
            residing_district=residing_district,
            residing_months=residing_months
        )
        return user


class LocalVerificationSubmitSerializer(serializers.Serializer):
    """
    Serializer cho Màn hình 3: Gửi hồ sơ xác minh cư dân local.
    Đưa trạng thái vào 'pending' để hệ thống thẩm định, không tự cấp badge.
    """
    phone_number = serializers.CharField(required=True)
    residing_district = serializers.CharField(required=True)
    residing_months = serializers.IntegerField(required=True, min_value=0)

    def update_profile(self, user):
        from .models import VerificationStatus

        user.phone_number = self.validated_data['phone_number']
        user.save(update_fields=['phone_number'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.residing_district = self.validated_data['residing_district']
        profile.residing_months = self.validated_data['residing_months']
        # Trạng thái chuyển thành pending chờ kiểm duyệt/xác minh, không tự phong verified
        profile.verification_status = VerificationStatus.PENDING
        profile.save()
        return profile


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True, help_text="Refresh token cần thu hồi")

