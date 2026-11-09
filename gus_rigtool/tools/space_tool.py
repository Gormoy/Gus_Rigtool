"""
Spaces: a space switch on any control - hand-made rigs too.

    import gus_rigtool.main as gr; gr.show_tool("spaces")

  1 Control : the control that gets the switch.
  2 Targets : what it can follow (label = node). 'Load selection' takes the targets first and the
              control last, in one go.
  3 Make    : parent (moves + turns), orient (turns only) or point (moves only); the attribute's name
              and the space it starts in. A 'space' group goes above the control (above its offset group
              when it has one) and follows the picked target. Animators switch with no jump in Gus Animtool.
  4 This control's switch: add the listed targets it doesn't have, try the next space (no jump), or
              remove the switch (asks first).
"""

import maya.cmds as cmds

from gus_rigtool.core import spaces, ui, utils

TOOL = "Spaces"
SETTINGS_KEY = "spaces"
DEFAULTS = {"kind": 1, "attr": "space"}

_P, N, _w, _guard = ui.tool_helpers("p_spaces_", TOOL)
_state = {}


def _st():
    return _state.setdefault(_P["p"], {"targets": []})


def _ctrl():
    name = (cmds.textField(N("Ctrl"), query=True, text=True) or "").strip()
    found = cmds.ls(name, long=True) or [] if name else []
    return found[0] if len(found) == 1 else None


def _ui():
    return {"kind": cmds.optionMenu(N("Kind"), query=True, select=True),
            "attr": (cmds.textField(N("Attr"), query=True, text=True) or "").strip() or "space"}


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _light():
    ctrl = _ctrl()
    targets = _st()["targets"]
    if not ctrl:
        return "idle", "Pick the control (1), then its targets (2) - or 'Load selection'."
    data = spaces.read(ctrl)
    if data:
        return "ok", "%s has a switch: %s = %s." % (ctrl.split("|")[-1], data["attr"],
                                                   ", ".join(lb for lb, _n in data["targets"]))
    if len(targets) < 2:
        return "warn", "%s: add 2 targets or more." % ctrl.split("|")[-1]
    return "ok", "%s: ready - %d targets." % (ctrl.split("|")[-1], len(targets))


def _refresh():
    if not cmds.textScrollList(N("Targets"), exists=True):
        return
    targets = _st()["targets"]
    cmds.textScrollList(N("Targets"), edit=True, removeAll=True)
    for lb, n in targets:
        cmds.textScrollList(N("Targets"), edit=True, append="%s = %s" % (lb, n))
    menu = N("Default")
    for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    for lb, _n in targets or [("(add targets)", None)]:
        cmds.menuItem(label=lb, parent=menu)
    ui.refresh_light(N("Light"))


def _picked():
    return [i - 1 for i in cmds.textScrollList(N("Targets"), query=True, selectIndexedItem=True) or []]


def set_ctrl(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the control.")
    cmds.textField(N("Ctrl"), edit=True, text=sel[-1].split("|")[-1])
    _refresh()


def _add(nodes):
    st = _st()
    have = [n for _l, n in st["targets"]]
    labels = [lb for lb, _n in st["targets"]]
    for node in nodes:
        short = node.split("|")[-1]
        if short in have:
            continue
        label = spaces.default_label(short)
        base, i = label, 2
        while label in labels:
            label, i = "%s%d" % (base, i), i + 1
        st["targets"].append([label, short])
        labels.append(label)


def add_selected(*_):
    sel = utils.selected_transforms()
    ctrl = _ctrl()
    sel = [n for n in sel if n != ctrl]
    if not sel:
        raise RuntimeError("select the nodes the control should follow.")
    _add(sel)
    _refresh()


def load_selection(*_):
    sel = utils.selected_transforms()
    if len(sel) < 3:
        raise RuntimeError("select 2 targets or more, then the control LAST.")
    cmds.textField(N("Ctrl"), edit=True, text=sel[-1].split("|")[-1])
    _st()["targets"] = []
    _add(sel[:-1])
    _refresh()


def remove_picked(*_):
    idx = _picked()
    if not idx:
        raise RuntimeError("pick targets in the list.")
    st = _st()
    st["targets"] = [t for i, t in enumerate(st["targets"]) if i not in idx]
    _refresh()


def move_picked(step, *_):
    idx = _picked()
    st = _st()
    if len(idx) != 1:
        raise RuntimeError("pick ONE target to move.")
    i, j = idx[0], idx[0] + step
    if 0 <= j < len(st["targets"]):
        st["targets"][i], st["targets"][j] = st["targets"][j], st["targets"][i]
    _refresh()
    cmds.textScrollList(N("Targets"), edit=True, selectIndexedItem=max(1, min(len(st["targets"]), j + 1)))


def relabel(*_):
    idx = _picked()
    st = _st()
    if len(idx) != 1:
        raise RuntimeError("pick ONE target to rename.")
    old = st["targets"][idx[0]][0]
    if cmds.promptDialog(title="Space label", message="Label (the name in the menu):", text=old,
                         button=["OK", "Cancel"], defaultButton="OK", cancelButton="Cancel",
                         dismissString="Cancel") != "OK":
        return
    new = cmds.promptDialog(query=True, text=True).strip().replace(" ", "_")
    if new:
        st["targets"][idx[0]][0] = new
    _refresh()


def make(*_):
    ctrl = _ctrl()
    if not ctrl:
        raise RuntimeError("pick the control first (1).")
    o = _ui()
    _save()
    default = cmds.optionMenu(N("Default"), query=True, select=True) - 1
    targets = [tuple(t) for t in _st()["targets"]]
    msg = "Control: %s\nTargets: %s\nFollows: %s" % (ctrl.split("|")[-1], ", ".join(
        "%s (%s)" % (lb, n.split("|")[-1]) for lb, n in targets), spaces.KINDS[o["kind"] - 1])
    if cmds.confirmDialog(title="Gus_Rigtool - space switch", message=msg + "\n\nNothing moves. One undo.",
                          button=["Make", "Cancel"], defaultButton="Make", cancelButton="Cancel",
                          dismissString="Cancel") != "Make":        # 5.6.7: a wrong selection order shows here
        return
    with utils.undo_chunk("gusrigSpaceSwitch"):
        grp = spaces.make(ctrl, [tuple(t) for t in _st()["targets"]], spaces.KINDS[o["kind"] - 1], o["attr"],
                          default)
    _refresh()
    utils.info(TOOL, "space switch on %s: %s (group %s). Switch with no jump in Gus Animtool." % (
        ctrl.split("|")[-1], o["attr"], grp.split("|")[-1]))


def standard_spaces(*_):
    plan = spaces.standard_plan()
    if not plan:
        raise RuntimeError("nothing to make: no built limbs found, or they all have switches already.")
    lines = ["%s (%s): %s" % (c.split("|")[-1], k, ", ".join(lb for lb, _n in t)) for c, t, k in plan]
    if cmds.confirmDialog(title="Gus_Rigtool - standard spaces", message="\n".join(lines) +
                          "\n\nNothing moves (checked: undone if it did). One undo.", button=["Make", "Cancel"],
                          defaultButton="Make", cancelButton="Cancel", dismissString="Cancel") != "Make":
        return
    with utils.undo_chunk("gusrigStandardSpaces"):
        made, failed = spaces.standard(plan)
    for c, why in failed:
        print("Standard spaces: %s not made - %s" % (c, why))
    _refresh()
    utils.info(TOOL, "%d space switch(es) made%s. Check this scene > Spaces tests them." % (
        len(made), (", %d not made - see the Script Editor" % len(failed)) if failed else ""))


def add_missing(*_):
    ctrl = _ctrl()
    data = spaces.read(ctrl) if ctrl else None
    if not data:
        raise RuntimeError("the control has no switch made here - use Make.")
    have = [n for _l, n in data["targets"]]
    added = []
    with utils.undo_chunk("gusrigSpaceAdd"):
        for lb, n in _st()["targets"]:
            if n not in have:
                spaces.add_target(ctrl, lb, n)
                added.append(lb)
    _refresh()
    if not added:
        raise RuntimeError("every listed target is already in the switch.")
    utils.info(TOOL, "added %s to %s's switch." % (", ".join(added), ctrl.split("|")[-1]))


def try_next(*_):
    ctrl = _ctrl()
    data = spaces.read(ctrl) if ctrl else None
    if not data:
        raise RuntimeError("the control has no switch made here.")
    plug = ctrl + "." + data["attr"]
    nxt = (int(cmds.getAttr(plug)) + 1) % len(data["targets"])
    with utils.undo_chunk("gusrigSpaceTry"):
        spaces.switch(ctrl, nxt)
    utils.info(TOOL, "%s = %s, no jump." % (data["attr"], data["targets"][nxt][0]))


def remove(*_):
    ctrl = _ctrl()
    data = spaces.read(ctrl) if ctrl else None
    if not data:
        raise RuntimeError("the control has no switch made here.")
    if cmds.confirmDialog(title="Remove space switch", message="Remove %s's switch (%s)?\nThe control stays "
                          "where it is; keys on '%s' go with the attribute. (Ctrl+Z brings it back.)" % (
                              ctrl.split("|")[-1], data["attr"], data["attr"]),
                          button=["Remove", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Remove":
        return
    with utils.undo_chunk("gusrigSpaceRemove"):
        spaces.remove(ctrl)
    _st()["targets"] = [list(t) for t in data["targets"]]
    _refresh()
    utils.info(TOOL, "switch removed (its targets are back in the list).")


def load_switch(*_):
    ctrl = _ctrl()
    data = spaces.read(ctrl) if ctrl else None
    if not data:
        raise RuntimeError("the control has no switch made here.")
    _st()["targets"] = [list(t) for t in data["targets"]]
    _refresh()


def build(prefix="p_spaces_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Control", step=1, help_text="The control that gets the switch. 'Load selection': select the "
               "targets, then the control LAST - both are filled in one go.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.textField(N("Ctrl"), placeholderText="the control", changeCommand=_w(lambda *_: _refresh()))
    cmds.button(label="< sel", width=50, command=_w(_guard(set_ctrl)), annotation="The (last) selected control.")
    cmds.setParent("..")
    cmds.button(label="Load selection (targets..., control last)", height=26, command=_w(_guard(load_selection)))
    ui.end_section()

    ui.section("Targets", step=2, help_text="What the control can follow, in the menu's order. The label is the "
               "name in the menu (from the node's name, without side / type).")
    cmds.textScrollList(N("Targets"), height=110, allowMultiSelection=True, font="fixedWidthFont")
    ui.row(3, 113)
    cmds.button(label="Add selected", command=_w(_guard(add_selected)))
    cmds.button(label="Rename label...", command=_w(_guard(relabel)))
    cmds.button(label="Remove picked", command=_w(_guard(remove_picked)),
                annotation="From this list only (nothing in the scene).")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Move up", command=_w(_guard(lambda *_: move_picked(-1))))
    cmds.button(label="Move down", command=_w(_guard(lambda *_: move_picked(1))))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Make", step=3, help_text="parent: follows moves and turns. orient: turns only. point: moves only. "
               "The space group goes above the control's offset group (or the control when it has none); the "
               "control keeps its values. Starts in: the space it uses when made.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 100), (2, 220)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Follows")
    cmds.optionMenu(N("Kind"), changeCommand=_w(_save))
    for k in ("parent (move + turn)", "orient (turn)", "point (move)"):
        cmds.menuItem(label=k)
    cmds.optionMenu(N("Kind"), edit=True, select=max(1, min(3, int(s["kind"]))))
    cmds.text(label="Attribute")
    cmds.textField(N("Attr"), text=s["attr"], changeCommand=_w(_save))
    cmds.text(label="Starts in")
    cmds.optionMenu(N("Default"))
    cmds.setParent("..")
    ui.main_button("Make space switch", _w(_guard(make)), "Shows the control and targets first. One undo.")
    cmds.button(label="Standard spaces (every built limb)", height=26, command=_w(_guard(standard_spaces)),
                annotation="IK feet: world / COG / hips. Knee pole vectors: foot / world / COG. Arm pole vectors: "
                           "chest / world / hand. FK arms (turn only): chest / COG / world. Skips controls that "
                           "have a switch already. Shows the list first.")
    ui.end_section()

    ui.section("This control's switch", step=4, help_text="Add: the listed targets the switch doesn't have yet "
               "(at the end of its menu). Next space: try it, with no jump. Remove: asks first; the control stays "
               "where it is.")
    ui.row(2, 170)
    cmds.button(label="Show its targets", command=_w(_guard(load_switch)))
    cmds.button(label="Add listed targets", command=_w(_guard(add_missing)))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Next space (no jump)", command=_w(_guard(try_next)))
    cmds.button(label="Remove switch", command=_w(_guard(remove)))
    cmds.setParent("..")
    ui.end_section()
    _refresh()


def show():
    ui.open_panel("spaces")


SCHEMA = [
    ("kind", "Follows", "choice", ["parent (move + turn)", "orient (turn)", "point (move)"]),
    ("attr", "Attribute name", "text", None),
]
