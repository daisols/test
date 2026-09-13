"""Public entry point for temporal fusion processing.

The implementation is kept in the legacy module until downstream users have
migrated; this stable name avoids exposing versioned filenames in new code.
"""

from .function3.adapter import step3

__all__ = ["step3"]
