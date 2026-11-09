"""
Side colours shared by every Gus_Rigtool tool (L, R and centre).
They are saved between Maya sessions.
"""

import maya.cmds as cmds

from gus_rigtool.core import curves, utils

DEFAULT_SIDE_COLORS = {
    "L": [0.0, 0.25, 1.0],     # blue
    "R": [1.0, 0.0, 0.0],      # red
    "C": [1.0, 1.0, 0.0],      # yellow
}


def side_colors():
    saved = utils.load_setting("sideColors", {})
    out = dict(DEFAULT_SIDE_COLORS)
    out.update({k: v for k, v in saved.items() if k in out})
    return out


def save_side_colors(colors):
    utils.save_setting("sideColors", colors)


def color_for(node, pairs=None):
    """Side colour from the name, or from the position when the name has no side."""
    from gus_rigtool.core import sides
    return side_colors()[sides.side_of_node(node, pairs)]


def set_node_color(node, rgb):
    """Colour a control (its curve shapes) or a joint / other node (its own override)."""
    shapes = curves.curve_shapes(node)
    if shapes:
        curves.set_color(node, rgb)
        return
    try:
        cmds.setAttr(node + ".overrideEnabled", 1)
        cmds.setAttr(node + ".overrideRGBColors", 1)
        cmds.setAttr(node + ".overrideColorRGB", *rgb)
    except RuntimeError:
        pass


def apply_side_color(node, pairs=None):
    set_node_color(node, color_for(node, pairs))
