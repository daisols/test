# images/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ImageDownloadTaskViewSet, SatelliteImageViewSet

# Create the router.
router = DefaultRouter()
router.register(r'tasks', ImageDownloadTaskViewSet)
router.register(r'images', SatelliteImageViewSet)

# URL patterns.
urlpatterns = [
    path('', include(router.urls)),
]
