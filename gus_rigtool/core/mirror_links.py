"""
Mirror what links a control to the rig onto its twin (4.1.0): custom attribute values, follows, space switches,
constraints and pivots. Twins by name (L_ <-> R_ and your side pairs); a target with no twin (a centre node,
like the jaw or the head) is used as it is.

Each function returns a list of (twin, what was done) and a list of (node, why skipped).
"""

import maya.cmds as cmds

from gus_rigtool.core import naming
from gus_rigtool.core import nodes as _nodes

KINDS = ("attrs", "follows", "spaces", "constraints", "pivots")


_long = _nodes.unique_long


def twin(node):
    """The other-side node by name, or None (centre / no match)."""
    from gus_rigtool.core import joint_labels
    other = joint_labels.twin_name(naming.short_name(node))
    return _long(other) if other else None


def twin_or_same(node):
    """The twin, or the node itself when it has no side (a centre target)."""
    t = twin(node)
    if t:
        return t
    from gus_rigtool.core import joint_labels
    return None if joint_labels.twin_name(naming.short_name(node)) else _long(node)


# ---------------------------------------------------------------------------
# attribute values
# ---------------------------------------------------------------------------

_NUM = ("double", "float", "long", "short", "bool", "enum", "doubleLinear", "doubleAngle", "byte")


def attrs(nodes):
    """Custom (user) keyable / channel-box values copied to the twin, same values."""
    done, skipped = [], []
    for n in nodes:
        t = twin(n)
        if not t:
            skipped.append((n, "no twin"))
            continue
        copied = []
        for a in cmds.listAttr(n, userDefined=True) or []:
            plug, dst = "%s.%s" % (n, a), "%s.%s" % (t, a)
            try:
                if cmds.getAttr(plug, type=True) not in _NUM or not cmds.attributeQuery(a, node=t, exists=True):
                    continue
                if not (cmds.getAttr(plug, keyable=True) or cmds.getAttr(plug, channelBox=True)):
                    continue
                if not cmds.getAttr(dst, settable=True):
                    continue
                cmds.setAttr(dst, cmds.getAttr(plug))
                copied.append(a)
            except (RuntimeError, ValueError):
                continue
        done.append((t, "%d value(s)" % len(copied)))
    return done, skipped


# ---------------------------------------------------------------------------
# follows
# ---------------------------------------------------------------------------

def follows(nodes, replace=False):
    """The same follow on the twin: twin driver (or the same centre driver), same channels / weight / curve,
    the pivot mirrored, same axes rule."""
    from gus_rigtool.core import follow, mirror_engine
    done, skipped = [], []
    for n in nodes:
        g = follow.follow_group_of(_long(n) or n)
        m = follow._meta(g) if g else None
        if not m:
            skipped.append((n, "doesn't follow anything"))
            continue
        t = twin(n)
        if not t:
            skipped.append((n, "no twin"))
            continue
        driver, src = twin_or_same(m["driver"]), twin_or_same(m["source"])
        if not driver or not src:
            skipped.append((n, "its driver %s has a side but no twin" % m["driver"]))
            continue
        if follow.follow_group_of(t):
            if not replace:
                skipped.append((n, "%s already follows (tick Replace)" % naming.short_name(t)))
                continue
            follow.remove([t])
        spec = follow.settings_of(n)
        pivot = spec["pivot"]
        if pivot not in ("driver", "control"):
            pivot = mirror_engine.reflect_point(pivot, 0)
        spec.update(driver=driver, source=src, pivot=pivot)
        follow._add_with(spec, t)
        done.append((t, "follows %s" % naming.short_name(driver)))
    return done, skipped


# ---------------------------------------------------------------------------
# space switches
# ---------------------------------------------------------------------------

def spaces(nodes, replace=False):
    from gus_rigtool.core import spaces as SP
    done, skipped = [], []
    for n in nodes:
        data = SP.read(_long(n) or n)
        if not data:
            skipped.append((n, "no space switch"))
            continue
        t = twin(n)
        if not t:
            skipped.append((n, "no twin"))
            continue
        targets = []
        for label, node in data["targets"]:
            tt = twin_or_same(node)
            if not tt:
                break
            targets.append((label, tt))
        if len(targets) != len(data["targets"]):
            skipped.append((n, "a target has a side but no twin"))
            continue
        if SP.read(t):
            if not replace:
                skipped.append((n, "%s already has a switch (tick Replace)" % naming.short_name(t)))
                continue
            SP.remove(t)
        try:
            current = cmds.getAttr("%s.%s" % (n, data["attr"]))
        except (RuntimeError, ValueError):
            current = 0
        SP.make(t, targets, data.get("kind", "parent"), data["attr"], current)
        done.append((t, "%d space(s)" % len(targets)))
    return done, skipped


# ---------------------------------------------------------------------------
# constraints
# ---------------------------------------------------------------------------

CONSTRAINTS = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint")


def _constraints_on(node):
    out = []
    for c in cmds.listRelatives(node, children=True, fullPath=True) or []:
        if cmds.nodeType(c) in CONSTRAINTS:
            out.append(c)
    return out


def constraints(nodes, replace=False):
    """Constraints that drive the node (children constraint nodes) made again on the twin, from the twin targets
    (or the same centre targets), keeping the twin where it is (maintain offset). Space switch constraints are
    left to 'spaces'."""
    from gus_rigtool.core import spaces as SP
    done, skipped = [], []
    for n in nodes:
        n = _long(n) or n
        cons = _constraints_on(n)
        data = SP.read(n)
        if data:
            cons = [c for c in cons if naming.short_name(c) != data.get("constraint")]
        if not cons:
            skipped.append((n, "no constraints on it"))
            continue
        t = twin(n)
        if not t:
            skipped.append((n, "no twin"))
            continue
        made = []
        for con in cons:
            kind = cmds.nodeType(con)
            fn = getattr(cmds, kind)
            targets = fn(con, query=True, targetList=True) or []
            twins_ = [twin_or_same(x) for x in targets]
            if not targets or not all(twins_):
                skipped.append((n, "%s: a target has a side but no twin" % kind))
                continue
            existing = [c for c in _constraints_on(t) if cmds.nodeType(c) == kind]
            if existing:
                if not replace:
                    skipped.append((n, "%s already has a %s (tick Replace)" % (naming.short_name(t), kind)))
                    continue
                cmds.delete(existing)
            weights = [cmds.getAttr(con + "." + a) for a in fn(con, query=True, weightAliasList=True) or []]
            flags = {}
            if kind == "aimConstraint":
                for k in ("aimVector", "upVector", "worldUpType", "worldUpVector"):
                    try:
                        flags[k] = fn(con, query=True, **{k: True})
                    except (RuntimeError, TypeError):
                        pass
                flags = {k: v for k, v in flags.items() if v is not None}
            new = fn(twins_, t, maintainOffset=True, **flags)[0]
            for alias, w in zip(fn(new, query=True, weightAliasList=True) or [], weights):
                cmds.setAttr(new + "." + alias, w)
            try:
                cmds.setAttr(new + ".interpType", cmds.getAttr(con + ".interpType"))
            except (RuntimeError, ValueError):
                pass
            made.append(kind)
        if made:
            done.append((t, ", ".join(made)))
    return done, skipped


# ---------------------------------------------------------------------------
# pivots
# ---------------------------------------------------------------------------

def pivots(nodes, orient=False):
    from gus_rigtool.core import pivots as PV
    done, skipped = [], []
    for o, t in PV.mirror_pivots(nodes, 0, orient):
        if t:
            done.append((t, "pivot"))
        else:
            skipped.append((o, "no twin"))
    return done, skipped


def run(nodes, kinds, replace=False, orient=False):
    """Every kind asked for; returns {kind: (done, skipped)}. (Paths found again before each kind: follows and
    spaces add groups above the controls.)"""
    from gus_rigtool.core import utils
    ids = [utils.uuid(n) for n in nodes if cmds.objExists(n)]
    out = {}
    for k in kinds:
        nodes = [p for p in (utils.path(i) for i in ids) if p]
        if k == "attrs":
            out[k] = attrs(nodes)
        elif k == "follows":
            out[k] = follows(nodes, replace)
        elif k == "spaces":
            out[k] = spaces(nodes, replace)
        elif k == "constraints":
            out[k] = constraints(nodes, replace)
        elif k == "pivots":
            out[k] = pivots(nodes, orient)
    return out
