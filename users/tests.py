from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, UserProfile


class UserAuthAndProfileTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_registration_creates_profile(self):
        """Đăng ký user tự động tạo UserProfile tương ứng"""
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
        self.assertTrue(user.profile.is_local_verified)
        self.assertEqual(user.profile.residing_months, 10)

    def test_verify_local_status_update(self):
        """Màn hình 3: Cập nhật thông tin cư trú từ < 6 tháng lên >= 6 tháng"""
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
        self.assertTrue(response.data['is_local_verified'])

        user.profile.refresh_from_db()
        self.assertTrue(user.profile.is_local_verified)
