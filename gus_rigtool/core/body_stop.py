"""
Stop a chain at the body (5.3.3): the Hare's cape rotated forward went into the body. For each control of the chain,
turn it towards the body a degree at a time (the others at rest) until the chain below it would touch the body mesh
(plus a margin); that angle becomes the control's rotation limit on that side - it can't be turned further in.

    from gus_rigtool.core import body_stop
    body_stop.fit("Hare_Body", ["Cape_01_FK_ctrl", "Cape_02_FK_ctrl", ...])
    body_stop.remove([...])

The limits read an attribute on each control (gusBodyStop, the measured angle) plus 'body_stop_extra' (degrees,
on the first control: more room, or less), and switch with 'body_stop' (on / off) on the first control.
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

STEP = 1.0
MAX_ANGLE = 120.0


def _short(n):
    return naming.short_name(n)


def _wpos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)


def _mesh_fn(mesh):
    import maya.api.OpenMaya as om
    shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [mesh])[0]
    sel = om.MSelectionList()
    sel.add(shape)
    return om.MFnMesh(sel.getDagPath(0))


def signed_distance(fn, p):
    """Distance from the body surface, negative inside (by the closest point's normal)."""
    import maya.api.OpenMaya as om
    pt = om.MPoint(p[0], p[1], p[2])
    cp, normal, _face = fn.getClosestPointAndNormal(pt, om.MSpace.kWorld)
    d = pt - cp
    side = d.x * normal.x + d.y * normal.y + d.z * normal.z
    return math.copysign(d.length(), side if abs(side) > 1e-12 else 1.0)


def _xform_point(p, m):
    return [p[0] * m[c] + p[1] * m[4 + c] + p[2] * m[8 + c] + m[12 + c] for c in range(3)]


def tip_local(ctrls, end=None):
    """Where the chain ends, in the last control's own space (so it turns with it): the end node, else one more
    segment past the last control."""
    from gus_rigtool.core import world_turn as WT
    pts = [_wpos(c) for c in ctrls]
    if end:
        tip = _wpos(end)
    elif len(pts) > 1:
        tip = [b + (b - a) for a, b in zip(pts[-2], pts[-1])]
    else:
        tip = pts[-1]
    m = cmds.xform(ctrls[-1], query=True, worldSpace=True, matrix=True)
    return _xform_point(tip, WT._inv(m))


def chain_points(ctrls, k, tip=None):
    """Points of the chain below control k: the controls after it, the half-way points, and the tip (tip: in the
    last control's space, from tip_local)."""
    pts = [_wpos(c) for c in ctrls]
    if tip is None:
        tip = tip_local(ctrls)
    pts.append(_xform_point(tip, cmds.xform(ctrls[-1], query=True, worldSpace=True, matrix=True)))
    out = []
    for i in range(k, len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        out += [[a[j] + (b[j] - a[j]) * t for j in range(3)] for t in (0.5, 1.0)]
    return out


def _free_axes(c):
    out = []
    for ax in "XYZ":
        plug = "%s.rotate%s" % (c, ax)
        try:
            if cmds.getAttr(plug, settable=True):
                out.append(ax)
        except (RuntimeError, ValueError):
            pass
    return out


def measure(ctrls, dist, end=None, margin=0.0, step=STEP, max_angle=MAX_ANGLE):
    """[(control, axis, sign, angle, note)]: for each control the axis / direction that takes the chain into the
    body fastest, and how far it turns before touching (dist(point) -> signed distance to the body)."""
    out = []
    tip = tip_local(ctrls, end)
    for k, c in enumerate(ctrls):
        axes = _free_axes(c)
        if not axes:
            out.append((c, None, 0, None, "rotation locked"))
            continue
        base = [dist(p) for p in chain_points(ctrls, k, tip)]
        if not base:
            out.append((c, None, 0, None, "nothing below it"))
            continue
        start = min(base)
        best = None
        for ax in axes:
            plug = "%s.rotate%s" % (c, ax)
            old = cmds.getAttr(plug)
            for sign in (1, -1):
                cmds.setAttr(plug, old + sign * 5.0)
                closer = start - min(dist(p) for p in chain_points(ctrls, k, tip))
                cmds.setAttr(plug, old)
                if best is None or closer > best[0]:
                    best = (closer, ax, sign)
        if not best or best[0] <= 1e-9:
            out.append((c, None, 0, None, "turning it doesn't bring the chain closer to the body"))
            continue
        _closer, ax, sign = best
        plug = "%s.rotate%s" % (c, ax)
        old = cmds.getAttr(plug)
        if start <= margin:
            out.append((c, ax, sign, 0.0, "already touching at rest"))
            continue
        angle, last_ok = 0.0, 0.0
        try:
            while angle < max_angle:
                angle += step
                cmds.setAttr(plug, old + sign * angle)
                if min(dist(p) for p in chain_points(ctrls, k, tip)) <= margin:
                    break
                last_ok = angle
            else:
                last_ok = None                                   # never touches within max_angle
        finally:
            cmds.setAttr(plug, old)
        out.append((c, ax, sign, last_ok, "" if last_ok is not None else "never touches (no limit)"))
    return out


def _settings(first):
    for attr, default, lo, hi in (("body_stop", 1.0, 0.0, 1.0), ("body_stop_extra", 0.0, -90.0, 90.0)):
        if not cmds.attributeQuery(attr, node=first, exists=True):
            if attr == "body_stop":
                cmds.addAttr(first, longName=attr, attributeType="bool", defaultValue=True, keyable=True)
            else:
                cmds.addAttr(first, longName=attr, attributeType="double", defaultValue=default, minValue=lo,
                             maxValue=hi, keyable=True)
    return first + ".body_stop", first + ".body_stop_extra"


def apply(rows, first):
    """Rotation limits from measure()'s rows. Returns lines."""
    on, extra = _settings(first)
    lines = []
    for c, ax, sign, angle, note in rows:
        if ax is None or angle is None:
            lines.append("%s: %s" % (_short(c), note))
            continue
        if not cmds.attributeQuery("gusBodyStop", node=c, exists=True):
            cmds.addAttr(c, longName="gusBodyStop", attributeType="double")
        rest = cmds.getAttr("%s.rotate%s" % (c, ax))
        cmds.setAttr(c + ".gusBodyStop", rest + sign * angle)
        adl = cmds.createNode("addDoubleLinear", name="%s_bodyStop_adl" % _short(c), skipSelect=True)
        cmds.connectAttr(c + ".gusBodyStop", adl + ".input1")
        if sign > 0:
            cmds.connectAttr(extra, adl + ".input2")
            limit, enable = "maxRot%sLimit" % ax, "maxRot%sLimitEnable" % ax
        else:
            md = cmds.createNode("multDoubleLinear", name="%s_bodyStop_neg_mdl" % _short(c), skipSelect=True)
            cmds.connectAttr(extra, md + ".input1")
            cmds.setAttr(md + ".input2", -1.0)
            cmds.connectAttr(md + ".output", adl + ".input2")
            limit, enable = "minRot%sLimit" % ax, "minRot%sLimitEnable" % ax
        cmds.connectAttr(adl + ".output", "%s.%s" % (c, limit), force=True)
        cmds.connectAttr(on, "%s.%s" % (c, enable), force=True)
        lines.append("%s: rotate%s %s%.0f degrees towards the body%s" % (
            _short(c), ax, "+" if sign > 0 else "-", angle, (" (%s)" % note) if note else ""))
    return lines


def remove(ctrls):
    """Takes the body stop off these controls (limits off, its nodes deleted)."""
    n = 0
    with utils.undo_chunk("gusrigBodyStopRemove"):
        for c in ctrls:
            for node in (cmds.listConnections(c + ".gusBodyStop", source=False, destination=True) or []
                         if cmds.attributeQuery("gusBodyStop", node=c, exists=True) else []):
                if cmds.nodeType(node) == "addDoubleLinear":
                    for m in cmds.listConnections(node + ".input2", source=True, destination=False) or []:
                        if cmds.nodeType(m) == "multDoubleLinear" and "_bodyStop_" in m:
                            cmds.delete(m)
                    cmds.delete(node)
                    n += 1
            for ax in "XYZ":
                for side in ("min", "max"):
                    plug = "%s.%sRot%sLimitEnable" % (c, side, ax)
                    src = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
                    if src and src[0].split(".")[-1] == "body_stop":
                        cmds.disconnectAttr(src[0], plug)
                        cmds.setAttr(plug, False)
            if cmds.attributeQuery("gusBodyStop", node=c, exists=True):
                cmds.deleteAttr(c + ".gusBodyStop")
    return n


def chain_controls(first):
    """The control and the controls nested under it (an FK chain), top first."""
    from gus_rigtool.tools import checker
    out = [first]
    for d in sorted(cmds.listRelatives(first, allDescendents=True, type="transform", fullPath=True) or [],
                    key=lambda x: x.count("|")):
        if checker.is_control(d) and d not in out:
            out.append(d)
    return out


def fit(body, ctrls, margin=None, end=None):
    """Measure and set the limits (one undo; any limits made before on these controls are replaced). Returns
    lines."""
    fn = _mesh_fn(body)
    if margin is None:
        bb = cmds.exactWorldBoundingBox(body)
        margin = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) * 0.005
    dist = lambda p: signed_distance(fn, p)
    with utils.undo_chunk("gusrigBodyStop"):
        remove(ctrls)
        rows = measure(ctrls, dist, end=end, margin=margin)
        return apply(rows, ctrls[0])
