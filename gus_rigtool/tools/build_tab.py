"""
Build: a full body rig from guides (modular builder).

    import gus_rigtool.main as gr; gr.show_tool("build")

  1. Modules   : Biped template, or add modules one by one; place the guides; mirror them.
  2. Settings  : names, options, orientation and controls of the selected module.
  3. Naming    : the name pattern and suffixes, and a preview of every name.
  4. Build     : Build (what isn't built) / Build picked / guides of picked modules / templates.
  5. Animation : IK / FK matching (no jump when switching); Make animator tools (Gus Animtool).
"""

import maya.cmds as cmds

from gus_rigtool.builder import build as bld
from gus_rigtool.builder import existing, guides, limb, modules, names
from gus_rigtool.core import naming, quick, ui, utils
from gus_rigtool.tools import build_form

TOOL = "Build"
SETTINGS_KEY = "build"
DEFAULTS = dict(bld.DEFAULTS)

_P, N, _w, _guard = ui.tool_helpers("p_build_", TOOL)
_rows = {}          # prefix -> [module group] shown in the list


def _height():
    try:
        return cmds.floatField(N("Height"), query=True, value=True)
    except RuntimeError:
        return bld.settings()["height"]


def _save_main(*_):
    try:
        utils.update_setting(SETTINGS_KEY, "height", _height())
        utils.update_setting(SETTINGS_KEY, "joint_radius", cmds.floatField(N("Radius"), query=True, value=True))
        utils.update_setting(SETTINGS_KEY, "keep_skin", cmds.checkBox(N("KeepSkin"), query=True, value=True))
        utils.update_setting(SETTINGS_KEY, "keep_shapes", cmds.checkBox(N("KeepShapes"), query=True, value=True))
        utils.update_setting(SETTINGS_KEY, "keep_skin_bound", cmds.checkBox(N("KeepBound"), query=True, value=True))
        utils.update_setting(SETTINGS_KEY, "keep_rig_data", cmds.checkBox(N("KeepData"), query=True, value=True))
        utils.update_setting(SETTINGS_KEY, "controls_on_top", cmds.checkBox(N("OnTop"), query=True, value=True))
    except RuntimeError:
        pass


# ===========================================================================
# light
# ===========================================================================

def _light():
    """'What to do now', from the scene."""
    groups = guides.module_groups()
    if not groups:
        return "warn", "Now: press Biped or Quadruped (Start), or add a module."
    changes = build_form.pending()
    if changes:
        mid, field, old, new = changes[0]
        return "warn", "Now: settings changed, not applied (%s: %s %s -> %s%s) - press Apply." % (
            mid, field, old, new, " +%d" % (len(changes) - 1) if len(changes) > 1 else "")
    if bld.is_built():
        waiting = bld._waiting()
        if waiting:
            return "warn", "Now: %d module(s) at their guides - place them, then Build picked." % len(waiting)
        return "ok", "Rig built (%d modules). Change a module: pick it, change its settings below the list, Apply, Build picked." % len(groups)
    return "ok", "Now: place the guides, Mirror all L > R, then Build (below the settings). (%d modules)" % len(groups)


# ===========================================================================
# 1. modules
# ===========================================================================

def _label(info, built=None):
    built = bld.is_built() if built is None else built
    state = ("built" if bld.is_module_built(info) else "guides") if built else "guides"
    return "%-3s %-16s %-12s %s" % (info["side"], info["name"][:16], info["type"].replace("_", " ")[:12], state)


def _all_groups():
    """Builder modules, then the adopted parts (3 Existing rig)."""
    return guides.module_groups() + existing.adopted_groups()


def _row_label(g, built):
    if existing.is_adopted(g):
        info = existing.read_adopted(g)
        return "%-3s %-16s %-12s %s" % (info["side"], info["name"][:16], "adopted", "adopted")
    return _label(guides.read(g), built)


def refresh_list(select=None):
    if not cmds.textScrollList(N("List"), exists=True):
        return
    groups = _all_groups()
    built = bld.is_built()
    _rows[_P["p"]] = groups
    cmds.textScrollList(N("List"), edit=True, removeAll=True,
                        append=[_row_label(g, built) for g in groups] or ["(no modules yet)"])
    for g in (select if isinstance(select, (list, tuple)) else [select]):
        if g and g in groups:
            cmds.textScrollList(N("List"), edit=True, selectIndexedItem=groups.index(g) + 1)
    _fill_form()
    _steps_refresh()
    if cmds.button(N("SymToggle"), exists=True):
        cmds.button(N("SymToggle"), edit=True, label=_sym_label())
    ui.refresh_light(N("Light"))


def refresh_now(*_):
    """The list read again from the scene; the picked modules stay picked if they still exist."""
    keep = _picked()
    before = len(_rows.get(_P["p"], []))
    refresh_list(keep)
    now = len(_rows.get(_P["p"], []))
    gone = before - now
    utils.info(TOOL, "list refreshed: %d module(s)%s." % (now, (", %d gone" % gone) if gone > 0 else ""))


def _stale():
    """True when the list doesn't match the scene's modules any more."""
    rows = _rows.get(_P["p"], [])
    return any(not cmds.objExists(g) for g in rows) or len(_all_groups()) != len(rows)


def _auto_refresh():
    """The list follows the scene by itself: new / open scene, undo / redo, a module deleted by hand."""
    lst = N("List")

    def run(check):
        def go(*_):
            if not cmds.textScrollList(lst, exists=True):
                return
            try:
                if not check or _stale():
                    refresh_list(_picked())
            except Exception:
                pass                                        # never get in the way of the user
        return _w(go)
    for event, check in (("SceneOpened", False), ("NewSceneOpened", False), ("Undo", False), ("Redo", False),
                         ("SelectionChanged", True)):
        try:
            cmds.scriptJob(event=[event, run(check)], parent=lst)
        except (RuntimeError, TypeError):
            pass


def _picked_all():
    """Every row picked in the list: builder modules and adopted parts."""
    try:
        picked = cmds.textScrollList(N("List"), query=True, selectIndexedItem=True) or []
    except RuntimeError:
        return []
    rows = _rows.get(_P["p"], [])
    picked = [picked] if isinstance(picked, int) else [p for p in picked if isinstance(p, int)]
    return [rows[i - 1] for i in picked if i - 1 < len(rows) and cmds.objExists(rows[i - 1])]


def _picked():
    """The builder modules picked in the list (adopted parts are left out: they aren't built by the tool)."""
    return [g for g in _picked_all() if not existing.is_adopted(g)]


def _current():
    picked = _picked()
    return picked[0] if picked else None


def _on_pick(*_):
    picked = _picked()
    if picked:
        cmds.select(picked, replace=True)
    _fill_form()


def _is_free():
    return utils.tool_settings(SETTINGS_KEY, DEFAULTS).get("guide_mode", "linked") == "free"


def _mode_label():
    return "Guides: Free (click: Linked)" if _is_free() else "Guides: Linked (click: Free)"


def _apply_guide_mode(free):
    utils.update_setting(SETTINGS_KEY, "guide_mode", "free" if free else "linked")
    with utils.undo_chunk("gusrigGuideMode"):
        guides.set_mode(free, _height())
    if cmds.radioButtonGrp(N("GuideMode"), exists=True):
        cmds.radioButtonGrp(N("GuideMode"), edit=True, select=2 if free else 1)
    if cmds.button(N("ModeToggle"), exists=True):
        cmds.button(N("ModeToggle"), edit=True, label=_mode_label())
    utils.info(TOOL, "guides are %s." % ("free: each moves alone" if free else "linked: children follow"))


def set_guide_mode(*_):
    _apply_guide_mode(cmds.radioButtonGrp(N("GuideMode"), query=True, select=True) == 2)


def toggle_guide_mode(*_):
    _apply_guide_mode(not _is_free())


def _sym_label():
    try:
        on = guides.symmetry_on()
    except RuntimeError:
        on = False
    return "Symmetry: On (click: Off)" if on else "Symmetry: Off (click: On)"


def toggle_symmetry(*_):
    on = not guides.symmetry_on()
    with utils.undo_chunk("gusrigGuideSymmetry"):
        n = guides.set_symmetry(on)
    if cmds.button(N("SymToggle"), exists=True):
        cmds.button(N("SymToggle"), edit=True, label=_sym_label())
    if on and not n:
        utils.warn(TOOL, "no left module has a right twin yet - Mirror it first (the lock links them by itself).")
    else:
        utils.info(TOOL, ("symmetry on: %d right guide(s) follow the left ones live (move the LEFT guides)." % n)
                   if on else "symmetry off: the right guides stay where they are and move on their own again.")


def set_move_alone(on, *_):
    quick.move_alone(bool(on))


def _move_alone_off():
    if quick.is_move_alone():
        quick.move_alone(False, quiet=True)
        utils.info(TOOL, "'Move one guide at a time' turned off for the rig.")
    try:
        cmds.checkBox(N("MoveAlone"), edit=True, value=False)
    except RuntimeError:
        pass


def biped(*_):
    _save_main()
    bld.biped(_height())
    refresh_list()


def quadruped(*_):
    _save_main()
    animal = bld.ANIMAL_NAMES[cmds.optionMenu(N("Animal"), query=True, select=True) - 1] \
        if cmds.optionMenu(N("Animal"), exists=True) else "dog"
    utils.update_setting(SETTINGS_KEY, "animal", animal)
    bld.quadruped(_height(), animal)
    refresh_list()


def add(*_):
    _save_main()
    mtype = modules.ORDER[cmds.optionMenu(N("AddType"), query=True, select=True) - 1]
    side = "CLR"[cmds.optionMenu(N("AddSide"), query=True, select=True) - 1]
    name = cmds.textField(N("AddName"), query=True, text=True).strip() or mtype
    mod = modules.MODULES[mtype]
    saved = utils.load_setting("build_module_" + mtype, {})
    s = mod.complete(dict(saved)) if saved else None
    keep = None
    if mtype == "chain":
        s, keep = _chain_start(mod, side if side in mod.SIDES else mod.SIDES[0], name, s)
        if s is None:
            return
    if mtype == "fingers":
        s = _fingers_on_paw(mod, side if side in mod.SIDES else mod.SIDES[0], s)
    g = bld.add_module(mtype, side, name, _height(), s, keep=keep, snap=True)
    utils.info(TOOL, "added %s (%s). Place its guides." % (name, side if side in mod.SIDES else mod.SIDES[0]))
    refresh_list(g)


def _fingers_on_paw(mod, side, s):
    """No arm but a front leg (quadruped): the fingers hang from the front paw's ball joint and get their
    curl / spread on the front leg's settings control."""
    s = s or mod.complete(mod.default_settings(side))
    infos = [guides.read(g) for g in guides.module_groups()]
    if (s.get("attach") or "").split(":")[0] != "arm" or any(i["type"] == "arm" for i in infos):
        return s
    for i in infos:
        if i["type"] == "front_leg" and i["side"] in (side, "C"):
            ball = i["settings"].get("names", {}).get("ball", "front_ball")
            s["attach"] = "%s:%s" % (i["name"], ball)
            break
    return s


def _chain_start(mod, side, name, s):
    """Where a new chain's guides start: a straight line, the selection or a curve.
    Returns (settings, {role: position}) or (None, None) when cancelled."""
    from gus_rigtool.builder import chain
    s = s or mod.complete(mod.default_settings(side))
    s["names"]["name"] = s["names"].get("name") or name
    if not s.get("attach"):                            # a tail hangs from the hips, an ear from the head
        have = set(guides.read(g)["type"] for g in guides.module_groups())
        want = ("spine", "spine:hips") if side == "C" else ("neck", "neck:head")
        if want[0] in have:
            s["attach"] = want[1]
    end = 1 if s["options"].get("end_joint", True) else 0
    answer = cmds.confirmDialog(
        title="Chain - start the guides from", button=["Straight line", "Selection", "Curve", "Cancel"],
        defaultButton="Straight line", cancelButton="Cancel", dismissString="Cancel",
        message="Straight line: %d guides at a default spot, ready to move.\n"
                "Selection: one guide on each selected joint / locator / object, in selection order.\n"
                "Curve: guides spread evenly along the selected curve." % (int(s["names"]["count"]) + end))
    if answer in (None, "Cancel"):
        return None, None
    if answer == "Straight line":
        return s, None
    sel = cmds.ls(selection=True, long=True, flatten=True) or []
    if answer == "Selection":
        sel = utils.selected_transforms(ordered=True)
        if len(sel) < 2:
            raise RuntimeError("select at least 2 joints, locators or objects (in order), then Add.")
        pts = chain.positions_from_selection(sel)
    else:
        crv = [n for n in sel if cmds.listRelatives(n, shapes=True, type="nurbsCurve")]
        if not crv:
            raise RuntimeError("select a curve, then Add.")
        res = cmds.promptDialog(title="Chain - joints along the curve", message="How many joints (end joint included)?",
                                text=str(int(s["names"]["count"]) + end), button=["OK", "Cancel"],
                                defaultButton="OK", cancelButton="Cancel", dismissString="Cancel")
        if res != "OK":
            return None, None
        try:
            count = int(cmds.promptDialog(query=True, text=True))
        except (TypeError, ValueError):
            raise ValueError("type a whole number of joints.")
        if count < 2:
            raise ValueError("a chain needs at least 2 joints.")
        pts = chain.positions_from_curve(crv[0], count)
    s["names"]["count"] = max(1, len(pts) - end)
    return s, {"j%d" % i: p for i, p in enumerate(pts)}


def delete_module(*_):
    g = _current()
    if not g:
        utils.warn(TOOL, "pick a module in the list.")
        return
    if bld.is_built():
        utils.warn(TOOL, "go back to the guides first.")
        return
    with utils.undo_chunk("gusrigDeleteModule"):
        guides.delete(g)
    refresh_list()


def mirror_one(*_):
    g = _current()
    if not g:
        utils.warn(TOOL, "pick a left (or right) module in the list.")
        return
    info = guides.read(g)
    with utils.undo_chunk("gusrigMirrorGuides"):
        new = guides.mirror(g, modules.MODULES[info["type"]], _height())
    utils.info(TOOL, "%s guides mirrored to the other side." % info["name"])
    refresh_list(new)


def mirror_all(*_):
    bld.mirror_all(_height())
    refresh_list()


# ===========================================================================
# 2. module settings: tools/build_form.py
# ===========================================================================

def _fill_form():
    build_form.fill()


# ===========================================================================
# 3. naming
# ===========================================================================

def _naming_rows():
    s = names.settings()
    cmds.textFieldGrp(N("Pattern"), label="Name pattern", text=s["pattern"], columnWidth2=(110, 200),
                      annotation="Tokens: {side} {part} {type}. Example: {side}{part}{type} -> L_humerus_jnt")
    cmds.textFieldGrp(N("Centre"), label="Centre side token", text=s["centre"], columnWidth2=(110, 200),
                      annotation="Side token for centre parts (spine, head). Empty = none; e.g. C_")
    ui.note("Suffixes ({type}) and variants (added to {part}):")
    cmds.rowColumnLayout(numberOfColumns=4, columnWidth=[(1, 70), (2, 90), (3, 70), (4, 90)])
    for group in ("suffixes", "variants"):
        for key, value in s[group].items():
            cmds.text(label=key, align="right")
            cmds.textField(N("%s_%s" % (group, key)), text=value)
    cmds.setParent("..")


def save_naming(*_):
    pattern = cmds.textFieldGrp(N("Pattern"), query=True, text=True).strip()
    problem = names.check_pattern(pattern)
    if problem:
        raise ValueError(problem)
    s = names.settings()
    data = {"pattern": pattern, "centre": cmds.textFieldGrp(N("Centre"), query=True, text=True).strip(),
            "suffixes": {}, "variants": {}}
    for group in ("suffixes", "variants"):
        for key in s[group]:
            data[group][key] = cmds.textField(N("%s_%s" % (group, key)), query=True, text=True)
    utils.save_setting(names.SETTINGS_KEY, data)
    utils.info(TOOL, "naming saved. Example: %s, %s" % (names.make("L", "humerus", "jnt"),
                                                          names.make("L", "humerus", "ctrl", "fk")))
    show_preview()


def reset_naming(*_):
    utils.save_setting(names.SETTINGS_KEY, {})
    s = names.settings()
    cmds.textFieldGrp(N("Pattern"), edit=True, text=s["pattern"])
    cmds.textFieldGrp(N("Centre"), edit=True, text=s["centre"])
    for group in ("suffixes", "variants"):
        for key, value in s[group].items():
            cmds.textField(N("%s_%s" % (group, key)), edit=True, text=value)
    show_preview()


def show_preview(*_):
    rows = bld.preview()
    if not rows:
        text = "No modules yet."
    else:
        clash = [n for _m, n, e in rows if e]
        lines = []
        if clash and not bld.is_built():
            lines.append("!! %d name(s) already exist in the scene: Build would stop." % len(clash))
        current = None
        for mod_id, n, exists in rows:
            if mod_id != current:
                lines.append("[%s]" % mod_id)
                current = mod_id
            lines.append("   %s%s" % (n, "   (exists)" if exists and not bld.is_built() else ""))
        text = "\n".join(lines)
    cmds.scrollField(N("Preview"), edit=True, text=text)


# ===========================================================================
# 4. build / templates
# ===========================================================================

def export_rig_data(*_):
    from gus_rigtool.builder import rig_data
    path = cmds.fileDialog2(fileMode=0, caption="Export rig data", fileFilter="Rig data (*.json)",
                            startingDirectory=bld.templates_dir())
    if not path:
        return
    sel = [n for n in utils.selected_transforms() if cmds.listRelatives(n, shapes=True, type="nurbsCurve")]
    n, k = rig_data.export(path[0], sel or None)
    utils.info(TOOL, "rig data saved: %d control(s), %d driven key curve(s)." % (n, k))


def import_rig_data(*_):
    from gus_rigtool.builder import rig_data
    path = cmds.fileDialog2(fileMode=1, caption="Import rig data", fileFilter="Rig data (*.json)",
                            startingDirectory=bld.templates_dir())
    if not path:
        return
    got, notes = rig_data.import_(path[0])
    ui.report_window("Gus_Rigtool - rig data", "\n".join(["%s: %d" % kv for kv in got.items()] + [""] + notes))


def forget_shapes(*_):
    picked = _picked()
    if not picked:
        raise RuntimeError("pick modules in the list (Modules in the scene).")
    n = bld.forget_shapes(picked)
    utils.info(TOOL, "%d module(s) will use their default control shapes after Build picked / Build." % n)


def _unapplied_ok():
    """Settings changed in the form but not applied: apply them first? False = cancel."""
    changes = build_form.pending()
    if not changes:
        return True
    answer = cmds.confirmDialog(
        title="Settings not applied", button=["Apply and build", "Build without them", "Cancel"],
        defaultButton="Apply and build", cancelButton="Cancel", dismissString="Cancel",
        message="These settings aren't applied yet:\n\n%s\n\nApply them first?" % build_form.describe(changes))
    if answer == "Cancel":
        return False
    if answer == "Apply and build":
        picked = _picked()
        (build_form.apply_common if len(picked) > 1 else build_form.apply)()
    return True


def build_rig(*_):
    if not _unapplied_ok():
        return
    _save_main()
    _move_alone_off()
    bld.build_all(_height())
    refresh_list()
    from gus_rigtool.tools import home
    home.say_next(TOOL, "rig built.")


def build_picked(*_):
    """Build or rebuild only the modules picked in the list (and the ones hanging from them)."""
    if not _unapplied_ok():
        return
    _save_main()
    picked = _picked()
    if not picked:
        raise RuntimeError("pick modules in the list (Modules in the scene).")
    ids = [guides.read(g)["id"] for g in picked]
    with_parents = False
    parents = bld.unbuilt_parents(ids)
    if parents:
        answer = cmds.confirmDialog(
            title="Build picked", button=["Build them too", "Only the picked", "Cancel"],
            defaultButton="Build them too", cancelButton="Cancel", dismissString="Cancel",
            message="%s hang(s) from modules that aren't built:\n\n%s\n\nBuild those too? (Only the picked: "
                    "they go under the root until those are built.)" % (", ".join(ids), "\n".join(parents)))
        if answer == "Cancel":
            return
        with_parents = answer == "Build them too"
    hanging = [t for t in bld.dependents(ids) if t not in ids]
    if hanging:
        answer = cmds.confirmDialog(title="Build picked", button=["Build", "Cancel"], defaultButton="Build",
                                    cancelButton="Cancel", dismissString="Cancel",
                                    message="The modules hanging from them are built / rebuilt too:\n\n%s"
                                            % "\n".join(hanging))
        if answer != "Build":
            return
    _move_alone_off()
    bld.build_picked(ids, _height(), with_parents)
    refresh_list(picked)


rebuild_selected = build_picked         # the old name


def _module_joints(info):
    st = bld._stored(info) or {}
    out = []
    for j in (st.get("joints") or {}).values():
        if j and cmds.objExists(j) and cmds.nodeType(j) == "joint" and j not in out:
            out.append(j)
    return out


def show_axes_picked(*_):
    """Toggle the joints' local axes of the picked modules (building the ones at their guides first)."""
    picked = _picked()
    if not picked:
        raise RuntimeError("pick modules in the list (Modules in the scene).")
    infos = [guides.read(g) for g in picked]
    waiting = [i for i in infos if not bld.is_module_built(i)]
    if waiting:
        if cmds.confirmDialog(title="Show joint axes", button=["Build them", "Cancel"], defaultButton="Build them",
                              cancelButton="Cancel", dismissString="Cancel",
                              message="%s %s at the guides. Build them to see their joint axes? (Back to guides "
                                      "(picked) takes them down again.)" % (", ".join(i["id"] for i in waiting),
                                                                            "is" if len(waiting) == 1 else "are")
                              ) != "Build them":
            return
        _move_alone_off()
        bld.build_picked([i["id"] for i in waiting], _height(), True)
        refresh_list(picked)
        infos = [guides.read(g) for g in _picked() or picked]
    joints = [j for i in infos for j in _module_joints(i)]
    if not joints:
        raise RuntimeError("no joints found for the picked modules.")
    on = not any(cmds.getAttr(j + ".displayLocalAxis") for j in joints)
    for j in joints:
        cmds.setAttr(j + ".displayLocalAxis", on)
    utils.info(TOOL, "joint axes %s on %d joint(s)%s." % ("shown" if on else "hidden", len(joints),
                                                         " - X red (down the bone), Y green, Z blue" if on else ""))


def show_guides_picked(*_):
    """Show only the picked modules' guides (the rig stays); again: hide them."""
    picked = _picked()
    if not picked:
        raise RuntimeError("pick modules in the list (Modules in the scene).")
    if bld.is_built() and sorted(guides.shown_only()) == sorted(picked) and not bld._waiting():
        guides.set_visible(False)
        utils.info(TOOL, "guides hidden.")
        return
    guides.show_only(picked)
    utils.info(TOOL, "showing the guides of %s. Move them, then Build picked (press again to hide)."
               % ", ".join(guides.read(g)["id"] for g in picked))


def back_picked(*_):
    picked = _picked()
    if not picked:
        raise RuntimeError("pick modules in the list (Modules in the scene).")
    ids = [guides.read(g)["id"] for g in picked]
    if not bld.is_built():
        raise RuntimeError("the rig isn't built: the guides are already there.")
    targets = bld.dependents(ids)
    if len(targets) > len(ids):
        answer = cmds.confirmDialog(title="Back to guides (picked)", button=["Go back", "Cancel"],
                                    defaultButton="Go back", cancelButton="Cancel", dismissString="Cancel",
                                    message="These modules hang from the picked ones and go back too:\n\n%s"
                                            % "\n".join(t for t in targets if t not in ids))
        if answer != "Go back":
            return
    _move_alone_off()
    bld.back_to_guides_selected(ids)
    refresh_list(picked)


def make_anim_tools(*_):
    from gus_rigtool.builder import anim_export
    folder = cmds.fileDialog2(fileMode=3, caption="Folder for the animator tools (Gus Animtool)",
                              okCaption="Save here")
    if not folder:
        return
    files = anim_export.make(folder[0])
    utils.info(TOOL, "animator tools saved in %s: %s. Animators drag drag_to_maya_animtool.mel into Maya."
               % (folder[0], ", ".join(f.replace("\\", "/").split("/")[-1] for f in files)))


def open_anim_tools(*_):
    from gus_rigtool.builder import anim_export
    version = anim_export.install_here()
    utils.info(TOOL, "Gus Animtool %s installed in your maya/scripts folder (with your naming) and opened." % version)


def guides_from_rig(*_):
    if not bld.is_built():
        raise RuntimeError("build the rig first: the guides are put back onto its joints.")
    moved, missing = bld.guides_from_rig()
    utils.info(TOOL, "%d guide(s) put back onto the rig%s." % (
        moved, ("; not found: %s" % ", ".join(missing[:8])) if missing else ""))


def back(*_):
    bld.back_to_guides()
    refresh_list()


def save_template(*_):
    path = cmds.fileDialog2(fileMode=0, caption="Save rig template", fileFilter="Rig template (*.json)",
                            startingDirectory=bld.templates_dir())
    if path:
        n = bld.save_template(path[0], _height())
        utils.info(TOOL, "template saved: %d modules, guide positions, settings and naming." % n)


def load_template(*_):
    path = cmds.fileDialog2(fileMode=1, caption="Load rig template", fileFilter="Rig template (*.json)",
                            startingDirectory=bld.templates_dir())
    if path:
        n = bld.load_template(path[0])
        utils.info(TOOL, "template loaded: %d modules." % n)
        refresh_list()


# ===========================================================================
# window
# ===========================================================================

PUBLISH_BOOLS = [
    ("lock_groups", "Lock the groups (offset / space / rig groups)",
     "Animators only see controls: every group's channels are locked and hidden."),
    ("hide_locked", "Hide locked channels on controls", "Locked channels leave the channel box."),
    ("lock_fk_translate", "FK controls can't translate", "Lock translate on every FK control."),
    ("hide_joints", "Hide the joints (skeleton_grp)", "The skin still works."),
    ("geo_reference", "Geometry not selectable (geo_grp as reference)", "Click through the model to the controls."),
    ("sets", "Selection sets (rig_ctrls_set, a set per module, bind_joints_set)", ""),
    ("protect_networks", "Protect the networks (lock utility nodes)",
     "Utility nodes, driven keys and constraints can't be deleted or renamed by accident. Unpublish unlocks them."),
    ("default_pose", "Save the default pose on each control", "Reset pose and Gus Animtool's Reset go back to it."),
    ("run_checker", "Run the Checker on the rig after", "A report window shows what the Checker found."),
]


def _publish_options():
    from gus_rigtool.builder import publish
    o = dict(publish.DEFAULTS, run_checker=True)
    o.update(utils.load_setting("build_publish", {}) or {})
    return o


def _save_publish(*_):
    o = {}
    for key, _l, _t in PUBLISH_BOOLS:
        o[key] = cmds.checkBox(N("Pub_" + key), query=True, value=True)
    o["guides"] = ["hide", "delete", "leave"][cmds.optionMenu(N("Pub_guides"), query=True, select=True) - 1]
    utils.save_setting("build_publish", o)
    return o


def publish_rig(*_):
    from gus_rigtool.builder import publish
    o = _save_publish()
    if o["guides"] == "delete" and guides.module_groups():
        if cmds.confirmDialog(title="Publish - delete the guides", button=["Delete them", "Cancel"],
                              message="Without guides you can't go Back to guides or rebuild a module.\n"
                                      "Save a template first if you may need them.",
                              defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Delete them":
            return
    done = publish.publish(o)
    refresh_list()
    from gus_rigtool.tools import home
    home.say_next(TOOL, "published.")
    if o.get("run_checker"):
        fails, warns, text = publish.check()
        ui.report_window("Gus_Rigtool - published rig",
                         "Published:\n  " + "\n  ".join(done) + "\n\nChecker on the rig: %d fail, %d warning\n\n%s"
                         % (fails, warns, text))


def _deliver(*_):
    from gus_rigtool.builder import deliver
    deliver.show()


def unpublish_rig(*_):
    from gus_rigtool.builder import publish
    publish.unpublish()
    refresh_list()


def _steps_refresh(select=None):
    from gus_rigtool.builder import custom_steps
    if not cmds.textScrollList(N("Steps"), exists=True):
        return
    items = custom_steps.steps()
    cmds.textScrollList(N("Steps"), edit=True, removeAll=True,
                        append=[custom_steps.label(i) for i in items] or ["(no scripts yet)"])
    if select is not None and 0 <= select < len(items):
        cmds.textScrollList(N("Steps"), edit=True, selectIndexedItem=select + 1)


def _step_index():
    picked = cmds.textScrollList(N("Steps"), query=True, selectIndexedItem=True) or []
    from gus_rigtool.builder import custom_steps
    if not picked or picked[0] - 1 >= len(custom_steps.steps()):
        raise RuntimeError("pick a script in the Custom steps list.")
    return picked[0] - 1


def step_add(when):
    from gus_rigtool.builder import custom_steps
    got = cmds.fileDialog2(fileFilter="Python (*.py)", dialogStyle=2, fileMode=1,
                           caption="Script to run %s every build" % ("before" if when == "pre" else "after"))
    if got:
        items = custom_steps.add(got[0], when)
        _steps_refresh(len(items) - 1)


def step_remove(*_):
    from gus_rigtool.builder import custom_steps
    custom_steps.remove(_step_index())
    _steps_refresh()


def step_toggle(*_):
    from gus_rigtool.builder import custom_steps
    i = _step_index()
    custom_steps.toggle(i)
    _steps_refresh(i)


def step_move(delta):
    from gus_rigtool.builder import custom_steps
    i = _step_index()
    custom_steps.move(i, delta)
    _steps_refresh(i + delta)


def step_run(*_):
    from gus_rigtool.builder import custom_steps
    item = custom_steps.steps()[_step_index()]
    err = custom_steps.run_one(item, item.get("when", "post"), [], bld.rig_groups()
                               if item.get("when") == "post" and bld.is_built() else {})
    if err:
        ui.report_window("Gus_Rigtool - custom step failed", err)
    else:
        utils.info(TOOL, "ran %s." % custom_steps.label(item))


def toggle_guide_names(on, *_):
    utils.update_setting(SETTINGS_KEY, "guide_names", bool(on))
    with utils.undo_chunk("gusrigGuideNames"):
        n = guides.show_names(bool(on))
    utils.info(TOOL, ("guide names shown (%d)." % n) if on else "guide names hidden.")


def _page():
    """A sub-tab's page: a column (sections go in it)."""
    return cmds.columnLayout(adjustableColumn=True, rowSpacing=4)


# ===========================================================================
# 3 Existing rig: adopt hand-made parts, rebuild others on their joints
# ===========================================================================

SWITCH_VALUES = [(0.0, 1.0), (1.0, 0.0), (0.0, 10.0), (10.0, 0.0)]
_scan = {}                     # prefix -> last scan
_limbs = {}                    # prefix -> limbs waiting to be adopted


def _field(key, label, tip="", pick=True, multi=True):
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(95, 200, 25),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label=label)
    cmds.textField(N(key), annotation=tip)
    if pick:
        cmds.button(label="<", command=_w(_guard(lambda *_, k=key, m=multi: _take(k, m))),
                    annotation="Take the selection (in the order you selected).")
    else:
        cmds.text(label="")
    cmds.setParent("..")


def _take(key, multi=True):
    sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(selection=True, long=True) or []
    if key == "ExSwitch":
        attrs = cmds.channelBox("mainChannelBox", query=True, selectedMainAttributes=True) or []
        if not sel or not attrs:
            raise RuntimeError("select the control, click the switch attribute in the channel box, then <.")
        long_attr = cmds.attributeQuery(attrs[0], node=sel[0], longName=True)
        cmds.textField(N(key), edit=True, text=naming.short_name(sel[0]) + "." + long_attr)
        return
    if not sel:
        raise RuntimeError("select something first.")
    sel = sel if multi else sel[:1]
    cmds.textField(N(key), edit=True, text=" ".join(naming.short_name(n) for n in sel))


BUILD_PANEL = "build_rig"


def _list_section(height=150, extra_buttons=True):
    ui.section("Modules in the scene", help_text="Click a module: its settings show right below the list. "
               "Ctrl / Shift-click several to set their common options or build them together. "
               "State: built, or guides (waiting to be built).")
    cmds.text(label="  %-3s %-16s %-12s %s" % ("Side", "Module", "Type", "State"), align="left",
              font="fixedWidthFont")
    cmds.textScrollList(N("List"), height=height, selectCommand=_w(_on_pick), allowMultiSelection=True,
                        font="fixedWidthFont",
                        annotation="Pick a module: its settings show below. Ctrl / Shift-click several.")
    ui.row(2, 170)
    cmds.button(label="Refresh", command=_w(_guard(refresh_now)),
                annotation="Read the scene again: modules you deleted (or from another scene) leave the list, "
                           "and each State is checked again. It also happens by itself on new / open scene, "
                           "undo / redo, and when a listed module disappears.")
    cmds.button(N("ModeToggle"), label=_mode_label(), command=_w(_guard(toggle_guide_mode)),
                annotation="Linked: moving a guide moves the ones below it. Free: every guide moves alone. "
                            "Click to switch (nothing moves).")
    cmds.setParent("..")
    cmds.button(N("SymToggle"), label=_sym_label(), command=_w(_guard(toggle_symmetry)),
                annotation="On: every right guide follows its left twin live (mirrored across X) - move the "
                           "left ones; the right ones can't be moved. Off: they stay where they are. Modules "
                           "mirrored later are linked by themselves while it is on.")
    if extra_buttons:
        ui.row(3, 113)
        cmds.button(label="Mirror picked", command=_w(_guard(mirror_one)),
                    annotation="Copy the picked module's guides to the other side.")
        cmds.button(label="Mirror all L > R", command=_w(_guard(mirror_all)))
        cmds.button(label="Delete", command=_w(_guard(delete_module)),
                    annotation="Delete the picked module's guides.")
        cmds.setParent("..")
    _auto_refresh()
    ui.end_section()



def _build_part(s, pop=True, advanced=True):
    """Build, Publish (and, with advanced, Keep, Custom steps, Naming, Templates): on the Modules page, and
    in the Build pop-out."""
    ui.section("Build", help_text="Build makes every module that isn't built yet (one undo): skeleton_grp (skin "
               "to these joints), controls_grp, rig_nodes_grp. Build picked builds or rebuilds only the modules "
               "picked in the list. Show guides (picked) shows their guides on the built rig; Back to guides "
               "(picked) takes only them down; Back to guides takes the whole rig down. The skin and the control "
               "shapes you changed are kept.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 4)])
    cmds.button(label="Build", height=32, backgroundColor=ui.MAIN_BG, command=_w(_guard(build_rig)),
                annotation="Build every module that isn't built yet. One undo.")
    if pop:
        cmds.button(label="Pop out", width=70, height=32, command=lambda *_: ui.open_panel(BUILD_PANEL),
                    annotation="This Build part in its own window (with its own module list), to dock anywhere.")
    else:
        cmds.text(label="")
    cmds.setParent("..")
    cmds.button(label="Build picked", height=26, command=_w(_guard(build_picked)),
                annotation="Only the modules picked in the list (and the ones hanging from them): a built one is "
                           "rebuilt from its guides and settings, one at its guides is built.")
    ui.row(2, 170)
    cmds.button(label="Show guides (picked)", command=_w(_guard(show_guides_picked)),
                annotation="Only the picked modules' guides show; the rig stays. Move them, then Build picked. "
                           "Press again to hide them.")
    cmds.button(label="Back to guides (picked)", command=_w(_guard(back_picked)),
                annotation="Only the picked modules (and the ones hanging from them) go back to their guides: "
                           "their rig is deleted, the skin and your control shapes saved.")
    cmds.setParent("..")
    cmds.button(label="Show joint axes (picked)", command=_w(_guard(show_axes_picked)),
                annotation="The picked modules' joints show their axes (X red, Y green, Z blue) - check twists "
                           "before you skin. Press again to hide them. Modules at their guides are built first "
                           "(it asks).")
    cmds.button(label="Back to guides (whole rig)", height=24, command=_w(_guard(back)),
                annotation="Delete the whole built rig and show every guide again. The skin is saved.")
    ui.end_section()

    ui.section("World controls (scale)", collapse=True, help_text="Global_ctrl (the scale) > World_ctrl > "
               "Local_ctrl from the World_ctrl your rig has: Global is new, above it - the rig's globalScale moves "
               "there, and everything that read it (stretchy limbs, IK spline, chains) reads it from Global. World "
               "moves and turns only (its follows / spaces stay). Local is new, under it - what was under World "
               "goes under it. Shows the plan first; nothing moves; one undo. Select the world control, or none (it "
               "finds it). Then Check this scene > Scale shows what doesn't grow with the rig; Repair fixes the "
               "usual causes.")
    ui.main_button("Make Global > World > Local", _w(_guard(world_levels)), "Shows what it will do first.")
    cmds.button(label="Make the rig scale", height=28, command=_w(_guard(make_scalable)),
                annotation="Everything that keeps the rig from growing evenly with Global_ctrl's globalScale: ribbon "
                           "follicles, joints held by constraints (every joint of a chain), stretch lengths. Nothing "
                           "moves at scale 1 (checked - undone if it did). One undo.")
    ui.end_section()

    ui.section("Visibility switches", collapse=True, help_text="A control above the head (Visibility_ctrl) with "
               "on / off switches for the animators: Body_Ctrls, Face_Ctrls, Secondary_Ctrls (ribbons, cloth), "
               "Joints, Geometry, and Geo_Display (Normal / Template / Reference). A switch hides the controls' "
               "shapes, never their groups - keys, constraints and IK / FK visibility don't change. Controls are "
               "sorted by name (face words -> Face, ribbons / cloth -> Secondary, the rest -> Body); move any with "
               "the buttons below. Your display layers are left alone (a group in one isn't switched). Shows the "
               "plan first; one undo.")
    vs = utils.tool_settings("vis_switches", VIS_DEFAULTS)
    cmds.gridLayout(numberOfColumns=3, cellWidthHeight=(115, 20))
    for k in VIS_ALL:
        cmds.checkBox(N("Vis_" + k), label=k, value=k in vs["which"], changeCommand=_w(_save_vis),
                      annotation="Make this switch (5.6.20: only the ticked ones; tick more later and Make again)")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(80, 190, 60))
    cmds.text(label="Switches on", align="right")
    cmds.textField(N("Vis_on"), text=vs["on"], changeCommand=_w(_save_vis),
                   placeholderText="empty: a new gear above the head",
                   annotation="A control of yours to hold the switches - empty: a gear above the head (open while "
                              "you rig, locked by Publish)")
    cmds.button(label="< sel", command=_w(_guard(_vis_on_sel)))
    cmds.setParent("..")
    ui.main_button("Make the switches", _w(_guard(vis_switches)), "Select the head control first.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
    for k, label in (("Body_Ctrls", "Selected -> Body"), ("Face_Ctrls", "Selected -> Face"),
                     ("Secondary_Ctrls", "Selected -> Secondary")):
        cmds.button(label=label, command=_w(_guard(lambda *_a, k=k: vis_assign(k))),
                    annotation="The selected controls go on the %s switch." % k)
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Face switches -> selected", command=_w(_guard(vis_face_here)),
                annotation="The face's switches go on the selected control (e.g. Face_settings_ctrl): Face_Ctrls "
                           "(all of the face) and one per part - Brows, Eyelids, Eyes, Mouth, Tongue... Shows the "
                           "plan first; one undo.")
    cmds.button(label="Remove visibility switches", command=_w(_guard(vis_remove_hand)),
                annotation="Your own show / hide attributes on the selected controls (e.g. Sleeves, Bend on the "
                           "wrist gears) go; what they hid is shown again. Pick some in the Channel Box to remove "
                           "only those - on Visibility_ctrl too (one of its switches). Lists them first; one undo.")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Clothes controls: per part", command=_w(_guard(vis_clothes)),     # 5.6.30: the controls
                annotation="The secondary controls (collar, cape, sleeves, pants, belt, hood, bandages, tail, "
                           "tweaks...) one switch each, under Secondary_Ctrls - on Visibility_ctrl, or on the "
                           "control you select. Run again after adding controls. Shows the plan first; one undo.")
    cmds.button(label="Switch from selection...", command=_w(_guard(vis_from_selection)),
                annotation="Select the controls, then (last) the control the switch goes on - a gear of yours, "
                           "Face_settings_ctrl, Visibility_ctrl. Name it; put it under one of that control's master "
                           "switches (Face_Ctrls...) or on its own. One undo.")
    cmds.setParent("..")
    ui.row(2, 170)                                  # 5.6.29: the heavy clothes off while blocking (speed)
    cmds.button(label="Clothes: full / hidden", command=_w(_guard(vis_clothes_hidden)),
                annotation="The clothes MESHES: Visibility_ctrl.Clothes (Full / Hidden) and one per piece "
                           "(Hood_Geo, Shirt_Geo, Pants_Geo, Bandages_Geo) - the selected meshes, or the ones found by "
                           "name - hidden, and their own skin / delta mush switched off, so the rig moves faster while "
                           "blocking. Shows the plan first; safe mode checks nothing moves at Full.")
    cmds.button(label="Remove full / hidden", command=_w(_guard(vis_clothes_hidden_remove)),
                annotation="The Clothes switch goes: the meshes shown, their deformers on. One undo.")
    cmds.setParent("..")
    cmds.button(label="Remove all the switches", command=_w(_guard(vis_remove_all)),
                annotation="Every switch the tool made goes (Visibility_ctrl - deleted if the tool made it - and the "
                           "face's): every control, the joints and the geometry shown. Asks first; one undo.")
    ui.end_section()

    ui.section("Publish (clean rig for animators)", collapse=True,
               help_text="Publish makes the built rig clean: groups locked, locked channels hidden, joints hidden, "
               "selection sets (rig_ctrls_set with a set per module, bind_joints_set), each control remembers "
               "its default pose (Reset pose and Gus Animtool go back to it), guides hidden. Then the Checker runs on "
               "the rig. Unpublish puts everything back; Build / Back to guides unpublish first.")
    po = _publish_options()
    for key, label, tip in PUBLISH_BOOLS:
        cmds.checkBox(N("Pub_" + key), label=label, value=bool(po[key]), annotation=tip,
                      changeCommand=_w(_save_publish))
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 200), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Guides")
    cmds.optionMenu(N("Pub_guides"), changeCommand=_w(_save_publish),
                    annotation="hide: they stay (Back to guides still works). delete: smaller file, but no going "
                               "back to guides. leave: as they are.")
    for c in ("hide", "delete (no going back to guides)", "leave"):
        cmds.menuItem(label=c)
    cmds.optionMenu(N("Pub_guides"), edit=True, select=1 + ["hide", "delete", "leave"].index(po["guides"]))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Publish", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(publish_rig)),
                annotation="Clean the built rig for animators (one undo). Unpublish puts it back.")
    cmds.button(label="Unpublish", height=28, command=_w(_guard(unpublish_rig)),
                annotation="Put back everything Publish changed (not deleted guides).")
    cmds.setParent("..")
    cmds.button(label="Deliver to animators...", height=26, command=_w(_guard(_deliver)),
                annotation="One folder: the published rig, the animator tools with your naming, the rig check and "
                           "a README (optionally zipped). Your scene stays as it is.")
    ui.end_section()

    if advanced:
        _advanced_part(s)


def world_levels(*_):
    from gus_rigtool.core import world_levels as WL
    sel = [c for c in cmds.ls(selection=True, long=True, type="transform") or []]
    world = sel[0] if len(sel) == 1 else None
    lines = WL.plan(world)
    if cmds.confirmDialog(title="Gus_Rigtool - world controls", message="\n".join(lines) + "\n\nNothing moves. "
                          "One undo.", button=["Make", "Cancel"], defaultButton="Make", cancelButton="Cancel",
                          dismissString="Cancel") != "Make":
        return
    got = WL.make(world)
    utils.info(TOOL, "%s > %s > %s made: the scale is on %s (%d reader(s) moved), %d node(s) under %s." % (
        naming.short_name(got["global"]), naming.short_name(got["world"]), naming.short_name(got["local"]),
        naming.short_name(got["global"]), got["readers"], got["moved"], naming.short_name(got["local"])))


VIS_ALL = ("Body_Ctrls", "Face_Ctrls", "Secondary_Ctrls", "Joints", "Geometry", "Geo_Display")
VIS_DEFAULTS = {"which": list(VIS_ALL), "on": ""}


def _save_vis(*_):
    s = {"which": [k for k in VIS_ALL if cmds.checkBox(N("Vis_" + k), query=True, value=True)],
         "on": cmds.textField(N("Vis_on"), query=True, text=True).strip()}
    utils.save_setting("vis_switches", s)
    return s


def _vis_on_sel(*_):
    sel = cmds.ls(selection=True, type="transform") or []
    if len(sel) != 1:
        raise RuntimeError("select the one control the switches go on.")
    cmds.textField(N("Vis_on"), edit=True, text=sel[0])
    _save_vis()


def vis_clothes(*_):
    from gus_rigtool.core import vis_switch as VS
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    holder = sel[0] if len(sel) == 1 else None
    lines, _by = VS.secondary_plan(holder)
    if cmds.confirmDialog(title="Gus_Rigtool - clothes switches", message="\n".join(lines) + "\n\nNothing moves. "
                          "One undo.", button=["Make", "Cancel"], defaultButton="Make", cancelButton="Cancel",
                          dismissString="Cancel") != "Make":
        return
    got = VS.split_secondary(holder)
    utils.info(TOOL, "switches on %s: %s%s." % (
        naming.short_name(got["holder"]), ", ".join("%s %d" % kv for kv in got["parts"].items()) or "nothing",
        "; left alone (driven already): " + ", ".join(naming.short_name(x) for x in got["skipped"][:6])
        if got["skipped"] else ""))


def vis_clothes_hidden(*_):
    """5.6.29: Visibility_ctrl.Clothes - Full / Hidden - for the heavy clothes meshes (safe mode: nothing moves)."""
    from gus_rigtool.core import clothes_switch as CS, safe
    sel = [t for t in cmds.ls(selection=True, long=True, type="transform") or []
           if cmds.listRelatives(t, shapes=True, type="mesh")]
    meshes = sel or CS.suggest()
    if not meshes:
        raise RuntimeError("select the clothes meshes (none are found by name: hood, shirt, pants...).")
    if cmds.confirmDialog(title="Gus_Rigtool - clothes full / hidden", message="\n".join(CS.describe(meshes)) +
                          "\n\nNothing moves at Full (safe mode checks). One undo.", button=["Make", "Cancel"],
                          defaultButton="Make", cancelButton="Cancel", dismissString="Cancel") != "Make":
        return
    kept, got = safe.run(lambda: CS.make(meshes), label="gusrigClothesSwitch", states=("rest",))
    if not kept:
        raise RuntimeError("the clothes switch was undone - %s" % got)
    utils.info(TOOL, "Visibility_ctrl.Clothes + %s: %d mesh(es), %d deformer(s) switched with them%s." % (
        ", ".join(p["attr"] for p in got["parts"].values()), len(got["meshes"]), len(got["deformers"]),
        "; visibility driven already, left alone: " + ", ".join(
            naming.short_name(x) for x in got["skipped"]) if got["skipped"] else ""))


def vis_clothes_hidden_remove(*_):
    from gus_rigtool.core import clothes_switch as CS
    if not CS.remove():
        raise RuntimeError("there's no Clothes switch.")
    utils.info(TOOL, "the Clothes switch is gone: the clothes are shown and their deformers on.")


def vis_from_selection(*_):
    from gus_rigtool.core import vis_switch as VS
    sel = cmds.ls(selection=True, long=True, type="transform", orderedSelection=True) or \
        cmds.ls(selection=True, long=True, type="transform") or []
    if len(sel) < 2:
        raise RuntimeError("select the controls, then (last) the control the switch goes on.")
    holder, ctrls = sel[-1], sel[:-1]
    if cmds.promptDialog(title="Gus_Rigtool - switch from selection", message="%d control(s) -> a switch on %s.\n"
                         "Name:" % (len(ctrls), naming.short_name(holder)), button=["Next", "Cancel"],
                         defaultButton="Next", cancelButton="Cancel", dismissString="Cancel") != "Next":
        return
    name = cmds.promptDialog(query=True, text=True)
    masters = VS.masters_on(holder)
    master = None
    if masters:
        got = cmds.confirmDialog(title="Gus_Rigtool - switch from selection", message="Put %s under one of %s's "
                                 "switches (that one hides it too)?" % (name, naming.short_name(holder)),
                                 button=masters + ["On its own", "Cancel"], defaultButton=masters[0],
                                 cancelButton="Cancel", dismissString="Cancel")
        if got == "Cancel":
            return
        master = got if got in masters else None
    moved, skipped = VS.add_switch(ctrls, name, holder, master)
    utils.info(TOOL, "%s.%s shows / hides %d control(s)%s%s." % (
        naming.short_name(holder), name, moved, " (under %s)" % master if master else "",
        "; left alone (driven by something else): " + ", ".join(naming.short_name(x) for x in skipped[:6])
        if skipped else ""))


def vis_remove_all(*_):
    from gus_rigtool.core import vis_switch as VS
    sw, fh = VS.find(), VS.face_holder()
    if not sw and not fh:
        raise RuntimeError("no visibility switches in this scene.")
    lines = []
    if sw:
        lines.append("%s: its switches go%s" % (naming.short_name(sw), " - and the gear itself" if
                                                VS.made_by_tool(sw) else " (the control stays)"))
    if fh:
        lines.append("%s: the face's switches go (the control stays)" % naming.short_name(fh))
    if cmds.confirmDialog(title="Gus_Rigtool - remove the switches", message="\n".join(lines) + "\n\nEvery "
                          "control, the joints and the geometry are shown. One undo.", button=["Remove", "Cancel"],
                          defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Remove":
        return
    got = VS.remove_all()
    utils.info(TOOL, "visibility switches removed%s%s - everything shown." % (
        " (the gear deleted)" if got["gear_deleted"] else "", "; the face's too" if got["face"] else ""))


def vis_switches(*_):
    from gus_rigtool.core import vis_switch as VS
    o = _save_vis()
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    head = sel[0] if sel else None
    if not o["which"]:
        raise RuntimeError("tick at least one switch.")
    if not VS.find() and not head and not o["on"]:
        raise RuntimeError("select the head control: the switches go on a control just above it.")
    if cmds.confirmDialog(title="Gus_Rigtool - visibility switches", message="\n".join(VS.plan(head, o["on"] or None)) +
                          "\n\nNothing moves. One undo.", button=["Make", "Cancel"], defaultButton="Make",
                          cancelButton="Cancel", dismissString="Cancel") != "Make":
        return
    got = VS.make(head, which=o["which"], on=o["on"] or None)
    c = got["controls"]
    utils.info(TOOL, "%s: Body %d, Face %d, Secondary %d control(s)%s%s." % (
        naming.short_name(got["control"]), c["Body_Ctrls"], c["Face_Ctrls"], c["Secondary_Ctrls"],
        ("; " + ", ".join(got["groups"]) if got["groups"] else "") + (
            "; display layers let go: " + ", ".join(got["released"]) if got.get("released") else ""),
        "; %d left alone (their shapes' visibility is driven already): %s" % (
            len(got["skipped"]), ", ".join(naming.short_name(x) for x in got["skipped"][:6]))
        if got["skipped"] else ""))
    cmds.select(got["control"])


def vis_assign(switch):
    from gus_rigtool.core import vis_switch as VS
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if not sel:
        raise RuntimeError("select the controls to move.")
    moved, skipped = VS.assign(sel, switch)
    utils.info(TOOL, "%d control(s) on %s%s." % (moved, switch, "; left alone (driven already): " + ", ".join(
        naming.short_name(x) for x in skipped[:6]) if skipped else ""))


def vis_face_here(*_):
    from gus_rigtool.core import vis_switch as VS
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if len(sel) != 1:
        raise RuntimeError("select the one control the face's switches go on (e.g. Face_settings_ctrl).")
    lines, _face = VS.face_plan(sel[0])
    if cmds.confirmDialog(title="Gus_Rigtool - face switches", message="\n".join(lines) + "\n\nNothing moves. "
                          "One undo.", button=["Move", "Cancel"], defaultButton="Move", cancelButton="Cancel",
                          dismissString="Cancel") != "Move":
        return
    got = VS.move_face(sel[0])
    utils.info(TOOL, "face switches on %s: %s%s." % (
        naming.short_name(got["holder"]), ", ".join("%s %d" % kv for kv in got["parts"].items()),
        "; left alone (driven already): " + ", ".join(naming.short_name(x) for x in got["skipped"][:6])
        if got["skipped"] else ""))


def vis_remove_hand(*_):
    from gus_rigtool.core import connector
    from gus_rigtool.core import vis_switch as VS
    sel = cmds.ls(selection=True, long=True, type="transform") or []
    if not sel:
        raise RuntimeError("select the controls with your show / hide attributes (e.g. the wrist gears).")
    only = connector.channel_box_attrs() or None
    found = [(c, a, d) for c in sel for a, d in VS.hand_switches(c, only)]
    if not found:
        raise RuntimeError("no show / hide attributes of yours on the selected controls%s." % (
            " among the ones picked in the Channel Box" if only else ""))
    msg = "\n".join("%s.%s  (shows / hides %d)" % (naming.short_name(c), a, len(d)) for c, a, d in found[:25])
    if len(found) > 25:
        msg += "\n... and %d more" % (len(found) - 25)
    if cmds.confirmDialog(title="Gus_Rigtool - remove visibility switches", message=msg + "\n\nWhat they hid is "
                          "shown again; empty headings go too. One undo.", button=["Remove", "Cancel"],
                          defaultButton="Remove", cancelButton="Cancel", dismissString="Cancel") != "Remove":
        return
    done = VS.remove_hand_switches(sel, only)
    utils.info(TOOL, "removed %d switch(es)%s." % (
        len([x for x in done if x[2]]), " and %d empty heading(s)" % len([x for x in done if not x[2]])
        if any(not x[2] for x in done) else ""))


def make_scalable(*_):
    from gus_rigtool.core import scale_check as SC
    got = SC.make_scalable()
    if got["undone"]:
        utils.warn(TOOL, "undone - %s (%s). Nothing changed." % (got.get("why") or "it would have changed the rig at "
                                                                 "rest", got["undone"]))
        return
    after = got.get("after") or 0
    utils.info(TOOL, "the rig scales: %d constraint target(s), %d follicle(s), %d control group(s), %d limb group(s), "
               "%d IK length(s), %d joint(s) given the scale, %d joint(s) no longer scaled twice. Scale check x2: %d "
               "off before, %s." % (got.get("targets", 0), got["follicles"], got.get("groups", 0), got.get("limbs", 0),
                                    got["rest"], got["joints"], got.get("twice", 0), got.get("before") or 0,
                                    "everything grows with it now" if not after else
                                    "%d still off - Check this scene > Scale" % after))


def _advanced_part(s):
    """Keep when rebuilding, Custom steps, Naming, Templates (the Build tab's '4 Advanced' page)."""
    ui.section("Keep when rebuilding", collapse=False, help_text="Keep the skin: the weights are saved before joints are deleted "
               "and put back after the build. Keep shapes: control shapes you changed come back after a rebuild.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 80), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Joint size")
    cmds.floatField(N("Radius"), value=float(s["joint_radius"]), minValue=0.01, maxValue=1000000.0, step=0.01, precision=2,
                    changeCommand=_w(_save_main))
    cmds.setParent("..")
    cmds.checkBox(N("KeepSkin"), label="Keep the skin", value=s.get("keep_skin", True), changeCommand=_w(_save_main),
                  annotation="Back to guides / Build picked save the weights of every skinned mesh and unbind "
                             "it; the next build skins it again to the joints with the same names.")
    cmds.checkBox(N("KeepBound"), label="   ...keep it bound (no unbind: faster, the deformer order stays)",
                  value=s.get("keep_skin_bound", False), changeCommand=_w(_save_main),
                  annotation="The skin stays on the mesh: while the joints are rebuilt, hidden locators hold their "
                             "places; the new joints (same names) take them back with their new bind position. "
                             "Blendshapes and other deformers keep their order. A joint that isn't made again "
                             "leaves its weights on its locator (the log says which).")
    cmds.checkBox(N("KeepData"), label="Keep my attributes and space switches", value=s.get("keep_rig_data", True),
                  changeCommand=_w(_save_main),
                  annotation="Attributes you added to the module's controls and switches made with the Spaces tool "
                             "are made again after the rebuild (before your hook-ups come back).")
    cmds.checkBox(N("OnTop"), label="Controls in front of the mesh (not the face's)",
                  value=s.get("controls_on_top", True), changeCommand=_w(_save_main),
                  annotation="Maya's Always Draw On Top on the body controls, so the ones inside the body are "
                             "always seen. Make controls page: on / off for every control later.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 2)])
    cmds.checkBox(N("KeepShapes"), label="Keep the shapes I changed", width=1,
                  value=s.get("keep_shapes", True), changeCommand=_w(_save_main),
                  annotation="Change a control's shape (Shapes tab) on the built rig: Build picked and Back "
                             "to guides + Build put your shape back instead of the default one.")
    cmds.button(label="Forget (picked)", command=_w(_guard(forget_shapes)),
                annotation="The modules picked in the list go back to their default control shapes at the "
                           "next Build picked / Build.")
    cmds.setParent("..")
    cmds.text(label="Rig data file: shapes, colours, your attributes, driven keys, space switches (by name).",
              align="left", font="smallPlainLabelFont")
    ui.row(2, 170)
    cmds.button(label="Export rig data...", command=_w(_guard(export_rig_data)),
                annotation="The selected controls (or every rig control) to a .json file.")
    cmds.button(label="Import rig data...", command=_w(_guard(import_rig_data)),
                annotation="Put a rig data file back on the rig: matched by control name; driven keys from the "
                           "same driver are replaced.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Custom steps (your scripts, every build)", collapse=False,
               help_text="Your own Python scripts that run by themselves before (pre) or after (post) every "
               "Build / Build picked - so your extra work (set driven keys, constraints, attributes...) comes "
               "back on every rebuild. Saved in the scene. A script gets cmds, when, modules (the ids being "
               "built) and rig (the rig groups). A failing script is reported and never stops the build.")
    cmds.textScrollList(N("Steps"), height=70, annotation="The scripts, in the order they run.")
    ui.row(3, 113)
    cmds.button(label="Add pre...", command=_w(_guard(lambda *_: step_add("pre"))),
                annotation="A script that runs before the build.")
    cmds.button(label="Add post...", command=_w(_guard(lambda *_: step_add("post"))),
                annotation="A script that runs after the build (most of them).")
    cmds.button(label="Run picked now", command=_w(_guard(step_run)), annotation="Try the picked script now.")
    cmds.setParent("..")
    ui.row(4, 85)
    cmds.button(label="On / off", command=_w(_guard(step_toggle)))
    cmds.button(label="Up", command=_w(_guard(lambda *_: step_move(-1))))
    cmds.button(label="Down", command=_w(_guard(lambda *_: step_move(1))))
    cmds.button(label="Remove", command=_w(_guard(step_remove)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Naming", collapse=False,
               help_text="How every name is made. {side} comes from your naming pairs (Mirror tab), {part} is the "
                         "part name from the module settings, {type} the suffix. Preview lists every name the "
                         "build will make and warns about names that already exist.")
    _naming_rows()
    ui.row(3, 113)
    cmds.button(label="Save naming", command=_w(_guard(save_naming)))
    cmds.button(label="Reset naming", command=_w(_guard(reset_naming)))
    cmds.button(label="Preview names", command=_w(_guard(show_preview)))
    cmds.setParent("..")
    cmds.scrollField(N("Preview"), editable=False, height=130, wordWrap=False, text="Press Preview names.")
    ui.end_section()

    ui.section("Templates", collapse=False, help_text="Save the guides, every module's settings and your naming to "
               "a file, to start another character from it (or share it).")
    ui.row(2, 170)
    cmds.button(label="Save template...", command=_w(_guard(save_template)))
    cmds.button(label="Load template...", command=_w(_guard(load_template)))
    cmds.setParent("..")
    ui.end_section()


def build_rig_panel(prefix="p_build_rig_"):
    """The Build part on its own (Pop out): its own module list, then Build / Publish / Keep / Naming /
    Templates. Works with the main window closed."""
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)
    _list_section(height=120, extra_buttons=False)
    _build_part(s, pop=False)
    refresh_list()


def build(prefix="p_build_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()                  # Chain 'from selection' keeps your click order
    ui.status_light(N("Light"), _light, _w)
    tabs = cmds.tabLayout(N("Tabs"), innerMarginWidth=4, innerMarginHeight=4)

    # ---------------------------------------------------------------- 1 Rig builder (list, settings, build)
    p1 = _page()
    has = bool(guides.module_groups())
    ui.section("Start: template or add a module", collapse=has,
               help_text="Template - Biped: root, spine, neck, face, arms, legs, fingers. Quadruped: root, "
               "horizontal ribbon spine, neck, face, tail, front and back legs (nose towards +Z). Character height "
               "(the head's height for a quadruped) sizes the guides.\n\nAdd a module: pick a kind, a side and "
               "(optional) a name, then Add. It is placed at the guide it hangs from. Chain (tail, ear, antenna...) "
               "asks where its guides start: a straight line, the selection or a curve. Fingers on a quadruped "
               "(no arm) hang from the front paw.")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(105, 60, 85, 100),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Character height")
    cmds.floatField(N("Height"), value=float(s["height"]), minValue=1.0, maxValue=1000000.0, step=0.01, precision=1, changeCommand=_w(_save_main),
                    annotation="Maya units (cm by default). Sizes new guides and controls.")
    cmds.button(label="Biped", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(biped)),
                annotation="Biped template: root, spine, neck, face, both arms, legs and fingers.")
    cmds.button(label="Quadruped", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(quadruped)),
                annotation="Quadruped template: root, horizontal ribbon spine, neck, face, tail, front and back "
                           "legs. Height = the head's height; the nose points to +Z.")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(170, 120), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Quadruped animal")
    cmds.optionMenu(N("Animal"), annotation="Proportions and counts of the Quadruped template: dog (paws, 4 toes), "
                    "horse (long legs, hooves - no toes, long neck), cat (long tail), rabbit (low, short tail).")
    for a_ in bld.ANIMAL_NAMES:
        cmds.menuItem(label=a_)
    animal = s.get("animal", "dog")
    cmds.optionMenu(N("Animal"), edit=True, select=bld.ANIMAL_NAMES.index(animal) + 1 if animal in bld.ANIMAL_NAMES
                    else 1)
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(130, 45, 95, 60), adjustableColumn=3,
                   columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.optionMenu(N("AddType"), annotation="What to add.")
    for t in modules.ORDER:
        cmds.menuItem(label=modules.MODULES[t].LABEL)
    cmds.optionMenu(N("AddSide"), annotation="C centre, L left, R right.")
    for side in "CLR":
        cmds.menuItem(label=side)
    cmds.textField(N("AddName"), placeholderText="name (optional)",
                   annotation="Module name, e.g. arm. Use another name for a second one (e.g. arm2).")
    cmds.button(label="Add", command=_w(_guard(add)))
    cmds.setParent("..")
    ui.end_section()

    _list_section()

    ui.section("Guides", collapse=False,
               help_text="Linked: moving a guide moves the ones below it. Free: every guide moves alone. "
               "Move one at a time: Maya's Preserve Children (like D on a joint). Guide names: a label on every "
               "guide in the viewport.")
    cmds.radioButtonGrp(N("GuideMode"), label="Guides", numberOfRadioButtons=2,
                        labelArray2=["Linked (children follow)", "Free (each alone)"],
                        select=1 if s.get("guide_mode", "linked") == "linked" else 2,
                        columnWidth3=(60, 160, 130), changeCommand=_w(_guard(set_guide_mode)),
                        annotation="Linked: moving the humerus guide moves the arm below it. Free: every guide "
                                   "moves alone. Nothing moves when you switch.")
    cmds.checkBox(N("MoveAlone"), label="Move one guide at a time (children stay)",
                  value=quick.is_move_alone(), changeCommand=_w(set_move_alone),
                  annotation="Maya's Preserve Children for the Move / Rotate tools. Turned off by Build. "
                             "Also on the shelf: Move alone.")
    cmds.checkBox(N("GuideNames"), label="Show guide names in the viewport", value=s.get("guide_names", False),
                  changeCommand=_w(_guard(toggle_guide_names)),
                  annotation="A label on every guide (femur, toeA_01...). Turn it off before you render.")
    cmds.button(label="Guides from the rig", command=_w(_guard(guides_from_rig)),
                annotation="With the rig built: every guide goes onto its joint (and the foot / paw pivots onto "
                           "their pivots) - for guides that got moved or zeroed after building.")
    ui.end_section()

    ui.section("Settings of the picked module", help_text="Change, then Apply (updates the guides). Build picked "
               "puts it on the rig. Greyed = doesn't apply with the current choices.")
    cmds.columnLayout(N("Form"), adjustableColumn=True, rowSpacing=3)
    cmds.setParent("..")
    ui.end_section()

    _build_part(s, advanced=False)
    cmds.setParent(tabs)

    # ---------------------------------------------------------------- 2 Animation
    p4 = _page()
    ui.section("IK / FK switch", help_text="Select any control of a limb or chain (FK, IK, pole vector, tweak or "
               "settings). To FK: FK takes the IK pose. To IK: IK takes the FK pose. No jump. Chains: FK is exact; "
               "IK matches exactly at the IK controls.")
    ui.row(2, 170)
    cmds.button(label="Switch to FK (match)", command=_w(_guard(lambda *_: limb.match_selected("fk"))))
    cmds.button(label="Switch to IK (match)", command=_w(_guard(lambda *_: limb.match_selected("ik"))))
    cmds.setParent("..")
    ui.end_section()
    ui.section("Animator tools (Gus Animtool)", help_text="Gus Animtool: picker, pose library, tween slider, key "
               "tools, IK/FK, spaces - for any rig. Open: installs it in your maya/scripts folder with your naming "
               "(or updates it) and opens it. Make: saves it with its installer to a folder, for animators who "
               "don't have Gus_Rigtool.")
    ui.main_button("Open Gus Animtool", _w(_guard(open_anim_tools)),
                   "Install / update it in your maya/scripts folder and open it.")
    cmds.button(label="Make animator tools (folder)...", command=_w(_guard(make_anim_tools)),
                annotation="Save Gus Animtool and its installer to a folder.")
    ui.end_section()
    cmds.setParent(tabs)

    p5 = _page()
    _existing_page()
    cmds.setParent(tabs)

    p6 = _page()
    cmds.text(label="  Settings you set once: what a rebuild keeps, your own build steps, naming, templates.",
              align="left", font="smallPlainLabelFont")
    _advanced_part(s)
    cmds.setParent(tabs)

    cmds.tabLayout(tabs, edit=True, tabLabel=[(p1, "1 Rig builder"), (p4, "2 Animation"), (p5, "3 Existing rig"),
                                              (p6, "4 Advanced")])
    index = int(s.get("sub_page2", 1) or 1)
    if 1 <= index <= 4:
        cmds.tabLayout(tabs, edit=True, selectTabIndex=index)
    cmds.tabLayout(tabs, edit=True, changeCommand=_w(lambda *_: ui.flush_shown() or utils.update_setting(
        SETTINGS_KEY, "sub_page2", cmds.tabLayout(N("Tabs"), query=True, selectTabIndex=True))))
    cmds.setParent("..")
    refresh_list()


def show():
    ui.open_panel("build")


SCHEMA = [
    ("height", "Character height", "float", None),
    ("joint_radius", "Joint size", "float", None),
    ("keep_skin", "Keep the skin on Back to guides / Rebuild", "bool", None),
    ("keep_shapes", "Keep the control shapes you changed on Rebuild / Build", "bool", None),
    ("guide_mode", "Guides: linked / free", "text", None),
]


# names used by scripts made with earlier versions
apply_form = build_form.apply
apply_common = build_form.apply_common
reset_form = build_form.reset
_read_form = build_form.read


# the Existing rig page lives in tools/build_existing (4.2.0); its names are still reachable from here
from gus_rigtool.tools import build_existing as _bx  # noqa: E402
from gus_rigtool.tools.build_existing import _existing_page  # noqa: E402


def _take_existing_names():
    g = globals()
    for name, value in vars(_bx).items():
        if not name.startswith("__") and name not in g:
            g[name] = value


_take_existing_names()
