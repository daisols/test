# views.py
import json
import datetime as dt
import os.path
import csv
import hashlib
import math
import threading
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import pandas as pd
import numpy as np
import requests
import rasterio
from math import exp

from django.conf import settings
from config.settings import MEDIA_ROOT
from polygons.tools import gcj02_to_wgs84

NASA_POWER_VARIABLES = [
    "TOA_SW_DWN", "ALLSKY_SFC_SW_DWN", "T2M", "T2M_MIN",
    "T2M_MAX", "T2MDEW", "WS2M", "RH2M", "PRECTOTCORR",
]
NASA_POWER_GRID_STEP = 0.5
_region_download_threads = {}

# Retain the original utility functions.
MJ_to_KJ = lambda x: x * 1e3
mm_to_cm = lambda x: x / 10.
tdew_to_kpa = lambda x: ea_from_tdew(x) / 10 * 10.
to_date = lambda d: d.date()


def getnasadata(latitude, longitude, start_date, end_date):
    power_variables = NASA_POWER_VARIABLES
    payload = {
        "parameters": ",".join(power_variables),
        "latitude": latitude,
        "longitude": longitude,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "community": "AG",
        "format": "JSON",
    }

    req = requests.get(
        settings.NASA_POWER_API_URL,
        params=payload,
        headers={'User-Agent': settings.NASA_POWER_USER_AGENT},
        timeout=settings.NASA_POWER_TIMEOUT_SECONDS,
    )
    req.raise_for_status()
    return req.json()


def _nasa_cache_path(latitude, longitude, start_date, end_date, cache_dir=None):
    """Return a stable cache filename for a NASA POWER point request."""
    # NASA POWER is delivered on a coarse grid. Quantizing keys means all
    # 100 m pixels that share a POWER cell reuse one downloaded response.
    latitude = round(float(latitude) / NASA_POWER_GRID_STEP) * NASA_POWER_GRID_STEP
    longitude = round(float(longitude) / NASA_POWER_GRID_STEP) * NASA_POWER_GRID_STEP
    identity = (
        f'{float(latitude):.6f},{float(longitude):.6f}:'
        f'{start_date:%Y%m%d}:{end_date:%Y%m%d}'
    )
    cache_key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    cache_root = Path(cache_dir) if cache_dir else Path(settings.MEDIA_ROOT) / 'nasa_power'
    return cache_root / f'{cache_key}.json'


def _cached_nasa_data_is_valid(cache_path):
    try:
        with cache_path.open('r', encoding='utf-8') as cache_file:
            cached = json.load(cache_file)
        parameters = cached.get('properties', {}).get('parameter') if isinstance(cached, dict) else None
        return (
            isinstance(cached, dict)
            and isinstance(cached.get('header'), dict)
            and isinstance(parameters, dict)
            and set(NASA_POWER_VARIABLES).issubset(parameters)
        )
    except (OSError, ValueError, TypeError):
        return False


def _get_cached_nasa_data(latitude, longitude, start_date, end_date, cache_dir=None):
    cache_path = _nasa_cache_path(latitude, longitude, start_date, end_date, cache_dir)
    candidates = [cache_path]
    legacy_path = _nasa_cache_path(latitude, longitude, start_date, end_date)
    if legacy_path != cache_path:
        candidates.append(legacy_path)
    for candidate in candidates:
        if not _cached_nasa_data_is_valid(candidate):
            continue
        try:
            with candidate.open('r', encoding='utf-8') as cache_file:
                cached = json.load(cache_file)
            if candidate != cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with cache_path.open('w', encoding='utf-8') as cache_file:
                    json.dump(cached, cache_file, ensure_ascii=True)
            return cached, True
        except (OSError, ValueError, TypeError):
            continue

    powerdata = getnasadata(latitude, longitude, start_date, end_date)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix('.tmp')
        with temporary_path.open('w', encoding='utf-8') as cache_file:
            json.dump(powerdata, cache_file, ensure_ascii=True)
        temporary_path.replace(cache_path)
    except OSError:
        # A read-only media directory must not prevent an analysis response.
        pass
    return powerdata, False


def _parse_weather_request(request):
    try:
        latitude = float(request.GET.get('latitude'))
        longitude = float(request.GET.get('longitude'))
        start_date = dt.datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
        end_date = dt.datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError('Latitude, longitude, start_date, and end_date are required and must be valid.')
    if start_date > end_date:
        raise ValueError('start_date must be earlier than or equal to end_date.')
    if request.GET.get('coordinate_system', 'wgs84').lower() == 'gcj02':
        longitude, latitude = gcj02_to_wgs84(longitude, latitude)
    return latitude, longitude, start_date, end_date


def _nasa_csv_response(powerdata, latitude, longitude, start_date, end_date):
    from django.http import HttpResponse

    parameters = powerdata.get('properties', {}).get('parameter', {})
    dates = sorted({
        date_key
        for values in parameters.values()
        if isinstance(values, dict)
        for date_key in values
    })
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="nasa_power_{start_date}_{end_date}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(['latitude_wgs84', 'longitude_wgs84'])
    writer.writerow([f'{latitude:.6f}', f'{longitude:.6f}'])
    writer.writerow([])
    writer.writerow(['date', *NASA_POWER_VARIABLES])
    for date_key in dates:
        writer.writerow([date_key, *[
            parameters.get(variable, {}).get(date_key, '')
            for variable in NASA_POWER_VARIABLES
        ]])
    return response


def _region_nasa_context(result_set_id, start_date=None, end_date=None):
    result_img = ResultImg.objects.get(id=result_set_id)
    start_date = start_date or result_img.start_day
    end_date = end_date or result_img.end_day
    result_dir = Path(result_img.result_dir)
    if not result_dir.is_absolute():
        result_dir = Path(MEDIA_ROOT) / result_dir
    tif_dir = result_dir / 'soil_moisture_result'
    tif_files = sorted(tif_dir.glob('*.tif')) + sorted(tif_dir.glob('*.tiff'))
    if not tif_files:
        raise ValueError('No GeoTIFF products were found for this result set.')
    with rasterio.open(tif_files[0]) as dataset:
        bounds = dataset.bounds
    step = NASA_POWER_GRID_STEP
    lon_start = math.floor(bounds.left / step) * step
    lon_end = math.ceil(bounds.right / step) * step
    lat_start = math.floor(bounds.bottom / step) * step
    lat_end = math.ceil(bounds.top / step) * step
    points = []
    longitude = lon_start
    while longitude <= lon_end + 1e-9:
        latitude = lat_start
        while latitude <= lat_end + 1e-9:
            points.append((round(latitude, 6), round(longitude, 6)))
            latitude += step
        longitude += step
    manifest_key = hashlib.sha256(
        f'{result_set_id}:{start_date:%Y%m%d}:{end_date:%Y%m%d}'.encode('utf-8')
    ).hexdigest()
    cache_dir = result_dir / 'nasa_power'
    manifest_path = cache_dir / 'regions' / f'{manifest_key}.json'
    return result_img, start_date, end_date, points, cache_dir, manifest_path


def _read_region_manifest(manifest_path):
    try:
        with manifest_path.open('r', encoding='utf-8') as manifest_file:
            value = json.load(manifest_file)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _write_region_manifest(manifest_path, value):
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = manifest_path.with_suffix('.tmp')
        with temporary_path.open('w', encoding='utf-8') as manifest_file:
            json.dump(value, manifest_file, ensure_ascii=True)
        temporary_path.replace(manifest_path)
    except OSError:
        pass


def _region_nasa_status(result_set_id, start_date=None, end_date=None):
    _, start_date, end_date, points, cache_dir, manifest_path = _region_nasa_context(
        result_set_id, start_date, end_date
    )
    total = len(points)
    downloaded = sum(
        _cached_nasa_data_is_valid(_nasa_cache_path(latitude, longitude, start_date, end_date, cache_dir))
        or _cached_nasa_data_is_valid(_nasa_cache_path(latitude, longitude, start_date, end_date))
        for latitude, longitude in points
    )
    manifest = _read_region_manifest(manifest_path)
    if downloaded == total and total:
        status = 'completed'
    elif (
        manifest.get('status') == 'downloading'
        and _region_download_threads.get(str(manifest_path))
        and _region_download_threads[str(manifest_path)].is_alive()
    ):
        status = 'downloading'
    elif manifest.get('status') == 'failed':
        status = 'failed'
    else:
        status = 'pending'
    return {
        'status': status,
        'downloaded': downloaded,
        'total': total,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    }, points, cache_dir, manifest_path


def _download_region_worker(points, start_date, end_date, cache_dir, manifest_path):
    downloaded = 0
    try:
        for latitude, longitude in points:
            cache_path = _nasa_cache_path(latitude, longitude, start_date, end_date, cache_dir)
            if not _cached_nasa_data_is_valid(cache_path):
                _get_cached_nasa_data(latitude, longitude, start_date, end_date, cache_dir)
            downloaded += 1
            _write_region_manifest(manifest_path, {
                'status': 'downloading',
                'downloaded': downloaded,
                'total': len(points),
            })
        _write_region_manifest(manifest_path, {
            'status': 'completed',
            'downloaded': len(points),
            'total': len(points),
        })
    except Exception as exc:
        _write_region_manifest(manifest_path, {
            'status': 'failed',
            'downloaded': downloaded,
            'total': len(points),
            'error': str(exc),
        })
    finally:
        _region_download_threads.pop(str(manifest_path), None)


def _process_POWER_records(powerdata):
    if not isinstance(powerdata, dict) or not isinstance(powerdata.get("header"), dict):
        messages = powerdata.get("messages") if isinstance(powerdata, dict) else None
        messages = messages or ["NASA POWER returned an invalid response"]
        raise ValueError("; ".join(str(message) for message in messages))

    fill_value = float(powerdata["header"]["fill_value"])
    power_variables = ["TOA_SW_DWN", "ALLSKY_SFC_SW_DWN", "T2M", "T2M_MIN",
                       "T2M_MAX", "T2MDEW", "WS2M", "RH2M", "PRECTOTCORR"]
    df_power = {}
    for varname in power_variables:
        s = pd.Series(powerdata["properties"]["parameter"][varname])
        s[s == fill_value] = np.nan
        df_power[varname] = s
    df_power = pd.DataFrame(df_power)
    df_power["DAY"] = pd.to_datetime(df_power.index, format="%Y%m%d")

    ix = df_power.isnull().any(axis=1)
    df_power = df_power[~ix]

    return df_power


def _estimate_AngstAB(df_power):
    angstA = 0.29
    angstB = 0.49
    if len(df_power) < 200:
        return angstA, angstB

    relative_radiation = df_power.ALLSKY_SFC_SW_DWN / df_power.TOA_SW_DWN
    ix = relative_radiation.notnull()
    angstrom_a = float(np.percentile(relative_radiation[ix].values, 5))
    angstrom_ab = float(np.percentile(relative_radiation[ix].values, 98))
    angstrom_b = angstrom_ab - angstrom_a

    MIN_A = 0.1
    MAX_A = 0.4
    MIN_B = 0.3
    MAX_B = 0.7
    MIN_SUM_AB = 0.6
    MAX_SUM_AB = 0.9
    A = abs(angstrom_a)
    B = abs(angstrom_b)
    SUM_AB = A + B

    if A < MIN_A or A > MAX_A or B < MIN_B or B > MAX_B or SUM_AB < MIN_SUM_AB or SUM_AB > MAX_SUM_AB:
        return angstA, angstB

    return angstrom_a, angstrom_b


def _POWER_to_PCSE(df_power):
    df_pcse = pd.DataFrame({
        "DAY": df_power.DAY.apply(to_date),
        "IRRAD": df_power.ALLSKY_SFC_SW_DWN.apply(MJ_to_KJ),
        "TMIN": df_power.T2M_MIN,
        "TMAX": df_power.T2M_MAX,
        "TDEW": df_power.T2MDEW,
        "VAP": df_power.T2MDEW.apply(tdew_to_kpa),
        "WIND": df_power.WS2M,
        "RH": df_power.RH2M,
        "RAIN": df_power.PRECTOTCORR
    })

    return df_pcse


def ea_from_tdew(tdew):
    if (tdew < -95.0 or tdew > 65.0):
        msg = 'tdew=%g is not in range -95 to +60 deg C' % tdew
        raise ValueError(msg)

    tmp = (17.27 * tdew) / (tdew + 237.3)
    ea = 0.6108 * exp(tmp)
    return ea


from result_img.models import ResultImg
from .moistureListByLngLat import get_values_by_date_from_folder_threaded
@csrf_exempt
@require_http_methods(["GET"])
def weather_data(request):
    'Weather endpoint accepting latitude, longitude, start_date and end_date (YYYY-MM-DD); return data formatted for ECharts.'
    try:
        # Read request parameters.
        result_img_id = request.GET.get('result_set_id')
        # Validate parameters.
        if not result_img_id:
            return JsonResponse({
                'success': False,
                'message': 'Missing one or more required parameters.'
            }, status=400)
        try:
            latitude, longitude, start_date, end_date = _parse_weather_request(request)
        except ValueError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        # Soil moisture data.
        result_img = ResultImg.objects.get(id=result_img_id)
        if not result_img:
            return JsonResponse({
                'success': False,
                'message': 'Unknown result set.'
            }, status=400)
        result_dir = result_img.result_dir
        if not os.path.isabs(result_dir):
            result_dir = os.path.join(MEDIA_ROOT, result_dir)
        tif_dir = os.path.join(result_dir, 'soil_moisture_result')
        moisture = get_values_by_date_from_folder_threaded(tif_dir, longitude, latitude)
        moisture = [0 if (i is None or np.isnan(i) or i<0.000001) else i for i in moisture]
        max_moisture = max(moisture, default=0)
        min_moisture = min(moisture, default=0)
        avg_moisture = sum(moisture) / len(moisture) if moisture else 0

        # Retrieve NASA data.
        try:
            powerdata, nasa_cached = _get_cached_nasa_data(
                latitude, longitude, start_date, end_date, Path(result_dir) / 'nasa_power'
            )
        except requests.Timeout:
            return JsonResponse({
                'success': False,
                'message': 'The NASA POWER request timed out. Try again later.'
            }, status=504)
        except requests.RequestException as e:
            return JsonResponse({
                'success': False,
                'message': f'NASA POWER data retrieval failed: {str(e)}'
            }, status=502)
        if not powerdata:
            return JsonResponse({
                'success': False,
                'message': 'NASA POWER returned no data. Try again later.'
            }, status=500)

        # Process the data.
        try:
            df_power = _process_POWER_records(powerdata)
        except (KeyError, TypeError, ValueError) as e:
            return JsonResponse({
                'success': False,
                'message': f'NASA POWER returned invalid data: {str(e)}'
            }, status=502)
        angstA, angstB = _estimate_AngstAB(df_power)
        df_pcse = _POWER_to_PCSE(df_power)

        # Handle missing values.
        std_datatime = pd.DataFrame(
            pd.date_range(start=start_date, end=end_date, freq='D'),
            columns=['DAY']
        )
        data = df_pcse.dropna()
        data['DAY'] = pd.to_datetime(data['DAY'])
        result = pd.merge(std_datatime, data, how='left', on='DAY')

        # Fill missing values.
        nan_indexset = set(np.where(np.isnan(result.iloc[:, 1:]))[0])
        for i in nan_indexset:
            window = result.iloc[i - 5:i + 6] if i >= 5 else result.iloc[0:i + 6]
            for column in ['IRRAD', 'TMIN', 'TMAX', 'TDEW', 'VAP', 'WIND', 'RH', 'RAIN']:
                result.loc[i, column] = window[column].mean()

        # Convert to the ECharts response format.
        # Dates.
        dates = [d.strftime('%Y-%m-%d') for d in result['DAY']]

        # Weather variable series.
        data_echarts = {
            'success': True,
            'site_info': {
                'latitude': latitude,
                'longitude': longitude,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'angstrom_a': angstA,
                'angstrom_b': angstB,
                'missing_days': len(nan_indexset),
                'nasa_cached': nasa_cached,
            },
            'dates': dates,
            'series': {
                'temperature': {
                    'tmin': result['TMIN'].tolist(),
                    'tmax': result['TMAX'].tolist()
                },
                'radiation': result['IRRAD'].tolist(),
                'vapor': result['VAP'].tolist(),
                'dew_point': result['TDEW'].tolist(),
                'wind': result['WIND'].tolist(),
                'humidity': result['RH'].tolist(),
                'rain': result['RAIN'].tolist(),
                'moisture': moisture,
                'max_moisture': max_moisture,
                'min_moisture': min_moisture,
                'avg_moisture': avg_moisture
            }
        }

        return JsonResponse(data_echarts)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Could not process the requested data: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def download_nasa_data(request):
    """Download the raw NASA POWER records used by point analysis as CSV."""
    try:
        latitude, longitude, start_date, end_date = _parse_weather_request(request)
        cache_dir = None
        result_set_id = request.GET.get('result_set_id')
        if result_set_id:
            _, _, _, _, cache_dir, _ = _region_nasa_context(result_set_id)
        powerdata, _ = _get_cached_nasa_data(latitude, longitude, start_date, end_date, cache_dir)
        if not isinstance(powerdata, dict) or not powerdata.get('properties', {}).get('parameter'):
            raise ValueError('NASA POWER returned no downloadable data.')
        return _nasa_csv_response(powerdata, latitude, longitude, start_date, end_date)
    except requests.Timeout:
        return JsonResponse({'success': False, 'message': 'The NASA POWER request timed out. Try again later.'}, status=504)
    except requests.RequestException as exc:
        return JsonResponse({'success': False, 'message': f'NASA POWER data retrieval failed: {exc}'}, status=502)
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["GET"])
def nasa_region_status(request):
    """Report whether NASA POWER data covers the result set's POWER cells."""
    result_set_id = request.GET.get('result_set_id')
    if not result_set_id:
        return JsonResponse({'success': False, 'message': 'result_set_id is required.'}, status=400)
    try:
        status_payload, _, _, _ = _region_nasa_status(result_set_id)
        return JsonResponse({'success': True, **status_payload})
    except ResultImg.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Unknown result set.'}, status=404)
    except (OSError, ValueError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def download_nasa_region(request):
    """Start background pre-download of NASA POWER data for the whole result area."""
    result_set_id = request.GET.get('result_set_id') or request.POST.get('result_set_id')
    if not result_set_id:
        return JsonResponse({'success': False, 'message': 'result_set_id is required.'}, status=400)
    try:
        status_payload, points, cache_dir, manifest_path = _region_nasa_status(result_set_id)
        if status_payload['status'] == 'completed':
            return JsonResponse({'success': True, **status_payload})
        if status_payload['status'] == 'downloading':
            return JsonResponse({'success': True, **status_payload}, status=202)
        _, start_date, end_date, _, cache_dir, _ = _region_nasa_context(result_set_id)
        _write_region_manifest(manifest_path, {
            'status': 'downloading',
            'downloaded': status_payload['downloaded'],
            'total': status_payload['total'],
        })
        thread = threading.Thread(
            target=_download_region_worker,
            args=(points, start_date, end_date, cache_dir, manifest_path),
            daemon=True,
        )
        _region_download_threads[str(manifest_path)] = thread
        thread.start()
        return JsonResponse({'success': True, **status_payload, 'status': 'downloading'}, status=202)
    except ResultImg.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Unknown result set.'}, status=404)
    except (OSError, ValueError) as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
