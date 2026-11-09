"""
Organize: tidy the Outliner.

    import gus_rigtool.main as gr; gr.show_tool("organize")

  1 Analyze   : every top-level item is looked at (controls inside? joints? skinned meshes? IK handles,
                follicles...) and gets a proposed place: geo_grp, skeleton_grp, controls_grp,
                rig_nodes_grp (hidden), or 'leave'. Nothing moves yet.
  2 The plan  : one row per item, with why. Change any row's destination.
  3 Organize  : moves them (one undo). Nothing moves in the viewport; skinned meshes get 'inherits
                transform' off. Restore puts every item back where it was (even after save / reopen).
  Rules       : group names (and an optional character prefix), name rules (*_proxy = geo), items never
                moved, where ribbon builds go, extras (Outliner colours, geo display layer, sorting).
"""

import maya.cmds as cmds

from gus_rigtool.core import organize, ui, utils

TOOL = "Organize"
SETTINGS_KEY = "organize"
DEFAULTS = dict(organize.DEFAULTS)
SORTS = ["none", "name", "side"]

_P, N, _w, _guard = ui.tool_helpers("p_organize_", TOOL)
_plan = {}                       # prefix -> rows


def _o():
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    try:
        s = dict(s)
        s["prefix"] = cmds.textField(N("Prefix"), query=True, text=True).strip()
        s["names"] = {k: (cmds.textField(N("Name_" + k), query=True, text=True).strip() or k)
                      for k in ("rig", "geo", "skeleton", "controls", "rig_nodes")}
        s["hide_rig_nodes"] = cmds.checkBox(N("HideNodes"), query=True, value=True)
        s["rules"] = cmds.scrollField(N("Rules"), query=True, text=True)
        s["never"] = cmds.textField(N("Never"), query=True, text=True)
        s["ribbons"] = organize.DESTS[cmds.optionMenu(N("Ribbons"), query=True, select=True) - 1]
        s["colors"] = cmds.checkBox(N("Colors"), query=True, value=True)
        s["geo_layer"] = cmds.checkBox(N("GeoLayer"), query=True, value=True)
        s["sort"] = SORTS[cmds.optionMenu(N("Sort"), query=True, select=True) - 1]
    except RuntimeError:
        pass
    return s


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _o())
    except RuntimeError:
        pass


def _light():
    rows = _plan.get(_P["p"])
    moved = len(organize.organized_nodes())
    if rows is None:
        return "idle", "Press Analyze: nothing moves until you press Organize.%s" % (
            " (%d item(s) organized before - Restore puts them back.)" % moved if moved else "")
    n = len([r for r in rows if r["dest"] != "leave"])
    return "ok", "Plan: %d of %d top-level item(s) move. Change any row, then Organize." % (n, len(rows))


def _clear_rows():
    for kid in cmds.columnLayout(N("Rows"), query=True, childArray=True) or []:
        try:
            cmds.deleteUI(kid)
        except RuntimeError:
            pass


def analyze(*_):
    _save()
    rows = organize.analyze(_o())
    _plan[_P["p"]] = rows
    _clear_rows()
    o = _o()
    for i, r in enumerate(rows):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(150, 150, 200), parent=N("Rows"),
                       columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2)])
        cmds.text(label=r["name"], align="left", annotation=r["node"])
        menu = cmds.optionMenu(N("Dest%d" % i), changeCommand=_w(lambda *_, k=i: _row_changed(k)))
        for d in organize.DESTS:
            label = organize.DEST_LABELS[d] if d in ("leave", "delete", "rig_nodes") else organize.group_name(d, o)
            cmds.menuItem(label=label)
        cmds.optionMenu(menu, edit=True, select=organize.DESTS.index(r["dest"]) + 1)
        cmds.text(label=r["why"], align="left", font="smallPlainLabelFont")
        cmds.setParent("..")
    if not rows:
        cmds.text(label="  (nothing at the top of the Outliner)", parent=N("Rows"), align="left")
    ui.refresh_light(N("Light"))


def _row_changed(i):
    rows = _plan.get(_P["p"]) or []
    if i < len(rows):
        rows[i]["dest"] = organize.DESTS[cmds.optionMenu(N("Dest%d" % i), query=True, select=True) - 1]
    ui.refresh_light(N("Light"))


def all_to(dest, *_):
    rows = _plan.get(_P["p"]) or []
    for i, r in enumerate(rows):
        if r["kind"] in ("unknown", "empty", "scene", "tool", "rig group"):
            continue
        r["dest"] = dest
        cmds.optionMenu(N("Dest%d" % i), edit=True, select=organize.DESTS.index(dest) + 1)
    ui.refresh_light(N("Light"))


def run(*_):
    rows = _plan.get(_P["p"])
    if rows is None:
        raise RuntimeError("press Analyze first, check the plan, then Organize.")
    _save()
    gone = [r for r in rows if not cmds.objExists(r["node"])]
    if gone:
        raise RuntimeError("the scene changed since Analyze (%s gone): Analyze again." % gone[0]["name"])
    notes = organize.apply(rows, _o())
    ui.report_window("Gus_Rigtool - organized", "\n".join(notes))
    _plan.pop(_P["p"], None)
    _clear_rows()
    ui.refresh_light(N("Light"))


def restore(*_):
    if not organize.organized_nodes():
        raise RuntimeError("nothing was organized in this scene.")
    if cmds.confirmDialog(title="Restore", message="Put every organized item back where it was?",
                          button=["Restore", "Cancel"], defaultButton="Restore", cancelButton="Cancel",
                          dismissString="Cancel") != "Restore":
        return
    organize.restore()
    _plan.pop(_P["p"], None)
    _clear_rows()
    ui.refresh_light(N("Light"))


def build(prefix="p_organize_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Analyze", step=1, help_text="Every top-level item of the Outliner is looked at: controls inside "
               "go to controls_grp, joints to skeleton_grp, meshes to geo_grp, IK handles / follicles / locators "
               "to rig_nodes_grp (hidden), ribbon builds where Rules says. Cameras, lights, the guides and the "
               "backup stay. Anything it isn't sure about stays and is listed. Nothing moves yet.")
    ui.main_button("Analyze the Outliner", _w(_guard(analyze)), "Make the plan (nothing moves).")
    ui.end_section()

    ui.section("The plan", step=2, help_text="One row per top-level item: where it goes, and why. Change any "
               "row (leave = don't touch; delete only works on empty groups).")
    ui.row(2, 170)
    cmds.button(label="Reset to proposed", command=_w(_guard(analyze)),
                annotation="Analyze again (undoes your row changes).")
    cmds.button(label="Every row: leave", command=_w(_guard(lambda *_: all_to("leave"))))
    cmds.setParent("..")
    cmds.scrollLayout(height=220, childResizable=True)
    cmds.columnLayout(N("Rows"), adjustableColumn=True, rowSpacing=1)
    cmds.setParent("..")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Organize", height=30, backgroundColor=ui.MAIN_BG, command=_w(_guard(run)),
                annotation="Move the items as the plan says. One undo.")
    cmds.button(label="Restore", height=30, command=_w(_guard(restore)),
                annotation="Everything Organize moved goes back where it was (even after save / reopen).")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Rules", step=3, collapse=True, help_text="Group names: empty prefix = rig_grp, geo_grp... (the "
               "names the builder and Publish use). With a prefix (e.g. Hare) they are Hare_rig_grp... - only for "
               "rigs not made with the builder. Name rules: one per line, pattern = destination (geo, skeleton, "
               "controls, rig_nodes, leave), wildcards * ?. Never move: names (wildcards ok).")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(110, 200),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Character prefix")
    cmds.textField(N("Prefix"), text=s.get("prefix", ""), placeholderText="empty: rig_grp, geo_grp...",
                   changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 110), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 2))
    for k, label in (("rig", "Rig group"), ("geo", "Geometry"), ("skeleton", "Skeleton"), ("controls", "Controls"),
                     ("rig_nodes", "Rig nodes")):
        cmds.text(label=label)
        cmds.textField(N("Name_" + k), text=s.get("names", {}).get(k, k), changeCommand=_w(_save),
                       annotation="The group's name without _grp.")
    cmds.setParent("..")
    cmds.checkBox(N("HideNodes"), label="Hide rig_nodes_grp", value=s.get("hide_rig_nodes", True),
                  changeCommand=_w(_save))
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 200), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Ribbon builds go to")
    cmds.optionMenu(N("Ribbons"), changeCommand=_w(_save))
    for d in organize.DESTS[:5]:
        cmds.menuItem(label=organize.DEST_LABELS[d])
    cmds.optionMenu(N("Ribbons"), edit=True, select=organize.DESTS.index(s.get("ribbons", "controls")) + 1)
    cmds.setParent("..")
    cmds.text(label="Name rules (pattern = destination), one per line:", align="left")
    cmds.scrollField(N("Rules"), text=s.get("rules", ""), height=60, wordWrap=False, changeCommand=_w(_save),
                     annotation="e.g.  *_proxy = geo     *_LOC = rig_nodes     temp_* = leave")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(110, 200),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Never move")
    cmds.textField(N("Never"), text=s.get("never", ""), changeCommand=_w(_save),
                   placeholderText="e.g. Hare_ref_grp cam_*")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Extras (off by default)", step=4, collapse=True,
               help_text="Outliner colours: each rig group gets its own colour. Geo layer: geo_grp in a display "
               "layer set to reference (click through the model). Sort: order inside each rig group.")
    cmds.checkBox(N("Colors"), label="Outliner colour per rig group", value=s.get("colors", False),
                  changeCommand=_w(_save))
    cmds.checkBox(N("GeoLayer"), label="geo_grp in a 'geo_layer' display layer (reference)",
                  value=s.get("geo_layer", False), changeCommand=_w(_save))
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 200), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Sort inside groups")
    cmds.optionMenu(N("Sort"), changeCommand=_w(_save))
    for x in ("don't sort", "by name", "by side (C, L, R)"):
        cmds.menuItem(label=x)
    cmds.optionMenu(N("Sort"), edit=True, select=SORTS.index(s.get("sort", "none")) + 1)
    cmds.setParent("..")
    ui.end_section()


def show():
    ui.open_panel("organize")


SCHEMA = [
    ("prefix", "Character prefix for the rig groups", "text", None),
    ("hide_rig_nodes", "Hide rig_nodes_grp", "bool", None),
    ("colors", "Outliner colour per rig group", "bool", None),
    ("geo_layer", "geo_grp in a reference display layer", "bool", None),
]
