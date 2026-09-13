from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import geopandas as gpd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from shapely.geometry import Polygon as ShapelyPolygon

from polygons.serializers import PolygonCreateSerializer


class PolygonCreateSerializerTests(TestCase):
    def test_accepts_wgs84_coordinates_and_derives_gcj02(self):
        coordinates = [[107.0, 40.8], [107.1, 40.8], [107.05, 40.9]]
        serializer = PolygonCreateSerializer(data={
            'name': 'test-field',
            'wgs84_coordinates': coordinates,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        polygon = serializer.save()
        self.assertEqual(polygon.wgs84_coordinates, coordinates)
        self.assertEqual(len(polygon.gcj02_coordinates), 3)

    def test_rejects_boundaries_with_fewer_than_three_vertices(self):
        serializer = PolygonCreateSerializer(data={
            'name': 'invalid-field',
            'wgs84_coordinates': [[107.0, 40.8], [107.1, 40.8]],
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('at least three vertices', str(serializer.errors))


class ShapefileUploadTests(TestCase):
    def test_zip_shapefile_creates_polygon_and_preserves_components(self):
        with TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / 'source'
            source_dir.mkdir()
            source_path = source_dir / 'boundary.shp'
            gpd.GeoDataFrame(
                {'field_id': [1]},
                geometry=[ShapelyPolygon([(107.0, 40.8), (107.1, 40.8), (107.1, 40.9), (107.0, 40.8)])],
                crs='EPSG:4326',
            ).to_file(source_path)

            archive_data = BytesIO()
            with ZipFile(archive_data, 'w') as archive:
                for component in source_dir.iterdir():
                    archive.write(component, arcname=f'boundary/{component.name}')

            media_root = Path(temp_dir) / 'media'
            with override_settings(MEDIA_ROOT=media_root):
                response = APIClient().post(
                    '/api/polygons/from-shp/',
                    {
                        'name': 'uploaded-field',
                        'files': SimpleUploadedFile(
                            'boundary.zip', archive_data.getvalue(), content_type='application/zip'
                        ),
                    },
                    format='multipart',
                )

            self.assertEqual(response.status_code, 201, response.content)
            payload = response.json()
            self.assertEqual(payload['name'], 'uploaded-field')
            self.assertEqual(payload['wgs84_shp_dir'], f"images/{payload['id']}/shp")
            self.assertTrue((media_root / payload['wgs84_shp_dir'] / 'boundary.shp').exists())

            archive_data.seek(0)
            duplicate = APIClient().post(
                '/api/polygons/from-shp/',
                {
                    'name': 'uploaded-field',
                    'files': SimpleUploadedFile(
                        'boundary.zip', archive_data.getvalue(), content_type='application/zip'
                    ),
                },
                format='multipart',
            )
            self.assertEqual(duplicate.status_code, 400)
            self.assertIn('name', duplicate.json())
