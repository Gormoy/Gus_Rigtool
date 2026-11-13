"""
Not a control (5.6.30): a curve that isn't a control any more (the Hare's old hidden Head_ctrl, Neck_ctrl,
L / R_IK_Elbow_ctrl, L / R_IK_Wrist_ctrl) gets the gusNotControl mark - the checker, Publish and Gus Animtool leave
it out (no 'hidden by a group' warning, no default pose, no picker button). Nothing in the rig changes; the mark
comes off again with 'A control again'.

    from gus_rigtool.core import control_role
    control_role.set_role(["Neck_ctrl"], control=False)
"""

import maya.cmds as cmds

from gus_rigtool.core import utils

MARK = "gusNotControl"                   # the same mark the sliders board's frames carry (5.6.17)


def is_marked(node):
    try:
        return bool(cmds.attributeQuery(MARK, node=node, exists=True))
    except (RuntimeError, ValueError):
        return False


def set_role(nodes, control=False):
    """control False: marked as not a control; True: the mark taken off. One undo. Returns the nodes changed."""
    changed = []
    with utils.undo_chunk("gusrigControlRole"):
        for n in nodes:
            if not control and not is_marked(n):
                cmds.addAttr(n, longName=MARK, attributeType="bool", defaultValue=True)
                changed.append(n)
            elif control and is_marked(n):
                cmds.deleteAttr(n + "." + MARK)
                changed.append(n)
    return changed
