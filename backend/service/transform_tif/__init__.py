"""Load the bundled Windows core; never fall back to local algorithm source."""
import platform
import json
from pathlib import Path
import sys

if sys.platform != 'win32' or sys.version_info[:2] != (3, 12) or platform.machine() != 'AMD64':
    raise ImportError('FieldMoist core requires Windows x64 and Python 3.12. See STARTUP.md.')

_package = Path(__file__).resolve().parent
_native = _package / '_native' / 'win_amd64_cp312'
if not (_native / 'manifest.json').is_file():
    raise ImportError('Private FieldMoist core is missing. Run tools/install_core.py as described in STARTUP.md.')
_manifest = json.loads((_native / 'manifest.json').read_text(encoding='utf-8'))
for _entry in _manifest['modules']:
    if not (_native / _entry['file']).is_file():
        raise ImportError(f"Bundled FieldMoist module is missing: {_entry['file']}")
for _group in ('function1', 'function2', 'function3', 'predeal'):
    if not (_native / _group / '__init__.py').is_file():
        raise ImportError(f'Bundled FieldMoist package is missing: {_group}')

# Native packages take precedence, including for multiprocessing workers.
__path__.insert(0, str(_native))
