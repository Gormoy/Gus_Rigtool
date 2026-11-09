"""
Cloth (5.3.0): a garment (the Hare's shirt) in layers - it follows the body, ribbons give the animator the
cloth's own motion (hem, cuffs), correctives fix the poses where it breaks.

    from gus_rigtool.core import cloth
    cloth.skin_like("Hare_Body", ["Shirt"])               # the body's joints and weights + a Delta Mush
    cloth.edge_ribbon(edges, "L_Cuff")                    # a ribbon on an edge loop, following the nearest joint
    cloth.cloth_layer("Shirt", ["L_Cuff", "R_Cuff"])      # the ribbons' joints take over near them (ngSkinTools
                                                          # layer when it's there, else blended into the skin)
    cloth.make_rom(); cloth.remove_rom()                  # a range-of-motion animation on the body controls
    cloth.fix_here("Shirt")                               # a Fixes sculpt for the joint bent most at this frame
"""

import json
import math
import re

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

TOOL = "Cloth"
ROM_NODE = "gusROM"


def _short(n):
    return naming.short_name(n)


def _long(n):
    found = cmds.ls(n, long=True) or []
    return found[0] if len(found) == 1 else None


def _skin(mesh):
    from gus_rigtool.core.skin_mirror import skin_of
    return skin_of(mesh)


def _influences(skin):
    return cmds.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []


# ---- 1. skin like the body ------------------------------------------------------------------------------------

def skin_like(body, garments, delta_mush=True, replace=False):
    """Each garment: bound to the body's joints with the body's weights (closest point, joints by label / name);
    an already skinned one keeps its weights unless replace (the body's joints are still added, weight 0). A Delta
    Mush after the skin. Returns lines."""
    from gus_rigtool.core import skin_tools
    src = _skin(body)
    if not src:
        raise RuntimeError("%s has no skin: select the skinned body first, then the garments." % _short(body))
    joints = _influences(src)
    lines = []
    with utils.undo_chunk("gusrigClothSkin"):
        for g in garments:
            dst = _skin(g)
            if dst and not replace:
                have = set(_influences(dst))
                add = [j for j in joints if j not in have]
                for j in add:
                    cmds.skinCluster(dst, edit=True, addInfluence=j, weight=0.0, lockWeights=False)
                lines.append("%s: already skinned - its weights kept%s" % (
                    _short(g), (", %d body joint(s) added at 0" % len(add)) if add else ""))
            else:
                skin_tools.copy(source=body, targets=[g], surface=0, influence=(3, 1, 0))   # label, name, closest
                dst = _skin(g)
                limit = int(cmds.skinCluster(src, query=True, maximumInfluences=True) or 4)
                over = skin_tools.limit_influences([g], limit=limit)
                fixed = skin_tools.normalize(dst, g)            # 5.3.1: every vertex adds up to 1
                lines.append("%s: the body's weights (%d joints, up to %d a vertex%s)" % (
                    _short(g), len(joints), limit, (", %d vertices brought to 1" % fixed) if fixed or over else ""))
            if delta_mush and not [h for h in cmds.listHistory(g, pruneDagObjects=True) or []
                                   if cmds.nodeType(h) == "deltaMush"]:
                dm = cmds.deltaMush(g, smoothingIterations=10, smoothingStep=0.5, pinBorderVertices=True,
                                    name=_short(g).split(":")[-1] + "_deltaMush")
                lines[-1] += "; Delta Mush %s" % (dm[0] if isinstance(dm, list) else dm)
    return lines


# ---- 2. a ribbon on a garment edge ----------------------------------------------------------------------------

def _nearest_joint(point, joints):
    best, d = None, None
    for j in joints:
        p = cmds.xform(j, query=True, worldSpace=True, translation=True)
        dd = sum((a - b) ** 2 for a, b in zip(p, point))
        if d is None or dd < d:
            best, d = j, dd
    return best


def _follow(ctrls_grp, joint):
    for kind in ("parentConstraint", "scaleConstraint"):
        old = cmds.listRelatives(ctrls_grp, type=kind, fullPath=True) or []
        if old:
            cmds.delete(old)
    cmds.parentConstraint(joint, ctrls_grp, maintainOffset=True)
    cmds.scaleConstraint(joint, ctrls_grp, maintainOffset=True)


def edge_ribbon(edges, name, count=12, every=2, joints=None, mirror=True):
    """A ribbon rig on a garment's edge loop / row (the hem, a cuff): follicle joints, controls every 'every'
    follicle, its controls following the nearest joint (of 'joints', else the skin of the garment, else every
    joint), and - mirror - the same on the other side. Returns [ribbons made]."""
    from gus_rigtool.core import face_kit, ribbon, joint_labels
    from gus_rigtool.core import mirror_setup as MS
    if not edges:
        raise RuntimeError("select the edge loop (the hem, a cuff) first.")
    mesh = edges[0].split(".")[0]
    if joints is None:
        sk = _skin(mesh)
        joints = [j for j in (_influences(sk) if sk else []) if cmds.nodeType(j) == "joint"] or \
            (cmds.ls(type="joint", long=True) or [])
    made = []
    with utils.undo_chunk("gusrigClothRibbon"):
        srf, _looped = face_kit.strip_from_edges(edges, name)
        bb = cmds.exactWorldBoundingBox(srf)
        size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2]) or 1.0
        ribbon.build_rig(dict(ribbon.FACE_KIT), surface=srf, prefix=name, num_follicles=int(count),
                         ctrl_every=int(every), include_ends=False, ctrl_radius=size * 0.06, ctrl_distance=size * 0.08,
                         fol_jnt_radius=size * 0.015, bind_jnt_radius=size * 0.02, made_by="Cloth: " + name)
        srf = _long(name) or srf
        made.append(srf)
        centre = [(bb[k] + bb[k + 3]) / 2.0 for k in range(3)]
        follow = _nearest_joint(centre, joints) if joints else None
        grp = _long(name + "_ctrls_grp")
        if follow and grp:
            _follow(grp, follow)
        if mirror and joint_labels.split_side(name)[0] in ("L", "R"):
            cmds.select(srf, replace=True)
            other = joint_labels.twin_name(name)
            ribbon.mirror_build(axis="X", prefix=other)
            o_srf = _long(other)
            if o_srf:
                made.append(o_srf)
                o_grp = _long(other + "_ctrls_grp")
                o_follow = MS.twin(follow) if follow else None
                if o_grp and o_follow:
                    _follow(o_grp, o_follow)
    return made


# ---- 3. a cloth layer -----------------------------------------------------------------------------------------

def ribbon_joints(ribbons):
    """The follicle joints (the ones a mesh is skinned to) of ribbon builds, given a ribbon or one of its nodes."""
    from gus_rigtool.core import ribbon
    builds = ribbon._find_builds()
    out = []
    for r in ribbons:
        key = ribbon._resolve(r)
        if key not in builds:
            for k, b in builds.items():                      # a control / group of a build
                if any(_long(r) and (_long(r) == n or _long(r).startswith(n + "|")) for n in b["nodes"]):
                    key = k
                    break
        if key not in builds:
            continue
        for n in builds[key]["nodes"]:
            if not n.endswith("_follicles_grp") or not cmds.objExists(n):
                continue
            for f in cmds.listRelatives(n, children=True, fullPath=True) or []:
                out += [j for j in cmds.listRelatives(f, children=True, type="joint", fullPath=True) or []
                        if j not in out]
    return out


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def layer_weights(points, joint_pos, inner=None, outer=None):
    """For each point: (mask 0..1, {joint index: weight}) - the two nearest ribbon joints share it (closer = more),
    the mask is 1 up to 'inner' from the nearest joint and fades to 0 at 'outer' (by default 1x and 3x the usual
    spacing between the ribbon's joints)."""
    gaps = []
    for i, a in enumerate(joint_pos):
        d = [math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))) for k, b in enumerate(joint_pos) if k != i]
        if d:
            gaps.append(min(d))
    spacing = sorted(gaps)[len(gaps) // 2] if gaps else 1.0
    inner = spacing * 1.0 if inner is None else inner
    outer = spacing * 3.0 if outer is None else outer
    out = []
    for p in points:
        ds = sorted((math.sqrt(sum((x - y) ** 2 for x, y in zip(p, q))), k) for k, q in enumerate(joint_pos))
        near = ds[:2]
        if len(near) == 2 and near[0][0] > 1e-9:
            w0, w1 = 1.0 / near[0][0] ** 2, 1.0 / max(near[1][0], 1e-9) ** 2
            tot = w0 + w1
            share = {near[0][1]: w0 / tot, near[1][1]: w1 / tot}
        else:
            share = {near[0][1]: 1.0}
        d = near[0][0]
        mask = 1.0 if d <= inner else (0.0 if d >= outer else 1.0 - _smooth((d - inner) / ((outer - inner) or 1.0)))
        out.append((mask, share))
    return out, inner, outer


def _points(mesh, skin=None):
    """The mesh's points in world space - at rest (the skin's original shape) when there is one (5.3.1: the posed
    mesh gave the wrong distances on a frame of the range of motion)."""
    shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [mesh])[0]
    if skin:
        orig = cmds.listConnections(skin + ".originalGeometry[0]", source=True, destination=False, shapes=True)
        if orig and cmds.nodeType(orig[0]) == "mesh":
            shape = cmds.ls(orig[0], long=True)[0]
    n = cmds.polyEvaluate(shape, vertex=True)
    return [cmds.pointPosition("%s.vtx[%d]" % (shape, i), world=True) for i in range(n)]


def _size(points):
    if not points:
        return 1.0
    return max(max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)) or 1.0


def off_rest(skin, size=1.0):
    """[(joint, distance, degrees)] for the skin's joints that aren't where the skin was bound (the rig is posed)."""
    from gus_rigtool.core import world_turn as WT
    out = []
    for j in _influences(skin):
        idx = _logical(skin, j)
        if idx is None:
            continue
        try:
            bpm = cmds.getAttr("%s.bindPreMatrix[%d]" % (skin, idx))
            wm = cmds.getAttr(j + ".worldMatrix[0]")
        except (RuntimeError, ValueError):
            continue
        if not bpm or not wm or len(bpm) != 16 or len(wm) != 16:
            continue
        m = WT._mul(wm, bpm)                                 # identity when the joint is where it was bound
        moved = sum(x * x for x in m[12:15]) ** 0.5
        ident = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        turned = WT._angle_between(ident, m)
        if moved > size * 0.002 or turned > 0.5:
            out.append((j, moved, turned))
    return sorted(out, key=lambda r: (-r[2], -r[1]))


def _logical(skin, joint):
    for p in cmds.listConnections(joint + ".worldMatrix", plugs=True, source=False, destination=True) or []:
        node, attr = p.split(".", 1)
        if node.split("|")[-1] == skin.split("|")[-1] and attr.startswith("matrix["):
            return int(attr[len("matrix["):-1])
    return None


def cloth_layer(mesh, ribbons, inner=None, outer=None, name=None):
    """The ribbons' joints take over the mesh near them: on their own ngSkinTools 2 layer (mask fading with distance)
    when ngSkinTools is loaded - else blended straight into the skin. 5.3.1: worked out at rest (the range of
    motion's first frame when there is one; refused while the rig is posed), and checked after: every vertex adds
    up to 1, and an ngSkinTools layer that doesn't give that is undone and blended instead. Returns a line."""
    from gus_rigtool.core import skin_tools
    skin = _skin(mesh)
    if not skin:
        raise RuntimeError("%s has no skin: Skin like the body first." % _short(mesh))
    joints = ribbon_joints(ribbons)
    if not joints:
        raise RuntimeError("no ribbon joints found in %s." % ", ".join(_short(r) for r in ribbons))
    now = cmds.currentTime(query=True)
    if cmds.objExists(ROM_NODE):                             # its first frame: everything at 0
        cmds.currentTime(json.loads(cmds.getAttr(ROM_NODE + ".gusRomData") or "{}").get("start", now))
    try:
        pts = _points(mesh, skin)
        off = off_rest(skin, _size(pts))
        if off:
            raise RuntimeError("the rig isn't at rest (%s%s moved from where %s was bound): go to a frame where it "
                               "rests, or Remove the range of motion, then try again." % (
                                   ", ".join(_short(j) for j, _d, _a in off[:4]), " ..." if len(off) > 4 else "",
                                   _short(mesh)))
        have = set(_influences(skin))
        for j in joints:
            if j not in have:
                cmds.skinCluster(skin, edit=True, addInfluence=j, weight=0.0, lockWeights=False)
        skin_tools.normalize(skin, mesh)                     # start from weights that add up to 1
        jpos = [cmds.xform(j, query=True, worldSpace=True, translation=True) for j in joints]
        rows, inner, outer = layer_weights(pts, jpos, inner, outer)
        name = name or "cloth " + ", ".join(_short(r) for r in ribbons)[:40]
        fade = " - fades from %.2f to %.2f" % (inner, outer)
        why = None
        try:
            cmds.undoInfo(openChunk=True, chunkName="gusrigClothNgLayer")
            try:
                line = _ng_layer(skin, joints, rows, name)
            finally:
                cmds.undoInfo(closeChunk=True)
            bad = _check(skin, mesh, joints)
            if not bad:
                return line + fade
            why = "the layer gave %s - undone" % bad
            cmds.undo()
        except Exception as e:                               # no ngSkinTools 2, or its API differs here
            why = why or str(e) or e.__class__.__name__
        _blend(skin, mesh, joints, rows)
        fixed = skin_tools.normalize(skin, mesh)
        return "blended into %s (ngSkinTools layer not used: %s)%s%s" % (
            _short(skin), why, fade, (", %d vertices brought to 1" % fixed) if fixed else "")
    finally:
        cmds.currentTime(now)


def _check(skin, mesh, joints):
    """What's wrong with the skin after a layer: vertices not adding up to 1, ribbon joints with no weight."""
    from gus_rigtool.core import skin_tools
    infl, _comp, weights = skin_tools._weights(skin, mesh)
    bad = [i for i, w in weights.items() if abs(sum(w) - 1.0) > 1e-3]
    if bad:
        return "%d vertices not adding up to 1" % len(bad)
    cols = [k for k, n in enumerate(infl) if (_long(n) or n) in joints]
    if cols and not any(w[k] > 1e-4 for w in weights.values() for k in cols):
        return "no weight on the ribbon joints"
    return None


def _ng_layer(skin, joints, rows, name):
    from ngSkinTools2 import api as ng                       # raises ImportError without ngSkinTools 2
    try:
        layers = ng.Layers(skin)
        existing = layers.list()
    except Exception:
        existing = []
    if not existing:
        layers = ng.init_layers(skin)                        # the base layer takes the current weights
    layer = layers.add(name)
    count = len(rows)
    for k, j in enumerate(joints):
        idx = _logical(skin, j)
        if idx is None:
            continue
        layer.set_weights(idx, [r[1].get(k, 0.0) for r in rows])
    layer.set_weights(ng.NamedPaintTarget.MASK, [r[0] for r in rows])
    return "ngSkinTools layer '%s' on %s, %d vertices" % (name, _short(skin), count)


def _blend(skin, mesh, joints, rows):
    """new = old x (1 - mask) + ribbon share x mask, for every vertex (one undo)."""
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    sel = om.MSelectionList()
    sel.add(skin)
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [mesh])[0]
    sel.add(shape)
    path = sel.getDagPath(1)
    comp = om.MFnSingleIndexedComponent()
    cobj = comp.create(om.MFn.kMeshVertComponent)
    comp.setCompleteData(len(rows))
    weights, count = fn.getWeights(path, cobj)
    infl = [p.fullPathName() for p in fn.influenceObjects()]
    col = dict((j, infl.index(j)) for j in joints if j in infl)
    w = list(weights)
    for v, (mask, share) in enumerate(rows):
        if mask <= 0:
            continue
        base = v * count
        total = sum(w[base:base + count]) or 1.0             # raw (Post) weights: as shares of 1 first
        for i in range(count):
            w[base + i] *= (1.0 - mask) / total
        for k, s in share.items():
            if joints[k] in col:
                w[base + col[joints[k]]] += s * mask
    idx = om.MIntArray(list(range(count)))
    fn.setWeights(path, cobj, idx, om.MDoubleArray(w), True)


def repair(mesh, limit=None):
    """5.3.1: a garment whose weights went wrong (vertices pulled to the world origin): every vertex limited to the
    skin's joints-per-vertex (4) and made to add up to 1. Returns (vertices over the limit, vertices not 1)."""
    from gus_rigtool.core import skin_tools
    skin = _skin(mesh)
    if not skin:
        raise RuntimeError("%s has no skin." % _short(mesh))
    limit = int(limit or cmds.skinCluster(skin, query=True, maximumInfluences=True) or 4)
    with utils.undo_chunk("gusrigClothRepair"):
        over = skin_tools.limit_influences([mesh], limit=limit)
        fixed = skin_tools.normalize(skin, mesh)
    return over, fixed


# ---- 4. range of motion ---------------------------------------------------------------------------------------

PARTS = [("spine", r"spine|chest|abdomen|waist|torso|pelvis|hips?_?ctrl|cog", 30),
         ("neck & head", r"neck|head", 35),
         ("clavicles", r"clav|scapula", 20),
         ("shoulders", r"shoulder|humerus|upper_?arm|^[lr]_arm|_arm_", 70),
         ("elbows", r"elbow|radius|fore_?arm|lower_?arm", 70),
         ("wrists", r"wrist|hand_ctrl|_hand$", 45),
         ("hips", r"femur|thigh|up_?leg|^[lr]_hip", 60),
         ("knees", r"knee|tibia|shin|low_?leg", 70),
         ("ankles", r"ankle|foot_ctrl", 35)]
SKIP = r"ik|pv|pole|settings|world|main|_fol_|mouth|brow|eye|lid|finger|thumb|index|middle|ring|pinky|toe|" \
       r"tongue|ear|tail|cape|sleeve|jaw|lip|cheek|nose|space|follow|global"


def rom_controls():
    """{part: [controls]} - the body's (FK) controls by name, both sides."""
    from gus_rigtool.tools import checker
    ctrls = [c for c in checker.transforms(None) if checker.is_control(c)]
    out = {}
    taken = set()
    for part, rx, _a in PARTS:
        hits = [c for c in ctrls if c not in taken and re.search(rx, _short(c).lower()) and
                not re.search(SKIP, _short(c).lower())]
        fk = [c for c in hits if "fk" in _short(c).lower()]
        hits = fk or hits
        if hits:
            out[part] = hits
            taken.update(hits)
    return out


def _keyable(plug):
    try:
        return cmds.getAttr(plug, keyable=True) and not cmds.getAttr(plug, lock=True) and \
            not cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True)
    except (RuntimeError, ValueError):
        return False


def make_rom(start=None, step=5):
    """Keys a range of motion: each body part in turn, each axis +angle / 0 / -angle / 0 (both sides together).
    Remembered on a 'gusROM' node, so remove_rom takes exactly these keys away. Returns (start, end, parts)."""
    if cmds.objExists(ROM_NODE):
        raise RuntimeError("there's a range of motion already: Remove it first.")
    parts = rom_controls()
    if not parts:
        raise RuntimeError("no body controls found by name (spine, neck, shoulder, elbow, hip, knee...).")
    start = int(start if start is not None else cmds.playbackOptions(query=True, minTime=True))
    t = start
    keyed, plan, was = [], [], {}
    with utils.undo_chunk("gusrigROM"):
        settings = utils.nodes_with_attr("ikfk")
        for s in settings:                                   # Gus_Rigtool limbs: FK (0) for the ROM
            if _keyable(s + ".ikfk"):
                was[s + ".ikfk"] = cmds.getAttr(s + ".ikfk")
                cmds.setKeyframe(s + ".ikfk", time=start, value=0)
                keyed.append(s + ".ikfk")
        for part, _rx, ang in PARTS:
            ctrls = parts.get(part)
            if not ctrls:
                continue
            plan.append("%s (%d) from frame %d" % (part, len(ctrls), t))
            for ax in "XYZ":
                plugs = [c + ".rotate" + ax for c in ctrls if _keyable(c + ".rotate" + ax)]
                for p in plugs:
                    if p not in keyed:
                        keyed.append(p)
                        was[p] = cmds.getAttr(p)
                        cmds.setKeyframe(p, time=start, value=0)
                for dt, v in ((0, 0), (step, ang), (2 * step, 0), (3 * step, -ang), (4 * step, 0)):
                    for p in plugs:
                        cmds.setKeyframe(p, time=t + dt, value=v)
                t += 4 * step
        node = cmds.createNode("network", name=ROM_NODE, skipSelect=True)
        cmds.addAttr(node, longName="gusRomData", dataType="string")
        cmds.setAttr(node + ".gusRomData", json.dumps({"start": start, "end": t, "plugs": keyed,
                                                         "was": was}), type="string")
        if cmds.playbackOptions(query=True, maxTime=True) < t:
            cmds.playbackOptions(maxTime=t)
    return start, t, plan


def remove_rom():
    """Takes the range of motion's keys away (and its node); every channel back to its value from before."""
    if not cmds.objExists(ROM_NODE):
        raise RuntimeError("no range of motion in this scene.")
    data = json.loads(cmds.getAttr(ROM_NODE + ".gusRomData") or "{}")
    plugs = data.get("plugs", [])
    n = 0
    with utils.undo_chunk("gusrigROMRemove"):
        for p in plugs:
            q = _find_plug(p)
            if not q:
                continue
            cmds.cutKey(q, time=(data["start"], data["end"]), clear=True)
            try:
                cmds.setAttr(q, data.get("was", {}).get(p, 0.0))
            except RuntimeError:
                pass
            n += 1
        if plugs and not n:                     # 5.6.6: found none - keep the record, say so
            raise RuntimeError("none of the %d keyed channels were found (renamed?) - the range of motion is kept. "
                               "Checker > 'Keys left on controls' > Fix deletes keys on every control." % len(plugs))
        cmds.delete(ROM_NODE)
    return n


def _find_plug(p):
    """5.6.6: the plug as saved (a full path), else the same control by name - the saved path is gone when groups
    went in above it (Global > World > Local made the Hare's 'Remove it' find 0 channels)."""
    if cmds.objExists(p):
        return p
    node, _sep, attr = p.partition(".")
    got = cmds.ls(node.split("|")[-1], long=True) or []
    return got[0] + "." + attr if len(got) == 1 and cmds.objExists(got[0] + "." + attr) else None


# ---- 5. a fix for this pose -----------------------------------------------------------------------------------

def bent_joint(mesh):
    """The joint of the mesh's skin bent most from its rest right now (degrees)."""
    from gus_rigtool.core import shape_fixes
    skin = _skin(mesh)
    if not skin:
        raise RuntimeError("%s has no skin." % _short(mesh))
    best, most = None, 0.0
    for j in _influences(skin):
        if cmds.nodeType(j) != "joint":
            continue
        try:
            a = shape_fixes._angle(shape_fixes.aim_now(j), shape_fixes.aim_rest(j))
        except Exception:
            continue
        if a > most:
            best, most = j, a
    return best, most


def fix_here(mesh, joint=None):
    """A Fixes sculpt of the mesh at this frame, driven by the joint bent most (or the one given)."""
    from gus_rigtool.core import shape_fixes
    if joint is None:
        joint, ang = bent_joint(mesh)
        if not joint or ang < 5:
            raise RuntimeError("nothing is bent at this frame (pose the rig, or go to a frame of the range of "
                               "motion).")
    return shape_fixes.start(mesh=mesh, joint=joint)
