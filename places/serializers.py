from rest_framework import serializers
from .models import Place, PlaceVerification, Tip


def mask_phone_or_name(user):
    """
    Hiển thị tên hoặc ẩn danh thông tin tác giả để bảo mật quyền riêng tư nhưng vẫn tạo độ tin cậy và tự nhiên.
    Ưu tiên: 'Minh T.' hoặc '0903***123'
    """
    if user.first_name:
        last_initial = f" {user.last_name[:1]}." if user.last_name else ""
        return f"{user.first_name}{last_initial}"
    if user.phone_number and len(user.phone_number) >= 7:
        return f"{user.phone_number[:4]}***{user.phone_number[-3:]}"
    if len(user.username) > 4:
        return f"{user.username[:2]}***{user.username[-2:]}"
    return user.username


class TipSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    residing_info = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Tip
        fields = [
            'id',
            'author_name',
            'residing_info',
            'content',
            'is_mine',
            'created_at',
            'updated_at'
        ]

    def get_author_name(self, obj):
        return mask_phone_or_name(obj.user)

    def get_residing_info(self, obj):
        profile = getattr(obj.user, 'profile', None)
        if profile and profile.residing_months:
            return f"Cư dân {profile.residing_district} ({profile.residing_months} tháng)"
        return "Cư dân địa phương"

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user_id == request.user.id
        return False


class TipCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tip
        fields = ['content']

    def validate_content(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Nội dung mẹo cần tối thiểu 5 ký tự hữu ích.")
        return value.strip()


class PlaceListSerializer(serializers.ModelSerializer):
    """
    Serializer tinh gọn (Lean) cho Màn hình 1 (Danh sách địa điểm).
    Tối ưu hóa tối đa payload mạng và tốc độ render giao diện Flutter.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    trust_tier_display = serializers.CharField(source='get_trust_tier_display', read_only=True)
    short_tip = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = [
            'id',
            'name',
            'category',
            'category_display',
            'district',
            'address',
            'cover_image',
            'trust_tier',
            'trust_tier_display',
            'verified_count',
            'last_verified_at',
            'short_tip',
        ]

    def get_short_tip(self, obj):
        tips = getattr(obj, '_prefetched_objects_cache', {}).get('tips')
        if tips is not None:
            first_tip = tips[0] if len(tips) > 0 else None
        else:
            first_tip = obj.tips.first()
        return first_tip.content if first_tip else ""


class PlaceDetailSerializer(serializers.ModelSerializer):
    """
    Serializer chi tiết cho Màn hình 2 (Chi tiết địa điểm).
    Bao gồm danh sách mẹo từ cư dân, tọa độ bản đồ, trạng thái xác thực của user hiện tại.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    trust_tier_display = serializers.CharField(source='get_trust_tier_display', read_only=True)
    tips = TipSerializer(many=True, read_only=True)
    user_has_verified = serializers.SerializerMethodField()
    my_tip = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = [
            'id',
            'name',
            'category',
            'category_display',
            'district',
            'address',
            'latitude',
            'longitude',
            'cover_image',
            'trust_tier',
            'trust_tier_display',
            'verified_count',
            'last_verified_at',
            'tips',
            'user_has_verified',
            'my_tip',
            'created_at',
            'updated_at',
        ]

    def get_user_has_verified(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.verifications.filter(user=request.user).exists()
        return False

    def get_my_tip(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            tip = obj.tips.filter(user=request.user).first()
            if tip:
                return TipSerializer(tip, context=self.context).data
        return None
