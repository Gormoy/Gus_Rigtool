"""
Mirror tool: shapes, full controls and joints, from one side to the other.

    import gus_rigtool.main as gr; gr.show()                  (Mirror tab)
    import gus_rigtool.tools.mirror_tool as mt; mt.show()     (own window)

Modes
  Shapes        the other-side controls already exist: their shapes become the
                mirror of the selected ones (CVs only).
  Full control  creates (or updates) the other-side control with its offset groups,
                shape, channel values, custom attributes and locked / hidden channels.
                  True mirror      : like the Ribbon Rig Builder. The same values move both
                                     sides as mirror images (translate and rotate). The top
                                     offset group gets a negative scale.
                  Behavior         : no negative scale. Rotations mirror; translate values
                                     are opposite (R = -L).
                  Same orientation : moved across, same axes as the source.
  Joints        mirrors joint chains, Behavior or Orientation, like Edit > Mirror Joint,
                with update-existing, custom mirror centre, labels, clean-up and colours.

Names: every (left, right) pair that matches is swapped, both ways, so you can select
either side. Names with no side (centre) are skipped.

4.1.0
  Mode bar      : one row at the top - Shapes, Full control, Joints, Geometry, Pose, Links, Skin - opens that
                  part and folds the others.
  List pairs    : every pair the Mirror button will make (new / update / skipped / no twin), before mirroring.
  Links         : custom attribute values, follows, space switches, constraints and pivots onto the twins.
"""

import maya.cmds as cmds

from gus_rigtool.core import colors, naming, sides, ui, utils
from gus_rigtool.core import mirror_engine as engine
from gus_rigtool.core import skin_mirror

TOOL = "Mirror"
SETTINGS_KEY = "mirror"

_P, N, _w, _guard = ui.tool_helpers("p_mirror_", TOOL)


from gus_rigtool.core import mirror_ops as _ops  # noqa: E402
from gus_rigtool.core.mirror_ops import (  # noqa: E402,F401  (the mirror operations, 4.2.0)
    CTRL_ORIENT, GEO_ORIENT, JNT_ORIENT, MODES, PARENT_RULES, PLANES, PREDICATES, PRESETS, UNGROUPED, _pairs,
    _plan, _plane, is_ctrl, resolve, run_full, run_geo, run_joints, run_shapes, why_not)


def _take_ops_names():
    """Every other name of the operations is still reachable as mirror_tool.<name> (older scripts)."""
    g = globals()
    for name, value in vars(_ops).items():
        if not name.startswith("__") and name not in g:
            g[name] = value


_take_ops_names()

DEFAULTS = {
    "mode": 2,                      # 1 shapes, 2 full control, 3 joints
    "ctrl_orient": 1,               # index in CTRL_ORIENT (1-based)
    "jnt_orient": 1,                # index in JNT_ORIENT (1-based)
    "geo_orient": 1,                # index in GEO_ORIENT (1-based)
    "ungrouped": 1,                 # index in UNGROUPED (1-based)
    "copy_materials": True,
    "plane": 1,                     # index in PLANES (1-based)
    "preset": 1,
    "search": "L_",
    "replace": "R_",
    "children": True,
    "rename_source": False,
    # advanced
    "tolerance": 0.01,
    "center_mode": 1,               # 1 world origin, 2 custom
    "center": [0.0, 0.0, 0.0],
    "search2": "",
    "replace2": "",
    "update_existing": True,
    "keep_skin": True,
    "parent_rule": 1,
    "clean_rotate": True,
    "round_tiny": True,
    "labels": False,
    "copy_look": True,
    "side_colors": False,
    "copy_attrs": True,
    "copy_locks": True,
    "copy_values": True,
    # pose
    "pose_centre": True,            # centre controls are mirrored onto themselves
    "pose_custom": True,            # custom attributes are copied by Mirror / Flip pose
    "anim_mode": 1,                 # mirror animation: 1 L>R, 2 R>L, 3 flip
    "anim_offset": 0,               # frames added to every mirrored key (half a cycle for walks)
    "anim_keys_only": True,         # only at the source's keys (else every frame)
    "anim_wrap": False,             # keys past the end wrap to the start (cycles)
    # skin weights
    "skin_direction": 1,            # 1 L -> R, 2 R -> L
    "skin_closest": False,          # joints whose names don't pair: closest joint
}

def _ui():
    o = {
        "mode": cmds.radioButtonGrp(N("Mode"), query=True, select=True),
        "ctrl_orient": cmds.radioButtonGrp(N("CtrlOrient"), query=True, select=True),
        "jnt_orient": cmds.radioButtonGrp(N("JntOrient"), query=True, select=True),
        "geo_orient": cmds.radioButtonGrp(N("GeoOrient"), query=True, select=True),
        "ungrouped": cmds.radioButtonGrp(N("Ungrouped"), query=True, select=True),
        "plane": cmds.radioButtonGrp(N("Plane"), query=True, select=True),
        "preset": cmds.optionMenu(N("Preset"), query=True, select=True),
        "search": cmds.textField(N("Search"), query=True, text=True).strip(),
        "replace": cmds.textField(N("Replace"), query=True, text=True).strip(),
        "children": cmds.checkBox(N("Children"), query=True, value=True),
        "center_mode": cmds.radioButtonGrp(N("CenterMode"), query=True, select=True),
        "center": cmds.floatFieldGrp(N("Center"), query=True, value=True)[:3],
        "search2": cmds.textField(N("Search2"), query=True, text=True).strip(),
        "replace2": cmds.textField(N("Replace2"), query=True, text=True).strip(),
        "parent_rule": cmds.optionMenu(N("ParentRule"), query=True, select=True),
        "tolerance": cmds.floatField(N("Tolerance"), query=True, value=True),
    }
    if cmds.radioButtonGrp(N("SkinDir"), exists=True):
        o["skin_direction"] = cmds.radioButtonGrp(N("SkinDir"), query=True, select=True)
    if cmds.optionMenu(N("AnimMode"), exists=True):
        o["anim_mode"] = cmds.optionMenu(N("AnimMode"), query=True, select=True)
        o["anim_offset"] = cmds.intField(N("AnimOffset"), query=True, value=True)
    for key in ("pose_centre", "pose_custom", "skin_closest", "anim_keys_only", "anim_wrap"):
        if cmds.checkBox(N("_") + key, exists=True):
            o[key] = cmds.checkBox(N("_") + key, query=True, value=True)
    for key in ("copy_materials", "rename_source", "update_existing", "keep_skin", "clean_rotate", "round_tiny", "labels",
                "copy_look", "side_colors", "copy_attrs", "copy_locks", "copy_values"):
        o[key] = cmds.checkBox(N("_") + key, query=True, value=True)
    return o


def _light():
    mode = cmds.radioButtonGrp(N("Mode"), query=True, select=True)
    sel = utils.selected_transforms(ordered=False)
    if not sel:
        return "warn", "Select what to mirror (%s mode)." % MODES[mode - 1]
    if ui.too_many(len(sel)):
        return "ok", "%d objects selected (too many to check here)." % len(sel)
    nodes, unused = resolve(sel, PREDICATES.get(mode, is_ctrl), False)
    if not nodes:
        return "warn", "%s %s." % (naming.short_name(unused[0]), why_not(unused[0], mode))
    return "ok", "%s mode: %d to mirror. Check the preview, then Mirror." % (MODES[mode - 1], len(nodes))


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _on_change(*_):
    try:
        mode = cmds.radioButtonGrp(N("Mode"), query=True, select=True)
        cmds.radioButtonGrp(N("CtrlOrient"), edit=True, manage=mode == 2)
        cmds.radioButtonGrp(N("JntOrient"), edit=True, manage=mode == 3)
        cmds.radioButtonGrp(N("GeoOrient"), edit=True, manage=mode == 4)
        cmds.radioButtonGrp(N("Ungrouped"), edit=True, manage=mode == 2)
        cmds.columnLayout(N("OptCtrl"), edit=True, manage=mode in (1, 2))
        cmds.columnLayout(N("OptJnt"), edit=True, manage=mode == 3)
        cmds.columnLayout(N("OptGeo"), edit=True, manage=mode == 4)
        cmds.checkBox(N("_keep_skin"), edit=True, manage=mode == 3)
        cmds.floatFieldGrp(N("Center"), edit=True,
                           enable=cmds.radioButtonGrp(N("CenterMode"), query=True, select=True) == 2)
        _paint_bar("mode", mode)
    except RuntimeError:
        return
    _save()
    preview()
    ui.refresh_light(N("Light"))


def _on_preset(*_):
    index = cmds.optionMenu(N("Preset"), query=True, select=True)
    _name, a, b = PRESETS[index - 1]
    if a is not None:
        cmds.textField(N("Search"), edit=True, text=a)
        cmds.textField(N("Replace"), edit=True, text=b)
    _on_change()


def _on_typed(*_):
    a = cmds.textField(N("Search"), query=True, text=True)
    b = cmds.textField(N("Replace"), query=True, text=True)
    index = len(PRESETS)
    for i, (_l, pa, pb) in enumerate(PRESETS):
        if (pa, pb) == (a, b):
            index = i + 1
    cmds.optionMenu(N("Preset"), edit=True, select=index)
    _on_change()


def preview(*_):
    """Show what the current selection would become."""
    if not cmds.text(N("Preview"), exists=True):
        return
    try:
        o = _ui()
    except RuntimeError:
        return
    selection = utils.selected_transforms(ordered=False)
    nodes, unused = resolve(selection, PREDICATES.get(o["mode"], is_ctrl), o["children"])
    if not nodes:
        if not selection:
            cmds.text(N("Preview"), edit=True, label="Select what to mirror.")
        else:
            cmds.text(N("Preview"), edit=True, label="\n".join(
                "%s %s" % (naming.short_name(n), why_not(n, o["mode"])) for n in unused[:4]))
        return
    lines = []
    for n in nodes[:4]:
        short = naming.short_name(n)
        pl = _plan(n, o)
        if pl is None:
            lines.append("%s  (centre, skipped)" % short)
            continue
        if o["mode"] == 1:
            state = "exists" if pl["existing"] else "missing, skipped"
        elif pl["existing"]:
            state = "exists, will update" if o["update_existing"] else "exists, skipped"
        else:
            state = "new"
        left = short
        if pl.get("rename_to"):
            left = "%s -> %s (renamed)" % (short, pl["rename_to"])
        lines.append("%s  ->  %s  (%s)" % (left, naming.short_name(pl["target_name"]), state))
    if len(nodes) > 4:
        lines.append("... and %d more" % (len(nodes) - 4))
    if len(nodes) > 1:
        new, update, skip = _count(o, nodes)
        lines.append("In all: %d new, %d update, %d skipped - 'List pairs' shows every one." % (new, update, skip))
    cmds.text(N("Preview"), edit=True, label="\n".join(lines))


def run(*_):
    o = _ui()
    _save()
    if not o["search"] or not o["replace"]:
        utils.warn(TOOL, "fill in both naming fields (e.g. L_ and R_).")
        return
    selection = utils.selected_transforms()
    if not selection:
        utils.warn(TOOL, "select what to mirror first.")
        return
    nodes, unused = resolve(selection, PREDICATES.get(o["mode"], is_ctrl), o["children"])
    if not nodes:
        reasons = ["'%s' %s" % (naming.short_name(n), why_not(n, o["mode"])) for n in unused[:3]]
        utils.warn(TOOL, "nothing to mirror in %s mode: %s." % (MODES[o["mode"] - 1], "; ".join(reasons)))
        return
    with utils.undo_chunk("gusrigMirror"):
        if o["mode"] == 1:
            msg, skipped = run_shapes(o)
        elif o["mode"] == 2:
            msg, skipped = run_full(o)
        elif o["mode"] == 3:
            msg, skipped = run_joints(o)
        else:
            msg, skipped = run_geo(o)
    if skipped:
        utils.warn(TOOL, "%s. Skipped %d: %s" % (msg, len(skipped), ", ".join(skipped[:6])
                                                + (" ..." if len(skipped) > 6 else "")))
    else:
        utils.info(TOOL, msg + ".")
    preview()


def _scene_sources(o, side):
    """Every node of the current mode in the scene whose name is on side ('L' or 'R')."""
    pred = PREDICATES.get(o["mode"], is_ctrl)
    pairs = _pairs(o)
    out = []
    for n in cmds.ls(type="transform", long=True) or []:
        if naming.side_of(n, pairs) == side and pred(n):
            out.append(n)
    return out


def _count(o, nodes):
    new = update = skip = 0
    for n in nodes:
        pl = _plan(n, o)
        if pl is None or pl.get("ambiguous"):
            skip += 1
        elif pl["existing"]:
            if o["mode"] == 1 or o["update_existing"]:
                update += 1
            else:
                skip += 1
        elif o["mode"] == 1:
            skip += 1
        else:
            new += 1
    return new, update, skip


def run_all(*_):
    """Mirror every node of the current mode in the scene, after a preview of what will happen."""
    o = _ui()
    _save()
    if not o["search"] or not o["replace"]:
        utils.warn(TOOL, "fill in both naming fields (e.g. L_ and R_).")
        return
    left, right = _scene_sources(o, "L"), _scene_sources(o, "R")
    if not left and not right:
        utils.warn(TOOL, "nothing named with '%s' or '%s' in %s mode." % (o["search"], o["replace"],
                                                                          MODES[o["mode"] - 1]))
        return
    lines = []
    for label, nodes in (("%s  ->  %s" % (o["search"], o["replace"]), left),
                         ("%s  ->  %s" % (o["replace"], o["search"]), right)):
        new, update, skip = _count(o, nodes)
        lines.append("%s :   %d found  -  %d new, %d updated, %d skipped" % (label, len(nodes), new, update, skip))
    answer = cmds.confirmDialog(
        title="Mirror whole scene (%s)" % MODES[o["mode"] - 1],
        message="%s mode, every %s in the scene:\n\n%s\n\nUpdated = moved / reshaped, never duplicated. "
                "One undo." % (MODES[o["mode"] - 1], {1: "control shape", 2: "control", 3: "joint",
                                                      4: "mesh"}[o["mode"]], "\n".join(lines)),
        button=["%s -> %s" % (o["search"], o["replace"]), "%s -> %s" % (o["replace"], o["search"]), "Cancel"],
        defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel")
    if answer == "Cancel":
        return
    sources = left if answer.startswith(o["search"] + " ") else right
    if not sources:
        utils.warn(TOOL, "nothing on that side.")
        return
    selection = cmds.ls(selection=True, long=True) or []
    o = dict(o, children=False)
    with utils.undo_chunk("gusrigMirrorAll"):
        cmds.select(sources, replace=True)
        msg, skipped = {1: run_shapes, 2: run_full, 3: run_joints, 4: run_geo}[o["mode"]](o) or (None, [])
        if selection:
            cmds.select([n for n in selection if cmds.objExists(n)], replace=True)
        else:
            cmds.select(clear=True)
    if skipped:
        utils.warn(TOOL, "whole scene: %s. Skipped %d: %s" % (msg, len(skipped), ", ".join(skipped[:6])
                                                             + (" ..." if len(skipped) > 6 else "")))
    else:
        utils.info(TOOL, "whole scene: %s." % msg)
    preview()


# ===========================================================================
# pose and twins
# ===========================================================================

def _engine(fn, *args, **kwargs):
    def run(*_):
        _save()
        try:
            fn(*args, **kwargs)
        except RuntimeError as e:
            utils.warn(TOOL, str(e).strip())
        twins_refresh()
    return run


def _has_time():
    try:
        engine.playback_range()
        return True
    except Exception:
        return False


def _anim_range_from_slider(*_):
    start, end = engine.playback_range()
    cmds.intField(N("AnimStart"), edit=True, value=start)
    cmds.intField(N("AnimEnd"), edit=True, value=end)


def mirror_animation(*_):
    o = _ui()
    start = cmds.intField(N("AnimStart"), query=True, value=True)
    end = cmds.intField(N("AnimEnd"), query=True, value=True)
    mode = ["L>R", "R>L", "flip"][int(o.get("anim_mode", 1)) - 1]
    engine.mirror_animation(mode, start, end, int(o.get("anim_offset", 0)), bool(o.get("anim_keys_only", True)),
                            bool(o.get("anim_wrap", False)))


def twins_refresh(*_):
    """Fill the twin list from the selection (and below), or the whole scene."""
    if not cmds.textScrollList(N("TwinList"), exists=True):
        return
    scope = cmds.radioButtonGrp(N("TwinScope"), query=True, select=True)
    if scope == 2:
        nodes = cmds.ls(type="transform", long=True) or []
    else:
        nodes = []
        for n in utils.selected_transforms(ordered=False):
            nodes.append(n)
            nodes += cmds.listRelatives(n, allDescendents=True, type="transform", fullPath=True) or []
    if ui.too_many(len(nodes)):
        cmds.textScrollList(N("TwinList"), edit=True, removeAll=True,
                            append=["(%d objects: too many to list here)" % len(nodes)])
        return
    rows = engine.list_twins(list(dict.fromkeys(nodes)))
    _twin_rows[_P["p"]] = rows
    labels = []
    for a, b, style in rows:
        if b:
            labels.append("%s   <->   %s%s" % (naming.short_name(a), naming.short_name(b),
                                               "   (%s)" % style if style else ""))
        else:
            labels.append("%s   (no twin)" % naming.short_name(a))
    missing = len([r for r in rows if not r[1]])
    cmds.textScrollList(N("TwinList"), edit=True, removeAll=True,
                        append=labels or ["(nothing with a side here)"])
    cmds.text(N("TwinInfo"), edit=True,
              label="%d pair(s), %d without a twin." % (len(rows) - missing, missing) if rows else
              "Select controls / joints (or choose Scene), then Refresh.")


_twin_rows = {}


def _twin_pick(*_):
    picked = cmds.textScrollList(N("TwinList"), query=True, selectIndexedItem=True) or []
    rows = _twin_rows.get(_P["p"], [])
    nodes = []
    for i in picked:
        if i - 1 < len(rows):
            nodes += [n for n in rows[i - 1][:2] if n and cmds.objExists(n)]
    if nodes:
        cmds.select(nodes, replace=True)


def twins_link(*_):
    sel = utils.selected_transforms(ordered=True)
    if len(sel) != 2:
        utils.warn(TOOL, "select exactly two objects to link as twins (left first).")
        return
    with utils.undo_chunk("gusrigLinkTwins"):
        engine.unlink(sel[0])
        engine.unlink(sel[1])
        engine.link(sel[0], sel[1])
    utils.info(TOOL, "linked %s and %s as twins." % (naming.short_name(sel[0]), naming.short_name(sel[1])))
    twins_refresh()


def twins_fix(scope="selection"):
    """Relink twins whose link disagrees with their mirrored name; a report lists what changed."""
    nodes = None
    if scope == "selection":
        sel = utils.selected_transforms()
        if not sel:
            utils.warn(TOOL, "select objects first (or use Fix twin links (scene)).")
            return
        nodes = list(sel)
        for n in sel:
            nodes += cmds.listRelatives(n, allDescendents=True, type="transform", fullPath=True) or []
    with utils.undo_chunk("gusrigFixTwins"):
        fixed, left = sides.fix_links(nodes)
    lines = ["Fixed %d twin link(s):" % len(fixed)]
    lines += ["  %s  ->  %s" % (naming.short_name(a), naming.short_name(b)) for a, b in fixed]
    if left:
        lines += ["", "Not fixed - no node has the mirrored name (rename it, or Link 2 selected):"]
        lines += ["  %s  is linked to  %s  (expected: %s)" % (naming.short_name(a), naming.short_name(b), w)
                  for a, b, w in left]
    if fixed or left:
        ui.report_window("Gus_Rigtool - twin links", "\n".join(lines))
    utils.info(TOOL, "fixed %d twin link(s)%s." % (len(fixed), ", %d need a rename" % len(left) if left else ""),
               "warn" if left else "ok")
    twins_refresh()


def twins_unlink(*_):
    sel = utils.selected_transforms()
    if not sel:
        utils.warn(TOOL, "select the objects to unlink.")
        return
    count = 0
    with utils.undo_chunk("gusrigUnlinkTwins"):
        for n in sel:
            if engine.unlink(n):
                count += 1
    utils.info(TOOL, "unlinked %d object(s). Their names still pair them, if they match." % count)
    twins_refresh()


def _skin_report(level, lines):
    if cmds.scrollField(N("SkinReport"), exists=True):
        cmds.scrollField(N("SkinReport"), edit=True, text="\n".join(lines))
    (utils.info if level == "ok" else utils.warn)(TOOL, lines[-1] if lines else "")


def skin_check(*_):
    o = _ui()
    _save()
    try:
        level, lines = skin_mirror.check(axis=_plane(o)[0], pairs=_pairs(o))
    except RuntimeError as e:
        _skin_report("warn", [str(e)])
        return
    _skin_report(level, lines)


def skin_run(*_):
    o = _ui()
    _save()
    if _plane(o)[1] != [0.0, 0.0, 0.0] and o["center_mode"] == 2:
        utils.warn(TOOL, "skin weights always mirror across the world origin (Maya), not the custom centre.")
    try:
        skin_mirror.mirror_weights(direction="L>R" if o["skin_direction"] == 1 else "R>L",
                                   closest_fallback=o["skin_closest"], axis=_plane(o)[0], pairs=_pairs(o))
    except RuntimeError as e:
        _skin_report("warn", [str(e)])
        return
    if cmds.scrollField(N("SkinReport"), exists=True):
        cmds.scrollField(N("SkinReport"), edit=True, text="Done. Undo with Ctrl+Z if it's not what you wanted.")


def apply_side_colors(*_):
    nodes = utils.selected_transforms()
    if not nodes:
        utils.warn(TOOL, "select the controls or joints to colour.")
        return
    pairs = _pairs(_ui())
    with utils.undo_chunk("gusrigSideColors"):
        for n in nodes:
            colors.apply_side_color(n, pairs)
    utils.info(TOOL, "coloured %d node(s) by side." % len(nodes))


def _save_colors(*_):
    colors.save_side_colors({
        "L": list(cmds.colorSliderGrp(N("ColL"), query=True, rgbValue=True)),
        "R": list(cmds.colorSliderGrp(N("ColR"), query=True, rgbValue=True)),
        "C": list(cmds.colorSliderGrp(N("ColC"), query=True, rgbValue=True)),
    })


def _reset_colors(*_):
    for key, ctrl in (("L", N("ColL")), ("R", N("ColR")), ("C", N("ColC"))):
        cmds.colorSliderGrp(ctrl, edit=True, rgb=tuple(colors.DEFAULT_SIDE_COLORS[key]))
    _save_colors()


def _get_center(*_):
    sel = cmds.ls(selection=True, flatten=True) or []
    if not sel:
        utils.warn(TOOL, "select an object or components to read the centre from.")
        return
    comps = [s for s in sel if "." in s]
    if comps:
        flat = cmds.xform(comps, query=True, worldSpace=True, translation=True)
        n = len(flat) // 3
        p = [sum(flat[i::3]) / n for i in range(3)]
    else:
        p = cmds.xform(sel[-1], query=True, worldSpace=True, rotatePivot=True)
    cmds.floatFieldGrp(N("Center"), edit=True, value1=p[0], value2=p[1], value3=p[2])
    cmds.radioButtonGrp(N("CenterMode"), edit=True, select=2)
    _on_change()


_frames = {}
BAR = [("Shapes", "mode", 1), ("Full control", "mode", 2), ("Joints", "mode", 3), ("Geometry", "mode", 4),
       ("Pose", "pose", None), ("Links", "links", None), ("Skin", "skin", None)]


def go(part, mode=None):
    """Open one part of the tool (and set the mode), fold the other parts."""
    frames = _frames.get(_P["p"], {})
    if mode:
        cmds.radioButtonGrp(N("Mode"), edit=True, select=mode)
        _on_change()
    want = "main" if part == "mode" else part
    for key, frame in frames.items():
        try:
            cmds.frameLayout(frame, edit=True, collapse=key != want)
        except RuntimeError:
            pass
    _paint_bar(part, mode or cmds.radioButtonGrp(N("Mode"), query=True, select=True))


def _paint_bar(part, mode):
    for label, p_, m in BAR:
        name = N("Bar_" + label.replace(" ", ""))
        if cmds.button(name, exists=True):
            on = p_ == part and (m is None or m == mode)
            cmds.button(name, edit=True, backgroundColor=ui.MAIN_BG if on else (0.36, 0.36, 0.36))


def pairs_report(o=None, nodes=None):
    """Every pair the Mirror button would make for the selection: (source, target, state)."""
    o = o or _ui()
    if nodes is None:
        nodes, _unused = resolve(utils.selected_transforms(ordered=False), PREDICATES.get(o["mode"], is_ctrl),
                                 o["children"])
    rows = []
    for n in nodes:
        pl = _plan(n, o)
        if pl is None:
            rows.append((n, None, "centre, skipped"))
            continue
        if pl.get("ambiguous"):
            rows.append((n, pl.get("target_name"), "several nodes have that name, skipped"))
            continue
        if o["mode"] == 1:
            state = "exists" if pl["existing"] else "missing - no twin, skipped"
        elif pl["existing"]:
            state = "exists, will update" if o["update_existing"] else "exists, skipped (Update existing is off)"
        else:
            state = "new"
        rows.append((n, pl["target_name"], state))
    return rows


def list_pairs(*_):
    o = _ui()
    rows = pairs_report(o)
    if not rows:
        raise RuntimeError("nothing to mirror in this mode with the selection.")
    lines = ["%s mode, names %s <-> %s%s" % (MODES[o["mode"] - 1], o["search"], o["replace"],
                                             ", children included" if o["children"] else ""), ""]
    for state in ("new", "exists, will update", "exists"):
        got = [r for r in rows if r[2] == state]
        if got:
            lines.append("%s (%d):" % (state, len(got)))
            lines += ["  %s  ->  %s" % (naming.short_name(a), naming.short_name(b)) for a, b, _s in got]
            lines.append("")
    other = [r for r in rows if r[2] not in ("new", "exists, will update", "exists")]
    if other:
        lines.append("Not mirrored (%d):" % len(other))
        lines += ["  %s  ->  %s   (%s)" % (naming.short_name(a), naming.short_name(b) if b else "-", st)
                  for a, b, st in other]
    ui.report_window("Gus_Rigtool - mirror pairs", "\n".join(lines))
    return rows


def mirror_setup(*_):
    from gus_rigtool.core import mirror_setup as MS
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        raise RuntimeError("select the controls (or nodes) your setup starts from, on one side.")
    text = MS.preview(sel)
    if cmds.confirmDialog(title="Mirror a setup", message=text, button=["Mirror it", "Cancel"],
                          defaultButton="Mirror it", cancelButton="Cancel", dismissString="Cancel") != "Mirror it":
        return
    MS.run(sel)


def mirror_links(*_):
    from gus_rigtool.core import mirror_links as ML
    sel = utils.selected_transforms()
    if not sel:
        raise RuntimeError("select the controls on the side to copy from.")
    kinds = [k for k in ML.KINDS if cmds.checkBox(N("Link_" + k), query=True, value=True)]
    if not kinds:
        raise RuntimeError("tick at least one thing to mirror.")
    replace = cmds.checkBox(N("LinkReplace"), query=True, value=True)
    orient = cmds.checkBox(N("LinkOrient"), query=True, value=True)
    with utils.undo_chunk("gusrigMirrorLinks"):
        out = ML.run(sel, kinds, replace, orient)
    lines, n_done, n_skip = [], 0, 0
    for k in kinds:
        done, skipped = out[k]
        n_done += len(done)
        n_skip += len(skipped)
        if done or skipped:
            lines.append("%s:" % k.title())
            lines += ["  %s: %s" % (naming.short_name(t), what) for t, what in done]
            lines += ["  skipped %s: %s" % (naming.short_name(n), why) for n, why in skipped]
    msg = "mirrored %d thing(s) onto the twins%s." % (n_done, ", %d skipped" % n_skip if n_skip else "")
    if n_skip:
        ui.report_window("Gus_Rigtool - mirror links", "\n".join(lines))
        utils.warn(TOOL, msg + " See the report.")
    else:
        utils.info(TOOL, msg)
    return out


def reset_defaults(*_):
    utils.save_setting(SETTINGS_KEY, {})
    cmds.evalDeferred(ui.rebuild_open)
    utils.info(TOOL, "settings reset to your defaults (or the Gus_Rigtool defaults).", "info")


def _checkbox(key, label, value, annotation=""):
    cmds.checkBox(N("_") + key, label=label, value=value, annotation=annotation, changeCommand=_w(_on_change))


def build(prefix="p_mirror_"):
    """Content of the Mirror tool, built into the current layout."""
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    utils.track_selection_order()

    # -------------------------------------------------- main
    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    frames = _frames[prefix] = {}
    cmds.gridLayout(numberOfColumns=4, cellWidthHeight=(86, 24))
    for label, part, mode in BAR:
        cmds.button(N("Bar_" + label.replace(" ", "")), label=label,
                    command=_w(lambda *_, p_=part, m=mode: go(p_, m)),
                    annotation="Open the %s part (the others fold)." % label)
    cmds.setParent("..")

    frames["main"] = ui.section("Mirror", step=1, help_text="Shapes: the other-side controls exist, their shapes become the "
               "mirror. Full control: creates or updates the other side (offset groups, values, attributes). "
               "Joints: mirrors chains. Geometry: mirrors meshes. The preview shows what will happen.")
    cmds.radioButtonGrp(N("Mode"), label="Mode", numberOfRadioButtons=4, labelArray4=MODES,
                        select=s["mode"], columnWidth5=(40, 65, 90, 60, 80), changeCommand=_w(_on_change),
                        annotation="Shapes: copy shapes onto existing other-side controls. "
                                   "Full control: create / update the other side. Joints: mirror chains. "
                                   "Geometry: mirror meshes.")
    cmds.radioButtonGrp(N("CtrlOrient"), label="Orientation", numberOfRadioButtons=3,
                        labelArray3=CTRL_ORIENT, select=s["ctrl_orient"],
                        columnWidth4=(70, 95, 75, 120), changeCommand=_w(_on_change),
                        annotation="True mirror: same values = mirrored motion (negative scale on the "
                                   "top offset). Behavior: no negative scale, translate values opposite. "
                                   "Same orientation: just moved across.")
    cmds.radioButtonGrp(N("JntOrient"), label="Orientation", numberOfRadioButtons=2,
                        labelArray2=JNT_ORIENT, select=s["jnt_orient"],
                        columnWidth3=(70, 90, 90), changeCommand=_w(_on_change),
                        annotation="Behavior: same rotate values = mirrored motion. "
                                   "Orientation: same world orientation as the source.")
    cmds.radioButtonGrp(N("Ungrouped"), label="No group", numberOfRadioButtons=3,
                        labelArray3=UNGROUPED, select=s["ungrouped"],
                        columnWidth4=(70, 70, 130, 100), changeCommand=_w(_on_change),
                        annotation="Controls without an offset group (e.g. frozen curves). Baked: clean "
                                   "transform, mirrored CVs. Add offset groups: makes _offset groups, then "
                                   "mirrors through them (same values = mirrored motion). Like grouped: "
                                   "uses the Orientation above on the control itself.")
    cmds.radioButtonGrp(N("GeoOrient"), label="Result", numberOfRadioButtons=4,
                        labelArray4=GEO_ORIENT, select=s["geo_orient"],
                        columnWidth5=(45, 60, 85, 70, 110), changeCommand=_w(_on_change),
                        annotation="Baked: the mirror is in the vertices, clean transform (best for export "
                                   "and skinning). The others mirror the transform, like controls.")
    cmds.radioButtonGrp(N("Plane"), label="Plane", numberOfRadioButtons=3,
                        labelArray3=[p[0] for p in PLANES], select=s["plane"],
                        columnWidth4=(60, 100, 100, 100), changeCommand=_w(_on_change))

    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 120, 80, 80),
                   columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.text(label="Names", align="right")
    cmds.optionMenu(N("Preset"), changeCommand=_w(_on_preset))
    for label, _a, _b in PRESETS:
        cmds.menuItem(label=label)
    cmds.textField(N("Search"), text=s["search"], changeCommand=_w(_on_typed),
                   annotation="Left-side token. Both directions are swapped.")
    cmds.textField(N("Replace"), text=s["replace"], changeCommand=_w(_on_typed),
                   annotation="Right-side token.")
    cmds.setParent("..")
    cmds.optionMenu(N("Preset"), edit=True, select=s["preset"])

    cmds.checkBox(N("Children"), label="Include children (everything under the selection)",
                  value=s["children"], changeCommand=_w(_on_change))
    _checkbox("rename_source", "Names without a side: rename the source too (arm -> L_arm)",
              s["rename_source"], "Side comes from the position: +X = Left, -X = Right. "
              "The copy always gets the other side.")
    cmds.frameLayout(label="Preview", collapsable=False, marginWidth=6, marginHeight=4)
    cmds.text(N("Preview"), label="", align="left")
    cmds.setParent("..")
    ui.main_button("Mirror", _w(run), "Mirror the selection with the settings above. One undo.")
    ui.row(2, 170)
    cmds.button(label="List pairs...", height=24, command=_w(_guard(list_pairs)),
                annotation="Every pair Mirror will make for the selection (new / update / skipped / no twin).")
    cmds.button(label="Mirror whole scene...", height=24, command=_w(run_all),
                annotation="Every control / joint / mesh of this mode named with your side tokens. Shows "
                           "what will be created, updated or skipped, then you pick the direction.")
    cmds.setParent("..")
    ui.end_section()

    # -------------------------------------------------- pose and twins
    frames["pose"] = ui.section("Pose and twins", step=2, collapse=True,
               help_text="Mirror pose: the selected controls' pose goes to their twins, mirrored (works with "
                         "every mirror style). Flip: swaps the two sides. Reset both: back to 0 on both sides. "
                         "Twins: L / R pairs found by link or by name; link two objects by hand when the "
                         "names don't match. Also on the shelf.")
    ui.row(3, 113)
    cmds.button(label="Mirror pose", command=_w(_engine(engine.mirror_pose)),
                annotation="Selected -> their twins. Both sides selected: left -> right.")
    cmds.button(label="Flip pose", command=_w(_engine(engine.flip_pose)),
                annotation="Swap the poses of the two sides.")
    cmds.button(label="Reset both", command=_w(_engine(engine.reset_pose)),
                annotation="Selected controls and their twins back to 0 (scale 1).")
    cmds.setParent("..")
    ui.row(3, 113)
    cmds.button(label="Pose L -> R", command=_w(_engine(engine.mirror_pose, "L>R")),
                annotation="Left side's pose onto the right, whichever side you selected.")
    cmds.button(label="Pose R -> L", command=_w(_engine(engine.mirror_pose, "R>L")),
                annotation="Right side's pose onto the left, whichever side you selected.")
    cmds.button(label="Select twin", command=_w(_engine(engine.select_twins, "other")),
                annotation="Select the other side.")
    cmds.setParent("..")
    ui.row(3, 113)
    cmds.button(label="Live follow L -> R", command=_w(_engine(engine.follow_on, "L>R")),
                annotation="While on, the right twins follow the left controls live, mirrored. The followers "
                           "can't be animated: it's for building and testing poses.")
    cmds.button(label="Live follow R -> L", command=_w(_engine(engine.follow_on, "R>L")),
                annotation="While on, the left twins follow the right controls live, mirrored.")
    cmds.button(label="Live follow off", command=_w(_engine(engine.follow_off, "selection")),
                annotation="Stop live follow for the selection and their twins. The pose stays. "
                           "Right-click the MP shelf button to turn it off in the whole scene.")
    cmds.setParent("..")
    _checkbox("pose_centre", "Centre controls: mirror onto themselves", s["pose_centre"],
              "A centre control (spine, head...) in the selection is mirrored across itself.")
    _checkbox("pose_custom", "Copy custom attributes (same values)", s["pose_custom"])
    cmds.separator(height=6, style="in")
    cmds.text(label="Mirror animation (the selected controls' keys, over a frame range)", align="left",
              font="boldLabelFont")
    cmds.rowLayout(numberOfColumns=6, columnWidth6=(40, 55, 30, 55, 65, 80),
                   columnAttach=[(1, "right", 2), (2, "both", 2), (3, "right", 2), (4, "both", 2), (5, "both", 2),
                                 (6, "both", 2)])
    cmds.text(label="From")
    start, end = engine.playback_range() if _has_time() else (1, 24)
    cmds.intField(N("AnimStart"), value=start, annotation="First frame.")
    cmds.text(label="to")
    cmds.intField(N("AnimEnd"), value=end, annotation="Last frame.")
    cmds.button(label="Time slider", command=_w(_anim_range_from_slider),
                annotation="Take the range from the time slider.")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(40, 90, 60, 60),
                   columnAttach=[(1, "right", 2), (2, "both", 2), (3, "right", 2), (4, "both", 2)])
    cmds.text(label="Mode")
    cmds.optionMenu(N("AnimMode"), changeCommand=_w(_on_change),
                    annotation="L -> R / R -> L: one side's animation onto the other. Flip: the sides swap.")
    for label in ("L -> R", "R -> L", "Flip"):
        cmds.menuItem(label=label)
    cmds.optionMenu(N("AnimMode"), edit=True, select=int(s.get("anim_mode", 1)))
    cmds.text(label="Offset")
    cmds.intField(N("AnimOffset"), value=int(s.get("anim_offset", 0)), changeCommand=_w(_on_change),
                  annotation="Frames added to every mirrored key: half the cycle length for a walk.")
    cmds.setParent("..")
    _checkbox("anim_keys_only", "Only at the keys (else every frame)", s.get("anim_keys_only", True),
              "Keys only where the source side has keys. Off: a key on every frame (baked).")
    _checkbox("anim_wrap", "Keys past the end wrap to the start (cycles)", s.get("anim_wrap", False),
              "For cycles: a key pushed past the last frame by the offset goes back to the start.")
    cmds.button(label="Mirror animation", height=26, command=_w(_engine(mirror_animation)),
                annotation="Replaces the other side's keys in the range (one undo).")
    cmds.separator(height=6, style="in")
    cmds.radioButtonGrp(N("TwinScope"), label="Twins in", numberOfRadioButtons=2,
                        labelArray2=["Selection", "Scene"], select=1, columnWidth3=(60, 80, 80),
                        changeCommand=_w(twins_refresh))
    cmds.textScrollList(N("TwinList"), height=110, allowMultiSelection=True,
                        selectCommand=_w(_twin_pick),
                        annotation="Click a pair to select both. (style) = how the twin was mirrored.")
    cmds.text(N("TwinInfo"), label="", align="left")
    ui.row(3, 113)
    cmds.button(label="Refresh", command=_w(twins_refresh))
    cmds.button(label="Link 2 selected", command=_w(twins_link),
                annotation="Make the two selected objects twins (when their names don't match).")
    cmds.button(label="Unlink", command=_w(twins_unlink),
                annotation="Break the twin link of the selected objects.")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Fix twin links (selection)", command=_w(lambda *_: twins_fix("selection")),
                annotation="Selected objects (and below) whose twin link points to another node than their "
                           "mirrored name (L_ <-> R_) are relinked to that name.")
    cmds.button(label="Fix twin links (scene)", command=_w(lambda *_: twins_fix("scene")),
                annotation="Every twin link in the scene that disagrees with the mirrored name is relinked.")
    cmds.setParent("..")
    ui.end_section()

    # -------------------------------------------------- links
    frames["links"] = ui.section("Links, attributes and pivots", step=3, collapse=True,
                                 help_text="Select controls on one side: their twins get the same custom attribute "
                                 "values, follows (twin driver, or the same centre driver like the jaw; the pivot "
                                 "mirrored), space switches (twin targets), constraints (twin targets, keeping the "
                                 "twin where it is) and pivots. A target with no side is used as it is. Replace: "
                                 "the twin's own follow / switch / constraint is replaced; off: it is skipped.")
    from gus_rigtool.core import mirror_links as ML
    labels = {"attrs": "Custom attribute values", "follows": "Follows", "spaces": "Space switches",
              "constraints": "Constraints", "pivots": "Pivots"}
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(170, 22))
    for k in ML.KINDS:
        cmds.checkBox(N("Link_" + k), label=labels[k], value=k in ("attrs", "follows", "spaces"))
    cmds.setParent("..")
    cmds.checkBox(N("LinkReplace"), label="Replace what the twin already has", value=False)
    cmds.checkBox(N("LinkOrient"), label="Pivots: mirror the handle orientation too", value=False)
    ui.main_button("Mirror onto the twins", _w(_guard(mirror_links)), "Selected controls -> their twins. One undo.")
    cmds.separator(height=8, style="in")
    ui.note("A setup you built by hand (constraints fed by multiplyDivide / unitConversion... nodes): select the "
            "controls it starts from on one side.")
    cmds.button(label="Mirror a setup (constraints, utility nodes, missing groups)...", height=26,
                command=_w(_guard(mirror_setup)),
                annotation="Shows what it will do first: the groups / controls the other side is missing are "
                           "made (mirrored), the constraints remade on the twins, the utility nodes copied with "
                           "their values and wired side for side. Controls at rest. One undo; again replaces.")
    ui.end_section()

    # -------------------------------------------------- skin weights
    frames["skin"] = ui.section("Skin weights", step=4, collapse=True,
               help_text="Select a skinned mesh to mirror one side onto the other, or two meshes (source, "
                         "then its twin) to copy across. Select vertices to change only those (on the side "
                         "that receives). Joints are paired by name (your naming pairs); the twin mesh is "
                         "skinned to the twin joints if it isn't yet. Check first: symmetry, joints without "
                         "a twin. Mirrors across the world origin.")
    cmds.radioButtonGrp(N("SkinDir"), label="Direction", numberOfRadioButtons=2,
                        labelArray2=["L -> R", "R -> L"], select=s["skin_direction"],
                        columnWidth3=(60, 80, 80), changeCommand=_w(_on_change))
    _checkbox("skin_closest", "Joints whose names don't pair: use the closest joint", s["skin_closest"],
              "Off: only joints paired by name get weights (missing twins are reported).")
    ui.row(2, 170)
    cmds.button(label="Check", command=_w(skin_check))
    cmds.button(label="Mirror skin weights", command=_w(skin_run), backgroundColor=ui.MAIN_BG)
    cmds.setParent("..")
    cmds.scrollField(N("SkinReport"), editable=False, wordWrap=True, height=70,
                     text="Select a skinned mesh, then Check.")
    ui.end_section()

    # -------------------------------------------------- advanced
    ui.section("More options", step=5, collapse=True, help_text="Mirror centre, extra name pairs, where new "
               "nodes go, and options per mode. Only the options of the current mode are shown.")
    cmds.radioButtonGrp(N("CenterMode"), label="Mirror centre", numberOfRadioButtons=2,
                        labelArray2=["World origin", "Custom"], select=s["center_mode"],
                        columnWidth3=(85, 100, 80), changeCommand=_w(_on_change))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    c = s["center"]
    cmds.floatFieldGrp(N("Center"), label="Position", numberOfFields=3, value1=c[0], value2=c[1],
                       value3=c[2], precision=3, columnWidth4=(85, 60, 60, 60), changeCommand=_w(_on_change))
    cmds.button(label="Get", width=50, command=_w(_get_center),
                annotation="Read the centre from the selected object or components.")
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(230, 80))
    cmds.text(label="Centre tolerance (side from position)", align="right")
    cmds.floatField(N("Tolerance"), value=s["tolerance"], minValue=0.0, maxValue=1000000.0, step=0.01, precision=3,
                    changeCommand=_w(_on_change),
                    annotation="Names without a side: closer than this to the mirror centre = centre (skipped).")
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=3, columnWidth3=(140, 80, 80),
                   columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Extra names (e.g. lf / rt)", align="right")
    cmds.textField(N("Search2"), text=s["search2"], changeCommand=_w(_on_change))
    cmds.textField(N("Replace2"), text=s["replace2"], changeCommand=_w(_on_change))
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(85, 230))
    cmds.text(label="New parent", align="right")
    cmds.optionMenu(N("ParentRule"), changeCommand=_w(_on_change),
                    annotation="Where new controls / joints go. Mirrored parent: under R_clavicle "
                               "if it exists, else the same parent as the source (e.g. spine).")
    for label in PARENT_RULES:
        cmds.menuItem(label=label)
    cmds.setParent("..")
    cmds.optionMenu(N("ParentRule"), edit=True, select=s["parent_rule"])

    _checkbox("update_existing", "Update existing (move them, never duplicate)", s["update_existing"])
    _checkbox("side_colors", "Apply side colours", s["side_colors"])
    cmds.columnLayout(N("OptCtrl"), adjustableColumn=True, rowSpacing=4)
    cmds.separator(height=6, style="in")
    cmds.text(label="Controls", font="boldLabelFont", align="left")
    _checkbox("copy_values", "Copy channel values (mirrored pose)", s["copy_values"])
    _checkbox("copy_attrs", "Copy custom attributes and their values", s["copy_attrs"])
    _checkbox("copy_locks", "Copy locked / hidden channels", s["copy_locks"])
    cmds.setParent("..")
    cmds.columnLayout(N("OptJnt"), adjustableColumn=True, rowSpacing=4)
    cmds.separator(height=6, style="in")
    cmds.text(label="Joints", font="boldLabelFont", align="left")
    _checkbox("clean_rotate", "Rotate values into Joint Orient (rotate = 0)", s["clean_rotate"])
    _checkbox("round_tiny", "Round tiny values (0.000001 -> 0)", s["round_tiny"])
    _checkbox("labels", "Joint labels (Side + name), for mirror skin weights", s["labels"])
    _checkbox("copy_look", "Copy radius and draw style", s["copy_look"])
    _checkbox("keep_skin", "Updating skinned joints: keep the mesh in place", s["keep_skin"],
              "Updates the skin bind data so the mesh does not move. Do it in the bind pose.")
    cmds.setParent("..")
    cmds.columnLayout(N("OptGeo"), adjustableColumn=True, rowSpacing=4)
    cmds.separator(height=6, style="in")
    cmds.text(label="Geometry", font="boldLabelFont", align="left")
    _checkbox("copy_materials", "Copy materials (per face too)", s["copy_materials"])
    cmds.setParent("..")
    cmds.button(label="Reset all settings to defaults", height=22, command=_w(reset_defaults))
    ui.end_section()

    # -------------------------------------------------- side colours
    ui.section("Side colours", step=6, collapse=True, help_text="The L / R / centre colours used by every "
               "tool (Mirror, Shapes 'Colour by side', Groups, Joints, Checker).")
    sc = colors.side_colors()
    for key, ctrl, label in (("L", N("ColL"), "Left"), ("R", N("ColR"), "Right"), ("C", N("ColC"), "Centre")):
        cmds.colorSliderGrp(ctrl, label=label, rgb=tuple(sc[key]), columnWidth3=(60, 60, 200),
                            changeCommand=_w(_save_colors))
    ui.row(2, 160)
    cmds.button(label="Colour selection by side", command=_w(apply_side_colors))
    cmds.button(label="Reset colours", command=_w(_reset_colors))
    cmds.setParent("..")
    ui.note("Used by every Gus_Rigtool tool. Side comes from the names above.")
    ui.end_section()

    ui.on_selection(N("Preview"), _w(preview))
    _on_change()


def show():
    """The Mirror tool as its own dockable panel."""
    ui.open_panel("mirror")


SCHEMA = [
    ("mode", "Mode", "choice", MODES),
    ("ctrl_orient", "Controls: orientation", "choice", CTRL_ORIENT),
    ("jnt_orient", "Joints: orientation", "choice", JNT_ORIENT),
    ("geo_orient", "Geometry: result", "choice", GEO_ORIENT),
    ("ungrouped", "Controls without a group", "choice", UNGROUPED),
    ("plane", "Plane", "choice", [p[0] for p in PLANES]),
    ("search", "Names: left token", "text", None),
    ("replace", "Names: right token", "text", None),
    ("search2", "Extra names: left", "text", None),
    ("replace2", "Extra names: right", "text", None),
    ("children", "Include children", "bool", None),
    ("rename_source", "Rename the source with its side", "bool", None),
    ("tolerance", "Centre tolerance", "float", None),
    ("parent_rule", "New parent", "choice", PARENT_RULES),
    ("update_existing", "Update existing", "bool", None),
    ("side_colors", "Apply side colours", "bool", None),
    ("copy_values", "Controls: copy channel values", "bool", None),
    ("copy_attrs", "Controls: copy custom attributes", "bool", None),
    ("copy_locks", "Controls: copy locked / hidden channels", "bool", None),
    ("clean_rotate", "Joints: rotate into Joint Orient", "bool", None),
    ("round_tiny", "Joints: round tiny values", "bool", None),
    ("labels", "Joints: labels", "bool", None),
    ("copy_look", "Joints: copy radius and draw style", "bool", None),
    ("keep_skin", "Joints: keep skinned mesh in place", "bool", None),
    ("copy_materials", "Geometry: copy materials", "bool", None),
    ("pose_centre", "Pose: centre controls mirror onto themselves", "bool", None),
    ("pose_custom", "Pose: copy custom attributes", "bool", None),
    ("anim_offset", "Mirror animation: frame offset", "int", None),
    ("anim_keys_only", "Mirror animation: only at the keys", "bool", None),
    ("anim_wrap", "Mirror animation: wrap keys inside the range", "bool", None),
    ("skin_direction", "Skin weights: direction", "choice", ["L -> R", "R -> L"]),
    ("skin_closest", "Skin weights: closest joint fallback", "bool", None),
]
