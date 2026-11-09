"""
Space switches on any control (hand-made rigs too): a 'space' group above the control follows one of
the targets, picked by an enum attribute on the control. Gus Animtool switches it with no jump, like the
builder's own spaces (it works on any enum attribute).

    from gus_rigtool.core import spaces
    spaces.make("L_hand_IK_ctrl", [("world", "world_ctrl"), ("chest", "chest_ctrl")])

What was made is written on the control (gusSpaceSwitch), so Remove / Add target find it again.
"""

import json

import maya.cmds as cmds

from gus_rigtool.core import naming
from gus_rigtool.core import nodes as _nodes

META = "gusSpaceSwitch"
KINDS = ["parent", "orient", "point"]


_short = _nodes.short


_long = _nodes.unique_long


def default_label(node):
    """'L_chest_ctrl' -> 'chest', 'World_ctrl' -> 'World'."""
    label = naming.label_of(_short(node)) or _short(node)
    for centre in ("C_", "M_", "c_", "m_", "Ctr_", "Mid_"):
        if label.startswith(centre) and len(label) > len(centre):
            return label[len(centre):]
    return label


def parse(text):
    """'label = node' lines (or comma separated) -> [(label, node)]."""
    out = []
    for item in text.replace(";", "\n").replace(",", "\n").splitlines():
        if "=" in item:
            label, node = [x.strip() for x in item.split("=", 1)]
            if label and node:
                out.append((label, node))
    return out


def piece_of(ctrl):
    """What goes under the space group: the control's parent when it is an empty group holding only
    the control (its offset group), else the control itself."""
    parent = (cmds.listRelatives(ctrl, parent=True, fullPath=True) or [None])[0]
    if parent and not cmds.listRelatives(parent, shapes=True) and \
            len(cmds.listRelatives(parent, children=True, type="transform") or []) == 1 and \
            cmds.nodeType(parent) == "transform":
        return parent
    return _long(ctrl)


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


def _constraint_fn(kind):
    """Always a parent constraint (one offset per target, so switching never jumps or turns); orient / point
    skip the translate / rotate channels."""
    skip = {"orient": {"skipTranslate": ["x", "y", "z"]}, "point": {"skipRotate": ["x", "y", "z"]}}.get(kind, {})

    def fn(*args, **kw):
        if not kw.get("query") and not kw.get("edit"):
            kw = dict(skip, **kw)
        return cmds.parentConstraint(*args, **kw)
    return fn


CHANNELS = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")


def _unlock(node):
    """5.6.7: the node's locked channels unlocked (Maya can't re-parent a node keeping its place when its channels
    are locked - it keeps the old values, measured from the old parent: the Hare's builder offsets are all locked,
    the arm jumped 9.33). Returns them, to lock again."""
    out = []
    for a in CHANNELS:
        try:
            if cmds.getAttr(node + "." + a, lock=True):
                cmds.setAttr(node + "." + a, lock=False)
                out.append(a)
        except (RuntimeError, ValueError):
            pass
    return out


def _relock(node, channels):
    for a in channels:
        try:
            cmds.setAttr(node + "." + a, lock=True)
        except (RuntimeError, ValueError):
            pass


def _parent_keeping(piece, parent):
    """piece under parent (None: the world), where it is, even with locked channels. Returns its new path."""
    locked = _unlock(piece)
    name = _short(piece)
    got = cmds.parent(piece, parent) if parent else cmds.parent(piece, world=True)
    new = cmds.ls(got[0], long=True)[0] if got else (_long(name) or piece)
    _relock(new, locked)
    return new


def _under(node, top):
    n, t = _long(node), _long(top)
    return bool(n and t and n.startswith(t + "|"))


def _check(ctrl, targets, attr):
    if not _long(ctrl):
        raise RuntimeError("'%s' not found (or several nodes have that name)." % ctrl)
    if len(targets) < 2:
        raise RuntimeError("a space switch needs 2 targets or more.")
    labels = [lb for lb, _n in targets]
    if len(set(labels)) != len(labels):
        raise RuntimeError("two targets have the same label.")
    for label, node in targets:
        if not _long(node):
            raise RuntimeError("target '%s' (%s) not found, or several nodes have that name." % (node, label))
        if _long(node) == _long(ctrl):
            raise RuntimeError("the control can't be its own space.")
        if _under(node, piece_of(ctrl)):              # 5.6.7: a loop - the rig would spin (the Hare turned 90)
            raise RuntimeError("target '%s' is inside %s's own hierarchy: it would follow itself. Is %s really the "
                               "control? (select it alone and press '< sel')" % (_short(node), _short(ctrl),
                                                                                  _short(ctrl)))
    if read(ctrl):
        raise RuntimeError("%s already has a space switch - Remove it first, or Add targets to it." % _short(ctrl))
    if cmds.attributeQuery(attr, node=ctrl, exists=True):
        raise RuntimeError("%s already has an attribute '%s' - pick another name." % (_short(ctrl), attr))


def _condition(ctrl, attr, i, weight_plug):
    cond = cmds.createNode("condition", name="%s_%s%d_cond" % (naming.strip_type_suffix(_short(ctrl)), attr, i))
    cmds.connectAttr(ctrl + "." + attr, cond + ".firstTerm")
    cmds.setAttr(cond + ".secondTerm", i)
    cmds.setAttr(cond + ".colorIfTrueR", 1)
    cmds.setAttr(cond + ".colorIfFalseR", 0)
    cmds.connectAttr(cond + ".outColorR", weight_plug)
    return cond


def make(ctrl, targets, kind="parent", attr="space", default=0):
    """Make the switch. targets: [(label, node)]. Returns the space group. 5.6.7: works on locked groups (the
    builder's); checked - if the control moved, the switch is taken off again and it says so."""
    attr = attr.strip() or "space"
    _check(ctrl, targets, attr)
    before = cmds.xform(_long(ctrl), query=True, worldSpace=True, matrix=True)
    grp = _make(ctrl, targets, kind, attr, default)
    after = cmds.xform(_long(_short(ctrl)), query=True, worldSpace=True, matrix=True)
    off = max(abs(a - b) for a, b in zip(before, after))
    if off > 1e-3:
        remove(_short(ctrl))
        raise RuntimeError("making the switch moved %s (by %.3g) - taken off again, nothing changed. Send this to "
                           "Gus." % (_short(ctrl), off))
    return grp


def _make(ctrl, targets, kind, attr, default):
    ctrl = _long(ctrl)
    ctrl_name = _short(ctrl)
    piece = piece_of(ctrl)
    parent = (cmds.listRelatives(piece, parent=True, fullPath=True) or [None])[0]
    grp = cmds.createNode("transform", name=naming.unique(naming.strip_type_suffix(ctrl_name) + "_space_grp"))
    cmds.xform(grp, worldSpace=True, matrix=cmds.xform(piece, query=True, worldSpace=True, matrix=True))
    if parent:
        grp = cmds.parent(grp, parent)[0]
    grp = cmds.ls(grp, long=True)[0]
    _parent_keeping(piece, grp)
    ctrl = _long(ctrl_name) or ctrl
    grp = _long(_short(grp)) or grp
    fn = _constraint_fn(kind)
    con = fn([_long(n) for _l, n in targets], grp, maintainOffset=True)[0]
    if kind != "point":
        try:
            cmds.setAttr(con + ".interpType", 2)                 # shortest: no flips between targets
        except RuntimeError:
            pass
    default = max(0, min(len(targets) - 1, int(default)))
    cmds.addAttr(ctrl, longName=attr, attributeType="enum", enumName=":".join(lb for lb, _n in targets),
                 defaultValue=default, keyable=True)
    cmds.setAttr(ctrl + "." + attr, default)
    aliases = fn(con, query=True, weightAliasList=True) or []
    conds = [_condition(ctrl, attr, i, con + "." + alias) for i, alias in enumerate(aliases)]
    _write(ctrl, {"attr": attr, "kind": kind, "group": _short(grp), "constraint": _short(con),
                  "conditions": [_short(c) for c in conds], "piece": _short(piece),
                  "targets": [[lb, _short(n)] for lb, n in targets]})
    return grp


def add_target(ctrl, label, node):
    """One more target on an existing switch (at the end of the menu)."""
    data = read(ctrl)
    if not data:
        raise RuntimeError("%s has no space switch made here." % _short(ctrl))
    if label in [lb for lb, _n in data["targets"]]:
        raise RuntimeError("the switch already has a target called '%s'." % label)
    if not _long(node):
        raise RuntimeError("'%s' not found." % node)
    grp, con = _long(data["group"]), _long(data["constraint"])
    if not grp or not con:
        raise RuntimeError("the switch's group or constraint is gone - Remove it and make it again.")
    fn = _constraint_fn(data["kind"])
    attr = data["attr"]
    plug = _long(ctrl) + "." + attr
    current = cmds.getAttr(plug)
    world = cmds.xform(grp, query=True, worldSpace=True, matrix=True)
    fn(_long(node), grp, maintainOffset=True)
    cmds.xform(grp, worldSpace=True, matrix=world)
    names = [lb for lb, _n in data["targets"]] + [label]
    cmds.addAttr(plug, edit=True, enumName=":".join(names))
    aliases = fn(con, query=True, weightAliasList=True) or []
    i = len(names) - 1
    if len(aliases) > i:
        data["conditions"].append(_short(_condition(_long(ctrl), attr, i, con + "." + aliases[i])))
    data["targets"].append([label, _short(node)])
    _write(_long(ctrl), data)
    cmds.setAttr(plug, current)
    return i


def remove(ctrl):
    """Take the switch off: the control goes back under its old parent, where it is now (no jump), and
    the group, constraint, condition nodes and the attribute are deleted."""
    data = read(ctrl)
    if not data:
        raise RuntimeError("%s has no space switch made here." % _short(ctrl))
    ctrl = _long(ctrl)
    grp = _long(data["group"])
    piece = _long(data["piece"]) or ctrl
    if grp and piece:
        parent = (cmds.listRelatives(grp, parent=True, fullPath=True) or [None])[0]
        _parent_keeping(piece, parent)
    for c in data.get("conditions", []):
        if _long(c):
            cmds.delete(_long(c))
    if grp and _long(data["group"]):
        cmds.delete(_long(data["group"]))
    ctrl = _long(_short(ctrl)) or ctrl
    plug = ctrl + "." + data["attr"]
    if cmds.attributeQuery(data["attr"], node=ctrl, exists=True):
        cmds.setAttr(plug, lock=False)
        cmds.deleteAttr(plug)
    cmds.deleteAttr(ctrl + "." + META)
    return data


def switch(ctrl, index, attr=None):
    """Change space with no jump: the control stays where it is."""
    data = read(ctrl) or {}
    attr = attr or data.get("attr", "space")
    ctrl = _long(ctrl)
    m = cmds.xform(ctrl, query=True, worldSpace=True, matrix=True)
    cmds.setAttr(ctrl + "." + attr, index)
    cmds.xform(ctrl, worldSpace=True, matrix=m)


# ---- 5.6.7: the usual spaces in one go -------------------------------------------------------------------------

LEG_WORDS = ("ankle", "foot", "leg", "toe", "ball", "heel")
ARM_WORDS = ("wrist", "hand", "arm", "palm")


def _ctrl_named(*candidates):
    """The control (a transform with a curve) whose name is one of these, any case - the first found."""
    want = [c.lower() for c in candidates if c]
    found = {}
    for s in cmds.ls(type="nurbsCurve", long=True) or []:
        t = (cmds.listRelatives(s, parent=True, fullPath=True) or [None])[0]
        if t:
            found.setdefault(_short(t).lower(), []).append(t)
    for w in want:
        got = found.get(w)
        if got and len(set(got)) == 1:
            return got[0]
    return None


def _targets(pairs):
    """[(label, node)] for the targets found (label from the node's name when not given)."""
    out = []
    for label, node in pairs:
        if node and node not in [n for _l, n in out]:
            out.append((label or default_label(node), node))
    return out


def standard_plan():
    """[(control, [(label, target)], kind)]: the usual spaces for the rig's limbs (from what the builder wrote on
    each limb's settings control) - IK feet: world / COG / hips; knee pole vectors: foot / world / COG; arm pole
    vectors: chest / world / hand; FK arms (orient): chest / COG / world. Controls with a switch already, and
    targets the rig doesn't have, are left out."""
    from gus_rigtool.builder import names
    from gus_rigtool.core import utils, world_levels
    try:
        world = world_levels.levels().get("world")
    except Exception:
        world = None
    world = world or _ctrl_named("World_ctrl", names.make("C", "world", "ctrl"))
    cog = _ctrl_named("COG_ctrl", names.make("C", "COG", "ctrl"), "C_cog_ctrl")
    chest = _ctrl_named("Chest_ctrl", names.make("C", "chest", "ctrl"))
    hips = _ctrl_named("Waist_ctrl", "Hips_ctrl", names.make("C", "hips", "ctrl"), "Pelvis_ctrl")
    out = []

    def add(ctrl, pairs, kind):
        ctrl = _long(_short(ctrl)) if ctrl else None
        if not ctrl or read(ctrl) or cmds.attributeQuery("space", node=ctrl, exists=True):
            return
        t = [(lb, _short(n)) for lb, n in _targets(pairs) if n != ctrl and not _under(n, piece_of(ctrl))]
        if len(t) >= 2:                   # names, not paths: a switch made earlier in the plan moves a target
            out.append((_short(ctrl), t, kind))

    for st in sorted(utils.nodes_with_attr("gusIkCtrl")):
        get = lambda key: [x for x in (cmds.getAttr(st + "." + key) or "").split() if x] \
            if cmds.attributeQuery(key, node=st, exists=True) else []
        ik = (get("gusIkCtrl") or [None])[0]
        pv = (get("gusPvCtrl") or [None])[0]
        fk = get("gusFkCtrls")
        if not ik:
            continue
        low = ik.lower()
        ik_l = _long(ik)
        if any(w in low for w in LEG_WORDS):
            add(ik, [(None, world), ("COG", cog), (None, hips)], "parent")
            add(pv, [("Foot", ik_l), (None, world), ("COG", cog)], "parent")
        elif any(w in low for w in ARM_WORDS):
            add(pv, [(None, chest), (None, world), ("Hand", ik_l)], "parent")
            top = [c for c in fk if "clav" not in c.lower()]
            if top:
                add(top[0], [(None, chest), ("COG", cog), (None, world)], "orient")
    return out


def standard(plan=None):
    """Make the standard spaces (standard_plan, or the plan given). Returns (made, [(control, why)])."""
    made, failed = [], []
    for ctrl, targets, kind in plan if plan is not None else standard_plan():
        try:
            make(ctrl, targets, kind)
            made.append(_short(ctrl))
        except RuntimeError as e:
            failed.append((_short(ctrl), str(e)))
    return made, failed
