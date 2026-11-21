"""
Review Notes self test - the things only real Maya can answer (CLAUDE.md rule 11). Run it in a NEW, EMPTY scene
(it exports the scene to a temp file to see what gets saved; your scene is not changed or saved):

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
    return loaded, "version %s" % cmds.pluginInfo(controller.PLUGIN, query=True, version=True)


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
    path = os.path.join(tempfile.mkdtemp(prefix="review_notes_test"), "export_test.ma")
    cmds.file(path, exportAll=True, type="mayaAscii", force=True)
    with open(path) as f:
        text = f.read()
    node_in = "REVIEW_NOTES" in text or "createNode reviewNotes" in text
    req = 'requires "reviewNotesNode"' in text
    return not node_in and not req, "node in the file: %s, 'requires reviewNotesNode': %s" % (node_in, req)


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


def run():
    del LINES[:]
    LINES.append("Review Notes %s self test - Maya %s" % (reviewNotes.__version__, cmds.about(version=True)))
    _check("plugin loads", _plugin)
    _check("one REVIEW_NOTES node", _one_node)
    _check("Show menu > Review notes", _show_menu)
    _check("Review notes shown in each view", _show_menu_in_views)
    _check("node not saved in the scene", _not_saved)
    _check("review file: save, read again, change", _file_round_trip)
    _check("camera of the view", _camera)
    text = "\n".join(LINES)
    print(text)
    fails = sum(1 for line in LINES if line.startswith("FAIL"))
    print("Review Notes self test: %s" % ("all ok" if not fails else "%d FAIL" % fails))
    return text
