from datetime import datetime
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import geopandas as gpd
from pymysql import install_as_MySQLdb
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union
from django.conf import settings
from django.db import transaction
from .models import Polygon
from .serializers import PolygonSerializer, PolygonCreateSerializer
from result_img.models import ResultImg

logger = logging.getLogger(__name__)


_SHP_SUFFIXES = {'.shp', '.shx', '.dbf', '.prj', '.cpg'}


def _stage_shapefile_uploads(uploads, staging_dir):
    """Write uploaded SHP components to a temporary, flat-safe workspace."""
    for upload in uploads:
        filename = Path(upload.name or '').name
        suffix = Path(filename).suffix.lower()
        if suffix == '.zip':
            with zipfile.ZipFile(upload) as archive:
                for member in archive.infolist():
                    member_name = member.filename.replace('\\', '/')
                    parts = PurePosixPath(member_name).parts
                    if member.is_dir() or not parts or any(part in {'', '.', '..'} for part in parts):
                        continue
                    member_suffix = Path(parts[-1]).suffix.lower()
                    if member_suffix not in _SHP_SUFFIXES:
                        continue
                    destination = staging_dir / Path(parts[-1]).name
                    with archive.open(member) as source, destination.open('wb') as target:
                        shutil.copyfileobj(source, target)
            continue
        if suffix not in _SHP_SUFFIXES:
            raise ValueError('Only .zip, .shp, .shx, .dbf, .prj, and .cpg files are supported.')
        destination = staging_dir / filename
        with destination.open('wb') as target:
            for chunk in upload.chunks():
                target.write(chunk)


def _read_shapefile_boundary(shp_path):
    frame = gpd.read_file(shp_path)
    if frame.empty:
        raise ValueError('The Shapefile contains no features.')
    if frame.crs is None:
        raise ValueError('The Shapefile must include a .prj file with a CRS.')
    frame = frame.to_crs('EPSG:4326')
    geometries = [geometry for geometry in frame.geometry if geometry is not None and not geometry.is_empty]
    if not geometries:
        raise ValueError('The Shapefile contains no valid geometry.')
    geometry = unary_union(geometries)
    if geometry.geom_type == 'MultiPolygon':
        geometry = max(geometry.geoms, key=lambda item: item.area)
    if not isinstance(geometry, ShapelyPolygon):
        raise ValueError('The Shapefile must contain Polygon or MultiPolygon geometry.')
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or geometry.geom_type != 'Polygon':
        raise ValueError('The Shapefile boundary is invalid.')
    return [[float(longitude), float(latitude)] for longitude, latitude in geometry.exterior.coords]


class PolygonViewSet(viewsets.ModelViewSet):
    queryset = Polygon.objects.all()
    serializer_class = PolygonSerializer

    def get_serializer_class(self):
        'Select the serializer for the current action.'
        if self.action == 'create':
            return PolygonCreateSerializer
        return PolygonSerializer

    def create(self, request, *args, **kwargs):
        'Create a polygon.'
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(
        detail=False,
        methods=['post'],
        url_path='from-shp',
        parser_classes=[MultiPartParser, FormParser],
    )
    def from_shp(self, request, *args, **kwargs):
        """Create a polygon from an uploaded ESRI Shapefile bundle."""
        name = str(request.data.get('name', '')).strip()
        uploads = request.FILES.getlist('files') or request.FILES.getlist('shapefile')
        if not uploads:
            upload = request.FILES.get('file') or request.FILES.get('shp')
            uploads = [upload] if upload else []
        if not name:
            return Response({'name': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        if not uploads:
            return Response(
                {'files': ['Upload a .zip Shapefile bundle or the .shp/.shx/.dbf/.prj files.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with tempfile.TemporaryDirectory(prefix='fieldmoist-shp-') as temp_dir:
                staging = Path(temp_dir)
                _stage_shapefile_uploads(uploads, staging)
                shp_path = next(
                    (path for path in staging.rglob('*') if path.is_file() and path.suffix.lower() == '.shp'),
                    None,
                )
                if shp_path is None:
                    raise ValueError('The upload does not contain a .shp file.')
                coordinates = _read_shapefile_boundary(shp_path)

                serializer = PolygonCreateSerializer(data={
                    'name': name,
                    'wgs84_coordinates': coordinates,
                })
                serializer.is_valid(raise_exception=True)
                with transaction.atomic():
                    polygon = serializer.save()
                    media_dir = Path(settings.MEDIA_ROOT) / 'images' / str(polygon.id) / 'shp'
                    media_dir.mkdir(parents=True, exist_ok=True)
                    for source in staging.rglob('*'):
                        if source.is_file() and source.suffix.lower() in {'.shp', '.shx', '.dbf', '.prj', '.cpg'}:
                            shutil.copy2(source, media_dir / source.name)
                    polygon.wgs84_shp_dir = os.path.relpath(media_dir, settings.MEDIA_ROOT).replace('\\', '/')
                    polygon.save(update_fields=['wgs84_shp_dir', 'updated_at'])
                return Response(PolygonSerializer(polygon).data, status=status.HTTP_201_CREATED)
        except DRFValidationError:
            raise
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            return Response({'files': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Failed to create polygon from uploaded Shapefile.')
            detail = str(exc).strip()
            message = 'The Shapefile could not be read. Check that all components and the .prj CRS file are present.'
            if settings.DEBUG and detail:
                message = f'{message} Details: {detail}'
            return Response(
                {'files': [message]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def list(self, request, *args, **kwargs):
        'List polygons.'

        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        'Retrieve polygon details.'
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        'Update a polygon.'
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        'Partially update a polygon.'
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        'Delete a polygon.'
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='image-dates')
    def image_dates(self, request, pk=None):
        'Return acquisition dates and image IDs for the polygon and requested satellite.'
        polygon = self.get_object()
        satellite = request.query_params.get('satellite', None)
        start_day = request.query_params.get('start_day', None)
        end_day = request.query_params.get('end_day', None)

        if not satellite:
            return Response({
                'status': 'error',
                'message': 'Provide the satellite parameter.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Import SatelliteImage from the images application.
        from images.models import SatelliteImage

        # Query acquisition dates for this polygon and satellite.
        images = (SatelliteImage.objects.filter(
            polygon=polygon,
            satellite=satellite,
        )).order_by('shoot_time')

        # Normalize the start_day parameter.
        if start_day and start_day != '':
            try:
                # Accept several common date formats.
                if len(start_day) == 10 and start_day[4] == '-' and start_day[7] == '-':
                    # YYYY-MM-DD format.
                    start_date = datetime.strptime(start_day, '%Y-%m-%d')
                elif len(start_day) == 8:
                    # YYYYMMDD format.
                    start_date = datetime.strptime(start_day, '%Y%m%d')
                else:
                    # Try other formats.
                    start_date = datetime.strptime(start_day, '%Y-%m-%d')

                images = images.filter(shoot_time__gte=start_date)
            except ValueError:
                return Response({
                    'status': 'error',
                    'message': f'Invalid start date: {start_day}. Use YYYY-MM-DD.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Normalize the end_day parameter.
        if end_day and end_day != '':
            try:
                # Accept several common date formats.
                if len(end_day) == 10 and end_day[4] == '-' and end_day[7] == '-':
                    # YYYY-MM-DD format.
                    end_date = datetime.strptime(end_day, '%Y-%m-%d')
                elif len(end_day) == 8:
                    # YYYYMMDD format.
                    end_date = datetime.strptime(end_day, '%Y%m%d')
                else:
                    # Try other formats.
                    end_date = datetime.strptime(end_day, '%Y-%m-%d')

                # Include the end date through 23:59:59.
                from datetime import timedelta
                end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
                images = images.filter(shoot_time__lte=end_date)
            except ValueError:
                return Response({
                    'status': 'error',
                    'message': f'Invalid end date: {end_day}. Use YYYY-MM-DD.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Exclude records with NULL shoot_time.
        images = images.filter(shoot_time__isnull=False)

        # Build the date and ID list.
        dates_and_ids = []
        for image in images:
            dates_and_ids.append({
                'id': image.id,
                'date': image.shoot_time.strftime('%Y-%m-%d')
            })

        print(dates_and_ids)

        return Response({
            'polygon_id': polygon.id,
            'satellite': satellite,
            'dates_and_ids': dates_and_ids,
            'count': len(dates_and_ids)
        })
    @action(detail=True, methods=['get'], url_path='result-set-list')
    def get_result_set_list(self, request, pk=None):
        result_set = ResultImg.objects.filter(polygon=self.get_object(), is_delete=False)
        result_set_dateRange_id_dict = [
            {
                'start_date':result_set.start_day,
                'end_date':result_set.end_day,
                "result_set_id":result_set.id,
                "status":result_set.status,
            }
            for result_set in result_set
        ]
        return Response(result_set_dateRange_id_dict, status=status.HTTP_200_OK)


