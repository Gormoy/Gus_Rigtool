"""
Review Notes in Maya: loads the plugin, keeps one REVIEW_NOTES node in the scene, and finds the review file.

    import reviewNotes.controller as rn
    rn.show()          # the shelf button: notes on, and what's in the review file
    rn.sample()        # adds a sample note on the camera you look through, on this frame (step 1 test)
    rn.off()           # removes the node (the notes stay in the file)

Step 1 has no drawing tools yet (step 2) and no notes window (step 3).
"""

import os

import maya.cmds as cmds

from reviewNotes import store

PLUGIN = "reviewNotesNode"
NODE = "REVIEW_NOTES"
NODE_TYPE = "reviewNotes"
HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_PATH = os.path.join(HERE, "plugin", PLUGIN + ".py")

_jobs = []


def _tell(msg, warn=False):
    print("Review Notes: %s" % msg)
    try:
        cmds.inViewMessage(amg=msg, pos="topCenter", fade=True, fadeStayTime=3000 if warn else 1500)
    except RuntimeError:
        pass


def load_plugin():
    if not cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        cmds.loadPlugin(PLUGIN_PATH, quiet=True)
    no_requires()
    return cmds.pluginInfo(PLUGIN, query=True, loaded=True)


def no_requires():
    """Saved scenes must not ask for this plugin: 0.1.1 wrote 'requires "reviewNotesNode.py"' into test.ma on a
    normal save (not on export), so opening it gave "Plug-in reviewNotesNode.py was not found" (Gus, 2026-11-21)."""
    try:
        cmds.pluginInfo(PLUGIN, edit=True, writeRequires=False)
        return True
    except Exception as e:
        print("Review Notes: saved scenes may ask for the plugin (%s)" % e)
        return False


def node():
    """The REVIEW_NOTES shape, or None."""
    if not cmds.pluginInfo(PLUGIN, query=True, loaded=True):
        return None
    found = cmds.ls(type=NODE_TYPE) or []
    return found[0] if found else None


def ensure_node():
    """One REVIEW_NOTES node (made if missing). Neither it nor its transform is saved in the scene."""
    load_plugin()
    shape = node()
    if shape:
        return shape
    sel = cmds.ls(selection=True)
    shape = cmds.createNode(NODE_TYPE, name=NODE + "Shape", skipSelect=True)
    xform = cmds.listRelatives(shape, parent=True)[0]
    xform = cmds.rename(xform, NODE)
    shape = cmds.listRelatives(xform, shapes=True)[0]
    try:
        import maya.api.OpenMaya as om
        sl = om.MSelectionList()
        sl.add(xform)
        om.MFnDependencyNode(sl.getDependNode(0)).setDoNotWrite(True)
    except Exception as e:
        print("Review Notes: the node may be saved in the scene (%s)" % e)
    for attr in ("translate", "rotate", "scale"):
        cmds.setAttr("%s.%s" % (xform, attr), lock=True)
    cmds.select(sel, replace=True) if sel else cmds.select(clear=True)
    return shape


def off():
    shape = node()
    if shape:
        cmds.delete(cmds.listRelatives(shape, parent=True))


def review_path():
    """The review file in use: the node's Review File, or the one next to the scene."""
    shape = node()
    if shape:
        own = cmds.getAttr(shape + ".reviewFile")
        if own:
            return own
    return store.path_for_scene(cmds.file(query=True, sceneName=True))


def current_camera():
    """The camera of the view you last clicked (or the first view on screen)."""
    panel = cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
        panels = cmds.getPanel(type="modelPanel") or []
        visible = set(cmds.getPanel(visiblePanels=True) or [])
        panel = next((p for p in panels if p in visible), None)
    if not panel:
        return None
    cam = cmds.modelPanel(panel, query=True, camera=True)
    if cmds.nodeType(cam) == "camera":
        cam = cmds.listRelatives(cam, parent=True)[0]
    return cam.split("|")[-1]


def summary(path):
    if not path:
        return "save the scene first: the notes go in a file next to it."
    try:
        notes = store.read(path)["notes"]
    except store.ReviewFileError as e:
        return str(e)
    if not notes:
        return "no notes yet for %s." % os.path.basename(path)[:-len(store.SUFFIX)]
    open_ = sum(1 for n in notes if n["status"] != "done")
    cams = sorted({n["camera"] for n in notes})
    return "%d note(s), %d open, on %s - %s" % (len(notes), open_, ", ".join(cams), path)


def show():
    """The shelf button (step 1): notes on in every view, and what's in the review file."""
    ensure_node()
    _tell(summary(review_path()))


def sample(text="Sample note: arc too flat here, push the peak higher.", hold=6):
    """Adds a sample note on the camera you look through, from this frame (tests the whole path in step 1)."""
    path = review_path()
    if not path:
        _tell("save the scene first: the notes go in a file next to it.", warn=True)
        return None
    cam = current_camera()
    if not cam:
        _tell("click in a camera view first.", warn=True)
        return None
    _, version = store.split_version(cmds.file(query=True, sceneName=True))
    frame = int(round(cmds.currentTime(query=True)))
    strokes = [{"tool": "bezier", "color": [1.0, 0.30, 0.26], "width": 3, "closed": False, "anchors": [
                   [[0.30, 0.70], [0.30, 0.70], [0.33, 0.30]],
                   [[0.45, 0.18], [0.37, 0.18], [0.53, 0.18]],
                   [[0.60, 0.70], [0.57, 0.30], [0.60, 0.70]]]},
               {"tool": "arrow", "color": [1.0, 0.30, 0.26], "width": 3, "points": [[0.45, 0.42], [0.45, 0.26]]}]
    note = store.add_note(path, store.make_note(cam, frame, hold, "change", text, strokes, scene_version=version))
    ensure_node()
    cmds.refresh(force=True)
    _tell("note %s added on %s, frames %d-%d." % (note["id"], cam, frame, frame + hold - 1))
    return note


# ---------------- opening scenes ----------------
def _after_open(*_):
    """A scene opened: if it has notes, they show (the node is made again: it's never saved in the scene)."""
    try:
        path = store.path_for_scene(cmds.file(query=True, sceneName=True))
        if path and os.path.isfile(path):
            ensure_node()
            print("Review Notes: %s" % summary(path))
    except Exception as e:
        print("Review Notes: notes not shown for this scene (%s)" % e)


def watch():
    """Called from userSetup.py at Maya start (the installer adds it)."""
    unwatch()
    try:
        import maya.api.OpenMaya as om
        _jobs.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, _after_open))
    except Exception as e:
        print("Review Notes: won't show notes when a scene opens (%s)" % e)


def unwatch():
    import maya.api.OpenMaya as om
    while _jobs:
        try:
            om.MMessage.removeCallback(_jobs.pop())
        except Exception:
            pass
