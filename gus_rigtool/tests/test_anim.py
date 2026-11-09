# Gus Anim (the standalone animator tool) on a built biped + chain
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.setKeyframe = mock.MagicMock(); cmds.currentTime = mock.MagicMock(return_value=1.0)
cmds.optionVar = mock.MagicMock(return_value=False); cmds.text = mock.MagicMock(return_value=False)
import gus_anim as ga
ga.opt = lambda key, default: {"key_switch": 0}.get(key, default)
from gus_rigtool.builder import build as bld, guides
from gus_rigtool.core import mirror_engine as me
bld.biped(180)
g = bld.add_module("chain", "C", "tail", 180); s = guides.read(g)["settings"]
s["attach"] = "spine:hips"; s["options"]["type"] = "fk + ik spline"; guides.save_settings(g, s)
bld.build_all(180)
cmds.select("L_humerus_FK_ctrl"); print("settings of FK ctrl:", ga.short(ga.settings_of(ga.long_name("L_humerus_FK_ctrl"))))
cmds.select("tail_03_tweak_ctrl"); print("settings of tweak:", ga.short(ga.limbs_of_selection()[0]))
cmds.select("L_wrist_IK_ctrl", "tail_01_FK_ctrl"); ga.switch("ik")
print("after To IK:", getAttr("L_wrist_settings_ctrl.ikfk"), getAttr("tail_settings_ctrl.ikfk"))
ga.switch("toggle"); print("after toggle:", getAttr("L_wrist_settings_ctrl.ikfk"), getAttr("tail_settings_ctrl.ikfk"))
# FK control takes the IK joint's rotation
import numpy as np
A = lambda m: np.array(m).reshape(4, 4)
print("FK humerus == IK humerus joint (rotation):",
      np.allclose(A(world(S.get("L_humerus_FK_ctrl")))[:3, :3], A(world(S.get("L_humerus_IK_jnt")))[:3, :3], atol=1e-5))
# mirror pose: same answer as the Mirror tab's engine
S.get("L_humerus_FK_ctrl").attrs["rotate"] = [10.0, 25.0, -40.0]
cmds.select("L_humerus_FK_ctrl"); ga.mirror_pose("L>R")
mine = list(S.get("R_humerus_FK_ctrl").attrs["rotate"])
t, r, sc = me.pose_target(ga.long_name("L_humerus_FK_ctrl"), ga.long_name("R_humerus_FK_ctrl"), 0, [0, 0, 0])
print("mirror pose matches the Mirror tab:", np.allclose(mine, r, atol=1e-6), [round(v, 3) for v in mine])
cmds.select("L_humerus_FK_ctrl"); ga.select_twin(); print("twin:", [n.name for n in S.sel])
# space switch: no jump
ik = ga.long_name("L_wrist_IK_ctrl")
print("space attrs:", [a for a, _n in ga.space_attrs(ik)])
before = world(S.get("L_wrist_IK_ctrl"))
cmds.optionMenu = mock.MagicMock(side_effect=lambda *a, **k: "space" if k.get("value") else 3 if k.get("select") else None)
cmds.select("L_wrist_IK_ctrl"); ga.space_switch()
print("space now:", getAttr("L_wrist_IK_ctrl.space"), "| same place:", np.allclose(before, world(S.get("L_wrist_IK_ctrl")), atol=1e-6))
# reset + selection sets
cmds.select("L_humerus_FK_ctrl"); ga.reset_pose("selection"); print("reset:", S.get("L_humerus_FK_ctrl").attrs["rotate"])
ga.current_character = lambda: ""
for which in ("fk", "ik", "tweaks", "all"):
    ga.select_set(which); print(which, len(S.sel))
cmds.select("tail_02_FK_ctrl"); ga.select_set("limb"); print("tail limb:", len(S.sel))
print("characters:", ga.characters())
# the file Gus_Rigtool writes for animators
import tempfile
from gus_rigtool.builder import anim_export
files = anim_export.make(tempfile.mkdtemp())
print("written:", [os.path.basename(f) for f in files])
import json as _json
print("defaults.json:", _json.load(open(os.path.join(files[0], "defaults.json"))))
for f in sorted(os.listdir(files[0])):
    if f.endswith(".py"):
        compile(open(os.path.join(files[0], f)).read(), f, "exec")
print("package files:", sorted(f for f in os.listdir(files[0]) if f.endswith(".py")), "compile: True")
# a referenced rig: every name gets a namespace
for n in S.nodes:
    n.name = "hero:" + n.name
ga.current_character = lambda: "hero:"
cmds.select("hero:L_wrist_IK_ctrl"); ga.switch("fk")
print("namespaced switch:", getAttr("hero:L_wrist_settings_ctrl.ikfk"), "| characters:", ga.characters())
cmds.select("hero:tail_02_FK_ctrl"); ga.select_set("limb"); print("namespaced tail limb:", len(S.sel))
cmds.select("hero:L_humerus_FK_ctrl"); ga.select_twin(); print("namespaced twin:", [n.name for n in S.sel])
