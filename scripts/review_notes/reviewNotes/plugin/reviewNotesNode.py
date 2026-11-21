"""
Review Notes plugin: the REVIEW_NOTES node. One per scene; it draws every note of the scene's review file in 2D
over the camera each note belongs to, on the note's frames (nearby notes faint, the onion skin's colours).

It's a locator with a Viewport 2.0 draw override, not a render override, so it shows together with the onion
skin and in playblasts (try-it, Gus 2026-11-21). The node is never saved in the scene (do-not-write): the notes
live in the review file, and a scene sent to someone without the tool opens clean.

Settings are the node's attributes (Attribute Editor): Review File (empty = next to the scene), Show Nearby,
Nearby Frames, Only Open, Show Text, Opacity, Hide While Playing, Show Gate (the try-it's green box).

A THIN SHELL (0.1.2, Gus OK'd): the drawing itself is in reviewNotes/nodedraw.py, looked up again on every
refresh, so an update works as soon as the installer reloads the reviewNotes folder - no Maya restart. Only a
change in this file (new settings, the node's id) needs the plugin reloaded; the installer does that too (it
clears undo first, or Maya refuses to unload a plugin whose node is in the undo queue).
"""

import importlib

import maya.api.OpenMaya as om
import maya.api.OpenMayaRender as omr
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

NODE_TYPE = "reviewNotes"
NODE_ID = 0x0007F3A2                      # local-use range (0 - 0x7ffff); a registered id later if it's shared
CLASSIFICATION = "drawdb/geometry/reviewNotes"
REGISTRANT = "reviewNotesDrawOverride"
FILTER = "reviewNotes"                    # Show menu > Review notes
VERSION = "0.2.1"


def maya_useNewAPI():
    pass


class ReviewNotesNode(omui.MPxLocatorNode):
    aFile = aNearby = aNearbyFrames = aOnlyOpen = aShowText = aOpacity = aHidePlaying = aDebugGate = None

    @staticmethod
    def creator():
        return ReviewNotesNode()

    @staticmethod
    def initialize():
        t = om.MFnTypedAttribute()
        n = om.MFnNumericAttribute()
        cls = ReviewNotesNode
        cls.aFile = t.create("reviewFile", "rf", om.MFnData.kString)
        cls.aNearby = n.create("showNearby", "sn", om.MFnNumericData.kBoolean, True)
        cls.aNearbyFrames = n.create("nearbyFrames", "nf", om.MFnNumericData.kInt, 6)
        n.setMin(0)
        n.setMax(48)
        cls.aOnlyOpen = n.create("onlyOpen", "oo", om.MFnNumericData.kBoolean, False)
        cls.aShowText = n.create("showText", "st", om.MFnNumericData.kBoolean, True)
        cls.aOpacity = n.create("opacity", "op", om.MFnNumericData.kFloat, 1.0)
        n.setMin(0.0)
        n.setMax(1.0)
        cls.aHidePlaying = n.create("hideWhilePlaying", "hp", om.MFnNumericData.kBoolean, False)
        cls.aDebugGate = n.create("showGate", "sg", om.MFnNumericData.kBoolean, False)
        for a in (cls.aFile, cls.aNearby, cls.aNearbyFrames, cls.aOnlyOpen, cls.aShowText, cls.aOpacity,
                  cls.aHidePlaying, cls.aDebugGate):
            om.MPxNode.addAttribute(a)

    def postConstructor(self):
        try:
            om.MFnDependencyNode(self.thisMObject()).setDoNotWrite(True)
        except Exception:
            pass

    def isBounded(self):
        return False


class DrawData(om.MUserData):
    def __init__(self):
        try:
            om.MUserData.__init__(self, False)
        except TypeError:
            om.MUserData.__init__(self)
        self.items = []
        self.scale = 1.0


_told = {}


def _drawing():
    """reviewNotes.nodedraw as it is NOW (after an update it's the new one: the installer reloads the folder)."""
    return importlib.import_module("reviewNotes.nodedraw")


def _tell_once(text):
    if _told.get("error") != text:
        _told["error"] = text
        if text:
            print("Review Notes: %s" % text)


class ReviewNotesDrawOverride(omr.MPxDrawOverride):
    @staticmethod
    def creator(obj):
        return ReviewNotesDrawOverride(obj)

    @staticmethod
    def draw(context, data):
        return

    def __init__(self, obj):
        omr.MPxDrawOverride.__init__(self, obj, ReviewNotesDrawOverride.draw, True)   # redrawn every refresh

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def isBounded(self, objPath, cameraPath):
        return False

    def hasUIDrawables(self):
        return True

    def prepareForDraw(self, objPath, cameraPath, frameContext, oldData):
        data = oldData if isinstance(oldData, DrawData) else DrawData()
        data.items = []
        try:
            data.items, data.scale = _drawing().prepare(objPath, cameraPath, frameContext)
            _tell_once("")
        except Exception as e:                     # a drawing problem must never break the viewport
            _tell_once("nothing drawn (%s)" % e)
        return data

    def addUIDrawables(self, objPath, dm, frameContext, data):
        if not isinstance(data, DrawData) or not data.items:
            return
        try:
            _drawing().paint(dm, data.items, data.scale)
        except Exception as e:
            _tell_once("nothing drawn (%s)" % e)


def initializePlugin(obj):
    plugin = om.MFnPlugin(obj, "Gus", VERSION)
    plugin.registerNode(NODE_TYPE, om.MTypeId(NODE_ID), ReviewNotesNode.creator, ReviewNotesNode.initialize,
                        om.MPxNode.kLocatorNode, CLASSIFICATION)
    omr.MDrawRegistry.registerDrawOverrideCreator(CLASSIFICATION, REGISTRANT, ReviewNotesDrawOverride.creator)
    try:
        cmds.pluginDisplayFilter(FILTER, register=True, label="Review notes", classification=CLASSIFICATION)
    except Exception as e:
        print("Review Notes: no Show menu entry (%s)" % e)


def uninitializePlugin(obj):
    plugin = om.MFnPlugin(obj)
    try:
        cmds.pluginDisplayFilter(FILTER, deregister=True)
    except Exception:
        pass
    omr.MDrawRegistry.deregisterDrawOverrideCreator(CLASSIFICATION, REGISTRANT)
    plugin.deregisterNode(om.MTypeId(NODE_ID))
