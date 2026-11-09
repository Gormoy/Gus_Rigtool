"""
Skin weights to / from one readable .json file (Skin tab, 5).

The file:
    {"format": "gus_skin_weights", "version": 2,
     "meshes": {"body_geo": {"points": vertex count, "joints": ["spine_jnt", ...],
                             "joint_positions": {"spine_jnt": [x, y, z], ...},
                             "max_influences": 4, "skin_method": 0,
                             "positions": [[x, y, z], ...]        one per vertex (world, at export),
                             "weights": [[[joint index, weight], ...], ...]   one line per vertex, only > 0}}}

Import matches meshes and joints by name without namespaces (hare:body_geo = body_geo), sets every vertex in one
go, and handles what changed:
  - by vertex number when the mesh has the same number of points, else by closest position (or as you choose);
  - a joint missing from the scene: its weights go to the nearest joint (by where they were) and it's listed;
  - a mesh without skin is bound first (to the joints it needs); a skinned mesh gets the joints it lacks added.
"""

import json
import math
import os

import maya.cmds as cmds

from gus_rigtool.core import utils

from gus_rigtool.core import naming
from gus_rigtool.core.skin_mirror import influences, skin_of

FORMAT = "gus_skin_weights"
VERSION = 2
METHODS = ["auto", "index", "closest"]          # auto: by vertex number if the counts match, else closest
TINY = 1e-5


def _bare(name):
    """'|grp|hare:body_geo' -> 'body_geo'."""
    return naming.short_name(name).split(":")[-1]


def _shape(geo):
    shapes = cmds.listRelatives(geo, shapes=True, noIntermediate=True, fullPath=True) or []
    return shapes[0] if shapes else geo


def _comp_name(geo):
    return "vtx" if cmds.nodeType(_shape(geo)) == "mesh" else "cv"


def point_count(geo):
    shape = _shape(geo)
    if cmds.nodeType(shape) == "mesh":
        return int(cmds.polyEvaluate(shape, vertex=True))
    return len(cmds.ls(shape + ".cv[*]", flatten=True) or [])


def positions(geo):
    """World positions of every vertex / CV."""
    try:
        import maya.api.OpenMaya as om
        if cmds.nodeType(_shape(geo)) == "mesh":
            sel = om.MSelectionList()
            sel.add(_shape(geo))
            pts = om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)
            return [[p.x, p.y, p.z] for p in pts]
    except Exception:                                       # no API (or not a mesh): one command
        pass
    flat = cmds.xform("%s.%s[*]" % (geo, _comp_name(geo)), query=True, worldSpace=True, translation=True) or []
    return [flat[i:i + 3] for i in range(0, len(flat) - 2, 3)]


# ---------------------------------------------------------------------------
# reading / writing all of a skin's weights in one go
# ---------------------------------------------------------------------------

def _api(skin, geo):
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    sel = om.MSelectionList()
    sel.add(skin)
    sel.add(_shape(geo))
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    dag = sel.getDagPath(1)
    comp_fn = om.MFnSingleIndexedComponent()
    kind = om.MFn.kMeshVertComponent if cmds.nodeType(_shape(geo)) == "mesh" else om.MFn.kCurveCVComponent
    comp = comp_fn.create(kind)
    comp_fn.setCompleteData(point_count(geo))
    return om, fn, dag, comp


def get_weights(skin, geo):
    """(joint long names in the skin's order, [[w per joint] per point])."""
    joints = influences(skin)
    count = point_count(geo)
    try:
        _om, fn, dag, comp = _api(skin, geo)
        flat, n = fn.getWeights(dag, comp)
        flat = list(flat)
        return joints, [flat[i * n:(i + 1) * n] for i in range(count)]
    except Exception:                                       # no API: per point (slow, but works)
        rows = []
        cname = _comp_name(geo)
        for i in range(count):
            vals = cmds.skinPercent(skin, "%s.%s[%d]" % (geo, cname, i), query=True, value=True) or []
            rows.append(list(vals) + [0.0] * (len(joints) - len(vals)))
        return joints, rows


def set_weights(skin, geo, rows):
    """rows: [[w per joint, in the skin's influence order] per point]. Every point in one go."""
    joints = influences(skin)
    try:
        om, fn, dag, comp = _api(skin, geo)
        idx = om.MIntArray(list(range(len(joints))))
        flat = om.MDoubleArray([w for r in rows for w in r])
        fn.setWeights(dag, comp, idx, flat, False)
        return
    except Exception:                                       # no API: per point
        pass
    cname = _comp_name(geo)
    for i, r in enumerate(rows):
        cmds.skinPercent(skin, "%s.%s[%d]" % (geo, cname, i), transformValue=list(zip(joints, r)),
                         normalize=False)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def collect(geo):
    skin = skin_of(geo)
    if not skin:
        return None
    joints, rows = get_weights(skin, geo)
    weights = []
    for r in rows:
        weights.append([[i, round(w, 5)] for i, w in enumerate(r) if w > TINY])
    jpos = {}
    for j in joints:
        try:
            jpos[_bare(j)] = [round(v, 4) for v in cmds.xform(j, query=True, worldSpace=True, translation=True)]
        except (RuntimeError, ValueError):
            pass
    return {"points": len(rows), "joints": [_bare(j) for j in joints], "joint_positions": jpos,
            "max_influences": cmds.skinCluster(skin, query=True, maximumInfluences=True),
            "skin_method": cmds.skinCluster(skin, query=True, skinMethod=True),
            "positions": [[round(v, 4) for v in p] for p in positions(geo)], "weights": weights}


def _dump(data):
    """JSON a person can read: the header indented, one line per vertex."""
    out = ['{"format": "%s", "version": %d, "meshes": {' % (FORMAT, VERSION)]
    names = sorted(data)
    for mi, name in enumerate(names):
        m = data[name]
        out.append('  %s: {' % json.dumps(name))
        for key in ("points", "joints", "joint_positions", "max_influences", "skin_method"):
            out.append('    "%s": %s,' % (key, json.dumps(m[key])))
        for key in ("positions", "weights"):
            out.append('    "%s": [' % key)
            rows = m[key]
            out += ["      %s%s" % (json.dumps(r), "," if i < len(rows) - 1 else "") for i, r in enumerate(rows)]
            out.append('    ]%s' % ("," if key == "positions" else ""))
        out.append('  }%s' % ("," if mi < len(names) - 1 else ""))
    out.append("}}")
    return "\n".join(out) + "\n"


def export_file(path, geos):
    """Every skinned mesh of geos into one file. Returns the meshes written."""
    data = {}
    for g in geos:
        got = collect(g)
        if got:
            data[_bare(g)] = got
    if not data:
        raise RuntimeError("none of the selected meshes is skinned.")
    if not path.lower().endswith(".json"):
        path += ".json"
    with open(path, "w") as f:
        f.write(_dump(data))
    return sorted(data), path


def read_file(path):
    with open(path) as f:
        data = json.load(f)
    if data.get("format") != FORMAT:
        raise RuntimeError("%s isn't a Gus_Rigtool skin weights file." % os.path.basename(path))
    return data


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

def scene_meshes():
    out = []
    for s in cmds.ls(type=("mesh", "nurbsCurve"), long=True, noIntermediate=True) or []:
        t = cmds.listRelatives(s, parent=True, fullPath=True)
        if t and t[0] not in out:
            out.append(t[0])
    return out


def guess_mesh(name, meshes=None, selected=None):
    """The scene mesh for a file entry: same name without namespaces (one only), else None."""
    meshes = scene_meshes() if meshes is None else meshes
    same = [m for m in meshes if _bare(m) == _bare(name)]
    if len(same) == 1:
        return same[0]
    if selected and len(selected) == 1:
        return selected[0]
    return None


def find_joint(name):
    bare = _bare(name)
    found = []
    for pattern in (bare, "*:" + bare):                     # the name, then the name in any namespace
        try:
            found += [j for j in cmds.ls(pattern, long=True) or [] if _bare(j) == bare]
        except (RuntimeError, ValueError):
            pass
    found = list(dict.fromkeys(found))
    return found[0] if len(found) == 1 else None


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def map_joints(entry):
    """{file joint index: scene joint} and [(file name, stand-in or None)] for the missing ones."""
    found, missing = {}, []
    for i, n in enumerate(entry["joints"]):
        j = find_joint(n)
        if j:
            found[i] = j
        else:
            missing.append(i)
    pos = entry.get("joint_positions", {})
    from gus_rigtool.core.skin_tools import rig_joints            # the rig's bind joints (not FK / IK helpers)
    pool = list(dict.fromkeys(list(found.values()) + rig_joints())) or (cmds.ls(type="joint", long=True) or [])
    pool_pos = {}
    for j in pool:
        try:
            pool_pos[j] = cmds.xform(j, query=True, worldSpace=True, translation=True)
        except (RuntimeError, ValueError):
            pass
    notes = []
    for i in missing:
        name = entry["joints"][i]
        p = pos.get(name)
        best = min(pool_pos, key=lambda j: _dist(pool_pos[j], p)) if (p and pool_pos) else None
        if best:
            found[i] = best
        notes.append((name, best))
    return found, notes


class Nearest(object):
    """Closest stored point to a position (a grid, so big meshes stay fast)."""

    def __init__(self, points):
        self.points = points
        lo = [min(p[k] for p in points) for k in range(3)]
        hi = [max(p[k] for p in points) for k in range(3)]
        span = max(max(h - l for l, h in zip(lo, hi)), 1e-6)
        self.cell = span / max(1.0, round(len(points) ** (1.0 / 3.0)))
        self.lo = lo
        self.grid = {}
        for i, p in enumerate(points):
            self.grid.setdefault(self._key(p), []).append(i)

    def _key(self, p):
        return tuple(int(math.floor((p[k] - self.lo[k]) / self.cell)) for k in range(3))

    def find(self, p):
        k = self._key(p)
        best, best_d = None, None
        ring = 0
        while True:
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    for dz in range(-ring, ring + 1):
                        if max(abs(dx), abs(dy), abs(dz)) != ring:
                            continue
                        for i in self.grid.get((k[0] + dx, k[1] + dy, k[2] + dz), ()):
                            d = _dist(self.points[i], p)
                            if best_d is None or d < best_d:
                                best, best_d = i, d
            if best is not None and best_d <= ring * self.cell:
                return best
            ring += 1
            if ring > 2000:
                return best


def import_entry(entry, geo, method="auto", bind=True):
    """The file entry's weights on geo. Returns a report line (and raises RuntimeError when it can't)."""
    count = point_count(geo)
    if method == "auto":
        method = "index" if count == entry["points"] else "closest"
    if method == "index" and count != entry["points"]:
        raise RuntimeError("%s has %d points, the file %d: use 'closest position'." % (_bare(geo), count,
                                                                                    entry["points"]))
    jmap, missing = map_joints(entry)
    if not jmap:
        raise RuntimeError("none of its joints are in the scene")
    needed = list(dict.fromkeys(jmap.values()))
    skin = skin_of(geo)
    if not skin:
        if not bind:
            raise RuntimeError("it has no skin (tick 'Bind meshes without a skin')")
        skin = cmds.skinCluster(needed, geo, toSelectedBones=True, maximumInfluences=entry.get("max_influences", 4),
                                skinMethod=entry.get("skin_method", 0), name=_bare(geo) + "_skinCluster")[0]
    have = set(utils.ls(influences(skin), long=True) or [])
    for j in needed:
        if j not in have:
            cmds.skinCluster(skin, edit=True, addInfluence=j, weight=0.0, lockWeights=False)
    joints = utils.ls(influences(skin), long=True) or []
    col = {j: i for i, j in enumerate(joints)}
    if method == "index":
        source = list(range(count))
    else:
        near = Nearest(entry["positions"])
        source = [near.find(p) for p in positions(geo)]
    rows = []
    for s in source:
        r = [0.0] * len(joints)
        for i, w in entry["weights"][s]:
            j = jmap.get(i)
            if j in col:
                r[col[j]] += w
        total = sum(r)
        rows.append([w / total for w in r] if total > 1e-9 else r)
    set_weights(skin, geo, rows)
    line = "%s: %d point(s), %s" % (naming.short_name(geo), count,
                                     "by vertex number" if method == "index" else "by closest position")
    if missing:
        line += "; joints not in the scene: " + ", ".join(
            "%s -> %s" % (n, _bare(b) if b else "dropped") for n, b in missing)
    return line


def import_file(path, plan, method="auto", bind=True):
    """plan: {file mesh name: scene mesh (None: skip)}. Returns (report lines, done count)."""
    data = read_file(path)
    lines, done = [], 0
    for name, entry in sorted(data["meshes"].items()):
        geo = plan.get(name)
        if not geo:
            lines.append("%s: skipped" % name)
            continue
        try:
            lines.append(import_entry(entry, geo, method, bind))
            done += 1
        except RuntimeError as e:
            lines.append("%s: not done - %s" % (name, e))
    return lines, done
