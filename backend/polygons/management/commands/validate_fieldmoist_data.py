from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate the local datasets required by the bundled demos."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", choices=("jiefangzha", "test", "all"), default="all")

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT) / "images"
        dataset = options["dataset"]
        errors = []
        if dataset in ("jiefangzha", "all"):
            base = root / "83"
            errors += self._check_boundary(base / "shp", "jiefangzha")
            result = base / "2018-05-01_2018-05-24"
            errors += self._check_count(result / "soil_moisture_result", "*.tif", 24, "jiefangzha GeoTIFF")
            errors += self._check_count(result / "soil_moisture_png", "*.png", 24, "jiefangzha PNG")
        if dataset in ("test", "all"):
            base = root / "82"
            errors += self._check_boundary(base / "shp", "offline test")
            errors += self._check_count(base / "offline" / "smap", "*.tif", 2, "offline test SMAP")
            if not (base / "82" / "local_soil_moisture").is_dir():
                errors.append("missing offline test soil-moisture directory: images/82/82/local_soil_moisture")
            if not (base / "82" / "measurements" / "measurements.xlsx").is_file():
                errors.append("missing offline test measurements workbook")
            if not (base / "2018-05-01_2018-05-24" / "process" / "shared_ml_model_rf.pkl").is_file():
                errors.append("missing offline test shared model")
        if errors:
            raise CommandError("Dataset validation failed:\n- " + "\n- ".join(errors))
        self.stdout.write(self.style.SUCCESS(f"{dataset} dataset validation passed."))

    @staticmethod
    def _check_boundary(path, label):
        if not any(path.glob("*.shp")):
            return [f"missing {label} boundary SHP under {path}"]
        return []

    @staticmethod
    def _check_count(path, pattern, minimum, label):
        count = len(list(path.glob(pattern)))
        return [] if count >= minimum else [f"{label}: expected at least {minimum}, found {count} ({path})"]
