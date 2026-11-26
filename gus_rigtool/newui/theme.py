"""5.8.0: the new look's theme lives in the Animtool (anim/gus_animtool/look/theme.py) - one copy for both tools.
Gus_Rigtool uses its own copy of the Animtool's, so this name is the very same module."""
import sys

from gus_rigtool.core.safe_start import look

sys.modules[__name__] = look("theme")
