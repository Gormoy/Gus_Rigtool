# 5.7.10: lighter - Publish in its own file (opening it doesn't load Build), the Checker's checks in their own file
# (Publish, Check this scene, Repair... load only the checks, not the page), Face's step lights read the selection
# once per change; four new checks (Gus: "all of them")
import sys
exec(open("fakemaya.py").read())

def check(label, cond):
    ok.append(bool(cond))
    print("%s %s" % ("PASS" if cond else "FAIL", label))
ok = []

# --- 1. Publish on its own
for m in [m for m in list(sys.modules) if m.startswith("gus_rigtool.tools.")]:
    del sys.modules[m]
from gus_rigtool import registry
mod = registry.module("publish")
check("Publish: its own file (tools/publish_tab.py)", mod.__name__ == "gus_rigtool.tools.publish_tab")
check("...opening it doesn't load Build", "gus_rigtool.tools.build_tab" not in sys.modules)
from gus_rigtool.tools import build_tab
check("...Build's page still has Publish (legacy look) and its names still answer", callable(build_tab.publish_rig)
      and callable(build_tab.NP) and callable(build_tab.build_publish_panel))

# --- 2. the checks on their own
for m in [m for m in list(sys.modules) if m.startswith("gus_rigtool.tools.checker")]:
    del sys.modules[m]
from gus_rigtool.core import rig_checks as RC, repair, space_check
from gus_rigtool import scene_check
from gus_rigtool.builder import publish
check("Publish, Check this scene, Repair, Spaces load the checks, not the Checker page",
      "gus_rigtool.tools.checker" not in sys.modules)
from gus_rigtool.tools import checker
check("...the page has every check under the same names", all(getattr(checker, c[4].__name__) is c[4]
                                                              for c in RC.CHECKS))
ORIG = ["ctrl_zero", "ctrl_keys", "ctrl_no_offset", "ctrl_neg_scale", "ctrl_color", "ctrl_hidden", "ctrl_constrained",
        "ctrl_no_switch", "ctrl_locked_shown", "twins_missing", "live_follow", "jnt_rotate", "jnt_scale", "jnt_flip",
        "jnt_twist", "jnt_off_guides", "jnt_not_mirrored", "mesh_history", "mesh_unfrozen", "skin_influences",
        "skin_unused", "skin_off_skeleton", "skin_legacy", "geo_no_skin", "orig_shapes", "default_material",
        "orig_shapes_ref", "dup_names", "dup_names_ref", "util_names", "empty_groups", "unknown", "guides_shown",
        "empty_layers", "namespaces", "naming_side", "naming_suffix"]
ids = [c[0] for c in RC.CHECKS]
check("the 37 checks kept as they are (Gus: 'keep them as they are')", all(i in ids for i in ORIG))
NEW = ["ctrl_rotate_order_twin", "jnt_keys", "jnt_ssc_scaled", "skin_normalize"]
check("...and the 4 new ones (Gus: 'all of them'), on by default, warnings or notes - never FAIL",
      all(i in ids for i in NEW) and all(c[6] and c[3] in ("WARN", "INFO") for c in RC.CHECKS if c[0] in NEW))
check("...each with its help text, and in Settings (a tick each)", all(i in RC.HELP for i in NEW) and
      all("on_" + i in RC.DEFAULTS for i in NEW))

# --- 3. the new checks find what they should
j1 = cmds.ls(createNode("joint", name="Arm_jnt"), long=True)[0]
j2 = cmds.ls(createNode("joint", name="Hand_jnt", parent=j1), long=True)[0]
crv = createNode("animCurveTA", name="Arm_jnt_rotateZ")
connectAttr(crv + ".output", j1 + ".rotateZ")
check("Keys on joints: the keyed joint", any(n.endswith("Arm_jnt") for n in RC.find_jnt_keys(None)) and
      not any(n.endswith("Hand_jnt") for n in RC.find_jnt_keys(None)))
md = createNode("multiplyDivide", name="arm_scale_md")
connectAttr(md + ".outputX", j1 + ".scaleX")
cmds.setAttr(j2 + ".segmentScaleCompensate", 1)
check("Segment scale compensate under a scaled joint: the hand (its arm is scaled by the rig)",
      [n.split("|")[-1] for n in RC.find_jnt_ssc_scaled(None)] == ["Hand_jnt"])
from unittest import mock
from gus_rigtool.core import mirror_engine, skin_mirror
l, r = createNode("transform", name="L_foot_ctrl"), createNode("transform", name="R_foot_ctrl")
cmds.setAttr(l + ".rotateOrder", 2)
with mock.patch.object(RC, "is_control", lambda n: n.split("|")[-1] in ("L_foot_ctrl", "R_foot_ctrl")), \
        mock.patch.object(mirror_engine, "twin_of", lambda n, pairs=None: "R_foot_ctrl" if "L_foot" in n else None):
    got = RC.find_ctrl_rotate_order_twin(None)
check("Left / right controls with different rotate orders: L_foot_ctrl (yzx vs xyz)", [n.split("|")[-1] for n in got]
      == ["L_foot_ctrl"])
mesh = createNode("transform", name="Body")
skin = createNode("skinCluster", name="Body_skin")
cmds.setAttr(skin + ".normalizeWeights", 0)
with mock.patch.object(RC, "_skinned_meshes", lambda scope: [(mesh, skin)]), \
        mock.patch.object(skin_mirror, "skin_of", lambda n: skin):
    found = RC.find_skin_normalize(None)
    RC.fix_skin_normalize(found)
    after = RC.find_skin_normalize(None)
check("Skins that don't keep weights adding up to 1: found; Fix sets Interactive (nothing moves)",
      found == [mesh] and not after and cmds.getAttr(skin + ".normalizeWeights") == 1)

# --- 4. Face's step lights: one reading per selection change
from gus_rigtool.tools import face_kit_tool as FK
calls = []
real_ls = cmds.ls
def counting_ls(*a, **k):
    if k.get("flatten"):
        calls.append(1)
    return real_ls(*a, **k)
with mock.patch.object(cmds, "ls", counting_ls):
    FK._SNAP["key"] = None
    for part in ("eyelids", "mouth", "brows", "strip"):
        FK._part_light(part)
check("Face: the 4 step lights read the selection once (5.7.9.1: once each)", len(calls) == 1)
print("%d/%d passed" % (sum(ok), len(ok)))
