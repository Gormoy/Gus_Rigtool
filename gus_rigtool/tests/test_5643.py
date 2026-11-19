# 5.6.43: Attach without 'divide by zero' (the divider's floor 0.001 - Maya counts anything under 0.00001 as zero);
# Repair (and attaching again) fixes 5.6.41-42 attaches; the floating Animtool bar (every tool, the Attach window and
# the Arcs panel, opens with the window); the shelf never loses a button without a word; the Face kit tab with a
# deleted ribbon
import os, sys
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
cmds.undoInfo = mock.MagicMock()
from gus_animtool import anim as A, actions as AC, attach as AT
said = []
A.message = lambda text, level="ok": said.append((text, level))
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- 1. the divider's floor
check("the floor is 0.001 (above Maya's 0.00001 'zero')", AT.SAFE == 0.001 and AT.SAFE > 1e-5)
hand = cmds.ls(createNode("transform", name="L_wrist_IK_ctrl"), long=True)[0]
for a in ("hold_free", "hold_axe"):
    cmds.addAttr(hand, longName=a, attributeType="double", defaultValue=0.0)
bm = createNode("blendMatrix", name="L_wrist_IK_ctrl_attach_blend")
data = {"blend": bm, "norm": [], "holders": [{"attr": "hold_free"}, {"attr": "hold_axe"}]}
AT._wire(hand, data)
clamps = [n for n in data["norm"] if cmds.nodeType(n) == "clamp"]
check("a new attach: every divider's floor at 0.001 (no warning when nothing holds it)",
      len(clamps) == 2 and all(abs(cmds.getAttr(c + ".minR") - 0.001) < 1e-9 for c in clamps))
for c in clamps:                                       # as 5.6.41-42 made them
    cmds.setAttr(c + ".minR", 1e-6)
check("an attach from 5.6.41-42: fixed (2 floors raised)", AT._fix_safe(data) == 2 and
      all(abs(cmds.getAttr(c + ".minR") - 0.001) < 1e-9 for c in clamps))
check("fixed already: nothing to do the second time", AT._fix_safe(data) == 0)
for c in clamps:
    cmds.setAttr(c + ".minR", 1e-6)
with mock.patch.object(AT, "read", lambda f: data), mock.patch.object(AT, "attached", lambda: [hand]), \
        mock.patch.object(AT, "_parent", lambda f: None), mock.patch.object(AT, "is_old", lambda d: False):
    n = AT.repair()
check("Repair: fixes them too (and says so)", n == 2 and cmds.getAttr(clamps[0] + ".minR") == 0.001)
for c in clamps:
    cmds.setAttr(c + ".minR", 1e-6)
with mock.patch.object(AT, "read", lambda f: dict(data, version=2)), mock.patch.object(AT, "is_old", lambda d: False):
    AT._setup(hand)
check("attaching it again fixes it on the way", cmds.getAttr(clamps[0] + ".minR") == 0.001)
src = open(os.path.join(os.getcwd(), "..", "anim", "gus_animtool", "attach.py")).read()
check("no 1e-6 floor left in the attach", "1e-6)" not in src.split("def _wire")[1].split("def _fix_safe")[0])

# --- 2. the bar
check("the Bar button: on the shelf and the toolbar, with its icon",
      AC.info("bar")[1] == "Bar" and "bar" in AC.TOOLBAR_DEFAULT and not AC.icon("bar").endswith("pythonFamily.png"))
for k in ("attach_window", "arcs_panel"):
    check("its icon: %s" % k, os.path.isfile(os.path.join(os.getcwd(), "..", "anim", "gus_animtool", "icons",
                                                          "ga_%s.png" % k)))
said[:] = []
with mock.patch.dict(sys.modules, {"gus_animtool.bar": None}):
    AC.run("bar")
check("no Qt: the Bar button says so (no error box)", said and "bar couldn't open" in said[-1][0])
ui_src = open(os.path.join(os.getcwd(), "..", "anim", "gus_animtool", "ui.py")).read()
check("the bar opens with the Animtool window (unless turned off)", 'A.opt("bar_auto", 1)' in ui_src and
      "bar.show()" in ui_src.split("def show():")[1])
bar_src = open(os.path.join(os.getcwd(), "..", "anim", "gus_animtool", "bar.py")).read()
check("the bar: a tool window (in front of Maya, on the Mac too)", "QtCore.Qt.Tool" in bar_src and
      "WA_MacAlwaysShowToolWindow" in bar_src)

# --- 3. the shelf: a button that fails is made without its menu, and named
from gus_animtool import toolbar as TB
made, real = [], getattr(cmds, "shelfButton", None)
def shelfButton(*a, **k):
    if k.get("label") == "Attach" and "menuItem" in k:
        raise RuntimeError("bad menu")
    made.append(k.get("label"))
cmds.shelfLayout = lambda *a, **k: True if k.get("exists") else []
cmds.separator = lambda *a, **k: None
cmds.shelfButton = shelfButton
said[:] = []
TB.make_shelf()
if real is not None:
    cmds.shelfButton = real
check("shelf: Attach made without its right-click menu, not lost", "Attach" in made and "Bar" in made)
check("...and the Script Editor says which one and why", said and "Attach" in said[-1][0] and "bad menu" in said[-1][0]
      and said[-1][1] == "warn")

# --- 4. the Face kit tab: a ribbon deleted since
sys.path.insert(0, os.path.join(os.getcwd(), "..", ".."))
from gus_rigtool.core import face_kit
check("Face kit: a ribbon that's gone is skipped (no crash)", face_kit.part_of("|Cape_Ribbon_ribbon_grp|Cape_Ribbon") is None)

print("%d/%d passed" % (sum(ok), len(ok)))
