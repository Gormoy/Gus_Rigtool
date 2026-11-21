"""
Gus_Rigtool main window: every tool in a tab, as a dockable panel.

    import gus_rigtool.main as gr; gr.show()

Each tab has a "Pop out" button that opens the tool in its own panel, so several
tools can be open side by side.
"""

import os

import maya.cmds as cmds
import maya.mel as mel

import gus_rigtool
from gus_rigtool import registry
from gus_rigtool.core import quick, ui, utils

SHELF = "Gus_Rigtool"


WINDOW_KEY = "window"            # 5.7: "new" (default) or "old" - Toolbox > Settings > Window


def new_window():
    """True: the 5.7 window (the default); False: the 5.6 one (Toolbox > Settings > Window)."""
    return utils.load_setting(WINDOW_KEY, "new") != "old"


def use_window(which):
    """'new' or 'old': which window gr.show() opens from now on - the other one closes, this one opens."""
    utils.save_setting(WINDOW_KEY, "old" if which == "old" else "new")
    try:                        # after the click: the button that asked is in the window that closes
        cmds.evalDeferred(lambda: _switch(which))
    except (RuntimeError, AttributeError):
        _switch(which)


def _switch(which):
    if which == "old":
        try:
            from gus_rigtool.newui import window
            window.close()
        except Exception:
            pass
        ui.open_panel(ui.MAIN_KEY)
    else:
        try:
            if cmds.workspaceControl(ui.panel_name(ui.MAIN_KEY), exists=True):
                cmds.deleteUI(ui.panel_name(ui.MAIN_KEY))
        except RuntimeError:
            pass
        from gus_rigtool.newui import window
        window.show("settings")


def show():
    if new_window():
        try:
            from gus_rigtool.newui import window
            return window.show()
        except Exception as e:                  # the new window can't open: the old one, and say why
            ui.report_error(e, "new window")
    ui.open_panel(ui.MAIN_KEY)


def show_tool(key):
    if new_window():
        try:
            from gus_rigtool.newui import window
            return window.show(key)
        except Exception as e:
            ui.report_error(e, "new window")
    ui.open_panel(key)


def _icon(key):
    path = os.path.join(gus_rigtool.ROOT, "icons", "gr_%s.png" % key)
    return path.replace("\\", "/") if os.path.isfile(path) else "pythonFamily.png"


# 5.7.9: the shelf in the sidebar's order, a gap between areas (Build rig is Build's: not twice)
SHELF_GROUPS = [["home"], ["build", "face", "ribbon", "joints"], ["skin", "fixes"],
                ["controls_tab", "behaviour", "attrs", "channels", "spaces", "follow", "stick"],
                ["constrain", "connect", "nodes", "sdk"], ["checker", "organize", "publish"],
                ["select", "groups", "mirror", "rename", "pivots"], ["settings", "main", "reload"]]


def _shelf_buttons():
    """[[(label, key, tooltip, command)]] - one list per area, in the sidebar's order."""
    tools = dict((k, (lab, sub)) for k, lab, _m, sub in registry.TOOLS)
    special = {"main": ("Main", "Gus_Rigtool - every tool", "import gus_rigtool.main as gr; gr.show()"),
               "reload": ("Reload", "Reload Gus_Rigtool after updating its files",
                          "import gus_rigtool; gus_rigtool.reload_all(); import gus_rigtool.main as gr; gr.show()")}
    groups = []
    for keys in SHELF_GROUPS:
        g = []
        for k in keys:
            if k in special:
                lab, tip, cmd = special[k]
                g.append((lab, k, tip, cmd))
            else:
                try:                                       # (Publish is a page of Check & publish, not a tab)
                    lab, sub = tools[k] if k in tools else registry.get(k)[1::2]
                except KeyError:
                    continue
                g.append((lab, k, sub, "import gus_rigtool.main as gr; gr.show_tool('%s')" % k))
        if g:
            groups.append(g)
    return groups


def _shelf_menu(key):
    """Right-click on a tool's shelf button: its settings, and favourites (5.7.9)."""
    items = []
    try:
        if getattr(registry.module(key), "SCHEMA", None):
            items.append(("Settings of %s..." % registry.get(key)[1],
                          "import gus_rigtool.newui.favourites as F; F.open_settings('%s')" % key))
    except Exception:
        pass
    items.append(("Add to / take off favourites",
                  "import gus_rigtool.newui.favourites as F; F.toggle('%s')" % key))
    items.append(("Pop out (its own panel)", "import gus_rigtool.newui.favourites as F; F.pop('%s')" % key))
    return items


def make_shelf(*_):
    """
    Fill the 'Gus_Rigtool' shelf with one button per tool, then the quick shortcuts
    (Freeze, Center pivot...; which ones: Settings tab). If the shelf exists its buttons
    are replaced (never added twice); otherwise the shelf is created.
    """
    if cmds.shelfLayout(SHELF, exists=True):
        for child in cmds.shelfLayout(SHELF, query=True, childArray=True) or []:
            try:
                cmds.deleteUI(child)
            except RuntimeError:
                pass
    else:
        mel.eval('addNewShelfTab "%s"' % SHELF)
    groups = _shelf_buttons()
    buttons = [b for g in groups for b in g]
    for gi, group in enumerate(groups):
        if gi:
            try:
                cmds.separator(parent=SHELF, style="shelf", horizontal=False)
            except RuntimeError:
                pass
        for label, key, annotation, command in group:
            flags = {}
            if key not in ("main", "reload"):
                menu = _shelf_menu(key)
                flags = {"menuItem": menu, "menuItemPython": list(range(len(menu)))}
            tip = annotation + (" (right-click: its settings)" if flags else "")
            try:
                cmds.shelfButton(parent=SHELF, label=label, annotation=tip, image=_icon(key), command=command,
                                 sourceType="python", **flags)
            except (RuntimeError, TypeError):           # its menu refused: the button anyway, without it
                cmds.shelfButton(parent=SHELF, label=label, annotation=annotation, image=_icon(key),
                                 command=command, sourceType="python")
    shortcuts = quick.shelf_buttons()
    if shortcuts:
        try:
            cmds.separator(parent=SHELF, style="shelf", horizontal=False)
        except RuntimeError:
            pass
    for key, label, annotation, command, menu in shortcuts:
        # left-click: the usual version; right-click: the variants (saved with the shelf)
        flags = {}
        if menu:
            flags = {"menuItem": [(m, c) for m, c in menu],
                     "menuItemPython": list(range(len(menu)))}
        cmds.shelfButton(parent=SHELF, label=label, annotation=annotation + " (right-click for more)",
                         image=_icon("q_" + key), command=command, sourceType="python", **flags)
    try:
        mel.eval("saveAllShelves $gShelfTopLevel")
    except RuntimeError:
        pass
    utils.info("Gus_Rigtool", "shelf '%s' ready with %d tool buttons and %d shortcuts."
               % (SHELF, len(buttons), len(shortcuts)))
