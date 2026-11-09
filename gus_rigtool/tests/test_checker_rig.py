# New rig checks on a built biped / quadruped: controls driven by constraints, guides shown, locked channels shown
exec(open("fakemaya.py").read())
cmds.listConnections = (lambda orig: (lambda *a, **k: orig(*a, **{x: y for x, y in k.items() if x != "skipConversionNodes"})))(cmds.listConnections)
from gus_rigtool.builder import build as bld
from gus_rigtool.tools import checker
for kind in ("biped", "quadruped"):
    S.__init__()
    getattr(bld, kind)(100); bld.build_all(100)
    print(kind, "constrained controls:", [n.split("|")[-1] for n in checker.find_ctrl_constrained([])])
    print(kind, "locked shown:", len(checker.find_ctrl_locked_shown([])))
    g = checker.find_guides_shown([])
    print(kind, "guides shown:", [x.split("|")[-1] for x in g], "after fix:", checker.fix_guides_shown(g), checker.find_guides_shown([]))
from gus_rigtool.builder import guides
guides.set_visible(True)
g = checker.find_guides_shown([])
print("shown by hand:", [x.split("|")[-1] for x in g], "after fix:", checker.fix_guides_shown(g), checker.find_guides_shown([]))
print("all checks:", len(checker.CHECKS), "help for each:", all(c[0] in checker.HELP for c in checker.CHECKS))
