"""
Visibility switches (5.6.5): one control near the head with on / off switches for the animators -
Body_Ctrls, Face_Ctrls, Secondary_Ctrls, Joints, Geometry - and Geo_Display (Normal / Template / Reference).

A control switch hides the control's curve shapes, never its group: keys, constraints, IK / FK visibility and the
'hidden by a group' check don't change. Joints and Geometry use the group's drawing override (skeleton_grp,
geo_grp); display layers are left alone (5.6.7) - a group in one isn't driven.
Which switch a control is on is its connection - no list to keep up to date.

    from gus_rigtool.core import vis_switch
    vis_switch.make("Head_ctrl")              # the switch control above the head, every control sorted
    vis_switch.assign(["L_Brow_ctrl"], "Face_Ctrls")
"""

import re

import maya.cmds as cmds

# 5.6.18: the face's switches can move to a control of yours (the Hare's Face_settings_ctrl): Face_Ctrls (all of
# the face) and one per part, each part shown when both its own switch and Face_Ctrls are on
FACE_MARK = "gusFaceVis"
FACE_HEADER = "_Face_Vis"
# 5.6.22: finer - first match wins (the lid ribbon's controls before the lid masters, the pupils before the eyes,
# the mouth ribbon before the mouth)
FACE_PARTS = (("Eyelid_Ribbons", r"lids?_fol|lids?_ribbon"), ("Eyelids", r"lid"), ("Pupils", r"pupil|iris"),
              ("Eyes", r"(^|_)(l_|r_)?eyes?(_|$|\d)"), ("Brows", r"brow"), ("Tongue", r"tongue"),
              ("Mouth_Ribbon", r"(mouth|lips?)_fol|(mouth|lips?)_ribbon"),
              ("Mouth", r"mouth|lip|jaw|teeth|tooth|corner|smile|chin"), ("Facial_Ribbons", r"facial|cheek"),
              ("Nose", r"nose|nostril"), ("Ears", r"(^|_)ears?(_|$|\d)"), ("Other", r""))
# 5.6.22: the clothes (and the other secondary controls) one switch each, under Secondary_Ctrls
CLOTH_PARTS = (("Collar", r"collar"), ("Cape", r"cape"), ("Sleeves", r"sleeve"), ("Pants", r"pants|trouser"),
               ("Belt", r"belt"), ("Hood", r"hood"), ("Bandages", r"bandage"), ("Shirt", r"shirt"),
               ("Scarf", r"scarf"), ("Skirt", r"skirt"), ("Hair", r"hair"), ("Tail", r"tail"),
               ("Tweaks", r"tweak|bendy|bend"), ("Other_Secondary", r""))
PARTS_ATTR = "gusVisParts"          # on a holder: the part switches the tool made there (JSON list)
MASTER_ATTR = "gusVisMaster"        # on a part's node: the master switch it multiplies

from gus_rigtool.core import naming, utils

TOOL = "Visibility switches"
MARK = "gusVisSwitch"
MADE = "gusVisGear"
NAME = "Visibility_ctrl"
CTRL_SWITCHES = ("Body_Ctrls", "Face_Ctrls", "Secondary_Ctrls")
SWITCHES = CTRL_SWITCHES + ("Joints", "Geometry")
DISPLAY = "Geo_Display"
DISPLAY_TYPES = "Normal:Template:Reference"
SECONDARY = r"_fol_|ribbon|cape|collar|sleeve|pants|cloth|jiggle|bendy|belt|hood|skirt|bandage|hair|scarf|tweak"
LEVELS = r"^(Global|World|Local)_ctrl\d*$"


def _short(n):
    return naming.short_name(n)


def _long(n):
    got = cmds.ls(n, long=True) if n else []
    return got[0] if got else None


def find():
    """The switch control (the one carrying the mark), or None."""
    try:
        got = cmds.ls("*." + MARK, objectsOnly=True, long=True) or []
    except (RuntimeError, TypeError):
        got = []
    if not got:
        named = _long(NAME)
        got = [named] if named and cmds.attributeQuery(MARK, node=named, exists=True) else []
    return got[0] if got else None


def kind(ctrl):
    """'Face_Ctrls', 'Secondary_Ctrls' or 'Body_Ctrls' - by the control's name (face words first: the mouth and
    eyelid ribbons are face)."""
    from gus_rigtool.core import on_top
    name = _short(ctrl).lower()
    if on_top.is_face(ctrl):
        return "Face_Ctrls"
    if re.search(SECONDARY, name):
        return "Secondary_Ctrls"
    return "Body_Ctrls"


RIDER = "_squashRider"              # the head squash's hidden copy of a face curve (core/head_squash.RIDER)


def _shapes(ctrl):
    """The control's own curves - not its hidden intermediate shapes, not (5.6.23) the head squash's hidden copies
    (a switch on their visibility showed them: the uncoloured navy duplicates)."""
    return [s for s in cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve", fullPath=True) or []
            if not cmds.getAttr(s + ".intermediateObject") and RIDER not in _short(s)]


def fix_riders():
    """5.6.23: the head squash's hidden curve copies hidden again - a switch on their visibility disconnected, the
    visibility back to 0. Returns how many were fixed."""
    try:
        got = cmds.ls(type="nurbsCurve", long=True) or []
    except (RuntimeError, TypeError):
        got = []
    got = [s for s in got if RIDER in _short(s)]
    n = 0
    for s in got:
        src = cmds.listConnections(s + ".visibility", source=True, destination=False, plugs=True) or []
        for p in src:
            cmds.disconnectAttr(p, s + ".visibility")
        if src or cmds.getAttr(s + ".visibility"):
            try:
                cmds.setAttr(s + ".visibility", 0)
            except RuntimeError:
                continue
            n += 1
    return n


def controls():
    """Every control the switches are for: not the switch control itself, not Global / World / Local, not the
    control holding the face's switches."""
    from gus_rigtool.core import on_top
    sw = find()
    fh = face_holder()
    return [c for c in on_top.controls() if c not in (sw, fh) and not re.match(LEVELS, _short(c))]


def face_holder():
    """The control holding the face's switches (5.6.18), or None."""
    try:
        got = cmds.ls("*." + FACE_MARK, objectsOnly=True, long=True) or []
    except (RuntimeError, TypeError):
        got = []
    return got[0] if got else None


def part_of(ctrl, table):
    n = _short(ctrl).lower()
    for part, rx in table:
        if rx and re.search(rx, n):
            return part
    return table[-1][0]


def face_part(ctrl):
    return part_of(ctrl, FACE_PARTS)


def _prefix(master):
    return {"Face_Ctrls": "Face", "Secondary_Ctrls": "Secondary", "Body_Ctrls": "Body"}.get(master or "", "Custom")


def _part_node(part, master="Face_Ctrls"):
    return "%s_%s_vis_mdl" % (_prefix(master), part)


def _record_part(holder, part):
    import json
    if not cmds.attributeQuery(PARTS_ATTR, node=holder, exists=True):
        cmds.addAttr(holder, longName=PARTS_ATTR, dataType="string")
    got = json.loads(cmds.getAttr(holder + "." + PARTS_ATTR) or "[]")
    if part not in got:
        got.append(part)
        cmds.setAttr(holder + "." + PARTS_ATTR, json.dumps(got), type="string")


def recorded_parts(holder):
    import json
    if not holder or not cmds.attributeQuery(PARTS_ATTR, node=holder, exists=True):
        return []
    try:
        return json.loads(cmds.getAttr(holder + "." + PARTS_ATTR) or "[]")
    except ValueError:
        return []


def _part_plug(holder, part, master="Face_Ctrls"):
    """<Prefix>_<part>_vis_mdl.output = holder.<master> x holder.<part> (no master on the holder: the part alone) -
    made with the part's switch the first time."""
    if not cmds.attributeQuery(part, node=holder, exists=True):
        cmds.addAttr(holder, longName=part, attributeType="bool", defaultValue=True, keyable=True)
    _record_part(holder, part)
    node = _long(_part_node(part, master))
    if not node:
        node = cmds.createNode("multDoubleLinear", name=_part_node(part, master), skipSelect=True)
        cmds.addAttr(node, longName=MASTER_ATTR, dataType="string")
        cmds.setAttr(node + "." + MASTER_ATTR, master or "", type="string")
        if master and cmds.attributeQuery(master, node=holder, exists=True):
            cmds.connectAttr(holder + "." + master, node + ".input1")
        else:
            cmds.setAttr(node + ".input1", 1)
        cmds.connectAttr(holder + "." + part, node + ".input2")
    return node + ".output"


def _face_part_plug(holder, part):
    return _part_plug(holder, part, "Face_Ctrls")


def _is_part_source(node):
    n = _short(node)
    return n.endswith("_vis_mdl") and (n.startswith("Face_") or cmds.attributeQuery(MASTER_ATTR, node=node,
                                                                                    exists=True))


_is_face_source = _is_part_source


def _master_of(node):
    if cmds.attributeQuery(MASTER_ATTR, node=node, exists=True):
        return cmds.getAttr(node + "." + MASTER_ATTR) or None
    return "Face_Ctrls"


def part_nodes():
    """Every part switch's node the tool made (5.6.18 face ones too)."""
    return [n for n in cmds.ls(type="multDoubleLinear", long=True) or [] if _short(n).endswith("_vis_mdl") and
            _is_part_source(n)]


def switch_of(ctrl, sw=None):
    """The switch a control is on ('Face_Ctrls'...), or None."""
    sw = _short(sw or find() or "")
    for s in _shapes(ctrl):
        src = cmds.listConnections(s + ".visibility", source=True, destination=False, plugs=True) or []
        if src and _short(src[0].split(".")[0]) == sw:
            return src[0].split(".")[-1]
        if src and _is_part_source(src[0].split(".")[0]):
            return _master_of(src[0].split(".")[0]) or "Custom"
    return None


def unassigned():
    """Controls on no switch (only when there is a switch control) - shapes driven by something else don't count."""
    sw = find()
    if not sw:
        return []
    out = []
    for c in controls():
        shapes = _shapes(c)
        if shapes and not switch_of(c, sw) and not all(
                cmds.listConnections(x + ".visibility", source=True, destination=False) for x in shapes):
            out.append(c)
    return out


def _add_attrs(sw, which=None):
    """which (5.6.20): the switches to have - None: all of them."""
    which = list(SWITCHES) + [DISPLAY] if which is None else which
    if not cmds.attributeQuery(MARK, node=sw, exists=True):
        cmds.addAttr(sw, longName=MARK, attributeType="bool", defaultValue=True)
        cmds.setAttr(sw + "." + MARK, keyable=False, channelBox=False)
    for a in SWITCHES:
        if a == "Face_Ctrls" and face_holder():
            continue                                 # 5.6.18: the face's switches are on their own control
        if a in which and not cmds.attributeQuery(a, node=sw, exists=True):
            cmds.addAttr(sw, longName=a, attributeType="bool", defaultValue=True, keyable=True)
    if DISPLAY in which and not cmds.attributeQuery(DISPLAY, node=sw, exists=True):
        cmds.addAttr(sw, longName=DISPLAY, attributeType="enum", enumName=DISPLAY_TYPES, defaultValue=0,
                     keyable=True)


def _make_control(head):
    """Visibility_ctrl (a gear) above the head control, following it; channels locked and hidden."""
    from gus_rigtool.builder import controls as BC
    b = cmds.exactWorldBoundingBox(head)
    size = max(b[3] - b[0], b[5] - b[2], 1.0) * 0.25
    pos = [(b[0] + b[3]) / 2.0, b[4] + size * 2.0, (b[2] + b[5]) / 2.0]
    m = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, pos[0], pos[1], pos[2], 1.0]
    _off, c = BC.make("C", "Visibility", "gear", size, m, head, "Y", mirror=None, lock=())
    if _short(c) != NAME:
        c = cmds.rename(c, NAME)
    c = _long(c)
    # 5.6.20: open while you rig (place it, turn it, size it) - Publish locks it for the animators
    if not cmds.attributeQuery(MADE, node=c, exists=True):
        cmds.addAttr(c, longName=MADE, attributeType="bool", defaultValue=True)
        cmds.setAttr(c + "." + MADE, keyable=False, channelBox=False)
    return c


TRS = ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ")


def open_gear(sw):
    """5.6.20: the gear's move / turn / size open (5.6.5 - 5.6.19 locked them) - while you rig; Publish locks them."""
    for a in TRS:
        try:
            cmds.setAttr(sw + "." + a, lock=False)
            cmds.setAttr(sw + "." + a, keyable=True)
        except RuntimeError:
            pass


def made_by_tool(sw):
    """The gear the tool made (5.6.20 marks it; before, it was the one called Visibility_ctrl) - not your own
    control holding the switches."""
    return bool(sw) and (cmds.attributeQuery(MADE, node=sw, exists=True) or _short(sw) == NAME)


def _layer_of(node):
    """The display layer drawing node (its drawOverride comes from a layer), or None."""
    src = cmds.listConnections(node + ".drawOverride", source=True, destination=False) or []
    return src[0] if src and cmds.nodeType(src[0]) == "displayLayer" else None


def _drive_group(sw, group, attr, display=False):
    """group shown / hidden (and drawn normal / template / reference) by the switch, through its own drawing
    override. 5.6.7: a group in a display layer is left alone (the layer is yours - 5.6.5 drove the layer and took
    it over). Returns what it drove, or None."""
    if _layer_of(group):
        return None
    if not cmds.getAttr(group + ".overrideEnabled"):
        cmds.setAttr(group + ".overrideEnabled", 1)
    dst = group + (".overrideDisplayType" if display else ".overrideVisibility")
    src = cmds.listConnections(dst, source=True, destination=False, plugs=True) or []
    if src and _short(src[0].split(".")[0]) != _short(sw):
        return None
    cmds.connectAttr(sw + "." + attr, dst, force=True)
    return _short(group)


def release_layers(sw=None):
    """5.6.7: display layers the switches drive (5.6.5 connected Geo_Display to the layers under geo_grp, and a
    layer holding geo_grp to Geometry) let go - they're yours again, their settings as they are now. Returns the
    layers."""
    sw = sw or find()
    if not sw:
        return []
    out = []
    for a in SWITCHES + (DISPLAY,):
        if not cmds.attributeQuery(a, node=sw, exists=True):
            continue
        for d in cmds.listConnections(sw + "." + a, source=False, destination=True, plugs=True) or []:
            node = d.split(".")[0]
            if cmds.nodeType(node) == "displayLayer":
                cmds.disconnectAttr(sw + "." + a, d)
                if node not in out:
                    out.append(node)
    return out


def assign(ctrls, switch, sw=None):
    """Put the controls on a switch (their curve shapes' visibility from it). Shapes whose visibility something
    else drives are left alone. Returns (moved, skipped)."""
    if switch == "Face_Ctrls" and face_holder():
        return _assign_face(ctrls, face_holder())
    cloth = [p for p, _r in CLOTH_PARTS if p in recorded_parts(sw or find())]
    if switch == "Secondary_Ctrls" and cloth:          # 5.6.22: split into parts: onto the control's part
        moved, skipped = 0, []
        for c in ctrls:
            m, sk = _assign_part([c], sw or find(), part_of(c, CLOTH_PARTS), "Secondary_Ctrls")
            moved += m
            skipped += sk
        return moved, skipped
    sw = sw or find()
    if not sw:
        raise RuntimeError("make the visibility switches first.")
    if switch not in CTRL_SWITCHES:
        raise RuntimeError("%s isn't a control switch (%s)." % (switch, ", ".join(CTRL_SWITCHES)))
    moved, skipped = 0, []
    for c in ctrls:
        if c == sw:
            continue
        shapes = _shapes(c)
        done = False
        for s in shapes:
            src = cmds.listConnections(s + ".visibility", source=True, destination=False, plugs=True) or []
            if src and src[0].split(".")[0] != _short(sw):
                continue
            if cmds.getAttr(s + ".visibility", lock=True):
                continue
            cmds.connectAttr(sw + "." + switch, s + ".visibility", force=True)
            done = True
        if done:
            moved += 1
        elif shapes:
            skipped.append(c)
    return moved, skipped


def plan(head, on=None):
    """Lines: what make() will do."""
    by = {}
    for c in controls():
        by.setdefault(kind(c), []).append(c)
    from gus_rigtool.builder import names
    out = ["%s: already there - controls on no switch get sorted" % _short(find()) if find() else
           "the switches go on %s (your control)" % _short(on) if on else
           "%s: new, above %s (follows it; open while you rig, Publish locks it)" % (NAME, _short(head))]
    for k in CTRL_SWITCHES:
        out.append("%s: %d control(s)%s" % (k, len(by.get(k, [])), (" - e.g. " + ", ".join(
            _short(c) for c in by[k][:4])) if by.get(k) else ""))
    for k, g in (("Joints", names.make("C", "skeleton", "grp")), ("Geometry", names.make("C", "geo", "grp"))):
        n = _long(g)
        out.append("%s: %s" % (k, ((g + " (in display layer %s: left to you)" % _layer_of(n)) if _layer_of(n) else g)
                                   if n else "no %s - nothing" % g))
    return out


def make(head=None, which=None, on=None):
    """The switch control above head (made once) - or (5.6.20) on: a control of yours - with the switches in which
    (None: all); controls on no switch sorted (face words -> Face, ribbons / cloth -> Secondary, the rest -> Body),
    for the control switches it has. One undo. Returns {'control', 'controls': {switch: n}, 'skipped', 'groups'}."""
    from gus_rigtool.builder import names
    which = list(SWITCHES) + [DISPLAY] if which is None else list(which)
    sw = find()
    if not sw and on:
        sw = _long(on)
        if not sw:
            raise RuntimeError("%s isn't in the scene." % on)
    if not sw:
        head = _long(head)
        if not head:
            raise RuntimeError("select the head control: the switches go on a control just above it.")
    out = {"control": None, "controls": dict((k, 0) for k in CTRL_SWITCHES), "skipped": [], "groups": []}
    with utils.undo_chunk("gusrigVisSwitch"):
        if not sw:
            sw = _make_control(head)
        if made_by_tool(sw):
            open_gear(sw)
        _add_attrs(sw, which)
        out["control"] = sw
        out["released"] = release_layers(sw)
        sorted_ = {}
        for c in controls():
            if c != sw and not switch_of(c, sw):
                sorted_.setdefault(kind(c), []).append(c)
        for k, cs in sorted_.items():
            if not (cmds.attributeQuery(k, node=sw, exists=True) or (k == "Face_Ctrls" and face_holder())):
                continue                             # a switch you left out: its controls stay as they are
            n, skipped = assign(cs, k, sw)
            out["controls"][k] += n
            out["skipped"] += skipped
        for attr, g in (("Joints", names.make("C", "skeleton", "grp")), ("Geometry", names.make("C", "geo", "grp"))):
            n = _long(g)
            if n and cmds.attributeQuery(attr, node=sw, exists=True):
                got = _drive_group(sw, n, attr)
                if got:
                    out["groups"].append("%s -> %s" % (attr, got))
                elif _layer_of(n):
                    out["groups"].append("%s: %s is in display layer %s - left to you" % (attr, g, _layer_of(n)))
                if attr == "Geometry" and cmds.attributeQuery(DISPLAY, node=sw, exists=True):
                    got = _drive_group(sw, n, DISPLAY, display=True)
                    if got:
                        out["groups"].append("%s -> %s" % (DISPLAY, got))
        out["riders"] = fix_riders()
    return out


# ---------------------------------------------------------------------------
# 5.6.18: the face's switches on a control of yours; hand-made switches taken off
# ---------------------------------------------------------------------------

def _assign_face(ctrls, holder):
    """Controls onto their face part's switch (by name). Shapes driven by something other than a switch are left
    alone. Returns (moved, skipped)."""
    sw = _short(find() or "")
    moved, skipped = 0, []
    for c in ctrls:
        if c == holder:
            continue
        shapes = _shapes(c)
        plug = None
        done = False
        for x in shapes:
            src = cmds.listConnections(x + ".visibility", source=True, destination=False, plugs=True) or []
            if src and not (_short(src[0].split(".")[0]) == sw or _is_face_source(src[0].split(".")[0])):
                continue
            if cmds.getAttr(x + ".visibility", lock=True):
                continue
            plug = plug or _face_part_plug(holder, face_part(c))
            cmds.connectAttr(plug, x + ".visibility", force=True)
            done = True
        if done:
            moved += 1
        elif shapes:
            skipped.append(c)
    return moved, skipped


def face_plan(holder):
    """Lines: what move_face() will do - the parts and how many controls each."""
    holder = _long(holder)
    if not holder:
        raise RuntimeError("select the control the face's switches go on (e.g. Face_settings_ctrl).")
    sw = find()
    from gus_rigtool.core import on_top
    face = [c for c in controls() if c != holder and (switch_of(c, sw) == "Face_Ctrls" or
                                                      (not switch_of(c, sw) and on_top.is_face(c)))]
    by = {}
    for c in face:
        by.setdefault(face_part(c), []).append(c)
    out = ["%s gets Face_Ctrls (all of the face) and a switch per part:" % _short(holder)]
    for part, _rx in FACE_PARTS:
        if by.get(part):
            out.append("  %s: %d control(s) - e.g. %s" % (part, len(by[part]),
                                                         ", ".join(_short(c) for c in by[part][:3])))
    if sw and cmds.attributeQuery("Face_Ctrls", node=sw, exists=True):
        out.append("%s.Face_Ctrls goes (the other switches stay there)" % _short(sw))
    if switch_of(holder, sw):
        out.append("%s itself stays visible (it holds the switches)" % _short(holder))
    return out, face


def move_face(holder):
    """The face's switches onto holder: a header, Face_Ctrls, a switch per part (only parts with controls). The
    face controls on Visibility_ctrl's Face_Ctrls - and face controls on no switch - go onto their part. One undo.
    Returns {'holder', 'parts': {part: n}, 'skipped'}."""
    _lines, face = face_plan(holder)
    holder = _long(holder)
    sw = find()
    out = {"holder": holder, "parts": {}, "skipped": []}
    with utils.undo_chunk("gusrigFaceVis"):
        if not cmds.attributeQuery(FACE_MARK, node=holder, exists=True):
            cmds.addAttr(holder, longName=FACE_MARK, attributeType="bool", defaultValue=True)
            cmds.setAttr(holder + "." + FACE_MARK, keyable=False, channelBox=False)
        if not cmds.attributeQuery(FACE_HEADER, node=holder, exists=True):
            cmds.addAttr(holder, longName=FACE_HEADER, attributeType="enum", enumName="--------")
            cmds.setAttr(holder + "." + FACE_HEADER, keyable=False, channelBox=True)
            cmds.setAttr(holder + "." + FACE_HEADER, lock=True)
        if not cmds.attributeQuery("Face_Ctrls", node=holder, exists=True):
            cmds.addAttr(holder, longName="Face_Ctrls", attributeType="bool", defaultValue=True, keyable=True)
        for x in _shapes(holder):                       # the holder itself: always visible
            for src in cmds.listConnections(x + ".visibility", source=True, destination=False, plugs=True) or []:
                cmds.disconnectAttr(src, x + ".visibility")
            try:
                cmds.setAttr(x + ".visibility", 1)
            except RuntimeError:
                pass
        for part, _rx in FACE_PARTS:
            cs = [c for c in face if face_part(c) == part]
            if cs:
                n, skipped = _assign_face(cs, holder)
                out["parts"][part] = n
                out["skipped"] += skipped
        if sw and cmds.attributeQuery("Face_Ctrls", node=sw, exists=True):
            cmds.deleteAttr(sw + ".Face_Ctrls")
        _drop_empty_parts(holder)                       # 5.6.22: run again - the old Cheeks, Eyes... that got split
        out["riders"] = fix_riders()
    return out


def _drop_empty_parts(holder):
    """Part switches on holder whose node shows nothing any more: node and switch go."""
    for node in part_nodes():
        src = cmds.listConnections(node + ".input2", source=True, destination=False, plugs=True) or []
        if not src or _long(src[0].split(".")[0]) != holder:
            continue
        if cmds.listConnections(node + ".output", source=False, destination=True):
            continue
        attr = src[0].split(".")[-1]
        cmds.delete(node)
        if cmds.attributeQuery(attr, node=holder, exists=True) and not cmds.listConnections(holder + "." + attr,
                                                                                           destination=True):
            cmds.deleteAttr(holder + "." + attr)


def _header(holder, name):
    if not cmds.attributeQuery(name, node=holder, exists=True):
        cmds.addAttr(holder, longName=name, attributeType="enum", enumName="--------")
        cmds.setAttr(holder + "." + name, keyable=False, channelBox=True)
        cmds.setAttr(holder + "." + name, lock=True)


def _assign_part(ctrls, holder, part, master):
    """Controls onto one part switch. Shapes driven by something other than the tool's switches are left alone.
    Returns (moved, skipped)."""
    sw = _short(find() or "")
    moved, skipped = 0, []
    plug = None
    for c in ctrls:
        if c == holder:
            continue
        shapes = _shapes(c)
        done = False
        for x in shapes:
            src = cmds.listConnections(x + ".visibility", source=True, destination=False, plugs=True) or []
            if src and not (_short(src[0].split(".")[0]) in (sw, _short(holder)) or
                            _is_part_source(src[0].split(".")[0])):
                continue
            if cmds.getAttr(x + ".visibility", lock=True):
                continue
            plug = plug or _part_plug(holder, part, master)
            cmds.connectAttr(plug, x + ".visibility", force=True)
            done = True
        if done:
            moved += 1
        elif shapes:
            skipped.append(c)
    return moved, skipped


def secondary_plan(holder=None):
    """5.6.22: (lines, {part: [controls]}) - the secondary controls (clothes, tweaks...) one switch per part, under
    Secondary_Ctrls on holder (Visibility_ctrl by default)."""
    holder = _long(holder) or find()
    if not holder:
        raise RuntimeError("make the visibility switches first (or pick the control for the clothes' switches).")
    sw = find()
    by = {}
    for c in controls():
        if c == holder:
            continue
        on = switch_of(c, sw)
        if on == "Secondary_Ctrls" or (not on and kind(c) == "Secondary_Ctrls"):
            by.setdefault(part_of(c, CLOTH_PARTS), []).append(c)
    out = ["%s gets Secondary_Ctrls (all of them) and a switch per part:" % _short(holder)]
    for part, _rx in CLOTH_PARTS:
        if by.get(part):
            out.append("  %s: %d control(s) - e.g. %s" % (part, len(by[part]),
                                                         ", ".join(_short(c) for c in by[part][:3])))
    return out, by


def split_secondary(holder=None):
    """The secondary controls onto a switch per part (Collar, Cape, Sleeves, Pants...), each under
    Secondary_Ctrls. One undo. Returns {'holder', 'parts': {part: n}, 'skipped'}."""
    _lines, by = secondary_plan(holder)
    holder = _long(holder) or find()
    out = {"holder": holder, "parts": {}, "skipped": []}
    with utils.undo_chunk("gusrigSecondaryVis"):
        _header(holder, "_Secondary_Vis")
        if not cmds.attributeQuery("Secondary_Ctrls", node=holder, exists=True):
            cmds.addAttr(holder, longName="Secondary_Ctrls", attributeType="bool", defaultValue=True, keyable=True)
        for part, _rx in CLOTH_PARTS:
            if by.get(part):
                n, skipped = _assign_part(by[part], holder, part, "Secondary_Ctrls")
                out["parts"][part] = n
                out["skipped"] += skipped
        _drop_empty_parts(holder)
        out["riders"] = fix_riders()
    return out


def masters_on(holder):
    return [m for m in CTRL_SWITCHES if holder and cmds.attributeQuery(m, node=holder, exists=True)]


def add_switch(ctrls, name, holder, master=None):
    """5.6.22: a switch of your own - the selected controls on holder.<name>, under holder.<master> when given (one
    switch hides them all). One undo. Returns (moved, skipped)."""
    name = re.sub(r"\W+", "_", (name or "").strip()).strip("_")
    if not name:
        raise RuntimeError("give the switch a name (Sleeves, Cape, Fingers...).")
    if name[0].isdigit():
        name = "_" + name
    holder = _long(holder)
    if not holder:
        raise RuntimeError("pick the control the switch goes on.")
    ctrls = [c for c in ctrls if c != holder]
    if not ctrls:
        raise RuntimeError("select the controls the switch shows / hides.")
    taken = set(SWITCHES) | {DISPLAY, MARK, MADE, FACE_MARK, PARTS_ATTR}
    if name in taken or (cmds.attributeQuery(name, node=holder, exists=True) and name not in recorded_parts(holder)):
        raise RuntimeError("%s already has an attribute called %s - pick another name." % (_short(holder), name))
    with utils.undo_chunk("gusrigAddSwitch"):
        if master and not cmds.attributeQuery(master, node=holder, exists=True):
            master = None
        got = _assign_part(ctrls, holder, name, master)
        fix_riders()
        return got


VIS_PLUGS = ("visibility", "overrideVisibility", "lodVisibility")
DISPLAY_PLUGS = ("overrideDisplayType", "displayType")


def hand_switches(ctrl, only=None):
    """A control's own attributes that only show / hide things (every output a visibility) and nothing drives -
    [(attr, [what it drives])]. Not the tool's switches (Visibility_ctrl's, the face's). only: these names."""
    ctrl = _long(ctrl)
    parts = set(recorded_parts(ctrl))               # 5.6.22: a gear's own "Sleeves" is yours, not the tool's
    if ctrl in (find(), face_holder()):
        parts |= set(p for p, _r in FACE_PARTS + CLOTH_PARTS)
    ours = set(SWITCHES + (DISPLAY, MARK, FACE_MARK, FACE_HEADER, "Head_Squash", PARTS_ATTR)) | parts
    if only:                                         # 5.6.20: one of the tool's own, picked in the Channel Box
        ours = set((MARK, MADE, FACE_MARK, FACE_HEADER, "Head_Squash", PARTS_ATTR)) | parts
    out = []
    for a in cmds.listAttr(ctrl, userDefined=True) or []:
        if a in ours or (only and a not in only):
            continue
        try:
            if cmds.getAttr(ctrl + "." + a, type=True) not in ("bool", "long", "short", "byte", "double", "float",
                                                               "doubleLinear"):
                continue
        except (RuntimeError, ValueError):
            continue
        if cmds.listConnections(ctrl + "." + a, source=True, destination=False):
            continue
        dst = cmds.listConnections(ctrl + "." + a, source=False, destination=True, plugs=True) or []
        if dst and all(d.split(".")[-1] in VIS_PLUGS + (DISPLAY_PLUGS if only else ()) for d in dst):
            out.append((a, dst))
    return out


def remove_hand_switches(ctrls, only=None):
    """Those switches off the controls: what they hid shown again, the attributes gone, and a heading (an enum
    starting with '_', driving nothing) left with nothing under it goes too. One undo. Returns [(ctrl, attr, n)]."""
    done = []
    with utils.undo_chunk("gusrigRemoveVisSwitches"):
        for c in ctrls:
            c = _long(c)
            got = hand_switches(c, only)
            if not got:
                continue
            before = cmds.listAttr(c, userDefined=True) or []
            for a, dst in got:
                for d in dst:
                    try:
                        cmds.disconnectAttr(c + "." + a, d)
                        cmds.setAttr(d, 0 if d.split(".")[-1] in DISPLAY_PLUGS else 1)
                    except RuntimeError:
                        pass
                cmds.setAttr(c + "." + a, lock=False)
                cmds.deleteAttr(c + "." + a)
                done.append((_short(c), a, len(dst)))
            gone = set(a for a, _d in got)
            for i, a in enumerate(before):          # headings left with nothing under them
                if not a.startswith("_") or a in gone or not cmds.attributeQuery(a, node=c, exists=True):
                    continue
                if cmds.getAttr(c + "." + a, type=True) != "enum" or cmds.listConnections(c + "." + a):
                    continue
                under = []
                for b in before[i + 1:]:
                    if b.startswith("_") and cmds.attributeQuery(b, node=c, exists=True) and \
                            cmds.getAttr(c + "." + b, type=True) == "enum":
                        break
                    under.append(b)
                if under and all(b in gone for b in under):
                    cmds.setAttr(c + "." + a, lock=False)
                    cmds.deleteAttr(c + "." + a)
                    done.append((_short(c), a, 0))
    return done


def remove_all():
    """5.6.20: every switch the tool made goes - Visibility_ctrl's (the gear deleted when the tool made it, else the
    switches taken off your control) and the face's: every control, the joints and the geometry shown, drawn
    normal; the head squash stays on. One undo. Returns {'switches', 'gear_deleted', 'face'}."""
    sw = find()
    fh = face_holder()
    if not sw and not fh and not part_nodes():
        raise RuntimeError("no visibility switches in this scene.")
    out = {"switches": 0, "gear_deleted": False, "face": False}
    with utils.undo_chunk("gusrigVisRemove"):
        holders = set()
        for node in part_nodes():                       # 5.6.22: every part switch, wherever it is
            src = cmds.listConnections(node + ".input2", source=True, destination=False, plugs=True) or []
            for d in cmds.listConnections(node + ".output", source=False, destination=True, plugs=True) or []:
                cmds.disconnectAttr(node + ".output", d)
                try:
                    cmds.setAttr(d, 1)
                except RuntimeError:
                    pass
            cmds.delete(node)
            if src:
                h, attr = _long(src[0].split(".")[0]), src[0].split(".")[-1]
                holders.add(h)
                if h and cmds.attributeQuery(attr, node=h, exists=True):
                    cmds.deleteAttr(h + "." + attr)
        for h in holders:
            for a in ("_Secondary_Vis", PARTS_ATTR):
                if h and cmds.objExists(h) and cmds.attributeQuery(a, node=h, exists=True):
                    cmds.setAttr(h + "." + a, lock=False)
                    cmds.deleteAttr(h + "." + a)
        if fh:
            for a in ("Face_Ctrls", FACE_HEADER, FACE_MARK):
                if cmds.attributeQuery(a, node=fh, exists=True):
                    cmds.setAttr(fh + "." + a, lock=False)
                    cmds.deleteAttr(fh + "." + a)
            out["face"] = True
        if sw:
            for a in SWITCHES + (DISPLAY, "Head_Squash"):
                if not cmds.attributeQuery(a, node=sw, exists=True):
                    continue
                for d in cmds.listConnections(sw + "." + a, source=False, destination=True, plugs=True) or []:
                    keep = 0 if d.split(".")[-1] in DISPLAY_PLUGS else 1 if d.split(".")[-1] in VIS_PLUGS else \
                        cmds.getAttr(sw + "." + a)              # the squash's switch: as it is (on)
                    cmds.disconnectAttr(sw + "." + a, d)
                    try:
                        cmds.setAttr(d, keep)
                    except RuntimeError:
                        pass
                out["switches"] += 1
            if made_by_tool(sw):
                off = cmds.listRelatives(sw, parent=True, fullPath=True) or []
                cmds.delete(off[0] if off and len(cmds.listRelatives(off[0], children=True) or []) == 1 else sw)
                out["gear_deleted"] = True
            else:
                for a in SWITCHES + (DISPLAY, MARK, MADE):
                    if cmds.attributeQuery(a, node=sw, exists=True):
                        cmds.deleteAttr(sw + "." + a)
        out["riders"] = fix_riders()               # 5.6.23: shown again above - the squash's copies hidden again
    return out


def all_switch_holders():
    """Controls holding switches: Visibility_ctrl, the face's, and any with switches of your own."""
    out = [h for h in (find(), face_holder()) if h]
    for node in part_nodes():
        src = cmds.listConnections(node + ".input2", source=True, destination=False) or []
        h = _long(src[0]) if src else None
        if h and h not in out:
            out.append(h)
    return out
