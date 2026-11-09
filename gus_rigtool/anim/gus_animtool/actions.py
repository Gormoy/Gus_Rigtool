"""
Every one-click action of Gus Animtool, in one list: the shelf, the Time Slider toolbar and the window's icon
row are made from it. Each action: key (its icon is icons/ga_<key>.png), label, tooltip, the call, and a
right-click menu [(label, call)].

    import gus_animtool.actions as a; a.run("key")
"""

import os

import maya.cmds as cmds

import gus_animtool
from gus_animtool import anim as A

_I = "import gus_animtool.actions as _ga; _ga.run(%r)"

# (key, label, tooltip, group)
ACTIONS = [
    ("main", "Gus Animtool", "The Gus Animtool window", "open"),
    ("picker", "Picker", "The picker: a button per control (edit it with Edit)", "open"),
    ("poses", "Poses", "The pose library", "open"),
    ("clips", "Clips", "The animation library: save a clip, apply it here (mirrored, insert...)", "open"),
    ("tween_prev", "Tween <", "A third towards the previous key's pose (Alt+Shift+,)", "tween"),
    ("tween_next", "Tween >", "A third towards the next key's pose (Alt+Shift+.)", "tween"),
    ("nudge_left", "Nudge <", "Keys one step earlier (Alt+,)", "keys"),
    ("nudge_right", "Nudge >", "Keys one step later (Alt+.)", "keys"),
    ("key", "Key", "Key the selection without changing its curves (right-click: key everything)", "keys"),
    ("tan_auto", "Auto", "Auto tangents: selected Graph Editor keys, else the keys at this frame", "tangents"),
    ("tan_spline", "Spline", "Spline tangents", "tangents"),
    ("tan_linear", "Linear", "Linear tangents", "tangents"),
    ("tan_flat", "Flat", "Flat tangents", "tangents"),
    ("tan_step", "Stepped", "Stepped tangents", "tangents"),
    ("blocking", "Blocking / spline", "The whole character: every key stepped for blocking (new keys too), or back "
     "to spline (right-click: choose, scope)", "tangents"),
    ("mirror", "Mirror", "Mirror the pose left -> right (right-click: right -> left)", "pose"),
    ("flip", "Flip", "Both sides swap poses", "pose"),
    ("reset", "Reset", "The selection back to rest (right-click: the whole character)", "pose"),
    ("twin", "Twin", "Select the other side", "pose"),
    ("ikfk", "IK/FK", "Switch the selected limbs, no jump", "pose"),
    ("copy_keys", "Copy keys", "Copy the selection's keys at this frame, or in the range shift-dragged in the "
     "Time Slider (right-click: the whole animation)", "anim"),
    ("paste_keys", "Paste keys", "Paste them from this frame on, by control name (right-click: merge, whole "
     "animation)", "anim"),
    ("inbetween_add", "Add inbetween", "Every key after this frame one step later (Alt+]; right-click: scope)",
     "anim"),
    ("inbetween_remove", "Remove inbetween", "The frames after this one go, the rest moves earlier (Alt+[; "
     "right-click: scope)", "anim"),
    ("offset_minus", "Offset -", "The selection's keys one step earlier (right-click: same / cascade)", "anim"),
    ("offset_plus", "Offset +", "The selection's keys one step later (right-click: same / cascade)", "anim"),
    ("offset_back", "Back to original", "Offsets undone: the timing from before any offset (right-click: keep "
     "as original)", "anim"),
    ("mirror_cycle", "Mirror cycle", "Key the first half (e.g. 1-13): it's mirrored onto the second half (13-25), "
     "the Time Slider set to the cycle (right-click: without looping)", "anim"),
    ("cycle_continue", "Continue cycle", "The cycle repeats more times as keys; the root keeps going forward "
     "(right-click: how many, no keys)", "anim"),
    ("cycle_place", "Cycle in place", "The walk loops on the spot: the root's steady forward travel taken out "
     "(Forward puts it back)", "anim"),
    ("cycle_forward", "Cycle forward", "The travel taken out by In place put back", "anim"),
    ("bake_keys", "Bake keys", "A key every N frames over the frame range (right-click: 1, 2, 4)", "anim"),
    ("reduce_keys", "Reduce keys", "Fewer keys, same motion (right-click: tolerance)", "anim"),
    ("overlap", "Overlap", "The selected chain (base to tip) swings behind and settles, baked to keys "
     "(right-click: softer / stiffer, cycle)", "anim"),
    ("stretch", "Slower / faster", "The whole character's motion over the Time Slider range becomes N frames - "
     "slower or faster (right-click: 150%, 200%, 75%...)", "anim"),
    ("reverse", "Reverse", "The keys in the frame range play backwards", "anim"),
    ("time_scale", "Time scale", "Keys after this frame spread x1.25 (right-click: other amounts)", "anim"),
    ("pull", "Pull", "Selected keys towards the pivot key (Alt+-)", "curves"),
    ("push", "Push", "Selected keys away from the pivot key (Alt+=)", "curves"),
    ("negate", "Negate", "Selected keys flipped around the pivot key (Alt+Shift+-)", "curves"),
    ("smooth", "Smooth", "Selected keys towards their neighbours", "curves"),
    ("noise", "Noise", "A little noise on the selected keys", "curves"),
    ("redundant", "Redundant", "Delete selected keys that change nothing", "curves"),
    ("euler", "Euler", "Fix rotation flips", "curves"),
    ("temp_world", "World space", "Animate the selection in world space for a while", "space"),
    ("temp_pivot", "Temp pivot", "A temporary pivot for the selection", "space"),
    ("bake_back", "Bake back", "Temporary spaces baked back onto the controls", "space"),
    ("attach", "Attach", "Select what follows, then what it holds on to: from this frame it follows, no jump", "space"),
    ("release", "Release", "The selected attached thing stays where it is from this frame (right-click: bake / "
     "remove)", "space"),
    ("arcs", "Arcs", "A motion trail per selected control (right-click: clear)", "view"),
    ("hide_ctrls", "Controls", "Hide / show the controls in the viewport", "view"),
    ("isolate", "Isolate", "Isolate the selection in the viewport (again: everything)", "view"),
    ("hider", "Body parts", "Show every body part (right-click: hide / isolate a part)", "view"),
    ("ghosts", "Ghosts", "See-through copies a few frames before / after (right-click: clear)", "view"),
    ("playblast", "Playblast", "Playblast the frame range (right-click: size)", "view"),
]

MENUS = {
    "key": [("Key everything selected", "key_all")],
    "mirror": [("Right -> left", "mirror_rl")],
    "reset": [("Reset the whole character", "reset_all")],
    "copy_keys": [("Copy the whole animation", "copy_anim")],
    "paste_keys": [("Paste keys, keep mine (merge)", "paste_merge"), ("Paste the whole animation", "paste_anim"),
                   ("Paste the whole animation from this frame", "paste_anim_here")],
    "inbetween_add": [("Scope: selected controls", "scope_1"), ("Scope: the whole character", "scope_2"),
                      ("Scope: everything animated", "scope_3")],
    "inbetween_remove": [("Scope: selected controls", "scope_1"), ("Scope: the whole character", "scope_2"),
                         ("Scope: everything animated", "scope_3")],
    "offset_minus": [("Mode: all the same", "omode_1"), ("Mode: cascade (base to tip)", "omode_2")],
    "offset_plus": [("Mode: all the same", "omode_1"), ("Mode: cascade (base to tip)", "omode_2")],
    "offset_back": [("Back to original: only the selection", "offset_back_sel"),
                    ("Keep the current timing as the original", "offset_keep")],
    "time_scale": [("x0.5 (twice as fast)", "ts_0.5"), ("x0.75", "ts_0.75"), ("x1.5", "ts_1.5"),
                   ("x2 (twice as slow)", "ts_2")],
    "arcs": [("Clear the arcs", "arcs_clear")],
    "ghosts": [("Clear the ghosts", "ghosts_clear")],
    "release": [("Bake the attached motion to keys", "attach_bake"), ("Remove the attach (no bake)", "attach_remove")],
    "mirror_cycle": [("Mirror without looping the curves", "mirror_cycle_noloop")],
    "blocking": [("Blocking (stepped)", "block_on"), ("Spline (back)", "block_off"),
                 ("Scope: the whole character", "blkscope_1"), ("Scope: selected controls", "blkscope_2")],
    "bake_keys": [("Bake every frame", "bake_1"), ("Bake every 2 frames", "bake_2"), ("Bake every 4 frames", "bake_4")],
    "reduce_keys": [("Reduce: 0.5% (closest)", "red_0.005"), ("Reduce: 1%", "red_0.01"),
                    ("Reduce: 3% (fewest keys)", "red_0.03")],
    "overlap": [("Softer (more lag)", "ovl_soft"), ("Stiffer (less lag)", "ovl_stiff"),
                ("As a cycle (loops)", "ovl_cycle")],
    "stretch": [("125% (a bit slower)", "str_125"), ("150%", "str_150"), ("200% (twice as slow)", "str_200"),
                ("75% (faster)", "str_75"), ("50% (twice as fast)", "str_50")],
    "cycle_continue": [("Repeat 1 more time", "cyc_1"), ("Repeat 3 more times", "cyc_3"),
                       ("Repeat 7 more times", "cyc_7"),
                       ("Loop the curves instead (no new keys)", "cycle_curves"),
                       ("Scope: the whole character", "cycscope_1"), ("Scope: selected controls", "cycscope_2")],
    "hider": [("Hide / show: %s" % p, "hide_%d" % i) for i, p in enumerate(
        ["Head & face", "Torso", "L arm", "R arm", "L hand", "R hand", "L leg", "R leg", "Tail & ears"])] +
             [("Only: %s" % p, "iso_%d" % i) for i, p in enumerate(
                 ["Head & face", "Torso", "L arm", "R arm", "L hand", "R hand", "L leg", "R leg", "Tail & ears"])],
    "playblast": [("Playblast at 50 %", "blast_50"), ("Playblast at 100 %", "blast_100")],
}

RENAMED = {"copy_anim": "copy_keys", "paste_anim": "paste_keys", "offset": "offset_plus"}    # before 3.1

TOOLBAR_DEFAULT = ["picker", "poses", "tween_prev", "tween_next", "nudge_left", "nudge_right", "key", "tan_auto",
                   "tan_spline", "tan_linear", "tan_flat", "tan_step", "blocking", "mirror", "flip", "reset", "twin", "ikfk",
                   "copy_keys", "paste_keys", "inbetween_remove", "inbetween_add", "offset_minus", "offset_plus",
                   "offset_back", "pull", "push", "negate", "smooth", "temp_world",
                   "temp_pivot", "bake_back", "attach", "release", "arcs", "ghosts", "hider", "hide_ctrls", "isolate",
                   "playblast", "clips", "main"]


def icon(key):
    path = os.path.join(gus_animtool.ROOT, "icons", "ga_%s.png" % key)
    return path.replace("\\", "/") if os.path.isfile(path) else "pythonFamily.png"


def command(key):
    return _I % key


def info(key):
    for k, label, tip, group in ACTIONS:
        if k == key:
            return k, label, tip, group
    raise KeyError(key)


def _ui():
    from gus_animtool import ui
    return ui


def _call(key):
    from gus_animtool import keys as K
    from gus_animtool import tempspace as TS
    from gus_animtool import tools
    from gus_animtool import tween as T
    if key == "main":
        return gus_animtool.show()
    if key == "picker":
        return A.show_picker()
    if key == "poses":
        return A.show_library()
    if key == "clips":
        from gus_animtool import animlib
        return animlib.show()
    if key in ("mirror_cycle", "mirror_cycle_noloop"):
        from gus_animtool import cycle
        n = cycle.mirror(loop=False if key == "mirror_cycle_noloop" else None)
        return "cycle mirrored on %d control(s)" % n
    if key == "cycle_continue" or key.startswith("cyc_"):
        from gus_animtool import cycle
        times = int(key[4:]) if key.startswith("cyc_") else None
        return "cycle continued on %d curve(s)" % cycle.continue_cycle(times)
    if key == "cycle_curves":
        from gus_animtool import cycle
        return "%d curve(s) loop" % cycle.continue_with_curves()
    if key.startswith("cycscope_"):
        A.set_opt("cycle_scope", int(key[9:]))
        return "continue cycle on: %s" % ("the whole character" if key == "cycscope_1" else "the selected controls")
    if key == "attach":
        from gus_animtool import attach as AT
        AT.attach()
        return None
    if key == "release":
        from gus_animtool import attach as AT
        AT.release()
        return None
    if key in ("attach_bake", "attach_remove"):
        from gus_animtool import attach as AT
        if key == "attach_bake":
            return "baked %d frame(s)" % AT.bake()
        sel = [n for n in A.selected() if AT.read(n)]
        if not sel:
            raise RuntimeError("select something attached.")
        for n in sel:
            AT.remove(n)
        return "attach removed from %d (no bake)" % len(sel)
    if key == "hider" or (key.split("_")[0] in ("hide", "iso") and key.split("_")[-1].isdigit()):
        # hide_<n> / iso_<n>: body parts (hide_ctrls is the controls toggle, further down)
        from gus_animtool import hider as H
        if key == "hider":
            H.show_all()
            return "every body part shown"
        part = H.PARTS[int(key.split("_")[1])]
        what = ["controls", "geo", "both"][max(0, min(2, int(A.opt("hider_what", 1)) - 1))]
        if key.startswith("hide_"):
            return "%s %s" % (part, "shown" if H.toggle(part, what) else "hidden")
        return ("only %s shown" % part) if H.isolate(part, what) else "every body part shown"
    if key == "ghosts":
        return "%d ghost(s)" % tools.ghosts()
    if key == "ghosts_clear":
        tools.clear_ghosts()
        return "ghosts cleared"
    if key in ("tween_prev", "tween_next"):
        return T.step(-1 if key == "tween_prev" else 1)
    if key in ("nudge_left", "nudge_right"):
        n = K.nudge((-1 if key == "nudge_left" else 1) * int(A.opt("nudge_step", 1)))
        return "nudged %d" % n
    if key == "key":
        return "keyed %d control(s)" % K.key_keep_curve()
    if key == "key_all":
        sel = tools._nodes()
        cmds.setKeyframe(sel)
        return "keyed %d control(s)" % len(sel)
    if key.startswith("tan_"):
        name = {"tan_step": "step"}.get(key, key[4:])
        return "%s tangents on %d curve(s) / control(s)" % (name, tools.tangents(name))
    if key == "mirror":
        return A.mirror_pose("L>R")
    if key == "mirror_rl":
        return A.mirror_pose("R>L")
    if key == "flip":
        return A.flip_pose()
    if key == "reset":
        return A.reset_pose("selection")
    if key == "reset_all":
        return A.reset_pose("character")
    if key == "twin":
        return A.select_twin("other")
    if key == "ikfk":
        return A.switch("toggle")
    if key == "copy_anim":
        return "copied %d curve(s)" % tools.copy_animation()
    if key in ("paste_anim", "paste_anim_here"):
        n = tools.paste_animation(at_current=key == "paste_anim_here")
        return "pasted %d curve(s)" % n
    if key == "copy_keys":
        n, k = K.copy_keys()
        return "copied %d key(s) of %d control(s)" % (k, n)
    if key in ("paste_keys", "paste_merge"):
        return "pasted %d key(s)" % K.paste_keys(merge=True if key == "paste_merge" else None)
    if key in ("inbetween_add", "inbetween_remove"):
        step = int(A.opt("inbetween_step", 1)) * (1 if key == "inbetween_add" else -1)
        n = K.inbetween(step)
        return "%s %d frame(s) after this one (%d curves)" % ("added" if step > 0 else "removed", abs(step), n)
    if key.startswith("scope_"):
        A.set_opt("inbetween_scope", int(key[6:]))
        return "inbetweens now on: %s" % K.SCOPE_LABELS[int(key[6:]) - 1].lower()
    if key in ("offset_minus", "offset_plus"):
        step = int(A.opt("offset_step", 1)) * (1 if key == "offset_plus" else -1)
        return "offset %d control(s) by %+d" % (K.offset(step), step)
    if key.startswith("omode_"):
        A.set_opt("offset_mode", int(key[6:]))
        return "offset mode: %s" % ("all the same" if key == "omode_1" else "cascade")
    if key in ("offset_back", "offset_back_sel"):
        n = K.back_to_original(tools._nodes() if key == "offset_back_sel" else None)
        return "%d curve(s) back to their original timing" % n
    if key == "offset_keep":
        K.keep_as_original()
        return "the current timing is the new original"
    if key in ("blocking", "block_on", "block_off"):
        on = tools.blocking({"block_on": True, "block_off": False}.get(key))
        return "blocking (stepped)" if on else "spline"
    if key.startswith("blkscope_"):
        A.set_opt("block_scope", int(key[9:]))
        return "blocking / spline on: %s" % ("the whole character" if key == "blkscope_1" else "the selected controls")
    if key in ("cycle_place", "cycle_forward"):
        from gus_animtool import cycle
        n = cycle.in_place() if key == "cycle_place" else cycle.forward()
        return "%d curve(s) %s" % (n, "in place" if key == "cycle_place" else "moving forward")
    if key == "bake_keys" or (key.startswith("bake_") and key[5:].isdigit()):     # not bake_back
        step = int(key[5:]) if key != "bake_keys" else None
        return "baked %d channel(s)" % K.bake(step)
    if key == "reduce_keys" or key.startswith("red_"):
        gone, before = K.reduce_keys(float(key[4:]) if key.startswith("red_") else None)
        return "%d of %d key(s) removed" % (gone, before)
    if key == "overlap" or key.startswith("ovl_"):
        from gus_animtool import motion as M
        k = M.opt("overlap_stiffness")
        flags = {"ovl_soft": {"stiffness": k * 0.6}, "ovl_stiff": {"stiffness": min(1.0, k * 1.6)},
                 "ovl_cycle": {"cycle": True}}.get(key, {})
        return "overlap on %d control(s)" % M.overlap(**flags)
    if key == "stretch" or key.startswith("str_"):
        if key == "stretch":
            first, last = tools.stretch_range()
            old = int(last - first + 1)
            if cmds.promptDialog(title="Slower / faster", message="%g-%g is %d frames. New length (frames):"
                                 % (first, last, old), text=str(int(round(old * 1.5))), button=["OK", "Cancel"],
                                 defaultButton="OK", cancelButton="Cancel", dismissString="Cancel") != "OK":
                return None
            length = int(float(cmds.promptDialog(query=True, text=True)))
            return "%d curve(s) retimed" % tools.stretch(length)
        return "%d curve(s) retimed" % tools.stretch(percent=float(key[4:]))
    if key == "reverse":
        return "reversed %d control(s)" % tools.reverse()
    if key == "time_scale" or key.startswith("ts_"):
        f = 1.25 if key == "time_scale" else float(key[3:])
        tools.time_scale(f)
        return "time x%g from the current frame" % f
    if key in ("pull", "push"):
        return "%d key(s) %sed" % (K.push_pull(key), key)
    if key == "negate":
        return "%d key(s) negated" % K.negate()
    if key == "smooth":
        return "smoothed %d key(s)" % tools.smooth()
    if key == "noise":
        return "noise on %d key(s)" % tools.noise(float(A.opt("noise_amount", 0.05)))
    if key == "redundant":
        return "deleted %d redundant key(s)" % K.delete_redundant()
    if key == "euler":
        return "filtered %d curve(s)" % K.euler()
    if key == "temp_world":
        TS.world()
        return "world space: animate the locators, then Bake back"
    if key == "temp_pivot":
        TS.pivot()
        return "temp pivot: move the locator, turn it, then Bake back"
    if key == "bake_back":
        return "baked back %d control(s)" % TS.bake_back()
    if key == "arcs":
        return "%d arc(s)" % len(tools.arcs())
    if key == "arcs_clear":
        tools.clear_arcs()
        return "arcs cleared"
    if key == "hide_ctrls":
        return "controls %s" % ("shown" if tools.toggle_controls() else "hidden")
    if key == "isolate":
        return "isolate %s" % ("on" if tools.toggle_isolate() else "off")
    if key == "playblast" or key.startswith("blast_"):
        scale = int(key[6:]) if key.startswith("blast_") else None
        return "playblast: %s" % tools.playblast(scale)
    raise RuntimeError("unknown action: %s" % key)


def run(key):
    """Run an action (one undo, problems become a warning on the window / in the script editor)."""
    A.track_selection_order()
    try:
        got = _call(key)
        if isinstance(got, str):
            A.message(got + ".")
        return got
    except (RuntimeError, ValueError) as e:                 # expected: say what to do
        A.message(str(e), "warn")
    except Exception as e:                                  # a button never throws at the animator
        import traceback
        print(traceback.format_exc())
        A.message("error: %s (details in the Script Editor)" % e, "warn")
    return None


def icon_button(key, text=False, width=None, height=30, **flags):
    """An icon button for an action, with its right-click menu (an unnamed popup: Maya names can't hold '|')."""
    _k, label, tip, _g = info(key)
    size = {"width": width} if width else {}
    b = cmds.iconTextButton(style="iconAndTextHorizontal" if text else "iconOnly", image1=icon(key), label=label,
                            annotation=label + ": " + tip, height=height, command=command(key), sourceType="python",
                            **dict(size, **flags))
    menu = menu_items(key)
    if menu:
        pm = cmds.popupMenu(parent=b, button=3)
        for mlabel, mcmd in menu:
            cmds.menuItem(label=mlabel, command=mcmd, sourceType="python", parent=pm)
    return b


def menu_items(key):
    """[(label, command string)] for a right-click menu."""
    return [(label, command(sub)) for label, sub in MENUS.get(key, [])]
