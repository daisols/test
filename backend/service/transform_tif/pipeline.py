"""Public entry point for the FieldMoist soil-moisture processing pipeline.

The historical ``transform_tif`` module remains as a compatibility shim.
New integrations should import :func:`run` from this module.
"""

from .transform_tif import run, transform_tif

__all__ = ["run", "transform_tif"]
