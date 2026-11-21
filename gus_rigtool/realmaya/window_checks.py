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
    from gus_animtool import ui as AU
    if cmds.workspaceControl(AU.WINDOW, exists=True):              # 5.6.48: the title Maya saved was the old one
        label = cmds.workspaceControl(AU.WINDOW, query=True, label=True)
        rep.expect("the Animtool window's title says this version", gus_animtool.__version__ in (label or ""), label)


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
    from gus_rigtool.newui.proxy import cmds as pc            # 5.7: the new window's Controls too
    gr.show_tool("shapes")
    rep.expect("the old Shapes button opens the Controls tab on Edit shape",
               pc.tabLayout(CT.N("Pages"), exists=True) and CT.page() == 2)
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
    for _i in range(3):                            # 5.6.48: Maya runs the 'selection changed' work when it's idle -
        try:                                       # evalDeferred waits in Maya's own idle queue (flushIdleQueue)
            cmds.flushIdleQueue()
        except Exception:
            pass
        try:
            import maya.utils
            maya.utils.processIdleEvents()
        except Exception:
            pass
    rep.expect("shape handle, then click something else: kept (the handle gone)", not SE.handles_active() and
               not cmds.ls("*" + SE.HANDLE + "*"),
               "" if not SE.handles_active() else "Maya hadn't done it yet inside this check - try it by hand: "
               "Edit shape > Move / turn / size, move the handle, click empty space", bad=NOTE)
    if SE.handles_active():
        SE.handles_cancel()
    rep.add(INFO, "look at the Controls tab", "the list on the left (drag the divider), Make / Edit shape on the right")


def new_window(rep):
    """5.7: the new window - opens, its title, one window inside, nothing cut off narrow or wide, docked and
    floating, a Controls action and its Ctrl+Z, Settings, Pop out, the favourites, Skin, profiles.
    5.7.2.1: each part runs on its own - one that crashes is reported and the others still run."""
    import time
    import gus_rigtool
    from gus_rigtool.newui import window as W
    from gus_rigtool.newui import favourites as FV
    from gus_rigtool.newui.qt import QtCore, QtWidgets, maya_widget
    rep.start("The new window (5.7)")
    W.close()
    t0 = time.time()
    f = W.show()
    QtWidgets.QApplication.processEvents()
    rep.add(INFO, "it opened in", "%.2f s" % (time.time() - t0))
    rep.expect("it's open and visible", f is not None and f.isVisible())
    if f is None:
        return
    label = cmds.workspaceControl(W.WS, query=True, label=True)
    rep.expect("its title says this version", gus_rigtool.__version__ in (label or ""), label)

    def settle():
        for _i in range(3):
            QtWidgets.QApplication.processEvents()

    def inside():
        host = maya_widget(W.WS, "control")
        return len([x for x in host.findChildren(W.Frame) if W.alive(x)]) if host is not None else -1

    def cut_pages(area, subs):
        cut = {}
        for width in (330, 700):
            try:
                cmds.workspaceControl(W.WS, edit=True, resizeWidth=width)
            except RuntimeError:
                pass
            for sub in subs:
                f.go(sub[:2])
                settle()
                got = W.cut_off(area)
                if got:
                    cut["%s at %d" % (sub[-1], f.width())] = got[:2]
        return cut

    def one_window():
        n = inside()
        rep.expect("one window inside it (5.7.0 had two, one under the other)", n == 1, "%d inside" % n)

    def controls_cut():
        cut = cut_pages(f._area("controls"), f._area("controls").subs)
        rep.expect("nothing cut off: every Controls page, narrow and wide - no button text cut either", not cut,
                   str(list(cut.items())[:3]))

    def docking():
        cmds.workspaceControl(W.WS, edit=True, tabToControl=("ChannelBoxLayerEditor", -1))
        cmds.workspaceControl(W.WS, edit=True, restore=True)         # its tab in front (5.7.0: it was behind)
        settle()
        n = inside()
        rep.expect("docked next to the Channel Box (its tab in front): there, still one window",
                   W.alive(W._frame["w"]) and W._frame["w"].isVisible() and n == 1, "%d inside" % n)
        cmds.workspaceControl(W.WS, edit=True, floating=True)
        settle()
        rep.expect("...floating again", W._frame["w"].isVisible())

    def limits():
        c = _circle("Check_limit_ctrl")
        cmds.select(c, replace=True)
        f.go(("behaviour", None))
        page = f.areas["controls"].pages["behaviour"]
        page.fields["q7_behaviour_LimMin"].widget.setText("-45")
        page.fields["q7_behaviour_LimMax"].widget.setText("90")
        page.fields["q7_behaviour_LimCh"].widget.setCurrentIndex(5)
        for b in page.cards[0].findChildren(QtWidgets.QPushButton):
            if b.text() == "Apply to the selected controls":
                b.click()
                break
        lim = cmds.transformLimits(c, query=True, rotationZ=True)
        rep.expect("Behaviour > Limits in the new window: rotate Z -45 .. 90 on the control", lim == [-45.0, 90.0],
                   str(lim))
        cmds.undo()
        rep.expect("...one Ctrl+Z takes it off", not any(cmds.transformLimits(c, query=True,
                                                                             enableRotationZ=True) or []))

    def settings():                            # 5.7.2: its own button (5.7.2's check still looked in the Toolbox)
        f.go(("settings", None))
        settle()
        st = f.areas["settings"].widgets.get(("settings", None))
        rep.expect("Settings: its own button at the bottom of the sidebar; today's Settings page in it (the "
                   "Window switch on it)", list(f.nav)[-1] == "settings" and st is not None and
                   st.layout().count() > 0 and st.isVisible())

    def pop_out():
        f.go(("behaviour", None))
        pop = f.pop_out()
        settle()
        rep.expect("Pop out: Behaviour in its own panel (the new look), the main window still open",
                   W.alive(pop) and pop.isVisible() and cmds.workspaceControl(W.pop_name("behaviour"), exists=True)
                   and W.alive(W._frame["w"]))
        if cmds.workspaceControl(W.pop_name("behaviour"), exists=True):
            cmds.deleteUI(W.pop_name("behaviour"))

    def favourites():
        bar = FV.show_bar()
        settle()
        rep.expect("the favourites bar: open, in front of Maya, one square per favourite",
                   bar.isVisible() and bool(bar.windowFlags() & QtCore.Qt.Tool) and list(bar.buttons) == FV.keys(),
                   ", ".join(bar.buttons))
        rep.expect("the favourites row at the top of the window: the same favourites",
                   [b.property("fav") for b in f.favs.findChildren(QtWidgets.QToolButton) if b.property("fav")] ==
                   FV.keys())
        FV.close_bar()

    def skin():
        sk = f._area("skin")
        cut = cut_pages(sk, sk.subs)
        rep.expect("Skin: its 7 sub-pages, nothing cut off narrow or wide", len(sk.subs) == 7 and not cut,
                   str(list(cut.items())[:3]))
        f.go(("skin", "Bind"))
        settle()
        rep.expect("Skin: Skin and Fixes on the top row, Skin's 6 pages under them (5.7.3)",
                   [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)] == ["Skin", "Fixes"] and
                   len(f.tabs2.findChildren(QtWidgets.QPushButton)) == 6)

    def build():                               # 5.7.3: the Build area in the new look, two rows of tabs
        bd = f._area("build")
        cut = cut_pages(bd, bd.subs)
        rep.expect("Build: Build's 4 pages, Face's 3, Ribbon's 2, Joints - nothing cut off narrow or wide (drop-downs "
                   "too)", len(bd.subs) == 10 and not cut, str(list(cut.items())[:3]))
        f.go(("build", 1))
        settle()
        top = [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)]
        under = [b.text() for b in f.tabs2.findChildren(QtWidgets.QPushButton)] if f.tabs2.isVisible() else []
        rep.expect("two rows of tabs: Build Face Ribbon Joints, then Rig builder Animation Existing rig Advanced",
                   top == ["Build", "Face", "Ribbon", "Joints"] and len(under) == 4, "%s / %s" % (top, under))
        f.go(("face", "Build the face"))                   # 5.7.4: Face and Ribbon as steps
        settle()
        steps = [c.title for c in bd.pages["face"].cards if c.isVisible()]
        rep.expect("Face > Build the face: the face map, then Setup, Eyes, Eyelids, Mouth, Brows, Facial strips",
                   bd.face_card.isVisible() and steps == ["Setup", "Eyes", "Eyelids", "Mouth", "Brows",
                                                          "Facial strips"], str(steps))
        f.go(("ribbon", "Make a ribbon"))
        settle()
        rep.expect("Ribbon > Make a ribbon: the steps strip on top (Surface, Joints, Controls, Create)",
                   bd.strip.isVisible())
        rep.add(INFO, "look at Face > Build the face", "select two curves (the line above and below the left eye): "
                "the Eyelids step says they fit and gets a yellow dot; the face map shows the eyelids yellow")
        from gus_rigtool.tools import ribbon_tool as RT
        col = bd.pages["ribbon"].fields.get(RT.N("Color"))
        rep.expect("Ribbon: the control colour is a colour square", col is not None and
                   getattr(col.widget, "swatch", None) is not None)
        f.go(("build", 1))
        settle()
        lists = [w for w in bd.findChildren(QtWidgets.QListWidget) if w.isVisible()]
        from gus_rigtool.tools import build_tab as B
        if not lists or not B._rows.get(B._P["p"]):         # 5.7.3: '(no modules yet)' is a row, not a module
            rep.add(INFO, "Build > Settings of the picked module", "no modules in this scene: not checked (open a "
                    "scene with guides and run it again to check it)")
            return
        was = cmds.ls(selection=True) or []
        try:
            lists[0].clearSelection()
            lists[0].item(0).setSelected(True)
            settle()
            from gus_rigtool.tools import build_tab as B
            form = bd.pages["build"].fields.get(B.N("Form"))
            shown = [w.text() for w in form.widget.findChildren(QtWidgets.QLabel) if w.isVisible()] if form else []
            rep.expect("Build: pick a module in the list - its settings appear (in the new look)",
                       any("  -  " in t for t in shown), str(shown[:2]))
        finally:
            lists[0].clearSelection()
            cmds.select(was, replace=True) if was else cmds.select(clear=True)

    def connect():                             # 5.7.5: the Connect area in the new look
        cn = f._area("connect")
        cut = cut_pages(cn, cn.subs)
        rep.expect("Connect: Constraints, Connections, Nodes' 3 pages, Driven keys - nothing cut off narrow or wide",
                   len(cn.subs) == 6 and not cut, str(list(cut.items())[:3]))
        f.go(("nodes", "See & trace"))
        settle()
        top = [b.text() for b in f.tabs.findChildren(QtWidgets.QPushButton)]
        rep.expect("two rows of tabs: Constraints Connections Nodes Driven keys, then Nodes' pages",
                   top == ["Constraints", "Connections", "Nodes", "Driven keys"] and f.tabs2.isVisible(), str(top))
        [b for b in f.tabs.findChildren(QtWidgets.QPushButton) if b.text() == "Connections"][0].click()
        settle()
        rep.expect("the Connections tab opens Connections (5.7.4 could open the area's last page)",
                   cn.current == ("connect", None), str(cn.current))

    def check_area():                          # 5.7.6: Check & publish in the new look, Publish moved there
        ck = f._area("check")
        cut = cut_pages(ck, ck.subs)
        rep.expect("Check & publish: Checker, Organize, Publish - nothing cut off narrow or wide",
                   [s[0] for s in ck.subs] == ["checker", "organize", "publish"] and not cut,
                   str(list(cut.items())[:3]))
        f.go(("build", 1))
        settle()
        bp = f._area("build").pages.get("build")
        rep.expect("Build > Rig builder: no Publish section (it's on Check & publish > Publish now)",
                   bp is not None and not [c for c in bp.cards if c.title.startswith("Publish")])
        f.go(("checker", None), as_tool=True)
        settle()
        rep.add(INFO, "look at Check & publish", "Run checks and Find repairs: their rows show on the page; "
                "Organize > Analyze the Outliner: the plan shows on the page")

    def profiles():
        was = FV.current()
        try:
            FV.set_current("Skin")
            settle()
            rep.expect("favourites profile 'Skin': the row shows Skin and Fixes",
                       [b.property("fav") for b in f.favs.findChildren(QtWidgets.QToolButton) if b.property("fav")]
                       == ["skin", "fixes"])
        finally:
            FV.set_current(was)

    for name, part in (("one window", one_window), ("Controls pages, narrow and wide", controls_cut),
                       ("docking", docking), ("Limits + Ctrl+Z", limits), ("Settings", settings),
                       ("Pop out", pop_out), ("favourites bar and row", favourites), ("Skin", skin),
                       ("Build", build), ("Connect", connect),
                       ("Check & publish", check_area), ("favourites profiles", profiles)):
        rep.guard("new window: " + name, part)
    rep.add(INFO, "look at the new window", "the sidebar, the coloured areas; drag it narrow - nothing is cut off, "
            "the sidebar becomes icons")
    f.go(("controls_tab", 1))


def new_look(rep):
    """5.7.7: the new look (Settings > Window > Look), the Toolbox in the new window, and your own section order
    (it opens the window in the new look, then puts back the look you had)."""
    from gus_rigtool.core import utils
    from gus_rigtool.newui import theme, widgets
    from gus_rigtool.newui import window as W
    from gus_rigtool.newui.qt import QtWidgets
    rep.start("The new look (5.7.7)")
    was = utils.load_setting(theme.LOOK_KEY, "today")
    sub = ("controls_tab", 2)

    def settle():
        for _i in range(3):
            QtWidgets.QApplication.processEvents()

    def reopen():
        W.close()
        settle()
        f = W.show()
        settle()
        return f

    try:
        utils.save_setting(theme.LOOK_KEY, "new")
        f = reopen()
        rep.expect("Settings > Window > New look: the window opens in it", f is not None and theme.new_look())
        if f is None:
            return

        def pages():
            cut = {}
            for width in (330, 700):
                try:
                    cmds.workspaceControl(W.WS, edit=True, resizeWidth=width)
                except RuntimeError:
                    pass
                for key in W.NEW_LOOK:
                    a = f._area(key)
                    for x in a.subs:
                        f.go(tuple(x[:2]), as_tool=True)
                        settle()
                        got = W.cut_off(a)
                        if got:
                            cut["%s > %s at %d" % (key, x[-1], f.width())] = got[:2]
            rep.expect("new look: nothing cut off on any redone page, narrow and wide", not cut,
                       str(list(cut.items())[:3]))
            f.go(("groups", None), as_tool=True)
            settle()
            folds = [x for x in f.findChildren(widgets.Fold) if x.isVisible() and x.title == "Options"]
            rep.expect("Toolbox > Groups: 'Options (n)' folded, what's set beside it",
                       folds and folds[0].words.text().strip(), folds[0].words.text() if folds else "no fold")

        def order():
            f.go(sub, as_tool=True)
            settle()
            a = f._area("controls")
            first = [c.title for c in a._visual(sub)]
            sz = [c for c in a._cards_of(sub) if c.title.startswith("Size")]
            if not sz:
                rep.expect("Edit shape has 'Size and turn'", False, str(first))
                return
            sz[0].moved.emit(sz[0].title, "@Move to top")
            settle()
            rep.expect("Edit shape: right-click > Move to top puts 'Size and turn' above the swap-shape grid",
                       a._visual(sub)[0].title.startswith("Size"), str([c.title[:20] for c in a._visual(sub)][:3]))
            g = reopen()
            g.go(sub, as_tool=True)
            settle()
            a = g._area("controls")
            rep.expect("...the window opened again keeps that order", a._visual(sub)[0].title.startswith("Size"))
            c = a._cards_of(sub)[0]
            c.moved.emit(c.title, "@Reset order")
            settle()
            rep.expect("...Reset order: the tool's own order", [c.title for c in g._area("controls")._visual(sub)]
                       == first)

        rep.guard("new look: pages", pages)
        rep.guard("new look: your order", order)
        rep.add(INFO, "look at the new look", "Edit shape: drag a section by its title onto another; right-click a "
                "title: Move up / Move down / Move to top / Reset order")
    finally:
        utils.save_setting(theme.LOOK_KEY, was)
        reopen()


CHECKS = [("versions", versions), ("the bar", bar_in_front), ("the shelf", shelf), ("undo", undo),
          ("time slider stretches", bookmarks), ("pick-walk", pick_walk), ("inbetween", inbetween), ("controls tab", controls_tab),
          ("new window", new_window), ("new look", new_look), ("maya facts", lambda rep: __import__("gus_rigtool.realmaya.maya_facts", fromlist=["x"]).facts(rep))]


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
