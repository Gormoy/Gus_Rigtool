# 5.0.3: Make animator tools leaves one installer to drag (an old drag_to_maya_anim.mel in the folder goes)
import os, sys, tempfile
exec(open("fakemaya.py").read())
from gus_rigtool.builder import anim_export
d = tempfile.mkdtemp()
open(os.path.join(d, "drag_to_maya_anim.mel"), "w").write("// old")
anim_export.make(d)
mels = sorted(f for f in os.listdir(d) if f.endswith(".mel"))
print("installers in the folder:", mels)
print("the toolkit has one too:", sorted(f for f in os.listdir(os.path.join(os.getcwd(), "..", "anim")) if f.endswith(".mel")))
