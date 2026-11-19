# 5.6.42: the Animtool's arcs back to the plain arc (one orange line over the shot, dots, bigger keys, it stays),
# with the right-click options (range around my frame, handles on the selected key - off by default, timing beads,
# clear); the message; the Attach window stays in front on the Mac
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
from gus_animtool import anim as A, actions as AC, arctrail as T
_opts = {}
A.opt = lambda key, default: _opts.get(key, default)
A.set_opt = lambda key, value: _opts.__setitem__(key, value)
A.frame_range = lambda: (1, 100)
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- the look
ATTRS = ["showFrameMarkers", "frameMarkerSize", "keyframeSize", "trailThickness", "showFrames", "preFrame",
         "postFrame", "fadeInoutFrames", "trailDrawMode", "trailColor", "preFrameColor", "postFrameColor",
         "showInTangent", "showOutTangent"]
def styled(**kw):
    sets_ = {}
    with mock.patch.object(cmds, "listRelatives", lambda n, **k: ["|trailShape"] if k.get("shapes") else []), \
            mock.patch.object(cmds, "listAttr", lambda n, **k: list(ATTRS)), \
            mock.patch.object(cmds, "attributeQuery", lambda a, **k: [0.0]), \
            mock.patch.object(cmds, "setAttr", lambda plug, *v, **k: sets_.__setitem__(plug.split(".")[-1], v)):
        T.style("|trail", **kw)
    return sets_
s = styled()
check("the plain arc: one orange line, dots on the frames, bigger keys, no frame numbers (as before 5.6.40)",
      s["trailColor"] == T.COLOUR and s["showFrameMarkers"] == (True,) and s["keyframeSize"] == (9.0,) and
      s["frameMarkerSize"] == (6.0,) and s["trailThickness"] == (2.0,) and s["showFrames"] == (False,))
check("no past / future colours, no draw mode change (5.6.40's look gone)",
      "preFrameColor" not in s and "postFrameColor" not in s and "trailDrawMode" not in s)
check("the whole shot: Maya's own range (its defaults), no fade", s["preFrame"] == (0.0,) and s["postFrame"] == (0.0,)
      and s["fadeInoutFrames"] == (0.0,))
check("handles off by default", s["showInTangent"] == (False,) and s["showOutTangent"] == (False,))
_opts.update(arcs_around=True, arcs_handles=True)
s = styled()
check("Range around my frame: 24 before / after; Show handles: on (Maya shows them on the selected key)",
      s["preFrame"] == (24,) and s["postFrame"] == (24,) and s["showInTangent"] == (True,))
_opts.clear()

# --- the button
hand = cmds.ls(createNode("transform", name="L_hand_ik_ctrl"), long=True)[0]
fk = cmds.ls(createNode("transform", name="L_wrist_fk_ctrl"), long=True)[0]
for ax in "XYZ":
    cmds.setAttr(fk + ".translate" + ax, lock=True)
made = []
T.make = lambda nodes: made.extend(nodes) or list(nodes)
T.has_translate_keys = lambda n: False
said = T.show([hand, fk, "|gusAnimtool_arcs_grp|L_hand_ik_ctrl_arcHandle"])
check("Arcs: an arc on each selected control (not on an arc itself)", made == [hand, fk])
check("the message: no translate keys yet -> set a key; the FK one only rotates -> don't drag it",
      "no translate keys yet" in said and "L_wrist_fk_ctrl only rotates" in said)
try:
    T.show([]); msg = ""
except RuntimeError as e:
    msg = str(e)
check("nothing selected: 'select the controls first'", "select the controls" in msg)

# --- right-click
check("right-click on Arcs: clear, the whole shot, around my frame, handles, timing beads",
      [c for _l, c in AC.MENUS["arcs"]] == ["arcs_clear", "arcs_shot", "arcs_around", "arcs_handles", "arcs_weighted"])
restyled = []
T.restyle = lambda: restyled.append(1)
check("around my frame: kept, the arcs restyled", "24 frames around" in AC._call("arcs_around") and
      _opts["arcs_around"] is True and restyled)
check("the whole shot again", "whole shot" in AC._call("arcs_shot") and _opts["arcs_around"] is False)
check("handles: on, then off", "on" in AC._call("arcs_handles") and _opts["arcs_handles"] is True and
      "off" in AC._call("arcs_handles"))
check("no follow selection / pin any more", not hasattr(T, "follow") and not hasattr(T, "pin"))

# --- the Attach window on the Mac
src = open(os.path.join(os.getcwd(), "..", "anim", "gus_animtool", "attachwin.py")).read()
check("the Attach window: a tool window on the Mac (stays in front of Maya), shown even when Maya isn't active",
      'QtCore.Qt.Tool if sys.platform == "darwin"' in src and "WA_MacAlwaysShowToolWindow" in src)

print("%d/%d passed" % (sum(ok), len(ok)))
