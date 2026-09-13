"""Quiet algorithm output in both server threads and spawned Windows workers.

Only the task orchestrator emits short stage messages. Avoid redirecting global
stdout/stderr, which would also swallow messages from unrelated request threads.
"""
import warnings

from rasterio.errors import NotGeoreferencedWarning
from tqdm import tqdm as _tqdm

# Array reprojection supplies its transform explicitly; rasterio's temporary
# in-memory dataset may still issue this warning while opening the array.
warnings.filterwarnings('ignore', category=NotGeoreferencedWarning, module=r'rasterio\.warp')


def quiet_print(*args, **kwargs):
    pass


def quiet_traceback(*args, **kwargs):
    pass


def tqdm(*args, **kwargs):
    kwargs['disable'] = True
    return _tqdm(*args, **kwargs)
