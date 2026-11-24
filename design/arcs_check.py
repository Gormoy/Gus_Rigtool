# Arcs check (5.7.10.1, Gus: "when I click arcs nothing shows on the viewport").
# Select the control (one that moves), paste in the Script Editor (Python), run, copy what it prints.
import maya.cmds as cmds
from gus_animtool import arctrail as T, anim as A

out = []
def say(*a):
    out.append(" ".join(str(x) for x in a)); print("ARCS:", out[-1])

sel = cmds.ls(selection=True, long=True) or []
nodes = T.controls(sel)
say("selected:", [T._short(n) for n in sel], "-> controls:", [T._short(n) for n in nodes])
try:
    say("frame range used:", A.frame_range())
except Exception as e:
    say("frame range: ERROR", e)
grp = cmds.ls(T.GROUP, long=True)
say("arcs group:", grp, "visible:", [cmds.getAttr(g + ".visibility") for g in grp])
for n in nodes:
    old = T._trails_of(n)
    say(T._short(n), "| moves:", T.moves(n), "| translate keys:", T.has_translate_keys(n), "| arcs already there:",
        [(t.split("|")[-1], cmds.getAttr(t + ".visibility")) for t in old])
say("hidden by the Arcs panel:", [T._short(n) for n in T.state()["hidden"]])
for p in cmds.getPanel(visiblePanels=True) or []:
    if cmds.getPanel(typeOf=p) == "modelPanel":
        say("viewport", p, "| shows motion trails:", cmds.modelEditor(p, query=True, motionTrails=True),
            "| isolate select on:", cmds.isolateSelect(p, query=True, state=True))
# a fresh arc: the old ones away, then the button's own command
T.clear()
try:
    say("Arcs button again (fresh):", T.show(sel))
except Exception as e:
    say("Arcs button again: ERROR", e)
for n in nodes:
    for t in T._trails_of(n):
        shapes = cmds.listRelatives(t, shapes=True, fullPath=True) or []
        say("made", t.split("|")[-1], "| visible:", cmds.getAttr(t + ".visibility"), "| shapes:",
            [cmds.nodeType(s) for s in shapes])
cmds.select(sel, replace=True) if sel else None
print("\n".join(["--- copy from here ---"] + out))
