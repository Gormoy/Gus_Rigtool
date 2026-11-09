"""
Skin helpers for the Skin tab: bind, copy, prune, limit influences, remove unused influences,
export / import weights. (Mirror weights is in skin_mirror.)
"""

import json
import os

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core.skin_mirror import influences, skin_of

BIND_METHODS = ["Closest distance", "Closest in hierarchy", "Heat map", "Geodesic voxel"]
SKIN_METHODS = ["Classic linear", "Dual quaternion", "Weight blended"]
SURFACE_ASSOC = ["closestPoint", "rayCast", "closestComponent", "uv"]
INFLUENCE_ASSOC = ["closestJoint", "name", "oneToOne", "label", "closestBone"]
IMPORT_METHODS = ["index", "nearest", "barycentric", "bilinear", "over"]
MANIFEST = "gus_skin_weights.json"


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def _transform(node):
    node = node.split(".")[0]
    if cmds.objectType(node, isAType="shape"):
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    return cmds.ls(node, long=True)[0]


def _has_geo(node):
    return bool(cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True,
                                   type=("mesh", "nurbsCurve", "nurbsSurface")) or [])


def selected_geo():
    out = []
    for s in cmds.ls(selection=True, long=True) or []:
        if cmds.nodeType(s.split(".")[0]) == "joint":
            continue
        t = _transform(s)
        if t not in out and _has_geo(t):
            out.append(t)
    return out


def selected_joints():
    return cmds.ls(selection=True, type="joint", long=True) or []


def rig_joints():
    """The bind joints under skeleton_grp (the ones the builder makes to skin to)."""
    from gus_rigtool.builder import names
    grp = cmds.ls(names.make("C", "skeleton", "grp"), long=True) or []
    if not grp:
        return []
    return cmds.listRelatives(grp[0], allDescendents=True, type="joint", fullPath=True) or []


def _need_skin(geo):
    skin = skin_of(geo)
    if not skin:
        raise RuntimeError("'%s' has no skin." % naming.short_name(geo))
    return skin


# ---------------------------------------------------------------------------
# bind / copy
# ---------------------------------------------------------------------------

def bind(geos=None, joints=None, max_influences=4, bind_method=0, skin_method=0):
    """Skin each geo to joints (the selected ones, else skeleton_grp's). Returns the new skinClusters."""
    geos = geos or selected_geo()
    joints = joints or selected_joints() or rig_joints()
    if not geos:
        raise RuntimeError("select the meshes to skin (and joints, or none for skeleton_grp's joints).")
    if not joints:
        raise RuntimeError("no joints: select some, or build the rig (skeleton_grp).")
    made, skipped = [], []
    with utils.undo_chunk("gusrigBind"):
        try:                                                  # labels first: every mirror pairs left / right
            from gus_rigtool.core import joint_labels
            joint_labels.label(joints)
        except Exception:
            pass
        for g in geos:
            if skin_of(g):
                skipped.append(naming.short_name(g))
                continue
            kw = dict(toSelectedBones=True, maximumInfluences=int(max_influences), obeyMaxInfluences=False,
                      skinMethod=int(skin_method), normalizeWeights=1,
                      name=naming.short_name(g) + "_skinCluster")
            if bind_method == 3:                                  # geodesic voxel: bind first, then voxel weights
                skin = cmds.skinCluster(joints, g, bindMethod=0, **kw)[0]
                try:
                    cmds.geomBind(skin, bindMethod=3, maxInfluences=int(max_influences), falloff=0.2,
                                  geodesicVoxelParams=(256, True))
                except (RuntimeError, AttributeError):
                    utils.warn("Skin", "geodesic voxel failed (GPU / plugin?): closest distance used for %s."
                               % naming.short_name(g))
            else:
                skin = cmds.skinCluster(joints, g, bindMethod=[0, 1, 2][bind_method], **kw)[0]
            made.append(skin)
    if skipped:
        utils.warn("Skin", "already skinned, left as they are: %s." % ", ".join(skipped))
    return made


def copy(source=None, targets=None, surface=0, influence=(0, 1)):
    """Copy the skin of the first selected geo onto the others (binding them first when needed)."""
    if source is None:
        geos = selected_geo()
        if len(geos) < 2:
            raise RuntimeError("select the skinned source, then the meshes to copy to.")
        source, targets = geos[0], geos[1:]
    src_skin = _need_skin(source)
    joints = influences(src_skin)
    max_inf = cmds.skinCluster(src_skin, query=True, maximumInfluences=True)
    method = cmds.skinCluster(src_skin, query=True, skinMethod=True)
    inf_assoc = [INFLUENCE_ASSOC[i] for i in (influence if isinstance(influence, (list, tuple)) else [influence])]
    with utils.undo_chunk("gusrigCopySkin"):
        for t in targets:
            dst = skin_of(t)
            if not dst:
                dst = cmds.skinCluster(joints, t, toSelectedBones=True, maximumInfluences=max_inf,
                                       skinMethod=method, name=naming.short_name(t) + "_skinCluster")[0]
                try:                                       # 5.3.1: the source's normalization (Post stays Post)
                    cmds.setAttr(dst + ".normalizeWeights", cmds.getAttr(src_skin + ".normalizeWeights"))
                except RuntimeError:
                    pass
            cmds.copySkinWeights(sourceSkin=src_skin, destinationSkin=dst, noMirror=True,
                                 surfaceAssociation=SURFACE_ASSOC[surface], influenceAssociation=inf_assoc)
            normalize(dst, t)
    return len(targets)


def normalize(skin, geo):
    """5.3.1: every vertex's weights made to add up to 1 (a Post skin keeps raw sums that don't - copied into an
    Interactive one they pulled vertices to the world origin). Returns the vertices that didn't."""
    bad = bad_sums(skin, geo)
    if bad:
        mode = cmds.getAttr(skin + ".normalizeWeights")
        if mode == 0:
            cmds.setAttr(skin + ".normalizeWeights", 1)
        cmds.skinPercent(skin, geo, normalize=True)
        if mode == 0:
            cmds.setAttr(skin + ".normalizeWeights", 0)
    return len(bad)


def bad_sums(skin, geo, tol=1e-3):
    """Vertex indices whose weights don't add up to 1."""
    _infl, _comp, weights = _weights(skin, geo)
    return [i for i, w in sorted(weights.items()) if abs(sum(w) - 1.0) > tol]


def twice(skin):
    """{joint (long name): [matrix slots]} for joints plugged into the skin more than once (5.3.3: the Hare's hood
    had every cape joint twice - Maya's paint list and ngSkinTools list by name and broke / froze)."""
    slots = {}
    for i in cmds.getAttr(skin + ".matrix", multiIndices=True) or []:
        src = cmds.listConnections("%s.matrix[%d]" % (skin, i), source=True, destination=False) or []
        if src:
            slots.setdefault((cmds.ls(src[0], long=True) or [src[0]])[0], []).append(i)
    return dict((j, idx) for j, idx in slots.items() if len(idx) > 1)


def same_names(skin):
    """{short name: [joints]} for different joints in the skin sharing a short name (5.3.4): Maya's paint list and
    ngSkinTools list influences by name and break."""
    by = {}
    for i in cmds.getAttr(skin + ".matrix", multiIndices=True) or []:
        for src in cmds.listConnections("%s.matrix[%d]" % (skin, i), source=True, destination=False) or []:
            full = (cmds.ls(src, long=True) or [src])[0]
            lst = by.setdefault(full.split("|")[-1], [])
            if full not in lst:
                lst.append(full)
    return dict((k, v) for k, v in by.items() if len(v) > 1)


def add_joints(mesh, joints, hierarchy=True):
    """5.3.4: joints (and, hierarchy, every joint under them) into the mesh's skin - each exactly once, weight 0,
    the ones already in skipped. Maya's Add Influence with chain roots selected passed every joint twice (the
    Hare's cape: each cape joint plugged into the hood's skin twice - painting and ngSkinTools broke).
    Returns (added, already in)."""
    skin = skin_of(mesh)
    if not skin:
        raise RuntimeError("%s has no skin: bind it first." % naming.short_name(mesh))
    want = []
    for j in joints:
        for x in [j] + ((cmds.listRelatives(j, allDescendents=True, type="joint", fullPath=True) or [])[::-1]
                        if hierarchy else []):
            full = (cmds.ls(x, long=True) or [x])[0]
            if cmds.nodeType(full) == "joint" and full not in want:
                want.append(full)
    have = set(cmds.ls(influences(skin), long=True) or [])
    added = []
    with utils.undo_chunk("gusrigAddJoints"):
        for j in want:
            if j in have:
                continue
            cmds.skinCluster(skin, edit=True, addInfluence=j, weight=0.0, lockWeights=False)
            have.add(j)
            added.append(j)
    return added, len(want) - len(added)


def _bpm_differs(skin, a, b, tol=1e-4):
    try:
        ma = cmds.getAttr("%s.bindPreMatrix[%d]" % (skin, a))
        mb = cmds.getAttr("%s.bindPreMatrix[%d]" % (skin, b))
        return any(abs(x - y) > tol for x, y in zip(ma, mb))
    except (RuntimeError, ValueError, TypeError):
        return False


def merge_twice(skin):
    """Each extra slot's weights onto the joint's first slot, the extra slot unplugged (nothing moves when both
    were bound in the same pose). Returns (slots merged, joints whose slots were bound in different poses)."""
    found = twice(skin)
    verts = cmds.getAttr(skin + ".weightList", multiIndices=True) or []
    merged, posed = 0, []
    with utils.undo_chunk("gusrigMergeTwice"):
        for j, idx in found.items():
            keep = idx[0]
            for extra in idx[1:]:
                if _bpm_differs(skin, keep, extra) and j not in posed:
                    posed.append(j)
                for v in verts:
                    we = cmds.getAttr("%s.weightList[%d].weights[%d]" % (skin, v, extra))
                    if we:
                        wk = cmds.getAttr("%s.weightList[%d].weights[%d]" % (skin, v, keep))
                        cmds.setAttr("%s.weightList[%d].weights[%d]" % (skin, v, keep), wk + we)
                    try:
                        cmds.removeMultiInstance("%s.weightList[%d].weights[%d]" % (skin, v, extra), b=True)
                    except RuntimeError:
                        pass
                for a in ("matrix", "bindPreMatrix", "lockWeights", "influenceColor"):
                    try:
                        cmds.removeMultiInstance("%s.%s[%d]" % (skin, a, extra), b=True)
                    except RuntimeError:
                        pass
                merged += 1
    return merged, posed


# ---------------------------------------------------------------------------
# cleaning weights
# ---------------------------------------------------------------------------

def prune(geos=None, below=0.01):
    geos = geos or selected_geo()
    if not geos:
        raise RuntimeError("select skinned meshes.")
    with utils.undo_chunk("gusrigPrune"):
        for g in geos:
            skin = _need_skin(g)
            cmds.skinPercent(skin, g, pruneWeights=float(below), normalize=True)
    return len(geos)


def _api_weights(skin, geo, count, n_infl):
    """Every vertex's weights in one call (OpenMaya); None when that isn't possible."""
    try:
        import maya.api.OpenMaya as om
        import maya.api.OpenMayaAnim as oma
        sel = om.MSelectionList()
        sel.add(skin)
        sel.add(geo)
        fn = oma.MFnSkinCluster(sel.getDependNode(0))
        path = sel.getDagPath(1)
        path.extendToShape()
        comp_fn = om.MFnSingleIndexedComponent()
        comp = comp_fn.create(om.MFn.kMeshVertComponent if path.apiType() == om.MFn.kMesh
                              else om.MFn.kCurveCVComponent)
        comp_fn.setCompleteData(count)
        flat, n = fn.getWeights(path, comp)
        flat = [float(x) for x in flat]
        if int(n) != n_infl or len(flat) != count * n_infl:
            return None
        return {i: flat[i * n_infl:(i + 1) * n_infl] for i in range(count)}
    except Exception:
        return None


def _weights(skin, geo):
    """(influences, component name, {vertex index: [weight per influence]})."""
    infl = cmds.skinCluster(skin, query=True, influence=True) or []
    is_mesh = bool(cmds.listRelatives(geo, shapes=True, type="mesh"))
    comp = "vtx" if is_mesh else "cv"
    count = int(cmds.polyEvaluate(geo, vertex=True)) if is_mesh else len(cmds.ls(geo + ".cv[*]", flatten=True) or [])
    out = _api_weights(skin, geo, count, len(infl))
    if out is None:                                       # slower, but works everywhere
        out = {i: cmds.skinPercent(skin, "%s.%s[%d]" % (geo, comp, i), query=True, value=True) or []
               for i in range(count)}
    return infl, comp, out


def limit_influences(geos=None, limit=4):
    """Keep only the 'limit' biggest weights on every vertex (the rest is shared out). Returns vertices fixed."""
    geos = geos or selected_geo()
    if not geos:
        raise RuntimeError("select skinned meshes.")
    fixed = 0
    with utils.undo_chunk("gusrigLimitInfluences"):
        for g in geos:
            skin = _need_skin(g)
            infl, comp, weights = _weights(skin, g)
            for i, w in weights.items():
                used = [k for k, v in enumerate(w) if v > 1e-6]
                if len(used) <= limit:
                    continue
                keep = sorted(used, key=lambda k: -w[k])[:limit]
                total = sum(w[k] for k in keep) or 1.0
                cmds.skinPercent(skin, "%s.%s[%d]" % (g, comp, i), normalize=False,
                                 transformValue=[(infl[k], (w[k] / total) if k in keep else 0.0) for k in used])
                fixed += 1
            cmds.skinCluster(skin, edit=True, maximumInfluences=int(limit), obeyMaxInfluences=True)
            try:
                cmds.skinCluster(skin, edit=True, forceNormalizeWeights=True)
            except RuntimeError:
                pass
    return fixed


def unused_influences(skin):
    """Influences of skin that carry no weight at all."""
    infl = cmds.skinCluster(skin, query=True, influence=True) or []
    weighted = set(cmds.skinCluster(skin, query=True, weightedInfluence=True) or [])
    return [i for i in infl if i not in weighted]


def remove_unused(geos=None):
    geos = geos or selected_geo()
    if not geos:
        raise RuntimeError("select skinned meshes.")
    removed = 0
    with utils.undo_chunk("gusrigRemoveUnused"):
        for g in geos:
            skin = _need_skin(g)
            unused = unused_influences(skin)
            keep = len(cmds.skinCluster(skin, query=True, influence=True) or []) - len(unused)
            for j in unused:
                if keep < 1:
                    break
                cmds.skinCluster(skin, edit=True, removeInfluence=j)
                removed += 1
    return removed


# ---------------------------------------------------------------------------
# export / import
# ---------------------------------------------------------------------------

def _read_manifest(folder):
    path = os.path.join(folder, MANIFEST)
    if os.path.isfile(path):
        with open(path) as f:
            try:
                return json.load(f)
            except ValueError:
                return {}
    return {}


def import_weights(folder, geos=None, method="index"):
    """Exports from before 3.12 (a folder of .xml files). Weights back on the selected meshes (or every mesh in the folder found in the scene).
    A mesh without a skin is bound to the joints it had. Returns (done, notes)."""
    data = _read_manifest(folder)
    if not data:
        raise RuntimeError("no Gus_Rigtool skin weights in that folder (%s missing)." % MANIFEST)
    names_ = [naming.short_name(g) for g in (geos or selected_geo())] or sorted(data)
    done, notes = [], []
    with utils.undo_chunk("gusrigImportWeights"):
        for short in names_:
            entry = data.get(short)
            if not entry:
                notes.append("%s: not in the folder" % short)
                continue
            found = cmds.ls(short, long=True) or []
            if len(found) != 1:
                notes.append("%s: %s in the scene" % (short, "not" if not found else "more than one"))
                continue
            geo = found[0]
            skin = skin_of(geo)
            if not skin:
                joints = [j for j in entry["influences"] if len(cmds.ls(j) or []) == 1]
                if not joints:
                    notes.append("%s: none of its joints are in the scene" % short)
                    continue
                if len(joints) < len(entry["influences"]):
                    notes.append("%s: %d joint(s) missing" % (short, len(entry["influences"]) - len(joints)))
                skin = cmds.skinCluster(joints, geo, toSelectedBones=True,
                                        maximumInfluences=entry.get("max_influences", 4),
                                        skinMethod=entry.get("method", 0), name=short + "_skinCluster")[0]
            cmds.deformerWeights(entry["file"], im=True, deformer=skin, method=method, path=folder)
            try:
                cmds.skinCluster(skin, edit=True, forceNormalizeWeights=True)
            except RuntimeError:
                pass
            done.append(short)
    return done, notes


# ---------------------------------------------------------------------------
# vertex weights (Skin tab, 6)
# ---------------------------------------------------------------------------

_clip = {"weights": None, "from": ""}


def selected_points():
    """Selected vertices / CVs, one per item."""
    return [c for c in cmds.ls(selection=True, flatten=True) or [] if ".vtx[" in c or ".cv[" in c]


def _skin_of_points(points):
    geos = []
    for p in points:
        g = _transform(p)
        if g not in geos:
            geos.append(g)
    out = {}
    for g in geos:
        skin = skin_of(g)
        if not skin:
            raise RuntimeError("%s has no skin." % naming.short_name(g))
        out[g] = skin
    return out


def point_weights(skin, point):
    names = cmds.skinPercent(skin, point, query=True, transform=None) or []
    values = cmds.skinPercent(skin, point, query=True, value=True) or []
    return {n: float(v) for n, v in zip(names, values) if v > 1e-6}


def copy_point_weights(points=None):
    """Copy the weights of the selected vertex (several: their average). Returns the weights."""
    points = points or selected_points()
    if not points:
        raise RuntimeError("select the vertex (or vertices: their average) to copy from.")
    skins = _skin_of_points(points)
    total = {}
    for p in points:
        for j, v in point_weights(skins[_transform(p)], p).items():
            total[j] = total.get(j, 0.0) + v
    s = sum(total.values()) or 1.0
    _clip["weights"] = {j: v / s for j, v in total.items()}
    _clip["from"] = "%d point(s)" % len(points)
    return _clip["weights"]


def paste_point_weights(points=None):
    """The copied weights on the selected vertices (joints the skin doesn't have are skipped, the rest
    shared out). Returns how many points."""
    if not _clip["weights"]:
        raise RuntimeError("copy a vertex's weights first.")
    points = points or selected_points()
    if not points:
        raise RuntimeError("select the vertices to paste on.")
    skins = _skin_of_points(points)
    done, missing = 0, set()
    with utils.undo_chunk("gusrigPasteWeights"):
        for g, skin in skins.items():
            have = {naming.short_name(i) for i in cmds.skinCluster(skin, query=True, influence=True) or []}
            w = {j: v for j, v in _clip["weights"].items() if naming.short_name(j) in have}
            missing |= set(_clip["weights"]) - set(w)
            s = sum(w.values())
            if s <= 0:
                continue
            mine = [p for p in points if _transform(p) == g]
            cmds.skinPercent(skin, mine, transformValue=[(j, v / s) for j, v in w.items()], normalize=True)
            done += len(mine)
    if missing:
        utils.warn("Skin", "not in the skin, skipped: %s" % ", ".join(sorted(naming.short_name(m) for m in missing)))
    return done


def hammer(points=None):
    """Maya's Hammer: the selected vertices get the weights of their neighbours."""
    points = points or selected_points()
    if not points:
        raise RuntimeError("select the vertices to hammer.")
    import maya.mel as mel
    cmds.select(points, replace=True)
    mel.eval("weightHammerVerts")
    return len(points)


def _neighbours(point):
    edges = cmds.polyListComponentConversion(point, toEdge=True) or []
    verts = utils.ls(cmds.polyListComponentConversion(edges, toVertex=True) or [], flatten=True) or []
    return [v for v in verts if v != point]


def smooth(points=None, strength=0.5):
    """Each selected vertex moves its weights 'strength' of the way to its neighbours' average."""
    points = points or selected_points()
    if not points:
        raise RuntimeError("select the vertices to smooth.")
    skins = _skin_of_points(points)
    new = {}
    for p in points:
        skin = skins[_transform(p)]
        mine = point_weights(skin, p)
        nb = _neighbours(p) if ".vtx[" in p else []
        if not nb:
            continue
        avg = {}
        for n in nb:
            for j, v in point_weights(skin, n).items():
                avg[j] = avg.get(j, 0.0) + v / len(nb)
        keys = set(mine) | set(avg)
        w = {j: mine.get(j, 0.0) * (1 - strength) + avg.get(j, 0.0) * strength for j in keys}
        s = sum(w.values()) or 1.0
        new[p] = (skin, {j: v / s for j, v in w.items() if v / s > 1e-5})
    with utils.undo_chunk("gusrigSmoothWeights"):
        for p, (skin, w) in new.items():
            cmds.skinPercent(skin, p, transformValue=list(w.items()), normalize=True)
    return len(new)


def move_weights(src, dst, points=None, geos=None):
    """Every weight of joint src goes to joint dst, on the selected vertices (or whole selected meshes).
    dst is added to the skin when it isn't in it. Returns how many meshes."""
    points = points if points is not None else selected_points()
    geos = geos or ([] if points else selected_geo())
    if not points and not geos:
        raise RuntimeError("select vertices or skinned meshes, and the two joints (FROM first, then TO).")
    jobs = {}
    if points:
        for g, skin in _skin_of_points(points).items():
            jobs[g] = (skin, [p for p in points if _transform(p) == g])
    for g in geos:
        skin = skin_of(g)
        if not skin:
            raise RuntimeError("%s has no skin." % naming.short_name(g))
        jobs[g] = (skin, [g + (".vtx[*]" if cmds.listRelatives(g, shapes=True, type="mesh") else ".cv[*]")])
    with utils.undo_chunk("gusrigMoveWeights"):
        for g, (skin, comps) in jobs.items():
            have = [naming.short_name(i) for i in cmds.skinCluster(skin, query=True, influence=True) or []]
            if naming.short_name(src) not in have:
                raise RuntimeError("%s isn't in %s's skin." % (naming.short_name(src), naming.short_name(g)))
            if naming.short_name(dst) not in have:
                cmds.skinCluster(skin, edit=True, addInfluence=dst, weight=0.0)
            cmds.skinPercent(skin, comps, transformMoveWeights=[src, dst])
    return len(jobs)


# ---------------------------------------------------------------------------
# weight list (4.4.0): the selected vertices' weights per joint, type a value, average, lock
# ---------------------------------------------------------------------------

def weight_table(points=None):
    """[(joint, average weight over the points, locked)] of the selected vertices (one skin), biggest first;
    joints with no weight on them are left out."""
    points = points or selected_points()
    if not points:
        return []
    skins = _skin_of_points(points)
    if len(skins) != 1:
        raise RuntimeError("select vertices on one skinned mesh.")
    skin = list(skins.values())[0]
    total = {}
    for p in points:
        for j, v in point_weights(skin, p).items():
            total[j] = total.get(j, 0.0) + v
    n = float(len(points))
    out = []
    for j, v in total.items():
        try:
            locked = bool(cmds.getAttr(j + ".liw"))
        except (RuntimeError, ValueError):
            locked = False
        out.append((j, v / n, locked))
    return sorted(out, key=lambda r: -r[1])


def set_joint_weight(joint, value, points=None):
    """Every selected vertex gets value on this joint; the other (unlocked) joints share the rest, keeping their
    proportions (Maya's normalise). Returns how many points."""
    points = points or selected_points()
    if not points:
        raise RuntimeError("select the vertices.")
    value = max(0.0, min(1.0, float(value)))
    skins = _skin_of_points(points)
    done = 0
    with utils.undo_chunk("gusrigSetWeight"):
        for g, skin in skins.items():
            have = {naming.short_name(i) for i in cmds.skinCluster(skin, query=True, influence=True) or []}
            if naming.short_name(joint) not in have:
                raise RuntimeError("%s isn't in %s's skin." % (naming.short_name(joint), naming.short_name(g)))
            mine = [p for p in points if _transform(p) == g]
            cmds.skinPercent(skin, mine, transformValue=[(joint, value)], normalize=True)
            done += len(mine)
    return done


def average_points(points=None):
    """Every selected vertex gets the average of the selection's weights (a smooth patch). Returns the count."""
    points = points or selected_points()
    if not points or len(points) < 2:
        raise RuntimeError("select two or more vertices to average.")
    copy_point_weights(points)
    return paste_point_weights(points)


def lock_joints(joints, locked=True):
    """Lock / unlock joints' weights (paint and normalise leave locked ones alone). Returns the count."""
    n = 0
    for j in joints:
        try:
            cmds.setAttr(j + ".liw", bool(locked))
            n += 1
        except (RuntimeError, ValueError):
            pass
    return n
