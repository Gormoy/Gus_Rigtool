# 4.2.0: Ribbon next to Face and linked, Stick to skin tab, Build '4 Advanced', shared helpers, split modules
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from gus_rigtool import registry
from gus_rigtool.core import ribbon, nodes, ui, utils
ui.report_error = lambda e, w="": __import__("traceback").print_exc()
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
cats = dict((c, k) for c, _l, k in registry.CATEGORIES)
check("Ribbon sits next to Face (Build)", cats["build"][:3] == ["build", "face", "ribbon"] and "ribbon" not in cats["toolbox"])
check("Stick to skin has its own tab after Follow", cats["controls"].index("stick") == cats["controls"].index("follow") + 1)
# builds remember who made them
for name, made in (("Mouth_ribbon", "Face kit: Mouth_ribbon"), ("Spine_ribbon", "")):
    g = cmds.createNode("transform", name=name + "_ctrls_grp")
    for a, v in (("rrbSurface", name), ("rrbSkin", ""), ("rrbSettings", '{"prefix": "%s", "made_by": "%s"}' % (name, made))):
        cmds.addAttr(g, longName=a, dataType="string"); cmds.setAttr(g + "." + a, v, type="string")
    cmds.createNode("transform", name=name)
rows = ribbon.builds_list()
check("builds list, with who made them", [(r[0].split("|")[-1], r[1].get("made_by")) for r in rows] ==
      [("Mouth_ribbon", "Face kit: Mouth_ribbon"), ("Spine_ribbon", "")])
from gus_rigtool.tools import ribbon_tool as rt, face_kit_tool as ft
check("the Face tab part that made it", rt.face_section("Face kit: L_Eyelid_Ribbon") == "Eyelids"
      and rt.face_section("Face kit: Mouth_ribbon") == "Mouth" and rt.face_section("Face kit: L_cheek_Ribbon") == "Facial strips")
check("Face kit settings shared", ribbon.FACE_KIT["pivot_on_shape"] is False and ribbon.FACE_KIT["face_axis"] == "Z")
cmds.evalDeferred = lambda *a, **k: None
rt.load_settings(None, {"prefix": "Mouth_ribbon", "ctrl_every": 3, "not_an_option": 1})
saved = utils.load_setting("ribbon", {})
check("Load its settings: the tab's options become the build's", saved.get("ctrl_every") == 3 and "not_an_option" not in saved)
rt.build("RB_")
check("Ribbon tab lists the builds", any("Face kit: Mouth_ribbon" in x for x in UI["RB_Builds"].get("append", [])))
ft.build("FC_")
check("Face tab lists only its ribbons", [x.split()[0] for x in UI["FC_Ribbons"].get("append", [])] == ["Mouth_ribbon"])
from gus_rigtool.tools import stick_tab as st, follow_tab as fo
st.build("ST_")
check("Stick to skin page builds, Follow no longer has it", "ST_StickRotate" in UI and not hasattr(fo, "stick"))
# shared helpers
a = cmds.createNode("transform", name="a"); b = cmds.createNode("transform", name="b", parent=a)
check("shared helpers", nodes.short("|a|b") == "b" and nodes.short(None) is None and nodes.parent_of(nodes.long_name("b")) == "|a"
      and nodes.unique_long("b") == "|a|b")
from gus_rigtool.core import follow, sticky, spaces
check("modules use the shared ones", follow._parent is nodes.parent_of and sticky._long is nodes.unique_long
      and spaces._short is nodes.short)
# split modules keep their names
from gus_rigtool.tools import mirror_tool, build_tab
check("split modules still answer every old name", callable(ribbon.edge_to_curve) and callable(ribbon.check_curves)
      and callable(mirror_tool.run_full) and callable(mirror_tool.set_joint_world) and callable(build_tab.ex_scan)
      and callable(build_tab._q_rows))
print("ALL OK" if all(ok) else "SOME FAILED")
