"""
Deliver: one folder with everything the animators need, without touching your working scene.

    <folder>/<name>_rig.ma          the rig, published (your scene is published only for the save, then put back)
    <folder>/animator_tools/        Gus Animtool with your naming + its installer (drag_to_maya_animtool.mel)
    <folder>/rig_check.txt          the Checker's report on the rig
    <folder>/README.txt             what's in the rig, how to use it, your notes
    <folder>.zip                    (option) the folder zipped, to send

    from gus_rigtool.builder import deliver; deliver.deliver("D:/delivery/hero_v001", "hero")
"""

import datetime
import os
import shutil

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.builder import publish

TOOL = "Deliver"

README = """{name} - rig delivery ({date})

Made with Gus_Rigtool {rig_version}. Animator tools: Gus Animtool {anim_version}.

IN THIS FOLDER
  {scene}            the rig - reference it into your shot (File > Create Reference). The model is inside it:
                        no other file needed
  animator_tools/       picker, pose library, IK/FK switch, mirror, tween... (works with this rig as it is)
  rig_check.txt         the rig check: {fails} fail, {warns} warning

INSTALL THE ANIMATOR TOOLS (once)
  Drag animator_tools/drag_to_maya_animtool.mel into Maya's viewport (Maya 2024 or later).
  A "Gus_Animtool" shelf appears. Later: import gus_animtool; gus_animtool.show()

THE RIG
  Controls: {controls}
  Parts: {modules}
  Reset pose: Gus Animtool > Reset (each control remembers its default pose).
  IK / FK: Gus Animtool > Limbs > IK/FK switch (no jump).
  Selection sets: rig_ctrls_set (every control, a set per part), bind_joints_set.

THE PICKER (Gus Animtool > Picker)
  It comes with the rig: {picker}.
  Edit it and Save: your version stays on your computer and you see it in every shot with this rig.
  Picker > Export picker... / Import picker...: take it to another computer (or give it to someone).
  Picker > Back to the rig's picker: forget your version.

POSE LIBRARY
  {poses}.
  Reference the rig with the same namespace everywhere (a version number at the end doesn't matter).
{notes}"""


def _modules():
    from gus_rigtool.builder import build as bld
    try:
        return ["%s (%s)" % (i.get("name") or i.get("id"), i.get("type")) for i in bld._infos()
                if bld.is_module_built(i)]
    except Exception:
        return []


def _anim_version():
    import re
    path = os.path.join(gus_rigtool.ROOT, "anim", "gus_animtool", "__init__.py")
    try:
        with open(path) as f:
            got = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
        return got.group(1) if got else "?"
    except (IOError, OSError):
        return "?"


def default_name():
    scene = cmds.file(query=True, sceneName=True) or ""
    base = os.path.splitext(os.path.basename(scene))[0] if scene else "rig"
    for tail in ("_publish", "_rig", "_wip"):
        if base.lower().endswith(tail):
            base = base[:-len(tail)]
    return base or "rig"


def _referenced_files():
    try:
        return cmds.file(query=True, reference=True) or []
    except RuntimeError:
        return []


def model_inside(log=None):
    """In the OPEN scene (the delivery copy): every referenced file imported (nested ones too; unloaded ones
    removed), the namespaces merged away (Geo_Hare_07:Belt -> Belt), then the duplicate names that leaves renamed.
    Returns lines."""
    from gus_rigtool.tools import checker
    lines = []
    for _round in range(10):                               # nested references come in on the next round
        refs = _referenced_files()
        if not refs:
            break
        for r in refs:
            try:
                loaded = cmds.referenceQuery(r, isLoaded=True)
            except RuntimeError:
                loaded = False
            if loaded:
                cmds.file(r, importReference=True)
                lines.append("model imported: %s" % os.path.basename(r))
            else:
                cmds.file(r, removeReference=True)
                lines.append("unloaded reference removed: %s" % os.path.basename(r))
    spaces = [n for n in (cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True) or [])
              if n.split(":")[-1] not in ("UI", "shared")]
    for ns in sorted(spaces, key=lambda n: -n.count(":")):  # the deepest first
        try:
            cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            lines.append("namespace merged away: %s:" % ns)
        except RuntimeError as e:
            lines.append("namespace %s kept (%s)" % (ns, str(e).strip()))
    dups = checker.find_dup_names(None)
    if dups:
        n = checker.fix_dup_names(dups, ask=False)
        lines.append("%d duplicate name(s) renamed (the model's copies of Belt, Gums_UP...)" % n)
    return lines


def deliver(folder, name=None, notes="", zip_it=False, options=None, import_model=True):
    """Write the delivery folder. Returns {'scene', 'folder', 'zip', 'fails', 'warns', 'model'}.
    Your scene: published only while saving the copy, then put back as it was (if it wasn't published).
    import_model (5.4.0): the copy is opened, the model imported into it (no reference to your model file, no
    'Geo_...:' prefix), saved, and your scene opened again - so your scene must be saved first."""
    from gus_rigtool.builder import anim_export
    if not publish.rig_group():
        raise RuntimeError("no rig with controls in the scene (Build first, or select your rig's top group).")
    work = cmds.file(query=True, sceneName=True) or ""
    if import_model and _referenced_files():
        if not work:
            raise RuntimeError("save your scene first: the delivery opens a copy to put the model inside it, then "
                               "opens your scene again.")
        if cmds.file(query=True, modified=True):
            raise RuntimeError("your scene has unsaved changes: save it first (the delivery opens a copy to put "
                               "the model inside it, then opens your scene again from disk).")
    name = (name or default_name()).strip().replace(" ", "_")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    scene = os.path.join(folder, "%s_rig.ma" % name)
    was = publish.is_published()
    o = dict(publish.DEFAULTS)
    o.update(options or {})
    if o.get("guides") == "delete":
        o["guides"] = "hide"                       # never delete your guides for a delivery
    try:
        if not was:
            publish.publish(o)
        fails, warns, report = publish.check()
        cmds.file(scene, exportAll=True, type="mayaAscii", force=True, preserveReferences=True)
    finally:
        if not was:
            try:
                publish.unpublish(quiet=True)
            except Exception:
                pass
    model = []
    if import_model and _referenced_files():
        try:
            cmds.file(scene, open=True, force=True)
            from gus_rigtool.core import network_tools
            locked = network_tools.unprotect()            # renaming the model's duplicates needs them unlocked
            model = model_inside()
            if locked:
                network_tools.protect()
            fails, warns, report = publish.check()
            cmds.file(save=True, type="mayaAscii", force=True)
        finally:
            cmds.file(work, open=True, force=True)
    with open(os.path.join(folder, "rig_check.txt"), "w") as f:
        f.write(report)
    anim_export.make(os.path.join(folder, "animator_tools"))
    poses = copy_poses(os.path.splitext(scene)[0] + "_poses")      # 5.6.22: next to the rig
    ctrls = publish.rig_controls()
    top = publish.rig_group()
    has_picker = bool(top and cmds.attributeQuery("gusPicker", node=top, exists=True) and
                      cmds.getAttr(top + ".gusPicker"))
    picker = ("the rigger's picker, saved in the rig" if has_picker else
              "made automatically from the controls when it opens (the rigger can save one in the rig)")
    with open(os.path.join(folder, "README.txt"), "w") as f:
        f.write(README.format(
            name=name, date=datetime.date.today().isoformat(), rig_version=gus_rigtool.__version__,
            anim_version=_anim_version(), scene=os.path.basename(scene), fails=fails, warns=warns,
            controls=len(ctrls), modules=", ".join(_modules()) or "-", picker=picker,
            notes=("\nNOTES\n  " + notes.strip().replace("\n", "\n  ") + "\n") if notes.strip() else "",
            poses=("%d pose(s) and %d clip(s) in %s/ - the pose library fills itself from them the first time it "
                   "opens on this rig (Library > Get the rig's poses: again, any time)" % (
                       poses["poses"], poses["clips"], os.path.basename(poses["folder"]))) if poses["poses"] or
            poses["clips"] else "none saved by the rigger"))
    out = {"scene": scene, "folder": folder, "zip": None, "fails": fails, "warns": warns, "model": model,
           "poses": poses, "picker": has_picker}
    if zip_it:
        out["zip"] = shutil.make_archive(folder.rstrip("/\\"), "zip", os.path.dirname(folder.rstrip("/\\")),
                                         os.path.basename(folder.rstrip("/\\")))
    return out


def copy_poses(dst):
    """5.6.22: the rigger's pose library for this rig (poses, folders, clips) -> dst (next to the delivered rig).
    Returns {'folder', 'poses', 'clips'}."""
    out = {"folder": dst, "poses": 0, "clips": 0}
    try:
        from gus_animtool import anim as A
        src = A.character_folder("")
    except Exception:
        return out
    if not os.path.isdir(src):
        return out
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        for f in files:
            if not f.endswith((".json", ".png")):
                continue
            to = os.path.join(dst, rel) if rel != "." else dst
            if not os.path.isdir(to):
                os.makedirs(to)
            shutil.copy2(os.path.join(root, f), os.path.join(to, f))
            if f.endswith(".json"):
                out["clips" if rel.split(os.sep)[0] == "clips" else "poses"] += 1
    return out


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

WIN = "gusRigDeliverWin"


def show(*_):
    from gus_rigtool.core import utils
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    s = utils.load_setting("deliver", {}) or {}
    cmds.window(WIN, title="Gus_Rigtool - Deliver to animators", widthHeight=(460, 330))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnAttach=("both", 8))
    cmds.text(label="One folder: the published rig (.ma), the animator tools with your naming, the rig check and "
                    "a README. Your scene stays as it is.", align="left", wordWrap=True)
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 300))
    cmds.text(label="Rig name")
    cmds.textField(WIN + "Name", text=default_name())
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(70, 300, 60))
    cmds.text(label="Folder")
    cmds.textField(WIN + "Folder", text=s.get("parent", ""))
    cmds.button(label="Browse", command=lambda *_: _browse())
    cmds.setParent("..")
    cmds.text(label="Notes for the animators (optional)", align="left")
    cmds.scrollField(WIN + "Notes", height=70, wordWrap=True, text="")
    cmds.checkBox(WIN + "Model", label="Model inside the rig (import the referenced model, no 'Geo_...:' prefix)",
                  value=bool(s.get("model", True)),
                  annotation="The delivered rig doesn't point to your model file: one file is all the animators "
                             "need. Your scene must be saved first; it's opened again after.")
    cmds.checkBox(WIN + "Zip", label="Also make a .zip to send", value=bool(s.get("zip", False)))
    cmds.button(label="Deliver", height=34, backgroundColor=(0.33, 0.52, 0.40), command=lambda *_: _go())
    cmds.showWindow(WIN)


def _browse():
    got = cmds.fileDialog2(fileMode=3, caption="Where to put the delivery folder")
    if got:
        cmds.textField(WIN + "Folder", edit=True, text=got[0])


def _go():
    from gus_rigtool.core import ui, utils
    name = cmds.textField(WIN + "Name", query=True, text=True).strip() or default_name()
    parent = cmds.textField(WIN + "Folder", query=True, text=True).strip()
    if not parent:
        cmds.confirmDialog(title=TOOL, message="Pick a folder first (Browse).", button=["OK"])
        return
    zip_it = cmds.checkBox(WIN + "Zip", query=True, value=True)
    model = cmds.checkBox(WIN + "Model", query=True, value=True)
    utils.save_setting("deliver", {"parent": parent, "zip": zip_it, "model": model})
    if model and _referenced_files() and cmds.file(query=True, modified=True):
        if cmds.confirmDialog(title=TOOL, message="Your scene has unsaved changes. Save it, then deliver?\n(The "
                              "delivery opens a copy to put the model inside it, then opens your scene again.)",
                              button=["Save and deliver", "Cancel"], defaultButton="Save and deliver",
                              cancelButton="Cancel", dismissString="Cancel") != "Save and deliver":
            return
        cmds.file(save=True)
    folder = os.path.join(parent, "%s_delivery" % name)
    try:
        got = deliver(folder, name, cmds.scrollField(WIN + "Notes", query=True, text=True), zip_it,
                      import_model=model)
    except (RuntimeError, ValueError, IOError, OSError) as e:
        cmds.confirmDialog(title=TOOL, message=str(e), button=["OK"])
        return
    utils.info(TOOL, "delivered: %s%s" % (folder, (" + " + got["zip"]) if got["zip"] else ""))
    ui.report_window("Gus_Rigtool - delivered",
                     "Folder: %s\n\n  %s\n  animator_tools/\n  rig_check.txt (%d fail, %d warning)\n  README.txt%s"
                     % (folder, os.path.basename(got["scene"]), got["fails"], got["warns"],
                        ("\n\nZip: " + got["zip"]) if got["zip"] else "")
                     + (("\n\nIn the delivered rig:\n  " + "\n  ".join(got["model"])) if got.get("model") else "")
                     + ("\n\nThe rig check found problems - look at rig_check.txt before sending."
                        if got["fails"] else "")
                     + ("\n\n%s/: %d pose(s), %d clip(s)" % (os.path.basename(got["poses"]["folder"]),
                                                          got["poses"]["poses"], got["poses"]["clips"])
                        if got["poses"]["poses"] or got["poses"]["clips"] else "\n\nNo poses of yours to send.")
                     + ("" if got.get("picker") else "\n\nNO PICKER SAVED IN THE RIG: the animators get the automatic "
                        "one. Open the picker, Edit, Save (in the rig file), save the scene and deliver again."))
