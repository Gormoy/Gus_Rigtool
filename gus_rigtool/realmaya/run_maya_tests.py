"""
Real-Maya tests (5.6.35): the tool run inside Maya itself - mayapy, Maya's own Python, no window - on small scenes
each test builds from scratch, then (if you chose one) your Hare scene opened and checked, never saved.

Double-click run_maya_tests.bat (Windows) or run_maya_tests.command (Mac). Or by hand:
    "C:/Program Files/Autodesk/Maya2024/bin/mayapy.exe" run_maya_tests.py [--scene PATH] [--no-scene]

Writes maya_test_results.txt next to this file - send that one. Nothing is saved: no scene file is written.
Your choice of Hare scene is kept in gus_maya_tests.json in your home folder (delete it to choose again).
"""

import json
import os
import platform
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                         # .../gus_rigtool
TOP = os.path.dirname(PKG)                          # the folder that holds gus_rigtool
OUT = os.path.join(HERE, "maya_test_results.txt")
CONFIG = os.path.join(os.path.expanduser("~"), "gus_maya_tests.json")
SCENE_TYPES = (".ma", ".mb")


def _paths():
    for p in (os.path.join(PKG, "anim"), TOP, HERE):
        if p not in sys.path:
            sys.path.insert(0, p)


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(CONFIG, "w") as f:
            json.dump(cfg, f, indent=1)
    except (IOError, OSError):
        pass


def clean_path(text):
    """A path dragged into a terminal: quotes and spaces around it, Mac's backslash-escaped spaces."""
    p = (text or "").strip().strip('"').strip("'").strip()
    if "\\ " in p:
        p = p.replace("\\ ", " ")
    return p


def scene_to_use(argv, ask=input):
    """The Hare scene for the smoke test: --scene PATH, --no-scene, the saved choice, or asked once."""
    cfg = load_config()
    if "--no-scene" in argv:
        return None
    if "--scene" in argv:
        i = argv.index("--scene")
        path = clean_path(argv[i + 1]) if i + 1 < len(argv) else ""
        cfg["scene"] = path
        save_config(cfg)
        return path or None
    if "scene" in cfg:
        return cfg["scene"] or None
    try:
        got = clean_path(ask("Your Hare scene for the last test (drag the .ma / .mb file here and press Enter, "
                             "or just Enter to skip it): "))
    except (EOFError, KeyboardInterrupt):
        got = ""
    if got and not got.lower().endswith(SCENE_TYPES):
        print("  that isn't a .ma / .mb file - skipped (run again with --scene PATH to choose it).")
        got = ""
    cfg["scene"] = got
    save_config(cfg)
    return got or None


def _plugins(cmds):
    for p in ("matrixNodes", "quatNodes", "lookdevKit", "fbxmaya"):
        try:
            if not cmds.pluginInfo(p, query=True, loaded=True):
                cmds.loadPlugin(p, quiet=True)
        except Exception:
            pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    _paths()
    scene = scene_to_use(argv)
    print("Starting Maya (no window) - a minute...")
    t0 = time.time()
    import maya.standalone
    maya.standalone.initialize(name="python")
    text = ""
    try:
        import maya.cmds as cmds
        _plugins(cmds)
        import gus_rigtool
        from gus_rigtool.core.report import Report
        import maya_cases as cases
        rep = Report("Real Maya tests")
        for name, fn in cases.CASES:
            print("  test: " + name)
            if name not in cases.WHOLE_RIG:          # d and f use the biped e built
                cmds.file(new=True, force=True)
            rep.guard(name, fn, rep)
        if scene:
            print("  test: your scene (opened, never saved)")
            rep.guard("your scene", cases.hare, rep, scene)
        extra = ["Tool: %s   from %s" % (gus_rigtool.__version__, PKG),
                 "Your scene: %s" % (scene or "skipped")]
        text = rep.text(header_lines=extra)
        text += "\n" + cases.APPENDIX.get("scene", "")
    except Exception:
        text = "Gus_Rigtool real Maya tests could not run:\n\n" + traceback.format_exc()
    finally:
        try:
            with open(OUT, "w") as f:
                f.write(text)
        except (IOError, OSError):
            pass
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
    print(text)
    print("\nDone in %.0fs. Results saved: %s  (%s) - send that file." % (time.time() - t0, OUT, platform.system()))
    return text


if __name__ == "__main__":
    main()
