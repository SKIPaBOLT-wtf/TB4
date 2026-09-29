"""Keep bundled libraries out of native commands launched by the desktop worker."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def prepare_external_programs() -> None:
    if not getattr(sys, 'frozen', False):
        return
    if os.name == 'nt':
        import ctypes
        if not ctypes.windll.kernel32.SetDllDirectoryW(None):
            raise OSError('DLL_SEARCH_RESET_FAILED')
    else:
        original = os.environ.get('LD_LIBRARY_PATH_ORIG')
        if original is None:
            os.environ.pop('LD_LIBRARY_PATH', None)
        else:
            os.environ['LD_LIBRARY_PATH'] = original
    # Remove only bundled entries added by runtime hooks; retain host PATH.
    bundle = Path(sys._MEIPASS).resolve()
    paths = []
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        try:
            Path(entry).resolve().relative_to(bundle)
        except (ValueError, OSError):
            paths.append(entry)
    os.environ['PATH'] = os.pathsep.join(paths)
