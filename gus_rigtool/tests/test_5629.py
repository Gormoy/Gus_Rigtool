# 5.6.29: Publish learns the mirror table on every control Animtool sees, the Clothes switch (Full / Hidden),
# more speed timings (clothes hidden, GPU override off, each heavy skin), joints with no weight through Repair,
# checks that couldn't run are said, the test runner (exact names, prefixes, --update needs names), the
# diagnostic scripts and the control options table
import ast, os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_rigtool.core import repair, clothes_switch as CS, report as R
from gus_rigtool.core import rigspeed as speed
from gus_rigtool import scene_check
from gus_rigtool.builder import publish
ok = []
def reset():
    S.__init__()
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

DEFORMERS = ("skinCluster", "deltaMush", "ffd", "tweak")
real_type = cmds.objectType
def otype(name, isAType=None):
    if isAType == "geometryFilter":
        return real_type(name) in DEFORMERS
    return real_type(name, isAType=isAType)

# --- 1. Publish: the mirror table on every control Animtool sees
A = mock.MagicMock()
A.namespace_of.return_value = ""
A.character_controls.return_value = ["|ctrl|Hand_ctrl", "|ribbons|Cape_fol_04_ctrl", "|ribbons|Collar_fol_09_ctrl"]
got = publish.mirror_table_controls(A, ["|ctrl|Hand_ctrl", "|ctrl|COG_ctrl"])
check("the rig's controls, then every other control Animtool sees (the cape's ribbons) - each once",
      got == ["|ctrl|Hand_ctrl", "|ctrl|COG_ctrl", "|ribbons|Cape_fol_04_ctrl", "|ribbons|Collar_fol_09_ctrl"])
A.character_controls.side_effect = RuntimeError("no Animtool")
check("Animtool can't list them: the rig's own still learn", publish.mirror_table_controls(A, ["|c"]) == ["|c"])

# --- 2. the Clothes switch
reset()
createNode("transform", name="Visibility_ctrl")
for t in ("Hood", "Pants", "Hare_Body"):
    createNode("transform", name=t)
    createNode("mesh", name=t + "Shape", parent=t)
for d, kind in (("skinCluster18", "skinCluster"), ("skinCluster23", "skinCluster"), ("Pants_deltaMush", "deltaMush"),
                ("skinCluster10", "skinCluster"), ("Head_squash", "ffd")):
    createNode(kind, name=d)
    addAttr(d, longName="nodeState", attributeType="long")
hist = {"|Hood|HoodShape": ["skinCluster18"], "|Pants|PantsShape": ["skinCluster23", "Pants_deltaMush", "Head_squash"],
        "|Hare_Body|Hare_BodyShape": ["skinCluster10", "Head_squash"]}
deforms = {"skinCluster18": ["|Hood|HoodShape"], "skinCluster23": ["|Pants|PantsShape"],
           "Pants_deltaMush": ["|Pants|PantsShape"], "skinCluster10": ["|Hare_Body|Hare_BodyShape"],
           "Head_squash": ["|Pants|PantsShape", "|Hare_Body|Hare_BodyShape"]}
def history(node, **k):
    return list(hist.get(ls(node, long=True)[0], []))
def deformer(d, **k):
    return list(deforms[d])
with mock.patch.object(cmds, "listHistory", history), mock.patch.object(cmds, "deformer", deformer, create=True), \
        mock.patch.object(cmds, "objectType", otype), \
        mock.patch.object(CS, "_switch_control", lambda: ls("Visibility_ctrl", long=True)[0]):
    check("found by name: the skinned clothes (Hood, Pants), not the body", CS.suggest() == ["|Hood", "|Pants"])
    meshes, kept, switched = CS.plan(["Hood", "Pants"])
    check("switched with them: their own skins and delta mush; the head squash (it moves the body too) stays on",
          switched == ["skinCluster18", "skinCluster23", "Pants_deltaMush"] and
          kept == [("Head_squash", "it deforms other meshes too")])
    data = CS.make(["Hood", "Pants"])
    rev = data["reverse"]
    check("Visibility_ctrl.Clothes (Full / Hidden): the meshes' visibility through a reverse, the deformers' "
          "node state straight", getAttr("Visibility_ctrl.Clothes") == 0 and
          listConnections("Hood.visibility", source=True, destination=False) == [rev] and
          listConnections("skinCluster23.nodeState", source=True, destination=False, plugs=True) ==
          ["Visibility_ctrl.Clothes"] and not listConnections("Head_squash.nodeState", source=True,
                                                               destination=False))
    check("what it drives is kept on the switch", CS.read()["meshes"] == ["|Hood", "|Pants"])
    seen = []
    with CS.hidden() as there:
        seen.append((there, getAttr("Visibility_ctrl.Clothes")))
    check("for timing: hidden for a moment, then back at Full", seen == [(True, 1)] and
          getAttr("Visibility_ctrl.Clothes") == 0)
    CS.make(["Hood"])
    check("made again: the old one goes first (Pants back on)", CS.read()["meshes"] == ["|Hood"] and
          not listConnections("skinCluster23.nodeState", source=True, destination=False))
    check("removed: shown, on, the attribute gone", CS.remove() and not attributeQuery(
        "Clothes", node="Visibility_ctrl", exists=True) and not objExists(rev) and
        not listConnections("Hood.visibility", source=True, destination=False))
with mock.patch.object(CS, "_switch_control", lambda: None):
    try:
        CS.make(["Hood"])
        refused = False
    except RuntimeError as e:
        refused = "visibility switches first" in str(e)
check("no Visibility_ctrl yet: it says to make the switches first", refused)

# --- 3. speed timings
reset()
createNode("transform", name="COG_ctrl")
for sk in ("skinCluster10", "skinCluster18", "tinySkin"):
    createNode("skinCluster", name=sk)
    addAttr(sk, longName="nodeState", attributeType="long")
states = []
def step(plug, steps):
    off = [s for s in ("skinCluster10", "skinCluster18", "tinySkin") if getAttr(s + ".nodeState")]
    states.append(off)
    return 100.0 - 40.0 * ("skinCluster10" in off) - 10.0 * ("skinCluster18" in off) - 4.0 * ("tinySkin" in off)
with mock.patch.object(speed, "_step_time", step), mock.patch.object(cmds, "autoKeyframe", lambda **k: False,
                                                                    create=True):
    speed.time_drag(["|COG_ctrl"])
    check("an ordinary drag switches no skin off",
          states == [[]])
    t = speed.time_drag(["|COG_ctrl"], off=["skinCluster18"])
    check("off: only those deformers are switched off, then back on", states[-1] == ["skinCluster18"] and
          t["|COG_ctrl"] == 90.0 and getAttr("skinCluster18.nodeState") == 0)
    setAttr("COG_ctrl.translateX", lock=True)
    speed.time_drag(["|COG_ctrl"])
    check("a control that can't be dragged is said, with why", speed.SKIPPED == {"|COG_ctrl": "translateX is "
                                                                                    "locked or driven"})
    setAttr("COG_ctrl.translateX", lock=False)
    sizes = {"skinCluster10": (7300, 172), "skinCluster18": (677, 94), "tinySkin": (20, 1)}
    with mock.patch.object(speed, "_skin_size", lambda s: sizes[s]), \
            mock.patch.object(speed, "_mesh_of", lambda s: {"skinCluster10": "Hare_Body", "skinCluster18": "Hood"}
                              .get(s, "x")), \
            mock.patch.object(speed, "gpu_on", lambda: True), mock.patch.object(speed, "gpu_set", lambda on: True), \
            mock.patch.object(CS, "_switch_control", lambda: None):
        x = speed.extra_timings("|COG_ctrl", small=1)
check("each heavy skin off on its own, minus what every skin costs (the smallest: 4 ms)",
      x["base"] == 100.0 and x["overhead"] == 4.0 and
      [(s, m, round(g), round(r)) for s, m, _v, _n, g, r in x["skins"]] == [("skinCluster10", "Hare_Body", 40, 36),
                                                                             ("skinCluster18", "Hood", 10, 6)])
check("GPU override off timed (and back on); no clothes switch: not timed", x["gpu_off"] == 100.0 and
      x["clothes"] is None)
rep = R.Report("x")
rep.start("Speed")
with mock.patch.object(speed, "extra_timings", lambda c: {
        "base": 105.0, "clothes": 70.0, "gpu_off": 90.0, "overhead": 4.0, "skipped": [],
        "skins": [("skinCluster18", "Hood", 677, 94, 10.0, 6.0)]}):
    scene_check._speed_more(rep, speed, {"|COG_ctrl": 105.0, "|World_ctrl": 107.0})
text = rep.text()
check("Check this scene: the COG with the clothes hidden (35 ms saved)", "with the clothes hidden" in text and
      "35 ms saved" in text)
check("GPU override slower than off on this computer: a note", "GPU override is SLOWER than off for this rig: on 105 "
      "ms, off 90 ms" in text)
check("each heavy skin's cost above what every skin costs", "Hood 10.0 ms (6.0 above the ~4.0 ms every skin costs)"
      in text)

# --- 4. joints with no weight (Repair, safe mode); checks that couldn't run are said
reset()
createNode("skinCluster", name="skinCluster18")
createNode("skinCluster", name="ngSkin")
createNode("transform", name="Hood")
createNode("mesh", name="HoodShape", parent="Hood")
infl = {"skinCluster18": ["spine", "L_arm", "old_jnt"], "ngSkin": ["a", "b"]}
removed = []
def skin(name=None, **k):
    if k.get("query") and k.get("influence"):
        return [j for j in infl[name] if (name, j) not in removed]
    if k.get("query") and k.get("geometry"):
        return ["HoodShape"]
    if k.get("edit") and k.get("removeInfluence"):
        removed.append((name, k["removeInfluence"]))
    return []
from gus_rigtool.core import skin_tools
with mock.patch.object(cmds, "skinCluster", lambda *a, **k: skin(a[0] if a else None, **k)), \
        mock.patch.object(skin_tools, "unused_influences", lambda s: {"skinCluster18": ["old_jnt"],
                                                                      "ngSkin": ["b"]}[s]), \
        mock.patch.object(repair, "ng_skins", lambda: {"ngSkin"}):
    it = repair._skin_unused()
    check("found: Hood's joint with no weight (the ngSkinTools skin is left alone)", it.id == "skin_unused" and
          it.count == 1 and "Hood" in it.detail)
    msg = it.fix()
    check("fixed: taken out of the skin", removed == [("skinCluster18", "old_jnt")] and "1 joint(s)" in msg)
check("it goes through safe mode (rest, x2, animation)", repair.safe_states("skin_unused") == ("rest", "scale", "anim"))
def broken():
    """Something the Hare needs."""
    raise RuntimeError("Maya said no")
with mock.patch.object(repair, "FINDERS", [broken]):
    repair.find()
check("a check that couldn't run is listed with why (it used to look like 'nothing to repair')",
      repair.ERRORS == [("Something the Hare needs.", "Maya said no")])
rep = R.Report("x")
with mock.patch.object(repair, "stray_keys", mock.MagicMock(side_effect=RuntimeError("bad pairBlend"))):
    try:
        scene_check.check_ready(rep)
    except Exception:
        pass
check("Ready for animators: couldn't look for stray keys - said, not taken as none",
      "couldn't look for keys on constrained channels" in rep.text())

# --- 5. the test runner
import run_tests as RT
tests = ["/t/test_fix561.py", "/t/test_fix5617.py", "/t/test_publish.py", "/t/test_hand_publish501.py"]
got, unknown = RT.select(tests, ["publish"])
check("names are exact: 'publish' is only test_publish (5.6.28 also ran hand_publish501)",
      got == ["/t/test_publish.py"] and unknown == [])
got, unknown = RT.select(tests, ["fix56*", "nosuch"])
check("a name ending in * is a prefix; an unknown name is said", got == tests[:2] and unknown == ["nosuch"])
check("--update without names is refused", RT.main(["--update"]) == 1)

# --- 6. the diagnostic scripts and the options table
root = os.path.join(os.getcwd(), "..", "..", "scripts")
for f in ("diagnostics/squash_reach.py", "diagnostics/deltamush_scale.py", "audit/control_options.py"):
    with open(os.path.join(root, f)) as fh:
        ast.parse(fh.read())
check("the scripts read as Python", True)
sys.path.insert(0, os.path.join(root, "audit"))
import control_options as CO
lines, gaps = CO.table()
check("the options table: the Ribbon's distance in front and the Builder's shape turns are found where they are",
      "distance in front: only in Ribbon" in gaps and "shape turned (any angle): only in Builder" in gaps)
with open(os.path.join(root, "diagnostics", "deltamush_scale.py")) as fh:
    dm = fh.read()
check("the Delta Mush script never sets displacement above 1 (Maya refuses it)",
      'setAttr(dm + ".displacement", 1.0)' in dm and "2.0)" not in dm.split("displacement")[-1][:40])

print("%d/%d passed" % (sum(ok), len(ok)))
