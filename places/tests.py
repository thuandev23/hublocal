from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, UserProfile
from places.models import Place, PlaceVerification, Tip, TrustTier, CategoryChoices


class HubLocalIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Local user đủ điều kiện tại Thủ Đức (sống 8 tháng >= 6 tháng)
        self.local_user = User.objects.create_user(
            username='localleader',
            first_name='Minh',
            last_name='Tran',
            phone_number='0909123456',
            password='password123'
        )
        self.local_profile = UserProfile.objects.create(
            user=self.local_user,
            residing_district='Thủ Đức',
            residing_months=8
        )

        # Local user đủ điều kiện nhưng ở Quận 1 (sống 12 tháng)
        self.q1_user = User.objects.create_user(
            username='q1resident',
            phone_number='0909999888',
            password='password123'
        )
        self.q1_profile = UserProfile.objects.create(
            user=self.q1_user,
            residing_district='Quận 1',
            residing_months=12
        )

        # Non-local user (mới đến sống 2 tháng < 6 tháng)
        self.newbie_user = User.objects.create_user(
            username='newbie',
            phone_number='0918111222',
            password='password123'
        )
        self.newbie_profile = UserProfile.objects.create(
            user=self.newbie_user,
            residing_district='Thủ Đức',
            residing_months=2
        )

        # Place mẫu tại Thủ Đức
        self.place = Place.objects.create(
            name='Cà Phê Sân Vườn Làng Đại Học',
            category=CategoryChoices.EAT_DRINK,
            district='Thủ Đức',
            address='123 Đường Số 8, Linh Trung, Thủ Đức'
        )

    def test_local_verification_status(self):
        """Kiểm tra quy tắc nghiệp vụ: Cư trú >= 6 tháng tự động được công nhận là Local Verified"""
        self.assertTrue(self.local_profile.is_local_verified)
        self.assertFalse(self.newbie_profile.is_local_verified)

    def test_verify_place_by_local(self):
        """Local xác thực địa điểm -> tăng verified_count và chuyển tier sang 1"""
        self.client.force_authenticate(user=self.local_user)
        url = reverse('places:place-verify', kwargs={'pk': self.place.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.place.refresh_from_db()
        self.assertEqual(self.place.verified_count, 1)
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_1_VERIFIED)

    def test_verify_place_by_non_local_fails(self):
        """User chưa đủ 6 tháng không được phép xác thực địa điểm"""
        self.client.force_authenticate(user=self.newbie_user)
        url = reverse('places:place-verify', kwargs={'pk': self.place.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('code'), 'REQUIRES_LOCAL_VERIFICATION')

    def test_verify_place_district_mismatch(self):
        """Cư dân Quận 1 không được phép xác thực địa điểm ở Thủ Đức (Bảo vệ tính local)"""
        self.client.force_authenticate(user=self.q1_user)
        url = reverse('places:place-verify', kwargs={'pk': self.place.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get('code'), 'DISTRICT_MISMATCH')

    def test_trust_tier_progression(self):
        """Kiểm tra bậc tín nhiệm: 0 -> 1-2 -> 3+"""
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_0_UNVERIFIED)

        # Tạo thêm 2 local users tại Thủ Đức
        u2 = User.objects.create_user(username='u2', phone_number='0909000002', password='p')
        UserProfile.objects.create(user=u2, residing_district='Thủ Đức', residing_months=12)
        u3 = User.objects.create_user(username='u3', phone_number='0909000003', password='p')
        UserProfile.objects.create(user=u3, residing_district='Thủ Đức', residing_months=24)

        PlaceVerification.objects.create(place=self.place, user=self.local_user)
        self.place.recalculate_trust_metrics()
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_1_VERIFIED)

        PlaceVerification.objects.create(place=self.place, user=u2)
        self.place.recalculate_trust_metrics()
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_1_VERIFIED)

        PlaceVerification.objects.create(place=self.place, user=u3)
        self.place.recalculate_trust_metrics()
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_2_HIGH_TRUST)
        self.assertEqual(self.place.verified_count, 3)

    def test_tip_creation_and_unique_constraint(self):
        """Mỗi user chỉ có 1 tip cho 1 place, cố tình tạo thêm sẽ bị chặn"""
        self.client.force_authenticate(user=self.local_user)
        url = reverse('places:place-tip', kwargs={'pk': self.place.pk})

        # Tạo tip lần 1
        res1 = self.client.post(url, {'content': 'Quán này đi tầm 14h vắng và mát mẻ nhất, nên thử cà phê muối.'})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['author_name'], 'Minh T.')

        # Cố tạo tip lần 2 trên cùng place -> lỗi 400
        res2 = self.client.post(url, {'content': 'Tip thứ hai spam thử'})
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Cập nhật bằng PUT -> thành công
        res3 = self.client.put(url, {'content': 'Quán đổi giờ mở cửa từ 7h sáng, rất yên tĩnh.'})
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(res3.data['content'], 'Quán đổi giờ mở cửa từ 7h sáng, rất yên tĩnh.')

    def test_list_and_filter_places_api(self):
        """Kiểm tra API danh sách và lọc theo khu vực/danh mục"""
        url = reverse('places:place-list')
        response = self.client.get(url, {'district': 'Thủ Đức', 'category': 'EAT_DRINK'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)
