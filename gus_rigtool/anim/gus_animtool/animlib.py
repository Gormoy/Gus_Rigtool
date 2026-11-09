"""
Animation library: clips (a walk cycle, a blink, a lip-sync bit) saved from the selected controls' keys over the
frame range - with a picture - and applied at the current frame on any copy of the character: replace the keys
in its span, merge with them, or insert (the later keys move after it); mirrored (left <-> right) if you like.

Clips live next to the poses: <pose library>/<character>/clips/<name>.json (+ .png).
"""

import json
import os

import maya.cmds as cmds

from gus_animtool import anim as A

VERSION = 1
MODES = ["replace", "merge", "insert"]


def folder(ns=None):
    path = os.path.join(A.character_folder(ns), "clips")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def names(ns=None):
    return sorted(f[:-5] for f in os.listdir(folder(ns)) if f.endswith(".json"))


_bare = A.bare


def _attr_of(curve):
    plug = (cmds.listConnections(curve + ".output", plugs=True, source=False, destination=True) or [None])[0]
    return plug.split(".", 1)[1] if plug else None


def capture(nodes, start, end):
    """{control: {attr: [[frame - start, value, in tangent, out tangent]]}} of the keys in start-end."""
    out = {}
    for n in nodes:
        attrs = {}
        for c in A.time_curves(n):
            attr = _attr_of(c)
            if not attr:
                continue
            times = cmds.keyframe(c, query=True, time=(start, end), timeChange=True) or []
            if not times:
                continue
            vals = cmds.keyframe(c, query=True, time=(start, end), valueChange=True) or []
            itt = cmds.keyTangent(c, query=True, time=(start, end), inTangentType=True) or ["auto"] * len(times)
            ott = cmds.keyTangent(c, query=True, time=(start, end), outTangentType=True) or ["auto"] * len(times)
            attrs[attr] = [[round(t - start, 4), v, i, o] for t, v, i, o in zip(times, vals, itt, ott)]
        if attrs:
            out[_bare(n)] = attrs
    return out


def save(name, nodes=None, start=None, end=None, ns=None, thumbnail=True):
    """Save the clip. Returns (name, controls, frames)."""
    name = "".join(c if c.isalnum() or c in "_-" else "_" for c in (name or "").strip()) or "clip"
    nodes = nodes or A.selected() or A.character_controls(ns)
    if start is None:
        start, end = A.frame_range()
    data = {"version": VERSION, "length": end - start, "controls": capture(nodes, start, end)}
    if not data["controls"]:
        raise RuntimeError("no keys on the selection in frames %g-%g." % (start, end))
    path = folder(ns)
    with open(os.path.join(path, name + ".json"), "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    if thumbnail:
        try:
            mid = int(round((start + end) / 2.0))
            cmds.playblast(frame=[mid], format="image", compression="png", viewer=False, showOrnaments=False,
                           completeFilename=os.path.join(path, name + ".png"), widthHeight=(160, 120), percent=100,
                           forceOverwrite=True, clearCache=True)
        except Exception:
            pass
    return name, len(data["controls"]), data["length"]


def load(name, ns=None):
    with open(os.path.join(folder(ns), name + ".json")) as f:
        return json.load(f)


def picture(name, ns=None):
    p = os.path.join(folder(ns), name + ".png")
    return p if os.path.isfile(p) else None


def delete(name, ns=None):
    for ext in (".json", ".png"):
        p = os.path.join(folder(ns), name + ext)
        if os.path.exists(p):
            os.remove(p)


def apply(name, mode="replace", mirrored=False, only=None, ns=None, at=None):
    """The clip from frame at (now) on. only: just these controls (the selection). Returns how many controls."""
    data = load(name, ns)
    ns = (A.current_character() if ns is None else ns) or ""
    t0 = cmds.currentTime(query=True) if at is None else at
    length = float(data.get("length", 0))
    only = set(_bare(n) for n in only) if only else None
    targets = []
    for bare, attrs in data["controls"].items():
        if only is not None and bare not in only:
            continue
        node = A.resolve(bare, ns)
        if node:
            targets.append((node, attrs))
    if not targets:
        raise RuntimeError("none of the clip's controls are in this character.")
    with A.Undo("gusAnimtoolApplyClip"):
        nodes = [n for n, _a in targets]
        if mode == "insert":
            curves = A.time_curves(nodes)
            if curves:
                cmds.keyframe(curves, edit=True, relative=True, timeChange=length + 1, time=(t0, 1e6))
        for node, attrs in targets:
            for attr, keys in attrs.items():
                plug = node + "." + attr
                if not cmds.objExists(plug) or not A._settable(plug):
                    continue
                if mode == "replace":
                    try:
                        cmds.cutKey(node, attribute=attr, time=(t0, t0 + length), clear=True)
                    except RuntimeError:
                        pass
                for dt, v, itt, ott in keys:
                    t = t0 + dt
                    cmds.setKeyframe(node, attribute=attr, time=t, value=v)
                    try:
                        cmds.keyTangent(node, attribute=attr, time=(t, t), inTangentType=itt, outTangentType=ott)
                    except RuntimeError:
                        pass
        if mirrored:
            A.flip_range(nodes, t0, t0 + length)
    A.message("clip '%s' on %d control(s), frames %g-%g (%s%s)." % (name, len(targets), t0, t0 + length, mode,
                                                                    ", mirrored" if mirrored else ""))
    return len(targets)


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

WIN = "gusAnimtoolClipsWin"
CP = "gusAnimtoolClips_"


def _picked():
    got = cmds.textScrollList(CP + "List", query=True, selectItem=True) or []
    if not got:
        raise RuntimeError("pick a clip in the list.")
    return got[0]


def _fill(*_):
    cmds.textScrollList(CP + "List", edit=True, removeAll=True)
    for n in names():
        cmds.textScrollList(CP + "List", edit=True, append=n)
    _show_picture()


def _show_picture(*_):
    sel = cmds.textScrollList(CP + "List", query=True, selectItem=True) or []
    pic = picture(sel[0]) if sel else None
    cmds.image(CP + "Pic", edit=True, image=pic or "", visible=bool(pic))


def _save(*_):
    name = cmds.textField(CP + "Name", query=True, text=True) or ""
    if not name.strip():
        raise RuntimeError("type a name for the clip.")
    n, c, length = save(name)
    _fill()
    A.message("clip '%s' saved: %d control(s), %g frames." % (n, c, length))


def _apply(*_):
    mode = MODES[cmds.optionMenu(CP + "Mode", query=True, select=True) - 1]
    only = A.selected() if cmds.checkBox(CP + "Only", query=True, value=True) else None
    apply(_picked(), mode, cmds.checkBox(CP + "Mirror", query=True, value=True), only)


def _delete(*_):
    name = _picked()
    if cmds.confirmDialog(title="Delete clip", message="Delete the clip '%s'?" % name, button=["Delete", "Cancel"],
                          defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") == "Delete":
        delete(name)
        _fill()


def show(*_):
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    cmds.window(WIN, title="Gus Animtool - Animation library", widthHeight=(380, 520))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4, columnAttach=("both", 6))
    cmds.text(label="Clips of %s" % (A.current_character() or "this character"), align="left", font="boldLabelFont")
    cmds.textScrollList(CP + "List", height=170, allowMultiSelection=False, selectCommand=A.guard(_show_picture),
                        doubleClickCommand=A.guard(_apply))
    cmds.image(CP + "Pic", width=160, height=120, visible=False)
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(50, 300),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="Apply")
    cmds.optionMenu(CP + "Mode", annotation="Replace: the keys in the clip's span go. Merge: kept. Insert: the later "
                                            "keys move after the clip.")
    for m in ("Replace the keys there", "Merge with them", "Insert (push the later keys)"):
        cmds.menuItem(label=m)
    cmds.setParent("..")
    cmds.checkBox(CP + "Mirror", label="Mirrored (left <-> right)", value=False)
    cmds.checkBox(CP + "Only", label="Only on the selected controls", value=False)
    A._buttons([("Apply here", _apply, "The clip from the current frame on (double-click works too)."),
                ("Delete...", _delete, "Delete the picked clip.")])
    cmds.separator(height=10)
    cmds.text(label="Save the selection's keys over the window's frame range (nothing selected: every control):",
              align="left", wordWrap=True)
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.textField(CP + "Name", placeholderText="clip name (walk, blink...)")
    cmds.button(label="Save clip", width=90, backgroundColor=A.MAIN_BG, command=A.guard(_save))
    cmds.setParent("..")
    cmds.showWindow(WIN)
    _fill()
    return WIN
