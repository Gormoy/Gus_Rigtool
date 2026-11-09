"""
Gus Animtool - animator tools for any rig (and the best with Gus_Rigtool rigs).

    import gus_animtool; gus_animtool.show()

Install / update: drag drag_to_maya_animtool.mel into Maya's viewport, or Update... in its window.
"""

import os

__version__ = "5.6.27"               # always the same as Gus_Rigtool's (a test checks it)

ROOT = os.path.dirname(os.path.abspath(__file__))


def show(*_):
    from gus_animtool import ui
    return ui.show()
