# Self-test: runs end to end on the fake (constraints aren't solved here, so only the flow and the report are checked)
exec(open("fakemaya.py").read())
def _file(*a, **k):
    if k.get("new"):
        S.__init__()
    return False
cmds.file = _file
cmds.about = lambda **k: "fake"
from gus_rigtool.builder import selftest
text = selftest.run(100)
lines = text.splitlines()
print(lines[0].split(" - ")[0].split(" ")[0], "| sections:", [l for l in lines if l.startswith("==")])
print("checks per row kind:", sorted(set(l.split()[0] for l in lines if l.startswith("  "))))
print("crashed:", [l for l in lines if "crashed" in l or " build " in l])
names_ = sorted(set(l[8:].split("  ")[0].split(" (")[0] for l in lines if l.startswith("  ")))
print("\n".join(names_))
print("skips:", [l.strip() for l in lines if l.startswith("  SKIP")])
