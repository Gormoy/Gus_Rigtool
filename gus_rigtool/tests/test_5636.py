# 5.6.36: after the first real-Maya run on the Mac - your scene's model file found from its Windows path, Check
# this scene not crashing on a skin whose mesh didn't load, no reference node as 'history', Speed skipped with no
# window; test f on the wrist IK control; the self-test's rig checks in the run
import os, sys, tempfile
exec(open("fakemaya.py").read())
from unittest import mock
HERE = os.path.join(os.getcwd(), "..", "realmaya")
sys.path.insert(0, HERE)
import maya_cases as MC
from gus_rigtool import scene_check
from gus_rigtool.core import report as R
from gus_rigtool.tools import checker
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. your scene on the Mac: the model file saved with the Windows drive's path
tmp = tempfile.mkdtemp()
proj = os.path.join(tmp, "T7", "The Tree That Bloomed in Winter", "TTTBMW_Hare_Rigging").replace("\\", "/")
os.makedirs(os.path.join(proj, "scenes"))
os.makedirs(os.path.join(proj, "assets"))
scene = os.path.join(proj, "scenes", "Hare_Rigging_v210_NewSkinWeigh.ma")
model = os.path.join(proj, "assets", "Geo_Hare_08_MovedTail.mb")
for f in (scene, model):
    open(f, "w").close()
check("the project is the folder above 'scenes'", MC.project_of(scene) == proj)
win = "H:/Assignments/The Tree That Bloomed in Winter/TTTBMW_Hare_Rigging//assets/Geo_Hare_08_MovedTail.mb"
check("the Windows path (H:/...//assets/...) found in this computer's project",
      MC.local_path(win, proj) == model.replace("\\", "/"))
check("only the file name right: found in the project's assets folder",
      MC.local_path("D:/old/Geo_Hare_08_MovedTail.mb", proj) == model.replace("\\", "/"))
check("not there at all: None (the results say where it looked)", MC.local_path("H:/x/Nope.mb", proj) is None)
check("a path that's already right is kept", MC.local_path(model, proj) == model)

# --- 2. Check this scene on a skin whose mesh didn't load (the Hare on the Mac)
reset = lambda: S.__init__()
reset()
createNode("transform", name="Body")
createNode("mesh", name="BodyShape", parent="Body")
createNode("skinCluster", name="skinCluster10")
rep = R.Report("x")
q = {"geometry": ["BodyShape"], "influence": ["a_jnt"]}
def skin_q(s, **k):
    return next((v for f, v in q.items() if k.get(f)), None)
with mock.patch.object(cmds, "ls", lambda *a, **k: ["skinCluster10"] if k.get("type") == "skinCluster" else
                       (["|Body|BodyShape"] if a else [])), \
        mock.patch.object(cmds, "skinCluster", skin_q, create=True), \
        mock.patch.object(scene_check, "_skin_weights", mock.Mock(side_effect=scene_check.MissingMesh("Body"))), \
        mock.patch.object(cmds, "getAttr", lambda p, **k: 2), \
        mock.patch.object(cmds, "listConnections", lambda *a, **k: []):
    try:
        scene_check.check_skin(rep)
        crashed = None
    except Exception as e:
        crashed = e
text = rep.text()
check("Skin: the mesh that didn't load is said, the section doesn't crash (it did on the Mac)",
      crashed is None and "its mesh isn't loaded (Body) - weights not read" in text and "1 skin(s) read" in text)
check("MissingMesh is a ValueError, so Repair's skin read still skips it", issubclass(scene_check.MissingMesh,
                                                                                      ValueError))
src = open(checker.__file__).read()
check("Vertices over the influence limit: a skin with no influences left is skipped (division by zero on the Mac)",
      "if not count:" in src)
check("a reference node isn't 'non-deformer history' (Geo_Hare_07RNfosterParent1 on the Mac)",
      "reference" in checker._NOT_SHAPE)

# --- 3. Speed with no window
rep = R.Report("x")
with mock.patch.object(cmds, "about", lambda **k: True if k.get("batch") else "2024"):
    scene_check.check_speed(rep)
check("Speed: skipped and said why when Maya has no window (it read 0 ms on the Mac)",
      "speed skipped" in rep.text() and "ms" not in "".join(r[2] for r in rep.rows))

# --- 4. the real-Maya tests
src = open(os.path.join(HERE, "maya_cases.py")).read()
f = src[src.index("def ikfk_mirror"):src.index("def rig_selftest")]
check("test f takes the wrist's IK control, never the pole vector, and lets Maya catch up before measuring",
      '"wrist" in c.lower()' in f and '"pv" not in' in f and f.count("_settle()") >= 3)
check("the self-test's rig checks run too (g, after f)", [n for n, _f in MC.CASES][-1] == "g. rig self-test")
check("your scene: the model loaded from this computer, then the eye dry run, then closed without saving",
      "loadReferenceDepth=\"none\"" in src and "_load_references(rep, project)" in src and
      src.index("eye_dry_run, rep") < src.index("closed without saving\", path"))

print("%d/%d passed" % (sum(ok), len(ok)))
