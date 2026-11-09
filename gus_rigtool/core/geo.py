"""
Mesh helpers for mirroring: copy a mesh, mirror it baked into the vertices, update an
existing copy, copy materials.

All steps use Maya commands, so every change is undoable.
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import utils


# ---------------------------------------------------------------------------
# finding shapes
# ---------------------------------------------------------------------------

def mesh_shapes(node, intermediate=False):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    out = []
    for s in shapes:
        if cmds.nodeType(s) != "mesh":
            continue
        if bool(cmds.getAttr(s + ".intermediateObject")) == intermediate:
            out.append(s)
    return out


def is_mesh(node):
    return bool(mesh_shapes(node))


def has_deformers(shape):
    for h in cmds.listHistory(shape, pruneDagObjects=True) or []:
        if cmds.objectType(h, isAType="geometryFilter"):
            return True
    return False


def source_shape(node):
    """
    (shape to copy from, deformed?) - the visible mesh, or for a deformed mesh
    (skin, blendShape...) its original shape, so the copy has the undeformed geometry.
    """
    final = mesh_shapes(node)[0]
    if not has_deformers(final):
        return final, False
    for s in mesh_shapes(node, intermediate=True):
        if not cmds.listConnections(s + ".inMesh", source=True, destination=False):
            return s, True
    return final, True


def vertex_count(node):
    return cmds.polyEvaluate(node, vertex=True)


# ---------------------------------------------------------------------------
# copies
# ---------------------------------------------------------------------------

def _mat_vals(m):
    return [m.getElement(r, c) for r in range(4) for c in range(4)]


def local_copy(shape, name="rtTmpMesh"):
    """New transform (at the origin) holding a copy of shape's mesh, no history."""
    t = cmds.createNode("transform", name=name)
    m = cmds.createNode("mesh", parent=t, name=name + "Shape")
    cmds.connectAttr(shape + ".outMesh", m + ".inMesh")
    cmds.polyEvaluate(m, vertex=True)                  # make Maya compute the copy
    cmds.disconnectAttr(shape + ".outMesh", m + ".inMesh")
    return cmds.ls(t, long=True)[0]


def world_copy(src, shape):
    """Copy of the mesh with its vertices in world space, under a transform at the origin."""
    t = local_copy(shape)
    cmds.xform(t, worldSpace=True, matrix=cmds.getAttr(src + ".worldMatrix[0]"))
    cmds.makeIdentity(t, apply=True, translate=True, rotate=True, scale=True, normal=0)
    return t


def mirror_vertices(t, axis, center):
    """Reflect every vertex across the plane and turn the normals back outwards."""
    scale = [1.0, 1.0, 1.0]
    scale[axis] = -1.0
    cmds.scale(scale[0], scale[1], scale[2], t + ".vtx[*]", pivot=tuple(center), relative=True)
    cmds.polyNormal(t, normalMode=0, userNormalMode=0, constructionHistory=False)


def into_space(t, world_matrix):
    """Re-express a world-space mesh (transform at the origin) in another node's space."""
    inv = om.MMatrix(world_matrix).inverse()
    cmds.xform(t, worldSpace=True, matrix=_mat_vals(inv))
    cmds.makeIdentity(t, apply=True, translate=True, rotate=True, scale=True, normal=0)


def move_shape_under(t, target):
    """Move the mesh shape of t under target (keeping local coordinates), delete t."""
    shape = mesh_shapes(t)[0]
    shape = cmds.parent(shape, target, relative=True, shape=True)[0]
    cmds.delete(t)
    base = target.split("|")[-1].split(":")[-1]
    return cmds.rename(cmds.ls(shape, long=True)[0], base + "Shape")


def set_points_from(dst, t):
    """Give dst the vertex positions of t (same topology, same object space)."""
    try:
        cmds.polyTransfer(dst, vertices=True, alternateObject=t, constructionHistory=False)
        return
    except (RuntimeError, TypeError):
        pass
    flat = cmds.xform(t + ".vtx[*]", query=True, objectSpace=True, translation=True)
    for i in range(len(flat) // 3):
        cmds.xform("%s.vtx[%d]" % (dst, i), objectSpace=True, translation=flat[i * 3:i * 3 + 3])


# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------

def copy_materials(src, dst):
    """Assign src's shading groups to dst, per face when src uses per-face materials."""
    src_shape = mesh_shapes(src)[0]
    dst_shape = mesh_shapes(dst)[0]
    dst_t = cmds.ls(dst, long=True)[0]
    engines = set(cmds.listConnections(src_shape, type="shadingEngine") or [])
    for sg in engines:
        members = cmds.sets(sg, query=True) or []
        for m in members:
            long_m = (cmds.ls(m, long=True) or [m])[0]
            node = long_m.split(".")[0]
            if node not in (cmds.ls(src, long=True)[0], cmds.ls(src_shape, long=True)[0]):
                continue
            try:
                if "." in long_m:
                    comp = long_m.split(".", 1)[1]
                    cmds.sets("%s.%s" % (dst_t, comp), edit=True, forceElement=sg)
                else:
                    cmds.sets(dst_shape, edit=True, forceElement=sg)
            except RuntimeError as e:
                utils.warn("Mirror", "could not copy material '%s' to '%s' (%s)." % (sg, dst_t, e))
    if not engines:
        try:
            cmds.sets(dst_shape, edit=True, forceElement="initialShadingGroup")
        except RuntimeError:
            pass
