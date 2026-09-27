# 🚢 Cẩm Nang Triển Khai Sản Xuất (Production Deployment Guide) — HubLocal

Tài liệu này cung cấp quy trình từng bước dành cho DevOps / System Administrator khi đưa ứng dụng **HubLocal Backend** từ môi trường phát triển lên máy chủ thực tế (Production Server: Ubuntu / Debian / Cloud VPS).

---

## 📋 1. Checklist Bảo Mật & Sẵn Sàng Sản Xuất (Pre-flight Checklist)

Trước khi kích hoạt public domain:
- [ ] `DEBUG=0` trong file `.env`.
- [ ] `SECRET_KEY` được tạo ngẫu nhiên, độ dài tối thiểu 50 ký tự (`python -c "import secrets; print(secrets.token_urlsafe(50))"`).
- [ ] `ALLOWED_HOSTS` chỉ định danh sách tên miền cụ thể (ví dụ: `api.hublocal.vn,admin.hublocal.vn`), không dùng `*`.
- [ ] Cấu hình chứng chỉ SSL/TLS (HTTPS) thông qua Let's Encrypt / Certbot.
- [ ] Cổng Database `5432` không mở ra Internet bên ngoài (`0.0.0.0:5432`), chỉ cho phép nội bộ Docker network truy cập.
- [ ] Phân quyền thư mục file tĩnh và media an toàn.

---

## 🏗️ 2. Cài Đặt Môi Trường Máy Chủ (Server Provisioning)

### Bước 1: Cài đặt Docker & Docker Compose trên Ubuntu 22.04 / 24.04
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw ca-certificates gnupg

# Cài đặt Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Phân quyền cho user hiện tại chạy docker không cần sudo
sudo usermod -aG docker $USER
```

### Bước 2: Thiết lập Tường Lửa (UFW Firewall)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## ⚙️ 3. Quy Trình Triển Khai Ứng Dụng (Step-by-Step Deployment)

### 1. Clone Mã Nguồn Dự Án
```bash
cd /opt
sudo git clone <REPO_URL> hublocal
sudo chown -R $USER:$USER /opt/hublocal
cd /opt/hublocal
```

### 2. Thiết lập Biến Môi Trường Production
Tạo file `.env`:
```bash
nano .env
```
Nội dung mẫu chuẩn Production:
```env
DEBUG=0
SECRET_KEY=s7D9f#kL!29xPmQ@8zWbV4cR1tY6uI0oAeG3jH5nK8mF2vC4xZ9
ALLOWED_HOSTS=api.hublocal.vn,127.0.0.1,web

WEB_PORT=8123

DB_NAME=hublocal_prod_db
DB_USER=hublocal_prod_user
DB_PASSWORD=MatKhauDatabaseCucKyManhVaPhucTap2026!
DB_HOST=db
DB_PORT=5432
```

### 3. Đóng Gói Và Kích Hoạt Container
```bash
docker compose up --build -d
```

### 4. Thu Thập Static Files & Áp Dụng Migrations
```bash
docker compose exec web python manage.py collectstatic --noinput
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## 🔒 4. Cấu Hình Nginx Reverse Proxy & SSL (HTTPS)

Cài đặt Nginx trên host:
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Tạo cấu hình virtual host `/etc/nginx/sites-available/hublocal`:
```nginx
server {
    listen 80;
    server_name api.hublocal.vn;

    client_max_body_size 20M;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    location / {
        proxy_pass http://127.0.0.1:8123;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }

    location /static/ {
        alias /opt/hublocal/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }
}
```

Kích hoạt site và xin chứng chỉ SSL miễn phí:
```bash
sudo ln -s /etc/nginx/sites-available/hublocal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Đăng ký chứng chỉ Let's Encrypt SSL
sudo certbot --nginx -d api.hublocal.vn
```

---

## 💾 5. Tự Động Hóa Sao Lưu Dữ Liệu (Automated Backups)

Tạo script sao lưu `/opt/hublocal/scripts/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/hublocal"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

docker compose -f /opt/hublocal/docker-compose.yml exec -T db pg_dump -U hublocal_prod_user -d hublocal_prod_db | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Giữ lại các bản backup trong 30 ngày gần nhất
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -exec rm {} \;
```
Cấp quyền thực thi và đặt Cron Job chạy hàng ngày lúc 02:00 sáng:
```bash
chmod +x /opt/hublocal/scripts/backup.sh
crontab -e
```
Thêm dòng:
```cron
0 2 * * * /opt/hublocal/scripts/backup.sh > /dev/null 2>&1
```

---

## 📈 6. Giám Sát & Xử Lý Sự Cố (Monitoring & Troubleshooting)

| Triệu chứng | Kiểm tra nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| **API trả về 502 Bad Gateway** | `docker compose ps` | Container `django_web` bị tắt. Chạy `docker compose logs web` kiểm tra lỗi crash và `docker compose restart web`. |
| **Lỗi kết nối cơ sở dữ liệu** | `docker compose logs db` | Kiểm tra healthcheck của PostgreSQL. Đảm bảo thông số `DB_NAME`, `DB_USER`, `DB_PASSWORD` trong `.env` khớp với `db`. |
| **Treo hoặc tải chậm** | `htop` / `docker stats` | Kiểm tra CPU/RAM container. Xem lại slow query log hoặc tăng tài nguyên VPS. |
| **Không tải được ảnh/CSS admin** | Cấu hình Nginx `/static/` | Chạy lại `python manage.py collectstatic --noinput` và kiểm tra quyền đọc thư mục `staticfiles`. |
