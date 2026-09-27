import uuid
from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Chuẩn hóa cấu trúc lỗi trả về cho toàn bộ API của HubLocal.
    Mẫu response chuẩn cho Frontend:
    {
      "code": "ERROR_CODE",
      "message": "Mô tả lỗi dễ hiểu cho người dùng",
      "field_errors": { "field_name": ["chi tiết lỗi"] },
      "request_id": "uuid-v4"
    }
    """
    response = exception_handler(exc, context)
    request = context.get('request')
    request_id = getattr(request, 'request_id', str(uuid.uuid4()))

    if response is None:
        # Lỗi hệ thống không xử lý được (500)
        return Response({
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Đã có lỗi xảy ra trên hệ thống. Vui lòng thử lại sau.",
            "field_errors": {},
            "request_id": request_id
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = response.data
    code = "API_ERROR"
    message = "Yêu cầu không thể thực hiện."
    field_errors = {}

    # Xác định mã lỗi chuẩn hóa
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
        message = "Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại."
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        code = getattr(exc, 'code', 'PERMISSION_DENIED')
        if isinstance(data, dict) and 'code' in data:
            code = data.get('code')
        message = data.get('error', data.get('detail', 'Bạn không có quyền thực hiện hành động này.')) if isinstance(data, dict) else str(data)
    elif response.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
        message = data.get('error', data.get('detail', 'Không tìm thấy dữ liệu yêu cầu.')) if isinstance(data, dict) else "Không tìm thấy tài nguyên."
    elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        code = "RATE_LIMIT_EXCEEDED"
        message = "Bạn đã thực hiện thao tác quá thường xuyên. Vui lòng chờ ít phút."
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        code = "VALIDATION_ERROR"
        message = "Dữ liệu gửi lên không hợp lệ."
        if isinstance(data, dict):
            if 'error' in data:
                message = data['error']
                code = data.get('code', 'BAD_REQUEST')
            else:
                field_errors = data
        elif isinstance(data, list):
            message = "; ".join(str(item) for item in data)

    # Đóng gói chuẩn response
    standardized_data = {
        "code": code,
        "message": message,
        "field_errors": field_errors if field_errors else {},
        "request_id": request_id
    }

    response.data = standardized_data
    return response
