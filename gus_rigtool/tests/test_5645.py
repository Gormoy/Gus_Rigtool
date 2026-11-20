# 5.6.45: one control maker (every tool makes its controls the same way), every new control tagged as a Maya
# controller and linked to the control above it (pick-walk), Checker > Tag all controls (only when pressed),
# drag_to_maya.mel updates your own Gus Animtool folder too, the Animtool says when it's older than Gus_Rigtool
import os, sys, shutil, tempfile
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# --- a small fake of Maya's controller tag: a 'controller' node, its parent link
TAGS = {}                                    # control long name -> parent control (or None)
def controller(*a, **k):
    if k.get("parent") and len(a) == 2:
        TAGS[cmds.ls(a[0], long=True)[0]] = cmds.ls(a[1], long=True)[0]
        return None
    n = cmds.ls(a[0], long=True)[0]
    t = cmds.createNode("controller", name=n.split("|")[-1] + "_tag")
    cmds.connectAttr(n + ".message", t + ".controllerObject")
    TAGS.setdefault(n, None)
cmds.controller = controller
from gus_rigtool.core import control_maker as CM, shape_data, curves
ROOT = os.path.join(os.getcwd(), "..")

# --- 1. the maker
par = cmds.ls(createNode("transform", name="arm_grp"), long=True)[0]
m = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 3, 4, 5, 1]
top, ctrl = CM.new("L_arm_ctrl", shape_data.circle_curve(1.0), curves.rgb_style((0, 0, 1)),
                   groups=["L_arm_ctrl_zero", "L_arm_ctrl_offset"], matrix=m, parent=par)
check("a control in its groups (top first), under its parent",
      top == "|arm_grp|L_arm_ctrl_zero" and ctrl == "|arm_grp|L_arm_ctrl_zero|L_arm_ctrl_offset|L_arm_ctrl")
check("at its place (world)", [round(v, 6) for v in cmds.xform(ctrl, query=True, worldSpace=True, translation=True)]
      == [3, 4, 5])
same = curves.create_curve_control("old_way_ctrl", shape_data.circle_curve(1.0), curves.rgb_style((0, 0, 1)))
check("the same curve and colour as the old way", curves.curve_shapes(ctrl) and
      curves.read_shape(ctrl) == curves.read_shape(same) and curves.read_style(ctrl) == curves.read_style(same))
check("tagged as a Maya controller", CM.is_tagged(ctrl))
_t, hand = CM.new("L_hand_ctrl", shape_data.circle_curve(1.0), groups=["L_hand_ctrl_offset"], parent=ctrl)
check("a control under another: linked to it (pick-walk)", CM.link(hand) == ctrl and TAGS[hand] == ctrl)
_t, loose = CM.new("C_free_ctrl", shape_data.circle_curve(1.0), tag=False)
check("tag=False: left as it is", not CM.is_tagged(loose) and _t == loose)

# --- 2. every tool goes through it (the source)
CALLERS = {"Make controls": "core/make_controls.py", "Shapes (Create)": "tools/shape_library.py",
           "the Builder": "builder/controls.py", "Ribbon": "core/ribbon.py", "IK spline": "core/ik_spline.py",
           "World levels": "core/world_levels.py", "Face sliders": "core/face_sliders.py"}
for label, path in CALLERS.items():
    src = open(os.path.join(ROOT, path)).read()
    check("%s makes its controls with the one maker" % label, "control_maker." in src)
check("nothing makes a control another way any more (create_curve_control only in the maker / guides)",
      all("create_curve_control" not in open(os.path.join(ROOT, p)).read() for p in CALLERS.values()))
build_src = open(os.path.join(ROOT, "builder", "build.py")).read()
check("after a build: every control linked up the hierarchy", "control_maker.link_all(" in build_src)

# --- 3. the Builder's control: tagged
from gus_rigtool.builder import controls as BC
off, c = BC.make("L", "knee", "circle", 1.0, m, par, "X", mirror=None)
check("Builder: its control tagged, in its offset under the parent", CM.is_tagged(c) and off.startswith("|arm_grp|")
      and c.startswith(off + "|"))

# --- 4. Tag all controls: only when you press it; 'not a control' left out
old_a = cmds.ls(createNode("transform", name="Old_arm_ctrl"), long=True)[0]
curves.set_shape(old_a, shape_data.circle_curve(1.0))
old_b = cmds.ls(createNode("transform", name="Old_hand_ctrl", parent=old_a), long=True)[0]
curves.set_shape(old_b, shape_data.circle_curve(1.0))
gone = cmds.ls(createNode("transform", name="Old_head_ctrl"), long=True)[0]
curves.set_shape(gone, shape_data.circle_curve(1.0))
from gus_rigtool.core import control_role
control_role.set_role([gone], control=False)
check("an old rig: nothing tagged by itself", not CM.is_tagged(old_a) and not CM.is_tagged(old_b))
tagged, linked = CM.tag_all([old_a, old_b, gone])
check("Tag all controls: both tagged, the hand linked to the arm", tagged == 2 and CM.is_tagged(old_b) and
      TAGS.get(old_b) == old_a and linked >= 1)
check("...the 'not a control' curve left out", not CM.is_tagged(gone))
check("...pressing it again changes nothing", CM.tag_all([old_a, old_b])[0] == 0)
chk = open(os.path.join(ROOT, "tools", "checker.py")).read()
check("Checker: the 'Tag all controls as Maya controllers' button", "Tag all controls as Maya controllers" in chk)
pub = open(os.path.join(ROOT, "builder", "publish.py")).read()
check("Publish doesn't tag (you chose: only the button)", "control_maker" not in pub)

# --- 5. drag_to_maya.mel updates your own Animtool folder
inst = open(os.path.join(ROOT, "install.py")).read()
check("the installer updates Gus Animtool too", "updater.update_animtool(dest)" in inst)
from gus_rigtool.core import updater
tmp = tempfile.mkdtemp()
try:
    rig = os.path.join(tmp, "rig", "gus_rigtool")
    os.makedirs(os.path.join(rig, "anim", "gus_animtool"))
    open(os.path.join(rig, "anim", "gus_animtool", "__init__.py"), "w").write('__version__ = "5.6.45"\n')
    open(os.path.join(rig, "anim", "gus_animtool", "bar.py"), "w").write("# new\n")
    mine = os.path.join(tmp, "scripts", "gus_animtool")
    os.makedirs(mine)
    open(os.path.join(mine, "__init__.py"), "w").write('__version__ = "5.6.42"\n')
    open(os.path.join(mine, "defaults.json"), "w").write('{"naming": "mine"}')
    spec = mock.Mock(origin=os.path.join(mine, "__init__.py"))
    with mock.patch("importlib.util.find_spec", lambda name: spec):
        got = updater.update_animtool(rig)
    check("your Animtool folder gets the new files (5.6.42 -> 5.6.45)", got == mine and
          "5.6.45" in open(os.path.join(mine, "__init__.py")).read() and os.path.isfile(os.path.join(mine, "bar.py")))
    check("...your defaults kept", open(os.path.join(mine, "defaults.json")).read() == '{"naming": "mine"}')
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# --- 6. the Animtool says when it's older
sys.path.insert(0, os.path.join(ROOT, "anim"))
import gus_animtool, gus_rigtool
from gus_animtool import ui as AUI, anim as A
said = []
A.message = lambda t, level="ok": said.append((t, level))
asked = []
cmds.confirmDialog = lambda **k: asked.append(k["message"]) or "Not now"
with mock.patch.object(gus_animtool, "__version__", "5.6.42"), mock.patch.object(gus_rigtool, "__version__", "5.6.45"):
    r = AUI._version_check()
check("an older Animtool: it says so and offers the update", r is False and asked and "5.6.42" in asked[0] and
      "5.6.45" in asked[0] and said and said[-1][1] == "warn")
asked[:] = []
check("the same version: nothing asked", AUI._version_check() is None and not asked)
print("%d/%d passed" % (sum(ok), len(ok)))
