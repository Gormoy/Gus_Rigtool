"""
Head squash and stretch (5.6.11): a lattice round the head, AFTER the skin, bent and squashed by Maya's squash and
bend deformers, driven by Head_squash_ctrl above the head.

    Head_squash_ctrl   up / down: stretch / squash (the volume kept); left-right / front-back: the top bends
                       sliders: squash, bulge, bend (how much)
    on / off           Visibility_ctrl.Head_Squash (or the control's own 'squash_on'): off, nothing calculates

The lattice deforms the meshes only (the face comes out squashed once - the face ribbons aren't in it, or the face
would squash twice: ribbons -> face joints -> skin, then the lattice again) plus the face controls' curves, so they
stay on the squashed face. Past the lattice the effect fades out (ears, neck): the ears ride along.

    from gus_rigtool.core import head_squash as HS
    HS.make("Head_ctrl", ["Geo_Hare_07:Hare_Body", "L_Eye_geo", "R_Eye_geo"])
"""

import json
import math

import re

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

TOOL = "Head squash"
CTRL = "Head_squash_ctrl"
GRP = "Head_squash_grp"
META = "gusHeadSquash"
SWITCH = "Head_Squash"


def _short(n):
    return naming.short_name(n)


def _long(n):
    got = cmds.ls(n, long=True) if n else []
    return got[0] if len(got) == 1 else None


def find():
    c = _long(CTRL)
    return c if c and cmds.attributeQuery(META, node=c, exists=True) else None


def read():
    c = find()
    return json.loads(cmds.getAttr(c + "." + META) or "{}") if c else {}


NOT_FACE = r"(^|_)ears?(_|$|\d)|^(l_|r_|c_)?eyes?_ctrl$|^eyes?_(aim|target)"


def face_controls():
    """The face's controls (by name: mouth, lids, brows...) - not the ears (they ride the fade), not the eye aim
    targets (out in front), not the group controls / pose sliders / the squash's own (5.6.13: they stretched the
    Hare's box to 466 x 246)."""
    import re
    from gus_rigtool.core import on_top
    out = []
    for c in on_top.controls():
        n = _short(c).lower()
        if not on_top.is_face(c) or n == CTRL.lower() or re.search(NOT_FACE, n):
            continue
        if any(cmds.attributeQuery(a, node=c, exists=True) for a in ("gusGroupCtrl", "gusFacePoses", META)):
            continue
        out.append(c)
    return out


EAR = r"(^|_)ears?(_|$|\d)"


RIDES = ("tweak", "settings", "_fol_", "ribbon")       # ride the ear already - never follow on their own


def _ear_ctrls():
    import re
    from gus_rigtool.core import on_top
    return [c for c in on_top.controls() if re.search(EAR, _short(c).lower())]


def _side(c):
    n = _short(c).lower()
    for pre in ("l_", "r_", "c_"):
        if n.startswith(pre):
            return pre[0]
    x = cmds.xform(c, query=True, worldSpace=True, translation=True)[0]
    return "l" if x > 1e-3 else "r" if x < -1e-3 else "c"


def ear_units():
    """5.6.16: what follows the squash for each ear - [(the node to wrap, kind)]:
    'group': the deepest group holding all that side's ear controls, when only ear controls are under it (the
    Hare's L_Ear_ctrls_grp) - the whole ear rig (FK, IK, tweaks, settings) rides as one, nothing twice;
    'root': else each FK / IK top control (not the tweaks or the settings: they ride the ear). 5.6.15 took every
    ear control as a top - 26 on the Hare."""
    import re
    from gus_rigtool.core import on_top
    ears = _ear_ctrls()
    every = on_top.controls()
    out = []
    by_side = {}
    for c in ears:
        by_side.setdefault(_side(c), []).append(c)
    for side, cs in sorted(by_side.items()):
        parts = [c.split("|") for c in cs]
        common = []
        for level in zip(*parts):
            if len(set(level)) != 1:
                break
            common.append(level[0])
        anc = "|".join(common)
        if anc and anc not in cs and anc not in every:       # a group, not a control (not the head itself)
            under = [c for c in every if c.startswith(anc + "|")]
            if under and all(re.search(EAR, _short(c).lower()) and _side(c) == side for c in under):
                out.append((anc, "group"))
                continue
        tops = [c for c in cs if not any(w in _short(c).lower() for w in RIDES)]
        out += [(c, "root") for c in tops if not any(c.startswith(o + "|") for o in tops)]
    return out


def ear_roots():
    """(5.6.15 name) the nodes that follow the squash for the ears."""
    return [n for n, _k in ear_units()]


def _ear_weights(mesh, comps):
    """[weight of each member vertex on the ear joints] (by the mesh's skin), or None."""
    import re
    skins = cmds.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type="skinCluster")
    if not skins or not comps:
        return None
    flat = cmds.ls(comps, flatten=True) or []
    total = [0.0] * len(flat)
    for j in cmds.skinCluster(skins[0], query=True, influence=True) or []:
        if not re.search(EAR, _short(j).lower()):
            continue
        vals = cmds.skinPercent(skins[0], flat, transform=j, query=True) or []
        vals = vals if isinstance(vals, list) else [vals]
        for i, v in enumerate(vals[:len(flat)]):
            total[i] += v
    return flat, total


def _ear_riders(grp, head, made):
    """Each ear unit follows a point riding the squashed head at its base: a small plane (it goes in the lattice), a
    follicle on it (connected after the lattice is made - _connect_riders), and a group following it (and the
    head's scale): for an ear group, a new group INSIDE it holding all it held (it works even when the ear group is
    held by a constraint); for a single control, a group above its top group. Returns [ear records], [plane
    transforms]."""
    from gus_rigtool.core import spaces
    out, planes = [], []
    for node, kind in ear_units():
        name = _short(node)[:-5] if _short(node).endswith("_ctrl") else _short(node)
        p = cmds.xform(node, query=True, worldSpace=True, translation=True) if kind == "root" else \
            _base_of(node)
        plane = cmds.nurbsPlane(name=name + "_squash_srf", axis=(0, 1, 0), width=1.0, lengthRatio=1.0,
                                constructionHistory=False)[0]
        made.append(plane)
        cmds.setAttr(plane + ".translate", *p, type="double3")
        plane = cmds.ls(cmds.parent(plane, grp)[0], long=True)[0]
        cmds.setAttr(plane + ".visibility", 0)
        fs = cmds.createNode("follicle", name=name + "_squash_folShape", skipSelect=True)
        ft = cmds.listRelatives(fs, parent=True, fullPath=True)[0]
        made.append(ft)
        cmds.setAttr(fs + ".parameterU", 0.5)
        cmds.setAttr(fs + ".parameterV", 0.5)
        cmds.connectAttr(fs + ".outTranslate", ft + ".translate")
        cmds.connectAttr(fs + ".outRotate", ft + ".rotate")
        cmds.setAttr(ft + ".inheritsTransform", 0)
        ft = cmds.ls(cmds.parent(ft, grp)[0], long=True)[0]
        cmds.setAttr(ft + ".visibility", 0)
        rec = {"ctrl": _short(node), "kind": kind, "plane": _short(plane), "follicle": _short(ft)}
        if kind == "group":
            g = cmds.createNode("transform", name=name + "_squash_follow", parent=node, skipSelect=True)
            g = cmds.ls(g, long=True)[0]
            kids = [k for k in cmds.listRelatives(node, children=True, type="transform", fullPath=True) or []
                    if k != g and "constraint" not in cmds.nodeType(k).lower()]
            for k in kids:
                spaces._parent_keeping(k, g)
            rec.update({"group": _short(g), "parent": _short(node), "children": [_short(k) for k in kids]})
        else:
            piece = spaces.piece_of(node)
            parent = (cmds.listRelatives(piece, parent=True, fullPath=True) or [None])[0]
            g = cmds.createNode("transform", name=name + "_squash_follow", parent=parent, skipSelect=True) \
                if parent else cmds.createNode("transform", name=name + "_squash_follow", skipSelect=True)
            g = cmds.ls(g, long=True)[0]
            cmds.xform(g, worldSpace=True, matrix=cmds.xform(piece, query=True, worldSpace=True, matrix=True))
            spaces._parent_keeping(piece, g)
            rec.update({"group": _short(g), "piece": _short(piece)})
        made.append(g)
        out.append(rec)
        planes.append(plane)
    return out, planes


def _held_from_outside(unit):
    """5.6.18: nodes inside an ear unit held by a constraint to something that isn't the ear (the Hare's
    L_Ear_01_FK_zero <- Head_ctrl): they ignore the follow group above them, so the FK chain - and the result
    joints, tweaks and ear joints after it - never rode the squash. The top-most only (what's under one rides
    with it); held by ear pieces (tweaks <- result joints) don't count - they follow those."""
    import re
    out = []
    nodes = cmds.listRelatives(unit, allDescendents=True, type="transform", fullPath=True) or []
    for n in sorted(nodes, key=lambda x: x.count("|")):
        if "constraint" in cmds.nodeType(n).lower() or any(n.startswith(o + "|") for o in out):
            continue
        for con in set(cmds.listConnections(n, source=True, destination=False, type="constraint") or []):
            tg = [t for t in set(cmds.listConnections(con + ".target", source=True, destination=False) or [])
                  if _short(t) not in (_short(con), _short(n))]
            if any(not re.search(EAR, _short(t).lower()) and not (_long(t) or "").startswith(unit + "|")
                   for t in tg):
                out.append(n)
                break
    return out


def _m4(flat):
    return [list(flat[i * 4:i * 4 + 4]) for i in range(4)]


def _mul4(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _inv4(m):
    a = [list(r) + [1.0 if i == j else 0.0 for j in range(4)] for i, r in enumerate(m)]
    for c in range(4):
        piv = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        d = a[c][c] or 1e-12
        a[c] = [v / d for v in a[c]]
        for r in range(4):
            if r != c and a[r][c]:
                f = a[r][c]
                a[r] = [v - f * w for v, w in zip(a[r], a[c])]
    return [row[4:] for row in a]


def _ear_deltas(ears, head, made):
    """Under each held node, a group carrying only the squash's movement at the ear's base (worked out from the
    point it rides and the head - the head moving or the rig scaled change nothing; at rest it's nothing):
        delta = node . head^-1 . C . point . node^-1,   C = head(rest) . point(rest)^-1"""
    for e in ears:
        unit = _long(e.get("group")) if e.get("kind") == "group" else _long(e.get("piece"))
        ft = _long(e.get("follicle"))
        if not unit or not ft:
            continue
        deltas = []
        for n in _held_from_outside(unit):
            g = cmds.createNode("transform", name=_short(n) + "_squash_delta", parent=n, skipSelect=True)
            g = cmds.ls(g, long=True)[0] if len(cmds.ls(g) or []) == 1 else n + "|" + _short(g)
            for k in cmds.listRelatives(n, children=True, type="transform", fullPath=True) or []:
                if k != g and "constraint" not in cmds.nodeType(k).lower():
                    cmds.parent(k, g, relative=True)
            g = cmds.ls(g, long=True)[0] if len(cmds.ls(g) or []) == 1 else g
            c = _mul4(_m4(cmds.xform(head, query=True, worldSpace=True, matrix=True)),
                      _inv4(_m4(cmds.xform(ft, query=True, worldSpace=True, matrix=True))))
            mm = cmds.createNode("multMatrix", name=_short(n) + "_squash_delta_mm", skipSelect=True)
            dm = cmds.createNode("decomposeMatrix", name=_short(n) + "_squash_delta_dm", skipSelect=True)
            cmds.connectAttr(n + ".worldMatrix[0]", mm + ".matrixIn[0]")
            cmds.connectAttr(head + ".worldInverseMatrix[0]", mm + ".matrixIn[1]")
            cmds.setAttr(mm + ".matrixIn[2]", [v for row in c for v in row], type="matrix")
            cmds.connectAttr(ft + ".worldMatrix[0]", mm + ".matrixIn[3]")
            cmds.connectAttr(n + ".worldInverseMatrix[0]", mm + ".matrixIn[4]")
            cmds.connectAttr(mm + ".matrixSum", dm + ".inputMatrix")
            for a, b in (("outputTranslate", "translate"), ("outputRotate", "rotate"), ("outputScale", "scale"),
                         ("outputShear", "shear")):
                cmds.connectAttr(dm + "." + a, g + "." + b)
            made.extend([mm, dm])
            deltas.append([n, g])
        e["deltas"] = deltas


def _with_ears(centre, size):
    """5.6.17: the box grown to take in each ear's base (a tenth of the box past it) - their riding points must
    be inside the lattice, or they never move (the Hare's ear bases were above it)."""
    lo = [centre[i] - size[i] / 2.0 for i in range(3)]
    hi = [centre[i] + size[i] / 2.0 for i in range(3)]
    pad = size[1] * 0.1
    low = {}                                    # one base per side: the lowest (a root higher up rides that one)
    for node, kind in ear_units():
        p = _base_of(node) if kind == "group" else cmds.xform(node, query=True, worldSpace=True, translation=True)
        side = _side(node)
        if side not in low or p[1] < low[side][1]:
            low[side] = p
    for p in low.values():
        for i in range(3):
            lo[i] = min(lo[i], p[i] - pad)
            hi[i] = max(hi[i], p[i] + pad)
    return [(lo[i] + hi[i]) / 2.0 for i in range(3)], [hi[i] - lo[i] for i in range(3)]


def _base_of(group):
    """The lowest point of the controls in an ear group (the ear's base, where it meets the head)."""
    from gus_rigtool.core import on_top
    ps = [cmds.xform(c, query=True, worldSpace=True, translation=True) for c in on_top.controls()
          if c.startswith(group + "|")]
    if not ps:
        return cmds.xform(group, query=True, worldSpace=True, translation=True)
    return min(ps, key=lambda p: p[1])


def _connect_riders(ears, head):
    """After the lattice: each follicle reads the plane you'd see (the squashed one - 5.6.15 read the copy Maya
    keeps of the plane as it was, so the points never moved), each follow group follows its follicle."""
    for e in ears:
        plane = _long(e["plane"])
        ft = _long(e["follicle"])
        g = _long(e["group"])
        shape = [x for x in cmds.listRelatives(plane, shapes=True, fullPath=True) or []
                 if not cmds.getAttr(x + ".intermediateObject")][0]
        fs = cmds.listRelatives(ft, shapes=True, fullPath=True)[0]
        cmds.connectAttr(shape + ".local", fs + ".inputSurface", force=True)
        cmds.connectAttr(shape + ".worldMatrix[0]", fs + ".inputWorldMatrix", force=True)
        dm = cmds.createNode("decomposeMatrix", name=e["follicle"] + "_scale", skipSelect=True)
        cmds.connectAttr(head + ".worldMatrix[0]", dm + ".inputMatrix")      # 5.6.17: the point grows with the rig
        cmds.connectAttr(dm + ".outputScale", ft + ".scale")                # (it didn't: the ears drifted at x2)
        cmds.parentConstraint(ft, g, maintainOffset=True)
        cmds.scaleConstraint(head, g, maintainOffset=True)


def _middle(values, lo=0.05, hi=0.95):
    v = sorted(values)
    if not v:
        return 0.0, 0.0
    i, j = int(round(lo * (len(v) - 1))), int(round(hi * (len(v) - 1)))
    return v[i], v[j]


def _curves(ctrls):
    out = []
    for c in ctrls:
        out += [s for s in cmds.listRelatives(c, shapes=True, type="nurbsCurve", fullPath=True) or []
                if not cmds.getAttr(s + ".intermediateObject")]
    return out


def region(head, face=None):
    """(centre, size): the box the lattice fills - round the face controls (the mouth, lids, brows), down a little
    below the mouth, up well above the brows (the skull); else round the head control."""
    ps = [cmds.xform(c, query=True, worldSpace=True, translation=True) for c in (face or [])]
    if len(ps) < 3:
        b = cmds.exactWorldBoundingBox(head)
        lo, hi = [b[0], b[1], b[2]], [b[3], b[4], b[5]]
    else:                                   # the middle 90% on each axis: a few odd controls can't stretch it
        lo, hi = [], []
        for i in range(3):
            a, b = _middle([p[i] for p in ps])
            lo.append(a)
            hi.append(b)
    h = max(hi[1] - lo[1], 1e-3)
    w = max(hi[0] - lo[0], h * 0.5)
    d = max(hi[2] - lo[2], h * 0.5)
    lo = [lo[0] - w * 0.35, lo[1] - h * 0.2, lo[2] - d * 1.0]
    hi = [hi[0] + w * 0.35, hi[1] + h * 0.9, hi[2] + d * 0.35]
    return [(lo[i] + hi[i]) / 2.0 for i in range(3)], [hi[i] - lo[i] for i in range(3)]


def _inside(ctrls, centre, size, fade):
    out = []
    for c in ctrls:
        p = cmds.xform(c, query=True, worldSpace=True, translation=True)
        if all(abs(p[i] - centre[i]) <= size[i] / 2.0 + fade for i in range(3)):
            out.append(c)
    return out


def plan(head, meshes, fade=None, curves=False):
    face = face_controls()
    centre, size = region(head, face)
    fade = fade if fade is not None else size[1] * 0.35         # from the face's height (not the ears')
    centre, size = _with_ears(centre, size)
    counts = _members(meshes, centre, size, fade)
    return ["lattice: %.1f x %.1f x %.1f round the head (fades out over %.1f past it - ears, neck ride along)" % (
                size[0], size[1], size[2], fade),
            "meshes: %s" % ", ".join("%s (%s)" % (_short(m), ("%d of %d vertices" % counts[m][1:3]) if counts[m][1]
                                                    else "all") for m in meshes),
            "the rest of the body: not in it - it can't move",
            "ears riding the squash (keeping their shape): %s" % (", ".join(_short(e) for e in ear_roots()) or
                                                                  "none found"),
            "%s above the head: up / down squash - stretch, left-right / front-back bend" % CTRL]


def _ranges(ids):
    out, start, prev = [], None, None
    for i in sorted(ids):
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            out.append((start, prev))
            start = prev = i
    if start is not None:
        out.append((start, prev))
    return out


def _members(meshes, centre, size, fade):
    """{mesh: (the vertices inside, vertices in, vertices in all, the vertices outside)}: 5.6.14 only the vertices
    inside the box and its fade move - the rest of the body can't. (All of it when the vertices can't be read.)
    5.6.28: the lattice takes the whole mesh and the outside vertices get weight 0 - a set of vertices made Maya
    keep them as a component tag on the mesh, which a referenced model can lose (the Hare's Head_squash lost
    its tag: Maya warned on every update, and 5.6.27's Repair emptied the expression)."""
    out = {}
    pts = _points(meshes)
    for m in meshes:
        p = pts.get(m)
        if not p:
            out[m] = ([m], 0, 0, [])
            continue
        ids = [i for i, v in enumerate(p) if all(abs(v[k] - centre[k]) <= size[k] / 2.0 + fade for k in range(3))]
        inside = set(ids)
        comps = ["%s.vtx[%d:%d]" % (m, a, b) if a != b else "%s.vtx[%d]" % (m, a) for a, b in _ranges(ids)]
        rest = [i for i in range(len(p)) if i not in inside]           # 5.6.28: held at weight 0 (no tags)
        outside = ["%s.vtx[%d:%d]" % (m, a, b) if a != b else "%s.vtx[%d]" % (m, a) for a, b in _ranges(rest)]
        out[m] = (comps, len(ids), len(p), outside)
    return out


def _points(meshes):
    from gus_rigtool.core import scale_check as SC
    out = {}
    for m in meshes:
        s = SC._deformed_shape(m)
        out[m] = SC._points(s) if s else None
    return out


def _moved(before, after):
    worst = 0.0
    for m, p0 in before.items():
        p1 = after.get(m)
        if p0 and p1 and len(p0) == len(p1):
            worst = max([worst] + [math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))) for a, b in zip(p0, p1)])
    return worst


def _place(node, centre, size):
    cmds.setAttr(node + ".translate", *centre, type="double3")
    cmds.setAttr(node + ".scale", *size, type="double3")


def make(head, meshes, fade=None, curves=False):
    """The squash on the head (once). One undo; nothing moves at rest (checked - undone if it did). Returns the
    control."""
    if find():
        raise RuntimeError("the head has a squash already - Remove it first.")
    head = _long(head)
    meshes = [m for m in (_long(x) for x in meshes or []) if m]
    if not head:
        raise RuntimeError("pick the head control.")
    if not meshes:
        raise RuntimeError("pick the head's meshes (the body, eyes, brows...).")
    _clean_leftover()
    face = face_controls()
    centre, size = region(head, face)
    fade = fade if fade is not None else size[1] * 0.35         # from the face's height (not the ears')
    centre, size = _with_ears(centre, size)
    h = size[1]
    curves = False                                  # 5.6.14: control curves never go in (they lost their colour, their
    # switch, their connections - Maya hid the original shape). 5.6.18: a hidden copy of each goes in instead and
    # feeds the curve you see (_curve_riders) - the face controls' curves ride the squash, nothing else changes
    face = [f for f in face if "|" + BOARD_GRP + "|" not in f]
    counts = _members(meshes, centre, size, fade)
    members = [c for m in meshes for c in counts[m][0]]
    outside = {m: counts[m][3] for m in meshes if counts[m][1]}         # 5.6.28: weight 0, no component tag
    if not members:
        raise RuntimeError("none of the meshes' vertices are inside the head's box - pick the head's meshes.")
    before = _points(meshes)
    cv0 = _curve_points(face)
    made = []
    try:
        c = _build(head, meshes, members, face, centre, size, h, fade, curves, made, outside)
    except Exception:
        _delete([n for n in made if n] + [GRP])           # nothing left half made (5.6.12 left Head_squash_grp)
        raise
    worst = max(_moved(before, _points(meshes)), _moved(cv0, _curve_points(face)))
    if worst > 1e-3 * max(h, 1.0):
        try:
            if "gusrigHeadSquash" in (cmds.undoInfo(query=True, undoName=True) or ""):
                cmds.undo()
        except RuntimeError:
            pass
        raise RuntimeError("the squash moved the meshes at rest (up to %.3g) - undone." % worst)
    return c


def mesh_copies(mesh):
    """5.6.17: shapes under the mesh that only pass a mesh along - fed straight by another mesh shape, hidden
    (intermediate), feeding something on. Each Make of 5.6.11 - 5.6.16 left one per head mesh (Maya copied the
    mesh to put the lattice 'after' it) and Remove didn't take it away. Never the original, never the skin's own
    output, never the shape you see. Returns [(copy, what feeds it, what it feeds)]."""
    out = []
    t = _long(mesh) or mesh
    for s_ in cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or []:
        if not cmds.getAttr(s_ + ".intermediateObject"):
            continue
        src = cmds.listConnections(s_ + ".inMesh", source=True, destination=False, plugs=True, shapes=True) or []
        if not src or cmds.nodeType(src[0].split(".")[0]) != "mesh":
            continue
        dst = []
        for a in ("worldMesh", "outMesh"):
            dst += cmds.listConnections(s_ + "." + a, source=False, destination=True, plugs=True, shapes=True) or []
        if dst:
            out.append((s_, src[0], dst))
    return out


def clean_copies(meshes):
    """Each pass-through copy goes: what fed it feeds what it fed. Returns how many."""
    n = 0
    for m in meshes:
        for _i in range(10):                    # a chain: one at a time, read again
            got = mesh_copies(m)
            if not got:
                break
            shape, src, dst = got[0]
            for d in dst:
                cmds.connectAttr(src, d, force=True)
            cmds.delete(shape)
            n += 1
    return n


BOARD_GRP = "Face_sliders_grp"       # the sliders board's knobs: beside the face, never ride


def _visible_curves(ctrl):
    return [x for x in cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve", fullPath=True) or []
            if not cmds.getAttr(x + ".intermediateObject") and not _short(x).endswith(RIDER)]


def _curve_points(ctrls):
    out = {}
    for c in ctrls:
        for x in _visible_curves(c):
            try:
                out[x] = _triples(cmds.xform(x + ".cv[*]", query=True, worldSpace=True, translation=True))
            except (RuntimeError, ValueError, TypeError):
                pass
    return out


def _triples(flat):
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat or []) - 2, 3)]


RIDER = "_squashRider"


def _curve_riders(face):
    """5.6.18: per face-control curve a hidden copy under the same control - only the copy goes in the lattice,
    and it feeds the curve you see (its .create). The curve keeps its name, colour, switch and connections; the
    control itself doesn't move, so what it drives isn't moved twice. Returns [[curve, copy]]."""
    out = []
    for c in face:
        for x in _visible_curves(c):
            if cmds.listConnections(x + ".create", source=True, destination=False):
                continue                                 # already fed by something: left alone
            cp = cmds.createNode("nurbsCurve", name=_short(x) + RIDER, parent=c, skipSelect=True)
            cp = cmds.ls(cp, long=True)[0] if len(cmds.ls(cp) or []) == 1 else c + "|" + _short(cp)
            cmds.connectAttr(x + ".local", cp + ".create")
            try:
                cmds.getAttr(cp + ".spans")              # pull the shape over once
            except (RuntimeError, ValueError):
                pass
            cmds.disconnectAttr(x + ".local", cp + ".create")
            cmds.setAttr(cp + ".visibility", 0)
            out.append([x, cp])
    return out


def _ride(riders):
    for x, cp in riders:
        cmds.connectAttr(cp + ".local", x + ".create", force=True)


def _unride(riders, ffd):
    """The curves back as they were (the lattice off while they let go), the copies and their hidden originals
    gone."""
    if ffd and cmds.objExists(ffd):
        try:
            cmds.setAttr(ffd + ".envelope", 0)
        except RuntimeError:
            pass
    for x, cp in riders:
        if not (cmds.objExists(x) and cmds.objExists(cp)):
            continue
        try:
            cmds.getAttr(x + ".spans")                   # the undeformed shape pulled through once more
        except (RuntimeError, ValueError):
            pass
        for src in cmds.listConnections(x + ".create", source=True, destination=False, plugs=True) or []:
            cmds.disconnectAttr(src, x + ".create")
        t = (cmds.listRelatives(cp, parent=True, fullPath=True) or [None])[0]
        left = [k for k in cmds.listRelatives(t, shapes=True, fullPath=True) or [] if RIDER in _short(k)] if t else []
        _delete(left or [cp])


def _delete(nodes):
    for n in nodes:
        try:
            if cmds.objExists(n):
                cmds.delete(n)
        except (RuntimeError, ValueError):
            pass


def _clean_leftover():
    """A Head_squash_grp with no squash control in it: what a failed Make left - it goes."""
    if cmds.objExists(GRP) and not find():
        _delete(cmds.ls(GRP, long=True))


def lattice_targets(meshes, members, outside=None):
    """5.6.28: what goes in the lattice - whole meshes when their outside vertices are known (held at weight 0
    by hold_outside, no component tag needed), else the member vertices as before."""
    outside = outside or {}
    return [m for m in meshes if m in outside] + [c for c in members if c.split(".")[0] not in outside]


def hold_outside(ffd, outside):
    """5.6.28: the vertices outside the box and its fade get weight 0 (kept on the deformer, in the rig file)."""
    n = 0
    for m, comps in (outside or {}).items():
        if comps:
            cmds.percent(ffd, comps, value=0.0)
            n += 1
    return n


def _build(head, meshes, members, face, centre, size, h, fade, curves, made, outside=None):
    from gus_rigtool.builder import controls as BC
    with utils.undo_chunk("gusrigHeadSquash"):
        grp = cmds.createNode("transform", name=GRP, skipSelect=True)
        made.append(grp)
        grp = cmds.ls(cmds.parent(grp, head)[0], long=True)[0]
        ears, planes = _ear_riders(grp, head, made)          # 5.6.15: the ears ride the squash, keeping their shape
        riders = _curve_riders(face)                        # 5.6.18: the face controls' curves ride it too
        made.extend(cp for _x, cp in riders)
        targets = lattice_targets(meshes, members, outside)
        ffd, lat, base = cmds.lattice(targets + planes + [cp for _x, cp in riders], divisions=(4, 6, 4),
                                      objectCentered=False,
                                      ldivisions=(2, 2, 2), name="Head_squash")        # 5.6.17: no 'after'
        made.extend([ffd, lat, base])
        clean_copies(meshes)                            # if Maya copied a mesh anyway: the copy goes
        hold_outside(ffd, outside)                      # 5.6.28: outside the box and its fade: weight 0
        cmds.setAttr(ffd + ".outsideLattice", 2)          # 5.6.13: attributes of the node, not flags of the command
        cmds.setAttr(ffd + ".outsideFalloffDist", fade / h)   # 5.6.14: in the lattice's own units (it's 1 tall):
        # 5.6.13 gave scene units - 11.8 lattices out, the whole body moved
        _connect_riders(ears, head)
        _ear_deltas(ears, head, made)                   # 5.6.18: the FK chain held by the head rides too
        _ride(riders)
        if ears:                                    # the ear's vertices: the lattice less, as much as the ear moves
            for m in meshes:                        # them (they ride with the ear already - not moved twice)
                got = _ear_weights(m, [c for c in members if c == m or c.startswith(m + ".")])
                if not got:
                    continue
                buckets = {}
                for v, w in zip(*got):
                    if w > 1e-3:
                        buckets.setdefault(round(1.0 - min(w, 1.0), 2), []).append(v)
                for val, vs in buckets.items():
                    cmds.percent(ffd, vs, value=val)
        for n in (lat, base):
            _place(n, centre, size)
        lat, base = [cmds.ls(cmds.parent(n, grp)[0], long=True)[0] for n in (lat, base)]
        bottom = [centre[0], centre[1] - h / 2.0, centre[2]]
        sq, sqh = cmds.nonLinear(lat, type="squash", name="Head_squash_sq")
        bx, bxh = cmds.nonLinear(lat, type="bend", name="Head_squash_bendX")
        bz, bzh = cmds.nonLinear(lat, type="bend", name="Head_squash_bendZ")
        made.extend([sq, sqh, bx, bxh, bz, bzh])
        for d in (sq, bx, bz):
            cmds.setAttr(d + ".lowBound", 0)
            cmds.setAttr(d + ".highBound", 1)
        cmds.setAttr(sq + ".maxExpandPos", 0.5)
        for hnd, rot in ((sqh, 0), (bxh, 0), (bzh, 90)):
            cmds.setAttr(hnd + ".translate", *bottom, type="double3")
            cmds.setAttr(hnd + ".rotateY", rot)
            cmds.setAttr(hnd + ".scale", h, h, h, type="double3")
        handles = [cmds.ls(cmds.parent(x, grp)[0], long=True)[0] for x in (sqh, bxh, bzh)]
        for n in [lat, base] + handles:
            cmds.setAttr(n + ".visibility", 0)
        top = [centre[0], centre[1] + h * 0.5 + h * 0.25, centre[2]]
        m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, top[0], top[1], top[2], 1]
        off, c = BC.make("C", "tmpHeadSquash", "pin", h * 0.12, m, grp, "Y", mirror=None)
        c = cmds.rename(c, CTRL)
        c = _long(CTRL)
        off = cmds.listRelatives(c, parent=True, fullPath=True)[0]
        off = cmds.rename(off, "Head_squash_offset")
        c = _long(CTRL)
        for a in ("rx", "ry", "rz", "sx", "sy", "sz"):
            try:
                cmds.setAttr(c + "." + a, lock=True, keyable=False, channelBox=False)
            except RuntimeError:
                pass
        for attr, val, lo, hi in (("squash", 1.0, 0.0, 5.0), ("bulge", 1.0, 0.0, 5.0), ("bend", 1.0, 0.0, 5.0)):
            cmds.addAttr(c, longName=attr, attributeType="double", defaultValue=val, minValue=lo, maxValue=hi,
                         keyable=True)

        def drive(src, amount, dst, k):                 # dst = src / h x amount x k
            md = cmds.createNode("multiplyDivide", name="Head_squash_%s_md" % dst.split(".")[-1], skipSelect=True)
            cmds.connectAttr(src, md + ".input1X")
            cmds.connectAttr(amount, md + ".input2X")
            md2 = cmds.createNode("multDoubleLinear", name="Head_squash_%s_k" % dst.split(".")[-1], skipSelect=True)
            cmds.connectAttr(md + ".outputX", md2 + ".input1")
            cmds.setAttr(md2 + ".input2", k / h)
            cmds.connectAttr(md2 + ".output", dst)
            made.extend([md, md2])
        drive(c + ".translateY", c + ".squash", sq + ".factor", 1.0)
        drive(c + ".translateX", c + ".bend", bx + ".curvature", 2.0)
        drive(c + ".translateZ", c + ".bend", bz + ".curvature", 2.0)
        cmds.connectAttr(c + ".bulge", sq + ".expand")

        # on / off: Visibility_ctrl.Head_Squash when there is one, else on the control
        from gus_rigtool.core import vis_switch
        holder = vis_switch.find() or c
        attr = SWITCH if holder != c else "squash_on"
        if not cmds.attributeQuery(attr, node=holder, exists=True):
            cmds.addAttr(holder, longName=attr, attributeType="bool", defaultValue=True, keyable=True)
        rev = cmds.createNode("reverse", name="Head_squash_off", skipSelect=True)
        cmds.connectAttr(holder + "." + attr, rev + ".inputX")
        for d in (ffd, sq, bx, bz):
            cmds.connectAttr(rev + ".outputX", d + ".nodeState")
        made.append(rev)
        if holder != c:
            try:
                vis_switch.assign([c], "Face_Ctrls")
            except Exception:
                pass
        cmds.addAttr(c, longName=META, dataType="string")
        cmds.setAttr(c + "." + META, json.dumps({
            "ffd": ffd, "deformers": [sq, bx, bz], "group": _short(grp), "nodes": [_short(x) for x in made],
            "switch": "%s.%s" % (_short(holder), attr), "meshes": list(meshes),
            "curves": len(riders), "riders": riders, "fade": fade, "ears": ears}), type="string")
    return c


LEFT_TYPES = ("transform", "reverse", "multiplyDivide", "plusMinusAverage", "condition", "clamp", "setRange",
              "blendColors", "multDoubleLinear", "addDoubleLinear", "unitConversion", "remapValue")
LEFT_NAME = re.compile(r"^Head_squash_|_squash_(follow|srf|fol)\d*$")


def leftovers():
    """5.6.32: what a squash removed half-way leaves (Publish had locked its nodes): Head_squash_off,
    Head_squash_factor_md, the ears' <name>_squash_follow groups... The Head_squash_ctrl itself counts only when
    it's no squash any more (find() says none)."""
    out = []
    for n in cmds.ls(type=list(LEFT_TYPES), long=True) or []:
        short = _short(n).split(":")[-1]
        if not LEFT_NAME.search(short) or n in out:
            continue
        if short == CTRL and find():
            continue
        out.append(n)
    return out


def _locked_under(nodes):
    """The nodes and everything under them that are locked (Publish's protect), unlocked; returns their names to
    lock again afterwards."""
    got = []
    for n in nodes:
        if not cmds.objExists(n):
            continue
        for x in [n] + (cmds.listRelatives(n, allDescendents=True, fullPath=True) or []):
            try:
                if cmds.lockNode(x, query=True, lock=True)[0]:
                    cmds.lockNode(x, lock=False)
                    got.append(_short(x))
            except (RuntimeError, ValueError, TypeError):
                pass
    return got


def _relock(names):
    for name in names:
        for x in cmds.ls(name, long=True) or []:
            cmds.lockNode(x, lock=True)


def clean_leftovers():
    """5.6.32: the leftovers go. A _squash_follow group: what's under it moves up one level, where it is (the ear
    controls stay put), then the group goes; any other leftover group goes with what's in it. Nodes still locked by Publish are unlocked first; what stays is locked
    again. Returns the names gone."""
    from gus_rigtool.core import spaces
    found = leftovers()
    if not found:
        return []
    gone = []
    with utils.undo_chunk("gusrigHeadSquashLeftovers"):
        relock = _locked_under(found)
        groups = sorted([n for n in found if cmds.nodeType(n) == "transform"], key=lambda x: -x.count("|"))
        for g in groups:                                     # the deepest first
            g = _long(_short(g)) or (g if cmds.objExists(g) else None)
            if not g:
                continue
            parent = (cmds.listRelatives(g, parent=True, fullPath=True) or [None])[0]
            if _short(g).split(":")[-1].rstrip("0123456789").endswith("_squash_follow"):   # the ears ride in it
                for k in cmds.listRelatives(g, children=True, type="transform", fullPath=True) or []:
                    if "constraint" not in cmds.nodeType(k).lower():
                        spaces._parent_keeping(k, parent)
            gone.append(_short(g))                           # Head_squash_grp, the planes...: with what's in it
            cmds.delete(g)
        for n in found:
            if cmds.objExists(n) and cmds.nodeType(n) != "transform":
                gone.append(_short(n))
                cmds.delete(n)
        _relock([x for x in relock if x not in gone])
    return gone


def remove():
    """Everything the squash made; the meshes and curves back as they were. 5.6.32: Publish's locks come off
    first; with no squash but its leftovers (a remove that stopped half-way), the leftovers go - see
    clean_leftovers()."""
    c = find()
    if not c:
        if leftovers():
            clean_leftovers()
            return 0
        raise RuntimeError("no head squash in this scene.")
    data = read()
    with utils.undo_chunk("gusrigHeadSquashRemove"):
        mine = [data.get("group"), data.get("ffd")] + data.get("nodes", []) + data.get("deformers", []) + \
            [e.get("group") for e in data.get("ears", [])] + [g for e in data.get("ears", [])
                                                               for _n, g in e.get("deltas", [])]
        relock = _locked_under([x for x in (_long(m) for m in mine if m) if x])
        _unride(data.get("riders", []), data.get("ffd"))     # 5.6.18
        curves = _deformed_curves(data.get("ffd"))
        from gus_rigtool.core import spaces
        for e in data.get("ears", []):                 # 5.6.18: what the delta groups held back in place
            for n, g in e.get("deltas", []):
                if cmds.objExists(g) and cmds.objExists(n):
                    for k in cmds.listRelatives(g, children=True, type="transform", fullPath=True) or []:
                        cmds.parent(k, n, relative=True)
                    cmds.delete(g)
        for e in data.get("ears", []):                 # each ear back under its own parent, where it is
            g = _long(e.get("group"))
            if not g:
                continue
            parent = (cmds.listRelatives(g, parent=True, fullPath=True) or [None])[0]
            if e.get("kind") == "group":
                for k in cmds.listRelatives(g, children=True, type="transform", fullPath=True) or []:
                    if "constraint" not in cmds.nodeType(k).lower():
                        spaces._parent_keeping(k, parent)
            elif _long(e.get("piece")):
                spaces._parent_keeping(_long(e.get("piece")), parent)
            cmds.delete(g)
        holder, _dot, attr = data.get("switch", "").partition(".")
        for n in data.get("nodes", []) + data.get("deformers", []) + [data.get("ffd")]:
            if n and cmds.objExists(n):
                cmds.delete(n)
        g = _long(data.get("group"))
        if g:
            cmds.delete(g)
        if holder and holder != CTRL and cmds.objExists(holder) and attr and \
                cmds.attributeQuery(attr, node=holder, exists=True):
            cmds.deleteAttr(holder + "." + attr)
        for n in [x for x in cmds.ls(type="reverse") or []              # 5.6.31: a switch node left with nothing
                  if x.split("|")[-1].split(":")[-1].startswith("Head_squash_off")]:
            if not cmds.listConnections(n + ".outputX", source=False, destination=True):
                cmds.delete(n)
        repaired = repair_curves(curves)
        clean_copies([m for m in data.get("meshes", []) if cmds.objExists(m) and len(cmds.ls(m)) == 1])
        clean_leftovers()                                # 5.6.32: anything still there by name
        _relock([x for x in relock if cmds.objExists(x)])
    return repaired


def _deformed_curves(ffd):
    """The control transforms whose curves the lattice deforms (5.6.11 - 5.6.13 put them in)."""
    out = []
    if not ffd or not cmds.objExists(ffd):
        return out
    for s in cmds.listConnections(ffd + ".outputGeometry", source=False, destination=True, shapes=True) or []:
        if cmds.nodeType(s) == "nurbsCurve":
            t = (cmds.listRelatives(s, parent=True, fullPath=True) or [None])[0]
            if t and t not in out:
                out.append(t)
    return out


COLOUR = ("overrideEnabled", "overrideRGBColors", "overrideColor", "overrideColorR", "overrideColorG",
          "overrideColorB", "lineWidth", "alwaysDrawOnTop")


def repair_curves(ctrls):
    """Controls whose curve went through a deformer: Maya hid the original shape (the colour, the visibility switch
    on it) and drew a new one. The colour and the switch go onto the shape you see, the hidden one goes, the shape
    gets its name back. Returns how many."""
    n = 0
    for t in ctrls:
        if not cmds.objExists(t):
            continue
        shapes = cmds.listRelatives(t, shapes=True, type="nurbsCurve", fullPath=True) or []
        hidden = [x for x in shapes if cmds.getAttr(x + ".intermediateObject")]
        shown = [x for x in shapes if not cmds.getAttr(x + ".intermediateObject")]
        if not hidden or not shown:
            continue
        orig = hidden[0]
        name = _short(orig)[:-4] if _short(orig).endswith("Orig") else None
        for x in shown:
            for a in COLOUR:
                try:
                    if cmds.attributeQuery(a, node=orig, exists=True):
                        cmds.setAttr(x + "." + a, cmds.getAttr(orig + "." + a))
                except (RuntimeError, ValueError, TypeError):
                    pass
            for src in cmds.listConnections(orig + ".visibility", source=True, destination=False, plugs=True) or []:
                cmds.connectAttr(src, x + ".visibility", force=True)
        try:
            cmds.delete(t, constructionHistory=True)         # bakes the shown curve, the hidden original goes
        except RuntimeError:
            pass
        for x in hidden:
            if cmds.objExists(x):
                try:
                    cmds.delete(x)
                except RuntimeError:
                    pass
        left = [x for x in cmds.listRelatives(t, shapes=True, type="nurbsCurve", fullPath=True) or []]
        if name and len(left) == 1 and not cmds.objExists(name):
            cmds.rename(left[0], name)
        n += 1
    return n


def after_skin(mesh):
    """True when the squash's lattice comes after the mesh's skin (else the face squashes before it's skinned)."""
    data = read()
    ffd = data.get("ffd")
    if not ffd or not cmds.objExists(ffd):
        return True
    mesh = (cmds.ls(mesh, long=True) or [mesh])[0] if len(cmds.ls(mesh) or []) == 1 else mesh
    hist = cmds.listHistory(mesh, pruneDagObjects=True) or []           # newest first
    kinds = [cmds.nodeType(x) for x in hist]
    if ffd not in hist or "skinCluster" not in kinds:
        return True
    return hist.index(ffd) < kinds.index("skinCluster")
