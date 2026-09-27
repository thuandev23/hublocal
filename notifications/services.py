import logging
import os
from django.conf import settings
from .models import DeviceToken, Notification

logger = logging.getLogger(__name__)

# Quản lý khởi tạo Firebase Admin SDK
_firebase_initialized = False


def initialize_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin SDK đã được khởi tạo thành công.")
            return True
        else:
            # Kiểm tra nếu đã có default app được khởi tạo
            if firebase_admin._apps:
                _firebase_initialized = True
                return True
            logger.info("Chưa cấu hình FIREBASE_CREDENTIALS_PATH. Thông báo sẽ hoạt động ở chế độ mô phỏng (In-app + Log).")
            return False
    except Exception as e:
        logger.warning(f"Không thể khởi tạo Firebase Admin SDK: {e}")
        return False


def send_push_notification(user, title, body, data=None):
    """
    Gửi thông báo Push đến thiết bị di động của người dùng và lưu vào Hộp thư in-app.
    - An toàn: Không bao giờ crash chương trình nếu FCM gặp lỗi kết nối.
    - Tự làm sạch: Deactivate các token đã hết hạn hoặc bị gỡ ứng dụng.
    """
    if data is None:
        data = {}

    # Chuyển đổi mọi giá trị trong data thành string để tuân thủ quy chuẩn của FCM
    fcm_data = {str(k): str(v) for k, v in data.items()}

    # 1. Luôn lưu vào lịch sử Hộp thư thông báo trong App
    notification_record = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        data=data
    )

    # 2. Lấy danh sách các thiết bị đang kích hoạt của User
    active_tokens = list(
        DeviceToken.objects.filter(user=user, is_active=True).values_list('token', flat=True)
    )

    if not active_tokens:
        logger.info(f"User {user} chưa đăng ký thiết bị nhận push.")
        return notification_record

    # 3. Gửi Push qua Firebase Cloud Messaging
    is_ready = initialize_firebase()
    if is_ready:
        try:
            from firebase_admin import messaging

            # Cấu hình Android: High Priority + Heads-up Banner + Kênh thông báo chuẩn
            android_config = messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='hublocal_alerts',
                    sound='default',
                    default_sound=True,
                    priority='high',
                    click_action='FLUTTER_NOTIFICATION_CLICK',
                )
            )

            # Cấu hình iOS (APNs): Priority 10 + Âm thanh + Đánh dấu Badge
            apns_config = messaging.APNSConfig(
                headers={'apns-priority': '10'},
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1,
                        content_available=True,
                    )
                )
            )

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=fcm_data,
                tokens=active_tokens,
                android=android_config,
                apns=apns_config,
            )

            response = messaging.send_each_for_multicast(message)
            logger.info(f"Đã gửi Push tới {user}: {response.success_count} thành công, {response.failure_count} thất bại.")

            # Tự động dọn dẹp các token bị lỗi / hết hạn
            if response.failure_count > 0:
                for idx, res in enumerate(response.responses):
                    if not res.success:
                        error_code = getattr(res.exception, 'code', str(res.exception))
                        bad_token = active_tokens[idx]
                        logger.warning(f"FCM Token không hợp lệ ({error_code}): {bad_token[:12]}...")
                        DeviceToken.objects.filter(token=bad_token).update(is_active=False)

        except Exception as e:
            logger.error(f"Lỗi khi gửi thông báo FCM: {e}")
    else:
        logger.info(f"[FCM CHẾ ĐỘ MÔ PHỎNG] Gửi tới {user} ({len(active_tokens)} thiết bị): [{title}] - {body}")

    return notification_record
