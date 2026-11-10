"""
Safe mode (5.6.27): a fix may only be kept when nothing the animators see moved.

Before and after a fix the scene is looked at in a few states - as it is now (rest), the rig scaled x2, and a few
frames of real animation when the scene has keys - and every skinned / deformed mesh vertex and every control's
place is compared. Anything off by more than a hair = the fix is undone and what moved is listed.

    from gus_rigtool.core import safe
    before = safe.snapshot()
    ...fix...
    bad = safe.compare(before, safe.snapshot())      # [(state, node, how many, most)]

Looking never leaves anything behind: no undo steps, the time, the scale and every value go back as they were.
"""

import maya.cmds as cmds

TOL = 1e-3                    # cm - closer than this counts as not moved
STATES = ("rest", "scale", "anim")
ANIM_FRAMES = 3


def _no_undo(fn):
    """Run fn without recording undo steps (looking must not land in the fix's undo)."""
    try:
        was = cmds.undoInfo(query=True, state=True)
    except Exception:
        was = True
    try:
        cmds.undoInfo(stateWithoutFlush=False)
    except Exception:
        pass
    try:
        return fn()
    finally:
        try:
            cmds.undoInfo(stateWithoutFlush=was)
        except Exception:
            pass


def mesh_points():
    """{mesh: flat world points} of every mesh a deformer drives (skin, delta mush, lattice...)."""
    try:
        import maya.api.OpenMaya as om
    except ImportError:
        om = None
    out = {}
    for m in cmds.ls(type="mesh", noIntermediate=True, long=True) or []:
        try:
            if not cmds.listHistory(m, pruneDagObjects=True, interestLevel=1):
                continue
            if om:
                sel = om.MSelectionList()
                sel.add(m)
                pts = om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)
                out[m] = [c for p in pts for c in (p.x, p.y, p.z)]
            else:
                out[m] = list(cmds.xform(m + ".vtx[*]", query=True, worldSpace=True, translation=True) or [])
        except Exception:
            continue
    return out


def control_points():
    """{control: [x, y, z]} - every transform with a curve shape."""
    out = {}
    for s in cmds.ls(type="nurbsCurve", noIntermediate=True, long=True) or []:
        t = (cmds.listRelatives(s, parent=True, fullPath=True) or [None])[0]
        if t and t not in out:
            try:
                out[t] = list(cmds.xform(t, query=True, worldSpace=True, rotatePivot=True))
            except Exception:
                pass
    return out


def _uuid(node):
    try:
        return (cmds.ls(node, uuid=True) or [None])[0]
    except Exception:
        return None


def _by_uuid(found):
    """5.6.28: {uuid: (name, points)} - a node that's reparented or renamed by the fix is still the same node
    (5.6.27 keyed by the full path, so a moved node was silently skipped)."""
    out = {}
    for name, pts in found.items():
        out[_uuid(name) or name] = (name, pts)
    return out


def _look():
    pts = mesh_points()
    try:                                                    # Repair's 5.6.1 net: every skinned mesh
        from gus_rigtool.core import repair
        pts.update(repair.rest_points())
    except Exception:
        pass
    return {"mesh": _by_uuid(pts), "ctrl": _by_uuid(control_points())}


def anim_frames(n=ANIM_FRAMES):
    """A few frames across the keyed range (time keys on anything), [] when nothing is animated."""
    keys = []
    for c in cmds.ls(type=["animCurveTL", "animCurveTA", "animCurveTU"]) or []:
        try:
            if cmds.listConnections(c + ".output", source=False, destination=True):
                got = cmds.keyframe(c, query=True, timeChange=True) or []
                keys.extend(got)
        except Exception:
            pass
    if len(set(keys)) < 2:
        return []
    lo, hi = min(keys), max(keys)
    if n <= 1:
        return [lo]
    return sorted(set(round(lo + (hi - lo) * i / float(n - 1)) for i in range(n)))


def scale_plug():
    try:
        from gus_rigtool.core import scale_check as SC
        _c, plug = SC.scale_control()
        if plug and cmds.getAttr(plug, settable=True):
            return plug
    except Exception:
        pass
    return None


def snapshot(states=STATES, frames=None):
    """{state: look} - the scene seen in each state, everything put back."""
    def go():
        out = {}
        now = cmds.currentTime(query=True)
        if "rest" in states:
            out["rest"] = _look()
        if "scale" in states:
            plug = scale_plug()
            if plug:
                v = cmds.getAttr(plug)
                try:
                    cmds.setAttr(plug, v * 2.0)
                    out["scale"] = _look()
                finally:
                    cmds.setAttr(plug, v)
        if "anim" in states:
            try:
                for f in (frames if frames is not None else anim_frames()):
                    cmds.currentTime(f, update=True)
                    out["frame %g" % f] = _look()
            finally:                                        # 5.6.28: the time goes back even if a look fails
                cmds.currentTime(now, update=True)
        return out
    return _no_undo(go)


def _entry(key, value):
    """(name, points) - looks keyed by UUID hold (name, points); plain {name: points} looks still work."""
    if isinstance(value, tuple) and len(value) == 2:
        return value
    return key, value


def _moved_points(a, b, tol):
    n, most = 0, 0.0
    for i in range(0, len(a) - 2, 3):
        d = ((a[i] - b[i]) ** 2 + (a[i + 1] - b[i + 1]) ** 2 + (a[i + 2] - b[i + 2]) ** 2) ** 0.5
        if d > tol:
            n += 1
            most = max(most, d)
    return n, most


def compare(before, after, tol=TOL, skip=()):
    """[(state, node, how many points moved, most)] - only states seen both times. 5.6.28: a mesh or control that
    is gone, or whose points changed in number, is listed with most = None; skip: (state, key) pairs that aren't
    steady even without a fix (unsteady())."""
    bad = []
    for state, look in before.items():
        other = after.get(state)
        if not other:
            continue
        for kind in ("mesh", "ctrl"):
            if kind not in other:                       # that kind wasn't looked at the second time
                continue
            theirs = other[kind]
            for key, value in look.get(kind, {}).items():
                if (state, key) in skip:
                    continue
                name, a = _entry(key, value)
                if key not in theirs:
                    bad.append((state, name, 0, None))
                    continue
                _n, b = _entry(key, theirs[key])
                if len(b) != len(a):
                    bad.append((state, name, 0, None))
                    continue
                n, most = _moved_points(a, b, tol)
                if n:
                    bad.append((state, name, n, most))
    return bad


def unsteady(first, second, tol=TOL):
    """5.6.28: {(state, key)} that differ between two looks with nothing done in between - jiggle, wave
    expressions, dynamics depend on the frames before, so jumping to a frame can give another answer each time.
    Those aren't held against a fix (5.6.27 could undo a good fix for them)."""
    out = set()
    for state, look in first.items():
        other = second.get(state) or {}
        for kind in ("mesh", "ctrl"):
            theirs = other.get(kind, {})
            for key, value in look.get(kind, {}).items():
                _name, a = _entry(key, value)
                if key not in theirs:
                    continue
                _n, b = _entry(key, theirs[key])
                if len(a) != len(b) or _moved_points(a, b, tol)[0]:
                    out.add((state, key))
    return out


def describe(bad, n=4):
    if not bad:
        return "nothing moved"
    parts = []
    for s, node, k, d in bad[:n]:
        if d is None:
            parts.append("%s %s: gone, or its points changed" % (s, node.split("|")[-1]))
        else:
            parts.append("%s %s: %d point(s) up to %.3g" % (s, node.split("|")[-1], k, d))
    return "; ".join(parts) + (" ..." if len(bad) > n else "")


def before(states=STATES):
    """5.6.28: (frames, look, unsteady) to hold a fix to: the look taken before it, and - when there are frames of
    animation - what isn't steady on them anyway (looked at twice)."""
    frames = anim_frames() if "anim" in states else []
    look = snapshot(states, frames)
    shaky = set()
    if frames:
        shaky = unsteady(look, snapshot(("anim",), frames))
    return frames, look, shaky


def undo_own(label):
    """5.6.28: undo the last step only when it is ours (a fix that failed before changing anything left no step,
    and a plain undo would take back what was done before). True when undone."""
    try:
        if cmds.undoInfo(query=True, state=True) and label in (cmds.undoInfo(query=True, undoName=True) or ""):
            cmds.undo()
            return True
    except RuntimeError:
        pass
    return False


def run(fn, label="gusrigSafe", states=STATES):
    """Run fn as one undo step; undo it when anything moved. Returns (kept, result or what moved)."""
    frames, look, shaky = before(states)
    cmds.undoInfo(openChunk=True, chunkName=label)
    try:
        got = fn()
    except Exception:
        cmds.undoInfo(closeChunk=True)
        undo_own(label)                                 # 5.6.28: only our own step
        raise
    cmds.undoInfo(closeChunk=True)
    bad = compare(look, snapshot(states, frames), skip=shaky)
    if bad:
        if not undo_own(label):
            return False, "it moved, and it couldn't be undone (undo is off?): " + describe(bad)
        return False, "undone - it moved: " + describe(bad)
    return True, got
