"""
A 'Gus Animtool' section in the Time Slider's right-click menu: copy / paste keys, add / remove inbetweens,
offset and back to original - at the END of Maya's own menu (playblast, keys... all still there). Hooked when Gus
Animtool opens (Settings can turn it off); our part is added after Maya builds its items each time the menu opens.
"""

import maya.cmds as cmds

from gus_animtool import actions as AC
from gus_animtool import anim as A

SUB = "gusAnimtoolTimeSliderSub"
DIV = "gusAnimtoolTimeSliderDiv"
KEEP = "gusAnimtool_tsOriginal"            # optionVar: Maya's own post-menu command, kept across reloads / updates
MAYA_DEFAULT = "updateTimeSliderMenu %s"    # what Maya runs to fill the menu (Maya 2024+)
_state = {"menu": None, "original": None}

ITEMS = [("copy_keys", "Copy keys (this frame / highlighted range)"),
         ("paste_keys", "Paste keys here"),
         ("paste_merge", "Paste keys here, keep mine (merge)"),
         None,
         ("inbetween_add", "Add inbetween"),
         ("inbetween_remove", "Remove inbetween"),
         None,
         ("offset_minus", "Offset selection earlier"),
         ("offset_plus", "Offset selection later"),
         ("offset_back", "Offset: back to original"),
         ("offset_keep", "Offset: keep as original"),
         None,
         ("copy_anim", "Copy whole animation"),
         ("paste_anim", "Paste whole animation")]


def _slider():
    import maya.mel as mel
    try:
        return mel.eval("$gusAnimtoolTmp = $gPlayBackSlider")
    except RuntimeError:
        return None


def find_menu():
    """The Time Slider's right-click menu, or None."""
    if cmds.popupMenu("TimeSliderMenu", exists=True):
        return "TimeSliderMenu"
    slider = _slider()
    if slider:
        try:
            for m in cmds.control(slider, query=True, popupMenuArray=True) or []:
                if cmds.popupMenu(m, exists=True):
                    return m
        except RuntimeError:
            pass
    return None


def _add(menu):
    """Our submenu at the end of the menu (made again if Maya cleared it)."""
    if cmds.menuItem(SUB, exists=True):
        return SUB
    cmds.setParent(menu, menu=True)
    cmds.menuItem(DIV, divider=True, parent=menu)
    cmds.menuItem(SUB, label="Gus Animtool", subMenu=True, tearOff=True, parent=menu)
    for item in ITEMS:
        if item is None:
            cmds.menuItem(divider=True, parent=SUB)
            continue
        key, label = item
        cmds.menuItem(label=label, command=AC.command(key), sourceType="python", parent=SUB)
    return SUB


def _remove_ours():
    for item in (SUB, DIV):
        if cmds.menuItem(item, exists=True):
            cmds.deleteUI(item, menuItem=True)


def _count(menu):
    try:
        return len(cmds.popupMenu(menu, query=True, itemArray=True) or [])
    except RuntimeError:
        return 0


def _run(command):
    if not command:
        return False
    try:
        if callable(command):
            command()
        else:
            import maya.mel as mel
            mel.eval(command)
        return True
    except RuntimeError:
        return False


def _usable(command):
    """A post-menu command we can run: a MEL string (not the text Maya gives back for a Python function), or a
    Python function that isn't one of ours (an older copy of _post after a reload)."""
    if callable(command):
        return getattr(command, "__name__", "") != "_post"
    return isinstance(command, str) and bool(command.strip()) and "<" not in command and "_post" not in command


def _maya_default(menu):
    try:
        import maya.mel as mel
        if mel.eval('exists "updateTimeSliderMenu"'):
            return MAYA_DEFAULT % menu
    except RuntimeError:
        pass
    return None


def _post(*_):
    """Maya's items first, ours at the end. Ours are taken out before Maya runs (Maya only fills an empty menu),
    and if Maya still left it empty, its own build is run directly."""
    menu = _state.get("menu")
    _remove_ours()
    _run(_state.get("original"))
    if menu and not _count(menu):
        _run(_maya_default(menu))
    if menu:
        _add(menu)


def _ours_only(menu):
    """True when the menu holds only our items (Maya hasn't built its own yet - it builds them only into an
    empty menu)."""
    try:
        items = cmds.popupMenu(menu, query=True, itemArray=True) or []
    except RuntimeError:
        return False
    return bool(items) and all(i.split("|")[-1] in (SUB, DIV) for i in items)


def install(*_):
    """Hook our section onto the menu: it's added when the menu opens, AFTER Maya has built its own items (Maya
    only fills an empty menu, so nothing of ours is put there before). Returns True when hooked."""
    if not A.opt("timeslider_menu", 1):
        return False
    menu = find_menu()
    if not menu:
        return False
    if _ours_only(menu):                                    # only ours: give Maya its empty menu back
        _remove_ours()
    if _state.get("menu") != menu:
        try:
            current = cmds.popupMenu(menu, query=True, postMenuCommand=True)
        except RuntimeError:
            current = None
        if _usable(current):
            original = current
        else:                                               # after a reload: the one we kept, else Maya's own
            kept = cmds.optionVar(query=KEEP) if cmds.optionVar(exists=KEEP) else None
            original = kept if _usable(kept) else _maya_default(menu)
        if isinstance(original, str):
            cmds.optionVar(stringValue=(KEEP, original))
        _state["original"] = original
        _state["menu"] = menu
        try:
            cmds.popupMenu(menu, edit=True, postMenuCommand=_post)
        except RuntimeError:
            return False
    return True


def remove(*_):
    """Take our section out and give the menu back its own post-menu command."""
    _remove_ours()
    menu = _state.get("menu")
    if menu and cmds.popupMenu(menu, exists=True):
        try:
            cmds.popupMenu(menu, edit=True, postMenuCommand=_state.get("original") or "")
        except RuntimeError:
            pass
    _state["menu"] = None
    return True
