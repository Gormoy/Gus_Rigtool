"""
Settings: every option of every Gus_Rigtool tool in one place, and your own defaults.

    import gus_rigtool.main as gr; gr.show_tool("settings")

  Changes here are saved straight away; "Apply to open tools" refreshes open panels.
  Save as my defaults    : remember the current options of every tool as your defaults.
  Use my defaults        : every tool goes back to your saved defaults.
  Reset to Gus_Rigtool      : back to the Gus_Rigtool defaults (your saved defaults are cleared).
"""

import maya.cmds as cmds

from gus_rigtool import registry
from gus_rigtool.core import colors, quick, ui, utils

TOOL = "Settings"

_P, N, _w, _guard = ui.tool_helpers("p_settings_", TOOL)


def _tools():
    """[(key, label, module)] of the tools that have options."""
    out = []
    for key, label, _mod, _sub in registry.TOOLS:
        if key == "settings":
            continue
        mod = registry.module(key)
        if getattr(mod, "SCHEMA", None):
            out.append((key, label, mod))
    return out


def _current(mod):
    return utils.tool_settings(mod.SETTINGS_KEY, mod.DEFAULTS)


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------

def apply_to_open(*_):
    cmds.evalDeferred(ui.rebuild_open)
    utils.info(TOOL, "open tools refreshed with the current settings.")


def save_my_defaults(*_):
    data = {mod.SETTINGS_KEY: _current(mod) for _k, _l, mod in _tools()}
    data[quick.SETTINGS_KEY] = quick.settings()
    utils.save_setting("userDefaults", data)
    utils.info(TOOL, "saved as your defaults for %d tools." % len(data))


def use_my_defaults(*_):
    if not utils.load_setting("userDefaults", {}):
        utils.warn(TOOL, "no saved defaults yet. Use 'Save as my defaults' first.")
        return
    for _k, _l, mod in _tools():
        utils.save_setting(mod.SETTINGS_KEY, {})
    utils.save_setting(quick.SETTINGS_KEY, {})
    cmds.evalDeferred(ui.rebuild_open)
    utils.info(TOOL, "every tool is back to your saved defaults.")


def reset_all(*_):
    ok = cmds.confirmDialog(title="Reset Gus_Rigtool", button=["Reset", "Cancel"],
                            message="Every tool goes back to the Gus_Rigtool defaults.\n"
                                    "Your saved defaults and side colours are cleared too.",
                            defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel")
    if ok != "Reset":
        return
    for _k, _l, mod in _tools():
        utils.save_setting(mod.SETTINGS_KEY, {})
    utils.save_setting(quick.SETTINGS_KEY, {})
    utils.save_setting("userDefaults", {})
    colors.save_side_colors(dict(colors.DEFAULT_SIDE_COLORS))
    cmds.evalDeferred(ui.rebuild_open)
    utils.info(TOOL, "everything is back to the Gus_Rigtool defaults.")


def make_shelf(*_):
    import gus_rigtool.main as gr
    gr.make_shelf()


# ---------------------------------------------------------------------------
# option rows
# ---------------------------------------------------------------------------

_rows = {}             # prefix -> [(control, label)] for the search


def search(text, *_):
    text = (text or "").strip().lower()
    alive = []
    for ctrl, label in _rows.get(_P["p"], []):
        try:
            if cmds.control(ctrl, exists=True) or cmds.layout(ctrl, exists=True):
                kind = cmds.control if cmds.control(ctrl, exists=True) else cmds.layout
                kind(ctrl, edit=True, manage=(not text or text in label.lower()))
                alive.append((ctrl, label))
        except RuntimeError:
            pass
    _rows[_P["p"]] = alive
    for frame, _tool in _frames.get(_P["p"], []):
        try:
            if text:
                cmds.frameLayout(frame, edit=True, collapse=False)
        except RuntimeError:
            pass


_frames = {}


def export_settings(*_):
    path = cmds.fileDialog2(fileMode=0, caption="Export Gus_Rigtool settings", fileFilter="JSON (*.json)")
    if not path:
        return
    n_set, n_data = utils.export_everything(path[0])
    utils.info(TOOL, "exported %d setting(s) and %d data file(s) to %s." % (n_set, n_data, path[0]))


def import_settings(*_):
    path = cmds.fileDialog2(fileMode=1, caption="Import Gus_Rigtool settings", fileFilter="JSON (*.json)")
    if not path:
        return
    n_set, n_data = utils.import_everything(path[0])
    cmds.evalDeferred(ui.rebuild_open)
    utils.info(TOOL, "imported %d setting(s) and %d data file(s)." % (n_set, n_data))


def _option_row(mod, name, label, kind, choices, value):
    key = mod.SETTINGS_KEY

    def setter(convert):
        return _w(lambda v: utils.update_setting(key, name, convert(v)))

    if kind == "bool":
        ctrl = cmds.checkBox(label=label, value=bool(value), changeCommand=setter(bool))
        _rows.setdefault(_P["p"], []).append((ctrl, label))
        return
    row_ctrl = cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 170), adjustableColumn=2,
                              columnAttach=[(1, "right", 4), (2, "both", 2)])
    _rows.setdefault(_P["p"], []).append((row_ctrl, label))
    cmds.text(label=label)
    if kind == "choice":
        menu = cmds.optionMenu(changeCommand=setter(lambda lab, c=choices: c.index(lab) + 1))
        for c in choices:
            cmds.menuItem(label=c)
        try:
            cmds.optionMenu(menu, edit=True, select=int(value))
        except (RuntimeError, ValueError, TypeError):
            pass
    elif kind == "float":
        cmds.floatField(value=float(value), precision=3, changeCommand=setter(float))
    elif kind == "int":
        cmds.intField(value=int(value or 0), changeCommand=setter(int))
    else:
        cmds.textField(text=str(value), changeCommand=setter(lambda t: t.strip()))
    cmds.setParent("..")


def _side_colour_rows():
    current = colors.side_colors()
    controls = {}

    def save(*_):
        colors.save_side_colors({k: list(cmds.colorSliderGrp(c, query=True, rgbValue=True))
                                 for k, c in controls.items()})
    for key, label in (("L", "Left"), ("R", "Right"), ("C", "Centre")):
        controls[key] = cmds.colorSliderGrp(label=label, rgb=tuple(current[key]),
                                            columnWidth3=(60, 60, 200), changeCommand=_w(save))


def _quick_rows():
    current = quick.settings()

    def toggle(key):
        def run(on):
            hidden = [k for k in quick.settings().get("hidden", []) if k != key]
            if not on:
                hidden.append(key)
            utils.update_setting(quick.SETTINGS_KEY, "hidden", hidden)
        return _w(run)

    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 170), (2, 170)])
    for key, label, tip, _call, _menu in quick.BUTTONS:
        box = cmds.checkBox(label=label, value=key not in current.get("hidden", []), annotation=tip,
                            changeCommand=toggle(key))
        _rows[_P["p"]].append((box, "shortcut " + label))
    cmds.setParent("..")

    labels = {"history_default": "Delete history click", "snap_default": "Snap click",
              "point_default": "Loc at sel click"}
    for name, choices in quick.CHOICES.items():
        values = [v for v, _t in choices]

        def changed(text, name=name, choices=choices):
            value = [v for v, t in choices if t == text][0]
            utils.update_setting(quick.SETTINGS_KEY, name, value)

        line = cmds.rowLayout(numberOfColumns=2, columnWidth2=(150, 180), adjustableColumn=2,
                              columnAttach=[(1, "right", 4), (2, "both", 2)])
        cmds.text(label=labels[name])
        menu = cmds.optionMenu(changeCommand=_w(changed),
                               annotation="What a left-click does. The others stay on the right-click menu.")
        for _v, text in choices:
            cmds.menuItem(label=text)
        value = current.get(name, quick.DEFAULTS[name])
        cmds.optionMenu(menu, edit=True, select=(values.index(value) + 1) if value in values else 1)
        cmds.setParent("..")
        _rows[_P["p"]].append((line, "shortcut " + labels[name]))
    cmds.button(label="Update shelf", height=26, command=_w(make_shelf),
                annotation="Rebuild the Gus_Rigtool shelf with the ticked shortcuts.")


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def build(prefix="p_settings_"):
    _P["p"] = prefix
    _rows[prefix] = []
    _frames[prefix] = []

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Search options")
    cmds.textField(textChangedCommand=_w(search), annotation="Type part of an option's name, e.g. colour.")
    cmds.setParent("..")

    ui.section("Update", help_text="Install a newer Gus_Rigtool from its zip (the one you downloaded - no "
               "unzipping, no drag and drop). The old files are kept as gus_rigtool_backup; Gus_Rigtool restarts "
               "and the Script Editor says which version is running.")
    import gus_rigtool
    ui.note("Installed: Gus_Rigtool %s" % gus_rigtool.__version__)
    from gus_rigtool.core import updater
    cmds.button(label="Install update from zip...", height=26, command=_w(_guard(updater.install_dialog)))
    _end()

    ui.section("Defaults", help_text="Options are saved as you change them. 'Save as my defaults' remembers "
               "every tool's options; 'Use my defaults' goes back to them; 'Reset' returns to the Gus_Rigtool "
               "defaults.")
    ui.note("Options are saved as you change them. Tools that are already open pick them up "
            "with 'Apply to open tools' (or when reopened).")
    ui.row(2, 170)
    cmds.button(label="Apply to open tools", height=24, command=_w(apply_to_open))
    cmds.button(label="Save as my defaults", height=24, command=_w(save_my_defaults),
                annotation="Remember every tool's current options as your defaults.")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Use my defaults", height=24, command=_w(use_my_defaults),
                annotation="Every tool goes back to your saved defaults.")
    cmds.button(label="Reset to Gus_Rigtool defaults", height=24, command=_w(reset_all))
    cmds.setParent("..")
    cmds.separator(height=6, style="in")
    ui.row(2, 170)
    cmds.button(label="Export settings...", height=24, command=_w(export_settings),
                annotation="All settings, defaults, presets, side colours and saved shapes in one file.")
    cmds.button(label="Import settings...", height=24, command=_w(import_settings))
    cmds.setParent("..")
    cmds.button(label="Make Gus_Rigtool shelf", height=26, command=_w(make_shelf),
                annotation="A 'Gus_Rigtool' shelf with one button per tool, plus Main and Reload.")
    _end()

    ui.section("Self-test (check the rig builder in this Maya)", collapse=True,
               help_text="Builds a biped and a quadruped in NEW scenes and measures them: the mid spine control "
               "doesn't move the chest, IK/FK switches match (within 0.01), lip corners follow the jaw at 0.5, "
               "toes stay on the toe joint, the head has the neck's axes. You get a report to copy and send. "
               "Save your scene first: it is closed.")
    cmds.button(label="Run self-test (new scenes)...", height=26, command=_w(_guard(run_selftest)),
                annotation="Builds a biped and a quadruped in new scenes and checks them. Save your scene first.")
    cmds.button(label="Maya check: every tool and button (new scenes)...", height=26,
                command=_w(_guard(lambda *_: __import__("gus_rigtool.maya_check", fromlist=["x"]).run())),
                annotation="Opens every tool, builds, skins, rebuilds, publishes and delivers a rig, runs every "
                           "Gus Animtool action, the ribbons, follows, face kit, correctives and picker, then the "
                           "self-test. Problems are listed first. A report to send if anything fails.")
    cmds.button(label="Check this scene (reads only, your character)", height=26,
                command=_w(_guard(lambda *_: __import__("gus_rigtool.scene_check", fromlist=["x"]).run())),
                annotation="Reads the open file - ribbons, follows, joint labels, skin, stuck controls, fixes, face "
                           "kit, guides, connections, picker and every Checker test - and writes a diagnosis. "
                           "Nothing in the scene changes.")
    cmds.button(label="Speed report (times the tools on this character)", height=26,
                command=_w(_guard(lambda *_: __import__("gus_rigtool.core.speed", fromlist=["x"]).run())),
                annotation="How long the tools you press most take on the open character - picker, select, key, "
                           "reset, mirror, poses, isolate, Check this scene, pages - slowest first. Anything it "
                           "changes is undone. Send it if something feels slow.")
    _end()

    ui.section("Side colours")
    _side_colour_rows()
    _end()

    ui.section("Shelf shortcuts", collapse=True,
               help_text="The quick buttons after the tools on the Gus_Rigtool shelf. Left-click a "
                         "button for the usual version, right-click it for the variants. Tick the ones "
                         "you want, then 'Update shelf'.")
    _quick_rows()
    _end()

    for _key, label, mod in _tools():
        frame = ui.section(label, collapse=True)
        _frames[prefix].append((frame, label))
        values = _current(mod)
        for name, text, kind, choices in mod.SCHEMA:
            _option_row(mod, name, text, kind, choices, values.get(name, mod.DEFAULTS.get(name)))
        _end()


def _end():
    """Close a section with a little room under its last row (so nothing sits on the edge)."""
    cmds.separator(height=6, style="none")
    ui.end_section()


def run_selftest(*_):
    msg = "This builds a biped and a quadruped in NEW scenes: the current scene is closed."
    if cmds.file(query=True, modified=True):
        msg += "\n\nYour scene has unsaved changes - they will be lost."
    if cmds.confirmDialog(title="Gus_Rigtool self-test", message=msg, button=["Run", "Cancel"],
                          defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Run":
        return
    from gus_rigtool.builder import selftest
    text = selftest.run()
    ui.report_window("Gus_Rigtool self-test", text)
    utils.info(TOOL, text.splitlines()[1] if len(text.splitlines()) > 1 else "self-test done.")


def show():
    ui.open_panel("settings")
