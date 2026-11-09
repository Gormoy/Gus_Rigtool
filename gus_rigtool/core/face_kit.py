"""
Face kit: a face built on the mesh the way Tubero's was - ribbons on edge loops with follicle joints and controls,
the eye control's Blink, a mouth ribbon following the jaw, brows as a control hierarchy. Each part from the edges
you select; the left side is mirrored to the right.

    eyes(left_eye, head)                 eye joints, aim controls (L / R_Eye_ctrl) under Eyes_ctrl (head / world)
    eyelids(edges, eye, side)            a ribbon round the eye; Blink (set driven keys), Blink_Height on the
                                         eye control; mirrored
    mouth(edges, jaw, realistic)         one ribbon round the lips; each control follows the jaw by its height
                                         (lower lip 1, corners 0.5, upper lip 0); realistic: lip roll, sticky lips
    facial(edges, name, side)            any strip (cheek, nasolabial, around the eye); mirrored
    brows(edges, side)                   a ribbon along the brow: Brows_ctrl > L_Brow_main_ctrl > L_Brow_01..03
                                         - plain hierarchy, no constraints on the offsets

All of it goes in face_kit_grp, which follows the head.
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming, ribbon, utils
from gus_rigtool.core import nodes as _nodes

TOOL = "Face"
GRP = "face_kit_grp"
STYLES = {"cartoony": {"eyelid": 28, "eyelid_every": 4, "mouth": 28, "mouth_every": 3, "strip": 9, "strip_every": 2},
          "realistic": {"eyelid": 32, "eyelid_every": 2, "mouth": 36, "mouth_every": 2, "strip": 13,
                        "strip_every": 2}}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_long = _nodes.long_name


_pos = _nodes.world_pos


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _len(v):
    return math.sqrt(sum(x * x for x in v))


def _unit(v):
    n = _len(v)
    return [x / n for x in v] if n > 1e-9 else [0.0, 1.0, 0.0]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def group(head=None):
    """face_kit_grp (made once), following the head joint / control."""
    g = _long(GRP)
    if not g:
        g = cmds.createNode("transform", name=GRP)
        parent = _long("controls_grp")
        if parent:
            g = cmds.parent(g, parent)[0]
        g = _long(GRP)
    if head and _long(head) and not cmds.listRelatives(g, type="parentConstraint"):
        cmds.parentConstraint(_long(head), g, maintainOffset=True)
        cmds.scaleConstraint(_long(head), g, maintainOffset=True)
    return g


def _edges(edges):
    edges = [e for e in (cmds.ls(edges or cmds.ls(selection=True), flatten=True) or []) if ".e[" in e]
    if len(edges) < 3:
        raise RuntimeError("select the mesh's edges first (an edge loop round the eye / lips, or a row).")
    return edges


def _edges_now(edges):
    """The edges as a list, read now (from the selection when None); as given if there are none to read."""
    try:
        return _edges(edges)
    except RuntimeError:
        return edges


def strip_from_edges(edges, name, width=None):
    """A thin NURBS ribbon along the edges (round them when they make a loop). Returns (ribbon, looped)."""
    cmds.select(_edges(edges), replace=True)
    curve = ribbon.edge_to_curve(degree=3, form="Best guess", name=name + "_crv")
    shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
    looped = cmds.getAttr(shape + ".form") != 0
    cvs = cmds.ls(curve + ".cv[*]", flatten=True) or []
    pts = [_pos(c) for c in cvs]
    centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
    size = max(_len(_sub(p, centre)) for p in pts) or 1.0
    w = width or size * 0.12
    a = cmds.duplicate(curve, name=name + "_crvA")[0]
    b = cmds.duplicate(curve, name=name + "_crvB")[0]
    if looped:                                          # inside / outside the loop
        f = w / size
        for crv, s in ((a, 1.0 - f), (b, 1.0 + f)):
            cmds.scale(s, s, s, crv, pivot=centre, absolute=True)
            cmds.makeIdentity(crv, apply=True, scale=True)
    else:                                               # above / below the row (left / right if it runs up)
        chord = _sub(pts[-1], pts[0])
        side = _unit(_cross([0.0, 0.0, 1.0], chord))
        for crv, s in ((a, -0.5), (b, 0.5)):
            cmds.move(side[0] * w * s, side[1] * w * s, side[2] * w * s, crv, relative=True)
            cmds.makeIdentity(crv, apply=True, translate=True)
    srf = cmds.loft(a, b, degree=1, uniform=True, constructionHistory=False, name=name)[0]
    cmds.delete(curve, a, b)
    ribbon.along_u(srf)               # a loft runs along V: the builder needs the length along U
    return _long(srf), looped


def build_ribbon(name, edges, count, every, include_ends=True, ctrl_size=None):
    """A ribbon rig on the edges (follicle joints, controls, the ribbon skinned to them). Returns the ribbon."""
    srf, looped = strip_from_edges(edges, name)
    span = cmds.exactWorldBoundingBox(srf)
    size = max(span[3] - span[0], span[4] - span[1], span[5] - span[2]) or 1.0
    ribbon.build_rig(dict(ribbon.FACE_KIT), surface=srf, prefix=name, num_follicles=int(count),
                     ctrl_every=int(every), include_ends=include_ends, group_parent=group(),
                     ctrl_radius=ctrl_size or size * 0.04, ctrl_distance=size * 0.05,
                     fol_jnt_radius=size * 0.01, bind_jnt_radius=size * 0.015, made_by="Face kit: " + name)
    srf = _long(name) or srf
    # the ribbon group doesn't inherit transforms: its controls follow the head through face_kit_grp
    ctrls_grp = _long(name + "_ctrls_grp")
    if ctrls_grp and not cmds.listRelatives(ctrls_grp, type="parentConstraint"):
        cmds.parentConstraint(group(), ctrls_grp, maintainOffset=True)
        cmds.scaleConstraint(group(), ctrls_grp, maintainOffset=True)
    return srf


def _live(ctrls):
    """[(index, offset uuid, control uuid, world position)]: paths change when groups go in, uuids don't."""
    return [(i, utils.uuid(o), utils.uuid(c), _pos(c)) for i, o, c in ctrls]


def controls_of(srf):
    """[(follicle index, offset group, control)] of a ribbon build, in order."""
    builds = ribbon._find_builds()
    key = ribbon._resolve(srf)
    build = builds.get(key) or builds.get(_long(srf))
    if not build:
        return []
    out = []
    for i, off in sorted(ribbon._build_offsets(build).items()):
        c = ribbon._control_under(off)
        if c:
            out.append((i, off, c))
    return out


# ---------------------------------------------------------------------------
# re-runs (4.3.0): a part remembers how it was made; Redo makes it again keeping shapes and the meshes' weights
# ---------------------------------------------------------------------------

PART_ATTR = "gusFacePart"
PARTS = ("eyelids", "mouth", "facial", "brows")


def _edge_list(edges):
    if isinstance(edges, str):
        return [edges]
    return [str(e) for e in (edges or [])]


def _remember(srf, part, **args):
    import json
    srf = _long(srf)
    if not srf:
        return
    if not cmds.attributeQuery(PART_ATTR, node=srf, exists=True):
        cmds.addAttr(srf, longName=PART_ATTR, dataType="string")
    cmds.setAttr(srf + "." + PART_ATTR, json.dumps(dict(args, part=part)), type="string")


def part_of(srf):
    """How a face ribbon was made ({'part', 'edges', ...}), or None."""
    import json
    srf = _long(srf) or srf
    try:
        if srf and cmds.attributeQuery(PART_ATTR, node=srf, exists=True):
            return json.loads(cmds.getAttr(srf + "." + PART_ATTR) or "{}") or None
    except (RuntimeError, ValueError):
        pass
    return None


def first_side(srf):
    """The ribbon a Face part was made on (the left one), for a mirrored twin too."""
    key = _long(srf)
    if part_of(key):
        return key
    builds = ribbon._find_builds()
    first = ribbon._mirror_of(key, builds) if key in builds else None
    return first if first and part_of(first) else None


def _extras_of(part, data):
    """Nodes a part makes outside its ribbons (they're made again)."""
    from gus_rigtool.builder import names
    out = []
    if part == "mouth":
        out.append(names.make("C", "Mouth", "ctrl"))
    if part == "brows":
        for sd in ("L", "R"):
            out.append(names.make(sd, "Brow_main", "ctrl"))
    found = []
    for n in out:
        n = _long(n)
        if n:
            p = cmds.listRelatives(n, parent=True, fullPath=True)
            found.append(p[0] if p else n)                           # its offset group
    return found


def redo(srf, **changes):
    """Make a Face part again from the edges it remembers (changes: e.g. style='realistic', count=4): its old
    ribbons go, the new ones get the old control shapes (by order) and the meshes skinned to their joints keep
    their weights (same joint name, else the nearest). Returns the new ribbons."""
    from gus_rigtool.core import curves, ribbon_keep
    first = first_side(srf)
    if not first:
        raise RuntimeError("pick a ribbon the Face tab made (made with 4.3.0 or later: it remembers its edges).")
    data = dict(part_of(first))
    data.update({k: v for k, v in changes.items() if v is not None})
    part = data.pop("part")
    builds = ribbon._find_builds()
    keys = [first] + [t for t in ribbon._mirrors_of(first, builds) if cmds.objExists(t)]
    shapes, parked = {}, {}
    with utils.undo_chunk("gusrigFaceRedo"):
        for k in keys:
            name = naming.short_name(k)
            shapes[name] = [(curves.read_shape(c), curves.read_style(c)) for _i, _o, c in controls_of(k)]
            parked[name] = ribbon_keep.park(k)
        extras = _extras_of(part, data)
        for k in keys:
            if k in ribbon._find_builds():
                ribbon.delete_build(k)
        for n in extras + keys:
            if cmds.objExists(n):
                cmds.delete(n)
        edges = data.pop("edges")
        if part == "eyelids":
            made = eyelids(edges, data.pop("eye_ctrl"), side=data.get("side", "L"), style=data.get("style", "cartoony"),
                           do_mirror=data.get("do_mirror", True))
        elif part == "mouth":
            made = [mouth(edges, data.pop("jaw"), data.get("style", "cartoony"), data.get("realistic_extras"))]
        elif part == "facial":
            made = facial(edges, data.get("name", "facial"), data.get("side", "L"), data.get("style", "cartoony"),
                          data.get("do_mirror", True))
        else:
            made = brows(edges, data.get("side", "L"), int(data.get("count", 3)), data.get("style", "cartoony"),
                         data.get("do_mirror", True))
        made = [m for m in (made or []) if m]
        for m in made:
            name = naming.short_name(m)
            for (shape, style), (_i, _o, c) in zip(shapes.get(name, []), controls_of(m)):
                try:
                    curves.set_shape(c, shape, style)
                except (RuntimeError, ValueError, KeyError):
                    pass
            ribbon_keep.restore(parked.get(name), _long(name))
    utils.info(TOOL, "%s made again: %s (control shapes and skin weights kept)." % (
        part, ", ".join(naming.short_name(m) for m in made)))
    return made


def mirror(srf):
    """The ribbon's build mirrored to the other side (behaviour mirror). Returns the twin ribbon."""
    cmds.select(srf, replace=True)
    ribbon.mirror_build(axis="X", style="behavior")
    twin = naming.mirror_name(naming.short_name(srf), _pairs())
    return _long(twin) if twin else None


def _pairs():
    from gus_rigtool.core import sides
    return sides.default_pairs()


def driven_group(ctrl, suffix="_driven"):
    """A group right above the control (zeroed), for set driven keys - like Tubero's _driven groups."""
    name = naming.short_name(ctrl) + suffix
    parent = (cmds.listRelatives(ctrl, parent=True, fullPath=True) or [None])[0]
    if parent and parent.split("|")[-1] == name:
        return parent
    g = cmds.createNode("transform", name=name, parent=parent)
    g = cmds.ls(g, long=True)[0]
    cmds.xform(g, worldSpace=True, matrix=cmds.xform(ctrl, query=True, worldSpace=True, matrix=True))
    ctrl = cmds.parent(ctrl, g)[0]
    return g


def _local_vector(node, world_vec):
    """A world direction in node's space (rotation and scale)."""
    from gus_rigtool.core import shape_fixes as F
    m = cmds.xform(node, query=True, worldSpace=True, matrix=True)
    inv = F.inverse(list(m))
    return F.vmul(world_vec, inv)


def _float(node, attr, value, lo=None, hi=None):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        flags = {}
        if lo is not None:
            flags["minValue"] = lo
        if hi is not None:
            flags["maxValue"] = hi
        cmds.addAttr(node, longName=attr, attributeType="double", defaultValue=value, keyable=True, **flags)
    return node + "." + attr


# ---------------------------------------------------------------------------
# eyes
# ---------------------------------------------------------------------------

def _centre(node):
    """The centre of an eye: a mesh's bounding box, else the node's position."""
    if cmds.listRelatives(node, shapes=True, type="mesh"):
        b = cmds.exactWorldBoundingBox(node)
        return [(b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0, (b[2] + b[5]) / 2.0]
    return _pos(node)


def eyes(left_eye, head, distance=None):
    """L / R eye joints at the eye centres (under head), each aimed at its control; both under Eyes_ctrl, which
    has head / world space. left_eye: the left eye mesh (or a locator at its centre). Returns the controls."""
    from gus_rigtool.builder import controls as BC
    head = _long(head)
    if not head:
        raise RuntimeError("pick the head joint (or control) for the eyes to hang from.")
    g = group(head)
    c_l = _centre(left_eye)
    c_r = [-c_l[0], c_l[1], c_l[2]]
    dist = distance or max(abs(c_l[0]) * 6.0, 5.0)
    joint_parent = head if cmds.nodeType(head) == "joint" else g
    with utils.undo_chunk("gusrigFaceEyes"):
        main_off, main = BC.make("C", "Eyes", "rectangle", abs(c_l[0]) * 1.8, _t([0.0, c_l[1], c_l[2] + dist]), g,
                                 "Z", mirror=None)
        made = {}
        for side, c in (("L", c_l), ("R", c_r)):
            cmds.select(clear=True)
            j = _long(cmds.joint(name="%s_Eye" % side, position=c))
            end = cmds.joint(name="%s_Eye_End" % side, position=[c[0], c[1], c[2] + abs(c_l[0]) * 0.5])
            cmds.select(clear=True)
            j = _long(cmds.parent(j, joint_parent)[0])
            if not cmds.listRelatives(j, children=True, type="joint"):
                cmds.parent(end, j)
            _eo, ctrl = BC.make(side, "Eye", "circle", abs(c_l[0]) * 0.5, _t([c[0], c[1], c[2] + dist]), main, "Z",
                                mirror=None)
            cmds.aimConstraint(ctrl, j, maintainOffset=True, aimVector=(0, 0, 1), upVector=(0, 1, 0),
                               worldUpType="objectrotation", worldUpVector=(0, 1, 0), worldUpObject=g)
            for a, v, lo, hi in (("Blink", 0.0, 0.0, 1.0), ("Blink_Height", 0.5, 0.0, 1.0)):
                _float(ctrl, a, v, lo, hi)
            made[side] = ctrl
        from gus_rigtool.builder import names
        world = _long(names.make("C", "world", "ctrl"))
        if world:                                           # look round with the head, or stay on a spot
            BC.add_spaces("C", "Eyes", main, main_off, [("head", g), ("world", world)], default=0)
    utils.info(TOOL, "eyes: L_Eye / R_Eye joints aimed at their controls under Eyes_ctrl; Blink, Blink_Height on "
               "each eye control.")
    return made


def aim_eyes(joints, head=None, distance=None):
    """5.6.5: eye joints the rig already has (skinned) aimed at L / R_Eye_ctrl - the joints stay, the skin doesn't
    change; an aim constraint (maintain offset) turns them. The eye controls go under Eyes_ctrl: the one the rig
    has, else a new one under the face (head / world space - head needed then). Left = +X. Returns the controls."""
    from gus_rigtool.builder import controls as BC, names
    joints = [_long(j) for j in joints or []]
    joints = [j for j in joints if j and cmds.nodeType(j) == "joint"]
    if len(joints) != 2:
        raise RuntimeError("select the two eye joints (left and right).")
    for j in joints:
        for a in ("rotate", "rotateX", "rotateY", "rotateZ"):
            if cmds.listConnections(j + "." + a, source=True, destination=False):
                raise RuntimeError("%s's rotation is driven already - it can't be aimed too." % j.split("|")[-1])
    pos = dict((j, _pos(j)) for j in joints)
    left, right = sorted(joints, key=lambda j: -pos[j][0])
    half = abs(pos[left][0] - pos[right][0]) / 2.0 or 1.0
    dist = distance or max(half * 6.0, 5.0)
    main = _long(names.make("C", "Eyes", "ctrl")) or _long("Eyes_ctrl")
    up = (cmds.listRelatives(left, parent=True, fullPath=True) or [None])[0] or _long(head)
    made = {}
    with utils.undo_chunk("gusrigFaceAimEyes"):
        if not main:
            head = _long(head)
            if not head:
                raise RuntimeError("no Eyes_ctrl in the rig: pick the head joint (or control) for a new one.")
            g = group(head)
            cy = (pos[left][1] + pos[right][1]) / 2.0
            cz = (pos[left][2] + pos[right][2]) / 2.0
            cx = (pos[left][0] + pos[right][0]) / 2.0
            main_off, main = BC.make("C", "Eyes", "rectangle", half * 1.8, _t([cx, cy, cz + dist]), g, "Z",
                                     mirror=None)
            world = _long(names.make("C", "world", "ctrl"))
            if world:
                _sp, main_off, main = BC.add_spaces("C", "Eyes", main, main_off, [("head", g), ("world", world)],
                                                    default=0)
        for side, j in (("L", left), ("R", right)):
            name = names.make(side, "Eye", "ctrl")
            ctrl = _long(name)
            if not ctrl:
                p = pos[j]
                _eo, ctrl = BC.make(side, "Eye", "circle", half * 0.5, _t([p[0], p[1], p[2] + dist]), main, "Z",
                                    mirror=None)
            cmds.aimConstraint(ctrl, j, maintainOffset=True, aimVector=(0, 0, 1), upVector=(0, 1, 0),
                               worldUpType="objectrotation", worldUpVector=(0, 1, 0), worldUpObject=up or main)
            made[side] = ctrl
    utils.info(TOOL, "eyes aimed: %s -> %s, %s -> %s (under %s). The skin didn't change." % (
        left.split("|")[-1], made["L"].split("|")[-1], right.split("|")[-1], made["R"].split("|")[-1],
        main.split("|")[-1]))
    return made


def _t(p):
    return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, p[0], p[1], p[2], 1.0]


# ---------------------------------------------------------------------------
# eyelids
# ---------------------------------------------------------------------------

def _split_lids(ctrls, centre):
    """(upper, lower, corners) of [(index, offset, control, position)]: the two widest are the corners (they don't
    move on a blink); the others split by height at the middle of the lid controls themselves (4.4.0: the eye
    centre is only used if they're all at one height), so a loop that sits a bit off the eye still splits."""
    by_x = sorted(ctrls, key=lambda c: c[3][0])
    corners = {by_x[0][2], by_x[-1][2]} if len(by_x) > 2 else set()
    rest = [c for c in ctrls if c[2] not in corners]
    ys = [c[3][1] for c in rest]
    mid = (min(ys) + max(ys)) / 2.0 if ys and max(ys) - min(ys) > 1e-6 else centre[1]
    upper = [c for c in rest if c[3][1] >= mid]
    lower = [c for c in rest if c[3][1] < mid]
    return upper, lower, corners


def _nearest_by_x(item, others):
    return min(others, key=lambda o: abs(o[3][0] - item[3][0])) if others else None


def blink_plan(srf, centre):
    """(controls found, upper, lower, pairs) - what blink_setup will work with (for reports)."""
    ctrls = _live(controls_of(srf))
    upper, lower, _c = _split_lids(ctrls, centre)
    pairs = sum(1 for it in upper if _nearest_by_x(it, lower)) + sum(1 for it in lower if _nearest_by_x(it, upper))
    return len(ctrls), len(upper), len(lower), pairs


def blink_setup(srf, eye_ctrl, centre):
    """Blink on the eye control closes the lids (set driven keys on _driven groups: 0 open, 1 the lids meet
    at Blink_Height); Blink_Height moves where they meet (0 on the lower lid, 1 on the upper)."""
    ctrls = _live(controls_of(srf))
    upper, lower, _corners = _split_lids(ctrls, centre)
    blink = eye_ctrl + ".Blink"
    height = eye_ctrl + ".Blink_Height"
    done = 0
    for lid, others, share in ((upper, lower, "up"), (lower, upper, "low")):
        for item in lid:
            other = _nearest_by_x(item, others)
            if not other:
                continue
            c = utils.path(item[2])
            gap = _sub(other[3], item[3])                             # all the way to the other lid
            drv = driven_group(c)
            parent = cmds.listRelatives(drv, parent=True, fullPath=True)[0]
            half = _local_vector(parent, [g * 0.5 for g in gap])      # meet half way: Blink_Height 0.5
            for ax, v in zip("XYZ", half):
                plug = drv + ".translate" + ax
                cmds.setDrivenKeyframe(plug, currentDriver=blink, driverValue=0.0, value=0.0)
                cmds.setDrivenKeyframe(plug, currentDriver=blink, driverValue=1.0, value=v)
            # height: the meeting line moves up / down - a second group, blink x (height - 0.5) x the gap
            hg = driven_group(drv, "_height")
            full = _local_vector(cmds.listRelatives(hg, parent=True, fullPath=True)[0], gap)
            sign = 1.0 if share == "up" else -1.0
            label = naming.short_name(c)
            pma = cmds.createNode("plusMinusAverage", name=label + "_heightShift")
            cmds.setAttr(pma + ".operation", 2)                       # height - 0.5
            cmds.connectAttr(height, pma + ".input1D[0]")
            cmds.setAttr(pma + ".input1D[1]", 0.5)
            mul = cmds.createNode("multDoubleLinear", name=label + "_heightBlink")
            cmds.connectAttr(pma + ".output1D", mul + ".input1")
            cmds.connectAttr(blink, mul + ".input2")
            md = cmds.createNode("multiplyDivide", name=label + "_heightMove")
            for ax in "XYZ":
                cmds.connectAttr(mul + ".output", md + ".input1" + ax)
            # upper lid: height 1 -> stays up (moves back by half the gap); lower: height 0 -> stays down
            for ax, v in zip("XYZ", full):
                cmds.setAttr(md + ".input2" + ax, -sign * v)
            cmds.connectAttr(md + ".output", hg + ".translate")
            done += 1
    return done


def eyelids(edges, eye_ctrl, centre=None, side="L", style="cartoony", do_mirror=True):
    """The eyelid ribbon round the eye (edges: the loop round the left eye), Blink on the eye control,
    mirrored to the right eye control. Returns the ribbons."""
    edges = _edges_now(edges)              # now: the selection changes while building
    eye_ctrl = _long(eye_ctrl)
    if not eye_ctrl:
        raise RuntimeError("make the eyes first (or pick the eye control).")
    st = STYLES[style]
    name = "%s_Eyelid_Ribbon" % side
    with utils.undo_chunk("gusrigFaceEyelids"):
        srf = build_ribbon(name, edges, st["eyelid"], st["eyelid_every"], include_ends=False)
        _remember(srf, "eyelids", edges=_edge_list(edges), eye_ctrl=naming.short_name(eye_ctrl), side=side,
                  style=style, do_mirror=do_mirror)
        centre = centre or _eye_centre(eye_ctrl)
        _float(eye_ctrl, "Blink", 0.0, 0.0, 1.0)
        _float(eye_ctrl, "Blink_Height", 0.5, 0.0, 1.0)
        n = blink_setup(srf, eye_ctrl, centre)
        if not n:
            found, up, low, _p = blink_plan(srf, centre)
            utils.warn(TOOL, "Blink set no lid controls: %d control(s) on %s, %d upper / %d lower - check the edge "
                       "loop goes all round the eye." % (found, naming.short_name(srf), up, low))
        out = [srf]
        if do_mirror:
            twin = mirror(srf)
            twin_ctrl = _long(naming.mirror_name(naming.short_name(eye_ctrl), _pairs()) or "")
            if twin and twin_ctrl:
                _float(twin_ctrl, "Blink", 0.0, 0.0, 1.0)
                _float(twin_ctrl, "Blink_Height", 0.5, 0.0, 1.0)
                blink_setup(twin, twin_ctrl, [-centre[0], centre[1], centre[2]])
                out.append(twin)
    utils.info(TOOL, "eyelids: %d lid controls close on Blink (%s)." % (n, ", ".join(naming.short_name(x) for x in out)))
    return out


def _eye_centre(eye_ctrl):
    """The eye joint the control aims (its aim constraint), else the control's height and side."""
    for con in cmds.listConnections(eye_ctrl, type="aimConstraint") or []:
        for j in cmds.listConnections(con + ".constraintRotateX", source=False, destination=True) or []:
            return _pos(j)
    return _pos(eye_ctrl)


# ---------------------------------------------------------------------------
# mouth
# ---------------------------------------------------------------------------

def mouth(edges, jaw, style="cartoony", realistic_extras=None):
    """One ribbon round the lips (centre), each control following the jaw by its height. Returns the ribbon."""
    edges = _edges_now(edges)              # now: the selection changes while building
    from gus_rigtool.core import follow
    jaw = _long(jaw)
    if not jaw:
        raise RuntimeError("pick the jaw control (or joint) the lower lip follows.")
    st = STYLES[style]
    extras = style == "realistic" if realistic_extras is None else realistic_extras
    with utils.undo_chunk("gusrigFaceMouth"):
        srf = build_ribbon("Mouth_ribbon", edges, st["mouth"], st["mouth_every"], include_ends=False)
        _remember(srf, "mouth", edges=_edge_list(edges), jaw=naming.short_name(jaw), style=style,
                  realistic_extras=realistic_extras)
        try:                                                    # right half: mirror axes of the left half
            ribbon.mirror_sides(srf)
        except RuntimeError:
            pass
        ctrls = _live(controls_of(srf))
        ys = [x[3][1] for x in ctrls]
        top, bottom = max(ys), min(ys)
        mid = (top + bottom) / 2.0
        half = max((top - bottom) / 2.0, 1e-4)
        wide = max(abs(x[3][0]) for x in ctrls) or 1.0
        for _i, _o, cid, p in ctrls:
            t = max(-1.0, min(1.0, (mid - p[1]) / half))              # +1 lower lip, -1 upper lip
            corner = abs(p[0]) / wide                                   # 1 at the corners
            w = 0.5 + 0.5 * t * (1.0 - corner ** 2)
            follow.add(jaw, [utils.path(cid)], channels=("rotate", "translate"), attr_on="ctrl", weight=round(w, 3))
        if extras:
            _lip_extras(srf, ctrls, mid)
    utils.info(TOOL, "mouth: %d controls follow %s (lower lip 1, corners 0.5, upper 0)%s." % (
        len(ctrls), naming.short_name(jaw), "; lip roll and sticky lips on Mouth_ctrl" if extras else ""))
    return srf


def _lip_extras(srf, ctrls, mid):
    """Realistic: Mouth_ctrl with upper_roll / lower_roll (the lip controls turn) and sticky (each upper control
    and the lower one under it meet half way). ctrls: [(index, offset uuid, control uuid, position)]."""
    from gus_rigtool.builder import controls as BC
    pts = [x[3] for x in ctrls]
    centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
    width = max(abs(p[0]) for p in pts) or 1.0
    _mo, main = BC.make("C", "Mouth", "rectangle", width * 0.4, _t([0.0, centre[1], centre[2] + width * 0.6]),
                        group(), "Z", mirror=None)
    up_roll = _float(main, "upper_roll", 0.0)
    low_roll = _float(main, "lower_roll", 0.0)
    sticky = _float(main, "sticky", 0.0, 0.0, 1.0)
    upper = [x for x in ctrls if x[3][1] >= mid]
    lower = [x for x in ctrls if x[3][1] < mid]
    for x in upper + lower:
        roll = driven_group(utils.path(x[2]), "_roll")
        cmds.connectAttr(up_roll if x in upper else low_roll, roll + ".rotateX")
    for me, others in [(x, lower) for x in upper] + [(x, upper) for x in lower]:
        them = _nearest_by_x(me, others)                         # each control: the one across the mouth
        if not them:
            continue
        zip_ = driven_group(utils.path(me[2]), "_sticky")
        local = _local_vector(cmds.listRelatives(zip_, parent=True, fullPath=True)[0],
                              [g * 0.5 for g in _sub(them[3], me[3])])
        md = cmds.createNode("multiplyDivide", name=naming.short_name(utils.path(me[2])) + "_stickyMove")
        for ax in "XYZ":
            cmds.connectAttr(sticky, md + ".input1" + ax)
        for ax, v in zip("XYZ", local):
            cmds.setAttr(md + ".input2" + ax, v)
        cmds.connectAttr(md + ".output", zip_ + ".translate")
    return main


# ---------------------------------------------------------------------------
# facial strips, brows
# ---------------------------------------------------------------------------

def facial(edges, name="facial", side="L", style="cartoony", do_mirror=True):
    """A strip of the face (cheek, nasolabial line, round the eye) as a ribbon with controls; mirrored."""
    edges = _edges_now(edges)              # now: the selection changes while building
    st = STYLES[style]
    with utils.undo_chunk("gusrigFaceStrip"):
        srf = build_ribbon("%s_%s_Ribbon" % (side, name), edges, st["strip"], st["strip_every"], include_ends=True)
        _remember(srf, "facial", edges=_edge_list(edges), name=name, side=side, style=style, do_mirror=do_mirror)
        out = [srf]
        if do_mirror:
            twin = mirror(srf)
            if twin:
                out.append(twin)
    utils.info(TOOL, "%s: %s." % (name, ", ".join(naming.short_name(x) for x in out)))
    return out


def brows(edges, side="L", count=3, style="cartoony", do_mirror=True):
    """A ribbon along the brow with count controls, under L_Brow_main_ctrl, under Brows_ctrl - a plain
    hierarchy (moving a parent moves its children; nothing pins them)."""
    edges = _edges_now(edges)              # now: the selection changes while building
    from gus_rigtool.builder import controls as BC
    with utils.undo_chunk("gusrigFaceBrows"):
        srf = build_ribbon("%s_Brow_Ribbon" % side, edges, max(count * 3, 9), 3, include_ends=True)
        _remember(srf, "brows", edges=_edge_list(edges), side=side, count=count, style=style, do_mirror=do_mirror)
        made = [srf]
        if do_mirror:
            twin = mirror(srf)
            if twin:
                made.append(twin)
        g = group()
        all_pts = [_pos(c) for s in made for _i, _o, c in controls_of(s)]
        top = max(p[1] for p in all_pts)
        z = max(p[2] for p in all_pts)
        size = max(abs(p[0]) for p in all_pts) or 1.0
        from gus_rigtool.builder import names
        brows_ctrl = _long(names.make("C", "Brows", "ctrl"))
        if not brows_ctrl:
            brows_off, brows_ctrl = BC.make("C", "Brows", "rectangle", size * 0.5,
                                            _t([0.0, top + size * 0.25, z]), g, "Z", mirror=None)
        for s in made:
            ctrls = controls_of(s)
            pts = [_pos(c) for _i, _o, c in ctrls]
            sd = "L" if sum(p[0] for p in pts) >= 0 else "R"
            mid = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            _mo, main = BC.make(sd, "Brow_main", "rectangle", size * 0.25,
                                _t([mid[0], mid[1] + size * 0.12, mid[2]]), brows_ctrl, "Z", mirror=None)
            for _i, off, _c in ctrls:
                cmds.parent(off, main)
    utils.info(TOOL, "brows: Brows_ctrl > L / R_Brow_main_ctrl > the brow controls (plain hierarchy).")
    return made
