import json
import tempfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import RequestFactory, SimpleTestCase

from .moistureListByLngLat import get_values_by_date_from_folder_threaded
from .weatherView import (
    NASA_POWER_VARIABLES,
    _get_cached_nasa_data,
    _process_POWER_records,
    download_nasa_data,
    getnasadata,
    weather_data,
)


class NasaPowerRequestTests(SimpleTestCase):
    @patch('service.weather.weatherView.requests.get')
    def test_request_uses_current_power_parameters_and_timeout(self, get):
        response = Mock()
        response.json.return_value = {'header': {'fill_value': -999}}
        get.return_value = response

        result = getnasadata(
            34.2,
            108.9,
            date(2026, 6, 1),
            date(2026, 6, 7),
        )

        self.assertEqual(result, {'header': {'fill_value': -999}})
        params = get.call_args.kwargs['params']
        self.assertNotIn('user', params)
        self.assertNotIn('request', params)
        self.assertEqual(get.call_args.kwargs['timeout'], 20)
        response.raise_for_status.assert_called_once()

    def test_invalid_power_response_exposes_nasa_message(self):
        with self.assertRaisesRegex(ValueError, 'Invalid request parameters'):
            _process_POWER_records({
                'messages': ['Invalid request parameters'],
            })

    def test_nasa_response_is_cached_and_reused(self):
        payload = {
            'header': {'fill_value': -999},
            'properties': {'parameter': {
                variable: {'20260601': 20} for variable in NASA_POWER_VARIABLES
            }},
        }
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            with patch('service.weather.weatherView.getnasadata', return_value=payload) as get_nasa_data:
                first, first_cached = _get_cached_nasa_data(34.2, 108.9, date(2026, 6, 1), date(2026, 6, 1))
                second, second_cached = _get_cached_nasa_data(34.2, 108.9, date(2026, 6, 1), date(2026, 6, 1))

        self.assertFalse(first_cached)
        self.assertTrue(second_cached)
        self.assertEqual(first, second)
        get_nasa_data.assert_called_once()

    def test_download_endpoint_returns_csv(self):
        payload = {
            'header': {'fill_value': -999},
            'properties': {'parameter': {'T2M': {'20260601': 20}}},
        }
        request = RequestFactory().get('/api/weather_data/download/', {
            'latitude': 34.2,
            'longitude': 108.9,
            'start_date': '2026-06-01',
            'end_date': '2026-06-01',
        })
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            with patch('service.weather.weatherView.getnasadata', return_value=payload):
                response = download_nasa_data(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('TOA_SW_DWN', response.content.decode('utf-8'))


class MoistureFileReaderTests(SimpleTestCase):
    def test_empty_folder_returns_empty_values(self):
        values = get_values_by_date_from_folder_threaded(
            'folder-that-does-not-exist',
            108.9,
            34.2,
        )

        self.assertEqual(values, [])


class WeatherDataErrorTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/api/weather_data/', {
            'latitude': 34.2,
            'longitude': 108.9,
            'start_date': '2018-05-01',
            'end_date': '2018-05-24',
            'result_set_id': '83',
        })

    @patch(
        'service.weather.weatherView.get_values_by_date_from_folder_threaded',
        return_value=[],
    )
    @patch('service.weather.weatherView.ResultImg.objects.get')
    @patch(
        'service.weather.weatherView._get_cached_nasa_data',
        side_effect=requests.Timeout('timed out'),
    )
    def test_timeout_returns_504(self, get_nasa_data, get_result, get_moisture):
        get_result.return_value = SimpleNamespace(result_dir='unused')

        response = weather_data(self.request)

        self.assertEqual(response.status_code, 504)
        body = json.loads(response.content)
        self.assertFalse(body['success'])
        self.assertIn('timed out', body['message'])

    @patch(
        'service.weather.weatherView.get_values_by_date_from_folder_threaded',
        return_value=[],
    )
    @patch('service.weather.weatherView.ResultImg.objects.get')
    @patch(
        'service.weather.weatherView._get_cached_nasa_data',
        side_effect=requests.ConnectionError('connection failed'),
    )
    def test_connection_error_returns_502(
        self,
        get_nasa_data,
        get_result,
        get_moisture,
    ):
        get_result.return_value = SimpleNamespace(result_dir='unused')

        response = weather_data(self.request)

        self.assertEqual(response.status_code, 502)
        body = json.loads(response.content)
        self.assertFalse(body['success'])
        self.assertIn('retrieval failed', body['message'])
