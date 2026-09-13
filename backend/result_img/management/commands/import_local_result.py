import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from django.core.management.base import BaseCommand, CommandError
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from rasterio.features import shapes
from rasterio.mask import mask
from shapely.geometry import shape
from shapely.ops import unary_union

from polygons.models import Polygon
from polygons.tools import wgs84_to_gcj02
from result_img.models import ResultImg


def _valid_mask(data, nodata):
    valid = np.isfinite(data) & (data >= 0)
    if nodata is not None and np.isfinite(nodata):
        valid &= data != nodata
    return valid


def _largest_valid_polygon(tif_path):
    with rasterio.open(tif_path) as dataset:
        if dataset.count != 1:
            raise CommandError(f"{tif_path.name} must contain exactly one band")
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise CommandError(f"{tif_path.name} must use EPSG:4326, got {dataset.crs}")

        data = dataset.read(1)
        valid = _valid_mask(data, dataset.nodata)
        if not valid.any():
            raise CommandError(f"{tif_path.name} has no finite data pixels")

        polygons = [
            shape(geometry)
            for geometry, value in shapes(
                valid.astype(np.uint8),
                mask=valid,
                transform=dataset.transform,
                connectivity=8,
            )
            if value == 1
        ]
        geometry = unary_union(polygons)
        if geometry.geom_type == "MultiPolygon":
            geometry = max(geometry.geoms, key=lambda item: item.area)

        if geometry.geom_type != "Polygon" or geometry.is_empty:
            raise CommandError("Could not derive a single valid-data polygon from the reference TIF")
        return geometry, dataset.bounds, dataset.transform, dataset.width, dataset.height


def _load_boundary_shp(shp_path):
    boundary_frame = gpd.read_file(shp_path)
    if boundary_frame.empty:
        raise CommandError(f"Boundary SHP is empty: {shp_path}")
    if boundary_frame.crs is None:
        raise CommandError(f"Boundary SHP has no CRS: {shp_path}")
    boundary_frame = boundary_frame.to_crs("EPSG:4326")
    geometry = unary_union([item for item in boundary_frame.geometry if item is not None])
    if geometry.geom_type == "MultiPolygon":
        geometry = max(geometry.geoms, key=lambda item: item.area)
    if geometry.geom_type != "Polygon" or geometry.is_empty:
        raise CommandError("Boundary SHP must contain a non-empty Polygon")
    return geometry


def _date_files(input_dir, start_day, end_day):
    files = sorted([*input_dir.glob("*.tif"), *input_dir.glob("*.tiff")])
    by_date = {}
    for path in files:
        try:
            file_day = date.fromisoformat(path.stem)
        except ValueError as exc:
            raise CommandError(f"Invalid result filename: {path.name}; expected YYYY-MM-DD.tif") from exc
        by_date[file_day] = path

    expected = []
    current = start_day
    while current <= end_day:
        expected.append(current)
        current += timedelta(days=1)

    missing = [item.isoformat() for item in expected if item not in by_date]
    extra = [item.isoformat() for item in by_date if item < start_day or item > end_day]
    if missing:
        raise CommandError(f"Missing {len(missing)} daily TIF files; first missing date: {missing[0]}")
    if extra:
        raise CommandError(f"Found files outside the requested range; first extra date: {extra[0]}")
    return [by_date[item] for item in expected]


def _color_lut():
    color_map = LinearSegmentedColormap.from_list(
        "CB-RdBu",
        [(0.8392, 0.1529, 0.1569), (1.0, 1.0, 1.0), (0.1216, 0.4667, 0.7059)],
        N=256,
    )
    return (color_map(np.linspace(0, 1, 256)) * 255).astype(np.uint8)


def _write_aligned_outputs(tif_path, png_path, boundary, color_min, color_max, lut, crop_tif):
    temp_tif_path = tif_path.with_name(f".{tif_path.name}.aligning")
    with rasterio.open(tif_path) as dataset:
        if dataset.count != 1 or dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise CommandError(f"Incompatible TIF: {tif_path.name}")
        masked_data, output_transform = mask(
            dataset,
            [boundary.__geo_interface__],
            crop=True,
            filled=False,
        )
        data = masked_data[0].astype(np.float32, copy=False)
        valid = ~np.ma.getmaskarray(data) & _valid_mask(np.asarray(data), dataset.nodata)

        if crop_tif:
            profile = dataset.profile.copy()
            nodata = dataset.nodata
            if nodata is None:
                nodata = np.nan if np.issubdtype(np.dtype(dataset.dtypes[0]), np.floating) else 0
            profile.update(
                height=data.shape[0],
                width=data.shape[1],
                transform=output_transform,
                nodata=nodata,
            )
            try:
                with rasterio.open(temp_tif_path, "w", **profile) as output:
                    output.write(np.ma.filled(masked_data, nodata))
                    output.update_tags(**dataset.tags())
            except Exception:
                temp_tif_path.unlink(missing_ok=True)
                raise

        normalized = np.zeros(data.shape, dtype=np.float32)
        np.subtract(np.asarray(data), color_min, out=normalized, where=valid)
        normalized /= color_max - color_min
        np.clip(normalized, 0, 1, out=normalized)
        indices = (normalized * 255).astype(np.uint8)
        rgba = lut[indices].copy()
        rgba[~valid, 3] = 0
        Image.fromarray(rgba, mode="RGBA").save(png_path, format="PNG", compress_level=6)

    if crop_tif:
        os.replace(temp_tif_path, tif_path)


def _validate_rasters(tif_files, reference_transform, reference_width, reference_height):
    for tif_path in tif_files:
        with rasterio.open(tif_path) as dataset:
            compatible = (
                dataset.count == 1
                and dataset.crs is not None
                and dataset.crs.to_epsg() == 4326
                and dataset.width == reference_width
                and dataset.height == reference_height
                and dataset.transform.almost_equals(reference_transform)
            )
            if not compatible:
                raise CommandError(f"Raster grid does not match the reference TIF: {tif_path.name}")


class Command(BaseCommand):
    help = "Register precomputed daily GeoTIFFs as a completed result set."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--result-dir", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)
        parser.add_argument("--color-min", type=float, default=0.0)
        parser.add_argument("--color-max", type=float, default=0.4)
        parser.add_argument("--overwrite-png", action="store_true")
        parser.add_argument(
            "--boundary-shp",
            help="Use this existing simplified SHP as the crop/display boundary without rewriting it.",
        )
        parser.add_argument(
            "--keep-tif-grid",
            action="store_true",
            help="Generate aligned PNG files without cropping and masking the source TIF files.",
        )
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--analyze-only", action="store_true")

    def handle(self, *args, **options):
        try:
            start_day = date.fromisoformat(options["start_date"])
            end_day = date.fromisoformat(options["end_date"])
        except ValueError as exc:
            raise CommandError("Dates must use YYYY-MM-DD") from exc
        if start_day > end_day:
            raise CommandError("start-date must not be after end-date")
        if options["color_min"] >= options["color_max"]:
            raise CommandError("color-min must be less than color-max")
        if options["workers"] < 1:
            raise CommandError("workers must be at least 1")

        result_dir = Path(options["result_dir"]).resolve()
        input_dir = result_dir / "soil_moisture_result"
        png_dir = result_dir / "soil_moisture_png"
        if not input_dir.is_dir():
            raise CommandError(f"Missing directory: {input_dir}")

        tif_files = _date_files(input_dir, start_day, end_day)
        with rasterio.open(tif_files[0]) as reference_dataset:
            raster_bounds = reference_dataset.bounds
            transform = reference_dataset.transform
            width = reference_dataset.width
            height = reference_dataset.height
        _validate_rasters(tif_files, transform, width, height)
        boundary_shp = Path(options["boundary_shp"]) if options["boundary_shp"] else result_dir.parent / "shp" / "shp.shp"
        if not boundary_shp.is_absolute():
            boundary_shp = Path.cwd() / boundary_shp
        if boundary_shp.exists():
            boundary = _load_boundary_shp(boundary_shp)
        else:
            raise CommandError(
                f"Missing simplified boundary SHP: {boundary_shp}. "
                "The import command does not create or modify boundary SHP files."
            )
        coordinates = [[float(lng), float(lat)] for lng, lat in boundary.exterior.coords]

        self.stdout.write(f"TIF files: {len(tif_files)}")
        self.stdout.write(f"Raster bounds: {tuple(round(value, 8) for value in raster_bounds)}")
        self.stdout.write(f"Valid-data bounds: {tuple(round(value, 8) for value in boundary.bounds)}")
        self.stdout.write(f"Boundary vertices: {len(coordinates)}")
        self.stdout.write("TIF and PNG files will use the exact valid-data boundary")
        if options["analyze_only"]:
            return

        existing = Polygon.objects.filter(name=options["name"]).first()
        expected_id = int(result_dir.parent.name) if result_dir.parent.name.isdigit() else None
        if existing is None and expected_id is not None and Polygon.objects.filter(pk=expected_id).exists():
            raise CommandError(f"Polygon ID {expected_id} is already in use")

        gcj02_coordinates = [list(wgs84_to_gcj02(*point)) for point in coordinates]
        if existing is None:
            polygon = Polygon.objects.create(
                id=expected_id,
                name=options["name"],
                gcj02_coordinates=gcj02_coordinates,
                wgs84_coordinates=coordinates,
            )
        else:
            polygon = existing
            if expected_id is not None and polygon.pk != expected_id:
                raise CommandError(
                    f"Polygon {polygon.name} has ID {polygon.pk}, but result-dir is under ID {expected_id}"
                )
            polygon.gcj02_coordinates = gcj02_coordinates
            polygon.wgs84_coordinates = coordinates
            polygon.save(update_fields=["gcj02_coordinates", "wgs84_coordinates", "updated_at"])

        self.stdout.write(f"Preserved existing boundary SHP: {boundary_shp}")

        png_dir.mkdir(parents=True, exist_ok=True)
        lut = _color_lut()
        pending = []
        for tif_path in tif_files:
            png_path = png_dir / f"{tif_path.stem}.png"
            if not options["keep_tif_grid"] or options["overwrite_png"] or not png_path.exists():
                pending.append((tif_path, png_path))

        generated = 0
        with ThreadPoolExecutor(max_workers=options["workers"]) as executor:
            futures = {
                executor.submit(
                    _write_aligned_outputs,
                    tif_path,
                    png_path,
                    boundary,
                    options["color_min"],
                    options["color_max"],
                    lut,
                    options["keep_tif_grid"] is False,
                ): tif_path
                for tif_path, png_path in pending
            }
            for future in as_completed(futures):
                tif_path = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    raise CommandError(f"Failed to generate PNG for {tif_path.name}: {exc}") from exc
                generated += 1
                if generated == 1 or generated % 25 == 0 or generated == len(pending):
                    self.stdout.write(f"PNG progress: {generated}/{len(pending)}")

        result = ResultImg.objects.filter(
            polygon=polygon,
            start_day=start_day,
            end_day=end_day,
        ).order_by("id").first()
        if result is None:
            result = ResultImg.objects.create(
                polygon=polygon,
                start_day=start_day,
                end_day=end_day,
                result_dir=str(result_dir),
            )
        result.result_dir = str(result_dir)
        result.process = 100
        result.status = "completed"
        result.is_delete = False
        result.save(update_fields=["result_dir", "process", "status", "is_delete"])

        self.stdout.write(self.style.SUCCESS(
            f"Imported polygon {polygon.name} (ID {polygon.pk}) and result set {result.pk}; "
            f"generated {generated} PNG files."
        ))
