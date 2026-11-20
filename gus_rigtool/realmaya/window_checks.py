"""
Test this release (5.6.46): the checks that need Maya's window - the Terminal run (run_maya_tests.py) can't see
them: the bar in front of Maya, the Time Slider's coloured stretches, undo, pick-walk, the shelf's buttons, the
Animtool being the same version as Gus_Rigtool, Add / Remove inbetween.

From the Animtool bar: = > Test this release (in this Maya)...
Or:  from gus_rigtool.realmaya import window_checks; window_checks.run()

It asks before leaving your scene, works on a new empty scene, and ends on a new empty scene - your scene is
never changed or saved by it. The report opens in a window and goes on the clipboard: paste it in your message.
"""

import sys
import traceback

import maya.cmds as cmds

from gus_rigtool.core.report import FAIL, INFO, NOTE, Report

TITLE = "Test this release"
WIN = "gusWindowChecksReport"


def _circle(name, parent=None):
    c = cmds.circle(name=name, normal=(1, 0, 0), constructionHistory=False)[0]
    if parent:
        c = cmds.parent(c, parent)[0]
    return cmds.ls(c, long=True)[0]


def _keyed(name, keys=((1, 0.0), (10, 2.0), (20, 5.0), (30, 1.0)), parent=None):
    n = _circle(name, parent)
    for f, v in keys:
        for a, k in (("translateX", 1.0), ("translateY", 0.5)):
            cmds.setKeyframe(n, attribute=a, time=f, value=v * k)
    return n


def leave_scene():
    """Your scene: saved if you say so (and it has a name), then a new empty one. False: you cancelled."""
    if cmds.file(query=True, modified=True):
        name = cmds.file(query=True, sceneName=True)
        buttons = (["Save, then test", "Don't save", "Cancel"] if name else ["Don't save", "Cancel"])
        got = cmds.confirmDialog(title=TITLE, message="Test this release works on a NEW empty scene.\n\nYour "
                                 "scene has changes%s." % ("" if name else " and no name yet (save it yourself "
                                                                           "first if you want to keep them)"),
                                 button=buttons, defaultButton=buttons[0], cancelButton="Cancel",
                                 dismissString="Cancel")
        if got == "Cancel":
            return False
        if got.startswith("Save"):
            cmds.file(save=True)
    cmds.file(new=True, force=True)
    return True


# --------------------------------------------------------------------------- the checks
def versions(rep):
    import gus_animtool
    import gus_rigtool
    rep.start("Versions: one Animtool")
    rep.add(INFO, "Gus_Rigtool / Gus Animtool", "%s / %s%s" % (
        gus_rigtool.__version__, gus_animtool.__version__,
        " (your installed copy runs Gus_Rigtool's)" if getattr(gus_animtool, "REDIRECTED", None) else ""))
    rep.expect("the Animtool is the same version as Gus_Rigtool", gus_animtool.__version__ == gus_rigtool.__version__,
               "%s vs %s" % (gus_animtool.__version__, gus_rigtool.__version__))
    rep.add(INFO, "your naming read from", getattr(gus_animtool, "LOCAL_ROOT", "?"))


def bar_in_front(rep):
    from gus_animtool import bar
    rep.start("The Animtool bar")
    b = bar.show()
    from gus_animtool.bar import QtCore, QtWidgets
    QtWidgets.QApplication.processEvents()
    rep.expect("it's open and visible", b.isVisible())
    rep.expect("a tool window (stays in front of Maya)", bool(b.windowFlags() & QtCore.Qt.Tool))
    keep = getattr(QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
    if sys.platform == "darwin" and keep is not None:
        rep.expect("the Mac: shown even when Maya isn't the active app", b.testAttribute(keep))
    screen = QtWidgets.QApplication.primaryScreen().availableGeometry() if hasattr(
        QtWidgets.QApplication, "primaryScreen") else None
    if screen is not None:
        rep.expect("on the screen (not lost off the edge)", screen.intersects(b.frameGeometry()),
                   "bar %s, screen %s" % (b.frameGeometry().getRect(), screen.getRect()), bad=NOTE)
    rep.add(INFO, "buttons on it", str(len(b.buttons)))


def shelf(rep):
    from gus_animtool import actions as AC
    from gus_animtool import toolbar
    rep.start("The Gus_Animtool shelf: every button")
    if not cmds.shelfLayout(toolbar.SHELF, exists=True):
        rep.add(NOTE, "no Gus_Animtool shelf", "Animtool window > Settings > Make the shelf")
        return
    labels = []
    for b in cmds.shelfLayout(toolbar.SHELF, query=True, childArray=True) or []:
        try:
            if cmds.objectTypeUI(b) == "shelfButton":
                labels.append(cmds.shelfButton(b, query=True, label=True))
        except RuntimeError:
            pass
    missing = [label for _k, label, _t, _g in AC.ACTIONS if label not in labels]
    rep.expect("every tool has its button (Attach too)", not missing,
               (", ".join(missing) + " - fix: Animtool window > Settings > Make the shelf") if missing else "")


def undo(rep):
    from gus_animtool import arctrail
    rep.start("Undo (Ctrl+Z)")
    n = _keyed("undo_check_ctrl")
    curves = cmds.listConnections(n + ".translateX", source=True, destination=False, type="animCurve")
    rep.add(INFO, "undo on", str(cmds.undoInfo(query=True, state=True)))
    arctrail.make_weighted([n], ask=False)
    rep.expect("timing beads: the curve weighted", cmds.keyTangent(curves, query=True, weightedTangents=True) == [True])
    cmds.undo()
    rep.expect("Ctrl+Z: not weighted again", cmds.keyTangent(curves, query=True, weightedTangents=True) == [False])


def bookmarks(rep):
    from gus_animtool import attach as AT
    rep.start("Attach: the coloured stretches on the Time Slider")
    cmds.playbackOptions(minTime=1, maxTime=40)
    hand = _keyed("L_check_hand_ctrl")
    box = _circle("Check_box_ctrl")
    cmds.currentTime(10)
    AT.attach(box, hand)
    marks = [b for b in cmds.ls(type="timeSliderBookmark") or []
             if (cmds.getAttr(b + ".name") or "").startswith("gusAttach_")]
    rep.expect("a stretch on the Time Slider for the box", len(marks) >= 1, str(len(marks)))
    rep.add(INFO, "look at the Time Slider", "a coloured stretch from frame 10 (the box on the hand)")


def pick_walk(rep):
    from gus_rigtool.core import control_maker as CM, shape_data
    rep.start("Pick-walk (the arrow keys) on controls made by the tool")
    _t, arm = CM.new("Check_arm_ctrl", [shape_data.circle_curve(1.0)], groups=["Check_arm_ctrl_offset"])
    _t, hand = CM.new("Check_hand_ctrl", [shape_data.circle_curve(0.5)], groups=["Check_hand_ctrl_offset"], parent=arm)
    CM.link(hand)
    rep.expect("both are Maya controllers", CM.is_tagged(arm) and CM.is_tagged(hand))
    cmds.select(hand, replace=True)
    try:
        cmds.pickWalk(direction="up")
    except RuntimeError as e:
        rep.add(FAIL, "pick-walk up", str(e))
        return
    got = cmds.ls(selection=True, long=True) or []
    rep.expect("pick-walk up from the hand goes to the arm", got == [arm], str(got))


def inbetween(rep):
    from gus_animtool import keys as K
    rep.start("Add / Remove inbetween")
    a = _keyed("Check_inb_ctrl")
    times = lambda: cmds.keyframe(a + ".translateX", query=True, timeChange=True)
    cmds.select(a, replace=True)
    cmds.currentTime(10)
    K.inbetween(1, "selection")
    rep.expect("Add: the keys after 10 one frame later", times() == [1, 10, 21, 31], str(times()))
    K.inbetween(-1, "selection")
    rep.expect("Remove: back where they were", times() == [1, 10, 20, 30], str(times()))


def controls_tab(rep):
    """5.6.47: the Controls tab opens, the shape list, preview on a real control, the handles and click-away."""
    from gus_rigtool.core import curves, shape_data, shape_edit as SE, control_maker as CM
    from gus_rigtool.tools import controls_tab as CT
    import gus_rigtool.main as gr
    rep.start("The Controls tab (Make controls + Shapes)")
    gr.show_tool("shapes")
    rep.expect("the old Shapes button opens the Controls tab on Edit shape",
               cmds.tabLayout(CT.N("Pages"), exists=True) and CT.page() == 2)
    rep.add(INFO, "shapes in the list", str(len(CT._rows.get(CT._P["p"], []))))
    _t, c = CM.new("Check_shape_ctrl", [shape_data.circle_curve(1.0)])
    own = curves.read_shape(c)
    cmds.select(c, replace=True)
    SE.preview([c], dict(shape_data.builtin_shapes()[0][1])["square"])
    rep.expect("hover preview: the square shows on the control", curves.read_shape(c) != own)
    SE.end_preview()
    rep.expect("...the mouse leaves: its own circle back", curves.read_shape(c) == own)
    hs = SE.handles_start([c])
    cmds.setAttr(hs[0] + ".translateY", 2.0)
    cmds.select(clear=True)                        # clicking something else
    try:
        import maya.utils
        maya.utils.processIdleEvents()
    except Exception:
        pass
    rep.expect("shape handle, then click something else: kept (the handle gone)", not SE.handles_active() and
               not cmds.ls("*" + SE.HANDLE + "*"))
    rep.add(INFO, "look at the Controls tab", "the list on the left (drag the divider), Make / Edit shape on the right")


CHECKS = [("versions", versions), ("the bar", bar_in_front), ("the shelf", shelf), ("undo", undo),
          ("time slider stretches", bookmarks), ("pick-walk", pick_walk), ("inbetween", inbetween), ("controls tab", controls_tab),
          ("maya facts", lambda rep: __import__("gus_rigtool.realmaya.maya_facts", fromlist=["x"]).facts(rep))]


def run(ask=True):
    """Run them all; the report in a window and on the clipboard. Returns the report text (None: cancelled)."""
    if ask and not leave_scene():
        return None
    if not ask:
        cmds.file(new=True, force=True)
    import gus_rigtool
    rep = Report("Test this release (in Maya's window)")
    for name, fn in CHECKS:
        cmds.file(new=True, force=True)
        rep.guard(name, fn, rep)
    cmds.file(new=True, force=True)
    text = rep.text(header_lines=["Gus_Rigtool %s" % gus_rigtool.__version__,
                                  "Maya %s   %s" % (cmds.about(version=True), cmds.about(operatingSystem=True))])
    show(text)
    return text


def show(text):
    try:
        from gus_animtool.bar import QtWidgets
        QtWidgets.QApplication.clipboard().setText(text)
        copied = True
    except Exception:
        copied = False
    try:
        if cmds.window(WIN, exists=True):
            cmds.deleteUI(WIN)
        cmds.window(WIN, title=TITLE + (" - the report is on the clipboard" if copied else ""),
                    widthHeight=(720, 520))
        cmds.paneLayout()
        cmds.scrollField(text=text, editable=False, wordWrap=False)
        cmds.showWindow(WIN)
    except Exception:
        print(text)
        print(traceback.format_exc())
