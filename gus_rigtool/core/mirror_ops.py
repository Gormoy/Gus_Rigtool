"""
Mirror operations (split out of tools/mirror_tool in 4.2.0): the maths and scene work behind the Mirror tool's
Shapes / Full control / Joints / Geometry modes. tools/mirror_tool still has every name.
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import colors, curves, geo, naming, sides, skin, utils
from gus_rigtool.core import nodes as _nodes
from gus_rigtool.core import mirror_engine as engine

TOOL = "Mirror"

MODES = ["Shapes", "Full control", "Joints", "Geometry"]
GEO_ORIENT = ["Baked", "True mirror", "Behavior", "Same orientation"]
UNGROUPED = ["Baked", "Add offset groups", "Like grouped"]
CTRL_ORIENT = ["True mirror", "Behavior", "Same orientation"]
JNT_ORIENT = ["Behavior", "Orientation"]
PLANES = [("YZ (across X)", 0), ("XZ (across Y)", 1), ("XY (across Z)", 2)]
PARENT_RULES = ["Mirrored parent, else same parent", "Same parent as source", "World"]
PRESETS = [
    ("L_  /  R_", "L_", "R_"),
    ("_L  /  _R", "_L", "_R"),
    ("l_  /  r_", "l_", "r_"),
    ("Left  /  Right", "Left", "Right"),
    ("Custom", None, None),
]

EPS = 1e-6


# ===========================================================================
# matrix helpers
# ===========================================================================

def _m(node):
    return om.MMatrix(cmds.getAttr(node + ".worldMatrix[0]"))


def _vals(m):
    return [m.getElement(r, c) for r in range(4) for c in range(4)]


def reflection(axis, center):
    """The mirror plane, for mirror_matrix (the maths lives in core.mirror_engine)."""
    return (axis, list(center))


def mirror_matrix(world, mode, refl):
    """
    Target world matrix of the other side (an MMatrix), from the shared mirror engine.
    mode: 'true'     - reflected (determinant -1: Maya shows a negative scale)
          'behavior' - reflected, then all three axes flipped (a clean rotation)
          'same'     - same axes as the source, reflected position
    """
    return engine.mirror_mmatrix(world, mode, refl[0], refl[1])


def _rot_only(m):
    return om.MTransformationMatrix(m).rotation(asQuaternion=True).asMatrix()


def _euler(values, order=0):
    import math
    r = [math.radians(x) for x in values]
    return om.MEulerRotation(r[0], r[1], r[2], order).asMatrix()


def _to_deg_xyz(m):
    import math
    e = om.MTransformationMatrix(m).rotation()
    return [math.degrees(e.x), math.degrees(e.y), math.degrees(e.z)]


reflect_point = engine.reflect_point


# ===========================================================================
# scene helpers
# ===========================================================================

_parent = _nodes.parent_of


def _find(name):
    """Long names of nodes called name (namespaces included)."""
    if not name:
        return []
    return cmds.ls(name, long=True) or []


def _child_transforms(node):
    kids = cmds.listRelatives(node, children=True, fullPath=True, type="transform") or []
    return [k for k in kids if not cmds.objectType(k, isAType="constraint")]


_settable = utils.settable


def _set3(node, attr, values):
    for axis, v in zip("XYZ", values):
        plug = "%s.%s%s" % (node, attr, axis)
        if _settable(plug):
            cmds.setAttr(plug, v)


def _round_tiny(node, attrs=("translate", "rotate", "jointOrient")):
    for attr in attrs:
        if not cmds.attributeQuery(attr, node=node, exists=True):
            continue
        for axis in "XYZ":
            plug = "%s.%s%s" % (node, attr, axis)
            try:
                if abs(cmds.getAttr(plug)) < 1e-5 and _settable(plug):
                    cmds.setAttr(plug, 0.0)
            except (RuntimeError, ValueError):
                pass


# ===========================================================================
# options
# ===========================================================================

def _pairs(o):
    pairs = [(o["search"], o["replace"])]
    if o["search2"] and o["replace2"]:
        pairs.append((o["search2"], o["replace2"]))
    return pairs


def _plane(o):
    axis = PLANES[o["plane"] - 1][1]
    center = o["center"] if o["center_mode"] == 2 else [0.0, 0.0, 0.0]
    return axis, center


def _ordered(nodes):
    """Unique, parents before children."""
    seen, out = set(), []
    for n in sorted(nodes, key=lambda x: x.count("|")):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


# ===========================================================================
# attributes
# ===========================================================================

_NUMERIC = ("double", "float", "long", "short", "bool", "byte", "doubleLinear", "doubleAngle")
_CHANNELS = [a + x for a in ("translate", "rotate", "scale") for x in "XYZ"] + ["visibility"]


def copy_user_attrs(src, dst):
    for attr in cmds.listAttr(src, userDefined=True) or []:
        try:
            if (cmds.attributeQuery(attr, node=src, multi=True)
                    or cmds.attributeQuery(attr, node=src, listChildren=True)
                    or cmds.attributeQuery(attr, node=src, listParent=True)):
                continue
            plug = src + "." + attr
            atype = cmds.getAttr(plug, type=True)
            if not cmds.attributeQuery(attr, node=dst, exists=True):
                if atype == "string":
                    cmds.addAttr(dst, longName=attr, dataType="string")
                elif atype == "enum":
                    names = cmds.attributeQuery(attr, node=src, listEnum=True)[0]
                    cmds.addAttr(dst, longName=attr, attributeType="enum", enumName=names)
                elif atype in _NUMERIC:
                    kw = {"longName": attr, "attributeType": atype}
                    if cmds.attributeQuery(attr, node=src, minExists=True):
                        kw["minValue"] = cmds.attributeQuery(attr, node=src, minimum=True)[0]
                    if cmds.attributeQuery(attr, node=src, maxExists=True):
                        kw["maxValue"] = cmds.attributeQuery(attr, node=src, maximum=True)[0]
                    default = cmds.attributeQuery(attr, node=src, listDefault=True)
                    if default:
                        kw["defaultValue"] = default[0]
                    cmds.addAttr(dst, **kw)
                else:
                    continue
                keyable = cmds.getAttr(plug, keyable=True)
                cmds.setAttr(dst + "." + attr, keyable=keyable)
                if not keyable:
                    cmds.setAttr(dst + "." + attr, channelBox=cmds.getAttr(plug, channelBox=True))
            dplug = dst + "." + attr
            if _settable(dplug):
                value = cmds.getAttr(plug)
                if atype == "string":
                    cmds.setAttr(dplug, value or "", type="string")
                else:
                    cmds.setAttr(dplug, value)
            cmds.setAttr(dplug, lock=cmds.getAttr(plug, lock=True))
        except (RuntimeError, ValueError, TypeError) as e:
            utils.warn(TOOL, "could not copy attribute '%s' (%s)." % (attr, e))


def unlock_channels(node):
    for ch in _CHANNELS:
        try:
            cmds.setAttr(node + "." + ch, lock=False)
        except RuntimeError:
            pass


def copy_channel_states(src, dst):
    for ch in _CHANNELS:
        try:
            s, d = src + "." + ch, dst + "." + ch
            keyable = cmds.getAttr(s, keyable=True)
            cmds.setAttr(d, keyable=keyable)
            if not keyable:
                cmds.setAttr(d, channelBox=cmds.getAttr(s, channelBox=True))
            cmds.setAttr(d, lock=cmds.getAttr(s, lock=True))
        except RuntimeError:
            pass


# ===========================================================================
# shapes
# ===========================================================================

def mirror_shape_onto(src, dst, axis, center, style=None):
    """dst gets src's shape, mirrored in world space."""
    curves.set_shape(dst, curves.read_shape(src), style if style is not None else curves.read_style(dst))
    positions = curves.world_positions(src)
    for shape_pts in positions:
        for i, p in enumerate(shape_pts):
            shape_pts[i] = reflect_point(p, axis, center)
    curves.set_world_positions(dst, positions)


def is_ctrl(n):
    return bool(curves.curve_shapes(n))


def is_joint(n):
    return cmds.nodeType(n) == "joint"


def is_geo(n):
    return geo.is_mesh(n) and not curves.curve_shapes(n)


PREDICATES = {1: is_ctrl, 2: is_ctrl, 3: is_joint, 4: is_geo}


def _inner(node, pred):
    """Selected group that only holds one thing (e.g. an offset group): that thing."""
    for _ in range(6):
        if cmds.listRelatives(node, shapes=True):
            return None
        kids = _child_transforms(node)
        if len(kids) != 1:
            return None
        node = kids[0]
        if pred(node):
            return node
    return None


def resolve(selection, pred, children, keep_order=False):
    """(nodes to mirror, selected nodes that gave nothing). Parents first, unless keep_order."""
    found, unused = [], []
    for n in selection:
        before = len(found)
        if pred(n):
            found.append(n)
        else:
            inner = _inner(n, pred)
            if inner:
                found.append(inner)
        if children:
            for d in cmds.listRelatives(n, allDescendents=True, fullPath=True, type="transform") or []:
                if pred(d):
                    found.append(d)
        if len(found) == before:
            unused.append(n)
    if keep_order:
        seen = set()
        return [f for f in found if not (f in seen or seen.add(f))], unused
    return _ordered(found), unused


def why_not(node, mode):
    """Why a selected node gives nothing in this mode."""
    if is_joint(node):
        return "is a joint (use Joints mode)"
    if is_geo(node):
        return "is a mesh (use Geometry mode)"
    if is_ctrl(node):
        return "is a curve control (use Full control or Shapes mode)"
    if mode == 3:
        return "is not a joint"
    return "has no %s in it" % ("mesh" if mode == 4 else "curve control")


def _control_nodes(selection, children):
    return resolve(selection, is_ctrl, children)[0]


def _plan(node, o, side=None):
    axis, center = _plane(o)
    return sides.plan(node, _pairs(o), axis, center, o["rename_source"], side)


def _source_renamed(node, plan_):
    """Apply the source rename of a plan. Returns the node's current long name."""
    if plan_ and plan_.get("rename_to") and plan_["rename_to"] != naming.short_name(node):
        return sides.apply_rename(node, plan_["rename_to"])
    return node


def run_shapes(o):
    axis, center = _plane(o)
    pairs = _pairs(o)
    done, skipped = 0, []
    ids = [utils.uuid(n) for n in _control_nodes(utils.selected_transforms(), o["children"])]
    for nid in ids:
        src = utils.path(nid)
        pl = _plan(src, o)
        short = naming.short_name(src)
        if not pl:
            skipped.append(short + " (centre)")
            continue
        if not pl["existing"]:
            skipped.append(short + " (no '%s' yet: use Full control to create it)" % pl["target_name"])
            continue
        if curves.other_shapes(pl["existing"]):
            skipped.append(short + " (other side is not a curve control)")
            continue
        dst_id = utils.uuid(pl["existing"])
        src = _source_renamed(src, pl)
        dst = utils.path(dst_id)
        mirror_shape_onto(src, dst, axis, center, curves.read_style(dst))
        sides.link(src, dst)
        if o["side_colors"]:
            colors.apply_side_color(src, pairs)
            colors.apply_side_color(dst, pairs)
        done += 1
    return "mirrored %d shape(s)" % done, skipped


# ===========================================================================
# full control
# ===========================================================================

def offset_chain(ctrl, o, side):
    """Empty single-child groups directly above ctrl that can be mirrored (top first)."""
    chain, node = [], ctrl
    for _ in range(6):
        p = _parent(node)
        if (not p or cmds.nodeType(p) != "transform"
                or cmds.listRelatives(p, shapes=True)
                or len(_child_transforms(p)) != 1
                or _plan(p, o, side) is None):
            break
        chain.insert(0, p)
        node = p
    return chain


def _target_parent(src_parent, o):
    """Where a new other-side node goes, by the parent rule."""
    rule = o["parent_rule"]
    if rule == 3 or not src_parent:
        return None
    if rule == 1:
        twin = sides.get_twin(src_parent)
        if twin:
            return twin
        found = _find(naming.mirror_name(src_parent, _pairs(o)))
        if len(found) == 1:
            return found[0]
    return src_parent


def _get_or_create(plan_, parent, make):
    """(node, created) for the other side of a plan."""
    if plan_.get("ambiguous"):
        raise RuntimeError("several nodes are named '%s'" % plan_["target_name"])
    if plan_["existing"]:
        return plan_["existing"], False
    node = make(plan_["target_name"])
    nid = utils.uuid(node)
    if parent:
        cmds.parent(node, parent, relative=True)      # starts at the parent's origin
    return utils.path(nid), True


def mirror_control(src, o, mode, plan_):
    axis, center = _plane(o)
    refl = reflection(axis, center)
    side = plan_["side"]
    src_id = utils.uuid(src)

    chain_ids = [utils.uuid(n) for n in offset_chain(src, o, side)]
    ungrouped = o.get("ungrouped", 1) if not chain_ids else 0
    if ungrouped == 2:
        # add an offset group above the source first, then mirror through it
        from gus_rigtool.tools.group_maker import group_each
        tops = group_each([src_id], ["_offset"], replace=False, match=True, side_color=False)
        src = utils.path(src_id)
        chain_ids = [utils.uuid(n) for n in offset_chain(src, o, side)]
        if not tops or not chain_ids:
            raise RuntimeError("could not add an offset group")
        ungrouped = 0
    top = utils.path(chain_ids[0]) if chain_ids else src
    parent = _target_parent(_parent(top), o)

    created_any = False
    prev = parent
    for cid in chain_ids:
        node = utils.path(cid)
        pl = _plan(node, o, side)
        dst, created = _get_or_create(pl, prev, lambda n: cmds.createNode("transform", name=n))
        dst_id = utils.uuid(dst)
        node = _source_renamed(node, pl)
        dst = utils.path(dst_id)
        created_any = created_any or created
        cmds.xform(dst, worldSpace=True, matrix=_vals(mirror_matrix(_m(node), mode, refl)))
        sides.link(node, dst)
        prev = dst

    src = utils.path(src_id)
    dst, created = _get_or_create(plan_, prev, lambda n: cmds.createNode("transform", name=n))
    dst_id = utils.uuid(dst)
    if chain_ids and not created and prev and _parent(dst) != prev:
        cmds.parent(dst, prev)                     # existing R control into its offset group
    src = _source_renamed(src, plan_)
    dst = utils.path(dst_id)
    created_any = created_any or created

    unlock_channels(dst)
    if chain_ids:
        if o["copy_values"] or created:
            t = cmds.getAttr(src + ".translate")[0]
            r = cmds.getAttr(src + ".rotate")[0]
            s = cmds.getAttr(src + ".scale")[0]
            if mode == "behavior":
                t = [-x for x in t]
            _set3(dst, "translate", t)
            _set3(dst, "rotate", r)
            _set3(dst, "scale", s)
            cmds.setAttr(dst + ".rotateOrder", cmds.getAttr(src + ".rotateOrder"))
    elif ungrouped == 1:
        # Baked: clean transform (same axes, mirrored position, no negative scale);
        # the mirror goes into the CVs below
        cmds.xform(dst, worldSpace=True, matrix=_vals(mirror_matrix(_m(src), "same", refl)))
    else:
        # no offset group, as set: the control itself takes the mirrored matrix
        cmds.xform(dst, worldSpace=True, matrix=_vals(mirror_matrix(_m(src), mode, refl)))

    dst = utils.path(dst_id)
    style = curves.read_style(src)
    if o["side_colors"]:
        other = "R" if side == "L" else "L"
        style.update(curves.rgb_style(colors.side_colors()[other]))
        style.pop("overrideColor", None)
        colors.set_node_color(src, colors.side_colors()[side])
    mirror_shape_onto(src, dst, axis, center, style)

    if o["copy_attrs"]:
        copy_user_attrs(src, dst)
    if o["copy_locks"]:
        copy_channel_states(src, dst)
    engine.link(src, dst, mode if (chain_ids or ungrouped != 1) else "baked")
    return created_any


def run_full(o):
    mode = ["true", "behavior", "same"][o["ctrl_orient"] - 1]
    made, updated, renamed, skipped = 0, 0, 0, []
    ids = [utils.uuid(n) for n in _control_nodes(utils.selected_transforms(), o["children"])]
    for nid in ids:
        src = utils.path(nid)
        pl = _plan(src, o)
        if pl is None:
            skipped.append(naming.short_name(src) + " (centre)")
            continue
        if pl["existing"] and not o["update_existing"]:
            skipped.append(naming.short_name(src) + " (exists)")
            continue
        try:
            if pl.get("rename_to"):
                renamed += 1
            if mirror_control(src, o, mode, pl):
                made += 1
            else:
                updated += 1
        except RuntimeError as e:
            utils.warn(TOOL, "'%s': %s" % (naming.short_name(src), e))
            skipped.append(naming.short_name(src) + " (%s)" % e)
    msg = "controls: %d created, %d updated (%s)" % (made, updated, CTRL_ORIENT[o["ctrl_orient"] - 1])
    if renamed:
        msg += "; %d source(s) renamed with their side" % renamed
    return msg, skipped


# ===========================================================================
# joints
# ===========================================================================

def set_joint_world(joint, target, keep_rotate):
    """Put a joint at a world matrix with translate + Joint Orient (rotate kept or zeroed)."""
    if not keep_rotate:
        _set3(joint, "rotate", [0.0, 0.0, 0.0])
    _set3(joint, "rotateAxis", [0.0, 0.0, 0.0])

    parent_inv = om.MMatrix(cmds.getAttr(joint + ".parentInverseMatrix[0]"))
    pos = om.MPoint(target.getElement(3, 0), target.getElement(3, 1), target.getElement(3, 2))
    local = pos * parent_inv
    _set3(joint, "translate", [local.x, local.y, local.z])

    r = _euler(cmds.getAttr(joint + ".rotate")[0], cmds.getAttr(joint + ".rotateOrder"))
    jo = _rot_only(r.inverse() * _rot_only(target) * parent_inv)
    _set3(joint, "jointOrient", _to_deg_xyz(jo))


def _joints_from_selection(children):
    return resolve(utils.selected_transforms(), is_joint, children)[0]


def _label(joint, side, pairs):
    side = {"L": 1, "R": 2, "C": 0}[side]
    try:
        cmds.setAttr(joint + ".side", side)
        cmds.setAttr(joint + ".type", 18)                          # Other
        cmds.setAttr(joint + ".otherType", naming.label_of(joint, pairs), type="string")
    except RuntimeError:
        pass


def run_joints(o):
    mode = ["behavior", "same"][o["jnt_orient"] - 1]
    pairs = _pairs(o)
    axis, center = _plane(o)
    refl = reflection(axis, center)
    keep_rotate = not o["clean_rotate"]

    joints = _joints_from_selection(o["children"])
    if not joints:
        return None, []

    # plan everything (and read world matrices) before anything moves or is renamed
    plan_list, skipped, renamed = [], [], 0
    for j in joints:
        pl = _plan(j, o)
        if pl is None:
            skipped.append(naming.short_name(j) + " (centre)")
            continue
        if pl.get("ambiguous"):
            skipped.append(naming.short_name(j) + " (several '%s')" % pl["target_name"])
            continue
        if pl["existing"] and not o["update_existing"]:
            skipped.append(naming.short_name(j) + " (exists)")
            continue
        existing = pl["existing"]
        plan_list.append({
            "src_id": utils.uuid(j), "plan": pl, "name": pl["target_name"],
            "existing_id": utils.uuid(existing) if existing else None,
            "target": mirror_matrix(_m(j), mode, refl),
            "w_old": _m(existing) if existing else None,
        })

    # renames first, so new joints find their renamed parents' twins
    for item in plan_list:
        src = utils.path(item["src_id"])
        if item["plan"].get("rename_to"):
            _source_renamed(src, item["plan"])
            renamed += 1

    made, updated, skinned = 0, 0, []
    for item in plan_list:
        src = utils.path(item["src_id"])
        if item["existing_id"]:
            dst = utils.path(item["existing_id"])
            updated += 1
        else:
            parent = _target_parent(_parent(src), o)
            dst = cmds.createNode("joint", name=item["name"], parent=parent) if parent \
                else cmds.createNode("joint", name=item["name"])
            dst = cmds.ls(dst, long=True)[0]
            made += 1
        dst_id = utils.uuid(dst)

        cmds.setAttr(dst + ".rotateOrder", cmds.getAttr(src + ".rotateOrder"))
        _set3(dst, "scale", cmds.getAttr(src + ".scale")[0])
        if keep_rotate:
            _set3(dst, "rotate", cmds.getAttr(src + ".rotate")[0])
        set_joint_world(dst, item["target"], keep_rotate)
        dst = utils.path(dst_id)
        try:
            cmds.setAttr(dst + ".preferredAngle", *cmds.getAttr(src + ".preferredAngle")[0])
        except RuntimeError:
            pass

        if o["round_tiny"]:
            _round_tiny(dst)
        if o["copy_look"]:
            for attr in ("radius", "drawStyle", "segmentScaleCompensate"):
                try:
                    cmds.setAttr(dst + "." + attr, cmds.getAttr(src + "." + attr))
                except RuntimeError:
                    pass
        side = item["plan"]["side"]
        other = "R" if side == "L" else "L"
        if o["labels"]:
            _label(src, side, pairs)
            _label(dst, other, pairs)
        if o["side_colors"]:
            colors.set_node_color(src, colors.side_colors()[side])
            colors.set_node_color(dst, colors.side_colors()[other])
        engine.link(src, dst, mode)
        if item["existing_id"] and o["keep_skin"]:
            if skin.compensate(dst, item["w_old"], _m(dst)):
                skinned.append(naming.short_name(dst))

    msg = "joints: %d created, %d updated (%s)" % (made, updated, JNT_ORIENT[o["jnt_orient"] - 1])
    if renamed:
        msg += "; %d source(s) renamed with their side" % renamed
    if skinned:
        msg += "; skin kept in place for %d" % len(skinned)
    return msg, skipped


# ===========================================================================
# geometry
# ===========================================================================

def mirror_geo(src, o, mode, plan_):
    """Mirror one mesh. mode: 'baked', 'true', 'behavior' or 'same'. Returns True if created."""
    axis, center = _plane(o)
    refl = reflection(axis, center)
    side = plan_["side"]
    src_id = utils.uuid(src)

    # groups that only hold this mesh are mirrored too (clean axes when baked)
    group_mode = "same" if mode == "baked" else mode
    chain_ids = [utils.uuid(n) for n in offset_chain(src, o, side)]
    top = utils.path(chain_ids[0]) if chain_ids else src
    prev = _target_parent(_parent(top), o)
    for cid in chain_ids:
        node = utils.path(cid)
        pl = _plan(node, o, side)
        dst, _created = _get_or_create(pl, prev, lambda n: cmds.createNode("transform", name=n))
        dst_id = utils.uuid(dst)
        node = _source_renamed(node, pl)
        dst = utils.path(dst_id)
        cmds.xform(dst, worldSpace=True, matrix=_vals(mirror_matrix(_m(node), group_mode, refl)))
        sides.link(node, dst)
        prev = dst

    src = utils.path(src_id)
    shape, deformed = geo.source_shape(src)
    if deformed:
        utils.warn(TOOL, "'%s' has deformers: copied from its original shape, without them."
                   % naming.short_name(src))
    target = mirror_matrix(_m(src), "same" if mode == "baked" else mode, refl)

    if plan_["existing"]:
        dst = plan_["existing"]
        dst_id = utils.uuid(dst)
        if mode == "baked":
            dst_shapes = geo.mesh_shapes(dst)
            if not dst_shapes:
                raise RuntimeError("the other side '%s' is not a mesh" % naming.short_name(dst))
            if geo.has_deformers(dst_shapes[0]):
                raise RuntimeError("the other side has deformers (skin...), not updated")
            if geo.vertex_count(dst) != geo.vertex_count(src):
                raise RuntimeError("the other side has a different topology, not updated")
            tmp = geo.world_copy(src, shape)
            geo.mirror_vertices(tmp, axis, center)
            geo.into_space(tmp, _m(dst))
            geo.set_points_from(dst, tmp)
            cmds.delete(tmp)
        else:
            cmds.xform(dst, worldSpace=True, matrix=_vals(target))
        created = False
    else:
        dst = cmds.createNode("transform", name=plan_["target_name"])
        dst_id = utils.uuid(dst)
        if prev:
            cmds.parent(dst, prev, relative=True)
        dst = utils.path(dst_id)
        cmds.xform(dst, worldSpace=True, matrix=_vals(target))
        if mode == "baked":
            tmp = geo.world_copy(src, shape)
            geo.mirror_vertices(tmp, axis, center)
            geo.into_space(tmp, _m(dst))
        else:
            tmp = geo.local_copy(shape)
        geo.move_shape_under(tmp, utils.path(dst_id))
        if o["copy_materials"]:
            geo.copy_materials(utils.path(src_id), utils.path(dst_id))
        created = True

    src = _source_renamed(utils.path(src_id), plan_)
    engine.link(src, utils.path(dst_id), mode)
    return created


def run_geo(o):
    mode = ["baked", "true", "behavior", "same"][o["geo_orient"] - 1]
    made, updated, renamed, skipped = 0, 0, 0, []
    nodes, _unused = resolve(utils.selected_transforms(), is_geo, o["children"])
    for nid in [utils.uuid(n) for n in nodes]:
        src = utils.path(nid)
        short = naming.short_name(src)
        pl = _plan(src, o)
        if pl is None:
            skipped.append(short + " (centre)")
            continue
        if pl.get("ambiguous"):
            skipped.append(short + " (several '%s')" % pl["target_name"])
            continue
        if pl["existing"] and not o["update_existing"]:
            skipped.append(short + " (exists)")
            continue
        try:
            if pl.get("rename_to"):
                renamed += 1
            if mirror_geo(src, o, mode, pl):
                made += 1
            else:
                updated += 1
        except RuntimeError as e:
            utils.warn(TOOL, "'%s': %s." % (short, e))
            skipped.append(short + " (%s)" % e)
    msg = "geometry: %d created, %d updated (%s)" % (made, updated, GEO_ORIENT[o["geo_orient"] - 1])
    if renamed:
        msg += "; %d source(s) renamed with their side" % renamed
    return msg, skipped


# ===========================================================================
# window
# ===========================================================================
