from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView,
    MeView,
    LogoutView,
    UserProfileView,
    SubmitLocalVerificationView,
    AcknowledgeCelebrationView,
)

app_name = 'users'

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/ack-celebration/', AcknowledgeCelebrationView.as_view(), name='ack_celebration'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/verify-local/', SubmitLocalVerificationView.as_view(), name='verify_local'),
]
