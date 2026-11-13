"""
Joints: evenly spaced, cleanly oriented joint chains on a curve, edges or objects.

    import gus_rigtool.main as gr; gr.show_tool("joints")

Input (from the selection)
  a NURBS curve | polygon edges / an edge loop (turned into a curve) |
  two or more objects (a path through them, in selection order) |
  a ribbon built with the Ribbon Rig Builder ("Match a ribbon": one joint per follicle)
Placement : count or spacing, even by length / by parameter / one per CV, trims, reverse
Orient    : aim + up axes; up from No flip / World / Object / Curve normal
Result    : a chain (parented) or separate joints, rotate = 0 (all in Joint Orient)
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import chain_math, colors, ik_spline, naming, shape_data, sides, ui, utils

TOOL = "Joints"
SETTINGS_KEY = "joints"

COUNT_MODES = ["Count", "Spacing"]
DISTRIBUTIONS = ["Even by length", "By parameter", "One per CV", "Match a ribbon"]
AXIS_ITEMS = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]
UP_MODES = ["No flip", "World axis", "Object", "Curve normal"]
WORLD_ITEMS = ["X", "Y", "Z"]
LAST_MODES = ["Copy parent", "World"]
RESULTS = ["Chain", "Separate joints"]
IK_DRIVERS = ["Control joints", "Clusters"]
STRETCH_MODES = ["Translate", "Scale"]
SHAPE_NAMES = [n for _c, items in shape_data.builtin_shapes() for n, _d in items]

DEFAULTS = {
    "count_mode": 1,
    "count": 10,
    "spacing": 1.0,
    "distribution": 1,
    "trim_start": 0.0,
    "trim_end": 0.0,
    "reverse": False,
    "aim_axis": 1,           # +X
    "up_axis": 3,            # +Y
    "up_mode": 1,            # No flip
    "world_up": 2,           # Y
    "up_object": "",
    "last": 1,
    "name": "chain",
    "suffix": "_jnt",
    "start_number": 1,
    "padding": 2,
    "add_side": False,
    "result": 1,
    "parent": "",
    "radius": 0.5,
    "side_color": False,
    "labels": False,
    "keep_curve": False,
    "preview_locators": False,
    # IK spline
    "ik": False,
    "ik_spans": 4,
    "ik_driver": 1,
    "ik_count": 3,
    "ik_shape": "circle",
    "ik_size": 1.0,
    "ik_twist": True,
    "ik_stretch": False,
    "ik_stretch_mode": 1,
    "ik_global_scale": "",
    "ik_volume": False,
}

PREVIEW_GRP = "gusrigJointPreview_grp"
_last_preview = {"key": None}       # skip the preview when nothing changed (no loops)

_P, N, _w, _guard = ui.tool_helpers("p_joints_", TOOL)


# ===========================================================================
# input
# ===========================================================================

def _curve_shape(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    for s in shapes:
        if cmds.nodeType(s) == "nurbsCurve":
            return s
    return None


def _surface_shape(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    for s in shapes:
        if cmds.nodeType(s) == "nurbsSurface":
            return s
    return None


def read_input():
    """
    What the selection gives:
      {'kind': 'curve'|'edges'|'objects'|'ribbon', 'name': str, 'curve': transform or None,
       'temp': bool, 'points': [..] for objects / ribbon}
    or None with a message.
    """
    sel = cmds.ls(orderedSelection=True, long=True, flatten=True) or \
        cmds.ls(selection=True, long=True, flatten=True) or []
    if not sel:
        return None, "Select a curve, edges, two or more objects, or a built ribbon."
    edges = [s for s in sel if ".e[" in s]
    if edges:
        return {"kind": "edges", "edges": edges, "name": sel[0].split(".")[0].split("|")[-1]}, None
    objs = [s for s in sel if "." not in s]
    for o in objs:
        if _curve_shape(o):
            return {"kind": "curve", "curve": o, "name": naming.short_name(o)}, None
        if _surface_shape(o):
            return {"kind": "ribbon", "surface": o, "name": naming.short_name(o)}, None
    transforms = [o for o in objs if cmds.objectType(o, isAType="transform")]
    if len(transforms) >= 2:
        return {"kind": "objects", "objects": transforms,
                "name": naming.strip_type_suffix(transforms[0]).split("|")[-1]}, None
    return None, "Select a curve, edges, two or more objects, or a built ribbon."


def _edges_to_curve(edges):
    cmds.select(edges, replace=True)
    curve = cmds.polyToCurve(form=2, degree=1, conformToSmoothMeshPreview=False)[0]
    cmds.delete(curve, constructionHistory=True)
    return cmds.ls(curve, long=True)[0]


def _objects_to_curve(objs):
    pts = [cmds.xform(o, query=True, worldSpace=True, rotatePivot=True) for o in objs]
    return cmds.ls(cmds.curve(degree=1, point=[tuple(p) for p in pts]), long=True)[0]


def _fn(curve):
    sel = om.MSelectionList()
    sel.add(_curve_shape(curve))
    return om.MFnNurbsCurve(sel.getDagPath(0))


def ribbon_points(surface):
    """World positions of a ribbon's follicles, in U order. None if it has no follicles."""
    shape = _surface_shape(surface)
    fols = set(cmds.listConnections(shape + ".local", type="follicle", source=False,
                                    destination=True, shapes=True) or [])
    if not fols:
        return None
    items = []
    for f in fols:
        f_shape = f if cmds.nodeType(f) == "follicle" else \
            (cmds.listRelatives(f, shapes=True, type="follicle", fullPath=True) or [None])[0]
        if not f_shape:
            continue
        t = cmds.listRelatives(f_shape, parent=True, fullPath=True)[0]
        items.append((cmds.getAttr(f_shape + ".parameterU"),
                      cmds.xform(t, query=True, worldSpace=True, translation=True)))
    return [p for _u, p in sorted(items)]


# ===========================================================================
# placement
# ===========================================================================

def points_on_curve(curve, o):
    """(points, closed, normals, total length) for the options."""
    fn = _fn(curve)
    closed = fn.form in (om.MFnNurbsCurve.kClosed, om.MFnNurbsCurve.kPeriodic)
    total = fn.length()
    umin, umax = fn.knotDomain
    params = []
    if o["distribution"] == 2:                                   # by parameter
        n = max(1, int(o["count"]))
        a = umin + (umax - umin) * o["trim_start"]
        b = umax - (umax - umin) * o["trim_end"]
        if n == 1:
            params = [(a + b) / 2.0]
        else:
            last = n if closed else n - 1
            params = [a + (b - a) * i / float(last) for i in range(n)]
    elif o["distribution"] == 3:                                 # one per CV
        for p in fn.cvPositions(om.MSpace.kWorld):
            try:
                _pt, u = fn.closestPoint(om.MPoint(p), space=om.MSpace.kWorld)
            except TypeError:
                _pt, u = fn.closestPoint(om.MPoint(p), None, 1e-6, om.MSpace.kWorld)
            params.append(u)
        if closed and len(params) > 1 and abs(params[-1] - params[0]) < 1e-6:
            params = params[:-1]
    else:                                                        # even by length
        mode = "spacing" if o["count_mode"] == 2 else "count"
        for d in chain_math.lengths_for(total, mode, o["count"], o["spacing"],
                                        o["trim_start"], o["trim_end"], closed):
            params.append(fn.findParamFromLength(min(max(d, 0.0), total)))

    points, normals = [], []
    for u in params:
        p = fn.getPointAtParam(u, om.MSpace.kWorld)
        points.append([p.x, p.y, p.z])
        try:
            nrm = fn.normal(u, om.MSpace.kWorld)
            normals.append([nrm.x, nrm.y, nrm.z])
        except RuntimeError:
            normals.append([0.0, 0.0, 0.0])
    return points, closed, normals, total


def plan(o):
    """
    Read the selection and work out every joint position: dict with points, frames,
    info text... or (None, message). Temporary curves are deleted again.
    """
    data, msg = read_input()
    if not data:
        return None, msg
    temp = None
    selection = cmds.ls(orderedSelection=True, long=True, flatten=True) or \
        cmds.ls(selection=True, long=True, flatten=True) or []
    try:
        if data["kind"] == "ribbon" or o["distribution"] == 4:
            src = data.get("surface")
            if not src:
                return None, "'Match a ribbon': select a ribbon built with the Ribbon Rig Builder."
            points = ribbon_points(src)
            if not points:
                return None, "'%s' has no follicles yet: build the ribbon first." % data["name"]
            closed, normals, total = False, None, None
        else:
            if data["kind"] == "edges":
                temp = _edges_to_curve(data["edges"])
                curve = temp
            elif data["kind"] == "objects":
                temp = _objects_to_curve(data["objects"])
                curve = temp
            else:
                curve = data["curve"]
            points, closed, normals, total = points_on_curve(curve, o)
        if o["reverse"]:
            points.reverse()
            if normals:
                normals.reverse()
        if not points:
            return None, "No joints with these settings."

        up_obj = None
        if o["up_mode"] == 3:
            found = cmds.ls(o["up_object"], long=True) if o["up_object"] else []
            if not found:
                return None, "Up direction 'Object': pick the up object first (Get)."
            up_obj = cmds.xform(found[0], query=True, worldSpace=True, rotatePivot=True)
        mode = {1: "noflip", 2: "world", 3: "object", 4: "normal"}[o["up_mode"]]
        frames = chain_math.frames(points, closed=closed,
                                   aim_axis=AXIS_ITEMS[o["aim_axis"] - 1],
                                   up_axis=AXIS_ITEMS[o["up_axis"] - 1], up_mode=mode,
                                   ref=chain_math.WORLD[WORLD_ITEMS[o["world_up"] - 1]],
                                   object_point=up_obj, normals=normals,
                                   last="parent" if o["last"] == 1 else "world")
        gap = chain_math.length(chain_math.sub(points[1], points[0])) if len(points) > 1 else 0.0
        info = "%d joints, %.3g apart, on '%s'" % (len(points), gap, data["name"])
        if total:
            info += " (length %.3g)" % total
        result = {"points": points, "frames": frames, "info": info, "data": data}
        if temp and o["keep_curve"]:
            result["keep"] = temp
            temp = None
        return result, None
    except ValueError as e:
        return None, str(e)
    finally:
        if temp and cmds.objExists(temp):
            cmds.delete(temp)
        if selection and (cmds.ls(selection=True, long=True, flatten=True) or []) != selection:
            cmds.select(selection, replace=True)


# ===========================================================================
# naming
# ===========================================================================

def joint_names(o, count, source_name, first_point):
    base = o["name"].strip() or naming.strip_type_suffix(source_name).split(":")[-1]
    if o["add_side"]:
        pairs = sides.default_pairs()
        if not sides.has_side(base, pairs):
            p = first_point
            side = "L" if p[0] > sides.tolerance() else ("R" if p[0] < -sides.tolerance() else "C")
            if side in ("L", "R"):
                base = sides.add_side(base, side, pairs[0])
    pad = max(1, int(o["padding"]))
    start = int(o["start_number"])
    return ["%s_%s%s" % (base, str(start + i).zfill(pad), o["suffix"]) for i in range(count)]


# ===========================================================================
# create
# ===========================================================================

def create(o):
    result, msg = plan(o)
    if not result:
        utils.warn(TOOL, msg)
        return []
    from gus_rigtool.tools.mirror_tool import set_joint_world, _round_tiny

    names = joint_names(o, len(result["points"]), result["data"]["name"], result["points"][0])
    parent = None
    if o["parent"]:
        found = cmds.ls(o["parent"], long=True)
        if len(found) == 1:
            parent = found[0]
        else:
            utils.warn(TOOL, "parent '%s' not found, joints made at the world level." % o["parent"])
    chain = o["result"] == 1

    made = []
    prev = parent
    for name, pt, fr in zip(names, result["points"], result["frames"]):
        under = prev if chain else parent
        j = cmds.createNode("joint", name=naming.unique(name), parent=under) if under \
            else cmds.createNode("joint", name=naming.unique(name))
        j = cmds.ls(j, long=True)[0]
        jid = utils.uuid(j)
        set_joint_world(j, om.MMatrix(chain_math.matrix(fr, pt)), False)
        j = utils.path(jid)
        _round_tiny(j)
        cmds.setAttr(j + ".radius", float(o["radius"]))
        if o["side_color"]:
            colors.apply_side_color(j)
        if o["labels"]:
            side = sides.side_of_node(j)
            try:
                cmds.setAttr(j + ".side", {"L": 1, "R": 2, "C": 0}[side])
                cmds.setAttr(j + ".type", 18)
                cmds.setAttr(j + ".otherType", naming.label_of(j), type="string")
            except RuntimeError:
                pass
        made.append(j)
        prev = j
    if result.get("keep"):
        utils.info(TOOL, "kept the curve '%s'." % naming.short_name(result["keep"]), "info")
    return made


# ===========================================================================
# preview
# ===========================================================================

def clear_preview(*_):
    state = cmds.undoInfo(query=True, stateWithoutFlush=True)
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        if cmds.objExists(PREVIEW_GRP):
            cmds.delete(PREVIEW_GRP)
    finally:
        cmds.undoInfo(stateWithoutFlush=state)


def _show_locators(points, o):
    """Temporary markers, made outside the undo queue."""
    state = cmds.undoInfo(query=True, stateWithoutFlush=True)
    cmds.undoInfo(stateWithoutFlush=False)
    sel = cmds.ls(selection=True, long=True, flatten=True) or []
    try:
        if cmds.objExists(PREVIEW_GRP):
            cmds.delete(PREVIEW_GRP)
        grp = cmds.createNode("transform", name=PREVIEW_GRP)
        size = max(0.05, float(o["radius"]))
        for i, p in enumerate(points):
            loc = cmds.spaceLocator(name="gusrigJointPreview%d" % (i + 1))[0]
            cmds.setAttr(loc + ".localScale", size, size, size)
            cmds.xform(loc, worldSpace=True, translation=p)
            cmds.parent(loc, grp)
        cmds.setAttr(grp + ".overrideEnabled", 1)
        cmds.setAttr(grp + ".overrideDisplayType", 2)              # reference: not selectable
    finally:
        if sel:
            cmds.select(sel, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=state)


def preview(*_):
    if not cmds.text(N("Preview"), exists=True):
        return
    try:
        o = _ui()
    except RuntimeError:
        return
    key = (tuple(cmds.ls(selection=True, long=True, flatten=True) or []), repr(sorted(o.items())), _P["p"])
    if key == _last_preview["key"]:
        return
    _last_preview["key"] = key
    state = cmds.undoInfo(query=True, stateWithoutFlush=True)
    cmds.undoInfo(stateWithoutFlush=False)                         # temp curves: no undo noise
    try:
        result, msg = plan(dict(o, keep_curve=False))
    finally:
        cmds.undoInfo(stateWithoutFlush=state)
    if not result:
        cmds.text(N("Preview"), edit=True, label=ui.wrap(msg), annotation=msg)
        clear_preview()
        return
    names = joint_names(o, len(result["points"]), result["data"]["name"], result["points"][0])
    label = result["info"] + "\n" + names[0] + (" ... " + names[-1] if len(names) > 1 else "")
    if o["ik"]:
        label += "\n" + _ik_summary(o)
    cmds.text(N("Preview"), edit=True, label=ui.wrap(label), annotation=label)
    if o["preview_locators"]:
        _show_locators(result["points"], o)
    else:
        clear_preview()


# ===========================================================================
# window
# ===========================================================================

def _ui():
    q = lambda kind, name, **k: getattr(cmds, kind)(N(name), query=True, **k)
    return {
        "count_mode": q("radioButtonGrp", "CountMode", select=True),
        "count": q("intField", "Count", value=True),
        "spacing": q("floatField", "Spacing", value=True),
        "distribution": q("optionMenu", "Dist", select=True),
        "trim_start": q("floatField", "TrimS", value=True) / 100.0,
        "trim_end": q("floatField", "TrimE", value=True) / 100.0,
        "reverse": q("checkBox", "Reverse", value=True),
        "aim_axis": q("optionMenu", "Aim", select=True),
        "up_axis": q("optionMenu", "Up", select=True),
        "up_mode": q("optionMenu", "UpMode", select=True),
        "world_up": q("optionMenu", "WorldUp", select=True),
        "up_object": q("textField", "UpObj", text=True).strip(),
        "last": q("optionMenu", "Last", select=True),
        "name": q("textField", "Name", text=True).strip(),
        "suffix": q("textField", "Suffix", text=True).strip(),
        "start_number": q("intField", "Start", value=True),
        "padding": q("intField", "Pad", value=True),
        "add_side": q("checkBox", "AddSide", value=True),
        "result": q("radioButtonGrp", "Result", select=True),
        "parent": q("textField", "Parent", text=True).strip(),
        "radius": q("floatField", "Radius", value=True),
        "side_color": q("checkBox", "SideColor", value=True),
        "labels": q("checkBox", "Labels", value=True),
        "keep_curve": q("checkBox", "KeepCurve", value=True),
        "preview_locators": q("checkBox", "PreviewLoc", value=True),
        "ik": q("checkBox", "IK", value=True),
        "ik_spans": q("intField", "IKSpans", value=True),
        "ik_driver": q("radioButtonGrp", "IKDriver", select=True),
        "ik_count": q("intField", "IKCount", value=True),
        "ik_shape": SHAPE_NAMES[q("optionMenu", "IKShape", select=True) - 1],
        "ik_size": q("floatField", "IKSize", value=True),
        "ik_twist": q("checkBox", "IKTwist", value=True),
        "ik_stretch": q("checkBox", "IKStretch", value=True),
        "ik_stretch_mode": q("radioButtonGrp", "IKStretchMode", select=True),
        "ik_global_scale": q("textField", "IKGlobal", text=True).strip(),
        "ik_volume": q("checkBox", "IKVolume", value=True),
    }


def _light():
    data, msg = read_input()
    if not data:
        return "warn", msg
    kind = {"curve": "curve", "edges": "%d edges" % len(data.get("edges", [])),
            "objects": "path through %d objects" % len(data.get("objects", [])), "ribbon": "ribbon"}[data["kind"]]
    return "ok", "Input: %s '%s'. Set the options, then Create joints." % (kind, data["name"])


def _save():
    try:
        s = _ui()
        s["trim_start"] *= 100.0
        s["trim_end"] *= 100.0
        utils.save_setting(SETTINGS_KEY, s)
    except RuntimeError:
        pass


def _on_change(*_):
    try:
        mode = cmds.radioButtonGrp(N("CountMode"), query=True, select=True)
        dist = cmds.optionMenu(N("Dist"), query=True, select=True)
        upm = cmds.optionMenu(N("UpMode"), query=True, select=True)
        cmds.intField(N("Count"), edit=True, enable=mode == 1 or dist == 2)
        cmds.floatField(N("Spacing"), edit=True, enable=mode == 2 and dist == 1)
        cmds.optionMenu(N("WorldUp"), edit=True, enable=upm in (1, 2))
        cmds.textField(N("UpObj"), edit=True, enable=upm == 3)
        stretch = cmds.checkBox(N("IKStretch"), query=True, value=True)
        cmds.intField(N("IKCount"), edit=True,
                      enable=cmds.radioButtonGrp(N("IKDriver"), query=True, select=True) == 1)
        for name in ("IKStretchMode", "IKGlobal", "IKVolume"):
            kind = {"IKStretchMode": cmds.radioButtonGrp, "IKGlobal": cmds.textField,
                    "IKVolume": cmds.checkBox}[name]
            kind(N(name), edit=True, enable=stretch)
    except RuntimeError:
        return
    _save()
    preview()
    ui.refresh_light(N("Light"))


def _get_into(field):
    def run(*_):
        sel = cmds.ls(selection=True, long=True) or []
        objs = [s for s in sel if "." not in s]
        if not objs:
            utils.warn(TOOL, "select an object first.")
            return
        cmds.textField(N(field), edit=True, text=naming.short_name(objs[-1]))
        _on_change()
    return run


def ik_options(o, base, root=None):
    color = colors.side_colors()["C"]
    if o["side_color"] and root:
        color = colors.side_colors()[sides.side_of_node(root)]
    else:
        color = utils.tool_settings("shapeLibrary", {}).get("color", color)
    return {
        "base": base, "spans": o["ik_spans"],
        "driver": "clusters" if o["ik_driver"] == 2 else "joints",
        "count": o["ik_count"], "shape": o["ik_shape"], "size": o["ik_size"],
        "aim_axis": AXIS_ITEMS[o["aim_axis"] - 1], "up_axis": AXIS_ITEMS[o["up_axis"] - 1],
        "twist": o["ik_twist"], "stretch": o["ik_stretch"],
        "stretch_mode": "scale" if o["ik_stretch_mode"] == 2 else "translate",
        "global_scale": o["ik_global_scale"], "volume": o["ik_volume"], "color": color,
    }


def _ik_summary(o):
    if o["ik_driver"] == 2:
        what = "clusters"
    else:
        what = "%d controls" % int(o["ik_count"])
    extra = [x for x, on in (("twist", o["ik_twist"]), ("stretch", o["ik_stretch"]),
                             ("volume", o["ik_stretch"] and o["ik_volume"])) if on]
    return "+ IK spline (%s%s)" % (what, ", " + ", ".join(extra) if extra else "")


def run(*_):
    o = _ui()
    _save()
    _last_preview["key"] = None
    ik_made = None
    with utils.undo_chunk("gusrigJoints"):
        clear_preview()
        made = create(o)
        if made and o["ik"]:
            if o["result"] != 1:
                utils.warn(TOOL, "IK spline needs a chain (Result: Chain). Joints made without IK.")
            else:
                try:
                    ik_made = ik_spline.build(made, ik_options(o, ik_spline.base_from_joint(made[0]), made[0]))
                except RuntimeError as e:
                    utils.warn(TOOL, "IK spline not added: %s." % e)
        if made:
            cmds.select(ik_made["controls"] if ik_made else made, replace=True)
    if made:
        msg = "created %d joints: %s ... %s" % (len(made), naming.short_name(made[0]), naming.short_name(made[-1]))
        if ik_made:
            msg += ", with IK spline (%d controls)" % len(ik_made["controls"])
        utils.info(TOOL, msg + ".")


def add_ik_to_selected(*_):
    """Add the IK spline to an existing chain: select its first joint."""
    o = _ui()
    _save()
    roots = [n for n in (cmds.ls(selection=True, long=True, type="joint") or [])]
    if not roots:
        utils.warn(TOOL, "select the first joint of a chain.")
        return
    chain = ik_spline.chain_from_root(roots[0])
    with utils.undo_chunk("gusrigJointsIK"):
        try:
            made = ik_spline.build(chain, ik_options(o, ik_spline.base_from_joint(chain[0]), chain[0]))
        except RuntimeError as e:
            utils.warn(TOOL, "IK spline not added: %s." % e)
            return
        cmds.select(made["controls"], replace=True)
    utils.info(TOOL, "IK spline on %d joints, %d controls." % (len(chain), len(made["controls"])))


def _get_global_scale(*_):
    sel = [n for n in (cmds.ls(selection=True) or []) if "." not in n]
    if not sel:
        utils.warn(TOOL, "select the node that scales the rig (e.g. the main control).")
        return
    node = sel[-1]
    attr = "globalScale" if cmds.attributeQuery("globalScale", node=node, exists=True) else "scaleY"
    cmds.textField(N("IKGlobal"), edit=True, text="%s.%s" % (naming.short_name(node), attr))
    _on_change()


def _menu(name, items, value, annotation=""):
    cmds.optionMenu(N(name), changeCommand=_w(_on_change), annotation=annotation)
    for item in items:
        cmds.menuItem(label=item)
    cmds.optionMenu(N(name), edit=True, select=value)


def _labeled(label, width=110):
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(width, 200), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label=label)


def build(prefix="p_joints_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)

    # ------------------------------------------------------------ placement
    ui.section("Placement", step=1, help_text="Select a curve, edges or an edge loop, two or more objects "
               "(a path through them), or a built ribbon. Count: that many joints. Spacing: one joint every "
               "N units. Even by length gives equal distances; Match a ribbon puts one joint per follicle.")
    cmds.radioButtonGrp(N("CountMode"), label="By", numberOfRadioButtons=2, labelArray2=COUNT_MODES,
                        select=s["count_mode"], columnWidth3=(110, 80, 80), changeCommand=_w(_on_change))
    _labeled("Joints")
    cmds.intField(N("Count"), value=int(s["count"]), minValue=1, maxValue=1000000, step=1, changeCommand=_w(_on_change))
    cmds.setParent("..")
    _labeled("Spacing")
    cmds.floatField(N("Spacing"), value=s["spacing"], minValue=0.001, maxValue=1000000.0, step=0.01, precision=3,
                    changeCommand=_w(_on_change), annotation="One joint every ... units (Even by length).")
    cmds.setParent("..")
    _labeled("Distribution")
    _menu("Dist", DISTRIBUTIONS, s["distribution"],
          "Even by length: equal distances. Match a ribbon: one joint per follicle of a built ribbon.")
    cmds.setParent("..")
    _labeled("Trim start / end %")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(80, 80))
    cmds.floatField(N("TrimS"), value=s["trim_start"], minValue=0, maxValue=99, precision=1,
                    changeCommand=_w(_on_change))
    cmds.floatField(N("TrimE"), value=s["trim_end"], minValue=0, maxValue=99, precision=1,
                    changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.checkBox(N("Reverse"), label="Reverse direction (start from the other end)", value=s["reverse"],
                  changeCommand=_w(_on_change))
    ui.end_section()

    # ------------------------------------------------------------ orientation
    ui.section("Orientation", step=2, help_text="Aim axis points down the chain, up axis to the side. "
               "No flip follows the curve smoothly (best for tails and spines). Rotate values end up at 0.")
    _labeled("Aim axis")
    _menu("Aim", AXIS_ITEMS, s["aim_axis"], "The joint axis that points down the chain.")
    cmds.setParent("..")
    _labeled("Up axis")
    _menu("Up", AXIS_ITEMS, s["up_axis"])
    cmds.setParent("..")
    _labeled("Up direction")
    _menu("UpMode", UP_MODES, s["up_mode"],
          "No flip: follows the curve smoothly (best for tails, spines). World: the world axis below. "
          "Object: towards an object. Curve normal: the curve's bend direction.")
    cmds.setParent("..")
    _labeled("World up")
    _menu("WorldUp", WORLD_ITEMS, s["world_up"], "Start direction for No flip, or the axis for World.")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(110, 160, 50), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Up object")
    cmds.textField(N("UpObj"), text=s["up_object"], changeCommand=_w(_on_change))
    cmds.button(label="Get", command=_w(_get_into("UpObj")))
    cmds.setParent("..")
    _labeled("Last joint")
    _menu("Last", LAST_MODES, s["last"])
    cmds.setParent("..")
    ui.end_section()

    # ------------------------------------------------------------ naming / result
    ui.section("Naming and result", step=3, help_text="Names are name_01_suffix... (empty name = the "
               "curve's name). Chain = parented joints; Separate = loose joints.")
    _labeled("Name")
    cmds.textField(N("Name"), text=s["name"], changeCommand=_w(_on_change),
                   annotation="Empty = the curve's name.")
    cmds.setParent("..")
    _labeled("Suffix")
    cmds.textField(N("Suffix"), text=s["suffix"], changeCommand=_w(_on_change))
    cmds.setParent("..")
    _labeled("Start number / padding")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(80, 80))
    cmds.intField(N("Start"), value=int(s["start_number"]), minValue=0, maxValue=1000000, step=1, changeCommand=_w(_on_change))
    cmds.intField(N("Pad"), value=int(s["padding"]), minValue=1, maxValue=6, step=1, changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.checkBox(N("AddSide"), label="Add the side from the position (tail -> L_tail)", value=s["add_side"],
                  changeCommand=_w(_on_change))
    cmds.radioButtonGrp(N("Result"), label="Result", numberOfRadioButtons=2, labelArray2=RESULTS,
                        select=s["result"], columnWidth3=(110, 80, 120), changeCommand=_w(_on_change))
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(110, 160, 50), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Parent under")
    cmds.textField(N("Parent"), text=s["parent"], changeCommand=_w(_on_change),
                   annotation="Empty = world.")
    cmds.button(label="Get", command=_w(_get_into("Parent")))
    cmds.setParent("..")
    _labeled("Radius")
    cmds.floatField(N("Radius"), value=s["radius"], minValue=0.01, maxValue=1000000.0, step=0.01, precision=2, changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.checkBox(N("SideColor"), label="Side colour", value=s["side_color"], changeCommand=_w(_on_change))
    cmds.checkBox(N("Labels"), label="Joint labels", value=s["labels"], changeCommand=_w(_on_change))
    cmds.checkBox(N("KeepCurve"), label="Keep the curve made from edges / objects", value=s["keep_curve"],
                  changeCommand=_w(_on_change))
    ui.end_section()

    # ------------------------------------------------------------ preview + create
    ui.section("IK spline", step=4, collapse=not s["ik"], help_text="Adds a spline IK when creating joints, "
               "or to an existing chain (select its first joint). Controls bend the curve; the first / last "
               "twist it; stretch follows the curve length with a 'stretch' switch on the last control.")
    cmds.checkBox(N("IK"), label="Add IK spline when creating joints", value=s["ik"],
                  changeCommand=_w(_on_change))
    _labeled("Curve spans")
    cmds.intField(N("IKSpans"), value=int(s["ik_spans"]), minValue=1, maxValue=1000000, step=1, changeCommand=_w(_on_change),
                  annotation="Spans of the clean IK curve made from the chain.")
    cmds.setParent("..")
    cmds.radioButtonGrp(N("IKDriver"), label="Drivers", numberOfRadioButtons=2, labelArray2=IK_DRIVERS,
                        select=s["ik_driver"], columnWidth3=(110, 110, 80), changeCommand=_w(_on_change),
                        annotation="Control joints: smooth bending (skinned to the curve). "
                                   "Clusters: one per curve CV, more direct.")
    _labeled("Controls")
    cmds.intField(N("IKCount"), value=int(s["ik_count"]), minValue=2, maxValue=5, step=1,
                  changeCommand=_w(_on_change))
    cmds.setParent("..")
    _labeled("Control shape")
    cmds.optionMenu(N("IKShape"), changeCommand=_w(_on_change))
    for name in SHAPE_NAMES:
        cmds.menuItem(label=shape_data.label(name))
    cmds.optionMenu(N("IKShape"), edit=True,
                    select=SHAPE_NAMES.index(s["ik_shape"]) + 1 if s["ik_shape"] in SHAPE_NAMES else 1)
    cmds.setParent("..")
    _labeled("Control size")
    cmds.floatField(N("IKSize"), value=float(s["ik_size"]), minValue=0.01, maxValue=1000000.0, step=0.01, precision=2,
                    changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.checkBox(N("IKTwist"), label="Twist from the first / last control", value=s["ik_twist"],
                  changeCommand=_w(_on_change))
    cmds.checkBox(N("IKStretch"), label="Stretch with the curve ('stretch' switch on the last control)",
                  value=s["ik_stretch"], changeCommand=_w(_on_change))
    cmds.radioButtonGrp(N("IKStretchMode"), label="Stretch by", numberOfRadioButtons=2,
                        labelArray2=STRETCH_MODES, select=s["ik_stretch_mode"], columnWidth3=(110, 90, 80),
                        changeCommand=_w(_on_change))
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(110, 160, 50), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Global scale")
    cmds.textField(N("IKGlobal"), text=s["ik_global_scale"], changeCommand=_w(_on_change),
                   annotation="node.attribute that scales the whole rig, e.g. main_ctrl.scaleY. Empty = none.")
    cmds.button(label="Get", command=_w(_get_global_scale))
    cmds.setParent("..")
    cmds.checkBox(N("IKVolume"), label="Volume preservation (thinner when stretched)", value=s["ik_volume"],
                  changeCommand=_w(_on_change))
    cmds.button(label="Add IK to selected chain (select its first joint)", height=26,
                command=_w(add_ik_to_selected))
    ui.end_section()

    ui.section("Preview and create", step=5, help_text="The text shows what will be made. Preview "
               "locators are temporary markers (not in the undo queue), removed on Create or close.")
    cmds.checkBox(N("PreviewLoc"), label="Show preview locators in the viewport",
                  value=s["preview_locators"], changeCommand=_w(_on_change),
                  annotation="Temporary markers, not in the undo queue. Removed on Create or close.")
    cmds.text(N("Preview"), label="", align="left", height=2 * ui.NOTE_LINE + 4)
    ui.main_button("Create joints", _w(run), "One undo.")
    ui.end_section()

    _centre_section()
    ui.on_selection(N("Preview"), _w(preview))
    cmds.scriptJob(uiDeleted=[N("Preview"), clear_preview], runOnce=True)
    _on_change()


# ---------------------------------------------------------------------------
# 4.1.1: a joint (locator, group) at the centre of the selection
# ---------------------------------------------------------------------------

CP_KINDS = ["Joint", "Locator", "Group"]
CP_PER = ["Everything", "Each object", "Each piece"]
CP_HOW = ["Average", "Box centre"]
CP_ORIENT = ["World", "From the components"]


def _cp_options():
    return {"cp_kind": cmds.radioButtonGrp(N("CpKind"), query=True, select=True),
            "cp_per": cmds.radioButtonGrp(N("CpPer"), query=True, select=True),
            "cp_how": cmds.radioButtonGrp(N("CpHow"), query=True, select=True),
            "cp_orient": cmds.radioButtonGrp(N("CpOrient"), query=True, select=True),
            "cp_chain": cmds.checkBox(N("CpChain"), query=True, value=True),
            "cp_parent": cmds.checkBox(N("CpParent"), query=True, value=True),
            "cp_name": cmds.textField(N("CpName"), query=True, text=True)}


def _cp_save(*_):
    try:
        for k, v in _cp_options().items():
            utils.update_setting(SETTINGS_KEY, k, v)
    except RuntimeError:
        pass
    _cp_what()


def _cp_args(o, sel):
    from gus_rigtool.core import centre_point as CP
    parent = None
    objs = [x for x in sel if "." not in x]
    if o["cp_parent"] and objs and cmds.nodeType(objs[-1]) == "joint":
        parent, sel = objs[-1], [x for x in sel if x != objs[-1]]
    return dict(kind=CP.KINDS[o["cp_kind"] - 1], per=CP.PER[o["cp_per"] - 1],
                how=("average", "box")[o["cp_how"] - 1], orient=("world", "components")[o["cp_orient"] - 1],
                chain=o["cp_chain"], parent=parent, name=o["cp_name"], sel=sel)


def _cp_what(*_):
    from gus_rigtool.core import centre_point as CP
    if not cmds.text(N("CpWhat"), exists=True):
        return
    try:
        o = _cp_options()
        sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
        if not sel:
            cmds.text(N("CpWhat"), edit=True, label="Select vertices, edges, faces, CVs or objects.")
            return
        a = _cp_args(o, sel)
        flat = len(cmds.ls(sel, flatten=True) or [])
        if flat > (400 if a["per"] == "piece" else 5000):
            cmds.text(N("CpWhat"), edit=True, label="%d points selected (counted when you press Make)." % flat)
            return
        groups = CP.groups_from_selection(a["sel"], a["per"])
        names = CP.names_for(groups, a["kind"], a["name"])
        text = "%d %s(s): %s" % (len(names), a["kind"], ", ".join(names[:4]) + (" ..." if len(names) > 4 else ""))
        if a["chain"] and len(names) > 1:
            text += "\nchained in selection order"
        if a["parent"]:
            text += "\nunder %s" % naming.short_name(a["parent"])
        cmds.text(N("CpWhat"), edit=True, label=text)
    except (RuntimeError, ValueError) as e:
        cmds.text(N("CpWhat"), edit=True, label=str(e))


def centre_point(*_):
    from gus_rigtool.core import centre_point as CP
    o = _cp_options()
    _cp_save()
    sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
    if not sel:
        raise RuntimeError("select vertices, edges, faces, CVs or objects first.")
    made = CP.make(**_cp_args(o, sel))
    utils.info(TOOL, "made %d: %s" % (len(made), ", ".join(naming.short_name(m) for m in made[:6])))


def _centre_section():
    s = utils.tool_settings(SETTINGS_KEY, dict(DEFAULTS, cp_kind=1, cp_per=1, cp_how=1, cp_orient=1, cp_chain=False,
                                               cp_parent=False, cp_name=""))
    ui.section("At the centre of the selection", step=6, help_text="A joint (or locator, or group) at the centre "
               "of what you select: vertices, edges, faces, CVs, objects, mixed. Each piece: one per separate piece "
               "(e.g. both eyes' vertices -> two joints; edge loops -> one per loop). From the components: the axes "
               "follow a face's normal / an edge. Chain: the joints one under the next, in selection order (edge "
               "loops down a tail). Under the last selected joint: select it last.")
    cmds.radioButtonGrp(N("CpKind"), label="Make", numberOfRadioButtons=3, labelArray3=CP_KINDS,
                        select=s["cp_kind"], columnWidth4=(70, 60, 70, 60), changeCommand=_w(_cp_save))
    cmds.radioButtonGrp(N("CpPer"), label="One for", numberOfRadioButtons=3, labelArray3=CP_PER,
                        select=s["cp_per"], columnWidth4=(70, 85, 90, 85), changeCommand=_w(_cp_save))
    cmds.radioButtonGrp(N("CpHow"), label="Centre", numberOfRadioButtons=2, labelArray2=CP_HOW,
                        select=s["cp_how"], columnWidth3=(70, 85, 90), changeCommand=_w(_cp_save))
    cmds.radioButtonGrp(N("CpOrient"), label="Axes", numberOfRadioButtons=2, labelArray2=CP_ORIENT,
                        select=s["cp_orient"], columnWidth3=(70, 70, 140), changeCommand=_w(_cp_save))
    cmds.checkBox(N("CpChain"), label="Chain them (in selection order, X down the chain)", value=s["cp_chain"],
                  changeCommand=_w(_cp_save))
    cmds.checkBox(N("CpParent"), label="Under the last selected joint", value=s["cp_parent"],
                  changeCommand=_w(_cp_save))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 200),
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Name")
    cmds.textField(N("CpName"), text=s["cp_name"], placeholderText="empty = from the object (L_ / R_ added)",
                   changeCommand=_w(_cp_save))
    cmds.setParent("..")
    cmds.text(N("CpWhat"), label="", align="left", wordWrap=True, height=44, font="smallPlainLabelFont")
    ui.main_button("Make at the centre", _w(_guard(centre_point)), "One undo.")
    ui.end_section()
    ui.on_selection(N("CpWhat"), _w(_cp_what))
    _cp_what()


def show():
    ui.open_panel("joints")


SCHEMA = [
    ("count_mode", "By", "choice", COUNT_MODES),
    ("count", "Joints", "float", None),
    ("spacing", "Spacing", "float", None),
    ("distribution", "Distribution", "choice", DISTRIBUTIONS),
    ("reverse", "Reverse direction", "bool", None),
    ("aim_axis", "Aim axis", "choice", AXIS_ITEMS),
    ("up_axis", "Up axis", "choice", AXIS_ITEMS),
    ("up_mode", "Up direction", "choice", UP_MODES),
    ("world_up", "World up", "choice", WORLD_ITEMS),
    ("last", "Last joint", "choice", LAST_MODES),
    ("name", "Name", "text", None),
    ("suffix", "Suffix", "text", None),
    ("padding", "Number padding", "float", None),
    ("add_side", "Add the side from the position", "bool", None),
    ("result", "Result", "choice", RESULTS),
    ("radius", "Radius", "float", None),
    ("side_color", "Side colour", "bool", None),
    ("labels", "Joint labels", "bool", None),
    ("keep_curve", "Keep the curve made from edges / objects", "bool", None),
    ("preview_locators", "Show preview locators", "bool", None),
    ("ik", "IK spline: add when creating", "bool", None),
    ("ik_spans", "IK spline: curve spans", "float", None),
    ("ik_driver", "IK spline: drivers", "choice", IK_DRIVERS),
    ("ik_count", "IK spline: controls", "float", None),
    ("ik_size", "IK spline: control size", "float", None),
    ("ik_twist", "IK spline: twist", "bool", None),
    ("ik_stretch", "IK spline: stretch", "bool", None),
    ("ik_stretch_mode", "IK spline: stretch by", "choice", STRETCH_MODES),
    ("ik_volume", "IK spline: volume preservation", "bool", None),
]
