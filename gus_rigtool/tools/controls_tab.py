"""
Controls (5.6.47): Make controls and Shapes in one tab - the long shape list on the left (drag the divider to
make it wider), two short pages on the right:

- Make: a control on each selected joint / object (or one at the centre with nothing selected) - size, facing,
  in front (+X -X +Y -Y +Z -Z, the pivot on the joint or on the shape), drive, groups, hierarchy, both sides.
- Edit shape: for controls that exist - hover a shape in the list to see it on them, click to keep it; move the
  shape in front, shape handles (Done / Cancel / click something else), size, stretch on one axis, turn 90,
  colour, line width, copy, mirror, save a curve as My shape.

The big button says what it will do with your selection; when it can't, it's greyed out and says why.

    import gus_rigtool.main as gr; gr.show_tool("controls_tab")
"""

import os

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.core import control_maker, curves, naming, shape_data, shape_edit, ui, utils

TOOL = "Controls"
SETTINGS_KEY = "controlsTab"
AXES6 = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]
DRIVES = ["Constrain", "Parent", "Direct"]
DEFAULTS = {"shape": "circle", "auto_size": True, "size": 1.0, "size_factor": 1.0, "face": 1, "front": 0.0,
            "front_axis": "+Y", "pivot_on_shape": False, "drive": 1, "stack": "_offset", "hierarchy": True,
            "both_sides": False, "scale": True, "side_colour": True, "lock": True, "tag": True, "name": "",
            "add_side": True, "centre_prefix": "", "edit_front": 1.0, "edit_axis": "+Y", "stretch_axis": "Y",
            "step": 1.2, "line_width": 2.0, "page": 1, "keep_size": True, "gap": 20.0}

_P, N, _w, _guard = ui.tool_helpers("p_controls_", TOOL)
_rows = {}                                             # prefix -> [(shape name, button, category)]
WANT_PAGE = {"page": None}                             # an old Shapes / Make controls button: which page


# --------------------------------------------------------------------------- the shapes
def shape_names():
    """[(category, [names])] - the built-in shapes, then My shapes."""
    out = [(cat, [n for n, _d in items]) for cat, items in shape_data.builtin_shapes()]
    try:
        from gus_rigtool.tools.shape_library import load_custom
        mine = sorted(load_custom())
    except Exception:
        mine = []
    out.append(("My shapes", mine))
    return out


def shape_data_of(name):
    from gus_rigtool.tools.shape_library import all_shapes
    data = all_shapes().get(name)
    if not data:
        raise RuntimeError('shape "%s" not found.' % name)
    return data


def _thumb(name):
    path = os.path.join(gus_rigtool.ROOT, "icons", "shapes", "small", name + ".png")
    return path.replace("\\", "/") if os.path.isfile(path) else None


def picked():
    return utils.tool_settings(SETTINGS_KEY, DEFAULTS).get("shape") or "circle"


def pick(name, *_):
    """A shape clicked in the list - one click does it (5.6.48, like the old Shapes tab): on the Make page the
    controls are made at once; on the Edit shape page it goes on the selected controls."""
    utils.update_setting(SETTINGS_KEY, "shape", name)
    shape_edit.end_preview()
    _mark(name)
    if page() == 2:
        sel = shape_edit.controls(utils.selected_transforms())
        if sel:
            use_shape()
            return
        refresh()
        return
    refresh()
    return make()


def _mark(name):
    for n, b, _c in _rows.get(_P["p"], []):
        try:
            if cmds.control(b, exists=True):
                cmds.iconTextButton(b, edit=True, backgroundColor=(0.32, 0.43, 0.53) if n == name else
                                    (0.27, 0.27, 0.27))
        except RuntimeError:
            pass


def filter_list(*_):
    text = cmds.textField(N("Search"), query=True, text=True).strip().lower().replace(" ", "_")
    for n, b, _c in _rows.get(_P["p"], []):
        try:
            if cmds.control(b, exists=True):
                cmds.control(b, edit=True, manage=(not text or text in n.lower()))
        except RuntimeError:
            pass


def _hover(name, entering):
    """Hovering a shape on the Edit shape page: it shows on the selected controls (not an undo step)."""
    if page() != 2:
        return
    try:
        if entering:
            sel = shape_edit.controls(utils.selected_transforms())
            if sel:
                shape_edit.preview(sel, shape_data_of(name), keep_size=_val("KeepSize", True))
                _set_button(N("UseBtn"), "Use %s on %d control(s)" % (shape_data.label(name), len(sel)), True)
        else:
            shape_edit.end_preview()
            refresh()
    except Exception:
        shape_edit.end_preview()


def _hover_filter(button, name):
    """Qt: tell us when the mouse comes in / goes out of a shape's row (Maya's own buttons can't)."""
    try:
        import maya.OpenMayaUI as omui
        try:
            from PySide6 import QtCore
            from shiboken6 import wrapInstance
        except ImportError:
            from PySide2 import QtCore
            from shiboken2 import wrapInstance
        ptr = omui.MQtUtil.findControl(button)
        if not ptr:
            return None
        widget = wrapInstance(int(ptr), QtCore.QObject)

        class Hover(QtCore.QObject):
            def eventFilter(self, obj, event):
                t = event.type()
                if t == QtCore.QEvent.Enter:
                    _hover(name, True)
                elif t == QtCore.QEvent.Leave:
                    _hover(name, False)
                return False
        f = Hover(widget)
        widget.installEventFilter(f)
        return f
    except Exception:
        return None


def _shape_list():
    _rows[_P["p"]] = []
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
    cmds.textField(N("Search"), placeholderText="Search shapes...", textChangedCommand=_w(filter_list),
                   annotation="Type part of a name: arrow, cube...")
    cmds.scrollLayout(N("ListScroll"), childResizable=True, height=560, horizontalScrollBarThickness=0)
    cmds.columnLayout(N("List"), adjustableColumn=True, rowSpacing=1)
    current = picked()
    for cat, names in shape_names():
        cmds.text(label="  " + cat.upper(), align="left", font="smallBoldLabelFont", height=20)
        if not names and cat == "My shapes":
            cmds.text(label="   (Edit shape > Save the selected curve)", align="left", height=18)
        for n in names:
            thumb = _thumb(n)
            flags = {"image1": thumb} if thumb else {}
            b = cmds.iconTextButton(style="iconAndTextHorizontal" if thumb else "textOnly",
                                    label=" " + shape_data.label(n), annotation=shape_data.label(n), height=26,
                                    align="left", command=_w(lambda n=n: pick(n)),
                                    backgroundColor=(0.32, 0.43, 0.53) if n == current else (0.27, 0.27, 0.27),
                                    **flags)
            if cat == "My shapes":
                cmds.popupMenu(parent=b)
                cmds.menuItem(label='Delete "%s"' % n, command=_w(lambda *_, n=n: _delete_mine(n)))
            _rows[_P["p"]].append((n, b, cat))
            _hover_filter(b, n)
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.setParent("..")


def _delete_mine(name):
    from gus_rigtool.tools import shape_library
    shape_library.delete_custom(name)
    ui.rebuild_page("controls_tab")


# --------------------------------------------------------------------------- reading the page
def _val(name, default=None):
    """A field's value (checkBox / floatField / textField / optionMenu / radioButtonGrp), or default."""
    c = N(name)
    for kind, flag in ((cmds.checkBox, "value"), (cmds.floatField, "value"), (cmds.textField, "text"),
                       (cmds.optionMenu, "value"), (cmds.radioButtonGrp, "select")):
        try:
            if kind(c, exists=True):
                return kind(c, query=True, **{flag: True})
        except (RuntimeError, TypeError):
            pass
    return default


def settings():
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    for key, ctl in (("auto_size", "Auto"), ("size_factor", "Factor"), ("size", "Size"), ("face", "Face"),
                     ("front", "Front"), ("front_axis", "FrontAxis"), ("pivot_on_shape", "PivotShape"),
                     ("drive", "Drive"), ("stack", "Stack"), ("hierarchy", "Hier"), ("both_sides", "Both"),
                     ("scale", "Scale"), ("side_colour", "SideCol"), ("lock", "Lock"), ("tag", "Tag"),
                     ("name", "Name"), ("add_side", "AddSide"), ("centre_prefix", "Centre"),
                     ("edit_front", "EditFront"), ("edit_axis", "EditAxis"), ("stretch_axis", "StretchAxis"),
                     ("step", "Step"), ("line_width", "Width"), ("keep_size", "KeepSize"), ("gap", "Gap")):
        v = _val(ctl)
        if v is not None:
            s[key] = v
    return s


def _save(*_):
    try:
        s = settings()
        s["page"] = page()
        utils.save_setting(SETTINGS_KEY, s)
    except RuntimeError:
        pass
    refresh()


def page():
    try:
        if cmds.tabLayout(N("Pages"), exists=True):
            return cmds.tabLayout(N("Pages"), query=True, selectTabIndex=True)
    except RuntimeError:
        pass
    return 1


def _set_button(name, label, enabled):
    try:
        if cmds.button(name, exists=True):
            cmds.button(name, edit=True, label=label, enable=enabled)
    except RuntimeError:
        pass


def _set_text(name, label):
    try:
        if cmds.text(name, exists=True):
            cmds.text(name, edit=True, label=label)
    except RuntimeError:
        pass


# --------------------------------------------------------------------------- what the buttons will do
def make_targets(sel=None):
    """(the joints / objects to put controls on, the selected controls - 5.6.48: each gets a NEW control at its
    place too, it isn't changed)."""
    sel = utils.selected_transforms(ordered=True) if sel is None else sel
    ctrls = shape_edit.controls(sel)
    return [n for n in sel if n not in ctrls], ctrls


def describe(sel=None):
    """(Make page's line, its button label, button on?, Edit page's line, its button label, button on?)."""
    sel = utils.selected_transforms(ordered=True) if sel is None else sel
    targets, ctrls = make_targets(sel)
    label = shape_data.label(picked())
    if targets or ctrls:
        parts = []
        if targets:
            kinds = "joint" if all(cmds.nodeType(t) == "joint" for t in targets) else "object"
            names = ", ".join(naming.short_name(t) for t in targets[:3]) + (" ..." if len(targets) > 3 else "")
            parts.append("%d %s(s): %s." % (len(targets), kinds, names))
        if ctrls:
            names = ", ".join(naming.short_name(c) for c in ctrls[:3]) + (" ..." if len(ctrls) > 3 else "")
            parts.append("%d control(s): %s - a new control at each one's place (they aren't changed)." %
                         (len(ctrls), names))
        make_line = " ".join(parts)
        make_btn, make_on = "Make %d control(s) (%s)" % (len(targets) + len(ctrls), label), True
    else:
        make_line = "Nothing selected: one control at the centre of the scene."
        make_btn, make_on = "Make 1 control at the centre (%s)" % label, True
    if ctrls:
        names = ", ".join(naming.short_name(c) for c in ctrls[:3]) + (" ..." if len(ctrls) > 3 else "")
        edit_line = "%d control(s): %s. Hover a shape to see it on them; click it to keep." % (len(ctrls), names)
        edit_btn, edit_on = "Use %s on %d control(s)" % (label, len(ctrls)), True
    else:
        edit_line = "Select the controls to change."
        edit_btn, edit_on = "Select controls to change", False
    return make_line, make_btn, make_on, edit_line, edit_btn, edit_on


def refresh(*_):
    try:
        m_line, m_btn, m_on, e_line, e_btn, e_on = describe()
    except RuntimeError:
        return
    _set_text(N("MakeWhat"), m_line)
    _set_button(N("MakeBtn"), m_btn, m_on)
    _set_text(N("EditWhat"), e_line)
    _set_button(N("UseBtn"), e_btn, e_on)
    active = shape_edit.handles_active()
    _set_button(N("HandlesDone"), "Done", active)
    _set_button(N("HandlesCancel"), "Cancel", active)


# --------------------------------------------------------------------------- Make
def make(*_):
    s = settings()
    _save()
    targets, ctrls = make_targets()
    name = s["shape"] = picked()
    made = []
    if ctrls:
        made = on_controls(ctrls, s)
    if targets:
        from gus_rigtool.core import make_controls as MC
        from gus_rigtool.tools.group_maker import parse_suffixes
        out = MC.make(targets, shape=name, size=None if s["auto_size"] else s["size"], face="XYZ"[s["face"] - 1],
                      stack=parse_suffixes(s["stack"]) or ["_offset"], drive=MC.DRIVE[s["drive"] - 1],
                      scale=s["scale"], hierarchy=s["hierarchy"], lock=s["lock"], tag=s["tag"],
                      side_colour=s["side_colour"], both_sides=s["both_sides"], size_factor=s["size_factor"],
                      front=s["front"], front_axis=s["front_axis"], pivot_on_shape=s["pivot_on_shape"])
        utils.info(TOOL, "%d control(s): %s" % (len(out), ", ".join(naming.short_name(c) for _n, c in out[:5]) +
                                                 (" ..." if len(out) > 5 else "")))
        made += [c for _n, c in out]
        if ctrls:
            cmds.select(made, replace=True)
        return made
    if made:
        return made
    return [make_one(s)]


def on_controls(ctrls, s):
    """A NEW control at each selected control's place (its pivot and turn), a bit bigger than it so you can click
    both; the selected controls aren't changed, driven or parented - so it works on any rig, referenced or
    locked (5.6.48: the old Shapes tab did this)."""
    data = shape_data.face(shape_data_of(s["shape"]), "XYZ"[s["face"] - 1])
    style = {}
    if s["side_colour"]:
        from gus_rigtool.core import colors
        style = curves.rgb_style(colors.side_colors()["C"])
    made = []
    with utils.undo_chunk("gusrigControlsOnControls"):
        for c in ctrls:
            try:
                center, half = shape_data.bounds(curves.read_shape(c))
            except (RuntimeError, ValueError, TypeError):
                center, half = (0.0, 0.0, 0.0), 1.0
            if s["auto_size"]:
                shape = shape_data.fit(data, center, half * 1.25 * float(s["size_factor"] or 1.0))
            else:
                shape = shape_data.scale(data, float(s["size"]))
            base = naming.strip_type_suffix(naming.split_namespace(naming.short_name(c))[1])
            ctrl_name, offset_name = naming.ctrl_names(base)
            _top, ctrl = control_maker.new(ctrl_name, shape, style, groups=[offset_name],
                                           matrix=curves.match_matrix(c), tag=s["tag"])
            made.append(ctrl)
        cmds.select(made, replace=True)
    utils.info(TOOL, "%d new control(s) on the selected control(s): %s" % (
        len(made), ", ".join(naming.short_name(c) for c in made[:5]) + (" ..." if len(made) > 5 else "")))
    return made


def make_one(s):
    """Nothing selected: one control at the centre, named from the Name field (or the shape)."""
    from gus_rigtool.tools.shape_library import _with_side
    data = shape_data.scale(shape_data.face(shape_data_of(s["shape"]), "XYZ"[s["face"] - 1]),
                            float(s["size"] if not s["auto_size"] else s["size_factor"]))
    base = (s.get("name") or s["shape"]).strip()
    if base.endswith(naming.CTRL):
        base = base[:-len(naming.CTRL)]
    base = _with_side(base, None, s)
    ctrl_name, offset_name = naming.ctrl_names(base)
    style = {}
    if s["side_colour"]:
        from gus_rigtool.core import colors
        style = curves.rgb_style(colors.side_colors()["C"])
    with utils.undo_chunk("gusrigControlsMakeOne"):
        _top, ctrl = control_maker.new(naming.unique(ctrl_name), data, style,
                                       groups=[naming.unique(offset_name)], tag=s["tag"])
        if s["front"]:
            shape_edit.in_front([ctrl], s["front"], s["front_axis"])
        cmds.select(ctrl, replace=True)
    utils.info(TOOL, "made %s." % naming.short_name(ctrl))
    return ctrl


# --------------------------------------------------------------------------- Edit shape
def _ctrls():
    got = shape_edit.controls(utils.selected_transforms())
    if not got:
        raise RuntimeError("select the controls to change.")
    return got


def use_shape(*_):
    shape_edit.end_preview()
    nodes = _ctrls()
    done = shape_edit.use_shape(nodes, shape_data_of(picked()), keep_size=_val("KeepSize", True))
    cmds.select(nodes, replace=True)
    utils.info(TOOL, "%s on %d control(s)." % (shape_data.label(picked()), len(done)))
    return done


def _ctrls_and_mesh():
    sel = utils.selected_transforms()
    if len(sel) < 2:
        raise RuntimeError("select the controls, then the mesh (last).")
    nodes = shape_edit.controls(sel[:-1])
    if not nodes:
        raise RuntimeError("select the controls to change, then the mesh (last).")
    return nodes, sel[-1], float(settings()["gap"]) / 100.0


def fit_body(*_):
    nodes, mesh, gap = _ctrls_and_mesh()
    got, missed = shape_edit.fit_to_body(nodes, mesh, gap)
    cmds.select(got, replace=True)
    utils.info(TOOL, "%d control(s) fit to %s%s." % (len(got), naming.short_name(mesh),
                                                      (" - %d point(s) found no skin and stayed" % missed)
                                                      if missed else ""))
    return got


def lie_skin(*_):
    nodes, mesh, gap = _ctrls_and_mesh()
    got = shape_edit.lie_on_skin(nodes, mesh, gap)
    cmds.select(got, replace=True)
    utils.info(TOOL, "%d control(s) on the skin of %s." % (len(got), naming.short_name(mesh)))
    return got


def edges_shape(*_):
    sel = cmds.ls(selection=True, flatten=True) or []
    edges = [e for e in sel if ".e[" in e]
    nodes = shape_edit.controls(utils.selected_transforms())           # the mesh itself is never one
    got = shape_edit.from_edges(edges, nodes, float(settings()["gap"]) / 100.0)
    cmds.select(got, replace=True)
    utils.info(TOOL, ("%d control(s) took the loop's shape." % len(got)) if nodes else
               "a new control on the loop: %s." % naming.short_name(got[0]))
    return got


def edit_in_front(*_):
    s = settings()
    _save()
    return shape_edit.in_front(_ctrls(), s["edit_front"], s["edit_axis"])


def size(up, *_):
    s = settings()
    f = max(1.001, float(s["step"]))
    return shape_edit.resize(_ctrls(), f if up else 1.0 / f)


def stretch(up, *_):
    s = settings()
    f = max(1.001, float(s["step"]))
    return shape_edit.stretch(_ctrls(), s["stretch_axis"], f if up else 1.0 / f)


def turn(axis, *_):
    return shape_edit.turn90(_ctrls(), axis)


def handles(*_):
    got = shape_edit.handles_start(_ctrls())
    refresh()
    utils.info(TOOL, "move / turn / size the handle(s); Done - or click something else - keeps it, Cancel throws "
                     "it away.")
    return got


def handles_done(*_):
    n = shape_edit.handles_done()
    refresh()
    return n


def handles_cancel(*_):
    n = shape_edit.handles_cancel()
    refresh()
    return n


def colour(rgb, *_):
    nodes = _ctrls()
    with utils.undo_chunk("gusrigControlsColour"):
        for n in nodes:
            curves.set_color(n, rgb)
    return nodes


def colour_by_side(*_):
    from gus_rigtool.core import colors
    nodes = _ctrls()
    with utils.undo_chunk("gusrigControlsColourSide"):
        for n in nodes:
            colors.apply_side_color(n)
    return nodes


def line_width(*_):
    w = float(settings()["line_width"])
    _save()
    nodes = _ctrls()
    with utils.undo_chunk("gusrigControlsWidth"):
        for n in nodes:
            curves.set_line_width(n, w)
    return nodes


def copy_shape(*_):
    from gus_rigtool.tools import shape_library
    shape_library.copy_shape()


def mirror_shape(*_):
    from gus_rigtool.tools import shape_library
    shape_library.mirror_shape(axis="X")


def save_mine(*_):
    from gus_rigtool.tools import shape_library
    shape_library.save_selected()
    ui.rebuild_page("controls_tab")


# --------------------------------------------------------------------------- the page
def _axis_menu(name, current, annotation):
    cmds.optionMenu(N(name), changeCommand=_w(_save), annotation=annotation, width=58)
    for a in AXES6:
        cmds.menuItem(label=a)
    cmds.optionMenu(N(name), edit=True, value=current if current in AXES6 else "+Y")


def _swatches():
    from gus_rigtool.tools.shape_library import SWATCHES
    cmds.gridLayout(numberOfColumns=6, cellWidthHeight=(34, 20))
    for label, rgb in SWATCHES:
        cmds.button(label="", backgroundColor=rgb, annotation=label,
                    command=_w(_guard(lambda *_, c=rgb: colour(c))))
    cmds.setParent("..")


def _make_page(s):
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    cmds.text(N("MakeWhat"), label="", align="left", wordWrap=True, height=34, backgroundColor=(0.21, 0.27, 0.35))
    ui.section("Size and place")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 70, 20, 60), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                                    (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Size")
    cmds.checkBox(N("Auto"), label="Auto  x", value=s["auto_size"], changeCommand=_w(_save),
                  annotation="Auto: half the bone (joints) or the object's size, times this. Off: the size below.")
    cmds.text(label="")
    cmds.floatField(N("Factor"), value=float(s["size_factor"]), precision=2, minValue=0.01, step=0.05,
                    changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(70, 70), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="or size")
    cmds.floatField(N("Size"), value=float(s["size"]), precision=2, minValue=0.001, step=0.05, changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.radioButtonGrp(N("Face"), label="Facing", numberOfRadioButtons=3, labelArray3=["X", "Y", "Z"],
                        select=s["face"], columnWidth4=(70, 40, 40, 40), changeCommand=_w(_save),
                        annotation="The control's axis the shape faces (X: along a joint's bone).")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(70, 60, 64), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                               (3, "both", 2)])
    cmds.text(label="In front")
    cmds.floatField(N("Front"), value=float(s["front"]), precision=2, step=0.1, changeCommand=_w(_save),
                    annotation="How far in front the shape sits (0: on the joint). Negative: the other way.")
    _axis_menu("FrontAxis", s["front_axis"], "Along which of the control's axes.")
    cmds.setParent("..")
    cmds.checkBox(N("PivotShape"), label="Pivot on the shape (off: the pivot stays on the joint)",
                  value=s["pivot_on_shape"], changeCommand=_w(_save))
    ui.end_section()
    ui.section("How it drives")
    cmds.radioButtonGrp(N("Drive"), label="Drive", numberOfRadioButtons=3, labelArray3=DRIVES, select=s["drive"],
                        columnWidth4=(70, 80, 60, 60), changeCommand=_w(_save))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 160),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Groups")
    cmds.textField(N("Stack"), text=s["stack"], changeCommand=_w(_save),
                   annotation="Group suffixes, top first, comma separated (your Groups stacks: the Groups tab).")
    cmds.setParent("..")
    cmds.checkBox(N("Hier"), label="Follow the hierarchy (a chain gets an FK chain)", value=s["hierarchy"],
                  changeCommand=_w(_save))
    cmds.checkBox(N("Both"), label="Both sides (the L_ / R_ twins too)", value=s["both_sides"], changeCommand=_w(_save))
    cmds.checkBox(N("Scale"), label="The control scales it too", value=s["scale"], changeCommand=_w(_save))
    ui.end_section()
    ui.section("Custom")
    cmds.checkBox(N("SideCol"), label="Colour by side", value=s["side_colour"], changeCommand=_w(_save))
    cmds.checkBox(N("Lock"), label="Lock and hide visibility", value=s["lock"], changeCommand=_w(_save))
    cmds.checkBox(N("Tag"), label="Maya controllers (pick-walk)", value=s["tag"], changeCommand=_w(_save))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 160),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Name")
    cmds.textField(N("Name"), text=s["name"], changeCommand=_w(_save), placeholderText="(nothing selected) the shape",
                   annotation="The name when nothing is selected. Empty: the shape's name.")
    cmds.setParent("..")
    cmds.checkBox(N("AddSide"), label="Add the side from the position (arm -> L_arm)", value=s["add_side"],
                  changeCommand=_w(_save))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 80),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Centre")
    cmds.textField(N("Centre"), text=s["centre_prefix"], changeCommand=_w(_save), annotation="e.g. C_ (empty: none)")
    cmds.setParent("..")
    ui.end_section()
    cmds.button(N("MakeBtn"), label="Make", height=34, backgroundColor=ui.MAIN_BG, command=_w(_guard(make)),
                annotation="One undo. Every control is a Maya controller.")
    cmds.setParent("..")


def _edit_page(s):
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    cmds.text(N("EditWhat"), label="", align="left", wordWrap=True, height=34, backgroundColor=(0.21, 0.27, 0.35))
    cmds.button(N("UseBtn"), label="Use", height=34, backgroundColor=ui.MAIN_BG, command=_w(_guard(use_shape)))
    cmds.checkBox(N("KeepSize"), label="Keep their size and place", value=s["keep_size"], changeCommand=_w(_save))
    ui.section("Move the shape (the pivot stays)")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 56, 64, 60), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                                    (3, "both", 2), (4, "both", 2)])
    cmds.text(label="In front")
    cmds.floatField(N("EditFront"), value=float(s["edit_front"]), precision=2, step=0.1, changeCommand=_w(_save))
    _axis_menu("EditAxis", s["edit_axis"], "Along which of the control's axes.")
    cmds.button(label="Apply", command=_w(_guard(edit_in_front)))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 2), (2, "both", 2),
                                                                        (3, "both", 2)])
    cmds.button(N("HandlesStart"), label="Move / turn / size the shape...", command=_w(_guard(handles)),
                annotation="A handle on the shape only. Done - or click something else - puts it into the curve; "
                           "the control's channels stay at zero. Cancel throws it away.")
    cmds.button(N("HandlesDone"), label="Done", enable=False, command=_w(_guard(handles_done)))
    cmds.button(N("HandlesCancel"), label="Cancel", enable=False, command=_w(_guard(handles_cancel)))
    cmds.setParent("..")
    ui.end_section()
    ui.section("On the body (select the controls, then the mesh)")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(70, 56, 120), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                                 (3, "left", 4)])
    cmds.text(label="Gap %")
    cmds.floatField(N("Gap"), value=float(s["gap"]), precision=0, minValue=0.0, step=5, changeCommand=_w(_save),
                    annotation="How far off the skin: Fit - % of the distance from the pivot to the skin; Lie and "
                               "Edges - % of the shape's size.")
    cmds.text(label="off the skin", align="left")
    cmds.setParent("..")
    cmds.button(label="Fit to the body", command=_w(_guard(fit_body)),
                annotation="Each point goes out (or in) from the pivot to the skin, plus the gap - a bracelet "
                           "around the wrist. Select the controls, then the mesh.")
    cmds.button(label="Lie on the skin", command=_w(_guard(lie_skin)),
                annotation="Each point pressed onto the nearest skin, lifted by the gap - face controls. Select "
                           "the controls, then the mesh.")
    cmds.button(label="Shape from edges", command=_w(_guard(edges_shape)),
                annotation="Select an edge loop (and, in the Outliner, the controls to change): they take its "
                           "shape. Only edges: a new control on the loop.")
    ui.end_section()
    ui.section("Size and turn")
    ui.row(5, 46)
    cmds.text(label="Size")
    cmds.button(label="-", command=_w(_guard(lambda *_: size(False))))
    cmds.button(label="+", command=_w(_guard(lambda *_: size(True))))
    cmds.text(label="step")
    cmds.floatField(N("Step"), value=float(s["step"]), precision=2, minValue=1.01, step=0.05, changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 58, 40, 40), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                                    (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Stretch")
    cmds.optionMenu(N("StretchAxis"), changeCommand=_w(_save), annotation="Longer / shorter on this axis only.")
    for a in "XYZ":
        cmds.menuItem(label=a)
    cmds.optionMenu(N("StretchAxis"), edit=True, value=s["stretch_axis"] if s["stretch_axis"] in "XYZ" else "Y")
    cmds.button(label="-", command=_w(_guard(lambda *_: stretch(False))))
    cmds.button(label="+", command=_w(_guard(lambda *_: stretch(True))))
    cmds.setParent("..")
    ui.row(4, 46)
    cmds.text(label="Turn 90")
    for a in "XYZ":
        cmds.button(label=a, command=_w(_guard(lambda *_, a=a: turn(a))))
    cmds.setParent("..")
    ui.end_section()
    ui.section("Look")
    _swatches()
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 50, 60, 70), columnAttach=[(1, "right", 4), (2, "both", 2),
                                                                                    (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Line width")
    cmds.floatField(N("Width"), value=float(s["line_width"]), precision=1, minValue=-1.0, step=0.5,
                    changeCommand=_w(_save), annotation="-1: Maya's default")
    cmds.button(label="Apply", command=_w(_guard(line_width)))
    cmds.button(label="By side", command=_w(_guard(colour_by_side)), annotation="The L / R / centre colours.")
    cmds.setParent("..")
    ui.end_section()
    ui.section("Copy and mirror")
    cmds.button(label="Copy shape: first selected -> the others", command=_w(_guard(copy_shape)))
    cmds.button(label="Mirror shape L -> R", command=_w(_guard(mirror_shape)),
                annotation="Two controls: first -> second. Otherwise each to its other-side twin.")
    cmds.button(label="Save the selected curve as My shape", command=_w(_guard(save_mine)))
    ui.end_section()
    cmds.setParent("..")


def build(prefix="p_controls_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()
    cmds.paneLayout(N("Split"), configuration="vertical2", paneSize=[(1, 38, 100), (2, 62, 100)],
                    annotation="Drag the line to make the shape list wider or narrower.")
    _shape_list()
    cmds.tabLayout(N("Pages"), innerMarginWidth=4, innerMarginHeight=4, changeCommand=_w(_on_page))
    mk = cmds.scrollLayout(childResizable=True)
    _make_page(s)
    cmds.setParent("..")
    ed = cmds.scrollLayout(childResizable=True)
    _edit_page(s)
    cmds.setParent("..")
    cmds.tabLayout(N("Pages"), edit=True, tabLabel=[(mk, "Make"), (ed, "Edit shape")])
    want = WANT_PAGE.get("page") or int(s.get("page", 1) or 1)
    WANT_PAGE["page"] = None
    cmds.tabLayout(N("Pages"), edit=True, selectTabIndex=max(1, min(2, want)))
    cmds.setParent("..")
    cmds.setParent("..")
    ui.on_selection(N("MakeWhat"), _w(refresh))
    refresh()


def _on_page(*_):
    shape_edit.end_preview()
    _save()


def show(page_index=None):
    WANT_PAGE["page"] = page_index
    ui.open_panel("controls_tab")
