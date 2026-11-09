"""
Overlap / follow-through: a chain (tail, ears, antenna, hair) swings behind what it hangs on, springs and settles -
baked to rotation keys you can edit.

    Select the chain's controls base -> tip (or only the first one: the controls under it are found).
    Overlap: over the frame range, each control's rotation gets the lag; more towards the tip.

How: each control's child (the next control; the last one: a point past its end) is followed by a spring
(stiffness, damping) instead of moving rigidly; the control turns to point at the spring. One undo.
Cycle: the spring runs over the cycle once first, so the result loops without a jump.
"""

import math

import maya.cmds as cmds

from gus_animtool import anim as A

DEFAULTS = {"overlap_stiffness": 0.3, "overlap_damping": 0.35, "overlap_amount": 1.0, "overlap_tip": 0.5,
            "overlap_cycle": 0}


def opt(key):
    v = A.opt(key, DEFAULTS[key])
    return type(DEFAULTS[key])(v)


# ---------------------------------------------------------------------------
# small vector maths
# ---------------------------------------------------------------------------

def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-9 else [0.0, 0.0, 0.0]


def arc(a, b):
    """(axis, angle) turning direction a onto direction b."""
    a, b = _unit(a), _unit(b)
    axis = _cross(a, b)
    s, c = _len(axis), max(-1.0, min(1.0, _dot(a, b)))
    if s < 1e-9:
        return [1.0, 0.0, 0.0], 0.0
    return _mul(axis, 1.0 / s), math.atan2(s, c)


def rotate(v, axis, angle):
    """Rodrigues: v turned by angle around a unit axis."""
    c, s = math.cos(angle), math.sin(angle)
    return _add(_add(_mul(v, c), _mul(_cross(axis, v), s)), _mul(axis, _dot(axis, v) * (1 - c)))


def _apply(m, p):
    """Point p in the space of world matrix m (Maya rows)."""
    return [p[0] * m[0] + p[1] * m[4] + p[2] * m[8] + m[12],
            p[0] * m[1] + p[1] * m[5] + p[2] * m[9] + m[13],
            p[0] * m[2] + p[1] * m[6] + p[2] * m[10] + m[14]]


def _local(m, p):
    """World point p into the space of m (rows orthogonal, any scale)."""
    d = _sub(p, m[12:15])
    out = []
    for r in range(3):
        row = m[r * 4:r * 4 + 3]
        n = _dot(row, row) or 1.0
        out.append(_dot(d, row) / n)
    return out


# ---------------------------------------------------------------------------
# chain
# ---------------------------------------------------------------------------

def chain(nodes):
    """The chain base -> tip: the selected controls; one selected -> it and the controls under it (one path)."""
    if len(nodes) > 1:
        return list(nodes)
    root = nodes[0]
    out = [root]
    below = [d for d in (cmds.listRelatives(root, allDescendents=True, type="transform", fullPath=True) or [])
             if A.is_control(d)]
    below.sort(key=lambda d: d.count("|"))
    for d in below:
        if d.startswith(out[-1] + "|"):
            out.append(d)
    return out


def _tip_offset(nodes, m_last):
    """Where the spring of the last control points: past its end, as far as the segment before it."""
    last = A.position(m_last)
    if len(nodes) > 1:
        prev = A.position(A.world(nodes[-2]))
        seg = _sub(last, prev)
    else:
        seg = _mul(_unit(m_last[0:3]), 10.0)
    if _len(seg) < 1e-6:
        seg = _mul(_unit(m_last[0:3]), 10.0)
    return _local(m_last, _add(last, seg))


# ---------------------------------------------------------------------------
# simulate and bake
# ---------------------------------------------------------------------------

def springs(goals, stiffness, damping, cycle=False):
    """goals: [frame][segment] world points; returns the spring points, same shape.
    cycle: the last frame is the loop frame (= the first): the spring runs round the loop until it repeats, and
    the loop frame gets the first frame's result - no jump when it loops."""
    n = len(goals[0]) if goals else 0
    frames = goals[:-1] if cycle and len(goals) > 2 else goals
    p = [list(g) for g in frames[0]]
    v = [[0.0, 0.0, 0.0] for _ in range(n)]
    out = []
    for _pass in range(4 if cycle else 1):
        out = []
        for g in frames:
            row = []
            for i in range(n):
                acc = _sub(_mul(_sub(g[i], p[i]), stiffness[i]), _mul(v[i], damping))
                v[i] = _add(v[i], acc)
                p[i] = _add(p[i], v[i])
                row.append(list(p[i]))
            out.append(row)
    if frames is not goals:
        out.append([list(x) for x in out[0]])
    return out


def overlap(nodes=None, start=None, end=None, stiffness=None, damping=None, amount=None, tip=None, cycle=None):
    """Bake the overlap on the chain over start-end. Returns how many controls."""
    nodes = chain(nodes or A._pose_sel())
    nodes = [n for n in nodes if all(A._settable(n + "." + a) for a in A._R)]
    if not nodes:
        raise RuntimeError("select the chain's controls (base to tip) - their rotation must be free.")
    if start is None:
        start, end = A.frame_range()
    if end - start < 2:
        raise RuntimeError("set a frame range of a few frames at least.")
    k = opt("overlap_stiffness") if stiffness is None else float(stiffness)
    d = opt("overlap_damping") if damping is None else float(damping)
    amt = opt("overlap_amount") if amount is None else float(amount)
    tip = opt("overlap_tip") if tip is None else float(tip)
    cycle = bool(opt("overlap_cycle")) if cycle is None else bool(cycle)
    n = len(nodes)
    stiff = [max(0.02, min(1.0, k * (1.0 - tip * (i / float(max(1, n)))))) for i in range(n)]
    frames = list(range(int(start), int(end) + 1))
    now = cmds.currentTime(query=True)
    bases, goals = [], []
    cmds.refresh(suspend=True)
    try:
        cmds.currentTime(frames[0], update=True)
        offset = _tip_offset(nodes, A.world(nodes[-1]))
        for f in frames:                                   # the motion as it is
            cmds.currentTime(f, update=True)
            ms = [A.world(x) for x in nodes]
            pos = [A.position(m) for m in ms]
            bases.append(pos)
            goals.append(pos[1:] + [_apply(ms[-1], offset)])
        sim = springs(goals, stiff, d, cycle)
        with A.Undo("gusAnimtoolOverlap"):
            for fi, f in enumerate(frames):
                cmds.currentTime(f, update=True)
                for i, node in enumerate(nodes):
                    axis, angle = arc(_sub(goals[fi][i], bases[fi][i]), _sub(sim[fi][i], bases[fi][i]))
                    angle *= amt
                    if abs(angle) < 1e-7:
                        cmds.setKeyframe(node, attribute=A._R, time=f)
                        continue
                    m = A.world(node)                       # now: with the turns of the controls above
                    new = list(m)
                    for r in range(3):
                        new[r * 4:r * 4 + 3] = rotate(m[r * 4:r * 4 + 3], axis, angle)
                    A.set_world(node, new, translate=False)
                    cmds.setKeyframe(node, attribute=A._R, time=f)
            curves = [c for c in A.time_curves(nodes) if A.is_rotation(c)]
            if curves:
                try:
                    cmds.filterCurve(curves, filter="euler")
                except RuntimeError:
                    pass
    finally:
        cmds.refresh(suspend=False)
        cmds.currentTime(now, update=True)
    A.message("overlap on %d control(s), frames %g-%g%s." % (n, start, end, " (loops)" if cycle else ""))
    return n
