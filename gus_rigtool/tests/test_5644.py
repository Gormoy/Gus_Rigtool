# 5.6.44: the floating bar replaces the toolbar under the Time Slider (turned off once; Settings brings it back);
# the bar's buttons can be chosen; Settings: the bar opens with the window, Open the bar, Bar buttons; real-Maya
# cases h (undo off without a window) and i (a keyed hand: its held space follows the stick) corrected
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ANIM = os.path.join(os.getcwd(), "..", "anim", "gus_animtool")
ui = open(os.path.join(ANIM, "ui.py")).read()
show = ui.split("def show():")[1]

# --- the toolbar off once (the bar replaces it), then your choice again
opts = {"toolbar": 1}
first = show.split('if not A.opt("bar_replaces_toolbar", 0):')[1].split("if A.opt(\"toolbar\", 0):")[0]
hidden = []
env = {"A": type("A", (), {"opt": staticmethod(lambda k, d: opts.get(k, d)),
                           "set_opt": staticmethod(lambda k, v: opts.__setitem__(k, v))})}
toolbar = type("tb", (), {"hide": staticmethod(lambda: hidden.append(1))})
with mock.patch.dict(sys.modules, {"gus_animtool.toolbar": toolbar}):
    import gus_animtool
    gus_animtool.toolbar = toolbar
    code = "if not A.opt('bar_replaces_toolbar', 0):" + first
    exec(code, env)
    check("the update: the toolbar turned off and hidden once", opts["toolbar"] == 0 and hidden and
          opts["bar_replaces_toolbar"] == 1)
    opts["toolbar"] = 1                                     # you turn it on again in Settings
    exec(code, env)
check("...only once: turned on again in Settings, it stays on", opts["toolbar"] == 1 and len(hidden) == 1)
check("the window still shows the toolbar when you want it", 'if A.opt("toolbar", 0):' in show)
check("Settings: the bar opens with the window / Open the bar / Bar buttons...", '"The bar opens with this window"'
      in ui and '"Open the bar"' in ui and '"Bar buttons..."' in ui and '"Toolbar under the Time Slider"' in ui)

# --- the bar's choice (Qt not needed for the list)
bar = open(os.path.join(ANIM, "bar.py")).read()
check("the bar: Choose buttons... in its menu, a tick per tool", '"Choose buttons..."' in bar and "class Chooser" in bar)
check("all ticked = every tool (new tools show up too)", 'A.set_opt("bar_keys", "" if not chosen or len(chosen) == '
      'len(every)' in bar)

# --- real-Maya cases corrected
cases = open(os.path.join(os.getcwd(), "..", "realmaya", "maya_cases.py")).read()
check("case i: the keyed hand's held space follows the stick (its own keys on top)", "_held_rel(lhand, prop)" in cases)
check("case i: Time Slider stretches only checked with a window", 'cmds.about(batch=True)' in cases)
check("case h: Ctrl+Z only checked when undo is on", 'undoInfo(query=True, state=True)' in cases)
# --- Add / Remove inbetween: Maya's "Cannot move keys" on one curve no longer stops the others
from gus_animtool import keys as K
said = []
A.message = lambda t, level="ok": said.append((t, level))
cmds.undoInfo = mock.MagicMock()
edits, cuts = [], []
def keyframe(c=None, **k):
    if k.get("query"):
        return 1
    if c == "Locked_rotateY":
        raise RuntimeError("Cannot move keys")
    edits.append((c, k.get("timeChange"), k.get("option")))
with mock.patch.object(K, "scope_curves", lambda scope=None: ["Arm_translateX", "Locked_rotateY", "Leg_translateY"]), \
        mock.patch.object(cmds, "keyframe", keyframe), mock.patch.object(cmds, "currentTime", lambda **k: 10.0), \
        mock.patch.object(cmds, "cutKey", lambda c, **k: cuts.append(c), create=True):
    n = K.inbetween(-1)
    check("Remove inbetween: the other curves still move (one refused)", n == 2 and
          [e[0] for e in edits] == ["Arm_translateX", "Leg_translateY"] and all(e[1] == -1 for e in edits))
    check("...moved the safe way (like Offset)", all(e[2] == "over" for e in edits))
    check("...and it says which curve didn't move and why", said and "Locked_rotateY" in said[-1][0] and
          "Cannot move keys" in said[-1][0] and said[-1][1] == "warn")
with mock.patch.object(K, "scope_curves", lambda scope=None: ["Locked_rotateY"]), \
        mock.patch.object(cmds, "keyframe", keyframe), mock.patch.object(cmds, "currentTime", lambda **k: 10.0):
    try:
        K.inbetween(1); msg = ""
    except RuntimeError as e:
        msg = str(e)
check("every curve refused: says so plainly (nothing moved)", "no keys moved" in msg and "Locked_rotateY" in msg)

print("%d/%d passed" % (sum(ok), len(ok)))
