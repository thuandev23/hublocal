tổng hợp và phân loại toàn bộ các tính năng hiện có của hệ thống HubLocal.

Hệ thống hiện tại là một giải pháp hoàn chỉnh từ Dữ liệu thực tế 
→
→ Nghiệp vụ lõi 
→
→ API RESTful chuẩn mực 
→
→ Push Notification 
→
→ Cổng Quản trị Vận hành.

🗺️ 1. Quản Trị & Khám Phá Dữ Liệu Địa Điểm (Places & Discovery)
Dữ liệu thực tế 100%:
Đã nạp 172 địa điểm thực tế tại TP. Thủ Đức với tên, địa chỉ, số điện thoại, tọa độ GPS chuẩn xác.
Album ảnh chất lượng cao (photos): Lưu trữ từ 2 đến 19 ảnh độ phân giải cao từ Google CDN cho mỗi địa điểm.
Tách bạch dữ liệu tham khảo: Lưu trữ đánh giá Google (google_rating, google_review_count, google_reviews) tách biệt hoàn toàn với mẹo độc quyền của HubLocal.
Tìm kiếm & Bộ lọc đa năng (GET /places/):
Tìm kiếm theo từ khóa search (tên quán, số nhà, tên đường).
Lọc theo danh mục category: Ăn uống (EAT_DRINK), Vui chơi (PLAY), Dịch vụ (SERVICES).
Lọc theo khu vực district / district_code.
Lọc theo bậc tín nhiệm trust_tier (0, 1, 2).
Định vị GPS & Tìm quanh đây (Haversine Distance):
Truyền tọa độ latitude, longitude và bán kính radius (km) 
⟹
⟹ Hệ thống tự động tính khoảng cách thực tế distance_km và sắp xếp các quán từ gần nhất đến xa nhất.
Danh mục Quận/Huyện linh hoạt:
API GET /districts/ và GET /places/districts/ cung cấp danh sách các quận đang có dữ liệu để hiển thị Dropdown trên Mobile.
Công cụ CLI nạp & làm giàu dữ liệu (import_google_places):
Nạp dữ liệu từ scraper tự động, chống trùng lặp tuyệt đối, bảo toàn toàn bộ mẹo và lượt xác thực cũ của người dùng.
🛡️ 2. Cơ Chế Tín Nhiệm & Chống Gian Lận (Trust Tier & Anti-Spam)
Phân tầng tín nhiệm tự động (Trust Tier):
Tier 0: Địa điểm mới nạp, chưa có cư dân bảo chứng.
Tier 1: Có từ 1 - 2 cư dân địa phương xác thực (Huy hiệu tích xanh xác nhận).
Tier 2 (High Trust): Có từ 3 cư dân địa phương trở lên xác thực (Huy hiệu ngôi sao kèm số lượng cư dân bảo chứng).
Bảo chứng địa phương nghiêm ngặt:
Ràng buộc đúng quận (DISTRICT_MISMATCH): Cư dân Thủ Đức chỉ có quyền xác nhận các quán thuộc Thủ Đức, không được phép can thiệp quận khác.
Chống spam xác thực: Mỗi cư dân chỉ được xác thực 1 quán duy nhất 1 lần (UniqueConstraint).
Chống tự phong cư dân: Không tự động cấp tích xanh cho tài khoản tự khai thời gian; bắt buộc phải qua quy trình kiểm duyệt (unverified 
→
→ pending 
→
→ verified).
💡 3. Mẹo Ẩn Danh Độc Quyền Từ Cư Dân (Local Tips System)
Đặc quyền cư dân: Chỉ tài khoản đã được phê duyệt xác thực (verified) mới có quyền đăng mẹo cho quán.
Bảo vệ quyền riêng tư (Anonymous Tips): Thông tin người viết được ẩn danh trên API để tránh thiên vị hoặc tư thù cá nhân.
Mỗi quán 1 mẹo tối ưu (Upsert): Mỗi cư dân duy trì 1 mẹo duy nhất trên 1 quán, có toàn quyền sửa đổi hoặc xóa mẹo của mình bất kỳ lúc nào (POST /places/{id}/tips/, DELETE /places/{id}/tips/my-tip/).
📌 4. Tương Tác: Lưu Địa Điểm & Báo Cáo Sai Lệch (Bookmarks & Reports)
Lưu quán yêu thích (Bookmarks):
Lưu quán: POST /places/{id}/save/ (tự động ngăn chặn lưu trùng).
Bỏ lưu quán: DELETE /places/{id}/save/.
Xem danh sách quán đã bookmark: GET /places/saved/.
Kiểm tra trạng thái lưu is_saved (True/False) ngay trong chi tiết quán.
Cộng đồng phản ánh sai thông tin (POST /places/{id}/report/):
Người dùng báo cáo quán đã đóng cửa (CLOSED), sai lệch thông tin (WRONG_INFO), nội dung spam (SPAM) hoặc vấn đề khác (OTHER).
Đưa vào hàng đợi Admin để kiểm tra và cập nhật trạng thái địa điểm.
👤 5. Tài Khoản, Phân Quyền & Vinh Danh Cư Dân (Auth & Celebration UX)
Xác thực JWT an toàn:
Đăng ký (/auth/register/), Đăng nhập (/auth/login/), Đổi mới token (/auth/refresh/).
Đăng xuất an toàn có thu hồi token (/auth/logout/ - Token Blacklist).
Quản lý hồ sơ & Phân quyền (GET /auth/me/):
Trả về chi tiết quyền hạn: can_verify_places, can_add_tips.
Impact Metrics: Thống kê đóng góp của cư dân (Số quán đã xác thực, số mẹo đã viết, số quán đã giúp thăng hạng lên Tier 2).
Trải nghiệm Vinh danh Cư dân (Celebration UX):
Trả về cờ show_celebration_modal: true khi tài khoản vừa được duyệt để kích hoạt pop-up hiệu ứng pháo hoa Confetti trên app.
API POST /auth/ack-celebration/ để tắt pop-up sau khi người dùng đã xem.
Nộp hồ sơ cư dân: API POST /auth/verify-local/ đưa hồ sơ vào trạng thái chờ duyệt (pending).
🔔 6. Thông Báo Đẩy Firebase FCM & Hộp Thư In-App (Notifications)
Quản lý thiết bị di động:
Đăng ký FCM Device Token: POST /notifications/devices/ (hỗ trợ Android, iOS, Web).
Hủy token khi user đăng xuất: DELETE /notifications/devices/.
Hộp thư thông báo trong App:
Lấy danh sách thông báo: GET /notifications/.
Đánh dấu đã đọc: POST /notifications/{id}/read/ và POST /notifications/read-all/.
Thông báo kích hoạt tự động theo sự kiện (Event-driven Signals):
Duyệt cư dân: Gửi push "🎉 Hồ sơ cư dân của bạn đã được duyệt!" ngay khi admin duyệt.
Từ chối cư dân: Gửi push kèm lý do chi tiết giải thích cho người dùng.
Quán lên Tier 2: Tự động gửi push vinh danh tới tất cả cư dân từng xác nhận quán đó.
🛠️ 7. Cổng Quản Trị Vận Hành (Admin Portal)
Quản trị cư dân 1-Click (/admin/users/userprofile/):
Huy hiệu màu sắc trực quan: ⏳ Chờ phê duyệt (Vàng), ● Đã xác thực (Xanh), ✕ Bị từ chối (Đỏ).
Nút bấm duyệt nhanh [Duyệt] và [Từ chối] trực tiếp ngay trên từng dòng danh sách.
Bulk Actions duyệt/từ chối hàng loạt ứng viên.
Quản trị phản ánh (/admin/places/placereport/):
Xử lý các báo cáo quán đóng cửa/sai thông tin với nút Đã xử lý hoặc Bác bỏ.
Quản trị thông báo & Thiết bị (/admin/notifications/):
Theo dõi trạng thái token thiết bị, lịch sử thông báo, nút gửi lại Push Notification.
Quản trị địa điểm (/admin/places/place/):
Xem ảnh Thumbnail trực tiếp trên danh sách, thống kê tương tác (Lượt xác thực/Mẹo/Lưu).
⚙️ 8. Hạ Tầng Kỹ Thuật & Độ Tin Cậy (Architecture & Reliability)
Chuẩn hóa lỗi Unified Error Envelope: Toàn bộ API lỗi trả về cấu trúc đồng nhất {code, message, field_errors, request_id}.
Tài liệu OpenAPI / Swagger: Tự động tạo tài liệu tương tác đầy đủ tại /swagger/ và /redoc/.
Đóng gói Docker Compose: Chạy khép kín Django Web API + PostgreSQL 16 Alpine với Persistent Volume và Healthcheck.
Hỗ trợ Ngrok Tunnel: Tự động cấu hình ALLOWED_HOSTS và CSRF_TRUSTED_ORIGINS phục vụ test trực tiếp trên điện thoại thật.
Kiểm thử tự động: 21/21 Unit & Integration Tests pass 100%, đảm bảo không có lỗi hồi quy.