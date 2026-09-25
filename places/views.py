from django.db.models import Prefetch
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import Place, PlaceVerification, Tip, CategoryChoices, TrustTier
from .serializers import (
    PlaceListSerializer,
    PlaceDetailSerializer,
    TipSerializer,
    TipCreateUpdateSerializer
)


class PlaceWriteActionThrottle(UserRateThrottle):
    """Giới hạn tần suất thao tác ghi (xác thực hoặc viết tip) để chống bot/spam"""
    rate = '60/hour'


class PlaceViewSet(viewsets.ModelViewSet):
    """
    API Quản lý và Khám phá Địa điểm HubLocal.
    - list: Tìm kiếm, lọc theo Danh mục và Khu vực (sử dụng Composite Index).
    - retrieve: Xem chi tiết mẹo từ cư dân, bản đồ và trạng thái xác thực.
    - verify: Nút "Tôi cũng biết chỗ này" dành cho cư dân local >= 6 tháng thuộc cùng khu vực.
    - tip: Thêm/Sửa/Xóa mẹo cá nhân cho địa điểm.
    """
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'address']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'categories']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action in ['verify', 'tip']:
            return [PlaceWriteActionThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action == 'list':
            return PlaceListSerializer
        return PlaceDetailSerializer

    def get_queryset(self):
        queryset = Place.objects.all()

        district = self.request.query_params.get('district', 'Thủ Đức')
        if district:
            queryset = queryset.filter(district__iexact=district.strip())

        category = self.request.query_params.get('category')
        if category and category in CategoryChoices.values:
            queryset = queryset.filter(category=category)

        trust_tier = self.request.query_params.get('trust_tier')
        if trust_tier is not None and trust_tier.isdigit():
            queryset = queryset.filter(trust_tier=int(trust_tier))

        if self.action == 'list':
            # Prefetch tips để phục vụ preview trên Card mà không sinh N+1 queries
            return queryset.prefetch_related(
                Prefetch('tips', queryset=Tip.objects.order_by('-updated_at'))
            )

        if self.action == 'retrieve':
            return queryset.prefetch_related(
                Prefetch(
                    'tips',
                    queryset=Tip.objects.select_related('user', 'user__profile').order_by('-updated_at')
                ),
                'verifications'
            )

        return queryset

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Trả về danh mục phục vụ Filter Chips trên giao diện Flutter"""
        return Response([
            {'key': choice.value, 'label': choice.label}
            for choice in CategoryChoices
        ])

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Nút "Tôi cũng biết chỗ này" cho cư dân địa phương.
        Yêu cầu:
        1. Cư dân đã xác thực cư trú >= 6 tháng (is_local_verified = True).
        2. Khu vực cư trú của user phải khớp với quận của địa điểm (chống xác thực chéo khu vực).
        """
        place = self.get_object()
        user = request.user
        profile = getattr(user, 'profile', None)

        if not profile or not profile.is_local_verified:
            return Response({
                'error': 'Bạn cần xác thực cư trú tối thiểu 6 tháng tại khu vực này để xác nhận địa điểm.',
                'code': 'REQUIRES_LOCAL_VERIFICATION'
            }, status=status.HTTP_403_FORBIDDEN)

        # Kiểm tra khớp quận cư trú
        if profile.residing_district.strip().lower() != place.district.strip().lower():
            return Response({
                'error': f'Bạn chỉ có quyền xác thực địa điểm thuộc khu vực bạn cư trú ({profile.residing_district}).',
                'code': 'DISTRICT_MISMATCH'
            }, status=status.HTTP_403_FORBIDDEN)

        verification, created = PlaceVerification.objects.get_or_create(
            place=place,
            user=user
        )

        # Tính toán và lưu ngay lập tức để trả kết quả realtime cho client
        place.recalculate_trust_metrics()
        place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at', 'updated_at'])

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        message = 'Đã xác thực địa điểm thành công!' if created else 'Bạn đã xác thực địa điểm này trước đó.'
        return Response({
            'message': message,
            'verified_count': place.verified_count,
            'trust_tier': place.trust_tier,
            'last_verified_at': place.last_verified_at
        }, status=status_code)

    @action(detail=True, methods=['post', 'put', 'delete'])
    def tip(self, request, pk=None):
        """
        Quản lý Mẹo từ cư dân local cho địa điểm:
        - POST: Tạo mẹo mới (chỉ 1 mẹo / người / địa điểm).
        - PUT: Cập nhật mẹo của mình.
        - DELETE: Xóa mẹo của mình.
        """
        place = self.get_object()
        user = request.user

        if request.method == 'POST':
            if Tip.objects.filter(place=place, user=user).exists():
                return Response({
                    'error': 'Bạn đã có mẹo cho địa điểm này. Vui lòng cập nhật thay vì tạo mới.'
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer = TipCreateUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tip = serializer.save(place=place, user=user)

            # Cập nhật metrics place nếu user là local verified và cùng quận
            profile = getattr(user, 'profile', None)
            if profile and profile.is_local_verified and (profile.residing_district.strip().lower() == place.district.strip().lower()):
                PlaceVerification.objects.get_or_create(place=place, user=user)
                place.recalculate_trust_metrics()
                place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at', 'updated_at'])

            return Response(
                TipSerializer(tip, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        elif request.method == 'PUT':
            try:
                tip = Tip.objects.get(place=place, user=user)
            except Tip.DoesNotExist:
                return Response({'error': 'Bạn chưa có mẹo nào tại địa điểm này.'}, status=status.HTTP_404_NOT_FOUND)

            serializer = TipCreateUpdateSerializer(tip, data=request.data)
            serializer.is_valid(raise_exception=True)
            tip = serializer.save()

            return Response(
                TipSerializer(tip, context={'request': request}).data,
                status=status.HTTP_200_OK
            )

        elif request.method == 'DELETE':
            try:
                tip = Tip.objects.get(place=place, user=user)
                tip.delete()
                return Response({'message': 'Đã xóa mẹo thành công.'}, status=status.HTTP_200_OK)
            except Tip.DoesNotExist:
                return Response({'error': 'Không tìm thấy mẹo để xóa.'}, status=status.HTTP_404_NOT_FOUND)
