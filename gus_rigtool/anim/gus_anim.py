"""Old name of Gus Animtool: 'import gus_anim; gus_anim.show()' keeps working (it is the same module)."""
import sys

from gus_animtool import anim as _anim

sys.modules[__name__] = _anim
