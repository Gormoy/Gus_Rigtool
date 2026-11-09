# 4.5.0: pose library - folders, search, rename, move, update pose / picture, preview (Back undoes it)
import os, sys, tempfile
exec(open("fakemaya.py").read())
from unittest import mock
sys.path.insert(0, os.path.join(os.getcwd(), "..", "anim"))
from gus_animtool import anim as A
LIB = tempfile.mkdtemp()
_opts = {"library": LIB}
A.opt = lambda key, default: _opts.get(key, default)
A.profile = lambda ns=None: {}
cmds.currentTime = mock.MagicMock(return_value=1.0)
def blast(**k):
    open(k["completeFilename"], "w").write("png")
cmds.playblast = blast
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
t = cmds.createNode("transform", name="L_hand_ctrl"); cmds.createNode("nurbsCurve", name="L_hand_ctrlShape", parent=t)
c = cmds.ls(t, long=True)[0]
cmds.setAttr(c + ".tx", 3.0)
check("save at the top", A.save_pose("open", [c], "")[0] == "open")
name, n = A.save_pose("fist!", [c], "", folder="Hands")
check("save in a folder", name == "Hands/fist_" and os.path.exists(os.path.join(LIB, "rig", "Hands", "fist_.json"))
      and os.path.exists(os.path.join(LIB, "rig", "Hands", "fist_.png")))
os.makedirs(os.path.join(LIB, "rig", "clips"))                       # the clip library's folder
check("folders listed (not the clips folder)", A.pose_folders("") == ["Hands"])
check("all poses", A.pose_files("") == ["open", "Hands/fist_"])
check("one folder", A.pose_files("", "Hands") == ["Hands/fist_"])
check("no folder", A.pose_files("", A.NO_FOLDER) == ["open"])
check("search (any case)", A.pose_files("", None, "FIS") == ["Hands/fist_"])
new = A.rename_pose("Hands/fist_", "punch", "")
check("rename keeps the folder (picture too)", new == "Hands/punch" and os.path.exists(os.path.join(LIB, "rig", "Hands", "punch.png")))
A.save_pose("open2", [c], "")
try:
    A.rename_pose("open2", "open", ""); check("no overwriting a pose with the same name", False)
except RuntimeError as e:
    check("no overwriting a pose with the same name", "already" in str(e) and "open2" in A.pose_files(""))
moved = A.move_pose("Hands/punch", "", "")
check("move out of the folder", moved == "punch" and "punch" in A.pose_files("", A.NO_FOLDER))
cmds.setAttr(c + ".tx", 7.0)
check("update pose: the current values", A.update_pose("punch", "") == 1 and A.load_pose("punch", "")["L_hand_ctrl"]["translateX"] == 7.0)
os.remove(os.path.join(LIB, "rig", "punch.png"))
check("update picture", A.snap_picture("punch", "") and os.path.exists(os.path.join(LIB, "rig", "punch.png")))
check("a folder can't be called 'clips'", A.make_folder("clips", "") == "clips_poses")
# preview: applied as one undo, Back undoes it
undos = []
cmds.undo = lambda *a, **k: undos.append(1)
A._lib_apply = lambda mirrored=False: None
A._lib.update(picked="punch", preview=False)
A.message = lambda *a, **k: None
A._lib_preview(True)
A._lib_back()
check("preview then Back: one undo", undos == [1] and not A._lib["preview"])
A._lib_preview(False); A._lib_preview(False)
check("a second preview takes the first off first", undos == [1, 1])
A._lib_keep()
try:
    A._lib_back(); check("Back after Keep does nothing", False)
except RuntimeError:
    check("Back after Keep does nothing", undos == [1, 1])
print("ALL OK" if all(ok) else "SOME FAILED")
