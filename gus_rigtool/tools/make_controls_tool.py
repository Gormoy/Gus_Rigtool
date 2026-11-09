"""
Make controls: a control on each selected joint or object, in one click.

    import gus_rigtool.main as gr; gr.show_tool("makectrl")

  Shape, size (auto: half the bone, or the object's size), facing axis, side colour.
  Groups: a stack from the Groups tool (Offset, Control: _offset, _sdk, _driven...).
  Drive : Constrain (parent + scale constraint; the skeleton stays as it is) - Parent (the joint goes under
          the control) - Direct (connections, rest values kept).
  Follow the hierarchy: a joint chain gets an FK chain of controls.
  Both sides: the selection's L_ / R_ twins get controls too.
Joints are never frozen. Names: L_arm_jnt -> L_arm_ctrl, L_arm_ctrl_offset.
"""

import maya.cmds as cmds

from gus_rigtool.core import make_controls as MC
from gus_rigtool.core import naming, ui, utils

TOOL = "Make controls"
SETTINGS_KEY = "makectrl"
DRIVES = ["Constrain", "Parent", "Direct"]
AXES = ["X", "Y", "Z"]
DEFAULTS = {"shape": "circle", "auto_size": True, "size": 1.0, "size_factor": 1.0, "face": 1, "stack": "_offset",
            "drive": 1, "scale": True, "hierarchy": True, "lock": True, "tag": True, "side_colour": True,
            "both_sides": False}

_P, N, _w, _guard = ui.tool_helpers("p_makectrl_", TOOL)


def _shape_names():
    from gus_rigtool.core import shape_data
    out = []
    for _cat, items in shape_data.builtin_shapes():
        out += [n for n, _d in items]
    try:
        from gus_rigtool.tools.shape_library import load_custom
        out += sorted(n for n in load_custom() if n not in out)
    except Exception:
        pass
    return out


def _ui():
    return {
        "shape": cmds.optionMenu(N("Shape"), query=True, value=True),
        "auto_size": cmds.checkBox(N("Auto"), query=True, value=True),
        "size": cmds.floatField(N("Size"), query=True, value=True),
        "size_factor": cmds.floatField(N("Factor"), query=True, value=True),
        "face": cmds.radioButtonGrp(N("Face"), query=True, select=True),
        "stack": cmds.textField(N("Stack"), query=True, text=True),
        "drive": cmds.radioButtonGrp(N("Drive"), query=True, select=True),
        "scale": cmds.checkBox(N("Scale"), query=True, value=True),
        "hierarchy": cmds.checkBox(N("Hier"), query=True, value=True),
        "lock": cmds.checkBox(N("Lock"), query=True, value=True),
        "tag": cmds.checkBox(N("Tag"), query=True, value=True),
        "side_colour": cmds.checkBox(N("SideCol"), query=True, value=True),
        "both_sides": cmds.checkBox(N("Both"), query=True, value=True),
    }


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass
    what()


def _stack(o):
    from gus_rigtool.tools.group_maker import parse_suffixes
    return parse_suffixes(o["stack"]) or ["_offset"]


def _args(o):
    return dict(shape=o["shape"], size=None if o["auto_size"] else o["size"], face=AXES[o["face"] - 1],
                stack=_stack(o), drive=MC.DRIVE[o["drive"] - 1], scale=o["scale"], hierarchy=o["hierarchy"],
                lock=o["lock"], tag=o["tag"], side_colour=o["side_colour"], both_sides=o["both_sides"],
                size_factor=o["size_factor"])


def what(*_):
    """The 'What will happen' line."""
    if not cmds.text(N("What"), exists=True):
        return
    try:
        o = _ui()
    except RuntimeError:
        return
    sel = utils.selected_transforms(ordered=True)
    if not sel:
        cmds.text(N("What"), edit=True, label="Select the joints or objects to put controls on.")
        return
    rows = MC.plan(sel, _stack(o), o["hierarchy"], o["both_sides"])
    lines = []
    for node, ctrl, groups, par, note in rows[:4]:
        if note:
            lines.append("%s: %s" % (naming.short_name(node), note))
        else:
            lines.append("%s  ->  %s > %s%s" % (naming.short_name(node), " > ".join(groups), ctrl,
                                               ("   (under %s)" % par) if par else ""))
    if len(rows) > 4:
        lines.append("... and %d more" % (len(rows) - 4))
    drive = {1: "constrained (parent%s)" % (" + scale" if o["scale"] else ""), 2: "parented under the control",
             3: "connected"}[o["drive"]]
    lines.append("%d control(s); the joints / objects get %s." % (len([r for r in rows if not r[4]]), drive))
    cmds.text(N("What"), edit=True, label="\n".join(lines))


def run(*_):
    o = _ui()
    _save()
    sel = utils.selected_transforms(ordered=True)
    if not sel:
        raise RuntimeError("select the joints or objects to put controls on.")
    out = MC.make(sel, **_args(o))
    skipped = len(MC.plan(sel, _stack(o), o["hierarchy"], o["both_sides"])) - len(out)
    msg = "%d control(s): %s" % (len(out), ", ".join(naming.short_name(c) for _n, c in out[:5]) +
                                 (" ..." if len(out) > 5 else ""))
    if skipped > 0:
        utils.warn(TOOL, msg + ". %d already had one (skipped)." % skipped)
    else:
        utils.info(TOOL, msg + ".")
    what()


def _use_stack(*_):
    from gus_rigtool.tools import group_maker as gm
    i = cmds.optionMenu(N("StackMenu"), query=True, select=True) - 2
    all_ = gm.stacks()
    if 0 <= i < len(all_):
        cmds.textField(N("Stack"), edit=True, text=all_[i][1])
        _save()


def _on_auto(*_):
    try:
        cmds.floatField(N("Size"), edit=True, enable=not cmds.checkBox(N("Auto"), query=True, value=True))
        cmds.floatField(N("Factor"), edit=True, enable=cmds.checkBox(N("Auto"), query=True, value=True))
    except RuntimeError:
        pass
    _save()


def _light():
    sel = utils.selected_transforms()
    if not sel:
        return "warn", "Select the joints or objects to put controls on."
    return "ok", "%s. Check the line under the options, then Make controls." % ui.selection_summary(sel)


def _stop_pick():
    from gus_rigtool.core import body_stop
    from gus_rigtool.tools import checker
    sel = utils.selected_transforms()
    meshes = [n for n in sel if cmds.listRelatives(n, shapes=True, type="mesh")]
    ctrls = [n for n in sel if checker.is_control(n)]
    if not ctrls:
        raise RuntimeError("select the body mesh, then the chain's first control (or every control to limit).")
    if len(ctrls) == 1:
        ctrls = body_stop.chain_controls(ctrls[0])
    return (meshes[0] if meshes else None), ctrls


def body_stop_fit(*_):
    from gus_rigtool.core import body_stop
    body, ctrls = _stop_pick()
    if not body:
        raise RuntimeError("select the body mesh first, then the chain's first control.")
    lines = body_stop.fit(body, ctrls)
    print("Stop at the body:\n" + "\n".join("  " + x for x in lines))
    utils.info(TOOL, "%d control(s) limited at the body - details in the Script Editor; 'body_stop_extra' on %s "
               "gives more room." % (sum(1 for x in lines if "towards the body" in x), naming.short_name(ctrls[0])))


def body_stop_remove(*_):
    from gus_rigtool.core import body_stop
    _body, ctrls = _stop_pick()
    n = body_stop.remove(ctrls)
    utils.info(TOOL, "body stop taken off %d control(s)." % n)


def build(prefix="p_makectrl_"):
    from gus_rigtool.tools import group_maker as gm
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()
    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)

    ui.section("Controls on the selection", step=1, help_text="Select joints or objects. Each gets a control "
               "at its pivot with its axes, in an offset group stack. Constrain: the control drives the joint by "
               "a parent (+ scale) constraint and the skeleton stays as it is. Parent: the joint goes under the "
               "control. Direct: connections (the joint's rest values kept). Follow the hierarchy: a chain gets an "
               "FK chain. Joints are never frozen.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 200),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Shape")
    cmds.optionMenu(N("Shape"), changeCommand=_w(_save))
    names = _shape_names()
    for n in names:
        cmds.menuItem(label=n)
    cmds.setParent("..")
    if s["shape"] in names:
        cmds.optionMenu(N("Shape"), edit=True, value=s["shape"])
    cmds.rowLayout(numberOfColumns=5, columnWidth5=(70, 90, 45, 40, 60),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "right", 2), (4, "both", 2), (5, "both", 2)])
    cmds.text(label="Size")
    cmds.checkBox(N("Auto"), label="Auto  x", value=s["auto_size"], changeCommand=_w(_on_auto),
                  annotation="Auto: half the bone (joints) or the object's size, times this factor.")
    cmds.floatField(N("Factor"), value=float(s["size_factor"]), precision=2, minValue=0.01, maxValue=1000000.0, step=0.01, changeCommand=_w(_save))
    cmds.text(label="or")
    cmds.floatField(N("Size"), value=float(s["size"]), precision=2, minValue=0.001, maxValue=1000000.0, step=0.01, changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.radioButtonGrp(N("Face"), label="Facing", numberOfRadioButtons=3, labelArray3=AXES, select=s["face"],
                        columnWidth4=(70, 50, 50, 50), changeCommand=_w(_save),
                        annotation="The control's axis the shape faces (X: along a joint's bone).")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(70, 130, 140),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Groups")
    cmds.optionMenu(N("StackMenu"), changeCommand=_w(_use_stack), annotation="Your Groups tool stacks.")
    cmds.menuItem(label="(stack)")
    for name, text in gm.stacks():
        cmds.menuItem(label="%s: %s" % (name, text))
    cmds.textField(N("Stack"), text=s["stack"], changeCommand=_w(_save),
                   annotation="Group suffixes, top first, comma separated.")
    cmds.setParent("..")
    cmds.radioButtonGrp(N("Drive"), label="Drive", numberOfRadioButtons=3, labelArray3=DRIVES, select=s["drive"],
                        columnWidth4=(70, 85, 65, 65), changeCommand=_w(_save))
    cmds.checkBox(N("Scale"), label="The control scales it too (scale stays unlocked)", value=s["scale"],
                  changeCommand=_w(_save))
    cmds.checkBox(N("Hier"), label="Follow the hierarchy (a chain gets an FK chain of controls)",
                  value=s["hierarchy"], changeCommand=_w(_save))
    cmds.checkBox(N("Both"), label="Both sides (the L_ / R_ twins get controls too)", value=s["both_sides"],
                  changeCommand=_w(_save))
    cmds.checkBox(N("SideCol"), label="Colour by side", value=s["side_colour"], changeCommand=_w(_save))
    cmds.checkBox(N("Lock"), label="Lock and hide visibility (and scale, when it doesn't scale)", value=s["lock"],
                  changeCommand=_w(_save))
    cmds.checkBox(N("Tag"), label="Tag as Maya controllers (pickers and animation tools find them)",
                  value=s["tag"], changeCommand=_w(_save))
    cmds.text(N("What"), label="", align="left", wordWrap=True, height=72, font="smallPlainLabelFont")
    ui.main_button("Make controls", _w(_guard(run)), "One undo.")
    ui.end_section()
    ui.note("In front of the mesh, stop at the body, limits: Controls > Behaviour.")
    ui.on_selection(N("What"), _w(what))
    _on_auto()


def show():
    ui.open_panel("makectrl")


SCHEMA = [
    ("shape", "Shape", "text", None),
    ("auto_size", "Auto size", "bool", None),
    ("size_factor", "Auto size x", "float", None),
    ("size", "Size (when not auto)", "float", None),
    ("face", "Facing", "choice", AXES),
    ("stack", "Group stack", "text", None),
    ("drive", "Drive", "choice", DRIVES),
    ("scale", "The control scales it too", "bool", None),
    ("hierarchy", "Follow the hierarchy", "bool", None),
    ("both_sides", "Both sides", "bool", None),
    ("side_colour", "Colour by side", "bool", None),
    ("lock", "Lock and hide visibility", "bool", None),
    ("tag", "Tag as Maya controllers", "bool", None),
]
