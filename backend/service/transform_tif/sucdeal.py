from service.processing_output import quiet_print as print
import os
import glob
from multiprocessing import Pool, cpu_count
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import geometry_mask
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.cm as cm
from PIL import Image


def color_single_tif(args):
    'Worker function that processes one TIFF in a single process.'
    input_path, output_dir, cmap_name, minValue, maxValue, max_size_mb, shp_path = args

    try:
        # Read the raster mask and georeferencing together. Raster nodata,
        # NaN and the simplified SHP boundary all control PNG transparency.
        with rasterio.open(input_path) as src:
            if src.count != 1:
                raise ValueError(f"Only single-band GeoTIFFs are supported: {input_path}")
            masked = src.read(1, masked=True)
            data = np.asarray(masked.filled(np.nan), dtype=np.float32)
            valid_mask = ~np.ma.getmaskarray(masked) & np.isfinite(data)
            raster_crs = src.crs
            raster_transform = src.transform

        if shp_path:
            boundary = gpd.read_file(shp_path)
            if boundary.empty:
                raise ValueError(f"The SHP boundary is empty: {shp_path}")
            if boundary.crs is None:
                raise ValueError(f"The SHP boundary has no CRS: {shp_path}")
            if raster_crs is None:
                raise ValueError(f"The GeoTIFF has no CRS: {input_path}")
            boundary = boundary.to_crs(raster_crs)
            inside_boundary = geometry_mask(
                [geometry.__geo_interface__ for geometry in boundary.geometry if geometry is not None],
                out_shape=data.shape,
                transform=raster_transform,
                invert=True,
                all_touched=False,
            )
            valid_mask &= inside_boundary

        # Normalize and clip the data.
        if minValue >= maxValue:
            raise ValueError("minValue必须小于maxValue")
        normalized = np.clip((data - minValue) / (maxValue - minValue), 0, 1)

        # Select the color map.
        if cmap_name == "CB-RdBu":
            # Custom blue-white-red palette approximating CB-RdBu.
            cmap = LinearSegmentedColormap.from_list(
                "CB-RdBu",
                [
                    (0.8392, 0.1529, 0.1569),# Dark red.
                    (1.0, 1.0, 1.0),  # White.
                    (0.1216, 0.4667, 0.7059),  # Dark blue.
                ],
                N=256
            )
        else:
            cmap = cm.get_cmap(cmap_name, 256)

        # Apply the palette and convert to 8-bit RGB.
        colored = (cmap(normalized)[:, :, :3] * 255).astype(np.uint8)

        # Pixels outside the simplified SHP (and raster NaN/nodata pixels)
        # are transparent regardless of their RGB value.
        alpha_channel = np.where(valid_mask, 255, 0).astype(np.uint8)

        # Combine RGB and alpha channels.
        rgba_image = np.dstack((colored, alpha_channel))

        # Reduce image size to meet the file size limit.
        # Step 1: reduce resolution proportionally.
        original_height, original_width = rgba_image.shape[:2]
        scale_factor = 1.0

        # Compute the target dimensions for the size limit.
        while True:
            new_height = int(original_height * scale_factor)
            new_width = int(original_width * scale_factor)

            # Keep alpha binary while downsampling so pixels outside the SHP
            # cannot acquire color from Lanczos interpolation at the edge.
            resized_rgb = Image.fromarray(colored, mode='RGB').resize(
                (new_width, new_height), Image.LANCZOS)
            resized_alpha = Image.fromarray(alpha_channel, mode='L').resize(
                (new_width, new_height), Image.NEAREST)
            resized_image = Image.merge('RGBA', (*resized_rgb.split(), resized_alpha))

            # Save temporarily to measure file size.
            output_filename = os.path.splitext(os.path.basename(input_path))[0] + '_temp.png'
            temp_output_path = os.path.join(output_dir, output_filename)

            resized_image.save(temp_output_path, format='PNG', optimize=True)

            # Check the file size.
            file_size_mb = os.path.getsize(temp_output_path) / (1024 * 1024)

            if file_size_mb <= max_size_mb or scale_factor <= 0.3:  # Do not reduce below 30 percent of the original dimensions.
                # Accept the image when it meets the limit or reaches the minimum scale.
                final_image = resized_image
                os.remove(temp_output_path)  # Delete the temporary file.
                break
            else:
                # Delete the temporary file and reduce the dimensions further.
                os.remove(temp_output_path)
                scale_factor *= 0.9  # Reduce dimensions by ten percent per iteration.

        # Save the final PNG.
        output_filename = os.path.splitext(os.path.basename(input_path))[0] + '.png'
        output_path = os.path.join(output_dir, output_filename)

        # Save PNG using optimized settings.
        final_image.save(
            output_path,
            format='PNG',
            optimize=True,  # Enable optimization.
            compress_level=9  # Maximum compression level.
        )

        # Verify the final file size.
        final_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"已处理: {output_filename} (大小: {final_size_mb:.2f} MB)")

    except Exception as e:
        print(f"处理{os.path.basename(input_path)}出错: {str(e)}")


def batch_color_tifs(input_dir, output_dir, cmap_name="CB-RdBu", minValue=0.0,
                     maxValue=0.4, max_size_mb=20, shp_dir=None):
    'Colorize all single-band TIFFs in input_dir in parallel. Write PNGs to output_dir using cmap_name (default CB-RdBu), minValue/maxValue (default 0.0/0.4), and max_size_mb (default 20 MB).'
    # Create the output directory.
    os.makedirs(output_dir, exist_ok=True)

    # Find all TIFF files.
    tif_files = glob.glob(os.path.join(input_dir, "*.tif")) + \
                glob.glob(os.path.join(input_dir, "*.tiff"))

    if not tif_files:
        print("未找到任何TIFF文件")
        return

    shp_path = None
    if shp_dir:
        shp_files = sorted(glob.glob(os.path.join(shp_dir, '*.shp')))
        if not shp_files:
            raise FileNotFoundError(f"No .shp file was found in {shp_dir}")
        shp_path = shp_files[0]

    # Prepare worker arguments, including max_size_mb.
    process_args = [
        (file, output_dir, cmap_name, minValue, maxValue, max_size_mb, shp_path)
        for file in tif_files
    ]

    # Process files in parallel with a limited CPU allocation.
    max_workers = max(1, int(cpu_count() * 0.2))
    print(f"启动并行处理，使用{max_workers}个进程，共{len(tif_files)}个文件")

    with Pool(processes=max_workers) as pool:
        pool.map(color_single_tif, process_args)

    print("批量处理完成")


