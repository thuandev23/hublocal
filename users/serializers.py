from rest_framework import serializers
from .models import User, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'residing_district',
            'residing_months',
            'is_local_verified',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['is_local_verified', 'created_at', 'updated_at']


class UserDetailSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number', 'first_name', 'last_name', 'profile']
        read_only_fields = ['id']


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
    Serializer cho Màn hình 3: Xác thực trở thành local.
    Người dùng gửi số điện thoại, khu vực đang sống, thời gian đã sống.
    """
    phone_number = serializers.CharField(required=True)
    residing_district = serializers.CharField(required=True)
    residing_months = serializers.IntegerField(required=True, min_value=0)

    def update_profile(self, user):
        user.phone_number = self.validated_data['phone_number']
        user.save(update_fields=['phone_number'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.residing_district = self.validated_data['residing_district']
        profile.residing_months = self.validated_data['residing_months']
        profile.save()
        return profile
