"""
Rename: many nodes at once, with a preview.

    import gus_rigtool.main as gr; gr.show_tool("rename")

  New name     : a base name with numbers in selection order ('finger_##_jnt' -> finger_01_jnt...;
                 no # = base_01). Blank: the names are kept and only the steps below change them.
  Search / replace, Prefix / suffix.
  Swap side    : L_ <-> R_ (your side pairs from the Mirror tool).
  Fix to my naming : side token + part + type suffix from Build > Naming (joint _jnt, curve _ctrl,
                 mesh _geo, empty _grp ...).
  The steps run in that order. Hierarchy: the children too. Shapes follow: shapes become <name>Shape.
"""

import maya.cmds as cmds

from gus_rigtool.core import renamer, ui, utils

TOOL = "Rename"
SETTINGS_KEY = "rename"
STARTS = ["0", "1"]
PADS = ["1", "2", "3", "4"]
STEPS = ["1", "2", "5", "10"]
DEFAULTS = {"start": 2, "pad": 2, "step": 1, "hierarchy": False, "shapes": False}

_P, N, _w, _guard = ui.tool_helpers("p_rename_", TOOL)


def _menu(name, items, value):
    cmds.optionMenu(N(name), changeCommand=_w(_on_change))
    for i in items:
        cmds.menuItem(label=i)
    cmds.optionMenu(N(name), edit=True, select=max(1, min(len(items), int(value))))


def _q(name, items):
    return int(items[cmds.optionMenu(N(name), query=True, select=True) - 1])


def _t(name):
    return cmds.textField(N(name), query=True, text=True) or ""


def _ui():
    return {"base": _t("Base").strip(), "search": _t("Search"), "replace": _t("Replace"), "prefix": _t("Prefix"),
            "suffix": _t("Suffix"), "start": _q("Start", STARTS), "pad": _q("Pad", PADS), "step": _q("Step", STEPS),
            "swap": cmds.checkBox(N("Swap"), query=True, value=True),
            "fix": cmds.checkBox(N("Fix"), query=True, value=True),
            "hierarchy": cmds.checkBox(N("Hier"), query=True, value=True),
            "shapes": cmds.checkBox(N("Shapes"), query=True, value=True)}


def _save(*_):
    try:
        o = _ui()
        utils.save_setting(SETTINGS_KEY, {"start": STARTS.index(str(o["start"])) + 1, "pad": PADS.index(str(o["pad"])) + 1,
                                          "step": STEPS.index(str(o["step"])) + 1, "hierarchy": o["hierarchy"],
                                          "shapes": o["shapes"]})
    except (RuntimeError, ValueError):
        pass


def _rows():
    o = _ui()
    nodes = renamer.nodes_from(utils.selected_transforms(), o["hierarchy"])
    return renamer.plan(nodes, o), o


def preview(*_):
    if not cmds.scrollField(N("Preview"), exists=True):
        return
    try:
        rows, _o = _rows()
    except RuntimeError:
        return
    if not rows:
        cmds.scrollField(N("Preview"), edit=True, text="Select what to rename.")
        return
    changed = [r for r in rows if r[2] != r[1]]
    lines = ["%-28s ->  %s" % (old, new) for _n, old, new in changed[:60]]
    if len(changed) > 60:
        lines.append("... and %d more" % (len(changed) - 60))
    dup = renamer.clashes(rows)
    head = "%d of %d change" % (len(changed), len(rows))
    if dup:
        head += "  -  used twice: %s (Maya adds numbers)" % ", ".join(dup[:4])
    cmds.scrollField(N("Preview"), edit=True, text=head + "\n" + "\n".join(lines or ["(nothing changes)"]))


def _on_change(*_):
    _save()
    preview()


def run(*_):
    rows, o = _rows()
    if not rows:
        raise RuntimeError("select what to rename.")
    with utils.undo_chunk("gusrigRename"):
        done = renamer.apply(rows, o["shapes"])
    differ = [(a, b) for (a, b), r in zip(done, [r for r in rows if r[2] != r[1]]) if b != r[2].split(":")[-1]]
    preview()
    if not done:
        raise RuntimeError("nothing to change - type a new name, search, prefix... (see the preview).")
    utils.info(TOOL, "renamed %d node(s)%s." % (len(done), (" - %d got a number added by Maya" % len(differ))
                                                if differ else ""))


def _light():
    sel = utils.selected_transforms()
    if not sel:
        return "idle", "Select the nodes to rename (in the order you want the numbers)."
    return "ok", "%s - check the preview, then Rename." % ui.selection_summary(sel, "node")


def build(prefix="p_rename_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Names", step=1, help_text="The steps run top to bottom. New name: # are the numbers "
               "(finger_##_jnt -> finger_01_jnt), in selection order; without # the number goes at the end. "
               "Blank fields are skipped. Swap side uses your side pairs; Fix to my naming uses Build > Naming "
               "(side + part + type suffix: joint _jnt, curve _ctrl, mesh _geo, empty _grp...).")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 90), (2, 250)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    for label, name, hint in (("New name", "Base", "blank = keep the names; e.g. spine_##_jnt"),
                              ("Search", "Search", ""), ("Replace with", "Replace", ""),
                              ("Prefix", "Prefix", ""), ("Suffix", "Suffix", "")):
        cmds.text(label=label)
        cmds.textField(N(name), placeholderText=hint, changeCommand=_w(_on_change),
                       textChangedCommand=_w(lambda *_: preview()))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=6, columnWidth=[(1, 40), (2, 60), (3, 55), (4, 60), (5, 35), (6, 60)],
                   columnAlign=[(1, "right"), (3, "right"), (5, "right")])
    cmds.text(label="Start")
    _menu("Start", STARTS, s["start"])
    cmds.text(label="Digits")
    _menu("Pad", PADS, s["pad"])
    cmds.text(label="Step")
    _menu("Step", STEPS, s["step"])
    cmds.setParent("..")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 170), (2, 170)])
    cmds.checkBox(N("Swap"), label="Swap side (L_ <-> R_)", value=False, changeCommand=_w(_on_change))
    cmds.checkBox(N("Fix"), label="Fix to my naming", value=False, changeCommand=_w(_on_change),
                  annotation="Side token + part + type suffix, from Build > Naming.")
    cmds.checkBox(N("Hier"), label="Children too", value=s["hierarchy"], changeCommand=_w(_on_change))
    cmds.checkBox(N("Shapes"), label="Shapes follow (<name>Shape)", value=s["shapes"], changeCommand=_w(_on_change))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Preview", step=2)
    cmds.scrollField(N("Preview"), editable=False, wordWrap=False, height=150, font="fixedWidthFont", text="")
    ui.main_button("Rename", _w(_guard(run)), "One undo.")
    ui.end_section()

    ui.on_selection(N("Preview"), _w(preview))
    preview()


def show():
    ui.open_panel("rename")


SCHEMA = [
    ("start", "Numbers start at", "choice", STARTS),
    ("pad", "Digits", "choice", PADS),
    ("step", "Step", "choice", STEPS),
    ("hierarchy", "Children too", "bool", None),
    ("shapes", "Shapes follow", "bool", None),
]
