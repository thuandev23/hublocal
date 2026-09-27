import math
from rest_framework import serializers
from .models import Place, PlaceVerification, Tip, SavedPlace, PlaceReport, ReportTypeChoices


def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách đường chim bay giữa hai tọa độ địa lý (Haversine formula).
    Đơn vị trả về: Kilometers (km), làm tròn 2 chữ số thập phân.
    """
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (ValueError, TypeError):
        return None

    R = 6371.0  # Bán kính Trái Đất (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


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
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Nội dung mẹo cần tối thiểu 5 ký tự hữu ích.")
        if len(cleaned) > 1000:
            raise serializers.ValidationError("Nội dung mẹo tối đa không vượt quá 1000 ký tự.")
        return cleaned


class PlaceListSerializer(serializers.ModelSerializer):
    """
    Serializer tinh gọn (Lean) cho Màn hình 1 (Danh sách địa điểm).
    Tối ưu hóa tối đa payload mạng và tốc độ render giao diện Flutter.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    trust_tier_display = serializers.CharField(source='get_trust_tier_display', read_only=True)
    short_tip = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = [
            'id',
            'name',
            'category',
            'category_display',
            'status',
            'status_display',
            'district',
            'district_code',
            'address',
            'latitude',
            'longitude',
            'cover_image',
            'thumbnail_image',
            'min_price',
            'max_price',
            'price_currency',
            'opening_hours_text',
            'google_maps_url',
            'google_rating',
            'google_review_count',
            'trust_tier',
            'trust_tier_display',
            'verified_count',
            'last_verified_at',
            'short_tip',
            'is_saved',
            'distance_km',
        ]

    def get_short_tip(self, obj):
        tips = getattr(obj, '_prefetched_objects_cache', {}).get('tips')
        if tips is not None:
            first_tip = tips[0] if len(tips) > 0 else None
        else:
            first_tip = obj.tips.first()
        return first_tip.content if first_tip else ""

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        saved_place_ids = self.context.get('saved_place_ids')
        if saved_place_ids is not None:
            return obj.id in saved_place_ids
        return obj.saved_by.filter(user=request.user).exists()

    def get_distance_km(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        user_lat = request.query_params.get('lat')
        user_lng = request.query_params.get('lng')
        if user_lat and user_lng and obj.latitude and obj.longitude:
            return calculate_haversine_distance(user_lat, user_lng, obj.latitude, obj.longitude)
        return None


class PlaceDetailSerializer(serializers.ModelSerializer):
    """
    Serializer chi tiết cho Màn hình 2 (Chi tiết địa điểm).
    Bao gồm danh sách mẹo từ cư dân, khoảng giá, giờ mở cửa, trạng thái hoạt động,
    tọa độ bản đồ, thông tin và review từ Google Maps, trạng thái xác thực.
    """
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    trust_tier_display = serializers.CharField(source='get_trust_tier_display', read_only=True)
    tips = TipSerializer(many=True, read_only=True)
    user_has_verified = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    my_tip = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = [
            'id',
            'name',
            'category',
            'category_display',
            'status',
            'status_display',
            'district',
            'district_code',
            'address',
            'latitude',
            'longitude',
            'cover_image',
            'thumbnail_image',
            'photos',
            'min_price',
            'max_price',
            'price_currency',
            'price_updated_at',
            'opening_hours_text',
            'opening_hours_structured',
            'data_source',
            'google_maps_url',
            'google_rating',
            'google_review_count',
            'google_reviews',
            'google_scraped_at',
            'imported_at',
            'trust_tier',
            'trust_tier_display',
            'verified_count',
            'last_verified_at',
            'tips',
            'user_has_verified',
            'is_saved',
            'distance_km',
            'my_tip',
            'created_at',
            'updated_at',
        ]

    def get_user_has_verified(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.verifications.filter(user=request.user).exists()
        return False

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.saved_by.filter(user=request.user).exists()
        return False

    def get_distance_km(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        user_lat = request.query_params.get('lat')
        user_lng = request.query_params.get('lng')
        if user_lat and user_lng and obj.latitude and obj.longitude:
            return calculate_haversine_distance(user_lat, user_lng, obj.latitude, obj.longitude)
        return None

    def get_my_tip(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            tip = obj.tips.filter(user=request.user).first()
            if tip:
                return TipSerializer(tip, context=self.context).data
        return None


class PlaceReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceReport
        fields = ['report_type', 'description']

    def validate_description(self, value):
        cleaned = value.strip()
        if len(cleaned) > 1000:
            raise serializers.ValidationError("Nội dung phản ánh tối đa không vượt quá 1000 ký tự.")
        return cleaned

