# Wrong twin links (left _driven group linked to the right control): the name wins, Fix twin links relinks,
# the SDK mirror lands on R_..._driven, the Ribbon mirror links control to control
exec(open("fakemaya.py").read())
from gus_rigtool.core import sides, mirror_engine
from gus_rigtool.tools import sdk_tool
def chain(side):
    off = cmds.createNode("transform", name="%s_Eyelids_fol_01_ctrl_offset" % side)
    drv = cmds.createNode("transform", name="%s_Eyelids_fol_01_ctrl_driven" % side, parent=off)
    c = cmds.createNode("transform", name="%s_Eyelids_fol_01_ctrl" % side, parent=drv)
    cmds.createNode("nurbsCurve", name="%s_Eyelids_fol_01_ctrlShape" % side, parent=c)
    return [cmds.ls(x, long=True)[0] for x in (off, drv, c)]
L, R = chain("L"), chain("R")
le = cmds.ls(cmds.createNode("transform", name="L_Eye_ctrl"), long=True)[0]
re_ = cmds.ls(cmds.createNode("transform", name="R_Eye_ctrl"), long=True)[0]
j13 = cmds.ls(cmds.createNode("transform", name="R_Eye_joint13_ctrl"), long=True)[0]
sides.link(L[1], R[2]); sides.link(le, j13)                 # the wrong links from the scene
short = lambda n: n.split("|")[-1] if n else n
print("twin of L driven:", short(mirror_engine.twin_of(L[1])), "| twin of L_Eye_ctrl:", short(mirror_engine.twin_of(le)))
print("bad links:", sorted((short(a), short(b), short(c)) for a, b, c in sides.bad_links()))
# SDK plan: driven keys land on R_..._driven, driver R_Eye_ctrl, with a note
sdk_tool.find_sdks = lambda d, a=None: [{"attr": "Blink", "curve": "crv1", "plug": L[1] + ".translateZ", "blend": None}]
cmds.keyframe = lambda *a, **k: 3
o = dict(sdk_tool.DEFAULTS, mode=1, flip=[], attr_filter="All")
for r in sdk_tool.plan(o, le):
    print("SDK row:", sdk_tool.row_text(r).split("=>")[1].strip())
fixed, left = sides.fix_links()
print("fixed:", sorted((short(a), short(b)) for a, b in fixed), "| left:", left)
print("links now:", short(sides.get_twin(L[1])), short(sides.get_twin(R[1])), short(sides.get_twin(le)), "| bad:", sides.bad_links())
# ribbon: the control under an offset, past a _driven group
from gus_rigtool.core import ribbon
print("ribbon control under offset:", short(ribbon._control_under(L[0])), "| groups between:", [short(g) for g in ribbon._groups_between(L[0], L[2])])
print("R control linked back to L control:", short(sides.get_twin(R[2])), "| R_Eye_joint13_ctrl link:", sides.get_twin(j13))
