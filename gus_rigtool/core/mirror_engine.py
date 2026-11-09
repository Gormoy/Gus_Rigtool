"""
The one mirror engine of Gus_Rigtool, used by the Mirror tab, the Ribbon, the shelf and
(later) the modular builds.

Matrices are plain lists of 16 numbers in Maya's layout (row vectors: the last row is the
position), so the maths works without Maya and is the same everywhere.

Styles (how a twin's axes relate to the source's):
    'true'     : the reflection itself (determinant -1, Maya shows a -1 scale). The same
                 translate and rotate values move both sides as mirror images.
    'behavior' : the reflection with all three axes turned round (no -1 scale). The same
                 rotate values mirror, translate values are opposite.
    'same'     : same axes as the source, only the position is reflected.

Pose: mirror_pose / flip_pose / reset_pose work with any style, because they compare each
pair at rest (controls at 0, joints with rotate 0) instead of guessing from the style.
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, sides, utils
from gus_rigtool.core import nodes as _nodes

TOOL = "Mirror"
STYLE_ATTR = "rtMirrorStyle"
STYLES = ("true", "behavior", "same", "baked")
ORDERS = [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (1, 0, 2), (2, 1, 0)]   # Maya rotateOrder enum
EPS = 1e-9

IDENTITY = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
NEG = [-1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


# ===========================================================================
# 4x4 maths (plain lists, Maya layout)
# ===========================================================================

def mul(a, b):
    """a * b (Maya order: a is applied first)."""
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def inverse(m):
    """Inverse of a 4x4 matrix (Gauss-Jordan)."""
    a = [list(m[r * 4:r * 4 + 4]) + [1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("matrix cannot be inverted")
        a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col]
        a[col] = [v / p for v in a[col]]
        for r in range(4):
            if r != col and a[r][col]:
                f = a[r][col]
                a[r] = [v - f * w for v, w in zip(a[r], a[col])]
    return [a[r][4 + c] for r in range(4) for c in range(4)]


def reflection(axis, center=(0.0, 0.0, 0.0)):
    """Reflection across the plane perpendicular to axis (0 X, 1 Y, 2 Z), through center."""
    m = list(IDENTITY)
    m[axis * 4 + axis] = -1.0
    m[12 + axis] = 2.0 * center[axis]
    return m


def mirror_list(m, style="true", axis=0, center=(0.0, 0.0, 0.0)):
    """The other side's world matrix for world matrix m, in a mirror style."""
    refl = reflection(axis, center)
    out = mul(list(m), refl)
    if style == "behavior":
        return mul(NEG, out)
    if style in ("same", "baked"):
        same = list(m)
        same[12:15] = out[12:15]
        return same
    return out


def mirror_mmatrix(world, style, axis=0, center=(0.0, 0.0, 0.0)):
    """mirror_list for an OpenMaya MMatrix (returns an MMatrix)."""
    import maya.api.OpenMaya as om
    vals = [world.getElement(r, c) for r in range(4) for c in range(4)]
    return om.MMatrix(mirror_list(vals, style, axis, center))


def reflect_point(p, axis, center=(0.0, 0.0, 0.0)):
    p = list(p)
    p[axis] = 2.0 * center[axis] - p[axis]
    return p


# ---------------------------------------------------------------- euler / channels

def _axis_rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    m = list(IDENTITY)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m[i * 4 + i], m[i * 4 + j], m[j * 4 + i], m[j * 4 + j] = c, s, -s, c
    return m


def euler_matrix(r, order=0):
    """Rotation matrix of rotate values (degrees) in a Maya rotate order."""
    i, j, k = ORDERS[order]
    return mul(mul(_axis_rot(i, r[i]), _axis_rot(j, r[j])), _axis_rot(k, r[k]))


def matrix_euler(m, order=0):
    """Rotate values (degrees) of a pure rotation matrix, in a Maya rotate order."""
    i, j, k = ORDERS[order]
    par = 1.0 if (i, j, k) in ORDERS[:3] else -1.0
    n = [[m[c * 4 + r] for c in range(3)] for r in range(3)]        # transposed
    sb = max(-1.0, min(1.0, -par * n[k][i]))
    b = math.asin(sb)
    if abs(math.cos(b)) > 1e-6:
        a = math.atan2(par * n[k][j], n[k][k])
        c = math.atan2(par * n[j][i], n[i][i])
    else:                                                            # gimbal: put it all in a
        a = math.atan2(-par * n[j][k], n[j][j])
        c = 0.0
    out = [0.0, 0.0, 0.0]
    out[i], out[j], out[k] = math.degrees(a), math.degrees(b), math.degrees(c)
    return out


def compose(t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1), order=0, jo=None):
    """Local matrix S * R * (JO) * T, like Maya builds it (pivots ignored)."""
    m = [s[0], 0, 0, 0, 0, s[1], 0, 0, 0, 0, s[2], 0, 0, 0, 0, 1.0]
    m = mul(m, euler_matrix(r, order))
    if jo is not None:
        m = mul(m, euler_matrix(jo, 0))
    m[12:15] = [float(v) for v in t]
    return m


def decompose(m, order=0, jo=None):
    """(t, r, s) channels of a local matrix (the inverse of compose)."""
    t = list(m[12:15])
    rs = list(m)
    rs[12:15] = [0.0, 0.0, 0.0]
    if jo is not None:
        rs = mul(rs, inverse(euler_matrix(jo, 0)))
    rows = [rs[r * 4:r * 4 + 3] for r in range(3)]
    s = [math.sqrt(sum(v * v for v in row)) or 1.0 for row in rows]
    rows = [[v / sc for v in row] for row, sc in zip(rows, s)]
    det = (rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
           - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
           + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0]))
    if det < 0:
        s[0] = -s[0]
        rows[0] = [-v for v in rows[0]]
    rot = list(IDENTITY)
    for r in range(3):
        rot[r * 4:r * 4 + 3] = rows[r]
    return t, matrix_euler(rot, order), s


# ===========================================================================
# styles remembered on the nodes
# ===========================================================================

def tag_style(nodes, style):
    """Remember the mirror style on twins (a hidden string attribute)."""
    for node in nodes:
        if not node or not cmds.objExists(node):
            continue
        try:
            if not cmds.attributeQuery(STYLE_ATTR, node=node, exists=True):
                cmds.addAttr(node, longName=STYLE_ATTR, dataType="string", hidden=True)
            cmds.setAttr(node + "." + STYLE_ATTR, style, type="string")
        except RuntimeError:
            pass


def style_of(node):
    try:
        if cmds.attributeQuery(STYLE_ATTR, node=node, exists=True):
            return cmds.getAttr(node + "." + STYLE_ATTR) or None
    except RuntimeError:
        pass
    return None


# ===========================================================================
# twins
# ===========================================================================

def plane():
    """(axis, center) from the Mirror tab's settings."""
    s = sides.mirror_settings()
    axis = [0, 1, 2][int(s.get("plane", 1)) - 1]
    center = s.get("center", [0.0, 0.0, 0.0]) if int(s.get("center_mode", 1)) == 2 else [0.0, 0.0, 0.0]
    return axis, list(center)


def twin_of(node, pairs=None):
    """The other side of node: its linked twin, else the node with the mirrored name. Or None.
    A link that disagrees with an existing mirrored name loses to the name (sides.checked_twin)."""
    return sides.checked_twin(node, pairs)[0]


def side_of(node, pairs=None):
    axis, center = plane()
    return sides.side_of_node(node, pairs or sides.default_pairs(), axis, center)


def link(a, b, style=None):
    sides.link(a, b)
    if style:
        tag_style([a, b], style)


def unlink(node):
    """Break the twin link of node (both ways)."""
    twin = sides.get_twin(node)
    for n in [node, twin]:
        if n and cmds.attributeQuery(sides.TWIN_ATTR, node=n, exists=True):
            for src in cmds.listConnections(n + "." + sides.TWIN_ATTR, source=True, destination=False,
                                            plugs=True) or []:
                try:
                    cmds.disconnectAttr(src, n + "." + sides.TWIN_ATTR)
                except RuntimeError:
                    pass
    return twin


def is_poseable(node):
    """Controls (curve shapes) and joints: the things that hold a pose."""
    if cmds.nodeType(node) == "joint":
        return True
    if cmds.attributeQuery("gusRole", node=node, exists=True):     # a builder guide holds a position, not a pose
        return False
    return bool(cmds.listRelatives(node, shapes=True, type="nurbsCurve") or [])


def list_twins(nodes):
    """[(node, twin or None, style or '')] for the poseable nodes, each pair once."""
    out, seen = [], set()
    pairs = sides.default_pairs()
    for n in nodes:
        if n in seen or not is_poseable(n):
            continue
        twin = twin_of(n, pairs)
        seen.add(n)
        if twin:
            seen.add(twin)
            if side_of(n, pairs) == "R" and side_of(twin, pairs) == "L":
                n, twin = twin, n
        elif naming.side_of(n, pairs) == "C" and side_of(n, pairs) == "C":
            continue                                    # centre: no twin expected
        out.append((n, twin, style_of(twin or n) or style_of(n) or ""))
    return out


# ===========================================================================
# pose
# ===========================================================================

_T = ["translateX", "translateY", "translateZ"]
_R = ["rotateX", "rotateY", "rotateZ"]
_S = ["scaleX", "scaleY", "scaleZ"]


def _get3(node, attrs):
    return [cmds.getAttr("%s.%s" % (node, a)) for a in attrs]


_settable = utils.settable


_parent = _nodes.parent_of


def _jo(node):
    if cmds.nodeType(node) == "joint":
        return _get3(node, ["jointOrientX", "jointOrientY", "jointOrientZ"])
    return None


def local_now(node):
    """Local matrix from the channels (pivots ignored)."""
    return compose(_get3(node, _T), _get3(node, _R), _get3(node, _S),
                   cmds.getAttr(node + ".rotateOrder"), _jo(node))


def local_rest(node):
    """Local matrix at rest: controls at 0 (scale 1); joints with rotate 0; other nodes as they are."""
    if cmds.nodeType(node) == "joint":
        return compose(_get3(node, _T), (0, 0, 0), _get3(node, _S), 0, _jo(node))
    if is_poseable(node):
        return list(IDENTITY)
    return list(cmds.getAttr(node + ".matrix"))


def world_rest(node):
    """World matrix of node with every control / joint above it (and itself) at rest."""
    m = local_rest(node)
    p = _parent(node)
    while p:
        m = mul(m, local_rest(p))
        p = _parent(p)
    return m


def pose_target(src, dst, axis, center):
    """(t, r, s) for dst so it holds the mirror of src's pose (any mirror style)."""
    q = mul(mul(world_rest(src), reflection(axis, center)), inverse(world_rest(dst)))
    delta = mul(local_now(src), inverse(local_rest(src)))
    delta_dst = mul(mul(inverse(q), delta), q)
    local = mul(delta_dst, local_rest(dst))
    return decompose(local, cmds.getAttr(dst + ".rotateOrder"), _jo(dst))


def _custom_values(node):
    out = {}
    for attr in cmds.listAttr(node, keyable=True, userDefined=True) or []:
        try:
            if cmds.getAttr("%s.%s" % (node, attr), type=True) in ("double", "float", "long", "short",
                                                                     "bool", "enum", "doubleLinear",
                                                                     "doubleAngle", "byte"):
                out[attr] = cmds.getAttr("%s.%s" % (node, attr))
        except (RuntimeError, ValueError):
            pass
    return out


def _apply(dst, trs, custom):
    t, r, s = trs
    for attrs, values in ((_T, t), (_R, r), (_S, s)):
        for a, v in zip(attrs, values):
            plug = "%s.%s" % (dst, a)
            if abs(v) < 1e-6:
                v = 0.0
            if _settable(plug) and abs(cmds.getAttr(plug) - v) > 1e-7:
                cmds.setAttr(plug, v)
    for attr, v in (custom or {}).items():
        plug = "%s.%s" % (dst, attr)
        if cmds.objExists(plug) and _settable(plug):
            try:
                cmds.setAttr(plug, v)
            except RuntimeError:
                pass


def _pose_selection():
    sel = [n for n in utils.selected_transforms(ordered=True) if is_poseable(n)]
    if not sel:
        raise RuntimeError("select controls or joints first.")
    return sel


def _pairs_for(sel, direction, include_centre):
    """[(src, dst)] to mirror. direction: 'auto', 'L>R' or 'R>L'."""
    pairs = sides.default_pairs()
    selected = set(sel)
    out, done, missing = [], set(), []
    for n in sel:
        twin = twin_of(n, pairs)
        if twin is None:
            if include_centre and side_of(n, pairs) == "C":
                out.append((n, n))
            else:
                missing.append(n)
            continue
        side = side_of(n, pairs)
        if direction == "L>R":
            src = n if side == "L" else twin
        elif direction == "R>L":
            src = n if side == "R" else twin
        elif twin in selected:
            src = n if side == "L" else twin           # both sides selected: left wins
        else:
            src = n
        dst = twin if src == n else n
        if dst not in done:
            done.add(dst)
            out.append((src, dst))
    return out, missing


def _report(what, count, missing):
    msg = "%s %d control(s)." % (what, count)
    if missing:
        msg += " No twin for %d: %s" % (len(missing), ", ".join(naming.short_name(m) for m in missing[:4]))
        utils.warn(TOOL, msg)
    else:
        utils.info(TOOL, msg)


def _pose_options(include_centre, custom):
    s = sides.mirror_settings()
    if include_centre is None:
        include_centre = s.get("pose_centre", True)
    if custom is None:
        custom = s.get("pose_custom", True)
    return include_centre, custom


def mirror_pose(direction="auto", include_centre=None, custom=None):
    """Copy the pose of the selected controls to their twins, mirrored."""
    include_centre, custom = _pose_options(include_centre, custom)
    sel = _pose_selection()
    axis, center = plane()
    jobs, missing = _pairs_for(sel, direction, include_centre)
    results = [(dst, pose_target(src, dst, axis, center), _custom_values(src) if custom else {})
               for src, dst in jobs]
    with utils.undo_chunk("gusrigMirrorPose"):
        for dst, trs, values in results:
            _apply(dst, trs, values)
    _report("mirrored the pose of" if direction == "auto" else "mirrored (%s) the pose of" % direction.replace(">", " -> "),
            len(results), missing)


def _flip_jobs(sel, include_centre):
    pairs = sides.default_pairs()
    jobs, seen, missing = [], set(), []
    for n in sel:
        if n in seen:
            continue
        twin = twin_of(n, pairs)
        if twin:
            seen.update([n, twin])
            jobs += [(n, twin), (twin, n)]
        elif include_centre and side_of(n, pairs) == "C":
            seen.add(n)
            jobs.append((n, n))
        else:
            missing.append(n)
    return jobs, missing


def flip_pose(include_centre=None, custom=None):
    """Swap the poses of the two sides (and flip centre controls onto themselves)."""
    include_centre, custom = _pose_options(include_centre, custom)
    sel = _pose_selection()
    axis, center = plane()
    jobs, missing = _flip_jobs(sel, include_centre)
    results = [(dst, pose_target(src, dst, axis, center), _custom_values(src) if custom else {})
               for src, dst in jobs]                     # all read before anything changes
    with utils.undo_chunk("gusrigFlipPose"):
        for dst, trs, values in results:
            _apply(dst, trs, values)
    _report("flipped the pose of", len(results), missing)


# ---------------------------------------------------------------------------
# animation: mirror / flip every key (or frame) in a range, with a time offset
# ---------------------------------------------------------------------------

def playback_range():
    return (int(cmds.playbackOptions(query=True, minTime=True)), int(cmds.playbackOptions(query=True, maxTime=True)))


def out_time(f, start, end, offset, wrap):
    """Where a frame lands: f + offset, wrapped inside start..end for cycles."""
    t = f + offset
    length = end - start
    if wrap and length > 0:
        t = start + ((t - start) % length)
    return t


def _frames(sources, start, end, keys_only):
    if not keys_only:
        return list(range(int(start), int(end) + 1))
    keys = cmds.keyframe(sources, query=True, time=(start, end), timeChange=True) or []
    return sorted(set([float(start), float(end)] + [float(k) for k in keys]))


def bake_mirror(jobs, target, custom_of, start, end, offset=0, keys_only=True, wrap=False):
    """jobs [(src, dst)]: dst gets keys of target(src, dst) for every src frame, at the frame + offset.
    Everything is read first, then the old keys of dst in the range are replaced. Returns keys set."""
    sources = sorted(set(s for s, _d in jobs))
    frames = _frames(sources, start, end, keys_only)
    if wrap and end > start:
        frames = [f for f in frames if f < end]         # a cycle: the last frame is the first one again
        lands_on_start = start + ((-offset) % (end - start))
        frames = sorted(set(frames + [float(lands_on_start)]))     # so the cycle has a key at both ends
    now = cmds.currentTime(query=True)
    data = []
    try:
        for f in frames:
            cmds.currentTime(f, update=True)
            for src, dst in jobs:
                data.append((dst, out_time(f, start, end, offset, wrap), target(src, dst), custom_of(src)))
    finally:
        cmds.currentTime(now, update=True)
    if wrap and end > start:                             # close the cycle: the last frame = the first
        data += [(d, end, trs, values) for d, t, trs, values in data if abs(t - start) < 1e-6]
    lo, hi = (start, end) if wrap else (start + offset, end + offset)
    count = 0
    dsts = sorted(set(d for _s, d in jobs))
    for d in dsts:
        try:
            cmds.cutKey(d, time=(lo, hi), clear=True)
        except RuntimeError:
            pass
    for dst, t, trs, values in data:
        for attrs, vals in zip((_T, _R, _S), trs):
            for a, v in zip(attrs, vals):
                plug = "%s.%s" % (dst, a)
                if _settable(plug):
                    cmds.setKeyframe(dst, attribute=a, time=t, value=0.0 if abs(v) < 1e-6 else v)
                    count += 1
        for a, v in (values or {}).items():
            plug = "%s.%s" % (dst, a)
            if cmds.objExists(plug) and _settable(plug):
                cmds.setKeyframe(dst, attribute=a, time=t, value=v)
                count += 1
    curves = cmds.listConnections([d + "." + a for d in dsts for a in _R], source=True, destination=False,
                                  type="animCurve") or []
    if curves:
        try:
            cmds.filterCurve(curves, filter="euler")          # no flips between keys
        except RuntimeError:
            pass
    return count


def mirror_animation(mode="L>R", start=None, end=None, offset=0, keys_only=True, wrap=False,
                     include_centre=None, custom=None):
    """mode: 'L>R', 'R>L', 'auto' (like Mirror pose) or 'flip'. The selected controls (and twins)."""
    include_centre, custom = _pose_options(include_centre, custom)
    sel = _pose_selection()
    if start is None or end is None:
        start, end = playback_range()
    if end < start:
        raise RuntimeError("the end frame is before the start frame.")
    axis, center = plane()
    if mode == "flip":
        jobs, missing = _flip_jobs(sel, include_centre)
    else:
        jobs, missing = _pairs_for(sel, mode, include_centre)
    if not jobs:
        raise RuntimeError("nothing to mirror (no twins in the selection).")
    with utils.undo_chunk("gusrigMirrorAnim"):
        keys = bake_mirror(jobs, lambda s, d: pose_target(s, d, axis, center),
                           (lambda s: _custom_values(s)) if custom else (lambda s: {}),
                           start, end, offset, keys_only, wrap)
    _report("%s the animation (%g-%g%s) of" % ("flipped" if mode == "flip" else "mirrored", start, end,
                                              ", offset %g" % offset if offset else ""), len(jobs), missing)
    return keys


def _published_pose(node):
    try:
        if cmds.attributeQuery("gusDefaultPose", node=node, exists=True):
            return json.loads(cmds.getAttr(node + ".gusDefaultPose") or "{}")
    except (RuntimeError, ValueError):
        pass
    return {}


def reset_pose(both=True, custom=None):
    """Selected controls (and their twins) back to rest: translate / rotate 0, scale 1."""
    custom = _pose_options(True, custom)[1]
    sel = _pose_selection()
    nodes = list(sel)
    if both:
        for n in sel:
            twin = twin_of(n)
            if twin and twin not in nodes:
                nodes.append(twin)
    with utils.undo_chunk("gusrigResetPose"):
        for n in nodes:
            saved = _published_pose(n)
            trs = ((cmds.getAttr(n + ".translate")[0] if cmds.nodeType(n) == "joint" else (0, 0, 0)),
                   (0, 0, 0), (1, 1, 1))
            if saved:                                    # the pose saved by Publish
                trs = tuple(tuple(saved.get(a + ax, d[i]) for i, ax in enumerate("XYZ"))
                            for a, d in zip(("translate", "rotate", "scale"), trs))
            defaults = {}
            if custom:
                for attr in _custom_values(n):
                    d = [saved[attr]] if attr in saved else cmds.attributeQuery(attr, node=n, listDefault=True)
                    if d:
                        defaults[attr] = d[0]
            _apply(n, trs, defaults)
    utils.info(TOOL, "reset %d control(s)%s." % (len(nodes), " (both sides)" if both else ""))


def select_twins(mode="other"):
    """mode 'other': select the other side; 'both': both sides; 'add': add the other side."""
    sel = utils.selected_transforms(ordered=True)
    if not sel:
        raise RuntimeError("select something first.")
    twins, missing = [], []
    for n in sel:
        t = twin_of(n)
        if t:
            twins.append(t)
        else:
            missing.append(n)
    if mode == "other":
        result = twins + missing          # centre / unmatched stay selected
    else:
        result = sel + [t for t in twins if t not in sel]
    cmds.select(result, replace=True)
    msg = "selected %d twin(s)" % len(twins)
    if missing:
        msg += "; no twin for %d (kept selected): %s" % (len(missing),
                                                         ", ".join(naming.short_name(m) for m in missing[:4]))
    utils.info(TOOL, msg + ".")


# ===========================================================================
# live follow: one side follows the other, mirrored, through Maya matrix nodes
# ===========================================================================

FOLLOW_ATTR = "rtFollowOf"


def _set_matrix(plug, m):
    cmds.setAttr(plug, *m, type="matrix")


def _free(plug):
    """Can a connection go into this plug (unlocked, nothing connected yet)?"""
    try:
        return (not cmds.getAttr(plug, lock=True)
                and not cmds.listConnections(plug, source=True, destination=False))
    except (RuntimeError, ValueError):
        return False


def follow_nodes(node=None):
    """The live-follow nodes of node (or of the whole scene)."""
    out = []
    for n in cmds.ls(type=("multMatrix", "decomposeMatrix"), long=True) or []:
        try:
            if cmds.attributeQuery(FOLLOW_ATTR, node=n, exists=True):
                if node is None or cmds.getAttr(n + "." + FOLLOW_ATTR) == naming.short_name(node):
                    out.append(n)
        except RuntimeError:
            pass
    return out


def follow_pair(src, dst, axis, center):
    """dst follows src, mirrored (any style), until follow_off. Returns the nodes made."""
    q = mul(mul(world_rest(src), reflection(axis, center)), inverse(world_rest(dst)))
    after = mul(mul(inverse(local_rest(src)), q), local_rest(dst))
    short = naming.short_name(dst)
    made = []

    mm = cmds.createNode("multMatrix", name=short + "_follow_mm")
    _set_matrix(mm + ".matrixIn[0]", inverse(q))
    cmds.connectAttr(src + ".matrix", mm + ".matrixIn[1]")
    _set_matrix(mm + ".matrixIn[2]", after)
    made.append(mm)

    dm = cmds.createNode("decomposeMatrix", name=short + "_follow_dm")
    cmds.connectAttr(mm + ".matrixSum", dm + ".inputMatrix")
    made.append(dm)
    rot_dm = dm
    jo = _jo(dst)
    if jo is not None:
        # a joint's local matrix holds its joint orient after the rotation: take it out for rotate
        mm2 = cmds.createNode("multMatrix", name=short + "_follow_jo_mm")
        cmds.connectAttr(mm + ".matrixSum", mm2 + ".matrixIn[0]")
        _set_matrix(mm2 + ".matrixIn[1]", inverse(euler_matrix(jo, 0)))
        rot_dm = cmds.createNode("decomposeMatrix", name=short + "_follow_jo_dm")
        cmds.connectAttr(mm2 + ".matrixSum", rot_dm + ".inputMatrix")
        made += [mm2, rot_dm]
    for d in set([dm, rot_dm]):
        try:
            cmds.connectAttr(dst + ".rotateOrder", d + ".inputRotateOrder")
        except RuntimeError:
            pass

    for out, attr, d in (("outputTranslate", "translate", dm), ("outputRotate", "rotate", rot_dm),
                         ("outputScale", "scale", rot_dm)):
        for axis_name in "XYZ":
            plug = "%s.%s%s" % (dst, attr, axis_name)
            if _free(plug):
                cmds.connectAttr("%s.%s%s" % (d, out, axis_name), plug)
    customs = []
    for attr in _custom_values(src):                  # custom attributes: same values
        plug = "%s.%s" % (dst, attr)
        if cmds.objExists(plug) and _free(plug):
            try:
                cmds.connectAttr("%s.%s" % (src, attr), plug)
                customs.append(attr)
            except RuntimeError:
                pass

    for n in made:
        cmds.addAttr(n, longName=FOLLOW_ATTR, dataType="string")
        cmds.setAttr(n + "." + FOLLOW_ATTR, short, type="string")
    cmds.addAttr(mm, longName="rtFollowAttrs", dataType="string")
    cmds.setAttr(mm + ".rtFollowAttrs", " ".join(customs), type="string")
    return made


def _unfollow(node):
    """Stop node following: its pose stays as it is now. Returns True if it was following."""
    nodes = follow_nodes(node)
    if not nodes:
        return False
    values = {a: cmds.getAttr(node + "." + a) for a in _T + _R + _S}
    for n in nodes:                                   # custom attributes linked by the follow
        if cmds.attributeQuery("rtFollowAttrs", node=n, exists=True):
            for attr in (cmds.getAttr(n + ".rtFollowAttrs") or "").split():
                plug = node + "." + attr
                for src in cmds.listConnections(plug, source=True, destination=False, plugs=True) or []:
                    try:
                        cmds.disconnectAttr(src, plug)
                    except RuntimeError:
                        pass
    cmds.delete(nodes)
    for a, v in values.items():
        plug = node + "." + a
        if _settable(plug):
            cmds.setAttr(plug, v)
    return True


def follow_on(direction="L>R"):
    """The other side of the selected controls follows them live, mirrored. direction 'L>R' or 'R>L'."""
    sel = _pose_selection()
    axis, center = plane()
    jobs, missing = _pairs_for(sel, direction, include_centre=False)
    jobs = [(s, d) for s, d in jobs if s != d]
    with utils.undo_chunk("gusrigFollowOn"):
        for src, dst in jobs:
            _unfollow(dst)
            _unfollow(src)                            # never both ways at once
            dst_trs = pose_target(src, dst, axis, center)
            _apply(dst, dst_trs, {})                  # starts where it will be
            follow_pair(src, dst, axis, center)
    _report("live follow on (%s) for" % direction.replace(">", " -> "), len(jobs), missing)


def follow_off(scope="selection"):
    """Stop live follow on the selection (and their twins), or on the whole scene."""
    if scope == "all":
        names = sorted(set(cmds.getAttr(n + "." + FOLLOW_ATTR) for n in follow_nodes()))
        targets = []
        for name in names:
            found = cmds.ls(name, long=True) or []
            if found:
                targets.append(found[0])
    else:
        sel = _pose_selection()
        targets = list(sel)
        for n in sel:
            t = twin_of(n)
            if t and t not in targets:
                targets.append(t)
    count = 0
    with utils.undo_chunk("gusrigFollowOff"):
        for t in targets:
            if _unfollow(t):
                count += 1
    utils.info(TOOL, "live follow off for %d control(s)%s." % (count, " (whole scene)" if scope == "all" else ""))
