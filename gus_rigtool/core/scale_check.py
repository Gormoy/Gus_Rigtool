"""
Scale check (5.6.0): scale the whole rig (its globalScale, x2), see what doesn't grow with it, put it back.

    from gus_rigtool.core import scale_check
    r = scale_check.run()      # {'control': ..., 'plug': ..., 'off': [(node, kind, text)], 'meshes': [...]}

Kinds:
  'stays'    doesn't scale - stays where it was (a follicle / ribbon left outside the scaled groups...)
  'size'     goes to the right place but keeps its size (a joint held by a parent constraint: the skin around it
             doesn't grow - the mesh loses its form there)
  'shape'    ends up somewhere else (stretches instead of growing: a stretchy limb / spline that measures its
             length without the global scale)
  'twice'    a skinned mesh that scales twice (under a scaled group and inheriting it)
  'mesh'     a skinned mesh that doesn't scale / changes shape

The static checks below (follicles(), joints(), meshes_twice(), rest_lengths()) find the usual causes without
scaling anything - Repair uses them.
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming
from gus_rigtool.core import world_turn as WT

FACTOR = 2.0
LEGACY = "legacy_grp"


def _short(n):
    return naming.short_name(n)


def _legacy(n):
    return ("|%s|" % LEGACY) in n + "|"


def scale_control():
    """(control, plug): the control that scales the rig and its scale plug (globalScale, else its scaleX)."""
    from gus_rigtool.core import on_top, world_levels
    got = world_levels.levels().get("global")
    if got:
        return got, got + ".globalScale"
    ctrls = on_top.controls()
    with_gs = [c for c in ctrls if cmds.attributeQuery("globalScale", node=c, exists=True)]
    if with_gs:
        c = sorted(with_gs, key=lambda x: x.count("|"))[0]
        return c, c + ".globalScale"
    w = WT.world_control(ctrls)
    if not w:
        return None, None
    try:
        if cmds.getAttr(w + ".scaleX", settable=True):
            return w, w + ".scaleX"
    except (RuntimeError, ValueError):
        pass
    return w, None


def _connected(plug):
    try:
        return bool(cmds.listConnections(plug, source=True, destination=False))
    except (RuntimeError, ValueError):
        return False


def _src(plug):
    try:
        got = cmds.listConnections(plug, source=True, destination=False, plugs=True, skipConversionNodes=True)
    except (RuntimeError, ValueError, TypeError):
        return None
    return got[0] if got else None


def plug_scales(plug, ctrl, depth=0):
    """5.6.3: does this scale input really grow with the rig? The global scale, a node computing from it, a scale
    constraint to something that scales, another node's scale that does - yes. A control's own scale channel that
    nothing drives (the Hare's follicles read World_ctrl.scaleX, which stays 1 under Global_ctrl) - no."""
    if depth > 8 or not plug:
        return False
    node, attr = plug.split(".", 1)
    long_node = (cmds.ls(node, long=True) or [node])[0]
    ctrl_long = (cmds.ls(ctrl, long=True) or [ctrl])[0] if ctrl else None
    if attr.split("[")[0] in ("globalScale",) or long_node == ctrl_long:
        return True
    try:
        kind = cmds.nodeType(node)
    except RuntimeError:
        return False
    if kind == "scaleConstraint":
        targets = cmds.scaleConstraint(node, query=True, targetList=True) or []
        return any(scaled_by_rig(cmds.ls(t, long=True)[0], ctrl) for t in targets if cmds.ls(t))
    if kind in ("multiplyDivide", "multDoubleLinear", "plusMinusAverage", "blendColors", "unitConversion",
                "addDoubleLinear", "condition", "clamp", "remapValue", "setRange", "floatMath", "decomposeMatrix"):
        ins = cmds.listConnections(node, source=True, destination=False, plugs=True, skipConversionNodes=True) or []
        return any(plug_scales(p, ctrl, depth + 1) for p in ins)
    if attr.split("[")[0] in ("scale", "scaleX", "scaleY", "scaleZ", "sx", "sy", "sz"):
        if cmds.objectType(node, isAType="transform"):
            inner = _src("%s.%s" % (node, attr)) or _src(node + ".scale")
            return plug_scales(inner, ctrl, depth + 1) if inner else False
    return True                                        # something else (an expression...): don't second-guess it


def _scale_in(n, ctrl):
    """The node's own scale is driven by something that grows with the rig."""
    for plug in (n + ".scaleX", n + ".scale"):
        s = _src(plug)
        if s:
            return plug_scales(s, ctrl)
    return False


def _cancels(child, parent):
    """5.6.3: Segment Scale Compensate only cancels the parent joint's scale when the child's inverseScale is
    really connected to it (re-parented joints - the Hare's tongue - have the setting but not the connection)."""
    if not (_ssc(child) and cmds.nodeType(parent) == "joint"):
        return False
    s = cmds.listConnections(child + ".inverseScale", source=True, destination=False) or []
    return bool(s) and (cmds.ls(s[0], long=True) or [s[0]])[0] == parent


def scaled_by_rig(node, ctrl):
    """True when node grows with the rig: the scale control (or something whose scale really grows with it) above
    it, every group in between passing it on (a group with inheritsTransform off stops it)."""
    n = node
    ctrl = (cmds.ls(ctrl, long=True) or [ctrl])[0] if ctrl else None
    own_cancelled = False                          # 5.6.2: Segment Scale Compensate on the joint below
    while n:
        if n == ctrl:
            return True
        if not own_cancelled and _scale_in(n, ctrl):
            return True
        try:
            if not cmds.getAttr(n + ".inheritsTransform"):
                return False
        except (RuntimeError, ValueError):
            return False
        par = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
        # a joint with Segment Scale Compensate cancels its parent joint's OWN scale (what's above it still passes)
        own_cancelled = bool(par) and _cancels(n, par)
        n = par
    return False


def _ssc(n):
    try:
        return cmds.nodeType(n) == "joint" and bool(cmds.getAttr(n + ".segmentScaleCompensate"))
    except (RuntimeError, ValueError):
        return False


# ---- the usual causes (static) --------------------------------------------------------------------------------

def follicles(ctrl=None):
    """Follicles with controls / joints under them that don't scale with the rig."""
    ctrl = ctrl or scale_control()[0]
    out = []
    for shape in cmds.ls(type="follicle", long=True) or []:
        t = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if not t or _legacy(t) or t in out:
            continue
        if not cmds.listRelatives(t, children=True, type="transform"):
            continue
        if not scaled_by_rig(t, ctrl):
            out.append(t)
    return out


def _skin_joints():
    out = set()
    for sk in cmds.ls(type="skinCluster") or []:
        for j in cmds.skinCluster(sk, query=True, influence=True) or []:
            out.update(cmds.ls(j, long=True) or [])
    return out


def _driver(j):
    """The first target of the parent / point / orient constraint that moves joint j, or None."""
    for kind in ("parentConstraint", "pointConstraint"):
        for con in set(cmds.listConnections(j + ".translateX", source=True, destination=False, type=kind) or []):
            got = cmds.listConnections(con + ".target[0].targetParentMatrix", source=True, destination=False) or []
            if got:
                return (cmds.ls(got[0], long=True) or got)[0]
    return None


def joints(ctrl=None):
    """[(joint, driver)]: skin joints moved by a constraint from a control that scales, not scaling themselves."""
    ctrl = ctrl or scale_control()[0]
    out = []
    fols = follicles(ctrl)
    for j in sorted(_skin_joints()):
        if _legacy(j) or scaled_by_rig(j, ctrl):
            continue
        d = _driver(j)
        if d and (scaled_by_rig(d, ctrl) or any(d == f or d.startswith(f + "|") for f in fols)):
            out.append((j, d))
    return out


def meshes_twice(ctrl=None):
    """Skinned meshes that inherit the rig's scale (skin + parent = twice)."""
    from gus_rigtool.core import organize
    ctrl = ctrl or scale_control()[0]
    out = []
    for shape in cmds.ls(type="mesh", long=True, noIntermediate=True) or []:
        t = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if not t or t in out or not organize._skinned(t):
            continue
        if scaled_by_rig(t, ctrl):
            out.append(t)
    return out


def rest_lengths(plug=None):
    """Stretch rest lengths (multDoubleLinear '...rest...' with input2 left at 1) not multiplied by the scale."""
    plug = plug or scale_control()[1]
    out = []
    for n in cmds.ls(type="multDoubleLinear") or []:
        if "rest" not in _short(n).lower():
            continue
        if _connected(n + ".input2") or abs(cmds.getAttr(n + ".input2") - 1.0) > 1e-9:
            continue
        out.append(n)
    return out if plug else []


def fix_follicles(nodes, plug):
    n = 0
    for t in nodes:
        for a in ("scaleX", "scaleY", "scaleZ"):
            p = "%s.%s" % (t, a)
            if cmds.getAttr(p, lock=True):
                cmds.setAttr(p, lock=False)
            cmds.connectAttr(plug, p, force=True)       # 5.6.3: also replaces an input that doesn't scale
        n += 1
    return n


def fix_joints(pairs, plug):
    """5.6.1: each joint's scale reads the global scale (top joints first; a joint under one that now scales is
    left alone). No scale constraint: one from a mirrored (-1 scaled) control turned the Hare's joints inside out.
    Only joints at scale 1 with free scale channels."""
    n = 0
    ctrl = plug.split(".")[0]
    for j, _d in sorted(pairs, key=lambda p: p[0].count("|")):
        if not cmds.objExists(j) or scaled_by_rig(j, ctrl):
            continue
        if any(_connected("%s.scale%s" % (j, a)) for a in "XYZ"):
            continue
        give_scale(j, plug)
        n += 1
    return n


def give_scale(node, plug):
    """5.6.3: node's scale = its own scale x the global scale (a multiplyDivide) - nothing changes at 1, a -1
    mirrored or 9.9 sized node keeps it."""
    md = cmds.createNode("multiplyDivide", name=_short(node).split(":")[-1] + "_globalScale_md", skipSelect=True)
    for a in "XYZ":
        p = "%s.scale%s" % (node, a)
        cmds.setAttr("%s.input1%s" % (md, a), cmds.getAttr(p))
        cmds.connectAttr(plug, "%s.input2%s" % (md, a))
        if cmds.getAttr(p, lock=True):
            cmds.setAttr(p, lock=False)
        cmds.connectAttr("%s.output%s" % (md, a), p, force=True)
    return md


# ---- 5.6.3: the Hare's other cases ----------------------------------------------------------------------------

def _has(node, kinds):
    return bool(cmds.listRelatives(node, allDescendents=True, type=kinds) or [])


def _cut_off(n):
    up = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
    while up:
        try:
            if not cmds.getAttr(up + ".inheritsTransform"):
                return True
        except (RuntimeError, ValueError):
            return False
        up = (cmds.listRelatives(up, parent=True, fullPath=True) or [None])[0]
    return False


def control_groups(ctrl=None):
    """Groups of controls cut off from the scale by a group that doesn't pass it on (the Hare's 13 ribbon
    *_ctrls_grp in DO_NOT_TOUCH): plain groups with controls under them, no follicles / surfaces / meshes,
    not scaled - the top one of each."""
    from gus_rigtool.core import on_top
    ctrl = ctrl or scale_control()[0]
    out = []
    for c in on_top.controls():
        if _legacy(c) or scaled_by_rig(c, ctrl):
            continue
        p, top = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0], None
        while p and _cut_off(p) and cmds.getAttr(p + ".inheritsTransform"):
            if not cmds.listRelatives(p, shapes=True) and not _has(p, ["follicle", "nurbsSurface", "mesh"]):
                top = p
            p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
        if top and top not in out and not any(top.startswith(o + "|") for o in out):
            out = [o for o in out if not o.startswith(top + "|")] + [top]
    return out


def world_measures(plug=None):
    """[(kind, node)]: distances measured in world units without the scale - an IK stretch's rest length ('rest'),
    a pin's length ('pin'), the soft IK distance ('soft'). At x2 the limb thinks it's pulled twice as far."""
    plug = plug or scale_control()[1]
    out = [("rest", n) for n in rest_lengths(plug)]
    for n in [x for x in cmds.ls(type="multiplyDivide") or [] if "PinLocal" in x]:
        if not _connected(n + ".input2X") and abs(cmds.getAttr(n + ".input2X") - 1.0) < 1e-9:
            out.append(("pin", n))
    for n in [x for x in cmds.ls(type="distanceBetween") or [] if "softDist" in x]:
        dsts = cmds.listConnections(n + ".distance", source=False, destination=True) or []
        if dsts and not any("Scaled" in d or "globalScale" in d for d in dsts):
            out.append(("soft", n))
    return out


def fix_world_measures(items, plug):
    for kind, n in items:
        if kind == "rest":
            cmds.connectAttr(plug, n + ".input2", force=True)
        elif kind == "pin":
            cmds.connectAttr(plug, n + ".input2X", force=True)
        elif kind == "soft":                           # distance / global scale, before everything that reads it
            dsts = cmds.listConnections(n + ".distance", source=False, destination=True, plugs=True) or []
            md = cmds.createNode("multiplyDivide", name=_short(n) + "_Scaled_globalScale", skipSelect=True)
            cmds.setAttr(md + ".operation", 2)
            cmds.connectAttr(n + ".distance", md + ".input1X")
            cmds.connectAttr(plug, md + ".input2X")
            for d in dsts:
                cmds.connectAttr(md + ".outputX", d, force=True)
    return len(items)


def target_scales():
    """5.6.4: [(plug, right)]: a constraint's target scale input fed by another node than its target (5.6.3's
    Global > World > Local pointed World_ctrl's at Global_ctrl.scale: at x2 the IK hands in 'root' space and the
    head / neck following the world went off - the global scale counted twice). right: the target's own scale."""
    out = []
    kinds = ["parentConstraint", "scaleConstraint", "pointConstraint", "orientConstraint", "aimConstraint"]
    for con in cmds.ls(type=kinds) or []:
        if not cmds.attributeQuery("targetScale", node=con, exists=True):
            continue
        for i in cmds.getAttr(con + ".target", multiIndices=True) or []:
            plug = "%s.target[%d].targetScale" % (con, i)
            src = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
            tgt = cmds.listConnections("%s.target[%d].targetParentMatrix" % (con, i), source=True,
                                       destination=False) or []
            if src and tgt and _short(src[0].split(".")[0]) != _short(tgt[0]):
                out.append((plug, tgt[0] + ".scale"))
    return out


def fix_target_scales(items):
    for plug, right in items:
        cmds.connectAttr(right, plug, force=True)
    return len(items)


def limb_groups(ctrl=None):
    """5.6.4: [(group, target)]: groups that follow a control with a parent constraint but don't get its scale (the
    Hare's L/R_femur_limb_grp follow Waist_ctrl: the legs stretched at x2 instead of growing). Plain groups only - no
    shapes, no meshes under them (a skinned mesh would scale twice), not scaled already."""
    ctrl = ctrl or scale_control()[0]
    out = []
    for con in set(cmds.ls(type="parentConstraint") or []):
        g = (cmds.listConnections(con + ".constraintTranslateX", source=False, destination=True) or
             cmds.listConnections(con + ".constraintTranslate", source=False, destination=True) or [None])[0]
        if not g:
            continue
        g = (cmds.ls(g, long=True) or [g])[0]
        if g in [x for x, _t in out] or _legacy(g) or cmds.nodeType(g) != "transform":
            continue
        if cmds.listRelatives(g, shapes=True) or _has(g, ["mesh"]) or _connected(g + ".scaleX") or \
                cmds.listConnections(g, source=True, destination=False, type="scaleConstraint"):
            continue
        if scaled_by_rig(g, ctrl):
            continue
        targets = cmds.parentConstraint(con, query=True, targetList=True) or []
        t = cmds.ls(targets[0], long=True) if targets else []
        if t and scaled_by_rig(t[0], ctrl):
            out.append((g, t[0]))
    return out


def fix_limb_groups(pairs):
    for g, t in pairs:
        cmds.scaleConstraint(t, g, maintainOffset=True)
    return len(pairs)


def scaled_twice(ctrl=None):
    """Joints that get the global scale AND inherit it from the joint above (the Hare's tongue: x4, x8 ... x64)."""
    ctrl = ctrl or scale_control()[0]
    out = []
    for j in cmds.ls(type="joint", long=True) or []:
        if _legacy(j) or not _scale_in(j, ctrl):
            continue
        par = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
        if par and not _cancels(j, par) and scaled_by_rig(par, ctrl):
            out.append(j)
    return out


def fix_twice(nodes):
    """Their own scale back (the multiplyDivide's first input, else 1), the connection off."""
    for j in nodes:
        for a in "XYZ":
            p = "%s.scale%s" % (j, a)
            src = _src(p)
            own = 1.0
            if src and cmds.nodeType(src.split(".")[0]) == "multiplyDivide" and src.endswith("output" + a):
                own = cmds.getAttr("%s.input1%s" % (src.split(".")[0], a))
            for s in cmds.listConnections(p, source=True, destination=False, plugs=True) or []:
                cmds.disconnectAttr(s, p)
            cmds.setAttr(p, own)
    return len(nodes)


def _ik_joints():
    out = set()
    for h in cmds.ls(type="ikHandle") or []:
        start = (cmds.listConnections(h + ".startJoint") or [None])[0]
        eff = (cmds.listConnections(h + ".endEffector") or [None])[0]
        end = (cmds.listConnections(eff + ".translateX", source=True, destination=False) or [None])[0] if eff else None
        if not start or not end:
            continue
        j = cmds.ls(end, long=True)[0]
        s = cmds.ls(start, long=True)[0]
        while j:
            out.add(j)
            if j == s:
                break
            j = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
    return out


def measure_joints(factor=FACTOR):
    """5.6.4: (stuck, twice), measured - skin and IK joints scaled x factor with the rig:
    stuck: keep their size and have no scale input (they need the global scale);
    twice: have a scale input and grow more than the rig (x4, x8... - the input should go). Top ones of a chain only
    (fixing them changes the ones below; the next pass measures again)."""
    ctrl, plug = scale_control()
    if not plug:
        return [], []
    joints_ = [j for j in (_skin_joints() | _ik_joints()) if cmds.nodeType(j) == "joint" and not _legacy(j)]
    before = {}
    for j in joints_:
        before[j] = max(_sizes(WT._wm(j)))
    plugs = [plug] if not plug.endswith(".scaleX") else [plug[:-1] + a for a in "XYZ"]
    olds = [cmds.getAttr(p) for p in plugs]
    undo = cmds.undoInfo(query=True, state=True)
    stuck, twice = [], []
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        for p, v in zip(plugs, olds):
            cmds.setAttr(p, v * factor)
        WT._settle()
        for j in joints_:
            if before[j] <= 1e-9:
                continue
            r = max(_sizes(WT._wm(j))) / before[j]
            fed = _connected(j + ".scaleX")
            if abs(r - 1.0) < 0.02 and not fed:
                stuck.append(j)
            elif r > factor * 1.05 and fed:
                twice.append(j)
    finally:
        for p, v in zip(plugs, olds):
            cmds.setAttr(p, v)
        WT._settle()
        cmds.undoInfo(stateWithoutFlush=undo)
    twice = [j for j in twice if not any(j.startswith(o + "|") for o in twice)]
    return sorted(stuck, key=lambda x: x.count("|")), sorted(twice, key=lambda x: x.count("|"))


def stuck_joints(factor=FACTOR):
    """Measured: skin and IK joints that keep their size when the rig scales x factor and have no scale input."""
    return measure_joints(factor)[0]


def twice_joints(factor=FACTOR):
    """5.6.4, measured: joints with a scale input that grow more than the rig (replaces the static scaled_twice in
    Make the rig scale and Repair - it disagreed with what really happens)."""
    return measure_joints(factor)[1]


def fix_meshes(nodes):
    for t in nodes:
        cmds.setAttr(t + ".inheritsTransform", 0)
    return len(nodes)


def fix_rest_lengths(nodes, plug):
    for n in nodes:
        cmds.connectAttr(plug, n + ".input2", force=True)
    return len(nodes)


def _score(factor=FACTOR):
    """How many controls / joints / skinned meshes don't scale evenly at x factor (the scale check)."""
    r = run(factor)
    return len(r["off"]) + len(r["meshes"])


def make_scalable():
    """5.6.4: everything that keeps the rig from scaling evenly, fixed in one go - and the scale check decides:
    measured before and after (x2); if more things are off after, or anything moved at scale 1, it's all undone.
    Fixes: constraint target scales, follicles, control groups, limb groups, IK lengths, joint chains, then measured
    passes (joints that keep their size get the scale; joints that grow twice lose it). One undo.
    Returns {'targets', 'follicles', 'groups', 'limbs', 'rest', 'joints', 'twice', 'before', 'after', 'undone'}."""
    from gus_rigtool.core import repair, utils
    ctrl, plug = scale_control()
    if not ctrl or not plug:
        raise RuntimeError("no global scale: make Global > World > Local first.")
    rest0 = repair.rest_points()
    out = {"targets": 0, "follicles": 0, "groups": 0, "limbs": 0, "joints": 0, "rest": 0, "twice": 0,
           "before": _score(), "after": None, "undone": None,
           "why": None}
    with utils.undo_chunk("gusrigMakeScalable"):
        out["targets"] = fix_target_scales(target_scales())
        out["follicles"] = fix_follicles(follicles(ctrl), plug)
        for g in control_groups(ctrl):            # 5.6.3: ribbon control groups cut off by a no-inherit group
            give_scale(g, plug)
            out["groups"] += 1
        out["limbs"] = fix_limb_groups(limb_groups(ctrl))
        out["rest"] = fix_world_measures(world_measures(plug), plug)
        for _i in range(10):                      # chains: each pass reaches the joints below the ones just fixed
            n = fix_joints(joints(ctrl), plug)
            out["joints"] += n
            if not n:
                break
        for _i in range(6):                       # measured: what still keeps its size, what grows twice
            stuck, twice = measure_joints()
            for j in stuck:
                give_scale(j, plug)
            out["joints"] += len(stuck)
            out["twice"] += fix_twice(twice)
            if not stuck and not twice:
                break
    bad = repair.moved(rest0, repair.rest_points()) if rest0 else []
    why = None
    if bad:
        why = "; ".join("%s: %d vertices, up to %.3g" % (_short(g), n, d) for g, n, d in bad[:3])
        out["why"] = "it would have changed the rig at rest"
    else:
        out["after"] = _score()
        if out["after"] > out["before"]:
            why = "%d off before, %d after" % (out["before"], out["after"])
            out["why"] = "the scale check x2 got worse"
    if why:
        try:
            if "gusrigMakeScalable" in (cmds.undoInfo(query=True, undoName=True) or ""):
                cmds.undo()
        except RuntimeError:
            pass
        out["undone"] = why
    return out


# ---- the test ----------------------------------------------------------------------------------------------------

def _sizes(m):
    return [math.sqrt(sum(m[r * 4 + i] ** 2 for i in range(3))) for r in range(3)]


def _diag(node):
    try:
        bb = cmds.exactWorldBoundingBox(node)
    except (RuntimeError, ValueError):
        return 0.0
    return math.sqrt(sum((bb[3 + i] - bb[i]) ** 2 for i in range(3)))


def _deformed_shape(t):
    """5.6.8: the shape the skin writes (not an Orig / unused shape under the same transform)."""
    shapes = [x for x in cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or []
              if not cmds.getAttr(x + ".intermediateObject")]
    for x in shapes:
        if cmds.ls(cmds.listHistory(x, pruneDagObjects=True) or [], type="skinCluster"):
            return x
    return shapes[0] if shapes else None


def _points(shape):
    """World positions of the shape's vertices (OpenMaya), or None."""
    try:
        import maya.api.OpenMaya as om
        sel = om.MSelectionList()
        sel.add(shape)
        return [(p.x, p.y, p.z) for p in om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)]
    except Exception:
        return None


def _mesh_error(p0, p1, d, factor):
    """(how far the vertices are from where the scale takes them - the worst, as a share of the mesh's size;
    the size ratio). p0 / p1: points before / after; d: what the scale control did."""
    lo = [min(p[i] for p in p0) for i in range(3)]
    hi = [max(p[i] for p in p0) for i in range(3)]
    size = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3))) or 1.0
    worst = 0.0
    for a, b in zip(p0, p1):
        want = [a[0] * d[0] + a[1] * d[4] + a[2] * d[8] + d[12], a[0] * d[1] + a[1] * d[5] + a[2] * d[9] + d[13],
                a[0] * d[2] + a[1] * d[6] + a[2] * d[10] + d[14]]
        worst = max(worst, math.sqrt(sum((b[i] - want[i]) ** 2 for i in range(3))))
    lo1 = [min(p[i] for p in p1) for i in range(3)]
    hi1 = [max(p[i] for p in p1) for i in range(3)]
    ratio = math.sqrt(sum((hi1[i] - lo1[i]) ** 2 for i in range(3))) / size
    return worst / (size * factor), ratio


def run(factor=FACTOR, nodes=None):
    """Scale the rig by factor, compare, put it back (nothing kept, nothing on the undo list)."""
    from gus_rigtool.core import on_top, organize
    ctrl, plug = scale_control()
    result = {"control": ctrl, "plug": plug, "off": [], "meshes": [], "checked": 0}
    if not plug:
        return result
    if nodes is None:
        nodes = on_top.controls() + (cmds.ls(type="joint", long=True) or [])
    nodes = [n for n in dict.fromkeys(nodes) if n != ctrl and not _legacy(n)]
    meshes = []
    for shape in cmds.ls(type="mesh", long=True, noIntermediate=True) or []:
        t = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if t and t not in meshes and organize._skinned(t):
            meshes.append(t)
    WT._settle()
    before = {}
    for n in nodes:
        try:
            before[n] = WT._wm(n)
        except (RuntimeError, ValueError):
            pass
    sizes0 = dict((m, _diag(m)) for m in meshes)
    shapes = dict((m, _deformed_shape(m)) for m in meshes)                  # 5.6.8: the vertices, not the box
    points0 = dict((m, _points(shapes[m])) if shapes[m] else (m, None) for m in meshes)
    c0 = WT._wm(ctrl)
    plugs = [plug] if not plug.endswith(".scaleX") else [plug[:-1] + a for a in "XYZ"]
    olds = [cmds.getAttr(p) for p in plugs]
    undo = cmds.undoInfo(query=True, state=True)
    ys = [m[13] for m in before.values()]
    height = max(1.0, (max(ys) - min(ys)) if ys else 1.0)
    tol = height * 0.002 * factor
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        for p, v in zip(plugs, olds):
            cmds.setAttr(p, v * factor)
        WT._settle()
        d = WT._mul(WT._inv(c0), WT._wm(ctrl))           # what the scale control did
        for n, m0 in before.items():
            try:
                m1 = WT._wm(n)
            except (RuntimeError, ValueError):
                continue
            want = WT._mul(m0, d)
            off = math.sqrt(sum((m1[12 + i] - want[12 + i]) ** 2 for i in range(3)))
            still = math.sqrt(sum((m1[12 + i] - m0[12 + i]) ** 2 for i in range(3)))
            s0, s1 = _sizes(m0), _sizes(m1)
            grew = max(s1[i] / s0[i] for i in range(3) if s0[i] > 1e-9) if any(s0) else factor
            if off <= tol:
                if abs(grew - factor) > 0.02 * factor and abs(grew - 1.0) < 0.02:
                    result["off"].append((n, "size", "goes to the right place but keeps its size"))
                continue
            if still <= tol and abs(grew - 1.0) < 0.02:
                result["off"].append((n, "stays", "doesn't scale (stays where it was)"))
            else:
                result["off"].append((n, "shape", "ends up %.2f away from where the scale takes it" % off))
        for m in meshes:
            p0 = points0.get(m)
            p1 = _points(shapes[m]) if p0 else None
            if p0 and p1 and len(p0) == len(p1):
                err, r = _mesh_error(p0, p1, d, factor)
                if abs(r - factor * factor) < 0.05 * factor:
                    result["meshes"].append((m, "twice", "scales twice (x%.2f)" % r))
                elif abs(r - 1.0) < 0.02:
                    result["meshes"].append((m, "mesh", "doesn't scale"))
                elif err > 0.02:
                    result["meshes"].append((m, "mesh", "loses its form: vertices up to %.0f%% of its size off" % (
                        err * 100)))
                continue
            if sizes0[m] <= 1e-9:
                continue
            r = _diag(m) / sizes0[m]
            if abs(r - factor * factor) < 0.05 * factor:
                result["meshes"].append((m, "twice", "scales twice (x%.2f)" % r))
            elif abs(r - 1.0) < 0.02:
                result["meshes"].append((m, "mesh", "doesn't scale"))
            elif abs(r - factor) > 0.03 * factor:
                result["meshes"].append((m, "mesh", "changes size x%.2f instead of x%g" % (r, factor)))
        result["checked"] = len(before)
    finally:
        for p, v in zip(plugs, olds):
            cmds.setAttr(p, v)
        WT._settle()
        cmds.undoInfo(stateWithoutFlush=undo)
    return result


def causes():
    """[(id, label, nodes)]: the usual causes found without scaling (what Repair offers)."""
    ctrl, plug = scale_control()
    if not ctrl or not plug:
        return []
    out = []
    f = follicles(ctrl)
    if f:
        out.append(("follicles", "follicles (ribbons) that don't scale with the rig", f))
    j = joints(ctrl)
    if j:
        out.append(("joints", "skin joints held by a constraint that don't scale", [x for x, _d in j]))
    m = meshes_twice(ctrl)
    if m:
        out.append(("meshes", "skinned meshes that scale twice", m))
    r = rest_lengths(plug)
    if r:
        out.append(("rest", "stretch lengths not multiplied by the scale (they stretch instead of growing)", r))
    return out
