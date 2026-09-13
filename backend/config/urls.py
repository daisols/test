from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from service.weather.weatherView import (
    download_nasa_data,
    download_nasa_region,
    nasa_region_status,
    weather_data,
)


def health(_request):
    return JsonResponse({'service': 'FieldMoist API', 'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/', include('polygons.urls')),
    path('api/', include('images.urls')),
    path('api/', include('result_img.urls')),
    path('api/weather_data/', weather_data, name='weather_data'),
    path('api/weather_data/download/', download_nasa_data, name='download_nasa_data'),
    path('api/weather_data/region-status/', nasa_region_status, name='nasa_region_status'),
    path('api/weather_data/region-download/', download_nasa_region, name='download_nasa_region'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
