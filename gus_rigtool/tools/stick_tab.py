"""
Stick to skin: controls that ride on a skinned mesh (lips, cheeks, brows, nose...) - moved out of Follow (4.2.0).

    import gus_rigtool.main as gr; gr.show_tool("stick")

Select the controls, then the skinned mesh LAST, Stick. Each control reads the skin weights under it and follows
those joints the way the skin does (except the joints it moves itself), with a 'stick' slider (0 = its parent,
1 = on the skin). Unstick puts them back. Show follow joints: what a stuck control follows.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, ui, utils

TOOL = "Stick to skin"
SETTINGS_KEY = "stick"
DEFAULTS = {}

_P, N, _w, _guard = ui.tool_helpers("p_stick_", TOOL)


def stick(*_):
    from gus_rigtool.core import sticky
    sel = utils.selected_transforms()
    if len(sel) < 2:
        raise RuntimeError("select the controls, then the skinned mesh LAST.")
    mesh, ctrls = sel[-1], sel[:-1]
    if not cmds.listRelatives(mesh, shapes=True, type="mesh"):
        raise RuntimeError("the last selected (%s) isn't a mesh - select the controls, then the mesh last."
                           % naming.short_name(mesh))
    ignore = [j for j in (cmds.textField(N("StickIgnore"), query=True, text=True) or "").replace(",", " ").split()
              if cmds.objExists(j)]
    with utils.undo_chunk("gusrigStick"):
        sticky.stick(ctrls, mesh, rotate=bool(cmds.checkBox(N("StickRotate"), query=True, value=True)),
                     ignore=ignore)


def _take_ignore(*_):
    joints = cmds.ls(selection=True, type="joint") or []
    if not joints:
        raise RuntimeError("select the joints the copy must not follow.")
    cmds.textField(N("StickIgnore"), edit=True, text=" ".join(naming.short_name(j) for j in joints))


def show_follow(*_):
    from gus_rigtool.core import sticky
    stuck = [n for n in utils.selected_transforms() if sticky.read(n)]
    if not stuck:
        raise RuntimeError("select a stuck control.")
    weights = {}
    for n in stuck:
        for j, w in sticky.follow_joints(n).items():
            weights[j] = max(weights.get(j, 0.0), w)
    joints = [j for j in weights if cmds.objExists(j)]
    if not joints:
        raise RuntimeError("its joints are gone - Unstick and Stick again.")
    cmds.select(joints, replace=True)
    utils.info(TOOL, "follows: %s (selected)." % ", ".join("%s %.0f%%" % (naming.short_name(j), weights[j] * 100)
                                                         for j in sorted(weights, key=lambda x: -weights[x])))

def unstick(*_):
    from gus_rigtool.core import sticky
    sel = [n for n in utils.selected_transforms() if sticky.read(n)]
    if not sel:
        raise RuntimeError("select stuck controls.")
    with utils.undo_chunk("gusrigUnstick"):
        for n in sel:
            sticky.unstick(n)
    utils.info(TOOL, "%d control(s) back as before." % len(sel))


def select_stuck(*_):
    from gus_rigtool.core import sticky
    got = cmds.ls("*." + sticky.META, objectsOnly=True, long=True) or []
    if not got:
        raise RuntimeError("no stuck controls in the scene.")
    cmds.select(got, replace=True)



def _what(*_):
    if not cmds.text(N("What"), exists=True):
        return
    sel = utils.selected_transforms(ordered=True)
    if len(sel) < 2:
        text = "Select the controls, then the skinned mesh LAST."
    elif not cmds.listRelatives(sel[-1], shapes=True, type="mesh"):
        text = "The last selected (%s) isn't a mesh: select the mesh last." % naming.short_name(sel[-1])
    else:
        text = "%d control(s) will stick to %s%s." % (len(sel) - 1, naming.short_name(sel[-1]),
                                                     " (turning with it too)" if cmds.checkBox(
                                                         N("StickRotate"), query=True, value=True) else "")
    cmds.text(N("What"), edit=True, label=text)


def build(prefix="p_stick_"):
    _P["p"] = prefix
    ui.section("Stick to skin", step=1, help_text="Controls that ride on the skin: select the controls (any - lips, "
               "cheeks, brows, nose...), then the skinned mesh LAST, Stick. Add more later the same way. Each control "
               "reads the skin weights of the vertices under it (e.g. jaw 60%, head 30%, cheek 10%) and follows those "
               "joints the way the skin does - EXCEPT the joints it moves itself (their share goes to the joint "
               "above) - so it stays on the skin, with no cycle. A 'stick' slider on each control: 0 = follows its parent, 1 = on the skin. By default they "
               "ride with translation only (axes as rigged); tick 'Turn with the skin' to also rotate. Show follow "
               "joints: select a stuck control - selects its joints and prints their weights. Don't follow: joints "
               "it must not follow either (select joints, <). Unstick puts them back. Kept through rebuilds.")
    cmds.checkBox(N("StickRotate"), label="Turn with the skin too (else translation only)", value=False)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(80, 230, 25),
                   columnAttach=[(1, "right", 2), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Don't follow")
    cmds.textField(N("StickIgnore"), placeholderText="joints (optional)",
                   annotation="Joints the hidden copy must not follow (on top of the ones the controls move).")
    cmds.button(label="<", command=_w(_guard(_take_ignore)), annotation="The selected joints.")
    cmds.setParent("..")
    cmds.text(N("What"), label="", align="left", wordWrap=True, height=30, font="smallPlainLabelFont")
    ui.row(2, 170)
    cmds.button(label="Stick", backgroundColor=ui.MAIN_BG, command=_w(_guard(stick)),
                annotation="Controls first, the skinned mesh last. One undo.")
    cmds.button(label="Unstick", command=_w(_guard(unstick)), annotation="The selected stuck controls go back.")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Select stuck", command=_w(_guard(select_stuck)), annotation="Every stuck control.")
    cmds.button(label="Show follow joints", command=_w(_guard(show_follow)),
                annotation="Select a stuck control: selects the joints it follows (weights in the Script Editor).")
    cmds.setParent("..")
    ui.end_section()
    ui.on_selection(N("What"), _w(_what))
    _what()


def show():
    ui.open_panel("stick")


SCHEMA = []
