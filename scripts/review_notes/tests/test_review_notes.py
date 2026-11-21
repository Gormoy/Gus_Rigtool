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
        sys.modules.pop("reviewNotes.nodedraw", None)
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
        sys.modules.pop("reviewNotes.nodedraw", None)
        sys.path.pop(0)
        shutil.rmtree(self.dir)

    def ctx(self, w=3268, h=2166):
        return types.SimpleNamespace(getViewportDimensions=lambda: (0, 0, w, h))

    def test_new_api_has_no_mfileio(self):
        """0.1.0 asked maya.api.OpenMaya for MFileIO (it isn't there) and drew nothing."""
        self.assertFalse(hasattr(sys.modules["maya.api.OpenMaya"], "MFileIO"))
        self.assertEqual(self.plugin._drawing().scene_file(), self.state["scene"])

    def test_update_works_without_restart(self):
        """The plugin looks the drawing up on every refresh: after the installer reloads the folder (it drops the
        reviewNotes modules), the NEW drawing code is used - no Maya restart (Gus, 2026-11-21)."""
        o = self.plugin.ReviewNotesDrawOverride(None)
        cam = types.SimpleNamespace(parts=["shotCam", "shotCamShape"])
        obj = types.SimpleNamespace(node=lambda: None)
        self.assertEqual(len(o.prepareForDraw(obj, cam, self.ctx(), None).items), 3)
        new = types.ModuleType("reviewNotes.nodedraw")             # what an update would bring
        new.prepare = lambda *a: ([("line", (0, 1, 0, 1), 1.0, [(0, 0), (1, 1)])], 1.0)
        sys.modules["reviewNotes.nodedraw"] = new
        self.assertEqual(len(o.prepareForDraw(obj, cam, self.ctx(), None).items), 1)

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

    def test_unsaved_drawing_only_on_its_frame(self):
        from reviewNotes import sketch
        sys.modules.pop("reviewNotes.nodedraw", None)
        s = sketch.SKETCH
        s.clear()
        s.start("shotCam", 1008)
        s.press((0.1, 0.1))
        s.move((0.3, 0.3))
        s.release((0.3, 0.3))
        o = self.plugin.ReviewNotesDrawOverride(None)
        cam = types.SimpleNamespace(parts=["shotCam", "shotCamShape"])
        obj = types.SimpleNamespace(node=lambda: None)
        here = len(o.prepareForDraw(obj, cam, self.ctx(), None).items)
        self.state["frame"] = 1009
        there = len(o.prepareForDraw(obj, cam, self.ctx(), None).items)
        s.clear()
        self.assertEqual(here - there, 1)                     # only the drawing goes (the saved note holds 1006-1011)

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


class SaveTests(unittest.TestCase):
    """0.1.3: REVIEW_NOTES is out of the scene while it saves (Maya wrote 'requires reviewNotesNode' when it was
    there, even with do-not-write) and comes back after with its settings; none of it goes in the undo queue."""

    def setUp(self):
        st = self.st = {"nodes": {"REVIEW_NOTESShape": {"onlyOpen": True, "opacity": 0.5, "reviewFile": ""}},
                        "undo": True, "undo_while_deleting": None, "deferred": [], "made": 0}
        cmds = types.ModuleType("maya.cmds")

        def ls(*a, **k):
            return list(st["nodes"]) if k.get("type") == "reviewNotes" else []

        def delete(nodes):
            st["undo_while_deleting"] = st["undo"]
            st["nodes"].clear()

        def undoInfo(query=False, stateWithoutFlush=None):
            if query:
                return st["undo"]
            st["undo"] = stateWithoutFlush

        def setAttr(plug, value, type=None):
            name, attr = plug.split(".")
            st["nodes"][name][attr] = value

        cmds.ls = ls
        cmds.delete = delete
        cmds.undoInfo = undoInfo
        cmds.pluginInfo = lambda *a, **k: True
        cmds.listRelatives = lambda n, parent=False: ["REVIEW_NOTES"]
        cmds.getAttr = lambda plug: st["nodes"][plug.split(".")[0]].get(plug.split(".")[1], False)
        cmds.setAttr = setAttr
        cmds.evalDeferred = lambda fn, lowestPriority=False: st["deferred"].append(fn)
        self.saved = {k: sys.modules.get(k) for k in ("maya", "maya.cmds", "reviewNotes.controller")}
        sys.modules["maya"] = types.ModuleType("maya")
        sys.modules["maya.cmds"] = cmds
        sys.modules.pop("reviewNotes.controller", None)
        import importlib
        import reviewNotes
        if hasattr(reviewNotes, "controller"):
            del reviewNotes.controller                  # or the copy from the test before comes back
        controller = importlib.import_module("reviewNotes.controller")
        self.c = controller

        def ensure():
            st["made"] += 1
            st["nodes"]["REVIEW_NOTESShape"] = {}
            return "REVIEW_NOTESShape"
        controller.ensure_node = ensure

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_out_for_the_save_back_after(self):
        self.c._before_save()
        self.assertEqual(self.st["nodes"], {})                       # not there while Maya writes the file
        self.assertFalse(self.st["undo_while_deleting"])             # and not in the undo queue
        self.assertTrue(self.st["undo"])                             # undo back on after
        self.c._after_save()
        self.assertEqual(len(self.st["deferred"]), 1)                # put back once Maya is idle
        self.st["deferred"][0]()
        node = self.st["nodes"]["REVIEW_NOTESShape"]
        self.assertEqual((node["onlyOpen"], node["opacity"]), (True, 0.5))   # its settings kept
        self.assertTrue(self.st["undo"])

    def test_no_node_no_work(self):
        self.st["nodes"].clear()
        self.c._before_save()
        self.c._after_save()
        self.assertEqual((self.st["deferred"], self.st["made"]), ([], 0))


class SketchTests(unittest.TestCase):
    """Drawing a note: what each tool does with the mouse (sketch.py) and the mouse -> gate maths."""

    def setUp(self):
        from reviewNotes import sketch
        self.s = sketch.Sketch()
        self.s.start("shotCam", 1012)

    def test_from_screen_is_to_screen_backwards(self):
        for p in ((0.0, 0.0), (0.25, 0.8), (1.0, 1.0)):
            x, y = draw.to_screen(p, GATE)
            back = draw.from_screen(x, y, GATE)
            self.assertAlmostEqual(back[0], p[0])
            self.assertAlmostEqual(back[1], p[1])

    def test_pen(self):
        s = self.s
        s.press((0.1, 0.1))
        for i in range(1, 6):
            s.move((0.1 + i * 0.02, 0.1))
        s.release((0.2, 0.1))
        self.assertEqual(len(s.strokes), 1)
        self.assertEqual(s.strokes[0]["tool"], "pen")
        self.assertGreaterEqual(len(s.strokes[0]["points"]), 5)
        s.press((0.5, 0.5))
        s.release((0.5, 0.5))                                   # a click is not a stroke
        self.assertEqual(len(s.strokes), 1)

    def test_arrow_and_circle_two_points(self):
        s = self.s
        s.set_tool("arrow")
        s.press((0.7, 0.6))
        s.move((0.6, 0.7))
        s.release((0.53, 0.78))
        s.set_tool("circle")
        s.press((0.4, 0.72))
        s.release((0.52, 0.9))
        self.assertEqual([(x["tool"], x["points"]) for x in s.strokes],
                         [("arrow", [[0.7, 0.6], [0.53, 0.78]]), ("circle", [[0.4, 0.72], [0.52, 0.9]])])

    def test_curve_like_illustrator(self):
        s = self.s
        s.set_tool("curve")
        s.press((0.3, 0.7))
        s.release((0.3, 0.7))                                   # click = corner (no handles)
        s.press((0.45, 0.2))
        s.move((0.52, 0.2))
        s.release((0.53, 0.2))                                  # click-drag = smooth point
        s.press((0.6, 0.7))
        s.release((0.6, 0.7))
        a = s.curve["anchors"]
        self.assertEqual(a[0], [[0.3, 0.7], [0.3, 0.7], [0.3, 0.7]])
        self.assertEqual(a[1][2], [0.53, 0.2])                   # handle out where the mouse let go
        self.assertAlmostEqual(a[1][1][0], 0.37)                 # handle in mirrored
        self.assertEqual(len(s.handles()), 3)
        # drag the out handle: the in handle stays opposite (same length it had)
        s.press((0.53, 0.2))
        s.release((0.45, 0.12))
        out, inn = a[1][2], a[1][1]
        self.assertAlmostEqual(out[0] - 0.45, -(inn[0] - 0.45))
        self.assertAlmostEqual(out[1] - 0.2, -(inn[1] - 0.2))
        # Ctrl-drag breaks it: only that handle moves
        before = list(a[1][1])
        s.press(tuple(a[1][2]), ctrl=True)
        s.release((0.6, 0.3), ctrl=True)
        self.assertEqual(a[1][1], before)
        # drag a point: it moves with its handles
        s.press((0.6, 0.7))
        s.release((0.62, 0.72))
        self.assertEqual(a[2][0], [0.62, 0.72])
        # click the first point: closed and finished
        s.press((0.3, 0.7))
        self.assertIsNone(s.curve)
        self.assertTrue(s.strokes[-1]["closed"])
        self.assertEqual(s.strokes[-1]["tool"], "bezier")
        self.assertEqual(draw.polylines(s.strokes[-1])[0][0], draw.polylines(s.strokes[-1])[0][-1])

    def test_curve_ended_by_another_tool_or_save(self):
        s = self.s
        s.set_tool("curve")
        for p in ((0.1, 0.1), (0.2, 0.2)):
            s.press(p)
            s.release(p)
        s.set_tool("pen")
        self.assertEqual(len(s.strokes), 1)
        s.set_tool("curve")
        s.press((0.5, 0.5))
        s.release((0.5, 0.5))
        self.assertEqual(len(s.finish()), 1)                    # a 1-point curve is dropped
        self.assertIsNone(s.curve)

    def test_eraser_and_clear(self):
        s = self.s
        s.press((0.1, 0.1))
        s.move((0.3, 0.1))
        s.release((0.3, 0.1))
        s.set_tool("eraser")
        s.press((0.5, 0.9))
        self.assertEqual(len(s.strokes), 1)                      # far away: nothing
        s.press((0.2, 0.105))
        self.assertEqual(len(s.strokes), 2)                      # cut in two
        self.assertEqual((s.strokes[0]["points"][0], s.strokes[1]["points"][-1]), ([0.1, 0.1], [0.3, 0.1]))
        s.clear()
        self.assertIsNone(s.camera)

    def test_eraser_on_curves_circles_arrows(self):
        from reviewNotes import sketch
        curve = {"tool": "bezier", "color": [1, 0, 0], "width": 3, "closed": False,
                 "anchors": [[[0.1, 0.5], [0.1, 0.5], [0.2, 0.1]], [[0.5, 0.1], [0.4, 0.1], [0.6, 0.1]],
                             [[0.9, 0.5], [0.8, 0.1], [0.9, 0.5]]]}
        out, changed = sketch.cut([curve], (0.5, 0.1), 0.02)
        self.assertTrue(changed)
        self.assertEqual([x["tool"] for x in out], ["pen", "pen"])           # the arc split at its peak
        self.assertEqual(out[0]["color"], [1, 0, 0])
        ring = {"tool": "circle", "points": [[0.4, 0.7], [0.6, 0.9]]}
        out, changed = sketch.cut([ring], (0.6, 0.8), 0.02)
        self.assertEqual((changed, len(out)), (True, 1))                    # a ring cut once: one open line
        arrow = {"tool": "arrow", "points": [[0.1, 0.5], [0.4, 0.5]]}
        out, changed = sketch.cut([arrow], (0.25, 0.5), 0.02)
        self.assertEqual(len(out), 3)                                       # shaft in two + the head
        same, changed = sketch.cut([ring, arrow], (0.9, 0.1), 0.02)
        self.assertFalse(changed)
        self.assertEqual(same, [ring, arrow])                               # untouched: kept as they were

    def test_saved_notes_eraser_saves_once_keeps_backup(self):
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "shot.review.json")
            n = store.add_note(path, store.make_note("cam", 1, strokes=[{"tool": "pen", "points": [[0, 0], [1, 0]]}]))
            store.add_note(path, store.make_note("cam", 2))                 # the .bak now has note 1 as it was
            with open(path + ".bak") as f:
                before = f.read()
            store.set_strokes(path, {n["id"]: [{"tool": "pen", "points": [[0, 0], [0.4, 0]]}]}, backup=False)
            with open(path + ".bak") as f:
                self.assertEqual(f.read(), before)                          # a drag doesn't replace the backup
            self.assertEqual(store.read(path)["notes"][0]["strokes"][0]["points"], [[0, 0], [0.4, 0]])
        finally:
            shutil.rmtree(d)

    def test_drawing_shown_live_with_handles(self):
        s = self.s
        s.set_tool("curve")
        s.press((0.3, 0.7))
        s.move((0.35, 0.6))
        s.release((0.35, 0.6))
        items = draw.sketch_items(s.all_strokes(), s.handles(), GATE, 2.0)
        lines = [i for i in items if i[0] == "line"]
        self.assertEqual(len(lines), 5)                          # 2 handle lines + 2 handle dots + the point


class Fixes021Tests(unittest.TestCase):
    """0.2.1 (Gus): the drawing sticks to its frame, the eraser drags and finds strokes, Esc drops a curve."""

    def test_drag_eraser(self):
        """0.2.2: rubbing across two lines cuts a gap in each; the third line is left alone."""
        from reviewNotes import sketch
        s = sketch.Sketch()
        for y in (0.1, 0.3, 0.5):
            s.press((0.1, y))
            s.move((0.4, y))
            s.release((0.4, y))
        s.set_tool("eraser")
        s.press((0.25, 0.0))
        s.move((0.25, 0.2))
        s.move((0.25, 0.32))
        s.release((0.25, 0.32))
        self.assertEqual(len(s.strokes), 5)                    # 2 + 2 pieces, and the untouched line
        r = sketch.eraser_radius(s.width)
        for st in s.strokes:
            for q in st["points"]:
                if q[1] in (0.1, 0.3):
                    self.assertGreaterEqual(abs(q[0] - 0.25), r * 0.99)   # nothing left under the eraser
        self.assertIn([[0.1, 0.5], [0.4, 0.5]], [st["points"] for st in s.strokes])

    def test_nearest_on_saved_strokes(self):
        from reviewNotes import sketch
        strokes = [{"tool": "circle", "points": [[0.4, 0.7], [0.6, 0.9]]},
                   {"tool": "arrow", "points": [[0.1, 0.1], [0.3, 0.1]]}]
        self.assertEqual(sketch.nearest(strokes, (0.6, 0.8))[0], 0)        # on the circle's edge
        self.assertEqual(sketch.nearest(strokes, (0.2, 0.1))[0], 1)        # on the arrow's shaft
        self.assertEqual(sketch.nearest(strokes, (0.5, 0.8)), (None, None))  # inside the circle: nothing

    def test_esc_drops_the_curve(self):
        from reviewNotes import sketch
        s = sketch.Sketch()
        s.set_tool("curve")
        for p in ((0.1, 0.1), (0.2, 0.2)):
            s.press(p)
            s.release(p)
        s.cancel_curve()
        self.assertTrue(s.empty())


if __name__ == "__main__":
    unittest.main(verbosity=1)
