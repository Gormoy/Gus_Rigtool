"""
The REVIEW_NOTES node's drawing, called by the plugin on every refresh.

It lives here, not in the plugin file, so an update takes effect as soon as the installer runs: the installer
reloads the reviewNotes folder, while a plugin's own code only reloads when the plugin is unloaded (0.1.1 needed
a Maya restart - Gus, 2026-11-21). The plugin (plugin/reviewNotesNode.py) only registers the node, its settings
and the draw override, and hands each refresh to prepare() and paint() here.
"""

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.api.OpenMayaRender as omr
import maya.cmds as cmds

from reviewNotes import draw, store

_said = {}


def say(key, text):
    """A line in the Script Editor, once per new message (drawing runs on every refresh)."""
    if _said.get(key) != text:
        _said[key] = text
        if text:
            print("Review Notes: %s" % text)


def pixel_ratio():
    """Screen pixels per point: 2 on a Mac Retina screen (MAYA_FACTS: view sizes are in screen pixels)."""
    try:
        try:
            from PySide2 import QtGui
        except ImportError:
            from PySide6 import QtGui
        return float(QtGui.QGuiApplication.primaryScreen().devicePixelRatio()) or 1.0
    except Exception:
        return 1.0


def render_aspect():
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


def options(node, scale):
    fn = om.MFnDependencyNode(node)

    def get(name):
        return fn.findPlug(name, False)
    return draw.Options(show_nearby=get("showNearby").asBool(), nearby_frames=get("nearbyFrames").asInt(),
                        only_open=get("onlyOpen").asBool(), show_text=get("showText").asBool(),
                        opacity=get("opacity").asFloat(), debug_gate=get("showGate").asBool(), scale=scale)


def prepare(objPath, cameraPath, frameContext):
    """(items, scale) for one view: what build_items() gives, in that view's pixels."""
    scale = pixel_ratio()
    node = objPath.node()
    opts = options(node, scale)
    if om.MFnDependencyNode(node).findPlug("hideWhilePlaying", False).asBool() and oma.MAnimControl.isPlaying():
        return [], scale
    notes, problem = store.notes_for_drawing(review_file(node))
    say("file", problem)
    if not notes and not opts.debug_gate:
        return [], scale
    cam_path = om.MDagPath(cameraPath)
    shape = cam_path.partialPathName()
    cam_path.pop()
    names = draw.camera_names(shape, cam_path.partialPathName())
    frame = int(round(oma.MAnimControl.currentTime().asUnits(om.MTime.uiUnit())))
    _, _, w, h = frameContext.getViewportDimensions()
    cam = om.MFnCamera(cameraPath)
    view = cam.getViewingFrustum(w / float(max(1, h)), True, False, True)
    render = cam.getRenderingFrustum(render_aspect())
    gate = draw.gate_rect(view, render, w, h)
    return draw.build_items(notes, names, frame, gate, opts), scale


def paint(dm, items, scale):
    """Draws the items with Maya's 2D drawing (dm = the MUIDrawManager)."""
    k = scale
    dm.beginDrawable()
    for item in items:
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
