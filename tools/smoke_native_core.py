"""Check module loading and Windows multiprocessing without private source."""
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    import numpy as np

    native = ROOT / 'backend/service/transform_tif/_native/win_amd64_cp312'
    manifest = json.loads((native / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['modules']:
        module = importlib.import_module(entry['module'])
        assert Path(module.__file__).resolve() == (native / entry['file']).resolve(), module.__file__
    from service.transform_tif.predeal.lee_filter import process_all, worker
    data = np.random.default_rng(7).uniform(1, 10, (2, 16, 16)).astype('float32')
    for method in ('lee', 'refined'):
        expected = np.asarray([worker(band, method, 3) for band in data])
        actual = process_all(data, method=method, win=3, n_workers=2)
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
    print(f'{len(manifest["modules"])} native imports and Windows worker checks passed.')


if __name__ == '__main__':
    main()
