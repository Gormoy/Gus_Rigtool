"""
Ribbon: builds ribbon rigs on NURBS surfaces (the Ribbon Rig Builder, in Gus_Rigtool).

    import gus_rigtool.main as gr; gr.show_tool("ribbon")

  1. Surface   : make or pick the ribbon; the light shows which way it runs and if it twists
  2. Follicles : how many, where (CV rows / even U / even by length), across the width
  3. Controls  : which follicles get one, Shape Library shape, colour
  4. Build     : Create / Rebuild / Delete, and Mirror build to the other side

The bar at the top shows the ribbon the buttons act on: the selected one (or a node of its
build), else the last one built.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, ribbon, ui, utils

TOOL = "Ribbon"
SETTINGS_KEY = "ribbon"
PREVIEW_GRP = "gusrigRibbonPreview_grp"

DEFAULTS = dict(ribbon.DEFAULTS)
DEFAULTS.update({"preview_locators": False})

_P, N, _w, _guard = ui.tool_helpers("p_ribbon_", TOOL, dialog=False)
_last_preview = {"key": None}


# ===========================================================================
# reading / writing the options
# ===========================================================================

def _q(kind, name, **k):
    return getattr(cmds, kind)(N(name), query=True, **k)


def _ui():
    shapes = ribbon.SHAPES()
    connect = list(ribbon.CONNECT.values())
    return {
        "prefix": _q("textFieldGrp", "Prefix", text=True),
        "num_follicles": _q("intField", "Count", value=True),
        "distribution": ["auto", "length"][_q("optionMenu", "Dist", select=True) - 1],
        "auto_count": list(ribbon.AUTO_COUNTS)[_q("optionMenu", "AutoCount", select=True) - 1],
        "v_pos": _q("floatSliderGrp", "V", value=True),
        "make_joints": _q("checkBox", "Joints", value=True),
        "fol_jnt_radius": _q("floatField", "FolRad", value=True),
        "make_ctrls": _q("checkBox", "Ctrls", value=True),
        "ctrl_mode": "every" if _q("radioButtonGrp", "Mode", select=True) == 1 else "list",
        "ctrl_every": _q("intField", "Every", value=True),
        "ctrl_list": _q("textField", "List", text=True),
        "include_ends": _q("checkBox", "Ends", value=True),
        "ctrl_shape": shapes[_q("optionMenu", "Shape", select=True) - 1],
        "joint_connect": connect[_q("optionMenu", "Connect", select=True) - 1],
        "ctrl_radius": _q("floatField", "Radius", value=True),
        "ctrl_distance": _q("floatField", "Dist2", value=True),
        "dir_axis": "XYZ"[_q("optionMenu", "DirAxis", select=True) - 1],
        "face_axis": "XYZ"[_q("optionMenu", "FaceAxis", select=True) - 1],
        "color": list(_q("colorSliderGrp", "Color", rgbValue=True)),
        "use_side_colors": _q("checkBox", "SideCol", value=True),
        "pivot_on_shape": _q("checkBox", "PivShape", value=True),
        "pivot_scale": _q("checkBox", "PivScale", value=True),
        "lock_hide": _q("checkBox", "Lock", value=True),
        "bind_jnt_radius": _q("floatField", "BindRad", value=True),
        "make_skin": _q("checkBox", "Skin", value=True),
        "make_groups": _q("checkBox", "Groups", value=True),
        "ribbon_group": _q("checkBox", "RibbonGrp", value=True),
        "group_parent": _q("textField", "GroupParent", text=True).strip(),
        "mirror_axis": "XYZ"[_q("optionMenu", "MirAxis", select=True) - 1],
        "mirror_prefix": _q("textField", "MirPrefix", text=True),
        "mirror_color": list(_q("colorSliderGrp", "MirColor", rgbValue=True)),
        "mirror_style": list(ribbon.MIRROR_STYLES)[_q("optionMenu", "MirStyle", select=True) - 1],
        "rebuild_mirror": _q("checkBox", "RebuildMirror", value=True),
        "preview_locators": _q("checkBox", "PreviewLoc", value=True),
    }


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _build_settings():
    s = _ui()
    s.pop("preview_locators", None)
    return s


# ===========================================================================
# lights and preview
# ===========================================================================

def _selected_surface():
    for n in cmds.ls(selection=True, long=True) or []:
        if "." in n:
            continue
        if cmds.nodeType(n) == "nurbsSurface":
            return cmds.listRelatives(n, parent=True, fullPath=True)[0]
        if cmds.listRelatives(n, shapes=True, type="nurbsSurface"):
            return n
    return None


def _target_surface():
    """The ribbon the preview is about: the selected surface, else the current ribbon."""
    surf = _selected_surface()
    if surf:
        return surf
    info = ribbon.current_ribbon()
    return info["surface"] if info and cmds.objExists(info["surface"]) else None


def _light():
    info = ribbon.current_ribbon()
    if not info:
        return "warn", "No ribbon: select a NURBS ribbon (or make one in step 1)."
    name = naming.short_name(info["surface"])
    if not info["built"]:
        return "ok", "Current ribbon: %s  -  not built yet." % name
    text = "Current ribbon: %s  -  built (%d follicles, %d controls)" % (name, info["follicles"], info["controls"])
    if info["mirrored_to"]:
        text += ", mirrored to %s" % naming.short_name(info["mirrored_to"])
    if info["mirror_of"]:
        text += ", mirror of %s" % naming.short_name(info["mirror_of"])
    return "ok", text


def _set_step(name, level, text):
    ctrl = N(name)
    if cmds.text(ctrl, exists=True):
        cmds.text(ctrl, edit=True, label="  " + text, backgroundColor=ui.LIGHT_BG.get(level, ui.LIGHT_BG["idle"]))


def refresh(*_):
    """Step lights, summary and preview locators (skipped when nothing changed)."""
    if not cmds.text(N("Summary"), exists=True):
        return
    try:
        s = _ui()
    except RuntimeError:
        return
    surf = _target_surface()
    key = (surf, repr(sorted(s.items())), _P["p"])
    if key == _last_preview["key"]:
        return
    _last_preview["key"] = key

    # 1. surface
    if not surf:
        _set_step("L1", "warn", "Select a NURBS ribbon, or make one below.")
        _set_step("L2", "idle", "")
        _set_step("L3", "idle", "")
        cmds.text(N("Summary"), edit=True, label="Select a ribbon to see what will be built.")
        _clear_locators()
        return
    try:
        level, lines = ribbon.surface_check(surf)
        _set_step("L1", level, "%s: %s" % (naming.short_name(surf), " | ".join(lines)))
    except Exception as e:
        _set_step("L1", "warn", "%s: %s" % (naming.short_name(surf), e))
        return

    # 2. follicles + 3. controls
    try:
        n, pts = ribbon.preview_points(surf, s)
    except Exception as e:
        _set_step("L2", "warn", str(e))
        return
    dist = ribbon.DISTRIBUTIONS[s["distribution"]]
    _set_step("L2", "ok", "%d follicles, %s, %d%% across the width." % (n, dist, round(s["v_pos"] * 100)))
    ctrl_text = "no controls"
    level = "ok"
    if s["make_ctrls"]:
        try:
            looped = ribbon.is_looped(surf)
            idx = ribbon._control_indices(n, s["ctrl_mode"], s["ctrl_every"], s["ctrl_list"],
                                          s["include_ends"] and not looped)
            if idx:
                ctrl_text = "controls on joints %s (%d)%s" % (", ".join(str(i + 1) for i in idx), len(idx),
                                                              ", loop: no ends" if looped else "")
            else:
                ctrl_text, level = "no joints picked for controls", "warn"
        except ValueError as e:
            ctrl_text, level = str(e), "warn"
    _set_step("L3", level, ctrl_text + ("  -  shape: %s" % s["ctrl_shape"] if s["make_ctrls"] else ""))

    parts = ["%d follicles" % n, ctrl_text]
    if s["make_ctrls"] and s["make_skin"]:
        parts.append("skin on")
    cmds.text(N("Summary"), edit=True, label="  " + "  |  ".join(parts))
    if s["preview_locators"]:
        _show_locators(pts, s)
    else:
        _clear_locators()


def _clear_locators(*_):
    state = cmds.undoInfo(query=True, stateWithoutFlush=True)
    cmds.undoInfo(stateWithoutFlush=False)
    try:
        if cmds.objExists(PREVIEW_GRP):
            cmds.delete(PREVIEW_GRP)
    finally:
        cmds.undoInfo(stateWithoutFlush=state)


def _show_locators(points, s):
    state = cmds.undoInfo(query=True, stateWithoutFlush=True)
    cmds.undoInfo(stateWithoutFlush=False)
    sel = cmds.ls(selection=True, long=True) or []
    try:
        if cmds.objExists(PREVIEW_GRP):
            cmds.delete(PREVIEW_GRP)
        grp = cmds.createNode("transform", name=PREVIEW_GRP)
        size = max(0.05, float(s["fol_jnt_radius"]))
        for i, p in enumerate(points):
            loc = cmds.spaceLocator(name="gusrigRibbonPreview%d" % (i + 1))[0]
            cmds.setAttr(loc + ".localScale", size, size, size)
            cmds.xform(loc, worldSpace=True, translation=p)
            cmds.parent(loc, grp)
        cmds.setAttr(grp + ".overrideEnabled", 1)
        cmds.setAttr(grp + ".overrideDisplayType", 2)
    finally:
        if sel:
            cmds.select(sel, replace=True)
        else:
            cmds.select(clear=True)
        cmds.undoInfo(stateWithoutFlush=state)


def _on_change(*_):
    _update_enabled()
    _save()
    refresh()
    ui.refresh_light(N("Light"))


def _update_enabled(*_):
    try:
        ctrls = _q("checkBox", "Ctrls", value=True)
        by_list = _q("radioButtonGrp", "Mode", select=True) == 2
        shapes = ribbon.SHAPES()
        joint_only = shapes[_q("optionMenu", "Shape", select=True) - 1] == ribbon.JOINT_ONLY
        cmds.intField(N("Every"), edit=True, enable=ctrls and not by_list)
        cmds.textField(N("List"), edit=True, enable=ctrls and by_list)
        cmds.optionMenu(N("Connect"), edit=True, enable=ctrls and joint_only)
        for name in ("Dist2",):
            cmds.floatField(N(name), edit=True, enable=ctrls and not joint_only)
        cmds.checkBox(N("PivShape"), edit=True, enable=ctrls and not joint_only)
        cmds.checkBox(N("PivScale"), edit=True,
                      enable=ctrls and not joint_only and _q("checkBox", "PivShape", value=True))
        cmds.floatField(N("FolRad"), edit=True, enable=_q("checkBox", "Joints", value=True))
    except RuntimeError:
        pass


# ===========================================================================
# actions
# ===========================================================================

RIBBON_SETUPS = {
    # circle around the ribbon, pivot on the joint
    "body": {"Dist2": 0.0, "FaceAxis": "X", "PivShape": False, "PivScale": False},
    # controls in front, pivot on them
    "face": {"Dist2": 1.5, "DirAxis": "Z", "FaceAxis": "Z", "PivShape": True, "PivScale": False},
    # what the Face kit builds with (ribbon.FACE_KIT): pivot on the joint, side colours
    "facekit": {"FaceAxis": "Z", "PivShape": False, "PivScale": False, "SideCol": True},
}


def _ribbon_preset(kind):
    """Fill the control options for a body or face ribbon (only these options change)."""
    for name, value in RIBBON_SETUPS[kind].items():
        if name in ("DirAxis", "FaceAxis"):
            cmds.optionMenu(N(name), edit=True, select="XYZ".index(value) + 1)
        elif name == "Dist2":
            cmds.floatField(N(name), edit=True, value=value)
        else:
            cmds.checkBox(N(name), edit=True, value=value)
    shapes = ribbon.SHAPES()
    if "circle" in shapes:
        cmds.optionMenu(N("Shape"), edit=True, select=shapes.index("circle") + 1)
    _on_change()
    utils.info(TOOL, "%s setup: %s." % ({"facekit": "Face kit"}.get(kind, kind.title() + " ribbon"), {
        "body": "circle around the ribbon, pivot on the joint", "face": "controls in front, pivot on them",
        "facekit": "the Face kit's settings: pivot on the joint, side colours"}[kind]))


# ---------------------------------------------------------------------------
# builds in the scene (4.2.0): where each came from, load its settings, back to the Face tab
# ---------------------------------------------------------------------------

_rows = {}
FACE_SECTIONS = (("Eyelid", "Eyelids"), ("Mouth", "Mouth"), ("Brow", "Brows"))


def face_section(made_by):
    for word, section in FACE_SECTIONS:
        if word in made_by:
            return section
    return "Facial strips"


def refresh_builds(*_):
    if not cmds.textScrollList(N("Builds"), exists=True):
        return
    rows = ribbon.builds_list()
    _rows[_P["p"]] = rows
    labels = ["%s   (%s, %d controls%s)" % (naming.short_name(k), st.get("made_by") or "Ribbon tab", n,
                                            ", pivot on the shape" if st.get("pivot_on_shape") else "")
              for k, st, n in rows]
    cmds.textScrollList(N("Builds"), edit=True, removeAll=True, append=labels or ["(no ribbon builds)"])


def _picked_build():
    idx = cmds.textScrollList(N("Builds"), query=True, selectIndexedItem=True) or []
    rows = _rows.get(_P["p"], [])
    if not idx or idx[0] - 1 >= len(rows):
        raise RuntimeError("pick a build in the list first.")
    return rows[idx[0] - 1]


def _select_build(*_):
    key, _st, _n = _picked_build()
    if cmds.objExists(key):
        cmds.select(key, replace=True)


def load_settings(key=None, settings=None):
    """The tab's options become the build's (it rebuilds the page)."""
    if settings is None:
        builds = ribbon._find_builds()
        settings = ribbon._build_settings(builds[key]) if key in builds else None
    if not settings:
        raise RuntimeError("this build has no saved settings (made before 1.2) - rebuild it to save them.")
    cur = utils.load_setting(SETTINGS_KEY, {})
    cur.update({k: v for k, v in settings.items() if k in DEFAULTS})
    utils.save_setting(SETTINGS_KEY, cur)
    cmds.evalDeferred(ui.rebuild_open)


def _load_picked(*_):
    key, st, _n = _picked_build()
    if cmds.objExists(key):
        cmds.select(key, replace=True)
    load_settings(key, st)
    utils.info(TOOL, "the options are now %s's." % naming.short_name(key))


def _to_face(*_):
    key, st, _n = _picked_build()
    if not (st.get("made_by") or "").startswith("Face kit"):
        raise RuntimeError("%s wasn't made by the Face tab." % naming.short_name(key))
    if cmds.objExists(key):
        cmds.select(key, replace=True)
    ui.go_to_tool("face", face_section(st["made_by"]))


def _get_parent(*_):
    sel = cmds.ls(selection=True, long=True) or []
    if sel:
        cmds.textField(N("GroupParent"), edit=True, text=naming.short_name(sel[0]))
        _on_change()


def organize_existing(*_):
    parent = cmds.textField(N("GroupParent"), query=True, text=True).strip()
    cmds.undoInfo(openChunk=True)
    try:
        made = ribbon.organize_builds(parent)
    finally:
        cmds.undoInfo(closeChunk=True)
    utils.info(TOOL, "%d build(s) put in their own _ribbon_grp." % len(made) if made else
               "every build is already in its _ribbon_grp.")


def _done(*_):
    _last_preview["key"] = None
    _clear_locators()


def _scale_off_once():
    """4.0.6: 'Scale controls too' starts off once (an old saved 'on' made direct connections by surprise)."""
    if utils.load_setting("ribbonScaleReset406", False):
        return
    saved = utils.load_setting(SETTINGS_KEY, {})
    saved["pivot_scale"] = False
    utils.save_setting(SETTINGS_KEY, saved)
    utils.save_setting("ribbonScaleReset406", True)


def create(*_):
    _save()
    _done()
    ribbon.build_rig(_build_settings())
    _last_preview["key"] = None
    refresh()
    ui.refresh_light(N("Light"))


def rebuild(*_):
    _save()
    st = _build_settings()
    try:
        pv = ribbon.rebuild_preview(st)
    except Exception:
        pv = None
    if pv and (pv["meshes"] or pv["controls_now"] != pv["controls_new"]):
        msg = "%s: %d control(s) now -> %d after the rebuild (%d follicles)." % (
            naming.short_name(pv["ribbon"]), pv["controls_now"], pv["controls_new"], pv["follicles_new"])
        if pv["meshes"]:
            msg += ("\n\nSkinned to its joints: %s. Their weights are kept: a joint that's still there keeps its "
                    "own, a removed joint's go to the nearest new one." % ", ".join(pv["meshes"][:6]))
        if cmds.confirmDialog(title="Rebuild", message=msg, button=["Rebuild", "Cancel"], defaultButton="Rebuild",
                              cancelButton="Cancel", dismissString="Cancel") != "Rebuild":
            return
    _done()
    ribbon.rebuild(st)
    refresh()
    ui.refresh_light(N("Light"))


def delete(*_):
    try:
        pv = ribbon.rebuild_preview(_build_settings())
    except Exception:
        pv = None
    if pv and pv["meshes"] and cmds.confirmDialog(
            title="Delete build", button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
            dismissString="Cancel",
            message="%s's joints skin %s. Deleting the build deletes them: those weights go to the meshes' other "
                    "joints. (Rebuild keeps them instead.) Delete?" % (naming.short_name(pv["ribbon"]),
                                                                       ", ".join(pv["meshes"][:6]))) != "Delete":
        return
    ribbon.delete_build()
    _last_preview["key"] = None
    refresh()
    ui.refresh_light(N("Light"))


def mirror(*_):
    s = _ui()
    _save()
    ribbon.mirror_build(axis=s["mirror_axis"], prefix=s["mirror_prefix"], color=s["mirror_color"],
                       style=s["mirror_style"])
    ui.refresh_light(N("Light"))


def mirror_sides(*_):
    s = _ui()
    ribbon.mirror_sides(axis=s["mirror_axis"])
    ui.refresh_light(N("Light"))


def toggle_symmetric(*_):
    """5.6.27: mark / unmark the picked ribbon as not symmetric (a collar whose base isn't)."""
    builds = ribbon._find_builds()
    key = ribbon._pick_build(builds)
    if key is None:
        return
    ribbon.set_asymmetric(key, not ribbon.is_asymmetric(key))
    ui.refresh_light(N("Light"))


def make_symmetric(*_):
    """5.0.7: show how far the other side is from the exact mirror, then move it there (one undo)."""
    s = _ui()
    r = ribbon.symmetry_report(axis=s["mirror_axis"])
    if not r["controls"] and not r["follicles"]:
        utils.info(TOOL, "%s is already exactly symmetric." % naming.short_name(r["key"]))
        return
    rows = ["%s -> %s  off %.4f" % (naming.short_name(m), naming.short_name(f), d)
            for kind in ("controls", "follicles") for m, f, d in r[kind]]
    side = "the -X side" if r["sign"] < 0 else "the +X side"
    if cmds.confirmDialog(
            title="Gus_Rigtool - make symmetric", button=["Make symmetric", "Cancel"],
            defaultButton="Make symmetric", cancelButton="Cancel", dismissString="Cancel",
            message="Master: %s (named L_ or +X). These move onto the exact mirror of their twin:\n\n%s%s\n\n"
                    "The joints that follow them keep the mesh where it is (their skins take the new place "
                    "as rest). One undo." % (side, "\n".join(rows[:25]),
                                             "\n..." if len(rows) > 25 else "")) != "Make symmetric":
        return
    lines = ribbon.make_symmetric(report=r)
    ui.report_window("Gus_Rigtool - make symmetric", "\n".join(lines))
    ui.refresh_light(N("Light"))


def to_constraints(*_):
    ribbon.to_constraints()
    ui.refresh_light(N("Light"))


def to_copying(*_):
    ribbon.to_copying(scale=bool(cmds.checkBox(N("PivScale"), query=True, value=True)))
    ui.refresh_light(N("Light"))


def replace_surface(*_):
    """Select the new NURBS surface, then the built ribbon (or one of its controls)."""
    sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
    if len(sel) < 2:
        raise RuntimeError("select the NEW surface first, then the built ribbon (or one of its controls).")
    new = sel[0]
    if not cmds.listRelatives(new, shapes=True, type="nurbsSurface"):
        raise RuntimeError("%s isn't a NURBS surface: select the new surface first." % naming.short_name(new))
    cmds.select(sel[1:], replace=True)
    old = ribbon._selected_surface()
    if not old:
        raise RuntimeError("the second selection isn't part of a ribbon build.")
    ribbon.replace_surface(old, new)
    refresh_builds()


def _surface_action(fn):
    @_guard
    def run(*_):
        fn()
        _last_preview["key"] = None
        refresh()
        ui.refresh_light(N("Light"))
    return run


def _make_plane():
    ribbon.make_plane(name=_q("textFieldGrp", "PlName", text=True) or "ribbon",
                      length=_q("floatFieldGrp", "PlLen", value1=True),
                      width=_q("floatFieldGrp", "PlWid", value1=True),
                      spans_u=_q("intFieldGrp", "PlSu", value1=True),
                      spans_v=_q("intFieldGrp", "PlSv", value1=True),
                      degree=ribbon.DEGREES[_q("optionMenuGrp", "PlDeg", value=True)],
                      normal=_q("optionMenuGrp", "PlNormal", value=True))


def _edge_to_curve():
    ribbon.edge_to_curve(degree=ribbon.DEGREES[_q("optionMenuGrp", "EcDeg", value=True)],
                         form=_q("optionMenuGrp", "EcForm", value=True),
                         rebuild_spans=_q("intFieldGrp", "EcSpans", value1=True),
                         start=_q("optionMenuGrp", "EcStart", value=True),
                         reverse=_q("checkBox", "EcRev", value=True),
                         delete_history=_q("checkBox", "EcHist", value=True),
                         name=_q("textFieldGrp", "EcName", text=True) or "edgeCurve")


def _check():
    ribbon.check_curves(fix=False)


def _fix():
    curves_, _lines = ribbon.check_curves(fix=True)
    cmds.select(curves_)


def _loft():
    ribbon.loft_curves(uniform=_q("checkBox", "LfUniform", value=True),
                       auto_reverse=_q("checkBox", "LfAuto", value=True),
                       close=_q("checkBox", "LfClose", value=True),
                       degree=ribbon.DEGREES[_q("optionMenuGrp", "LfDeg", value=True)],
                       section_spans=max(1, _q("intFieldGrp", "LfSpans", value1=True)),
                       partial_range=_q("optionMenuGrp", "LfRange", value=True) == "Partial",
                       along_u=_q("checkBox", "LfAlongU", value=True),
                       flip=_q("checkBox", "LfFlip", value=True),
                       auto_fix=_q("checkBox", "LfFix", value=True),
                       name=_q("textFieldGrp", "LfName", text=True) or "ribbon")


# ===========================================================================
# window
# ===========================================================================

def _menu_grp(name, label, items, default):
    cmds.optionMenuGrp(N(name), label=label, columnWidth2=(150, 150))
    for item in items:
        cmds.menuItem(label=item)
    cmds.optionMenuGrp(N(name), edit=True, value=default)


def _menu(name, items, select, annotation=""):
    cmds.optionMenu(N(name), changeCommand=_w(_on_change), annotation=annotation)
    for item in items:
        cmds.menuItem(label=item)
    cmds.optionMenu(N(name), edit=True, select=select)


def _labeled(label, width=150):
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(width, 180), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label=label)


def _step_light(name):
    cmds.text(N(name), label="", align="left", height=20, enableBackground=True,
              backgroundColor=ui.LIGHT_BG["idle"])


def build(prefix="p_ribbon_"):
    _P["p"] = prefix
    _scale_off_once()
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()
    shapes = ribbon.SHAPES()
    shape = ribbon.OLD_SHAPES.get(s["ctrl_shape"], s["ctrl_shape"])

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)

    # ------------------------------------------------------------ 1 surface
    ui.section("Surface", step=1, help_text="Select the NURBS ribbon. The light shows which way it runs (U "
               "must run along the length), whether it twists, and where its front faces. No ribbon yet? "
               "Make a plane, or turn edges into curves and loft them below.")
    _step_light("L1")
    cmds.frameLayout(label="Make a plane", collapsable=True, collapse=True, marginWidth=6, marginHeight=4)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
    cmds.textFieldGrp(N("PlName"), label="Name", text="ribbon", columnWidth2=(150, 150))
    cmds.floatFieldGrp(N("PlLen"), label="Length (along U)", value1=20.0, columnWidth2=(150, 80))
    cmds.floatFieldGrp(N("PlWid"), label="Width", value1=4.0, columnWidth2=(150, 80))
    cmds.intFieldGrp(N("PlSu"), label="Spans along length", value1=8, columnWidth2=(150, 80))
    cmds.intFieldGrp(N("PlSv"), label="Spans across", value1=1, columnWidth2=(150, 80))
    _menu_grp("PlDeg", "Degree", list(ribbon.DEGREES), "Cubic")
    _menu_grp("PlNormal", "Plane normal axis", ["X", "Y", "Z"], "Z")
    cmds.button(label="Make plane", height=26, command=_w(_surface_action(_make_plane)))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="Edge to curve", collapsable=True, collapse=True, marginWidth=6, marginHeight=4)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
    ui.note("Select polygon edges (a loop or a connected chain), then press the button.")
    cmds.textFieldGrp(N("EcName"), label="Name", text="edgeCurve", columnWidth2=(150, 150))
    _menu_grp("EcDeg", "Degree", list(ribbon.DEGREES), "Cubic")
    _menu_grp("EcForm", "Form", list(ribbon.EDGE_FORMS), "Best guess")
    cmds.intFieldGrp(N("EcSpans"), label="Rebuild spans (0 = keep)", value1=0, columnWidth2=(150, 80))
    _menu_grp("EcStart", "Start point", ribbon.START_RULES, "Maya default")
    cmds.checkBox(N("EcRev"), label="Reverse direction", value=False)
    cmds.checkBox(N("EcHist"), label="Delete history", value=True)
    cmds.button(label="Edge to curve", height=26, command=_w(_surface_action(_edge_to_curve)))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="Check / fix curves, loft", collapsable=True, collapse=True, marginWidth=6,
                     marginHeight=4)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
    ui.note("Select the curves in loft order. Check reports problems; Fix changes the selected curves.")
    ui.row(2, 170)
    cmds.button(label="Check curves", command=_w(_surface_action(_check)))
    cmds.button(label="Fix curves", command=_w(_surface_action(_fix)))
    cmds.setParent("..")
    report = cmds.scrollField(N("Report"), editable=False, wordWrap=True, height=80, text="")
    ribbon.REPORT["ctrl"] = report
    cmds.textFieldGrp(N("LfName"), label="Name", text="ribbon", columnWidth2=(150, 150))
    cmds.checkBox(N("LfUniform"), label="Uniform", value=True)
    cmds.checkBox(N("LfAuto"), label="Auto reverse", value=True)
    cmds.checkBox(N("LfClose"), label="Close", value=False)
    _menu_grp("LfDeg", "Surface degree", list(ribbon.DEGREES), "Linear")
    cmds.intFieldGrp(N("LfSpans"), label="Section spans", value1=1, columnWidth2=(150, 80))
    _menu_grp("LfRange", "Curve range", ["Complete", "Partial"], "Complete")
    cmds.checkBox(N("LfAlongU"), label="Make the ribbon run along U (needed to build)", value=True)
    cmds.checkBox(N("LfFlip"), label="Flip normals", value=False)
    cmds.checkBox(N("LfFix"), label="Check and fix the curves first (on copies, originals untouched)", value=True)
    cmds.button(label="Loft selected curves", height=28, command=_w(_surface_action(_loft)))
    cmds.setParent("..")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Swap U/V", command=_w(_surface_action(ribbon.swap_uv)),
                annotation="When the ribbon runs along V.")
    cmds.button(label="Flip normals", command=_w(_surface_action(ribbon.flip_normals)),
                annotation="Turns the front side over, without changing the order along the length.")
    cmds.setParent("..")
    ui.end_section()

    # ------------------------------------------------------------ 2 follicles
    ui.section("Follicles", step=2, help_text="Follicles stick to the ribbon; each gets a joint. Count 0 = "
               "automatic: one per span (default) or one per CV row (original). Even by length spaces them by real distance, so they "
               "line up with chains from the Joints tab. Position across width: 0.5 = the middle.")
    _step_light("L2")
    cmds.textFieldGrp(N("Prefix"), label="Name prefix", text=s["prefix"], columnWidth2=(150, 180),
                      changeCommand=_w(_on_change), annotation="Empty = the ribbon's name.")
    _labeled("Follicles (0 = auto)")
    cmds.intField(N("Count"), value=int(s["num_follicles"]), minValue=0, maxValue=1000000, step=1, changeCommand=_w(_on_change))
    cmds.setParent("..")
    _labeled("Auto count")
    autos = list(ribbon.AUTO_COUNTS)
    _menu("AutoCount", list(ribbon.AUTO_COUNTS.values()),
          autos.index(s["auto_count"]) + 1 if s["auto_count"] in autos else 1,
          "Used when Follicles is 0. One per span: on every span line, evenly spaced (8 spans = 9 "
          "joints). One per CV row: the original rule; a cubic ribbon then gets an extra joint near "
          "each end.")
    cmds.setParent("..")
    _labeled("Distribution")
    _menu("Dist", list(ribbon.DISTRIBUTIONS.values()), 2 if s["distribution"] == "length" else 1)
    cmds.setParent("..")
    cmds.floatSliderGrp(N("V"), label="Position across width", field=True, minValue=0.0, maxValue=1.0, step=0.05,
                        value=float(s["v_pos"]), columnWidth3=(150, 50, 120), changeCommand=_w(_on_change))
    cmds.checkBox(N("Joints"), label="Joints on the follicles", value=s["make_joints"],
                  changeCommand=_w(_on_change))
    ui.more_options()
    _labeled("Follicle joint radius")
    cmds.floatField(N("FolRad"), value=float(s["fol_jnt_radius"]), precision=2, changeCommand=_w(_on_change))
    cmds.setParent("..")
    ui.end_section()
    ui.end_section()

    # ------------------------------------------------------------ 3 controls
    ui.section("Controls", step=3, help_text="Pick which follicles get a control: every N joints, or a "
               "list (counting from 1), plus the first / last. Shapes come from the Shape Library; 'None "
               "(joint only)' makes the joint itself the control. Each control drives a bind joint that "
               "skins the ribbon.")
    _step_light("L3")
    cmds.checkBox(N("Ctrls"), label="Controls (with bind joints)", value=s["make_ctrls"],
                  changeCommand=_w(_on_change))
    cmds.radioButtonGrp(N("Mode"), label="Controls on", numberOfRadioButtons=2,
                        labelArray2=["Every N joints", "Custom list"], select=1 if s["ctrl_mode"] == "every" else 2,
                        columnWidth3=(150, 110, 100), changeCommand=_w(_on_change))
    _labeled("Every N joints")
    cmds.intField(N("Every"), value=int(s["ctrl_every"]), minValue=1, maxValue=1000000, step=1, changeCommand=_w(_on_change),
                  annotation="1 = every joint, 2 = joint 1, 3, 5...")
    cmds.setParent("..")
    _labeled("Custom list")
    cmds.textField(N("List"), text=s["ctrl_list"], changeCommand=_w(_on_change),
                   annotation="Joint numbers, counting from 1. Example: 1, 4, 7")
    cmds.setParent("..")
    cmds.checkBox(N("Ends"), label="Always include the first and last joint", value=s["include_ends"],
                  changeCommand=_w(_on_change),
                  annotation="Ignored on a ribbon that goes all the way round (a loop has no ends).")
    _labeled("Control shape")
    _menu("Shape", shapes, shapes.index(shape) + 1 if shape in shapes else 1)
    cmds.setParent("..")
    _labeled("Joint control connects by")
    _menu("Connect", list(ribbon.CONNECT), 1 if s["joint_connect"] == "skin" else 2)
    cmds.setParent("..")
    _labeled("Control size")
    cmds.floatField(N("Radius"), value=float(s["ctrl_radius"]), precision=2, changeCommand=_w(_on_change))
    cmds.setParent("..")
    _labeled("Distance in front")
    cmds.floatField(N("Dist2"), value=float(s["ctrl_distance"]), precision=2, changeCommand=_w(_on_change),
                    annotation="How far in front of the joint the shape sits. Negative = the other side.")
    cmds.setParent("..")
    cmds.checkBox(N("PivShape"), label="Pivot on the control shape (the joint follows by constraints)",
                  value=s["pivot_on_shape"], changeCommand=_w(_on_change),
                  annotation="Off: the pivot is on the joint and the shape sits in front, so the handle "
                             "appears on the joint. On: the handle appears on the control; the bind joint "
                             "stays on the ribbon and follows the control by point + orient constraints: "
                             "it moves with it and turns around itself. The "
                             "control then spins in place instead of swinging around the joint. Good for "
                             "face ribbons.")
    cmds.checkBox(N("PivScale"), label="   Scale controls too (the joint copies the control directly)",
                  value=s["pivot_scale"], changeCommand=_w(_on_change),
                  annotation="On: the bind joint copies translate, rotate and scale by direct connections "
                             "(own group in _bind_grp), so scaling the control scales the joint.")
    ui.row(3, 113)
    cmds.button(label="Body ribbon setup", command=_w(lambda *_: _ribbon_preset("body")),
                annotation="Circle around the ribbon, on the joint (pivot on the joint). For arms, legs, "
                           "spines.")
    cmds.button(label="Face kit setup", command=_w(lambda *_: _ribbon_preset("facekit")),
                annotation="The settings the Face tab builds its ribbons with.")
    cmds.button(label="Face ribbon setup", command=_w(lambda *_: _ribbon_preset("face")),
                annotation="Controls in front of the ribbon with the pivot on them. For lips, brows, "
                           "cheeks.")
    cmds.setParent("..")
    c = s["color"]
    cmds.colorSliderGrp(N("Color"), label="Control colour", rgb=(c[0], c[1], c[2]), columnWidth3=(150, 50, 120),
                        changeCommand=_w(_on_change))
    cmds.checkBox(N("SideCol"), label="Use side colours instead (L / R / centre)", value=s["use_side_colors"],
                  changeCommand=_w(_on_change))
    ui.more_options()
    _labeled("Move direction")
    _menu("DirAxis", ["X", "Y", "Z"], "XYZ".index(s["dir_axis"]) + 1)
    cmds.setParent("..")
    _labeled("Shape facing")
    _menu("FaceAxis", ["X", "Y", "Z"], "XYZ".index(s["face_axis"]) + 1)
    cmds.setParent("..")
    _labeled("Bind joint radius")
    cmds.floatField(N("BindRad"), value=float(s["bind_jnt_radius"]), precision=2, changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.checkBox(N("Lock"), label="Lock and hide scale and visibility", value=s["lock_hide"],
                  changeCommand=_w(_on_change))
    cmds.checkBox(N("Skin"), label="Skin the ribbon to the bind joints", value=s["make_skin"],
                  changeCommand=_w(_on_change))
    cmds.checkBox(N("Groups"), label="Put everything in groups", value=s["make_groups"],
                  changeCommand=_w(_on_change))
    cmds.checkBox(N("RibbonGrp"), label="One <prefix>_ribbon_grp for the whole build (ribbon included)",
                  value=s.get("ribbon_group", True), changeCommand=_w(_on_change),
                  annotation="The ribbon, follicles, controls and bind groups in one group that doesn't "
                             "inherit transforms (safe under anything).")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(95, 160, 40),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Put it under")
    cmds.textField(N("GroupParent"), text=s.get("group_parent", ""), changeCommand=_w(_on_change),
                   placeholderText="e.g. controls_grp (empty: the world)")
    cmds.button(label="Get", command=_w(_get_parent), annotation="Take the selected group.")
    cmds.setParent("..")
    ui.end_section()
    ui.end_section()

    # ------------------------------------------------------------ 4 build
    ui.section("Build and mirror", step=4, help_text="Create builds on the selected ribbon. Rebuild deletes "
               "the current ribbon's build and makes it again with these settings (one undo). Delete keeps "
               "the ribbon. Mirror build copies the ribbon to the other side and builds a separate rig whose "
               "controls mirror the first side's: select both twins and type the same value in the "
               "Channel Box, they move in mirrored directions (dragging both with the Move tool set to "
               "World moves them the same way in the world, in any Maya rig). Rebuild on a mirrored ribbon "
               "builds it again from its first side, so it stays a mirror.")
    cmds.frameLayout(label="Preview", collapsable=False, marginWidth=6, marginHeight=4)
    cmds.text(N("Summary"), label="", align="left")
    cmds.checkBox(N("PreviewLoc"), label="Show preview locators at the follicles", value=s["preview_locators"],
                  changeCommand=_w(_on_change),
                  annotation="Temporary markers, not in the undo queue. Removed on Create or close.")
    cmds.setParent("..")
    ui.main_button("Create", _w(_guard(create)), "Build on the selected ribbon. One undo.")
    ui.row(2, 170)
    cmds.button(label="Rebuild", height=26, command=_w(_guard(rebuild)),
                annotation="Delete the current ribbon's build and build again with these settings (e.g. more or "
                           "fewer controls). Meshes skinned to its joints keep their weights: a joint that's still "
                           "there keeps them, a removed joint's go to the nearest new one. A mirrored ribbon is "
                           "built again from its first side, so it stays a mirror.")
    cmds.button(label="Delete build", height=26, command=_w(_guard(delete)),
                annotation="Deletes the current ribbon's build. The ribbon is kept.")
    cmds.setParent("..")
    cmds.button(label="Organize existing builds (one _ribbon_grp each)", height=24,
                command=_w(_guard(organize_existing)),
                annotation="Builds made before (or without the option) get their own _ribbon_grp, under "
                           "'Put it under' if set. Nothing moves in the viewport.")
    cmds.checkBox(N("RebuildMirror"), label="Rebuild also updates its mirror", value=s["rebuild_mirror"],
                  changeCommand=_w(_on_change),
                  annotation="Rebuilding the first side also rebuilds the ribbon mirrored from it, "
                             "so the two stay twins.")
    cmds.separator(height=8, style="in")
    _labeled("Mirror axis")
    _menu("MirAxis", ["X", "Y", "Z"], "XYZ".index(s["mirror_axis"]) + 1)
    cmds.setParent("..")
    _labeled("Mirror prefix")
    cmds.textField(N("MirPrefix"), text=s["mirror_prefix"], changeCommand=_w(_on_change),
                   annotation="Empty = swap the side (L_ <-> R_...), or add it from the position.")
    cmds.setParent("..")
    _labeled("Mirror style")
    styles = list(ribbon.MIRROR_STYLES)
    _menu("MirStyle", list(ribbon.MIRROR_STYLES.values()),
          styles.index(s["mirror_style"]) + 1 if s["mirror_style"] in styles else 1,
          "True mirror: the twin is the reflection (-1 scale on its offset group), like the original "
          "tool: the same translate and rotate values move the pair in mirrored directions. "
          "Behavior: no -1 scale (like Maya's joint Behavior mirror): the same rotate values "
          "mirror, translate values go the opposite way.")
    cmds.setParent("..")
    mc = s["mirror_color"]
    cmds.colorSliderGrp(N("MirColor"), label="Mirror control colour", rgb=(mc[0], mc[1], mc[2]),
                        columnWidth3=(150, 50, 120), changeCommand=_w(_on_change))
    cmds.button(label="Mirror build", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(mirror)),
                annotation="Mirror the current ribbon's build to the other side.")
    cmds.button(label="Make the right side mirror the left (loops: mouth...)", height=26,
                command=_w(_guard(mirror_sides)),
                annotation="One ribbon round both sides (a mouth): the -X side controls get axes that mirror "
                           "their +X twins, so the same values move both sides alike. Nothing moves; weights "
                           "stay. Select the ribbon or one of its controls.")
    cmds.button(label="Not symmetric (mark / unmark: a collar whose base isn't)", height=26,
                command=_w(_guard(toggle_symmetric)),
                annotation="The ribbon's base isn't meant to be symmetric (the hood's collar): no mirror warnings, "
                           "the two buttons below leave it alone and mirror pose gives its controls no twin. "
                           "Nothing in the rig moves. Click again to take the mark off.")
    cmds.button(label="Make symmetric (other side exactly on its twin's mirror)", height=26,
                command=_w(_guard(make_symmetric)),
                annotation="A ribbon round both sides (a mouth): controls and follicles on the other side move onto "
                           "the exact mirror spot of their twin (the L_ side, else +X, is the master), so skin "
                           "mirroring finds every pair. The mesh doesn't move. Shows the list first.")
    cmds.button(label="Replace the surface (new surface, then the ribbon)", height=26,
                command=_w(_guard(replace_surface)),
                annotation="Select the new NURBS surface, then the built ribbon: built again on the new one with "
                           "the same settings, the meshes' weights moved onto the new joints. The old surface is "
                           "hidden as <name>_old.")
    cmds.button(label="Switch to copying (direct connections)", height=26, command=_w(_guard(to_copying)),
                annotation="The reverse of Switch to constraints: each joint copies its control (translate, "
                           "rotate; scale too if 'Scale controls too' is ticked). Nothing moves, weights stay.")
    cmds.button(label="Switch to constraints (joints copying their controls)", height=26,
                command=_w(_guard(to_constraints)),
                annotation="A ribbon with the pivot on the shape whose joints copy their controls (built before "
                           "4.0.5, or with 'Scale controls too'): the joints go back on the ribbon, driven by point "
                           "+ orient constraints (scale back to 1). Nothing moves, weights stay. Controls at rest. "
                           "Select the ribbon or one of its controls.")
    ui.end_section()

    ui.section("Builds in the scene", step=5, help_text="Every ribbon build, and who made it (the Ribbon tab, or the "
               "Face tab: eyelids, mouth, brows, strips). Load its settings: this tab's options become that build's "
               "(e.g. to rebuild it with one change). Open in Face tab: the Face tab part that made it.")
    cmds.textScrollList(N("Builds"), height=90, allowMultiSelection=False, selectCommand=_w(_select_build))
    ui.row(3, 113)
    cmds.button(label="Refresh", command=_w(refresh_builds))
    cmds.button(label="Load its settings", command=_w(_guard(_load_picked)))
    cmds.button(label="Open in Face tab", command=_w(_guard(_to_face)))
    cmds.setParent("..")
    ui.end_section()

    ui.on_selection(N("Summary"), _w(refresh))
    cmds.scriptJob(uiDeleted=[N("Summary"), _clear_locators], runOnce=True)
    refresh_builds()
    _last_preview["key"] = None
    _update_enabled()
    refresh()


def show():
    ui.open_panel("ribbon")


SCHEMA = [
    ("num_follicles", "Follicles (0 = auto)", "float", None),
    ("distribution", "Distribution", "text", None),
    ("auto_count", "Auto count (span / cv)", "text", None),
    ("pivot_on_shape", "Pivot on the control shape", "bool", None),
    ("pivot_scale", "Pivot on shape: joint copies scale", "bool", None),
    ("v_pos", "Position across width", "float", None),
    ("make_joints", "Joints on the follicles", "bool", None),
    ("make_ctrls", "Controls", "bool", None),
    ("ctrl_every", "Every N joints", "float", None),
    ("include_ends", "Always include first / last joint", "bool", None),
    ("ctrl_shape", "Control shape", "text", None),
    ("ctrl_radius", "Control size", "float", None),
    ("ctrl_distance", "Distance in front", "float", None),
    ("use_side_colors", "Use side colours", "bool", None),
    ("lock_hide", "Lock and hide scale / visibility", "bool", None),
    ("make_skin", "Skin the ribbon", "bool", None),
    ("make_groups", "Put everything in groups", "bool", None),
    ("ribbon_group", "One _ribbon_grp per build", "bool", None),
    ("group_parent", "Put the ribbon group under", "text", None),
    ("preview_locators", "Show preview locators", "bool", None),
]
