"""
Joint chains and limb machinery: bind / FK / IK chains, IK/FK blend, stretch, pole vectors,
and the IK/FK matching animators use (no jump when switching).
"""

import maya.cmds as cmds

from gus_rigtool.builder import controls, mathx, names
from gus_rigtool.core import mirror_engine as me


def world(node):
    return list(cmds.getAttr(node + ".worldMatrix[0]"))


# ---------------------------------------------------------------------------
# chains
# ---------------------------------------------------------------------------

def joint_chain(side, parts, matrices, parent=None, variant=None, radius=1.0, chain=True):
    """Joints at world matrices (rotation in Joint Orient, rotate 0). chain=False: all under parent."""
    out = []
    s = names.settings()
    for part, m in zip(parts, matrices):
        under = out[-1] if (chain and out) else parent
        j = cmds.createNode("joint", name=names.make(side, part, "jnt", variant, s),
                            parent=under) if under else cmds.createNode("joint", name=names.make(side, part, "jnt",
                                                                                                  variant, s))
        j = cmds.ls(j, long=True)[0]
        pw = world(under) if under else list(me.IDENTITY)
        local = me.mul(m, me.inverse(pw))
        t, r, _s = me.decompose(local, 0)
        cmds.setAttr(j + ".translate", *t)
        cmds.setAttr(j + ".jointOrient", *r)
        cmds.setAttr(j + ".rotate", 0, 0, 0)
        cmds.setAttr(j + ".radius", radius)
        out.append(j)
    return out


def hide(nodes):
    for n in nodes:
        try:
            cmds.setAttr(n + ".visibility", 0)
        except RuntimeError:
            pass


def blend(side, bind, fk, ik, blend_plug):
    """bind[i] follows fk[i] (blend 0) or ik[i] (blend 1)."""
    rev = cmds.createNode("reverse", name=bind[0].split("|")[-1] + "_ikfkRev")
    cmds.connectAttr(blend_plug, rev + ".inputX")
    for b, f, i in zip(bind, fk, ik):
        con = cmds.parentConstraint(f, i, b, maintainOffset=False)[0]
        cmds.setAttr(con + ".interpType", 2)
        w = cmds.parentConstraint(con, query=True, weightAliasList=True)
        cmds.connectAttr(rev + ".outputX", con + "." + w[0])
        cmds.connectAttr(blend_plug, con + "." + w[1])


def visibility_switch(side, part, blend_plug, fk_nodes, ik_nodes):
    """FK controls show while the blend is under 1, IK controls while it is over 0."""
    for nodes, op, value in ((fk_nodes, 4, 1.0), (ik_nodes, 2, 0.0)):      # 4: less than, 2: greater than
        if not nodes:
            continue
        cond = cmds.createNode("condition", name=names.make(side, part + ("_fkVis" if op == 4 else "_ikVis"),
                                                             "grp").replace("_grp", "_cond"))
        cmds.connectAttr(blend_plug, cond + ".firstTerm")
        cmds.setAttr(cond + ".secondTerm", value)
        cmds.setAttr(cond + ".operation", op)
        cmds.setAttr(cond + ".colorIfTrueR", 1)
        cmds.setAttr(cond + ".colorIfFalseR", 0)
        for n in nodes:
            cmds.connectAttr(cond + ".outColorR", n + ".visibility", force=True)


def ik_handle(side, part, start, end, solver="ikRPsolver", parent=None):
    name = names.make(side, part, "ik")
    h, eff = cmds.ikHandle(startJoint=start, endEffector=end, solver=solver, name=name)
    cmds.rename(eff, name + "_eff")
    if parent:
        h = cmds.parent(h, parent)[0]
    cmds.setAttr(h + ".visibility", 0)
    return cmds.ls(h, long=True)[0]


def fk_controls(side, joints, parts, shape, size, face, parent, lock=("sx", "sy", "sz", "v")):
    """One control per joint, each under the previous; each drives its joint (parent constraint)."""
    offsets, ctrls = [], []
    under = parent
    for j, part in zip(joints, parts):
        off, ctrl = controls.make(side, part, shape, size, world(j), under, face, "fk", lock=lock)
        cmds.parentConstraint(ctrl, j, maintainOffset=False)
        offsets.append(off)
        ctrls.append(ctrl)
        under = ctrl
    return offsets, ctrls


def mirror_control(side, part, offset, ctrl):
    """A right-side control that moves as the mirror of its left twin: its offset group gets scale X -1, so the
    same values (or moving both at once) mirror. What hung from the control hangs from the returned 'hold' group
    instead (under the control, at its place, world axes: no -1 scale below it)."""
    cmds.setAttr(offset + ".scaleX", -1)
    pos = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
    return controls.group(names.make(side, part + "_hold", "grp"), ctrl, mathx.translate_matrix(pos))


def no_flip(side, part, handle, hold, start_pos, pv_pos, settings):
    """Knee / elbow that can follow the foot instead of the pole vector (never flips): a second pole target
    under the IK control (its 'hold'), at the pole vector's place, blended by knee_mode (0 = pole vector, 1 =
    follows the foot); knee_twist turns it around the limb's line."""
    nm = lambda kind: names.make(side, part + kind, "grp")
    handle = cmds.ls(handle.split("|")[-1], long=True)[0]          # it may have moved (foot pivots)
    end_pos = cmds.xform(hold, query=True, worldSpace=True, rotatePivot=True)
    line = mathx.sub(start_pos, end_pos)
    side_vec = mathx.sub(pv_pos, end_pos)
    m = mathx.axes_matrix("X", line, "Y", side_vec, end_pos)
    # an offset group holds the turn, so knee_twist drives a rotateX that is 0 at rest (driving the group that
    # holds the turn wiped it out: the knee popped by 4 units in the Self-test)
    zero = controls.group(nm("_kneeTwistOffset"), hold, m)
    twist = controls.group(nm("_kneeTwist"), zero, m)
    target = controls.group(nm("_autoPole"), twist, mathx.translate_matrix(pv_pos))
    mode = controls.add_float(settings, "knee_mode", 0.0, 0.0, 1.0)
    turn = controls.add_float(settings, "knee_twist", 0.0)
    cmds.connectAttr(turn, twist + ".rotateX")
    con = cmds.poleVectorConstraint(target, handle)[0]
    w = cmds.poleVectorConstraint(con, query=True, weightAliasList=True) or []
    if len(w) >= 2:
        rev = cmds.createNode("reverse", name=nm("_kneeMode").replace("_grp", "_rev"))
        cmds.connectAttr(mode, rev + ".inputX")
        cmds.connectAttr(rev + ".outputX", con + "." + w[0])
        cmds.connectAttr(mode, con + "." + w[-1])
    return target


def mirrors(side, opt):
    """True when this limb's right IK control / pole vector move as the mirror of the left ones."""
    return side == "R" and opt.get("ik_mirror", True) and opt.get("ik_orient", "world") == "world"


# ---------------------------------------------------------------------------
# stretch
# ---------------------------------------------------------------------------

def stretch(side, part, ik_joints, start_node, end_node, on_plug, scale_plug, aim="X", lengths=None,
            pin_plug=None, pv_node=None):
    """IK chain stretches when the IK control goes further than the chain's length (on_plug 0/1; None: no
    automatic stretch). lengths: a plug per bone that scales its length (1 = as built). pin_plug (0-1): the
    elbow / knee goes onto pv_node - the first bone reaches from start_node to the pole vector, the second
    from the pole vector to end_node."""
    axis = aim.lstrip("-")
    rest = sum(abs(cmds.getAttr("%s.translate%s" % (j, axis))) for j in ik_joints[1:])
    if rest < 1e-6:
        return
    nm = lambda kind: names.make(side, part + "_stretch" + kind, "grp").replace("_grp", "")
    factor = None
    if on_plug:
        dist = cmds.createNode("distanceBetween", name=nm("Dist"))
        for i, node in enumerate((start_node, end_node)):
            dm = cmds.createNode("decomposeMatrix", name=nm("Dm%d" % i))
            cmds.connectAttr(node + ".worldMatrix[0]", dm + ".inputMatrix")
            cmds.connectAttr(dm + ".outputTranslate", dist + ".point%d" % (i + 1))
        norm = cmds.createNode("multiplyDivide", name=nm("Norm"))
        cmds.setAttr(norm + ".operation", 2)
        cmds.connectAttr(dist + ".distance", norm + ".input1X")
        restm = cmds.createNode("multDoubleLinear", name=nm("Rest"))
        cmds.setAttr(restm + ".input1", rest)
        if scale_plug:
            cmds.connectAttr(scale_plug, restm + ".input2")
        else:
            cmds.setAttr(restm + ".input2", 1.0)
        cmds.connectAttr(restm + ".output", norm + ".input2X")
        clamp = cmds.createNode("condition", name=nm("Clamp"))        # ratio > 1 ? ratio : 1
        cmds.setAttr(clamp + ".operation", 2)
        cmds.connectAttr(norm + ".outputX", clamp + ".firstTerm")
        cmds.setAttr(clamp + ".secondTerm", 1.0)
        cmds.connectAttr(norm + ".outputX", clamp + ".colorIfTrueR")
        cmds.setAttr(clamp + ".colorIfFalseR", 1.0)
        onoff = cmds.createNode("blendTwoAttr", name=nm("OnOff"))
        cmds.setAttr(onoff + ".input[0]", 1.0)
        cmds.connectAttr(clamp + ".outColorR", onoff + ".input[1]")
        cmds.connectAttr(on_plug, onoff + ".attributesBlender")
        factor = onoff + ".output"
    pin_ends = [(start_node, pv_node), (pv_node, end_node)] if pin_plug and pv_node else []
    for idx, j in enumerate(ik_joints[1:]):
        plug = "%s.translate%s" % (j, axis)
        value = cmds.getAttr(plug)
        jn = j.split("|")[-1]
        mul = cmds.createNode("multDoubleLinear", name=nm("Len_" + jn))
        cmds.setAttr(mul + ".input1", value)
        if factor:
            cmds.connectAttr(factor, mul + ".input2")
        else:
            cmds.setAttr(mul + ".input2", 1.0)
        out = mul + ".output"
        if lengths and idx < len(lengths) and lengths[idx]:
            bone = cmds.createNode("multDoubleLinear", name=nm("Bone_" + jn))
            cmds.connectAttr(out, bone + ".input1")
            cmds.connectAttr(lengths[idx], bone + ".input2")
            out = bone + ".output"
        if idx < len(pin_ends):
            a, b = pin_ends[idx]
            d = cmds.createNode("distanceBetween", name=nm("PinDist%d" % idx))
            for k, node in enumerate((a, b)):
                dm = cmds.createNode("decomposeMatrix", name=nm("PinDm%d%d" % (idx, k)))
                cmds.connectAttr(node + ".worldMatrix[0]", dm + ".inputMatrix")
                cmds.connectAttr(dm + ".outputTranslate", d + ".point%d" % (k + 1))
            local = cmds.createNode("multiplyDivide", name=nm("PinLocal%d" % idx))   # world length / rig scale
            cmds.setAttr(local + ".operation", 2)
            cmds.connectAttr(d + ".distance", local + ".input1X")
            if scale_plug:
                cmds.connectAttr(scale_plug, local + ".input2X")
            else:
                cmds.setAttr(local + ".input2X", 1.0)
            sign = cmds.createNode("multDoubleLinear", name=nm("PinSign%d" % idx))
            cmds.connectAttr(local + ".outputX", sign + ".input1")
            cmds.setAttr(sign + ".input2", -1.0 if value < 0 else 1.0)
            bl = cmds.createNode("blendTwoAttr", name=nm("Pin%d" % idx))
            cmds.connectAttr(out, bl + ".input[0]")
            cmds.connectAttr(sign + ".output", bl + ".input[1]")
            cmds.connectAttr(pin_plug, bl + ".attributesBlender")
            out = bl + ".output"
        cmds.connectAttr(out, plug)


def soft_ik(side, part, start_node, handle, chain_len, soft_plug, scale_plug=None, stretch_plug=None):
    """Soft IK: as the limb gets near straight, the IK end slows down instead of snapping (no 'pop').
    The handle is pulled back towards the start: d_soft = a + s (1 - e^-((d - a) / s)), a = L - s,
    s = soft * L / 4. soft 0 = normal IK. With stretch on, soft fades out (the limb stretches instead)."""
    nm = lambda kind: names.make(side, part + "_soft" + kind, "grp").replace("_grp", "")
    handle = cmds.ls(handle.split("|")[-1], long=True)[0]          # its path changed when it was parented
    parent = (cmds.listRelatives(handle, parent=True, fullPath=True) or [None])[0]
    end = cmds.createNode("transform", name=names.make(side, part + "_softEnd", "grp"))
    cmds.xform(end, worldSpace=True, translation=cmds.xform(handle, query=True, worldSpace=True, translation=True))
    if parent:
        end = cmds.parent(end, parent)[0]
    end = cmds.ls(end, long=True)[0]

    def pos(node, tag):
        dm = cmds.createNode("decomposeMatrix", name=nm("Dm" + tag))
        cmds.connectAttr(node + ".worldMatrix[0]", dm + ".inputMatrix")
        return dm + ".outputTranslate"

    def md(a, b, op, tag):
        n = cmds.createNode("multiplyDivide", name=nm(tag))
        cmds.setAttr(n + ".operation", op)
        for plug, v in (("input1X", a), ("input2X", b)):
            (cmds.connectAttr(v, n + "." + plug) if isinstance(v, str) else cmds.setAttr(n + "." + plug, v))
        return n + ".outputX"

    def pma(a, b, op, tag):
        n = cmds.createNode("plusMinusAverage", name=nm(tag))
        cmds.setAttr(n + ".operation", op)
        for i, v in enumerate((a, b)):
            plug = "%s.input1D[%d]" % (n, i)
            (cmds.connectAttr(v, plug) if isinstance(v, str) else cmds.setAttr(plug, v))
        return n + ".output1D"

    def cond(first, second, if_true, if_false, tag, op=2):
        n = cmds.createNode("condition", name=nm(tag))
        cmds.setAttr(n + ".operation", op)                 # 2: greater than
        for plug, v in (("firstTerm", first), ("secondTerm", second), ("colorIfTrueR", if_true),
                        ("colorIfFalseR", if_false)):
            (cmds.connectAttr(v, n + "." + plug) if isinstance(v, str) else cmds.setAttr(n + "." + plug, v))
        return n + ".outColorR"

    dist = cmds.createNode("distanceBetween", name=nm("Dist"))
    cmds.connectAttr(pos(start_node, "Start"), dist + ".point1")
    cmds.connectAttr(pos(end, "End"), dist + ".point2")
    d = dist + ".distance"
    if scale_plug:
        d = md(d, scale_plug, 2, "Scaled")
    s = md(soft_plug, chain_len * 0.25, 1, "S")
    a = pma(chain_len, s, 2, "A")                             # where softening starts
    s_safe = cond(s, 1e-4, s, 1e-4, "SSafe")
    x = md(pma(d, a, 2, "Over"), s_safe, 2, "X")
    e = md(2.718281828, md(x, -1.0, 1, "NegX"), 3, "Exp")    # e^-x
    soft_d = pma(a, md(s, pma(1.0, e, 2, "OneMinusE"), 1, "SPart"), 1, "SoftD")
    near = cond(d, a, soft_d, d, "Near")                      # only past a
    final = cond(s, 1e-4, near, d, "On")                      # soft 0: plain IK
    d_safe = cond(d, 1e-6, d, 1e-6, "DSafe")
    ratio = md(final, d_safe, 2, "Ratio")
    if stretch_plug:
        bl = cmds.createNode("blendTwoAttr", name=nm("StretchFade"))
        cmds.connectAttr(ratio, bl + ".input[0]")
        cmds.setAttr(bl + ".input[1]", 1.0)
        cmds.connectAttr(stretch_plug, bl + ".attributesBlender")
        ratio = bl + ".output"
    con = cmds.pointConstraint(start_node, end, handle, maintainOffset=False)[0]
    w = cmds.pointConstraint(con, query=True, weightAliasList=True)
    rev = cmds.createNode("reverse", name=nm("Rev"))
    cmds.connectAttr(ratio, rev + ".inputX")
    cmds.connectAttr(rev + ".outputX", con + "." + w[0])
    cmds.connectAttr(ratio, con + "." + w[1])
    return ratio


# ---------------------------------------------------------------------------
# IK / FK matching (animators: switch without a jump)
# ---------------------------------------------------------------------------

META = ("gusFkCtrls", "gusFkJoints", "gusIkJoints", "gusIkCtrl", "gusPvCtrl", "gusBlend", "gusFootAttrs", "gusEnd",
        "gusHockCtrl")


def store_meta(settings_ctrl, **values):
    for key, value in values.items():
        controls.add_string(settings_ctrl, key, " ".join(value) if isinstance(value, (list, tuple)) else value)


def _meta(settings_ctrl, key):
    return [n for n in controls.get_string(settings_ctrl, key).split() if n]


def find_settings(node):
    """The limb settings control of a selected limb control (or the settings control itself)."""
    if controls.get_string(node, "gusBlend"):
        return node
    from gus_rigtool.core import utils
    short = node.split("|")[-1]
    for n in utils.nodes_with_attr("gusBlend"):
        for key in ("gusFkCtrls", "gusIkCtrl", "gusPvCtrl", "gusIkCtrls", "gusTweaks", "gusHockCtrl"):
            if short in [x.split("|")[-1] for x in _meta(n, key)]:
                return n
    return None


_ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]


def set_world(node, m, translate=True, rotate=True):
    """Put node at world matrix m (translate / rotate only: locked scale is never touched)."""
    order = cmds.getAttr(node + ".rotateOrder")
    rot = list(me.IDENTITY)
    for r in range(3):
        rot[r * 4:r * 4 + 3] = mathx.norm(m[r * 4:r * 4 + 3])
    parent = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    pw = world(parent) if parent else list(me.IDENTITY)
    if mathx.det3(pw) < 0:                         # a mirrored control (scale -1 above it): local values
        rot[12:15] = m[12:15]
        if mathx.det3(rot) > 0:                    # a plain rotation can't be reached under -1: closest mirror
            rot[0:3] = [-x for x in rot[0:3]]
        t, r, _s = me.decompose(me.mul(rot, me.inverse(pw)), order)
        for attrs, values, on in ((("tx", "ty", "tz"), t, translate), (("rx", "ry", "rz"), r, rotate)):
            for a, v in zip(attrs, values):
                plug = node + "." + a
                if on and cmds.getAttr(plug, settable=True):
                    cmds.setAttr(plug, v)
        return
    if rotate:
        cmds.xform(node, worldSpace=True, rotation=me.matrix_euler(rot, order), rotateOrder=_ORDERS[order])
    if translate:
        cmds.xform(node, worldSpace=True, translation=m[12:15])


def _first(nodes):
    return cmds.ls(nodes[0], long=True)[0] if nodes and cmds.ls(nodes[0]) else None


def match_fk_to_ik(settings_ctrl):
    """FK controls take the IK pose, then the limb switches to FK."""
    fk = _meta(settings_ctrl, "gusFkCtrls")
    ikj = _meta(settings_ctrl, "gusIkJoints")
    for c, j in zip(fk, ikj):
        set_world(c, world(j), translate=False)   # rotation only (controls hold their place)
    cmds.setAttr(settings_ctrl + "." + controls.get_string(settings_ctrl, "gusBlend"), 0)


def match_ik_to_fk(settings_ctrl):
    """IK control and pole vector take the FK pose, then the limb switches to IK."""
    ik_ctrl = _first(_meta(settings_ctrl, "gusIkCtrl"))
    pv = _first(_meta(settings_ctrl, "gusPvCtrl"))
    ikj = _meta(settings_ctrl, "gusIkJoints")
    fkj = _meta(settings_ctrl, "gusFkJoints")
    for attr in _meta(settings_ctrl, "gusFootAttrs"):         # foot roll back to 0 first
        if cmds.objExists(ik_ctrl + "." + attr) and cmds.getAttr(ik_ctrl + "." + attr, settable=True):
            cmds.setAttr(ik_ctrl + "." + attr, 0)
    try:
        end = int(controls.get_string(settings_ctrl, "gusEnd") or 2)
    except ValueError:
        end = 2
    if ik_ctrl and len(ikj) > end and len(fkj) > end:
        offset = me.mul(world(ik_ctrl), me.inverse(world(ikj[end])))
        set_world(ik_ctrl, me.mul(offset, world(fkj[end])))
    if pv and len(fkj) >= 3:
        a, b, c = [mathx.position(world(j)) for j in fkj[:3]]
        cmds.xform(pv, worldSpace=True, translation=mathx.pole_position(a, b, c))
    hock = _first(_meta(settings_ctrl, "gusHockCtrl"))
    if hock and len(ikj) > 2 and len(fkj) > 2:                # quadruped leg: the hock angle too
        from gus_rigtool.builder import quad
        quad.match_hock(hock, ikj[2], fkj[2])
    cmds.setAttr(settings_ctrl + "." + controls.get_string(settings_ctrl, "gusBlend"), 1)


def match_selected(to="fk"):
    """to: 'fk', 'ik' or 'toggle' (each limb goes to the other mode)."""
    from gus_rigtool.core import utils
    sel = cmds.ls(selection=True, long=True) or []
    done = []
    with utils.undo_chunk("gusrigMatchIkFk"):
        for n in sel:
            s = find_settings(n)
            if s and s not in done:
                if not controls.get_string(s, "gusBlend"):
                    continue                                 # an FK-only chain: nothing to switch
                mode = to
                if to == "toggle":
                    mode = "ik" if cmds.getAttr(s + "." + controls.get_string(s, "gusBlend")) < 0.5 else "fk"
                if controls.get_string(s, "gusChain"):
                    from gus_rigtool.builder import chain
                    (chain.match_to_fk if mode == "fk" else chain.match_to_ik)(s)
                else:
                    (match_fk_to_ik if mode == "fk" else match_ik_to_fk)(s)
                done.append(s)
        from gus_rigtool.builder import existing          # adopted / taught limbs of other rigs
        for n in sel:
            if n not in done and not find_settings(n):
                found = existing.taught_of(n)
                if found and found[0] not in done:
                    existing.taught_match(n, to)
                    done.append(found[0])
    if not done:
        raise RuntimeError("select a limb or chain control (FK, IK, pole vector, tweak or settings) of a "
                           "rig part with an IK/FK switch.")
    utils.info("Build", "matched %d limb(s)%s." % (len(done), {"fk": " to FK", "ik": " to IK"}.get(to, "")))
