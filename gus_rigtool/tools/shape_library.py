"""
Control Shape Library

    import gus_rigtool.tools.shape_library as sl; sl.show()      (own window)
    import gus_rigtool.main as gr; gr.show()                       (Shapes tab of the main window)

Click a shape to:
  Create  - nothing selected: a new control at the origin, named from the Name field.
            objects selected: a control matched to each one (position + rotation),
            named after it: L_arm_jnt -> L_arm_ctrl inside L_arm_ctrl_offset.
  Replace - swap the shape of the selected controls. Only the shape nodes change, so
            keys, constraints and connections stay. Colour and line width are kept.

Edit shapes: rotate 90, scale, copy (first selected -> others) and mirror L -> R.
All of them move CVs only, so the control's channels stay clean.

Custom shapes are saved in gus_rigtool/data/controlShapes.json.
Right-click a custom shape button to delete it.
"""

import json
import os

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.core import colors, curves, naming, shape_data, sides, ui, utils

TOOL = "Shape Library"
SETTINGS_KEY = "shapeLibrary"

_P, N, _w, _guard = ui.tool_helpers("p_shapes_", TOOL)


LIBRARY_FILE = os.path.join(gus_rigtool.DATA_DIR, "controlShapes.json")

SWATCHES = [
    ("Red", (1.0, 0.0, 0.0)), ("Blue", (0.0, 0.25, 1.0)), ("Yellow", (1.0, 1.0, 0.0)),
    ("Green", (0.0, 0.8, 0.1)), ("Light blue", (0.3, 0.75, 1.0)), ("Pink", (1.0, 0.4, 0.7)),
    ("Orange", (1.0, 0.5, 0.0)), ("Purple", (0.6, 0.2, 1.0)), ("Cyan", (0.0, 1.0, 1.0)),
    ("Dark red", (0.5, 0.0, 0.0)), ("Dark blue", (0.0, 0.0, 0.5)), ("White", (1.0, 1.0, 1.0)),
]

DEFAULTS = {
    "mode": 1,              # 1 create, 2 replace
    "name": "",
    "size": 1.0,
    "facing": 2,            # 1 X, 2 Y, 3 Z
    "offset": True,
    "match_size": True,
    "scale_step": 1.2,
    "mirror_axis": "X",
    "color": [1.0, 1.0, 0.0],
    "line_width": 1.0,
    "add_side": False,
    "centre_prefix": "",
}


# ---------------------------------------------------------------------------
# library file
# ---------------------------------------------------------------------------

def load_custom():
    if not os.path.exists(LIBRARY_FILE):
        return {}
    try:
        with open(LIBRARY_FILE, "r") as f:
            return json.load(f)
    except (IOError, ValueError) as e:
        utils.warn(TOOL, "could not read %s (%s)." % (LIBRARY_FILE, e))
        return {}


def _write_custom(data):
    if not os.path.isdir(gus_rigtool.DATA_DIR):
        os.makedirs(gus_rigtool.DATA_DIR)
    with open(LIBRARY_FILE, "w") as f:
        json.dump(data, f, indent=1)


def all_shapes():
    """{name: curves} of built-in and custom shapes."""
    out = {}
    for _category, items in shape_data.builtin_shapes():
        out.update(dict(items))
    out.update(load_custom())
    return out


# ---------------------------------------------------------------------------
# settings from the window
# ---------------------------------------------------------------------------

def _ui():
    return {
        "mode": cmds.radioButtonGrp(N("Mode"), query=True, select=True),
        "name": cmds.textFieldGrp(N("Name"), query=True, text=True).strip(),
        "size": cmds.floatSliderGrp(N("Size"), query=True, value=True),
        "facing": cmds.radioButtonGrp(N("Facing"), query=True, select=True),
        "offset": cmds.checkBox(N("Offset"), query=True, value=True),
        "match_size": cmds.checkBox(N("Match"), query=True, value=True),
        "scale_step": cmds.floatField(N("Step"), query=True, value=True),
        "mirror_axis": cmds.optionMenu(N("MirAxis"), query=True, value=True),
        "color": list(cmds.colorSliderGrp(N("Color"), query=True, rgbValue=True)),
        "line_width": cmds.floatField(N("Width"), query=True, value=True),
        "add_side": cmds.checkBox(N("AddSide"), query=True, value=True),
        "centre_prefix": cmds.textField(N("Centre"), query=True, text=True).strip(),
    }


def _on_mode(*_):
    _save_ui()
    ui.refresh_light(N("Light"))


def _save_ui(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _prepared(curves_data, s):
    """Shape turned to the facing axis and scaled to the size setting."""
    axis = "XYZ"[s["facing"] - 1]
    return shape_data.scale(shape_data.face(curves_data, axis), s["size"])


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------

def on_shape(name, *_):
    s = _ui()
    _save_ui()
    data = all_shapes().get(name)
    if not data:
        utils.warn(TOOL, 'shape "%s" not found.' % name)
        return
    if s["mode"] == 2:
        replace_shape(data, s)
    else:
        create_controls(name, data, s)


def create_controls(shape_name, data, s):
    targets = utils.selected_transforms()
    shape = _prepared(data, s)
    style = curves.rgb_style(s["color"], s["line_width"])
    made = []

    with utils.undo_chunk("shapeLibraryCreate"):
        if not targets:
            base = s["name"] or shape_name
            if base.endswith(naming.CTRL):
                base = base[:-len(naming.CTRL)]
            base = _with_side(base, None, s)
            made.append(_new_control(base, shape, style, s["offset"], None))
        else:
            for target in targets:
                base = _with_side(naming.strip_type_suffix(target), target, s)
                made.append(_new_control(base, shape, style, s["offset"], target))
        cmds.select(made, replace=True)

    utils.info(TOOL, "created %d control(s)." % len(made))


def _with_side(base, target, s):
    """
    Add the side to a name that has none: from the target's position (+X = L, -X = R),
    or the centre prefix for centre objects (and for controls made with nothing selected).
    """
    if not s.get("add_side"):
        return base
    pairs = sides.default_pairs()
    if sides.has_side(base, pairs):
        return base
    side = sides.side_from_position(target) if target else "C"
    if side in ("L", "R"):
        return sides.add_side(base, side, pairs[0])
    prefix = s.get("centre_prefix", "")
    ns, short = naming.split_namespace(base)
    if prefix and not short.startswith(prefix):
        return ns + prefix + short
    return base


def _new_control(base, shape, style, offset, target):
    ctrl_name, offset_name = naming.ctrl_names(base)
    ctrl = curves.create_curve_control(ctrl_name, shape, style)
    top = ctrl
    if offset:
        grp = cmds.createNode("transform", name=offset_name)
        ctrl = cmds.parent(ctrl, grp, relative=True)[0]
        top = cmds.ls(grp, long=True)[0]
        ctrl = cmds.ls(ctrl, long=True)[0]
    if target:
        cmds.xform(top, worldSpace=True, matrix=curves.match_matrix(target))
    return ctrl


def replace_shape(data, s):
    targets = utils.selected_transforms()
    if not targets:
        utils.warn(TOOL, "select the controls whose shape should change.")
        return
    done = 0
    with utils.undo_chunk("shapeLibraryReplace"):
        for node in targets:
            if curves.other_shapes(node):
                utils.warn(TOOL, "skipped '%s': it has a non-curve shape." % naming.short_name(node))
                continue
            shape = _prepared(data, s)
            old = curves.read_shape(node)
            if s["match_size"] and old:
                center, half = shape_data.bounds(old)
                shape = shape_data.fit(shape, center, half)
            style = curves.read_style(node) if old else curves.rgb_style(s["color"], s["line_width"])
            curves.set_shape(node, shape, style)
            done += 1
        cmds.select(targets, replace=True)
    utils.info(TOOL, "replaced the shape of %d control(s)." % done)


def _controls_or_warn():
    nodes = [n for n in utils.selected_transforms() if curves.curve_shapes(n)]
    if not nodes:
        utils.warn(TOOL, "select one or more curve controls.")
    return nodes


def rotate_cvs(axis, *_):
    nodes = _controls_or_warn()
    if not nodes:
        return
    if axis == "X":
        func = lambda p: (p[0], -p[2], p[1])
    elif axis == "Y":
        func = lambda p: (p[2], p[1], -p[0])
    else:
        func = lambda p: (-p[1], p[0], p[2])
    with utils.undo_chunk("shapeLibraryRotate"):
        for n in nodes:
            curves.map_cvs_object(n, func)
    utils.info(TOOL, "rotated the shape of %d control(s) 90 deg on %s." % (len(nodes), axis))


def scale_cvs(up, *_):
    nodes = _controls_or_warn()
    if not nodes:
        return
    step = max(1.001, cmds.floatField(N("Step"), query=True, value=True))
    f = step if up else 1.0 / step
    with utils.undo_chunk("shapeLibraryScale"):
        for n in nodes:
            curves.map_cvs_object(n, lambda p: (p[0] * f, p[1] * f, p[2] * f))
    _save_ui()


def copy_shape(*_):
    nodes = utils.selected_transforms()
    if len(nodes) < 2 or not curves.curve_shapes(nodes[0]):
        utils.warn(TOOL, "select the control to copy from first, then the others.")
        return
    data = curves.read_shape(nodes[0])
    done = 0
    with utils.undo_chunk("shapeLibraryCopy"):
        for target in nodes[1:]:
            if curves.other_shapes(target):
                utils.warn(TOOL, "skipped '%s': it has a non-curve shape." % naming.short_name(target))
                continue
            curves.set_shape(target, data, curves.read_style(target))
            done += 1
        cmds.select(nodes, replace=True)
    utils.info(TOOL, "copied the shape of '%s' to %d control(s)."
               % (naming.short_name(nodes[0]), done))


def mirror_shape(*_):
    """
    Two controls selected: the first is mirrored onto the second.
    Otherwise: every selected control is mirrored onto its other-side twin, found by the
    twin link, then the name, then the position. Selecting an offset group = its control.
    """
    from gus_rigtool.tools.mirror_tool import is_ctrl, resolve
    nodes = resolve(utils.selected_transforms(), is_ctrl, False, keep_order=True)[0]
    if not nodes:
        utils.warn(TOOL, "select the L control(s), or an L control then its R control.")
        return
    axis = "XYZ".index(cmds.optionMenu(N("MirAxis"), query=True, value=True))

    pairs_names = sides.default_pairs()

    def twin_of(node):
        """Other-side control: twin link, then name, then position."""
        pl = sides.plan(node, pairs_names, axis, (0.0, 0.0, 0.0), rename_source=False)
        return [pl["existing"]] if pl and pl["existing"] else []

    pairs = []
    if len(nodes) == 2:
        first_twin = twin_of(nodes[0])
        # first -> second when picked by hand (or when the first has no twin)
        if first_twin == [nodes[1]] or not first_twin:
            pairs = [(nodes[0], nodes[1])]
    if not pairs:
        sources = set()
        for n in nodes:
            twin = twin_of(n)
            if not twin:
                utils.warn(TOOL, "no other-side control found for '%s'." % naming.short_name(n))
                continue
            if twin[0] in sources:
                continue                           # both sides selected: mirror one way only
            sources.add(n)
            pairs.append((n, twin[0]))

    done = 0
    with utils.undo_chunk("shapeLibraryMirror"):
        for src, dst in pairs:
            if curves.other_shapes(dst):
                utils.warn(TOOL, "skipped '%s': it has a non-curve shape." % naming.short_name(dst))
                continue
            curves.set_shape(dst, curves.read_shape(src), curves.read_style(dst))
            positions = curves.world_positions(src)
            for shape_pts in positions:
                for p in shape_pts:
                    p[axis] = -p[axis]
            curves.set_world_positions(dst, positions)
            sides.link(src, dst)
            done += 1
        cmds.select(nodes, replace=True)
    utils.info(TOOL, "mirrored %d shape(s) across %s." % (done, "XYZ"[axis]))


def apply_color(rgb=None, *_):
    if rgb is not None:
        cmds.colorSliderGrp(N("Color"), edit=True, rgb=tuple(rgb))
    rgb = cmds.colorSliderGrp(N("Color"), query=True, rgbValue=True)
    _save_ui()
    nodes = [n for n in utils.selected_transforms() if curves.curve_shapes(n)]
    if not nodes:
        return                                     # just sets the colour for new controls
    with utils.undo_chunk("shapeLibraryColor"):
        for n in nodes:
            curves.set_color(n, rgb)


def apply_line_width(*_):
    width = cmds.floatField(N("Width"), query=True, value=True)
    _save_ui()
    nodes = _controls_or_warn()
    with utils.undo_chunk("shapeLibraryLineWidth"):
        for n in nodes:
            curves.set_line_width(n, width)


def save_selected(*_):
    nodes = [n for n in utils.selected_transforms() if curves.curve_shapes(n)]
    if len(nodes) != 1:
        utils.warn(TOOL, "select one curve to save as a shape.")
        return
    result = cmds.promptDialog(title="Save shape", message="Shape name:",
                               text=naming.strip_type_suffix(naming.split_namespace(nodes[0])[1]),
                               button=["Save", "Cancel"], defaultButton="Save",
                               cancelButton="Cancel", dismissString="Cancel")
    if result != "Save":
        return
    name = cmds.promptDialog(query=True, text=True).strip().replace(" ", "_")
    if not name:
        return
    builtin = set()
    for _c, items in shape_data.builtin_shapes():
        builtin.update(n for n, _d in items)
    if name in builtin:
        utils.warn(TOOL, '"%s" is a built-in shape name, pick another.' % name)
        return
    lib = load_custom()
    if name in lib:
        ok = cmds.confirmDialog(title="Save shape", message='Replace the saved shape "%s"?' % name,
                                button=["Replace", "Cancel"], defaultButton="Replace",
                                cancelButton="Cancel", dismissString="Cancel")
        if ok != "Replace":
            return
    data = curves.read_shape(nodes[0])
    _center, half = shape_data.bounds(data)
    lib[name] = shape_data.scale(data, 1.0 / half)            # size 1, pivot kept where it was
    _write_custom(lib)
    _build_custom_frame()
    utils.info(TOOL, 'saved shape "%s" to %s.' % (name, LIBRARY_FILE))


def delete_custom(name, *_):
    ok = cmds.confirmDialog(title="Delete shape", message='Delete the saved shape "%s"?' % name,
                            button=["Delete", "Cancel"], defaultButton="Cancel",
                            cancelButton="Cancel", dismissString="Cancel")
    if ok != "Delete":
        return
    lib = load_custom()
    lib.pop(name, None)
    _write_custom(lib)
    _build_custom_frame()
    utils.info(TOOL, 'deleted shape "%s".' % name)


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

_buttons = {}          # prefix -> [(shape name, button)]


def _thumb(name):
    path = os.path.join(gus_rigtool.ROOT, "icons", "shapes", name + ".png")
    return path.replace("\\", "/") if os.path.isfile(path) else None


def _shape_grid(items, custom=False):
    cmds.gridLayout(numberOfColumns=4, cellWidthHeight=(84, 70) if not custom else (84, 26), autoGrow=True)
    for name in items:
        image = None if custom else _thumb(name)
        if image:
            b = cmds.iconTextButton(style="iconAndTextVertical", image=image, label=shape_data.label(name),
                                    annotation=shape_data.label(name), command=_w(lambda n=name: on_shape(n)))
        else:
            b = cmds.button(label=shape_data.label(name), command=_w(lambda *_, n=name: on_shape(n)))
        if custom:
            cmds.popupMenu(parent=b)
            cmds.menuItem(label='Delete "%s"' % name, command=_w(lambda *_, n=name: delete_custom(n)))
        _buttons.setdefault(_P["p"], []).append((name, b))
    cmds.setParent("..")


def filter_shapes(*_):
    """Show only the shapes whose name contains the search text."""
    text = cmds.textField(N("Search"), query=True, text=True).strip().lower().replace(" ", "_")
    alive = []
    for name, b in _buttons.get(_P["p"], []):
        try:
            if cmds.control(b, exists=True):
                cmds.control(b, edit=True, manage=(not text or text in name.lower()))
                alive.append((name, b))
        except RuntimeError:
            pass
    _buttons[_P["p"]] = alive


def _light():
    sel = utils.selected_transforms(ordered=False)
    if cmds.radioButtonGrp(N("Mode"), query=True, select=True) == 2:
        ctrls = [n for n in sel if curves.curve_shapes(n)]
        if not ctrls:
            return "warn", "Replace: select the controls whose shape should change."
        return "ok", "Click a shape: replaces the shape of %d control(s)." % len(ctrls)
    if not sel:
        return "ok", "Click a shape: one new control at the origin."
    return "ok", "Click a shape: %d control(s), matched to the selection." % len(sel)


def _build_custom_frame():
    if not cmds.frameLayout(N("CustomFrame"), exists=True):
        return
    for child in cmds.frameLayout(N("CustomFrame"), query=True, childArray=True) or []:
        cmds.deleteUI(child)
    cmds.setParent(N("CustomFrame"))
    names = sorted(load_custom())
    if names:
        _shape_grid(names, custom=True)
    else:
        cmds.text(label="No saved shapes yet. Select a curve and press Save.", align="left", wordWrap=True,
                  height=34, width=1)


def build(prefix="p_shapes_"):
    """Content of the Shapes tool, built into the current layout."""
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()

    _buttons[prefix] = []
    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save_ui, _w)

    # -------------------------------------------------- settings
    ui.section("Settings", step=1, help_text="Create makes new controls (one per selected object, matched "
               "to it, or one at the origin). Replace swaps the shape of the selected controls; keys, "
               "constraints and connections stay.")
    cmds.radioButtonGrp(N("Mode"), label="Click a shape to:", numberOfRadioButtons=2,
                        labelArray2=["Create", "Replace"], select=s["mode"],
                        columnWidth3=(110, 80, 80), changeCommand=_w(_on_mode),
                        annotation="Create: new controls. Replace: swap the shape of the selected controls.")
    cmds.floatSliderGrp(N("Size"), label="Size", field=True, minValue=0.1, maxValue=10.0,
                        fieldMaxValue=1000.0, value=s["size"], precision=2,
                        columnWidth3=(50, 60, 200), changeCommand=_w(_save_ui))
    cmds.radioButtonGrp(N("Facing"), label="Facing", numberOfRadioButtons=3,
                        labelArray3=["X", "Y", "Z"], select=s["facing"],
                        columnWidth4=(50, 50, 50, 50), changeCommand=_w(_save_ui),
                        annotation="The axis the flat shapes face.")
    ui.end_section()

    ui.more_options()
    cmds.textFieldGrp(N("Name"), label="Name (nothing selected):", text=s["name"],
                      columnWidth2=(150, 180), changeCommand=_w(_save_ui),
                      annotation="Used when nothing is selected. Empty = the shape name.")
    cmds.checkBox(N("Offset"), label="Create: add an offset group (_ctrl_offset)",
                  value=s["offset"], changeCommand=_w(_save_ui))
    cmds.checkBox(N("AddSide"), label="Create: add the side from the position (arm -> L_arm)",
                  value=s["add_side"], changeCommand=_w(_save_ui),
                  annotation="Only for names without a side. +X = Left, -X = Right. "
                             "Uses the naming pattern of the Mirror tab.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 80))
    cmds.text(label="Create: centre prefix (empty = none)", align="right")
    cmds.textField(N("Centre"), text=s["centre_prefix"], changeCommand=_w(_save_ui),
                   annotation="e.g. C_ for controls in the middle.")
    cmds.setParent("..")
    cmds.checkBox(N("Match"), label="Replace: keep the current size and position",
                  value=s["match_size"], changeCommand=_w(_save_ui))
    ui.end_section()

    # -------------------------------------------------- shapes
    ui.section("Shapes", step=2, help_text="Click a shape. Type in the search field to find one by name. "
               "Your own shapes are at the bottom (right-click one to delete it).")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Search")
    cmds.textField(N("Search"), textChangedCommand=_w(filter_shapes),
                   annotation="Filter the shapes by name, e.g. arrow.")
    cmds.setParent("..")
    for category, items in shape_data.builtin_shapes():
        cmds.frameLayout(label=category, collapsable=True, marginWidth=4, marginHeight=4)
        _shape_grid([n for n, _d in items])
        cmds.setParent("..")

    cmds.frameLayout(N("CustomFrame"), label="My shapes (right-click to delete)", collapsable=True,
                     marginWidth=4, marginHeight=4)
    cmds.setParent("..")
    cmds.button(label="Save selected curve as a shape", height=26, command=_w(save_selected))
    ui.end_section()

    # -------------------------------------------------- edit
    ui.section("Edit shapes (CVs only)", step=3, help_text="These move CVs only, so the control's "
               "channels stay clean. Copy: select the source first. Mirror: an L control then its R, or only "
               "L controls (their twins are found by link, name or position).")
    ui.row(4, 80)
    cmds.text(label="Rotate 90:")
    for axis in "XYZ":
        cmds.button(label=axis, command=_w(lambda *_, a=axis: rotate_cvs(a)))
    cmds.setParent("..")

    ui.row(4, 80)
    cmds.text(label="Scale:")
    cmds.button(label="-", command=_w(lambda *_: scale_cvs(False)))
    cmds.button(label="+", command=_w(lambda *_: scale_cvs(True)))
    cmds.floatField(N("Step"), value=s["scale_step"], minValue=1.01, maxValue=1000000.0, step=0.01, precision=2,
                    annotation="Scale step", changeCommand=_w(_save_ui))
    cmds.setParent("..")

    cmds.button(label="Copy shape (first selected -> others)", height=26, command=_w(copy_shape))

    cmds.rowLayout(numberOfColumns=3, columnWidth3=(80, 70, 190))
    cmds.text(label="Mirror axis:")
    cmds.optionMenu(N("MirAxis"), changeCommand=_w(_save_ui))
    for axis in "XYZ":
        cmds.menuItem(label=axis)
    cmds.optionMenu(N("MirAxis"), edit=True, value=s["mirror_axis"])
    cmds.button(label="Mirror shape L -> R", width=186, command=_w(mirror_shape),
                annotation="Two controls selected: first -> second. Otherwise: each to its "
                           "other-side twin, found by name. (More options in the Mirror tab.)")
    cmds.setParent("..")
    ui.end_section()

    # -------------------------------------------------- colour
    ui.section("Colour and line width", step=4, help_text="Swatches colour the selected controls and "
               "new ones. Colour by side uses the side colours from the Mirror tab / Settings.")
    cmds.gridLayout(numberOfColumns=6, cellWidthHeight=(56, 22))
    for label, rgb in SWATCHES:
        cmds.button(label="", backgroundColor=rgb, annotation=label,
                    command=_w(lambda *_, c=rgb: apply_color(c)))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.colorSliderGrp(N("Color"), label="Colour", rgb=tuple(s["color"]),
                        columnWidth3=(50, 60, 150), changeCommand=_w(_save_ui))
    cmds.button(label="Apply", width=60, command=_w(lambda *_: apply_color()))
    cmds.setParent("..")
    cmds.button(label="Colour by side (L / R / centre colours)", height=24, command=_w(color_by_side),
                annotation="Uses the side colours set in the Mirror tab.")
    ui.row(3, 80)
    cmds.text(label="Line width:")
    cmds.floatField(N("Width"), value=s["line_width"], minValue=-1.0, maxValue=1000000.0, step=0.01, precision=1,
                    annotation="-1 = Maya default", changeCommand=_w(_save_ui))
    cmds.button(label="Apply", command=_w(apply_line_width))
    cmds.setParent("..")
    ui.note("Swatches colour the selected controls, and new ones.")
    ui.end_section()

    _build_custom_frame()


def color_by_side(*_):
    nodes = utils.selected_transforms()
    if not nodes:
        utils.warn(TOOL, "select the controls to colour.")
        return
    with utils.undo_chunk("shapeLibraryColorBySide"):
        for n in nodes:
            colors.apply_side_color(n)
    utils.info(TOOL, "coloured %d node(s) by side." % len(nodes))


def show():
    """The Shape Library as its own dockable panel."""
    ui.open_panel("shapes")


SCHEMA = [
    ("mode", "Click a shape to", "choice", ["Create", "Replace"]),
    ("size", "Size", "float", None),
    ("facing", "Facing", "choice", ["X", "Y", "Z"]),
    ("offset", "Create: add an offset group", "bool", None),
    ("add_side", "Create: add the side from the position", "bool", None),
    ("centre_prefix", "Create: centre prefix", "text", None),
    ("match_size", "Replace: keep the current size and position", "bool", None),
    ("scale_step", "Scale step", "float", None),
    ("line_width", "Line width", "float", None),
]
