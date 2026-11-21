"""
Review Notes - TRY-IT (CLAUDE.md rule 12: viewport looks proven before the tool is built).

Use a TEST scene (it clears undo when it runs again). Paste this whole file into a Python tab of the Script
Editor and run it, with the camera you want to test in the active view. It:
  1. writes a tiny test plugin to Maya's temp folder and loads it;
  2. writes a review file with 3 sample notes on THIS camera from the current frame, and 1 on "top";
  3. makes one node, REVIEW_NOTES_try, that draws the notes over the view.
Run it again to start fresh. Remove everything with:  review_try_remove()

What to look at (and screenshot):
  a. Display > Camera / Light Manipulator off; turn on the Resolution Gate (the view's gate button).
     The thin GREEN box with the + must sit exactly on Maya's gate. Resize the panel, 2D pan/zoom: still on it?
  b. Frames F..F+5: red arc (made with the curve tool) + label. F+6..F+9: yellow circle + arrow.
     F-6..F-1 and after: the same notes very faint (orange before, blue after).
  c. Look through "top": only the "top" note shows there.
  d. Onion skin ON in the same view: do the notes still show?
  e. Playblast F..F+9 (Show > Locators on): are the notes in the movie?
The Script Editor prints a line each time the camera, view size or gate changes - paste those lines too.
"""

import json
import os

import maya.cmds as cmds

PLUGIN_NAME = "gusReviewNotesTry"

PLUGIN_SOURCE = r'''
"""Review Notes try-it plugin (test only): one locator that draws review notes in 2D over its camera."""
import json
import math
import os

try:
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    import maya.api.OpenMayaRender as omr
    import maya.api.OpenMayaUI as omui
    IN_MAYA = True
except ImportError:            # the preview renderer imports the drawing maths without Maya
    IN_MAYA = False

NODE_TYPE = "gusReviewNotesTry"
NODE_ID = 0x0007F3A1           # local-use id range (0 - 0x7ffff), fine for a test
CLASSIFICATION = "drawdb/geometry/gusReviewNotesTry"
REGISTRANT = "gusReviewNotesTryOverride"
PAST = (0.16, 0.47, 1.0)       # the onion skin's colours
NEXT = (1.0, 0.51, 0.08)
NEARBY = 6
TYPE_COLOURS = {"change": (1.0, 0.70, 0.68), "fix": (1.0, 0.85, 0.54), "add": (0.62, 0.89, 0.76),
                "idea": (0.70, 0.78, 1.0)}


# ---------------- drawing maths (no Maya) ----------------
def bezier(anchors, closed=False, steps=16):
    pts = []
    spans = list(zip(anchors[:-1], anchors[1:]))
    if closed and len(anchors) > 1:
        spans.append((anchors[-1], anchors[0]))
    for n, (a, b) in enumerate(spans):
        p0, p1, p2, p3 = a[0], a[2], b[1], b[0]
        for i in range(0 if n == 0 else 1, steps + 1):
            t = i / float(steps)
            u = 1 - t
            pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def ellipse(a, b, n=48):
    cx, cy, rx, ry = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, abs(b[0] - a[0]) / 2.0, abs(b[1] - a[1]) / 2.0
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def polylines(stroke):
    """A stroke as lists of points in gate space (0-1, y down)."""
    tool = stroke.get("tool", "pen")
    if tool == "bezier":
        return [bezier(stroke.get("anchors", []), stroke.get("closed", False))]
    pts = [tuple(p[:2]) for p in stroke.get("points", [])]
    if len(pts) < 2:
        return []
    if tool == "circle":
        return [ellipse(pts[0], pts[-1])]
    if tool == "arrow":
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        ang = math.atan2((y1 - y0) * 9 / 16.0, x1 - x0)
        size = 0.025
        head = []
        for side in (-0.45, 0.45):
            head.append((x1 - size * math.cos(ang + side), y1 - size * math.sin(ang + side) * 16 / 9.0))
        return [[(x0, y0), (x1, y1)], [head[0], (x1, y1), head[1]]]
    return [pts]


def gate_rect(view, render, width, height):
    """Where the resolution gate is in the view, in pixels (x0, y0, x1, y1), y up from the bottom.
    view / render = (left, right, bottom, top) of the viewing and rendering frustums."""
    vl, vr, vb, vt = view
    rl, rr, rb, rt = render
    sx, sy = width / (vr - vl), height / (vt - vb)
    return ((rl - vl) * sx, (rb - vb) * sy, (rr - vl) * sx, (rt - vb) * sy)


def to_screen(p, gate):
    x0, y0, x1, y1 = gate
    return (x0 + p[0] * (x1 - x0), y1 - p[1] * (y1 - y0))


def camera_matches(note_camera, names):
    want = note_camera.split("|")[-1]
    return want in names or want.split(":")[-1] in names


def build_items(notes, camera_names, frame, gate, nearby=NEARBY):
    """Everything to draw: ("line", rgba, width, [screen points]) and ("text", rgba, (x, y), text)."""
    items = []
    x0, y0, x1, y1 = gate
    green = (0.35, 1.0, 0.45, 0.9)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    items.append(("line", green, 1.0, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]))
    items.append(("line", green, 1.0, [(cx - 10, cy), (cx + 10, cy)]))
    items.append(("line", green, 1.0, [(cx, cy - 10), (cx, cy + 10)]))
    row = 0
    for note in sorted(notes, key=lambda n: n.get("frame", 0)):
        if not camera_matches(note.get("camera", ""), camera_names):
            continue
        start, hold = int(note.get("frame", 0)), max(1, int(note.get("hold", 1)))
        end = start + hold - 1
        if start <= frame <= end:
            tint, alpha = None, 1.0
        elif start - nearby <= frame < start:
            tint, alpha = NEXT, 0.3
        elif end < frame <= end + nearby:
            tint, alpha = PAST, 0.3
        else:
            continue
        for stroke in note.get("strokes", []):
            rgb = tint or tuple(stroke.get("color", (1, 0.3, 0.26)))[:3]
            for line in polylines(stroke):
                items.append(("line", rgb + (alpha,), float(stroke.get("width", 3)),
                              [to_screen(p, gate) for p in line]))
        if tint is None and note.get("text"):
            label = "%s  %s" % (note.get("type", "note").upper(), note["text"])
            items.append(("text", TYPE_COLOURS.get(note.get("type"), (1, 1, 1)) + (1.0,),
                          (x0 + 10, y1 - 24 - row * 22), label))
            row += 1
    return items


_cache = {}


def load_notes(path):
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return []
    if _cache.get(path, (None,))[0] != stamp:
        try:
            with open(path) as f:
                _cache[path] = (stamp, json.load(f).get("notes", []))
        except (IOError, OSError, ValueError) as e:
            print("Review Notes try: can't read %s: %s" % (path, e))
            _cache[path] = (stamp, [])
    return _cache[path][1]


# ---------------- Maya ----------------
def maya_useNewAPI():
    pass


if IN_MAYA:
    class ReviewNode(omui.MPxLocatorNode):
        aFile = None

        @staticmethod
        def creator():
            return ReviewNode()

        @staticmethod
        def initialize():
            fn = om.MFnTypedAttribute()
            ReviewNode.aFile = fn.create("reviewFile", "rf", om.MFnData.kString)
            om.MPxNode.addAttribute(ReviewNode.aFile)

        def isBounded(self):
            return False

    class DrawData(om.MUserData):
        def __init__(self):
            try:
                om.MUserData.__init__(self, False)
            except TypeError:
                om.MUserData.__init__(self)
            self.items = []

    _last = {"said": None}

    def _render_aspect():
        sel = om.MSelectionList()
        sel.add("defaultResolution")
        fn = om.MFnDependencyNode(sel.getDependNode(0))
        w, h = fn.findPlug("width", False).asInt(), fn.findPlug("height", False).asInt()
        return fn.findPlug("deviceAspectRatio", False).asFloat() or (w / float(h)), w, h

    class ReviewDrawOverride(omr.MPxDrawOverride):
        @staticmethod
        def creator(obj):
            return ReviewDrawOverride(obj)

        @staticmethod
        def draw(context, data):
            return

        def __init__(self, obj):
            omr.MPxDrawOverride.__init__(self, obj, ReviewDrawOverride.draw, True)   # always redrawn

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
                plug = om.MFnDependencyNode(objPath.node()).findPlug("reviewFile", False)
                notes = load_notes(plug.asString())
                shape = om.MDagPath(cameraPath)
                names = {shape.partialPathName().split("|")[-1]}
                shape.pop()
                names.add(shape.partialPathName().split("|")[-1])
                names |= {n.split(":")[-1] for n in names}
                frame = int(round(oma.MAnimControl.currentTime().asUnits(om.MTime.uiUnit())))
                _, _, w, h = frameContext.getViewportDimensions()
                aspect, rw, rh = _render_aspect()
                cam = om.MFnCamera(cameraPath)
                view = cam.getViewingFrustum(w / float(h), True, False, True)
                render = cam.getRenderingFrustum(aspect)
                gate = gate_rect(view, render, w, h)
                said = (sorted(names)[0], w, h, tuple(round(g) for g in gate))
                if said != _last["said"]:
                    _last["said"] = said
                    print("Review Notes try: camera %s, view %dx%d, gate x %d-%d y %d-%d (render %dx%d, overscan %.2f)"
                          % (shape.partialPathName(), w, h, gate[0], gate[2], gate[1], gate[3], rw, rh,
                             cam.overscan))
                data.items = build_items(notes, names, frame, gate)
            except Exception as e:
                if _last.get("err") != str(e):
                    _last["err"] = str(e)
                    print("Review Notes try: nothing drawn: %s" % e)
            return data

        def addUIDrawables(self, objPath, dm, frameContext, data):
            if not isinstance(data, DrawData):
                return
            dm.beginDrawable()
            for item in data.items:
                if item[0] == "line":
                    _, rgba, width, pts = item
                    dm.setColor(om.MColor(rgba))
                    dm.setLineWidth(width)
                    dm.lineStrip(om.MPointArray([om.MPoint(x, y) for x, y in pts]), True)
                else:
                    _, rgba, (x, y), text = item
                    dm.setColor(om.MColor(rgba))
                    dm.setFontSize(omr.MUIDrawManager.kDefaultFontSize)
                    dm.text2d(om.MPoint(x, y), text, omr.MUIDrawManager.kLeft, [len(text) * 8 + 20, 20],
                              om.MColor((0.08, 0.08, 0.08, 0.75)), False)
            dm.endDrawable()


def initializePlugin(obj):
    plugin = om.MFnPlugin(obj, "Gus", "0.0.1-try")
    plugin.registerNode(NODE_TYPE, om.MTypeId(NODE_ID), ReviewNode.creator, ReviewNode.initialize,
                        om.MPxNode.kLocatorNode, CLASSIFICATION)
    omr.MDrawRegistry.registerDrawOverrideCreator(CLASSIFICATION, REGISTRANT, ReviewDrawOverride.creator)


def uninitializePlugin(obj):
    plugin = om.MFnPlugin(obj)
    omr.MDrawRegistry.deregisterDrawOverrideCreator(CLASSIFICATION, REGISTRANT)
    plugin.deregisterNode(om.MTypeId(NODE_ID))
'''


def _sample_notes(camera, f):
    """Three notes on this camera from frame f, one on top - the same file format the tool will use."""
    red, yellow, green = [1.0, 0.30, 0.26], [1.0, 0.82, 0.25], [0.30, 0.89, 0.63]
    return {"version": 1, "shot": "tryit", "fps": 24, "notes": [
        {"id": "n_0001", "camera": camera, "frame": f, "hold": 6, "type": "change", "status": "open",
         "text": "Arc at the top is too flat. Push the peak higher.", "author": "Gus",
         "strokes": [{"tool": "bezier", "color": red, "width": 3, "closed": False, "anchors": [
             [[0.30, 0.70], [0.30, 0.70], [0.33, 0.30]],
             [[0.45, 0.18], [0.37, 0.18], [0.53, 0.18]],
             [[0.60, 0.70], [0.57, 0.30], [0.60, 0.70]]]},
             {"tool": "arrow", "color": red, "width": 3, "points": [[0.45, 0.42], [0.45, 0.26]]}]},
        {"id": "n_0002", "camera": camera, "frame": f + 6, "hold": 4, "type": "fix", "status": "in progress",
         "text": "Contact: the foot slides. Lock it here.", "author": "Gus",
         "strokes": [{"tool": "circle", "color": yellow, "width": 3, "points": [[0.40, 0.72], [0.52, 0.90]]},
                     {"tool": "arrow", "color": yellow, "width": 3, "points": [[0.70, 0.60], [0.53, 0.78]]}]},
        {"id": "n_0003", "camera": "top", "frame": f, "hold": 10, "type": "add", "status": "open",
         "text": "Only on the top camera.", "author": "Gus",
         "strokes": [{"tool": "pen", "color": green, "width": 2,
                      "points": [[0.2, 0.5], [0.3, 0.45], [0.4, 0.5], [0.5, 0.45], [0.6, 0.5]]}]},
    ]}


def _active_camera():
    panel = cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
        panel = (cmds.getPanel(visiblePanels=True) or [""])[0]
    try:
        cam = cmds.modelPanel(panel, query=True, camera=True)
        if cmds.nodeType(cam) == "camera":
            cam = cmds.listRelatives(cam, parent=True)[0]
        return cam.split("|")[-1]
    except Exception:
        return "persp"


def review_try_remove():
    if cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
        nodes = cmds.ls(type=PLUGIN_NAME) or []
        if nodes:
            cmds.delete([cmds.listRelatives(n, parent=True)[0] for n in nodes])
        cmds.flushUndo()
        try:
            cmds.unloadPlugin(PLUGIN_NAME + ".py", force=True)
        except RuntimeError as e:
            print("Review Notes try: plugin kept loaded (%s)" % e)


def review_try():
    folder = os.path.join(cmds.internalVar(userTmpDir=True), "gus_review_try")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    review_try_remove()
    plugin = os.path.join(folder, PLUGIN_NAME + ".py")
    with open(plugin, "w") as f:
        f.write(PLUGIN_SOURCE)
    if not cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
        cmds.loadPlugin(plugin)
    camera = _active_camera()
    f0 = int(round(cmds.currentTime(query=True)))
    review = os.path.join(folder, "tryit.review.json")
    with open(review, "w") as f:
        json.dump(_sample_notes(camera, f0), f, indent=2)
    shape = cmds.createNode(PLUGIN_NAME, name="REVIEW_NOTES_tryShape")
    cmds.rename(cmds.listRelatives(shape, parent=True)[0], "REVIEW_NOTES_try")
    cmds.setAttr(shape + ".reviewFile", review, type="string")
    cmds.select(clear=True)
    cmds.refresh(force=True)
    print("Review Notes try: notes on %s, frames %d-%d (and one on top). File: %s" % (camera, f0, f0 + 9, review))
    print("Review Notes try: scrub %d-%d, check the green box against the Resolution Gate, then screenshot."
          % (f0 - 6, f0 + 15))


review_try()
