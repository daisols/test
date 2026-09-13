import os
import threading

import numpy as np
import rasterio
from PIL import Image
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from config import settings
from .models import ImageDownloadTask, SatelliteImage
from .serializers import (
    ImageDownloadTaskSerializer,
    ImageDownloadTaskCreateSerializer,
    ImageDownloadTaskUpdateSerializer,
    SatelliteImageSerializer,
    SatelliteImageListSerializer
)
from .tools import process_satellite_imagery_with_mosaic


class ImageDownloadTaskViewSet(viewsets.ModelViewSet):
    queryset = ImageDownloadTask.objects.all()
    serializer_class = ImageDownloadTaskSerializer

    def get_serializer_class(self):
        'Select the serializer for the current action.'
        if self.action == 'create':
            return ImageDownloadTaskCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ImageDownloadTaskUpdateSerializer
        return ImageDownloadTaskSerializer

    def get_queryset(self):
        'Filter tasks using query parameters.'
        queryset = ImageDownloadTask.objects.all()
        request: Request = self.request
        status = request.query_params.get('status', None)
        polygon_id = request.query_params.get('polygon_id', None)

        if status:
            queryset = queryset.filter(status=status)
        if polygon_id:
            queryset = queryset.filter(polygon_id=polygon_id)

        return queryset

    def create(self, request, *args, **kwargs):
        'Create a download task.'
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute_task(self, request, pk=None):
        'Download imagery from GEE to the server.'
        task = self.get_object()

        # Check whether the task can run.
        if task.status not in ['pending', 'failed']:
            return Response({
                'status': 'error',
                'message': f'Task status is {task.status}; it cannot be executed.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Download asynchronously and save imagery on the server.
        thread = threading.Thread(
            target=process_satellite_imagery_with_mosaic,
            args=(task,)
        )
        thread.daemon = True
        thread.start()

        return Response({
            'status': 'success',
            'message': f'Task {task.name} started. Imagery will be downloaded to the server.'
        })

    @action(detail=True, methods=['get'], url_path='status')
    def task_status(self, request, pk=None):
        'Return task execution status.'
        task = self.get_object()
        return Response({
            'task_id': task.id,
            'name': task.name,
            'status': task.status,
            'progress': task.progress,
            'start_time': task.start_time,
            'end_time': task.end_time,
            'downloaded_images_count': task.downloaded_images_count,
            'error_message': task.error_message,
            'created_at': task.created_at,
            'updated_at': task.updated_at,
            'completed_at': task.completed_at
        })

    def destroy(self, request, *args, **kwargs):
        'Delete the download task without deleting downloaded image files.'
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SatelliteImageViewSet(viewsets.ModelViewSet):
    queryset = SatelliteImage.objects.all()
    serializer_class = SatelliteImageSerializer

    def get_serializer_class(self):
        'Select the serializer for the current action.'
        if self.action == 'list':
            return SatelliteImageListSerializer
        return SatelliteImageSerializer

    def get_queryset(self):
        'Filter imagery using query parameters.'
        queryset = SatelliteImage.objects.all()
        request: Request = self.request
        polygon_id = request.query_params.get('polygon_id', None)

        if polygon_id:
            queryset = queryset.filter(polygon_id=polygon_id)

        return queryset

    @action(detail=False, methods=['get'], url_path='by-polygon')
    def by_polygon(self, request):
        'Retrieve imagery by polygon ID.'
        polygon_id = request.query_params.get('polygon_id')
        if not polygon_id:
            return Response({
                'status': 'error',
                'message': 'Provide the polygon_id parameter.'
            }, status=status.HTTP_400_BAD_REQUEST)

        images = SatelliteImage.objects.filter(polygon_id=polygon_id)
        serializer = SatelliteImageListSerializer(images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        'Download an image file.'
        image = self.get_object()

        if not image.image:
            return Response({
                'status': 'error',
                'message': 'The image file does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Resolve the absolute file path.
        file_path = os.path.join(settings.MEDIA_ROOT, str(image.image))

        if not os.path.exists(file_path):
            return Response({
                'status': 'error',
                'message': 'The image file does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            # Return a file response that triggers a browser download.
            response = FileResponse(
                open(file_path, 'rb'),
                content_type='image/tiff'  # Adjust for the actual file type.
            )
            # Set the download filename.
            filename = os.path.basename(file_path)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'File download failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='statistics')
    def statistics(self, request):
        'Return image statistics.'
        total_images = SatelliteImage.objects.count()

        return Response({
            'total_images': total_images,
        })

    @action(detail=True, methods=['get'], url_path='png')
    def get_png(self, request, pk=None):
        'Return the URL of a polygon-clipped PNG converted from TIFF. Reuse an existing PNG; otherwise create and save it.'
        image = self.get_object()

        if not image.image:
            return Response({
                'status': 'error',
                'message': 'The image file does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Resolve the absolute TIFF path.
        tiff_file_path = os.path.join(settings.MEDIA_ROOT, str(image.image))

        if not os.path.exists(tiff_file_path):
            return Response({
                'status': 'error',
                'message': 'The image file does not exist.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Build the PNG path, with polygon clipping enabled by default.
        png_file_path = os.path.splitext(tiff_file_path)[0] + '_polygon.png'
        # Build the relative PNG URL path.
        png_relative_path = os.path.splitext(str(image.image).replace('\\', '/'))[0] + '_polygon.png'

        # Check whether the PNG already exists.
        if os.path.exists(png_file_path):
            # Return the URL of an existing PNG.
            png_url = f"/{settings.MEDIA_URL}{png_relative_path}"
            print('png_url = ', png_url)
            return Response({
                'status': 'success',
                'message': 'The PNG image already exists.',
                'png_url': png_url
            })
        # Create the PNG if it does not exist.
        try:
            print(f"处理TIFF文件: {tiff_file_path}")

            # Process the GeoTIFF with rasterio.
            with rasterio.open(tiff_file_path) as src:
                # Prepare the polygon geometry.
                polygon_geometry = None
                if hasattr(image, 'polygon') and image.polygon:
                    try:
                        # Expect gcj02_coordinates as [[lng, lat], [lng, lat], ...].
                        polygon_data = image.polygon.wgs84_coordinates

                        # Validate the structure and convert it to GeoJSON.
                        if isinstance(polygon_data, list) and len(polygon_data) > 0:
                            # Close the polygon by repeating the first point at the end.
                            if polygon_data[0] != polygon_data[-1]:
                                polygon_data.append(polygon_data[0])

                            # Convert to a GeoJSON Polygon.
                            polygon_geometry = {
                                "type": "Polygon",
                                "coordinates": [polygon_data]
                            }
                            print(f"多边形几何信息: {polygon_geometry}")
                    except Exception as e:
                        print(f"处理多边形几何信息出错: {e}")
                        polygon_geometry = None

                # Read the image data.
                if src.count == 1:
                    # Process a single-band image.
                    band = src.read(1)

                    # Normalize to the range 0-255.
                    band_min, band_max = band.min(), band.max()
                    if band_max > band_min:  # Avoid division by zero.
                        band_normalized = ((band - band_min) / (band_max - band_min) * 255).astype(np.uint8)
                    else:
                        band_normalized = np.zeros_like(band, dtype=np.uint8)

                    # Create an RGBA image with transparency.
                    rgba = np.zeros((band.shape[0], band.shape[1], 4), dtype=np.uint8)
                    rgba[:, :, 0] = band_normalized  # Red
                    rgba[:, :, 1] = band_normalized  # Green
                    rgba[:, :, 2] = band_normalized  # Blue

                    # Apply the polygon mask.
                    if polygon_geometry:
                        try:
                            from rasterio.features import geometry_mask
                            # The mask is False inside the polygon and True outside.
                            print(f"创建掩膜，使用变换矩阵: {src.transform}")
                            mask = geometry_mask(
                                [polygon_geometry],  # GeoJSON geometry.
                                transform=src.transform,
                                invert=False,  # True marks the area outside the polygon.
                                out_shape=band.shape
                            )
                            # Make pixels outside the polygon transparent.
                            rgba[:, :, 3] = np.where(mask, 0, 255)  # Transparent outside the polygon; opaque inside.
                            print("成功应用多边形掩膜到单波段图像")
                        except Exception as mask_error:
                            print(f"应用掩膜时出错: {mask_error}")
                            import traceback
                            traceback.print_exc()
                            rgba[:, :, 3] = (band_normalized > 0) * 255  # Default opacity.
                    else:
                        rgba[:, :, 3] = (band_normalized > 0) * 255  # Alpha channel (opacity).

                    image_data = rgba
                elif src.count >= 3:
                    # Process the first three bands of a multiband image.
                    # Read three bands and reorder their dimensions.
                    data = src.read([1, 2, 3])  # Read RGB bands.
                    data = np.transpose(data, (1, 2, 0))  # Reorder to (height, width, channels).

                    # Normalize to the range 0-255.
                    data_min, data_max = data.min(), data.max()
                    if data_max > data_min:  # Avoid division by zero.
                        data_normalized = ((data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
                    else:
                        data_normalized = np.zeros_like(data, dtype=np.uint8)

                    # Apply the polygon mask.
                    if polygon_geometry:
                        try:
                            from rasterio.features import geometry_mask
                            # Create the mask.
                            mask = geometry_mask(
                                [polygon_geometry],  # GeoJSON geometry.
                                transform=src.transform,
                                invert=False,  # True marks the area outside the polygon.
                                out_shape=(data_normalized.shape[0], data_normalized.shape[1])
                            )
                            # Add an alpha channel.
                            alpha_channel = np.where(mask, 0, 255).astype(np.uint8)  # Opaque inside the polygon.
                            image_data = np.dstack([data_normalized, alpha_channel])
                            print("成功应用多边形掩膜到多波段图像")
                        except Exception as mask_error:
                            print(f"应用掩膜时出错: {mask_error}")
                            import traceback
                            traceback.print_exc()
                            image_data = data_normalized
                    else:
                        image_data = data_normalized
                else:
                    # Otherwise process the first band.
                    band = src.read(1)
                    band_min, band_max = band.min(), band.max()
                    if band_max > band_min:
                        band_normalized = ((band - band_min) / (band_max - band_min) * 255).astype(np.uint8)
                    else:
                        band_normalized = np.zeros_like(band, dtype=np.uint8)
                    image_data = band_normalized

                # Save as PNG using PIL.
                if len(image_data.shape) == 3 and image_data.shape[2] == 4:
                    # RGBA image.
                    pil_image = Image.fromarray(image_data, 'RGBA')
                elif len(image_data.shape) == 3 and image_data.shape[2] == 3:
                    # RGB image.
                    pil_image = Image.fromarray(image_data, 'RGB')
                else:
                    # Grayscale image.
                    pil_image = Image.fromarray(image_data, 'L')

            # Ensure that the PNG directory exists.
            png_dir = os.path.dirname(png_file_path)
            if not os.path.exists(png_dir):
                os.makedirs(png_dir)

            # Save the PNG to disk.
            pil_image.save(png_file_path, format='PNG')
            print(f"PNG图像已保存到: {png_file_path}")

            # Return the PNG URL.
            png_url = f"/{settings.MEDIA_URL}{png_relative_path}"
            return Response({
                'status': 'success',
                'message': 'PNG image created successfully.',
                'png_url': png_url
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息: {error_details}")
            return Response({
                'status': 'error',
                'message': f'Image conversion failed: {str(e)}',
                'details': error_details
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



