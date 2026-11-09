# Chain wave: a wave group above every FK control, one expression driven by wave / wave_up / speed / length
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
made = []
cmds.expression = lambda **k: made.append(k) or k.get("name")
from gus_rigtool.builder import build as bld, guides, modules
mod = modules.MODULES["chain"]
s = mod.complete(mod.default_settings("C")); s["names"]["name"], s["names"]["count"] = "tail", 4
s["options"]["wave"] = True; s["options"]["curl"] = True
bld.add_module("chain", "C", "tail", 100.0, s)
bld.build_all(100.0)
st = cmds.ls("tail_settings_ctrl")[0]
print("attrs:", [a for a in cmds.listAttr(st, userDefined=True) if not a.startswith("gus")])
c = cmds.ls("tail_02_FK_ctrl", long=True)[0]
print("fk control path:", " > ".join(x for x in c.split("|")[-3:]))
print("expression:", made[0]["name"], "|", made[0]["string"].splitlines()[:2])
