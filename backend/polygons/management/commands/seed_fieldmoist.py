from pathlib import Path

import geopandas as gpd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from shapely.ops import unary_union

from polygons.models import Polygon
from polygons.tools import wgs84_to_gcj02
from result_img.models import ResultImg


class Command(BaseCommand):
    help = 'Register the bundled Jiefangzha boundary and its May 2018 result set.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-file-check',
            action='store_true',
            help='Register metadata even when daily raster files are not present.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        polygon_root = media_root / 'images' / '83'
        shp_path = polygon_root / 'shp' / 'shp.shp'
        result_dir = polygon_root / '2018-05-01_2018-05-24'
        tif_dir = result_dir / 'soil_moisture_result'
        png_dir = result_dir / 'soil_moisture_png'

        if not shp_path.exists():
            raise CommandError(f'Missing simplified boundary: {shp_path}')

        frame = gpd.read_file(shp_path)
        if frame.empty or frame.crs is None:
            raise CommandError('The boundary shapefile must contain geometry and a CRS.')
        frame = frame.to_crs('EPSG:4326')
        geometry = unary_union([item for item in frame.geometry if item is not None])
        if geometry.geom_type == 'MultiPolygon':
            geometry = max(geometry.geoms, key=lambda item: item.area)
        if geometry.geom_type != 'Polygon' or geometry.is_empty:
            raise CommandError('The simplified boundary must contain a non-empty Polygon.')

        if not options['skip_file_check']:
            tif_count = len(list(tif_dir.glob('*.tif')))
            png_count = len(list(png_dir.glob('*.png')))
            if tif_count != 24 or png_count != 24:
                raise CommandError(
                    f'Expected 24 TIF and 24 PNG files; found {tif_count} TIF and {png_count} PNG.'
                )

        coordinates = [[float(x), float(y)] for x, y in geometry.exterior.coords]
        gcj_coordinates = [list(wgs84_to_gcj02(x, y)) for x, y in coordinates]

        # Keep user-created areas and results intact; this command only
        # creates or updates the bundled jiefangzha example.
        polygon, _ = Polygon.objects.update_or_create(
            pk=83,
            defaults={
                'name': 'jiefangzha',
                'wgs84_coordinates': coordinates,
                'gcj02_coordinates': gcj_coordinates,
                'wgs84_shp_dir': 'images/83/shp',
            },
        )
        ResultImg.objects.filter(polygon=polygon).exclude(pk=83).delete()
        ResultImg.objects.update_or_create(
            pk=83,
            defaults={
                'polygon': polygon,
                'start_day': '2018-05-01',
                'end_day': '2018-05-24',
                'result_dir': 'images/83/2018-05-01_2018-05-24',
                'process': 100,
                'status': 'completed',
                'is_delete': False,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            'FieldMoist dataset registered: polygon 83, result set 83, 2018-05-01 to 2018-05-24.'
        ))
