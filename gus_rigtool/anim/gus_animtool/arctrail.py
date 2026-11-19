"""
Arcs (5.6.40): Maya's editable motion trail, dressed like the onion skin's arcs - only some frames before / after
your frame (fading at the ends), the past in blue and the future in orange, a dot on every frame, bigger dots on
keys, a thin line - and still editable: drag a key dot, its bezier handles show on the key you select.

  follow selection (the Arcs button): the arcs show on what you select and move to what you select next
  pin                                : the selection's arcs stay when you select something else
  rotation-only controls (FK)        : shown by the onion skin's arcs (if it's installed) - they can't be dragged
  timing beads                       : need weighted tangents - "Make weighted" asks before changing your curves
  saving                             : the trails are taken out before a save and put back after (no arc nodes in
                                       your files); another scene opened: they're gone

Untested in real Maya: the trail's settings are found by name (Maya's names change between versions); a setting
that isn't there is skipped, the arc still shows.
"""
import maya.cmds as cmds

from gus_animtool import anim as A

GROUP = "gusAnimtool_arcs_grp"
PAST = (0.16, 0.47, 1.0)          # the onion skin's colours
FUTURE = (1.0, 0.51, 0.08)
RANGES = (12, 24, 48, 0)          # 0 = the whole frame range
FOLLOW_MAX = 4                    # follow selection: arcs on the first 4 selected controls (trails are heavy)

_state = {"follow": False, "followed": [], "pinned": [], "onion": [], "jobs": [], "callbacks": [], "saved": None,
          "busy": False}


# --------------------------------------------------------------------------- what kind of control
FREE_SOURCES = ("animCurve", "pairBlend", "animBlendNodeBase")    # keys, also through a blend or anim layers


def moves(node):
    """True when the control's arc can be edited: a translate channel that's free - keyable, not locked, not driven
    by a constraint or anything else than keys (5.6.41: keyed or not; 5.6.40 wanted keys, so a control moved by
    its parent or an attach got no arc)."""
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
    """The controls among these (not the arcs themselves: selecting a key dot on an arc to drag it must not move
    the arcs to something else; not components)."""
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


# --------------------------------------------------------------------------- the trail
def _range_frames():
    return int(A.opt("arcs_range", 24))


def _group():
    got = cmds.ls(GROUP, long=True)
    if got:
        return got[0]
    with A.NoUndo():
        return cmds.ls(cmds.createNode("transform", name=GROUP), long=True)[0]


def _short(n):
    return n.split("|")[-1].split(":")[-1]


def make(nodes):
    """Editable trails on these controls. Returns the trail nodes made. Your selection is put back after (Maya
    selects a new trail - that must not count as you selecting something)."""
    s, e = A.frame_range()
    sel = cmds.ls(selection=True, long=True) or []
    was = _state["busy"]
    _state["busy"] = True
    made = []
    try:
        grp = _group()
        for n in nodes:
            got = cmds.snapshot(n, motionTrail=True, increment=1, startTime=s, endTime=e,
                                name=_short(n) + "_arc") or []
            for g in got:
                if cmds.nodeType(g) == "transform":
                    try:
                        g = cmds.parent(g, grp)[0]
                    except RuntimeError:
                        pass
                made.append(g)
                style(g)
    finally:
        try:
            if sel:
                cmds.select(sel, replace=True)
            else:
                cmds.select(clear=True)
        except (RuntimeError, ValueError):
            pass
        _state["busy"] = was
    return made


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


def _enum_index(node, attr, word):
    """The index of the enum value whose name has this word (Maya's enum names differ between versions)."""
    try:
        names = (cmds.attributeQuery(attr, node=node, listEnum=True) or [""])[0].split(":")
    except (RuntimeError, ValueError, TypeError):
        return None
    for i, name in enumerate(names):
        if word in name.lower().replace(" ", ""):
            return i
    return None


def style(node, frames=None):
    """The onion skin look on a trail: a window around your frame, fading ends, past / future colours, a dot on
    every frame, bigger keys, a thin line; the bezier handles on the selected key only. Returns what was set."""
    frames = _range_frames() if frames is None else int(frames)
    done = []
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or [node]
    for sh in shapes:
        have = _attrs(sh)

        def put(attr, *value, **kw):
            if attr in have and _set(sh, attr, *value, **kw):
                done.append(attr)
        put("showFrameMarkers", True)
        put("frameMarkerSize", 5.0)
        put("keyframeSize", 9.0)
        put("trailThickness", 1.5)
        put("showFrames", False)
        if frames:
            put("preFrame", frames)
            put("postFrame", frames)
            put("fadeInoutFrames", max(2, frames // 3))
        else:
            s, e = A.frame_range()
            put("preFrame", e - s + 1)
            put("postFrame", e - s + 1)
            put("fadeInoutFrames", 0)
        if "trailDrawMode" in have:
            i = _enum_index(sh, "trailDrawMode", "past")
            if i is not None:
                put("trailDrawMode", i)
        colours = [a for a in have if a.lower().endswith("color") and not a[-1].isdigit()]
        for a in colours:
            low = a.lower()
            if "pre" in low or "past" in low:
                put(a, *PAST, type="double3")
            elif "post" in low or "future" in low:
                put(a, *FUTURE, type="double3")
        put("trailColor", *FUTURE, type="double3")
        # the bezier handles: on the key you select (Maya shows them only there)
        for a in have:
            low = a.lower()
            if low.startswith("show") and "tangent" in low:
                put(a, True)
    return done


def restyle():
    for t in trails():
        style(t)


def trails():
    grp = cmds.ls(GROUP, long=True)
    if not grp:
        return []
    return cmds.listRelatives(grp[0], children=True, fullPath=True) or []


def _trails_of(node):
    short = _short(node) + "_arc"
    return [t for t in trails() if t.split("|")[-1].startswith(short)]


# --------------------------------------------------------------------------- the onion skin (rotation-only controls)
def _onion():
    try:
        import onionSkinRenderer.session as session
        return session.get()
    except Exception:
        return None


def show_in_onion(nodes):
    """Rotation-only controls: their arcs drawn by the onion skin (light, any control). Returns how many."""
    s = _onion()
    if s is None or not nodes:
        return 0
    a = s.o.arcs
    new = [(n, None) for n in nodes if (n, None) not in a.points]
    if new:
        a.setPoints(a.points + new)
        _state["onion"] += [p for p in new if p not in _state["onion"]]
        try:
            s._arcKeys()
        except Exception:
            pass
        if not s.prefs.get("arcsShow"):
            s.setArcs("arcsShow", True)
        s.changed()
        s.scheduleAutoFill()
    return len(nodes)


def _drop_from_onion(points):
    s = _onion()
    if s is None:
        return
    for p in points:
        if p in s.o.arcs.points:
            s.o.arcs.removePoint(p)
        if p in _state["onion"]:
            _state["onion"].remove(p)
    s.changed()


def onion_is_on():
    s = _onion()
    try:
        return bool(s and s.isOn())
    except Exception:
        return False


# --------------------------------------------------------------------------- show for a selection
def show(nodes):
    """Arcs on these controls: editable trails where the translate is animated, onion skin arcs for the others.
    Returns (editable controls, view-only controls, view-only controls with nothing to show them)."""
    nodes = controls(nodes)
    edit = [n for n in nodes if moves(n)]
    view = [n for n in nodes if n not in edit]
    have = set()
    for n in edit:
        if _trails_of(n):
            have.add(n)
    with A.NoUndo():                                       # showing arcs isn't an undo step
        make([n for n in edit if n not in have])
    shown = show_in_onion(view) if view else 0
    return edit, view, ([] if shown else view)


def describe(edit, view, unseen):
    parts = []
    keyed = [n for n in edit if has_translate_keys(n)]
    bare = [n for n in edit if n not in keyed]
    if keyed:
        parts.append("%d editable arc(s): %s (drag a key dot; select a key for its handles)" % (
            len(keyed), ", ".join(_short(n) for n in keyed[:3])))
    if bare:
        parts.append("%d arc(s) with no translate keys yet: %s (set a key to edit it)" % (
            len(bare), ", ".join(_short(n) for n in bare[:3])))
    seen = [v for v in view if v not in unseen]
    if seen:
        parts.append("%d shown by the onion skin%s (they only rotate: shown, not editable)" % (
            len(seen), "" if onion_is_on() else " - turn the onion skin ON in your camera view to see them"))
    if unseen:
        parts.append("%s only rotate%s: no arc to drag (install the onion skin to see them)" % (
            ", ".join(_short(n) for n in unseen[:3]), "s" if len(unseen) == 1 else ""))
    return "; ".join(parts) if parts else "select a control first"


# --------------------------------------------------------------------------- follow selection / pin
def follow(on=None):
    """The Arcs button: arcs follow your selection (on / off). Returns the new state."""
    on = (not _state["follow"]) if on is None else bool(on)
    _state["follow"] = on
    _watch()
    if on:
        _selection_changed()
    else:
        _clear_followed()
    return on


def _selection_changed(*_):
    if not _state["follow"] or _state["busy"]:
        return
    _state["busy"] = True
    try:
        sel = controls(cmds.ls(selection=True, long=True) or [])[:FOLLOW_MAX]
        if not sel:
            return                                          # nothing selected: keep what shows
        keep = set(_state["pinned"]) | set(sel)
        old = [n for n in _state["followed"] if n not in keep]
        if old:
            with A.NoUndo():
                for n in old:
                    for t in _trails_of(n):
                        if cmds.objExists(t):
                            cmds.delete(t)
            _drop_from_onion([(n, None) for n in old])
        show(sel)
        _state["followed"] = [n for n in sel if n not in _state["pinned"]]
    finally:
        _state["busy"] = False


def _clear_followed():
    with A.NoUndo():
        for n in _state["followed"]:
            for t in _trails_of(n):
                if cmds.objExists(t):
                    cmds.delete(t)
    _drop_from_onion([(n, None) for n in _state["followed"]])
    _state["followed"] = []


def pin(nodes):
    """These controls' arcs stay when you select something else."""
    nodes = controls(nodes)
    if not nodes:
        raise RuntimeError("select the controls whose arcs should stay.")
    got = show(nodes)
    for n in nodes:
        if n not in _state["pinned"]:
            _state["pinned"].append(n)
        if n in _state["followed"]:
            _state["followed"].remove(n)
    _watch()
    return got


def clear():
    """Every arc away (trails and the ones we gave the onion skin); follow selection off."""
    _state["follow"] = False
    _drop_from_onion(list(_state["onion"]))
    _state["followed"], _state["pinned"] = [], []
    grp = cmds.ls(GROUP, long=True)
    if grp:
        with A.NoUndo():
            cmds.delete(grp)
    _unwatch()
    return True


def set_range(frames):
    A.set_opt("arcs_range", int(frames))
    restyle()
    return int(frames)


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
    """The selection job (follow) and the save / open callbacks - made once, while there are arcs."""
    if not any(cmds.scriptJob(exists=j) for j in _state["jobs"]):
        _state["jobs"] = [cmds.scriptJob(event=["SelectionChanged", _deferred_follow]),
                          cmds.scriptJob(event=["SceneOpened", _scene_gone]),
                          cmds.scriptJob(event=["NewSceneOpened", _scene_gone])]
    if not _state["callbacks"]:
        try:
            import maya.api.OpenMaya as om
            msg = om.MSceneMessage
            _state["callbacks"] = [msg.addCallback(msg.kBeforeSave, _before_save),
                                   msg.addCallback(msg.kAfterSave, _after_save)]
        except Exception:
            _state["callbacks"] = []


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


def _deferred_follow(*_):
    if _state["follow"] and not _state["busy"]:
        cmds.evalDeferred(_selection_changed, lowestPriority=True)


def _before_save(*_):
    """No arc nodes in your file: the trails are taken out (and put back after the save)."""
    controls_with = [n for n in _state["followed"] + _state["pinned"] if cmds.objExists(n)]
    _state["saved"] = controls_with
    grp = cmds.ls(GROUP, long=True)
    if grp:
        with A.NoUndo():
            cmds.delete(grp)


def _after_save(*_):
    nodes = _state.get("saved") or []
    _state["saved"] = None
    if nodes:
        cmds.evalDeferred(lambda: show(nodes), lowestPriority=True)


def _scene_gone(*_):
    _state["followed"], _state["pinned"], _state["onion"] = [], [], []
    _state["follow"] = False
    _unwatch()


def state():
    return dict(_state)
