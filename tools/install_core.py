"""Install an authorized private binary checkout into this application."""
import argparse
from pathlib import Path
import shutil
import tempfile

from verify_release import validate

ROOT = Path(__file__).resolve().parents[1]
REL = Path('backend/service/transform_tif/_native/win_amd64_cp312')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-dir', type=Path, required=True, help='Extracted private repository root')
    parser.add_argument('--upgrade', action='store_true', help='Replace the installed core after stopping the backend')
    args = parser.parse_args()
    source = args.from_dir.resolve()
    validate(source)
    license_path = source / 'LICENSE.txt'
    if not license_path.is_file():
        raise SystemExit('Private core LICENSE.txt is missing.')
    target = ROOT / REL
    if target.exists():
        validate(ROOT)
        if (target / 'manifest.json').read_bytes() == (source / REL / 'manifest.json').read_bytes():
            print('The matching core is already installed.')
            return
        if not args.upgrade:
            raise SystemExit('A different core version is installed. Stop the backend and rerun with --upgrade.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='install-', dir=target.parent) as temp:
        prepared = Path(temp) / target.name
        shutil.copytree(source / REL, prepared, ignore=shutil.ignore_patterns('__pycache__'))
        backup = Path(temp) / 'previous-core'
        try:
            if target.exists():
                target.rename(backup)
            prepared.rename(target)
            validate(ROOT)
        except Exception:
            if backup.exists():
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            raise
    shutil.copy2(license_path, ROOT / 'backend/service/transform_tif/CORE_LICENSE.txt')
    validate(ROOT)
    print('Windows core installed. Run python tools/smoke_native_core.py next.')


if __name__ == '__main__':
    main()
