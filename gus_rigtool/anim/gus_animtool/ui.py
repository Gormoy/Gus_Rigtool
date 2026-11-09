"""
The Gus Animtool window: a header (Picker, Poses, Update...), the character and frame range, then tabs -
Pick, Pose, Keys, Space, Limbs, Settings - each made of sections with a '?' help, like Gus_Rigtool.
"""

import maya.cmds as cmds

import gus_animtool
from gus_animtool import anim as A
from gus_animtool import keys as K
from gus_animtool import selsets as S
from gus_animtool import tempspace as TS
from gus_animtool import tools as TL
from gus_animtool import tween as T

WINDOW = A.WINDOW
P = A.P
TABS = ["Pick", "Pose", "Keys", "Space", "Limbs", "Settings"]
STEPS = ["1", "2", "3", "5", "10"]
FACTORS = ["0.95", "0.9", "0.8", "0.75", "0.5"]
PIVOT_LABELS = ["Key on the left", "Key on the right", "Last selected key"]
NOISE = ["0.02", "0.05", "0.1", "0.2"]
BLAST = ["50", "75", "100"]
GHOST_N = ["1", "2", "3", "4", "5"]
BACKUP_MIN = ["2", "5", "10", "15"]
BACKUP_KEEP = ["3", "5", "10"]


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

def section(label, help_text="", collapse=False):
    f = cmds.frameLayout(label=label, collapsable=True, collapse=collapse, marginWidth=6, marginHeight=4,
                         annotation=help_text)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    if help_text:
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.text(label="")
        cmds.button(label="?", width=22, height=18, annotation=help_text,
                    command=lambda *_: cmds.confirmDialog(title=label, message=help_text, button=["OK"]))
        cmds.setParent("..")
    return f


def end():
    cmds.setParent("..")
    cmds.setParent("..")


def buttons(items, width=None):
    A._buttons(items, width)


def _menu(name, items, value):
    cmds.optionMenu(P + name, changeCommand=A.guard(_save))
    for i in items:
        cmds.menuItem(label=i)
    try:
        cmds.optionMenu(P + name, edit=True, select=items.index(str(value)) + 1)
    except ValueError:
        pass


def _q(name, items):
    return int(items[cmds.optionMenu(P + name, query=True, select=True) - 1])


def _save(*_):
    try:
        A.set_opt("nudge_step", _q("NudgeStep", STEPS))
        if cmds.optionMenu(P + "InbetweenStep", exists=True):
            A.set_opt("inbetween_step", _q("InbetweenStep", STEPS))
            A.set_opt("offset_step", _q("OffsetStep", STEPS))
        if cmds.optionMenu(P + "PPFactor", exists=True):
            A.set_opt("pushpull_factor", float(FACTORS[cmds.optionMenu(P + "PPFactor", query=True, select=True) - 1]))
            A.set_opt("pushpull_pivot", cmds.optionMenu(P + "PPPivot", query=True, select=True))
        if cmds.optionMenu(P + "Noise", exists=True):
            A.set_opt("noise_amount", float(NOISE[cmds.optionMenu(P + "Noise", query=True, select=True) - 1]))
        if cmds.optionMenu(P + "GhostBefore", exists=True):
            A.set_opt("ghost_before", _q("GhostBefore", GHOST_N))
            A.set_opt("ghost_after", _q("GhostAfter", GHOST_N))
            A.set_opt("ghost_step", _q("GhostStep", STEPS))
        if cmds.optionMenu(P + "BackupMin", exists=True):
            A.set_opt("backup_minutes", _q("BackupMin", BACKUP_MIN))
            A.set_opt("backup_keep", _q("BackupKeep", BACKUP_KEEP))
        if cmds.optionMenu(P + "Blast", exists=True):
            A.set_opt("playblast_scale", int(BLAST[cmds.optionMenu(P + "Blast", query=True, select=True) - 1]))
        A.set_opt("tween_mode", cmds.optionMenu(P + "TweenMode", query=True, select=True))
        A.set_opt("tween_key", cmds.checkBox(P + "TweenKey", query=True, value=True))
    except RuntimeError:
        pass


def _done(text):
    A.message(text)


# ---------------------------------------------------------------------------
# tween slider
# ---------------------------------------------------------------------------

def _tween_mode():
    return cmds.optionMenu(P + "TweenMode", query=True, select=True) - 1


def _amount(value, mode):
    if mode == 0:
        return (value + 100.0) / 200.0              # -100 previous key, 0 half way, 100 next key
    return value / 100.0


def _tween_nodes():
    nodes = [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select controls first.")
    return nodes


def tween_drag(*_):
    mode = _tween_mode()
    T.drag(_tween_nodes(), mode, _amount(cmds.intSliderGrp(P + "Tween", query=True, value=True), mode))


def tween_release(*_):
    mode = _tween_mode()
    value = cmds.intSliderGrp(P + "Tween", query=True, value=True)
    if T._drag.get("start") is None:
        n = T.apply(_tween_nodes(), mode, _amount(value, mode))
    else:
        n = T.release(mode, _amount(value, mode))
    cmds.intSliderGrp(P + "Tween", edit=True, value=0)
    _done("%s %d: %d attribute(s)." % (T.MODES[mode], value, n))


def tween_at(value, *_):
    mode = _tween_mode()
    n = T.apply(_tween_nodes(), mode, _amount(value, mode))
    _done("%s %d: %d attribute(s)." % (T.MODES[mode], value, n))


# ---------------------------------------------------------------------------
# keys / space cleanup / profile / hotkeys
# ---------------------------------------------------------------------------

def _nudge(direction, *_):
    n = K.nudge(direction * _q("NudgeStep", STEPS))
    _done("nudged %d curve(s) / control(s)." % n)


def _clean(*_):
    keys_gone, static = K.clean()
    _done("deleted %d key(s) that changed nothing and %d curve(s) that never change." % (keys_gone, static))


def _pick_menu(name, key, *_):
    A.set_opt(key, cmds.optionMenu(P + name, query=True, select=True))


def _menu_pick(name, labels, key, default=1):
    """A dropdown saved as its position (1, 2, 3...) in the option key."""
    cmds.optionMenu(P + name, changeCommand=A.guard(lambda *_: _pick_menu(name, key)))
    for lb in labels:
        cmds.menuItem(label=lb)
    try:
        A.menu_select(P + name, max(1, min(len(labels), int(A.opt(key, default)))))
    except (RuntimeError, ValueError, TypeError):
        pass


def _space_nodes():
    sel = A.selected()
    return sel or A.character_controls()


def _find_jumps(*_):
    jumps = K.space_jumps(_space_nodes())
    if not jumps:
        _done("no jumps: every keyed space change keeps its control in place.")
        return []
    lines = ["%s.%s at frame %g (%d -> %d)" % (A.short(n), a, t, v0, v1) for n, a, t, v0, v1 in jumps]
    A.message("%d jump(s): %s" % (len(jumps), "; ".join(lines[:3])), "warn")
    return jumps


def _fix_jumps(*_):
    jumps = K.space_jumps(_space_nodes())
    if not jumps:
        _done("no jumps to fix.")
        return
    if cmds.confirmDialog(title="Fix space switch keys", message="%d keyed space change(s) make the control jump:\n"
                          "%s\n\nKey the control in place at each one (and the frame before)?" % (
                              len(jumps), "\n".join("%s.%s at %g" % (A.short(n), a, t) for n, a, t, _a, _b in
                                                    jumps[:12])),
                          button=["Fix", "Cancel"], defaultButton="Fix", cancelButton="Cancel",
                          dismissString="Cancel") != "Fix":
        return
    _done("fixed %d space switch key(s): no jump." % K.fix_space_jumps(jumps))


def _profile_fill(*_):
    if not cmds.text(P + "ProfName", exists=True):
        return
    p = A.profile()
    cmds.text(P + "ProfName", edit=True, label="  Rig: %s   (%s)" % (A.rig_name(), "profile saved" if p else
                                                                      "no profile yet - the general options"))
    for key, name in (("suffix", "PSuffix"), ("left", "PLeft"), ("right", "PRight"), ("control_set", "PSet"),
                      ("control_group", "PGroup")):
        cmds.textField(P + name, edit=True, text=p.get(key, ""))
    _sets_fill()


def _profile_save(*_):
    data = dict(A.profile())
    for key, name in (("suffix", "PSuffix"), ("left", "PLeft"), ("right", "PRight"), ("control_set", "PSet"),
                      ("control_group", "PGroup")):
        v = (cmds.textField(P + name, query=True, text=True) or "").strip()
        if v:
            data[key] = v
        else:
            data.pop(key, None)
    path = A.save_profile(data)
    _profile_fill()
    n = len(A.character_controls())
    _done("profile of '%s' saved (%d controls found with it): %s" % (A.rig_name(), n, path))


def _profile_take(name, *_):
    sel = cmds.ls(selection=True) or []
    if not sel:
        raise RuntimeError("select the set / group first.")
    cmds.textField(P + name, edit=True, text=sel[0].split(":")[-1])


def _hotkeys(on, *_):
    from gus_animtool import hotkeys
    A.set_opt("hotkeys", int(bool(on)))
    if on:
        used = hotkeys.install()
        _done("hotkeys on (hotkey set '%s'): Alt+, / Alt+. nudge, Alt+Shift+, / Alt+Shift+. tween." % used)
    else:
        hotkeys.remove()
        _done("hotkeys off.")


def _update(*_):
    from gus_animtool import updater
    updater.install_dialog()


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

def _push(direction, *_):
    _done("%d key(s) %sed." % (K.push_pull(direction), direction))


def _negate(*_):
    _done("%d key(s) negated." % K.negate())


def _redundant(*_):
    _done("%d redundant key(s) deleted." % K.delete_redundant())


def _rot_order(*_):
    nodes = [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select the controls.")
    order = K.ORDERS[cmds.optionMenu(P + "RotOrder", query=True, select=True) - 1]
    _done("%d control(s) now %s (motion kept)." % (K.convert_rotate_order(nodes, order), order))


def _sets_fill(*_):
    if not cmds.textScrollList(P + "Sets", exists=True):
        return
    cmds.textScrollList(P + "Sets", edit=True, removeAll=True)
    for n in S.names():
        cmds.textScrollList(P + "Sets", edit=True, append=n)


def _set_chosen():
    got = cmds.textScrollList(P + "Sets", query=True, selectItem=True) or []
    if not got:
        raise RuntimeError("pick a set in the list.")
    return got[0]


def _set_save(*_):
    name = cmds.textField(P + "SetName", query=True, text=True) or ""
    if not name.strip():
        try:
            name = _set_chosen()
        except RuntimeError:
            raise RuntimeError("type a name (or pick a set to overwrite).")
    n = S.save(name)
    _sets_fill()
    _done("set '%s': %d control(s), saved in the rig profile." % (name.strip(), n))


def _set_select(add=False, *_):
    _done("%d control(s) selected." % S.select(_set_chosen(), add=add))


def _set_remove(*_):
    name = _set_chosen()
    if cmds.confirmDialog(title="Remove set", message="Remove the set '%s'?" % name, button=["Remove", "Cancel"],
                          defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Remove":
        return
    S.remove(name)
    _sets_fill()


def _temp(which, *_):
    got = {"world": TS.world, "camera": TS.camera, "pivot": TS.pivot}[which]()
    _done("temporary %s space: animate the locator%s, then Bake back." % (which, "" if which == "pivot" else "s"))
    return got


def _bake_back(*_):
    _done("%d control(s) baked back; the temporary spaces are gone." % TS.bake_back())


def _clips(*_):
    from gus_animtool import animlib
    animlib.show()


def _hider(action, *_):
    from gus_animtool import hider as H
    part = H.PARTS[cmds.optionMenu(P + "HidePart", query=True, select=True) - 1]
    what = ["controls", "geo", "both"][cmds.optionMenu(P + "HideWhat", query=True, select=True) - 1]
    if action == "toggle":
        _done("%s %s." % (part, "shown" if H.toggle(part, what) else "hidden"))
    elif action == "isolate":
        _done(("only %s shown." % part) if H.isolate(part, what) else "every part shown.")
    elif action == "all":
        H.show_all("both")
        _done("every part shown.")
    elif action == "add":
        _done("%d added to %s (saved in the rig profile)." % (H.add_selected(part), part))
    elif action == "remove":
        _done("%d taken out of %s." % (H.remove_selected(part), part))
    elif action == "reset":
        H.reset()
        _done("parts found again from the names.")


def _attach_list(*_):
    from gus_animtool import attach as AT
    lines = []
    for n in AT.attached():
        ev = ", ".join("%g: %s" % (f, lb) for f, lb in AT.events(n))
        lines.append("%s - %s" % (A.short(n), ev))
    cmds.scrollField(P + "AttachList", edit=True, text="\n".join(lines) or "nothing attached yet.")


def _attach(what, *_):
    from gus_animtool import attach as AT
    if what == "attach":
        AT.attach()
    elif what == "release":
        AT.release()
    elif what == "bake":
        _done("baked %d frame(s): plain keys, the attach is gone." % AT.bake())
    elif what == "remove":
        sel = [n for n in A.selected() if AT.read(n)]
        if not sel:
            raise RuntimeError("select something attached.")
        for n in sel:
            AT.remove(n)
        _done("attach removed (no bake).")
    _attach_list()


def _backup_toggle(on, *_):
    from gus_animtool import backup
    A.set_opt("backup_on", int(bool(on)))
    if on:
        backup.start()
        _done("crash backup on: a copy every %d minutes when the scene changed." % int(A.opt("backup_minutes", 5)))
    else:
        backup.stop()


def _toolbar_toggle(on, *_):
    from gus_animtool import toolbar
    A.set_opt("toolbar", int(bool(on)))
    if on:
        toolbar.show()
        _done("toolbar under the Time Slider.")
    else:
        toolbar.hide()


def _timeslider_toggle(on, *_):
    from gus_animtool import timeslider
    A.set_opt("timeslider_menu", int(bool(on)))
    if on:
        _done("in the Time Slider's right-click menu." if timeslider.install() else "the Time Slider's menu "
              "wasn't found (it's added next time Gus Animtool opens).")
    else:
        timeslider.remove()


def _make_shelf(*_):
    from gus_animtool import toolbar
    _done("'Gus_Animtool' shelf: %d buttons." % toolbar.make_shelf())


def _toolbar_pick(*_):
    """A small window: a checkbox per tool."""
    from gus_animtool import actions as AC
    from gus_animtool import toolbar
    win = P + "BarPick"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title="Toolbar buttons", widthHeight=(300, 520))
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
    shown = set(toolbar.keys_shown())
    boxes = []
    for k, label, tip, _g in AC.ACTIONS:
        cmds.rowLayout(numberOfColumns=2, columnWidth2=(26, 250))
        cmds.image(image=AC.icon(k), width=24, height=24)
        boxes.append((k, cmds.checkBox(label=label, value=k in shown, annotation=tip)))
        cmds.setParent("..")

    def apply_(*_):
        keys = [k for k, b in boxes if cmds.checkBox(b, query=True, value=True)]
        A.set_opt("toolbar_keys", ",".join(keys) if keys else ",".join(AC.TOOLBAR_DEFAULT))
        toolbar.refresh()
        cmds.deleteUI(win)

    def default_(*_):
        A.set_opt("toolbar_keys", "")
        toolbar.refresh()
        cmds.deleteUI(win)
    cmds.button(label="Apply", height=28, backgroundColor=A.MAIN_BG, command=A.guard(apply_))
    cmds.button(label="Back to the default buttons", command=A.guard(default_))
    cmds.showWindow(win)


def _tab(name):
    cmds.scrollLayout(P + "Tab" + name, childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)


def _end_tab():
    cmds.setParent("..")
    cmds.setParent("..")


def icon_buttons(keys, text=True, per_row=None):
    """Icon buttons for actions (actions.py), sharing the width; text: the label next to the icon."""
    from gus_animtool import actions as AC
    per_row = per_row or len(keys)
    for r in range(0, len(keys), per_row):
        row = keys[r:r + per_row]
        form = cmds.formLayout(height=32, numberOfDivisions=1000)
        attach = []
        for i, k in enumerate(row):
            b = AC.icon_button(k, text=text, backgroundColor=(0.30, 0.31, 0.33), flat=False)
            n = per_row if len(keys) > per_row else len(row)
            attach += [(b, "left", 2, int(1000 * i / n)), (b, "right", 2, int(1000 * (i + 1) / n))]
        cmds.formLayout(form, edit=True, attachPosition=attach)
        cmds.setParent("..")


QUICK = ["key", "tan_auto", "tan_spline", "tan_linear", "tan_flat", "tan_step", "mirror", "flip", "reset", "twin",
         "ikfk", "copy_keys", "paste_keys", "inbetween_remove", "inbetween_add", "offset_minus", "offset_plus",
         "offset_back", "pull", "push", "arcs", "hide_ctrls", "isolate", "playblast"]


def build():
    """The window's content (Maya also runs this when it restores a docked window)."""
    from gus_animtool import actions as AC
    if cmds.formLayout(P + "Root", exists=True):
        return
    if cmds.workspaceControl(WINDOW, exists=True):
        cmds.setParent(WINDOW)
    root = cmds.formLayout(P + "Root")
    top = cmds.columnLayout(P + "Top", adjustableColumn=True, rowSpacing=4)
    head = cmds.formLayout(height=34, backgroundColor=A.HEADER_BG)
    title = cmds.text(label="  Gus Animtool %s" % gus_animtool.__version__, font="boldLabelFont", align="left",
                      backgroundColor=A.HEADER_BG)
    hb = []
    for k, label, tip, fn in (("picker", "Picker", "A button per control (zoom, pan, drag to select; Edit to change "
                                                   "it).", A.show_picker),
                              ("poses", "Poses", "The pose library: save, apply, mirror, blend.", A.show_library),
                              ("clips", "Clips", "The animation library: save clips, apply them here.", _clips),
                              ("update", "Update", "Install a newer zip.", _update)):
        hb.append(cmds.iconTextButton(style="iconAndTextHorizontal", image1=AC.icon(k), label=label, height=30,
                                      annotation=tip, command=A.guard(fn), backgroundColor=A.HEADER_BG))
    attach = [(title, "top", 2), (title, "left", 0), (title, "bottom", 2)]
    for b in hb:
        attach += [(b, "top", 2)]
    cmds.formLayout(head, edit=True, attachForm=attach + [(hb[-1], "right", 4)],
                    attachControl=[(hb[i], "right", 4, hb[i + 1]) for i in range(len(hb) - 1)] +
                    [(title, "right", 4, hb[0])],
                    attachNone=[(b, "left") for b in hb])
    cmds.setParent("..")
    if A.opt("window_icons", 1):
        cmds.columnLayout(P + "Quick", adjustableColumn=True)          # two rows that stretch: all always shown
        icon_buttons(QUICK, text=False, per_row=(len(QUICK) + 1) // 2)
        cmds.setParent("..")
    cmds.text(P + "Status", label="  Select controls, then click. Every action is one undo.", align="left",
              height=22, backgroundColor=A.OK_BG)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 2), (2, "both", 2),
                                                                        (3, "both", 2)])
    cmds.text(label="Character")
    cmds.optionMenu(P + "Char", changeCommand=A.guard(lambda *_: _profile_fill()),
                    annotation="The character the tools work on. Picking a control picks it too.")
    cmds.button(label="Refresh", command=A.guard(A.fill_characters))
    cmds.setParent("..")
    try:
        start, end_ = cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True)
    except (RuntimeError, TypeError):
        start, end_ = 1, 24
    cmds.rowLayout(numberOfColumns=5, columnWidth5=(50, 55, 25, 55, 90),
                   columnAttach=[(i + 1, "both", 2) for i in range(5)])
    cmds.text(label="Frames")
    cmds.intField(P + "Start", value=int(start or 1), annotation="The range for bake, mirror animation, switch over "
                                                                  "the range.")
    cmds.text(label="to")
    cmds.intField(P + "End", value=int(end_ or 24))
    cmds.button(label="Time slider", command=A.guard(A._range_from_slider), annotation="Take the time slider's range.")
    cmds.setParent("..")

    cmds.setParent("..")                                     # out of the top column
    tabs = cmds.tabLayout(P + "Tabs", innerMarginWidth=4, innerMarginHeight=4)
    _pick_tab()
    _pose_tab()
    _keys_tab()
    _space_tab()
    _limbs_tab()
    _settings_tab()
    cmds.tabLayout(tabs, edit=True, tabLabel=[(P + "Tab" + t, t) for t in TABS])
    index = int(A.opt("tab", 1) or 1)
    if 1 <= index <= len(TABS):
        cmds.tabLayout(tabs, edit=True, selectTabIndex=index)
    cmds.tabLayout(tabs, edit=True, changeCommand=lambda *_: A.set_opt(
        "tab", cmds.tabLayout(P + "Tabs", query=True, selectTabIndex=True)))
    cmds.setParent("..")
    cmds.formLayout(root, edit=True, attachForm=[(top, "top", 2), (top, "left", 2), (top, "right", 2),
                                                 (tabs, "left", 2), (tabs, "right", 2), (tabs, "bottom", 2)],
                    attachControl=[(tabs, "top", 4, top)])
    cmds.setParent("..")

    A.fill_characters()
    A.fill_space_menus()
    _profile_fill()
    cmds.scriptJob(event=["SelectionChanged", A.guard(A._follow_selection)], parent=P + "Root")


def _pick_tab():
    _tab("Pick")
    section("Picker and poses", "Picker: a button per control, laid out automatically (Body, Face, Hands, Tweaks "
            "pages; each button shaped like its control, the two sides mirrored). Click: select (Shift add, Ctrl take "
            "away), drag a box, double-click: the limb, right-click: more. Wheel zooms, middle drag pans, F frames. "
            "Edit: move, resize, colour, shape, label, align, mirror, add buttons / sliders / commands / pages, a "
            "background picture - Save keeps it for the rig (every scene). Poses: the pose library.")
    buttons([("Open the picker", A.show_picker, "Click: select. Shift: add / take away. Ctrl: take away."),
             ("Open the pose library", A.show_library, "Save a pose with a picture; apply it, mirrored, blended."),
             ("Animation library", _clips, "Save clips (walk, blink...) and apply them here.")])
    end()
    section("Select", "Every control of the character, the selected limbs' controls, or every FK / IK / tweak "
            "control. Twin: the other side of the selection.")
    buttons([("All controls", lambda *_: A.select_set("all"), "Every control of the character."),
             ("This limb", lambda *_: A.select_set("limb"), "Every control of the selected limbs / chains."),
             ("Twin", lambda *_: A.select_twin("other"), "The other side.")])
    buttons([("FK", lambda *_: A.select_set("fk"), "Every FK control."),
             ("IK", lambda *_: A.select_set("ik"), "Every IK control and pole vector."),
             ("Tweaks", lambda *_: A.select_set("tweaks"), "Every tweak control.")])
    end()
    section("Selection sets", "Your own groups of controls (mouth, L hand...). Saved in the rig profile, so every "
            "scene with this rig has them. Save: the selection under the typed name (or over the picked set). "
            "Double-click a set: select it.")
    cmds.textScrollList(P + "Sets", height=90, allowMultiSelection=False,
                        doubleClickCommand=A.guard(lambda *_: _set_select(False)))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.textField(P + "SetName", annotation="The new set's name.")
    cmds.button(label="Save", width=60, command=A.guard(_set_save), annotation="The selection, as this set.")
    cmds.setParent("..")
    buttons([("Select", lambda *_: _set_select(False), "Select the set."),
             ("Add", lambda *_: _set_select(True), "Add the set to the selection."),
             ("Remove...", _set_remove, "Forget the set (asks first).")])
    end()
    section("Body parts (hider)", "Hide / show a body part (its controls, the meshes you added to it, or both), or "
            "show only that part (Only; again: all back). Parts are found from the control names - change them: "
            "pick a part, select controls / meshes, Add. Saved in the rig profile (every scene with this rig). "
            "Right-click the toolbar's body icon for each part.")
    from gus_animtool import hider as H
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(35, 110, 35, 110), columnAttach=[(i + 1, "both", 2)
                                                                                     for i in range(4)])
    cmds.text(label="Part")
    cmds.optionMenu(P + "HidePart")
    for p_ in H.PARTS:
        cmds.menuItem(label=p_)
    cmds.text(label="Hide")
    _menu_pick("HideWhat", ["Controls", "Meshes", "Both"], "hider_what")
    cmds.setParent("..")
    buttons([("Hide / show", lambda *_: _hider("toggle"), "This part on / off."),
             ("Only this", lambda *_: _hider("isolate"), "Only this part (again: all)."),
             ("Show all", lambda *_: _hider("all"), "Every part back.")])
    buttons([("Add selected", lambda *_: _hider("add"), "The selected controls / meshes join this part."),
             ("Take out", lambda *_: _hider("remove"), "The selected ones leave this part."),
             ("Reset parts", lambda *_: _hider("reset"), "Parts found from the names again.")])
    end()
    section("View", "Arcs: a motion trail per selected control over the frame range (right-click: clear them). "
            "Controls: hide / show the controls in the viewport. Isolate: only the selection in the viewport "
            "(again: everything). Ghosts: see-through copies of the character (or the selected meshes) a few "
            "frames before (blue) and after (orange) - they update when you change keys (right-click: clear). "
            "Playblast: the frame range from the viewport you look through, into the project's movies folder.")
    icon_buttons(["arcs", "hide_ctrls", "isolate"])
    icon_buttons(["ghosts"])
    cmds.rowLayout(numberOfColumns=6, columnWidth6=(45, 45, 40, 45, 35, 45),
                   columnAttach=[(i + 1, "both", 2) for i in range(6)])
    cmds.text(label="Before")
    _menu("GhostBefore", GHOST_N, A.opt("ghost_before", 2))
    cmds.text(label="After")
    _menu("GhostAfter", GHOST_N, A.opt("ghost_after", 2))
    cmds.text(label="Every")
    _menu("GhostStep", STEPS, A.opt("ghost_step", 2))
    cmds.setParent("..")
    end()
    section("Playblast", "The frame range from the viewport you look through, saved as <folder>/<shot>_v001 (the "
            "next free version each time) and opened in your player. HUD: shot (top left), artist and date (top "
            "right), focal length (bottom left), frame / total (bottom right); Maya's own HUDs come back after.")
    o = TL.blast_settings()
    for label, key, value, tip in (("Shot", "blast_shot", o["shot"], "Empty: the scene's name."),
                                   ("Artist", "blast_artist", o["artist"], "Empty: your login name.")):
        cmds.textFieldGrp(P + key, label=label, text=value, columnWidth2=(50, 220), annotation=tip,
                          changeCommand=A.guard(lambda v, k=key: A.set_opt(k, str(v))))
    cmds.textFieldButtonGrp(P + "blast_folder", label="Folder", text=o["folder"], buttonLabel="...",
                            columnWidth3=(50, 190, 30), annotation="Empty: the project's movies folder.",
                            changeCommand=A.guard(lambda v: A.set_opt("blast_folder", str(v))),
                            buttonCommand=A.guard(_blast_folder))
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(110, 45, 50, 60), columnAttach=[(i + 1, "both", 2) for i in range(4)])
    cmds.checkBox(P + "BlastHud", label="HUD", value=o["hud"],
                  changeCommand=A.guard(lambda v: A.set_opt("blast_hud", int(bool(v)))))
    cmds.text(label="Size %")
    _menu("Blast", BLAST, str(int(A.opt("playblast_scale", 100))))
    cmds.text(label="")
    cmds.setParent("..")
    icon_buttons(["playblast"])
    end()
    _end_tab()


def _pose_tab():
    _tab("Pose")
    section("Tween / pose slider", "Between keys: -100 the previous key's pose, 0 half way, 100 the next key's "
            "(type more for overshoot). From rest: + pushes the pose further, - pulls it to rest (-100 = rest). "
            "Mirror: 100 = the twin's pose mirrored. Drag: you see it live; letting go applies it (one undo) and "
            "keys it when 'Key it' is on (or auto key). Hotkeys (Settings): Alt+Shift+, / Alt+Shift+.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.optionMenu(P + "TweenMode", changeCommand=A.guard(_save))
    for m in T.MODES:
        cmds.menuItem(label=m)
    A.menu_select(P + "TweenMode", max(1, min(3, int(A.opt("tween_mode", 1)))))
    cmds.checkBox(P + "TweenKey", label="Key it", value=bool(A.opt("tween_key", 1)), changeCommand=A.guard(_save))
    cmds.setParent("..")
    cmds.intSliderGrp(P + "Tween", field=True, minValue=-100, maxValue=100, fieldMinValue=-200, fieldMaxValue=200,
                      value=0, columnWidth2=(45, 250), dragCommand=A.guard(tween_drag),
                      changeCommand=A.guard(tween_release))
    buttons([(str(v), (lambda *_, x=v: tween_at(x)), "Apply at %d." % v) for v in (-100, -50, -25, 25, 50, 100)],
            width=55)
    end()
    section("Mirror / flip / reset", "Any rig with left / right names. Mirror: the selected controls' twins take "
            "their pose. Flip: both sides swap. Reset: back to rest (the pose saved by Publish on Gus rigs).")
    buttons([("Mirror L -> R", lambda *_: A.mirror_pose("L>R"), "The twins take the pose."),
             ("Mirror R -> L", lambda *_: A.mirror_pose("R>L"), "The other way."),
             ("Flip", A.flip_pose, "Both sides swap poses.")])
    buttons([("Reset selected", lambda *_: A.reset_pose("selection"), "Back to rest."),
             ("Reset character", lambda *_: A.reset_pose("character"), "Every control of the character."),
             ("Select twin", lambda *_: A.select_twin("other"), "The other side.")])
    end()
    section("Copy / paste pose", "Copy the selected controls' pose; paste it on the selected controls with the "
            "same names - in this character or another one (namespace).")
    buttons([("Copy pose", lambda *_: _done("copied %d control(s)." % K.copy_pose()), "The selection's pose."),
             ("Paste pose", lambda *_: _done("pasted on %d control(s)." % K.paste_pose()), "On the selection.")],
            width=165)
    end()
    section("Mirror animation", "Over the frame range: the left side's keys onto the right (or the other way), or "
            "both sides swap. Offset: frames added (half the cycle for a walk); Wrap keeps the cycle closed.")
    buttons([("Anim L -> R", lambda *_: A.mirror_animation("L>R"), "The left side's keys onto the right."),
             ("Anim R -> L", lambda *_: A.mirror_animation("R>L"), "The right side's keys onto the left."),
             ("Flip anim", lambda *_: A.mirror_animation("flip"), "The two sides swap animation.")])
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(50, 60, 220), columnAttach=[(i + 1, "both", 2) for i in range(3)])
    cmds.text(label="Offset")
    cmds.intField(P + "AnimOffset", value=int(A.opt("anim_offset", 0)), changeCommand=A.guard(A._save_options))
    cmds.checkBox(P + "Wrap", label="Wrap inside the range (cycles)", value=bool(A.opt("anim_wrap", 0)),
                  changeCommand=A.guard(A._save_options))
    cmds.setParent("..")
    cmds.separator(height=6, style="in")
    end()
    section("Cycles", "Walk / run: key the first half (1 = left contact ... 13 = right contact), select the "
            "character's controls, Mirror cycle: the second half is made (13-25) and the Time Slider shows the "
            "cycle. Continue cycle: it repeats as keys, the root / COG keeps going forward. To pick frames "
            "yourself, shift-drag in the Time Slider: the first half for Mirror, the whole cycle for Continue.")
    icon_buttons(["mirror_cycle", "cycle_continue"])
    cmds.checkBox(P + "CycleLoop", label="Loop the curves (cycle before / after)", value=bool(A.opt("cycle_loop", 1)),
                  changeCommand=A.guard(lambda v: A.set_opt("cycle_loop", int(bool(v)))))
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(110, 50, 160), columnAttach=[(i + 1, "both", 2) for i in range(3)])
    cmds.text(label="Continue: repeat", align="left")
    cmds.intField(P + "CycleTimes", value=int(A.opt("cycle_times", 3)), minValue=1, maxValue=100,
                  changeCommand=A.guard(lambda v: A.set_opt("cycle_times", int(v))))
    cmds.text(label="more time(s)", align="left")
    cmds.setParent("..")
    cmds.checkBox(P + "CycleForward", label="Keep going forward (controls that travel: root, COG)",
                  value=bool(A.opt("cycle_forward", 1)),
                  changeCommand=A.guard(lambda v: A.set_opt("cycle_forward", int(bool(v)))))
    cmds.checkBox(P + "CycleScope", label="Whole character (off: only the selected controls)",
                  value=int(A.opt("cycle_scope", 1)) == 1,
                  changeCommand=A.guard(lambda v: A.set_opt("cycle_scope", 1 if v else 2)))
    buttons([("Loop curves instead (no keys)", lambda *_: __import__("gus_animtool.cycle", fromlist=["x"])
              .continue_with_curves(), "The curves repeat after the cycle; travelling ones keep going.")])
    cmds.text(label="In place: the walk loops on the spot (the root's steady travel taken out; bounce and sway "
              "stay). Forward: the travel back, exactly.", align="left", wordWrap=True)
    icon_buttons(["cycle_place", "cycle_forward"])
    end()
    _end_tab()


def _stretch_sync(which):
    from gus_animtool import tools
    try:
        first, last = tools.stretch_range()
    except Exception:                              # building the window must never fail on this
        return
    old = last - first + 1
    if old <= 0 or not cmds.intField(P + "StretchLen", exists=True):
        return
    if which == "len":
        n = cmds.intField(P + "StretchLen", query=True, value=True)
        cmds.intField(P + "StretchPct", edit=True, value=int(round(100.0 * n / old)))
    else:
        pct = cmds.intField(P + "StretchPct", query=True, value=True)
        cmds.intField(P + "StretchLen", edit=True, value=int(round(old * pct / 100.0)))


def _stretch_go(*_):
    from gus_animtool import tools
    tools.stretch(cmds.intField(P + "StretchLen", query=True, value=True))
    _stretch_sync("pct")


def _blast_folder(*_):
    got = cmds.fileDialog2(fileMode=3, caption="Playblast folder")
    if got:
        A.set_opt("blast_folder", got[0])
        cmds.textFieldButtonGrp(P + "blast_folder", edit=True, text=got[0])


def _keys_tab():
    _tab("Keys")
    section("Nudge", "Keys selected in the Graph Editor - or the selection's keys at the current frame - move by "
            "the step; the current frame follows. Hotkeys (Settings): Alt+, / Alt+.")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 70, 50, 60), columnAttach=[(i + 1, "both", 2)
                                                                                   for i in range(4)])
    cmds.button(label="<  Earlier", command=A.guard(lambda *_: _nudge(-1)))
    cmds.button(label="Later  >", command=A.guard(lambda *_: _nudge(1)))
    cmds.text(label="frames")
    _menu("NudgeStep", STEPS, A.opt("nudge_step", 1))
    cmds.setParent("..")
    end()
    section("Copy / paste keys", "Copy: the selected controls' keys at the current frame (no key there: their pose), "
            "or every key in the range you shift-drag in the Time Slider. Paste: from the current frame on, matched "
            "by control name (one control copied: pasted on every selected one); the keys already in that span "
            "go, unless 'Merge' is ticked. Also in the Time Slider's right-click menu. Right-click the buttons: the "
            "whole animation.")
    icon_buttons(["copy_keys", "paste_keys"])
    cmds.checkBox(P + "PasteMerge", label="Merge (keep the keys already there)", value=bool(A.opt("paste_merge", 0)),
                  changeCommand=A.guard(lambda v: A.set_opt("paste_merge", int(bool(v)))))
    end()
    section("Inbetweens", "Add: every key after the current frame moves later by the step (more time). Remove: the "
            "frames after the current one go (their keys too) and the rest moves earlier. On: the selected "
            "controls, the whole character, or everything animated in the scene. Hotkeys: Alt+] / Alt+[.")
    icon_buttons(["inbetween_remove", "inbetween_add"])
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(40, 50, 25, 200), adjustableColumn=4,
                   columnAttach=[(i + 1, "both", 2) for i in range(4)])
    cmds.text(label="Step")
    _menu("InbetweenStep", STEPS, A.opt("inbetween_step", 1))
    cmds.text(label="On")
    _menu_pick("InbetweenScope", K.SCOPE_LABELS, "inbetween_scope")
    cmds.setParent("..")
    end()
    section("Offset", "Offset - / +: every key of the selected controls moves by the step - all the same, or cascading "
            "(select base to tip: the first stays, each next one a step more - overlap). Back to original: the "
            "timing from before any offset comes back (saved in the scene). Keep as original: the current timing "
            "becomes the original.")
    icon_buttons(["offset_minus", "offset_plus"])
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(40, 50, 40, 200), adjustableColumn=4,
                   columnAttach=[(i + 1, "both", 2) for i in range(4)])
    cmds.text(label="Step")
    _menu("OffsetStep", STEPS, A.opt("offset_step", 1))
    cmds.text(label="Mode")
    _menu_pick("OffsetMode", ["All the same", "Cascade (base to tip)"], "offset_mode")
    cmds.setParent("..")
    buttons([("Back to original", lambda *_: _done("%d curve(s) back to their original timing." %
                                                   K.back_to_original()), "Every offset undone."),
             ("Keep as original", lambda *_: (K.keep_as_original(), _done("the current timing is the new "
                                                                          "original.")), "Forget the offsets.")])
    end()
    section("Keys", "Key (keep the curve): a key on every keyed attribute without changing the motion. Clean up: "
            "keys that change nothing and curves that never change go (values kept). Euler filter: fixes "
            "rotation flips.")
    buttons([("Key (keep the curve)", lambda *_: _done("keyed %d control(s)." % K.key_keep_curve()),
              "A key without changing the curves."),
             ("Clean up keys", _clean, "Delete keys / curves that change nothing."),
             ("Euler filter", lambda *_: _done("filtered %d rotation curve(s)." % K.euler()), "Fix rotation flips.")])
    end()
    section("Tangents", "Auto, spline, linear, flat, stepped: the keys selected in the Graph Editor - or, with none "
            "selected, the selection's keys at the current frame.")
    icon_buttons(["tan_auto", "tan_spline", "tan_linear", "tan_flat", "tan_step"])
    cmds.text(label="Blocking / spline: the whole character's keys stepped for blocking (new keys too), then back "
              "to spline in one click - each key gets its own tangent back.", align="left", wordWrap=True)
    icon_buttons(["blocking"])
    end()
    section("Retime", "Reverse: the keys in the frame range play backwards. Time scale: the keys after the current "
            "frame spread x1.25 (right-click: x0.5 ... x2), snapped to whole frames.")
    icon_buttons(["reverse", "time_scale", "stretch"])
    cmds.text(label="Slower / faster: the whole character over the Time Slider range (or a shift-drag highlight) "
              "becomes this many frames; later keys follow, keys land on whole frames.", align="left", wordWrap=True)
    cmds.rowLayout(numberOfColumns=5, columnWidth5=(70, 50, 40, 50, 80),
                   columnAttach=[(i + 1, "both", 2) for i in range(5)])
    cmds.text(label="New length", align="left")
    cmds.intField(P + "StretchLen", value=0, minValue=0, maxValue=1000000, step=1, changeCommand=A.guard(lambda *_: _stretch_sync("len")))
    cmds.text(label="frames")
    cmds.intField(P + "StretchPct", value=150, minValue=1, maxValue=1000000, step=1, changeCommand=A.guard(lambda *_: _stretch_sync("pct")))
    cmds.text(label="%", align="left")
    cmds.setParent("..")
    buttons([("Stretch", A.guard(_stretch_go), "Apply: the motion becomes the new length (one undo)."),
             ("Now", A.guard(lambda *_: _stretch_sync("pct")), "Read the Time Slider range again.")])
    _stretch_sync("pct")
    end()
    section("Bake / reduce", "Bake: a key every N frames over the frame range on every animated channel (the "
            "scope of inbetweens: selection, character or everything) - keys outside the range stay. Reduce: "
            "removes the keys that don't change the curve's shape (within the tolerance, a share of each "
            "curve's range); first, last, highs and lows always stay.")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(70, 45, 80, 50), columnAttach=[(i + 1, "both", 2) for i in range(4)])
    cmds.text(label="Bake every", align="left")
    cmds.intField(P + "BakeStep", value=int(A.opt("bake_step", 1)), minValue=1, maxValue=24,
                  changeCommand=A.guard(lambda v: A.set_opt("bake_step", int(v))))
    cmds.text(label="Tolerance %", align="right")
    cmds.floatField(P + "ReduceTol", value=float(A.opt("reduce_tolerance", 0.01)) * 100, minValue=0.01,
                    maxValue=50, precision=2, changeCommand=A.guard(lambda v: A.set_opt("reduce_tolerance",
                                                                                      float(v) / 100.0)))
    cmds.setParent("..")
    icon_buttons(["bake_keys", "reduce_keys"])
    end()
    section("Curves", "Smooth: each selected Graph Editor key moves half way to the average of its neighbours. "
            "Noise: a small random offset on the selected keys (a share of the curve's range). Euler: fixes "
            "rotation flips.")
    icon_buttons(["smooth", "noise", "euler"])
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(90, 70), columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="Noise amount")
    _menu("Noise", NOISE, "%g" % float(A.opt("noise_amount", 0.05)))
    cmds.setParent("..")
    end()
    section("Graph Editor keys  (push / pull / negate)", "On the keys selected in the Graph Editor, each curve on its "
            "own. Pull: the keys' values move towards the pivot key (softer); Push: away from it (bigger). Negate: "
            "flipped upside down around the pivot key (the opposite pose). Delete redundant: selected keys with the "
            "same value as both neighbours go. Ideas from Aaron Koressel's ack scripts. Hotkeys (Settings): "
            "Alt+- pull, Alt+= push, Alt+Shift+- negate.")
    buttons([("Pull", lambda *_: _push("pull"), "Towards the pivot key."),
             ("Push", lambda *_: _push("push"), "Away from the pivot key."),
             ("Negate", _negate, "Flip around the pivot key."),
             ("Delete redundant", _redundant, "Selected keys that change nothing.")])
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(40, 125, 45, 60), columnAttach=[(i + 1, "both", 2)
                                                                                    for i in range(4)])
    cmds.text(label="Pivot")
    cmds.optionMenu(P + "PPPivot", changeCommand=A.guard(_save), annotation="The key the values scale around.")
    for lab in PIVOT_LABELS:
        cmds.menuItem(label=lab)
    try:
        A.menu_select(P + "PPPivot", min(3, max(1, int(A.opt("pushpull_pivot", 1)))))
    except (RuntimeError, ValueError, TypeError):
        pass
    cmds.text(label="Factor")
    _menu("PPFactor", FACTORS, "%g" % float(A.opt("pushpull_factor", 0.9)))
    cmds.setParent("..")
    end()
    section("Rotate order", "The selected controls get the new rotate order; their rotation keys are re-made so the "
            "motion doesn't change (Euler filter after). Without keys: the pose stays.", collapse=True)
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(80, 200), columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.optionMenu(P + "RotOrder", annotation="The new rotate order.")
    for o in K.ORDERS:
        cmds.menuItem(label=o)
    cmds.button(label="Convert (keep the motion)", command=A.guard(_rot_order))
    cmds.setParent("..")
    end()
    _end_tab()


def _space_tab():
    _tab("Space")
    section("Space switch  (any rig)", "Change a space / follow / parent attribute with no jump: the control stays "
            "where it is. Over the frame range: the new space on every key (or frame), the motion in the world "
            "stays.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(150, 110, 70),
                   columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 2)])
    cmds.optionMenu(P + "SpaceAttr", changeCommand=A.guard(A.fill_space_values),
                    annotation="The selected control's space / follow attribute.")
    cmds.optionMenu(P + "SpaceValue", annotation="The new space.")
    cmds.button(label="Switch", command=A.guard(A.space_switch), backgroundColor=A.MAIN_BG,
                annotation="The control changes space and stays exactly where it is.")
    cmds.setParent("..")
    cmds.button(label="Switch over the frame range (keeps the motion)", command=A.guard(A.space_switch_range))
    cmds.checkBox(P + "KeysOnly", label="Only at the keys in the range (else every frame)",
                  value=bool(A.opt("range_keys_only", 1)), changeCommand=A.guard(A._save_options))
    end()
    section("Space switch key cleanup", "Finds keyed space changes that make the control jump (keyed without a "
            "no-jump switch), on the selection or the whole character. Fix keys the control in place at each one "
            "(and the frame before) and makes the space key stepped.")
    buttons([("Find jumps", _find_jumps, "List them (nothing changes)."),
             ("Fix jumps...", _fix_jumps, "Asks first. One undo.")], width=165)
    end()
    section("Temporary spaces", "World: a locator per selected control follows it over the frame range, then the "
            "control follows the locator - animate in world space. Camera: the same, seen from the camera you look "
            "through (arcs, screen spacing). Pivot: a locator at the control - move it, then turn it to rotate "
            "around a new pivot. Bake back: the controls keep the motion as keys; the helpers go.")
    buttons([("World", lambda *_: _temp("world"), "Animate the selection in world space."),
             ("Camera", lambda *_: _temp("camera"), "Animate it in the camera's space."),
             ("Pivot", lambda *_: _temp("pivot"), "A temporary pivot for the selection.")])
    cmds.button(label="Bake back (keep the motion)", command=A.guard(_bake_back), backgroundColor=A.MAIN_BG)
    end()
    section("Attach props", "Select what FOLLOWS, then what it holds on to (last), Attach: from this frame it "
            "follows, no jump. A box then the hand: the box follows the hand (fingers never move it). The IK hand "
            "then the box: the hand follows the box. Attach again later to something else (the other hand, a "
            "table). Release: from this frame it stays where it is. Change the grip: Release, move the hand, Attach "
            "again at the same frame. Its own keys still work on top. Bake: plain keys every frame of the range, "
            "the attach goes. Coloured bookmarks on the Time Slider show when it's held (Maya 2020+).")
    icon_buttons(["attach", "release"])
    buttons([("Bake to keys", lambda *_: _attach("bake"), "Plain keys over the frame range; the attach goes."),
             ("Remove (no bake)", lambda *_: _attach("remove"), "The attach goes; it follows its parent again."),
             ("List", _attach_list, "What's attached, and from which frame to what.")])
    cmds.scrollField(P + "AttachList", height=60, editable=False, wordWrap=True, text="")
    end()
    _end_tab()


def _limbs_tab():
    _tab("Limbs")
    section("IK / FK  (Gus_Rigtool rigs and taught limbs)", "Select any control of a limb or chain. Switch: no jump "
            "(keyed on the frame before and this one when 'Key on switch' is on). Bake: every frame of the range, "
            "the other mode holds the motion - Gus rigs and limbs you taught.")
    buttons([("Switch", lambda *_: A.switch("toggle"), "Each selected limb goes to the other mode."),
             ("To FK", lambda *_: A.switch("fk"), "FK takes the IK pose."),
             ("To IK", lambda *_: A.switch("ik"), "IK takes the FK pose.")])
    buttons([("Bake to FK", lambda *_: A.bake("fk"), "Every frame of the range: FK holds the motion, keyed."),
             ("Bake to IK", lambda *_: A.bake("ik"), "Every frame of the range: IK holds the motion, keyed.")],
            width=165)
    end()
    section("Overlap / follow-through", "Select a chain's controls base to tip (tail, ears, antenna, hair - or "
            "only the first one). Over the frame range each one swings behind what it hangs on, springs and "
            "settles - baked to rotation keys you can edit. More towards the tip. Cycle: it loops without a jump.")
    rows = (("Stiffness", "overlap_stiffness", 0.3, 0.02, 1.0, "Higher: follows faster, less lag."),
            ("Damping", "overlap_damping", 0.35, 0.0, 1.0, "Higher: settles sooner, less wobble."),
            ("Amount", "overlap_amount", 1.0, 0.0, 2.0, "How much of it goes on the keys (1 = all)."),
            ("Tip looser", "overlap_tip", 0.5, 0.0, 0.95, "How much looser the tip is than the base."))
    for label, key, default, lo, hi, tip in rows:
        cmds.floatSliderGrp(P + key, label=label, field=True, minValue=lo, maxValue=hi, precision=2, step=0.01,
                            fieldStep=0.01, value=float(A.opt(key, default)), columnWidth3=(70, 50, 150),
                            annotation=tip,
                            changeCommand=A.guard(lambda v, k=key: A.set_opt(k, float(v))))
    cmds.checkBox(P + "OverlapCycle", label="Cycle (settle over one loop first)", value=bool(A.opt("overlap_cycle", 0)),
                  changeCommand=A.guard(lambda v: A.set_opt("overlap_cycle", int(bool(v)))))
    icon_buttons(["overlap"])
    end()
    section("Jiggle  (Gus_Rigtool chains)", "Chains built with the Jiggle option (ears, tail) follow through when what "
            "they hang from moves, while you play. Set the amount with 'jiggle' on the chain's settings control "
            "(0 = off). Bake: the jiggle becomes keys over the frame range (scrubbing then shows it exactly).")
    buttons([("Bake jiggle to keys", lambda *_: _done("jiggle baked on %d group(s)." % TL.bake_jiggle()),
              "Plays through the frame range and keys the jiggle.")], width=330)
    end()
    section("Teach a limb  (IK / FK for other rigs)", "Put the rig in a pose where FK and IK line up (the rest pose), "
            "fill these (< takes the selection), Teach. Saved in the scene; Export / Import to use it in other "
            "scenes.", collapse=True)
    for key, label, tip in (("TName", "Name", "e.g. L_arm"),
                            ("TFk", "FK controls", "3, top to bottom (select them in order)"),
                            ("TJoints", "Joints", "the 3 joints they move: upper, middle, end"),
                            ("TIk", "IK control", ""), ("TPv", "Pole vector", "optional"),
                            ("TSwitch", "Switch attr", "select the control, click the attribute in the channel "
                                                       "box, then <")):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(75, 200, 25),
                       columnAttach=[(1, "right", 2), (2, "both", 2), (3, "both", 2)])
        cmds.text(label=label)
        cmds.textField(P + key, annotation=tip)
        if key != "TName":
            cmds.button(label="<", command=A.guard(lambda *_, k=key: A._teach_take(k)), annotation="Take the selection.")
        else:
            cmds.text(label="")
        cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(75, 200), columnAttach=[(1, "right", 2), (2, "both", 2)])
    cmds.text(label="Values")
    cmds.optionMenu(P + "TValues", annotation="The switch values for FK and IK.")
    for a, b in A.SWITCH_VALUES:
        cmds.menuItem(label="FK %g  /  IK %g" % (a, b))
    cmds.setParent("..")
    buttons([("Teach", A._teach, "Save this limb (in the scene)."),
             ("Forget", A._forget, "Forget the limb named above."),
             ("Export...", A._export_taught, "Save the taught limbs to a file."),
             ("Import...", A._import_taught, "Load taught limbs from a file.")])
    cmds.text(P + "TList", label=A._taught_label(), align="left")
    end()
    _end_tab()


def _settings_tab():
    _tab("Settings")
    section("Options", "Key on switch: IK/FK and space switches key the frame before and the switch frame. Custom "
            "attributes: mirror / reset / poses include them (ikfk, stretch...). Left / right and control suffix: "
            "for every rig without its own profile.")
    cmds.checkBox(P + "KeySwitch", label="Key on switch (the frame before and the switch frame)",
                  value=bool(A.opt("key_switch", 1)), changeCommand=A.guard(A._save_options))
    cmds.checkBox(P + "Custom", label="Mirror / reset custom attributes too (ikfk, stretch...)",
                  value=bool(A.opt("pose_custom", 1)), changeCommand=A.guard(A._save_options))
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(90, 60, 50, 60), columnAttach=[(i + 1, "both", 2)
                                                                                   for i in range(4)])
    cmds.text(label="Left / right")
    cmds.textField(P + "Left", text=A.opt("left", A.DEFAULT_PAIRS[0][0]), changeCommand=A.guard(A._save_options))
    cmds.text(label="/")
    cmds.textField(P + "Right", text=A.opt("right", A.DEFAULT_PAIRS[0][1]), changeCommand=A.guard(A._save_options))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(90, 170), columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="Control suffix")
    cmds.textField(P + "Suffix", text=A.opt("suffix", A.DEFAULT_SUFFIX), changeCommand=A.guard(A._save_options),
                   annotation="Left at _ctrl: controls are found automatically on any rig (names like _ctrl / _CTL / _con, controller tags, controls sets, and hand-made curves you can key). Type your own (several: _ctrl, _CON) to use only those names. Empty: any curve.")
    cmds.setParent("..")
    end()
    section("Rig profile (this rig, every scene)", "How to read THIS rig - saved by rig name in the shared folder, "
            "so every scene with this rig uses it. Blank fields use the options above. Control set: a selection "
            "set holding the controls. Control group: every curve under it is a control.")
    cmds.text(P + "ProfName", label="", align="left", font="boldLabelFont")
    for name, label, tip in (("PSuffix", "Control suffix", "e.g. _CTRL"), ("PLeft", "Left token", "e.g. Lf_"),
                             ("PRight", "Right token", "e.g. Rt_"), ("PSet", "Control set", "a selection set"),
                             ("PGroup", "Control group", "every curve under it")):
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(90, 170, 30),
                       columnAttach=[(1, "right", 2), (2, "both", 2), (3, "both", 2)])
        cmds.text(label=label)
        cmds.textField(P + name, annotation=tip)
        if name in ("PSet", "PGroup"):
            cmds.button(label="<", command=A.guard(lambda *_, x=name: _profile_take(x)), annotation="The selection.")
        else:
            cmds.text(label="")
        cmds.setParent("..")
    cmds.button(label="Save the profile", height=26, backgroundColor=A.MAIN_BG, command=A.guard(_profile_save))
    end()
    section("Hotkeys", "Off until you turn them on. Maya's default hotkey set can't change, so a 'Gus_Animtool' set "
            "(a copy of yours) is made and used. Alt+, / Alt+.: nudge keys. Alt+Shift+, / Alt+Shift+.: a third "
            "towards the previous / next key. Alt+- / Alt+=: pull / push the selected keys. Alt+Shift+-: negate "
            "them. Alt+] / Alt+[: add / remove an inbetween. They're also in the Hotkey Editor's Custom Scripts > "
            "Gus Animtool, to bind your own.")
    cmds.checkBox(P + "Hotkeys", label="Hotkeys on", value=bool(A.opt("hotkeys", 0)),
                  changeCommand=A.guard(lambda v: _hotkeys(v)))
    end()
    section("Toolbar, shelf and window", "Toolbar: the everyday tools as icons under the Time Slider (drag its "
            "tab to move it; Maya remembers). Shelf: a 'Gus_Animtool' shelf with every tool (right-click a button "
            "for more). Window: floating (drag its tab onto Maya's side to dock it) or docked next to the Channel "
            "Box; the icon row at the top.")
    cmds.checkBox(P + "Toolbar", label="Toolbar under the Time Slider", value=bool(A.opt("toolbar", 0)),
                  changeCommand=A.guard(_toolbar_toggle))
    buttons([("Toolbar buttons...", _toolbar_pick, "Which tools the toolbar shows."),
             ("Make the shelf", _make_shelf, "The 'Gus_Animtool' shelf (its buttons are replaced, never doubled).")])
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(70, 200),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="Window")
    cmds.optionMenu(P + "Dock", changeCommand=A.guard(lambda *_: A.set_opt(
        "dock", cmds.optionMenu(P + "Dock", query=True, select=True))), annotation="How the window opens next time.")
    for d in DOCK:
        cmds.menuItem(label=d)
    A.menu_select(P + "Dock", max(1, min(2, int(A.opt("dock", 1)))))
    cmds.setParent("..")
    cmds.checkBox(P + "TSMenu", label="Gus Animtool in the Time Slider's right-click menu",
                  value=bool(A.opt("timeslider_menu", 1)), changeCommand=A.guard(_timeslider_toggle))
    cmds.checkBox(P + "Icons", label="Icon row at the top of the window (next time it opens)",
                  value=bool(A.opt("window_icons", 1)),
                  changeCommand=A.guard(lambda v: A.set_opt("window_icons", int(bool(v)))))
    end()
    section("Crash backup", "Off until you turn it on. Every few minutes, if the scene changed, a copy is saved to "
            "<maya>/gus_anim_backups/<scene>/ (your scene itself is untouched). The last few copies are kept. "
            "Recover: the list of copies by time - open one after a crash.")
    cmds.checkBox(P + "Backup", label="Save a backup copy every", value=bool(A.opt("backup_on", 0)),
                  changeCommand=A.guard(_backup_toggle))
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(55, 60, 45, 60), columnAttach=[(i + 1, "both", 2)
                                                                                   for i in range(4)])
    _menu("BackupMin", BACKUP_MIN, A.opt("backup_minutes", 5))
    cmds.text(label="minutes, keep")
    _menu("BackupKeep", BACKUP_KEEP, A.opt("backup_keep", 5))
    cmds.text(label="copies")
    cmds.setParent("..")
    buttons([("Recover...", lambda *_: __import__("gus_animtool.backup", fromlist=["x"]).show_recover(),
              "The backups by time - open one."),
             ("Back up now", lambda *_: _done("backup: %s" % __import__("gus_animtool.backup", fromlist=["x"])
                                               .backup_now(force=True)), "A copy right now.")])
    end()
    section("Update", "Pick the newest Gus Animtool zip (or a Gus_Rigtool zip): it installs and restarts. The old "
            "files are kept as gus_animtool_backup.")
    buttons([("Update...", _update, "Install a newer zip.")], width=330)
    cmds.text(label="  Gus Animtool %s" % gus_animtool.__version__, align="left")
    end()
    _end_tab()


DOCK = ["Floating (drag its tab to dock it)", "Docked next to the Channel Box"]


def show():
    """The window. Floating by default - drag its tab onto Maya's side to dock it; Maya remembers where."""
    A.track_selection_order()
    if cmds.workspaceControl(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    flags = {"floating": True}
    if int(A.opt("dock", 1)) == 2 and cmds.workspaceControl("ChannelBoxLayerEditor", exists=True):
        flags = {"tabToControl": ("ChannelBoxLayerEditor", -1)}
    import gus_animtool
    cmds.workspaceControl(WINDOW, label="Gus Animtool %s" % gus_animtool.__version__, retain=False, initialWidth=400,
                          initialHeight=720,
                          minimumWidth=340, widthProperty="preferred",
                          uiScript="import gus_animtool.ui as _u; _u.build()", **flags)
    if not cmds.formLayout(P + "Root", exists=True):
        build()
    if A.opt("toolbar", 0):
        from gus_animtool import toolbar
        toolbar.show()
    try:
        from gus_animtool import backup, timeslider
        timeslider.install()
        backup.ensure()
    except Exception:                                        # never stop the window from opening
        pass
    return WINDOW
