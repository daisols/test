import os.path
import re
import shutil
import threading
from pathlib import Path

import rasterio
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from .models import ResultImg
from images.models import ImageDownloadTask
from polygons.models import Polygon
from polygons.tools import wgs84_to_gcj02
from polygons.views import _read_shapefile_boundary
from .serializers import ResultImgCreateSerializer, ResultImgListSerializer, ResultImgSerializer

from config.settings import MEDIA_ROOT
from service.transform_tif.transform_tif import run

from service.weather.moistureListByLngLat import get_min_max_arv_moisture


def _result_absolute_dir(result_dir):
    path = Path(result_dir)
    if not path.is_absolute():
        path = Path(MEDIA_ROOT) / path
    return path.resolve(strict=False)


from service.test_workspace import reset_test_workspace as _reset_test_workspace


def _raster_bounds_payload(tif_path):
    with rasterio.open(tif_path) as dataset:
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise ValueError(f"{Path(tif_path).name} must use EPSG:4326")
        bounds = dataset.bounds

    wgs_corners = [
        (bounds.left, bounds.bottom),
        (bounds.left, bounds.top),
        (bounds.right, bounds.bottom),
        (bounds.right, bounds.top),
    ]
    gcj_corners = [wgs84_to_gcj02(lng, lat) for lng, lat in wgs_corners]

    return {
        'wgs84': {
            'southwest': [bounds.left, bounds.bottom],
            'northeast': [bounds.right, bounds.top],
        },
        'gcj02': {
            'southwest': [
                min(point[0] for point in gcj_corners),
                min(point[1] for point in gcj_corners),
            ],
            'northeast': [
                max(point[0] for point in gcj_corners),
                max(point[1] for point in gcj_corners),
            ],
        },
    }


class ResultImgViewSet(viewsets.ModelViewSet):
    # Allow only POST, GET and DELETE requests.
    http_method_names = ['get','post','delete']
    queryset = ResultImg.objects.all()
    serializer_class = ResultImgSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    def get_queryset(self):
        'List result sets.'
        queryset = super().get_queryset()
        queryset = queryset.filter(is_delete=False)
        return queryset
    def get_serializer_class(self):
        if self.action == 'create':
            return ResultImgCreateSerializer
        elif self.action == 'list':
            return ResultImgListSerializer
        else:
            return ResultImgSerializer
    def list(self, request, *args, **kwargs):
        'List result sets.'
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        'Retrieve an instance by ID.'
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        'Create a result set.'
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        polygon = serializer.validated_data['polygon']
        polygon_id = polygon.id
        start_day = serializer.validated_data['start_day'].strftime('%Y-%m-%d')
        end_day = serializer.validated_data['end_day'].strftime('%Y-%m-%d')

        generation_mode = serializer.validated_data.get('generation_mode', 'online')
        offline_files = request.FILES.getlist('offline_files')
        offline_satellites = request.data.getlist('offline_satellites') if hasattr(request.data, 'getlist') else []
        moisture_files = request.FILES.getlist('soil_moisture_files')
        excel_upload = request.FILES.get('measurement_excel')
        smap_count = sum(1 for value in offline_satellites if value == 'smap')
        is_test_preset = generation_mode == 'offline' and polygon_id == 82 and polygon.name.lower() == 'test' and not offline_files and not moisture_files and not excel_upload
        if generation_mode == 'offline' and not is_test_preset and (
            (moisture_files and smap_count < 2) or
            (not moisture_files and len(offline_files) < 6)
        ):
            return Response({'offline_files': ['Upload at least two SMAP GeoTIFF files. Sentinel-1/2 files are optional only when precomputed soil-moisture GeoTIFF files are supplied.']}, status=status.HTTP_400_BAD_REQUEST)

        # Check for an existing instance.
        last_instance = ResultImg.objects.filter(polygon=polygon_id,start_day=start_day,end_day=end_day).first()
        if last_instance:
            running_statuses = {
                'Waiting', 'waiting', 'queued', 'downloading', 'filtering',
                'preprocessing', 'processing', 'solving', 'colorizing',
            }
            if last_instance.status in running_statuses:
                return Response({
                    'detail': 'A task for this area and date range is already running. Please do not submit it again.',
                    'status': last_instance.status,
                    'process': last_instance.process,
                    'id': last_instance.id,
                }, status=status.HTTP_409_CONFLICT)
            last_instance.is_delete = False
            last_instance.generation_mode = generation_mode
            last_instance.local_moisture_dir = None
            last_instance.measurement_excel_path = None
            if is_test_preset:
                self._apply_test_preset(last_instance)
            if generation_mode == 'offline':
                self._register_offline_files(last_instance, offline_files, offline_satellites)
            if moisture_files:
                last_instance.local_moisture_dir = self._store_moisture_files(last_instance, moisture_files)
            if excel_upload:
                last_instance.measurement_excel_path = self._store_measurement_excel(last_instance, excel_upload)
            if last_instance.status == 'failed' or is_test_preset:
                last_instance.status = 'Waiting'
                last_instance.process = 0
                last_instance.save(update_fields=['is_delete', 'status', 'process', 'generation_mode', 'local_moisture_dir', 'measurement_excel_path'])

                def retry_task(instance_id):
                    try:
                        instance = ResultImg.objects.get(id=instance_id)
                        run(instance)
                        if instance.status != 'failed':
                            instance.status = 'completed'
                            instance.process = 100
                            instance.save(update_fields=['status', 'process'])
                    except Exception:
                        instance.status = 'failed'
                        instance.save(update_fields=['status'])

                thread = threading.Thread(target=retry_task, args=(last_instance.id,))
                thread.daemon = True
                thread.start()
            else:
                last_instance.save(update_fields=['is_delete', 'generation_mode', 'local_moisture_dir', 'measurement_excel_path'])
            serializer = ResultImgSerializer(last_instance)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        # Create the result directory.
        result_dir = os.path.join(MEDIA_ROOT,'images', str(polygon_id), f'{start_day}_{end_day}')
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        # Save the instance.
        save_kwargs = {'result_dir': result_dir, 'generation_mode': generation_mode}
        # The bundled offline test data is intentionally kept addressable as
        # Dataset 82. Use that primary key when it is available; otherwise
        # retain Django's normal auto-increment behavior.
        if is_test_preset and not ResultImg.objects.filter(pk=82).exists():
            save_kwargs['id'] = 82
        instance = serializer.save(**save_kwargs)
        if generation_mode == 'offline':
            self._register_offline_files(instance, offline_files, offline_satellites)
        if moisture_files:
            instance.local_moisture_dir = self._store_moisture_files(instance, moisture_files)
        if excel_upload:
            instance.measurement_excel_path = self._store_measurement_excel(instance, excel_upload)
        if is_test_preset:
            self._apply_test_preset(instance)
        if moisture_files or excel_upload:
            instance.save(update_fields=['local_moisture_dir', 'measurement_excel_path'])

        # Run processing in a background thread.
        def background_task(instance_id):
            try:
                # Fetch a fresh instance inside the worker thread.
                instance = ResultImg.objects.get(id=instance_id)
                run(instance)
                if instance.status != 'failed':
                    instance.status = 'completed'
                    instance.process = 100
                    instance.save(update_fields=['status', 'process'])
            except Exception as e:
                instance.status = 'failed'
                instance.save(update_fields=['status'])

        thread = threading.Thread(target=background_task, args=(instance.id,))
        thread.daemon = True
        thread.start()

        response_data = ResultImgSerializer(instance).data
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)

    @staticmethod
    def _register_offline_files(instance, uploads, satellites):
        """Copy local satellite files and create the records consumed by run()."""
        from images.models import SatelliteImage
        media_root = Path(MEDIA_ROOT)
        for index, upload in enumerate(uploads):
            satellite = satellites[index] if index < len(satellites) else ''
            satellite = satellite if satellite in {'sentinel-1', 'sentinel-2', 'smap'} else None
            if not satellite:
                lower_name = (upload.name or '').lower()
                satellite = 'sentinel-1' if ('sentinel-1' in lower_name or 's1' in lower_name) else 'sentinel-2' if ('sentinel-2' in lower_name or 's2' in lower_name) else 'smap' if 'smap' in lower_name else None
            match = re.search(r'(\d{4}[-_]\d{2}[-_]\d{2}|\d{8})', upload.name or '')
            if not satellite or not match:
                raise ValueError(f'Could not determine satellite type/date from {upload.name}. Include satellite name and YYYY-MM-DD in each filename.')
            raw_date = match.group(1).replace('_', '-').replace('-', '')
            shoot_date = parse_date(f'{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}')
            if not shoot_date:
                raise ValueError(f'Invalid date in offline file {upload.name}.')
            destination_dir = media_root / 'images' / str(instance.polygon_id) / 'offline' / satellite
            destination_dir.mkdir(parents=True, exist_ok=True)
            safe_name = Path(upload.name).name
            destination = destination_dir / safe_name
            with destination.open('wb') as target:
                for chunk in upload.chunks():
                    target.write(chunk)
            relative_path = os.path.relpath(destination, media_root).replace('\\', '/')
            SatelliteImage.objects.update_or_create(
                polygon_id=instance.polygon_id,
                satellite=satellite,
                shoot_time=shoot_date,
                defaults={'name': safe_name, 'image': relative_path, 'file_size': destination.stat().st_size},
            )

    @staticmethod
    def _apply_test_preset(instance):
        """Attach the bundled offline test inputs without browser uploads."""
        from images.models import SatelliteImage
        media_root = Path(MEDIA_ROOT)
        base = media_root / 'images' / '82'
        moisture_dir = base / '82' / 'local_soil_moisture'
        measurement_path = base / '82' / 'measurements' / 'measurements.xlsx'
        smap_dir = base / 'offline' / 'smap'
        if not moisture_dir.is_dir() or not measurement_path.is_file() or not smap_dir.is_dir():
            raise ValueError('The offline test preset is incomplete under media/images/82.')
        instance.local_moisture_dir = os.path.relpath(moisture_dir, media_root).replace('\\', '/')
        instance.measurement_excel_path = os.path.relpath(measurement_path, media_root).replace('\\', '/')
        for path in sorted(smap_dir.glob('*.tif')) + sorted(smap_dir.glob('*.tiff')):
            match = re.search(r'(\d{4}[-_]\d{2}[-_]\d{2}|\d{8})', path.name)
            if not match:
                continue
            raw = match.group(1).replace('-', '').replace('_', '')
            shoot_date = parse_date(f'{raw[:4]}-{raw[4:6]}-{raw[6:8]}')
            if not shoot_date:
                continue
            relative = os.path.relpath(path, media_root).replace('\\', '/')
            SatelliteImage.objects.update_or_create(
                polygon_id=instance.polygon_id,
                satellite='smap',
                shoot_time=shoot_date,
                defaults={'name': path.name, 'image': relative, 'file_size': path.stat().st_size},
            )
        instance.save(update_fields=['local_moisture_dir', 'measurement_excel_path'])

    @action(detail=False, methods=['get'], url_path='offline-test-preset')
    def offline_test_preset(self, request):
        """Return (and, if necessary, register) the bundled ``test`` preset."""
        base = Path(MEDIA_ROOT) / 'images' / '82'
        shp_candidates = sorted((base / 'shp').glob('*.shp'))
        if not shp_candidates:
            return Response({'detail': 'The offline test boundary is missing from media/images/82/shp.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            wgs84 = _read_shapefile_boundary(shp_candidates[0])
        except Exception as exc:
            return Response({'detail': f'Could not read the offline test boundary: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
        polygon = Polygon.objects.filter(name='test').first()
        created = polygon is None
        if created:
            polygon = Polygon(
                # Keep the preset's polygon id aligned with its bundled
                # media/images/82 directory when that id is still unused.
                id=82 if not Polygon.objects.filter(pk=82).exists() else None,
                name='test',
                gcj02_coordinates=[list(wgs84_to_gcj02(lng, lat)) for lng, lat in wgs84],
                wgs84_coordinates=wgs84,
            )
            polygon.save(force_insert=True)
        if not created and not polygon.wgs84_coordinates:
            polygon.wgs84_coordinates = wgs84
            polygon.gcj02_coordinates = [list(wgs84_to_gcj02(lng, lat)) for lng, lat in wgs84]
            polygon.save(update_fields=['wgs84_coordinates', 'gcj02_coordinates'])
        return Response({
            'polygon_id': polygon.id,
            'name': polygon.name,
            'start_day': '2018-05-01',
            'end_day': '2018-05-24',
            'gcj02_coordinates': polygon.gcj02_coordinates,
            'wgs84_coordinates': polygon.wgs84_coordinates,
            'local_moisture_dir': 'images/82/82/local_soil_moisture',
            'local_moisture_path': 'media/images/82/82/local_soil_moisture',
            'measurement_excel_path': 'images/82/82/measurements/measurements.xlsx',
            'measurement_excel_display_path': 'media/images/82/82/measurements/measurements.xlsx',
            'smap_dir': 'images/82/offline/smap',
            'smap_path': 'media/images/82/offline/smap',
            'model_path': 'media/images/82/2018-05-01_2018-05-24/process/shared_ml_model_rf.pkl',
            'shp_path': 'media/images/82/shp',
        })

    @staticmethod
    def _store_moisture_files(instance, uploads):
        target_dir = Path(MEDIA_ROOT) / 'images' / str(instance.polygon_id) / str(instance.id) / 'local_soil_moisture'
        target_dir.mkdir(parents=True, exist_ok=True)
        for upload in uploads:
            destination = target_dir / Path(upload.name or 'soil_moisture.tif').name
            with destination.open('wb') as target:
                for chunk in upload.chunks():
                    target.write(chunk)
        return os.path.relpath(target_dir, MEDIA_ROOT).replace('\\', '/')

    @staticmethod
    def _store_measurement_excel(instance, upload):
        target_dir = Path(MEDIA_ROOT) / 'images' / str(instance.polygon_id) / str(instance.id) / 'measurements'
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / Path(upload.name or 'measurements.xlsx').name
        with destination.open('wb') as target:
            for chunk in upload.chunks():
                target.write(chunk)
        return os.path.relpath(destination, MEDIA_ROOT).replace('\\', '/')

    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        instance = self.get_object()
        # Download tasks keep the detailed exception (for example an Earth
        # Engine authentication/network error). Expose it alongside the result
        # progress so the UI can tell the user why a generation job stopped.
        download_task = ImageDownloadTask.objects.filter(
            polygon_id=instance.polygon_id,
            start_day=instance.start_day,
            end_day__gte=instance.end_day,
        ).order_by('-created_at').first()
        return Response({
            'id': instance.id,
            'status': instance.status,
            'process': instance.process,
            'start_day': instance.start_day,
            'end_day': instance.end_day,
            'error': download_task.error_message if download_task else None,
        })

    @action(detail=True, methods=['post'], url_path='rerun-test')
    def rerun_test(self, request, pk=None):
        """Rerun only the bundled offline ``test`` dataset."""
        instance = self.get_object()
        if not (
            instance.generation_mode == 'offline'
            and instance.polygon_id == 82
            and instance.polygon.name.lower() == 'test'
        ):
            return Response({'detail': 'This rerun action is available only for the offline test dataset.'}, status=status.HTTP_400_BAD_REQUEST)
        running_statuses = {
            'Waiting', 'waiting', 'queued', 'downloading', 'filtering',
            'preprocessing', 'processing', 'solving', 'colorizing',
        }
        if instance.status in running_statuses:
            return Response({
                'detail': 'The test task is already running.',
                'id': instance.id,
                'status': instance.status,
                'process': instance.process,
            }, status=status.HTTP_409_CONFLICT)

        try:
            _reset_test_workspace(instance.result_dir)
        except OSError as exc:
            return Response(
                {'detail': f'Could not reset the test workspace before rerun: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        instance.status = 'Waiting'
        instance.process = 0
        instance.is_delete = False
        instance.save(update_fields=['status', 'process', 'is_delete'])

        def background_task(instance_id):
            try:
                current = ResultImg.objects.get(id=instance_id)
                run(current)
                if current.status != 'failed':
                    current.status = 'completed'
                    current.process = 100
                    current.save(update_fields=['status', 'process'])
            except Exception:
                current = ResultImg.objects.get(id=instance_id)
                current.status = 'failed'
                current.save(update_fields=['status'])

        thread = threading.Thread(target=background_task, args=(instance.id,))
        thread.daemon = True
        thread.start()
        return Response(ResultImgSerializer(instance).data, status=status.HTTP_202_ACCEPTED)

    def destroy(self, request, *args, **kwargs):
        'Soft-delete a result set.'
        instance = self.get_object()
        if request.query_params.get('purge', '').lower() in {'1', 'true', 'yes'}:
            result_dir = _result_absolute_dir(instance.result_dir)
            polygon = instance.polygon
            polygon_media_dir = Path(MEDIA_ROOT) / 'images' / str(polygon.id)
            instance.delete()
            # Remove the area only when this was its last result set. This
            # keeps shared polygon boundaries available to other datasets.
            if not ResultImg.objects.filter(polygon_id=polygon.id, is_delete=False).exists():
                polygon.delete()
                # A polygon's media directory contains its boundary, source
                # imagery, cached NASA data, processing workspace, and final
                # products. Once its last result set is purged, remove the
                # complete directory (for example images/84 or images/85).
                if polygon_media_dir.exists() and polygon_media_dir.is_dir():
                    import shutil
                    shutil.rmtree(polygon_media_dir, ignore_errors=True)
            if result_dir.exists() and result_dir.is_dir():
                import shutil
                shutil.rmtree(result_dir, ignore_errors=True)
            return Response(status=status.HTTP_204_NO_CONTENT)
        # Set is_delete to true.
        instance.is_delete = True
        instance.save(update_fields=['is_delete'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def get_png(self, request, pk=None):
        'Download the PNG for a specified date.'
        # Retrieve the instance.
        instance = self.get_object()

        # Read the date query parameter.
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'Provide the date query parameter in YYYY-MM-DD format.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate the date format.
        try:
            date_obj = parse_date(date_str)
            if not date_obj:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if date_obj < instance.start_day or date_obj > instance.end_day:
            return Response({'error': f'Date must be within {instance.start_day} and {instance.end_day}.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Build the file path.
        png_filename = f"{date_str}.png"
        result_dir = _result_absolute_dir(instance.result_dir)
        png_path = result_dir / 'soil_moisture_png' / png_filename

        # Check whether the file exists.
        if not os.path.exists(png_path):
            return Response({'error': f'No PNG product was found for {date_str}.'},
                            status=status.HTTP_404_NOT_FOUND)
        tif_path = result_dir / 'soil_moisture_result' / f"{date_str}.tif"
        if not tif_path.exists():
            return Response({'error': f'No GeoTIFF product was found for {date_str}.'},
                            status=status.HTTP_404_NOT_FOUND)
        min_moisture, max_moisture ,avg_moisture = get_min_max_arv_moisture(tif_path)
        bounds = _raster_bounds_payload(tif_path)
        # Return the file.
        try:
            # Convert the absolute path to a relative URL.
            relative_path = os.path.relpath(png_path, MEDIA_ROOT)
            png_url = os.path.join('/media/', relative_path).replace('\\', '/')
            return Response({
                'png_url': png_url,
                'bounds': bounds,
                'min_moisture': min_moisture,
                'max_moisture': max_moisture,
                'avg_moisture': avg_moisture,
            })
        except Exception as e:
            return Response({'error': f'Could not generate the product URL: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def get_tif(self, request, pk=None):
        'Download the TIFF for a specified date.'
        # Retrieve the instance.
        instance = self.get_object()

        # Read the date query parameter.
        date_str = request.query_params.get('date')
        if not date_str:
            return Response({'error': 'Provide the date query parameter in YYYY-MM-DD format.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate the date format.
        try:
            date_obj = parse_date(date_str)
            if not date_obj:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if date_obj < instance.start_day or date_obj > instance.end_day:
            return Response({'error': f'Date must be within {instance.start_day} and {instance.end_day}.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Build the file path.
        tif_filename = f"{date_str}.tif"
        tif_path = _result_absolute_dir(instance.result_dir) / 'soil_moisture_result' / tif_filename

        # Check whether the file exists.
        if not os.path.exists(tif_path):
            return Response({'error': f'No GeoTIFF product was found for {date_str}.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Return the file.
        try:
            with open(tif_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='image/tif')
                response['Content-Disposition'] = f'attachment; filename="{tif_filename}"'
                return response
        except Exception as e:
            return Response({'error': f'Could not read the GeoTIFF file: {str(e)}'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='list')
    def list_files(self, request, pk=None):
        'List files in the result set.'
        instance = self.get_object()
        base_dir = _result_absolute_dir(instance.result_dir)
        png_dir = base_dir / 'soil_moisture_png'
        # List filenames without extensions.
        file_list = []
        if not png_dir.is_dir():
            return Response(
                {'error': f'Result directory is missing: {png_dir}'},
                status=status.HTTP_404_NOT_FOUND,
            )
        for f in sorted(os.listdir(png_dir)):
            file_path = os.path.join(png_dir, f)
            if os.path.isfile(file_path):
                try:
                    file_date = parse_date(os.path.splitext(f)[0])
                except (TypeError, ValueError):
                    file_date = None
                if file_date and not (instance.start_day <= file_date <= instance.end_day):
                    continue
                # Separate the filename from its extension.
                file_name_without_ext = os.path.splitext(f)[0]
                file_list.append(file_name_without_ext)

        return Response({
            'files': file_list
        }, status=status.HTTP_200_OK)
