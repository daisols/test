"""Validate native artifacts and prevent core-source distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = 'backend/service/transform_tif/'
GROUPS = ('function1', 'function2', 'function3', 'predeal')


def validate(root):
    native = root / CORE / '_native/win_amd64_cp312'
    manifest = json.loads((native / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['platform'] != 'win_amd64' or manifest['python'] != 'cp312':
        raise ValueError('Unsupported native platform')
    allowed = {'manifest.json'}
    for group in GROUPS:
        init = native / group / '__init__.py'
        if init.read_bytes():
            raise ValueError(f'Native package initializer must be empty: {init}')
        allowed.add(f'{group}/__init__.py')
    for entry in manifest['modules']:
        relative = entry['file']
        if not re.fullmatch(r'(function[123]|predeal)/[a-z][a-z0-9_]*\.cp312-win_amd64\.pyd', relative):
            raise ValueError(f'Invalid native path: {relative}')
        group, filename = relative.split('/')
        if entry['module'] != f"service.transform_tif.{group}.{filename.split('.')[0]}":
            raise ValueError(f'Native module name mismatch: {relative}')
        if relative not in allowed and (native / relative).suffix == '.pyd':
            allowed.add(relative)
        else:
            raise ValueError(f'Invalid native manifest entry: {relative}')
        data = (native / relative).read_bytes()
        if not data.startswith(b'MZ') or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'Invalid native artifact: {relative}')
    for path in native.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.relative_to(native).as_posix() not in allowed:
            raise ValueError(f'Unexpected file in native distribution: {path}')
    return len(manifest['modules'])


def check_paths(paths, public=False):
    for path in paths:
        name = path.replace('\\', '/')
        if public and (name.startswith(CORE + '_native/') or Path(name).suffix.lower() == '.pyd'):
            raise ValueError(f'Private binary would be published publicly: {name}')
        if Path(name).name == '.env' or Path(name).suffix in {'.sqlite3', '.key', '.pem'}:
            raise ValueError(f'Local configuration or credentials would be published: {name}')
        if name.startswith(('.private-build/', 'release/')) or any(name.startswith(CORE + g + '/') for g in GROUPS):
            raise ValueError(f'Private source/build file would be published: {name}')
        if Path(name).suffix.lower() in {'.pyc', '.pyo', '.pyx', '.pxd', '.c', '.cpp', '.pdb', '.obj', '.lib'}:
            raise ValueError(f'Source/cache/debug artifact would be published: {name}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--public', action='store_true', help='Check public source without private binaries')
    parser.add_argument('--zip', type=Path, help='Export only Git-visible files for a source-free trial')
    args = parser.parse_args()
    root = args.root.resolve()
    count = 0 if args.public else validate(root)
    if (root / '.git').exists():
        paths = subprocess.check_output([
            'git', '-c', f'safe.directory={root.as_posix()}', 'ls-files',
            '--cached', '--others', '--exclude-standard', '-z',
        ], cwd=root).decode('utf-8').split('\0')
        paths = sorted(set(filter(None, paths)))
    else:
        paths = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts]
    check_paths(paths, public=args.public)
    if args.zip:
        args.zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip, 'w', zipfile.ZIP_DEFLATED) as archive:
            for relative in paths:
                archive.write(root / relative, relative)
    print(f'Release check passed: {count} native modules; {len(paths)} files; no core source.')


if __name__ == '__main__':
    main()
