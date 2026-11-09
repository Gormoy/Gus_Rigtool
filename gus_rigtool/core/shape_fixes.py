"""
Corrective shapes ("fixes"): sculpt a fix in a bent pose; it turns on by itself as the joint bends.

    1. Pose the rig (bend the elbow), select the skinned mesh and the joint that bends -> start(): a copy of the
       mesh in this pose to sculpt (the mesh hides meanwhile).
    2. Sculpt the copy (any tool), then apply(): the sculpt becomes a blendShape target in front of the skin
       (worked back through the skinning, so it lands exactly where you sculpted), and a pose reader turns it on:
       1 at the sculpted bend, fading to 0 at rest.
    3. mirror(): the same fix on the other side (the twin joint, the mesh's mirrored points).

The pose reader: the joint's aim (towards its child) in its parent's space, compared with the sculpted aim:
weight 1 when they match, 0 when the joint is back at rest (a cone round the sculpted pose).
Fixes are listed on the blendShape (gusFixes), so they can be re-sculpted, mirrored or deleted.
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core.skin_mirror import influences, skin_of

TOOL = "Fixes"
BS_SUFFIX = "_fixes"
META = "gusFixes"
SCULPT_META = "gusFixSculpt"


# ---------------------------------------------------------------------------
# 4x4 maths (Maya rows: point x matrix)
# ---------------------------------------------------------------------------

def mmul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def pmul(p, m):
    x, y, z = p
    return [x * m[0] + y * m[4] + z * m[8] + m[12], x * m[1] + y * m[5] + z * m[9] + m[13],
            x * m[2] + y * m[6] + z * m[10] + m[14]]


def vmul(v, m):
    x, y, z = v
    return [x * m[0] + y * m[4] + z * m[8], x * m[1] + y * m[5] + z * m[9], x * m[2] + y * m[6] + z * m[10]]


def inverse(m):
    """Inverse of an affine 4x4 (rows)."""
    a = [m[0:3], m[4:7], m[8:11]]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12:
        raise ValueError("a matrix can't be inverted (a scale of 0?).")
    inv = [[(a[1][1] * a[2][2] - a[1][2] * a[2][1]) / det, (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / det,
            (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / det],
           [(a[1][2] * a[2][0] - a[1][0] * a[2][2]) / det, (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / det,
            (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / det],
           [(a[1][0] * a[2][1] - a[1][1] * a[2][0]) / det, (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / det,
            (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / det]]
    t = m[12:15]
    it = [-(t[0] * inv[0][c] + t[1] * inv[1][c] + t[2] * inv[2][c]) for c in range(3)]
    return inv[0] + [0.0] + inv[1] + [0.0] + inv[2] + [0.0] + it + [1.0]


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n > 1e-9 else [1.0, 0.0, 0.0]


def _angle(a, b):
    a, b = _unit(a), _unit(b)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


# ---------------------------------------------------------------------------
# the mesh, its skin
# ---------------------------------------------------------------------------

def _mesh(node):
    if cmds.nodeType(node) == "mesh":
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    return cmds.ls(node, long=True)[0]


def _shape(mesh):
    return [s for s in cmds.listRelatives(mesh, shapes=True, fullPath=True, noIntermediate=True) or []
            if cmds.nodeType(s) == "mesh"][0]


def local_points(mesh):
    """Object-space points (what deformers see)."""
    flat = cmds.xform(mesh + ".vtx[*]", query=True, objectSpace=True, translation=True) or []
    return [flat[i:i + 3] for i in range(0, len(flat) - 2, 3)]


def world_points(mesh):
    flat = cmds.xform(mesh + ".vtx[*]", query=True, worldSpace=True, translation=True) or []
    return [flat[i:i + 3] for i in range(0, len(flat) - 2, 3)]


def set_local_points(mesh, pts):
    """Object-space points onto a mesh, all at once (one by one without the API)."""
    try:
        import maya.api.OpenMaya as om
        sel = om.MSelectionList()
        sel.add(_shape(mesh))
        om.MFnMesh(sel.getDagPath(0)).setPoints(om.MPointArray([om.MPoint(*p) for p in pts]), om.MSpace.kObject)
        return
    except Exception:
        pass
    for i, p in enumerate(pts):
        cmds.xform("%s.vtx[%d]" % (mesh, i), objectSpace=True, translation=tuple(p))


def skin_input_points(mesh, skin):
    """The points going INTO the skin (rest shape plus earlier deformers): read with the skin turned off."""
    env = cmds.getAttr(skin + ".envelope")
    cmds.setAttr(skin + ".envelope", 0.0)
    try:
        return local_points(mesh)
    finally:
        cmds.setAttr(skin + ".envelope", env)


def influence_matrices(skin):
    """[(bindPreMatrix x worldMatrix) per influence, in the skin's influence order]."""
    out = []
    for j in influences(skin):
        plugs = [p for p in (cmds.listConnections(j + ".worldMatrix", plugs=True, source=False, destination=True)
                             or []) if p.split(".")[0].split("|")[-1] == skin.split("|")[-1] and ".matrix[" in p]
        if not plugs:
            raise RuntimeError("can't find how %s feeds %s." % (naming.short_name(j), skin))
        idx = int(plugs[0].split("[")[-1].rstrip("]"))
        bpm = cmds.getAttr("%s.bindPreMatrix[%d]" % (skin, idx))
        out.append(mmul(list(bpm), list(cmds.getAttr(j + ".worldMatrix[0]"))))
    return out


def unskin(mesh, skin, posed_local):
    """The rest-space points that the skin would move onto posed_local (the inverse of linear skinning per
    point: p_rest = p_posed x (sum of w x G x BPM x W x Minv) ^ -1)."""
    from gus_rigtool.core import skin_io
    _joints, rows = skin_io.get_weights(skin, mesh)
    mats = influence_matrices(skin)
    geom = list(cmds.getAttr(skin + ".geomMatrix"))
    minv = inverse(list(cmds.getAttr(mesh + ".worldMatrix[0]")))
    out = []
    for i, p in enumerate(posed_local):
        acc = [0.0] * 16
        for w, m in zip(rows[i], mats):
            if w > 1e-6:
                for k in range(16):
                    acc[k] += w * m[k]
        a = mmul(mmul(geom, acc), minv)
        out.append(pmul(p, inverse(a)))
    return out


# ---------------------------------------------------------------------------
# pose reader
# ---------------------------------------------------------------------------

def aim_axis(joint):
    """The joint's local axis towards its first child (X if it has none)."""
    kids = cmds.listRelatives(joint, children=True, type="joint", fullPath=True) or []
    if kids:
        t = cmds.getAttr(kids[0] + ".translate")[0]
        if sum(abs(x) for x in t) > 1e-6:
            return _unit(list(t))
    return [1.0, 0.0, 0.0]


def aim_now(joint):
    """The joint's aim, in its parent's space, now."""
    return _unit(vmul(aim_axis(joint), list(cmds.getAttr(joint + ".matrix"))))


def aim_rest(joint):
    """The aim at rest (rotate 0: only the joint orient)."""
    jo = [math.radians(v) for v in cmds.getAttr(joint + ".jointOrient")[0]]
    m = _euler_xyz(jo)
    return _unit(vmul(aim_axis(joint), m))


def _euler_xyz(r):
    cx, cy, cz = [math.cos(a) for a in r]
    sx, sy, sz = [math.sin(a) for a in r]
    rx = [1, 0, 0, 0, 0, cx, sx, 0, 0, -sx, cx, 0, 0, 0, 0, 1]
    ry = [cy, 0, -sy, 0, 0, 1, 0, 0, sy, 0, cy, 0, 0, 0, 0, 1]
    rz = [cz, sz, 0, 0, -sz, cz, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    return mmul(mmul(rx, ry), rz)


def make_reader(name, joint, pose_aim, cone):
    """weight = 1 when the joint's aim is the sculpted one, 0 when it's cone degrees away (at rest). Returns
    the output plug."""
    axis = aim_axis(joint)
    vp = cmds.createNode("vectorProduct", name=name + "_aim")
    cmds.setAttr(vp + ".operation", 3)                      # vector x matrix
    cmds.setAttr(vp + ".normalizeOutput", 1)
    cmds.setAttr(vp + ".input1", *axis)
    cmds.connectAttr(joint + ".matrix", vp + ".matrix")
    ab = cmds.createNode("angleBetween", name=name + "_angle")
    cmds.connectAttr(vp + ".output", ab + ".vector1")
    cmds.setAttr(ab + ".vector2", *pose_aim)
    rm = cmds.createNode("remapValue", name=name + "_weight")
    cmds.connectAttr(ab + ".angle", rm + ".inputValue")
    cmds.setAttr(rm + ".inputMin", 0.0)
    cmds.setAttr(rm + ".inputMax", max(1.0, float(cone)))
    cmds.setAttr(rm + ".outputMin", 1.0)
    cmds.setAttr(rm + ".outputMax", 0.0)
    cmds.setAttr(rm + ".value[0].value_Interp", 2)          # smooth
    return rm + ".outValue", [vp, ab, rm]


# ---------------------------------------------------------------------------
# blendShape and the list of fixes
# ---------------------------------------------------------------------------

def blendshape_of(mesh, create=True):
    for n in cmds.listHistory(mesh, pruneDagObjects=True) or []:
        if cmds.nodeType(n) == "blendShape" and cmds.attributeQuery(META, node=n, exists=True):
            return n
    if not create:
        return None
    bs = cmds.blendShape(mesh, frontOfChain=True, name=naming.short_name(mesh) + BS_SUFFIX)[0]
    cmds.addAttr(bs, longName=META, dataType="string")
    cmds.setAttr(bs + "." + META, "{}", type="string")
    return bs


def fixes(bs):
    try:
        return json.loads(cmds.getAttr(bs + "." + META) or "{}")
    except (ValueError, RuntimeError):
        return {}


def _save(bs, data):
    cmds.setAttr(bs + "." + META, json.dumps(data), type="string")


def _free_index(bs):
    used = cmds.getAttr(bs + ".weight", multiIndices=True) or []
    return (max(used) + 1) if used else 0


# ---------------------------------------------------------------------------
# workflow
# ---------------------------------------------------------------------------

def start(mesh=None, joint=None, name=None):
    """A copy of the posed mesh to sculpt. Returns it."""
    sel = cmds.ls(selection=True, long=True) or []
    joint = joint or next((s for s in sel if cmds.nodeType(s) == "joint"), None)
    mesh = mesh or next((s for s in sel if cmds.nodeType(s) != "joint" and
                         cmds.listRelatives(s, shapes=True, type="mesh")), None)
    if not mesh or not joint:
        raise RuntimeError("pose the rig, then select the skinned mesh and the joint that bends (e.g. the elbow).")
    mesh = _mesh(mesh)
    skin = skin_of(mesh)
    if not skin:
        raise RuntimeError("%s has no skin." % naming.short_name(mesh))
    if joint not in influences(skin) and cmds.ls(joint, long=True)[0] not in influences(skin):
        utils.warn(TOOL, "%s isn't in the skin - fine, it only drives the fix." % naming.short_name(joint))
    pose = aim_now(joint)
    cone = _angle(pose, aim_rest(joint))
    if cone < 5:
        raise RuntimeError("bend %s first (it's at rest): the fix is for a pose." % naming.short_name(joint))
    name = name or "%s_%d" % (naming.short_name(joint).replace("_jnt", ""), int(round(cone)))
    copy = cmds.duplicate(mesh, name=name + "_SCULPT")[0]
    copy = cmds.ls(copy, long=True)[0]
    for s in cmds.listRelatives(copy, shapes=True, fullPath=True) or []:
        if cmds.getAttr(s + ".intermediateObject"):
            cmds.delete(s)
    for a in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"):
        try:
            cmds.setAttr(copy + "." + a, lock=False)
        except RuntimeError:
            pass
    try:
        cmds.parent(copy, world=True)
        copy = cmds.ls(copy.split("|")[-1], long=True)[0]
    except RuntimeError:
        pass
    cmds.addAttr(copy, longName=SCULPT_META, dataType="string")
    cmds.setAttr(copy + "." + SCULPT_META, json.dumps({"mesh": mesh, "joint": cmds.ls(joint, long=True)[0],
                                                       "aim": pose, "cone": cone, "name": name}), type="string")
    cmds.setAttr(mesh + ".visibility", False)
    cmds.select(copy, replace=True)
    utils.info(TOOL, "sculpt %s, then Apply (it turns on as %s bends to %d degrees)." % (
        naming.short_name(copy), naming.short_name(joint), int(round(cone))))
    return copy


def apply(sculpt=None):
    """The sculpt becomes a fix on its mesh (re-sculpting an existing fix replaces it). Returns the fix name."""
    sculpt = sculpt or next((s for s in cmds.ls(selection=True, long=True) or []
                             if cmds.attributeQuery(SCULPT_META, node=s, exists=True)), None)
    if not sculpt:
        raise RuntimeError("select the sculpt copy (made by Sculpt fix).")
    info = json.loads(cmds.getAttr(sculpt + "." + SCULPT_META))
    mesh, joint, name = info["mesh"], info["joint"], info["name"]
    skin = skin_of(mesh)
    if not skin:
        raise RuntimeError("%s lost its skin." % naming.short_name(mesh))
    cmds.setAttr(mesh + ".visibility", True)
    minv = inverse(list(cmds.getAttr(mesh + ".worldMatrix[0]")))
    target = [pmul(p, minv) for p in world_points(sculpt)]
    if len(target) != len(local_points(mesh)):
        raise RuntimeError("the sculpt has a different point count (don't add / delete points).")
    with utils.undo_chunk("gusrigFixApply"):
        bs = blendshape_of(mesh)
        data = fixes(bs)
        weight_was = None
        if name in data:                                       # re-sculpt: the old target goes first
            weight_was = data[name]
            remove(mesh, name, keep_reader=True)
            data = fixes(bs)
        base = skin_input_points(mesh, skin)
        rest = unskin(mesh, skin, target)
        tgt = cmds.duplicate(mesh, name=name)[0]
        for s in cmds.listRelatives(tgt, shapes=True, fullPath=True) or []:
            if cmds.getAttr(s + ".intermediateObject"):
                cmds.delete(s)
        orig = local_points(_orig_shape(mesh))
        set_local_points(tgt, [[o[k] + r[k] - b[k] for k in range(3)] for o, b, r in zip(orig, base, rest)])
        index = _free_index(bs)
        cmds.blendShape(bs, edit=True, target=(mesh, index, tgt, 1.0))
        cmds.delete(tgt)
        alias = "%s.weight[%d]" % (bs, index)
        if weight_was and weight_was.get("reader"):
            out_plug = weight_was["reader"][-1] + ".outValue"
            nodes = weight_was["reader"]
        else:
            out_plug, nodes = make_reader(name, joint, info["aim"], info["cone"])
        cmds.connectAttr(out_plug, alias, force=True)
        data[name] = {"index": index, "joint": joint, "aim": info["aim"], "cone": info["cone"], "reader": nodes}
        _save(bs, data)
        cmds.delete(sculpt)
    utils.info(TOOL, "fix '%s' on %s: on at the sculpted bend of %s, off at rest." % (
        name, naming.short_name(mesh), naming.short_name(joint)))
    return name


def _orig_shape(mesh):
    """The mesh's rest shape (the intermediate 'Orig' one), or the mesh itself."""
    for s in cmds.listRelatives(mesh, shapes=True, fullPath=True) or []:
        if cmds.getAttr(s + ".intermediateObject") and not cmds.listConnections(s + ".inMesh", source=True):
            return s
    return _shape(mesh)


def remove(mesh, name, keep_reader=False):
    bs = blendshape_of(mesh, create=False)
    data = fixes(bs) if bs else {}
    if name not in data:
        raise RuntimeError("no fix '%s' on %s." % (name, naming.short_name(mesh)))
    rec = data.pop(name)
    try:
        aliases = cmds.aliasAttr(bs, query=True) or []
        for alias, plug in zip(aliases[0::2], aliases[1::2]):
            if plug == "weight[%d]" % rec["index"]:
                cmds.aliasAttr(bs + "." + alias, remove=True)
    except RuntimeError:
        pass
    try:
        cmds.removeMultiInstance("%s.weight[%d]" % (bs, rec["index"]), b=True)
        cmds.removeMultiInstance("%s.inputTarget[0].inputTargetGroup[%d]" % (bs, rec["index"]), b=True)
    except RuntimeError:
        pass
    if not keep_reader:
        nodes = [n for n in rec.get("reader") or [] if cmds.objExists(n)]
        if nodes:
            cmds.delete(nodes)
    _save(bs, data)
    return rec


def listing(mesh):
    """[(name, joint, sculpted angle, weight now)]."""
    bs = blendshape_of(mesh, create=False)
    if not bs:
        return []
    out = []
    for name, rec in sorted(fixes(bs).items()):
        try:
            w = cmds.getAttr("%s.weight[%d]" % (bs, rec["index"]))
        except (RuntimeError, ValueError):
            w = 0.0
        out.append((name, rec["joint"], rec["cone"], w))
    return out


# ---------------------------------------------------------------------------
# mirror
# ---------------------------------------------------------------------------

def _rest_world(node):
    """A joint chain's world matrix at rest (rotate 0): translate + joint orient, up the parents."""
    m = None
    n = node
    while n:
        t = list(cmds.getAttr(n + ".translate")[0])
        if cmds.nodeType(n) == "joint":
            r = _euler_xyz([math.radians(v) for v in cmds.getAttr(n + ".jointOrient")[0]])
        else:
            r = list(cmds.getAttr(n + ".matrix"))
        local = list(r)
        local[12:15] = t
        m = local if m is None else mmul(m, local)
        n = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
    return m


def mirror_aim(joint, twin, aim, axis=0):
    """The sculpted aim (in joint's parent space) as the twin's: through the world at rest, mirrored across the
    axis (the shared mirror engine)."""
    from gus_rigtool.core import mirror_engine
    p = (cmds.listRelatives(joint, parent=True, fullPath=True) or [None])[0]
    tp = (cmds.listRelatives(twin, parent=True, fullPath=True) or [None])[0]
    pw = _rest_world(p) if p else [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    tw = _rest_world(tp) if tp else [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    world = mirror_engine.reflect_point(vmul(aim, pw), axis)          # a direction: reflect through the origin
    return _unit(vmul(world, inverse(tw)))


def mirror(mesh, name, axis=0):
    """The fix on the other side: mirrored points, the twin joint's reader. Returns the new fix's name."""
    from gus_rigtool.core import joint_labels
    bs = blendshape_of(mesh, create=False)
    data = fixes(bs) if bs else {}
    if name not in data:
        raise RuntimeError("no fix '%s' on %s." % (name, naming.short_name(mesh)))
    rec = data[name]
    twin_name = joint_labels.twin_name(rec["joint"])
    found = cmds.ls(twin_name, long=True) if twin_name else []
    if not found:
        raise RuntimeError("%s has no twin joint by name." % naming.short_name(rec["joint"]))
    twin = found[0]
    new_name = joint_labels.twin_name(name) or (name + "_mirror")
    pts = local_points(_orig_shape(mesh))
    pairs = mirror_map(pts, axis)
    if len(pairs) < len(pts) * 0.9:
        raise RuntimeError("%s isn't symmetric (no mirrored points found)." % naming.short_name(mesh))
    deltas = _target_deltas(bs, rec["index"], len(pts))
    with utils.undo_chunk("gusrigFixMirror"):
        tgt = cmds.duplicate(mesh, name=new_name)[0]
        for s in cmds.listRelatives(tgt, shapes=True, fullPath=True) or []:
            if cmds.getAttr(s + ".intermediateObject"):
                cmds.delete(s)
        new = []
        for i, o in enumerate(pts):
            j = pairs.get(i)
            d = list(deltas[j]) if j is not None else [0.0, 0.0, 0.0]
            d[axis] = -d[axis]
            new.append([o[0] + d[0], o[1] + d[1], o[2] + d[2]])
        set_local_points(tgt, new)
        if new_name in data:
            remove(mesh, new_name)
            data = fixes(bs)
        index = _free_index(bs)
        cmds.blendShape(bs, edit=True, target=(mesh, index, tgt, 1.0))
        cmds.delete(tgt)
        aim = mirror_aim(rec["joint"], twin, rec["aim"], axis)
        out_plug, nodes = make_reader(new_name, twin, aim, rec["cone"])
        cmds.connectAttr(out_plug, "%s.weight[%d]" % (bs, index), force=True)
        data[new_name] = {"index": index, "joint": twin, "aim": aim, "cone": rec["cone"], "reader": nodes}
        _save(bs, data)
    utils.info(TOOL, "fix '%s' mirrored as '%s' (on %s)." % (name, new_name, naming.short_name(twin)))
    return new_name


def mirror_map(pts, axis=0, tolerance=None):
    """{point index: index of its mirror image across the axis} (rest shape, object space)."""
    if not pts:
        return {}
    span = max(max(p[k] for p in pts) - min(p[k] for p in pts) for k in range(3)) or 1.0
    tol = tolerance or span * 0.001
    grid = {}
    for i, p in enumerate(pts):
        grid.setdefault(tuple(int(round(v / tol)) for v in p), []).append(i)
    out = {}
    for i, p in enumerate(pts):
        q = list(p)
        q[axis] = -q[axis]
        k = tuple(int(round(v / tol)) for v in q)
        best, dist = None, None
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                for c in (-1, 0, 1):
                    for j in grid.get((k[0] + a, k[1] + b, k[2] + c), []):
                        d = sum((x - y) ** 2 for x, y in zip(pts[j], q))
                        if dist is None or d < dist:
                            best, dist = j, d
        if best is not None:
            out[i] = best
    return out


def _target_deltas(bs, index, count):
    """The target's offsets per point (blendShape stores only the moved points)."""
    base = "%s.inputTarget[0].inputTargetGroup[%d].inputTargetItem[6000]" % (bs, index)
    comps = cmds.getAttr(base + ".inputComponentsTarget") or []
    offsets = cmds.getAttr(base + ".inputPointsTarget") or []
    out = [[0.0, 0.0, 0.0] for _ in range(count)]
    ids = []
    for c in comps:
        rng = c.split("[")[-1].rstrip("]")
        if ":" in rng:
            a, b = rng.split(":")
            ids += list(range(int(a), int(b) + 1))
        elif rng.isdigit():
            ids.append(int(rng))
    for i, off in zip(ids, offsets):
        if i < count:
            out[i] = list(off[:3])
    return out
