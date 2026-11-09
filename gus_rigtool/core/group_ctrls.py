"""
Group controls (5.6.8): one control that moves a set of other controls, each by its own weight - a mouth corner
that moves the lip controls next to it (and a little of the cheek), an upper lip that moves the whole lip. They
add on top of everything already there: the jaw follow, the control's own values, other group controls.

Each driven control gets a layer group right above it (once, shared by every group control):
    <ctrl's parent>
      <ctrl>_groups          translate / rotate = the sum of each group control x its weight, turned into this
                             control's axes (so up is up for every lip control, whatever its own orientation)
        <ctrl>
A joint that copies the control's channels (ribbon 'pivot on the control shape') gets the same layer.

    from gus_rigtool.core import group_ctrls as GC
    GC.make("Upper_Lip_ctrl", {"Mouth_fol_14_ctrl": 1.0, "L_Mouth_fol_10_ctrl": 0.6})
    GC.mouth_plan(GC.ribbon_controls("Mouth"), GC.ribbon_controls("L_Facial_ribbon", "R_Facial_ribbon"))
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import world_turn as WT

TOOL = "Group controls"
META = "gusGroupCtrl"            # on a group control: {driven ctrl: [weight, [nodes]]}
LAYER = "gusGroupLayer"           # on a layer group: the control it carries
MIN_WEIGHT = 0.05


def _short(n):
    return naming.short_name(n)


def _long(n):
    got = cmds.ls(n, long=True) if n else []
    return got[0] if len(got) == 1 else None


def _pos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def read(group_ctrl):
    try:
        if cmds.attributeQuery(META, node=group_ctrl, exists=True):
            return json.loads(cmds.getAttr(group_ctrl + "." + META) or "{}")
    except (RuntimeError, ValueError):
        pass
    return {}


def _write(group_ctrl, data):
    if not cmds.attributeQuery(META, node=group_ctrl, exists=True):
        cmds.addAttr(group_ctrl, longName=META, dataType="string")
    cmds.setAttr(group_ctrl + "." + META, json.dumps(data), type="string")


def all_groups():
    return [n for n in cmds.ls(type="transform", long=True) or [] if cmds.attributeQuery(META, node=n, exists=True)]


# ---- the layer above a driven control ------------------------------------------------------------------------

def _rot3(m):
    """The 3x3 axes of a world matrix, lengths taken out (the sign of a mirror kept)."""
    out = []
    for r in range(3):
        v = m[r * 4:r * 4 + 3]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def _det(a):
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
            a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def _inv3(m):
    d = _det(m) or 1e-12
    return [[(m[(j + 1) % 3][(i + 1) % 3] * m[(j + 2) % 3][(i + 2) % 3] -
              m[(j + 1) % 3][(i + 2) % 3] * m[(j + 2) % 3][(i + 1) % 3]) / d for j in range(3)] for i in range(3)]


def _scale(m):
    return sum(math.sqrt(sum(x * x for x in m[r * 4:r * 4 + 3])) for r in range(3)) / 3.0


def _space_matrix(src_parent, dst_parent, lengths=True):
    """4x4 (row vectors, Maya order) turning a vector in src_parent's axes into dst_parent's axes (lengths: and
    its units - a control under a scaled group moves as far in the world as the group control did). Returns
    (matrix, the mirror sign)."""
    ma = WT._wm(src_parent) if src_parent else [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    mb = WT._wm(dst_parent) if dst_parent else [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    if lengths:
        # 5.6.10 exact: v_world = v_src * A, v_dst = v_world * B^-1 (A, B the full 3x3s - scale, mirror, uneven
        # scale all included): the driven control moves in the world exactly weight x what the group control did
        a = [ma[r * 4:r * 4 + 3] for r in range(3)]
        b = _inv3([mb[r * 4:r * 4 + 3] for r in range(3)])
        m = [[sum(a[i][q] * b[q][j] for q in range(3)) for j in range(3)] for i in range(3)]
        return [m[0][0], m[0][1], m[0][2], 0.0, m[1][0], m[1][1], m[1][2], 0.0, m[2][0], m[2][1], m[2][2], 0.0,
                0.0, 0.0, 0.0, 1.0], _det(_rot3(ma)) * _det(_rot3(mb))
    a, b = _rot3(ma), _rot3(mb)
    # turns: axes only. v_world = v_src * A ; v_dst = v_world * B^T (B orthonormal)
    m = [[sum(a[i][q] * b[j][q] for q in range(3)) for j in range(3)] for i in range(3)]
    return [m[0][0], m[0][1], m[0][2], 0.0, m[1][0], m[1][1], m[1][2], 0.0, m[2][0], m[2][1], m[2][2], 0.0,
            0.0, 0.0, 0.0, 1.0], _det(a) * _det(b)


def layer_of(ctrl):
    p = (cmds.listRelatives(ctrl, parent=True, fullPath=True) or [None])[0]
    if p and cmds.attributeQuery(LAYER, node=p, exists=True):
        return p
    return None


def _sum_of(lay, attr):
    """5.6.9: the plusMinusAverage feeding the layer's translate / rotate - through the unit conversion Maya puts
    between a sum and a rotate (degrees -> radians): 5.6.8 didn't look through it and crashed on the second group
    control reaching a control."""
    got = cmds.listConnections(lay + "." + attr, source=True, destination=False, skipConversionNodes=True) or []
    got = [g for g in got if cmds.nodeType(g) == "plusMinusAverage"]
    return got[0] if got else None


def _add_layer(node, carries):
    """The layer group right above node (made once): at node's parent's origin and axes, turning / scaling round
    node's place. Returns (layer, translate pma, rotate pma)."""
    from gus_rigtool.core import spaces
    lay = layer_of(node)
    if lay:
        pmas = _heal(lay)                       # 5.6.20: a layer that lost its sum nodes gets new ones
        if all(pmas):
            return lay, pmas[0], pmas[1]
        raise RuntimeError("%s's layer %s is driven by something else - remove the group controls and make them "
                           "again." % (_short(node), _short(lay)))
    parent = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    name = _short(node) + "_groups"
    lay = cmds.createNode("transform", name=name, parent=parent, skipSelect=True) if parent else \
        cmds.createNode("transform", name=name, skipSelect=True)
    lay = cmds.ls(lay, long=True)[0]
    cmds.addAttr(lay, longName=LAYER, dataType="string")
    cmds.setAttr(lay + "." + LAYER, _short(carries), type="string")
    here = cmds.getAttr(node + ".translate")[0]
    for a in ("rotatePivot", "scalePivot"):
        cmds.setAttr(lay + "." + a, *here, type="double3")
    spaces._parent_keeping(node, lay)
    pt = cmds.createNode("plusMinusAverage", name=name + "_t", skipSelect=True)
    pr = cmds.createNode("plusMinusAverage", name=name + "_r", skipSelect=True)
    cmds.connectAttr(pt + ".output3D", lay + ".translate")
    cmds.connectAttr(pr + ".output3D", lay + ".rotate")
    return lay, pt, pr


def _heal(lay):
    """The layer's translate / rotate sums - a missing one made again (5.6.19 could leave a layer without them: a
    save taken back with Maya's undo inside the button's own undo step). Returns [translate pma, rotate pma];
    None for one driven by something else (left alone)."""
    out = []
    for a, tag in (("translate", "_t"), ("rotate", "_r")):
        pma = _sum_of(lay, a)
        if not pma:
            if cmds.listConnections(lay + "." + a, source=True, destination=False):
                out.append(None)
                continue
            pma = cmds.createNode("plusMinusAverage", name=_short(lay) + tag, skipSelect=True)
            cmds.connectAttr(pma + ".output3D", lay + "." + a, force=True)
        out.append(pma)
    return out


def repair_layers():
    """Every layer: missing sums made again, layers nothing feeds any more gone (their control back under its old
    parent). Returns {'healed': [layers], 'dropped': n}."""
    healed = []
    for lay in cmds.ls("*." + LAYER, objectsOnly=True, long=True) or []:
        if not all(_sum_of(lay, a) for a in ("translate", "rotate")):
            _heal(lay)
            healed.append(_short(lay))
    before = len(cmds.ls("*." + LAYER, objectsOnly=True) or [])
    _drop_empty_layers()
    return {"healed": healed, "dropped": before - len(cmds.ls("*." + LAYER, objectsOnly=True) or [])}


def _free_index(pma):
    used = set(cmds.getAttr(pma + ".input3D", multiIndices=True) or [])
    con = cmds.listConnections(pma + ".input3D", source=True, destination=False, plugs=True, connections=True) or []
    for plug in con[0::2]:                      # ours: 'pma.input3D[3]' (and the children of it)
        if "input3D[" in plug:
            try:
                used.add(int(plug.split("input3D[")[1].split("]")[0]))
            except ValueError:
                pass
    i = 0
    while i in used:
        i += 1
    return i


def _copiers(ctrl):
    """Joints copying this control's channels (they need the same layer)."""
    out = []
    for plug in ("translate", "rotate"):
        for dst in cmds.listConnections("%s.%s" % (ctrl, plug), source=False, destination=True) or []:
            d = cmds.ls(dst, long=True)[0]
            if cmds.nodeType(d) == "joint" and d not in out:
                out.append(d)
    return out


def _connect(group_ctrl, ctrl, weight):
    """group_ctrl's translate / rotate x weight into ctrl's layer (and its copiers'). Returns the nodes made."""
    made = []
    gp = (cmds.listRelatives(group_ctrl, parent=True, fullPath=True) or [None])[0]
    tag = "%s_%s" % (naming.strip_type_suffix(_short(group_ctrl)), _short(ctrl))
    outs = []
    for node in [ctrl] + _copiers(ctrl):
        lay, pt, pr = _add_layer(node, ctrl)
        par = (cmds.listRelatives(lay, parent=True, fullPath=True) or [None])[0]
        m, sign = _space_matrix(gp, par)
        mr, _s = _space_matrix(gp, par, lengths=False)          # turns: degrees stay degrees
        outs.append((pt, pr, m, mr, sign))
    for kind, attr in (("t", "translate"), ("r", "rotate")):
        md = cmds.createNode("multiplyDivide", name=tag + "_" + kind + "_w", skipSelect=True)
        cmds.connectAttr(group_ctrl + "." + attr, md + ".input1")
        cmds.setAttr(md + ".input2", weight, weight, weight, type="double3")
        made.append(md)
        for pt, pr, m, mr, sign in outs:
            vp = cmds.createNode("vectorProduct", name=tag + "_" + kind + "_axes", skipSelect=True)
            cmds.setAttr(vp + ".operation", 3)                      # vector x matrix: into the control's axes
            cmds.setAttr(vp + ".matrix", m if kind == "t" else mr, type="matrix")
            cmds.connectAttr(md + ".output", vp + ".input1")
            src = vp + ".output"
            if kind == "r" and sign < 0:                            # a mirror turns a turn the other way
                neg = cmds.createNode("multiplyDivide", name=tag + "_r_mirror", skipSelect=True)
                cmds.setAttr(neg + ".input2", -1, -1, -1, type="double3")
                cmds.connectAttr(src, neg + ".input1")
                src = neg + ".output"
                made.append(neg)
            pma = pt if kind == "t" else pr
            cmds.connectAttr(src, "%s.input3D[%d]" % (pma, _free_index(pma)))
            made.append(vp)
    return [_short(x) for x in made]


def _disconnect(nodes):
    for n in nodes:
        if cmds.objExists(n):
            cmds.delete(n)


def _drop_empty_layers():
    """Layers no group control feeds any more: the control goes back under its old parent, the layer goes."""
    from gus_rigtool.core import spaces
    for lay in cmds.ls("*." + LAYER, objectsOnly=True, long=True) or []:
        pmas = [p for p in (_sum_of(lay, "translate"), _sum_of(lay, "rotate")) if p]
        if any(cmds.listConnections(p + ".input3D", source=True, destination=False) for p in set(pmas)):
            continue
        kids = cmds.listRelatives(lay, children=True, type="transform", fullPath=True) or []
        parent = (cmds.listRelatives(lay, parent=True, fullPath=True) or [None])[0]
        for k in kids:
            spaces._parent_keeping(k, parent)
        cmds.delete(list(set(pmas)) + [lay])


# ---- group controls --------------------------------------------------------------------------------------------

def set_weights(group_ctrl, weights):
    """{ctrl: weight}: added, changed, or (weight under 0.05) taken off. Returns the group's data."""
    group_ctrl = _long(group_ctrl) or group_ctrl
    data = read(group_ctrl)
    # 5.6.19: the deepest first, and found again by name - a layer above a control changes the path of
    # everything under it (a chain: the ear's FK)
    for c, w in sorted(weights.items(), key=lambda kv: -kv[0].count("|")):
        key = _short(c)
        if key in data:
            mds = [n for n in data[key][1] if n.endswith("_t_w") or n.endswith("_r_w")]
            if w >= MIN_WEIGHT:
                for md in mds:
                    cmds.setAttr(md + ".input2", w, w, w, type="double3")
                data[key][0] = w
                continue
            _disconnect(data.pop(key)[1])
        elif w >= MIN_WEIGHT:
            ctrl = _long(c) or _long(_short(c))
            if not ctrl or ctrl == group_ctrl:
                continue
            data[key] = [w, _connect(group_ctrl, ctrl, w)]
    _write(group_ctrl, data)
    _drop_empty_layers()
    return data


def make(name, weights, position=None, parent=None, size=1.0, shape="circle", side="C", mirrored=False):
    """A new group control (name) at position, under parent, moving each control by its weight. One undo; nothing
    moves. Returns the control."""
    from gus_rigtool.builder import controls as BC
    if _long(name):
        raise RuntimeError("%s exists already." % name)
    targets = [c for c in weights if _long(c)]
    if not targets:
        raise RuntimeError("no controls to move.")
    if position is None:
        ps = [_pos(c) for c in targets]
        position = [sum(p[i] for p in ps) / len(ps) for i in range(3)]
    m = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, position[0], position[1], position[2], 1.0]
    with utils.undo_chunk("gusrigGroupCtrl"):
        off, c = BC.make(side, "tmpGroupCtrl", shape, size, m, _long(parent) if parent else None, "Z", mirror=None)
        c = cmds.rename(c, name)
        c = cmds.ls(c, long=True)[0]
        off = cmds.ls(cmds.listRelatives(c, parent=True, fullPath=True)[0], long=True)[0]
        off = cmds.rename(off, name.replace("_ctrl", "") + "_offset")
        c = _long(name)
        o = cmds.listRelatives(c, parent=True, fullPath=True)[0]
        for a in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            try:
                cmds.setAttr(o + "." + a, lock=False)
            except RuntimeError:
                pass
        # 5.6.10: its group set in WORLD space - a clean mirror for the right side (the same values move it the
        # mirror way), plain for the rest. 5.6.8 set the local scale X to -1: under the Hare's Head_01_CTRL (its
        # axes scaled and turned) that came out [25.8, 1, -1] - stretched, moving the lips 9x.
        sx = -1.0 if mirrored else 1.0
        cmds.xform(o, worldSpace=True, matrix=[sx, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0,
                                               position[0], position[1], position[2], 1])
        sizes = [math.sqrt(sum(v * v for v in WT._wm(o)[r * 4:r * 4 + 3])) for r in range(3)]
        if max(abs(x - 1.0) for x in sizes) > 1e-3:
            cmds.delete(o)                              # nothing left half made
            raise RuntimeError("%s's group comes out stretched (%s) under %s - not made." % (
                name, ", ".join("%.3f" % x for x in sizes), _short(parent) if parent else "the world"))
        c = _long(name)
        for a in ("sx", "sy", "sz"):
            try:
                cmds.setAttr(c + "." + a, lock=True, keyable=False, channelBox=False)
            except RuntimeError:
                pass
        _write(c, {})
        set_weights(c, dict((t, weights[t]) for t in targets))
        try:
            from gus_rigtool.core import vis_switch
            if vis_switch.find():
                vis_switch.assign([c], "Face_Ctrls")
        except Exception:
            pass
    return c


def remove(group_ctrl):
    """The group control and everything it made; the controls it moved stay where they are at rest."""
    group_ctrl = _long(group_ctrl) or group_ctrl
    data = read(group_ctrl)
    with utils.undo_chunk("gusrigGroupCtrlRemove"):
        for _c, (_w, nodes) in data.items():
            _disconnect(nodes)
        off = cmds.listRelatives(group_ctrl, parent=True, fullPath=True)
        cmds.delete(off[0] if off and len(cmds.listRelatives(off[0], children=True) or []) == 1 else group_ctrl)
        _drop_empty_layers()
    return len(data)


# ---- the mouth -------------------------------------------------------------------------------------------------

def ribbon_controls(*names):
    """The controls of the ribbon builds with these names (any case; 'Mouth', 'L_Facial_ribbon'...)."""
    from gus_rigtool.core import face_kit, ribbon
    want = [n.lower() for n in names if n]
    out = []
    for key, _st, _n in ribbon.builds_list():
        if _short(key).lower() in want:
            out += [c for _i, _o, c in face_kit.controls_of(key) if c not in out]
    return out


def _falloff(d, radius):
    if d >= radius:
        return 0.0
    t = 1.0 - d / radius
    return t * t * (3.0 - 2.0 * t)                      # smooth: 1 at the centre, 0 at the radius


def mouth_plan(mouth, face=None):
    """{group control name: {'weights': {ctrl: w}, 'position', 'size', 'side', 'mirrored', 'shape', 'jaw'}} for
    Mouth_main / Upper_Lip / Lower_Lip / L / R_Mouth_Corner, from the mouth's controls (and face controls nearby:
    the cheeks, which the corners and the mouth pull a little)."""
    mouth = [c for c in mouth if _long(c)]
    face = [c for c in face or [] if _long(c) and c not in mouth]
    if len(mouth) < 4:
        raise RuntimeError("pick the mouth's controls (4 or more) - the mouth ribbon.")
    pos = dict((c, _pos(c)) for c in mouth + face)
    cx = sum(pos[c][0] for c in mouth) / len(mouth)
    cy = sum(pos[c][1] for c in mouth) / len(mouth)
    front = max(pos[c][2] for c in mouth)
    by_x = sorted(mouth, key=lambda c: pos[c][0])
    lc, rc = by_x[-1], by_x[0]                         # left = +X
    hw = max(abs(pos[lc][0] - cx), abs(pos[rc][0] - cx), 1e-3)
    upper = [c for c in mouth if c not in (lc, rc) and pos[c][1] >= cy]
    lower = [c for c in mouth if c not in (lc, rc) and pos[c][1] < cy]
    f = hw * 0.35
    s = hw * 0.18
    plan = {}

    def lip(cs, corner_w):
        w = dict((c, max(MIN_WEIGHT, 1.0 - 0.5 * (abs(pos[c][0] - cx) / hw) ** 2)) for c in cs)
        w[lc] = w[rc] = corner_w
        return w
    top = max([pos[c][1] for c in upper] or [cy])
    bot = min([pos[c][1] for c in lower] or [cy])
    plan["Upper_Lip_ctrl"] = {"weights": lip(upper, 0.3), "position": [cx, top + s, front + f], "size": s,
                              "side": "C", "mirrored": False, "shape": "circle", "jaw": False}
    plan["Lower_Lip_ctrl"] = {"weights": lip(lower, 0.3), "position": [cx, bot - s, front + f], "size": s,
                              "side": "C", "mirrored": False, "shape": "circle", "jaw": True}
    for side, corner, sign in (("L", lc, 1.0), ("R", rc, -1.0)):
        w = {}
        for c in mouth:
            v = _falloff(_dist(pos[c], pos[corner]), hw * 1.1)
            if v >= MIN_WEIGHT:
                w[c] = round(v, 3)
        for c in face:
            v = 0.5 * _falloff(_dist(pos[c], pos[corner]), hw * 1.6)
            if v >= MIN_WEIGHT:
                w[c] = round(v, 3)
        p = pos[corner]
        plan["%s_Mouth_Corner_ctrl" % side] = {"weights": w, "position": [p[0] + sign * s, p[1], front + f],
                                               "size": s, "side": side, "mirrored": side == "R", "shape": "circle",
                                               "jaw": False}
    w = dict((c, 1.0) for c in mouth)
    for c in face:
        v = 0.6 * _falloff(_dist(pos[c], [cx, cy, front]), hw * 2.2)
        if v >= MIN_WEIGHT:
            w[c] = round(v, 3)
    plan["Mouth_main_ctrl"] = {"weights": w, "position": [cx, cy, front + f * 2.5], "size": hw * 0.9,
                               "side": "C", "mirrored": False, "shape": "rectangle", "jaw": False}
    for p in plan.values():               # names, not paths: the layers made by the first ones change the paths
        p["weights"] = dict((_short(c), w) for c, w in p["weights"].items())
    return plan


def plan_text(plan):
    lines = []
    for name in ("Mouth_main_ctrl", "Upper_Lip_ctrl", "Lower_Lip_ctrl", "L_Mouth_Corner_ctrl", "R_Mouth_Corner_ctrl"):
        p = plan.get(name)
        if not p:
            continue
        ws = sorted(p["weights"].items(), key=lambda x: -x[1])
        lines.append("%s: %d control(s) - %s%s" % (name, len(ws), ", ".join("%s %.2f" % (_short(c), w)
                                                                           for c, w in ws[:5]),
                                                   " ..." if len(ws) > 5 else ""))
    return lines


def make_mouth(plan, head, jaw=None):
    """Every group control of the plan, under head (the lower lip under jaw when given). One undo. Returns them."""
    made = []
    with utils.undo_chunk("gusrigMouthGroups"):
        for name in ("Mouth_main_ctrl", "Upper_Lip_ctrl", "Lower_Lip_ctrl", "L_Mouth_Corner_ctrl",
                     "R_Mouth_Corner_ctrl"):
            p = plan.get(name)
            if not p or not p["weights"] or _long(name):
                continue
            parent = jaw if (p["jaw"] and jaw and _long(jaw)) else head
            made.append(make(name, p["weights"], p["position"], parent, p["size"], p["shape"], p["side"],
                             p["mirrored"]))
    return made


def ribbon_of(ctrl):
    """The name of the ribbon build a control belongs to, or None."""
    from gus_rigtool.core import face_kit, ribbon
    c = _long(ctrl)
    for key, _st, _n in ribbon.builds_list():
        if c in [x for _i, _o, x in face_kit.controls_of(key)]:
            return _short(key)
    return None


def head_and_jaw(head=None, jaw=None):
    """The control the group controls go under (the head) and the lower lip's (the jaw): the ones given, else the
    rig's Head_ctrl / Jaw control by name."""
    from gus_rigtool.core import space_check
    from gus_rigtool.tools import checker
    h = _long(head) if head else None
    h = h or space_check.head_control()
    j = _long(jaw) if jaw else None
    if not j:
        for c in checker.transforms(None):
            n = _short(c).lower()
            if checker.is_control(c) and n in ("jaw_ctrl", "jaw_end_ctrl", "c_jaw_ctrl"):
                j = c
                break
    return h, j
