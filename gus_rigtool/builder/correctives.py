"""
Corrective (volume) joints for limbs: at a bending joint (shoulder, elbow, wrist, hip, knee, ankle, hock), a joint
under the bone above that turns HALF way with the bend. Skinned to the area around the bend, it keeps the volume
(no candy-wrapper collapse at the elbow, the knee stays round). Both sides are always made, so mirroring the skin
finds every twin.
"""

import maya.cmds as cmds

from gus_rigtool.builder import limb


def make(ctx, pairs, out, weight=0.5):
    """pairs: [(part name, upper joint, bending joint)]. The new joints go into out['joints']. Returns them."""
    made = []
    for part, upper, lower in pairs:
        if not upper or not lower or not cmds.objExists(upper) or not cmds.objExists(lower):
            continue
        m = limb.world(lower)
        j = limb.joint_chain(ctx.side, [part + "_cor"], [m], upper, None, ctx.radius * 0.6)[0]
        oc = cmds.orientConstraint(upper, lower, j, maintainOffset=True)[0]
        try:
            cmds.setAttr(oc + ".interpType", 2)                 # shortest: no flip on a big bend
            targets = cmds.orientConstraint(oc, query=True, weightAliasList=True) or []
            if len(targets) == 2:
                cmds.setAttr(oc + "." + targets[0], 1.0 - weight)
                cmds.setAttr(oc + "." + targets[1], weight)
        except (RuntimeError, ValueError):
            pass
        out["joints"][j.split("|")[-1]] = j
        made.append(j)
    return made


OPTION = ("Corrective joints (keep the volume at the bends: a joint turning half way at each one - skin to it)",
          "bool", None)
