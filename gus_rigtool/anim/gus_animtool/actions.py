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
    ("bar", "Bar", "The Animtool bar: every tool in a small strip that floats over Maya, anywhere you like "
     "(it opens with the Animtool window)", "open"),
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
    ("attach", "Attach", "Select what follows, then what it holds on to: from this frame it follows, no jump "
     "(right-click: hand-over, both hands, where it holds, the Attach window)", "space"),
    ("release", "Release", "The selected attached thing stays where it is from this frame (right-click: bake / "
     "remove)", "space"),
    ("arcs", "Arcs", "An arc on each selected control: drag a key dot to change it (right-click: the Arcs panel, "
     "clear, range, handles, timing beads)", "view"),
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
    "arcs": [("Arcs panel (every arc, its colour, range, look)", "arcs_panel"), ("Clear the arcs", "arcs_clear"), ("Range: the whole shot", "arcs_shot"),
             ("Range: around my frame (24 before / after)", "arcs_around"),
             ("Show handles on the selected key (on / off)", "arcs_handles"),
             ("Timing beads: make the selection's curves weighted (asks first)", "arcs_weighted"),
             ("Break the handles (move one at a time)", "arcs_break"), ("Join the handles again", "arcs_join")],
    "ghosts": [("Clear the ghosts", "ghosts_clear")],
    "attach": [("Hand-over to the second one (4 frames)", "attach_handover"),
               ("Both hands: held by both (50 / 50)", "attach_both"),
               ("Show where it holds", "attach_show"), ("Go to the previous change", "attach_prev"),
               ("Go to the next change", "attach_next"), ("Open the Attach window", "attach_window"),
               ("Repair attaches in this scene (stutter, divide-by-zero warnings)", "attach_repair")],
    "release": [("Bake the attached motion to keys", "attach_bake"),
                ("Bake ALL attaches in this shot (finish the shot)", "attach_bake_all"),
                ("Remove the attach (no bake)", "attach_remove"),
                ("Show where it holds", "attach_show"), ("Open the Attach window", "attach_window")],
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
                   "playblast", "clips", "main", "bar"]


# ---------------------------------------------------------------------------- 5.8.0: the one list, completed
# Everything the shelf, the bar, the toolbar, the window - and later the pie, the dock and search - need to know
# about a tool, here: its category and colour, the two windows that only the bar shows, the options its right-click
# strip shows, and the profiles. (Gus: the categories and colours of the 5.8 preview - the icons' own colours.)

# (key, name, colour, colour-blind safe colour - Okabe-Ito)
CATEGORIES = [("pick", "Pick & see", "#e15c8f", "#cc79a7"), ("pose", "Pose", "#5cc270", "#009e73"),
              ("tween", "Tween", "#9e70eb", "#9a8cd9"), ("keys", "Keys & tangents", "#f0ae33", "#e69f00"),
              ("timing", "Timing & cycles", "#33bdb3", "#56b4e9"), ("curves", "Graph curves", "#f57b3d", "#d55e00"),
              ("space", "Spaces & props", "#48c2eb", "#0072b2"), ("open", "Windows", "#4c93e7", "#bbbbbb")]
GROUP_CATEGORY = {"open": "open", "tween": "tween", "keys": "keys", "tangents": "keys", "pose": "pose",
                  "anim": "timing", "curves": "curves", "space": "space", "view": "pick"}

# the windows the bar shows right after their tool (not on the shelf / toolbar): (key, label, tooltip, group, after)
EXTRAS = [("attach_window", "Attach window", "The Attach window: what's attached, who holds it over time, its changes",
           "space", "release"),
          ("arcs_panel", "Arcs panel", "The Arcs panel: every arc, its colour, range, look", "view", "arcs")]

_STEPS = [1, 2, 3, 5, 10]
_SCOPE3 = ["Selected controls", "The whole character", "Everything animated"]
_SCOPE_CHAR = ["The whole character", "Selected controls"]
# a tool's options for its right-click strip: (option, label, kind, choices) - kind: "bool", "choice" (saved as 1, 2,
# 3...), "value" (saved as the value itself). The same options its section in the window sets.
OPTIONS = {
    "tween_prev": [("tween_mode", "Mode", "choice", ["Between keys", "From rest", "Mirror"]),
                   ("tween_key", "Key it", "bool", None)],
    "nudge_left": [("nudge_step", "Step (frames)", "value", _STEPS)],
    "inbetween_add": [("inbetween_step", "Step (frames)", "value", _STEPS),
                      ("inbetween_scope", "Scope", "choice", _SCOPE3)],
    "offset_minus": [("offset_step", "Step (frames)", "value", _STEPS),
                     ("offset_mode", "Mode", "choice", ["All the same", "Cascade (base to tip)"])],
    "blocking": [("block_scope", "Scope", "choice", _SCOPE_CHAR)],
    "paste_keys": [("paste_merge", "Keep mine (merge)", "bool", None)],
    "cycle_continue": [("cycle_times", "Repeat", "value", [1, 3, 7]), ("cycle_scope", "Scope", "choice", _SCOPE_CHAR)],
    "bake_keys": [("bake_step", "Every (frames)", "value", [1, 2, 4])],
    "reduce_keys": [("reduce_tolerance", "How close", "value", [0.005, 0.01, 0.03])],
    "overlap": [("overlap_cycle", "As a cycle (loops)", "bool", None)],
    "pull": [("pushpull_factor", "Amount", "value", [0.95, 0.9, 0.8, 0.75, 0.5]),
             ("pushpull_pivot", "Around", "choice", ["Key on the left", "Key on the right", "Last selected key"])],
    "noise": [("noise_amount", "Amount", "value", [0.02, 0.05, 0.1, 0.2])],
    "ghosts": [("ghost_before", "Before", "value", [1, 2, 3, 4, 5]), ("ghost_after", "After", "value", [1, 2, 3, 4, 5]),
               ("ghost_step", "Every (frames)", "value", _STEPS)],
    "playblast": [("playblast_scale", "Size (%)", "value", [50, 75, 100])],
    "ikfk": [("key_switch", "Key the switch", "bool", None)],
}
for _a, _b in (("tween_next", "tween_prev"), ("nudge_right", "nudge_left"), ("inbetween_remove", "inbetween_add"),
               ("offset_plus", "offset_minus"), ("push", "pull")):
    OPTIONS[_a] = OPTIONS[_b]

# the profiles of the 5.8 preview (Gus: "name them differently and suggest new ones"): (name, short, tools)
PROFILES = [
    ("Blocking", "BLK", ["key", "blocking", "tan_step", "tween_prev", "tween_next", "mirror", "flip", "reset",
                         "copy_keys", "paste_keys", "inbetween_add", "inbetween_remove", "ikfk"]),
    ("Splining", "SPL", ["blocking", "tan_auto", "tan_spline", "tan_flat", "tan_linear", "nudge_left", "nudge_right",
                         "offset_minus", "offset_plus", "offset_back", "euler", "redundant"]),
    ("Polish", "POL", ["overlap", "push", "pull", "negate", "smooth", "noise", "arcs", "arcs_panel", "ghosts",
                       "tween_prev", "tween_next"]),
    ("Spaces & props", "SPC", ["attach", "release", "attach_window", "temp_world", "temp_pivot", "bake_back", "ikfk",
                               "twin", "key"]),
    ("Cycles", "CYC", ["mirror_cycle", "cycle_continue", "cycle_place", "cycle_forward", "offset_minus",
                       "offset_plus", "stretch", "time_scale", "reverse"]),
    ("Review", "REV", ["picker", "poses", "arcs", "ghosts", "hide_ctrls", "hider", "isolate", "playblast"]),
    ("Clean-up", "CLN", ["bake_keys", "reduce_keys", "smooth", "euler", "redundant", "copy_keys", "paste_keys"]),
]


def every(where="bar"):
    """Every tool, in order. 'shelf' / 'toolbar': the actions; 'bar': without the bar's own button, each window
    right after its tool (the All tools profile)."""
    out = []
    after = dict((e[4], e[0]) for e in EXTRAS)
    for k, _l, _t, _g in ACTIONS:
        if where == "bar" and k == "bar":
            continue
        out.append(k)
        if where == "bar" and k in after:
            out.append(after[k])
    return out


def describe(key):
    """(key, label, tooltip, group) of an action or of a window the bar shows."""
    for e in EXTRAS:
        if e[0] == key:
            return e[:4]
    return info(key)


def category(key):
    return GROUP_CATEGORY[describe(key)[3]]


def colour(key, colour_blind=False):
    cat = category(key)
    for k, _n, c, cb in CATEGORIES:
        if k == cat:
            return cb if colour_blind else c
    return "#888888"


# each option's default: the same as the tool's own (a test checks they agree)
OPTION_DEFAULTS = {"tween_mode": 1, "tween_key": 1, "nudge_step": 1, "inbetween_step": 1, "inbetween_scope": 1,
                   "offset_step": 1, "offset_mode": 1, "block_scope": 1, "paste_merge": 0, "cycle_times": 3,
                   "cycle_scope": 1, "bake_step": 1, "reduce_tolerance": 0.01, "overlap_cycle": 0,
                   "pushpull_factor": 0.9, "pushpull_pivot": 1, "noise_amount": 0.05, "ghost_before": 2,
                   "ghost_after": 2, "ghost_step": 2, "playblast_scale": 100, "key_switch": 1}


def options(key):
    """[(option, label, kind, choices, current value)] - the tool's right-click strip."""
    return [(name, label, kind, choices, A.opt(name, OPTION_DEFAULTS[name]))
            for name, label, kind, choices in OPTIONS.get(key, [])]


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
    if key == "bar":
        try:
            from gus_animtool import bar
        except ImportError as e:
            raise RuntimeError("the Animtool bar couldn't open (Qt: %s)." % e)
        bar.show()
        return None
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
    if key == "attach_handover":
        from gus_animtool import attach as AT
        AT.hand_over()
        return None
    if key == "attach_both":
        from gus_animtool import attach as AT
        AT.both()
        return None
    if key == "attach_show":
        from gus_animtool import attach as AT
        nodes = [n for n in A.selected() if AT.read(n)] or AT.attached()
        if not nodes:
            raise RuntimeError("nothing is attached in this scene.")
        text = "\n".join(AT.describe(n) for n in nodes)
        print("Gus Animtool - where it holds:\n" + text)
        return "where it holds (also in the Script Editor): " + " | ".join(
            "%s: %s" % (A.short(n), ", ".join("%g %s" % e for e in AT.events(n)) or "-") for n in nodes)
    if key in ("attach_prev", "attach_next"):
        from gus_animtool import attach as AT
        return "frame %g" % AT.go_change(backwards=key == "attach_prev")
    if key == "attach_window":
        try:
            from gus_animtool import attachwin
        except ImportError as e:
            raise RuntimeError("the Attach window couldn't open (Qt: %s)." % e)
        attachwin.show()
        return None
    if key == "attach_repair":
        from gus_animtool import attach as AT
        return "repaired %d attach part(s): no more stutter or divide-by-zero warnings" % AT.repair()
    if key == "release":
        from gus_animtool import attach as AT
        AT.release()
        return None
    if key == "attach_bake_all":
        from gus_animtool import attach as AT
        n = len([x for x in AT.attached() if AT.read(x)])
        if not n:
            raise RuntimeError("nothing is attached in this scene.")
        lo, hi = A.frame_range()
        if cmds.confirmDialog(title="Gus Animtool", message="Bake all %d attach(es) to plain keys, frames %g-%g?\n\n"
                              "The motion stays; the attach setups go. Ctrl+Z undoes it." % (n, lo, hi),
                              button=["Bake all", "Cancel"], defaultButton="Bake all", cancelButton="Cancel",
                              dismissString="Cancel") != "Bake all":
            return None
        done = AT.bake_all(lo, hi)
        return "baked %d attach(es) to keys, frames %g-%g" % (len(done), lo, hi)
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
        return "%s %d frame(s) after this one (%d curve(s) moved)" % ("added" if step > 0 else "removed", abs(step), n)
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
        from gus_animtool import arctrail
        return arctrail.show(tools._nodes())
    if key == "arcs_panel":
        try:
            from gus_animtool import arcswin
        except ImportError as e:
            raise RuntimeError("the Arcs panel couldn't open (Qt: %s)." % e)
        arcswin.show()
        return None
    if key in ("arcs_shot", "arcs_around"):
        from gus_animtool import arctrail
        arctrail.set_option("arcs_around", key == "arcs_around")
        return "arcs: %s" % ("24 frames around your frame" if key == "arcs_around" else "the whole shot")
    if key == "arcs_handles":
        from gus_animtool import arctrail
        on = arctrail.set_option("arcs_handles", not bool(A.opt("arcs_handles", False)))
        return "arcs: handles on the selected key %s" % ("on" if on else "off")
    if key in ("arcs_break", "arcs_join"):
        from gus_animtool import arctrail
        n = arctrail.break_handles(tools._nodes() if A.selected() else [], join=key == "arcs_join")
        return "%d key(s): handles %s" % (n, "joined again" if key == "arcs_join" else "broken (each moves on its "
                                                                                     "own)")
    if key == "arcs_weighted":
        from gus_animtool import arctrail
        n = arctrail.make_weighted(tools._nodes())
        return ("%d curve(s) now weighted: the timing beads show on their arcs" % n) if n else "nothing changed"
    if key == "arcs_clear":
        from gus_animtool import arctrail
        arctrail.clear()
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
    A.LAST_ACTION["key"] = key
    try:
        got = _call(key)
        if isinstance(got, str):
            A.message(got + ".")
        return got
    except (RuntimeError, ValueError) as e:                 # expected: say what to do
        A.message(str(e), "warn")
    except Exception as e:                                  # a button never throws at the animator
        import traceback
        details = traceback.format_exc()
        print(details)
        A.message("error: %s (details in the Script Editor)" % e, "warn")
        A.note_problem("error: %s" % e, details)
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
