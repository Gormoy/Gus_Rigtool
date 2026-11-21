"""
Review Notes self test - the things only real Maya can answer (CLAUDE.md rule 11). Run it in a NEW, EMPTY scene
(it saves that empty scene to a temp file to see what gets saved, then makes a new scene):

    import reviewNotes.selftest as t; t.run()

Paste the lines it prints. The look itself (notes on the right frames / camera, with the onion skin, in a
playblast) is checked with your eyes: rn.sample() then scrub.
"""

import os
import tempfile

import maya.cmds as cmds

import reviewNotes
from reviewNotes import controller, store

LINES = []


def _line(ok, what, detail=""):
    LINES.append("%s  %s%s" % ("ok  " if ok is True else ("INFO" if ok is None else "FAIL"), what,
                               (" - " + detail) if detail else ""))


def _check(what, fn):
    try:
        ok, detail = fn()
        _line(ok, what, detail)
    except Exception as e:
        _line(False, what, "error: %s" % e)


def _plugin():
    loaded = controller.load_plugin()
    version = cmds.pluginInfo(controller.PLUGIN, query=True, version=True)
    if version != reviewNotes.__version__:
        return False, "the plugin running is %s, the tool is %s - restart Maya" % (version, reviewNotes.__version__)
    return loaded, "version %s" % version


def _watching():
    n = len(controller._jobs)
    return n >= 5, "%d scene callbacks (open, before / after save, before / after export)" % n


def _one_node():
    a = controller.ensure_node()
    b = controller.ensure_node()
    n = len(cmds.ls(type=controller.NODE_TYPE) or [])
    return a == b and n == 1, "%s, %d node(s)" % (a, n)


def _show_menu():
    filters = cmds.pluginDisplayFilter(query=True, listFilters=True) or []
    return "reviewNotes" in filters, "Show menu filters: %s" % ", ".join(f for f in filters if "review" in f.lower())


def _show_menu_in_views():
    out = []
    for panel in cmds.getPanel(type="modelPanel") or []:
        try:
            on = cmds.modelEditor(panel, query=True, queryPluginObjects="reviewNotes")
            out.append("%s %s" % (panel, "on" if on else "OFF"))
        except Exception as e:
            out.append("%s ? (%s)" % (panel, e))
    return None, "; ".join(out)


def _not_saved():
    """A real SAVE, not an export: 0.1.1 passed the export check but a normal save wrote 'requires'."""
    if cmds.file(query=True, sceneName=True) or len(cmds.ls(dag=True)) > 30:
        return None, "skipped: run the self test in a NEW, EMPTY scene (File > New Scene)"
    path = os.path.join(tempfile.mkdtemp(prefix="review_notes_test"), "save_test.ma")
    controller.ensure_node()                     # the node IS there when the save starts
    cmds.file(rename=path)
    try:
        cmds.file(save=True, type="mayaAscii", force=True)
    finally:
        cmds.file(new=True, force=True)
    with open(path) as f:
        text = f.read()
    node_in = "REVIEW_NOTES" in text or "createNode reviewNotes" in text
    req = any(line.startswith("requires") and "reviewNotesNode" in line for line in text.splitlines())
    flag = cmds.pluginInfo(controller.PLUGIN, query=True, writeRequires=True)
    return not node_in and not req, "saved scene: node in it %s, 'requires reviewNotesNode' %s (plugin's writeRequires %s)" % (
        node_in, req, flag)


def _file_round_trip():
    folder = tempfile.mkdtemp(prefix="review_notes_test")
    path = store.path_for_scene(os.path.join(folder, "sh010_anim_v012.ma"))
    a = store.add_note(path, store.make_note("persp", 10, text="one"))
    store.add_note(path, store.make_note("persp", 20, text="two"))
    store.update_note(path, a["id"], status="done")
    data = store.read(path)
    ok = os.path.basename(path) == "sh010_anim.review.json" and len(data["notes"]) == 2 and \
        data["notes"][0]["status"] == "done"
    return ok, "%s, %d notes" % (os.path.basename(path), len(data["notes"]))


def _camera():
    cam = controller.current_camera()
    return cam is not None, "the view you clicked looks through %s" % cam


def _draw_tool():
    from reviewNotes import drawtool
    drawtool._make_context()
    ok = cmds.draggerContext(drawtool.CONTEXT, exists=True)
    return ok, "the drawing tool %s" % ("is there" if ok else "could not be made")


def _mouse():
    import maya.api.OpenMayaUI as omui
    from reviewNotes import drawtool, nodedraw
    view = omui.M3dView.active3dView()
    gate = nodedraw.view_gate(view)
    p = drawtool._mouse_on_gate(view)
    return None, "view %dx%d px, gate x %d-%d y %d-%d, the mouse now at %.2f, %.2f of the gate" % (
        view.portWidth(), view.portHeight(), gate[0], gate[2], gate[1], gate[3], p[0], p[1])


def _window():
    from reviewNotes import window
    w = window.show()
    rows = w.list.topLevelItemCount()
    window.close()
    return True, "opened and closed (%d note(s) listed)" % rows


def run():
    del LINES[:]
    LINES.append("Review Notes %s self test - Maya %s" % (reviewNotes.__version__, cmds.about(version=True)))
    _check("plugin loads", _plugin)
    _check("one REVIEW_NOTES node", _one_node)
    _check("watching saves", _watching)
    _check("Show menu > Review notes", _show_menu)
    _check("Review notes shown in each view", _show_menu_in_views)
    _check("review file: save, read again, change", _file_round_trip)
    _check("camera of the view", _camera)
    _check("drawing tool", _draw_tool)
    _check("mouse -> gate (where the mouse is)", _mouse)
    _check("the window", _window)
    _check("node not saved in the scene (a real save; ends with a new scene)", _not_saved)
    text = "\n".join(LINES)
    print(text)
    fails = sum(1 for line in LINES if line.startswith("FAIL"))
    print("Review Notes self test: %s" % ("all ok" if not fails else "%d FAIL" % fails))
    return text
