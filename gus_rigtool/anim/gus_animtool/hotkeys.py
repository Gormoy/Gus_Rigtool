"""
Optional hotkeys (off until you turn them on in Settings). Maya's default hotkey set can't be changed, so
turning them on makes a 'Gus_Animtool' set (a copy of the one you use) and makes it the current set.

    Alt + ,          nudge keys one frame left        Alt + .          nudge keys one frame right
    Alt + Shift + ,  a third towards the previous key Alt + Shift + .  a third towards the next key
"""

import maya.cmds as cmds

SET = "Gus_Animtool"
KEYS = [
    ("GusAnimtoolNudgeLeft", "Gus Animtool: nudge keys left", "import gus_animtool.keys as k; k.nudge(-1)",
     ",", False),
    ("GusAnimtoolNudgeRight", "Gus Animtool: nudge keys right", "import gus_animtool.keys as k; k.nudge(1)",
     ".", False),
    ("GusAnimtoolTweenPrev", "Gus Animtool: towards the previous key",
     "import gus_animtool.tween as t; t.step(-1)", ",", True),
    ("GusAnimtoolTweenNext", "Gus Animtool: towards the next key",
     "import gus_animtool.tween as t; t.step(1)", ".", True),
    ("GusAnimtoolPull", "Gus Animtool: pull the selected keys (softer)",
     "import gus_animtool.keys as k; k.push_pull('pull')", "-", False),
    ("GusAnimtoolPush", "Gus Animtool: push the selected keys (bigger)",
     "import gus_animtool.keys as k; k.push_pull('push')", "=", False),
    ("GusAnimtoolNegate", "Gus Animtool: negate the selected keys",
     "import gus_animtool.keys as k; k.negate()", "-", True),
    ("GusAnimtoolInbetweenAdd", "Gus Animtool: add an inbetween",
     "import gus_animtool.actions as a; a.run('inbetween_add')", "]", False),
    ("GusAnimtoolInbetweenRemove", "Gus Animtool: remove an inbetween",
     "import gus_animtool.actions as a; a.run('inbetween_remove')", "[", False),
]


def _wrapped(command):
    return ("from gus_animtool import anim as _a\n"
            "try:\n    %s\nexcept Exception as _e:\n    _a.message(str(_e), 'warn')" % command)


def _user_set():
    current = cmds.hotkeySet(query=True, current=True)
    if current == "Maya_Default":
        if not cmds.hotkeySet(SET, exists=True):
            cmds.hotkeySet(SET, source="Maya_Default")
        cmds.hotkeySet(SET, edit=True, current=True)
        return SET
    return current


def install():
    """Make the commands and bind the keys. Returns the hotkey set used."""
    used = _user_set()
    for name, label, command, key, shift in KEYS:
        if cmds.runTimeCommand(name, exists=True):
            cmds.runTimeCommand(name, edit=True, command=_wrapped(command), commandLanguage="python")
        else:
            cmds.runTimeCommand(name, annotation=label, category="Custom Scripts.Gus Animtool",
                                command=_wrapped(command), commandLanguage="python")
        cmds.nameCommand(name + "NameCommand", annotation=label, command=name, sourceType="mel")
        cmds.hotkey(keyShortcut=key, altModifier=True, shiftModifier=shift, name=name + "NameCommand")
    return used


def remove():
    """Take the keys off (the commands stay in the Hotkey Editor's Custom Scripts)."""
    for _name, _label, _cmd, key, shift in KEYS:
        try:
            cmds.hotkey(keyShortcut=key, altModifier=True, shiftModifier=shift, name="")
        except RuntimeError:
            pass
