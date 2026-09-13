from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from polygons.models import Polygon
from result_img.models import ResultImg
from service.test_workspace import reset_test_workspace


class WorkspaceResetTests(SimpleTestCase):
    def test_removes_cropped_results_and_cycles_but_preserves_inputs(self):
        with TemporaryDirectory() as temp:
            media = Path(temp)
            base = media / 'images/82/2018-05-01_2018-05-24'
            keep = ['process/shared_ml_model_rf.pkl', 'nasa_power/cell.json']
            stale = ['process/cycles/old/AMPm.tif', 'soil_moisture_result/2018-05-01.tif',
                     'soil_moisture_png/2018-05-01.png', 'org_smap/old.tif', '.fusion.complete']
            for name in keep + stale:
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            with patch('service.test_workspace.MEDIA_ROOT', media):
                reset_test_workspace(base)
                reset_test_workspace(base)
                with self.assertRaises(ValueError):
                    reset_test_workspace(media / 'images/83')
            for name in keep:
                self.assertEqual((base / name).read_bytes(), b'fixture')
            for name in stale:
                self.assertFalse((base / name).exists())


class TestSubmissionTests(TestCase):
    def test_completed_test_submission_starts_a_new_worker(self):
        polygon = Polygon.objects.create(id=82, name='test', wgs84_coordinates=[], gcj02_coordinates=[])
        result = ResultImg.objects.create(polygon=polygon, start_day=date(2018, 5, 1),
            end_day=date(2018, 5, 24), result_dir='images/82/2018-05-01_2018-05-24',
            generation_mode='offline', status='completed', process=100)
        with patch('result_img.views.ResultImgViewSet._apply_test_preset'), patch('result_img.views.threading.Thread') as thread:
            response = APIClient().post('/api/result_img/', {'polygon':82,
                'generation_mode':'offline', 'start_day':'2018-05-01', 'end_day':'2018-05-24'}, format='json')
        self.assertEqual(response.status_code, 201)
        result.refresh_from_db()
        self.assertEqual((result.status, result.process), ('Waiting', 0))
        thread.return_value.start.assert_called_once()
