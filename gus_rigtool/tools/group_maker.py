"""
Groups: make groups named after the selected objects, with your own suffix.

    import gus_rigtool.main as gr; gr.show_tool("groups")

Suffix field
  One suffix ("_grp") = one group. Several, comma separated ("_zero, _sdk, _offset") =
  stacked groups, top to bottom. Preset buttons add their suffix; Clear empties it.
Place
  Match & zero : the group matches the object; the object's translate / rotate become 0.
  Keep values  : the group sits at the parent's origin; the object keeps its values.
Name
  Add suffix     : L_arm_ctrl -> L_arm_ctrl_grp
  Replace suffix : L_arm_ctrl -> L_arm_grp   (removes the last "_part")
Mode
  Each       : every object gets its own group(s).
  Shared grp : one neutral group (zero values) holding all the objects. Nothing moves.
  Make set   : no parenting; a Maya set with the objects.

4.1.0
  Stacks       : one click fills a whole stack ("Control: _offset, _sdk, _driven"); save your own.
  Place        : At last selected - the groups go on the last selected object (its pivot and axes).
  Where        : Above the object (as before) or Above its parent (a new group between the parent and
                 the grandparent, matching the parent: e.g. an _sdk above an existing _offset).
  Remove group : the selected groups go; their children stay exactly where they are.
"""

import maya.cmds as cmds

from gus_rigtool.core import colors, naming, sides, ui, utils
from gus_rigtool.core import nodes as _nodes

TOOL = "Groups"
SETTINGS_KEY = "groups"
PRESETS = ("_grp", "_offset", "_ctrl_offset", "_zero", "_sdk", "_auto", "_driven")
EPSILON = 1e-5

DEFAULTS = {
    "suffix": "_grp",
    "place": 1,
    "name": 1,
    "mode": 1,
    "side_color": False,
    "where": 1,
}
# ready-made stacks (top first); yours are saved under 'groupStacks'
STACKS = [("Offset", "_offset"), ("Zero + offset", "_zero, _offset"), ("Control", "_offset, _sdk, _driven"),
          ("Offset + SDK", "_offset, _sdk"), ("Auto", "_offset, _auto")]
STACKS_KEY = "groupStacks"

_P, N, _w, _guard = ui.tool_helpers("p_groups_", TOOL)


# ---------------------------------------------------------------------------
# naming
# ---------------------------------------------------------------------------

def parse_suffixes(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if part:
            out.append(part if part.startswith("_") else "_" + part)
    return out


def make_name(obj, suffix, replace):
    ns, base = naming.split_namespace(obj)
    if replace and "_" in base:
        base = base.rsplit("_", 1)[0]
    return ns + base + suffix


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_parent = _nodes.parent_of


def _new_group(name, parent):
    if parent:
        grp = cmds.group(empty=True, name=naming.unique(name), parent=parent)
    else:
        grp = cmds.group(empty=True, name=naming.unique(name), world=True)
    return utils.uuid(grp)


def _match_matrix(obj):
    """obj's world rotation (no scale) at its pivot (the shared mirror engine's maths)."""
    from gus_rigtool.core import mirror_engine
    world = cmds.xform(obj, query=True, worldSpace=True, matrix=True)
    _t, rot, _s = mirror_engine.decompose(world)
    return mirror_engine.compose(cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True), rot)


def _clean_zeros(obj):
    attrs = ["translate", "rotate"] + (["jointOrient"] if cmds.nodeType(obj) == "joint" else [])
    for attr in attrs:
        for axis in "XYZ":
            plug = "%s.%s%s" % (obj, attr, axis)
            try:
                if abs(cmds.getAttr(plug)) < EPSILON and cmds.getAttr(plug, settable=True):
                    cmds.setAttr(plug, 0)
            except (RuntimeError, ValueError):
                pass


def _zero_joint(joint):
    try:
        if all(abs(v) < EPSILON for v in cmds.getAttr(joint + ".rotateAxis")[0]):
            for attr in ("rotate", "jointOrient"):
                if cmds.getAttr(joint + "." + attr, settable=True):
                    cmds.setAttr(joint + "." + attr, 0, 0, 0)
    except RuntimeError:
        pass


def _outliner_side_color(group_id, obj):
    """Colour a group's name in the Outliner by the object's side (nothing in the viewport)."""
    grp = utils.path(group_id)
    side = sides.side_of_node(obj)
    if side == "C":
        return
    rgb = colors.side_colors()[side]
    try:
        cmds.setAttr(grp + ".useOutlinerColor", 1)
        cmds.setAttr(grp + ".outlinerColor", *rgb)
    except RuntimeError:
        pass


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------

def stacks():
    """[(name, suffixes text)]: the ready-made ones, then yours."""
    mine = utils.load_setting(STACKS_KEY, {}) or {}
    return list(STACKS) + sorted(mine.items())


def save_stack(name, text):
    name = (name or "").strip()
    if not name or not parse_suffixes(text):
        raise RuntimeError("give the stack a name and at least one suffix.")
    mine = utils.load_setting(STACKS_KEY, {}) or {}
    mine[name] = ", ".join(parse_suffixes(text))
    utils.save_setting(STACKS_KEY, mine)
    return name


def delete_stack(name):
    mine = utils.load_setting(STACKS_KEY, {}) or {}
    if name not in mine:
        raise RuntimeError("'%s' is a ready-made stack (only yours can be deleted)." % name)
    del mine[name]
    utils.save_setting(STACKS_KEY, mine)


def insert_above_parent(obj_ids, suffixes, replace, side_color=False):
    """A new group (stack) between each object's parent and the grandparent, matching the parent; the parent
    keeps its place in the world. Named after the parent. Returns the new top groups."""
    tops = []
    done = set()
    for obj_id in obj_ids:
        obj = utils.path(obj_id)
        parent = _parent(obj) if obj else None
        if not parent:
            utils.warn(TOOL, "'%s' has no parent to put a group above." % naming.short_name(obj or obj_id))
            continue
        if parent in done:
            continue
        done.add(parent)
        pid = utils.uuid(parent)
        group_ids, current = [], _parent(parent)
        for suffix in suffixes:
            gid = _new_group(make_name(parent, suffix, replace), current)
            group_ids.append(gid)
            current = utils.path(gid)
        top = utils.path(group_ids[0])
        cmds.xform(top, worldSpace=True, matrix=_match_matrix(parent))
        for gid in group_ids[1:]:
            cmds.xform(utils.path(gid), worldSpace=True, matrix=_match_matrix(parent))
        try:
            cmds.parent(utils.path(pid), utils.path(group_ids[-1]))
        except RuntimeError as err:
            cmds.delete(top)
            utils.warn(TOOL, "could not group '%s' (%s)." % (naming.short_name(parent), str(err).strip()))
            continue
        if side_color:
            for gid in group_ids:
                _outliner_side_color(gid, utils.path(pid))
        tops.append(utils.path(group_ids[0]))
    return tops


def remove_groups(groups):
    """Delete groups; their children go to the group's parent and stay where they are in the world.
    Skips nodes that aren't plain groups (with a shape, a joint, or driven by connections). Returns
    (removed names, skipped [(name, why)])."""
    removed, skipped = [], []
    for g in groups:
        gid = utils.uuid(g)
        g = utils.path(gid)
        if not g:
            continue
        why = None
        if cmds.nodeType(g) != "transform":
            why = "not a group (%s)" % cmds.nodeType(g)
        elif cmds.listRelatives(g, shapes=True):
            why = "has a shape"
        else:
            driven = [a for a in ("translate", "rotate", "scale")
                      if cmds.listConnections("%s.%s" % (g, a), source=True, destination=False)]
            if driven:
                why = "its %s is driven (constraint / connection)" % "/".join(driven)
        if why:
            skipped.append((naming.short_name(g), why))
            continue
        up = _parent(g)
        kids = cmds.listRelatives(g, children=True, fullPath=True, type="transform") or []
        for k in kids:
            if cmds.nodeType(k).endswith("Constraint"):
                continue
            if up:
                cmds.parent(k, up)
            else:
                cmds.parent(k, world=True)
        removed.append(naming.short_name(g))
        cmds.delete(utils.path(gid))
    return removed, skipped


def group_each(obj_ids, suffixes, replace, match, side_color, target=None):
    """target: a node the top group matches instead of each object (Place: At last selected)."""
    tops = []
    for obj_id in obj_ids:
        obj = utils.path(obj_id)
        if not obj:
            continue
        group_ids, current = [], _parent(obj)
        for suffix in suffixes:
            gid = _new_group(make_name(obj, suffix, replace), current)
            group_ids.append(gid)
            current = utils.path(gid)
        top = utils.path(group_ids[0])
        if target:
            cmds.xform(top, worldSpace=True, matrix=_match_matrix(target))
        elif match:
            cmds.xform(top, worldSpace=True, matrix=_match_matrix(obj))
        try:
            cmds.parent(obj, utils.path(group_ids[-1]))
        except RuntimeError as err:
            cmds.delete(top)
            utils.warn(TOOL, "could not group '%s' (%s)." % (naming.short_name(obj), str(err).strip()))
            continue
        obj = utils.path(obj_id)
        if match and not target:
            if cmds.nodeType(obj) == "joint":
                _zero_joint(obj)
            _clean_zeros(obj)
            if any(abs(v) > EPSILON for v in cmds.getAttr(obj + ".rotatePivot")[0]):
                utils.warn(TOOL, "'%s' has frozen transforms / a moved pivot, so its translate "
                                 "is not zero." % naming.short_name(obj))
        if side_color:
            for gid in group_ids:
                _outliner_side_color(gid, obj)
        tops.append(utils.path(group_ids[0]))
    return tops


def group_shared(obj_ids, suffixes, replace, side_color):
    paths = [utils.path(o) for o in obj_ids if utils.path(o)]
    parents = {_parent(p) for p in paths}
    common = parents.pop() if len(parents) == 1 else None
    group_ids, current = [], common
    for suffix in suffixes:
        gid = _new_group(make_name(paths[0], suffix, replace), current)
        group_ids.append(gid)
        current = utils.path(gid)
    try:
        cmds.parent([utils.path(o) for o in obj_ids], utils.path(group_ids[-1]))
    except RuntimeError as err:
        cmds.delete(utils.path(group_ids[0]))
        utils.warn(TOOL, "could not group the selection (%s)." % str(err).strip())
        return []
    if common is None and len(paths) > 1:
        utils.warn(TOOL, "objects had different parents, so the group went under the world. "
                         "Their positions are kept.")
    if side_color:
        first = utils.path(obj_ids[0])                 # its path changed when it was parented
        for gid in group_ids:
            _outliner_side_color(gid, first)
    return [utils.path(group_ids[0])]


def make_set(obj_ids, suffixes, replace):
    paths = [utils.path(o) for o in obj_ids if utils.path(o)]
    if len(suffixes) > 1:
        utils.warn(TOOL, "sets use only the first suffix ('%s')." % suffixes[0])
    return cmds.sets(paths, name=naming.unique(make_name(paths[0], suffixes[0], replace)))


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def _ui():
    return {
        "suffix": cmds.textFieldGrp(N("Suffix"), query=True, text=True),
        "place": cmds.radioButtonGrp(N("Place"), query=True, select=True),
        "name": cmds.radioButtonGrp(N("Name"), query=True, select=True),
        "mode": cmds.radioButtonGrp(N("Mode"), query=True, select=True),
        "side_color": cmds.checkBox(N("SideColor"), query=True, value=True),
        "where": cmds.radioButtonGrp(N("Where"), query=True, select=True),
    }


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _selected_objects():
    return [n for n in utils.selected_transforms(ordered=True)]


def _short(n):
    return naming.short_name(n).split(":")[-1]


def preview(*_):
    if not cmds.text(N("Preview"), exists=True):
        return
    try:
        o = _ui()
    except RuntimeError:
        return
    cmds.text(N("Preview"), edit=True, label=preview_text(o, _selected_objects()))


def _taken(name):
    return bool(cmds.ls(name))


def preview_text(o, objs):
    """Exactly what Create will make (names, where, what moves)."""
    suffixes = parse_suffixes(o["suffix"])
    if not suffixes:
        return "Type a suffix, or pick a stack / preset."
    if not objs:
        return "Select the objects to group."
    replace = o["name"] == 2
    target = None
    if o.get("place") == 3 and o["mode"] == 1:
        if len(objs) < 2:
            return "At last selected: select the objects, then the target last."
        objs, target = objs[:-1], objs[-1]

    def names(obj):
        out = []
        for sx in suffixes:
            n = make_name(obj, sx, replace).split(":")[-1]
            out.append(n + ("*" if _taken(n) else ""))
        return " > ".join(out)
    if o["mode"] == 3:
        text = "set %s  (%d objects)" % (make_name(objs[0], suffixes[0], replace).split(":")[-1], len(objs))
    elif o["mode"] == 2:
        text = "%s  (holding %d objects, nothing moves)" % (names(objs[0]), len(objs))
    elif o.get("where") == 2:
        parents = []
        for obj in objs:
            p = _parent(obj)
            if p and p not in parents:
                parents.append(p)
        if not parents:
            return "Above its parent: the selection has no parents."
        lines = ["under %s: %s > %s" % (_short(_parent(p) or "world"), names(p), _short(p)) for p in parents[:3]]
        if len(parents) > 3:
            lines.append("... and %d more" % (len(parents) - 3))
        text = "\n".join(lines)
    else:
        lines = ["under %s: %s > %s" % (_short(_parent(obj) or "world"), names(obj), _short(obj)) for obj in objs[:3]]
        if len(objs) > 3:
            lines.append("... and %d more" % (len(objs) - 3))
        place = {1: "groups match each object, its values become 0", 2: "values kept",
                 3: "groups on %s" % _short(target) if target else ""}[o.get("place", 1)]
        text = "\n".join(lines) + "\n(" + place + ")"
    if "*" in text:
        text += "\n* name taken: Maya adds a number"
    return text


def _on_change(*_):
    _save()
    preview()


def run(*_):
    o = _ui()
    _save()
    apply(o)
    preview()


def apply(o, objs=None):
    """Group the selection (or objs) with options o (same keys as DEFAULTS). Used by the
    tab and by the shelf's Offset group shortcut."""
    suffixes = parse_suffixes(o["suffix"])
    if not suffixes:
        utils.warn(TOOL, "type a suffix or click a preset.")
        return
    objs = objs or utils.selected_transforms(ordered=True)
    if not objs:
        utils.warn(TOOL, "select one or more objects.")
        return
    target = None
    if o.get("place") == 3 and o["mode"] == 1:
        if len(objs) < 2:
            utils.warn(TOOL, "At last selected: select the objects, then the target last.")
            return
        objs, target = objs[:-1], objs[-1]
    ids = [utils.uuid(n) for n in objs]
    replace, match = o["name"] == 2, o["place"] in (1, 3)
    with utils.undo_chunk("gusrigGroups"):
        if o["mode"] == 1 and o.get("where", 1) == 2:
            result = insert_above_parent(ids, suffixes, replace, o["side_color"])
            if result:
                cmds.select(result, replace=True)
            msg = "put %d group stack(s) above the parents." % len(result)
        elif o["mode"] == 1:
            result = group_each(ids, suffixes, replace, match, o["side_color"], target)
            if result:
                cmds.select(result, replace=True)
            msg = "grouped %d object(s) with %d group(s) each." % (len(result), len(suffixes))
        elif o["mode"] == 2:
            result = group_shared(ids, suffixes, replace, o["side_color"])
            if not result:
                return
            cmds.select(result, replace=True)
            msg = "put %d object(s) in '%s'." % (len(ids), naming.short_name(result[0]))
        else:
            set_name = make_set(ids, suffixes, replace)
            result = [set_name]
            cmds.select(cmds.ls(ids, long=True), replace=True)
            msg = "created set '%s' with %d object(s)." % (set_name, len(ids))
    utils.info(TOOL, msg)
    return result


def _fill_stacks():
    for item in cmds.optionMenu(N("Stack"), query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    cmds.menuItem(label="(pick a stack)", parent=N("Stack"))
    for name, text in stacks():
        cmds.menuItem(label="%s: %s" % (name, text), parent=N("Stack"))


def _use_stack(*_):
    i = cmds.optionMenu(N("Stack"), query=True, select=True) - 2
    all_ = stacks()
    if 0 <= i < len(all_):
        cmds.textFieldGrp(N("Suffix"), edit=True, text=all_[i][1])
        _on_change()


def _save_stack(*_):
    text = cmds.textFieldGrp(N("Suffix"), query=True, text=True)
    if not parse_suffixes(text):
        raise RuntimeError("type the suffixes first (e.g. _offset, _sdk).")
    if cmds.promptDialog(title="Save stack", message="Name of the stack:", button=["Save", "Cancel"],
                         defaultButton="Save", cancelButton="Cancel", dismissString="Cancel") != "Save":
        return
    name = save_stack(cmds.promptDialog(query=True, text=True), text)
    _fill_stacks()
    utils.info(TOOL, "stack '%s' saved." % name)


def _delete_stack(*_):
    i = cmds.optionMenu(N("Stack"), query=True, select=True) - 2
    all_ = stacks()
    if not 0 <= i < len(all_):
        raise RuntimeError("pick one of your stacks in the menu first.")
    delete_stack(all_[i][0])
    _fill_stacks()
    utils.info(TOOL, "stack '%s' deleted." % all_[i][0])


def remove_selected(*_):
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if not sel:
        raise RuntimeError("select the groups to remove.")
    with utils.undo_chunk("gusrigGroupsRemove"):
        removed, skipped = remove_groups(sel)
    msg = "removed %d group(s)." % len(removed)
    if skipped:
        utils.warn(TOOL, msg + " Skipped: " + "; ".join("%s (%s)" % x for x in skipped[:5]))
    else:
        utils.info(TOOL, msg)


def _add_preset(suffix, *_):
    current = cmds.textFieldGrp(N("Suffix"), query=True, text=True).strip().rstrip(",")
    cmds.textFieldGrp(N("Suffix"), edit=True, text=suffix if not current else "%s, %s" % (current, suffix))
    _on_change()


def _clear(*_):
    cmds.textFieldGrp(N("Suffix"), edit=True, text="")
    _on_change()


def _light():
    objs = utils.selected_transforms(ordered=False)
    if not objs:
        return "warn", "Select the objects to group."
    return "ok", "%s. Check the preview, then Create." % ui.selection_summary(objs)


def build(prefix="p_groups_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Groups", help_text="One suffix makes one group; several (comma separated) make stacked groups, "
               "top first. Match & zero: the object's translate / rotate become 0. Shared grp: one neutral group "
               "holding everything. Make set: no parenting, a Maya set.")
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnWidth4=(50, 160, 50, 50),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Stack")
    cmds.optionMenu(N("Stack"), changeCommand=_w(_use_stack),
                    annotation="Fills the suffix field with a whole stack (top first).")
    _fill_stacks()
    cmds.button(label="Save", command=_w(_guard(_save_stack)), annotation="Save the suffix field as a stack.")
    cmds.button(label="Delete", command=_w(_guard(_delete_stack)), annotation="Delete one of your stacks.")
    cmds.setParent("..")
    cmds.textFieldGrp(N("Suffix"), label="Suffix", text=s["suffix"], columnWidth2=(50, 260),
                      adjustableColumn=2, changeCommand=_w(_on_change),
                      annotation="One suffix = one group. Comma separated = stacked groups, top first.")
    cmds.gridLayout(numberOfColumns=4, cellWidthHeight=(88, 24))
    for suffix in PRESETS:
        cmds.button(label=suffix, command=_w(lambda *_, x=suffix: _add_preset(x)))
    cmds.button(label="Clear", command=_w(_clear))
    cmds.setParent("..")
    cmds.radioButtonGrp(N("Place"), label="Place", numberOfRadioButtons=3,
                        labelArray3=["Match & zero", "Keep values", "At last selected"], select=s["place"],
                        columnWidth4=(50, 100, 90, 110), changeCommand=_w(_on_change),
                        annotation="Match & zero: the object's translate / rotate become 0. "
                                   "Keep values: the group sits at the parent's origin. At last selected: the "
                                   "groups go on the last selected object's pivot and axes.")
    cmds.radioButtonGrp(N("Where"), label="Where", numberOfRadioButtons=2,
                        labelArray2=["Above the object", "Above its parent"], select=s["where"],
                        columnWidth3=(50, 120, 120), changeCommand=_w(_on_change),
                        annotation="Above its parent: a new group between the parent and the grandparent, "
                                   "matching the parent (e.g. an _sdk above an existing _offset).")
    cmds.radioButtonGrp(N("Name"), label="Name", numberOfRadioButtons=2,
                        labelArray2=["Add suffix", "Replace suffix"], select=s["name"],
                        columnWidth3=(50, 110, 110), changeCommand=_w(_on_change))
    cmds.radioButtonGrp(N("Mode"), label="Mode", numberOfRadioButtons=3,
                        labelArray3=["Each", "Shared grp", "Make set"], select=s["mode"],
                        columnWidth4=(50, 70, 90, 80), changeCommand=_w(_on_change),
                        annotation="Shared grp: one neutral group holding everything, nothing moves.")
    cmds.checkBox(N("SideColor"), label="Colour new groups by side in the Outliner",
                  value=s["side_color"], changeCommand=_w(_on_change),
                  annotation="Only the Outliner name colour. Nothing changes in the viewport.")
    cmds.frameLayout(label="Preview", collapsable=False, marginWidth=6, marginHeight=4)
    cmds.text(N("Preview"), label="", align="left")
    cmds.setParent("..")
    ui.main_button("Create", _w(run), "Create the groups. One undo.")
    ui.end_section()

    ui.section("Remove groups", step=2, help_text="Select groups: they go, their children stay exactly where they "
               "are (moved up to the group's parent). Groups with a shape or driven by a constraint / connection "
               "are skipped.")
    cmds.button(label="Remove the selected groups (children stay in place)", height=26,
                command=_w(_guard(remove_selected)))
    ui.end_section()

    ui.on_selection(N("Preview"), _w(preview))
    preview()


def show():
    ui.open_panel("groups")


SCHEMA = [
    ("suffix", "Suffix", "text", None),
    ("place", "Place", "choice", ["Match & zero", "Keep values", "At last selected"]),
    ("name", "Name", "choice", ["Add suffix", "Replace suffix"]),
    ("mode", "Mode", "choice", ["Each", "Shared grp", "Make set"]),
    ("side_color", "Colour new groups by side (Outliner)", "bool", None),
    ("where", "Where", "choice", ["Above the object", "Above its parent"]),
]
