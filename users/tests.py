from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import User, UserProfile, VerificationStatus


class UserAuthAndProfileTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_registration_creates_profile(self):
        """Đăng ký user tự động tạo UserProfile với trạng thái unverified, không tự cấp local badge"""
        url = reverse('users:register')
        data = {
            'username': 'thuducresident',
            'phone_number': '0901234888',
            'password': 'strongpassword123',
            'residing_district': 'Thủ Đức',
            'residing_months': 10
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])

        user = User.objects.get(username='thuducresident')
        self.assertEqual(user.phone_number, '0901234888')
        # Kiểm tra tính nghiêm ngặt: Tuyệt đối không tự phong Local Verified
        self.assertFalse(user.profile.is_local_verified)
        self.assertEqual(user.profile.verification_status, VerificationStatus.UNVERIFIED)
        self.assertEqual(user.profile.residing_months, 10)

    def test_verify_local_status_update(self):
        """Màn hình 3: Gửi hồ sơ xác minh đưa vào trạng thái 'pending' chờ kiểm duyệt"""
        user = User.objects.create_user(
            username='transient',
            phone_number='0988776655',
            password='password123'
        )
        UserProfile.objects.create(
            user=user,
            residing_district='Thủ Đức',
            residing_months=3
        )
        self.assertFalse(user.profile.is_local_verified)

        self.client.force_authenticate(user=user)
        url = reverse('users:verify_local')
        data = {
            'phone_number': '0988776655',
            'residing_district': 'Thủ Đức',
            'residing_months': 7
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['verification_status'], VerificationStatus.PENDING)
        self.assertFalse(response.data['is_local_verified'])

        user.profile.refresh_from_db()
        self.assertEqual(user.profile.verification_status, VerificationStatus.PENDING)
        self.assertFalse(user.profile.is_local_verified)

    def test_auth_me_endpoint_and_permissions(self):
        """Kiểm tra API /auth/me/ trả về đầy đủ hồ sơ và phân quyền chính xác"""
        user = User.objects.create_user(
            username='verified_resident',
            phone_number='0909000111',
            password='password123'
        )
        UserProfile.objects.create(
            user=user,
            residing_district='Thủ Đức',
            residing_months=12,
            verification_status=VerificationStatus.VERIFIED
        )

        self.client.force_authenticate(user=user)
        url = reverse('users:me')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'verified_resident')
        self.assertTrue(response.data['permissions']['can_verify_places'])
        self.assertTrue(response.data['permissions']['can_add_tips'])
        self.assertTrue(response.data['show_celebration_modal'])
        self.assertIn('impact_metrics', response.data)
        self.assertEqual(response.data['impact_metrics']['verified_places_count'], 0)

    def test_acknowledge_celebration_modal(self):
        """Kiểm tra gọi API ack-celebration tắt cờ show_celebration_modal thành công"""
        user = User.objects.create_user(
            username='ack_user',
            password='password123'
        )
        UserProfile.objects.create(
            user=user,
            residing_district='Thủ Đức',
            residing_months=12,
            verification_status=VerificationStatus.VERIFIED,
            has_seen_verification_modal=False
        )

        self.client.force_authenticate(user=user)
        ack_url = reverse('users:ack_celebration')
        res_ack = self.client.post(ack_url)
        self.assertEqual(res_ack.status_code, status.HTTP_200_OK)
        self.assertFalse(res_ack.data['show_celebration_modal'])

        # Gọi lại /auth/me/ xem cờ show_celebration_modal đã tắt chưa
        me_url = reverse('users:me')
        res_me = self.client.get(me_url)
        self.assertFalse(res_me.data['show_celebration_modal'])

    def test_auth_logout_blacklists_token(self):
        """Kiểm tra API /auth/logout/ blacklist refresh token thành công"""
        user = User.objects.create_user(
            username='logout_user',
            password='password123'
        )
        refresh = RefreshToken.for_user(user)

        self.client.force_authenticate(user=user)
        url = reverse('users:logout')
        response = self.client.post(url, {'refresh': str(refresh)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_approve_and_reject_actions(self):
        """Kiểm tra admin có thể duyệt và từ chối hồ sơ cư dân qua custom action"""
        admin_user = User.objects.create_superuser(
            username='admin_boss',
            password='adminpassword',
            email='admin@hublocal.vn'
        )
        self.client.force_login(admin_user)

        user_pending = User.objects.create_user(username='applicant', password='p')
        profile = UserProfile.objects.create(
            user=user_pending,
            residing_district='Thủ Đức',
            residing_months=9,
            verification_status=VerificationStatus.PENDING
        )

        # 1. Thử duyệt 1-click qua endpoint /admin/users/userprofile/<id>/approve/
        approve_url = reverse('admin:userprofile-approve', args=[profile.pk])
        res_approve = self.client.get(approve_url, follow=True)
        self.assertEqual(res_approve.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, VerificationStatus.VERIFIED)
        self.assertTrue(profile.is_local_verified)
        self.assertIsNotNone(profile.verified_at)

        # 2. Thử từ chối 1-click qua endpoint /admin/users/userprofile/<id>/reject/
        reject_url = reverse('admin:userprofile-reject', args=[profile.pk])
        res_reject = self.client.get(reject_url, follow=True)
        self.assertEqual(res_reject.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.verification_status, VerificationStatus.REJECTED)
        self.assertFalse(profile.is_local_verified)
        self.assertTrue(len(profile.verification_rejected_reason) > 0)


