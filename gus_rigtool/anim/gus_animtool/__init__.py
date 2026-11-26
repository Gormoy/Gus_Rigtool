"""
Gus Animtool - animator tools for any rig (and the best with Gus_Rigtool rigs).

    import gus_animtool; gus_animtool.show()

Install / update: drag drag_to_maya_animtool.mel into Maya's viewport, or Update... in its window.

One Animtool (5.6.46): a copy in maya/scripts on a computer that also has Gus_Rigtool runs the Animtool that came
with Gus_Rigtool when that one is newer - so the two can never drift apart, however Gus_Rigtool was updated (its
Update button or drag_to_maya.mel). This copy's defaults.json (your rig's naming) is still the one read
(LOCAL_ROOT). An animator's copy (Deliver / Make animator tools, no Gus_Rigtool) runs as it is.
"""

import os
import re

__version__ = "5.7.12"               # always the same as Gus_Rigtool's (a test checks it)

ROOT = os.path.dirname(os.path.abspath(__file__))
LOCAL_ROOT = ROOT                    # where this copy was installed (its defaults.json)
REDIRECTED = None                    # the Gus_Rigtool copy this one runs instead, when it does


def _version_key(v):
    return [int(x) for x in re.findall(r"\d+", v or "")]


def _bundled():
    """Gus_Rigtool's own Animtool (anim/gus_animtool), if Gus_Rigtool is installed here: (folder, version)."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("gus_rigtool")
    except (ImportError, ValueError):
        return None, None
    if not spec or not spec.origin:
        return None, None
    folder = os.path.join(os.path.dirname(spec.origin), "anim", "gus_animtool")
    init = os.path.join(folder, "__init__.py")
    if not os.path.isfile(init):
        return None, None
    try:
        with open(init) as f:
            m = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
    except (IOError, OSError):
        return None, None
    return folder, (m.group(1) if m else None)


def _redirect():
    """Run Gus_Rigtool's newer Animtool instead of this copy (this module's code comes from there from now on)."""
    global ROOT, REDIRECTED, __version__
    if os.environ.get("GUS_ANIMTOOL_NO_REDIRECT"):
        return False
    folder, version = _bundled()
    if not folder or os.path.normcase(os.path.abspath(folder)) == os.path.normcase(ROOT):
        return False                                      # this IS Gus_Rigtool's copy, or there's none
    if not version or _version_key(version) <= _version_key(__version__):
        return False                                      # ours is as new: keep it
    __path__[:] = [folder]                                # the modules (ui, attach, bar...) come from there
    ROOT = folder
    REDIRECTED = folder
    __version__ = version
    return True


_redirect()


def show(*_):
    from gus_animtool import ui
    return ui.show()
