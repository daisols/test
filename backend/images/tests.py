from datetime import date

from django.test import TestCase

from images.models import ImageDownloadTask
from polygons.models import Polygon


class ImageDownloadTaskModelTests(TestCase):
    def test_task_uses_the_current_date_range_contract(self):
        polygon = Polygon.objects.create(
            name='test-area',
            gcj02_coordinates=[[116.3, 39.9], [116.4, 39.9], [116.4, 40.0]],
            wgs84_coordinates=[[116.29, 39.89], [116.39, 39.89], [116.39, 39.99]],
        )

        task = ImageDownloadTask.objects.create(
            name='Test download',
            polygon=polygon,
            start_day=date(2023, 1, 1),
            end_day=date(2023, 1, 31),
        )

        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.progress, 0)
        self.assertEqual(task.polygon, polygon)
