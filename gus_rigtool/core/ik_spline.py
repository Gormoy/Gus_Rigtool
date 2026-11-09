"""
Spline IK on a joint chain: curve, handle, drivers, controls, twist, optional stretch.

    build(chain_joints, options) -> dict of what was made

Options (keys):
    base            name base, e.g. "tail"
    spans           spans of the IK curve
    driver          "joints" (control joints skinned to the curve) or "clusters"
    count           number of control joints (2-5)
    shape           Shape Library shape name for the controls
    size            control size
    aim_axis        "+X" ...  (the chain's aim axis)
    up_axis         "+Y" ...  (the chain's up axis)
    twist           advanced twist from the first / last control
    stretch         stretch with the curve length
    stretch_mode    "translate" or "scale"
    global_scale    "node.attr" that scales the whole rig ("" = none)
    volume          volume preservation when stretching
    color           RGB for the controls
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import chain_math, curves, naming, shape_data, utils
from gus_rigtool.core import nodes as _nodes

AXIS_INDEX = {"+X": 0, "-X": 1, "+Y": 2, "-Y": 3, "+Z": 4, "-Z": 5}     # dForwardAxis
UP_INDEX = {"+Y": 0, "-Y": 1, "+Z": 3, "-Z": 4, "+X": 6, "-X": 7}       # dWorldUpAxis
UP_VECTOR = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0),
             "+Z": (0, 0, 1), "-Z": (0, 0, -1)}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def chain_from_root(root):
    """root and its first-child joints down to the end."""
    chain = [cmds.ls(root, long=True)[0]]
    while True:
        kids = cmds.listRelatives(chain[-1], children=True, type="joint", fullPath=True) or []
        if not kids:
            return chain
        chain.append(kids[0])


def base_from_joint(joint):
    """'tail_01_jnt' -> 'tail'."""
    base = naming.strip_type_suffix(joint).split(":")[-1]
    parts = base.split("_")
    while len(parts) > 1 and parts[-1].isdigit():
        parts.pop()
    return "_".join(parts)


_pos = _nodes.world_pos


def _group(name, parent=None):
    g = cmds.createNode("transform", name=naming.unique(name))
    if parent:
        cmds.parent(g, parent, relative=True)
    return cmds.ls(g, long=True)[0]


def _curve_fn(curve):
    sel = om.MSelectionList()
    sel.add(curves.curve_shapes(curve)[0])
    return om.MFnNurbsCurve(sel.getDagPath(0))


def _control_shape(o):
    shapes = {}
    for _cat, items in shape_data.builtin_shapes():
        shapes.update(dict(items))
    data = shapes.get(o["shape"], shapes["circle"])
    axis = o["aim_axis"][1]                         # the shape faces down the chain
    return shape_data.scale(shape_data.face(data, axis), float(o["size"]))


def _make_control(name, matrix, o):
    """Offset group + control at a world matrix. Returns (offset, ctrl)."""
    offset = cmds.createNode("transform", name=naming.unique(name + "_offset"))
    offset = cmds.ls(offset, long=True)[0]
    cmds.xform(offset, worldSpace=True, matrix=matrix)
    ctrl = curves.create_curve_control(naming.unique(name), _control_shape(o),
                                       curves.rgb_style(o["color"]))
    ctrl = cmds.parent(ctrl, offset, relative=True)[0]
    return offset, cmds.ls(ctrl, long=True)[0]


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build(chain, o):
    if len(chain) < 3:
        raise RuntimeError("a spline IK needs at least 3 joints")
    base = o["base"]
    made = {}

    top = _group(base + "_ik_grp")
    ctrls_grp = _group(base + "_ik_ctrls_grp", top)
    no_touch = _group(base + "_ik_noTouch_grp", top)
    cmds.setAttr(no_touch + ".visibility", 0)

    # ------------------------------------------------ curve through the chain
    pts = [_pos(j) for j in chain]
    crv = cmds.curve(degree=1, point=[tuple(p) for p in pts], name=naming.unique(base + "_ik_crv"))
    crv = cmds.rebuildCurve(crv, constructionHistory=False, replaceOriginal=True, rebuildType=0,
                            spans=max(1, int(o["spans"])), degree=3, keepRange=0,
                            keepEndPoints=True, keepControlPoints=False)[0]
    crv = cmds.ls(crv, long=True)[0]
    crv_id = utils.uuid(crv)
    cmds.parent(crv, no_touch)
    crv = utils.path(crv_id)
    cmds.setAttr(crv + ".inheritsTransform", 0)
    made["curve"] = crv

    # ------------------------------------------------ handle
    handle, _effector = cmds.ikHandle(startJoint=chain[0], endEffector=chain[-1], solver="ikSplineSolver",
                                      curve=crv, createCurve=False, parentCurve=False,
                                      name=naming.unique(base + "_ikHandle"))
    handle_id = utils.uuid(handle)
    cmds.parent(handle, no_touch)
    handle = utils.path(handle_id)
    made["handle"] = handle

    # ------------------------------------------------ drivers + controls
    crv = utils.path(crv_id)
    fn = _curve_fn(crv)
    total = fn.length()
    if o["driver"] == "clusters":
        cvs = cmds.ls(crv + ".cv[*]", flatten=True)
        driver_pts = [cmds.xform(cv, query=True, worldSpace=True, translation=True) for cv in cvs]
    else:
        n = max(2, min(5, int(o["count"])))
        driver_pts = []
        for i in range(n):
            u = fn.findParamFromLength(total * i / float(n - 1))
            p = fn.getPointAtParam(u, om.MSpace.kWorld)
            driver_pts.append([p.x, p.y, p.z])

    frames = chain_math.frames(driver_pts, aim_axis=o["aim_axis"], up_axis=o["up_axis"],
                               up_mode="noflip", ref=_chain_up(chain, o["up_axis"]))
    controls, drivers = [], []
    for i, (p, fr) in enumerate(zip(driver_pts, frames)):
        name = "%s_ik_%s_ctrl" % (base, str(i + 1).zfill(2))
        offset, ctrl = _make_control(name, chain_math.matrix(fr, p), o)
        ctrl_id = utils.uuid(ctrl)
        cmds.parent(offset, ctrls_grp)
        ctrl = utils.path(ctrl_id)
        if o["driver"] == "clusters":
            cl, cl_handle = cmds.cluster(cvs[i], name=naming.unique("%s_ik_%s_cluster" % (base, str(i + 1).zfill(2))))
            cl_handle = cmds.parent(cl_handle, ctrl)[0]
            cmds.setAttr(cmds.ls(cl_handle, long=True)[0] + ".visibility", 0)
            drivers.append(cl_handle)
        else:
            cmds.select(clear=True)
            drv = cmds.joint(name=naming.unique("%s_ik_%s_drv" % (base, str(i + 1).zfill(2))))
            drv = cmds.parent(drv, ctrl, relative=True)[0]
            drv = cmds.ls(drv, long=True)[0]
            cmds.setAttr(drv + ".visibility", 0)
            drivers.append(drv)
        controls.append(utils.path(ctrl_id))
    if o["driver"] != "clusters":
        cmds.skinCluster(drivers, utils.path(crv_id), toSelectedBones=True, maximumInfluences=2,
                         dropoffRate=4.0, name=naming.unique(base + "_ik_skinCluster"))
    made["controls"] = controls

    # ------------------------------------------------ twist
    if o["twist"]:
        h = utils.path(handle_id)
        cmds.setAttr(h + ".dTwistControlEnable", 1)
        cmds.setAttr(h + ".dWorldUpType", 4)                 # object rotation up (start / end)
        cmds.setAttr(h + ".dForwardAxis", AXIS_INDEX[o["aim_axis"]])
        cmds.setAttr(h + ".dWorldUpAxis", UP_INDEX[o["up_axis"]])
        v = UP_VECTOR[o["up_axis"]]
        cmds.setAttr(h + ".dWorldUpVector", *v)
        cmds.setAttr(h + ".dWorldUpVectorEnd", *v)
        cmds.connectAttr(controls[0] + ".worldMatrix[0]", h + ".dWorldUpMatrix", force=True)
        cmds.connectAttr(controls[-1] + ".worldMatrix[0]", h + ".dWorldUpMatrixEnd", force=True)

    # ------------------------------------------------ stretch
    if o["stretch"]:
        _stretch(chain, utils.path(crv_id), controls[-1], total, base, o)

    made["group"] = top
    return made


def _chain_up(chain, up_axis):
    """World direction of the chain's up axis at its first joint (No flip starts from it)."""
    m = cmds.getAttr(chain[0] + ".worldMatrix[0]")
    i, sign = chain_math.AXES[up_axis]
    return [m[i * 4] * sign, m[i * 4 + 1] * sign, m[i * 4 + 2] * sign]


def _stretch(chain, crv, last_ctrl, rest_length, base, o):
    """Joints follow the curve length; 'stretch' attribute (0-1) on the last control."""
    info = cmds.createNode("curveInfo", name=naming.unique(base + "_ik_curveInfo"))
    cmds.connectAttr(curves.curve_shapes(crv)[0] + ".worldSpace[0]", info + ".inputCurve")

    rest = cmds.createNode("multDoubleLinear", name=naming.unique(base + "_ik_restLength"))
    cmds.setAttr(rest + ".input1", rest_length)
    if o["global_scale"] and cmds.objExists(o["global_scale"]):
        cmds.connectAttr(o["global_scale"], rest + ".input2")
    else:
        cmds.setAttr(rest + ".input2", 1.0)

    ratio = cmds.createNode("multiplyDivide", name=naming.unique(base + "_ik_stretchRatio"))
    cmds.setAttr(ratio + ".operation", 2)
    cmds.connectAttr(info + ".arcLength", ratio + ".input1X")
    cmds.connectAttr(rest + ".output", ratio + ".input2X")

    # blend with the 'stretch' switch: 1 + (ratio - 1) * stretch
    if not cmds.attributeQuery("stretch", node=last_ctrl, exists=True):
        cmds.addAttr(last_ctrl, longName="stretch", attributeType="double", minValue=0, maxValue=1,
                     defaultValue=1, keyable=True)
    minus = cmds.createNode("addDoubleLinear", name=naming.unique(base + "_ik_stretchMinusOne"))
    cmds.connectAttr(ratio + ".outputX", minus + ".input1")
    cmds.setAttr(minus + ".input2", -1.0)
    weight = cmds.createNode("multDoubleLinear", name=naming.unique(base + "_ik_stretchWeight"))
    cmds.connectAttr(minus + ".output", weight + ".input1")
    cmds.connectAttr(last_ctrl + ".stretch", weight + ".input2")
    final = cmds.createNode("addDoubleLinear", name=naming.unique(base + "_ik_stretchFinal"))
    cmds.connectAttr(weight + ".output", final + ".input1")
    cmds.setAttr(final + ".input2", 1.0)
    out = final + ".output"

    axis = "XYZ"[chain_math.AXES[o["aim_axis"]][0]]
    others = [a for a in "XYZ" if a != axis]
    vol = None
    if o["volume"]:
        vol = cmds.createNode("multiplyDivide", name=naming.unique(base + "_ik_volume"))
        cmds.setAttr(vol + ".operation", 3)                    # power
        cmds.connectAttr(out, vol + ".input1X")
        cmds.setAttr(vol + ".input2X", -0.5)

    for j in chain[:-1] if o["stretch_mode"] == "scale" else chain[1:]:
        if o["stretch_mode"] == "scale":
            cmds.connectAttr(out, "%s.scale%s" % (j, axis), force=True)
        else:
            mult = cmds.createNode("multDoubleLinear", name=naming.unique(base + "_ik_stretchT"))
            cmds.setAttr(mult + ".input1", cmds.getAttr("%s.translate%s" % (j, axis)))
            cmds.connectAttr(out, mult + ".input2")
            cmds.connectAttr(mult + ".output", "%s.translate%s" % (j, axis), force=True)
    if vol:
        for j in chain[:-1]:
            for a in others:
                cmds.connectAttr(vol + ".outputX", "%s.scale%s" % (j, a), force=True)
