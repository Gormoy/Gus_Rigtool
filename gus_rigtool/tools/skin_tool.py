"""
Skin: bind, copy, clean, mirror and save skin weights.

    import gus_rigtool.main as gr; gr.show_tool("skin")

  1 Bind      : the selected meshes to the selected joints, or to skeleton_grp's joints when no joint
                is selected (the Gus_Rigtool rig).
  2 Copy      : the first selected skinned mesh onto the others (skins them first if needed).
  3 Clean     : prune small weights, limit influences per vertex, remove joints that carry no weight.
  4 Mirror    : one side's weights onto the other (same as Mirror > Geometry > skin).
  5 Save      : export the selected meshes' weights to one readable .json file; import it back - matched by
                name without namespaces, by vertex number or closest position, missing joints to the nearest
                one, meshes without skin bound first. Old folder exports still import.
  6 Vertex weights : copy / paste a vertex's weights, hammer, smooth, move one joint's weights to
                another (on vertices or whole meshes).
  8 Cloth     : a garment like the body (+ Delta Mush), ribbons on its edges, a cloth layer, a range of
                motion, a fix for the pose where it breaks (5.3.0).
"""

import os

import maya.cmds as cmds

from gus_rigtool.core import naming, skin_io, skin_mirror, skin_tools, ui, utils

TOOL = "Skin"
SETTINGS_KEY = "skin"

MAX_INF = ["1", "2", "3", "4", "5", "6", "8"]
PRUNE = ["0.001", "0.005", "0.01", "0.02", "0.05", "0.1"]
DEFAULTS = {"max_influences": 4, "bind_method": 0, "skin_method": 0, "surface": 0, "influence": 0,
            "prune": 0.01, "limit": 4, "mirror_direction": 1, "import_method": 0, "folder": "", "smooth": 0.5,
            "mirror_tol": 0.01}
SMOOTH = ["0.25", "0.5", "0.75", "1"]

_P, N, _w, _guard = ui.tool_helpers("p_skin_", TOOL)


def _menu(name, items, value, ann=""):
    cmds.optionMenu(N(name), changeCommand=_w(_save), annotation=ann)
    for i in items:
        cmds.menuItem(label=i)
    try:
        cmds.optionMenu(N(name), edit=True, select=[float(x) for x in items].index(float(value)) + 1)
    except (ValueError, RuntimeError):
        pass


def _menu_index(name, items, value, ann=""):
    cmds.optionMenu(N(name), changeCommand=_w(_save), annotation=ann)
    for i in items:
        cmds.menuItem(label=i)
    cmds.optionMenu(N(name), edit=True, select=max(1, min(len(items), int(value) + 1)))


def _q(name):
    return cmds.optionMenu(N(name), query=True, select=True) - 1


def _ui():
    return {"max_influences": int(MAX_INF[_q("MaxInf")]), "bind_method": _q("BindMethod"), "skin_method": _q("SkinMethod"),
            "surface": _q("Surface"), "influence": _q("Influence"), "prune": float(PRUNE[_q("Prune")]),
            "limit": int(MAX_INF[_q("Limit")]), "mirror_direction": _q("MirrorDir") + 1, "import_method": _q("ImportMethod"),
            "folder": cmds.textField(N("Folder"), query=True, text=True), "smooth": float(SMOOTH[_q("Smooth")])}


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _light():
    geos = skin_tools.selected_geo()
    joints = skin_tools.selected_joints()
    if not geos:
        return "idle", "Select meshes (and joints to bind to, or none for skeleton_grp's)."
    skinned = [g for g in geos if skin_mirror.skin_of(g)]
    text = "%d mesh(es), %d skinned" % (len(geos), len(skinned))
    if joints:
        text += ", %d joint(s) selected" % len(joints)
    return "ok", text + "."


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------

def bind(*_):
    o = _ui()
    _save()
    made = skin_tools.bind(max_influences=o["max_influences"], bind_method=o["bind_method"],
                           skin_method=o["skin_method"])
    from gus_rigtool.tools import home
    home.say_next(TOOL, "skinned %d mesh(es)." % len(made))


def add_joints(*_):
    sel = cmds.ls(selection=True, long=True) or []
    joints = [n for n in sel if cmds.nodeType(n) == "joint"]
    meshes = [n for n in sel if n not in joints and cmds.listRelatives(n, shapes=True, type=("mesh", "nurbsSurface",
                                                                                            "nurbsCurve"))]
    if not joints or not meshes:
        raise RuntimeError("select the skinned mesh and the joints to add (a chain's first joint brings the whole "
                           "chain).")
    lines = []
    for m in meshes:
        added, had = skin_tools.add_joints(m, joints, hierarchy=True)
        lines.append("%s: %d joint(s) added (weight 0)%s" % (naming.short_name(m), len(added),
                                                              (", %d already in" % had) if had else ""))
    utils.info(TOOL, "; ".join(lines) + ".")


def copy(*_):
    o = _ui()
    _save()
    infl = [o["influence"]] + ([1] if o["influence"] != 1 else [0])     # then by name / closest joint
    n = skin_tools.copy(surface=o["surface"], influence=infl)
    utils.info(TOOL, "skin copied onto %d mesh(es)." % n)


def prune(*_):
    o = _ui()
    _save()
    n = skin_tools.prune(below=o["prune"])
    utils.info(TOOL, "pruned weights under %g on %d mesh(es)." % (o["prune"], n))


def limit(*_):
    o = _ui()
    _save()
    n = skin_tools.limit_influences(limit=o["limit"])
    utils.info(TOOL, "%d vertices had more than %d influences: fixed." % (n, o["limit"]))


def remove_unused(*_):
    n = skin_tools.remove_unused()
    utils.info(TOOL, "removed %d joint(s) with no weight from the skin." % n)


def label_joints(*_):
    from gus_rigtool.core import joint_labels
    joints = cmds.ls(selection=True, type="joint", long=True) or joint_labels.rig_joints()
    if not joints:
        raise RuntimeError("no joints: select joints, or build / skin the rig first.")
    lonely = []
    n = joint_labels.label(joints, lonely)
    utils.info(TOOL, "labelled %d joint(s): in ngSkinTools set Mirror > Influences mapping to use joint labels." % n)
    if lonely:
        ui.report_window("Gus_Rigtool - joint labels",
                         "Labelled %d joint(s). These have no twin on the other side - their weights mirror onto "
                         "themselves (the other side looks black for them):\n\n%s\n\n'Add missing twins' "
                         "makes the ones missing by name (in the skin, weight 0); or fix the names and label again." % (
                             n, "\n".join("  %s: %s" % (naming_short(j), why) for j, why in lonely)))


def add_twins(*_):
    from gus_rigtool.core import joint_labels
    made = joint_labels.add_twins(cmds.ls(selection=True, type="joint", long=True) or None)
    if not made:
        utils.info(TOOL, "every left / right joint already has its twin.")
        return
    cmds.select(made, replace=True)
    utils.info(TOOL, "made %d twin joint(s) (selected), added to the skins with weight 0: %s. Mirror the weights "
               "now." % (len(made), ", ".join(naming_short(j) for j in made[:6])))


def check_mirrored(*_):
    from gus_rigtool.core import joint_labels
    bad = joint_labels.not_mirrored(cmds.ls(selection=True, type="joint", long=True) or None)
    if not bad:
        utils.info(TOOL, "every left / right joint pair is a mirror image.")
        return
    lines = ["%s  <->  %s : %s" % (naming_short(a), naming_short(b) if b else "(no twin by name)",
                                   ("%.3f off" % off) if off is not None else "") for a, b, off in bad]
    cmds.select([a for a, _b, _o in bad] + [b for _a, b, _o in bad if b], replace=True)
    ui.report_window("Gus_Rigtool - left / right joints", "Twin joints that aren't mirror images across X (selected):"
                     "\n\n%s\n\nFix the guides (Mirror guides) and rebuild, or mirror the skin by joint labels "
                     "(Label joints, then ngSkinTools: Influences mapping > joint labels)." % "\n".join(lines))


def mirror(*_):
    o = _ui()
    _save()
    try:
        level, lines = skin_mirror.check()
    except RuntimeError:
        level, lines = "ok", []                     # mirror_weights says what's wrong
    if level != "ok" and cmds.confirmDialog(
            title="Mirror weights - check first", button=["Mirror anyway", "Cancel"], defaultButton="Cancel",
            cancelButton="Cancel", dismissString="Cancel",
            message="Before mirroring:\n\n%s\n\nVertices with no partner get the closest weights; joints with no "
                    "twin keep their own. Fix first (Label joints / Add missing twins), or mirror anyway?"
                    % "\n".join(lines[:12])) != "Mirror anyway":
        return
    skin_mirror.mirror_weights(direction="L>R" if o["mirror_direction"] == 1 else "R>L", closest_fallback=True)


# ---------------------------------------------------------------- weight list (4.4.0)

_table = {}


def refresh_table(*_):
    if not cmds.textScrollList(N("Table"), exists=True):
        return
    pts = skin_tools.selected_points()
    if len(pts) > 400:
        cmds.textScrollList(N("Table"), edit=True, removeAll=True,
                            append=["%d vertices selected: select 400 or fewer to list their weights." % len(pts)])
        return
    try:
        rows = skin_tools.weight_table(pts) if pts else []
    except RuntimeError as e:
        rows = []
        cmds.textScrollList(N("Table"), edit=True, removeAll=True, append=[str(e)])
        return
    _table[_P["p"]] = rows
    labels = ["%-28s %6.3f%s" % (naming.short_name(j)[:28], w, "   locked" if lk else "") for j, w, lk in rows]
    cmds.textScrollList(N("Table"), edit=True, removeAll=True,
                        append=labels or ["(select vertices of a skinned mesh)"])
    cmds.text(N("TableInfo"), edit=True, label="%d vertex(es); average weights, biggest first" % len(pts)
              if rows else "")


def _picked_joints():
    idx = cmds.textScrollList(N("Table"), query=True, selectIndexedItem=True) or []
    rows = _table.get(_P["p"], [])
    out = [rows[i - 1][0] for i in idx if 0 < i <= len(rows)]
    if not out:
        raise RuntimeError("pick a joint in the list.")
    return out


def set_picked(*_):
    joint = _picked_joints()[0]
    v = cmds.floatField(N("Value"), query=True, value=True)
    n = skin_tools.set_joint_weight(joint, v)
    utils.info(TOOL, "%s = %.3f on %d vertex(es); the other joints share the rest." % (naming.short_name(joint), v, n))
    refresh_table()


def average_sel(*_):
    n = skin_tools.average_points()
    utils.info(TOOL, "%d vertices now have the selection's average weights." % n)
    refresh_table()


def lock_picked(locked, *_):
    n = skin_tools.lock_joints(_picked_joints(), locked)
    utils.info(TOOL, "%s %d joint(s)." % ("locked" if locked else "unlocked", n))
    refresh_table()


IMPORT_BY = ["Auto (vertex number if the same mesh, else closest)", "Vertex number", "Closest position"]


def _start_dir():
    o = _ui()
    folder = o.get("folder") or ""
    if folder and os.path.isfile(folder):
        folder = os.path.dirname(folder)
    return folder or cmds.workspace(query=True, rootDirectory=True)


def export(*_):
    geos = skin_tools.selected_geo()
    if not geos:
        raise RuntimeError("select the skinned meshes to export.")
    got = cmds.fileDialog2(fileMode=0, dialogStyle=2, startingDirectory=_start_dir(),
                           fileFilter="Skin weights (*.json)", caption="Export skin weights to")
    if not got:
        return
    saved, path = skin_io.export_file(got[0], geos)
    cmds.textField(N("Folder"), edit=True, text=path)
    _save()
    utils.info(TOOL, "weights of %d mesh(es) saved to %s (%s)." % (len(saved), os.path.basename(path),
                                                                  ", ".join(saved[:5])))


def import_(*_):
    got = cmds.fileDialog2(fileMode=1, dialogStyle=2, startingDirectory=_start_dir(),
                           fileFilter="Skin weights (*.json)", caption="Import skin weights from")
    if not got:
        return
    path = got[0]
    if os.path.basename(path) == skin_tools.MANIFEST:          # an export from before 3.12: a folder
        o = _ui()
        done, notes = skin_tools.import_weights(os.path.dirname(path),
                                                method=skin_tools.IMPORT_METHODS[o["import_method"]])
        ui.report_window("Gus_Rigtool - skin weights", "Old export (a folder)\n\nloaded on %d mesh(es)\n%s"
                         % (len(done), "\n".join(notes)))
        return
    import_window(path)


def import_window(path):
    """Which scene mesh gets which file mesh, how to match points, then Import."""
    data = skin_io.read_file(path)
    win = N("ImportWin")
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    meshes = skin_io.scene_meshes()
    labels = ["(skip)"] + [naming_short(m) for m in meshes]
    sel = skin_tools.selected_geo()
    cmds.window(win, title="Import skin weights - %s" % os.path.basename(path), widthHeight=(520, 360))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4, columnAttach=("both", 6))
    cmds.text(label="Each mesh in the file goes on the scene mesh you pick (found by name, namespaces ignored).",
              align="left")
    rows = []
    for name, entry in sorted(data["meshes"].items()):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(200, 300),
                       columnAttach=[(1, "both", 2), (2, "both", 2)])
        cmds.text(label="%s  (%d points, %d joints)" % (name, entry["points"], len(entry["joints"])), align="left")
        menu = cmds.optionMenu()
        for lb in labels:
            cmds.menuItem(label=lb)
        guess = skin_io.guess_mesh(name, meshes, sel if len(data["meshes"]) == 1 else None)
        if guess:
            cmds.optionMenu(menu, edit=True, select=meshes.index(guess) + 2)
        cmds.setParent("..")
        rows.append((name, menu))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(80, 400),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="Match points")
    by = cmds.optionMenu()
    for lb in IMPORT_BY:
        cmds.menuItem(label=lb)
    cmds.setParent("..")
    bind = cmds.checkBox(label="Bind meshes without a skin (to the joints they need)", value=True)

    def go(*_):
        plan = {}
        for name, menu in rows:
            i = cmds.optionMenu(menu, query=True, select=True)
            plan[name] = meshes[i - 2] if i > 1 else None
        method = skin_io.METHODS[cmds.optionMenu(by, query=True, select=True) - 1]
        with utils.undo_chunk("gusrigImportWeights"):
            lines, done = skin_io.import_file(path, plan, method, cmds.checkBox(bind, query=True, value=True))
        cmds.deleteUI(win)
        ui.report_window("Gus_Rigtool - skin weights", "%s\n\nweights put on %d mesh(es):\n\n%s"
                         % (os.path.basename(path), done, "\n".join(lines)))
        utils.info(TOOL, "weights put on %d mesh(es) - the report window has the details." % done)
    cmds.button(label="Import", height=30, command=_w(_guard(go)))
    cmds.button(label="Cancel", command=lambda *_: cmds.deleteUI(win))
    cmds.showWindow(win)
    return win


def naming_short(n):
    return n.split("|")[-1]


def copy_point(*_):
    w = skin_tools.copy_point_weights()
    utils.info(TOOL, "copied: %s." % ", ".join("%s %.2f" % (j.split("|")[-1], v) for j, v in
                                               sorted(w.items(), key=lambda x: -x[1])[:4]))


def paste_point(*_):
    n = skin_tools.paste_point_weights()
    utils.info(TOOL, "pasted on %d point(s)." % n)


def hammer(*_):
    n = skin_tools.hammer()
    utils.info(TOOL, "hammered %d vertices." % n)


def smooth(*_):
    o = _ui()
    _save()
    n = skin_tools.smooth(strength=o["smooth"])
    utils.info(TOOL, "smoothed %d vertices (strength %g)." % (n, o["smooth"]))


def move_weights(*_):
    joints = cmds.ls(orderedSelection=True, type="joint", long=True) or skin_tools.selected_joints()
    if len(joints) != 2:
        raise RuntimeError("select TWO joints (FROM first, then TO), and the vertices or meshes.")
    points = skin_tools.selected_points()
    n = skin_tools.move_weights(joints[0], joints[1], points=points)
    utils.info(TOOL, "moved %s's weights to %s (%s)." % (joints[0].split("|")[-1], joints[1].split("|")[-1],
                                                         "%d point(s)" % len(points) if points else "%d mesh(es)" % n))


# ---------------------------------------------------------------------------
# cloth (5.3.0)
# ---------------------------------------------------------------------------

def _report(title, lines):
    print(title + "\n" + "\n".join("  " + line for line in lines))
    utils.info(TOOL, title + (" " + lines[0] if len(lines) == 1 else " (details in the Script Editor)."))


def cloth_skin(*_):
    from gus_rigtool.core import cloth
    geos = skin_tools.selected_geo()
    if len(geos) < 2:
        raise RuntimeError("select the skinned body first, then the garments.")
    lines = cloth.skin_like(geos[0], geos[1:], delta_mush=cmds.checkBox(N("ClothDM"), query=True, value=True),
                            replace=cmds.checkBox(N("ClothReplace"), query=True, value=True))
    _report("Skin like the body:", lines)


def cloth_ribbon(*_):
    from gus_rigtool.core import cloth
    edges = cmds.filterExpand(cmds.ls(selection=True, flatten=True) or [], selectionMask=32) or []
    name = cmds.textField(N("ClothName"), query=True, text=True).strip()
    if not name:
        raise RuntimeError("type a name (L_Cuff, Hem...) first.")
    made = cloth.edge_ribbon(edges, name, count=cmds.intField(N("ClothCount"), query=True, value=True),
                             every=cmds.intField(N("ClothEvery"), query=True, value=True),
                             mirror=cmds.checkBox(N("ClothMirror"), query=True, value=True))
    cmds.select(made, replace=True)
    utils.info(TOOL, "ribbon(s) made: %s." % ", ".join(naming.short_name(m) for m in made))


def cloth_layer(*_):
    from gus_rigtool.core import cloth
    sel = cmds.ls(selection=True, long=True) or []
    meshes = [s for s in sel if cmds.listRelatives(s, shapes=True, type="mesh")]
    ribs = [s for s in sel if s not in meshes]
    if not meshes or not ribs:
        raise RuntimeError("select the garment, and its ribbons (or one of their controls).")
    _report("Cloth layer:", [cloth.cloth_layer(meshes[0], ribs)])


def cloth_repair(*_):
    from gus_rigtool.core import cloth
    geos = skin_tools.selected_geo()
    if not geos:
        raise RuntimeError("select the garment(s) to repair.")
    lines = []
    for g in geos:
        over, fixed = cloth.repair(g)
        lines.append("%s: %d vertices over the joint limit, %d not adding up to 1 - fixed" % (
            naming.short_name(g), over, fixed))
    _report("Repair weights:", lines)


def motion_pause(pause, *_):
    from gus_rigtool.builder import chain
    n = chain.pause_motion(pause)
    utils.info(TOOL, ("%d jiggle / wave expression(s) paused - press Back on when you're done skinning." if pause
                      else "%d jiggle / wave expression(s) back on.") % n)


def cloth_rom(*_):
    from gus_rigtool.core import cloth
    start, end, plan = cloth.make_rom()
    _report("Range of motion, frames %d-%d:" % (start, end), plan)


def cloth_rom_remove(*_):
    from gus_rigtool.core import cloth
    n = cloth.remove_rom()
    utils.info(TOOL, "range of motion removed (%d channels back as they were)." % n)


def cloth_fix(*_):
    from gus_rigtool.core import cloth
    geos = skin_tools.selected_geo()
    joints = cmds.ls(selection=True, type="joint", long=True) or []
    if not geos:
        raise RuntimeError("select the garment (and the joint, or none: the one bent most).")
    sculpt = cloth.fix_here(geos[0], joints[0] if joints else None)
    utils.info(TOOL, "sculpt %s, then Apply in the Fixes page." % naming.short_name(sculpt))


# ---------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------

def build(prefix="p_skin_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    ui.status_light(N("Light"), _light, _w)

    ui.section("Bind", step=1, help_text="Select the meshes, and the joints to bind to. No joint selected: the "
               "Gus_Rigtool rig's joints (everything under skeleton_grp). Meshes already skinned are left alone.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Max influences")
    _menu("MaxInf", MAX_INF, s["max_influences"], "Joints per vertex (4 for game engines).")
    cmds.text(label="Bind method")
    _menu_index("BindMethod", skin_tools.BIND_METHODS, s["bind_method"],
                "Closest distance is fast; heat map / geodesic voxel follow the shape better.")
    cmds.text(label="Skinning")
    _menu_index("SkinMethod", skin_tools.SKIN_METHODS, s["skin_method"],
                "Dual quaternion keeps volume when joints twist.")
    cmds.setParent("..")
    ui.main_button("Bind skin", _w(_guard(bind)), "Skin the selected meshes.")
    cmds.button(label="Add joints to the skin (each once)", command=_w(_guard(add_joints)),
                annotation="Select the skinned mesh and joints (a chain's first joint brings the whole chain): each "
                           "goes in exactly once, weight 0. Maya's Add Influence with chain roots selected can put "
                           "every joint in twice - painting and ngSkinTools then break.")
    ui.end_section()

    ui.section("Copy skin", step=2, help_text="Select the skinned source, then the meshes to copy to. Meshes "
               "without skin are skinned first to the same joints.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Match points by")
    _menu_index("Surface", ["Closest point", "Ray cast", "Closest component", "UV"], s["surface"])
    cmds.text(label="Match joints by")
    _menu_index("Influence", ["Closest joint", "Name", "One to one", "Label"], s["influence"])
    cmds.setParent("..")
    cmds.button(label="Copy skin (first selected > others)", height=26, backgroundColor=ui.MAIN_BG, command=_w(_guard(copy)))
    ui.end_section()

    ui.section("Clean", step=3, help_text="Prune: weights under the value become 0. Limit: each vertex keeps its "
               "biggest weights only (the rest is shared out). Remove unused: joints with no weight leave the "
               "skin (lighter files, faster).")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Prune under")
    _menu("Prune", PRUNE, s["prune"])
    cmds.text(label="Influences per vertex")
    _menu("Limit", MAX_INF, s["limit"])
    cmds.setParent("..")
    ui.row(3, 113)
    cmds.button(label="Prune", command=_w(_guard(prune)))
    cmds.button(label="Limit", command=_w(_guard(limit)))
    cmds.button(label="Remove unused", command=_w(_guard(remove_unused)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Mirror weights", step=4, help_text="Select a skinned mesh (or a vertex selection, or two meshes: "
               "source, then its twin). Joints are matched by their labels (made for you: by side name, and by "
               "position for joints with no side in the name). Label joints: Maya's joint labels "
               "(side + name without L_ / R_) on the selected joints, or every rig / skin joint - then ngSkinTools "
               "(Mirror > Influences mapping: joint labels) or Maya's Mirror Skin Weights ('Label') pair every left "
               "joint with its right twin. Check left / right: lists twin joints that aren't mirror images (why a "
               "mirror by distance picks the wrong joint).")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Direction")
    _menu_index("MirrorDir", ["L > R", "R > L"], s["mirror_direction"] - 1)
    cmds.setParent("..")
    cmds.button(label="Mirror weights", height=26, backgroundColor=ui.MAIN_BG, command=_w(_guard(mirror)))
    ui.row(2, 170)
    cmds.button(label="Label joints", command=_w(_guard(label_joints)),
                annotation="Side + name labels for ngSkinTools / Maya mirroring (selected joints, or every rig joint).")
    cmds.button(label="Check left / right", command=_w(_guard(check_mirrored)),
                annotation="Twin joints that aren't mirror images - selected and listed.")
    cmds.setParent("..")
    cmds.button(label="Add missing twins", command=_w(_guard(add_twins)),
                annotation="A left joint with no right one (or the other way round): its mirror image is made "
                           "under the twin parent and added to the same skins (weight 0), so mirroring works.")
    ui.end_section()

    ui.section("Save / load weights", step=5, help_text="Export: the selected skinned meshes into one .json file "
               "(readable: joints, and a line per vertex with its weights). Import: pick the file; a window "
               "matches each mesh in it to a scene mesh by name (namespaces ignored) - change any. Points match "
               "by vertex number, or by closest position when the mesh changed. A joint missing from the scene "
               "gives its weights to the nearest joint (listed in the report). A mesh without a skin is bound "
               "first. Old exports (a folder): pick their gus_skin_weights.json - 'Old exports by' is used.")
    cmds.textField(N("Folder"), text=s.get("folder", ""), placeholderText="last file (asked when you press a button)",
                   changeCommand=_w(_save), editable=False)
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Old exports by")
    _menu_index("ImportMethod", skin_tools.IMPORT_METHODS, s["import_method"])
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Export weights...", command=_w(_guard(export)))
    cmds.button(label="Import weights...", command=_w(_guard(import_)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Vertex weights", step=6, help_text="Copy: the selected vertex's weights (several: their average). "
               "Paste: on the selected vertices (joints not in their skin are skipped). Hammer: Maya's, the "
               "vertices take their neighbours' weights. Smooth: each vertex goes part of the way to its "
               "neighbours' average. Move weights: select the joint FROM, then the joint TO, and the vertices "
               "(or whole meshes) - every weight of the first goes to the second.")
    ui.row(3, 113)
    cmds.button(label="Copy", command=_w(_guard(copy_point)))
    cmds.button(label="Paste", command=_w(_guard(paste_point)))
    cmds.button(label="Hammer", command=_w(_guard(hammer)))
    cmds.setParent("..")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Smooth strength")
    _menu("Smooth", SMOOTH, s.get("smooth", 0.5))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Smooth", command=_w(_guard(smooth)))
    cmds.button(label="Move weights: joint 1 > 2", command=_w(_guard(move_weights)),
                annotation="Select the joint FROM, then TO, and the vertices or meshes.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("Weight list", step=7, help_text="Select vertices: every joint with weight on them, their average "
               "weight, and whether it's locked. Pick a joint, type a value, Set: the vertices get exactly that, the "
               "other unlocked joints share the rest (keeping their proportions). Average: every selected vertex "
               "gets the selection's average. Lock / Unlock: painting and Set leave locked joints alone.")
    cmds.text(N("TableInfo"), label="", align="left", font="smallPlainLabelFont")
    cmds.textScrollList(N("Table"), height=110, allowMultiSelection=True, font="fixedWidthFont")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(60, 70, 200),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Value")
    cmds.floatField(N("Value"), value=0.5, minValue=0.0, maxValue=1.0, precision=3, step=0.05)
    cmds.button(label="Set on the picked joint", backgroundColor=ui.MAIN_BG, command=_w(_guard(set_picked)))
    cmds.setParent("..")
    ui.row(3, 113)
    cmds.button(label="Average", command=_w(_guard(average_sel)))
    cmds.button(label="Lock", command=_w(_guard(lambda *_: lock_picked(True))))
    cmds.button(label="Unlock", command=_w(_guard(lambda *_: lock_picked(False))))
    cmds.setParent("..")
    ui.end_section()
    ui.section("Cloth", step=8, collapse=True, help_text="A garment in layers. 1 Skin like the body: select the "
               "skinned body, then the garments - they get the body's joints and weights (and a Delta Mush to "
               "smooth the folds). A garment already skinned keeps its weights unless 'Replace' is ticked. 2 Ribbon: "
               "select an edge loop of the garment (a cuff, the hem), type a name with its side (L_Cuff): a ribbon "
               "with controls, following the nearest joint, and the same on the other side. 3 Cloth layer: select "
               "the garment and its ribbons - their joints take over near them, fading out (an ngSkinTools layer "
               "when ngSkinTools 2 is loaded, else straight into the skin; worked out at rest, checked after). "
               "Repair weights: a garment pulled to the world origin - at most 4 joints a vertex, every vertex "
               "adding up to 1. 4 Range of motion: keys the body's "
               "controls (FK) bending one part at a time, to see where the garment breaks; Remove takes it away. "
               "5 Fix this pose: on a frame where it breaks, select the garment - a sculpt copy for the joint bent "
               "most, then Apply in the Fixes page.")
    ui.row(2, 170)
    cmds.checkBox(N("ClothDM"), label="Delta Mush", value=True)
    cmds.checkBox(N("ClothReplace"), label="Replace weights", value=False)
    cmds.setParent("..")
    ui.main_button("1  Skin like the body", _w(_guard(cloth_skin)), "Select the body, then the garments.")
    cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 120), (2, 200)], columnAlign=(1, "right"),
                         columnSpacing=(2, 6), rowSpacing=(1, 3))
    cmds.text(label="Name")
    cmds.textField(N("ClothName"), placeholderText="L_Cuff")
    cmds.text(label="Joints")
    cmds.intField(N("ClothCount"), value=12, minValue=3, maxValue=1000000, step=1)
    cmds.text(label="A control every")
    cmds.intField(N("ClothEvery"), value=2, minValue=1, maxValue=1000000, step=1)
    cmds.setParent("..")
    cmds.checkBox(N("ClothMirror"), label="The other side too", value=True)
    cmds.button(label="2  Ribbon on the selected edges", command=_w(_guard(cloth_ribbon)))
    ui.row(2, 170)
    cmds.button(label="3  Cloth layer", command=_w(_guard(cloth_layer)),
                annotation="Select the garment and its ribbons (the rig at rest).")
    cmds.button(label="Repair weights", command=_w(_guard(cloth_repair)),
                annotation="A garment pulled to the world origin: 4 joints a vertex at most, every vertex "
                           "adding up to 1.")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="4  Range of motion", command=_w(_guard(cloth_rom)))
    cmds.button(label="Remove it", command=_w(_guard(cloth_rom_remove)))
    cmds.setParent("..")
    cmds.button(label="5  Fix this pose", command=_w(_guard(cloth_fix)),
                annotation="A sculpt copy of the garment for the joint bent most at this frame.")
    ui.end_section()
    ui.section("Jiggle and wave", step=9, collapse=True, help_text="Chains with jiggle or wave keep turning their "
               "groups; while you skin or paint (ngSkinTools) that can keep the mesh re-evaluating. Pause: every "
               "jiggle / wave off. Back on: as they were. Check this scene says when they're paused.")
    ui.row(2, 170)
    cmds.button(label="Pause while skinning", command=_w(_guard(lambda *_: motion_pause(True))))
    cmds.button(label="Back on", command=_w(_guard(lambda *_: motion_pause(False))))
    cmds.setParent("..")
    ui.end_section()
    ui.on_selection(N("Table"), _w(refresh_table))


def show():
    ui.open_panel("skin")


SCHEMA = [
    ("max_influences", "Bind: max influences", "int", None),
    ("prune", "Prune under", "float", None),
    ("limit", "Influences per vertex", "int", None),
    ("mirror_tol", "Skin mirror tolerance (Check this scene)", "float", None),
]

