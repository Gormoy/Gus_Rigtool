# Deliver to animators: one folder (published rig .ma, animator tools, rig check, README, optional zip);
# the working scene is published only for the save and put back
exec(open("fakemaya.py").read())
import os, tempfile
from gus_rigtool.builder import build as bld, publish, deliver
try:
    deliver.deliver(os.path.join(tempfile.mkdtemp(), "x"))
except RuntimeError as e:
    print("no rig:", e)
bld.biped(100); bld.build_all(100)
saved = []
real_file = cmds.file
def file_(*a, **k):
    if k.get("exportAll"):
        saved.append((os.path.basename(a[0]), publish.is_published()))
        open(a[0], "w").write("//Maya ASCII\n")
        return a[0]
    if k.get("query") and k.get("sceneName"):
        return "/work/hero_wip.ma"
    return real_file(*a, **k) if callable(real_file) else None
cmds.file = file_
print("default name:", deliver.default_name())
root = tempfile.mkdtemp()
got = deliver.deliver(os.path.join(root, "hero_delivery"), "hero", notes="Feet: use the heel roll.", zip_it=True)
print("saved:", saved, "| scene published after:", publish.is_published())
print("files:", sorted(os.listdir(got["folder"])))
print("animator tools:", sorted(os.listdir(os.path.join(got["folder"], "animator_tools"))))
print("zip:", os.path.basename(got["zip"]), os.path.isfile(got["zip"]))
text = open(os.path.join(got["folder"], "README.txt")).read()
print("readme:", "hero_rig.ma" in text, "Controls: %d" % len(publish.rig_controls()) in text, "heel roll" in text,
      "Parts:" in text and "arm" in text.lower())
# already published: stays published
publish.publish(); saved[:] = []
deliver.deliver(os.path.join(root, "again"), "hero")
print("already published -> saved published:", saved, "| still published:", publish.is_published())
