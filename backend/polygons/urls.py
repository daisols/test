# polygons/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PolygonViewSet

router = DefaultRouter()
router.register(r'polygons', PolygonViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
