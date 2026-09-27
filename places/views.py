import math
from django.db.models import Prefetch, Count
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import (
    Place,
    PlaceVerification,
    Tip,
    SavedPlace,
    PlaceReport,
    CategoryChoices,
    TrustTier,
    PlaceStatus
)
from .serializers import (
    PlaceListSerializer,
    PlaceDetailSerializer,
    TipSerializer,
    TipCreateUpdateSerializer,
    PlaceReportCreateSerializer
)


class PlaceWriteActionThrottle(UserRateThrottle):
    """Giới hạn tần suất thao tác ghi (xác thực hoặc viết tip) để chống bot/spam"""
    rate = '60/hour'


class PlaceViewSet(viewsets.ModelViewSet):
    """
    API Quản lý và Khám phá Địa điểm HubLocal.
    - list: Tìm kiếm, lọc theo Danh mục, Khu vực, Trạng thái, Khoảng giá, Quanh đây.
    - retrieve: Xem chi tiết mẹo từ cư dân, khoảng giá, giờ mở cửa, bản đồ, trạng thái xác thực.
    - verify: Nút "Tôi cũng biết chỗ này" dành cho cư dân local đã xác minh thuộc cùng khu vực.
    - tip: Thêm/Sửa/Xóa mẹo cá nhân cho địa điểm (tối đa 1 mẹo/người/quán).
    - save: Lưu / Bỏ lưu địa điểm yêu thích.
    - saved: Lấy danh sách địa điểm đã lưu của người dùng.
    - report: Gửi phản ánh thông tin sai lệch cho địa điểm.
    - categories: Danh sách danh mục chuẩn.
    - districts: Danh sách các quận/khu vực hỗ trợ.
    """
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'address']

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'categories', 'districts']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_throttles(self):
        if self.action in ['verify', 'tip', 'save_place', 'report']:
            return [PlaceWriteActionThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        if self.action in ['list', 'saved']:
            return PlaceListSerializer
        return PlaceDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            # Tối ưu Zero-Waste & N+1 queries: gom toàn bộ ID địa điểm đã lưu vào một Set duy nhất
            context['saved_place_ids'] = set(
                SavedPlace.objects.filter(user=self.request.user).values_list('place_id', flat=True)
            )
        return context

    def get_queryset(self):
        queryset = Place.objects.all()

        # Lọc theo Quận/Khu vực
        district = self.request.query_params.get('district')
        if district:
            queryset = queryset.filter(district__iexact=district.strip())

        district_code = self.request.query_params.get('district_code')
        if district_code:
            queryset = queryset.filter(district_code__iexact=district_code.strip())

        # Lọc theo Danh mục
        category = self.request.query_params.get('category')
        if category and category in CategoryChoices.values:
            queryset = queryset.filter(category=category)

        # Lọc theo Phân tầng Tín nhiệm
        trust_tier = self.request.query_params.get('trust_tier')
        if trust_tier is not None and trust_tier.isdigit():
            queryset = queryset.filter(trust_tier=int(trust_tier))

        # Lọc theo Trạng thái hoạt động
        status_param = self.request.query_params.get('status')
        if status_param and status_param in PlaceStatus.values:
            queryset = queryset.filter(status=status_param)

        # Lọc theo Khoảng giá
        min_p = self.request.query_params.get('min_price')
        if min_p and min_p.isdigit():
            queryset = queryset.filter(min_price__gte=int(min_p))

        max_p = self.request.query_params.get('max_price')
        if max_p and max_p.isdigit():
            queryset = queryset.filter(max_price__lte=int(max_p))

        # Tìm kiếm Quanh đây (Near Me) theo Bounding Box
        user_lat = self.request.query_params.get('lat')
        user_lng = self.request.query_params.get('lng')
        radius_km = self.request.query_params.get('radius')
        if user_lat and user_lng and radius_km:
            try:
                lat = float(user_lat)
                lng = float(user_lng)
                rad = float(radius_km)
                dlat = rad / 111.0
                dlng = rad / (111.0 * max(0.1, math.cos(math.radians(lat))))
                queryset = queryset.filter(
                    latitude__range=(lat - dlat, lat + dlat),
                    longitude__range=(lng - dlng, lng + dlng)
                )
            except (ValueError, TypeError):
                pass

        if self.action in ['list', 'saved']:
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

    @action(detail=False, methods=['get'])
    def districts(self, request):
        """Trả về danh sách các quận/khu vực hỗ trợ cùng số lượng địa điểm thực tế"""
        districts_data = (
            Place.objects.values('district', 'district_code')
            .annotate(place_count=Count('id'))
            .order_by('-place_count')
        )
        return Response([
            {
                'code': d['district_code'],
                'name': d['district'],
                'place_count': d['place_count']
            }
            for d in districts_data
        ])

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Nút "Tôi cũng biết chỗ này" cho cư dân địa phương.
        Yêu cầu:
        1. Cư dân đã được xác minh chính thức (is_local_verified = True).
        2. Khu vực cư trú của user phải khớp với quận của địa điểm (chống xác thực chéo khu vực).
        3. Idempotent: Gọi lại nhiều lần không tạo bản ghi trùng hoặc tăng verified_count.
        """
        place = self.get_object()
        user = request.user
        profile = getattr(user, 'profile', None)

        if not profile or not profile.is_local_verified:
            return Response({
                'code': 'REQUIRES_LOCAL_VERIFICATION',
                'message': 'Bạn cần hoàn tất xác minh cư dân địa phương để xác nhận địa điểm này.',
                'field_errors': {}
            }, status=status.HTTP_403_FORBIDDEN)

        # Kiểm tra khớp quận cư trú
        if profile.residing_district.strip().lower() != place.district.strip().lower():
            return Response({
                'code': 'DISTRICT_MISMATCH',
                'message': f'Bạn chỉ có quyền xác thực địa điểm thuộc khu vực bạn cư trú ({profile.residing_district}).',
                'field_errors': {}
            }, status=status.HTTP_403_FORBIDDEN)

        verification, created = PlaceVerification.objects.get_or_create(
            place=place,
            user=user
        )

        # Tính toán lại chỉ số tín nhiệm
        place.recalculate_trust_metrics()
        place.save(update_fields=['verified_count', 'trust_tier', 'last_verified_at', 'updated_at'])

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({
            'place_id': place.id,
            'user_has_verified': True,
            'verified_count': place.verified_count,
            'trust_tier': place.trust_tier,
            'last_verified_at': place.last_verified_at
        }, status=status_code)

    @action(detail=True, methods=['post', 'delete'], url_path='save')
    def save_place(self, request, pk=None):
        """
        Lưu hoặc Bỏ lưu địa điểm yêu thích (Bookmarks):
        - POST: Lưu địa điểm (Idempotent).
        - DELETE: Bỏ lưu địa điểm.
        """
        place = self.get_object()
        user = request.user

        if request.method == 'POST':
            _, created = SavedPlace.objects.get_or_create(user=user, place=place)
            return Response({
                'place_id': place.id,
                'is_saved': True,
                'message': 'Đã lưu địa điểm vào danh sách yêu thích.'
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        elif request.method == 'DELETE':
            deleted_count, _ = SavedPlace.objects.filter(user=user, place=place).delete()
            return Response({
                'place_id': place.id,
                'is_saved': False,
                'message': 'Đã bỏ lưu địa điểm.'
            }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='saved')
    def saved(self, request):
        """
        Danh sách địa điểm đã lưu của người dùng hiện tại (kèm phân trang chuẩn).
        """
        saved_places = (
            Place.objects.filter(saved_by__user=request.user)
            .order_by('-saved_by__created_at')
            .prefetch_related(Prefetch('tips', queryset=Tip.objects.order_by('-updated_at')))
        )

        page = self.paginate_queryset(saved_places)
        if page is not None:
            serializer = PlaceListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = PlaceListSerializer(saved_places, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='report')
    def report(self, request, pk=None):
        """
        Gửi báo cáo sai lệch thông tin hoặc quán đã đóng cửa.
        """
        place = self.get_object()
        serializer = PlaceReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report = PlaceReport.objects.create(
            place=place,
            user=request.user,
            report_type=serializer.validated_data['report_type'],
            description=serializer.validated_data.get('description', '')
        )

        return Response({
            'report_id': report.id,
            'message': 'Cảm ơn bạn đã đóng góp phản ánh. Đội ngũ kiểm duyệt HubLocal sẽ xác minh sớm nhất.'
        }, status=status.HTTP_201_CREATED)

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
                    'code': 'TIP_ALREADY_EXISTS',
                    'message': 'Bạn đã có mẹo cho địa điểm này. Vui lòng cập nhật thay vì tạo mới.',
                    'field_errors': {}
                }, status=status.HTTP_400_BAD_REQUEST)

            serializer = TipCreateUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tip = serializer.save(place=place, user=user)

            place.save(update_fields=['updated_at'])

            return Response(
                TipSerializer(tip, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        elif request.method == 'PUT':
            try:
                tip = Tip.objects.get(place=place, user=user)
            except Tip.DoesNotExist:
                return Response({
                    'code': 'TIP_NOT_FOUND',
                    'message': 'Bạn chưa có mẹo nào tại địa điểm này.',
                    'field_errors': {}
                }, status=status.HTTP_404_NOT_FOUND)

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
                return Response({
                    'code': 'TIP_NOT_FOUND',
                    'message': 'Không tìm thấy mẹo để xóa.',
                    'field_errors': {}
                }, status=status.HTTP_404_NOT_FOUND)

