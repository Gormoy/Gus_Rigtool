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


def _load():
    if _NAME in sys.modules:
        return sys.modules[_NAME]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "anim", "gus_animtool",
                        "safestart.py")
    spec = importlib.util.spec_from_file_location(_NAME, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[_NAME] = mod
    return mod


_S = _load()
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
