FROM python:3.11-slim

# Thiết lập biến môi trường Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn dự án
COPY . /app/

# Mở port 8000 chuẩn hóa
EXPOSE 8000

# Chạy server Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
