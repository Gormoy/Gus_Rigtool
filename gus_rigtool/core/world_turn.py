"""
World turn test (5.1.1): turn the world control, see what doesn't come along exactly - double transforms (a knee
turning twice as fast, the mech's spring IK), nodes left behind (a pole vector outside the world control) - then
put the world back. Nothing is left changed, nothing goes on the undo list.

    from gus_rigtool.core import world_turn as WT
    WT.run()       # {'world': ..., 'axis': 'Y', 'angle': 90, 'off': [(node, turned, moved, what)], 'spring': [...]}
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming

ANGLE = 90.0
WORLD_WORDS = ("world", "main", "global", "master", "god", "root", "all", "move", "placement", "traj")


def _mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _inv(m):
    """Inverse of an affine 4x4 (row vectors, Maya's order)."""
    a = [m[0:3], m[4:7], m[8:11]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
           a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12:
        raise ValueError("singular matrix")
    c = [[(a[(j + 1) % 3][(i + 1) % 3] * a[(j + 2) % 3][(i + 2) % 3] -
           a[(j + 1) % 3][(i + 2) % 3] * a[(j + 2) % 3][(i + 1) % 3]) / det for j in range(3)] for i in range(3)]
    t = m[12:15]
    ti = [-sum(t[k] * c[k][j] for k in range(3)) for j in range(3)]
    return c[0] + [0.0] + c[1] + [0.0] + c[2] + [0.0] + ti + [1.0]


def _rows(m):
    """The 3 axes of a matrix, unit length (scale taken out)."""
    out = []
    for r in range(3):
        v = m[r * 4:r * 4 + 3]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def _angle_between(m1, m2):
    """Degrees between the orientations of two matrices."""
    a, b = _rows(m1), _rows(m2)
    # R = A^T B, angle from its trace
    tr = sum(sum(a[i][k] * b[i][k] for k in range(3)) for i in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def _wm(n):
    return cmds.xform(n, query=True, worldSpace=True, matrix=True)


def world_control(controls):
    """The control everything hangs under (5.3.0: stray curves with nothing under them - the Hare's edgeCurve1 -
    don't count): the one with the most controls under it, names like world / main / root first, then the
    highest."""
    if not controls:
        return None
    under = dict((c, len([x for x in controls if x.startswith(c + "|")])) for c in controls)
    pool = [c for c in controls if under[c]] or list(controls)

    def score(c):
        short = naming.short_name(c).lower()
        word = any(w in short for w in WORLD_WORDS)
        return (-under[c], not word, c.count("|"))
    return sorted(pool, key=score)[0]


def _turnable(node):
    for ax in "YXZ":
        plug = "%s.rotate%s" % (node, ax)
        try:
            if cmds.getAttr(plug, settable=True):
                return ax
        except (RuntimeError, ValueError):
            pass
    return None


def spring_handles():
    """IK handles using the spring solver (they can double a turn when the whole rig turns)."""
    out = []
    for h in cmds.ls(type="ikHandle") or []:
        sol = cmds.listConnections(h + ".ikSolver", source=True, destination=False) or []
        if sol and cmds.nodeType(sol[0]) == "ikSpringSolver":
            out.append(h)
    return out


def _settle():
    """Make Maya finish solving (IK handles, spline IK) before reading positions (5.2.0)."""
    handles = cmds.ls(type="ikHandle") or []
    try:
        if handles:
            cmds.dgeval(handles)
    except (RuntimeError, AttributeError, TypeError):
        pass
    try:
        cmds.refresh(force=True)
    except (RuntimeError, AttributeError, TypeError):
        pass


def run(world=None, nodes=None, angle=ANGLE):
    """Turn the world control by angle, compare every joint / control with where it should be, put it back."""
    from gus_rigtool.tools import checker
    ctrls = [n for n in checker.transforms(None) if checker.is_control(n)]
    world = world or world_control(ctrls)
    result = {"world": world, "axis": None, "angle": angle, "off": [], "spring": spring_handles()}
    if not world:
        return result
    ax = _turnable(world)
    result["axis"] = ax
    if not ax:
        return result
    world = cmds.ls(world, long=True)[0]
    nodes = nodes if nodes is not None else (ctrls + (cmds.ls(type="joint", long=True) or []))
    nodes = [n for n in dict.fromkeys(nodes) if n != world and "|legacy_grp|" not in n + "|"]   # 5.6.0: old joints
    plug = "%s.rotate%s" % (world, ax)
    _settle()
    before = {}
    for n in nodes:
        try:
            before[n] = _wm(n)
        except (RuntimeError, ValueError):
            pass
    w0 = _wm(world)
    old = cmds.getAttr(plug)
    undo = cmds.undoInfo(query=True, state=True)
    height = 1.0
    ys = [m[13] for m in before.values()]
    if ys:
        height = max(1.0, max(ys) - min(ys))
    tol_move = height * 0.002
    try:
        cmds.undoInfo(stateWithoutFlush=False)               # nothing of this on the undo list
        cmds.setAttr(plug, old + angle)
        _settle()
        d = _mul(_inv(w0), _wm(world))                       # what the world did
        for n, m0 in before.items():
            if n == world:
                continue
            try:
                m1 = _wm(n)
            except (RuntimeError, ValueError):
                continue
            want = _mul(m0, d)
            moved = math.sqrt(sum((m1[12 + i] - want[12 + i]) ** 2 for i in range(3)))
            turned = _angle_between(m0, m1)
            wrong = _angle_between(want, m1)
            if wrong > 1.0 or moved > tol_move:
                if turned < 1.0 and moved > tol_move:
                    what = "stays behind (doesn't follow the world)"
                elif turned > angle + 1.0:
                    what = "turns %.0f degrees (the world turned %.0f)" % (turned, angle)
                elif turned < angle - 1.0:
                    what = "turns only %.0f degrees (the world turned %.0f)" % (turned, angle)
                else:
                    what = "ends up %.2f away from where the world takes it" % moved
                result["off"].append((n, turned, moved, what))
    finally:
        cmds.setAttr(plug, old)
        cmds.undoInfo(stateWithoutFlush=undo)
    result["off"].sort(key=lambda r: (-abs(r[1] - angle), -r[2]))
    return result
