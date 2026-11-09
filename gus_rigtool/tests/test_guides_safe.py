# 4.0.1: guides zeroed after a build (the Checker's 'Controls not at zero' fix took them for controls) - the
# Checker / Reset leave guides alone, Back to guides puts zeroed guides back, 'Guides from the rig' recovers them
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, guides
from gus_rigtool.tools import checker
from gus_rigtool.core import quick

def P(n):
    return [round(v, 2) for v in cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, translation=True)]

def every_guide():
    return [g for grp in guides.module_groups() for g in guides.read(grp)["guides"].values()]

def zero_all():
    for g in every_guide():
        for a in "xyz":
            try:
                cmds.setAttr(g + ".t" + a, 0.0)
            except RuntimeError:
                pass

for kind in ("biped", "quadruped"):
    cmds.file(new=True, force=True) if callable(getattr(cmds, "file", None)) else None
    S.__init__()
    getattr(bld, kind)(180)
    names = ["L_humerus_gde", "L_femur_gde"] if kind == "biped" else ["L_femur_gde", "L_humerus_gde"]
    before = {n: P(n) for n in names}                       # (pivots: from the pivot groups - Maya only)
    bld.build_all(180)
    g0 = every_guide()[0]
    print(kind, "| checker counts guides as controls:", checker.is_control(g0),
          "| 'not at zero' finds guides:", any(guides.is_guide(n) for n in checker.find_ctrl_zero([])))
    cmds.select(cmds.ls("L_femur_gde", long=True)[0], replace=True)
    try:
        quick.reset()
    except RuntimeError as e:
        print("  reset on a guide:", e)
    zero_all()
    print("  zeroed:", P(names[0]))
    moved, missing = bld.guides_from_rig()
    after = {n: P(n) for n in before}
    print("  guides from the rig: moved", moved, "| back where they were:",
          all(max(abs(a - b) for a, b in zip(before[n], after[n])) < 0.01 for n in before), "| not found:", missing[:3])
    zero_all()
    bld.back_to_guides(True)
    print("  back to guides puts zeroed ones back:", all(max(abs(a - b) for a, b in zip(before[n], P(n))) < 0.01
                                                       for n in before))
