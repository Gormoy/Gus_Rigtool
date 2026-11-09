"""
Constraint helpers: make constraints in the usual patterns (many targets to one, one to many, pairs),
with offset and axes options; swap a constraint's targets; remove; report what drives what.
"""

import maya.cmds as cmds

from gus_rigtool.core import nodes as _nodes

TYPES = ["parent", "point", "orient", "scale", "aim", "poleVector"]
MODES = ["targets... > last", "first > each other", "pairs (1>2, 3>4...)"]


def fn(kind):
    return getattr(cmds, kind + "Constraint")


_short = _nodes.short


def plan(selection, mode):
    """[(targets, driven)] from the selection and the mode."""
    if len(selection) < 2:
        raise RuntimeError("select 2 nodes or more.")
    if mode == 0:
        return [(selection[:-1], selection[-1])]
    if mode == 1:
        return [([selection[0]], d) for d in selection[1:]]
    if len(selection) % 2:
        raise RuntimeError("pairs need an even selection (target, driven, target, driven...).")
    return [([selection[i]], selection[i + 1]) for i in range(0, len(selection), 2)]


def make(targets, driven, kind="parent", offset=True, skip_t="", skip_r="", skip_s="", aim=(1, 0, 0),
         up=(0, 1, 0)):
    """One constraint. skip_*: axes left free, e.g. 'y' or 'xz'. Returns the constraint."""
    kw = {}
    if kind != "poleVector":
        kw["maintainOffset"] = bool(offset)
    st, sr, ss = [list(x) for x in (skip_t or "", skip_r or "", skip_s or "")]
    if kind == "parent":
        if st:
            kw["skipTranslate"] = st
        if sr:
            kw["skipRotate"] = sr
    elif kind == "point" and st:
        kw["skip"] = st
    elif kind in ("orient", "aim") and sr:
        kw["skip"] = sr
    elif kind == "scale" and ss:
        kw["skip"] = ss
    if kind == "aim":
        kw["aimVector"] = list(aim)
        kw["upVector"] = list(up)
        kw["worldUpType"] = "vector"
    if kind == "poleVector" and cmds.nodeType(driven) != "ikHandle":
        raise RuntimeError("a pole vector constraint drives an IK handle - %s isn't one." % _short(driven))
    if kind == "parent" and len(st) == 3 and len(sr) == 3:
        raise RuntimeError("every axis is skipped - nothing would be driven.")
    con = fn(kind)(targets, driven, **kw)[0]
    if kind in ("parent", "orient"):
        try:
            cmds.setAttr(con + ".interpType", 2)
        except RuntimeError:
            pass
    return con


def constraints_on(node):
    """The constraints driving node (its constraint children)."""
    out = []
    for c in cmds.listRelatives(node, children=True, type="constraint", fullPath=True) or []:
        if c not in out:
            out.append(c)
    return out


def targets_of(con):
    kind = cmds.nodeType(con).replace("Constraint", "")
    got = []
    try:
        got = fn(kind)(con, query=True, targetList=True) or []
    except (RuntimeError, AttributeError, TypeError):
        got = []
    if not got:                                   # from what feeds its targets (target[i]...)
        pairs = cmds.listConnections(con, source=True, destination=False, plugs=True, connections=True) or []
        for dst, src in zip(pairs[0::2], pairs[1::2]):
            node = src.split(".")[0]
            if dst.split(".", 1)[-1].startswith("target[") and node not in got and \
                    _short(node) != _short(_driven_of(con)) and cmds.nodeType(node) != "unitConversion":
                got.append(node)
    return got


def _driven_of(con):
    return (cmds.listRelatives(con, parent=True, fullPath=True) or [""])[0]


def swap(driven, new_targets, offset=True):
    """Every constraint on driven gets new_targets instead of its targets (same kind and options).
    Returns the constraints changed."""
    done = []
    for con in constraints_on(driven):
        kind = cmds.nodeType(con).replace("Constraint", "")
        old = targets_of(con)
        f = fn(kind)
        kw = {} if kind == "poleVector" else {"maintainOffset": bool(offset)}
        for t in new_targets:
            f(t, driven, **kw)
        for t in old:
            if cmds.ls(t, long=True) and cmds.ls(t, long=True)[0] not in (cmds.ls(new_targets, long=True) or []):
                f(t, driven, edit=True, remove=True)
        done.append(_short(con))
    return done


def remove(nodes):
    n = 0
    for node in nodes:
        for c in constraints_on(node):
            if cmds.objExists(c):
                cmds.delete(c)
                n += 1
    return n


def drives(node):
    """Constraints that use node as a target: [(constraint, driven)]."""
    out = []
    for c in set(cmds.listConnections(node, source=False, destination=True, type="constraint") or []):
        d = _driven_of(c)
        if d and cmds.ls(d, long=True) != cmds.ls(node, long=True):
            out.append((_short(c), _short(d)))
    return sorted(out)


def report(nodes):
    lines = []
    for node in nodes:
        lines.append(_short(node))
        cons = constraints_on(node)
        for c in cons:
            lines.append("    driven by %-20s targets: %s" % (cmds.nodeType(c), ", ".join(_short(t) for t in
                                                                                       targets_of(c)) or "-"))
        for c, d in drives(node):
            lines.append("    drives    %-20s (%s)" % (d, c))
        if not cons and not drives(node):
            lines.append("    (no constraints)")
    return "\n".join(lines)
