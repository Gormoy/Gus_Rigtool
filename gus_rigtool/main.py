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


def show():
    ui.open_panel(ui.MAIN_KEY)


def show_tool(key):
    ui.open_panel(key)


def _icon(key):
    path = os.path.join(gus_rigtool.ROOT, "icons", "gr_%s.png" % key)
    return path.replace("\\", "/") if os.path.isfile(path) else "pythonFamily.png"


def _shelf_buttons():
    buttons = [("Main", "main", "Gus_Rigtool - every tool in tabs",
                "import gus_rigtool.main as gr; gr.show()")]
    for key, label, _mod, subtitle in registry.TOOLS:
        buttons.append((label, key, subtitle, "import gus_rigtool.main as gr; gr.show_tool('%s')" % key))
    buttons.append(("Reload", "reload", "Reload Gus_Rigtool after updating its files",
                    "import gus_rigtool; gus_rigtool.reload_all(); import gus_rigtool.main as gr; gr.show()"))
    return buttons


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
    buttons = _shelf_buttons()
    for label, key, annotation, command in buttons:
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
