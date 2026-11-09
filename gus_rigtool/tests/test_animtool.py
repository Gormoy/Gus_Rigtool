# Gus Animtool 2.0: tween slider (between keys / from rest / mirror, live drag then one apply), key tools
# (nudge, insert / remove frames, clean up, offset chain, copy / paste pose), space switch key cleanup,
# rig profiles, hotkeys, its updater
import os, sys, tempfile, zipfile
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
KEYS = {}                                                # "node.attr" -> {time: value}
NOW = [10.0]
def _plug(node, attr):
    return cmds.ls(node, long=True)[0].split("|")[-1] + "." + attr
_get = cmds.getAttr
def getAttr(plug, **k):
    if "time" in k:
        n, a = plug.split(".", 1)
        ks = KEYS.get(_plug(n, a))
        return ks[k["time"]] if ks and k["time"] in ks else _get(plug)
    return _get(plug, **k)
cmds.getAttr = getAttr
def keyframe(*a, **k):
    nodes = a[0] if a else []
    nodes = nodes if isinstance(nodes, list) else [nodes]
    plugs = []
    for n in nodes:
        if "." in n:
            plugs.append(_plug(*n.split(".", 1)))
        elif n.rsplit("_", 1)[0] + "." + n.rsplit("_", 1)[-1] in KEYS:          # a curve name: node_attr
            plugs.append(n.rsplit("_", 1)[0] + "." + n.rsplit("_", 1)[-1])
        else:
            s = cmds.ls(n, long=True)[0].split("|")[-1]
            plugs += [p for p in KEYS if p.startswith(s + ".")]
    if k.get("query"):
        if k.get("selected"):
            return []
        if k.get("name"):
            return [p.replace(".", "_") for p in plugs if KEYS.get(p)]
        if k.get("keyframeCount"):
            t = k.get("time")
            return sum(1 for p in plugs for x in KEYS.get(p, {}) if not t or t[0] <= x <= t[1])
        if k.get("timeChange"):
            return sorted(set(x for p in plugs for x in KEYS.get(p, {})))
        return []
    if k.get("edit"):
        t = k.get("time") or (-1e9, 1e9)
        for p in plugs:
            ks = KEYS.get(p, {})
            KEYS[p] = {(x + k["timeChange"] if t[0] <= x <= t[1] else x): v for x, v in ks.items()}
cmds.keyframe = keyframe
def setKeyframe(*a, **k):
    nodes = a[0] if isinstance(a[0], list) else [a[0]]
    for n in nodes:
        attrs = [k["attribute"]] if isinstance(k.get("attribute"), str) else (k.get("attribute") or [])
        if "." in n:
            n, at = n.split(".", 1); attrs = [at]
        for at in attrs:
            KEYS.setdefault(_plug(n, at), {})[NOW[0]] = _get(n + "." + at)
cmds.setKeyframe = setKeyframe
cmds.currentTime = lambda *a, **k: NOW[0] if k.get("query") else NOW.__setitem__(0, float(a[0]))
cmds.cutKey = lambda c, time=None, clear=False: [KEYS.get(c.replace("_", ".", 1) if c.count("_") else c, {}).pop(x, None)
                                                 for x in list(KEYS.get(c.rsplit("_", 1)[0] + "." + c.rsplit("_", 1)[1], {})) if time[0] <= x <= time[1]]
cmds.autoKeyframe = mock.MagicMock(return_value=False); cmds.keyTangent = mock.MagicMock()
cmds.optionVar = mock.MagicMock(return_value=False)
import gus_animtool
from gus_animtool import anim as A, tween as T, keys as K
_opts = {"tween_key": 1, "library": tempfile.mkdtemp()}
A.opt = lambda key, default: _opts.get(key, default)
c = cmds.createNode("transform", name="L_arm_ctrl"); cmds.createNode("nurbsCurve", name="L_arm_ctrlShape", parent=c)
r = cmds.createNode("transform", name="R_arm_ctrl"); cmds.createNode("nurbsCurve", name="R_arm_ctrlShape", parent=r)
cmds.listAttr = (lambda real: (lambda n, **k: ["translateX", "translateY", "rotateZ"] if k.get("keyable") and not k.get("userDefined") else real(n, **k)))(cmds.listAttr)
KEYS["L_arm_ctrl.translateX"] = {0.0: 0.0, 20.0: 10.0}
cmds.select(c)
print("between at 0 (half way):", T.targets([c], 0, 0.5)["L_arm_ctrl.translateX"], "| at 1:", T.targets([c], 0, 1.0)["L_arm_ctrl.translateX"])
cmds.setAttr(c + ".ty", 4.0)
print("from rest +50%:", T.targets([c], 1, 0.5)["L_arm_ctrl.translateY"], "| -100% (rest):", T.targets([c], 1, -1.0)["L_arm_ctrl.translateY"])
T.drag([c], 0, 0.25); T.drag([c], 0, 0.75)
print("live drag shows:", cmds.getAttr(c + ".tx"), "| keys while dragging:", sorted(KEYS["L_arm_ctrl.translateX"]))
n = T.release(0, 0.75)
print("release applies once:", cmds.getAttr(c + ".tx"), "| keyed at 10:", KEYS["L_arm_ctrl.translateX"].get(10.0), "| attrs:", n)
print("step to next:", T.step(1), round(cmds.getAttr(c + ".tx"), 3))
cmds.setAttr(r + ".tx", 3.0); cmds.setAttr(c + ".tx", 0.0)
print("mirror 100%:", T.targets([c], 2, 1.0).get("L_arm_ctrl.translateX"))
# keys
KEYS["L_arm_ctrl.translateX"] = {0.0: 0.0, 10.0: 5.0, 20.0: 10.0}
K.nudge(2); print("nudge +2:", sorted(KEYS["L_arm_ctrl.translateX"]), "| frame:", NOW[0])
NOW[0] = 5.0; K.inbetween(3, "selection"); print("insert 3 after 5:", sorted(KEYS["L_arm_ctrl.translateX"]))
d = cmds.createNode("transform", name="tail_02_ctrl")
KEYS["tail_02_ctrl.rotateZ"] = {0.0: 1.0, 10.0: 2.0}
cmds.select([c, d]); K.offset(2, "cascade"); print("offset chain:", sorted(KEYS["tail_02_ctrl.rotateZ"]))
cmds.select(c); print("copy:", K.copy_pose()); cmds.setAttr(c + ".ty", 0.0); cmds.select(c); print("paste:", K.paste_pose(), cmds.getAttr(c + ".ty"))
# profiles
print("rig name:", A.rig_name("hare01:"), A.rig_name(""))
print("no profile -> options suffix:", A.suffix())
A.save_profile({"suffix": "_CTRL", "left": "Lf_", "right": "Rt_"}, "")
print("profile:", A.profile(""), "| suffix now:", A.suffix(), "| pairs:", A.pairs()[0])
s = cmds.sets([c], name="anim_set"); A.save_profile({"control_set": "anim_set"}, ""); A._members_cache.clear()
print("controls from the set:", [A.short(x) for x in A.character_controls("")])
# hotkeys
cmds.hotkeySet = mock.MagicMock(side_effect=lambda *a, **k: "Maya_Default" if k.get("current") and k.get("query") else (False if k.get("exists") else None))
cmds.runTimeCommand = mock.MagicMock(return_value=False); cmds.nameCommand = mock.MagicMock(); cmds.hotkey = mock.MagicMock()
from gus_animtool import hotkeys
print("hotkeys on:", hotkeys.install(), "| keys bound:", cmds.hotkey.call_count)
# updater: a zip with a newer package
tmp = tempfile.mkdtemp(); z = os.path.join(tmp, "Gus_Animtool_install.zip")
with zipfile.ZipFile(z, "w") as zf:
    zf.writestr("gus_animtool/__init__.py", '__version__ = "9.9.9"\n')
    zf.writestr("gus_animtool/anim.py", "# new\n")
    zf.writestr("gus_anim.py", "# shim\n")
from gus_animtool import updater
print("zip version:", updater.zip_version(z))
inst = os.path.join(tmp, "scripts", "gus_animtool"); os.makedirs(inst)
open(os.path.join(inst, "__init__.py"), "w").write('__version__ = "2.0.0"\n'); open(os.path.join(inst, "defaults.json"), "w").write("{}")
gus_animtool.ROOT = inst
old, new, backup = updater.install(z)
print("installed:", new, "| defaults kept:", os.path.isfile(os.path.join(inst, "defaults.json")), "| shim:",
      os.path.isfile(os.path.join(tmp, "scripts", "gus_anim.py")), "| backup:", os.path.basename(backup))
# space switch key cleanup (the fake doesn't solve constraints: no jump is seen; the fix keys in place)
cmds.addAttr(c, longName="space", attributeType="enum", enumName="world:chest", keyable=True)
KEYS["L_arm_ctrl.space"] = {0.0: 0, 10.0: 1}
cmds.listAttr = (lambda real: (lambda n, **k: ["space"] if k.get("userDefined") and k.get("keyable") else real(n, **k)))(cmds.listAttr)
print("jumps found (fake: none):", K.space_jumps([c]))
NOW[0] = 3.0
print("fix keyed:", K.fix_space_jumps([(cmds.ls(c, long=True)[0], "space", 10.0, 0, 1)]), "| keys at 9 / 10:",
      9.0 in KEYS.get("L_arm_ctrl.translateX", {}), 10.0 in KEYS.get("L_arm_ctrl.translateX", {}), "| back at frame", NOW[0])
