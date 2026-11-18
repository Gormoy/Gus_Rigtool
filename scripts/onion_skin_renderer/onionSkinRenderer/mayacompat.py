"""
Stand-in for the few PyMEL calls this script used, written with maya.cmds - so it runs on a Maya 2024 without
PyMEL installed (PyMEL is an optional install since Maya 2022). Only what the script needs:
selected(), getCurrentTime(), animation.getCurrentTime(), findKeyframe(), lsUI(), uitypes.ModelEditor.
"""
import maya.cmds as cmds


class Node(str):
    """A node name that answers nodeName() / fullPath() like a PyMEL node (it is the long name)."""
    def nodeName(self):
        return self.split("|")[-1]

    def fullPath(self):
        return str(self)


def selected():
    return [Node(n) for n in cmds.ls(selection=True, long=True) or []]


def getCurrentTime():
    return cmds.currentTime(query=True)


class animation(object):
    getCurrentTime = staticmethod(getCurrentTime)


def findKeyframe(t=None, ts=False, w="next"):
    kw = {"which": w}
    if ts:
        kw["timeSlider"] = True
    if t is not None:
        kw["time"] = (t, t)
    return cmds.findKeyframe(**kw)


def lsUI(editors=True):
    return cmds.lsUI(editors=editors) or []


class _ModelEditor(object):
    def __init__(self, name):
        self.name = str(name)

    def getRendererOverrideName(self):
        return cmds.modelEditor(self.name, query=True, rendererOverrideName=True) or ""

    def setRendererOverrideName(self, value):
        cmds.modelEditor(self.name, edit=True, rendererOverrideName=value)

    def getActiveView(self):
        return cmds.modelEditor(self.name, query=True, activeView=True)


class uitypes(object):
    ModelEditor = _ModelEditor
