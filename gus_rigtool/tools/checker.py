"""
Checker: looks for common rig problems and fixes the safe ones.

    import gus_rigtool.main as gr; gr.show_tool("checker")

Scope: the selected hierarchies, or the whole scene when nothing is selected.
Each check shows FAIL / WARN / INFO / PASS with a count. "Select" selects the problems,
"Fix" appears only when the fix is safe (it never moves skinned geometry or changes how
things deform). Every fix is one undo.
"""

import math
import os

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import colors, naming, sides, ui, utils

TOOL = "Checker"
SETTINGS_KEY = "checker"
EPS = 1e-4
CTRL_SUFFIXES = ("_ctrl", "_Ctrl", "_CTL")
KNOWN_SUFFIXES = ("_ctrl", "_Ctrl", "_CTL", "_jnt", "_bind", "_drv", "_grp", "_offset", "_zero", "_sdk",
                  "_auto", "_driven", "_geo", "_mesh", "_crv", "_loc", "_fol", "_ikHandle", "_cluster",
                  "_srf", "_ribbon", "Handle", "_follow", "_followSpace")
SEVERITY_BG = {
    "FAIL": (0.55, 0.16, 0.16),
    "WARN": (0.55, 0.38, 0.10),
    "INFO": (0.22, 0.32, 0.45),
    "PASS": (0.20, 0.36, 0.22),
    "ERROR": (0.40, 0.40, 0.40),
}

_P, N, _w, _guard = ui.tool_helpers("p_checker_", TOOL)
_results = {}            # prefix -> {check id: [nodes]}


# ===========================================================================
# scope helpers
# ===========================================================================

def _roots():
    sel = sorted(set(cmds.ls(selection=True, long=True, type="transform") or []), key=len)
    roots = []
    for n in sel:
        if not any(n.startswith(r + "|") for r in roots):
            roots.append(n)
    return roots


_STARTUP = None


def _startup_cameras():
    global _STARTUP
    if _STARTUP is None:
        _STARTUP = set()
        for cam in cmds.ls(type="camera", long=True) or []:
            if cmds.camera(cam, query=True, startupCamera=True):
                _STARTUP.update(cmds.listRelatives(cam, parent=True, fullPath=True) or [])
    return _STARTUP


def transforms(scope):
    """Every transform (joints too) in the scope, long names."""
    if scope:
        out = list(scope)
        for r in scope:
            out += cmds.listRelatives(r, allDescendents=True, fullPath=True, type="transform") or []
    else:
        out = cmds.ls(type="transform", long=True) or []
    cams = _startup_cameras()
    seen = set()
    return [n for n in out if n not in cams and not n.startswith("|legacy_grp")   # the replaced parts' backup
            and not (n in seen or seen.add(n))]


def _shapes(n, intermediate=False):
    shapes = cmds.listRelatives(n, shapes=True, fullPath=True) or []
    return [s for s in shapes if bool(cmds.getAttr(s + ".intermediateObject")) == intermediate]


def is_control(n):
    if cmds.nodeType(n) == "joint":
        return False
    if cmds.attributeQuery("gusRole", node=n, exists=True):        # a builder guide: never a control
        return False
    if cmds.attributeQuery("gusNotControl", node=n, exists=True):  # 5.6.17: sliders board frames and labels
        return False
    short = naming.split_namespace(n)[1]
    if short.endswith(CTRL_SUFFIXES):
        return True
    if short.endswith(("_crv", "_curve", "Curve")):
        return False
    return any(cmds.nodeType(s) == "nurbsCurve" for s in _shapes(n))


def is_mesh(n):
    return any(cmds.nodeType(s) == "mesh" for s in _shapes(n))


_settable = utils.settable


def _vals(node, attr):
    return cmds.getAttr("%s.%s" % (node, attr))[0]


# ===========================================================================
# checks: find (scope -> nodes) and fix (nodes -> count)
# ===========================================================================

# ---------------------------------------------------------------- controls

def find_ctrl_zero(scope):
    out = []
    for n in transforms(scope):
        if not is_control(n):
            continue
        t, r, s = _vals(n, "translate"), _vals(n, "rotate"), _vals(n, "scale")
        if any(abs(v) > EPS for v in t + r) or any(abs(v - 1.0) > EPS for v in s):
            out.append(n)
    return out


def fix_ctrl_zero(nodes):
    """Free channels to 0 (scale 1). 5.6.33: counts only the controls it changed, and says which channels it can't
    change (locked or driven) - Behaviour > Rest here > Keep the pose zeroes those without moving the control."""
    done, stuck = 0, []
    for n in nodes:
        changed = False
        for attr, value in (("translate", 0.0), ("rotate", 0.0), ("scale", 1.0)):
            for a in "XYZ":
                plug = "%s.%s%s" % (n, attr, a)
                v = cmds.getAttr(plug)
                if abs(v - value) <= EPS:
                    continue
                if _settable(plug):
                    cmds.setAttr(plug, value)
                    changed = True
                else:
                    stuck.append("%s.%s%s %g (%s)" % (naming.short_name(n), attr, a, round(v, 3),
                                                      "locked" if cmds.getAttr(plug, lock=True) else "driven"))
        done += changed
    if stuck:
        utils.warn(TOOL, "%d channel(s) can't be zeroed here: %s - select those controls and use Behaviour > Rest "
                   "here > Keep the pose (the group takes the pose, nothing moves)" % (len(stuck),
                                                                                       ", ".join(stuck[:8])))
    return done


def _time_curves(n):
    found = cmds.listConnections(n, type="animCurve", source=True, destination=False) or []
    return [c for c in set(found) if cmds.nodeType(c) in ("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT")]


def find_ctrl_keys(scope):
    return [n for n in transforms(scope) if is_control(n) and _time_curves(n)]


def fix_ctrl_keys(nodes):
    for n in nodes:
        curves_ = _time_curves(n)
        if curves_:
            cmds.delete(curves_)
    return len(nodes)


def _has_offset(n):
    p = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
    if not p or cmds.nodeType(p) != "transform" or cmds.listRelatives(p, shapes=True):
        return False
    kids = [k for k in cmds.listRelatives(p, children=True, fullPath=True, type="transform") or []
            if not cmds.objectType(k, isAType="constraint")]
    return len(kids) == 1


def find_ctrl_no_offset(scope):
    return [n for n in transforms(scope) if is_control(n) and not _has_offset(n)]


def fix_ctrl_no_offset(nodes):
    from gus_rigtool.tools.group_maker import group_each
    return len(group_each([utils.uuid(n) for n in nodes], ["_offset"], replace=False, match=True,
                          side_color=False))


def find_ctrl_neg_scale(scope):
    return [n for n in transforms(scope) if is_control(n) and any(v < 0 for v in _vals(n, "scale"))]


def find_ctrl_color(scope):
    out = []
    for n in transforms(scope):
        if not is_control(n):
            continue
        want = colors.color_for(n)
        shapes = [s for s in _shapes(n) if cmds.nodeType(s) == "nurbsCurve"]
        if not shapes:
            continue
        s = shapes[0]
        ok = (cmds.getAttr(s + ".overrideEnabled") and cmds.getAttr(s + ".overrideRGBColors")
              and all(abs(a - b) < 0.02 for a, b in zip(cmds.getAttr(s + ".overrideColorRGB")[0], want)))
        if not ok:
            out.append(n)
    return out


def fix_ctrl_color(nodes):
    for n in nodes:
        colors.apply_side_color(n)
    return len(nodes)


# ---------------------------------------------------------------- joints

def _joints(scope):
    return [n for n in transforms(scope) if cmds.nodeType(n) == "joint"]


def _ik_joints():
    """Joints an IK handle turns (their rotate values come from the solver)."""
    out = set()
    for h in cmds.ls(type="ikHandle") or []:
        try:
            out.update(cmds.ls(cmds.ikHandle(h, query=True, jointList=True) or [], long=True) or [])
        except (RuntimeError, TypeError):
            pass
    return out


def _rotate_driven(j):
    """Rotate comes from the rig: a constraint, an expression, a node or a key feeds it (5.0.6)."""
    return any(cmds.listConnections(p, source=True, destination=False)
               for p in [j + ".rotate"] + [j + ".rotate" + x for x in "XYZ"])


def find_jnt_rotate(scope):
    """Joints holding rotate values at rest. Joints the rig turns (constraints, connections, IK) are left out:
    their rotate values are the rig working, not a bind pose problem (5.0.6)."""
    ik = None
    out = []
    for j in _joints(scope):
        if not any(abs(v) > EPS for v in _vals(j, "rotate")) or _rotate_driven(j):
            continue
        ik = _ik_joints() if ik is None else ik
        if j not in ik:
            out.append(j)
    return out


def _euler(values, order=0):
    r = [math.radians(v) for v in values]
    return om.MEulerRotation(r[0], r[1], r[2], order).asMatrix()


def fix_jnt_rotate(nodes):
    """Rotate values into Joint Orient: the joint does not move."""
    done = 0
    for j in nodes:
        if not all(_settable("%s.%s%s" % (j, a, x)) for a in ("rotate", "jointOrient") for x in "XYZ"):
            continue
        r = _euler(_vals(j, "rotate"), cmds.getAttr(j + ".rotateOrder"))
        jo = _euler(_vals(j, "jointOrient"))
        e = om.MTransformationMatrix(r * jo).rotation()
        cmds.setAttr(j + ".jointOrient", math.degrees(e.x), math.degrees(e.y), math.degrees(e.z))
        cmds.setAttr(j + ".rotate", 0, 0, 0)
        done += 1
    return done


def find_jnt_scale(scope):
    out = []
    for j in _joints(scope):
        if any(cmds.listConnections("%s.scale%s" % (j, a), source=True, destination=False) for a in "XYZ"):
            continue                                       # driven (e.g. stretch): fine
        if any(abs(v - 1.0) > EPS for v in _vals(j, "scale")):
            out.append(j)
    return out


def find_jnt_flip(scope):
    """Joints whose Y or Z axis turns more than 90 degrees from their parent's."""
    out = []
    for j in _joints(scope):
        p = (cmds.listRelatives(j, parent=True, fullPath=True, type="joint") or [None])[0]
        if not p:
            continue
        mj, mp = cmds.getAttr(j + ".worldMatrix[0]"), cmds.getAttr(p + ".worldMatrix[0]")
        dy = sum(mj[4 + i] * mp[4 + i] for i in range(3))
        dz = sum(mj[8 + i] * mp[8 + i] for i in range(3))
        if dy < 0 and dz < 0:
            out.append(j)
    return out


def find_jnt_twist(scope, limit=30.0):
    """Joints turned around their own bone more than `limit` degrees against their parent (the side axes
    compared after taking out the bend) - they rotate differently from the joints before them."""
    import math
    out = []
    for j in _joints(scope):
        p = (cmds.listRelatives(j, parent=True, fullPath=True, type="joint") or [None])[0]
        if not p:
            continue
        if len(cmds.listRelatives(p, children=True, type="joint") or []) != 1:
            continue                                        # a branch (hips -> legs, hand -> fingers)
        mj, mp = cmds.getAttr(j + ".worldMatrix[0]"), cmds.getAttr(p + ".worldMatrix[0]")
        aim = mj[0:3]
        la = math.sqrt(sum(v * v for v in aim)) or 1.0
        aim = [v / la for v in aim]
        pa = mp[0:3]
        lp = math.sqrt(sum(v * v for v in pa)) or 1.0
        if sum(a * b / lp for a, b in zip(aim, pa)) < 0.0:
            continue                                        # not the same bone line (a new chain)

        def flat(v):
            d = sum(a * b for a, b in zip(v, aim))
            w = [a - d * b for a, b in zip(v, aim)]
            n = math.sqrt(sum(x * x for x in w))
            return [x / n for x in w] if n > 1e-6 else None
        a, b = flat(mj[4:7]), flat(mp[4:7])
        if not a or not b:
            continue
        cosang = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
        if math.degrees(math.acos(cosang)) > float(limit):
            out.append(j)
    return out


# ---------------------------------------------------------------- geometry

_DEFORMER_PARTS = ("tweak", "groupParts", "groupId", "objectSet", "dagPose", "shadingEngine")


# 5.6.32: nodes that only drive a setting (a deformer's on / off, a weight) - never the mesh's shape. The Clothes
# switch's nodes reach the bandages through their skin's nodeState and were taken for model history.
_NOT_SHAPE = ("unitConversion", "expression", "choice", "network", "time", "blendWeighted", "remapValue",
              # 5.6.33: by name too - Maya 2024 says 'drawdb/shader/operation/condition:utility/general', and
              # plusMinusAverage is 'math/operation', so the 5.6.32 classification check missed them
              "condition", "plusMinusAverage", "reverse", "multiplyDivide", "clamp", "setRange", "blendColors",
              "multDoubleLinear", "addDoubleLinear", "floatMath", "floatLogic", "floatCondition")
SETTING_CLASSES = ("utility", "math")


def _drives_a_setting(h):
    t = cmds.nodeType(h)
    if t in _NOT_SHAPE or t.startswith("animCurve"):
        return True
    try:
        return any(part.startswith(SETTING_CLASSES) for c in cmds.getClassification(t) or []
                   for part in c.split(":"))
    except (RuntimeError, ValueError, TypeError, AttributeError):
        return False


def _non_deformer_history(shape):
    out = []
    for h in cmds.listHistory(shape, pruneDagObjects=True) or []:
        if cmds.objectType(h, isAType="geometryFilter") or cmds.nodeType(h) in _DEFORMER_PARTS or \
                _drives_a_setting(h):
            continue
        out.append(h)
    return out


def _deformed(shape):
    return any(cmds.objectType(h, isAType="geometryFilter")
               for h in cmds.listHistory(shape, pruneDagObjects=True) or [])


def find_mesh_history(scope):
    return [n for n in transforms(scope) if is_mesh(n) and _non_deformer_history(_shapes(n)[0])]


def history_detail(n):
    """5.6.31: (the history nodes as 'name (type)', referenced) - what 'non-deformer history' is on a mesh, and
    whether it's fixed here or in the model file."""
    nodes = _non_deformer_history(_shapes(n)[0]) if _shapes(n) else []
    try:
        ref = bool(cmds.referenceQuery(n, isNodeReferenced=True))
    except RuntimeError:
        ref = False
    return ["%s (%s)" % (naming.short_name(h), cmds.nodeType(h)) for h in nodes], ref


def fix_mesh_history(nodes):
    """5.6.22: a mesh inside a referenced file can't lose its history here (Maya refuses - the fix crashed):
    left, and said - fix it in the model file."""
    from gus_rigtool.core import safe
    done, ref, moved = 0, [], []
    for n in nodes:
        try:
            if cmds.referenceQuery(n, isNodeReferenced=True):
                ref.append(n)
                continue
        except RuntimeError:
            pass
        try:                                           # 5.6.31: undone if the mesh moves (the left eye did)
            kept, _why = safe.run(lambda n=n: cmds.bakePartialHistory(n, prePostDeformers=True),
                                  label="gusrigHistory", states=("rest",))
            if kept:
                done += 1
            else:
                moved.append(n)
        except RuntimeError:
            ref.append(n)
    if moved:
        utils.warn("Checker", "%d mesh(es) moved when their history went, so it was put back: %s - that history "
                   "places the mesh (a mirror, a move): keep it, or redo the mesh in the model file" % (
                       len(moved), ", ".join(naming.short_name(x) for x in moved[:6])))
    if ref:
        utils.warn("Checker", "%d mesh(es) are in a referenced file - delete their history in the model file "
                   "(%s), then reload the reference: %s" % (len(ref), _ref_file(ref[0]),
                                                          ", ".join(naming.short_name(x) for x in ref[:6])))
    return done


def _ref_file(node):
    try:
        return os.path.basename(cmds.referenceQuery(node, filename=True, withoutCopyNumber=True))
    except RuntimeError:
        return "the model file"


def find_mesh_unfrozen(scope):
    out = []
    for n in transforms(scope):
        if not is_mesh(n):
            continue
        t, r, s = _vals(n, "translate"), _vals(n, "rotate"), _vals(n, "scale")
        if any(abs(v) > EPS for v in t + r) or any(abs(v - 1.0) > EPS for v in s):
            out.append(n)
    return out


def fix_mesh_unfrozen(nodes):
    done = 0
    for n in nodes:
        shapes = [s for s in _shapes(n) if cmds.nodeType(s) == "mesh"]
        if shapes and _deformed(shapes[0]):
            continue                                       # skinned / deformed: not safe
        try:
            cmds.makeIdentity(n, apply=True, translate=True, rotate=True, scale=True, normal=0)
            done += 1
        except RuntimeError:
            pass
    return done


def find_skin_influences(scope, limit=4):
    """Vertices (as 'mesh.vtx[i]') with more than `limit` skin influences. 5.6.1: not on skins with ngSkinTools
    layers - ngSkinTools decides those weights (and writes them over any cut)."""
    import maya.api.OpenMayaAnim as oma
    from gus_rigtool.core import repair
    out = []
    ng = repair.ng_skins()
    meshes = [n for n in transforms(scope) if is_mesh(n)] if scope else None
    for skin in cmds.ls(type="skinCluster") or []:
        if skin in ng:
            continue
        # 5.6.17: the shape the skin itself writes (with other shapes after it - the head squash's copies - the
        # first one listed wasn't, and OpenMaya refused: the check crashed)
        direct = cmds.listConnections(skin + ".outputGeometry[0]", source=False, destination=True, shapes=True) or []
        geo = [g for g in direct if cmds.nodeType(g) in ("mesh", "nurbsSurface", "nurbsCurve")] or \
            (cmds.skinCluster(skin, query=True, geometry=True) or [])
        if not geo:
            continue
        shape = cmds.ls(geo[0], long=True)[0]
        if cmds.nodeType(shape) != "mesh":
            continue                    # a ribbon surface / curve: no vertices to count (5.0.5)
        mesh_t = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        if meshes is not None and mesh_t not in meshes:
            continue
        try:
            sel = om.MSelectionList()
            sel.add(skin)
            sel.add(shape)
            fn = oma.MFnSkinCluster(sel.getDependNode(0))
            path = sel.getDagPath(1)
            comp = om.MFnSingleIndexedComponent().create(om.MFn.kMeshVertComponent)
            om.MFnSingleIndexedComponent(comp).setCompleteData(cmds.polyEvaluate(shape, vertex=True))
            weights, count = fn.getWeights(path, comp)
        except (RuntimeError, ValueError):
            # 5.6.18: Maya won't hand over that shape (the Hare's body skin, with copies after it) - read the
            # skin's own weight list instead, as the eyelid check did
            for v in _over_limit_from_plugs(skin, limit):
                out.append("%s.vtx[%d]" % (mesh_t, v))
            continue
        for v in range(len(weights) // count):
            used = sum(1 for w in weights[v * count:(v + 1) * count] if w > 1e-5)
            if used > limit:
                out.append("%s.vtx[%d]" % (mesh_t, v))
    return out


def _over_limit_from_plugs(skin, limit):
    """Vertex ids with more than `limit` influences, read from the skin's weightList (no shape needed)."""
    out = []
    try:
        sel = om.MSelectionList()
        sel.add(skin)
        wl = om.MFnDependencyNode(sel.getDependNode(0)).findPlug("weightList", False)
        for i in range(wl.numElements()):
            e = wl.elementByPhysicalIndex(i)
            ws = e.child(0)
            used = sum(1 for k in range(ws.numElements()) if ws.elementByPhysicalIndex(k).asDouble() > 1e-5)
            if used > limit:
                out.append(e.logicalIndex())
    except (RuntimeError, ValueError, AttributeError):
        pass
    return out


def _orig(scope, in_ref):
    out = []
    for n in transforms(scope):
        for s in _shapes(n, intermediate=True):
            if not cmds.listConnections(s, source=False, destination=True) and _referenced(s) == in_ref:
                out.append(s)
    return out


def find_default_material(scope):
    """5.6.7: meshes on Maya's default material (initialShadingGroup): anything that changes it changes them (the
    Hare's bandages faded in the viewport). Returns the mesh transforms."""
    if not cmds.objExists("initialShadingGroup"):
        return []
    try:
        members = cmds.sets("initialShadingGroup", query=True) or []
    except (RuntimeError, ValueError, IndexError):
        return []
    inside = set(transforms(scope)) if scope else None
    out = []
    for m in cmds.ls(members, long=True, objectsOnly=True) or []:
        if cmds.nodeType(m) == "mesh":
            if cmds.getAttr(m + ".intermediateObject"):
                continue
            m = (cmds.listRelatives(m, parent=True, fullPath=True) or [m])[0]
        if cmds.nodeType(m) == "transform" and m not in out and (inside is None or m in inside):
            out.append(m)
    return out


def fix_default_material(nodes):
    """One material of their own (rig_geo_lambert) for them all."""
    mat = "rig_geo_lambert"
    if not cmds.objExists(mat):
        mat = cmds.shadingNode("lambert", asShader=True, name=mat)
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=mat + "SG")
        cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
    sg = (cmds.listConnections(mat + ".outColor", type="shadingEngine") or [None])[0]
    if not sg:
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=mat + "SG")
        cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
    cmds.sets(nodes, edit=True, forceElement=sg)
    return len(nodes)


def find_orig_shapes(scope):
    return _orig(scope, False)


def find_orig_shapes_ref(scope):
    """Unused Orig shapes inside a referenced file: they can only be cleaned in that file (5.0.6)."""
    return _orig(scope, True)


def fix_orig_shapes(nodes):
    cmds.delete(nodes)
    return len(nodes)


# ---------------------------------------------------------------- scene

def _referenced(n):
    try:
        return bool(cmds.referenceQuery(n, isNodeReferenced=True))
    except (RuntimeError, ValueError):
        return False


def _dups(scope, in_ref):
    """Transforms whose short name is used more than once; in_ref: the ones where every copy is inside a
    referenced file (can't be renamed here) - otherwise the rest (5.0.5)."""
    nodes = transforms(scope)
    counts = {}
    for n in cmds.ls(dag=True, long=True) or []:
        counts.setdefault(n.split("|")[-1], []).append(n)
    out = []
    for n in nodes:
        same = counts.get(n.split("|")[-1], [])
        if len(same) > 1 and all(_referenced(x) for x in same) == in_ref:
            out.append(n)
    return out


def find_dup_names(scope):
    return _dups(scope, False)


def find_dup_names_ref(scope):
    return _dups(scope, True)


def rename_plan(nodes):
    """[(node, new short name)] for duplicate names: the first copy (the one highest in the hierarchy, then the
    first found) keeps its name; each other one gets its parent's name in front when that makes it unique
    (Tongue_grp_Tongue_end_IK_ctrl), else a number (edgeCurve_2). Referenced nodes are left (5.3.3)."""
    taken = set(n.split("|")[-1] for n in cmds.ls(long=True) or [])
    by_name = {}
    for n in nodes:
        by_name.setdefault(n.split("|")[-1], []).append(n)
    plan = []
    for short, same in sorted(by_name.items()):
        every = [x for x in (cmds.ls(short, long=True) or []) if not _referenced(x)] or same
        every = sorted(set(every) | set(same), key=lambda x: (x.count("|"), x))
        for n in every[1:]:
            if _referenced(n):
                continue
            parts = n.split("|")
            parent = parts[-2].split(":")[-1] if len(parts) > 2 else ""
            base = short.split(":")[-1]
            new = "%s_%s" % (parent, base) if parent and not base.startswith(parent) else ""
            if not new or new in taken:
                i = 2
                while "%s_%d" % (base, i) in taken:
                    i += 1
                new = "%s_%d" % (base, i)
            taken.add(new)
            plan.append((n, new))
    return plan


def fix_dup_names(nodes, ask=True):
    """Rename the extra copies of duplicate names (shows old -> new first)."""
    plan = rename_plan(nodes)
    if not plan:
        return 0
    if ask:
        text = "\n".join("%s  ->  %s" % (n, new) for n, new in plan[:25]) + (
            "\n... (+%d)" % (len(plan) - 25) if len(plan) > 25 else "")
        if cmds.confirmDialog(title="Gus_Rigtool - rename duplicates", message="Rename these copies?\n\n" + text +
                              "\n\nScripts, picker buttons or follows that use the old name by name may need it.",
                              button=["Rename", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                              dismissString="Cancel") != "Rename":
            return 0
    done = 0
    with utils.undo_chunk("gusrigRenameDuplicates"):
        for n, new in sorted(plan, key=lambda r: -r[0].count("|")):     # deepest first: the paths above stay valid
            if cmds.objExists(n):
                cmds.rename(n, new)
                done += 1
    return done


def find_util_names(scope):
    """Utility nodes (multiplyDivide, clamp, unitConversion...) still called by their type + number, that can be
    named from their connections (5.0.9)."""
    from gus_rigtool.core import networks
    return [old for old, _new in networks.plan()]


def fix_util_names(nodes):
    from gus_rigtool.core import networks
    return len(networks.rename(networks.plan(nodes)))


def find_empty_groups(scope):
    out = []
    for n in transforms(scope):
        if (cmds.nodeType(n) != "transform" or cmds.listRelatives(n, children=True)
                or cmds.listRelatives(n, shapes=True)):
            continue
        if cmds.listConnections(n, source=True, destination=True):
            continue
        out.append(n)
    return out


def fix_empty_groups(nodes):
    cmds.delete(nodes)
    return len(nodes)


def find_unknown(scope):
    return cmds.ls(type=["unknown", "unknownDag", "unknownTransform"], long=True) or []


def fix_unknown(nodes):
    done = 0
    for n in nodes:
        try:
            cmds.lockNode(n, lock=False)
            cmds.delete(n)
            done += 1
        except RuntimeError:
            pass
    return done


def find_namespaces(scope):
    skip = {"UI", "shared"}
    out = []
    for ns in cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True) or []:
        if ns in skip:
            continue
        out += cmds.namespaceInfo(ns, listOnlyDependencyNodes=True, dagPath=True) or []
    return [n for n in out if cmds.objExists(n) and not _referenced(n)]     # a reference's own: not leftovers


# ---------------------------------------------------------------- naming

def _named_things(scope):
    return [n for n in transforms(scope) if is_control(n) or cmds.nodeType(n) == "joint"]


def find_twins_missing(scope):
    """Controls named on a side (L_ / R_...) whose other side cannot be found."""
    from gus_rigtool.core import mirror_engine
    pairs = sides.default_pairs()
    return [n for n in transforms(scope)
            if is_control(n) and naming.side_of(n, pairs) in ("L", "R")
            and mirror_engine.twin_of(n, pairs) is None]


def fix_twins_missing(nodes):
    """Link each to the control at its mirrored position (5.0.6), so Mirror finds it whatever the names."""
    from gus_rigtool.core import mirror_engine
    axis, center = mirror_engine.plane()
    ctrls = [n for n in transforms(None) if is_control(n)]
    return len(sides.link_by_position(nodes, ctrls, axis, center))


def find_live_follow(scope):
    """Controls still following their twin live (Mirror > Live follow)."""
    from gus_rigtool.core import mirror_engine
    names = set(cmds.getAttr(n + "." + mirror_engine.FOLLOW_ATTR) for n in mirror_engine.follow_nodes())
    return [n for n in transforms(scope) if naming.short_name(n) in names]


def fix_live_follow(nodes):
    from gus_rigtool.core import mirror_engine
    done = 0
    for n in nodes:
        if mirror_engine._unfollow(n):
            done += 1
    return done


def _side_tol(nodes):
    """How far off the centre counts as a side for naming (5.0.11): 2% of the rig's height - a tongue or a tail
    that hangs a little off the middle stays centre."""
    ys = []
    for n in nodes:
        try:
            ys.append(cmds.xform(n, query=True, worldSpace=True, rotatePivot=True)[1])
        except (RuntimeError, ValueError):
            pass
    height = (max(ys) - min(ys)) if ys else 0.0
    return max(sides.tolerance(), height * 0.02)


def _pivot_side(n, tol):
    """'L' / 'R' / 'C' from the pivot (5.1.1). The shape only counts when the pivot sits exactly at the world origin
    (a frozen control whose pivot was never placed): a centred settings control drawn off to one side stays centre."""
    p = cmds.xform(n, query=True, worldSpace=True, rotatePivot=True)
    if max(abs(v) for v in p) > 1e-6:
        return "L" if p[0] > tol else ("R" if p[0] < -tol else "C")
    return sides.side_from_position(n, tol=tol)


def find_naming_side(scope):
    pairs = sides.default_pairs()
    things = _named_things(scope)
    tol = _side_tol(things)
    return [n for n in things if not sides.has_side(n, pairs) and _pivot_side(n, tol) in ("L", "R")]


def naming_side_plan(nodes):
    """[(node, new name)] the side Fix would give."""
    pairs = sides.default_pairs()
    tol = _side_tol(nodes)
    out = []
    for n in nodes:
        side = _pivot_side(n, tol)
        if side in ("L", "R"):
            out.append((n, sides.add_side(naming.short_name(n), side, pairs[0])))
    return out


def fix_naming_side(nodes, ask=True):
    """Adds the side to the names - after showing the list (5.1.1: nothing gets an R_ / L_ by surprise)."""
    plan = naming_side_plan(nodes)
    if not plan:
        return 0
    if ask:
        rows = ["%s  ->  %s" % (naming.short_name(n), new) for n, new in plan]
        if cmds.confirmDialog(
                title="Gus_Rigtool - add the side to these names", button=["Rename", "Cancel"],
                defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel",
                message="%d name(s):\n\n%s%s\n\nRenaming can break follows, mirroring and scripts that use the "
                        "names. One undo." % (len(rows), "\n".join(rows[:30]), "\n..." if len(rows) > 30 else "")
        ) != "Rename":
            return 0
    done = 0
    for nid, new in [(utils.uuid(n), new) for n, new in plan]:
        sides.apply_rename(utils.path(nid), new)
        done += 1
    return done


CONSTRAINT_TYPES = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint",
                    "poleVectorConstraint", "geometryConstraint", "normalConstraint", "tangentConstraint",
                    "pointOnPolyConstraint")


def find_naming_suffix(scope):
    out = []
    for n in transforms(scope):
        short = naming.split_namespace(n)[1]
        if _referenced(n) or cmds.nodeType(n) in CONSTRAINT_TYPES:
            continue                    # not renamable here / Maya's own constraint names (5.0.6)
        if not short.endswith(KNOWN_SUFFIXES):
            out.append(n)
    return out


# ---------------------------------------------------------------- rig (3.0)

_CONSTRAINTS = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint",
                "poleVectorConstraint")


def _hidden_above(c):
    """Groups above a control (and the control) switched off by hand: visibility off, nothing driving it."""
    out = []
    parts = c.split("|")
    for i in range(2, len(parts) + 1):
        n = "|".join(parts[:i])
        try:
            if not cmds.getAttr(n + ".visibility") and not cmds.listConnections(
                    n + ".visibility", source=True, destination=False):
                out.append(n)
        except (RuntimeError, ValueError):
            pass
    return out


def find_ctrl_hidden(scope):
    """5.3.4: controls the animator can't see because a group above them (or the control) was hidden by hand - the
    Hare's Neck_ctrl_GRP took every neck and cape control with it. Driven visibility (IK / FK switch, the tweaks
    toggle) doesn't count. Returns the hidden groups."""
    out = []
    for n in transforms(scope):
        if not is_control(n):
            continue
        for h in _hidden_above(n):
            if h not in out:
                out.append(h)
    return out


def fix_ctrl_hidden(nodes):
    for n in nodes:
        cmds.setAttr(n + ".visibility", 1)
    return len(nodes)


def find_ctrl_no_switch(scope):
    """5.6.5: with visibility switches in the rig: controls on none of them (made after the switches)."""
    from gus_rigtool.core import vis_switch
    got = vis_switch.unassigned()
    if scope:
        got = [c for c in got if c in set(transforms(scope))]
    return got


def fix_ctrl_no_switch(nodes):
    from gus_rigtool.core import vis_switch
    n = 0
    for c in nodes:
        n += vis_switch.assign([c], vis_switch.kind(c))[0]
    return n


def find_ctrl_constrained(scope):
    """Controls whose own translate / rotate is driven by a constraint (animators can't key them)."""
    out = []
    for n in transforms(scope):
        if not is_control(n):
            continue
        for attr in ("translate", "rotate", "translateX", "rotateX", "rotateY", "rotateZ", "translateY",
                     "translateZ"):
            src = cmds.listConnections(n + "." + attr, source=True, destination=False, skipConversionNodes=True) or []
            if any(cmds.nodeType(s) in _CONSTRAINTS for s in src):
                out.append(n)
                break
    return out


_TRS = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ",
        "visibility"]


def find_ctrl_locked_shown(scope):
    """Controls with locked channels still in the channel box."""
    out = []
    for n in transforms(scope):
        if is_control(n) and any(cmds.getAttr(n + "." + a, lock=True) and
                                 (cmds.getAttr(n + "." + a, keyable=True) or cmds.getAttr(n + "." + a, channelBox=True))
                                 for a in _TRS):
            out.append(n)
    return out


def fix_ctrl_locked_shown(nodes):
    for n in nodes:
        for a in _TRS:
            if cmds.getAttr(n + "." + a, lock=True):
                cmds.setAttr(n + "." + a, keyable=False, channelBox=False)
    return len(nodes)


def _skinned_meshes(scope):
    from gus_rigtool.core.skin_mirror import skin_of
    return [(n, skin_of(n)) for n in transforms(scope) if is_mesh(n) and skin_of(n)]


def find_skin_unused(scope):
    """Skinned meshes with joints in the skin that carry no weight."""
    from gus_rigtool.core import skin_tools
    return [n for n, skin in _skinned_meshes(scope) if skin_tools.unused_influences(skin)]


def fix_skin_unused(nodes):
    from gus_rigtool.core import skin_tools
    return skin_tools.remove_unused(nodes)


def _group(name):
    from gus_rigtool.builder import names
    found = cmds.ls(names.make("C", name, "grp"), long=True) or []
    return found[0] if found else None


def find_skin_off_skeleton(scope):
    """Meshes skinned to joints outside skeleton_grp (when there is a Gus_Rigtool rig)."""
    skel = _group("skeleton")
    if not skel:
        return []
    from gus_rigtool.core.skin_mirror import influences
    made = _tool_made_joints()
    return [n for n, skin in _skinned_meshes(scope)
            if any(not j.startswith(skel + "|") and j not in made for j in influences(skin))]


def _tool_made_joints():
    """Joints Gus_Rigtool made outside skeleton_grp on purpose (5.3.4): ribbon / face kit / cloth joints (in a
    ribbon build, or tagged as such)."""
    out = set()
    try:
        from gus_rigtool.core import ribbon
        for b in ribbon._find_builds().values():
            for n in b["nodes"]:
                if cmds.objExists(n):
                    out.update(cmds.ls(cmds.listRelatives(n, allDescendents=True, type="joint", fullPath=True) or [],
                                       long=True) or [])
                    if cmds.nodeType(n) == "joint":
                        out.update(cmds.ls(n, long=True) or [])
    except Exception:
        pass
    for j in cmds.ls(type="joint", long=True) or []:
        if any(cmds.attributeQuery(a, node=j, exists=True) for a in ("rrbIndex", "gusRibbon", "gusFaceKit")):
            out.add(j)
    return out


def find_jnt_off_guides(scope):
    """Built joints away from their guides (rig at rest): a control left posed, keys, or a constraint / driven key
    of yours holding the part where it was before (e.g. a constraint with an old offset)."""
    from gus_rigtool.builder import build as bld, guides, modules, names
    tol = max(0.01, float(bld.settings()["height"]) * 0.0005)
    out = []
    for g in guides.module_groups():
        info = guides.read(g)
        mod = modules.MODULES.get(info["type"])
        if not mod or not bld.is_module_built(info):
            continue
        specs = mod.guide_specs(mod.complete(dict(info["settings"])), 100.0, info["side"])
        for sp in specs:
            if sp.get("kind") == "pivot":
                continue
            gd = info["guides"].get(sp["role"])
            j = cmds.ls(names.make(info["side"], sp["part"], "jnt"), long=True, type="joint") or []
            if not gd or len(j) != 1:
                continue
            a = cmds.xform(gd, query=True, worldSpace=True, translation=True)
            b = cmds.xform(j[0], query=True, worldSpace=True, translation=True)
            if max(abs(x - y) for x, y in zip(a, b)) > tol:
                out.append(j[0])
    return out


def find_jnt_not_mirrored(scope):
    """Left / right joints (by name) that aren't mirror images in position, or a side joint with no twin."""
    from gus_rigtool.core import joint_labels
    return [left for left, _right, _off in joint_labels.not_mirrored()]


def find_skin_legacy(scope):
    """Meshes still skinned to old joints in legacy_grp (they don't move with the rig)."""
    from gus_rigtool.builder import existing
    plan = existing.legacy_skin_plan()
    out = []
    for skin in plan:
        for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
            t = g if cmds.nodeType(g) == "transform" else (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
            out += [x for x in cmds.ls(t, long=True) if x not in out]
    return out


def fix_skin_legacy(nodes):
    from gus_rigtool.builder import existing
    moved, left = existing.repair_legacy_skin()
    if left:
        from gus_rigtool.core import utils
        utils.warn("Checker", "no new joint at the same spot for: %s (Skin 6 > Move weights)." % ", ".join(left[:6]))
    return moved


def find_geo_no_skin(scope):
    """Meshes in geo_grp that nothing deforms or drives (they won't follow the rig)."""
    geo = _group("geo")
    if not geo:
        return []
    meshes = [n for n in cmds.listRelatives(geo, allDescendents=True, type="transform", fullPath=True) or []
              if is_mesh(n)]
    if scope:
        inside = set(transforms(scope))
        meshes = [m for m in meshes if m in inside]
    out = []
    for m in meshes:
        if _deformed(_shapes(m)[0]) or _moved_by_rig(m, geo):
            continue
        out.append(m)
    return out


def _driven_transform(n):
    """Something moves n: a constraint, or a connection into its translate / rotate / offsetParentMatrix."""
    if cmds.listConnections(n, source=True, destination=False, type="constraint"):
        return True
    for a in ("translate", "rotate", "translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ",
              "offsetParentMatrix"):
        try:
            if cmds.listConnections(n + "." + a, source=True, destination=False):
                return True
        except (RuntimeError, ValueError):
            pass
    return False


def _moved_by_rig(mesh, geo):
    """The mesh, or a group above it (5.0.11: the Hare's belt pieces in one constrained group), is driven - or it
    sits under a joint."""
    node = mesh
    stop = set(geo) if isinstance(geo, (list, tuple)) else {geo}
    while node and node not in stop:
        if cmds.nodeType(node) == "joint" or _driven_transform(node):
            return True
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    return False


def find_guides_shown(scope):
    """Gus_Rigtool guides still visible while the rig is built."""
    from gus_rigtool.builder import guides
    top = guides.top_group(create=False)
    if not top or not _group("controls") or not cmds.getAttr(top + ".visibility"):
        return []
    return [top] if any(cmds.getAttr(g + ".visibility") for g in guides.module_groups()) else []


def fix_guides_shown(nodes):
    for n in nodes:
        cmds.setAttr(n + ".visibility", 0)
    return len(nodes)


def find_empty_layers(scope):
    out = []
    for layer in cmds.ls(type="displayLayer") or []:
        if layer.split(":")[-1] == "defaultLayer" or cmds.referenceQuery(layer, isNodeReferenced=True):
            continue
        if not cmds.editDisplayLayerMembers(layer, query=True, fullNames=True):
            out.append(layer)
    return out


def fix_empty_layers(nodes):
    cmds.delete(nodes)
    return len(nodes)


# ===========================================================================
# the list
# ===========================================================================

# id, area, label, severity, find, fix (None = select only), on by default
CHECKS = [
    ("ctrl_zero", "Controls", "Controls not at zero", "WARN", find_ctrl_zero, fix_ctrl_zero, True),
    ("ctrl_keys", "Controls", "Keys left on controls", "WARN", find_ctrl_keys, fix_ctrl_keys, True),
    ("ctrl_no_offset", "Controls", "Controls without an offset group", "WARN", find_ctrl_no_offset,
     fix_ctrl_no_offset, True),
    ("ctrl_neg_scale", "Controls", "Negative scale on a control", "WARN", find_ctrl_neg_scale, None, True),
    ("ctrl_color", "Controls", "Colour does not match its side", "INFO", find_ctrl_color, fix_ctrl_color, False),
    ("ctrl_hidden", "Controls", "Controls hidden by a group above them", "WARN", find_ctrl_hidden, fix_ctrl_hidden,
     True),
    ("ctrl_constrained", "Controls", "Controls driven by a constraint", "WARN", find_ctrl_constrained, None, True),
    ("ctrl_no_switch", "Controls", "Controls on no visibility switch", "INFO", find_ctrl_no_switch,
     fix_ctrl_no_switch, True),
    ("ctrl_locked_shown", "Controls", "Locked channels still shown", "INFO", find_ctrl_locked_shown,
     fix_ctrl_locked_shown, True),
    ("twins_missing", "Controls", "Side controls without a twin", "INFO", find_twins_missing,
     fix_twins_missing, True),
    ("live_follow", "Controls", "Live follow left on", "WARN", find_live_follow, fix_live_follow, True),
    ("jnt_rotate", "Joints", "Joints with rotate values", "WARN", find_jnt_rotate, fix_jnt_rotate, True),
    ("jnt_scale", "Joints", "Joints with scale not 1", "WARN", find_jnt_scale, None, True),
    ("jnt_flip", "Joints", "Up axis flips along a chain", "WARN", find_jnt_flip, None, True),
    ("jnt_twist", "Joints", "Joint twisted against its parent", "WARN", find_jnt_twist, None, True),
    ("jnt_off_guides", "Joints", "Built joints away from their guides", "WARN", find_jnt_off_guides, None, True),
    ("jnt_not_mirrored", "Joints", "Left / right joints not mirror images", "WARN", find_jnt_not_mirrored, None,
     True),
    ("mesh_history", "Geometry", "Meshes with non-deformer history", "WARN", find_mesh_history,
     fix_mesh_history, True),
    ("mesh_unfrozen", "Geometry", "Meshes with unfrozen transforms", "WARN", find_mesh_unfrozen,
     fix_mesh_unfrozen, True),
    ("skin_influences", "Geometry", "Vertices over the influence limit", "WARN", find_skin_influences, None, True),
    ("skin_unused", "Geometry", "Skinned meshes with joints that carry no weight", "INFO", find_skin_unused, fix_skin_unused, True),
    ("skin_off_skeleton", "Geometry", "Skinned to joints outside skeleton_grp", "WARN", find_skin_off_skeleton,
     None, True),
    ("skin_legacy", "Geometry", "Skinned to old joints in legacy_grp", "FAIL", find_skin_legacy, fix_skin_legacy,
     True),
    ("geo_no_skin", "Geometry", "Meshes in geo_grp that don't follow the rig", "WARN", find_geo_no_skin, None,
     True),
    ("orig_shapes", "Geometry", "Unused Orig shapes", "INFO", find_orig_shapes, fix_orig_shapes, True),
    ("default_material", "Geometry", "Meshes on Maya's default material", "INFO", find_default_material,
     fix_default_material, True),
    ("orig_shapes_ref", "Geometry", "Unused Orig shapes inside a referenced file", "INFO", find_orig_shapes_ref,
     None, True),
    ("dup_names", "Scene", "Duplicate names", "FAIL", find_dup_names, fix_dup_names, True),
    ("dup_names_ref", "Scene", "Duplicate names inside a referenced file", "WARN", find_dup_names_ref, None, True),
    ("util_names", "Scene", "Utility nodes with default names", "INFO", find_util_names, fix_util_names, True),
    ("empty_groups", "Scene", "Empty groups", "INFO", find_empty_groups, fix_empty_groups, True),
    ("unknown", "Scene", "Unknown nodes (missing plugins)", "WARN", find_unknown, fix_unknown, True),
    ("guides_shown", "Scene", "Rig guides still shown on a built rig", "INFO", find_guides_shown,
     fix_guides_shown, True),
    ("empty_layers", "Scene", "Empty display layers", "INFO", find_empty_layers, fix_empty_layers, True),
    ("namespaces", "Scene", "Leftover namespaces", "INFO", find_namespaces, None, True),
    ("naming_side", "Naming", "No side in the name, but on L / R", "INFO", find_naming_side, fix_naming_side, True),
    ("naming_suffix", "Naming", "No known suffix (_ctrl, _jnt, _grp...)", "INFO", find_naming_suffix, None, True),
]

HELP = {
    "jnt_not_mirrored": "A left joint and its right twin (L_ / R_ names) should be mirror images across X. When "
                        "they aren't, skin mirroring that matches joints by distance (ngSkinTools' default) can't pair "
                        "them and sends weights to the wrong joint (or keeps them on the left one). Fix the guides "
                        "(Mirror guides / symmetry lock) and rebuild, or mirror by joint labels (Skin 4 > Label "
                        "joints, then ngSkinTools Mirror > Influences mapping > joint labels). Side joints with no "
                        "twin by name are listed too.",
    "ctrl_zero": "Animators expect every control to start at 0 (scale 1), so 'reset' brings back the rest "
                 "pose. Fix sets the unlocked channels to 0 / 1. Use offset groups to hold positions.",
    "ctrl_keys": "Keys left from testing get exported or confuse animators. Fix deletes the time-based keys "
                 "on the controls (set driven keys are not touched).",
    "ctrl_no_offset": "Without an offset group a control cannot be zeroed in place. Fix adds an _offset group "
                      "that holds the position, so the control goes to 0.",
    "ctrl_neg_scale": "A negative scale on the control itself can flip constraints and break exports. Put it "
                      "on an offset group instead (the Mirror tool does this).",
    "live_follow": "These controls still follow their twin live (Mirror > Live follow), so animators can't "
                   "key them. Fix turns live follow off; the pose stays.",
    "twins_missing": "A control named on one side whose other side is missing (or named differently), so "
                     "Mirror pose and Select twin skip it. Fix links each one to the control at its mirrored "
                     "position (a loop like the mouth, numbered around, where 02's twin is 26). Or mirror it, or "
                     "link the pair by hand in Mirror > Pose and twins.",
    "ctrl_color": "Controls coloured by side are easier to read. Fix applies the side colours.",
    "jnt_rotate": "Joints the rig turns (constraints, connections, IK) are not listed. Joints should hold their orientation in Joint Orient, with rotate = 0, so the bind pose "
                  "is clean. Fix moves the values into Joint Orient; nothing moves.",
    "jnt_twist": "The joint is turned around its own bone against its parent (more than the twist limit), so "
                 "it rotates on different axes - e.g. a wrist aiming at a hand guide that is off the line. "
                 "Builder arms: Wrist axes = like the forearm. Other rigs: re-orient it (Joints tool).",
    "jnt_scale": "Joint scale other than 1 (not driven by stretch) usually comes from a mistake and scales "
                 "the skin. Check them by hand.",
    "jnt_flip": "The side axes turn more than 90 degrees from the parent: the chain twists or flips when "
                "animated. Re-orient those joints (e.g. with the Joints tool).",
    "mesh_history": "Modelling history makes files heavy and can change the mesh. Fix deletes non-deformer "
                    "history (skin and other deformers stay).",
    "mesh_unfrozen": "Meshes with transform values can cause offsets when skinning or exporting. Fix freezes "
                     "them (only meshes without deformers).",
    "skin_influences": "Game engines usually allow 4 influences per vertex (the limit is in 'Checks to run'). "
                       "Select shows those vertices; prune them in the skin tools.",
    "orig_shapes_ref": "Unused Orig shapes inside a referenced file (the model). They can't be deleted from this "
                       "scene: open the model file, delete them there and save it.",
    "orig_shapes": "Leftover 'Orig' shapes from deleted deformers add weight and confuse exports. Fix deletes "
                   "the unused ones.",
    "ctrl_hidden": "A group above the controls (or a control) has its visibility switched off by hand - every "
    "control under it disappears for the animator (the Hare's Neck_ctrl_GRP). Fix shows them again; visibility "
    "driven by a switch (IK / FK, tweaks) is left alone.",
    "dup_names": "Two objects with the same short name break scripts, constraints by name and exports. "
                 "Rename them.",
    "dup_names_ref": "The same short name used twice inside a referenced file (a model or prop you brought in). "
                     "They can't be renamed here: open that file, rename them there and save it.",
    "util_names": "multiplyDivide13, unitConversion260, clamp1... say nothing about what they do. Fix names each "
                  "one from what feeds it and what it ends up driving: L_Brow_02_ty_to_fol_11_sdk_md (control, "
                  "channel, target, kind). Nodes you named, nodes in a referenced file and nodes with nothing in "
                  "or out are left alone. One undo.",
    "empty_groups": "Empty groups with no connections are leftovers. Fix deletes them.",
    "unknown": "Nodes from plugins that are not loaded make Maya complain and can block saving as .ma. Fix "
               "deletes them.",
    "namespaces": "Leftover namespaces from imports make names long and break name-based tools.",
    "naming_side": "The name has no side but the object is clearly on L or R (more than 2% of the rig's height "
                   "from the centre: a tongue or tail hanging a little off the middle isn't listed). Fix adds the "
                   "side (pattern from the Mirror tab) - only with its own Fix button, never in 'Fix all safe': "
                   "renaming can break follows, mirroring and scripts that use the names.",
    "ctrl_constrained": "A constraint drives the control's own translate / rotate, so animators can't key "
                        "it. Put the constraint on its offset group instead.",
    "default_material": "Meshes on initialShadingGroup share Maya's default material: anything that changes it "
                        "(a key, transmission) changes them all - the Hare's bandages faded. Fix gives them one "
                        "material of their own (rig_geo_lambert).",
    "ctrl_no_switch": "Controls made after the visibility switches (Build > Visibility switches) are on none, so "
                      "the animators can't hide them. Fix puts each on Body, Face or Secondary by its name.",
    "ctrl_locked_shown": "Locked channels that still show in the channel box only clutter it. Fix hides them.",
    "skin_unused": "Joints in the skin that carry no weight make the file heavier and the skin slower. Fix "
                   "removes them from the skin (the weights don't change).",
    "jnt_off_guides": "With the rig at rest, every built joint should sit on its guide. When it doesn't, something "
                      "holds the part: a control left posed or keyed, or a constraint / driven key of yours (from "
                      "before a rebuild) - Constraints > What drives what? on the part's groups shows it. Since 3.8 a "
                      "rebuild re-makes your constraints with a fresh offset.",
    "skin_legacy": "3 Existing rig > Replace left some weights on the old joints, now hidden in legacy_grp: those "
                   "vertices don't move with the rig. Fix moves each old joint's weights to the new bind joint at "
                   "the same spot (Build > 3 Existing rig > 5 Backup shows the list first).",
    "skin_off_skeleton": "The mesh is skinned to joints that aren't the rig's bind joints (skeleton_grp): "
                         "exports and rebuilds miss them. Bind to skeleton_grp's joints (Skin tab).",
    "geo_no_skin": "A mesh in geo_grp with no skin, no constraint and no joint parent: it stays behind when "
                   "the rig moves. Skin it (Skin tab) or constrain it.",
    "guides_shown": "The rig is built but its guides are still visible. Fix hides them (Back to guides still "
                    "works).",
    "empty_layers": "Display layers with nothing in them. Fix deletes them.",
    "naming_suffix": "Names without a type suffix are harder to find and filter. Rename if your convention "
                     "uses suffixes.",
}

DEFAULTS = {"influence_limit": 4, "twist_limit": 30}
DEFAULTS.update({"on_" + c[0]: c[6] for c in CHECKS})


# ===========================================================================
# running
# ===========================================================================

def run_checks(o, scope):
    """{id: (severity, nodes or error text)} for the enabled checks."""
    out = {}
    for cid, _area, _label, severity, find, _fix, _on in CHECKS:
        if not o.get("on_" + cid, True):
            continue
        try:
            if cid == "skin_influences":
                nodes = find(scope, int(o["influence_limit"]))
            elif cid == "jnt_twist":
                nodes = find(scope, float(o.get("twist_limit", 30)))
            else:
                nodes = find(scope)
            out[cid] = ("PASS" if not nodes else severity, nodes)
        except Exception as e:                              # one broken check never stops the rest
            out[cid] = ("ERROR", str(e))
    return out


def report_text(results):
    lines = []
    for cid, area, label, _sev, _f, _x, _on in CHECKS:
        if cid not in results:
            continue
        sev, nodes = results[cid]
        count = len(nodes) if isinstance(nodes, list) else 0
        lines.append("%-5s  %-9s %-42s %d" % (sev, area, label, count))
        if isinstance(nodes, list):
            for n in nodes[:20]:
                lines.append("        " + naming.short_name(n))
            if len(nodes) > 20:
                lines.append("        ... and %d more" % (len(nodes) - 20))
        else:
            lines.append("        error: " + nodes)
    return "\n".join(lines)


# ===========================================================================
# window
# ===========================================================================

def _ui():
    o = {"influence_limit": cmds.intField(N("Limit"), query=True, value=True),
         "twist_limit": cmds.intField(N("TwistLimit"), query=True, value=True)}
    for c in CHECKS:
        o["on_" + c[0]] = cmds.checkBox(N("On_" + c[0]), query=True, value=True)
    return o


def _light():
    roots = _roots()
    if roots:
        return "ok", "Scope: %s. Run checks." % ui.selection_summary(roots, "hierarchie")
    return "ok", "Scope: the whole scene (nothing selected). Run checks."


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def run(*_):
    o = _ui()
    _save()
    roots = _roots()
    results = run_checks(o, roots)
    _results[_P["p"]] = results
    _show(results)
    fails = sum(1 for s, _n in results.values() if s == "FAIL")
    warns = sum(1 for s, _n in results.values() if s == "WARN")
    where = "%d selected hierarchies" % len(roots) if roots else "the whole scene"
    level = "warn" if fails or warns else "ok"
    utils.info(TOOL, "%d checks on %s: %d fail, %d warning." % (len(results), where, fails, warns), level)


_repairs = {}


def find_repairs(*_):
    from gus_rigtool.core import repair
    items = repair.find()
    _repairs[_P["p"]] = items
    col = N("Repairs")
    for child in cmds.columnLayout(col, query=True, childArray=True) or []:
        cmds.deleteUI(child)
    cmds.setParent(col)
    if not items and not repair.ERRORS:
        cmds.text(label="Nothing to repair.", align="left")
    for what, why in repair.ERRORS:                  # 5.6.29: a check that couldn't run says so
        cmds.text(label="  couldn't check: %s - %s" % (what, why), align="left", font="smallPlainLabelFont")
    for it in items:
        cmds.checkBox(N("Rep_" + it.id), label="%s  (%d)" % (it.label, it.count), value=True, annotation=it.detail)
        cmds.text(label="      " + it.detail, align="left", font="smallPlainLabelFont")
    cmds.setParent("..")
    utils.info(TOOL, "%d repair(s) found%s." % (len(items), "; %d check(s) couldn't run - listed" % len(
        repair.ERRORS) if repair.ERRORS else ""), "warn" if items or repair.ERRORS else "ok")


def apply_repairs(*_):
    from gus_rigtool.core import repair
    items = _repairs.get(_P["p"]) or []
    ids = [it.id for it in items if cmds.checkBox(N("Rep_" + it.id), exists=True)
           and cmds.checkBox(N("Rep_" + it.id), query=True, value=True)]
    if not ids:
        raise RuntimeError("press Find repairs, then tick what to repair.")
    out = repair.apply(ids, items)
    lines = ["%s: %s" % (label, res) for label, res in out]
    ui.report_window("Gus_Rigtool - repairs", "\n".join(lines) + "\n\nEach repair is its own undo step (Ctrl+Z, "
                     "newest first); one that failed was undone at once.")
    find_repairs()


def _show(results):
    col = N("Results")
    for child in cmds.columnLayout(col, query=True, childArray=True) or []:
        cmds.deleteUI(child)
    cmds.setParent(col)
    if not results:
        cmds.text(label="No checks are on.", align="left")
        return
    for cid, area, label, _sev, _find, fix, _on in CHECKS:
        if cid not in results:
            continue
        sev, nodes = results[cid]
        count = len(nodes) if isinstance(nodes, list) else 0
        cmds.rowLayout(numberOfColumns=6, columnWidth6=(48, 170, 34, 55, 45, 22), adjustableColumn=2,
                       columnAttach=[(1, "both", 1), (2, "both", 4), (3, "both", 1), (4, "both", 1),
                                     (5, "both", 1), (6, "both", 1)])
        cmds.text(label=sev, backgroundColor=SEVERITY_BG[sev], enableBackground=True, height=22)
        cmds.text(label=label if sev != "ERROR" else "%s (error: %s)" % (label, nodes), align="left",
                  annotation=area)
        cmds.text(label=str(count) if sev != "ERROR" else "-")
        cmds.button(label="Select", enable=count > 0, command=_w(lambda *_, c=cid: select_check(c)))
        cmds.button(label="Fix", enable=bool(fix) and count > 0,
                    command=_w(lambda *_, c=cid: fix_check(c)),
                    annotation="Safe fix, one undo." if fix else "No safe automatic fix.")
        cmds.button(label="?", annotation=HELP.get(cid, ""),
                    command=lambda *_, t=label, h=HELP.get(cid, ""): cmds.confirmDialog(title=t, message=h,
                                                                                        button=["OK"]))
        cmds.setParent("..")


def _current(cid):
    sev, nodes = _results.get(_P["p"], {}).get(cid, ("PASS", []))
    if not isinstance(nodes, list):
        return []
    return [n for n in nodes if cmds.objExists(n)]


def select_check(cid):
    nodes = _current(cid)
    if nodes:
        cmds.select(nodes, replace=True)
        utils.info(TOOL, "selected %d." % len(nodes), "info")


def _fix_one(cid):
    entry = [c for c in CHECKS if c[0] == cid][0]
    fix, nodes = entry[5], _current(cid)
    if not fix or not nodes:
        return 0
    return fix(nodes)


def fix_check(cid):
    with utils.undo_chunk("gusrigCheckerFix"):
        done = _fix_one(cid)
    label = [c[2] for c in CHECKS if c[0] == cid][0]
    utils.info(TOOL, "%s: fixed %d. Running the checks again..." % (label, done))
    cmds.evalDeferred(_w(run))                 # after this click: the list is rebuilt


NOT_IN_FIX_ALL = ("naming_side", "dup_names")       # 5.0.11: renaming isn't 'safe' (follows, mirroring, scripts by name)


def fix_all(*_):
    total = 0
    with utils.undo_chunk("gusrigCheckerFixAll"):
        for c in CHECKS:
            if c[5] and c[0] not in NOT_IN_FIX_ALL and _current(c[0]):
                try:
                    total += _fix_one(c[0])
                except Exception as e:
                    utils.warn(TOOL, "%s: %s" % (c[2], e))
    utils.info(TOOL, "fixed %d item(s) with the safe fixes. Running the checks again..." % total)
    cmds.evalDeferred(_w(run))


def copy_report(*_):
    results = _results.get(_P["p"])
    if not results:
        utils.warn(TOOL, "run the checks first.")
        return
    text = report_text(results)
    try:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        QtWidgets.QApplication.clipboard().setText(text)
        utils.info(TOOL, "report copied to the clipboard.", "info")
    except Exception:
        print(text)
        utils.info(TOOL, "report printed in the Script Editor.", "info")


def build(prefix="p_checker_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Check", help_text="Run checks on the selected hierarchies, or the whole scene when nothing "
               "is selected. Select shows the problems; Fix appears only for safe fixes (never moves skinned "
               "geometry). The ? on each row explains why it matters.")
    ui.main_button("Run checks", _w(run))
    cmds.columnLayout(N("Results"), adjustableColumn=True, rowSpacing=2)
    cmds.text(label="Not run yet.", align="left")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Fix all safe", command=_w(fix_all),
                annotation="Runs every safe fix (one undo), then checks again.")
    cmds.button(label="Copy report", command=_w(copy_report))
    cmds.setParent("..")
    cmds.button(label="Check this scene: full diagnosis (ribbons, follows, labels, skin...)", height=26,
                command=_w(_guard(lambda *_: __import__("gus_rigtool.scene_check", fromlist=["x"]).run())),
                annotation="Reads the whole scene and writes a report to send: problems first, then each ribbon, "
                           "follow, skin, stuck control... Nothing changes.")
    ui.end_section()

    ui.section("Repair", help_text="Finds what Check this scene can fix safely: ribbons whose joints copy their "
               "controls, loops whose right side doesn't mirror, unlabelled joints, missing twins, constraints with "
               "no target, guides at the origin, skins whose weights don't add up to 1, dead utility nodes. Tick, "
               "then Apply: one undo. Nothing moves.")
    ui.main_button("Find repairs", _w(_guard(find_repairs)), "Looks through the whole scene.")
    cmds.columnLayout(N("Repairs"), adjustableColumn=True, rowSpacing=2)
    cmds.text(label="Not looked yet.", align="left")
    cmds.setParent("..")
    cmds.button(label="Apply the ticked repairs", height=26, command=_w(_guard(apply_repairs)))
    ui.end_section()

    ui.section("Checks to run", collapse=True, help_text="Turn checks on or off, and set the skin influence "
               "limit. Save your own sets with the presets at the top.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 80))
    cmds.text(label="Skin influence limit per vertex", align="right")
    cmds.intField(N("Limit"), value=int(s["influence_limit"]), minValue=1, maxValue=16,
                  changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 80))
    cmds.text(label="Joint twist limit (degrees)", align="right")
    cmds.intField(N("TwistLimit"), value=int(s.get("twist_limit", 30)), minValue=1, maxValue=179,
                  changeCommand=_w(_save))
    cmds.setParent("..")
    area = None
    for cid, a, label, sev, _find, fix, _on in CHECKS:
        if a != area:
            cmds.text(label=a, font="boldLabelFont", align="left")
            area = a
        cmds.checkBox(N("On_" + cid), label="%s  (%s%s)" % (label, sev.lower(), ", fix" if fix else ""),
                      value=bool(s["on_" + cid]), changeCommand=_w(_save))
    ui.end_section()
    ui.section("Batch: several files", help_text="Check many scene files in one go with these settings - one "
               "report for all. Optionally publish each file with no FAIL, saved next to it as <name>_publish "
               "(your files are untouched).")
    cmds.button(label="Batch Checker / Publish...", height=26,
                command=lambda *_: __import__("gus_rigtool.tools.batch", fromlist=["x"]).show())
    ui.end_section()


def show():
    ui.open_panel("checker")


SCHEMA = [("influence_limit", "Skin influence limit", "float", None)] + \
    [("on_" + c[0], "Check: " + c[2], "bool", None) for c in CHECKS]
