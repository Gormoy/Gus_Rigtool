"""
Attributes: order, add, rename, delete, edit and copy the attributes of controls.

    import gus_rigtool.main as gr; gr.show_tool("attrs")

The reorder is based on attributesReorder.py by Romain Fleischer (delete an attribute, undo the
delete: it comes back at the end of the list, with its value, keys and connections).

  1 Order   : the list shows the first selected control's attributes (it follows the selection).
              Pick one or several (separators too), move them Top / Up / Down / Bottom, then Apply:
              every selected control gets that order (attributes it doesn't have are skipped).
              Ctrl+Z can't undo an order - use 'Back to the old order'.
  2 Add / edit : a new float / int / bool / enum / separator on every selected control, or new
              min / max / default / enum names for the picked attributes.
  3 Picked  : rename or delete the picked attributes (on every selected control that has them).
  4 Copy    : the picked attributes from the first selected control to the others.
"""

import maya.cmds as cmds

from gus_rigtool.core import attrs, ui, utils

TOOL = "Attributes"
SETTINGS_KEY = "attrs"
DEFAULTS = {"kind": 1, "keyable": True, "copy_connections": False}

_P, N, _w, _guard = ui.tool_helpers("p_attrs_", TOOL)
_state = {}          # prefix -> {"node": first selected, "order": [attr...]}
_history = {}        # node uuid -> the order before the last Apply


def _st():
    return _state.setdefault(_P["p"], {"node": None, "order": []})


def _sel():
    return utils.selected_transforms()


def _ui():
    return {"kind": cmds.optionMenu(N("Kind"), query=True, select=True),
            "keyable": cmds.checkBox(N("Keyable"), query=True, value=True),
            "copy_connections": cmds.checkBox(N("CopyConn"), query=True, value=True)}


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _light():
    sel = _sel()
    if not sel:
        return "idle", "Select one or more controls."
    first = attrs.user_attrs(sel[0])
    if len(sel) == 1:
        return ("ok" if first else "warn"), "%s: %d attribute(s)%s." % (
            sel[0].split("|")[-1], len(first), "" if first else " of its own - Add some in 2")
    differ = [n for n in sel[1:] if set(attrs.user_attrs(n)) != set(first)]
    if differ:
        return "warn", "%d controls - %d of them have other attributes than %s: each gets the order of the ones it has." % (
            len(sel), len(differ), sel[0].split("|")[-1])
    return "ok", "%d controls with the same attributes." % len(sel)


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------

def _picked():
    st = _st()
    idx = cmds.textScrollList(N("List"), query=True, selectIndexedItem=True) or []
    return [st["order"][i - 1] for i in idx if 0 < i <= len(st["order"])]


def _fill(keep=None):
    if not cmds.textScrollList(N("List"), exists=True):
        return
    st = _st()
    node = st["node"]
    cmds.textScrollList(N("List"), edit=True, removeAll=True)
    if not node or not cmds.objExists(node):
        cmds.text(N("ListNote"), edit=True, label="Select a control.")
        return
    for a in st["order"]:
        cmds.textScrollList(N("List"), edit=True, append=attrs.label(node, a))
    moved = st["order"] != attrs.user_attrs(node)
    cmds.text(N("ListNote"), edit=True, label="%s - %s" % (
        node.split("|")[-1], "order changed: Apply to use it" if moved else "the order it has now"))
    for a in keep or []:
        if a in st["order"]:
            cmds.textScrollList(N("List"), edit=True, selectIndexedItem=st["order"].index(a) + 1)


def reload(*_):
    st = _st()
    sel = _sel()
    st["node"] = sel[0] if sel else None
    st["order"] = attrs.user_attrs(sel[0]) if sel else []
    _fill()


def _move(where, *_):
    picked = _picked()
    if not picked:
        raise RuntimeError("pick one or more attributes in the list first.")
    st = _st()
    st["order"] = attrs.move(st["order"], picked, where)
    _fill(keep=picked)


def apply_order(*_):
    st = _st()
    sel = _sel()
    if not sel or not st["order"]:
        raise RuntimeError("select the controls, and set the order in the list.")
    done, total = [], 0
    for node in sel:
        old = attrs.user_attrs(node)
        n = attrs.apply_order(node, st["order"])
        if n:
            _history[utils.uuid(node)] = old
            done.append(node)
            total += n
    cmds.select(sel, replace=True)
    reload()
    if not done:
        utils.info(TOOL, "the order was already right - nothing changed.")
        return
    utils.info(TOOL, "new order on %d control(s) (%d attribute(s) moved). Ctrl+Z can't undo it: use "
                     "'Back to the old order'." % (len(done), total))


def back_order(*_):
    sel = _sel()
    done = 0
    for node in sel:
        old = _history.pop(utils.uuid(node), None)
        if old and attrs.apply_order(node, old):
            done += 1
    if sel:
        cmds.select(sel, replace=True)
    reload()
    if not done:
        raise RuntimeError("no order to put back on the selected controls (it is kept until Maya closes).")
    utils.info(TOOL, "old order back on %d control(s)." % done)


# ---------------------------------------------------------------------------
# add / edit
# ---------------------------------------------------------------------------

def _field(name):
    return cmds.textField(N(name), query=True, text=True) or ""


def add_attr(*_):
    sel = _sel()
    if not sel:
        raise RuntimeError("select the controls to add the attribute to.")
    o = _ui()
    _save()
    kind = attrs.KINDS[max(0, o["kind"] - 1)]
    made, skipped = [], []
    with utils.undo_chunk("gusrigAddAttr"):
        for node in sel:
            try:
                made.append(attrs.add(node, _field("Name"), kind, _field("Min"), _field("Max"), _field("Default"),
                                      _field("Enum"), o["keyable"]))
            except RuntimeError as e:
                skipped.append(str(e))
    reload()
    for s in skipped[:5]:
        utils.warn(TOOL, s)
    if made:
        utils.info(TOOL, "'%s' (%s) added to %d control(s)." % (made[0], kind, len(made)))


def edit_picked(*_):
    picked = _picked()
    if not picked:
        raise RuntimeError("pick the attributes to change in the list.")
    changes = 0
    with utils.undo_chunk("gusrigEditAttr"):
        for node in _sel():
            for a in picked:
                if cmds.attributeQuery(a, node=node, exists=True) and not attrs.is_separator(node, a):
                    if attrs.edit(node, a, _field("Min"), _field("Max"), _field("Default"), _field("Enum")):
                        changes += 1
    _fill(keep=picked)
    if not changes:
        raise RuntimeError("type a min, max, default or enum names first (blank fields are left alone).")
    utils.info(TOOL, "changed %d attribute(s)." % changes)


def read_picked(*_):
    st = _st()
    picked = _picked()
    if not picked or not st["node"]:
        raise RuntimeError("pick an attribute in the list.")
    i = attrs.info(st["node"], picked[0])
    fmt = lambda v: "" if v is None else ("%g" % v if isinstance(v, (int, float)) else str(v))
    cmds.textField(N("Name"), edit=True, text=picked[0])
    cmds.textField(N("Min"), edit=True, text=fmt(i["min"]))
    cmds.textField(N("Max"), edit=True, text=fmt(i["max"]))
    cmds.textField(N("Default"), edit=True, text=fmt(i["default"]))
    cmds.textField(N("Enum"), edit=True, text=i["enum"])
    kinds = {"double": 0, "float": 0, "doubleLinear": 0, "doubleAngle": 0, "long": 1, "short": 1, "bool": 2,
             "enum": 3}
    k = 4 if attrs.is_separator(st["node"], picked[0]) else kinds.get(i["type"], 0)
    cmds.optionMenu(N("Kind"), edit=True, select=k + 1)


def clear_limits(*_):
    picked = _picked()
    if not picked:
        raise RuntimeError("pick the attributes in the list.")
    n = 0
    with utils.undo_chunk("gusrigClearLimits"):
        for node in _sel():
            for a in picked:
                if cmds.attributeQuery(a, node=node, exists=True) and attrs.kind(node, a) not in ("enum", "bool"):
                    for which in ("min", "max"):
                        attrs.clear_limit(node, a, which)
                    n += 1
    utils.info(TOOL, "no min / max any more on %d attribute(s)." % n)


# ---------------------------------------------------------------------------
# picked: rename / delete / copy
# ---------------------------------------------------------------------------

def rename_picked(*_):
    picked = _picked()
    if len(picked) != 1:
        raise RuntimeError("pick ONE attribute to rename.")
    old = picked[0]
    if cmds.promptDialog(title="Rename attribute", message="New name for '%s':" % old, text=old,
                         button=["Rename", "Cancel"], defaultButton="Rename", cancelButton="Cancel",
                         dismissString="Cancel") != "Rename":
        return
    new = cmds.promptDialog(query=True, text=True)
    n = 0
    with utils.undo_chunk("gusrigRenameAttr"):
        for node in _sel():
            if cmds.attributeQuery(old, node=node, exists=True):
                attrs.rename(node, old, new)
                n += 1
    reload()
    utils.info(TOOL, "'%s' is now '%s' on %d control(s)." % (old, new, n))


def delete_picked(*_):
    picked = _picked()
    sel = _sel()
    if not picked:
        raise RuntimeError("pick the attributes to delete in the list.")
    nodes = [n for n in sel if any(cmds.attributeQuery(a, node=n, exists=True) for a in picked)]
    if cmds.confirmDialog(title="Delete attributes", message="Delete %s from %d control(s)?\nTheir keys and "
                          "connections go too. (Ctrl+Z brings them back.)" % (", ".join(picked), len(nodes)),
                          button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Delete":
        return
    n = 0
    with utils.undo_chunk("gusrigDeleteAttr"):
        for node in nodes:
            for a in picked:
                if cmds.attributeQuery(a, node=node, exists=True):
                    attrs.delete(node, a)
                    n += 1
    reload()
    utils.info(TOOL, "deleted %d attribute(s)." % n)


def copy_picked(*_):
    sel = _sel()
    picked = _picked()
    if len(sel) < 2:
        raise RuntimeError("select the control to copy from, then the controls to copy to.")
    if not picked:
        raise RuntimeError("pick the attributes to copy in the list (it shows the first selected control).")
    o = _ui()
    _save()
    added = updated = 0
    with utils.undo_chunk("gusrigCopyAttr"):
        for node in sel[1:]:
            a, u = attrs.copy(sel[0], node, picked, o["copy_connections"])
            added += len(a)
            updated += len(u)
    utils.info(TOOL, "%d attribute(s) added, %d already there (value%s copied) on %d control(s)." % (
        added, updated, " / connection" if o["copy_connections"] else "", len(sel) - 1))


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def build(prefix="p_attrs_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Order", step=1, help_text="The list shows the first selected control's attributes and follows the "
               "selection. Pick one or several (Ctrl / Shift-click; separators move like attributes), move them, then "
               "Apply order: every selected control gets it (attributes a control doesn't have are skipped, the ones "
               "not in the list stay after). Values, keys and connections are kept. Ctrl+Z can't undo an order: use "
               "'Back to the old order'. Reorder trick: attributesReorder.py by Romain Fleischer.")
    cmds.text(N("ListNote"), label="", align="left")
    cmds.textScrollList(N("List"), height=190, allowMultiSelection=True, font="fixedWidthFont",
                        annotation="Pick attributes (Ctrl / Shift-click several), then move them.")
    ui.row(4, 85)
    for label, where in (("Top", "top"), ("Up", "up"), ("Down", "down"), ("Bottom", "bottom")):
        cmds.button(label=label, command=_w(_guard(lambda *_, x=where: _move(x))))
    cmds.setParent("..")
    ui.main_button("Apply order to the selected controls", _w(_guard(apply_order)),
                   "Only the attributes from the first one that moved are touched.")
    ui.row(2, 170)
    cmds.button(label="Reload from selection", command=_w(_guard(reload)),
                annotation="Forget your changes to the list and read the control again.")
    cmds.button(label="Back to the old order", command=_w(_guard(back_order)),
                annotation="The order the selected controls had before the last Apply.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Add / edit", step=2, help_text="Add: the attribute on every selected control. Blank min / max / "
               "default = none. Enum names: off:on or world, root, chest. Separator: a divider line in the Channel "
               "Box with the name as its title. Edit picked: the filled fields change on the picked attributes "
               "(blank = left alone). Read picked fills the fields from the first picked attribute.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 100), (2, 240)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Name")
    cmds.textField(N("Name"), placeholderText="e.g. curl, space, Fingers")
    cmds.text(label="Type")
    cmds.optionMenu(N("Kind"), changeCommand=_w(_save))
    for k in attrs.KINDS:
        cmds.menuItem(label=k)
    cmds.optionMenu(N("Kind"), edit=True, select=max(1, min(len(attrs.KINDS), int(s["kind"]))))
    cmds.text(label="Min")
    cmds.textField(N("Min"), placeholderText="blank = none")
    cmds.text(label="Max")
    cmds.textField(N("Max"), placeholderText="blank = none")
    cmds.text(label="Default")
    cmds.textField(N("Default"), placeholderText="blank = 0")
    cmds.text(label="Enum names")
    cmds.textField(N("Enum"), placeholderText="enum only: off:on")
    cmds.setParent("..")
    cmds.checkBox(N("Keyable"), label="Keyable (off: shown in the Channel Box, not keyed)", value=s["keyable"],
                  changeCommand=_w(_save))
    ui.main_button("Add to the selected controls", _w(_guard(add_attr)), "One undo.")
    ui.row(3, 113)
    cmds.button(label="Edit picked", command=_w(_guard(edit_picked)),
                annotation="The filled fields go on the picked attributes (every selected control).")
    cmds.button(label="Read picked", command=_w(_guard(read_picked)),
                annotation="Fill the fields from the first picked attribute.")
    cmds.button(label="No min / max", command=_w(_guard(clear_limits)),
                annotation="Take the min and max off the picked attributes.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Picked attributes", step=3, help_text="Rename / delete the picked attributes on every selected "
               "control that has them. Delete asks first (Ctrl+Z brings them back).")
    ui.row(2, 170)
    cmds.button(label="Rename picked...", command=_w(_guard(rename_picked)))
    cmds.button(label="Delete picked", command=_w(_guard(delete_picked)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Copy to other controls", step=4, help_text="Select the control to copy FROM first, then the "
               "others. The picked attributes are made on them (same type, limits, names), with the same value - "
               "or the same incoming connection when the box is on. Attributes they already have just get the "
               "value / connection.")
    cmds.checkBox(N("CopyConn"), label="With their incoming connections (driven the same way)",
                  value=s["copy_connections"], changeCommand=_w(_save))
    cmds.button(label="Copy picked: first selected > others", height=26, command=_w(_guard(copy_picked)))
    ui.end_section()

    ui.note("Limits (how far controls move): Controls > Behaviour.")
    ui.on_selection(N("List"), _w(reload))
    reload()


def show():
    ui.open_panel("attrs")


SCHEMA = [
    ("kind", "Add: type", "choice", attrs.KINDS),
    ("keyable", "Add: keyable", "bool", None),
    ("copy_connections", "Copy: with incoming connections", "bool", None),
]
