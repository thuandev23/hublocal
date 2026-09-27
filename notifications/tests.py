from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from users.models import User, UserProfile, VerificationStatus
from places.models import Place, PlaceVerification, CategoryChoices, TrustTier
from notifications.models import DeviceToken, Notification, PlatformChoices
from notifications.services import send_push_notification


class NotificationSystemTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='noti_user',
            password='password123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            residing_district='Thủ Đức',
            residing_months=8,
            verification_status=VerificationStatus.PENDING
        )

    def test_register_device_token(self):
        """Kiểm tra API đăng ký FCM Device Token từ app Flutter"""
        self.client.force_authenticate(user=self.user)
        url = reverse('notifications:device_tokens')
        data = {
            'token': 'fcm_sample_token_android_123456789',
            'platform': 'android'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        token_obj = DeviceToken.objects.get(token='fcm_sample_token_android_123456789')
        self.assertEqual(token_obj.user, self.user)
        self.assertEqual(token_obj.platform, PlatformChoices.ANDROID)
        self.assertTrue(token_obj.is_active)

    def test_deactivate_device_token_on_logout(self):
        """Kiểm tra API hủy token khi người dùng đăng xuất khỏi thiết bị"""
        DeviceToken.objects.create(
            user=self.user,
            token='fcm_token_to_delete',
            platform=PlatformChoices.IOS,
            is_active=True
        )
        self.client.force_authenticate(user=self.user)
        url = reverse('notifications:device_tokens')
        response = self.client.delete(url, {'token': 'fcm_token_to_delete'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token_obj = DeviceToken.objects.get(token='fcm_token_to_delete')
        self.assertFalse(token_obj.is_active)

    def test_inapp_notifications_list_and_mark_read(self):
        """Kiểm tra lấy danh sách hộp thư thông báo và đánh dấu đã đọc"""
        n1 = Notification.objects.create(
            user=self.user,
            title='Thông báo 1',
            body='Nội dung 1',
            is_read=False
        )
        n2 = Notification.objects.create(
            user=self.user,
            title='Thông báo 2',
            body='Nội dung 2',
            is_read=False
        )

        self.client.force_authenticate(user=self.user)
        list_url = reverse('notifications:list')
        res_list = self.client.get(list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data['count'], 2)

        # Đánh dấu đọc n1
        read_url = reverse('notifications:mark_read', kwargs={'pk': n1.pk})
        res_read = self.client.post(read_url)
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)

        # Đánh dấu đọc tất cả
        read_all_url = reverse('notifications:mark_read_all')
        res_all = self.client.post(read_all_url)
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)

    def test_auto_notification_on_verification_approval(self):
        """Kiểm tra signal tự động gửi thông báo khi hồ sơ cư dân chuyển sang VERIFIED"""
        # Đăng ký sẵn 1 device token cho user
        DeviceToken.objects.create(
            user=self.user,
            token='device_token_verified_scenario',
            platform=PlatformChoices.ANDROID,
            is_active=True
        )

        initial_noti_count = Notification.objects.filter(user=self.user).count()

        # Admin duyệt hồ sơ
        self.profile.verification_status = VerificationStatus.VERIFIED
        self.profile.save()

        new_notis = Notification.objects.filter(user=self.user)
        self.assertEqual(new_notis.count(), initial_noti_count + 1)
        latest_noti = new_notis.latest('created_at')
        self.assertIn("Hồ sơ cư dân của bạn đã được duyệt", latest_noti.title)
        self.assertEqual(latest_noti.data.get('type'), 'VERIFICATION_APPROVED')

    def test_auto_notification_on_place_tier2_upgrade(self):
        """Kiểm tra signal gửi thông báo vinh danh cho các cư dân khi quán lên Tier 2"""
        place = Place.objects.create(
            name='Quán Cà Phê Vinh Danh',
            category=CategoryChoices.EAT_DRINK,
            district='Thủ Đức',
            address='123 Võ Văn Ngân'
        )

        u1 = User.objects.create_user(username='verifier_1', password='p')
        u2 = User.objects.create_user(username='verifier_2', password='p')
        u3 = User.objects.create_user(username='verifier_3', password='p')

        # 3 users xác nhận địa điểm
        PlaceVerification.objects.create(place=place, user=u1)
        PlaceVerification.objects.create(place=place, user=u2)
        PlaceVerification.objects.create(place=place, user=u3)

        # Tính toán lại để chuyển sang Tier 2
        place.recalculate_trust_metrics()
        place.save()

        # Kiểm tra u1, u2, u3 đều nhận được thông báo
        for u in [u1, u2, u3]:
            notis = Notification.objects.filter(user=u)
            self.assertTrue(notis.exists())
            self.assertIn("Quán quen của bạn đã thăng hạng", notis.first().title)
            self.assertEqual(notis.first().data.get('type'), 'PLACE_TIER_UPGRADED')

    def test_auto_notification_on_verification_rejection(self):
        """Kiểm tra signal tự động gửi thông báo khi hồ sơ cư dân chuyển sang REJECTED"""
        initial_noti_count = Notification.objects.filter(user=self.user).count()

        self.profile.verification_status = VerificationStatus.REJECTED
        self.profile.verification_rejected_reason = "Ảnh chụp không rõ thông tin."
        self.profile.save()

        new_notis = Notification.objects.filter(user=self.user)
        self.assertEqual(new_notis.count(), initial_noti_count + 1)
        latest_noti = new_notis.latest('created_at')
        self.assertIn("chưa được duyệt", latest_noti.title)
        self.assertEqual(latest_noti.data.get('type'), 'VERIFICATION_REJECTED')
        self.assertIn("Ảnh chụp không rõ", latest_noti.body)
