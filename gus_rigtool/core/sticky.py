"""
Stick to skin: controls that ride on a skinned mesh (a mouth control moves with the jaw, the cheeks, the head).

How (3.12.1 - the way the skin itself moves that spot):
  - at Stick, the vertices closest to the control are found and their skin weights read (e.g. jaw 0.6,
    head 0.3, cheek 0.1);
  - the control's new 'stick' group follows those joints with those weights - the same maths as the skin
    (each joint's bind matrix x where the joint is now, summed by weight) - so it moves exactly like that bit of
    skin;
  - joints the stuck control moves itself (directly or through anything) are left out, their share goes to the
    joint above them - so it can never loop;
  - the group is driven in world space and blended (the 'stick' slider) between following its anchor - the nearest
    parent the control doesn't move - (0) and riding with the skin (1);
  - translation only by default (axes as rigged); rotate=True also turns with the skin.
No hidden mesh, no pin, no follicle: a few matrix nodes per control. Unstick puts it back.

    from gus_rigtool.core import sticky
    sticky.stick(["L_lip_corner_ctrl"], "body_geo")
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import nodes as _nodes

META = "gusSticky"
NEAREST = 3                                     # vertices averaged under each control


_short = _nodes.short


_long = _nodes.unique_long


def _skin_of(mesh):
    from gus_rigtool.core.skin_mirror import skin_of
    return skin_of(mesh)


def _influences(skin):
    return utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []


def read(ctrl):
    try:
        if cmds.attributeQuery(META, node=ctrl, exists=True):
            return json.loads(cmds.getAttr(ctrl + "." + META) or "{}") or None
    except (RuntimeError, ValueError):
        pass
    return None


def _write(ctrl, data):
    if not cmds.attributeQuery(META, node=ctrl, exists=True):
        cmds.addAttr(ctrl, longName=META, dataType="string")
    cmds.setAttr(ctrl + "." + META, json.dumps(data), type="string")


# ---------------------------------------------------------------------------
# what the controls move (never follow those)
# ---------------------------------------------------------------------------

def future_of(ctrls):
    """Every node the controls move or feed (long names) - through constraints, ribbons, follicles, skins..."""
    out = set()
    for c in ctrls:
        try:
            got = cmds.listHistory(c, future=True, allFuture=True) or []
        except (RuntimeError, TypeError):
            got = []
        out.update(utils.ls(got, long=True) or [])
        out.update(cmds.listRelatives(c, allDescendents=True, fullPath=True) or [])
    return out


def downstream_joints(ctrls, future=None):
    """Joints moved by these controls or by anything under / driven by them."""
    from gus_rigtool.builder import existing
    out = set()
    for c in ctrls:
        todo = [c] + [k for k in cmds.listRelatives(c, allDescendents=True, type="transform", fullPath=True) or []
                      if cmds.listRelatives(k, shapes=True, type="nurbsCurve")]
        for k in todo:
            out.update(existing.driven_joints(k))
    future = future_of(ctrls) if future is None else future
    out.update(j for j in (utils.ls(list(future), type="joint", long=True) or []))
    return out


def anchor_of(piece, future):
    """The nearest parent of piece that the stuck controls don't move (nor anything above it), or None (world)."""
    chain = []
    p = cmds.listRelatives(piece, parent=True, fullPath=True)
    while p:
        chain.append(p[0])
        p = cmds.listRelatives(p[0], parent=True, fullPath=True)
    moved = [i for i, n in enumerate(chain) if n in future]
    start = (moved[-1] + 1) if moved else 0
    return chain[start] if start < len(chain) else None


# ---------------------------------------------------------------------------
# the skin under a point
# ---------------------------------------------------------------------------

def _points(mesh):
    from gus_rigtool.core import skin_io
    return skin_io.positions(mesh)


def nearest_vertices(mesh, pos, count=NEAREST):
    """[(vertex index, share)] of the count vertices closest to pos (closer = bigger share)."""
    pts = _points(mesh)
    if not pts:
        raise RuntimeError("%s has no points." % _short(mesh))
    d = sorted((sum((a - b) ** 2 for a, b in zip(p, pos)), i) for i, p in enumerate(pts))[:count]
    inv = [(i, 1.0 / (math.sqrt(dd) + 1e-6)) for dd, i in d]
    total = sum(w for _i, w in inv)
    return [(i, w / total) for i, w in inv]


def skin_weights_at(mesh, pos, count=NEAREST):
    """{joint long name: weight} of the skin around pos (the closest vertices, averaged)."""
    skin = _skin_of(mesh)
    if not skin:
        raise RuntimeError("%s has no skin." % _short(mesh))
    comp = "vtx" if cmds.nodeType((cmds.listRelatives(mesh, shapes=True, fullPath=True) or [mesh])[0]) == "mesh" \
        else "cv"
    out = {}
    for i, share in nearest_vertices(mesh, pos, count):
        point = "%s.%s[%d]" % (mesh, comp, i)
        names = cmds.skinPercent(skin, point, query=True, transform=None) or []
        vals = cmds.skinPercent(skin, point, query=True, value=True) or []
        for n, v in zip(names, vals):
            if v > 1e-5:
                j = (cmds.ls(n, long=True) or [n])[0]
                out[j] = out.get(j, 0.0) + v * share
    return out


def _parent_left(j, skipped, keep):
    """The nearest joint above j that isn't skipped (one already used, else any skin joint)."""
    p = cmds.listRelatives(j, parent=True, fullPath=True, type="joint")
    while p:
        if p[0] not in skipped and (p[0] in keep or not keep):
            return p[0]
        p = cmds.listRelatives(p[0], parent=True, fullPath=True, type="joint")
    return None


def follow_weights(weights, skip, influences=None):
    """The weights without the skipped joints: their share goes to the joint above them (one the skin uses);
    normalised. Raises when nothing is left."""
    keep = set(influences or []) - set(skip)
    out = {}
    for j, w in weights.items():
        target = j if j not in skip else _parent_left(j, set(skip), keep)
        if target:
            out[target] = out.get(target, 0.0) + w
    out = {j: w for j, w in out.items() if w > 1e-3}         # crumbs from far vertices aren't worth a node
    total = sum(out.values())
    if total < 1e-6:
        raise RuntimeError("the skin there only follows joints this control moves - nothing left to ride on.")
    return {j: w / total for j, w in out.items()}


def _bind_pre(skin, joint):
    """The skin's bind matrix for this joint (where it was when bound, inverted)."""
    for p in cmds.listConnections(joint + ".worldMatrix[0]", source=False, destination=True, plugs=True) or []:
        if p.split(".")[0] == _short(skin) and ".matrix[" in p:
            index = p[p.rindex("[") + 1:p.rindex("]")]
            return list(cmds.getAttr("%s.bindPreMatrix[%s]" % (skin, index)))
    from gus_rigtool.core import mirror_engine as me
    return me.inverse(list(cmds.getAttr(joint + ".worldMatrix[0]")))


# ---------------------------------------------------------------------------
# stick / unstick
# ---------------------------------------------------------------------------

def stick(ctrls, mesh, amount=1.0, rotate=False, ignore=None):
    """Stick the controls to the skinned mesh. rotate: also turn with the skin (default: translation only).
    ignore: joints they must not follow either. Returns the controls stuck."""
    from gus_rigtool.core import mirror_engine as me
    from gus_rigtool.core import spaces
    ctrls = [_long(c) for c in ctrls if _long(c)]
    mesh = _long(mesh)
    if not ctrls or not mesh:
        raise RuntimeError("select the controls, then the skinned mesh last.")
    skin = _skin_of(mesh)
    if not skin:
        raise RuntimeError("%s has no skin." % _short(mesh))
    already = [c for c in ctrls if read(c)]
    if already:
        raise RuntimeError("already stuck: %s - Unstick first." % ", ".join(_short(c) for c in already))
    infl = _influences(skin)
    ignore = [j for j in (utils.ls(list(ignore or []), long=True) or [])]
    done = []
    for c in ctrls:
        future = future_of([c])
        skip = downstream_joints([c], future) | set(ignore)
        piece = spaces.piece_of(c)
        parent = (cmds.listRelatives(piece, parent=True, fullPath=True) or [None])[0]
        anchor = anchor_of(piece, future)
        world = list(cmds.xform(piece, query=True, worldSpace=True, matrix=True))
        local = cmds.getAttr(piece + ".matrix")
        weights = follow_weights(skin_weights_at(mesh, world[12:15]), skip, infl)
        name = naming.strip_type_suffix(_short(c))
        nodes = []
        # where the skin around it is: sum of weight x (bind matrix x joint now)
        wt = cmds.createNode("wtAddMatrix", name=name + "_stick_skin")
        nodes.append(wt)
        now = [0.0] * 16
        for k, (j, w) in enumerate(sorted(weights.items())):
            pre = _bind_pre(skin, j)
            mm = cmds.createNode("multMatrix", name="%s_stick_%s" % (name, _short(j).split(":")[-1]))
            cmds.setAttr(mm + ".matrixIn[0]", pre, type="matrix")
            cmds.connectAttr(j + ".worldMatrix[0]", mm + ".matrixIn[1]")
            cmds.connectAttr(mm + ".matrixSum", "%s.wtMatrix[%d].matrixIn" % (wt, k))
            cmds.setAttr("%s.wtMatrix[%d].weightIn" % (wt, k), w)
            nodes.append(mm)
            cur = me.mul(pre, list(cmds.getAttr(j + ".worldMatrix[0]")))
            now = [a + w * b for a, b in zip(now, cur)]
        ride = cmds.createNode("multMatrix", name=name + "_stick_ride")     # no jump: as it is right now
        cmds.setAttr(ride + ".matrixIn[0]", me.mul(world, me.inverse(now)), type="matrix")
        cmds.connectAttr(wt + ".matrixSum", ride + ".matrixIn[1]")
        nodes.append(ride)
        follow = cmds.createNode("multMatrix", name=name + "_stick_follow")  # stick 0: rides with the anchor
        rel = world
        if anchor:
            rel = me.mul(world, me.inverse(list(cmds.xform(anchor, query=True, worldSpace=True, matrix=True))))
            cmds.connectAttr(anchor + ".worldMatrix[0]", follow + ".matrixIn[1]")
        cmds.setAttr(follow + ".matrixIn[0]", rel, type="matrix")
        nodes.append(follow)
        bm = cmds.createNode("blendMatrix", name=name + "_stick_blend")
        cmds.connectAttr(follow + ".matrixSum", bm + ".inputMatrix")
        cmds.connectAttr(ride + ".matrixSum", bm + ".target[0].targetMatrix")
        for a, on in (("useTranslate", True), ("useRotate", bool(rotate)), ("useScale", False), ("useShear", False)):
            try:
                cmds.setAttr("%s.target[0].%s" % (bm, a), on)
            except RuntimeError:
                pass
        nodes.append(bm)
        grp = cmds.createNode("transform", name=name + "_stick_grp")
        if parent:
            grp = cmds.parent(grp, parent, relative=True)[0]
        grp = cmds.ls(grp, long=True)[0]
        cmds.setAttr(grp + ".inheritsTransform", 0)                 # driven in world space: never reads parent
        cmds.parent(piece, grp, relative=True)
        c = _long(_short(c)) or c
        if not cmds.attributeQuery("stick", node=c, exists=True):
            cmds.addAttr(c, longName="stick", attributeType="double", minValue=0, maxValue=1, defaultValue=amount,
                         keyable=True)
        cmds.setAttr(c + ".stick", amount)
        cmds.connectAttr(c + ".stick", bm + ".envelope")
        cmds.connectAttr(bm + ".outputMatrix", grp + ".offsetParentMatrix")
        for a in ("translate", "rotate"):
            cmds.setAttr(grp + "." + a, 0, 0, 0)
        piece = cmds.ls(_short(piece), long=True)[0] if cmds.ls(_short(piece)) else piece
        for a, v in (("translate", (0, 0, 0)), ("rotate", (0, 0, 0)), ("scale", (1, 1, 1)), ("shear", (0, 0, 0))):
            try:
                cmds.setAttr(piece + "." + a, *v)
            except RuntimeError:
                pass
        _write(c, {"mesh": _short(mesh), "group": _short(grp), "piece": _short(piece), "local": list(local),
                   "nodes": [_short(n) for n in nodes], "anchor": _short(anchor) if anchor else None,
                   "rotate": bool(rotate), "joints": {_short(j): round(w, 4) for j, w in weights.items()},
                   "ignore": [_short(j) for j in ignore]})
        done.append(c)
    utils.info("Sticky", "%d control(s) ride on %s (stick 0-1 on each; %s)." % (
        len(done), _short(mesh), "turning with the skin" if rotate else "translation only"))
    return done


def follow_joints(ctrl):
    """{joint: weight} a stuck control follows."""
    d = read(ctrl) or {}
    return d.get("joints") or {}


def unstick(ctrl):
    """The control back as before (its offset group under its old parent, where it was at rest)."""
    data = read(ctrl)
    if not data:
        raise RuntimeError("%s isn't stuck." % _short(ctrl))
    ctrl = _long(ctrl)
    grp, piece = _long(data["group"]), _long(data["piece"])
    if grp and piece:
        parent = (cmds.listRelatives(grp, parent=True, fullPath=True) or [None])[0]
        piece = cmds.parent(piece, parent, relative=True)[0] if parent else cmds.parent(piece, world=True,
                                                                                       relative=True)[0]
        piece = cmds.ls(piece, long=True)[0]
        try:
            cmds.xform(piece, matrix=data["local"])
        except RuntimeError:
            pass
    for n in data.get("nodes", []) + [data["group"]]:
        if _long(n):
            cmds.delete(_long(n))
    ctrl = _long(_short(ctrl)) or ctrl
    for a in ("stick", META):
        if cmds.attributeQuery(a, node=ctrl, exists=True):
            cmds.deleteAttr(ctrl + "." + a)
    if data.get("pin"):                                      # stuck with 3.12.0 (a hidden mesh copy and a pin)
        pin = _long(data["pin"])
        if pin:
            try:
                cmds.removeMultiInstance("%s.inputMatrix[%d]" % (pin, data.get("index", 0)), b=True)
            except RuntimeError:
                pass
        still = [c for c in cmds.ls("*." + META, objectsOnly=True, long=True) or []
                 if (read(c) or {}).get("base") == data.get("base")]
        if not still:
            for n in (data["pin"], data.get("base")):
                if n and _long(n):
                    cmds.delete(_long(n))
    return data


def diagnose(ctrl, mesh):
    """A text report for fixing Stick to skin on a real scene: the control's groups, what drives each, the skin
    under it, the joints it moves (never followed) and what's left to follow. Prints it and returns it."""
    lines = []
    c = _long(ctrl)
    m = _long(mesh)
    if not c or not m:
        raise RuntimeError("give an existing control and mesh.")
    lines.append("control: %s   mesh: %s   skin: %s" % (c, m, _skin_of(m)))
    lines.append("groups above (top to bottom):")
    chain = c.split("|")[1:]
    for i in range(len(chain)):
        node = "|" + "|".join(chain[:i + 1])
        drivers = []
        for attr in ("translate", "rotate", "scale", "offsetParentMatrix", "parentInverseMatrix"):
            src = cmds.listConnections(node + "." + attr, source=True, destination=False, plugs=True,
                                       skipConversionNodes=True) or []
            drivers += ["%s <- %s" % (attr, s) for s in src]
        cons = [cmds.nodeType(k) for k in cmds.listRelatives(node, children=True, fullPath=True) or []
                if cmds.nodeType(k).endswith("Constraint")]
        lines.append("  %s%s%s" % (chain[i], ("   [" + "; ".join(drivers) + "]") if drivers else "",
                                   ("   constraints: " + ", ".join(cons)) if cons else ""))
    pos = cmds.xform(c, query=True, worldSpace=True, translation=True)
    try:
        lines.append("skin at the control: %s" % {_short(k): round(v, 3) for k, v in skin_weights_at(m, pos).items()})
    except Exception as e:
        lines.append("skin at the control: (%s)" % e)
    fut = future_of([c])
    moved = downstream_joints([c], fut)
    lines.append("joints this control moves (never followed): %s" % (sorted(_short(j) for j in moved) or "none"))
    try:
        lines.append("it would follow: %s" % {_short(k): round(v, 3) for k, v in
                                               follow_weights(skin_weights_at(m, pos), moved).items()})
    except Exception as e:
        lines.append("it would follow: (%s)" % e)
    lines.append("stuck now: %s" % (read(c) or "no"))
    text = "\n".join(lines)
    print(text)
    return text
