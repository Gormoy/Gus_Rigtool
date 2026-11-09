"""
Constraints: make, swap, remove and check constraints.

    import gus_rigtool.main as gr; gr.show_tool("constrain")

  1 Make   : parent / point / orient / scale / aim / pole vector, with or without offset, axes left free;
             in the order you select: targets then the driven LAST, the first driving each of the others,
             or pairs (target, driven, target, driven...).
  2 Swap   : select the driven node(s), then the new target LAST: their constraints use it instead
             of the old targets.
  3 Check  : what drives the selection, and what it drives; select the targets / driven nodes.
             Remove: the constraints ON the selected nodes (asks first).
"""

import maya.cmds as cmds

from gus_rigtool.core import constraints, ui, utils

TOOL = "Constraints"
SETTINGS_KEY = "constrain"
DEFAULTS = {"kind": 1, "mode": 1, "offset": True, "skip_t": "", "skip_r": "", "skip_s": "", "aim": 1, "up": 2}
VECTORS = ["+X", "+Y", "+Z", "-X", "-Y", "-Z"]
_VEC = {"+X": (1, 0, 0), "+Y": (0, 1, 0), "+Z": (0, 0, 1), "-X": (-1, 0, 0), "-Y": (0, -1, 0), "-Z": (0, 0, -1)}

_P, N, _w, _guard = ui.tool_helpers("p_constrain_", TOOL)


def _menu(name, items, value):
    cmds.optionMenu(N(name), changeCommand=_w(_save))
    for i in items:
        cmds.menuItem(label=i)
    cmds.optionMenu(N(name), edit=True, select=max(1, min(len(items), int(value))))


def _skip(row):
    return "".join(ax for ax in "xyz" if cmds.checkBox(N("Skip%s%s" % (row, ax)), query=True, value=True))


def _ui():
    return {"kind": cmds.optionMenu(N("Kind"), query=True, select=True),
            "mode": cmds.optionMenu(N("Mode"), query=True, select=True),
            "offset": cmds.checkBox(N("Offset"), query=True, value=True),
            "skip_t": _skip("T"), "skip_r": _skip("R"), "skip_s": _skip("S"),
            "aim": cmds.optionMenu(N("Aim"), query=True, select=True),
            "up": cmds.optionMenu(N("Up"), query=True, select=True)}


def _save(*_):
    try:
        o = _ui()
        utils.save_setting(SETTINGS_KEY, o)
        aim = constraints.TYPES[o["kind"] - 1] == "aim"
        for n in ("Aim", "Up"):
            cmds.optionMenu(N(n), edit=True, enable=aim)
        ui.refresh_light(N("Light"))
    except RuntimeError:
        pass


def _light():
    sel = utils.selected_transforms()
    if len(sel) < 1:
        return "idle", "Select targets then the driven node (see the order in 1)."
    try:
        o = _ui()
        jobs = constraints.plan(sel, o["mode"] - 1) if len(sel) > 1 else []
    except (RuntimeError, ValueError) as e:
        return "warn", str(e)
    if not jobs:
        return "idle", "%s - select more to make a constraint." % ui.selection_summary(sel)
    return "ok", "%d %s constraint(s): %s." % (len(jobs), constraints.TYPES[o["kind"] - 1], "; ".join(
        "%s > %s" % (",".join(t.split("|")[-1] for t in ts), d.split("|")[-1]) for ts, d in jobs[:2]) +
        (" ..." if len(jobs) > 2 else ""))


def make(*_):
    sel = utils.selected_transforms()
    o = _ui()
    _save()
    kind = constraints.TYPES[o["kind"] - 1]
    jobs = constraints.plan(sel, o["mode"] - 1)
    made = []
    with utils.undo_chunk("gusrigConstrain"):
        for targets, driven in jobs:
            made.append(constraints.make(targets, driven, kind, o["offset"], o["skip_t"], o["skip_r"], o["skip_s"],
                                         _VEC[VECTORS[o["aim"] - 1]], _VEC[VECTORS[o["up"] - 1]]))
    utils.info(TOOL, "%d %s constraint(s) made%s." % (len(made), kind, " (offset kept)" if o["offset"] else ""))


def swap(*_):
    sel = utils.selected_transforms()
    if len(sel) < 2:
        raise RuntimeError("select the driven node(s), then the new target LAST.")
    o = _ui()
    done = []
    with utils.undo_chunk("gusrigSwapTarget"):
        for d in sel[:-1]:
            done += constraints.swap(d, [sel[-1]], o["offset"])
    if not done:
        raise RuntimeError("the selected nodes have no constraints on them.")
    utils.info(TOOL, "%d constraint(s) now use %s." % (len(done), sel[-1].split("|")[-1]))


def remove(*_):
    sel = utils.selected_transforms()
    cons = [c for n in sel for c in constraints.constraints_on(n)]
    if not cons:
        raise RuntimeError("the selected nodes have no constraints on them.")
    if cmds.confirmDialog(title="Remove constraints", message="Delete the %d constraint(s) on the %d selected "
                          "node(s)?\nThey stay where they are now. (Ctrl+Z brings them back.)" % (len(cons), len(sel)),
                          button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Delete":
        return
    with utils.undo_chunk("gusrigRemoveConstraints"):
        n = constraints.remove(sel)
    utils.info(TOOL, "deleted %d constraint(s)." % n)


def show_report(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the nodes to check.")
    ui.report_window("Constraints", constraints.report(sel))


def select_targets(*_):
    sel = utils.selected_transforms()
    got = []
    for n in sel:
        for c in constraints.constraints_on(n):
            got += [t for t in constraints.targets_of(c) if t not in got]
    if not got:
        raise RuntimeError("no constraints on the selection.")
    cmds.select(got, replace=True)


def select_driven(*_):
    sel = utils.selected_transforms()
    got = []
    for n in sel:
        got += [d for _c, d in constraints.drives(n) if d not in got]
    if not got:
        raise RuntimeError("the selection drives no constraints.")
    cmds.select(got, replace=True)


def build(prefix="p_constrain_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Make", step=1, help_text="Order: 'targets... > last': select the targets, then the driven node "
               "LAST. 'first > each other': the first drives every other one. Pairs: target, driven, target, "
               "driven... Free axes: ticked axes are NOT driven. Parent and orient use 'shortest' interpolation "
               "(no flips between targets).")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 90), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Type")
    _menu("Kind", constraints.TYPES, s["kind"])
    cmds.text(label="Order")
    _menu("Mode", constraints.MODES, s["mode"])
    cmds.text(label="Aim axis")
    _menu("Aim", VECTORS, s["aim"])
    cmds.text(label="Up axis")
    _menu("Up", VECTORS, s["up"])
    cmds.setParent("..")
    cmds.checkBox(N("Offset"), label="Keep offset (nothing moves)", value=s["offset"], changeCommand=_w(_save))
    cmds.rowColumnLayout(numberOfColumns=4, columnWidth=[(1, 90), (2, 50), (3, 50), (4, 50)])
    for row, label in (("T", "Free move"), ("R", "Free turn"), ("S", "Free scale")):
        cmds.text(label=label, align="left")
        for ax in "xyz":
            cmds.checkBox(N("Skip%s%s" % (row, ax)), label=ax.upper(), changeCommand=_w(_save),
                          value=ax in (s.get("skip_" + row.lower()) or ""))
    cmds.setParent("..")
    ui.main_button("Constrain", _w(_guard(make)), "One undo.")
    ui.end_section()

    ui.section("Swap target", step=2, help_text="Select the driven node(s), then the new target LAST: every "
               "constraint on them uses the new target instead of the old ones (Keep offset from 1).")
    cmds.button(label="Swap to the last selected", height=26, backgroundColor=ui.MAIN_BG, command=_w(_guard(swap)))
    ui.end_section()

    ui.section("Check / remove", step=3, help_text="What drives / is driven by the selection. Remove: the "
               "constraints ON the selected nodes (asks first).")
    ui.row(3, 113)
    cmds.button(label="What drives what?", command=_w(_guard(show_report)))
    cmds.button(label="Select targets", command=_w(_guard(select_targets)))
    cmds.button(label="Select driven", command=_w(_guard(select_driven)))
    cmds.setParent("..")
    cmds.button(label="Remove constraints on selected", command=_w(_guard(remove)))
    ui.end_section()
    _save()


def show():
    ui.open_panel("constrain")


SCHEMA = [
    ("kind", "Type", "choice", constraints.TYPES),
    ("mode", "Order", "choice", constraints.MODES),
    ("offset", "Keep offset", "bool", None),
]
