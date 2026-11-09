"""
Mirror skin weights: one side of a mesh onto the other, or one mesh onto its twin mesh.

Joints are matched by name (your naming pairs, L_ <-> R_...): for the copy every influence
gets a joint label made from its name, so Maya's Copy Skin Weights pairs L_humerus_jnt with
R_humerus_jnt. The joints' own labels are put back afterwards. "Closest joint" can be added as
a fallback for joints whose names don't pair.

Maya mirrors across a plane through the world origin (YZ = across X).
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import naming, sides, utils

TOOL = "Mirror"
PLANES = {0: "YZ", 1: "XZ", 2: "XY"}


# ---------------------------------------------------------------------------
# finding things
# ---------------------------------------------------------------------------

def skin_of(mesh):
    """The skinCluster of a mesh (transform or shape), or None."""
    hist = cmds.listHistory(mesh, pruneDagObjects=True) or []
    found = utils.ls(hist, type="skinCluster") or []
    return found[0] if found else None


def influences(skin):
    return utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []


def _mesh_of(node):
    node = node.split(".")[0]
    if cmds.nodeType(node) == "mesh":
        node = cmds.listRelatives(node, parent=True, fullPath=True)[0]
    return cmds.ls(node, long=True)[0]


def _selection():
    """(meshes, vertices) from the selection (faces / edges become their vertices)."""
    sel = cmds.ls(selection=True, flatten=False) or []
    comps = [s for s in sel if "." in s]
    meshes = []
    for s in sel:
        m = _mesh_of(s)
        if m not in meshes and (cmds.listRelatives(m, shapes=True, type="mesh") or []):
            meshes.append(m)
    verts = cmds.ls(cmds.polyListComponentConversion(comps, toVertex=True) or [], flatten=True) if comps else []
    return meshes, verts


def twin_joint(joint, pairs):
    """The other side's joint, by name. Centre joints are their own twin. None if missing."""
    name = naming.mirror_name(joint, pairs)
    if name is None:
        return joint                                    # centre: mirrors onto itself
    found = cmds.ls(name, long=True) or []
    return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def _points(mesh):
    sel = om.MSelectionList()
    sel.add(mesh)
    return om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)


def symmetry(mesh, axis=0, tolerance=0.001):
    """(vertices, vertices without a mirrored partner) of a mesh, across the plane through the origin."""
    pts = _points(mesh)
    cell = max(tolerance, 1e-6)

    def key(x, y, z):
        return (int(round(x / cell)), int(round(y / cell)), int(round(z / cell)))

    grid = set()
    for p in pts:
        grid.add(key(p.x, p.y, p.z))
    lonely = 0
    for p in pts:
        q = [p.x, p.y, p.z]
        q[axis] = -q[axis]
        k = key(*q)
        if k not in grid and not any((k[0] + a, k[1] + b, k[2] + c) in grid
                                     for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1)):
            lonely += 1
    return len(pts), lonely


def check(source=None, dest=None, axis=0, pairs=None):
    """Report lines before mirroring: skin, symmetry, joints without a twin."""
    pairs = pairs or sides.default_pairs()
    meshes, verts = _selection()
    source = source or (meshes[0] if meshes else None)
    if not source:
        raise RuntimeError("select a skinned mesh (or two: source, then the twin mesh).")
    dest = dest or (meshes[1] if len(meshes) > 1 else source)
    skin = skin_of(source)
    if not skin:
        raise RuntimeError("'%s' has no skin cluster." % naming.short_name(source))
    lines, level = [], "ok"
    lines.append("source: %s (%s, %d joints)" % (naming.short_name(source), skin, len(influences(skin))))
    if dest != source:
        dskin = skin_of(dest)
        lines.append("target: %s (%s)" % (naming.short_name(dest), dskin or "not skinned yet: it will be "
                                                                             "skinned to the twin joints"))
    else:
        total, lonely = symmetry(source, axis)
        if lonely:
            level = "warn"
            lines.append("%d of %d vertices have no mirrored partner: those get the closest weights."
                         % (lonely, total))
        else:
            lines.append("mesh is symmetrical (%d vertices)." % total)
    if verts:
        lines.append("only the %d selected vertices will change." % len(verts))
    missing = [j for j in influences(skin) if twin_joint(j, pairs) is None]
    if missing:
        level = "warn"
        lines.append("no twin by name for %d joint(s): %s" % (
            len(missing), ", ".join(naming.short_name(j) for j in missing[:6])
            + (" ..." if len(missing) > 6 else "")))
    else:
        lines.append("every joint has a twin by name.")
    return level, lines


# ---------------------------------------------------------------------------
# labels (how Maya pairs the joints)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# mirror
# ---------------------------------------------------------------------------

def _bind_twin(source, dest, skin, pairs):
    """Skin dest to the twins of source's joints (same settings as far as Maya allows)."""
    joints = []
    for j in influences(skin):
        t = twin_joint(j, pairs)
        if t and t not in joints:
            joints.append(t)
    if not joints:
        raise RuntimeError("none of the joints of '%s' has a twin." % naming.short_name(source))
    max_inf = cmds.skinCluster(skin, query=True, maximumInfluences=True)
    return cmds.skinCluster(joints, dest, toSelectedBones=True, maximumInfluences=max_inf,
                            name=naming.short_name(dest) + "_skinCluster")[0]


def mirror_weights(direction="L>R", closest_fallback=False, axis=0, pairs=None):
    """
    Mirror the weights of the selected mesh (one side onto the other), or of the first selected
    mesh onto the second (its twin). With vertices selected, only those change.
    direction: 'L>R' (+X side onto -X) or 'R>L'.
    """
    pairs = pairs or sides.default_pairs()
    meshes, verts = _selection()
    if not meshes:
        raise RuntimeError("select a skinned mesh (or two: source, then the twin mesh).")
    source = meshes[0]
    dest = meshes[1] if len(meshes) > 1 else source
    skin = skin_of(source)
    if not skin:
        raise RuntimeError("'%s' has no skin cluster." % naming.short_name(source))

    association = ["label", "closestJoint"] if closest_fallback else ["label"]
    left_positive = True
    try:
        # which side of the axis is "left" in this scene (from a left joint, if there is one)
        for j in influences(skin):
            if naming.side_of(j, pairs) == "L":
                left_positive = cmds.xform(j, query=True, worldSpace=True, translation=True)[axis] >= 0
                break
    except RuntimeError:
        pass
    # Maya copies from the + side to the - side, unless mirrorInverse
    inverse = (direction == "R>L") == left_positive

    with utils.undo_chunk("gusrigMirrorSkin"):
        dskin = skin if dest == source else (skin_of(dest) or _bind_twin(source, dest, skin, pairs))
        joints = list(dict.fromkeys(influences(skin) + influences(dskin)))
        from gus_rigtool.core import joint_labels                 # by name, and by position for the rest
        joint_labels.label(joints)
        kwargs = dict(sourceSkin=skin, destinationSkin=dskin, mirrorMode=PLANES[axis],
                      mirrorInverse=inverse, surfaceAssociation="closestPoint",
                      influenceAssociation=association, normalize=True)
        if verts and dest == source:
            # only the selected vertices change: Maya then works from the selection
            cmds.select(verts, replace=True)
            kwargs.pop("sourceSkin")
            kwargs.pop("destinationSkin")
            cmds.copySkinWeights(**kwargs)
        else:
            cmds.copySkinWeights(**kwargs)
        if verts:
            cmds.select(verts, replace=True)
        else:
            cmds.select(meshes, replace=True)

    where = ("%d selected vertices of %s" % (len(verts), naming.short_name(source)) if verts and dest == source
             else naming.short_name(source) if dest == source
             else "%s -> %s" % (naming.short_name(source), naming.short_name(dest)))
    utils.info(TOOL, "mirrored skin weights %s on %s (by name%s)." % (
        direction.replace(">", " -> "), where, ", closest joint as fallback" if closest_fallback else ""))
