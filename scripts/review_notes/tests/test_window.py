"""
The Review Notes window built with real Qt (PySide6, off-screen) on a stand-in for Maya: it opens, saves a
note, lists, filters and changes notes. REVIEW_NOTES_PICTURE=<path in the repo> also saves a picture of it.

    pip install PySide6
    QT_QPA_PLATFORM=offscreen python3 scripts/review_notes/tests/test_window.py
"""

import os
import shutil
import sys
import tempfile
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))

STATE = {"scene": "", "time": 1012.0, "ctx": "selectSuperContext", "messages": [], "looked": None}


def _fake_maya():
    cmds = types.ModuleType("maya.cmds")

    def file(*a, **k):
        return STATE["scene"] if k.get("sceneName") else None

    def getPanel(*a, **k):
        if k.get("withFocus"):
            return "modelPanel4"
        if k.get("typeOf"):
            return "modelPanel"
        return ["modelPanel4"]

    def currentTime(*a, **k):
        if k.get("query"):
            return STATE["time"]
        STATE["time"] = a[0]

    cmds.file = file
    cmds.getPanel = getPanel
    cmds.modelPanel = lambda *a, **k: "shotCam"
    cmds.nodeType = lambda n: "transform"
    cmds.pluginInfo = lambda *a, **k: False
    cmds.ls = lambda *a, **k: []
    cmds.currentTime = currentTime
    cmds.objExists = lambda n: True
    cmds.lookThru = lambda panel, cam: STATE.__setitem__("looked", (panel, cam))
    cmds.inViewMessage = lambda **k: STATE["messages"].append(k.get("amg"))
    cmds.currentCtx = lambda: STATE["ctx"]
    cmds.setToolTo = lambda c: STATE.__setitem__("ctx", c)
    cmds.refresh = lambda **k: None
    cmds.undoInfo = lambda *a, **k: True
    mods = {"maya": types.ModuleType("maya"), "maya.cmds": cmds, "maya.api": types.ModuleType("maya.api")}
    for name in ("OpenMaya", "OpenMayaAnim", "OpenMayaRender", "OpenMayaUI"):
        mods["maya.api." + name] = types.ModuleType("maya.api." + name)
    sys.modules.update(mods)


_fake_maya()
from reviewNotes.qt import QtWidgets  # noqa: E402
from reviewNotes import controller, sketch, store, window  # noqa: E402

controller.ensure_node = lambda: "REVIEW_NOTESShape"      # the node itself is tested in Maya (self test)

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        STATE["scene"] = os.path.join(self.dir, "sh010_anim_v012.ma")
        self.path = store.path_for_scene(STATE["scene"])
        store.add_note(self.path, store.make_note("shotCam", 1001, 6, "change", "Arc too flat, push the peak higher."))
        n = store.add_note(self.path, store.make_note("shotCam", 1018, 4, "fix", "Contact: the foot slides."))
        store.update_note(self.path, n["id"], status="in progress")
        n = store.add_note(self.path, store.make_note("closeCam", 1024, 8, "add", "2 frame squash before the jump."))
        store.add_note(self.path, store.make_note("shotCam", 1038, 6, "idea", "Try a small hang at the last peak."))
        store.update_note(self.path, "n_0004", status="done")
        sketch.SKETCH.clear()
        self.w = window.show()
        APP.processEvents()

    def tearDown(self):
        window.close()
        APP.processEvents()
        shutil.rmtree(self.dir)

    def rows(self):
        return [self.w.list.topLevelItem(i).text(4) for i in range(self.w.list.topLevelItemCount())]

    def test_lists_and_filters(self):
        self.assertEqual(len(self.rows()), 4)
        self.w.filter.setCurrentText("Open")
        self.assertEqual(len(self.rows()), 3)
        self.w.filter.setCurrentText("This camera")
        self.assertEqual(len(self.rows()), 3)                     # shotCam's
        self.assertIn(self.path, self.w.path.text())

    def test_go_to_status_and_save(self):
        self.w.list.setCurrentItem(self.w.list.topLevelItem(2))
        self.w._go()
        self.assertEqual(STATE["time"], 1024)
        self.assertEqual(STATE["looked"], ("modelPanel4", "closeCam"))
        self.w._next_status()
        self.assertEqual(store.read(self.path)["notes"][2]["status"], "in progress")
        self.w.text.setPlainText("Text-only note")
        self.w.kind.setCurrentText("idea")
        self.w.save()
        notes = store.read(self.path)["notes"]
        self.assertEqual((notes[-1]["text"], notes[-1]["type"], notes[-1]["camera"]), ("Text-only note", "idea",
                                                                                        "shotCam"))
        self.assertEqual(self.w.text.toPlainText(), "")
        self.assertEqual(len(self.rows()), 5)

    def test_opacity_slider(self):
        """0.2.3 (Gus): an opacity control for the drawings - it sets REVIEW_NOTES.opacity."""
        got = {}
        window.controller.node = lambda: "REVIEW_NOTESShape"
        window.cmds.setAttr = lambda plug, v, **k: got.__setitem__(plug, v)
        try:
            self.w.opacity.setValue(40)
        finally:
            window.controller.node = lambda: None
        self.assertEqual(got, {"REVIEW_NOTESShape.opacity": 0.4})
        self.assertEqual(self.w.opacity_value.text(), "40%")

    def test_picture(self):
        """A picture of the window with a drawing in progress, for Gus (design/review_notes/window_0.2.0.png)."""
        s = sketch.SKETCH
        s.start("shotCam", 1012)
        s.set_tool("curve")
        for p in ((0.3, 0.7), (0.45, 0.2), (0.6, 0.7)):
            s.press(p)
            s.release(p)
        STATE["ctx"] = "reviewNotesDrawCtx"
        self.w.text.setPlainText("Arc at the top is too flat. Push the peak higher.")
        self.w.list.setCurrentItem(self.w.list.topLevelItem(0))
        self.w.resize(460, 640)
        self.w.sync()
        APP.processEvents()
        self.assertTrue(self.w.draw_btn.isChecked())
        self.assertIn("Not saved yet: 1 stroke(s) on shotCam", self.w.state.text())
        self.assertTrue(self.w.end_curve_btn.isEnabled())
        out = os.environ.get("REVIEW_NOTES_PICTURE")      # e.g. design/review_notes/window_0.2.0.png
        if out:
            self.w.grab().save(os.path.join(REPO, out))


if __name__ == "__main__":
    unittest.main(verbosity=1)
