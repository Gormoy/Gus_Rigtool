"""
Safe start for Gus_Rigtool's windows (5.7.11) - the same code as the Animtool's (anim/gus_animtool/safestart.py),
loaded from Gus_Rigtool's own copy of the Animtool, so it works however gus_animtool is installed.

    from gus_rigtool.core import safe_start
    op = safe_start.Opening("rigtool", "Gus_Rigtool")
"""

import importlib.util
import os
import sys

_NAME = "gus_rigtool._safestart"


def _load(filename="safestart.py", name=_NAME):
    """One of the Animtool's stand-alone files (they import nothing from it), from Gus_Rigtool's own copy."""
    if name in sys.modules:
        return sys.modules[name]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "anim", "gus_animtool",
                        filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[name] = mod
    return mod


_S = _load()
versions = _load("versions.py", "gus_rigtool._versions")      # 5.7.12: keep / check / go back
Opening = _S.Opening
died_last_time = _S.died_last_time
forget = _S.forget
last_log = _S.last_log
log_path = _S.log_path
note_path = _S.note_path
folder = _S.folder
NAMES = _S.NAMES
restore_call = _S.restore_call
all_logs = _S.all_logs
