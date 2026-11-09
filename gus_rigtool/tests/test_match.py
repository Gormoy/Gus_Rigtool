exec(open("fakemaya.py").read())
import numpy as np
from gus_rigtool.builder import build as bld, limb, guides
A=lambda m: np.array(m).reshape(4,4)
bld.biped(180); bld.build_all(180)
rot=lambda m: A(m)[:3,:3]/np.linalg.norm(A(m)[:3,:3],axis=1)[:,None]
# pose the IK chain, then FK takes it
S.get("L_humerus_IK_jnt").attrs["rotate"]=[10,20,30]; S.get("L_radius_IK_jnt").attrs["rotate"]=[0,-40,0]
cmds.select("L_wrist_IK_ctrl"); limb.match_selected("fk")
for c,j in (("L_humerus_FK_ctrl","L_humerus_IK_jnt"),("L_radius_FK_ctrl","L_radius_IK_jnt")):
    print(c,"matches",j,":",np.allclose(rot(world(S.get(c))),rot(world(S.get(j))),atol=1e-5))
# pose the FK chain, then IK takes it
S.get("L_humerus_FK_jnt").attrs["rotate"]=[0,30,10]; S.get("L_radius_FK_jnt").attrs["rotate"]=[0,-60,0]
before_off=me.mul(world(S.get("L_wrist_IK_ctrl")), me.inverse(world(S.get("L_wrist_IK_jnt"))))
cmds.select("L_humerus_FK_ctrl"); limb.match_selected("ik")
want=A(me.mul(before_off, world(S.get("L_wrist_FK_jnt"))))
got=A(world(S.get("L_wrist_IK_ctrl")))
print("IK ctrl placed on FK wrist:", np.allclose(got[3,:3],want[3,:3],atol=1e-4), np.allclose(rot(list(got.flatten())),rot(list(want.flatten())),atol=1e-5))
pv=A(world(S.get("L_radius_PV_ctrl")))[3,:3]; print("PV moved near the FK elbow plane:", pv.round(1))
