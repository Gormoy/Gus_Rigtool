"""
Face: the face on the mesh, the way Tubero's was made - ribbons on edge loops (follicle joints + controls), the
eye control's Blink, a mouth ribbon following the jaw, brows as a control hierarchy.

    import gus_rigtool.main as gr; gr.show_tool("face")
"""

import maya.cmds as cmds

from gus_rigtool.core import face_kit, naming, ui, utils

TOOL = "Face"
SETTINGS_KEY = "face_kit"
DEFAULTS = {"style": "cartoony", "head": "", "jaw": "", "mirror": True, "extras": False, "brow_count": 3,
            "strip_name": "facial", "mouth_ribbon": "", "face_ribbons": "", "group_weight": 0.5,
            "squash_meshes": "", "squash_fade": 0.0, "squash_curves": True,
            "pose_holder": "Mouth_main_ctrl", "pose_name": "Smile", "pose_split": True,
            "pose_keep_on": True}
_P, N, _w, _guard = ui.tool_helpers("p_face_", TOOL)


def _s():
    return utils.tool_settings(SETTINGS_KEY, DEFAULTS)


def _save(*_):
    s = _s()
    s["style"] = ["cartoony", "realistic"][cmds.radioButtonGrp(N("Style"), query=True, select=True) - 1]
    for key in ("head", "jaw", "strip_name"):
        s[key] = cmds.textField(N(key), query=True, text=True).strip()
    s["mirror"] = cmds.checkBox(N("Mirror"), query=True, value=True)
    s["extras"] = cmds.checkBox(N("Extras"), query=True, value=True)
    s["brow_count"] = cmds.intField(N("BrowCount"), query=True, value=True)
    utils.save_setting(SETTINGS_KEY, s)
    return s


def _pick(key, kind):
    sel = cmds.ls(selection=True) or []
    if not sel:
        raise RuntimeError("select the %s first." % kind)
    cmds.textField(N(key), edit=True, text=sel[0].split(".")[0])
    _save()


def _light():
    sel = cmds.ls(selection=True, flatten=True) or []
    edges = [e for e in sel if ".e[" in e]
    if edges:
        return "ok", "%d edges selected: make the eyelids, mouth, brows or a strip from them." % len(edges)
    s = _s()
    if not s.get("head"):
        return "warn", "Pick the head joint first (select it, press < next to Head)."
    return "idle", "Select the edges round the LEFT eye / the lips / along the LEFT brow, then the matching button."


def make_eyes(*_):
    s = _save()
    sel = cmds.ls(selection=True) or []
    if not sel:
        raise RuntimeError("select the LEFT eye mesh (or a locator at its centre).")
    face_kit.eyes(sel[0], s["head"])


def aim_eyes(*_):
    s = _save()
    sel = cmds.ls(selection=True, type="joint") or []
    face_kit.aim_eyes(sel, s.get("head") or None)


def _save_groups(*_):
    s = _s()
    for key in ("mouth_ribbon", "face_ribbons"):
        s[key] = cmds.textField(N(key), query=True, text=True).strip()
    s["group_weight"] = cmds.floatField(N("group_weight"), query=True, value=True)
    utils.save_setting(SETTINGS_KEY, s)
    return s


def _pick_ribbon(key, add):
    from gus_rigtool.core import group_ctrls as GC
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        raise RuntimeError("select a control of the ribbon.")
    names = []
    for n in sel:
        r = GC.ribbon_of(n)
        if r and r not in names:
            names.append(r)
    if not names:
        raise RuntimeError("the selected control isn't on a ribbon the tool made.")
    if add:
        have = [x.strip() for x in cmds.textField(N(key), query=True, text=True).split(",") if x.strip()]
        names = have + [x for x in names if x not in have]
    cmds.textField(N(key), edit=True, text=", ".join(names))
    _save_groups()


def make_mouth_groups(*_):
    from gus_rigtool.core import group_ctrls as GC
    s = _save_groups()
    face_s = _s()
    mouth = GC.ribbon_controls(s["mouth_ribbon"])
    if not mouth:
        raise RuntimeError("pick the mouth ribbon first (select a mouth control, press '< sel').")
    face = GC.ribbon_controls(*[x.strip() for x in s["face_ribbons"].split(",")])
    head, jaw = GC.head_and_jaw(face_s.get("head"), face_s.get("jaw"))
    if not head:
        raise RuntimeError("no head control found: pick the head above (step 1).")
    plan = GC.mouth_plan(mouth, face)
    lines = GC.plan_text(plan)
    msg = "\n".join(lines) + "\n\nUnder %s%s. Nothing moves. One undo." % (
        naming.short_name(head), (" (the lower lip under %s)" % naming.short_name(jaw)) if jaw else "")
    if cmds.confirmDialog(title="Gus_Rigtool - mouth group controls", message=msg, button=["Make", "Cancel"],
                          defaultButton="Make", cancelButton="Cancel", dismissString="Cancel") != "Make":
        return
    made = GC.make_mouth(plan, head, jaw)
    utils.info(TOOL, "%d group control(s): %s." % (len(made), ", ".join(naming.short_name(c) for c in made)))
    if made:
        cmds.select(made)


def set_group_weight(*_):
    from gus_rigtool.core import group_ctrls as GC
    s = _save_groups()
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if len(sel) < 2 or not GC.read(sel[0]) and not cmds.attributeQuery(GC.META, node=sel[0], exists=True):
        raise RuntimeError("select the group control first, then the controls it should move.")
    w = float(s["group_weight"])
    with utils.undo_chunk("gusrigGroupWeight"):
        GC.set_weights(sel[0], dict((c, w) for c in sel[1:]))
    utils.info(TOOL, "%d control(s) on %s at %.2f%s." % (len(sel) - 1, naming.short_name(sel[0]), w,
                                                          " (taken off)" if w < GC.MIN_WEIGHT else ""))


def new_group_ctrl(*_):
    from gus_rigtool.core import group_ctrls as GC
    s = _save_groups()
    sel = [c for c in cmds.ls(selection=True, long=True, type="transform") or []]
    if not sel:
        raise RuntimeError("select the controls the new group control should move.")
    head, _jaw = GC.head_and_jaw(_s().get("head"))
    i = 1
    while cmds.objExists("Group_%02d_ctrl" % i):
        i += 1
    ps = [cmds.xform(c, query=True, worldSpace=True, translation=True) for c in sel]
    pos = [sum(p[k] for p in ps) / len(ps) for k in range(3)]
    span = max(max(p[k] for p in ps) - min(p[k] for p in ps) for k in range(3)) or 1.0
    pos[2] += span * 0.4
    c = GC.make("Group_%02d_ctrl" % i, dict((x, float(s["group_weight"]) or 1.0) for x in sel), pos, head,
                span * 0.2)
    utils.info(TOOL, "%s moves %d control(s). Rename it as you like." % (naming.short_name(c), len(sel)))
    cmds.select(c)


def remove_group_ctrl(*_):
    from gus_rigtool.core import group_ctrls as GC
    sel = [c for c in cmds.ls(selection=True, long=True, type="transform") or []
           if cmds.attributeQuery(GC.META, node=c, exists=True)]
    if not sel:
        raise RuntimeError("select the group control(s) to remove.")
    for c in sel:
        GC.remove(c)
    utils.info(TOOL, "%d group control(s) removed - the controls they moved stay where they are." % len(sel))


def _save_squash(*_):
    s = _s()
    s["squash_meshes"] = cmds.textField(N("squash_meshes"), query=True, text=True).strip()
    s["squash_fade"] = cmds.floatField(N("squash_fade"), query=True, value=True)
    s["squash_curves"] = False
    utils.save_setting(SETTINGS_KEY, s)
    return s


def pick_squash_meshes(*_):
    sel = [t for t in cmds.ls(selection=True, long=True, type="transform") or []
           if cmds.listRelatives(t, shapes=True, type="mesh")]
    if not sel:
        raise RuntimeError("select the head's meshes (the body, eyes, brows, teeth, hair...).")
    cmds.textField(N("squash_meshes"), edit=True, text=", ".join(naming.short_name(t) if len(cmds.ls(
        naming.short_name(t))) == 1 else t for t in sel))
    _save_squash()


def make_squash(*_):
    from gus_rigtool.core import group_ctrls as GC, head_squash as HS
    s = _save_squash()
    head, _jaw = GC.head_and_jaw(_s().get("head"))
    sel = [c for c in cmds.ls(selection=True, long=True, type="transform") or [] if
           cmds.listRelatives(c, shapes=True, type="nurbsCurve")]
    head = sel[0] if len(sel) == 1 else head
    if not head:
        raise RuntimeError("select the head control (or pick the head above).")
    meshes = [x.strip() for x in s["squash_meshes"].split(",") if x.strip()]
    fade = s["squash_fade"] or None
    lines = HS.plan(head, meshes, fade)
    if cmds.confirmDialog(title="Gus_Rigtool - head squash", message="Under %s:\n" % naming.short_name(head) +
                          "\n".join(lines) + "\n\nNothing moves at rest (checked). One undo.",
                          button=["Make", "Cancel"], defaultButton="Make", cancelButton="Cancel",
                          dismissString="Cancel") != "Make":
        return
    c = HS.make(head, meshes, fade)
    utils.info(TOOL, "%s: up / down squash - stretch, sideways bend. On / off: %s." % (
        naming.short_name(c), HS.read().get("switch")))
    cmds.select(c)


def remove_squash(*_):
    from gus_rigtool.core import head_squash as HS
    if not HS.find() and HS.leftovers():             # 5.6.32: a remove that stopped half-way (Publish's locks)
        from gus_rigtool.core import safe
        kept, got = safe.run(HS.clean_leftovers, label="gusrigHeadSquashLeftovers", states=("rest",))
        if not kept:
            utils.warn(TOOL, "the head squash leftovers were put back - something moved when they went: %s" % got)
            return
        utils.info(TOOL, "head squash leftovers removed, nothing moved: %s." % ", ".join(got))
        return
    n = HS.remove()
    utils.info(TOOL, "head squash removed - the meshes are as they were%s." % (
        "; %d face control(s) repaired (colour, visibility switch, their shape's name)" % n if n else ""))


def clean_copies(*_):
    """5.6.17: the pass-through copies of the selected meshes go (they listed first)."""
    from gus_rigtool.core import head_squash as HS
    sel = [m for m in cmds.ls(selection=True, type="transform", long=True) or []
           if cmds.listRelatives(m, shapes=True, type="mesh")]
    if not sel:
        raise RuntimeError("select the meshes (Hare_Body, the head...).")
    found = [(m, c) for m in sel for c, _s_, _d in HS.mesh_copies(m)]
    if not found:
        utils.info(TOOL, "no extra mesh copies on the %d mesh(es) - nothing to clean." % len(sel))
        return
    msg = "\n".join("%s:  %s" % (naming.short_name(m), naming.short_name(c)) for m, c in found[:20])
    if len(found) > 20:
        msg += "\n... and %d more" % (len(found) - 20)
    if cmds.confirmDialog(title="Gus_Rigtool - mesh copies", message="Copies that only pass the mesh along "
                          "(hidden, fed by another copy):\n" + msg + "\n\nThe skin, ngSkinTools, the original "
                          "and the shape you see are not touched.", button=["Clean", "Cancel"],
                          defaultButton="Clean", cancelButton="Cancel", dismissString="Cancel") != "Clean":
        return
    with utils.undo_chunk("gusrigCleanCopies"):
        n = HS.clean_copies(sel)
    utils.info(TOOL, "%d extra mesh copy(ies) removed." % n)


def _save_poses(*_):
    s = _s()
    s["pose_holder"] = cmds.textField(N("pose_holder"), query=True, text=True).strip()
    s["pose_name"] = cmds.textField(N("pose_name"), query=True, text=True).strip()
    s["pose_split"] = cmds.checkBox(N("pose_split"), query=True, value=True)
    if cmds.checkBox(N("pose_keep_on"), exists=True):
        s["pose_keep_on"] = cmds.checkBox(N("pose_keep_on"), query=True, value=True)
    utils.save_setting(SETTINGS_KEY, s)
    return s


def pick_pose_holder(*_):
    sel = cmds.ls(selection=True, type="transform") or []
    if not sel:
        raise RuntimeError("select the control the sliders go on.")
    cmds.textField(N("pose_holder"), edit=True, text=sel[0])
    _save_poses()
    refresh_poses()


def refresh_poses(*_):
    from gus_rigtool.core import face_poses as FP
    if not cmds.textScrollList(N("Poses"), exists=True):
        return
    h = _s().get("pose_holder")
    cmds.textScrollList(N("Poses"), edit=True, removeAll=True)
    for p in FP.poses(h) if h and cmds.objExists(h) else []:
        d = FP.read(h)[p]
        cmds.textScrollList(N("Poses"), edit=True, append="%s  (%s, %d controls)" % (
            p, " / ".join(d["attrs"]), len(d["ctrls"])))


def clean_poses(*_):
    """5.6.17: Refresh - read the sliders again; poses whose sliders are gone leave the list."""
    from gus_rigtool.core import face_poses as FP
    h = _s().get("pose_holder")
    from gus_rigtool.core import group_ctrls as GC
    gone = FP.clean(h) if h and cmds.objExists(h) else []
    with utils.undo_chunk("gusrigRepairLayers"):
        fixed = GC.repair_layers()                      # 5.6.20
    refresh_poses()
    utils.info(TOOL, "poses read again%s%s%s." % (
        ": dropped %s (their sliders were gone)" % ", ".join(gone) if gone else " - all there",
        "; layers repaired: %s" % ", ".join(fixed["healed"][:6]) if fixed["healed"] else "",
        "; %d empty layer(s) gone" % fixed["dropped"] if fixed["dropped"] else ""))


_EDITING = {}             # 5.6.20: the pose Edit picked pose put on the controls (Save then replaces it by default)


def save_face_pose(*_):
    from gus_rigtool.core import face_poses as FP
    s = _save_poses()
    if not s["pose_holder"] or not cmds.objExists(s["pose_holder"]):
        raise RuntimeError("pick the control the sliders go on (Mouth_main_ctrl: make the group controls first, "
                           "or select any face control and press '< sel').")
    if not s["pose_name"]:
        raise RuntimeError("type the new pose's name (Smile, Angry, Surprised...).")
    name = FP._attr_name(s["pose_name"])
    keep_on = s.get("pose_keep_on", True)
    notes = []
    on = FP.sliders_on(s["pose_holder"]) if keep_on else {}
    if on:
        notes.append("On now - it goes into this pose too: " + ", ".join("%s (%.2f)" % kv for kv in sorted(on.items())))
    extra = FP.moved_outside(s["pose_holder"])
    if extra:
        notes.append("Moved, but not in the face: " + ", ".join(naming.short_name(c) for c in extra[:8]) +
                     (" ..." if len(extra) > 8 else "") + " - Include them? (Leave out: the pose without them)")
    existing = FP.poses(s["pose_holder"])
    if name in existing:                             # 5.6.20: a new one beside it, unless you say replace
        n = 2
        while "%s%d" % (name, n) in existing:
            n += 1
        new = "%s%d" % (name, n)
        buttons = ["Save as new: " + new, "Replace " + name, "Cancel"]
        if _EDITING.get("pose") == name:             # after Edit picked pose: replacing it is what you meant
            buttons = ["Replace " + name, "Save as new: " + new, "Cancel"]
        got = cmds.confirmDialog(title="Gus_Rigtool - save pose", message="%s is there already.\n\n%s" % (
            name, "\n\n".join(notes)), button=buttons, defaultButton=buttons[0], cancelButton="Cancel",
            dismissString="Cancel")
        if got == "Cancel":
            return
        if got.startswith("Save as new"):
            s["pose_name"] = new
        notes = []
    if notes:
        buttons = (["Save, include them", "Save, leave them out", "Cancel"] if extra else ["Save", "Cancel"])
        got = cmds.confirmDialog(title="Gus_Rigtool - save pose", message="\n\n".join(notes), button=buttons,
                                 defaultButton=buttons[0], cancelButton="Cancel", dismissString="Cancel")
        if got == "Cancel":
            return
        if got == "Save, leave them out":
            extra = []
    got = FP.save_pose(s["pose_holder"], s["pose_name"], s["pose_split"], include_on=keep_on, extra=extra)
    cmds.textField(N("pose_name"), edit=True, text="")            # 5.6.20: the next pose needs its own name
    _EDITING.clear()
    _save_poses()
    refresh_poses()
    utils.info(TOOL, "%s saved from %d control(s): %s on %s. The face is back at rest." % (
        got["pose"], got["controls"], " / ".join(got["attrs"]), s["pose_holder"]))


def remove_face_pose(*_):
    from gus_rigtool.core import face_poses as FP
    s = _save_poses()
    picked = cmds.textScrollList(N("Poses"), query=True, selectItem=True) or []
    name = picked[0].split()[0] if picked else s["pose_name"]
    FP.remove_pose(s["pose_holder"], name)
    refresh_poses()
    utils.info(TOOL, "%s removed." % name)


def edit_face_pose(*_):
    """5.6.18: the picked pose back on its controls - change it, then Save pose (same name) replaces it."""
    from gus_rigtool.core import face_poses as FP
    s = _save_poses()
    picked = cmds.textScrollList(N("Poses"), query=True, selectItem=True) or []
    if not picked:
        raise RuntimeError("pick the pose in the list first.")
    name = picked[0].split()[0]
    got = FP.edit_pose(s["pose_holder"], name)
    _EDITING["pose"] = got["pose"]
    cmds.textField(N("pose_name"), edit=True, text=got["pose"])
    cmds.checkBox(N("pose_split"), edit=True, value=got["split"])
    _save_poses()
    utils.info(TOOL, "%s is on its %d control(s) - change it, then Save pose (it replaces %s)%s." % (
        got["pose"], got["set"], got["pose"], "; not set: " + ", ".join(got["skipped"][:6]) if got["skipped"]
        else ""))


def make_board(*_):
    from gus_rigtool.core import face_sliders as FS, group_ctrls as GC
    s = _save_poses()
    sel = [c for c in cmds.ls(selection=True, long=True, type="transform") or []
           if cmds.listRelatives(c, shapes=True, type="nurbsCurve")]
    head = sel[0] if len(sel) == 1 else GC.head_and_jaw(_s().get("head"))[0]
    if not head:
        raise RuntimeError("select the head control.")
    lines = FS.plan(s["pose_holder"])
    if cmds.confirmDialog(title="Gus_Rigtool - sliders board", message="Next to %s:\n" % naming.short_name(head) +
                          "\n".join(lines) + "\n\nThe knobs drive the sliders; key the knobs.",
                          button=["Make", "Cancel"], defaultButton="Make", cancelButton="Cancel",
                          dismissString="Cancel") != "Make":
        return
    got = FS.make(s["pose_holder"], head)
    utils.info(TOOL, "sliders board: %d expression(s) - %s." % (len(got), ", ".join(sorted(got))))


def remove_board(*_):
    from gus_rigtool.core import face_sliders as FS
    with utils.undo_chunk("gusrigFaceSlidersRemove"):
        done = FS.remove()
    utils.info(TOOL, "sliders board removed - the sliders are free again (at 0)." if done else "no sliders board.")


def zero_face(*_):
    from gus_rigtool.core import face_poses as FP
    with utils.undo_chunk("gusrigZeroFace"):
        FP.zero_drivers()
    utils.info(TOOL, "the face controls and the group controls are back at 0.")


def make_face_sets(*_):
    from gus_rigtool.core import face_poses as FP, group_ctrls as GC
    s = _save_groups()
    mouth = GC.ribbon_controls(s["mouth_ribbon"]) if s.get("mouth_ribbon") else []
    face = GC.ribbon_controls(*[x.strip() for x in s.get("face_ribbons", "").split(",")])
    got = FP.make_sets(mouth, face)
    if not got:
        raise RuntimeError("no face controls found - pick the Mouth ribbon in Group controls (8) first.")
    utils.info(TOOL, "selection sets: %s (in gus_anim_sets - Gus Animtool lists them)." % ", ".join(
        "%s %d" % (k, v) for k, v in sorted(got.items())))


def _eye_ctrl():
    from gus_rigtool.builder import names
    found = cmds.ls(names.make("L", "Eye", "ctrl"), long=True) or []
    if not found:
        raise RuntimeError("make the eyes first (section 1).")
    return found[0]


def make_eyelids(*_):
    s = _save()
    face_kit.group(s["head"] or None)
    face_kit.eyelids(None, _eye_ctrl(), side="L", style=s["style"], do_mirror=s["mirror"])


def make_mouth(*_):
    s = _save()
    face_kit.group(s["head"] or None)
    face_kit.mouth(None, s["jaw"], style=s["style"], realistic_extras=s["extras"] or s["style"] == "realistic")


def make_brows(*_):
    s = _save()
    face_kit.group(s["head"] or None)
    face_kit.brows(None, "L", s["brow_count"], s["style"], s["mirror"])


def make_strip(*_):
    s = _save()
    face_kit.group(s["head"] or None)
    face_kit.facial(None, naming.short_name(s["strip_name"] or "facial"), "L", s["style"], s["mirror"])


_ribbon_rows = {}


def refresh_ribbons(*_):
    from gus_rigtool.core import ribbon
    if not cmds.textScrollList(N("Ribbons"), exists=True):
        return
    rows = [r for r in ribbon.builds_list() if (r[1].get("made_by") or "").startswith("Face kit")
            or face_kit.part_of(r[0])]
    _ribbon_rows[_P["p"]] = rows
    cmds.textScrollList(N("Ribbons"), edit=True, removeAll=True,
                        append=["%s   (%d controls)" % (naming.short_name(k), n) for k, _s, n in rows]
                        or ["(no face ribbons yet)"])


def _picked_ribbon():
    idx = cmds.textScrollList(N("Ribbons"), query=True, selectIndexedItem=True) or []
    rows = _ribbon_rows.get(_P["p"], [])
    if not idx or idx[0] - 1 >= len(rows):
        raise RuntimeError("pick a ribbon in the list first.")
    return rows[idx[0] - 1]


def open_in_ribbon(*_):
    from gus_rigtool.tools import ribbon_tool
    key, st, _n = _picked_ribbon()
    if cmds.objExists(key):
        cmds.select(key, replace=True)
    ribbon_tool.load_settings(key, st)
    ui.go_to_tool("ribbon", "Build and mirror")


def redo_part(*_):
    key, _st, _n = _picked_ribbon()
    data = face_kit.part_of(face_kit.first_side(key)) if face_kit.first_side(key) else None
    if not data:
        raise RuntimeError("%s was made before 4.3.0: it doesn't remember its edges. Delete it and make it again "
                           "once; from then on Redo works." % naming.short_name(key))
    style = "cartoony" if cmds.radioButtonGrp(N("Style"), query=True, select=True) == 1 else "realistic"
    changes = {"style": style}
    if data["part"] == "brows":
        changes["count"] = cmds.intField(N("BrowCount"), query=True, value=True)
    if cmds.confirmDialog(title="Redo %s" % data["part"], button=["Redo", "Cancel"], defaultButton="Redo",
                          cancelButton="Cancel", dismissString="Cancel",
                          message="Make the %s again (%s) from the edges it was made on?\n\nIts ribbons are built "
                                  "again; control shapes and the meshes' skin weights are kept. One undo." % (
                                      data["part"], style)) != "Redo":
        return
    face_kit.redo(key, **changes)
    refresh_ribbons()


def select_ribbon_controls(*_):
    key, _st, _n = _picked_ribbon()
    ctrls = [c for _i, _o, c in face_kit.controls_of(key)]
    if not ctrls:
        raise RuntimeError("no controls found on %s." % naming.short_name(key))
    cmds.select(ctrls, replace=True)


def build(prefix="p_face_"):
    _P["p"] = prefix
    s = _s()
    ui.status_light(N("Light"), _light, _w)
    ui.section("Setup", step=1, help_text="Cartoony: fewer controls (Tubero). Realistic: more controls, and the "
               "mouth gets lip roll and sticky lips. Head: the joint the face hangs from (everything follows it). "
               "Jaw: the control (or joint) the lower lip follows. Jaw, tongue, nose and teeth: the Build tab's "
               "Face module (switch off its eyes, lids, lips and brows).")
    cmds.radioButtonGrp(N("Style"), label="Style", labelArray2=["Cartoony", "Realistic"], numberOfRadioButtons=2,
                        select=1 if s["style"] == "cartoony" else 2, columnWidth3=(60, 90, 90),
                        changeCommand=_w(_save))
    for key, label, kind in (("head", "Head", "head joint"), ("jaw", "Jaw", "jaw control")):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(60, 200, 28))
        cmds.text(label=label, align="right")
        cmds.textField(N(key), text=s[key], changeCommand=_w(_save))
        cmds.button(label="<", command=_w(_guard(lambda *_, k=key, d=kind: _pick(k, d))),
                    annotation="Take the selected %s." % kind)
        cmds.setParent("..")
    cmds.checkBox(N("Mirror"), label="Mirror the left side to the right", value=bool(s["mirror"]),
                  changeCommand=_w(_save))
    ui.end_section()

    ui.section("Eyes", step=2, help_text="Select the LEFT eye mesh: L / R_Eye joints at the eye centres (under the "
               "head), aimed at L / R_Eye_ctrl under Eyes_ctrl (head / world space). Blink and Blink_Height go on "
               "each eye control.")
    ui.main_button("Make eyes", _w(_guard(make_eyes)), "From the selected left eye mesh.")
    cmds.button(label="Aim existing eye joints", height=26, command=_w(_guard(aim_eyes)),
                annotation="Your rig has eye joints already (skinned): select the two - they get aimed at L / "
                           "R_Eye_ctrl under Eyes_ctrl (the rig's own, or a new one with head / world space). The "
                           "joints and the skin stay as they are.")
    ui.end_section()

    ui.section("Eyelids", step=3, help_text="Select the edge loop round the LEFT eye: a ribbon with follicle joints "
               "and controls (L_Eyelid_Ribbon). Blink on L_Eye_ctrl closes the lids (set driven keys on each "
               "control's _driven group - edit them in the Graph Editor); Blink_Height moves where they meet. "
               "Mirrored to the right eye.")
    ui.main_button("Make eyelids", _w(_guard(make_eyelids)), "From the selected edge loop round the left eye.")
    ui.end_section()

    ui.section("Mouth", step=4, help_text="Select the edge loop round the lips: one ribbon (Mouth_ribbon) with "
               "controls all round. Each control follows the jaw by its height: lower lip 1, corners 0.5, upper lip "
               "0 (a 'follow' attribute on each - Follow groups, no constraints on the controls). Realistic (or the "
               "box): Mouth_ctrl with upper_roll, lower_roll and sticky.")
    cmds.checkBox(N("Extras"), label="Lip roll and sticky lips (always on for Realistic)", value=bool(s["extras"]),
                  changeCommand=_w(_save))
    ui.main_button("Make mouth", _w(_guard(make_mouth)), "From the selected edge loop round the lips.")
    ui.end_section()

    ui.section("Brows", step=5, help_text="Select the edges along the LEFT brow: a ribbon with this many controls, "
               "under L_Brow_main_ctrl, under Brows_ctrl - a plain hierarchy: moving the main moves the "
               "others (nothing pins them). Mirrored.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 50))
    cmds.text(label="Controls per brow", align="right")
    cmds.intField(N("BrowCount"), value=int(s["brow_count"]), minValue=2, maxValue=9, step=1, changeCommand=_w(_save))
    cmds.setParent("..")
    ui.main_button("Make brows", _w(_guard(make_brows)), "From the selected edges along the left brow.")
    ui.end_section()

    ui.section("Facial strips", step=6, help_text="Any strip of the face as a ribbon with controls: cheek, "
               "nasolabial line, under the eye... Select the edges on the LEFT side, name it, make it. Mirrored.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(60, 200))
    cmds.text(label="Name", align="right")
    cmds.textField(N("strip_name"), text=s["strip_name"], changeCommand=_w(_save))
    cmds.setParent("..")
    ui.main_button("Make strip", _w(_guard(make_strip)), "From the selected edges on the left side.")
    ui.end_section()

    ui.section("Face ribbons", step=7, help_text="Every ribbon the Face tab made. Open in Ribbon tab: the Ribbon tab "
               "with that ribbon selected and its settings loaded (rebuild it, change its controls, Switch to "
               "constraints, mirror sides...). Select controls: all its controls.")
    cmds.textScrollList(N("Ribbons"), height=80, allowMultiSelection=False)
    ui.row(3, 113)
    cmds.button(label="Refresh", command=_w(refresh_ribbons))
    cmds.button(label="Open in Ribbon tab", command=_w(_guard(open_in_ribbon)))
    cmds.button(label="Select controls", command=_w(_guard(select_ribbon_controls)))
    cmds.setParent("..")
    cmds.button(label="Redo this part (Style / brow count from above)", height=26, command=_w(_guard(redo_part)),
                annotation="Make the picked part again from the edges it was made on - e.g. Cartoony -> Realistic, "
                           "or more brow controls. Control shapes and skin weights are kept. One undo.")
    ui.end_section()
    refresh_ribbons()

    ui.section("Group controls (mouth)", step=8, help_text="Controls that move a set of controls each, by a "
               "weight: Mouth_main (the whole mouth), Upper / Lower_Lip (the lip, most in the middle), L / R_Mouth_"
               "Corner (the corner and the lip next to it). The face ribbons you add (cheeks...) follow the corners "
               "and the mouth a little, so the whole area shapes together. They add on top of everything there "
               "(the jaw follow, the controls' own values). Shows each one's controls and weights first; nothing "
               "moves; one undo. Set weight: select the group control, then the controls (0 takes them off).")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(95, 160, 60))
    cmds.text(label="Mouth ribbon", align="right")
    cmds.textField(N("mouth_ribbon"), text=s["mouth_ribbon"], changeCommand=_w(_save_groups))
    cmds.button(label="< sel", command=_w(_guard(lambda *_: _pick_ribbon("mouth_ribbon", add=False))),
                annotation="Select one of the mouth's controls.")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(95, 160, 60))
    cmds.text(label="Face ribbons", align="right")
    cmds.textField(N("face_ribbons"), text=s["face_ribbons"], changeCommand=_w(_save_groups))
    cmds.button(label="+ sel", command=_w(_guard(lambda *_: _pick_ribbon("face_ribbons", add=True))),
                annotation="Select a control of a face ribbon (cheeks, facial strip): its ribbon is added.")
    cmds.setParent("..")
    ui.main_button("Make mouth group controls", _w(_guard(make_mouth_groups)), "Shows the plan first.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(60, 60, 150))
    cmds.text(label="Weight", align="right")
    cmds.floatField(N("group_weight"), value=float(s["group_weight"]), minValue=0, maxValue=2, precision=2, step=0.05,
                    changeCommand=_w(_save_groups))
    cmds.button(label="Set weight (group, then controls)", command=_w(_guard(set_group_weight)))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="New group control (selected)", command=_w(_guard(new_group_ctrl)),
                annotation="A new control in front of the selected controls, moving them all (weight above).")
    cmds.button(label="Remove group control", command=_w(_guard(remove_group_ctrl)),
                annotation="The selected group control and everything it made. The controls stay where they are.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Head squash", step=9, help_text="Squash and stretch for the head: a lattice round the skull, after "
               "the skin, with Maya's squash and bend on it, driven by Head_squash_ctrl above the head - up / down "
               "squash - stretch (the volume kept), sideways / front-back the top bends; sliders squash, bulge, bend. "
               "The meshes you pick squash (the eyes too - leave them out to keep them round) - only their vertices "
               "round the head: the rest of the body can't move. The face controls stay as they are (they don't "
               "follow the squashed face yet). Past the lattice it fades out (Fade: 0 = a third of the "
               "head's height) - the ears and neck ride along. On / off: Visibility_ctrl.Head_Squash (off while "
               "blocking - faster). Select the head control, then Make.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(60, 190, 60))
    cmds.text(label="Meshes", align="right")
    cmds.textField(N("squash_meshes"), text=s["squash_meshes"], changeCommand=_w(_save_squash))
    cmds.button(label="< sel", command=_w(_guard(pick_squash_meshes)))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(60, 60, 150))
    cmds.text(label="Fade", align="right")
    cmds.floatField(N("squash_fade"), value=float(s["squash_fade"]), minValue=0, maxValue=1000000.0, step=0.01, precision=2,
                    changeCommand=_w(_save_squash))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Make head squash", backgroundColor=ui.MAIN_BG, command=_w(_guard(make_squash)))
    cmds.button(label="Remove head squash", command=_w(_guard(remove_squash)))
    cmds.setParent("..")
    ui.row(1, 343)
    cmds.button(label="Clean mesh copies (selected)", command=_w(_guard(clean_copies)),
                annotation="Hidden copies that only pass the mesh along (Make before 5.6.17 left one each time) "
                           "- they slow the rig. Lists them first.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Expressions and selection sets", step=10, help_text="Pose the face with its controls and the group "
               "controls, type a name, Save pose: the pose goes into sliders on the control below (Smile_L / "
               "Smile_R when split - each control left, right or shared in the middle by where it is) and the face "
               "goes back to rest. Sliders add together. Saving a name again replaces it. Zero the face: every "
               "face and group control to 0. Selection sets: mouth_all / upper / lower / corners / groups, face_all "
               "- in the rig (gus_anim_sets), Gus Animtool lists them.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(70, 180, 60))
    cmds.text(label="Sliders on", align="right")
    cmds.textField(N("pose_holder"), text=s["pose_holder"], changeCommand=_w(lambda *_: (_save_poses(),
                                                                                         refresh_poses())))
    cmds.button(label="< sel", command=_w(_guard(pick_pose_holder)))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(70, 140, 100))
    cmds.text(label="Pose", align="right")
    cmds.textField(N("pose_name"), text=s["pose_name"], changeCommand=_w(_save_poses),
                   annotation="Smile, Frown, Wide, Pucker... (one word)")
    cmds.checkBox(N("pose_split"), label="Split L / R", value=bool(s["pose_split"]), changeCommand=_w(_save_poses))
    cmds.setParent("..")
    cmds.checkBox(N("pose_keep_on"), label="Include expressions that are on", value=bool(s.get("pose_keep_on", True)),
                  changeCommand=_w(_save_poses),
                  annotation="On: the pose is the face as you see it (Angry up on the board + your changes = a new "
                             "expression of its own). Off: only what you moved - to use on top of the others.")
    ui.row(2, 170)
    cmds.button(label="Save pose", backgroundColor=ui.MAIN_BG, command=_w(_guard(save_face_pose)))
    cmds.button(label="Zero the face", command=_w(_guard(zero_face)))
    cmds.setParent("..")
    cmds.textScrollList(N("Poses"), height=70, allowMultiSelection=False)
    ui.row(2, 170)
    cmds.button(label="Refresh", command=_w(_guard(clean_poses)),
                annotation="Read the sliders again - a pose whose sliders are gone leaves the list")
    cmds.button(label="Edit picked pose", command=_w(_guard(edit_face_pose)),
                annotation="The picked pose back on its controls (the face looks the same, its sliders at 0): "
                           "change it, then Save pose with the same name - it replaces it")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Remove picked pose", command=_w(_guard(remove_face_pose)))
    cmds.button(label="Make selection sets", command=_w(_guard(make_face_sets)))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Make sliders board", command=_w(_guard(make_board)),
                annotation="A board next to the head: per expression an amount knob (drag up) and, split ones, a "
                           "shift knob (sideways: left only / both / right only). Select the head control first. "
                           "Made fresh each time; saving a pose updates it.")
    cmds.button(label="Remove board", command=_w(_guard(remove_board)))
    cmds.setParent("..")
    ui.end_section()
    refresh_poses()
