from service.processing_output import quiet_print as print
# file: tools.py
import ee
import logging
import os
import math
import concurrent.futures
from datetime import datetime, timedelta
from collections import defaultdict

from polygons.models import Polygon
from .models import ImageDownloadTask, SatelliteImage, ALLOWED_SATELLITES, COLLECTION_MAP, SATELLITE_BANDS
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.propagate = False


# Earth Engine initialization.
def initialize_earth_engine():
    'Initialize Earth Engine.'
    try:
        project = os.getenv('EARTH_ENGINE_PROJECT')
        if not project:
            raise RuntimeError('Set EARTH_ENGINE_PROJECT before starting a generation job.')

        # Prefer an explicitly configured service account when supplied. If no
        # credentials are configured, Earth Engine uses the local credentials
        # created by `earthengine authenticate`.
        service_account = os.getenv('EARTH_ENGINE_SERVICE_ACCOUNT')
        credentials_file = os.getenv('EARTH_ENGINE_CREDENTIALS_FILE') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if service_account or credentials_file:
            if not service_account or not credentials_file:
                raise RuntimeError(
                    'Set both EARTH_ENGINE_SERVICE_ACCOUNT and '
                    'EARTH_ENGINE_CREDENTIALS_FILE (or GOOGLE_APPLICATION_CREDENTIALS).'
                )
            credentials_path = os.path.expanduser(os.path.expandvars(credentials_file))
            if not os.path.isabs(credentials_path):
                credentials_path = os.path.join(settings.PROJECT_ROOT, credentials_path)
            credentials_path = os.path.abspath(credentials_path)
            if not os.path.isfile(credentials_path):
                raise RuntimeError(f'Earth Engine credentials file not found: {credentials_path}')
            credentials = ee.ServiceAccountCredentials(service_account, credentials_path)
            ee.Initialize(credentials=credentials, project=project)
        else:
            ee.Initialize(project=project)
        print("Earth Engine 初始化成功")
    except Exception as e:
        logger.error(f"Earth Engine 初始化失败: {str(e)}")
        raise


# Estimate image size.
def estimate_image_size(geometry, scale, satellite=None):
    'Estimate image size in bytes for a satellite, Earth Engine geometry, and resolution in meters.'
    # Select the band count for the satellite.
    if satellite and satellite in SATELLITE_BANDS:
        bands_count = len(SATELLITE_BANDS[satellite])
    else:
        bands_count = 3  # Default value.
    try:
        # Read the geometry bounding box.
        coords = geometry.bounds().coordinates().getInfo()[0]

        # Determine the bounding coordinate ranges.
        lons = [coord[0] for coord in coords]
        lats = [coord[1] for coord in coords]

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        # Compute width and height in degrees.
        width_deg = max_lon - min_lon
        height_deg = max_lat - min_lat

        # Approximate degree-to-meter conversion near the equator.
        # One longitude degree is about 111,320 m; one latitude degree is about 110,574 m.
        avg_lat = (min_lat + max_lat) / 2
        lon_to_meter = 111320 * math.cos(math.radians(avg_lat))
        lat_to_meter = 110574

        # Region width and height in meters.
        width_m = width_deg * lon_to_meter
        height_m = height_deg * lat_to_meter

        # Pixel area in square meters.
        pixel_area = scale * scale

        # Pixel count.
        pixel_count = (width_m * height_m) / pixel_area

        # Reserve three times the nominal eight bytes per PixelType sample.
        bytes_per_pixel_per_band = 9

        # Estimated total size in bytes.
        estimated_size = pixel_count * bands_count * bytes_per_pixel_per_band

        return int(estimated_size)
    except Exception as e:
        logger.warning(f"估算影像大小时出错: {str(e)}")
        # Fall back to 10 MB.
        return 10 * 1024 * 1024


# Compute a tiling plan.
def calculate_tiling_scheme(geometry, scale, satellite=None, max_size_mb=43):
    'Calculate the tile count for a satellite image at the given resolution and maximum size in MB.'
    try:
        # Estimate total size.
        estimated_size = estimate_image_size(geometry, scale, satellite)
        max_size_bytes = max_size_mb * 1024 * 1024

        # No tiling is required below the size limit.
        if estimated_size <= max_size_bytes:
            return 1

        # Compute the required number of tiles.
        tiles_needed = math.ceil(estimated_size / max_size_bytes)

        return tiles_needed
    except Exception as e:
        logger.warning(f"计算分块方案时出错: {str(e)}")
        return 64


# Split the geometry into tiles.
def split_geometry(geometry, tile_count):
    'Split an Earth Engine geometry into tile_count regions and return their geometries.'
    try:
        # Read the bounding box.
        bounds = geometry.bounds().coordinates().getInfo()[0]

        # Determine the bounding coordinate ranges.
        lons = [coord[0] for coord in bounds]
        lats = [coord[1] for coord in bounds]

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        # Determine the subdivision count.
        splits = int(math.ceil(math.sqrt(tile_count)))
        lon_splits = splits
        lat_splits = splits

        # Return the original geometry if no split is required.
        if lon_splits * lat_splits == 1:
            return [geometry]

        # Generate tile geometries.
        geometries = []
        lon_step = (max_lon - min_lon) / lon_splits
        lat_step = (max_lat - min_lat) / lat_splits

        for i in range(lon_splits):
            for j in range(lat_splits):
                # Build the coordinates of each tile boundary.
                sub_min_lon = min_lon + i * lon_step
                sub_max_lon = min_lon + (i + 1) * lon_step
                sub_min_lat = min_lat + j * lat_step
                sub_max_lat = min_lat + (j + 1) * lat_step

                # Create a rectangular geometry.
                sub_geom = ee.Geometry.Rectangle([sub_min_lon, sub_min_lat, sub_max_lon, sub_max_lat])

                # Keep only the intersection with the original geometry.
                try:
                    intersection = sub_geom.intersection(geometry, maxError=1)
                    # Check whether the intersection is valid.
                    if intersection.coordinates().getInfo():
                        geometries.append(intersection)
                except Exception as e:
                    logger.warning(f"几何交集计算失败 ({i},{j}): {str(e)}")
                    # Try the tile geometry directly if intersection fails.
                    try:
                        # Check whether the tile center is inside the original geometry.
                        center_lon = (sub_min_lon + sub_max_lon) / 2
                        center_lat = (sub_min_lat + sub_max_lat) / 2
                        point = ee.Geometry.Point([center_lon, center_lat])
                        contains = geometry.contains(point, maxError=1).getInfo()

                        if contains:
                            geometries.append(sub_geom)
                    except Exception as e2:
                        logger.warning(f"备用几何检查也失败: {str(e2)}")
                        continue

        # Return the original geometry if no valid tiles remain.
        if not geometries:
            logger.warning("没有生成有效的分割几何块，使用原始几何")
            return [geometry]

        return geometries
    except Exception as e:
        logger.error(f"分割几何区域时出错: {str(e)}")
        return [geometry]


# Download tiles and merge them.
def download_image_in_tiles(ee_image, geometry, scale, crs, save_path, tile_count=1, process_uuid=None, timestamp=None):
    'Download an Earth Engine image in tiles and merge them at save_path. Geometry, scale and CRS define the output grid; process_uuid and timestamp distinguish temporary files.'
    # Split the geometry.
    if tile_count > 1:
        sub_geometries = split_geometry(geometry, tile_count)
    else:
        sub_geometries = [geometry]

    if len(sub_geometries) == 1:
        # Download directly when only one region is needed.
        clipped_image = ee_image.clip(sub_geometries[0])
        download_url = clipped_image.getDownloadURL({
            'scale': scale,
            'crs': crs,
            'region': sub_geometries[0].coordinates().getInfo(),
            'filePerBand': False,
            'format': 'GEO_TIFF',
        })

        import urllib.request
        urllib.request.urlretrieve(download_url, save_path)
        return

    # Download multiple regions separately before merging.
    temp_files = []
    save_dir = os.path.dirname(save_path)

    try:
        # Download each subregion.
        valid_downloads = 0
        for idx, sub_geom in enumerate(sub_geometries):
            clipped_image = ee_image.clip(sub_geom)
            # Use a unique identifier to prevent filename collisions.
            if process_uuid and timestamp:
                temp_filename = f"temp_tile_{process_uuid}_{timestamp}_{idx}.tif"
            else:
                temp_filename = f"temp_tile_{int(datetime.now().timestamp() * 1000000)}_{idx}.tif"
            temp_path = os.path.join(save_dir, temp_filename)
            temp_files.append(temp_path)

            try:
                download_url = clipped_image.getDownloadURL({
                    'scale': scale,
                    'crs': crs,
                    'region': sub_geom.coordinates().getInfo(),
                    'filePerBand': False,
                    'format': 'GEO_TIFF'
                })

                import urllib.request
                urllib.request.urlretrieve(download_url, temp_path)
                print(f"下载瓦片 {idx + 1}/{len(sub_geometries)}: {temp_path}")
                valid_downloads += 1
            except Exception as e:
                logger.error(f"下载瓦片 {idx + 1} 失败: {str(e)}")
                # Remove failed files from temp_files.
                if temp_path in temp_files:
                    temp_files.remove(temp_path)
                continue

        # Raise an error if no tile was downloaded successfully.
        if valid_downloads == 0:
            raise Exception("没有成功下载任何瓦片")

        # Merge all tiles.
        if temp_files:
            import rasterio
            from rasterio.merge import merge

            # Open the temporary files.
            src_files = []
            for fp in temp_files:
                if os.path.exists(fp):
                    try:
                        src = rasterio.open(fp)
                        src_files.append(src)
                    except Exception as e:
                        logger.warning(f"打开临时文件失败 {fp}: {str(e)}")

            if src_files:
                # Merge the images.
                try:
                    mosaic, out_trans = merge(src_files)

                    # Copy the metadata.
                    out_meta = src_files[0].meta.copy()
                    out_meta.update({
                        "height": mosaic.shape[1],
                        "width": mosaic.shape[2],
                        "transform": out_trans,
                    })

                    # Write the final file.
                    with rasterio.open(save_path, "w", **out_meta) as dest:
                        dest.write(mosaic)

                    print(f"成功合并 {len(src_files)} 个瓦片到: {save_path}")
                except Exception as e:
                    logger.error(f"合并影像时出错: {str(e)}")
                    raise
                finally:
                    # Close all source files.
                    for src in src_files:
                        try:
                            src.close()
                        except:
                            pass

            # Remove temporary files.
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"删除临时文件失败 {temp_file}: {str(e)}")

    except Exception as e:
        # Remove temporary files.
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        raise e


# Look up satellite parameters.
def get_satellite_parameters(satellite):
    'Return the download parameters (scale, crs) for a satellite.'
    if satellite == 'sentinel-2':
        # Sentinel-2 image parameters.
        scale = 20  # Resolution: 20 meters.
        crs = 'EPSG:4326'
    elif satellite == 'sentinel-1':
        # Sentinel-1 image parameters.
        scale = 20  # Resolution: 20 meters.
        crs = 'EPSG:4326'
    elif satellite == 'smap':
        # SMAP image parameters.
        scale = 9000  # Resolution: 9 kilometers.
        crs = 'EPSG:4326'
    else:
        scale = 30
        crs = 'EPSG:4326'

    return scale, crs


# Step 1: initialize and load task information.
def initialize_download_task(task: ImageDownloadTask):
    'Initialize an ImageDownloadTask and return (start_day, end_day, bounding_box, wgs84_coords, geometry).'
    # Initialize Earth Engine.
    initialize_earth_engine()

    # Read the task parameters.
    start_day = task.start_day
    end_day = task.end_day

    polygon = task.polygon
    wgs84_coords = polygon.wgs84_coordinates
    if not wgs84_coords:
        raise ValueError("多边形缺少WGS84坐标")

    # Create an Earth Engine geometry.
    geometry = ee.Geometry.Polygon(wgs84_coords)

    # Compute the bounding rectangle used for clipping.
    bounding_box = geometry.bounds()

    return start_day, end_day, bounding_box, wgs84_coords, geometry

# Steps 2-5: download each satellite's imagery.
def download_satellite_images(task: ImageDownloadTask, satellite, start_day, end_day, bounding_box, wgs84_coords, geometry):
    'Download the requested satellite imagery for an ImageDownloadTask and date range. Use the supplied bounding box, WGS84 coordinates and Earth Engine geometry; return the processing result.'
    try:
        print(f"开始处理 {satellite} 影像下载任务: {task.name} (ID: {task.id})")

        polygon = task.polygon
        image_collection_name = COLLECTION_MAP.get(satellite)

        if not image_collection_name:
            raise ValueError(f"不支持的卫星类型: {satellite}")

        if satellite == 'smap':
            # Iterate over every day from start_day to end_day.
            current_date = datetime.strptime(str(start_day), '%Y-%m-%d').date()
            end_date = datetime.strptime(str(end_day), '%Y-%m-%d').date()

            all_dates_exist = True

            # Check each date in YYYY-MM-DD format.
            while current_date <= end_date:
                # Check whether the SMAP image already exists for this date.
                existing_image = SatelliteImage.objects.filter(
                    polygon=polygon,
                    satellite=satellite,
                    shoot_time=current_date
                ).exists()

                if not existing_image:
                    all_dates_exist = False
                    break

                current_date += timedelta(days=1)

            # Return immediately only when all dates are present.
            if all_dates_exist:
                return {
                    'success': True,
                    'message': f'SMAP数据已完整存在，跳过下载',
                    'downloaded_count': 0
                }

        # Query the image collection.
    # Earth Engine's end date is exclusive; task dates are stored as inclusive
    # dates so add one day before querying the collection.
        collection_end = datetime.strptime(str(end_day), '%Y-%m-%d').date() + timedelta(days=1)
        collection = ee.ImageCollection(image_collection_name) \
            .filterDate(start_day, collection_end.strftime('%Y-%m-%d')) \
            .filterBounds(bounding_box)

        # Select the requested bands.
        selected_bands = SATELLITE_BANDS.get(satellite, [])
        if selected_bands:
            collection = collection.select(selected_bands)

        # Read the image count.
        image_count = collection.size().getInfo()

        print(f"找到 {image_count} 张 {satellite} 影像")

        if image_count == 0:
            return {
                'success': True,
                'message': f'时间范围内没有找到 {satellite} 影像',
                'downloaded_count': 0
            }

        # Group images by date.
        date_groups = defaultdict(list)

        # Retrieve the image list.
        image_list = collection.toList(image_count)

        # Inspect images and group them by date.
        for i in range(image_count):
            try:
                image = ee.Image(image_list.get(i))
                image_info = image.getInfo()

                if not image_info or 'properties' not in image_info:
                    continue

                properties = image_info['properties']
                shoot_time_ms = properties['system:time_start']
                shoot_time = datetime.fromtimestamp(shoot_time_ms / 1000)
                image_date = shoot_time.date()

                # Read the image identifier.
                image_id = properties.get('system:id', f'{satellite}_image_{i}')

                date_groups[image_date].append({
                    'index': i,
                    'image_id': image_id,
                    'shoot_time': shoot_time,
                    'ee_image': image
                })

            except Exception as e:
                logger.error(f"分析第 {i + 1} 张 {satellite} 影像时出错: {str(e)}")
                continue
        print(f"共{len(date_groups.keys())}天")
        # Mosaic and download each date group.
        processed_count = 0

        # Look up satellite parameters.
        scale, crs = get_satellite_parameters(satellite)

        # Process date groups in parallel.
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            future_to_date = {}
            for image_date, images_in_date in date_groups.items():
                future = executor.submit(
                    process_date_group,
                    satellite,
                    image_date,
                    images_in_date,
                    bounding_box,
                    scale,
                    crs,
                    polygon
                )
                future_to_date[future] = image_date

            for future in concurrent.futures.as_completed(future_to_date):
                date = future_to_date[future]
                try:
                    result = future.result()
                    if result:
                        processed_count += 1
                except Exception as e:
                    logger.error(f"处理 {satellite} 日期 {date} 的影像时出错: {str(e)}")

        print(f"{satellite} 影像处理完成: {task.name}, 处理了 {processed_count} 个日期的影像")

        return {
            'success': True,
            'message': f'{satellite} 影像处理完成',
            'processed_dates': processed_count,
            'total_images_found': image_count
        }

    except Exception as e:
        logger.error(f"处理 {satellite} 影像任务 {task.name} 时发生错误: {str(e)}")
        return {
            'success': False,
            'message': f'{satellite} 影像处理失败: {str(e)}'
        }


def process_date_group(satellite, image_date, images_in_date, bounding_box, scale, crs, polygon):
    "Mosaic and download a satellite's images_in_date for image_date using the specified bounding box, scale, CRS and polygon."
    import uuid
    import time

    try:
        print(f"处理 {satellite} 日期 {image_date}，包含 {len(images_in_date)} 张影像")

        # Generate a unique identifier for this run.
        process_uuid = str(uuid.uuid4())[:8]
        timestamp = int(time.time())

        # Build the destination path.
        date_str = image_date.strftime('%Y-%m-%d')
        save_dir = os.path.join(settings.MEDIA_ROOT, 'images', str(polygon.id), satellite)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{date_str}.tif")

        if os.path.exists(save_path):
            # Check for an existing image record for this date and satellite.
            existing_image = SatelliteImage.objects.filter(
                polygon=polygon,
                satellite=satellite,
                shoot_time=image_date
            ).first()

            if existing_image:
                print(f"影像 {satellite} 日期 {image_date} 已存在，跳过下载")
                return True

        # Mosaic multiple images with Earth Engine.
        if len(images_in_date) > 1:
            # Use Earth Engine mosaic to combine images from the same day.
            ee_images = [img_data['ee_image'] for img_data in images_in_date]
            ee_image = ee_images[0]
            for i in range(1, len(ee_images)):
                ee_image = ee.ImageCollection([ee_image, ee_images[i]]).mosaic()
        else:
            # A single image needs no mosaic.
            ee_image = images_in_date[0]['ee_image']

        # Clip to the polygon's bounding rectangle.
        clipped_image = ee_image.clip(bounding_box)

        # Calculate the tiling plan.
        tile_count = calculate_tiling_scheme(bounding_box, scale, satellite, max_size_mb=42)

        # Pass the unique identifier to the tiled downloader.
        download_image_in_tiles(clipped_image, bounding_box, scale, crs, save_path, tile_count, process_uuid, timestamp)

        print(f"影像已下载到: {save_path}")

        # Create a satellite image record.
        relative_path = os.path.relpath(save_path, settings.MEDIA_ROOT)

        # Determine the image identifier and acquisition time.
        if len(images_in_date) > 1:
            # Multiple images were mosaicked.
            shoot_times = [img_data['shoot_time'] for img_data in images_in_date]
            image_ids = [img_data['image_id'] for img_data in images_in_date]

            # Use the earliest acquisition time for the mosaic.
            earliest_time = min(shoot_times)
            shoot_date = earliest_time.date()

            satellite_img = SatelliteImage.objects.create(
                polygon=polygon,
                satellite=satellite,
                name=f"{satellite}_{image_date}_mosaic",
                shoot_time=shoot_date,
                image_identifier='+'.join(image_ids[:3]) + (
                    '_and_more' if len(image_ids) > 3 else ''),
                image=relative_path,
                file_size=os.path.getsize(save_path) if os.path.exists(save_path) else None
            )
        else:
            # A single source image.
            image_data = images_in_date[0]
            satellite_img = SatelliteImage.objects.create(
                polygon=polygon,
                satellite=satellite,
                name=f"{satellite}_{image_date}_clipped",
                shoot_time=image_data['shoot_time'].date(),
                image_identifier=image_data['image_id'] + '_clipped',
                image=relative_path,
                file_size=os.path.getsize(save_path) if os.path.exists(save_path) else None
            )

        print(f"创建 {satellite} 影像记录: {satellite_img.name}")
        return True

    except Exception as e:
        logger.error(f"处理 {satellite} 日期 {image_date} 的影像时出错: {str(e)}")
        return False

from config.settings import MEDIA_ROOT
from polygons.tools import create_polygon_shapefile
from result_img.models import ResultImg
# Main image download task handler.
def process_satellite_imagery_with_mosaic(task: ImageDownloadTask):
    'Process an ImageDownloadTask by clipping, mosaicking and downloading imagery locally; return the processing result.'
    polygons_obj = Polygon.objects.get(id=task.polygon_id)
    if polygons_obj.wgs84_shp_dir is None:
        shp_dir = os.path.join(MEDIA_ROOT,'images' , str(polygons_obj.id), 'shp')
        create_polygon_shapefile(polygons_obj.wgs84_coordinates, shp_dir, 'shp')
        polygons_obj.wgs84_shp_dir = os.path.relpath(shp_dir, MEDIA_ROOT).replace('\\', '/')
        polygons_obj.save()

    try:
        # Step 1: initialize and load task information.
        start_day, end_day, bounding_box, wgs84_coords, geometry = initialize_download_task(task)
        # Mark the task as processing.
        task.status = 'processing'
        task.error_message = None
        task.save()

        # Step 3: download satellites in parallel.
        results = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_satellite = {
                executor.submit(
                    download_satellite_images,
                    task,
                    satellite,
                    start_day,
                    end_day,
                    bounding_box,
                    wgs84_coords,
                    geometry
                ): satellite for satellite in ALLOWED_SATELLITES
            }

            for future in concurrent.futures.as_completed(future_to_satellite):
                satellite = future_to_satellite[future]
                try:
                    result = future.result()
                    results[satellite] = result
                except Exception as e:
                    logger.error(f"处理 {satellite} 影像时出错: {str(e)}")
                    results[satellite] = {
                        'success': False,
                        'message': f'{satellite} 影像处理失败: {str(e)}'
                    }

        # Step 5: update task information.
        success_count = sum(1 for r in results.values() if r.get('success', False))

        if success_count == len(ALLOWED_SATELLITES):
            task.status = 'completed'
        else:
            task.status = 'failed'
            task.error_message = '; '.join(
                result.get('message', '') for result in results.values()
                if result and not result.get('success', False)
            ) or 'No satellite imagery was downloaded.'

        task.completed_at = timezone.now()
        task.save()

        print(f"任务处理完成: {task.name}, 成功处理 {success_count}/{len(ALLOWED_SATELLITES)} 种卫星影像")

        return {
            'success': success_count == len(ALLOWED_SATELLITES),
            'message': f'任务完成，成功处理 {success_count} 种卫星影像' if success_count == len(ALLOWED_SATELLITES) else (task.error_message or f'Only {success_count} of {len(ALLOWED_SATELLITES)} satellite datasets completed.'),
            'details': results
        }

    except Exception as e:
        task.status = 'failed'
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save()

        logger.error(f"处理任务 {task.name} 时发生错误: {str(e)}")
        return {
            'success': False,
            'message': f'任务处理失败: {str(e)}'
        }
