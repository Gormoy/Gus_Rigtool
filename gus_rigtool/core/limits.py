"""
Transform limits on controls (5.3.5): how far a control can move / turn / scale - Maya's own limits (Attribute Editor
> Limit Information), set on many controls at once, from the pose, and mirrored to the other side.

    from gus_rigtool.core import limits
    limits.set_limit(ctrls, "ty", 0, 32)          # None on a side: no limit there
    limits.from_pose(ctrls, "tz", "max")          # the current value becomes the max
    limits.mirror(ctrls)                          # the same limits on the R twins (flipped where the axis is)
    limits.clear(ctrls, "tz")                     # or every channel
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

CHANNELS = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")
_KIND = {"t": "translation", "r": "rotation", "s": "scale"}
_ATTR = {"t": ("Trans", "translate"), "r": ("Rot", "rotate"), "s": ("Scale", "scale")}


def _plugs(c, channel):
    """(min value, max value, min enable, max enable) plugs."""
    pre, _long = _ATTR[channel[0]]
    ax = channel[1].upper()
    return ("%s.min%s%sLimit" % (c, pre, ax), "%s.max%s%sLimit" % (c, pre, ax),
            "%s.min%s%sLimitEnable" % (c, pre, ax), "%s.max%s%sLimitEnable" % (c, pre, ax))


def get(c, channel):
    """(min or None, max or None) - None where that side isn't limited."""
    lo, hi, elo, ehi = _plugs(c, channel)
    return (cmds.getAttr(lo) if cmds.getAttr(elo) else None, cmds.getAttr(hi) if cmds.getAttr(ehi) else None)


def set_limit(ctrls, channel, lo=None, hi=None):
    """The limits on every control: lo / hi None = no limit on that side (switched off). Given the wrong way
    round (min 0, max -65) they're swapped. Returns how many."""
    channel = channel.lower()
    if channel not in CHANNELS:
        raise ValueError("channel: one of %s" % ", ".join(CHANNELS))
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo                                   # 'min 0 max -65' means -65 .. 0
    n = 0
    with utils.undo_chunk("gusrigLimits"):
        for c in ctrls:
            plo, phi, elo, ehi = _plugs(c, channel)
            if lo is not None:
                cmds.setAttr(plo, lo)
            if hi is not None:
                cmds.setAttr(phi, hi)
            cmds.setAttr(elo, lo is not None)
            cmds.setAttr(ehi, hi is not None)
            n += 1
    return n


def from_pose(ctrls, channel, side):
    """The current value becomes the min or the max (the other side kept). Returns [(control, value)]."""
    channel = channel.lower()
    out = []
    with utils.undo_chunk("gusrigLimitsPose"):
        for c in ctrls:
            v = cmds.getAttr("%s.%s" % (c, channel))
            plo, phi, elo, ehi = _plugs(c, channel)
            cmds.setAttr(plo if side == "min" else phi, v)
            cmds.setAttr(elo if side == "min" else ehi, True)
            out.append((c, v))
    return out


def clear(ctrls, channel=None):
    n = 0
    with utils.undo_chunk("gusrigLimitsClear"):
        for c in ctrls:
            for ch in ([channel.lower()] if channel else CHANNELS):
                _lo, _hi, elo, ehi = _plugs(c, ch)
                if cmds.getAttr(elo) or cmds.getAttr(ehi):
                    cmds.setAttr(elo, False)
                    cmds.setAttr(ehi, False)
                    n += 1
    return n


def limited(c):
    """{channel: (min, max)} for the channels with a limit."""
    out = {}
    for ch in CHANNELS:
        lo, hi = get(c, ch)
        if lo is not None or hi is not None:
            out[ch] = (lo, hi)
    return out


def _axis_world(c, channel):
    """The world direction the channel moves / turns the control (unit), from its parent's matrix."""
    par = cmds.listRelatives(c, parent=True, fullPath=True)
    m = cmds.xform(par[0], query=True, worldSpace=True, matrix=True) if par else \
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    sign = 1.0
    if channel[0] == "r":                                  # a rotation turns about the control's own axes - and in a
        m = cmds.xform(c, query=True, worldSpace=True, matrix=True)       # mirrored (-1 scale) frame the other way
        a, b, d = m[0:3], m[4:7], m[8:11]
        det = (a[0] * (b[1] * d[2] - b[2] * d[1]) - a[1] * (b[0] * d[2] - b[2] * d[0]) +
               a[2] * (b[0] * d[1] - b[1] * d[0]))
        sign = -1.0 if det < 0 else 1.0
    i = "xyz".index(channel[1])
    v = m[i * 4:i * 4 + 3]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [sign * x / n for x in v]


def flips(src, dst, channel, axis="x"):
    """True when the twin's channel goes the other way in the mirror (its limits flip: lo, hi -> -hi, -lo).
    Moves mirror like arrows (the mirror axis flips); turns like axles (the other two flip); scale never flips."""
    if channel[0] == "s":
        return False
    a = _axis_world(src, channel)
    b = _axis_world(dst, channel)
    k = "xyz".index(axis.lower())
    if channel[0] == "t":
        m = [(-x if i == k else x) for i, x in enumerate(a)]
    else:
        m = [(x if i == k else -x) for i, x in enumerate(a)]
    return sum(x * y for x, y in zip(m, b)) < 0


def mirror(ctrls, mode="auto", axis="x"):
    """Every limit of each control on its twin (L_ <-> R_). mode: 'auto' (flipped where the twin's channel goes
    the other way), 'same', 'flip'. Returns [(control, twin, [channels], [flipped channels])] and the ones with no
    twin."""
    from gus_rigtool.core import mirror_setup as MS
    done, alone = [], []
    with utils.undo_chunk("gusrigLimitsMirror"):
        for c in ctrls:
            t = MS.twin(c)
            if not t:
                alone.append(c)
                continue
            t = (cmds.ls(t, long=True) or [t])[0]
            chans, flipped = [], []
            for ch, (lo, hi) in limited(c).items():
                f = flips(c, t, ch, axis) if mode == "auto" else (mode == "flip" and ch[0] != "s")
                if f:
                    lo, hi = (-hi if hi is not None else None), (-lo if lo is not None else None)
                    flipped.append(ch)
                set_limit([t], ch, lo, hi)
                chans.append(ch)
            done.append((c, t, chans, flipped))
    return done, alone


def describe(c):
    lims = limited(c)
    if not lims:
        return "%s: no limits" % naming.short_name(c)
    fmt = lambda v: "-" if v is None else "%g" % v
    return "%s: %s" % (naming.short_name(c), ", ".join("%s %s..%s" % (ch, fmt(lo), fmt(hi))
                                                     for ch, (lo, hi) in sorted(lims.items())))
