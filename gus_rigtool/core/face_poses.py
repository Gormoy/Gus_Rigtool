"""
Face expressions and selection sets (5.6.12).

Expressions: pose the face with its controls (and the group controls), 'Save as Smile': the pose goes into
sliders on a control (Smile_L / Smile_R, or one Smile), the controls go back to 0. Sliders add together
(Smile 0.6 + Wide 0.3). Split L / R: each control is left (+X), right, or shared in the middle, by where it is.
They go through the same layer above each control as the group controls (<ctrl>_groups), so they add on top of
everything: the jaw follow, the group controls, the control's own values.

Selection sets: mouth_all / mouth_upper / mouth_lower / mouth_corners / mouth_groups / face_all - Maya sets in the
rig (they travel with it) under gus_anim_sets; Gus Animtool lists them with its own sets.

    from gus_rigtool.core import face_poses as FP
    FP.save_pose("Mouth_main_ctrl", "Smile", split=True)
    FP.make_sets(mouth, face)
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import group_ctrls as GC
from gus_rigtool.core import world_turn as WT

TOOL = "Face poses"
META = "gusFacePoses"            # on the slider control: {pose: {'split': bool, 'attrs': [...], 'ctrls': {...}}}
ANIM_SETS = "gus_anim_sets"
EPS = 1e-4


def _short(n):
    return naming.short_name(n)


def read(holder):
    try:
        if cmds.attributeQuery(META, node=holder, exists=True):
            return json.loads(cmds.getAttr(holder + "." + META) or "{}")
    except (RuntimeError, ValueError):
        pass
    return {}


def _write(holder, data):
    if not cmds.attributeQuery(META, node=holder, exists=True):
        cmds.addAttr(holder, longName=META, dataType="string")
    cmds.setAttr(holder + "." + META, json.dumps(data), type="string")


def _attr_name(pose):
    name = "".join(ch if ch.isalnum() else "_" for ch in pose.strip()).strip("_")
    if not name or name[0].isdigit():
        raise RuntimeError("name the pose with a word (Smile, Frown, Wide...).")
    return name[0].upper() + name[1:]


# ---- what the face looks like now, against its rest ---------------------------------------------------------------

BODY = r"(^|_)(head|neck|global|world|local|cog|root|hips?|chest|spine|shoulders?|visibility)(_|\d|$)|squash"


def _face_box(named):
    """5.6.20: the box round the face controls found by name (ears included), a tenth of its biggest size more each
    way."""
    ps = [cmds.xform(c, query=True, worldSpace=True, translation=True) for c in named]
    if not ps:
        return None
    lo = [min(p[i] for p in ps) for i in range(3)]
    hi = [max(p[i] for p in ps) for i in range(3)]
    pad = max(max(hi[i] - lo[i] for i in range(3)), 1e-3) * 0.1       # the face is thin front to back
    return [lo[i] - pad for i in range(3)], [hi[i] + pad for i in range(3)]


def pose_controls(holder=None):
    """The controls a pose is made of: the face's controls by name (mouth, lips, jaw, lids, brows, nose, cheeks,
    tongue, ears, facial...) and - 5.6.20 - any control inside the box round them (a face control without a face
    word in its name). Never the head / neck / body-level controls, the group controls, the slider control, the
    sliders board's knobs."""
    import re
    from gus_rigtool.core import on_top
    skip = set(GC.all_groups())
    h = cmds.ls(holder, long=True) if holder else []
    skip.update(h)
    every = [c for c in on_top.controls() if c not in skip and "|Face_sliders_grp|" not in c and
             not cmds.attributeQuery(META, node=c, exists=True)]
    named = [c for c in every if on_top.is_face(c)]
    box = _face_box(named)
    out = list(named)
    if box:
        lo, hi = box
        for c in every:
            if c in named or re.search(BODY, _short(c).lower()):
                continue
            p = cmds.xform(c, query=True, worldSpace=True, translation=True)
            if all(lo[i] <= p[i] <= hi[i] for i in range(3)):
                out.append(c)
    return out


def _drivers(holder=None):
    """Everything that can pose the face: the face controls and the group controls (their channels)."""
    return pose_controls(holder) + [g for g in GC.all_groups() if g not in (cmds.ls(holder, long=True) if holder
                                                                             else [])]


SWITCH = r"(^|_)(ik|fk)(_|$)|ikfk|stretch|soft|space|follow|vis|tweak|wave|global|squash|ctrls|(^|_)on$|^gus"


def _custom(c):
    """5.6.20: a control's own number attributes that shape the face (the tongue's curl, curl_side...) - not the
    switches (ikfk, stretch, space / follow, visibility, tweaks, wave...), not on / off ones, not the pose sliders."""
    import re
    out = []
    for a in cmds.listAttr(c, userDefined=True, keyable=True) or []:
        if re.search(SWITCH, a.lower()):
            continue
        plug = c + "." + a
        try:
            if cmds.getAttr(plug, type=True) not in ("double", "float", "doubleLinear", "doubleAngle", "long",
                                                     "short") or not cmds.getAttr(plug, settable=True):
                continue
        except (RuntimeError, ValueError):
            continue
        out.append(plug)
    return out


def _default(plug):
    try:
        got = cmds.attributeQuery(plug.split(".")[-1], node=plug.split(".")[0], listDefault=True)
        return got[0] if got else 0.0
    except (RuntimeError, ValueError, TypeError):
        return 0.0


def _channels(c):
    out = []
    for a in ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"):
        plug = c + "." + a
        try:
            if cmds.getAttr(plug, settable=True):
                out.append(plug)
        except (RuntimeError, ValueError):
            pass
    return out


def _snapshot(ctrls):
    return dict((c, WT._wm(c)) for c in ctrls)


def _axes(m):
    out = []
    for r in range(3):
        v = m[r * 4:r * 4 + 3]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


def _euler_xyz(r):
    """Degrees (rotate order xyz, Maya's row vectors) of a 3x3 rotation."""
    ry = math.asin(max(-1.0, min(1.0, -r[0][2])))
    rx = math.atan2(r[1][2], r[2][2])
    rz = math.atan2(r[0][1], r[0][0])
    return [math.degrees(rx), math.degrees(ry), math.degrees(rz)]


def _par(c):
    """The node above the control's layer (or above the control, before it has one)."""
    lay = GC.layer_of(c)
    return (cmds.listRelatives(lay or c, parent=True, fullPath=True) or [None])[0]


IDENT = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def _delta(c, rest, now, prest=None, pnow=None):
    """(translate, rotate) the control's layer needs to put it where it is now, from its rest - in the layer's
    parent's space (the layer's own channels). 5.6.19: measured against the parent as it is at rest and as it is
    posed (prest / pnow) - a control under another posed control (the ear's FK chain) took its parent's move too,
    and moved twice."""
    if prest is None:
        par = _par(c)
        prest = WT._wm(par) if par else IDENT
    pnow = pnow or prest
    def local(m, pm):
        b = GC._inv3([pm[r * 4:r * 4 + 3] for r in range(3)])
        d = [m[12 + i] - pm[12 + i] for i in range(3)]
        return [sum(d[q] * b[q][j] for q in range(3)) for j in range(3)]
    lr, ln = local(rest, prest), local(now, pnow)
    t = [ln[j] - lr[j] for j in range(3)]
    ra, rn = _axes(rest), _axes(now)
    pa, pn = _axes(prest), _axes(pnow)
    # in the parent's axes (row vectors): rest_l = Ra Pa^T, now_l = Rn Pn^T; the turn R = rest_l^T now_l
    rl_rest = [[sum(ra[i][q] * pa[j][q] for q in range(3)) for j in range(3)] for i in range(3)]
    rl_now = [[sum(rn[i][q] * pn[j][q] for q in range(3)) for j in range(3)] for i in range(3)]
    rl = [[sum(rl_rest[q][i] * rl_now[q][j] for q in range(3)) for j in range(3)] for i in range(3)]
    return t, _euler_xyz(rl)


def _side_weight(x, centre, band):
    """1 on the left (+X), 0 on the right, a smooth share in the middle."""
    if band <= 0:
        return 1.0 if x >= centre else 0.0
    t = max(0.0, min(1.0, (x - centre + band) / (2.0 * band)))
    return t * t * (3.0 - 2.0 * t)


# ---- save / remove --------------------------------------------------------------------------------------------------

def zero_drivers(drivers=None):
    for c in drivers if drivers is not None else _drivers():
        for plug in _channels(c):
            cmds.setAttr(plug, 0)
        for plug in _custom(c):                         # 5.6.20: curl and the like to their default
            cmds.setAttr(plug, _default(plug))


def _all_sliders(holder):
    out = []
    for p in read(holder).values():
        out += [holder + "." + a for a in p.get("attrs", [])]
    return out


def _board_off():
    """5.6.15: the sliders board drives the pose sliders - it goes while poses change and comes back after
    (with the new ones). Returns the head it was on, or None."""
    from gus_rigtool.core import face_sliders as FS
    b = FS.find()
    if not b:
        return None
    head = (cmds.listRelatives(b, parent=True, fullPath=True) or [None])[0]
    FS.remove()
    return head


def _board_on(holder, head):
    if head:
        from gus_rigtool.core import face_sliders as FS
        if poses(holder):
            FS.make(holder, head)


def moved_outside(holder):
    """5.6.20: controls moved now (a channel off 0) that aren't in a pose by name - not the board's knobs, not group
    controls, not the slider control. Before, they were left out without a word."""
    from gus_rigtool.core import on_top
    holder = (cmds.ls(holder, long=True) or [None])[0]
    skip = set(_drivers(holder))
    out = []
    for c in on_top.controls():
        if c in skip or c == holder or "|Face_sliders_grp|" in c or cmds.attributeQuery(META, node=c, exists=True):
            continue
        if any(abs(cmds.getAttr(p)) > EPS for p in _channels(c)):
            out.append(c)
    return out


def sliders_on(holder):
    """{slider: value} of the pose sliders up now (by hand or by the board's knobs)."""
    out = {}
    for sl in _all_sliders(holder):
        try:
            v = cmds.getAttr(sl)
        except (RuntimeError, ValueError):
            continue
        if abs(v) > EPS:
            out[sl.split(".")[-1]] = v
    return out


def _redone(node, controls):
    """5.6.21: does the rig move this node again by itself when a pose plays? A control (its own pose / the
    animator moves it), a node held by a constraint (a ribbon's follicle offset, the ear's zero, the jaw), a
    follicle, a node that doesn't inherit its parent's move."""
    if node in controls:
        return True
    if cmds.listConnections(node, source=True, destination=False, type="constraint"):
        return True
    if cmds.listRelatives(node, shapes=True, type="follicle"):
        return True
    try:
        return cmds.nodeType(node) != "joint" and not cmds.getAttr(node + ".inheritsTransform")
    except (RuntimeError, ValueError):
        return False


def _frame_of(c, controls):
    """The node a control's pose is measured against: up its parents, past what only channels move (driven keys,
    follows, the curl, lengths, earlier poses, group controls - a pose has to carry that), to the first the rig moves
    again by itself. None: the world."""
    p = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0]
    while p:
        if _redone(p, controls):
            return p
        p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
    return None


def _mul(a, b):
    """Two 4x4 matrices (16 numbers, Maya's row vectors): a then b."""
    return [sum(a[i * 4 + k] * b[k * 4 + j] for k in range(4)) for i in range(4) for j in range(4)]


def _inv(m):
    a = [list(m[i * 4:i * 4 + 4]) + [1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
    for c in range(4):
        piv = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        d = a[c][c] or 1e-12
        a[c] = [v / d for v in a[c]]
        for r in range(4):
            if r != c and a[r][c]:
                f = a[r][c]
                a[r] = [v - f * w for v, w in zip(a[r], a[c])]
    return [v for row in a for v in row[4:]]


def _measure(ctrls, frames=None):
    """The controls' world matrices, and their frames' (5.6.21: _frame_of)."""
    if frames is None:
        from gus_rigtool.core import on_top
        every = set(on_top.controls()) | set(ctrls)
        frames = dict((c, _frame_of(c, every)) for c in ctrls)
    return _snapshot(ctrls), dict((c, WT._wm(frames[c]) if frames.get(c) else IDENT) for c in ctrls)


def _knob_values():
    from gus_rigtool.core import face_sliders as FS
    out = {}
    for ks in FS.read().get("knobs", {}).values():
        for k in ks:
            for a in ("translateX", "translateY"):
                try:
                    out["%s.%s" % (k, a)] = cmds.getAttr("%s.%s" % (k, a))
                except (RuntimeError, ValueError):
                    pass
    return out


def save_pose(holder, pose, split=True, include_on=True, extra=None):
    """The face -> a pose. include_on (5.6.20): the face as you see it, the expressions that are on included (the
    board's knobs, sliders) - measured before anything is switched off; off: only what the controls themselves
    add. extra: more controls to take (moved ones without a face name). A save that stops part way is taken back by
    hand (5.6.19 used Maya's undo inside the button's own undo step - it could leave a layer half undone): the face
    as you posed it, the poses as they were."""
    hl = cmds.ls(holder, long=True)
    if not hl:
        raise RuntimeError("pick the control the sliders go on (Mouth_main_ctrl, or any face control).")
    ctrls = pose_controls(hl[0]) + [c for c in (extra or []) if c not in pose_controls(hl[0])]
    from gus_rigtool.core import on_top
    every = set(on_top.controls()) | set(ctrls)
    frames = dict((c, _frame_of(c, every)) for c in ctrls)
    seen = _measure(ctrls, frames) + (frames,) if include_on else None
    knobs = _knob_values()
    sliders = dict((sl, cmds.getAttr(sl)) for sl in _all_sliders(hl[0]) if cmds.objExists(sl))
    head = _board_off()
    ok = False
    try:
        got = _save_pose(hl[0], pose, split, seen=seen, extra=extra, sliders=sliders)
        ok = True
        return got
    finally:
        _board_on(cmds.ls(holder, long=True)[0] if cmds.ls(holder) else holder, head)
        if not ok:                                  # the knobs where they were
            for plug, v in knobs.items():
                try:
                    if cmds.objExists(plug.split(".")[0]) and cmds.getAttr(plug, settable=True):
                        cmds.setAttr(plug, v)
                except (RuntimeError, ValueError):
                    pass


def _save_pose(holder, pose, split=True, seen=None, extra=None, sliders=None):
    """The face (seen: as measured before - else as it is now, the sliders at 0) -> a pose (sliders on holder:
    <Pose>_L / _R, or <Pose>); the controls back to 0, the sliders too. A name that's there already is replaced -
    the new one is built first under a temporary name, the old one goes only when it's complete. One undo.
    Returns {'pose', 'attrs', 'controls'}."""
    holder = cmds.ls(holder, long=True)[0] if cmds.ls(holder) else None
    if not holder:
        raise RuntimeError("pick the control the sliders go on (Mouth_main_ctrl, or any face control).")
    name = _attr_name(pose)
    ctrls = pose_controls(holder) + [c for c in (extra or []) if c not in pose_controls(holder)]
    drivers = _drivers(holder) + [c for c in (extra or []) if c not in _drivers(holder)]
    replacing = name in read(holder)
    build = name + "_new" if replacing else name
    sliders = sliders if sliders is not None else dict((sl, cmds.getAttr(sl)) for sl in _all_sliders(holder)
                                                       if cmds.objExists(sl))
    made = {"nodes": [], "layers": [], "attrs": []}
    values = dict((p, cmds.getAttr(p)) for c in drivers for p in _channels(c) + _custom(c))
    with utils.undo_chunk("gusrigFacePose"):
        try:
            for sl in _all_sliders(holder):
                if cmds.objExists(sl) and cmds.getAttr(sl, settable=True):
                    cmds.setAttr(sl, 0)
            WT._settle()
            if seen:
                now, pnow, frames = seen
            else:
                from gus_rigtool.core import on_top
                every = set(on_top.controls()) | set(ctrls)
                frames = dict((c, _frame_of(c, every)) for c in ctrls)
                now, pnow = _measure(ctrls, frames)
            zero_drivers(drivers)
            WT._settle()
            rest, prest = _measure(ctrls, frames)
            # 5.6.21: each control against the first node above it the rig moves again by itself - the lids keep
            # their driven-key closing, the mouth its jaw follow, the tongue its curl, a ribbon's neighbours nothing
            # of what the ribbon gives them (5.6.20 kept that too: they moved twice), the ear's FK link its own turn
            moved = {}
            for c in ctrls:
                # where the control has to be: its pose relative to its frame, on the frame as it is at rest -
                # then measured in the axes of the node above its layer (the layer's own channels)
                target = _mul(_mul(now[c], _inv(pnow[c])), prest[c])
                par = _par(c)
                pm = WT._wm(par) if par else IDENT
                t, r = _delta(c, rest[c], target, pm, pm)
                if max(abs(v) for v in t + r) > EPS:
                    moved[c] = (t, r)
            if not moved:
                raise RuntimeError("the face is at rest: pose it first (the face controls and the group controls), "
                                   "then save.")
            xs = [rest[c][12] for c in ctrls]
            centre = (max(xs) + min(xs)) / 2.0              # the face's middle (half way between its sides)
            band = (max(xs) - min(xs)) * 0.08
            sides = ["L", "R"] if split else [""]
            attrs = []
            for suffix in sides:
                a = build + ("_" + suffix if suffix else "")
                if not cmds.attributeQuery(a, node=holder, exists=True):
                    cmds.addAttr(holder, longName=a, attributeType="double", defaultValue=0, minValue=0, maxValue=1,
                                 keyable=True)
                    made["attrs"].append(a)
                attrs.append(a)
            rec = {}
            # 5.6.19: the deepest first - a layer above a control changes the path of everything under it
            for c, (t, r) in sorted(moved.items(), key=lambda kv: -kv[0].count("|")):
                wl = _side_weight(rest[c][12], centre, band) if split else 1.0
                nodes = []
                for node in [c] + GC._copiers(c):
                    had = GC.layer_of(node)
                    lay, pt, pr = GC._add_layer(node, c)
                    if not had:
                        made["layers"].append(lay)
                    for a, share in zip(attrs, ([wl, 1.0 - wl] if split else [1.0])):
                        if share < EPS:
                            continue
                        for kind, vec, pma in (("t", t, pt), ("r", r, pr)):
                            if max(abs(v) for v in vec) < EPS:
                                continue
                            md = cmds.createNode("multiplyDivide", name="%s_%s_%s" % (a, _short(c), kind),
                                                 skipSelect=True)
                            made["nodes"].append(md)
                            cmds.setAttr(md + ".input1", *[v * share for v in vec], type="double3")
                            for ax in "XYZ":
                                cmds.connectAttr(holder + "." + a, md + ".input2" + ax)
                            cmds.connectAttr(md + ".output", "%s.input3D[%d]" % (pma, GC._free_index(pma)))
                            nodes.append(_short(md))
                rec[_short(c)] = {"t": t, "r": r, "left": round(wl, 3), "nodes": nodes}
            data = read(holder)
            data[build] = {"split": bool(split), "attrs": attrs, "ctrls": rec}
            _write(holder, data)
            if replacing:                                  # the new one is whole: the old one goes, the new one
                _remove_pose(holder, name)                 # takes its name
                final = []
                for a in attrs:
                    f = name + a[len(build):]
                    cmds.renameAttr(holder + "." + a, f)
                    final.append(f)
                data = read(holder)
                d = data.pop(build)
                d["attrs"] = final
                data[name] = d
                _write(holder, data)
                attrs = final
        except Exception as e:
            _take_back(holder, made, values, sliders)
            if isinstance(e, RuntimeError) and "at rest" in str(e):
                raise
            raise RuntimeError("couldn't save %s (%s) - nothing changed: the face is as you posed it, the poses as "
                               "they were." % (pose, e))
    return {"pose": name, "attrs": attrs, "controls": len(rec)}


def _take_back(holder, made, values, sliders):
    """What a stopped save made goes; the controls and sliders as they were."""
    from gus_rigtool.core import spaces
    for n in made["nodes"]:
        if cmds.objExists(n):
            cmds.delete(n)
    for lay in reversed(made["layers"]):
        if not cmds.objExists(lay):
            continue
        pmas = [x for x in (GC._sum_of(lay, "translate"), GC._sum_of(lay, "rotate")) if x]
        parent = (cmds.listRelatives(lay, parent=True, fullPath=True) or [None])[0]
        for k in cmds.listRelatives(lay, children=True, type="transform", fullPath=True) or []:
            spaces._parent_keeping(k, parent)
        cmds.delete(list(set(pmas)) + [lay])
    for a in made["attrs"]:
        if cmds.attributeQuery(a, node=holder, exists=True):
            cmds.deleteAttr(holder + "." + a)
    data = read(holder)
    for k in [k for k in data if k.endswith("_new") and any(a in made["attrs"] for a in data[k].get("attrs", []))]:
        data.pop(k)
    _write(holder, data)
    for p, v in list(values.items()) + list((sliders or {}).items()):
        try:
            if cmds.objExists(p.split(".")[0]) and cmds.getAttr(p, settable=True):
                cmds.setAttr(p, v)
        except (RuntimeError, ValueError):
            pass


def remove_pose(holder, pose):
    head = _board_off()
    try:
        return _remove_pose(holder, pose)
    finally:
        _board_on(cmds.ls(holder, long=True)[0], head)


def _remove_pose(holder, pose):
    holder = cmds.ls(holder, long=True)[0]
    data = read(holder)
    p = data.pop(_attr_name(pose), None)
    if not p:
        raise RuntimeError("no pose called %s on %s." % (pose, _short(holder)))
    for c in p["ctrls"].values():
        for n in c["nodes"]:
            if cmds.objExists(n):
                cmds.delete(n)
    for a in p["attrs"]:
        if cmds.attributeQuery(a, node=holder, exists=True):
            cmds.deleteAttr(holder + "." + a)
    _write(holder, data)
    GC._drop_empty_layers()
    return True


def edit_pose(holder, pose):
    """5.6.18: a saved pose back onto its controls, to change it: every slider to 0, the face controls to 0, then
    each of the pose's controls set to what the pose moved it (the face looks the same). Adjust, then Save pose with
    the same name - it replaces it. One undo. Returns {'pose', 'split', 'set', 'skipped'}."""
    head = _board_off()
    try:
        holder = cmds.ls(holder, long=True)[0]
        name = _attr_name(pose)
        d = read(holder).get(name)
        if not d:
            raise RuntimeError("no pose called %s on %s." % (pose, _short(holder)))
        out = {"pose": name, "split": bool(d.get("split")), "set": 0, "skipped": []}
        with utils.undo_chunk("gusrigEditPose"):
            for sl in _all_sliders(holder):
                try:
                    if cmds.getAttr(sl, settable=True):
                        cmds.setAttr(sl, 0)
                except (RuntimeError, ValueError):
                    pass
            zero_drivers(_drivers(holder))
            for c, rec in sorted(d.get("ctrls", {}).items()):
                got = cmds.ls(c, long=True) or []
                if len(got) != 1:
                    out["skipped"].append("%s (%s)" % (c, "not found" if not got else "more than one"))
                    continue
                missed = []
                for kind, vec in (("translate", rec.get("t") or [0, 0, 0]), ("rotate", rec.get("r") or [0, 0, 0])):
                    for ax, v in zip("XYZ", vec):
                        if abs(v) < EPS:
                            continue
                        plug = "%s.%s%s" % (got[0], kind, ax)
                        try:
                            if not cmds.getAttr(plug, settable=True):
                                raise RuntimeError
                            cmds.setAttr(plug, v)
                        except (RuntimeError, ValueError):
                            missed.append(kind[0] + ax.lower())
                if missed:
                    out["skipped"].append("%s (%s locked)" % (c, " ".join(missed)))
                out["set"] += 1
        return out
    finally:
        _board_on(cmds.ls(holder, long=True)[0], head)


def clean(holder):
    """5.6.17: poses whose sliders are gone (deleted by hand, or undone) leave the list, their leftover nodes
    with them. Returns the names dropped."""
    holder = (cmds.ls(holder, long=True) or [None])[0] if holder and cmds.objExists(holder) else None
    if not holder:
        return []
    data = read(holder)
    gone = [p for p, d in data.items()
            if not all(cmds.attributeQuery(a, node=holder, exists=True) for a in d.get("attrs", []))]
    for p in gone:
        d = data.pop(p)
        for c in d.get("ctrls", {}).values():
            for n in c.get("nodes", []):
                if cmds.objExists(n):
                    cmds.delete(n)
        for a in d.get("attrs", []):
            if cmds.attributeQuery(a, node=holder, exists=True):
                cmds.deleteAttr(holder + "." + a)
    if gone:
        _write(holder, data)
        GC._drop_empty_layers()
    return sorted(gone)


def poses(holder):
    return sorted(read(holder).keys()) if holder and cmds.objExists(holder) else []


def holders():
    return [n for n in cmds.ls(type="transform", long=True) or [] if cmds.attributeQuery(META, node=n, exists=True)]


# ---- selection sets ---------------------------------------------------------------------------------------------

def set_groups(mouth, face=None):
    """{set name: [controls]}: mouth_all, mouth_upper, mouth_lower, mouth_corners, mouth_groups, face_all."""
    mouth = [m for m in mouth if cmds.objExists(m)]
    out = {}
    if mouth:
        pos = dict((c, cmds.xform(c, query=True, worldSpace=True, translation=True)) for c in mouth)
        cy = sum(p[1] for p in pos.values()) / len(pos)
        by_x = sorted(mouth, key=lambda c: pos[c][0])
        corners = [by_x[0], by_x[-1]] if len(by_x) > 2 else []
        out["mouth_all"] = list(mouth)
        out["mouth_corners"] = corners
        out["mouth_upper"] = [c for c in mouth if c not in corners and pos[c][1] >= cy]
        out["mouth_lower"] = [c for c in mouth if c not in corners and pos[c][1] < cy]
    groups = [g for g in GC.all_groups() if any(w in _short(g).lower() for w in ("mouth", "lip"))]
    if groups:
        out["mouth_groups"] = groups
    face_all = list(dict.fromkeys(list(mouth) + list(face or []) + pose_controls()))
    if face_all:
        out["face_all"] = face_all
    return dict((k, v) for k, v in out.items() if v)


def make_sets(mouth, face=None):
    """The sets (made again when they exist), under gus_anim_sets. Returns {name: count}."""
    groups = set_groups(mouth, face)
    with utils.undo_chunk("gusrigFaceSets"):
        if not cmds.objExists(ANIM_SETS):
            cmds.sets(empty=True, name=ANIM_SETS)
        for name, members in groups.items():
            if cmds.objExists(name):
                cmds.delete(name)
            st = cmds.sets(members, name=name)
            cmds.sets(st, add=ANIM_SETS)
    return dict((k, len(v)) for k, v in groups.items())
