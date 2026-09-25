from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlaceViewSet

app_name = 'places'

router = DefaultRouter()
router.register(r'places', PlaceViewSet, basename='place')

urlpatterns = [
    path('', include(router.urls)),
]
