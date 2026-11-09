# 5.0.0: every 'Take me there' in the Guide points at a tool that exists, and a section that tool really has
import os, re, sys
exec(open("fakemaya.py").read())
from gus_rigtool import registry
from gus_rigtool.tools import guide
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
ROOT = os.path.join(os.getcwd(), "..")
mods = {k: m for k, _l, m, _s in registry.TOOLS}
bad = []
for key, title, _intro, steps, _tip in guide.PAGES:
    for text, tool, section in steps:
        if tool not in mods:
            bad.append("%s: no tool %r" % (title, tool)); continue
        if section is None:
            continue
        src = ""
        for m in [mods[tool]] + [mods[tool].rsplit(".", 1)[0] + "." + x for x in ("build_existing", "build_form")]:
            path = os.path.join(ROOT, *m.split(".")[1:]) + ".py"
            if os.path.exists(path):
                src += open(path).read()
        if section not in src:
            bad.append("%s: %s has no section %r" % (title, tool, section))
check("every Guide step opens a real tool and section", not bad)
for b in bad:
    print("   ", b)
check("pages: start, the 5 steps, toolbox, animators", [p[0] for p in guide.PAGES] ==
      ["start", "guides", "build", "skin", "controls", "finish", "toolbox", "anim"])
html = guide.html()
check("the web page has every page", all(guide._esc(p[1]) in html for p in guide.PAGES))
print("ALL OK" if all(ok) else "SOME FAILED")
