"""
Review Notes tests that run without Maya:

    python3 scripts/review_notes/tests/test_review_notes.py

- store: the review file (names, versions, reload-before-save, broken files never overwritten);
- draw: the maths of what's drawn (gate, curves, which notes show, colours, Retina sizes);
- plugin: the real plugin file run against a tiny stand-in for Maya's API (catches typos and wrong calls in
  its own code; how Maya itself draws is only proven by the try-it and the self test in Maya).
"""

import json
import os
import shutil
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from reviewNotes import draw, store  # noqa: E402

GATE = (377.0, 375.0, 2890.0, 1790.0)        # Gus's view on his Mac (Script Editor line, 2026-11-21)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sh010_anim" + store.SUFFIX)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_versions_dropped(self):
        self.assertEqual(store.split_version("/a/sh010_anim_v012.ma"), ("sh010_anim", "v012"))
        self.assertEqual(store.split_version("/a/sh010_anim.v3.mb"), ("sh010_anim", "v3"))
        self.assertEqual(store.split_version("/a/sh010_anim-V07.ma"), ("sh010_anim", "v07"))
        self.assertEqual(store.split_version("/a/sh010_anim.ma"), ("sh010_anim", ""))
        self.assertEqual(store.split_version("/a/v2.ma"), ("v2", ""))
        p12 = store.path_for_scene("/shots/sh010_anim_v012.ma")
        self.assertEqual(p12, store.path_for_scene("/shots/sh010_anim_v013.ma"))
        self.assertTrue(p12.endswith("sh010_anim.review.json"))

    def test_unsaved_scene_has_no_file(self):
        self.assertIsNone(store.path_for_scene(""))
        self.assertIsNone(store.path_for_scene("/x/untitled.ma"))

    def test_add_update_delete(self):
        a = store.add_note(self.path, store.make_note("shotCam", 1006, text="arc", scene_version="v012"))
        b = store.add_note(self.path, store.make_note("shotCam", 1020, kind="fix"))
        self.assertEqual((a["id"], b["id"]), ("n_0001", "n_0002"))
        store.update_note(self.path, "n_0001", status="done")
        data = store.read(self.path)
        self.assertEqual(data["notes"][0]["status"], "done")
        self.assertIn("updated", data["notes"][0])
        self.assertEqual(data["notes"][0]["scene_version"], "v012")
        self.assertTrue(store.delete_note(self.path, "n_0002"))
        self.assertFalse(store.delete_note(self.path, "n_0002"))
        self.assertEqual(len(store.read(self.path)["notes"]), 1)
        self.assertTrue(os.path.isfile(self.path + ".bak"))

    def test_someone_else_saved_meanwhile(self):
        store.add_note(self.path, store.make_note("shotCam", 1001, text="mine"))
        other = store.read(self.path)                                   # another Maya adds one meanwhile
        other["notes"].append(store.normalize_note({"id": "n_0007", "camera": "shotCam", "frame": 1010,
                                                    "text": "theirs"}))
        store.write(self.path, other)
        n = store.add_note(self.path, store.make_note("shotCam", 1030, text="mine again"))
        texts = [x["text"] for x in store.read(self.path)["notes"]]
        self.assertEqual(texts, ["mine", "theirs", "mine again"])
        self.assertEqual(n["id"], "n_0008")

    def test_broken_file_never_overwritten(self):
        with open(self.path, "w") as f:
            f.write("{ not json")
        with self.assertRaises(store.ReviewFileError):
            store.add_note(self.path, store.make_note("shotCam", 1001))
        with open(self.path) as f:
            self.assertEqual(f.read(), "{ not json")
        notes, problem = store.notes_for_drawing(self.path)
        self.assertEqual(notes, [])
        self.assertIn("can't be read", problem)

    def test_newer_format_refused(self):
        with open(self.path, "w") as f:
            json.dump({"version": 99, "notes": []}, f)
        with self.assertRaises(store.ReviewFileError):
            store.read(self.path)

    def test_unknown_fields_kept_and_defaults(self):
        with open(self.path, "w") as f:
            json.dump({"version": 1, "notes": [{"id": "n_0001", "camera": "cam", "frame": "12.6",
                                                "type": "weird", "future_field": 5}]}, f)
        n = store.read(self.path)["notes"][0]
        self.assertEqual((n["frame"], n["type"], n["status"], n["hold"]), (13, "change", "open", 1))
        self.assertEqual(n["future_field"], 5)
        self.assertIsNone(n["picture"])
        self.assertIsNone(n["pin"])

    def test_drawing_cache_follows_the_file(self):
        store.add_note(self.path, store.make_note("cam", 1))
        self.assertEqual(len(store.notes_for_drawing(self.path)[0]), 1)
        time.sleep(0.02)
        store.add_note(self.path, store.make_note("cam", 2))
        os.utime(self.path, (time.time() + 5, time.time() + 5))
        self.assertEqual(len(store.notes_for_drawing(self.path)[0]), 2)
        self.assertEqual(store.notes_for_drawing(os.path.join(self.dir, "none.review.json")), ([], ""))


def note(**kw):
    n = {"id": "n_0001", "camera": "shotCam", "frame": 1006, "hold": 6, "type": "change", "status": "open",
         "text": "Arc too flat", "strokes": [{"tool": "pen", "color": [1, 0, 0], "width": 3,
                                              "points": [[0.1, 0.1, 1], [0.2, 0.2, 1]]}]}
    n.update(kw)
    return n


class DrawTests(unittest.TestCase):
    def test_gate_from_frustums(self):
        render = (-0.5, 0.5, -0.28125, 0.28125)
        self.assertEqual(draw.gate_rect(render, render, 1920, 1080), (0.0, 0.0, 1920.0, 1080.0))
        view = (-0.65, 0.65, -0.65 / 1.5, 0.65 / 1.5)                     # overscan 1.3 in a 3:2 view
        x0, y0, x1, y1 = draw.gate_rect(view, render, 1500, 1000)
        self.assertAlmostEqual((x1 - x0) / (y1 - y0), 16 / 9.0)
        self.assertAlmostEqual((x0 + x1) / 2, 750)
        self.assertAlmostEqual(x1 - x0, 1500 / 1.3)

    def test_to_screen_top_left_is_up(self):
        self.assertEqual(draw.to_screen((0, 0), GATE), (377.0, 1790.0))
        self.assertEqual(draw.to_screen((1, 1), GATE), (2890.0, 375.0))

    def test_bezier_passes_through_its_points(self):
        anchors = [[[0.1, 0.5], [0.1, 0.5], [0.2, 0.1]], [[0.5, 0.1], [0.4, 0.1], [0.6, 0.1]],
                   [[0.9, 0.5], [0.8, 0.1], [0.9, 0.5]]]
        pts = draw.bezier(anchors, steps=16)
        self.assertEqual(len(pts), 33)
        self.assertEqual(pts[0], (0.1, 0.5))
        self.assertEqual(pts[16], (0.5, 0.1))
        self.assertEqual(pts[-1], (0.9, 0.5))
        closed = draw.bezier(anchors, closed=True)
        self.assertAlmostEqual(closed[-1][0], 0.1)
        self.assertEqual(draw.polylines({"tool": "bezier", "anchors": anchors[:1]}), [])

    def test_arrow_and_circle(self):
        shaft, head = draw.arrow((0.5, 0.8), (0.5, 0.2))
        self.assertEqual(shaft, [(0.5, 0.8), (0.5, 0.2)])
        self.assertEqual(head[1], (0.5, 0.2))
        self.assertAlmostEqual(head[0][0] - 0.5, 0.5 - head[2][0])          # symmetric
        self.assertGreater(head[0][1], 0.2)                                 # points back down the shaft
        ring = draw.ellipse((0.4, 0.7), (0.6, 0.9))
        self.assertAlmostEqual(ring[0][0], 0.6)
        self.assertEqual(draw.polylines({"tool": "pen", "points": [[0.1, 0.1]]}), [])
        self.assertEqual(len(draw.polylines({"tool": "something new", "points": [[0, 0], [1, 1]]})), 1)

    def test_cameras(self):
        names = draw.camera_names("shotCamShape", "chr:shotCam")
        self.assertEqual(names, {"shotCamShape", "shotCam", "chr:shotCam"})
        self.assertTrue(draw.camera_matches("shotCam", names))
        self.assertTrue(draw.camera_matches("|cams|chr:shotCam", names))
        self.assertFalse(draw.camera_matches("top", names))
        self.assertFalse(draw.camera_matches("", names))

    def test_when_notes_show(self):
        n = note()
        self.assertEqual([draw.note_state(n, f, 6) for f in (999, 1000, 1005, 1006, 1011, 1012, 1017, 1018)],
                         [None, "coming", "coming", "now", "now", "passed", "passed", None])
        self.assertIsNone(draw.note_state(n, 1005, 0))

    def test_build_items(self):
        notes = [note(), note(id="n_0002", camera="top"), note(id="n_0003", frame=1020, status="done", text="")]
        names = {"shotCam"}
        now = draw.build_items(notes, names, 1008, GATE)
        self.assertEqual([i[0] for i in now], ["line", "text"])              # only shotCam's note, one label
        self.assertEqual(now[0][1], (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(now[1][3], "CHANGE  Arc too flat")
        coming = draw.build_items(notes, names, 1015, GATE)                 # n_0003 (done) is 5 frames ahead
        self.assertEqual(len(coming), 2)
        self.assertEqual(coming[1][1][:3], draw.NEXT)
        self.assertAlmostEqual(coming[1][1][3], draw.NEARBY_ALPHA * draw.DONE_ALPHA)
        self.assertEqual(coming[0][1][:3], draw.PAST)                       # n_0001 ended at 1011
        done_now = draw.build_items(notes, names, 1020, GATE)
        self.assertEqual(done_now[-1][3], "CHANGE  [done]")
        only_open = draw.build_items(notes, names, 1020, GATE, draw.Options(only_open=True))
        self.assertTrue(all(i[0] == "line" and i[1][:3] == draw.PAST for i in only_open))
        quiet = draw.build_items(notes, names, 1015, GATE, draw.Options(show_nearby=False))
        self.assertEqual(quiet, [])

    def test_retina_and_gate_box(self):
        items = draw.build_items([note()], {"shotCam"}, 1006, GATE, draw.Options(scale=2.0, debug_gate=True))
        self.assertEqual(len(items), 5)                                      # box, +, +, stroke, label
        self.assertEqual(items[-1][2], (377.0 + 20, 1790.0 - 48))
        long_text = draw.label_text(note(text="x " * 200))
        self.assertTrue(long_text.endswith("..."))
        self.assertLessEqual(len(long_text), draw.LABEL_CHARS + 10)


# ---------------- the plugin against a tiny stand-in for Maya ----------------
def fake_maya(state):
    """Just enough of maya.api / maya.cmds for the plugin's own code to run."""
    om, oma, omr, omui, cmds = (types.ModuleType(n) for n in ("om", "oma", "omr", "omui", "cmds"))

    class Plug(object):
        def __init__(self, v):
            self.v = v

        def asString(self):
            return self.v

        asBool = asInt = asFloat = asString

    class MFnDependencyNode(object):
        def __init__(self, obj):
            self.obj = obj

        def findPlug(self, name, _wantNetworked):
            return Plug(state["attrs"][name])

        def setDoNotWrite(self, flag):
            state["doNotWrite"] = flag

    class MDagPath(object):
        def __init__(self, other=None):
            self.parts = list(other.parts) if other else ["shotCam", "shotCamShape"]

        def partialPathName(self):
            return self.parts[-1]

        def pop(self):
            self.parts.pop()

    class MFnCamera(object):
        overscan = 1.3

        def __init__(self, path):
            pass

        def getViewingFrustum(self, aspect, overscan, squeeze, panzoom):
            state["view_aspect"] = aspect
            return (-0.65, 0.65, -0.65 / aspect, 0.65 / aspect)

        def getRenderingFrustum(self, aspect):
            return (-0.5, 0.5, -0.5 / aspect, 0.5 / aspect)

    class MSelectionList(object):
        def add(self, name):
            pass

        def getDependNode(self, i):
            return "defaultResolution"

    class MTime(object):
        @staticmethod
        def uiUnit():
            return "film"

    class Now(object):
        def asUnits(self, unit):
            return state["frame"]

    class Base(object):
        def __init__(self, *a):
            pass

    class MUserData(object):
        def __init__(self, deleteAfterUse):
            pass

    class Recorder(object):
        def __getattr__(self, name):
            return lambda *a: state["drawn"].append((name,) + a)

    om.MUserData = MUserData
    om.MFnDependencyNode = MFnDependencyNode
    om.MDagPath = MDagPath
    om.MFnCamera = MFnCamera
    om.MSelectionList = MSelectionList
    om.MTime = MTime
    om.MColor = tuple
    om.MPoint = lambda x, y: (x, y)
    om.MPointArray = list
    om.MTypeId = int
    om.MPxNode = types.SimpleNamespace(kLocatorNode=1, addAttribute=lambda a: None)
    om.MFnTypedAttribute = om.MFnNumericAttribute = lambda: types.SimpleNamespace(
        create=lambda *a: a[0], setMin=lambda v: None, setMax=lambda v: None)
    om.MFnData = types.SimpleNamespace(kString=1)
    om.MFnNumericData = types.SimpleNamespace(kBoolean=1, kInt=2, kFloat=3)
    om.MFnPlugin = lambda *a: types.SimpleNamespace(
        registerNode=lambda *b: state["registered"].append(b[0]), deregisterNode=lambda *b: None)
    oma.MAnimControl = types.SimpleNamespace(currentTime=Now, isPlaying=lambda: state["playing"])
    omr.MPxDrawOverride = Base
    omr.MRenderer = types.SimpleNamespace(kAllDevices=7)
    omr.MUIDrawManager = types.SimpleNamespace(kDefaultFontSize=12, kLeft=0)
    omr.MDrawRegistry = types.SimpleNamespace(registerDrawOverrideCreator=lambda *a: state["registered"].append(a[1]),
                                              deregisterDrawOverrideCreator=lambda *a: None)
    omui.MPxLocatorNode = Base
    cmds.pluginDisplayFilter = lambda *a, **k: state["registered"].append(a[0])
    om1 = types.ModuleType("maya.OpenMaya")                    # the OLD API: the only one with MFileIO
    om1.MFileIO = types.SimpleNamespace(currentFile=lambda: state["scene"])
    maya = types.ModuleType("maya")
    api = types.ModuleType("maya.api")
    mods = {"maya": maya, "maya.api": api, "maya.api.OpenMaya": om, "maya.api.OpenMayaAnim": oma,
            "maya.api.OpenMayaRender": omr, "maya.api.OpenMayaUI": omui, "maya.cmds": cmds,
            "maya.OpenMaya": om1}
    return mods, Recorder()


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        scene = os.path.join(self.dir, "sh010_anim_v012.ma")
        self.state = {"attrs": {"reviewFile": "", "showNearby": True, "nearbyFrames": 6, "onlyOpen": False,
                                "showText": True, "opacity": 1.0, "hideWhilePlaying": False, "showGate": False,
                                "width": 960, "height": 540, "deviceAspectRatio": 16 / 9.0},
                      "scene": scene, "frame": 1008, "playing": False, "drawn": [], "registered": []}
        store.add_note(store.path_for_scene(scene), store.make_note("shotCam", 1006, text="arc", strokes=[
            {"tool": "arrow", "color": [1, 0, 0], "width": 3, "points": [[0.4, 0.4], [0.4, 0.2]]}]))
        mods, self.dm = fake_maya(self.state)
        self.saved = {k: sys.modules.get(k) for k in mods}
        sys.modules.update(mods)
        sys.modules.pop("reviewNotes.plugin.reviewNotesNode", None)
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "reviewNotes", "plugin"))
        import reviewNotesNode
        self.plugin = reviewNotesNode

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("reviewNotesNode", None)
        sys.path.pop(0)
        shutil.rmtree(self.dir)

    def ctx(self, w=3268, h=2166):
        return types.SimpleNamespace(getViewportDimensions=lambda: (0, 0, w, h))

    def test_new_api_has_no_mfileio(self):
        """0.1.0 asked maya.api.OpenMaya for MFileIO (it isn't there) and drew nothing."""
        self.assertFalse(hasattr(sys.modules["maya.api.OpenMaya"], "MFileIO"))
        self.assertEqual(self.plugin.scene_file(), self.state["scene"])

    def test_registers_node_override_and_show_menu(self):
        self.plugin.initializePlugin(None)
        self.assertEqual(self.state["registered"], ["reviewNotes", "reviewNotesDrawOverride", "reviewNotes"])
        self.plugin.ReviewNotesNode.initialize()
        node = self.plugin.ReviewNotesNode()
        node.thisMObject = lambda: None
        node.postConstructor()
        self.assertTrue(self.state["doNotWrite"])

    def test_draws_the_scene_notes(self):
        o = self.plugin.ReviewNotesDrawOverride(None)
        cam = types.SimpleNamespace(parts=["shotCam", "shotCamShape"])
        data = o.prepareForDraw(types.SimpleNamespace(node=lambda: None), cam, self.ctx(), None)
        self.assertEqual([i[0] for i in data.items], ["line", "line", "text"])
        self.assertAlmostEqual(self.state["view_aspect"], 3268 / 2166.0)
        o.addUIDrawables(None, self.dm, None, data)
        calls = [c[0] for c in self.state["drawn"]]
        self.assertEqual(calls[0], "beginDrawable")
        self.assertEqual(calls[-1], "endDrawable")
        self.assertEqual(calls.count("lineStrip"), 2)
        self.assertEqual(calls.count("text2d"), 1)

    def test_other_camera_playing_and_broken_file(self):
        o = self.plugin.ReviewNotesDrawOverride(None)
        top = types.SimpleNamespace(parts=["top", "topShape"])
        obj = types.SimpleNamespace(node=lambda: None)
        self.assertEqual(o.prepareForDraw(obj, top, self.ctx(), None).items, [])
        self.state["attrs"]["hideWhilePlaying"] = True
        self.state["playing"] = True
        cam = types.SimpleNamespace(parts=["shotCam", "shotCamShape"])
        self.assertEqual(o.prepareForDraw(obj, cam, self.ctx(), None).items, [])
        self.state["playing"] = False
        with open(store.path_for_scene(self.state["scene"]), "w") as f:
            f.write("broken")
        self.assertEqual(o.prepareForDraw(obj, cam, self.ctx(), None).items, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
