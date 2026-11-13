"""
Gus_Rigtool - personal rigging toolkit for Maya (2024+).

Main window (every tool in a tab):

    import gus_rigtool.main as gr; gr.show()

Install / update: drag drag_to_maya.mel into Maya's viewport.
"""

import os

__version__ = "5.6.35"

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")


def reload_all():
    """Reload every Gus_Rigtool module (core first, then tools)."""
    import importlib
    import sys

    names = [n for n in sys.modules if n == "gus_rigtool" or n.startswith("gus_rigtool.")]

    def order(name):
        if name == "gus_rigtool":
            return (0, name)
        if ".core" in name:
            return (1, name)
        return (2, name)

    for name in sorted(names, key=order):
        module = sys.modules.get(name)
        if module is not None:
            importlib.reload(module)
    print("Gus_Rigtool: reloaded %d module(s)." % len(names))
