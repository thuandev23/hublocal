import json
import os
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.utils import timezone
from places.models import Place, CategoryChoices


def map_category(raw_category):
    """
    Tự động phân loại danh mục dựa trên từ khóa danh mục của Google Maps
    """
    if not raw_category:
        return CategoryChoices.EAT_DRINK

    cat_str = str(raw_category).lower()
    eat_keywords = ['restaurant', 'quán', 'nhà hàng', 'cà phê', 'cafe', 'coffee', 'ăn', 'uống', 'food', 'bakery', 'trà']
    play_keywords = ['bida', 'billiards', 'karaoke', 'game', 'công viên', 'park', 'cinema', 'rạp', 'giải trí', 'sân bóng']
    service_keywords = ['sửa xe', 'tiệm', 'pharmacy', 'thuốc', 'giặt', 'laundry', 'salon', 'cắt tóc', 'barber', 'ngân hàng', 'dịch vụ']

    for kw in eat_keywords:
        if kw in cat_str:
            return CategoryChoices.EAT_DRINK
    for kw in play_keywords:
        if kw in cat_str:
            return CategoryChoices.PLAY_ENTERTAINMENT
    for kw in service_keywords:
        if kw in cat_str:
            return CategoryChoices.SERVICES

    return CategoryChoices.EAT_DRINK


class Command(BaseCommand):
    help = 'Nhập hoặc cập nhật dữ liệu địa điểm thật từ file JSON xuất bởi google-maps-scraper'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Đường dẫn tới file JSON chứa kết quả scraper')
        parser.add_argument(
            '--district',
            type=str,
            default='Thủ Đức',
            help='Quận/Khu vực mặc định cho các địa điểm (mặc định: Thủ Đức)'
        )

    def handle(self, *args, **options):
        json_file_path = options['json_file']
        district = options['district']

        if not os.path.exists(json_file_path):
            self.stderr.write(self.style.ERROR(f"Không tìm thấy file: {json_file_path}"))
            return

        items = []
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        items = parsed
                    elif isinstance(parsed, dict):
                        items = parsed.get('results', [parsed])
                except json.JSONDecodeError:
                    # Hỗ trợ định dạng JSON Lines và tự động bỏ qua banner ASCII
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                items.append(json.loads(line))
                            except Exception:
                                continue
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Lỗi khi đọc file JSON: {e}"))
            return

        if not items:
            self.stderr.write(self.style.WARNING("Không tìm thấy bản ghi JSON hợp lệ nào trong file."))
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0
        now = timezone.now()

        for item in items:
            name = item.get('title') or item.get('name')
            if not name:
                skipped_count += 1
                continue

            address = item.get('address') or item.get('formatted_address') or ''
            place_id = item.get('place_id') or item.get('data_id') or item.get('cid')
            google_url = item.get('link') or item.get('url') or ''
            cover_image = item.get('main_photo') or item.get('photo') or item.get('featured_image') or ''

            # Parse tọa độ
            lat = None
            lng = None
            raw_lat = item.get('latitude') or item.get('lat')
            raw_lng = item.get('longitude') or item.get('lng')
            if raw_lat and raw_lng:
                try:
                    lat = Decimal(str(raw_lat))
                    lng = Decimal(str(raw_lng))
                except (InvalidOperation, TypeError):
                    lat, lng = None, None

            # Parse rating & review count
            rating = None
            raw_rating = item.get('rating') or item.get('total_score')
            if raw_rating:
                try:
                    rating = Decimal(str(raw_rating))
                except (InvalidOperation, TypeError):
                    rating = None

            review_count = 0
            raw_count = item.get('reviews') or item.get('reviews_count') or item.get('user_ratings_total')
            if raw_count:
                try:
                    review_count = int(raw_count)
                except (ValueError, TypeError):
                    review_count = 0

            # Xử lý danh sách reviews (hỗ trợ cả user_reviews của gosom scraper)
            reviews_list = []
            raw_reviews = item.get('user_reviews') or item.get('reviews_data') or item.get('detailed_reviews') or []
            if isinstance(raw_reviews, list):
                for rev in raw_reviews[:10]:  # Giữ tối đa 10 review mới nhất để tham khảo
                    if isinstance(rev, dict):
                        reviews_list.append({
                            'author': rev.get('Name') or rev.get('author') or 'Khách Google',
                            'rating': rev.get('Rating') or rev.get('rating') or rev.get('score'),
                            'text': rev.get('Description') or rev.get('text_original') or rev.get('text') or '',
                            'time': rev.get('When') or rev.get('published_at') or rev.get('time') or '',
                        })

            # Parse thời điểm cào dữ liệu gốc từ file (nếu có trường time / scraped_at)
            scraped_at = None
            raw_time = item.get('time') or item.get('scraped_at')
            if raw_time:
                from django.utils.dateparse import parse_datetime
                # Hỗ trợ định dạng ISO, cắt bớt nanoseconds nếu quá dài
                try:
                    if '.' in str(raw_time) and len(str(raw_time).split('.')[-1]) > 7:
                        base, rest = str(raw_time).split('.')
                        # Giữ 6 chữ số microsecond + timezone
                        tz_part = 'Z' if rest.endswith('Z') else ''
                        frac = rest.rstrip('Z')[:6]
                        clean_time = f"{base}.{frac}{tz_part}"
                    else:
                        clean_time = str(raw_time)
                    scraped_at = parse_datetime(clean_time)
                except Exception:
                    scraped_at = None

            # Tự động đoán danh mục
            category = map_category(item.get('category') or item.get('categories') or name)

            # Chống trùng: Ưu tiên tìm theo google_place_id, sau đó tới google_maps_url, sau đó (name + district)
            place = None
            if place_id:
                place = Place.objects.filter(google_place_id=place_id).first()
            if not place and google_url:
                place = Place.objects.filter(google_maps_url=google_url).first()
            if not place:
                place = Place.objects.filter(name__iexact=name.strip(), district__iexact=district.strip()).first()

            if place:
                # ĐÃ TỒN TẠI: Chỉ cập nhật dữ liệu nguồn, KHÔNG đè mẹo của cư dân
                if place_id and not place.google_place_id:
                    place.google_place_id = place_id
                if google_url:
                    place.google_maps_url = google_url
                if rating is not None:
                    place.google_rating = rating
                if review_count > 0:
                    place.google_review_count = review_count
                if reviews_list:
                    place.google_reviews = reviews_list
                # Chỉ cập nhật google_scraped_at nếu trong file có timestamp cào mới
                if scraped_at:
                    place.google_scraped_at = scraped_at

                # Cập nhật tọa độ/ảnh nếu quán chưa có
                if not place.latitude and lat:
                    place.latitude = lat
                if not place.longitude and lng:
                    place.longitude = lng
                if not place.cover_image and cover_image:
                    place.cover_image = cover_image

                place.save()
                updated_count += 1
            else:
                # TẠO MỚI
                Place.objects.create(
                    name=name.strip(),
                    category=category,
                    district=district.strip(),
                    address=address.strip() or f"{district}, TP.HCM",
                    latitude=lat,
                    longitude=lng,
                    cover_image=cover_image or '',
                    google_place_id=place_id,
                    google_maps_url=google_url,
                    google_rating=rating,
                    google_review_count=review_count,
                    google_reviews=reviews_list,
                    google_scraped_at=scraped_at or now,
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Hoàn thành import dữ liệu Google Maps:\n"
            f"- Đã thêm mới: {created_count} địa điểm\n"
            f"- Đã cập nhật nguồn: {updated_count} địa điểm\n"
            f"- Bỏ qua: {skipped_count} dòng không hợp lệ"
        ))
