"""
Pivots: move the pivots of many objects to the same spot. Objects never move.

    import gus_rigtool.main as gr; gr.show_tool("pivots")

Targets
  Last Selected    : select the objects, then the target last (joint, control, mesh...).
  Components       : objects + some vertices / CVs / edges: their centre.
  World Origin     : 0, 0, 0.
  Selection Center : bounding-box centre of all the selected objects.
  Typed Position   : the X, Y, Z fields ("Get" reads them from the selection).
  Reset            : each object's own origin.

Match orientation (off by default) also turns the Move / Rotate handles to the target
(Last Selected) or the world. Handles only: values and hierarchy do not change.
Joints are never changed, but a joint works as the Last Selected target.

4.1.0
  Bounding box     : any of the 27 box spots (e.g. bottom centre), per object or for the whole selection.
  From geometry    : objects + a face / edge / 2-3 vertices: the pivot on them, handles along them.
  Along a chain    : objects, then joint A, then joint B: the pivot that far between them.
  Remember / Apply : keep a pivot spot (and handle orientation) and put it on other objects.
  Mirror to twins  : each object's other-side twin (by name) gets the mirrored pivot.
"""

import math

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import naming, pivots, ui, utils

TOOL = "Pivots"
SETTINGS_KEY = "pivots"

DEFAULTS = {
    "orient": False,
    "position": [0.0, 0.0, 0.0],
    "box": [2, 1, 2],              # per axis: 1 min, 2 centre, 3 max
    "box_each": True,
    "geo_position": True,
    "chain": 50.0,
    "mirror_orient": False,
}
BOX_LABELS = (["-X", "Centre", "+X"], ["Bottom", "Centre", "Top"], ["Back", "Centre", "Front"])

_P, N, _w, _guard = ui.tool_helpers("p_pivots_", TOOL)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _split_selection():
    """(objects, components) in selection order."""
    sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
    comps = [s for s in sel if "." in s]
    objs = []
    for s in sel:
        if "." in s:
            continue
        if cmds.objectType(s, isAType="shape"):
            s = cmds.listRelatives(s, parent=True, fullPath=True)[0]
        if cmds.objectType(s, isAType="transform") and s not in objs:
            objs.append(s)
    return objs, comps


def _editable(objs):
    keep = [o for o in objs if cmds.nodeType(o) != "joint"]
    skipped = [naming.short_name(o) for o in objs if cmds.nodeType(o) == "joint"]
    if skipped:
        utils.warn(TOOL, "skipped joint(s): %s." % ", ".join(skipped))
    return keep


def _components_center(comps):
    flat = cmds.xform(comps, query=True, worldSpace=True, translation=True) or []
    count = len(flat) // 3
    return [sum(flat[i::3]) / count for i in range(3)] if count else None


def _world_rotation_deg(node):
    e = om.MTransformationMatrix(om.MMatrix(cmds.getAttr(node + ".worldMatrix[0]"))).rotation()
    return [math.degrees(e.x), math.degrees(e.y), math.degrees(e.z)]


def _orient_handles(objs, orientation):
    """Turn the Move / Rotate handles (manipulator pivot) of each object."""
    failed = False
    for obj in objs:
        try:
            cmds.select(obj, replace=True)
            cmds.manipPivot(orientation=orientation)
        except (RuntimeError, TypeError):
            failed = True
    if failed:
        utils.warn(TOOL, "the handles could not be turned on some objects (positions were moved).")


def _apply(objs, position, orientation):
    objs = _editable(objs)
    if not objs:
        utils.warn(TOOL, "nothing to change.")
        return
    orient = cmds.checkBox(N("Orient"), query=True, value=True)
    original = cmds.ls(selection=True, long=True) or []
    done = 0
    with utils.undo_chunk("gusrigPivots"):
        for obj in objs:
            try:
                cmds.xform(obj, worldSpace=True, pivots=position)
                done += 1
            except RuntimeError as err:
                utils.warn(TOOL, "could not change '%s' (%s)." % (naming.short_name(obj), str(err).strip()))
        if orient:
            _orient_handles(objs, orientation)
        if original:
            cmds.select(original, replace=True)
    utils.info(TOOL, "moved the pivots of %d object(s) to (%.3f, %.3f, %.3f)." % (done, position[0],
                                                                                  position[1], position[2]))


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

def to_last_selected(*_):
    objs, _c = _split_selection()
    if len(objs) < 2:
        utils.warn(TOOL, "select the objects, then the target last.")
        return
    target = objs[-1]
    pos = cmds.xform(target, query=True, worldSpace=True, rotatePivot=True)
    _apply(objs[:-1], pos, _world_rotation_deg(target))


def to_components(*_):
    objs, comps = _split_selection()
    if not comps:
        utils.warn(TOOL, "select the objects plus some vertices / CVs / edges.")
        return
    if not objs:
        utils.warn(TOOL, "also select the objects whose pivots should move.")
        return
    _apply(objs, _components_center(comps), [0.0, 0.0, 0.0])


def to_origin(*_):
    objs, _c = _split_selection()
    if not objs:
        utils.warn(TOOL, "select one or more objects.")
        return
    _apply(objs, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])


def to_center(*_):
    objs, _c = _split_selection()
    if not objs:
        utils.warn(TOOL, "select one or more objects.")
        return
    bb = cmds.exactWorldBoundingBox(objs)
    _apply(objs, [(bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0], [0.0, 0.0, 0.0])


def to_typed(*_):
    objs, _c = _split_selection()
    if not objs:
        utils.warn(TOOL, "select one or more objects.")
        return
    _save()
    _apply(objs, cmds.floatFieldGrp(N("Pos"), query=True, value=True)[:3], [0.0, 0.0, 0.0])


def reset(*_):
    """Pivots back to each object's own origin (and the handles back to the object's axes)."""
    objs, _c = _split_selection()
    objs = _editable(objs)
    if not objs:
        utils.warn(TOOL, "select one or more objects.")
        return
    original = cmds.ls(selection=True, long=True) or []
    with utils.undo_chunk("gusrigPivotsReset"):
        for obj in objs:
            try:
                cmds.xform(obj, objectSpace=True, pivots=(0.0, 0.0, 0.0))
            except RuntimeError as err:
                utils.warn(TOOL, "could not reset '%s' (%s)." % (naming.short_name(obj), str(err).strip()))
            try:
                cmds.select(obj, replace=True)
                cmds.manipPivot(resetOrientation=True)
            except (RuntimeError, TypeError):
                pass
        if original:
            cmds.select(original, replace=True)
    utils.info(TOOL, "reset the pivots of %d object(s) to their own origin." % len(objs))


def _box_fracs():
    try:
        return [pivots.BOX[cmds.radioButtonGrp(N("Box%d" % i), query=True, select=True) - 1] for i in range(3)]
    except RuntimeError:
        return [0.5, 0.0, 0.5]


def to_box(fracs=None, each=None):
    """Pivots on a bounding-box spot: each object's own box, or the whole selection's."""
    objs, _c = _split_selection()
    objs = _editable(objs)
    if not objs:
        raise RuntimeError("select one or more objects (not joints).")
    fracs = fracs or _box_fracs()
    if each is None:
        each = cmds.radioButtonGrp(N("BoxEach"), query=True, select=True) == 1
    _save()
    with utils.undo_chunk("gusrigPivotsBox"):
        if each:
            for o in objs:
                pivots.set_pivots([o], pivots.box_point(pivots.bounding_box([o]), *fracs))
        else:
            pivots.set_pivots(objs, pivots.box_point(pivots.bounding_box(objs), *fracs))
    utils.info(TOOL, "pivots of %d object(s) on the %s of %s box." % (
        len(objs), pivots.box_label(*fracs), "each object's" if each else "the selection's"))


def from_geometry(*_):
    """Objects + components: pivot on the components (unless 'position' is off), handles along them."""
    objs, comps = _split_selection()
    objs = _editable(objs)
    if not comps:
        raise RuntimeError("select the objects, plus a face, an edge or 2-3 vertices / CVs.")
    if not objs:
        owners = {c.split(".")[0] for c in comps}
        objs = _editable([cmds.ls(o, long=True)[0] for o in owners if cmds.objExists(o)])
        objs = [cmds.listRelatives(o, parent=True, fullPath=True)[0] if cmds.objectType(o, isAType="shape")
                else o for o in objs]
    centre, rows = pivots.component_frame(comps)
    rot = pivots.euler_xyz(rows)
    keep_pos = not cmds.checkBox(N("GeoPos"), query=True, value=True)
    _save()
    with utils.undo_chunk("gusrigPivotsGeo"):
        for o in objs:
            pos = cmds.xform(o, query=True, worldSpace=True, rotatePivot=True) if keep_pos else centre
            pivots.set_pivots([o], pos, rot)
    utils.info(TOOL, "%d object(s): handles along the %s%s." % (
        len(objs), "face" if ".f[" in comps[0] else "edge" if ".e[" in comps[0] else "points",
        "" if keep_pos else ", pivot on them"))


def along_chain(*_):
    objs, _c = _split_selection()
    if len(objs) < 3:
        raise RuntimeError("select the objects, then joint A, then joint B (last).")
    a, b = objs[-2], objs[-1]
    pct = cmds.floatSliderGrp(N("Chain"), query=True, value=True)
    _save()
    pos = pivots.along(a, b, pct / 100.0)
    with utils.undo_chunk("gusrigPivotsChain"):
        n = pivots.set_pivots(objs[:-2], pos)
    utils.info(TOOL, "%d pivot(s) at %.0f%% from %s to %s." % (n, pct, naming.short_name(a), naming.short_name(b)))


def remember(*_):
    objs, comps = _split_selection()
    if comps:
        centre, rows = pivots.component_frame(comps) if len(comps) > 1 or ".f[" in comps[0] or ".e[" in comps[0]             else (_components_center(comps), None)
        mem = pivots.remember(None, centre, pivots.euler_xyz(rows) if rows else [0.0, 0.0, 0.0])
    elif objs:
        mem = pivots.remember(objs[-1])
    else:
        raise RuntimeError("select the object (or components) whose pivot to remember.")
    _show_memory()
    utils.info(TOOL, "remembered the pivot of %s." % mem["from"])


def apply_remembered(*_):
    mem = pivots.remembered()
    if not mem:
        raise RuntimeError("nothing remembered yet: select an object, Remember.")
    objs, _c = _split_selection()
    if not objs:
        raise RuntimeError("select the objects to get the remembered pivot.")
    orient = cmds.checkBox(N("Orient"), query=True, value=True)
    with utils.undo_chunk("gusrigPivotsApply"):
        n = pivots.set_pivots(objs, mem["position"], mem["rotation"] if orient else None)
    utils.info(TOOL, "%d pivot(s) put where %s's was%s." % (n, mem["from"], " (handles too)" if orient else ""))


def mirror_twins(*_):
    objs, _c = _split_selection()
    if not objs:
        raise RuntimeError("select objects on one side: their twins get the mirrored pivots.")
    orient = cmds.checkBox(N("MirOrient"), query=True, value=True)
    _save()
    with utils.undo_chunk("gusrigPivotsMirror"):
        got = pivots.mirror_pivots(objs, 0, orient)
    done = [t for _o, t in got if t]
    lonely = [naming.short_name(o) for o, t in got if not t]
    msg = "%d twin(s) got the mirrored pivot." % len(done)
    if lonely:
        utils.warn(TOOL, msg + " No twin by name: " + ", ".join(lonely[:6]))
    else:
        utils.info(TOOL, msg)


def _show_memory():
    if not cmds.text(N("Memory"), exists=True):
        return
    mem = pivots.remembered()
    cmds.text(N("Memory"), edit=True, label="Remembered: %s at (%.2f, %.2f, %.2f)" % (
        mem["from"], mem["position"][0], mem["position"][1], mem["position"][2]) if mem else "Nothing remembered.")


def get_position(*_):
    objs, comps = _split_selection()
    if comps:
        pos = _components_center(comps)
    elif objs:
        pos = cmds.xform(objs[-1], query=True, worldSpace=True, rotatePivot=True)
    else:
        utils.warn(TOOL, "select an object or components to read from.")
        return
    cmds.floatFieldGrp(N("Pos"), edit=True, value1=pos[0], value2=pos[1], value3=pos[2])
    _save()


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, {
            "orient": cmds.checkBox(N("Orient"), query=True, value=True),
            "position": cmds.floatFieldGrp(N("Pos"), query=True, value=True)[:3],
            "box": [cmds.radioButtonGrp(N("Box%d" % i), query=True, select=True) for i in range(3)],
            "box_each": cmds.radioButtonGrp(N("BoxEach"), query=True, select=True) == 1,
            "geo_position": cmds.checkBox(N("GeoPos"), query=True, value=True),
            "chain": cmds.floatSliderGrp(N("Chain"), query=True, value=True),
            "mirror_orient": cmds.checkBox(N("MirOrient"), query=True, value=True),
        })
    except RuntimeError:
        pass
    _what()


def _what(*_):
    """The 'What will happen' line."""
    if not cmds.text(N("What"), exists=True):
        return
    objs, comps = _split_selection()
    if not objs and not comps:
        text = "Select the objects whose pivots should move (joints never change)."
    else:
        parts = ["%d object(s)" % len(pivots.editable(objs))]
        if len(objs) >= 2:
            parts.append("Last Selected: %s" % naming.short_name(objs[-1]))
        if comps:
            parts.append("From geometry: %d component(s)" % len(comps))
        if len(objs) >= 3:
            parts.append("Along a chain: %s > %s" % (naming.short_name(objs[-2]), naming.short_name(objs[-1])))
        text = " | ".join(parts)
    cmds.text(N("What"), edit=True, label=text)


def _light():
    objs, comps = _split_selection()
    if not objs and not comps:
        return "warn", "Select the objects whose pivots should move."
    parts = ["%d object(s)" % len(objs)]
    if comps:
        parts.append("Components -> centre of %d component(s)" % len(comps))
    if len(objs) >= 2:
        parts.append("Last Selected -> %s" % naming.short_name(objs[-1]))
    return "ok", " | ".join(parts)


def build(prefix="p_pivots_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Move pivots to", step=1, help_text="Objects never move, only their pivots. Last Selected: "
               "select the objects, then the target last. Components: objects + vertices / CVs. Joints are "
               "never changed, but a joint works as the target.")
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(170, 30))
    cmds.button(label="Last Selected", command=_w(to_last_selected),
                annotation="Select the objects, then the target last.")
    cmds.button(label="Components", command=_w(to_components),
                annotation="Objects + vertices / CVs / edges: their centre.")
    cmds.button(label="World Origin", command=_w(to_origin))
    cmds.button(label="Selection Center", command=_w(to_center))
    cmds.setParent("..")
    p = s["position"]
    cmds.floatFieldGrp(N("Pos"), label="Position", numberOfFields=3, value1=p[0], value2=p[1],
                       value3=p[2], precision=3, columnWidth4=(55, 80, 80, 80), changeCommand=_w(_save))
    ui.row(2, 170)
    cmds.button(label="Get", command=_w(get_position), annotation="Read the position from the selection.")
    cmds.button(label="Apply Typed", command=_w(to_typed))
    cmds.setParent("..")
    cmds.checkBox(N("Orient"), label="Match orientation (Move / Rotate handles only)", value=s["orient"],
                  changeCommand=_w(_save))
    cmds.text(N("What"), label="", align="left", wordWrap=True, height=30, font="smallPlainLabelFont")
    ui.end_section()

    ui.section("Bounding box", step=2, help_text="The pivot on a spot of the bounding box: pick one per axis "
               "(e.g. Bottom + Centre + Centre = the bottom centre, where a prop stands). Each object: its own box. "
               "Whole selection: one box round everything.")
    for i, labels in enumerate(BOX_LABELS):
        cmds.radioButtonGrp(N("Box%d" % i), label="XYZ"[i], numberOfRadioButtons=3, labelArray3=labels,
                            select=s["box"][i], columnWidth4=(30, 80, 80, 80), changeCommand=_w(_save))
    cmds.radioButtonGrp(N("BoxEach"), label="Box of", numberOfRadioButtons=2,
                        labelArray2=["Each object", "Whole selection"], select=1 if s["box_each"] else 2,
                        columnWidth3=(50, 100, 120), changeCommand=_w(_save))
    ui.row(3, 113)
    cmds.button(label="Bottom centre", command=_w(_guard(lambda *_: to_box([0.5, 0.0, 0.5]))))
    cmds.button(label="Centre", command=_w(_guard(lambda *_: to_box([0.5, 0.5, 0.5]))))
    cmds.button(label="Top centre", command=_w(_guard(lambda *_: to_box([0.5, 1.0, 0.5]))))
    cmds.setParent("..")
    ui.main_button("Pivot on the picked box spot", _w(_guard(lambda *_: to_box())), "One undo.")
    ui.end_section()

    ui.section("From geometry", step=3, help_text="Select the objects, plus a face, an edge, or 2-3 vertices / "
               "CVs (in order). Face: handles stand on it (Y = its normal). Edge / 2 points: X along it. 3 points: "
               "Y = the plane's normal, X from the 1st to the 2nd. No objects selected: the components' own object.")
    cmds.checkBox(N("GeoPos"), label="Pivot on the components too (else only the handles turn)",
                  value=s["geo_position"], changeCommand=_w(_save))
    ui.main_button("Pivot + handles from the components", _w(_guard(from_geometry)), "One undo.")
    ui.end_section()

    ui.section("Along a chain", step=4, help_text="Select the objects, then joint (or object) A, then B last. "
               "The pivot goes that far from A to B (50% = half way).")
    cmds.floatSliderGrp(N("Chain"), label="% from A to B", field=True, minValue=0, maxValue=100, value=s["chain"],
                        precision=0, columnWidth3=(90, 50, 150), changeCommand=_w(_save))
    ui.main_button("Pivot between A and B", _w(_guard(along_chain)), "Objects, then A, then B. One undo.")
    ui.end_section()

    ui.section("Remember / mirror", step=5, help_text="Remember: the pivot (and handle orientation) of the last "
               "selected object, or of the selected components. Apply: the selected objects get it (handles too "
               "when Match orientation is on). Mirror to twins: each selected object's other-side twin (by name, "
               "L_ <-> R_) gets the mirrored pivot.")
    ui.row(2, 170)
    cmds.button(label="Remember", command=_w(_guard(remember)))
    cmds.button(label="Apply remembered", command=_w(_guard(apply_remembered)))
    cmds.setParent("..")
    cmds.text(N("Memory"), label="", align="left", font="smallPlainLabelFont")
    cmds.checkBox(N("MirOrient"), label="Mirror the handle orientation too", value=s["mirror_orient"],
                  changeCommand=_w(_save))
    cmds.button(label="Mirror pivots to the twins (L <-> R)", height=26, command=_w(_guard(mirror_twins)))
    ui.end_section()

    ui.section("Reset", step=6, help_text="Puts each pivot back at the object's own origin.")
    cmds.button(label="Reset pivots to each object's own origin", height=28, command=_w(reset))
    ui.end_section()
    ui.on_selection(N("What"), _w(_what))
    _show_memory()
    _what()


def show():
    ui.open_panel("pivots")


SCHEMA = [
    ("orient", "Match orientation (handles only)", "bool", None),
    ("box_each", "Bounding box of each object (else the whole selection)", "bool", None),
    ("geo_position", "From geometry: pivot on the components too", "bool", None),
    ("chain", "Along a chain: % from A to B", "float", None),
    ("mirror_orient", "Mirror pivots: handle orientation too", "bool", None),
]
