from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import rasterio
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from PIL import Image
from rasterio.transform import from_origin
from shapely.geometry import Polygon
from polygons.models import Polygon as PolygonModel
from result_img.models import ResultImg

from result_img.management.commands.import_local_result import (
    _color_lut,
    _write_aligned_outputs,
)
from result_img.views import _raster_bounds_payload


class AlignedRasterOutputTests(SimpleTestCase):
    def test_tif_png_and_alpha_mask_share_the_same_grid(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            tif_path = folder / '2018-05-01.tif'
            png_path = folder / '2018-05-01.png'
            self._write_tif(tif_path)
            boundary = Polygon([
                (1, 1),
                (5, 1),
                (1, 5),
                (1, 1),
            ])

            _write_aligned_outputs(
                tif_path,
                png_path,
                boundary,
                0.0,
                40.0,
                _color_lut(),
                crop_tif=True,
            )

            with rasterio.open(tif_path) as dataset:
                tif_mask = np.ma.getmaskarray(dataset.read(1, masked=True))
                tif_size = (dataset.width, dataset.height)
                bounds = dataset.bounds
            with Image.open(png_path) as image:
                rgba = np.asarray(image)
                png_size = image.size

            self.assertEqual(tif_size, png_size)
            np.testing.assert_array_equal(tif_mask, rgba[:, :, 3] == 0)
            self.assertEqual(tuple(bounds), (1.0, 1.0, 5.0, 5.0))

    def test_bounds_payload_uses_the_raster_georeference(self):
        with TemporaryDirectory() as temp_dir:
            tif_path = Path(temp_dir) / 'result.tif'
            self._write_tif(tif_path)

            bounds = _raster_bounds_payload(tif_path)

        self.assertEqual(bounds['wgs84']['southwest'], [0.0, 0.0])
        self.assertEqual(bounds['wgs84']['northeast'], [6.0, 6.0])
        self.assertLess(
            bounds['gcj02']['southwest'][0],
            bounds['gcj02']['northeast'][0],
        )

    @staticmethod
    def _write_tif(path):
        data = np.arange(36, dtype=np.float32).reshape(6, 6)
        data[0, 0] = -9999.0
        with rasterio.open(
            path,
            'w',
            driver='GTiff',
            height=6,
            width=6,
            count=1,
            dtype='float32',
            crs='EPSG:4326',
            transform=from_origin(0, 6, 1, 1),
            nodata=-9999.0,
        ) as dataset:
            dataset.write(data, 1)


class ResultProgressApiTests(TestCase):
    def setUp(self):
        self.polygon = PolygonModel.objects.create(
            name='progress-field',
            wgs84_coordinates=[[107.0, 40.8], [107.1, 40.8], [107.05, 40.9]],
            gcj02_coordinates=[[107.0, 40.8], [107.1, 40.8], [107.05, 40.9]],
        )

    def test_running_duplicate_returns_conflict_and_progress(self):
        result = ResultImg.objects.create(
            polygon=self.polygon,
            start_day='2018-05-01',
            end_day='2018-05-24',
            result_dir='images/progress-field',
            status='preprocessing',
            process=20,
        )
        client = APIClient()
        duplicate = client.post('/api/result_img/', {
            'polygon': self.polygon.id,
            'start_day': '2018-05-01',
            'end_day': '2018-05-24',
        }, format='json')
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()['id'], result.id)

        progress = client.get(f'/api/result_img/{result.id}/progress/')
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.json()['process'], 20)
        self.assertEqual(progress.json()['status'], 'preprocessing')
