"""
Review Notes plugin: the REVIEW_NOTES node. One per scene; it draws every note of the scene's review file in 2D
over the camera each note belongs to, on the note's frames (nearby notes faint, the onion skin's colours).

It's a locator with a Viewport 2.0 draw override, not a render override, so it shows together with the onion
skin and in playblasts (try-it, Gus 2026-11-21). The node is never saved in the scene (do-not-write): the notes
live in the review file, and a scene sent to someone without the tool opens clean.

Settings are the node's attributes (Attribute Editor): Review File (empty = next to the scene), Show Nearby,
Nearby Frames, Only Open, Show Text, Opacity, Hide While Playing, Show Gate (the try-it's green box).
"""

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.api.OpenMayaRender as omr
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from reviewNotes import draw, store

NODE_TYPE = "reviewNotes"
NODE_ID = 0x0007F3A2                      # local-use range (0 - 0x7ffff); a registered id later if it's shared
CLASSIFICATION = "drawdb/geometry/reviewNotes"
REGISTRANT = "reviewNotesDrawOverride"
FILTER = "reviewNotes"                    # Show menu > Review notes
VERSION = "0.1.1"


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


_said = {}


def _say(key, text):
    """A line in the Script Editor, once per new message (drawing runs on every refresh)."""
    if _said.get(key) != text:
        _said[key] = text
        if text:
            print("Review Notes: %s" % text)


def _pixel_ratio():
    """Screen pixels per point: 2 on a Mac Retina screen (MAYA_FACTS: view sizes are in screen pixels)."""
    try:
        try:
            from PySide2 import QtGui
        except ImportError:
            from PySide6 import QtGui
        return float(QtGui.QGuiApplication.primaryScreen().devicePixelRatio()) or 1.0
    except Exception:
        return 1.0


def _render_aspect():
    sel = om.MSelectionList()
    sel.add("defaultResolution")
    fn = om.MFnDependencyNode(sel.getDependNode(0))
    w, h = fn.findPlug("width", False).asInt(), fn.findPlug("height", False).asInt()
    return fn.findPlug("deviceAspectRatio", False).asFloat() or (w / float(max(1, h)))


def scene_file():
    """The open scene's file. MFileIO is only in Maya's OLD Python API (maya.OpenMaya), not in maya.api.OpenMaya
    (0.1.0 used the new one: nothing was drawn - Gus, 2026-11-21)."""
    try:
        import maya.OpenMaya as om1
        return om1.MFileIO.currentFile()
    except Exception:
        return cmds.file(query=True, sceneName=True)


def review_file(node):
    """The node's Review File, or the file next to the open scene when it's empty."""
    path = om.MFnDependencyNode(node).findPlug("reviewFile", False).asString()
    return path or store.path_for_scene(scene_file())


def _options(node, scale):
    fn = om.MFnDependencyNode(node)

    def get(name):
        return fn.findPlug(name, False)
    return draw.Options(show_nearby=get("showNearby").asBool(), nearby_frames=get("nearbyFrames").asInt(),
                        only_open=get("onlyOpen").asBool(), show_text=get("showText").asBool(),
                        opacity=get("opacity").asFloat(), debug_gate=get("showGate").asBool(), scale=scale)


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
        data.scale = _pixel_ratio()
        try:
            node = objPath.node()
            options = _options(node, data.scale)
            if om.MFnDependencyNode(node).findPlug("hideWhilePlaying", False).asBool() and oma.MAnimControl.isPlaying():
                return data
            notes, problem = store.notes_for_drawing(review_file(node))
            _say("file", problem)
            if not notes and not options.debug_gate:
                return data
            cam_path = om.MDagPath(cameraPath)
            shape = cam_path.partialPathName()
            cam_path.pop()
            names = draw.camera_names(shape, cam_path.partialPathName())
            frame = int(round(oma.MAnimControl.currentTime().asUnits(om.MTime.uiUnit())))
            _, _, w, h = frameContext.getViewportDimensions()
            cam = om.MFnCamera(cameraPath)
            view = cam.getViewingFrustum(w / float(max(1, h)), True, False, True)
            render = cam.getRenderingFrustum(_render_aspect())
            gate = draw.gate_rect(view, render, w, h)
            data.items = draw.build_items(notes, names, frame, gate, options)
            _say("error", "")
        except Exception as e:                     # a drawing problem must never break the viewport
            _say("error", "nothing drawn (%s)" % e)
        return data

    def addUIDrawables(self, objPath, dm, frameContext, data):
        if not isinstance(data, DrawData) or not data.items:
            return
        k = data.scale
        dm.beginDrawable()
        for item in data.items:
            if item[0] == "line":
                _, rgba, width, pts = item
                dm.setColor(om.MColor(rgba))
                dm.setLineWidth(width * k)
                dm.lineStrip(om.MPointArray([om.MPoint(x, y) for x, y in pts]), True)
            else:
                _, rgba, (x, y), text = item
                dm.setColor(om.MColor(rgba))
                dm.setFontSize(omr.MUIDrawManager.kDefaultFontSize)
                dm.text2d(om.MPoint(x, y), text, omr.MUIDrawManager.kLeft,
                          [int((len(text) * 8 + 24) * k), int(20 * k)], om.MColor((0.08, 0.08, 0.08, 0.75)), False)
        dm.endDrawable()


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
