exec(open("fakemaya.py").read())
import numpy as np
cmds.deleteAttr=lambda node, attribute=None: _n(node).user.pop(attribute, None)
from gus_rigtool.core import follow
def ctrl(name, pos):
    off=S.create("transform", name+"_offset"); off.attrs["translate"]=list(pos)
    c=S.create("transform", name, off); S.create("nurbsCurve", name+"Shape", c); return c.name
jaw=ctrl("Jaw_ctrl",[0,150,2])
jj=S.create("joint","jaw_jnt"); jj.attrs["translate"]=[0,149,1]
up=ctrl("upLip_ctrl",[0,149,9]); low=ctrl("lowLip_ctrl",[0,147,9])
done, sk = follow.add(jaw, [up, low], ("rotate",), "driver", 0.6, remap="weight", source="jaw_jnt")
print(done, sk)
print("shared attr:", getAttr("Jaw_ctrl.follow"), "| no per-ctrl attrs:",
      not cmds.attributeQuery("upLip_ctrl_follow", node="Jaw_ctrl", exists=True))
for n in ("upLip_ctrl_follow_remap.inputValue","lowLip_ctrl_follow_rotate.input1","lowLip_ctrl_follow_rotate.input2X"):
    print(n, "<-", cmds.listConnections(n, source=True, destination=False, plugs=True))
sp=world(S.get("lowLip_ctrl_followSpace")); print("space at jaw joint:", np.allclose(np.array(sp).reshape(4,4)[3,:3],[0,149,1]))
print("list:", follow.all_follows())
jj.attrs["rotate"]=[5,0,0]
try: follow.add(jaw, [ctrl("x_ctrl",[1,1,1])], source="jaw_jnt")
except RuntimeError as e: print("rest check:", e)
jj.attrs["rotate"]=[0,0,0]
print("removed:", follow.remove([up]), "attr kept (low still uses it):", cmds.attributeQuery("follow", node="Jaw_ctrl", exists=True))
print("removed:", follow.remove([low]), "| left:", follow.all_follows(), "| attr gone:", not cmds.attributeQuery("follow", node="Jaw_ctrl", exists=True))
