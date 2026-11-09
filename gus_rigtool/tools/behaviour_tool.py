"""
Behaviour (5.4.0): how the controls behave for the animator, in one place - how far they move (limits), drawn in
front of the mesh, a chain stopped at the body. (Lock / hide channels: the Channels page.)
    import gus_rigtool.main as gr; gr.show_tool("behaviour")
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, ui, utils

TOOL = "Behaviour"

_P, N, _w, _guard = ui.tool_helpers("p_behaviour_", TOOL)


def _ctrls():
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if not sel:
        raise RuntimeError("select the controls first.")
    return sel


def _short(n):
    return naming.short_name(n)


# ---- limits ---------------------------------------------------------------------------------------------------

def _num(name):
    t = cmds.textField(N(name), query=True, text=True).strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        raise RuntimeError("%s: type a number (or leave it blank for no limit)." % name.replace("Lim", ""))


def _channel():
    from gus_rigtool.core import limits
    return limits.CHANNELS[cmds.optionMenu(N("LimCh"), query=True, select=True) - 1]


def limit_apply(*_):
    from gus_rigtool.core import limits
    lo, hi = _num("LimMin"), _num("LimMax")
    if lo is None and hi is None:
        raise RuntimeError("type a min and / or a max (Clear takes limits off).")
    ch = _channel()
    n = limits.set_limit(_ctrls(), ch, lo, hi)
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    utils.info(TOOL, "%s limited %s .. %s on %d control(s)." % (ch, "-" if lo is None else "%g" % lo,
                                                              "-" if hi is None else "%g" % hi, n))


def limit_pose(side, *_):
    from gus_rigtool.core import limits
    got = limits.from_pose(_ctrls(), _channel(), side)
    utils.info(TOOL, "%s %s from the pose: %s." % (_channel(), side, ", ".join(
        "%s %g" % (_short(c), v) for c, v in got[:6])))


def limit_mirror(*_):
    from gus_rigtool.core import limits
    mode = ("auto", "same", "flip")[cmds.optionMenu(N("LimMode"), query=True, select=True) - 1]
    done, alone = limits.mirror(_ctrls(), mode=mode)
    lines = ["%s -> %s: %s%s" % (_short(c), _short(t), ", ".join(ch) or "no limits",
                                 (" (flipped: %s)" % ", ".join(f)) if f else "") for c, t, ch, f in done]
    lines += ["%s: no twin found" % _short(c) for c in alone]
    print("Limits mirrored:\n" + "\n".join("  " + x for x in lines))
    utils.info(TOOL, "limits mirrored on %d control(s)%s - details in the Script Editor." % (
        len(done), (", %d without a twin" % len(alone)) if alone else ""))


def limit_clear(which, *_):
    from gus_rigtool.core import limits
    n = limits.clear(_ctrls(), _channel() if which == "one" else None)
    utils.info(TOOL, "%d limit(s) taken off." % n)


def limit_show(*_):
    from gus_rigtool.core import limits
    lines = [limits.describe(c) for c in _ctrls()]
    print("\n".join(lines))
    utils.info(TOOL, lines[0] + (" (+%d more in the Script Editor)" % (len(lines) - 1) if len(lines) > 1 else ""))


# ---- in front / stop at the body ------------------------------------------------------------------------------

def on_top(on, *_):
    from gus_rigtool.core import on_top as OT
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    every = set(OT.controls())
    sel = [c for c in sel if c in every]
    changed, face, missing = OT.apply(sel or None, on=on, skip_face=cmds.checkBox(N("SkipFace"), query=True,
                                                                                    value=True))
    utils.info(TOOL, "%s: %d control shape(s) %s%s%s." % (
        "the selected controls" if sel else "every control", changed, "in front" if on else "back to normal",
        (", %d face control(s) skipped" % face) if face else "",
        (", %d without the setting (Maya before 2022, or locked)" % missing) if missing else ""))


def stop_fit(*_):
    from gus_rigtool.tools import make_controls_tool as MCT
    MCT.body_stop_fit()


def stop_remove(*_):
    from gus_rigtool.tools import make_controls_tool as MCT
    MCT.body_stop_remove()


def zero_here(*_):
    from gus_rigtool.core import zero_pose
    sel = _ctrls()
    done, skipped = zero_pose.apply(sel)
    for c, why in skipped:
        print("Keep the pose: %s skipped - %s" % (_short(c), why))
    utils.info(TOOL, "%d control(s) zeroed where they are (their groups took the pose - a new <control>_rest group "
               "where the one above couldn't)%s." % (
        len(done), (", %d skipped - see the Script Editor" % len(skipped)) if skipped else ""))


# ---- page -----------------------------------------------------------------------------------------------------

def build(prefix="p_behaviour_"):
    _P["p"] = prefix
    ui.section("Limits", step=1, help_text="How far the selected controls can move / turn / scale (Maya's transform "
               "limits). Pick the channel, type a min and / or a max (blank = no limit on that side; given the "
               "wrong way round, 0 and -65 become -65 .. 0), Apply. Min / Max from pose: move the control to where "
               "it should stop and press it. Mirror: every limit of the selected controls on their twins (L_ / R_) "
               "- Auto flips where the twin's channel goes the other way.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 90), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Channel")
    cmds.optionMenu(N("LimCh"))
    for ch in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
        cmds.menuItem(label=ch)
    cmds.text(label="Min")
    cmds.textField(N("LimMin"), placeholderText="blank = no limit")
    cmds.text(label="Max")
    cmds.textField(N("LimMax"), placeholderText="blank = no limit")
    cmds.setParent("..")
    ui.main_button("Apply to the selected controls", _w(_guard(limit_apply)), "One undo.")
    ui.row(2, 150)
    cmds.button(label="Min from pose", command=_w(_guard(lambda *_: limit_pose("min"))))
    cmds.button(label="Max from pose", command=_w(_guard(lambda *_: limit_pose("max"))))
    cmds.setParent("..")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 90), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6))
    cmds.text(label="Other side")
    cmds.optionMenu(N("LimMode"))
    for m in ("Auto", "Same values", "Flipped values"):
        cmds.menuItem(label=m)
    cmds.setParent("..")
    cmds.button(label="Mirror limits to the other side", height=26, command=_w(_guard(limit_mirror)))
    ui.row(3, 100)
    cmds.button(label="Show", command=_w(_guard(limit_show)), annotation="Print the selected controls' limits.")
    cmds.button(label="Clear channel", command=_w(_guard(lambda *_: limit_clear("one"))))
    cmds.button(label="Clear all", command=_w(_guard(lambda *_: limit_clear("all"))))
    cmds.setParent("..")
    ui.end_section()

    ui.section("In front of the mesh", step=2, help_text="Maya's Always Draw On Top on the controls: one inside the "
               "body is always seen. The selected controls, or every control when none is selected. Skip face: "
               "the face's controls stay as they are (they'd show through the back of the head). New rigs: Build "
               "page, 'Controls in front of the mesh'.")
    cmds.checkBox(N("SkipFace"), label="Skip face controls", value=True)
    ui.row(2, 150)
    cmds.button(label="In front", backgroundColor=ui.MAIN_BG, command=_w(_guard(lambda *_: on_top(True))))
    cmds.button(label="Normal", command=_w(_guard(lambda *_: on_top(False))))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Stop at the body", step=3, collapse=True, help_text="A chain (a cape) turned towards the body goes "
               "into it. Select the body mesh, then the chain's first control (the controls under it are taken), or "
               "the controls to limit: each gets a rotation limit where the chain below it would touch the body. "
               "body_stop (on / off) and body_stop_extra (degrees) on the first control. Fit again after changing "
               "the model; Remove takes the limits off.")
    ui.row(2, 150)
    cmds.button(label="Fit to the body", backgroundColor=ui.MAIN_BG, command=_w(_guard(stop_fit)))
    cmds.button(label="Remove", command=_w(_guard(stop_remove)))
    cmds.setParent("..")
    ui.end_section()
    ui.section("Rest here", step=4, help_text="A control moved to where it should rest (a cape ribbon control, the "
               "eyes): its move / turn / scale go into the group above it - nothing moves, the control reads 0 "
               "there, and resetting it brings it back to this spot. Skipped (and said why) when its group has other "
               "things under it or its channels are locked / driven. One undo.")
    ui.main_button("Keep the pose, zero the selected controls", _w(_guard(zero_here)), "Nothing moves.")
    ui.end_section()
    ui.note("Lock / hide channels: the Channels page.")


def show():
    ui.open_panel("behaviour")
