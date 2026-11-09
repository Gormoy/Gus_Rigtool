# 5.6.22: visibility - finer face parts (eyelid ribbons apart from the lid masters, pupils apart from the eyes, the
# mouth ribbon apart from the mouth); the clothes one switch each under Secondary_Ctrls; a switch of your own from
# the selection, under a master (one switch hides them all); Remove all takes every part away. The checker leaves
# a referenced mesh's history (it crashed). Deliver copies the pose library next to the rig; the animators' library
# fills itself from it once
import os, sys, tempfile, json
exec(open("fakemaya.py").read())
from gus_rigtool.core import vis_switch as VS
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
def mk(name, parent=None):
    c = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=c)
    return cmds.ls(c, long=True)[0]
parts = dict((n, VS.face_part(n)) for n in ("L_Eyelids_fol_01_ctrl", "L_Upper_Eyelids_ctrl", "L_Pupil_ctrl",
                                            "Eyes_ctrl", "L_Mouth_fol_06_ctrl", "Mouth_main_ctrl", "Jaw_end_ctrl",
                                            "L_Facial_ribbon_fol_05_ctrl", "L_Ear_01_FK_ctrl"))
print(parts)
check("face parts: lid ribbons / lid masters / pupils / eyes / mouth ribbon / mouth (jaw too) / facial / ears",
      list(parts.values()) == ["Eyelid_Ribbons", "Eyelids", "Pupils", "Eyes", "Mouth_Ribbon", "Mouth", "Mouth",
                               "Facial_Ribbons", "Ears"])
vis = mk("Visibility_ctrl")
for a in VS.SWITCHES:
    cmds.addAttr(vis, longName=a, attributeType="bool", defaultValue=True)
cmds.addAttr(vis, longName=VS.MARK, attributeType="bool", defaultValue=True)
collar, cape, sleeve, tw = mk("Collar_fol_09_ctrl"), mk("Cape_Ribbon_fol_04_ctrl"), mk("L_Sleeve_fol_05_ctrl"), \
    mk("L_humerus_bend_ctrl")
arm = mk("L_wrist_FK_ctrl")
for c in (collar, cape, sleeve, tw):
    cmds.connectAttr(vis + ".Secondary_Ctrls", c + "|" + c.split("|")[-1] + "Shape.visibility")
src = lambda c: (cmds.listConnections(c + "|" + c.split("|")[-1] + "Shape.visibility", source=True,
                                      destination=False) or [""])[0].split("|")[-1]
with mock.patch("gus_rigtool.core.on_top.controls", return_value=[vis, collar, cape, sleeve, tw, arm]), \
        mock.patch("gus_rigtool.core.on_top.is_face", return_value=False):
    lines, by = VS.secondary_plan()
    print("\n".join(lines))
    got = VS.split_secondary()
check("clothes: Collar, Cape, Sleeves, Tweaks each a switch, under Secondary_Ctrls",
      sorted(got["parts"]) == ["Cape", "Collar", "Sleeves", "Tweaks"] and
      [src(c) for c in (collar, cape, sleeve, tw)] == ["Secondary_Collar_vis_mdl", "Secondary_Cape_vis_mdl",
                                                       "Secondary_Sleeves_vis_mdl", "Secondary_Tweaks_vis_mdl"] and
      (cmds.listConnections("Secondary_Collar_vis_mdl.input1", source=True, destination=False) or [""])[0]
      .split("|")[-1] == "Visibility_ctrl")
check("... and they still count as on Secondary_Ctrls", VS.switch_of(collar) == "Secondary_Ctrls")
gear = mk("L_wrist_settings_ctrl")
cmds.addAttr(gear, longName="Body_Ctrls", attributeType="bool", defaultValue=True)
fingers = [mk("L_index_01_FK_ctrl"), mk("L_middle_01_FK_ctrl")]
moved, skipped = VS.add_switch(fingers, "Fingers", gear, "Body_Ctrls")
check("a switch of your own: Fingers on the wrist gear, under its Body_Ctrls",
      moved == 2 and src(fingers[0]) == "Body_Fingers_vis_mdl" and
      cmds.attributeQuery("Fingers", node=gear, exists=True) and "Fingers" in VS.recorded_parts(gear))
try:
    VS.add_switch(fingers, "Body_Ctrls", gear)
    refused = False
except RuntimeError:
    refused = True
check("a name the control has already: refused", refused)
check("its switches aren't offered as hand-made ones", not VS.hand_switches(gear))
out = VS.remove_all()
check("Remove all: every part gone, the controls shown", not VS.part_nodes() and src(collar) == "" and
      src(fingers[0]) == "" and not cmds.attributeQuery("Fingers", node=gear, exists=True))

# the checker: a referenced mesh is left (it crashed)
from gus_rigtool.tools import checker
m = cmds.createNode("transform", name="Geo:Eyebrows")
with mock.patch.object(cmds, "referenceQuery", side_effect=lambda n, **k: True if k.get("isNodeReferenced") else
                       "C:/models/Geo_Hare_08.mb"), \
        mock.patch.object(cmds, "bakePartialHistory", create=True, side_effect=RuntimeError("referenced")) as bake:
    n = checker.fix_mesh_history([cmds.ls(m, long=True)[0]])
check("mesh history in a referenced file: left (no crash), nothing baked", n == 0 and not bake.called)

# deliver: the pose library next to the rig; the animators' library fills itself once
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
from gus_rigtool.builder import deliver
lib = tempfile.mkdtemp()
src_dir = os.path.join(lib, "rig")
os.makedirs(os.path.join(src_dir, "Hands")); os.makedirs(os.path.join(src_dir, "clips"))
for f in ("Smile.json", "Smile.png", os.path.join("Hands", "fist.json"), os.path.join("clips", "walk.json")):
    open(os.path.join(src_dir, f), "w").write("{}")
out_dir = os.path.join(tempfile.mkdtemp(), "Hare_rig_poses")
with mock.patch.object(A, "character_folder", return_value=src_dir):
    got = deliver.copy_poses(out_dir)
check("Deliver: 2 poses (one in a folder) and a clip next to the rig", (got["poses"], got["clips"]) == (2, 1) and
      os.path.exists(os.path.join(out_dir, "Hands", "fist.json")))
mine = os.path.join(tempfile.mkdtemp(), "Hare")
os.makedirs(mine)
open(os.path.join(mine, "Smile.json"), "w").write('{"mine": 1}')
n = A._seed(mine, out_dir)
check("the animator's library: the rig's poses in, theirs not overwritten, once (marked)",
      n == 2 and json.load(open(os.path.join(mine, "Smile.json"))) == {"mine": 1} and
      os.path.exists(os.path.join(mine, "clips", "walk.json")) and os.path.exists(os.path.join(mine, ".rig_poses_seeded")))
print("%d/%d passed" % (sum(ok), len(ok)))
