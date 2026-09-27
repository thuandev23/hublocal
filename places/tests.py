from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, UserProfile, VerificationStatus
from places.models import Place, PlaceVerification, Tip, SavedPlace, PlaceReport, TrustTier, CategoryChoices


class HubLocalIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Local user đã được xác minh chính thức tại Thủ Đức
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
            residing_months=8,
            verification_status=VerificationStatus.VERIFIED
        )

        # Local user đã được xác minh nhưng ở Quận 1
        self.q1_user = User.objects.create_user(
            username='q1resident',
            phone_number='0909999888',
            password='password123'
        )
        self.q1_profile = UserProfile.objects.create(
            user=self.q1_user,
            residing_district='Quận 1',
            residing_months=12,
            verification_status=VerificationStatus.VERIFIED
        )

        # Non-local user (chưa gửi xác thực)
        self.newbie_user = User.objects.create_user(
            username='newbie',
            phone_number='0918111222',
            password='password123'
        )
        self.newbie_profile = UserProfile.objects.create(
            user=self.newbie_user,
            residing_district='Thủ Đức',
            residing_months=2,
            verification_status=VerificationStatus.UNVERIFIED
        )

        # Place mẫu tại Thủ Đức
        self.place = Place.objects.create(
            name='Cà Phê Sân Vườn Làng Đại Học',
            category=CategoryChoices.EAT_DRINK,
            district='Thủ Đức',
            address='123 Đường Số 8, Linh Trung, Thủ Đức',
            latitude=10.870000,
            longitude=106.800000
        )

    def test_local_verification_status(self):
        """Kiểm tra quy tắc nghiệp vụ: Chỉ trạng thái VERIFIED mới có cờ is_local_verified"""
        self.assertTrue(self.local_profile.is_local_verified)
        self.assertFalse(self.newbie_profile.is_local_verified)

    def test_verify_place_by_local(self):
        """Local xác thực địa điểm -> tăng verified_count, chuyển tier sang 1, trả đúng contract"""
        self.client.force_authenticate(user=self.local_user)
        url = reverse('places:place-verify', kwargs={'pk': self.place.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['place_id'], self.place.id)
        self.assertTrue(response.data['user_has_verified'])
        self.assertEqual(response.data['verified_count'], 1)
        self.assertEqual(response.data['trust_tier'], TrustTier.TIER_1_VERIFIED)
        self.assertIsNotNone(response.data['last_verified_at'])

        self.place.refresh_from_db()
        self.assertEqual(self.place.verified_count, 1)
        self.assertEqual(self.place.trust_tier, TrustTier.TIER_1_VERIFIED)

        # Kiểm tra tính Idempotent: Gọi lại lần 2 không tăng count
        res_repeat = self.client.post(url)
        self.assertEqual(res_repeat.status_code, status.HTTP_200_OK)
        self.assertEqual(res_repeat.data['verified_count'], 1)

    def test_verify_place_by_non_local_fails(self):
        """User chưa xác thực cư dân không được phép xác nhận địa điểm"""
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
        UserProfile.objects.create(
            user=u2,
            residing_district='Thủ Đức',
            residing_months=12,
            verification_status=VerificationStatus.VERIFIED
        )
        u3 = User.objects.create_user(username='u3', phone_number='0909000003', password='p')
        UserProfile.objects.create(
            user=u3,
            residing_district='Thủ Đức',
            residing_months=24,
            verification_status=VerificationStatus.VERIFIED
        )

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

    def test_save_and_unsave_place(self):
        """Kiểm tra lưu / bỏ lưu địa điểm và API danh sách đã lưu"""
        self.client.force_authenticate(user=self.local_user)
        save_url = reverse('places:place-save-place', kwargs={'pk': self.place.pk})

        # Lưu địa điểm
        res_save = self.client.post(save_url)
        self.assertEqual(res_save.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res_save.data['is_saved'])

        # Lấy danh sách đã lưu
        saved_list_url = reverse('places:place-saved')
        res_list = self.client.get(saved_list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data['count'], 1)
        self.assertEqual(res_list.data['results'][0]['id'], self.place.id)

        # Bỏ lưu địa điểm
        res_unsave = self.client.delete(save_url)
        self.assertEqual(res_unsave.status_code, status.HTTP_200_OK)
        self.assertFalse(res_unsave.data['is_saved'])

    def test_place_report_submission(self):
        """Kiểm tra gửi báo cáo sai lệch thông tin địa điểm"""
        self.client.force_authenticate(user=self.local_user)
        report_url = reverse('places:place-report', kwargs={'pk': self.place.pk})
        data = {
            'report_type': 'CLOSED',
            'description': 'Quán này đã trả mặt bằng từ tháng trước.'
        }
        response = self.client.post(report_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('report_id', response.data)

    def test_districts_endpoint(self):
        """Kiểm tra endpoint /districts/ trả về danh sách quận và số lượng địa điểm thực tế"""
        url = reverse('places:districts-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Thủ Đức')

