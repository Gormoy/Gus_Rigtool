"""
The Build tab's '3 Existing rig' page (split out of tools/build_tab in 4.2.0): scan a part of any rig, keep it
(adopt), rebuild it with the builder on its joints, replace the old part, backup. tools/build_tab still has every
name.
"""

import maya.cmds as cmds

from gus_rigtool.builder import build as bld  # noqa: F401
from gus_rigtool.builder import existing, guides, limb, modules, names  # noqa: F401
from gus_rigtool.core import naming, quick, ui, utils  # noqa: F401
from gus_rigtool.tools.build_tab import (  # noqa: F401
    N, SWITCH_VALUES, TOOL, _P, _field, _guard, _height, _limbs, _picked, _scan, _w, refresh_list)


def _nodes(key):
    out = []
    for n in cmds.textField(N(key), query=True, text=True).split():
        found = cmds.ls(n, long=True) or []
        if len(found) != 1:
            raise RuntimeError("'%s': %s." % (n, "not found" if not found else "several nodes have this name"))
        out.append(found[0])
    return out


def _set(key, nodes):
    cmds.textField(N(key), edit=True, text=" ".join(naming.short_name(n) for n in nodes if n))


def ex_scan(*_):
    info = existing.scan()
    _scan[_P["p"]] = info
    _set("ExControls", info["controls"])
    if info["limbs"]:
        lb = info["limbs"][0]
        _set("ExIk", [lb["ik"]])
        _set("ExPv", [lb["pv"]])
        bind = lb["ik_joints"][:3]
        _set("ExJoints", bind)
        fk = []
        for j in bind:
            c = next((c for c in info["controls"] if j in existing.driven_joints(c)), None)
            fk.append(c)
        if all(fk):
            _set("ExFk", fk)
    sp = existing.suggest_spaces(info)
    if sp:
        cmds.textField(N("ExSpaces"), edit=True, text=existing.spaces_text(sp))
    if info["switches"]:
        c, a = info["switches"][0]
        cmds.textField(N("ExSwitch"), edit=True, text=naming.short_name(c) + "." + a)
    ui.report_window("Gus_Rigtool - scan", existing.report(info))
    utils.info(TOOL, "scanned: %d controls, %d joints, %d IK limb(s). Check the fields, then Adopt or Place."
               % (len(info["controls"]), len(info["joints"]), len(info["limbs"])))


def ex_add_limb(*_):
    name = cmds.textField(N("ExLimbName"), query=True, text=True).strip()
    if not name:
        raise RuntimeError("give the limb a name (e.g. L_arm).")
    sw = cmds.textField(N("ExSwitch"), query=True, text=True).strip()
    if sw:
        node = cmds.ls(sw.split(".")[0], long=True)
        sw = (node[0] + "." + sw.split(".", 1)[1]) if node else sw
    a, b = SWITCH_VALUES[cmds.optionMenu(N("ExValues"), query=True, select=True) - 1]
    lb = {"name": name, "fk": _nodes("ExFk"), "joints": _nodes("ExJoints"), "ik": (_nodes("ExIk") or [None])[0],
          "pv": (_nodes("ExPv") or [None])[0], "switch": sw, "fk_value": a, "ik_value": b}
    if len(lb["fk"]) != 3 or len(lb["joints"]) != 3 or not lb["ik"]:
        raise RuntimeError("a limb needs 3 FK controls, 3 joints and the IK control.")
    lst = _limbs.setdefault(_P["p"], [])
    lst[:] = [x for x in lst if x["name"] != name] + [lb]
    cmds.textScrollList(N("ExLimbs"), edit=True, removeAll=True, append=[x["name"] for x in lst])
    utils.info(TOOL, "limb '%s' ready - it is taught when you press Adopt." % name)


def ex_clear_limbs(*_):
    _limbs[_P["p"]] = []
    cmds.textScrollList(N("ExLimbs"), edit=True, removeAll=True)


def ex_adopt(*_):
    name = cmds.textField(N("ExName"), query=True, text=True).strip()
    side = "CLR"[cmds.optionMenu(N("ExSide"), query=True, select=True) - 1]
    ctrls = _nodes("ExControls")
    spaces = existing.parse_spaces(cmds.textField(N("ExSpaces"), query=True, text=True))
    g = existing.adopt(name, side, ctrls, list(_limbs.get(_P["p"], [])), spaces=spaces)
    ex_clear_limbs()
    refresh_list(g)


def _ex_hint(*_):
    mtype = existing.placeable()[cmds.optionMenu(N("ExType"), query=True, select=True) - 1]
    cmds.text(N("ExHint"), edit=True, label="  Select: " + existing.joint_hint(mtype))


def ex_place(*_):
    mtype = existing.placeable()[cmds.optionMenu(N("ExType"), query=True, select=True) - 1]
    side = "CLR"[cmds.optionMenu(N("ExPlaceSide"), query=True, select=True) - 1]
    name = cmds.textField(N("ExPlaceName"), query=True, text=True).strip() or mtype
    joints = _nodes("ExPlaceJoints")
    g = existing.place_on_joints(mtype, side, name, joints, _height())
    refresh_list(g)


def _placed_picks():
    picked = _picked()
    if not picked:
        raise RuntimeError("pick the rebuilt module(s) in the list (1 Rig builder) - Ctrl-click several.")
    bad = [guides.read(g)["name"] for g in picked if not guides.read(g)["settings"].get("placed_on")]
    if bad:
        raise RuntimeError("not placed on joints: %s." % ", ".join(bad))
    return picked


def ex_check(*_):
    gs = _placed_picks()
    p = existing.plan_replace(gs, _nodes("ExOld"))
    head = ["Modules: " + ", ".join(guides.read(g)["name"] + " (" + guides.read(g)["side"] + ")" for g in gs), ""]
    ui.report_window("Gus_Rigtool - replace: what will happen", "\n".join(head + existing.plan_lines(p)))


def ex_replace(*_):
    gs = _placed_picks()
    p = existing.plan_replace(gs, _nodes("ExOld"))
    warn = ""
    if p["unmapped"]:
        warn += "\n\nWARNING: %d old joint(s) keep skin weights (no new joint): %s" % (
            len(p["unmapped"]), ", ".join(naming.short_name(j) for j in p["unmapped"][:8]))
    if p.get("lost"):
        warn += "\n\nWARNING: %d old joint(s) can't be found: %s" % (len(p["lost"]), ", ".join(p["lost"][:8]))
    msg = ("Replace %d module(s): move the skin from %d old joint(s) to the new ones, reconnect %d hook-up(s), and "
           "put the old part into %s (hidden)?%s" % (len(gs), len(p["map"]), len(p["hookups"]), existing.LEGACY,
                                                     warn))
    if cmds.confirmDialog(title="Replace the old part", message=msg, button=["Replace", "Cancel"],
                          defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Replace":
        return
    _p, notes = existing.replace(gs, _nodes("ExOld"))
    ui.report_window("Gus_Rigtool - replaced", "\n".join(notes))
    refresh_list(gs)


# place many: a list of rows (type, side, name, joints)
_queue = {}


def _q_rows():
    return _queue.setdefault(_P["p"], [])


def _q_refresh():
    if not cmds.textScrollList(N("ExQueue"), exists=True):
        return
    cmds.textScrollList(N("ExQueue"), edit=True, removeAll=True)
    for r in _q_rows():
        cmds.textScrollList(N("ExQueue"), edit=True, append="%s %-10s %-8s %d joints: %s ..%s" % (
            r["side"], r["name"] or r["type"], r["type"], len(r["joints"]), naming.short_name(r["joints"][0]),
            naming.short_name(r["joints"][-1])))


def _row_now():
    mtype = existing.placeable()[cmds.optionMenu(N("ExType"), query=True, select=True) - 1]
    side = "CLR"[cmds.optionMenu(N("ExPlaceSide"), query=True, select=True) - 1]
    name = (cmds.textField(N("ExPlaceName"), query=True, text=True) or "").strip() or mtype
    joints = _nodes("ExPlaceJoints")
    if not joints:
        raise RuntimeError("fill 'Old joints' (select them in order, then <).")
    return {"type": mtype, "side": side, "name": name, "joints": joints}


def ex_queue_add(*_):
    r = _row_now()
    existing.placement(r["type"], r["side"], r["name"], r["joints"], _height())      # checked now
    _q_rows().append(r)
    _q_refresh()


def ex_queue_twin(*_):
    rows = _q_rows()
    idx = cmds.textScrollList(N("ExQueue"), query=True, selectIndexedItem=True) or ([len(rows)] if rows else [])
    if not idx:
        raise RuntimeError("add a row first (or pick one).")
    added = 0
    for i in idx:
        r = rows[i - 1]
        if r["side"] not in "LR":
            continue
        twin = {"type": r["type"], "side": "R" if r["side"] == "L" else "L", "name": r["name"],
                "joints": existing.twin_joints(r["joints"])}
        if not any(x["side"] == twin["side"] and x["name"] == twin["name"] and x["type"] == twin["type"] for x in rows):
            rows.append(twin)
            added += 1
    _q_refresh()
    if not added:
        raise RuntimeError("no twin added (centre rows, or the twin is already in the list).")


def ex_queue_remove(*_):
    idx = cmds.textScrollList(N("ExQueue"), query=True, selectIndexedItem=True) or []
    if not idx:
        raise RuntimeError("pick rows in the list.")
    _queue[_P["p"]] = [r for i, r in enumerate(_q_rows()) if i + 1 not in idx]
    _q_refresh()


def ex_queue_place(*_):
    rows = _q_rows()
    if not rows:
        raise RuntimeError("the list is empty - Add rows first.")
    gs = existing.place_many(rows, _height())
    _queue[_P["p"]] = []
    _q_refresh()
    refresh_list(gs)
    utils.info(TOOL, "%d module(s) placed on their joints. Check their settings, then Build picked." % len(gs))


def ex_legacy_skin(*_):
    plan = existing.legacy_skin_plan()
    if not plan:
        raise RuntimeError("no skin uses joints in legacy_grp - nothing to move.")
    lines = existing.legacy_plan_lines(plan)
    count = sum(1 for rows in plan.values() for _o, n in rows if n)
    ui.report_window("Gus_Rigtool - legacy weights", "\n".join(lines))
    if cmds.confirmDialog(title="Move legacy weights", message="Move the weights of %d old joint(s) to their new "
                          "joints and take the old ones out of the skin?\n(The list is in the report window. "
                          "One undo.)" % count, button=["Move", "Cancel"], defaultButton="Move",
                          cancelButton="Cancel", dismissString="Cancel") != "Move":
        return
    moved, left = existing.repair_legacy_skin(plan)
    utils.info(TOOL, "moved the weights of %d old joint(s) to the new ones%s." % (
        moved, (" - no match for: %s (Skin 6 > Move weights)" % ", ".join(left[:6])) if left else ""),
        "warn" if left else "ok")


def ex_toggle_backup(*_):
    shown = existing.toggle_backup()
    utils.info(TOOL, "%s %s." % (existing.LEGACY, "shown" if shown else "hidden"))


def ex_remove_backup(*_):
    if cmds.confirmDialog(title="Remove backup", button=["Delete", "Cancel"], defaultButton="Cancel",
                          cancelButton="Cancel", dismissString="Cancel",
                          message="Delete %s (the old parts you replaced)? Do this when the new parts work."
                                  % existing.LEGACY) != "Delete":
        return
    existing.remove_backup()


def _existing_page():
    ui.section("1  Scan a part", help_text="Works on any rig. Select a part (its controls, joints or top group) "
               "and Scan: you get its controls, the joints they move, IK limbs, IK/FK switch attributes, skins, "
               "and what hangs from it. The fields below are filled in for you - check them.")
    ui.main_button("Scan selection", _w(_guard(ex_scan)), "Look at the selected part (nothing changes).")
    ui.end_section()

    ui.section("2  Keep it as it is (adopt)", help_text="Adopt a part you made by hand (a face, ribbons...): it "
               "joins the module list as 'adopted'. Nothing in the scene moves. IK/FK limbs you add are taught "
               "(no-jump IK/FK switch here and in Gus Animtool), Publish and mirror pose include it, and builder "
               "modules can hang from its joints.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(95, 160, 50),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Part name")
    cmds.textField(N("ExName"), placeholderText="e.g. face")
    cmds.optionMenu(N("ExSide"))
    for sd in "CLR":
        cmds.menuItem(label=sd)
    cmds.setParent("..")
    _field("ExControls", "Controls", "The part's controls (Scan fills this).")
    _field("ExSpaces", "Spaces it offers", "label = control, ... e.g. root = World_ctrl, cog = COG_ctrl, chest = "
           "Chest_ctrl. Builder modules (IK hands, paws, head) follow them by label. Scan suggests them.",
           pick=False)
    cmds.frameLayout(label="IK/FK limbs in this part (optional)", collapsable=True, collapse=True,
                     marginWidth=4, marginHeight=4)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
    cmds.text(label="Pose the limb so FK and IK line up (rest pose), fill these, then Add limb.", align="left")
    _field("ExLimbName", "Limb name", "e.g. L_arm", pick=False)
    _field("ExFk", "FK controls", "3: upper, middle, end")
    _field("ExJoints", "Joints", "the 3 joints they move")
    _field("ExIk", "IK control", "", multi=False)
    _field("ExPv", "Pole vector", "optional", multi=False)
    _field("ExSwitch", "Switch attr", "select the control, click the attribute in the channel box, then <")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(95, 200), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Values")
    cmds.optionMenu(N("ExValues"))
    for a, b in SWITCH_VALUES:
        cmds.menuItem(label="FK %g  /  IK %g" % (a, b))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Add limb", command=_w(_guard(ex_add_limb)))
    cmds.button(label="Clear limbs", command=_w(_guard(ex_clear_limbs)))
    cmds.setParent("..")
    cmds.textScrollList(N("ExLimbs"), height=50)
    cmds.setParent("..")
    cmds.setParent("..")
    ui.main_button("Adopt", _w(_guard(ex_adopt)), "Add the part to the module list as 'adopted'.")
    ui.end_section()

    ui.section("3  Rebuild it with the builder (place on joints)", help_text="Pick the kind of module, select "
               "the old joints in order, Place: a builder module whose guides sit on your joints. Then check its "
               "settings on 1 Rig builder and Build picked. Step 4 moves the skin and the hook-ups over.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnWidth3=(130, 45, 120),
                   columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2)])
    cmds.optionMenu(N("ExType"), changeCommand=_w(_ex_hint))
    for t_ in existing.placeable():
        cmds.menuItem(label=modules.MODULES[t_].LABEL)
    cmds.optionMenu(N("ExPlaceSide"))
    for sd in "CLR":
        cmds.menuItem(label=sd)
    cmds.textField(N("ExPlaceName"), placeholderText="name (optional)")
    cmds.setParent("..")
    cmds.text(N("ExHint"), label="", align="left", font="smallPlainLabelFont")
    _field("ExPlaceJoints", "Old joints", "in order, root to tip")
    ui.main_button("Place guides on the joints", _w(_guard(ex_place)), "Add the module with its guides on them.")
    cmds.text(label="Several at once: fill the row above, Add to list; Add its twin finds the other side's joints by "
                    "name. Then Place every row.", align="left", wordWrap=True, font="smallPlainLabelFont")
    ui.row(3, 113)
    cmds.button(label="Add to list", command=_w(_guard(ex_queue_add)),
                annotation="The row above (type, side, name, old joints) goes into the list.")
    cmds.button(label="Add its twin", command=_w(_guard(ex_queue_twin)),
                annotation="The picked rows (or the last one) for the other side: joints found by name (L_ <-> R_).")
    cmds.button(label="Remove picked", command=_w(_guard(ex_queue_remove)),
                annotation="From this list only.")
    cmds.setParent("..")
    cmds.textScrollList(N("ExQueue"), height=70, allowMultiSelection=True, font="fixedWidthFont")
    cmds.button(label="Place every row", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(ex_queue_place)),
                annotation="Every row is checked first; one undo.")
    _q_refresh()
    ui.end_section()

    ui.section("4  Replace the old part", help_text="Pick the rebuilt module(s) in the list (built; Ctrl-click "
               "several to replace them together). Old part: the "
               "old part's control groups (its joints are found by themselves). Check hook-ups shows what will "
               "happen. Replace: the skin moves to the new joints (weights unchanged, the mesh doesn't move), "
               "what hung from the old part follows the new one, the old part goes into legacy_grp (hidden).")
    _field("ExOld", "Old part", "the old part's top control groups")
    ui.row(2, 170)
    cmds.button(label="Check hook-ups", command=_w(_guard(ex_check)), annotation="What Replace will do.")
    cmds.button(label="Replace", backgroundColor=ui.MAIN_BG, command=_w(_guard(ex_replace)),
                annotation="Asks first. One undo.")
    cmds.setParent("..")
    ui.end_section()

    ui.section("5  Backup", help_text="legacy_grp holds the old parts you replaced, hidden. Remove it when the new "
               "parts work (it refuses while an old joint still drives a skin). Move legacy weights: skins that "
               "still use old joints in legacy_grp get those weights moved to the new joint at the same spot - "
               "it shows the list and asks first.")
    cmds.button(label="Move legacy weights to the new joints...", height=26, backgroundColor=ui.MAIN_BG,
                command=_w(_guard(ex_legacy_skin)),
                annotation="Old joints (legacy_grp) still in a skin: their weights go to the new joints. Asks first.")
    ui.row(2, 170)
    cmds.button(label="Show / hide backup", command=_w(_guard(ex_toggle_backup)))
    cmds.button(label="Remove backup", command=_w(_guard(ex_remove_backup)))
    cmds.setParent("..")
    ui.end_section()
    _ex_hint()


