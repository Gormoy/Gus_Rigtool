"""
The pages' `cmds` (5.7): Maya's own maya.cmds, except for the UI names the new window owns.

A tool's functions read and change their page's fields by name - cmds.textField(N("LimMin"), query=True, text=True).
In the new window those fields are Qt widgets: their names are registered here (REGISTRY) and these calls go to
them; every other call - and every name the old window made - goes to Maya as before. Nothing changes for the old
window. (Only the tools drawn in the new window, and core/ui, use this; the rest of Gus_Rigtool uses maya.cmds.)
"""

import maya.cmds as _mc

UI_KINDS = frozenset((
    "button", "checkBox", "text", "textField", "floatField", "intField", "optionMenu", "menuItem", "popupMenu",
    "radioButtonGrp", "textScrollList", "iconTextButton", "symbolCheckBox", "iconTextCheckBox", "floatSliderGrp",
    "intSliderGrp", "textFieldGrp", "floatFieldGrp", "intFieldGrp", "checkBoxGrp", "textFieldButtonGrp",
    "scrollField", "separator", "image", "canvas", "colorSliderGrp", "columnLayout", "rowLayout", "rowColumnLayout",
    "frameLayout", "formLayout", "scrollLayout", "tabLayout", "paneLayout", "gridLayout", "flowLayout",
    "control", "layout", "deleteUI", "objectTypeUI", "setParent", "optionMenuGrp", "nodeIconButton",
    "iconTextRadioButton", "iconTextRadioCollection", "radioCollection", "radioButton", "intSlider", "floatSlider",
    "palettePort", "swatchDisplayPort", "attrColorSliderGrp", "colorIndexSliderGrp"))

REGISTRY = {}                 # short UI name -> the new window's widget for it (render.Field)
_REC = {"on": None}           # while a page is recorded: the Recorder


def short(name):
    return str(name).split("|")[-1]


def owner(args, k):
    """The registered widget a call is about (its first argument, or parent= for a menu item), or None."""
    if args and isinstance(args[0], str):
        f = REGISTRY.get(short(args[0]))
        if f is not None:
            return f
    p = k.get("parent") or k.get("p")
    if isinstance(p, str):
        return REGISTRY.get(short(p))
    return None


class _Cmds(object):
    """maya.cmds, looked up at each call (so tests and Maya's own patches still apply)."""

    def __getattr__(self, name):
        real = getattr(_mc, name)
        if name not in UI_KINDS:
            return real

        def call(*args, **k):
            rec = _REC["on"]
            if rec is not None:
                return rec.call(name, args, k)
            if name == "deleteUI":
                names = [a for a in (args[0] if args and isinstance(args[0], (list, tuple)) else args)]
                mine = [a for a in names if isinstance(a, str) and short(a) in REGISTRY]
                for a in mine:
                    REGISTRY[short(a)].delete()
                rest = [a for a in names if a not in mine]
                return getattr(_mc, name)(*rest, **k) if rest else None
            f = owner(args, k)
            if f is not None:
                return f.cmd(name, args, k)
            return getattr(_mc, name)(*args, **k)
        call.__name__ = name
        return call

    def __setattr__(self, name, value):          # a test's mock.patch.object(module.cmds, ...) reaches maya.cmds
        setattr(_mc, name, value)

    def __delattr__(self, name):
        delattr(_mc, name)


cmds = _Cmds()
