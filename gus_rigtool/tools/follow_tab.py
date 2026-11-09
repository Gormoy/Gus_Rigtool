"""
Follow: controls follow part of a driver's motion - lips follow the jaw, lids follow the eyes,
cheeks follow the mouth corners...

    import gus_rigtool.main as gr; gr.show_tool("follow")

  1. Add      : select the driver first, then the followers; Add follow.
  2. Weights  : select followers, type a weight (0-1), Set weight. Or edit their 'follow' attribute.
  3. Follows  : every follow in the scene; select, remove, move the pivot.
Stick to skin has its own tab (4.2.0).
"""

import maya.cmds as cmds

from gus_rigtool.core import follow, naming, ui, utils

TOOL = "Follow"
SETTINGS_KEY = "follow"
DEFAULTS = {"channels": 1, "attr_on": 2, "weight": 1.0, "share_twins": False,
            "remap": 1, "remap_axis": 1, "remap_start": 0.0, "remap_end": 30.0,
            "pivot_mode": 1, "axes": 1}
PIVOT_LABELS = ["The driver", "Picked", "Each control"]
AXES_LABELS = ["Driver's", "Control's own", "World"]
CHANNELS = [("Rotate",), ("Translate",), ("Rotate", "Translate")]

_P, N, _w, _guard = ui.tool_helpers("p_follow_", TOOL)
_rows = {}


def _ui():
    return {"channels": cmds.radioButtonGrp(N("Channels"), query=True, select=True),
            "attr_on": cmds.radioButtonGrp(N("AttrOn"), query=True, select=True),
            "weight": cmds.floatField(N("Weight"), query=True, value=True),
            "share_twins": cmds.checkBox(N("Twins"), query=True, value=True),
            "remap": _mode(),
            "remap_axis": cmds.optionMenu(N("RemapAxis"), query=True, select=True),
            "remap_start": cmds.floatField(N("RemapStart"), query=True, value=True),
            "remap_end": cmds.floatField(N("RemapEnd"), query=True, value=True),
            "pivot_mode": cmds.radioButtonGrp(N("PivotMode"), query=True, select=True),
            "axes": cmds.radioButtonGrp(N("Axes"), query=True, select=True)}


def _pivot_items():
    try:
        return (cmds.textField(N("Pivot"), query=True, text=True) or "").split()
    except RuntimeError:
        return []


def _pivot(o):
    """The pivot for follow.add / move_pivot: 'driver', 'control' or a point."""
    mode = follow.PIVOTS[o["pivot_mode"] - 1]
    if mode == "picked":
        return follow.point_of(_pivot_items())
    return mode


def _load_pivot(*_):
    sel = cmds.ls(selection=True, flatten=False) or []
    if not sel:
        raise RuntimeError("select where the pivot goes (a locator, joint, object or vertices), then press <<.")
    cmds.textField(N("Pivot"), edit=True, text=" ".join(naming.short_name(x) if "." not in x else x for x in sel))
    cmds.radioButtonGrp(N("PivotMode"), edit=True, select=2)
    _on_remap()


def _clear_pivot(*_):
    cmds.textField(N("Pivot"), edit=True, text="")
    cmds.radioButtonGrp(N("PivotMode"), edit=True, select=1)
    _on_remap()


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


MODES = [
    ("No curve", "The control follows by its weight - always the same share of the driver."),
    ("Curve on the weight", "Same, but the weight goes through a curve (remap node) you can bend "
                            "afterwards with Edit curve."),
    ("Curve by jaw opening", "The control stays put at first, then starts following once the driver "
                             "turns past 'from', reaching its full weight at 'to'."),
]


def _mode():
    for i in range(len(MODES)):
        try:
            if cmds.radioButton(N("Mode%d" % (i + 1)), query=True, select=True):
                return i + 1
        except RuntimeError:
            pass
    return 1


def _on_remap(*_):
    try:
        on = _mode() == 3                       # greyed, never hidden: hiding breaks Maya's layout height
        for name in ("RemapAxis", "RemapStart", "RemapEnd"):
            ctl = cmds.optionMenu if name == "RemapAxis" else cmds.floatField
            ctl(N(name), edit=True, enable=on)
    except RuntimeError:
        pass
    _save()
    summary()


def summary(*_):
    """The 'What Add follow will do' line."""
    if not cmds.text(N("Summary"), exists=True):
        return
    try:
        o = _ui()
    except RuntimeError:
        return
    sel = utils.selected_transforms(ordered=True)
    chans = " + ".join(c.lower() for c in CHANNELS[o["channels"] - 1])
    if len(sel) < 2:
        head = "Select the driver first, then the controls that follow it."
    else:
        src = _source()
        head = "%d control(s) will follow %s%s." % (len(sel) - 1, naming.short_name(sel[0]),
                                                  " (rotation from %s)" % src if src else "")
    where = "on each control" if o["attr_on"] == 1 else "one 'follow' on the driver, shared"
    line = "%s x follow (%.2f, %s)" % (chans.capitalize(), o["weight"], where)
    if o["remap"] == 2:
        line += ", through a curve you can edit."
    elif o["remap"] == 3:
        line += ", curve by jaw opening: starts at %g deg, full at %g deg on %s." % (
            o["remap_start"], o["remap_end"], "XYZ"[o["remap_axis"] - 1])
    else:
        line += ", no curve."
    piv = PIVOT_LABELS[o["pivot_mode"] - 1].lower()
    if o["pivot_mode"] == 2:
        items = _pivot_items()
        piv = "picked (%s)" % (", ".join(items[:2]) + (" ..." if len(items) > 2 else "") if items else "nothing yet - <<")
    line += "\nPivot: %s. Axes: %s." % (piv, AXES_LABELS[o["axes"] - 1].lower())
    cmds.text(N("Summary"), edit=True, label=head + "\n" + line)


def edit_curve(*_):
    sel = utils.selected_transforms()
    nodes = [follow.remap_of(c) for c in sel]
    nodes = [n for n in nodes if n]
    if not nodes:
        raise RuntimeError("select a control that follows with a curve (Curve on the weight / by jaw opening).")
    cmds.select(nodes, replace=True)
    try:
        import maya.mel as mel
        mel.eval("openAEWindow")
    except Exception:
        pass
    utils.info(TOOL, "selected %s: edit its curve (Value) in the Attribute Editor." % ", ".join(nodes))


def _source():
    """The 'Rotation from' node, or None (= the driver)."""
    try:
        v = (cmds.textField(N("Source"), query=True, text=True) or "").strip()
    except RuntimeError:
        return None
    return v or None


def _load_source(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the node that rotates (e.g. the jaw joint), then press <<.")
    cmds.textField(N("Source"), edit=True, text=naming.short_name(sel[0]))
    summary()


def _clear_source(*_):
    cmds.textField(N("Source"), edit=True, text="")
    summary()


def _light():
    sel = utils.selected_transforms(ordered=True)
    if len(sel) < 2:
        return "warn", "Select the driver first (e.g. the jaw control), then the controls that follow it."
    return "ok", "Driver: %s. Followers: %d. Press Add follow." % (naming.short_name(sel[0]), len(sel) - 1)


def add(*_):
    o = _ui()
    _save()
    sel = utils.selected_transforms(ordered=True)
    if len(sel) < 2:
        raise RuntimeError("select the driver first, then one or more controls that follow it.")
    chans = [c.lower() for c in CHANNELS[o["channels"] - 1]]
    done, skipped = follow.add(sel[0], sel[1:], chans, "control" if o["attr_on"] == 1 else "driver",
                               o["weight"], o["share_twins"], follow.REMAPS[o["remap"] - 1],
                               "XYZ"[o["remap_axis"] - 1], o["remap_start"], o["remap_end"], _source(),
                               _pivot(o), follow.AXES[o["axes"] - 1])
    msg = "%d control(s) follow %s (%s): %s" % (len(done), naming.short_name(sel[0]), " + ".join(chans),
                                                 ", ".join(done[:6]) + (" ..." if len(done) > 6 else ""))
    if skipped:
        utils.warn(TOOL, msg + " Skipped: " + ", ".join(skipped[:5]))
    else:
        utils.info(TOOL, msg)
    refresh()


def move_pivot(*_):
    o = _ui()
    _save()
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the following controls whose pivot you want to move.")
    n = follow.move_pivot(sel, _pivot(o), follow.AXES[o["axes"] - 1])
    if not n:
        raise RuntimeError("none of the selected controls follow anything.")
    utils.info(TOOL, "%d follow(s) moved: pivot %s, axes %s. Nothing moved in the scene." % (
        n, PIVOT_LABELS[o["pivot_mode"] - 1].lower(), AXES_LABELS[o["axes"] - 1].lower()))
    refresh()


def update_selected(*_):
    """The selected followers get the options above (channels, weight, curve, pivot, axes); same driver."""
    o = _ui()
    _save()
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the following controls to update.")
    chans = [c.lower() for c in CHANNELS[o["channels"] - 1]]
    n = follow.update(sel, channels=chans, weight=o["weight"], attr_on="control" if o["attr_on"] == 1 else "driver",
                      remap=follow.REMAPS[o["remap"] - 1], axis="XYZ"[o["remap_axis"] - 1], start=o["remap_start"],
                      end=o["remap_end"], pivot=_pivot(o), axes=follow.AXES[o["axes"] - 1])
    if not n:
        raise RuntimeError("none of the selected controls follow anything.")
    utils.info(TOOL, "%d follow(s) updated (%s, weight %.2f, pivot %s, axes %s); same drivers, no jump." % (
        n, " + ".join(chans), o["weight"], PIVOT_LABELS[o["pivot_mode"] - 1].lower(),
        AXES_LABELS[o["axes"] - 1].lower()))
    refresh()


def copy_first(*_):
    sel = utils.selected_transforms(ordered=True)
    if len(sel) < 2:
        raise RuntimeError("select the control whose follow you want first, then the others.")
    done, skipped = follow.copy(sel[0], sel[1:])
    msg = "%d control(s) now follow like %s." % (len(done), naming.short_name(sel[0]))
    (utils.warn if skipped else utils.info)(TOOL, msg + (" Skipped: " + ", ".join(skipped[:5]) if skipped else ""))
    refresh()


def mirror_selected(*_):
    from gus_rigtool.core import mirror_links
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select following controls on one side: their twins get the mirrored follow.")
    done, skipped = mirror_links.follows(sel, replace=True)
    msg = "%d twin(s) follow, mirrored." % len(done)
    (utils.warn if skipped else utils.info)(TOOL, msg + (" Skipped: " + "; ".join(
        "%s (%s)" % (naming.short_name(n), why) for n, why in skipped[:4]) if skipped else ""))
    refresh()


def set_weight(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the following controls.")
    n = follow.set_weight(sel, cmds.floatField(N("SetValue"), query=True, value=True))
    utils.info(TOOL, "weight set on %d control(s)." % n)
    refresh()


def remove(*_):
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls to stop following.")
    n = follow.remove(sel)
    utils.info(TOOL, "%d control(s) no longer follow (they are back at their rest place)." % n)
    refresh()


def refresh(*_):
    if not cmds.textScrollList(N("List"), exists=True):
        return
    rows = follow.all_follows()
    _rows[_P["p"]] = rows
    labels = []
    for ctrl, driver, plug, chans, src in rows:
        try:
            w = cmds.getAttr(plug)
        except (RuntimeError, ValueError):
            w = "?"
        by = driver if src == driver else "%s (rotation of %s)" % (driver, src)
        try:
            how = follow.describe(ctrl) if cmds.objExists(ctrl) else "?"
        except Exception:                                   # one follow it can't read never empties the list
            how = "?"
        labels.append("%s  <-  %s   x %s   (%s, %s)" % (ctrl, by, w if isinstance(w, str) else "%.2f" % w,
                                                      "+".join(chans), how))
    cmds.textScrollList(N("List"), edit=True, removeAll=True, append=labels or ["(no follows yet)"])
    ui.refresh_light(N("Light"))


def _pick(*_):
    picked = cmds.textScrollList(N("List"), query=True, selectIndexedItem=True) or []
    rows = _rows.get(_P["p"], [])
    nodes = [rows[i - 1][0] for i in picked if isinstance(i, int) and i - 1 < len(rows)]
    nodes = [n for n in nodes if cmds.objExists(n)]
    if nodes:
        cmds.select(nodes, replace=True)


def _heading(label):
    cmds.separator(height=6, style="none")
    cmds.text(label=label, align="left", font="boldLabelFont", height=18)
    cmds.separator(height=4, style="in")


def build(prefix="p_follow_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()
    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)

    ui.section("Add follow", step=1, help_text="Select the driver first (e.g. the jaw control), then the controls "
               "that follow it. Rotation from: the node that really rotates (e.g. the jaw joint) - load it with "
               "<<; empty = the driver. Each follower gets a group above its offset group, at that node's pivot, "
               "that turns (and / or moves) by its channels x the weight (the driver's 'follow' attribute). "
               "Put it at rest (0) first. Pivot at / Axes: turn around another point (pick it with <<) and / or "
               "keep the control's own axes (eyelids). Works with ribbon and Build tab controls.")
    cmds.radioButtonGrp(N("Channels"), label="Follow", numberOfRadioButtons=3,
                        labelArray3=["Rotate", "Translate", "Both"], select=s["channels"],
                        columnWidth4=(70, 80, 90, 60), changeCommand=_w(_on_remap))
    cmds.radioButtonGrp(N("AttrOn"), label="Weight on", numberOfRadioButtons=2,
                        labelArray2=["Each control", "The driver (shared)"], select=s["attr_on"],
                        columnWidth3=(70, 110, 110), changeCommand=_w(_on_remap),
                        annotation="Each control: a 'follow' attribute on it. The driver: one 'follow' attribute "
                                   "on the driver (e.g. the jaw control), shared by all its followers.")
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, height=26,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)],
                   columnWidth4=(110, 150, 30, 45))
    cmds.text(label="Rotation from", annotation="The node that actually rotates (e.g. the jaw joint). "
              "Empty = the driver itself.")
    cmds.textField(N("Source"), placeholderText="empty = the driver", changeCommand=_w(summary),
                   annotation="The node whose rotation is followed and whose pivot is used.")
    cmds.button(label="<<", command=_w(_guard(_load_source)), annotation="Load the selected node.")
    cmds.button(label="Clear", command=_w(_clear_source))
    cmds.setParent("..")
    cmds.radioButtonGrp(N("PivotMode"), label="Pivot at", numberOfRadioButtons=3, labelArray3=PIVOT_LABELS,
                        select=s["pivot_mode"], columnWidth4=(70, 80, 65, 90), changeCommand=_w(_on_remap),
                        annotation="Where the follower turns around. The driver: its pivot. Picked: the point "
                                   "loaded below (locator, joint, object or vertices - their centre). Each control: "
                                   "every follower turns around itself.")
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, height=26,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)],
                   columnWidth4=(110, 150, 30, 45))
    cmds.text(label="Picked pivot")
    cmds.textField(N("Pivot"), placeholderText="select, then <<", changeCommand=_w(summary),
                   annotation="Objects or vertices: the pivot is their centre (position only).")
    cmds.button(label="<<", command=_w(_guard(_load_pivot)), annotation="Load the selection as the pivot.")
    cmds.button(label="Clear", command=_w(_clear_pivot))
    cmds.setParent("..")
    cmds.radioButtonGrp(N("Axes"), label="Axes", numberOfRadioButtons=3, labelArray3=AXES_LABELS,
                        select=s["axes"], columnWidth4=(70, 80, 95, 60), changeCommand=_w(_on_remap),
                        annotation="Driver's: the follow group turns like the driver. Control's own: only the "
                                   "pivot moves, the axes stay the control's (eyelids). World: world axes.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 80), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Start weight")
    cmds.floatField(N("Weight"), value=float(s["weight"]), minValue=0.0, maxValue=1.0, step=0.05, precision=2,
                    changeCommand=_w(_on_remap))
    cmds.setParent("..")
    cmds.checkBox(N("Twins"), label="Twins (L / R) share one weight", value=s["share_twins"],
                  changeCommand=_w(_save))
    # No nested frames, no hidden rows, no auto-height wrapped text: Maya sized the section too
    # small with those and cut off its last items (1.6.3). Plain heading + fixed heights instead.
    _heading("Curve (remap node)")
    cmds.radioCollection(N("Modes"))
    for i, (label, text) in enumerate(MODES):
        cmds.radioButton(N("Mode%d" % (i + 1)), label=label, select=(s["remap"] == i + 1),
                         onCommand=_w(_on_remap), collection=N("Modes"))
        cmds.text(label="      " + text, align="left", wordWrap=True, height=30, font="smallPlainLabelFont")
    cmds.rowLayout(numberOfColumns=6, columnWidth6=(80, 50, 40, 55, 30, 55), height=26,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "right", 2), (4, "both", 2),
                                 (5, "right", 2), (6, "both", 2)])
    cmds.text(label="Driver axis")
    cmds.optionMenu(N("RemapAxis"), changeCommand=_w(_on_remap))
    for a in "XYZ":
        cmds.menuItem(label=a)
    cmds.text(label="from")
    cmds.floatField(N("RemapStart"), value=float(s["remap_start"]), precision=1, changeCommand=_w(_on_remap),
                    annotation="Driver rotation (degrees) where the follow starts. Negative works too.")
    cmds.text(label="to")
    cmds.floatField(N("RemapEnd"), value=float(s["remap_end"]), precision=1, changeCommand=_w(_on_remap),
                    annotation="Driver rotation (degrees) where the follow reaches the full weight.")
    cmds.setParent("..")
    cmds.optionMenu(N("RemapAxis"), edit=True, select=s["remap_axis"])
    cmds.text(label="      (from / to: only for Curve by jaw opening)", align="left", height=16,
              font="smallPlainLabelFont")
    cmds.separator(height=6, style="none")
    ui.main_button("Add follow", _w(_guard(add)), "Driver first, then the followers. One undo.")
    _heading("What Add follow will do")
    cmds.text(N("Summary"), label="", align="left", wordWrap=True, height=58)
    cmds.separator(height=8, style="none")
    _on_remap()
    ui.end_section()

    ui.section("Weights", step=2, help_text="Select followers, type a weight, Set weight. 0 = doesn't follow, "
               "1 = follows fully, 0.5 = half. You can also change the 'follow' attribute in the Channel Box.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(80, 150), columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.floatField(N("SetValue"), value=0.5, minValue=0.0, maxValue=1.0, step=0.05, precision=2)
    cmds.button(label="Set weight on selection", command=_w(_guard(set_weight)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Follows in the scene", step=3, help_text="Click to select. Remove: the controls stop following "
               "and go back to their place at the driver's rest pose; groups, nodes and weights are deleted. "
               "Move follow pivot: the selected follows take the Pivot at / Axes from Add follow, with no jump.")
    cmds.textScrollList(N("List"), height=110, allowMultiSelection=True, selectCommand=_w(_pick))
    ui.row(3, 115)
    cmds.button(label="Update from options", command=_w(_guard(update_selected)),
                annotation="The selected followers get the options in Add follow (channels, weight, curve, pivot, "
                           "axes); same driver. Made again with no jump - put the driver at rest first.")
    cmds.button(label="Copy from first", command=_w(_guard(copy_first)),
                annotation="Select a following control first, then others: they follow the same way.")
    cmds.button(label="Mirror to twins", command=_w(_guard(mirror_selected)),
                annotation="The selected followers' L_ / R_ twins get the same follow, mirrored (twin driver, or "
                           "the same centre driver like the jaw).")
    cmds.setParent("..")
    ui.row(1, 345)
    cmds.button(label="Move follow pivot (uses Pivot at / Axes above)", command=_w(_guard(move_pivot)),
                annotation="Select following controls: their follow moves to the Pivot and Axes set in Add follow. "
                           "Nothing moves in the scene. Put the driver at rest first.")
    cmds.setParent("..")
    ui.row(3, 115)
    cmds.button(label="Refresh", command=_w(refresh))
    cmds.button(label="Remove follow", command=_w(_guard(remove)),
                annotation="Selected controls stop following.")
    cmds.button(label="Edit curve", command=_w(_guard(edit_curve)),
                annotation="Selects the control's remap node and opens the Attribute Editor on its curve.")
    cmds.setParent("..")
    cmds.separator(height=8, style="none")
    ui.end_section()

    ui.on_selection(N("Summary"), _w(summary))
    refresh()


def show():
    ui.open_panel("follow")


SCHEMA = [
    ("channels", "Follow (1 rotate, 2 translate, 3 both)", "choice", ["Rotate", "Translate", "Both"]),
    ("attr_on", "Weight on", "choice", ["Each control", "The driver (shared)"]),
    ("weight", "Start weight", "float", None),
    ("share_twins", "Twins share one weight", "bool", None),
    ("remap", "Remap curve", "choice", ["None", "Shape the weight", "By driver opening"]),
    ("remap_start", "Remap: opening from (degrees)", "float", None),
    ("remap_end", "Remap: opening to (degrees)", "float", None),
    ("pivot_mode", "Pivot at", "choice", PIVOT_LABELS),
    ("axes", "Axes", "choice", AXES_LABELS),
]
