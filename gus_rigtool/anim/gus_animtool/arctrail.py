"""
Arcs (5.6.42): back to the plain arc of before 5.6.40 - Maya's editable motion trail on each selected control over
the shot, one orange line, small dots for the spacing, bigger dots on the keys; it stays until you clear it.
Gus found 5.6.40's colours / window / follow selection "too much": an arc is a check you read at a glance.

Kept from 5.6.40 / 5.6.41 because they're quiet and safe:
  - any control gets an arc, keyed or not; a control that only rotates (FK) shows it, and the message says a drag
    would add translate keys;
  - no arc nodes in your files (taken out before a save, put back after); another scene: forgotten;
  - your selection is put back after making an arc, and an arc is never taken for a control.
Right-click: Clear, Range (the shot / around my frame), Show handles (on the selected key; off by default),
Timing beads (make weighted - asks first).

Untested in real Maya: the trail's settings are found by name; a setting Maya doesn't have is skipped.
"""
import json

import maya.cmds as cmds

from gus_animtool import anim as A

GROUP = "gusAnimtool_arcs_grp"
COLOUR = (1.0, 0.55, 0.15)        # the arc's orange (as before 5.6.40)
LEFT = (0.29, 0.64, 1.0)          # a left control's arc starts blue (like the onion skin's past)
AROUND = 24                       # Range: around my frame (frames before / after), the default
# the Arcs panel's settings (kept for next time): name -> default
OPTS = {"arcs_around": False, "arcs_frames": AROUND, "arcs_handles": False, "arcs_thick": 2.0, "arcs_dot": 6.0,
        "arcs_key": 9.0, "arcs_dots": True, "arcs_numbers": False, "arcs_step": 1}
FREE_SOURCES = ("animCurve", "pairBlend", "animBlendNodeBase")    # keys, also through a blend or anim layers

_state = {"nodes": [], "hidden": [], "callbacks": [], "jobs": [], "saved": None, "busy": False}


def opt(key):
    return type(OPTS[key])(A.opt(key, OPTS[key]))


# --------------------------------------------------------------------------- each arc's colour
def _colours():
    try:
        return json.loads(A.opt("arcs_colours", "{}") or "{}")
    except (TypeError, ValueError):
        return {}


def colour_of(node):
    """This control's arc colour: the one you picked (kept by its name), else left blue, the others orange."""
    short = _short(node)
    got = _colours().get(short)
    if got:
        return tuple(got[:3])
    low = short.lower()
    if low.startswith("l_") or "_l_" in low or low.startswith("left"):
        return LEFT
    return COLOUR


def set_colour(node, rgb):
    c = _colours()
    c[_short(node)] = [round(float(x), 4) for x in rgb[:3]]
    A.set_opt("arcs_colours", json.dumps(c))
    for t in _trails_of(node):
        style(t, colour=tuple(rgb[:3]))
    return tuple(rgb[:3])


# --------------------------------------------------------------------------- what kind of control
def moves(node):
    """True when dragging the arc makes sense: a translate channel that's free (keyable, not locked, not driven by
    a constraint) - keyed or not."""
    for ax in "XYZ":
        plug = "%s.translate%s" % (node, ax)
        try:
            if cmds.getAttr(plug, lock=True) or not cmds.getAttr(plug, keyable=True):
                continue
        except (RuntimeError, ValueError):
            continue
        src = cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True) or []
        if not src or any(cmds.objectType(s, isAType=t) for s in src for t in FREE_SOURCES):
            return True
    return False


def has_translate_keys(node):
    for ax in "XYZ":
        if cmds.listConnections("%s.translate%s" % (node, ax), source=True, destination=False, type="animCurve"):
            return True
    return False


def _is_trail(node):
    try:
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        return any(cmds.nodeType(s).startswith("motionTrail") for s in shapes)
    except (RuntimeError, ValueError):
        return False


def controls(nodes):
    """The controls among these - not an arc itself (selecting a key dot on an arc to drag it), not components."""
    out = []
    for n in nodes or []:
        if "." in n or GROUP in n or not cmds.objExists(n) or _is_trail(n):
            continue
        try:
            if cmds.objectType(n, isAType="transform") and n not in out:
                out.append(n)
        except (RuntimeError, ValueError):
            pass
    return out


# --------------------------------------------------------------------------- the arc
def _short(n):
    return n.split("|")[-1].split(":")[-1]


def _group():
    got = cmds.ls(GROUP, long=True)
    if got:
        return got[0]
    with A.NoUndo():
        return cmds.ls(cmds.createNode("transform", name=GROUP), long=True)[0]


def trails():
    grp = cmds.ls(GROUP, long=True)
    if not grp:
        return []
    return cmds.listRelatives(grp[0], children=True, fullPath=True) or []


def _trails_of(node):
    short = _short(node) + "_arc"
    return [t for t in trails() if t.split("|")[-1].startswith(short)]


def make(nodes):
    """An arc on each of these controls over the shot (not twice). Returns the trail nodes made. Your selection is
    put back after (Maya selects a new trail)."""
    s, e = A.frame_range()
    sel = cmds.ls(selection=True, long=True) or []
    was = _state["busy"]
    _state["busy"] = True
    made = []
    try:
        grp = _group()
        for n in nodes:
            if _trails_of(n):
                continue
            got = cmds.snapshot(n, motionTrail=True, increment=max(1, opt("arcs_step")), startTime=s, endTime=e,
                                name=_short(n) + "_arc") or []
            for g in got:
                if cmds.nodeType(g) == "transform":
                    try:
                        g = cmds.parent(g, grp)[0]
                    except RuntimeError:
                        pass
                made.append(g)
                style(g, colour=colour_of(n))
            ln = (cmds.ls(n, long=True) or [n])[0]
            if ln not in _state["nodes"]:
                _state["nodes"].append(ln)
    finally:
        try:
            if sel:
                cmds.select(sel, replace=True)
            else:
                cmds.select(clear=True)
        except (RuntimeError, ValueError):
            pass
        _state["busy"] = was
    if made:
        _watch()
    return made


def show(nodes):
    """The Arcs button: an arc on each selected control. Returns a message."""
    nodes = controls(nodes)
    if not nodes:
        raise RuntimeError("select the controls first.")
    with A.NoUndo():                                       # showing arcs isn't an undo step
        make(nodes)
    return describe(nodes)


def describe(nodes):
    keyed = [n for n in nodes if moves(n) and has_translate_keys(n)]
    bare = [n for n in nodes if moves(n) and not has_translate_keys(n)]
    turn = [n for n in nodes if not moves(n)]
    parts = []
    if keyed:
        parts.append("%d arc(s): drag a key dot to change it" % len(keyed))
    if bare:
        parts.append("%s: no translate keys yet (set a key to edit the arc)" % ", ".join(_short(n) for n in bare[:3]))
    if turn:
        parts.append("%s only rotate%s: the arc shows the motion; don't drag it" % (
            ", ".join(_short(n) for n in turn[:3]), "s" if len(turn) == 1 else ""))
    return "; ".join(parts) or "no arcs"


# --------------------------------------------------------------------------- the look
def _attrs(node):
    try:
        return set(cmds.listAttr(node) or [])
    except (RuntimeError, ValueError):
        return set()


def _set(node, attr, *value, **kw):
    try:
        cmds.setAttr("%s.%s" % (node, attr), *value, **kw)
        return True
    except (RuntimeError, ValueError, TypeError):
        return False


def _default(node, attr):
    try:
        return (cmds.attributeQuery(attr, node=node, listDefault=True) or [0])[0]
    except (RuntimeError, ValueError, TypeError):
        return 0


def style(node, around=None, handles=None, colour=None):
    """The plain look (the Arcs panel's settings): the line, dots on the frames, bigger dots on keys, frame numbers
    or not, its colour. Range: the shot (Maya's own default) or some frames before / after your frame. Handles: on
    the selected key, or off. Returns what was set."""
    around = opt("arcs_around") if around is None else around
    handles = opt("arcs_handles") if handles is None else handles
    colour = colour or COLOUR
    done = []
    for sh in cmds.listRelatives(node, shapes=True, fullPath=True) or [node]:
        have = _attrs(sh)

        def put(attr, *value, **kw):
            if attr in have and _set(sh, attr, *value, **kw):
                done.append(attr)
        put("showFrameMarkers", opt("arcs_dots"))
        put("frameMarkerSize", opt("arcs_dot"))
        put("keyframeSize", opt("arcs_key"))
        put("trailThickness", opt("arcs_thick"))
        put("showFrames", opt("arcs_numbers"))
        put("trailColor", *colour, type="double3")
        for a in ("preFrame", "postFrame"):
            if a in have:
                put(a, opt("arcs_frames") if around else _default(sh, a))
        if "fadeInoutFrames" in have:
            put("fadeInoutFrames", _default(sh, "fadeInoutFrames"))
        for a in have:
            low = a.lower()
            if low.startswith("show") and "tangent" in low:
                put(a, handles)
    return done


def control_of(trail):
    short = trail.split("|")[-1]
    for n in _state["nodes"]:
        if short.startswith(_short(n) + "_arc"):
            return n
    return None


def restyle():
    for t in trails():
        n = control_of(t)
        style(t, colour=colour_of(n) if n else None)


def set_option(key, value):
    """An Arcs panel setting - kept for next time, the arcs changed straight away (a new 'point every' remakes
    them: Maya samples the arc when it's made)."""
    A.set_opt(key, value)
    if key == "arcs_step":
        nodes = [n for n in _state["nodes"] if cmds.objExists(n)]
        hidden = list(_state["hidden"])
        clear()
        with A.NoUndo():
            make(nodes)
        for n in hidden:
            set_visible(n, False)
    else:
        restyle()
    return value


# --------------------------------------------------------------------------- one arc at a time (the panel)
def arcs():
    """[(control, its trails)] - the arcs in the scene, in the order they were made."""
    return [(n, _trails_of(n)) for n in _state["nodes"] if cmds.objExists(n) and _trails_of(n)]


def set_visible(node, visible):
    for t in _trails_of(node):
        try:
            cmds.setAttr(t + ".visibility", bool(visible))
        except RuntimeError:
            pass
    if visible and node in _state["hidden"]:
        _state["hidden"].remove(node)
    elif not visible and node not in _state["hidden"]:
        _state["hidden"].append(node)
    return bool(visible)


def remove(node):
    with A.NoUndo():
        for t in _trails_of(node):
            if cmds.objExists(t):
                cmds.delete(t)
    for lst in (_state["nodes"], _state["hidden"]):
        if node in lst:
            lst.remove(node)
    return True


def key_count(node):
    curves = []
    for ax in "XYZ":
        curves += cmds.listConnections("%s.translate%s" % (node, ax), source=True, destination=False,
                                       type="animCurve") or []
    return len(set(cmds.keyframe(curves, query=True, timeChange=True) or [])) if curves else 0


def note_of(node):
    if not moves(node):
        return "only rotates"
    n = key_count(node)
    return "keys on %d frame%s" % (n, "" if n == 1 else "s") if n else "no translate keys yet"


def clear():
    """Every arc away."""
    grp = cmds.ls(GROUP, long=True)
    if grp:
        with A.NoUndo():
            cmds.delete(grp)
    _state["nodes"], _state["hidden"] = [], []
    _unwatch()
    return True


# --------------------------------------------------------------------------- timing beads
def make_weighted(nodes, ask=True):
    """Timing beads need weighted tangents: this changes the controls' translate curves to weighted (the shape
    stays) - only after you say yes. Returns how many curves changed."""
    nodes = controls(nodes)
    curves = []
    for n in nodes:
        for ax in "XYZ":
            curves += cmds.listConnections("%s.translate%s" % (n, ax), source=True, destination=False,
                                           type="animCurve") or []
    curves = [c for c in curves if not cmds.keyTangent(c, query=True, weightedTangents=True)[0]]
    if not curves:
        raise RuntimeError("these controls' curves are already weighted (or have no keys) - the timing beads "
                           "show on their arcs.")
    if ask:
        got = cmds.confirmDialog(
            title="Timing beads", button=["Make weighted", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
            message="Timing beads need weighted tangents.\n\nThis changes %d curve(s) of %s to weighted tangents. "
                    "The curves keep their shape, but from now on the length of each handle counts (the Graph "
                    "Editor and the key tools treat them as weighted).\n\nCtrl+Z undoes it." % (
                        len(curves), ", ".join(_short(n) for n in nodes[:3])))
        if got != "Make weighted":
            return 0
    with A.Undo("gusAnimtoolWeighted"):
        cmds.keyTangent(curves, edit=True, weightedTangents=True)
    restyle()
    return len(curves)


# --------------------------------------------------------------------------- saving / scenes
def _watch():
    """The save callbacks and the scene jobs - while there are arcs."""
    if not any(_job_alive(j) for j in _state["jobs"]):
        _state["jobs"] = [cmds.scriptJob(event=["SceneOpened", _scene_gone]),
                          cmds.scriptJob(event=["NewSceneOpened", _scene_gone])]
    if not _state["callbacks"]:
        try:
            import maya.api.OpenMaya as om
            msg = om.MSceneMessage
            _state["callbacks"] = [msg.addCallback(msg.kBeforeSave, _before_save),
                                   msg.addCallback(msg.kAfterSave, _after_save)]
        except Exception:
            _state["callbacks"] = []


def _job_alive(j):
    try:
        return cmds.scriptJob(exists=j)
    except Exception:
        return False


def _unwatch():
    for j in _state["jobs"]:
        try:
            if cmds.scriptJob(exists=j):
                cmds.scriptJob(kill=j, force=True)
        except Exception:
            pass
    _state["jobs"] = []
    try:
        import maya.api.OpenMaya as om
        for cb in _state["callbacks"]:
            om.MMessage.removeCallback(cb)
    except Exception:
        pass
    _state["callbacks"] = []


def _before_save(*_):
    """No arc nodes in your file: the arcs are taken out (and put back after the save)."""
    _state["saved"] = [n for n in _state["nodes"] if cmds.objExists(n)]
    grp = cmds.ls(GROUP, long=True)
    if grp:
        with A.NoUndo():
            cmds.delete(grp)


def _after_save(*_):
    nodes = _state.get("saved") or []
    _state["saved"] = None
    if nodes:
        cmds.evalDeferred(lambda: _remake(nodes), lowestPriority=True)


def _remake(nodes):
    with A.NoUndo():
        make(nodes)
        for n in list(_state["hidden"]):
            set_visible(n, False)                 # a hidden arc stays hidden after a save


def _scene_gone(*_):
    _state["nodes"], _state["hidden"] = [], []
    _unwatch()


def state():
    return dict(_state)
