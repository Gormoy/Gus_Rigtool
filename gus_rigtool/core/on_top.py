"""
Controls in front of the mesh (5.3.1): Maya's 'Always Draw On Top' (Maya 2022+) on the controls' curve shapes, so
a control buried in the body (spine, hips, clavicles) is always seen. Face controls are skipped by default: they
sit on the surface already, and on top they'd show through the back of the head.

    from gus_rigtool.core import on_top
    on_top.apply()                 # every control, face skipped
    on_top.apply(on=False)         # off again
"""

import re

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

ATTR = "alwaysDrawOnTop"
FACE = r"mouth|lip|brow|eye|lid|cheek|nose|jaw|tongue|teeth|tooth|gum|chin|facial|face|squint|smile|sneer|" \
       r"pupil|iris|nostril|forehead|(^|_)ears?(_|$|\d)"


def is_face(node):
    return bool(re.search(FACE, naming.short_name(node).lower()))


def controls():
    """Every control of the scene (curves with a transform), long names."""
    from gus_rigtool.tools import checker
    return [c for c in checker.transforms(None) if checker.is_control(c)]


def _shapes(node):
    return [s for s in cmds.listRelatives(node, shapes=True, type="nurbsCurve", fullPath=True) or []
            if not cmds.getAttr(s + ".intermediateObject")]


def apply(nodes=None, on=True, skip_face=True):
    """Draw these controls (default: every control) on top, or not. Returns (changed, skipped face, no attribute)."""
    nodes = controls() if nodes is None else nodes
    changed, face, missing = 0, 0, 0
    with utils.undo_chunk("gusrigOnTop"):
        for n in nodes:
            if on and skip_face and is_face(n):
                face += 1
                continue
            for s in _shapes(n):
                if not cmds.attributeQuery(ATTR, node=s, exists=True):
                    missing += 1
                    continue
                try:
                    if bool(cmds.getAttr(s + "." + ATTR)) != bool(on):
                        cmds.setAttr(s + "." + ATTR, bool(on))
                        changed += 1
                except RuntimeError:                      # locked in a referenced rig
                    missing += 1
    return changed, face, missing


def count():
    """(controls on top, controls)."""
    ctrls = controls()
    on = 0
    for c in ctrls:
        shapes = _shapes(c)
        if shapes and all(cmds.attributeQuery(ATTR, node=s, exists=True) and cmds.getAttr(s + "." + ATTR)
                          for s in shapes):
            on += 1
    return on, len(ctrls)
