"""
The 'Gus_Animtool' shelf and the toolbar under the Time Slider - both made from actions.ACTIONS, with the same
icons and right-click menus.

    import gus_animtool.toolbar as tb; tb.make_shelf(); tb.show()
"""

import maya.cmds as cmds

from gus_animtool import actions as AC
from gus_animtool import anim as A

SHELF = "Gus_Animtool"
BAR = "gusAnimtoolToolbar"
BP = "gusAnimtoolBar_"


def _groups(keys):
    """[[keys of one group], ...] in order."""
    out, last = [], None
    for k in keys:
        g = AC.info(k)[3]
        if g != last:
            out.append([])
            last = g
        out[-1].append(k)
    return out


# ---------------------------------------------------------------------------
# shelf
# ---------------------------------------------------------------------------

def make_shelf(*_):
    """Fill the 'Gus_Animtool' shelf (made if missing; its buttons are replaced, never added twice)."""
    import maya.mel as mel
    if cmds.shelfLayout(SHELF, exists=True):
        for child in cmds.shelfLayout(SHELF, query=True, childArray=True) or []:
            try:
                cmds.deleteUI(child)
            except RuntimeError:
                pass
    else:
        mel.eval('addNewShelfTab "%s"' % SHELF)
    n = 0
    for i, group in enumerate(_groups([k for k, _l, _t, _g in AC.ACTIONS])):
        if i:
            try:
                cmds.separator(parent=SHELF, style="shelf", horizontal=False)
            except RuntimeError:
                pass
        for k in group:
            _k, label, tip, _g = AC.info(k)
            menu = AC.menu_items(k)
            flags = {"menuItem": menu, "menuItemPython": list(range(len(menu)))} if menu else {}
            cmds.shelfButton(parent=SHELF, label=label, annotation=tip + (" (right-click for more)" if menu else ""),
                             image=AC.icon(k), command=AC.command(k), sourceType="python", **flags)
            n += 1
    cmds.shelfButton(parent=SHELF, label="Update", annotation="Install a newer Gus Animtool zip", image=AC.icon("update"),
                     command="import gus_animtool.updater as _u; _u.install_dialog()", sourceType="python")
    try:
        mel.eval("saveAllShelves $gShelfTopLevel")
    except RuntimeError:
        pass
    return n + 1


# ---------------------------------------------------------------------------
# toolbar under the Time Slider
# ---------------------------------------------------------------------------

def _tween_drag(*_):
    from gus_animtool import tween as T
    from gus_animtool import ui
    mode = int(A.opt("tween_mode", 1)) - 1
    T.drag(ui._tween_nodes(), mode, ui._amount(cmds.intSlider(BP + "Tween", query=True, value=True), mode))


def _tween_release(*_):
    from gus_animtool import tween as T
    from gus_animtool import ui
    mode = int(A.opt("tween_mode", 1)) - 1
    value = cmds.intSlider(BP + "Tween", query=True, value=True)
    try:
        if T._drag.get("start") is None:
            T.apply(ui._tween_nodes(), mode, ui._amount(value, mode))
        else:
            T.release(mode, ui._amount(value, mode))
    finally:
        cmds.intSlider(BP + "Tween", edit=True, value=0)


def keys_shown():
    got = A.opt("toolbar_keys", "")
    keys = [AC.RENAMED.get(k, k) for k in (got.split(",") if got else AC.TOOLBAR_DEFAULT) if k]
    keys = list(dict.fromkeys(keys))
    known = set(k for k, _l, _t, _g in AC.ACTIONS)
    return [k for k in keys if k in known]


def build():
    """The toolbar's content (Maya also runs this when it restores the toolbar)."""
    if cmds.rowLayout(BP + "Row", exists=True):
        return
    if cmds.workspaceControl(BAR, exists=True):
        cmds.setParent(BAR)
    keys = keys_shown()
    groups = _groups(keys)
    count = len(keys) + (len(groups) - 1) + (1 if "tween_prev" in keys else 0)
    cmds.scrollLayout(BP + "Scroll", horizontalScrollBarThickness=8, verticalScrollBarThickness=0)
    cmds.rowLayout(BP + "Row", numberOfColumns=max(1, count), columnAttach=[(i + 1, "both", 1) for i in range(count)])
    for gi, group in enumerate(groups):
        if gi:
            cmds.separator(style="single", horizontal=False, width=8, height=28)
        for k in group:
            AC.icon_button(k, width=30, height=30)
            if k == "tween_prev":
                cmds.intSlider(BP + "Tween", minValue=-100, maxValue=100, value=0, width=110,
                               annotation="Tween: drag to see it, let go to apply (mode: the window's Pose tab).",
                               dragCommand=A.guard(_tween_drag), changeCommand=A.guard(_tween_release))
    cmds.setParent("..")
    cmds.setParent("..")


def show(*_):
    """The toolbar, docked under the Time Slider (drag its tab to move it; Maya remembers where)."""
    A.track_selection_order()
    if cmds.workspaceControl(BAR, exists=True):
        cmds.workspaceControl(BAR, edit=True, visible=True, restore=True)
        return BAR
    flags = {}
    if cmds.workspaceControl("TimeSlider", exists=True):
        flags["dockToControl"] = ("TimeSlider", "bottom")
    else:
        flags["floating"] = True
    cmds.workspaceControl(BAR, label="Gus Animtool", retain=False, heightProperty="fixed", initialHeight=48,
                          uiScript="import gus_animtool.toolbar as _tb; _tb.build()", **flags)
    if not cmds.rowLayout(BP + "Row", exists=True):
        build()
    try:
        from gus_animtool import timeslider
        timeslider.install()
    except Exception:
        pass
    return BAR


def hide(*_):
    if cmds.workspaceControl(BAR, exists=True):
        cmds.deleteUI(BAR)


def refresh(*_):
    """Rebuild the toolbar (after changing its buttons)."""
    shown = cmds.workspaceControl(BAR, exists=True)
    hide()
    if shown:
        show()
