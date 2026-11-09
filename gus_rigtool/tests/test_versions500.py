# 5.0.0: Gus Animtool always carries Gus_Rigtool's version (animators can tell they have the newest tools)
import os, re
here = os.getcwd()
rig = re.search(r'__version__ = "([^"]+)"', open(os.path.join(here, "..", "__init__.py")).read()).group(1)
anim = re.search(r'__version__ = "([^"]+)"', open(os.path.join(here, "..", "anim", "gus_animtool", "__init__.py")).read()).group(1)
print("same version:", rig == anim, "| WHATSNEW.txt names it:", ("Gus_Rigtool %s" % rig) in
      open(os.path.join(here, "..", "WHATSNEW.txt")).read())
