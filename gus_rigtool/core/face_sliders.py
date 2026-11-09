"""
On-screen sliders for the face expressions (5.6.15): a board next to the head, one column per expression -
an amount knob (drag it up: 0 -> 1) and, for a split pose, a shift knob under it (drag it sideways: left only /
both / right only). The knobs drive the sliders on Mouth_main_ctrl (Smile_L / Smile_R...); the animators key
the knobs.

    Smile_L = amount x min(1, 1 + shift)        shift -1: right only, 0: both, +1: left only
    Smile_R = amount x min(1, 1 - shift)

    from gus_rigtool.core import face_sliders as FS
    FS.make("Mouth_main_ctrl", "Head_01_CTRL")      # (again after saving new poses: it's made fresh)
"""

import json

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import face_poses as FP

TOOL = "Face sliders"
BOARD = "Face_sliders_grp"
META = "gusFaceSliders"


def _short(n):
    return naming.short_name(n)


def _long(n):
    got = cmds.ls(n, long=True) if n else []
    return got[0] if len(got) == 1 else None


def find():
    b = _long(BOARD)
    return b if b and cmds.attributeQuery(META, node=b, exists=True) else None


def read():
    b = find()
    return json.loads(cmds.getAttr(b + "." + META) or "{}") if b else {}


NOT_CTRL = "gusNotControl"          # 5.6.17: frames and labels - the checker doesn't count them as controls


def _not_ctrl(t):
    try:
        cmds.addAttr(t, longName=NOT_CTRL, attributeType="bool", defaultValue=True)
    except RuntimeError:
        pass


def _frame(name, x0, y0, w, h, parent):
    """A thin rectangle from (x0, y0), w x h (reference: it can't be picked)."""
    c = cmds.curve(name=name, degree=1, point=[(x0, y0, 0), (x0 + w, y0, 0), (x0 + w, y0 + h, 0), (x0, y0 + h, 0),
                                               (x0, y0, 0)])
    c = cmds.ls(cmds.parent(c, parent, relative=True)[0], long=True)[0]
    s = cmds.listRelatives(c, shapes=True, fullPath=True)[0]
    cmds.setAttr(s + ".overrideEnabled", 1)
    cmds.setAttr(s + ".overrideDisplayType", 2)
    _not_ctrl(c)
    return c


def _knob(name, size, parent, pos, colour=17):
    """5.6.17: the knob sits in its own offset group at pos - so the knob itself rests at 0 and reset works."""
    off = cmds.createNode("transform", name=name + "_offset", parent=parent, skipSelect=True)
    cmds.setAttr(off + ".translate", pos[0], pos[1], 0, type="double3")
    off = cmds.ls(off, long=True)[0]
    c = cmds.curve(name=name, degree=1, point=[(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0),
                                               (-size, -size, 0)])
    c = cmds.ls(cmds.parent(c, off, relative=True)[0], long=True)[0]
    s = cmds.listRelatives(c, shapes=True, fullPath=True)[0]
    cmds.setAttr(s + ".overrideEnabled", 1)
    cmds.setAttr(s + ".overrideColor", colour)
    return c


def _label(text, size, parent, pos):
    try:
        got = cmds.textCurves(text=text, font="Arial", name=text + "_label")
    except (RuntimeError, TypeError):
        return None
    t = cmds.ls(got[0], long=True)[0]
    cmds.setAttr(t + ".scale", size, size, size, type="double3")
    cmds.setAttr(t + ".translate", *pos, type="double3")
    t = cmds.ls(cmds.parent(t, parent, relative=True)[0], long=True)[0]
    cmds.setAttr(t + ".overrideEnabled", 1)
    cmds.setAttr(t + ".overrideDisplayType", 2)
    for n in [t] + (cmds.listRelatives(t, allDescendents=True, type="transform", fullPath=True) or []):
        _not_ctrl(n)
    return t


def _lock(c, keep):
    for a in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"):
        if a not in keep:
            try:
                cmds.setAttr(c + "." + a, lock=True, keyable=False, channelBox=False)
            except RuntimeError:
                pass


def face_box(head):
    """(centre, size) of the face - the same box as the head squash's lattice (round the face controls)."""
    from gus_rigtool.core import head_squash as HS
    return HS.region(head, HS.face_controls())


def plan(holder):
    holder = _long(holder)
    if not holder:
        raise RuntimeError("no slider control: save a pose first (Face kit > Expressions).")
    out = []
    for p in FP.poses(holder):
        d = FP.read(holder)[p]
        out.append("%s: amount knob%s -> %s" % (p, " + shift knob" if d["split"] else "", " / ".join(d["attrs"])))
    return out


def make(holder, head, size=None):
    """The board (made fresh: an old one goes first, its sliders back to 0). Returns {pose: [knobs]}."""
    holder = _long(holder)
    head = _long(head)
    if not holder:
        raise RuntimeError("no slider control: save a pose first (Face kit > Expressions).")
    if not head:
        raise RuntimeError("pick the head control (the board follows it).")
    poses = FP.poses(holder)
    if not poses:
        raise RuntimeError("no poses on %s yet - save one first." % _short(holder))
    for p in poses:                                    # a slider an animator has keyed: don't take it over
        for a in FP.read(holder)[p]["attrs"]:
            if cmds.listConnections("%s.%s" % (holder, a), source=True, destination=False, type="animCurve"):
                raise RuntimeError("%s.%s has keys - delete them first (the knobs will carry the animation)."
                                   % (_short(holder), a))
    centre, box = face_box(head)
    if size is None:
        size = box[1] * 0.6                        # 5.6.16: from the face, not the head control's curve (on the
    out = {}                                       # Hare a small circle inside the head: tiny knobs, inside it)
    with utils.undo_chunk("gusrigFaceSliders"):
        remove()
        board = cmds.createNode("transform", name=BOARD, skipSelect=True)
        # 5.6.17: beside the face, the amount sliders centred on the face's middle, the shift sliders right
        # under them - all within the face's height (5.6.16 started at the bottom and ran down to the shoulder)
        cmds.setAttr(board + ".translate", centre[0] + box[0] / 2.0 + box[1] * 0.3, centre[1],
                     centre[2] + box[2] / 2.0, type="double3")
        board = cmds.ls(cmds.parent(board, head)[0], long=True)[0]
        col = size * 0.7
        bottom = -size / 2.0
        shift_y = bottom - size * 0.2
        made = []
        for i, p in enumerate(poses):
            d = FP.read(holder)[p]
            x = i * col
            g = cmds.createNode("transform", name="%s_slider_grp" % p, parent=board, skipSelect=True)
            cmds.setAttr(g + ".translateX", x)
            g = cmds.ls(g, long=True)[0]
            _frame("%s_slider_frame" % p, -size * 0.06, bottom, size * 0.12, size, g)
            _label(p, size * 0.1, g, (-size * 0.25, -bottom + size * 0.14, 0))      # above its slider
            amount = _knob("%s_amount_ctrl" % p, size * 0.1, g, (0, bottom))
            _lock(amount, ("ty",))
            cmds.transformLimits(amount, translationY=(0, size), enableTranslationY=(True, True))
            a_norm = cmds.createNode("multDoubleLinear", name="%s_amount_n" % p, skipSelect=True)
            cmds.connectAttr(amount + ".translateY", a_norm + ".input1")
            cmds.setAttr(a_norm + ".input2", 1.0 / size)
            made.append(a_norm)
            knobs = [_short(amount)]
            if d["split"] and len(d["attrs"]) == 2:
                _frame("%s_shift_frame" % p, -size * 0.25, shift_y - size * 0.04, size * 0.5, size * 0.08, g)
                shift = _knob("%s_shift_ctrl" % p, size * 0.07, g, (0, shift_y), colour=18)
                _lock(shift, ("tx",))
                cmds.transformLimits(shift, translationX=(-size * 0.25, size * 0.25), enableTranslationX=(True, True))
                s_norm = cmds.createNode("plusMinusAverage", name="%s_shift_n" % p, skipSelect=True)
                cmds.connectAttr(shift + ".translateX", s_norm + ".input1D[0]")
                s_scale = cmds.createNode("multDoubleLinear", name="%s_shift_s" % p, skipSelect=True)
                cmds.connectAttr(s_norm + ".output1D", s_scale + ".input1")
                cmds.setAttr(s_scale + ".input2", 1.0 / (size * 0.25))      # -1 .. 1
                sides = cmds.createNode("plusMinusAverage", name="%s_sides" % p, skipSelect=True)
                cmds.setAttr(sides + ".input3D[0]", 1, 1, 0, type="double3")
                neg = cmds.createNode("multDoubleLinear", name="%s_shift_neg" % p, skipSelect=True)
                cmds.connectAttr(s_scale + ".output", neg + ".input1")
                cmds.setAttr(neg + ".input2", -1)
                cmds.connectAttr(s_scale + ".output", sides + ".input3D[1].input3Dx")
                cmds.connectAttr(neg + ".output", sides + ".input3D[1].input3Dy")
                cl = cmds.createNode("clamp", name="%s_sides_clamp" % p, skipSelect=True)
                cmds.setAttr(cl + ".max", 1, 1, 1, type="double3")
                cmds.connectAttr(sides + ".output3Dx", cl + ".inputR")
                cmds.connectAttr(sides + ".output3Dy", cl + ".inputG")
                md = cmds.createNode("multiplyDivide", name="%s_sides_md" % p, skipSelect=True)
                cmds.connectAttr(a_norm + ".output", md + ".input1X")
                cmds.connectAttr(a_norm + ".output", md + ".input1Y")
                cmds.connectAttr(cl + ".outputR", md + ".input2X")
                cmds.connectAttr(cl + ".outputG", md + ".input2Y")
                cmds.connectAttr(md + ".outputX", "%s.%s" % (holder, d["attrs"][0]), force=True)    # _L
                cmds.connectAttr(md + ".outputY", "%s.%s" % (holder, d["attrs"][1]), force=True)    # _R
                made += [s_norm, s_scale, sides, neg, cl, md]
                knobs.append(_short(shift))
            else:
                for a in d["attrs"]:
                    cmds.connectAttr(a_norm + ".output", "%s.%s" % (holder, a), force=True)
            out[p] = knobs
        try:
            from gus_rigtool.core import vis_switch
            if vis_switch.find():
                vis_switch.assign([_long(k) for ks in out.values() for k in ks], "Face_Ctrls")
        except Exception:
            pass
        cmds.addAttr(board, longName=META, dataType="string")
        cmds.setAttr(board + "." + META, json.dumps({"holder": _short(holder), "knobs": out,
                                                    "nodes": [_short(n) for n in made]}), type="string")
    return out


def remove():
    """The board and its nodes; the sliders on the holder let go (back to 0)."""
    b = find()
    if not b:
        return False
    data = read()
    holder = _long(data.get("holder"))
    for n in data.get("nodes", []):
        if cmds.objExists(n):
            cmds.delete(n)
    cmds.delete(b)
    if holder:
        for p in FP.poses(holder):
            for a in FP.read(holder)[p]["attrs"]:
                plug = "%s.%s" % (holder, a)
                for src in cmds.listConnections(plug, source=True, destination=False, plugs=True) or []:
                    cmds.disconnectAttr(src, plug)
                try:
                    cmds.setAttr(plug, 0)
                except RuntimeError:
                    pass
    return True
