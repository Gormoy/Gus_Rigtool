"""Keep skinned meshes still when a skinned joint is moved or re-oriented."""

import maya.cmds as cmds
import maya.api.OpenMaya as om


def world(node):
    return om.MMatrix(cmds.getAttr(node + ".worldMatrix[0]"))


def compensate(node, w_old, w_new):
    """
    Update the skinCluster bind data of node so the mesh does not move after the
    joint went from world matrix w_old to w_new. Resets the bind pose for it.
    Returns True if the node is a skin influence.
    """
    plugs = cmds.listConnections(node + ".worldMatrix", type="skinCluster",
                                 plugs=True, source=False, destination=True) or []
    if not plugs:
        return False
    delta = w_old * w_new.inverse()
    for plug in plugs:
        skin, attr = plug.split(".", 1)
        index = attr[attr.index("[") + 1:attr.index("]")]
        bpm_plug = "%s.bindPreMatrix[%s]" % (skin, index)
        if cmds.listConnections(bpm_plug, source=True, destination=False):
            continue                                   # driven bind data: leave it
        bpm = om.MMatrix(cmds.getAttr(bpm_plug))
        new = bpm * delta
        cmds.setAttr(bpm_plug, *[new.getElement(r, c) for r in range(4) for c in range(4)],
                     type="matrix")
    if cmds.attributeQuery("bindPose", node=node, exists=True):
        for pose in set(cmds.listConnections(node + ".bindPose", type="dagPose") or []):
            try:
                cmds.dagPose(node, reset=True, name=pose)
            except RuntimeError:
                pass
    return True
