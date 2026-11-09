"""
Speed report (4.5.0): how long the tools you press most take on THIS character, slowest first.

    from gus_rigtool.core import speed
    text = speed.run()                  # the open character (or the test biped in a new scene, if there's none)

Everything that changes the scene is undone straight after it's timed: the scene is left as it was.
Over half a second is listed first as SLOW.
"""

import os
import sys
import time

import maya.cmds as cmds

SLOW = 0.5


def _animtool():
    try:
        import gus_animtool  # noqa: F401
    except ImportError:
        import gus_rigtool
        path = os.path.join(gus_rigtool.ROOT, "anim")
        if path not in sys.path:
            sys.path.append(path)
        import gus_animtool  # noqa: F401
    from gus_animtool import anim
    return anim


class Timer(object):
    def __init__(self):
        self.rows = []                      # (label, seconds or None, note)

    def time(self, label, fn, undo=False, note=""):
        """Time fn(); undo: take what it did off afterwards (one undo step). Returns fn's result."""
        got = None
        cmds.undoInfo(openChunk=True, chunkName="gusSpeed")
        t0 = time.time()
        try:
            got = fn()
            self.rows.append((label, time.time() - t0, note))
        except Exception as e:
            self.rows.append((label, None, "failed: %s" % e))
        finally:
            cmds.undoInfo(closeChunk=True)
        if undo:
            try:
                cmds.undo()
            except Exception:
                pass
        return got

    def skip(self, label, why):
        self.rows.append((label, None, "skipped: " + why))

    def text(self, title, facts):
        timed = sorted([r for r in self.rows if r[1] is not None], key=lambda r: -r[1])
        slow = [r for r in timed if r[1] >= SLOW]
        lines = [title, ""] + ["  " + f for f in facts] + [""]
        lines.append("SLOW (over %.1f s): %s" % (SLOW, "none" if not slow else "%d" % len(slow)))
        for label, sec, note in slow:
            lines.append("  %6.2fs  %s%s" % (sec, label, ("   " + note) if note else ""))
        lines += ["", "EVERYTHING (slowest first)"]
        for label, sec, note in timed:
            lines.append("  %6.2fs  %s%s" % (sec, label, ("   " + note) if note else ""))
        other = [r for r in self.rows if r[1] is None]
        if other:
            lines += ["", "NOT TIMED"]
            lines += ["  %s   %s" % (label, note) for label, _s, note in other]
        return "\n".join(lines)


def _character(A):
    """(namespace, controls) of the character with the most controls, or ('', [])."""
    for cache in ("_auto_cache", "_pairs_cache", "_members_cache", "_position_cache"):
        getattr(A, cache, {}).clear()
    best = ("", [])
    for ns in A.characters() or [""]:
        ctrls = A.character_controls(ns)
        if len(ctrls) > len(best[1]):
            best = (ns, ctrls)
    return best


def run(ask=True, show=True):
    """Time the common tools on the open character; returns the report text (also shown and saved)."""
    A = _animtool()
    ns, ctrls = _character(A)
    if not ctrls:
        if ask and cmds.confirmDialog(
                title="Gus_Rigtool - speed report", button=["Build it", "Cancel"], defaultButton="Build it",
                cancelButton="Cancel", dismissString="Cancel",
                message="No character with controls in this scene.\nTime the test biped instead? It's built in a "
                        "NEW scene (save your work first).") != "Build it":
            return None
        from gus_rigtool.builder import build as bld
        cmds.file(new=True, force=True)
        bld.biped(180.0)
        bld.build_all(180.0)
        ns, ctrls = _character(A)
    t = Timer()
    for cache in ("_auto_cache", "_pairs_cache", "_members_cache", "_position_cache"):
        getattr(A, cache, {}).clear()
    t.time("find the controls (first time)", lambda: A.character_controls(ns))
    t.time("find the controls (again, straight after)", lambda: A.character_controls(ns))
    t.time("'is this a control?' for every control", lambda: [A.is_control(c) for c in ctrls])
    from gus_animtool import pickmodel as PM
    t.time("picker: automatic layout", lambda: PM.auto(ns))
    sel = cmds.ls(selection=True, long=True) or []
    t.time("select every control", lambda: cmds.select(ctrls, replace=True))
    t.time("key every control", lambda: cmds.setKeyframe(ctrls), undo=True)
    pose = t.time("read a pose (every control)", lambda: A.capture_pose(ctrls)) or {}
    if pose:
        t.time("apply a pose (every control)", lambda: A.apply_pose(pose, ns), undo=True)
    current = A.current_character()
    if current == ns:
        t.time("reset all", lambda: A.reset_pose("all"), undo=True)
        cmds.select(ctrls, replace=True)
        t.time("mirror pose L > R (every control)", lambda: A.mirror_pose("L>R"), undo=True)
    else:
        why = "pick '%s' in Gus Animtool's character list first" % (ns or A.ROOT)
        t.skip("reset all", why)
        t.skip("mirror pose L > R", why)
    try:
        from gus_animtool import hider
        parts = [p for p in hider.parts(ns) if p]
    except Exception:
        parts = []
    if parts:
        t.time("isolate a body part (%s), then show all" % parts[0],
               lambda: (hider.isolate(parts[0], ns=ns), hider.show_all(ns=ns)), undo=True)
    from gus_rigtool import scene_check
    from gus_rigtool.core import repair, ribbon, ui
    t.time("Check this scene", scene_check.report)
    t.time("Repair: look through the scene", repair.find)
    t.time("ribbon builds: read them", ribbon._find_builds)
    t.time("Gus_Rigtool main window: open", lambda: ui.open_panel(ui.MAIN_KEY))
    pages = ("build", "skin", "ribbon", "select", "mirror", "checker", "home")
    t.time("switch between %d pages" % len(pages), lambda: [ui.go_to_tool(k) for k in pages],
           note="(all %d together)" % len(pages))
    try:
        cmds.select(sel, replace=True) if sel else cmds.select(clear=True)
    except (RuntimeError, ValueError):
        pass
    import gus_rigtool
    facts = ["Gus_Rigtool %s" % gus_rigtool.__version__,
             "character: %s, %d controls (%s)" % (ns or A.ROOT, len(ctrls), A.found_text(ns)),
             "scene: %d transforms, %d curves, %d skins" % (
                 len(cmds.ls(type="transform") or []), len(cmds.ls(type="nurbsCurve") or []),
                 len(cmds.ls(type="skinCluster") or []))]
    text = t.text("Gus_Rigtool - speed report", facts)
    try:
        path = os.path.join(cmds.internalVar(userTmpDir=True), "gus_speed_report.txt")
        with open(path, "w") as f:
            f.write(text)
        text += "\n\nSaved: %s" % path
    except Exception:
        pass
    print(text)
    if show:
        try:
            ui.report_window("Gus_Rigtool - speed report", text)
        except Exception:
            pass
    return text
