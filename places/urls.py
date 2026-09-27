from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlaceViewSet

app_name = 'places'

router = DefaultRouter()
router.register(r'places', PlaceViewSet, basename='place')

urlpatterns = [
    path('districts/', PlaceViewSet.as_view({'get': 'districts'}), name='districts-list'),
    path('', include(router.urls)),
]
