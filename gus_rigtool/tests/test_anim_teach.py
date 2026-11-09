# Gus Anim: teach a limb of "another rig" (plain names), then To FK / To IK put the controls on the joints
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.setKeyframe = mock.MagicMock(); cmds.currentTime = mock.MagicMock(return_value=1.0)
cmds.optionVar = mock.MagicMock(return_value=False); cmds.text = mock.MagicMock(return_value=False)
import gus_anim as ga
ga.opt = lambda key, default: {"key_switch": 0}.get(key, default)
import numpy as np
A = lambda m: np.array(m).reshape(4, 4)
def make(name, parent=None, t=(0, 0, 0), ntype="transform"):
    n = cmds.createNode(ntype, name=name, parent=parent); cmds.setAttr(n + ".translate", *t); return n
# a little "other" rig: 3 joints, 3 FK controls (a bit rotated), IK control, pole vector, switch on a settings node
j1 = make("arm_a_jnt", None, (0, 10, 0), "joint"); j2 = make("arm_b_jnt", j1, (5, 0, -1), "joint"); j3 = make("arm_c_jnt", j2, (5, 0, 1), "joint")
f1 = make("FK_arm_a"); f2 = make("FK_arm_b", f1); f3 = make("FK_arm_c", f2)
cmds.setAttr(f1 + ".translate", 0, 10, 0); cmds.setAttr(f2 + ".translate", 5, 0, -1); cmds.setAttr(f3 + ".translate", 5, 0, 1)
cmds.setAttr(f1 + ".rotate", 0, 0, 30)                                   # controls don't sit like the joints
ik = make("IK_arm", None, (10, 10, 0)); cmds.setAttr(ik + ".rotate", 0, 45, 0)
pv = make("PV_arm", None, (5, 10, -10)); sw = make("arm_settings")
cmds.addAttr(sw, longName="FKIKBlend", attributeType="double", defaultValue=0)
L = lambda n: ga.long_name(n)
ga.teach("L_arm", [L(f1), L(f2), L(f3)], [L(j1), L(j2), L(j3)], L(ik), L(pv), "arm_settings.FKIKBlend", 0.0, 10.0)
print("taught:", sorted(ga.taught_data()), "| from the IK control:", ga.taught_of(L(ik)).name)
cmds.select(L(f2)); print("limbs of FK_arm_b:", [l.name for l in ga.limbs_of_selection()])
# the joints move (as if the IK moved them), then To FK
cmds.setAttr(j1 + ".rotate", 0, 20, 10); cmds.setAttr(j2 + ".rotate", 0, 0, -35)
d = ga.taught_data()["L_arm"]
cmds.select(L(ik)); ga.switch("fk")
ok = all(np.allclose((A(world(S.get(c))) @ np.linalg.inv(A(world(S.get(j)))))[:3, :3], A(off)[:3, :3], atol=1e-5)
         for c, j, off in zip(("FK_arm_a", "FK_arm_b", "FK_arm_c"), ("arm_a_jnt", "arm_b_jnt", "arm_c_jnt"), d["fk_off"]))
print("To FK: controls sit on the joints as taught:", ok, "| switch:", getAttr("arm_settings.FKIKBlend"))
ga.switch("ik")
ok = np.allclose(A(world(S.get("IK_arm"))) @ np.linalg.inv(A(world(S.get("arm_c_jnt")))), A(d["ik_off"]), atol=1e-5)
print("To IK: IK control on the end joint as taught:", ok, "| switch:", getAttr("arm_settings.FKIKBlend"))
ga.switch("toggle"); print("toggle ->", getAttr("arm_settings.FKIKBlend"))
ga.forget("L_arm"); print("after forget:", sorted(ga.taught_data()))
