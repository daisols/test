import os
import glob
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import rasterio


def get_values_by_date_from_folder_threaded(tif_folder_path, lng, lat):
    'Read TIFF values at longitude lng and latitude lat using threads. Return values sorted by filename date from tif_folder_path.'
    # Find all TIFF files in the directory.
    tif_files = glob.glob(os.path.join(tif_folder_path, "*.tif")) + \
                glob.glob(os.path.join(tif_folder_path, "*.tiff"))

    # Prepare processing arguments.
    process_args = []
    date_list = []

    for tif_file in tif_files:
        try:
            # Extract the date from the filename.
            filename = os.path.basename(tif_file)
            date_str = filename.split('.')[0]  # Remove the extension.
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')

            process_args.append((tif_file, lng, lat))
            date_list.append(date_obj)

        except ValueError:
            # Skip filenames that do not match YYYY-MM-DD.
            continue

    # Use a lightweight thread pool.
    max_workers = min(10, len(process_args))  # Limit the thread count.
    if not process_args:
        return []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        values = list(executor.map(_get_value_at_lng_lat_single_wrapper, process_args))

    # Keep missing values so the result remains aligned with the complete daily date axis.
    date_value_pairs = [(date_list[i], values[i]) for i in range(len(date_list))]

    # Sort by date.
    date_value_pairs.sort(key=lambda x: x[0])

    # Return only the values.
    return [value for _, value in date_value_pairs]


def _get_value_at_lng_lat_single_wrapper(args):
    'Wrapper for parallel processing.'
    tif_file_path, lng, lat = args
    return _get_value_at_lng_lat_single(tif_file_path, lng, lat)


def _get_value_at_lng_lat_single(tif_file_path, lng, lat):
    'Read the pixel at longitude lng and latitude lat from tif_file_path. Return None if it is outside the raster or an error occurs.'
    try:
        with rasterio.open(tif_file_path) as dataset:
            # Check for a single-band image.
            if dataset.count != 1:
                return None

            # Convert longitude and latitude to raster row and column.
            row, col = dataset.index(lng, lat)

            # Check that the row and column are within bounds.
            if (0 <= row < dataset.height) and (0 <= col < dataset.width):
                # Read one pixel.
                value = dataset.read(1, masked=True, window=((row, row + 1), (col, col + 1)))
                sample = value[0, 0]
                if np.ma.is_masked(sample) or not np.isfinite(sample) or sample < 0:
                    return None
                return float(sample)
            else:
                return None

    except Exception:
        return None


def get_min_max_arv_moisture(tif_file_path):
    'Return (minimum, maximum, mean) for a TIFF, or (None, None, None) on error.'
    try:
        with rasterio.open(tif_file_path) as dataset:
            # Check for a single-band image.
            if dataset.count != 1:
                return None, None, None

            # Read the entire band.
            data = dataset.read(1, masked=True)
            valid_data = data.compressed()
            valid_data = valid_data[np.isfinite(valid_data) & (valid_data >= 0)]

            if len(valid_data) == 0:
                return 0, 0, 0

            # Calculate statistics.
            min_value = float(np.min(valid_data))
            max_value = float(np.max(valid_data))
            mean_value = float(np.mean(valid_data))

            if min_value is None:
                min_value = 0
            if max_value is None:
                max_value = 0
            if mean_value is None:
                mean_value = 0
            return min_value, max_value, mean_value

    except Exception as e:
        print(f"Could not analyze {tif_file_path}: {str(e)}")
        return 0, 0, 0


