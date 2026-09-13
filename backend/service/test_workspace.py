import os
import shutil
from pathlib import Path

from config.settings import MEDIA_ROOT


def reset_test_workspace(result_dir):
    """Remove generated test outputs/intermediates while preserving inputs.

    The bundled test dataset keeps its SMAP rasters, local soil-moisture
    rasters, Excel coordinates, boundary, and shared model outside the
    generated cycle directories.  Removing the cycle cache and public
    products makes ``Run test again`` a genuine end-to-end rerun.
    """
    base_dir = Path(result_dir)
    if not base_dir.is_absolute():
        base_dir = Path(MEDIA_ROOT) / base_dir
    base_dir = base_dir.resolve()
    expected = (Path(MEDIA_ROOT) / 'images' / '82').resolve()
    if base_dir.parent != expected or base_dir.is_symlink():
        raise ValueError('Refusing to reset a workspace outside the test area.')
    if not base_dir.exists() or not base_dir.is_dir():
        return

    def remove_tree(path):
        def onerror(func, target, exc_info):
            # Generated rasters may be read-only after being copied between
            # machines.  Clear the DOS read-only bit and retry the operation.
            os.chmod(target, 0o666)
            func(target)
        shutil.rmtree(path, onerror=onerror)

    for name in (
        'soil_moisture_result', 'soil_moisture_png',
        # Preprocessed copies are generated inputs for the fusion stages and
        # must also be rebuilt for a true end-to-end test rerun.  The original
        # offline files live under images/82/offline and are preserved.
        'org_smap', 'org_sentinel1', 'org_sentinel2',
    ):
        target = base_dir / name
        if target.exists():
            remove_tree(target)

    for name in ('.stage1.complete', '.stage2.complete', '.fusion.complete'):
        marker = base_dir / name
        if marker.exists():
            marker.unlink()

    process_dir = base_dir / 'process'
    if process_dir.exists() and process_dir.is_dir():
        # Keep the supplied pre-trained model; all cycle folders and other
        # generated process artifacts are rebuilt from scratch.
        for child in process_dir.iterdir():
            if child.name == 'shared_ml_model_rf.pkl' and child.is_file():
                continue
            if child.is_dir():
                remove_tree(child)
            else:
                try:
                    child.unlink()
                except PermissionError:
                    os.chmod(child, 0o666)
                    child.unlink()

