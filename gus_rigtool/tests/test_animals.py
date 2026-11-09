# Quadruped template animal presets: dog keeps the old spots, horse / cat / rabbit change proportions and counts
exec(open("fakemaya.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
from gus_rigtool.builder import build as bld, guides
for animal in bld.ANIMAL_NAMES:
    for g in guides.module_groups():
        cmds.delete(g)
    bld.quadruped(100.0, animal)
    info = {(guides.read(g)["type"], guides.read(g)["side"]): guides.read(g) for g in guides.module_groups()}
    neck = info[("neck", "C")]["settings"]["options"]["joint_count"]
    tail = info[("chain", "C")]["settings"]["names"]["count"]
    toes = info[("back_leg", "L")]["settings"]["options"]["toe_count"]
    p = guides.positions(info[("back_leg", "L")]["group"])
    hips = guides.positions(info[("spine", "C")]["group"])["hips"]
    print("%-7s neck %d tail %d toes %d | femur y %.1f | hips y %.1f | modules %d" % (
        animal, neck, tail, toes, p["femur"][1], hips[1], len(info)))
bld.build_all(100.0)
print("rabbit builds:", bld.is_built())
