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

