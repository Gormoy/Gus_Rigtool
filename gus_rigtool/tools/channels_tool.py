"""
Channels: lock, hide and make keyable the channels of many controls at once.

    import gus_rigtool.main as gr; gr.show_tool("channels")

  1 Channels : tick the channels (translate / rotate / scale X Y Z, visibility, the controls' own
               attributes), then Lock + hide, Unlock + show, Lock, Unlock, Hide, Show, or Box only
               (shown in the Channel Box but not keyed).
  2 Default set : your usual 'lock + hide' set (scale and visibility at first) on the selection in one click.
  3 Copy / check : copy the ticked channels' state from the first selected control to the others, or
               see what is locked / hidden on the selection.
"""

import maya.cmds as cmds

from gus_rigtool.core import attrs, ui, utils

TOOL = "Channels"
SETTINGS_KEY = "channels"
STD = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"]
DEFAULTS = {"ticked": ["sx", "sy", "sz", "v"], "user": False, "default_set": ["sx", "sy", "sz", "v"]}
SKIP_PREFIX = ("gus", "rrb")
NUMERIC = ("double", "float", "long", "short", "byte", "bool", "enum", "doubleLinear", "doubleAngle", "time")

_P, N, _w, _guard = ui.tool_helpers("p_channels_", TOOL)


def _ticked():
    out = [c for c in STD if cmds.checkBox(N("C_" + c), query=True, value=True)]
    return out, cmds.checkBox(N("User"), query=True, value=True)


def _save(*_):
    try:
        t, u = _ticked()
        utils.update_setting(SETTINGS_KEY, "ticked", t)
        utils.update_setting(SETTINGS_KEY, "user", u)
    except RuntimeError:
        pass


def user_channels(node):
    """The control's own number attributes (not separators, not Gus_Rigtool's notes)."""
    out = []
    for a in attrs.user_attrs(node):
        if a.startswith(SKIP_PREFIX) or attrs.is_separator(node, a):
            continue
        if attrs.kind(node, a) in NUMERIC:
            out.append(a)
    return out


def _channels(node, std, user):
    return [c for c in std] + (user_channels(node) if user else [])


def set_state(nodes, std, user=False, lock=None, show=None, keyable=None):
    """lock True / False / None (leave). show: 'key' (keyable), 'box' (Channel Box only), 'hide', None."""
    count = 0
    for node in nodes:
        for c in _channels(node, std, user):
            plug = node + "." + c
            if not cmds.objExists(plug):
                continue
            try:
                if lock is not None:
                    cmds.setAttr(plug, lock=lock)
                if show == "key":
                    cmds.setAttr(plug, keyable=True)
                elif show == "box":
                    cmds.setAttr(plug, keyable=False)
                    cmds.setAttr(plug, channelBox=True)
                elif show == "hide":
                    cmds.setAttr(plug, keyable=False)
                    cmds.setAttr(plug, channelBox=False)
                count += 1
            except RuntimeError:
                pass
    return count


def state(node, c):
    plug = node + "." + c
    try:
        return {"lock": bool(cmds.getAttr(plug, lock=True)), "keyable": bool(cmds.getAttr(plug, keyable=True)),
                "box": bool(cmds.getAttr(plug, channelBox=True))}
    except (RuntimeError, ValueError):
        return None


def copy_state(source, targets, std, user=False):
    n = 0
    for c in _channels(source, std, user):
        s = state(source, c)
        if not s:
            continue
        show = "key" if s["keyable"] else ("box" if s["box"] else "hide")
        for t in targets:
            if cmds.objExists(t + "." + c):
                n += set_state([t], [c], False, s["lock"], show)
    return n


def report(nodes):
    lines = []
    for node in nodes:
        locked, hidden, box = [], [], []
        for c in STD + user_channels(node):
            s = state(node, c)
            if not s:
                continue
            if s["lock"]:
                locked.append(c)
            if not s["keyable"]:
                (box if s["box"] else hidden).append(c)
        lines.append("%s\n    locked: %s\n    hidden: %s\n    box only: %s" % (
            node.split("|")[-1], " ".join(locked) or "-", " ".join(hidden) or "-", " ".join(box) or "-"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def _light():
    sel = utils.selected_transforms()
    if not sel:
        return "idle", "Select the controls."
    t, u = _ticked()
    return "ok", "%s - %d channel(s) ticked%s." % (ui.selection_summary(sel, "control"), len(t),
                                                    " + their own attributes" if u else "")


def _do(lock=None, show=None, what="", *_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls.")
    t, u = _ticked()
    if not t and not u:
        raise RuntimeError("tick some channels first.")
    _save()
    with utils.undo_chunk("gusrigChannels"):
        n = set_state(sel, t, u, lock, show)
    utils.info(TOOL, "%s: %d channel(s) on %d control(s)." % (what, n, len(sel)))


def _tick(names, *_):
    for c in STD:
        cmds.checkBox(N("C_" + c), edit=True, value=c in names)
    _save()
    ui.refresh_light(N("Light"))


def save_default(*_):
    t, _u = _ticked()
    utils.update_setting(SETTINGS_KEY, "default_set", t)
    cmds.text(N("DefaultNote"), edit=True, label="Default set: " + (" ".join(t) or "-"))
    utils.info(TOOL, "default set: %s." % (" ".join(t) or "nothing"))


def apply_default(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls.")
    chans = utils.tool_settings(SETTINGS_KEY, DEFAULTS)["default_set"]
    with utils.undo_chunk("gusrigChannelsDefault"):
        n = set_state(sel, chans, False, True, "hide")
    utils.info(TOOL, "locked + hid %s on %d control(s) (%d channels)." % (" ".join(chans), len(sel), n))


def copy_first(*_):
    sel = utils.selected_transforms()
    if len(sel) < 2:
        raise RuntimeError("select the control to copy from, then the others.")
    t, u = _ticked()
    with utils.undo_chunk("gusrigChannelsCopy"):
        n = copy_state(sel[0], sel[1:], t, u)
    utils.info(TOOL, "copied %d channel state(s) from %s." % (n, sel[0].split("|")[-1]))


def show_report(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls.")
    ui.report_window("Channels", report(sel))


def build(prefix="p_channels_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Channels", step=1, help_text="Tick the channels, then a button: it acts on every selected control. "
               "Hide: out of the Channel Box. Box only: shown but not keyed. Their own attributes: the controls' "
               "number attributes (not separators).")
    cmds.rowColumnLayout(numberOfColumns=4, columnWidth=[(1, 70), (2, 60), (3, 60), (4, 60)])
    for row, label in (("t", "Translate"), ("r", "Rotate"), ("s", "Scale")):
        cmds.text(label=label, align="left")
        for ax in "xyz":
            c = row + ax
            cmds.checkBox(N("C_" + c), label=ax.upper(), value=c in s["ticked"], changeCommand=_w(_save))
    cmds.text(label="Visibility", align="left")
    cmds.checkBox(N("C_v"), label="v", value="v" in s["ticked"], changeCommand=_w(_save))
    cmds.text(label="")
    cmds.text(label="")
    cmds.setParent("..")
    cmds.checkBox(N("User"), label="Their own attributes too", value=s["user"], changeCommand=_w(_save))
    ui.row(5, 66)
    for label, names in (("All", STD), ("None", []), ("T", STD[0:3]), ("R", STD[3:6]), ("S", STD[6:9])):
        cmds.button(label=label, command=_w(lambda *_, x=names: _tick(x)))
    cmds.setParent("..")
    ui.main_button("Lock + hide", _w(_guard(lambda *_: _do(True, "hide", "locked + hidden"))),
                   "Locked and out of the Channel Box. One undo.")
    ui.row(3, 113)
    cmds.button(label="Unlock + show", command=_w(_guard(lambda *_: _do(False, "key", "unlocked + shown"))))
    cmds.button(label="Lock", command=_w(_guard(lambda *_: _do(True, None, "locked"))))
    cmds.button(label="Unlock", command=_w(_guard(lambda *_: _do(False, None, "unlocked"))))
    cmds.setParent("..")
    ui.row(3, 113)
    cmds.button(label="Hide", command=_w(_guard(lambda *_: _do(None, "hide", "hidden"))))
    cmds.button(label="Show (keyable)", command=_w(_guard(lambda *_: _do(None, "key", "keyable"))))
    cmds.button(label="Box only", command=_w(_guard(lambda *_: _do(None, "box", "box only"))),
                annotation="In the Channel Box, but not keyed (like a settings switch you don't animate).")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Default set", step=2, help_text="Your usual channels to lock + hide on controls. Save: the ticked "
               "channels become the set.")
    cmds.text(N("DefaultNote"), label="Default set: " + (" ".join(s["default_set"]) or "-"), align="left")
    ui.row(2, 170)
    cmds.button(label="Lock + hide the set", backgroundColor=ui.MAIN_BG, command=_w(_guard(apply_default)))
    cmds.button(label="Save ticks as the set", command=_w(_guard(save_default)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Copy / check", step=3, help_text="Copy: the ticked channels of the first selected control "
               "(locked, keyable, shown) go to the others. What's locked: a report of the selection.")
    ui.row(2, 170)
    cmds.button(label="Copy: first > others", command=_w(_guard(copy_first)))
    cmds.button(label="What's locked?", command=_w(_guard(show_report)))
    cmds.setParent("..")
    ui.end_section()


def show():
    ui.open_panel("channels")


SCHEMA = [
    ("user", "Their own attributes too", "bool", None),
]
