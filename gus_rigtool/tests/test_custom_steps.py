# Custom steps: a post script runs after Build and Build picked (it sees the modules and rig groups);
# a failing pre script is reported and the build still happens; off / remove work
import os, tempfile
exec(open("fakemaya.py").read())
from gus_rigtool.builder import build as bld, custom_steps
d = tempfile.mkdtemp()
post = os.path.join(d, "after_build.py"); pre = os.path.join(d, "broken.py")
open(post, "w").write("n = cmds.createNode('transform', name='step_ran_%d' % len(modules))\nprint('post step:', when, sorted(modules)[:3], sorted(rig)[:3])\n")
open(pre, "w").write("raise ValueError('oops in my script')\n")
bld.biped(180)
custom_steps.add(post, "post"); custom_steps.add(pre, "pre")
print("steps:", [custom_steps.label(i) for i in custom_steps.steps()])
bld.build_all(180)
print("built anyway:", bld.is_built(), "| post ran:", [n.name for n in S.nodes if n.name.startswith("step_ran")])
custom_steps.toggle(1)
bld.build_picked(["L:arm"], 180)
print("after Build picked:", sorted(n.name for n in S.nodes if n.name.startswith("step_ran")))
print("labels:", [custom_steps.label(i) for i in custom_steps.steps()])
custom_steps.remove(0); print("after remove:", [custom_steps.label(i) for i in custom_steps.steps()])
