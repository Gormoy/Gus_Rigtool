"""
Fixes: corrective shapes. Pose the rig, sculpt the fix, it turns on by itself as the joint bends.

    import gus_rigtool.main as gr; gr.show_tool("fixes")
"""

import json

import maya.cmds as cmds

from gus_rigtool.core import naming, shape_fixes, ui, utils

TOOL = "Fixes"
_P, N, _w, _guard = ui.tool_helpers("p_fixes_", TOOL)


def _light():
    sel = cmds.ls(selection=True, long=True) or []
    sculpt = [s for s in sel if cmds.attributeQuery(shape_fixes.SCULPT_META, node=s, exists=True)]
    if sculpt:
        return "ok", "Sculpting %s: sculpt it, then Apply." % naming.short_name(sculpt[0])
    joints = [s for s in sel if cmds.nodeType(s) == "joint"]
    meshes = [s for s in sel if cmds.listRelatives(s, shapes=True, type="mesh")]
    if meshes and joints:
        return "ok", "Ready: Sculpt fix on %s, driven by %s." % (naming.short_name(meshes[0]),
                                                                 naming.short_name(joints[0]))
    if meshes:
        n = len(shape_fixes.listing(meshes[0]))
        return "idle", "%s: %d fix(es). Add the joint that bends to the selection to sculpt one." % (
            naming.short_name(meshes[0]), n)
    return "idle", "Pose the rig, select the skinned mesh and the joint that bends."


def sculpt(*_):
    name = cmds.textField(N("Name"), query=True, text=True).strip() or None
    shape_fixes.start(name=name)
    refresh()


def apply(*_):
    shape_fixes.apply()
    refresh()


def cancel(*_):
    sel = [s for s in cmds.ls(selection=True, long=True) or []
           if cmds.attributeQuery(shape_fixes.SCULPT_META, node=s, exists=True)]
    if not sel:
        sel = [t for t in cmds.ls(type="transform", long=True) or []
               if cmds.attributeQuery(shape_fixes.SCULPT_META, node=t, exists=True)]
    if not sel:
        raise RuntimeError("no sculpt to cancel.")
    for s in sel:
        info = json.loads(cmds.getAttr(s + "." + shape_fixes.SCULPT_META))
        if cmds.objExists(info["mesh"]):
            cmds.setAttr(info["mesh"] + ".visibility", True)
        cmds.delete(s)
    utils.info(TOOL, "sculpt cancelled.")
    refresh()


def _mesh():
    for s in cmds.ls(selection=True, long=True) or []:
        if cmds.listRelatives(s, shapes=True, type="mesh") and \
                not cmds.attributeQuery(shape_fixes.SCULPT_META, node=s, exists=True):
            return s
    return _P.get("mesh")


def refresh(*_):
    if not cmds.textScrollList(N("List"), exists=True):
        return
    mesh = _mesh()
    _P["mesh"] = mesh
    cmds.textScrollList(N("List"), edit=True, removeAll=True)
    rows = shape_fixes.listing(mesh) if mesh and cmds.objExists(mesh) else []
    _P["rows"] = rows
    for name, joint, angle, w in rows:
        cmds.textScrollList(N("List"), edit=True, append="%-24s %-22s %3d deg   now %.2f" % (
            name, naming.short_name(joint), int(round(angle)), w))
    cmds.text(N("Mesh"), edit=True, label="  %s" % (naming.short_name(mesh) if mesh else "(select a mesh)"))


def _picked():
    idx = cmds.textScrollList(N("List"), query=True, selectIndexedItem=True) or []
    rows = _P.get("rows") or []
    out = [rows[i - 1][0] for i in idx if 0 < i <= len(rows)]
    if not out:
        raise RuntimeError("pick a fix in the list.")
    return out


def mirror(*_):
    for name in _picked():
        shape_fixes.mirror(_P["mesh"], name)
    refresh()


def delete(*_):
    names = _picked()
    if cmds.confirmDialog(title="Delete fixes", message="Delete %s?" % ", ".join(names),
                          button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Delete":
        return
    for name in names:
        shape_fixes.remove(_P["mesh"], name)
    utils.info(TOOL, "deleted %d fix(es)." % len(names))
    refresh()


def resculpt(*_):
    """Sculpt the picked fix again in the current pose (Apply replaces it, its reader stays)."""
    name = _picked()[0]
    rec = shape_fixes.fixes(shape_fixes.blendshape_of(_P["mesh"], create=False))[name]
    shape_fixes.start(_P["mesh"], rec["joint"], name)
    refresh()


def select_joint(*_):
    rows = dict((r[0], r[1]) for r in _P.get("rows") or [])
    cmds.select([rows[n] for n in _picked() if n in rows], replace=True)


def build(prefix="p_fixes_"):
    _P["p"] = prefix
    ui.status_light(N("Light"), _light, _w)
    ui.section("Sculpt a fix", step=1, help_text="Pose the rig (bend the elbow), select the skinned mesh and the "
               "joint that bends, Sculpt fix: a copy of the mesh in this pose appears (the mesh hides). Sculpt it "
               "with any tool - don't add or delete points - then Apply: it becomes a blendShape target in front "
               "of the skin, and turns on by itself as the joint bends (1 at the sculpted bend, 0 at rest).")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(90, 200))
    cmds.text(label="Name (optional)")
    cmds.textField(N("Name"), placeholderText="e.g. L_elbow_bend - blank: joint + angle")
    cmds.setParent("..")
    ui.main_button("Sculpt fix", _w(_guard(sculpt)), "A copy of the posed mesh to sculpt.")
    ui.row(2, 170)
    cmds.button(label="Apply", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(apply)),
                annotation="The selected sculpt becomes the fix.")
    cmds.button(label="Cancel sculpt", command=_w(_guard(cancel)), annotation="Delete the sculpt copy.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Fixes on the mesh", step=2, help_text="Select a mesh: its fixes, the joint driving each, the bend "
               "it's sculpted at and its weight now. Mirror: the same fix on the other side (the twin joint, "
               "mirrored points - the mesh must be symmetric). Sculpt again: pose, then re-sculpt the picked fix "
               "(Apply replaces it).")
    cmds.text(N("Mesh"), label="", align="left", font="boldLabelFont")
    cmds.textScrollList(N("List"), height=120, allowMultiSelection=True, font="fixedWidthFont")
    ui.row(3, 113)
    cmds.button(label="Refresh", command=_w(refresh))
    cmds.button(label="Mirror", command=_w(_guard(mirror)))
    cmds.button(label="Sculpt again", command=_w(_guard(resculpt)))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Select joint", command=_w(_guard(select_joint)))
    cmds.button(label="Delete", command=_w(_guard(delete)))
    cmds.setParent("..")
    ui.end_section()
    ui.on_selection(N("List"), _w(refresh))
    refresh()
