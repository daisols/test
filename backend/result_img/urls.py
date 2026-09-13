from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ResultImgViewSet
router = DefaultRouter()
router.register(r'result_img', ResultImgViewSet)
urlpatterns = [
    path('', include(router.urls)),
]