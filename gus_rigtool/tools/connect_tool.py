"""
Connect: drive attributes of many nodes from one driver.

    import gus_rigtool.main as gr; gr.show_tool("connect")

Select the driver FIRST, then the driven nodes.
  Driver attributes : typed (tx, ry, curl ...) or '< Channel Box' (pick them there).
  Driven attributes : blank = the same names; else in order (or one driver attribute to many).
  In between        : direct, multiply (by a factor), reverse (1 - x), negative (-x) - one node per link.
  Break incoming    : what drives the listed attributes on the selected nodes (keys too) is disconnected.
  What's connected? : a report of the selection's connections.
"""

import maya.cmds as cmds

from gus_rigtool.core import connector, ui, utils

TOOL = "Connect"
SETTINGS_KEY = "connect"
FACTORS = ["-2", "-1", "-0.5", "0.1", "0.25", "0.5", "2", "5", "10"]
DEFAULTS = {"middle": 1, "factor": 6}

_P, N, _w, _guard = ui.tool_helpers("p_connect_", TOOL)


def _ui():
    return {"middle": cmds.optionMenu(N("Middle"), query=True, select=True),
            "factor": cmds.optionMenu(N("Factor"), query=True, select=True),
            "src": connector.parse(cmds.textField(N("Src"), query=True, text=True) or ""),
            "dst": connector.parse(cmds.textField(N("Dst"), query=True, text=True) or "")}


def _save(*_):
    try:
        o = _ui()
        utils.save_setting(SETTINGS_KEY, {"middle": o["middle"], "factor": o["factor"]})
        cmds.optionMenu(N("Factor"), edit=True, enable=o["middle"] == 2)
    except RuntimeError:
        pass


def _light():
    sel = utils.selected_transforms()
    if len(sel) < 2:
        return "idle", "Select the driver FIRST, then the driven nodes."
    return "ok", "driver %s -> %d driven node(s)." % (sel[0].split("|")[-1], len(sel) - 1)


def _from_box(field, *_):
    got = connector.channel_box_attrs()
    if not got:
        raise RuntimeError("pick attributes in the Channel Box first (click / Ctrl-click their names).")
    cmds.textField(N(field), edit=True, text=", ".join(got))


def run(*_):
    sel = utils.selected_transforms()
    if len(sel) < 2:
        raise RuntimeError("select the driver FIRST, then the driven nodes.")
    o = _ui()
    _save()
    pairs = connector.pairs(o["src"], o["dst"])
    factor = float(FACTORS[o["factor"] - 1])
    with utils.undo_chunk("gusrigConnect"):
        made, problems = connector.connect(sel[0], sel[1:], pairs, o["middle"] - 1, factor)
    for p in problems[:6]:
        utils.warn(TOOL, p)
    if not made:
        raise RuntimeError("nothing connected%s." % ((" - " + problems[0]) if problems else ""))
    utils.info(TOOL, "%d connection(s) made (%s)." % (made, connector.MIDDLES[o["middle"] - 1]))


def break_incoming(*_):
    sel = utils.selected_transforms()
    o = _ui()
    names = o["dst"] or o["src"]
    if not sel or not names:
        raise RuntimeError("select the nodes, and type (or pick) the attributes to free.")
    with utils.undo_chunk("gusrigBreak"):
        n = connector.break_incoming(sel, names)
    utils.info(TOOL, "%d connection(s) broken on %s." % (n, ", ".join(names)))


def run_pattern(*_):
    o = _ui()
    _save()
    src = (cmds.textField(N("PatSrc"), query=True, text=True) or "").strip()
    dst = (cmds.textField(N("PatDst"), query=True, text=True) or "").strip()
    if not src or not dst:
        raise RuntimeError("type both: e.g. L_Brow_0*_ctrl.translateY and L_Brow_0*_sdk.rotateX")
    try:
        found = connector.pattern_pairs(src, dst)
    except ValueError as e:
        raise RuntimeError(str(e))
    rows = ["%s  ->  %s" % (connector._short(a.split(".")[0]) + "." + a.split(".", 1)[1],
                            connector._short(b.split(".")[0]) + "." + b.split(".", 1)[1]) for a, b in found]
    if cmds.confirmDialog(title="Gus_Rigtool - connect by pattern", button=["Connect", "Cancel"],
                          defaultButton="Connect", cancelButton="Cancel", dismissString="Cancel",
                          message="%d pair(s) (%s):\n\n%s%s" % (len(rows), connector.MIDDLES[o["middle"] - 1],
                                                                  "\n".join(rows[:30]),
                                                                  "\n..." if len(rows) > 30 else "")) != "Connect":
        return
    with utils.undo_chunk("gusrigConnectPattern"):
        made, problems = connector.connect_pairs(found, o["middle"] - 1, float(FACTORS[o["factor"] - 1]))
    for p in problems[:6]:
        utils.warn(TOOL, p)
    utils.info(TOOL, "%d connection(s) made by pattern." % made)


def show_report(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the nodes.")
    ui.report_window("Connections", connector.report(sel))


def build(prefix="p_connect_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Connect", step=1, help_text="Select the driver FIRST, then the driven nodes. Driven attributes "
               "blank: the same names. Else they go in order (or one driver attribute drives them all). In "
               "between: one node per link (multiply by the factor, reverse 1 - x, or -x).")
    for label, name, hint in (("Driver attrs", "Src", "e.g. curl, rx"), ("Driven attrs", "Dst", "blank = same names")):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth=[(1, 80), (3, 90)],
                       columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
        cmds.text(label=label)
        cmds.textField(N(name), placeholderText=hint)
        cmds.button(label="< Channel Box", command=_w(_guard(lambda *_, f=name: _from_box(f))),
                    annotation="The attributes picked in the Channel Box.")
        cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth=[(1, 80), (2, 140), (3, 50), (4, 70)],
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "right", 4), (4, "both", 2)])
    cmds.text(label="In between")
    cmds.optionMenu(N("Middle"), changeCommand=_w(_save))
    for m in connector.MIDDLES:
        cmds.menuItem(label=m)
    cmds.optionMenu(N("Middle"), edit=True, select=max(1, min(len(connector.MIDDLES), int(s["middle"]))))
    cmds.text(label="Factor")
    cmds.optionMenu(N("Factor"), changeCommand=_w(_save), enable=int(s["middle"]) == 2)
    for f in FACTORS:
        cmds.menuItem(label=f)
    cmds.optionMenu(N("Factor"), edit=True, select=max(1, min(len(FACTORS), int(s["factor"]))))
    cmds.setParent("..")
    ui.main_button("Connect", _w(_guard(run)), "One undo.")
    ui.end_section()

    ui.section("By name pattern", step=2, help_text="Connect many pairs by name: * stands for the part that "
               "changes, matched between the two (01 with 01...). E.g. L_Brow_0*_ctrl.translateY -> "
               "L_Brow_0*_sdk.rotateX. 'In between' and 'Factor' above are used. Shows the pairs first; one undo.")
    for label, name, hint in (("Driver", "PatSrc", "L_Brow_0*_ctrl.translateY"),
                              ("Driven", "PatDst", "L_Brow_0*_sdk.rotateX")):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth=[(1, 60)],
                       columnAttach=[(1, "right", 4), (2, "both", 2)])
        cmds.text(label=label)
        cmds.textField(N(name), placeholderText=hint)
        cmds.setParent("..")
    ui.main_button("Connect by pattern", _w(_guard(run_pattern)), "Shows the pairs first.")
    ui.end_section()

    ui.section("Break / check", step=3, help_text="Break incoming: on the selected nodes, whatever drives the "
               "Driven attributes (or the Driver ones when that field is blank) is disconnected - keys too. "
               "What's connected: a report of the selection.")
    ui.row(2, 170)
    cmds.button(label="Break incoming", command=_w(_guard(break_incoming)))
    cmds.button(label="What's connected?", command=_w(_guard(show_report)))
    cmds.setParent("..")
    ui.end_section()


def show():
    ui.open_panel("connect")


SCHEMA = [
    ("middle", "In between", "choice", connector.MIDDLES),
    ("factor", "Multiply factor", "choice", FACTORS),
]
