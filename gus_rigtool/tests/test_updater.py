# Updater: installs the zip's gus_rigtool over an installed copy, keeps a backup, skips tests, reads versions
import os, sys, shutil, tempfile, zipfile
exec(open("fakemaya.py").read())
import gus_rigtool
from gus_rigtool.core import updater
work = tempfile.mkdtemp()
inst = os.path.join(work, "scripts", "gus_rigtool")
os.makedirs(inst)
open(os.path.join(inst, "__init__.py"), "w").write('__version__ = "1.0.0"\n')
open(os.path.join(inst, "old_only.py"), "w").write("x = 1\n")
os.makedirs(os.path.join(inst, "__pycache__")); open(os.path.join(inst, "__pycache__", "a.pyc"), "w").write("")
z = os.path.join(work, "Gus_Rigtool_install (3).zip")
with zipfile.ZipFile(z, "w") as zf:
    zf.writestr("drag_to_maya.mel", "// mel")
    zf.writestr("gus_rigtool/__init__.py", '__version__ = "9.9.9"\n')
    zf.writestr("gus_rigtool/core/new.py", "y = 2\n")
    zf.writestr("gus_rigtool/tests/test_x.py", "z = 3\n")
print("zip version:", updater.zip_version(z))
real_root = gus_rigtool.ROOT
gus_rigtool.ROOT = inst
old, new, backup = updater.install(z)
gus_rigtool.ROOT = real_root
print("old -> new:", old, "->", new)
print("installed version file:", open(os.path.join(inst, "__init__.py")).read().strip())
print("new file there:", os.path.isfile(os.path.join(inst, "core", "new.py")),
      "| tests skipped:", not os.path.exists(os.path.join(inst, "tests")),
      "| old pycache gone:", not os.path.exists(os.path.join(inst, "__pycache__")))
print("backup has the old version:", open(os.path.join(backup, "__init__.py")).read().strip(), "| backup name:", os.path.basename(backup))
print("older check:", updater._key("3.2.3") < updater._key("3.10.0"))
shutil.rmtree(work)
