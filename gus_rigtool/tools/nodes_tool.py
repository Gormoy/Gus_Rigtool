"""
Nodes (5.0.9): utility node networks - the multiplyDivide / clamp / unitConversion / constraint chains your
controls drive.

    import gus_rigtool.main as gr; gr.show_tool("nodes")

  Name utility nodes : multiplyDivide13 -> L_Brow_02_ty_to_fol_11_sdk_md (what feeds it, the channel, what it
                       ends up driving). The selected controls' networks, or the whole scene with nothing
                       selected. Shows the list first; one undo.
  Select the setup   : every utility node and constraint the selected controls drive (and, ticked, the nodes
                       they move) - to delete, export or put in a set.
  5.1.0 - finding problems:
  Trace a channel    : the whole chain driving a channel, back to the controls, with every value.
  Compare sides      : what differs between the selected controls' networks and their twins'.
  At rest            : with the controls at rest, channels a network still moves (an offset left in).
  Find loops         : nodes that feed each other in a circle.
  5.2.0 - building:
  Make a driver      : a control's channel (its positive / negative side, up to a limit) x an amount drives
                       channels of other nodes - clamp + multiplyDivide, named, the other side too.
  5.5.0:
  Node Editor        : the selected control's network alone in the Node Editor, laid out drivers -> driven.
  Setups library     : a network (with its set driven keys) saved to a file and made again on another
                       character, names changed with find / replace or a namespace.
  Clean up           : unit conversions back to back folded away; the heaviest parts of the rig listed.
"""

import maya.cmds as cmds

from gus_rigtool.core import networks, ui, utils

TOOL = "Nodes"
SETTINGS_KEY = "nodes"
DEFAULTS = {"with_driven": 0, "drv_side": 1, "drv_limit": 0.0, "drv_mirror": 1, "drv_flip": 0}
SIDE_LABELS = ["Positive only", "Negative only", "Both ways"]

_P, N, _w, _guard = ui.tool_helpers("p_nodes_", TOOL)


def _light():
    sel = utils.selected_transforms()
    if not sel:
        return "idle", "Select controls to work on their networks (nothing selected = the whole scene for names)."
    return "ok", "%d selected." % len(sel)


def _selection():
    return cmds.ls(selection=True, long=True) or []


def name_nodes(*_):
    sel = _selection()
    if sel:
        net = networks.read(sel)
        pairs = networks.plan(net["utils"])
        where = "the selection's networks"
    else:
        pairs = networks.plan()
        where = "the scene"
    if not pairs:
        utils.info(TOOL, "no utility nodes with default names in %s." % where)
        return
    rows = ["%s  ->  %s" % (networks._short(o), n) for o, n in pairs]
    if cmds.confirmDialog(
            title="Gus_Rigtool - name utility nodes", button=["Rename", "Cancel"], defaultButton="Rename",
            cancelButton="Cancel", dismissString="Cancel",
            message="%d node(s) in %s:\n\n%s%s\n\nOne undo." % (len(pairs), where, "\n".join(rows[:30]),
                                                                  "\n..." if len(rows) > 30 else "")) != "Rename":
        return
    done = networks.rename(pairs)
    utils.info(TOOL, "%d utility node(s) named from their connections." % len(done))


def select_setup(*_):
    sel = _selection()
    if not sel:
        raise RuntimeError("select the control(s) the setup starts from.")
    net = networks.read(sel)
    nodes = net["utils"] + net["cons"]
    if cmds.checkBox(N("Driven"), query=True, value=True):
        nodes += [d for d in net["driven"] if d not in nodes]
    utils.save_setting(SETTINGS_KEY, {"with_driven": int(cmds.checkBox(N("Driven"), query=True, value=True))})
    if not nodes:
        raise RuntimeError("the selection drives no utility nodes or constraints.")
    cmds.select(nodes, replace=True)
    utils.info(TOOL, "selected %d utility node(s), %d constraint(s)%s." % (
        len(net["utils"]), len(net["cons"]),
        (" and %d driven node(s)" % len(net["driven"])) if cmds.checkBox(N("Driven"), query=True, value=True)
        else ""))


def _from_box(*_):
    from gus_rigtool.core import connector
    got = connector.channel_box_attrs()
    if not got:
        raise RuntimeError("pick a channel in the Channel Box first.")
    cmds.textField(N("Attr"), edit=True, text=got[0])


def trace(*_):
    sel = _selection()
    attr = (cmds.textField(N("Attr"), query=True, text=True) or "").strip()
    if not sel or not attr:
        raise RuntimeError("select the node, and type (or pick) the channel: rotateX, translate, tx...")
    lines = []
    for n in sel:
        plug = "%s.%s" % (n, attr)
        if not cmds.objExists(plug):
            lines.append("%s has no %s" % (networks._short(n), attr))
            continue
        lines += ["%s.%s" % (networks._short(n), attr), networks.trace_text(plug), ""]
    ui.report_window("Gus_Rigtool - trace %s" % attr, "\n".join(lines))


def compare(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls of one side (e.g. L_Brow_01-04_ctrl).")
    ui.report_window("Gus_Rigtool - compare sides", networks.compare_text(sel))


def rest(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls (their networks are checked).")
    rows = networks.at_rest(sel)
    if not rows:
        utils.info(TOOL, "at rest: everything the selected controls drive is at its rest value.")
        return
    lines = []
    for plug, v, r, who in rows:
        if v is None and r is None:
            lines.append("%s is not at rest - zero it first" % networks._short(plug))
        else:
            lines.append("%s = %s (rest %s), from %s" % (networks._short(plug), networks._fmt(v), networks._fmt(r),
                                                         who))
    ui.report_window("Gus_Rigtool - at rest", "\n".join(lines))


def find_loops(*_):
    found = networks.loops()
    if not found:
        utils.info(TOOL, "no loops: nothing feeds itself.")
        return
    lines = ["%d loop(s) - each group feeds itself in a circle; cut one connection in it:" % len(found), ""]
    for i, grp in enumerate(found):
        lines.append("%d) %s" % (i + 1, " -> ".join(networks._short(n) for n in grp[:12]) +
                                 (" ..." if len(grp) > 12 else "")))
    ui.report_window("Gus_Rigtool - loops", "\n".join(lines))


def _box_to(field):
    from gus_rigtool.core import connector
    got = connector.channel_box_attrs()
    if not got:
        raise RuntimeError("pick a channel in the Channel Box first.")
    cmds.textField(N(field), edit=True, text=got[0])


def _driver_args():
    from gus_rigtool.core import drivers
    sel = cmds.ls(orderedSelection=True, long=True) or _selection()
    if len(sel) < 2:
        raise RuntimeError("select the driver control FIRST, then the nodes it drives (their _sdk groups).")
    dattr = (cmds.textField(N("DrvAttr"), query=True, text=True) or "").strip()
    tattr = (cmds.textField(N("TgtAttr"), query=True, text=True) or "").strip()
    if not dattr or not tattr:
        raise RuntimeError("type (or pick) the driver's channel and the target channel.")
    raw = (cmds.textField(N("Amount"), query=True, text=True) or "").replace(";", ",")
    try:
        amounts = [float(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        raise RuntimeError("Amount: numbers, e.g. -4 or -4, -2, -1 (one per driven node, in selection order).")
    if not amounts:
        raise RuntimeError("type the amount (how much per unit of the driver), e.g. -4.")
    targets = sel[1:]
    if len(amounts) == 1:
        amounts = amounts * len(targets)
    if len(amounts) != len(targets):
        raise RuntimeError("%d amount(s) for %d driven node(s): give one, or one each." % (len(amounts), len(targets)))
    side = drivers.SIDES[cmds.optionMenu(N("DrvSide"), query=True, select=True) - 1]
    limit = cmds.floatField(N("DrvLimit"), query=True, value=True) or None
    mirror = cmds.checkBox(N("DrvMirror"), query=True, value=True)
    flip = cmds.checkBox(N("DrvFlip"), query=True, value=True)
    utils.save_setting(SETTINGS_KEY, {"drv_side": drivers.SIDES.index(side) + 1, "drv_limit": limit or 0.0,
                                      "drv_mirror": int(mirror), "drv_flip": int(flip),
                                      "with_driven": int(cmds.checkBox(N("Driven"), query=True, value=True))})
    return ("%s.%s" % (sel[0], dattr), [(t, tattr, a) for t, a in zip(targets, amounts)], side, limit, mirror, flip)


def make_driver(*_):
    from gus_rigtool.core import drivers
    args = _driver_args()
    text = drivers.preview(*args)
    if cmds.confirmDialog(title="Gus_Rigtool - make a driver", button=["Make", "Cancel"], defaultButton="Make",
                          cancelButton="Cancel", dismissString="Cancel",
                          message="%s\n\nOne undo." % text) != "Make":
        return
    made, skipped = drivers.make(*args)
    for p in skipped:
        utils.warn(TOOL, p)
    utils.info(TOOL, "%d node(s) made%s." % (len(made), ("; %d skipped" % len(skipped)) if skipped else ""))


# ---- 5.5.0 ----------------------------------------------------------------------------------------------------

def tidy(*_):
    from gus_rigtool.core import network_tools as NT
    sel = _selection()
    if not sel:
        raise RuntimeError("select a control (or a utility node / driven-key curve).")
    nodes, drivers, driven = NT.tidy(sel)
    utils.info(TOOL, "Node Editor: %d network node(s) between %d driver(s) and %d driven node(s)." % (
        len(nodes), len(drivers), len(driven)))


def _setup_name():
    return cmds.textField(N("SetupName"), query=True, text=True).strip()


def _setup_menu_fill():
    from gus_rigtool.core import setups
    menu = N("SetupList")
    if not cmds.optionMenu(menu, exists=True):
        return
    for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    got = setups.names()
    for name in got or ["(none saved)"]:
        cmds.menuItem(label=name, parent=menu)


def _picked_setup():
    name = cmds.optionMenu(N("SetupList"), query=True, value=True) or ""
    if not name or name.startswith("("):
        raise RuntimeError("no setup saved yet: select a control and Save first.")
    return name


def setup_save(*_):
    from gus_rigtool.core import setups
    sel = _selection()
    if not sel:
        raise RuntimeError("select the control(s) whose network to save.")
    name = _setup_name()
    if not name:
        raise RuntimeError("type a name for the setup (brow_raise, cheek_puff...).")
    if name in setups.names() and cmds.confirmDialog(
            title="Gus_Rigtool - setups", message="'%s' is already saved. Replace it?" % name,
            button=["Replace", "Cancel"], defaultButton="Replace", cancelButton="Cancel",
            dismissString="Cancel") != "Replace":
        return
    path, n, outside = setups.save(sel, name)
    _setup_menu_fill()
    print("Setup '%s' saved: %s\n  connects to: %s" % (name, path, ", ".join(outside)))
    utils.info(TOOL, "'%s' saved: %d node(s), connected to %d node(s) outside (listed in the Script Editor)." % (
        name, n, len(outside)))


def _mapping():
    find = cmds.textField(N("SetupFind"), query=True, text=True)
    repl = cmds.textField(N("SetupRepl"), query=True, text=True)
    ns = cmds.textField(N("SetupNs"), query=True, text=True).strip()
    return find, repl, ns


def setup_load(*_):
    from gus_rigtool.core import setups
    name = _picked_setup()
    find, repl, ns = _mapping()
    rows = setups.preview(name, find, repl, ns)
    lost = [there for _o, there, ok in rows if not ok]
    msg = "Make '%s' here. It connects to:\n%s" % (name, "\n".join(
        "  %s %s" % ("ok     " if ok else "MISSING", there) for _o, there, ok in rows[:25]))
    if len(rows) > 25:
        msg += "\n  ... %d more" % (len(rows) - 25)
    if lost:
        msg += "\n\n%d not found: those connections are skipped (change Find / Replace or the namespace)." % len(lost)
    if cmds.confirmDialog(title="Gus_Rigtool - load setup", message=msg, button=["Make", "Cancel"],
                          defaultButton="Make", cancelButton="Cancel", dismissString="Cancel") != "Make":
        return
    got = setups.load(name, find, repl, ns)
    if got["missing"] or got["failed"]:
        print("Setup '%s': not found: %s\n  failed: %s" % (name, ", ".join(got["missing"]) or "-",
                                                          ", ".join(got["failed"]) or "-"))
    utils.info(TOOL, "'%s' made: %d node(s), %d connection(s)%s. One undo." % (
        name, len(got["made"]), got["connected"],
        (", %d skipped - see the Script Editor" % (len(got["missing"]) + len(got["failed"])))
        if got["missing"] or got["failed"] else ""))


def setup_delete(*_):
    from gus_rigtool.core import setups
    name = _picked_setup()
    if cmds.confirmDialog(title="Gus_Rigtool - setups", message="Delete the saved setup '%s'?" % name,
                          button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Delete":
        return
    setups.delete(name)
    _setup_menu_fill()
    utils.info(TOOL, "'%s' deleted from the library." % name)


def setup_folder(*_):
    from gus_rigtool.core import setups
    got = cmds.fileDialog2(fileMode=3, caption="Setups folder", startingDirectory=setups.folder())
    if got:
        utils.save_setting("setups_folder", got[0])
        _setup_menu_fill()
        utils.info(TOOL, "setups folder: %s" % got[0])


def fold(*_):
    from gus_rigtool.core import network_tools as NT
    pairs = NT.double_conversions()
    if not pairs:
        utils.info(TOOL, "no unit conversions back to back.")
        return
    n = NT.fold_conversions()
    utils.info(TOOL, "%d pair(s) of unit conversions folded (the source connected straight). One undo." % n)


def heaviest(*_):
    from gus_rigtool.core import network_tools as NT
    ui.report_window("Gus_Rigtool - heaviest parts", "Nodes by part of the rig (utility nodes, driven keys, "
                     "constraints, expressions, follicles, IK):\n\n" + (NT.heaviest_text(20) or "nothing found"))


def rig_map(*_):
    from gus_rigtool.core import rig_map as RM
    RM.show()


def build(prefix="p_nodes_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Name utility nodes", step=1, help_text="multiplyDivide13, unitConversion260... get a name from "
               "what feeds them and what they end up driving: L_Brow_02_ty_to_fol_11_sdk_md (control, channel, "
               "target, kind). Select controls to name only their networks; nothing selected = the whole scene. "
               "Nodes you named, nodes in a referenced file and nodes with nothing in or out are left alone. "
               "Shows the list first; one undo. (Checker: 'Utility nodes with default names' does the same.)")
    ui.main_button("Name utility nodes from their connections", _w(_guard(name_nodes)), "Shows the list first.")
    ui.end_section()

    ui.section("Select the setup", step=2, help_text="Every utility node and constraint the selected controls "
               "drive, through the whole chain - to delete it, export it or put it in a set. Ticked: the nodes "
               "they move too (careful when deleting: those are your groups / joints).")
    cmds.checkBox(N("Driven"), label="Also the nodes it moves (groups, joints)", value=bool(s["with_driven"]))
    ui.main_button("Select the whole setup", _w(_guard(select_setup)), "From the selected controls.")
    ui.end_section()

    ui.section("Trace a channel", step=3, help_text="Select a node (a group, a joint, a control) and the channel: "
               "every node driving it back to the controls is listed with its values - multiplyDivide factors, "
               "clamp ranges, unit conversions, constraint targets and weights, set driven keys.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth=[(1, 60), (3, 90)],
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Channel")
    cmds.textField(N("Attr"), placeholderText="rotateX, translate, tx...")
    cmds.button(label="< Channel Box", command=_w(_guard(_from_box)))
    cmds.setParent("..")
    ui.main_button("Trace", _w(_guard(trace)), "Opens the chain in a report.")
    ui.end_section()

    ui.section("Make a driver", step=4, help_text="Select the driver control FIRST, then the nodes it drives "
               "(their _sdk groups - a channel already driven is skipped). Driver channel: e.g. translateY; only its "
               "positive side, only its negative side, or both; Limit: stop at this much (0 = no limit). Target "
               "channel: e.g. rotateX. Amount: per unit of the driver (-4: up 1 = -4 degrees) - one for all, or "
               "one each in selection order (-4, -2, -1). Other side too: the same on the R_ twins (Flip if it "
               "turns the wrong way there). Shows what it makes first; one undo.")
    for label, name, hint in (("Driver ch.", "DrvAttr", "translateY"), ("Target ch.", "TgtAttr", "rotateX")):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth=[(1, 70), (3, 90)],
                       columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
        cmds.text(label=label)
        cmds.textField(N(name), placeholderText=hint)
        cmds.button(label="< Channel Box", command=_w(_guard(lambda *_, f=name: _box_to(f))))
        cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth=[(1, 70), (2, 120), (3, 50), (4, 80)],
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "right", 4), (4, "both", 2)])
    cmds.text(label="Side")
    cmds.optionMenu(N("DrvSide"))
    for lab in SIDE_LABELS:
        cmds.menuItem(label=lab)
    cmds.optionMenu(N("DrvSide"), edit=True, select=max(1, min(3, int(s["drv_side"]))))
    cmds.text(label="Limit")
    cmds.floatField(N("DrvLimit"), value=float(s["drv_limit"]), minValue=0.0, maxValue=1000000.0, step=0.01, precision=3)
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth=[(1, 70)],
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Amount")
    cmds.textField(N("Amount"), placeholderText="-4   (or -4, -2, -1: one each)")
    cmds.setParent("..")
    cmds.checkBox(N("DrvMirror"), label="Other side too (the R_ twins)", value=bool(s["drv_mirror"]))
    cmds.checkBox(N("DrvFlip"), label="Flip the amount on the other side", value=bool(s["drv_flip"]))
    ui.main_button("Make the driver", _w(_guard(make_driver)), "Shows what it makes first; one undo.")
    ui.end_section()

    ui.section("Find problems", step=5, help_text="Compare sides: select one side's controls (L_Brow_01-04); every "
               "value that differs from their twins' networks is listed (factors, clamp ranges, weights, a node "
               "fed by another control, a piece only one side has). At rest: with the selected controls at rest, "
               "what their networks still move (an offset left in). Find loops: nodes feeding each other in a "
               "circle (Maya evaluates those wrong or slowly).")
    ui.row(3, 115)
    cmds.button(label="Compare sides", command=_w(_guard(compare)))
    cmds.button(label="At rest?", command=_w(_guard(rest)))
    cmds.button(label="Find loops", command=_w(_guard(find_loops)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Node Editor", step=6, help_text="Select a control (or any node of a setup): its network - the "
               "utility nodes and driven-key curves, the controls driving them and what they move - alone in the "
               "Node Editor, laid out from the drivers on the left to the driven nodes on the right. Rig map: "
               "everything the rig does in one tree (follows, space switches, limits, drivers, jiggles); click "
               "an item to select it.")
    ui.row(2, 150)
    cmds.button(label="Show in Node Editor", backgroundColor=ui.MAIN_BG, command=_w(_guard(tidy)))
    cmds.button(label="Rig map", command=_w(_guard(rig_map)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Setups library", step=7, collapse=True, help_text="Save: the network around the selected "
               "control(s) - utility nodes, set driven key curves with their keys and tangents - to a file under "
               "a name. Load: made again in this scene (another character), connected to the controls / joints "
               "it used by name. Find / Replace changes those names (Hare -> Fox, L_ -> R_); Namespace: when the "
               "character is referenced (Fox:). Shows what it will connect to (and what's missing) first. One "
               "undo.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth=[(1, 70)],
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Name")
    cmds.textField(N("SetupName"), placeholderText="brow_raise")
    cmds.setParent("..")
    ui.main_button("Save the selected network", _w(_guard(setup_save)), "Writes it to the setups folder.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth=[(1, 70)],
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Saved")
    cmds.optionMenu(N("SetupList"))
    cmds.setParent("..")
    _setup_menu_fill()
    for label, name, hint in (("Find", "SetupFind", "Hare"), ("Replace", "SetupRepl", "Fox"),
                              ("Namespace", "SetupNs", "blank = none")):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth=[(1, 70)],
                       columnAttach=[(1, "right", 4), (2, "both", 2)])
        cmds.text(label=label)
        cmds.textField(N(name), placeholderText=hint)
        cmds.setParent("..")
    ui.row(3, 100)
    cmds.button(label="Load", backgroundColor=ui.MAIN_BG, command=_w(_guard(setup_load)))
    cmds.button(label="Delete", command=_w(_guard(setup_delete)))
    cmds.button(label="Folder...", command=_w(_guard(setup_folder)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Clean up", step=8, collapse=True, help_text="Fold conversions: Maya adds a unitConversion "
               "wherever an angle meets a plain number; two back to back that cancel out (degrees -> radians -> "
               "degrees) are removed and the source connected straight. Heaviest parts: how many utility nodes, "
               "driven keys, constraints and expressions each part of the rig has - where to look when the rig "
               "plays slowly.")
    ui.row(2, 150)
    cmds.button(label="Fold conversions", command=_w(_guard(fold)))
    cmds.button(label="Heaviest parts", command=_w(_guard(heaviest)))
    cmds.setParent("..")
    ui.end_section()


def show():
    ui.open_panel("nodes")
