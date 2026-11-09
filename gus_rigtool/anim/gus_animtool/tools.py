"""
Everyday animator tools (toolbar / shelf / Keys tab):

  tangents     : the selected Graph Editor keys - or the selection's keys at the current frame - get a tangent type
  copy / paste : the selection's animation, by control name (works between characters and scenes in one session)
  reverse      : the selection's keys in the frame range play backwards
  time scale   : the selection's keys spread out / squeezed around the current frame (snapped to whole frames)
  smooth/noise : the selected Graph Editor keys smoothed towards their neighbours / given a little noise
  playblast    : the frame range from the viewport you look through, into your movies folder
  arcs         : a motion trail per selected control over the range (arc tracker); clear them
  viewport     : hide / show the controls, isolate the selection
"""

import os
import random

import maya.cmds as cmds

from gus_animtool import anim as A

TANGENTS = ["auto", "spline", "clamped", "linear", "flat", "step", "plateau"]
ARCS = "gusAnimtool_arcs_grp"
_clip = {"data": None, "start": None}


def _nodes(need=True):
    nodes = [n for n in A.selected() if cmds.objExists(n)]
    if need and not nodes:
        raise RuntimeError("select the controls first.")
    return nodes


def _now():
    return cmds.currentTime(query=True)


# ---------------------------------------------------------------------------
# tangents
# ---------------------------------------------------------------------------

def tangents(kind):
    """Selected Graph Editor keys, else the selection's keys at the current frame. Returns how many curves."""
    if kind not in TANGENTS:
        raise RuntimeError("unknown tangent: %s" % kind)
    flags = {"outTangentType": kind} if kind == "step" else {"inTangentType": kind, "outTangentType": kind}
    with A.Undo("gusAnimtoolTangents"):
        curves = cmds.keyframe(query=True, selected=True, name=True) or []
        if curves:
            for c in curves:
                for i in cmds.keyframe(c, query=True, selected=True, indexValue=True) or []:
                    cmds.keyTangent(c, index=(i, i), **flags)
            return len(curves)
        nodes = _nodes()
        t = _now()
        done = [n for n in nodes if cmds.keyframe(n, query=True, time=(t, t), keyframeCount=True)]
        if not done:
            raise RuntimeError("no keys selected in the Graph Editor, and no keys at this frame.")
        cmds.keyTangent(done, time=(t, t), **flags)
        return len(done)


def _block_curves(nodes=None):
    if nodes is None:
        nodes = _character() if int(A.opt("block_scope", 1)) == 1 else _nodes()
    curves = A.time_curves(nodes)
    if not curves:
        raise RuntimeError("no animation on these controls.")
    return curves


def is_blocking(curves):
    """True when most keys are stepped."""
    outs = [t for c in curves for t in (cmds.keyTangent(c, query=True, outTangentType=True) or [])]
    return bool(outs) and sum(1 for t in outs if t == "step") * 2 >= len(outs)


def blocking(on=None, nodes=None):
    """Blocking: every key of the character stepped, and new keys too. Spline: back - each key's out tangent
    takes its in tangent again (stepped only ever changes the out side), new keys as before. on=None: toggle."""
    curves = _block_curves(nodes)
    if on is None:
        on = not is_blocking(curves)
    with A.Undo("gusAnimtoolBlocking"):
        if on:
            cmds.keyTangent(curves, outTangentType="step")
            try:
                now = (cmds.keyTangent(query=True, g=True, outTangentType=True) or ["auto"])[0]
                if now != "step":
                    A.set_opt("block_prev_out", now)
                cmds.keyTangent(g=True, outTangentType="step")
            except (RuntimeError, TypeError):
                pass
        else:
            for c in curves:
                ins = cmds.keyTangent(c, query=True, inTangentType=True) or []
                runs, start = [], 0                    # one call per run of keys with the same tangent
                kinds = ["auto" if t in ("step", "stepnext") else t for t in ins]
                for i in range(1, len(kinds) + 1):
                    if i == len(kinds) or kinds[i] != kinds[start]:
                        runs.append((start, i - 1, kinds[start]))
                        start = i
                for a, b, t in runs:
                    cmds.keyTangent(c, index=(a, b), outTangentType=t)
            try:
                cmds.keyTangent(g=True, outTangentType=str(A.opt("block_prev_out", "auto")))
            except (RuntimeError, TypeError):
                pass
    A.message("%s: %d curve(s)%s." % ("Blocking (stepped)" if on else "Spline", len(curves),
                                       ", new keys stepped too" if on else ", new keys as before"))
    return on


# ---------------------------------------------------------------------------
# copy / paste animation
# ---------------------------------------------------------------------------

_strip = A.bare


def copy_animation(nodes=None):
    """Remember the selection's keys (every animated attribute). Returns how many curves."""
    nodes = nodes or _nodes()
    data = {}
    first = None
    for n in nodes:
        attrs = {}
        for c in A.time_curves(n):
            plug = (cmds.listConnections(c + ".output", plugs=True, source=False) or [None])[0]
            if not plug:
                continue
            attr = plug.split(".", 1)[1]
            times = cmds.keyframe(c, query=True, timeChange=True) or []
            vals = cmds.keyframe(c, query=True, valueChange=True) or []
            itt = cmds.keyTangent(c, query=True, inTangentType=True) or ["auto"] * len(times)
            ott = cmds.keyTangent(c, query=True, outTangentType=True) or ["auto"] * len(times)
            attrs[attr] = [list(k) for k in zip(times, vals, itt, ott)]
            if times:
                first = times[0] if first is None else min(first, times[0])
        if attrs:
            data[_strip(n)] = attrs
    if not data:
        raise RuntimeError("the selection has no animation.")
    _clip["data"], _clip["start"] = data, first
    return sum(len(a) for a in data.values())


def paste_animation(nodes=None, at_current=False, replace=True):
    """The copied keys onto the selection (matched by name; one control copied -> every selected one).
    at_current: the first copied key lands on the current frame. Returns how many curves."""
    data = _clip["data"]
    if not data:
        raise RuntimeError("copy some animation first.")
    nodes = nodes or _nodes()
    offset = (_now() - _clip["start"]) if at_current else 0.0
    one = list(data.values())[0] if len(data) == 1 else None
    n_curves = 0
    with A.Undo("gusAnimtoolPasteAnim"):
        for n in nodes:
            attrs = data.get(_strip(n)) or one
            if not attrs:
                continue
            for attr, keys in attrs.items():
                plug = n + "." + attr
                if not cmds.objExists(plug) or not A._settable(plug):
                    continue
                if replace:
                    try:
                        cmds.cutKey(n, attribute=attr, clear=True)
                    except RuntimeError:
                        pass
                for t, v, itt, ott in keys:
                    cmds.setKeyframe(n, attribute=attr, time=t + offset, value=v)
                    try:
                        cmds.keyTangent(n, attribute=attr, time=(t + offset, t + offset), inTangentType=itt,
                                        outTangentType=ott)
                    except RuntimeError:
                        pass
                n_curves += 1
    if not n_curves:
        raise RuntimeError("no control matches the copied names (copy one control to paste on any).")
    return n_curves


# ---------------------------------------------------------------------------
# retime / curves
# ---------------------------------------------------------------------------

def reverse(nodes=None):
    """The keys inside the frame range play backwards (same range)."""
    nodes = nodes or _nodes()
    s, e = A.frame_range()
    curves = A.time_curves(nodes)
    if not curves:
        raise RuntimeError("the selection has no animation.")
    with A.Undo("gusAnimtoolReverse"):
        cmds.scaleKey(curves, time=(s, e), timeScale=-1, timePivot=(s + e) * 0.5)
    return len(nodes)


def time_scale(factor, nodes=None, snap=True):
    """The selection's keys after the current frame spread (factor > 1) or squeeze (< 1) from the current frame."""
    nodes = nodes or _nodes()
    now = _now()
    curves = A.time_curves(nodes)
    if not curves:
        raise RuntimeError("the selection has no animation.")
    with A.Undo("gusAnimtoolTimeScale"):
        cmds.scaleKey(curves, time=(now, 1e6), timeScale=float(factor), timePivot=now)
        if snap:
            try:
                cmds.snapKey(curves, timeMultiple=1)
            except RuntimeError:
                pass
    return len(nodes)


def _character(nodes=None):
    """The whole character of the selection (every control), else the selection."""
    if nodes:
        return nodes
    sel = _nodes()
    every = A.character_controls(A.namespace_of(sel[0]))
    return every or sel


def stretch_range():
    """(first, last) frame to stretch: a range highlighted in the Time Slider, else the Time Slider's range."""
    from gus_animtool import keys as K
    hl = K.slider_range()
    if hl and hl[1] > hl[0]:
        return hl
    return (float(cmds.playbackOptions(query=True, minTime=True)),
            float(cmds.playbackOptions(query=True, maxTime=True)))


def stretch(length=None, percent=None, nodes=None, snap=True):
    """The whole character's motion slower (or faster): the range becomes 'length' frames (or percent %).
    Keys after the range move with it; the Time Slider follows; keys snap to whole frames."""
    nodes = _character(nodes)
    first, last = stretch_range()
    old = last - first + 1
    if length is None:
        if not percent:
            raise RuntimeError("give the new length in frames (or a %).")
        length = old * float(percent) / 100.0
    length = float(int(round(length)))
    if length < 2:
        raise RuntimeError("the new length is too short.")
    factor = length / old
    if abs(factor - 1) < 1e-6:
        return 0
    curves = A.time_curves(nodes)
    if not curves:
        raise RuntimeError("no animation on this character.")
    with A.Undo("gusAnimtoolStretch"):
        cmds.scaleKey(curves, time=(first, 1e6), timeScale=factor, timePivot=first)
        if snap:
            try:
                cmds.snapKey(curves, timeMultiple=1)
            except RuntimeError:
                pass
        new_last = first + length - 1
        try:
            end = cmds.playbackOptions(query=True, animationEndTime=True)
            cmds.playbackOptions(minTime=first, maxTime=new_last,
                                 animationEndTime=max(new_last, end + (new_last - last)))
        except (RuntimeError, TypeError):
            pass
    A.message("%g-%g (%d frames) is now %g-%g (%d frames), x%.2f on %d control(s)%s." % (
        first, last, old, first, new_last, length, factor, len(nodes), ", snapped to whole frames" if snap else ""))
    return len(curves)


def _selected_keys():
    curves = cmds.keyframe(query=True, selected=True, name=True) or []
    if not curves:
        raise RuntimeError("select keys in the Graph Editor first.")
    return curves


def smooth(amount=0.5):
    """Each selected key moves towards the average of its two neighbours (amount 1 = all the way)."""
    n = 0
    with A.Undo("gusAnimtoolSmooth"):
        for c in _selected_keys():
            vals = cmds.keyframe(c, query=True, valueChange=True) or []
            chosen = cmds.keyframe(c, query=True, selected=True, indexValue=True) or []
            new = {}
            for i in chosen:
                if 0 < i < len(vals) - 1:
                    avg = (vals[i - 1] + vals[i + 1]) * 0.5
                    new[i] = vals[i] + (avg - vals[i]) * amount
            for i, v in new.items():
                cmds.keyframe(c, index=(i, i), absolute=True, valueChange=v)
                n += 1
    return n


def noise(amount=0.1, seed=None):
    """The selected keys get a random offset: amount x the curve's range (0.1 = 10 %)."""
    rnd = random.Random(seed)
    n = 0
    with A.Undo("gusAnimtoolNoise"):
        for c in _selected_keys():
            vals = cmds.keyframe(c, query=True, valueChange=True) or [0.0]
            span = (max(vals) - min(vals)) or 1.0
            for i in cmds.keyframe(c, query=True, selected=True, indexValue=True) or []:
                cmds.keyframe(c, index=(i, i), relative=True, valueChange=rnd.uniform(-1, 1) * span * amount)
                n += 1
    return n


# ---------------------------------------------------------------------------
# playblast / arcs / viewport
# ---------------------------------------------------------------------------

def _panel():
    panel = cmds.getPanel(withFocus=True)
    if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
        visible = [p for p in cmds.getPanel(visiblePanels=True) or [] if cmds.getPanel(typeOf=p) == "modelPanel"]
        if not visible:
            raise RuntimeError("no viewport is open.")
        panel = visible[0]
    return panel


HUD = "gusAnimtoolHud_"


def blast_settings():
    """The playblast options (remembered): shot name, artist, folder, HUD on / off."""
    import getpass
    scene = os.path.splitext(os.path.basename(cmds.file(query=True, sceneName=True) or "untitled"))[0] or "untitled"
    try:
        user = getpass.getuser()
    except Exception:
        user = ""
    return {"shot": str(A.opt("blast_shot", "")) or scene, "artist": str(A.opt("blast_artist", "")) or user,
            "folder": str(A.opt("blast_folder", "")) or _movies(), "hud": bool(A.opt("blast_hud", 1)),
            "scale": int(A.opt("playblast_scale", 100))}


def _movies():
    try:
        folder = os.path.join(cmds.workspace(query=True, rootDirectory=True), "movies")
    except (RuntimeError, TypeError):
        folder = os.path.expanduser("~")
    return folder.replace("\\", "/")


def next_version(folder, shot):
    """<folder>/<shot>_v001, v002... - the first one not used yet (any movie extension)."""
    n = 1
    names = set(os.path.splitext(f)[0] for f in (os.listdir(folder) if os.path.isdir(folder) else []))
    while "%s_v%03d" % (shot, n) in names:
        n += 1
    return os.path.join(folder, "%s_v%03d" % (shot, n)).replace("\\", "/")


def _camera(panel):
    try:
        cam = cmds.modelPanel(panel, query=True, camera=True)
        if cmds.nodeType(cam) == "transform":
            shapes = cmds.listRelatives(cam, shapes=True) or [cam]
        else:
            shapes = [cam]
        return cam, shapes[0]
    except (RuntimeError, ValueError, TypeError, IndexError):
        return None, None


def _huds_on():
    """Maya's HUDs that are showing (they're hidden during our blast, then put back)."""
    out = []
    for h in cmds.headsUpDisplay(listHeadsUpDisplays=True) or []:
        try:
            if cmds.headsUpDisplay(h, query=True, visible=True):
                out.append(h)
        except RuntimeError:
            pass
    return out


def _hud_add(name, section, block, label, command, event=None):
    full = HUD + name
    if cmds.headsUpDisplay(full, exists=True):
        cmds.headsUpDisplay(full, remove=True)
    try:
        free = cmds.headsUpDisplay(nextFreeBlock=section)
    except RuntimeError:
        free = block
    flags = {"event": event} if event else {"attachToRefresh": True}
    cmds.headsUpDisplay(full, section=section, block=free, label=label, command=command, labelFontSize="large",
                        dataFontSize="large", blockSize="medium", **flags)
    return full


def make_hud(shot, artist, cam_shape, start, end):
    """Shot (top left), artist and date (top right), frame / total (bottom right), focal length (bottom left)."""
    import datetime
    today = datetime.date.today().isoformat()
    made = [_hud_add("shot", 0, 0, "", lambda: shot),
            _hud_add("artist", 4, 0, "", lambda: "%s   %s" % (artist, today)),
            _hud_add("frame", 9, 0, "", lambda: "%d / %d" % (int(round(cmds.currentTime(query=True))), int(end)))]
    if cam_shape:
        made.append(_hud_add("focal", 5, 0, "", lambda: "%gmm" % round(cmds.getAttr(cam_shape + ".focalLength"), 1)))
    return made


def clear_hud():
    for h in cmds.headsUpDisplay(listHeadsUpDisplays=True) or []:
        if h.startswith(HUD):
            try:
                cmds.headsUpDisplay(h, remove=True)
            except RuntimeError:
                pass


def playblast(scale=None, hud=None, shot=None, artist=None, folder=None):
    """The frame range from the viewport you look through, with the HUD (shot, artist, date, frame, focal),
    saved as <folder>/<shot>_v###. Opens in your player. Maya's own HUDs come back after. Returns the file."""
    o = blast_settings()
    scale = int(scale or o["scale"])
    hud = o["hud"] if hud is None else hud
    shot = shot or o["shot"]
    artist = o["artist"] if artist is None else artist
    folder = folder or o["folder"]
    s, e = A.frame_range()
    if not os.path.isdir(folder):
        os.makedirs(folder)
    path = next_version(folder, shot)
    panel = _panel()
    try:
        cmds.setFocus(panel)
    except RuntimeError:
        pass
    shown = []
    try:
        if hud:
            shown = _huds_on()
            for h in shown:
                cmds.headsUpDisplay(h, edit=True, visible=False)
            _cam, shape = _camera(panel)
            make_hud(shot, artist, shape, s, e)
        return cmds.playblast(startTime=s, endTime=e, filename=path, forceOverwrite=True, percent=scale,
                              viewer=True, showOrnaments=bool(hud), clearCache=True)
    finally:
        if hud:
            clear_hud()
            for h in shown:
                try:
                    cmds.headsUpDisplay(h, edit=True, visible=True)
                except RuntimeError:
                    pass


def arcs(nodes=None):
    """A motion trail per selected control over the frame range (arc tracker). Returns the trails."""
    nodes = nodes or _nodes()
    s, e = A.frame_range()
    grp = cmds.ls(ARCS, long=True)
    grp = grp[0] if grp else cmds.ls(cmds.createNode("transform", name=ARCS), long=True)[0]
    made = []
    with A.Undo("gusAnimtoolArcs"):
        for n in nodes:
            got = cmds.snapshot(n, motionTrail=True, increment=1, startTime=s, endTime=e,
                                name=_strip(n) + "_arc") or []
            for g in got:
                if cmds.nodeType(g) == "transform":
                    try:
                        g = cmds.parent(g, grp)[0]
                    except RuntimeError:
                        pass
                made.append(g)
                _style_trail(g)
    return made


def _style_trail(node):
    """Frame markers (spacing shows), keys bigger, a clear colour - on a motion trail."""
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or [node]
    for sh in shapes:
        for attr, value in (("showFrameMarkers", True), ("frameMarkerSize", 6.0), ("keyframeSize", 9.0),
                            ("trailThickness", 2.0), ("showFrames", False)):
            try:
                cmds.setAttr("%s.%s" % (sh, attr), value)
            except (RuntimeError, ValueError, TypeError):
                pass
        try:
            cmds.setAttr(sh + ".trailColor", 1.0, 0.55, 0.15, type="double3")
        except (RuntimeError, ValueError, TypeError):
            pass


def clear_arcs(*_):
    grp = cmds.ls(ARCS, long=True)
    if not grp:
        raise RuntimeError("no arcs to clear.")
    cmds.delete(grp)
    return True


def toggle_controls(*_):
    """Hide / show the controls (curves) in the viewport you look through. Returns True when shown."""
    panel = _panel()
    on = not cmds.modelEditor(panel, query=True, nurbsCurves=True)
    cmds.modelEditor(panel, edit=True, nurbsCurves=on)
    return on


def toggle_isolate(*_):
    """Isolate the selection in the viewport you look through (again: everything back)."""
    import maya.mel as mel
    panel = _panel()
    on = not cmds.isolateSelect(panel, query=True, state=True)
    if on and not cmds.ls(selection=True):
        raise RuntimeError("select what to isolate.")
    mel.eval("enableIsolateSelect %s %d" % (panel, int(on)))
    return on


# ---------------------------------------------------------------------------
# ghosts (onion skin)
# ---------------------------------------------------------------------------

GHOSTS = "gusAnimtool_ghosts_grp"


def character_meshes(ns=None):
    """The character's skinned meshes (its namespace), else the selected meshes."""
    sel = [n for n in cmds.ls(selection=True, long=True) or [] if cmds.listRelatives(n, shapes=True, type="mesh")]
    if sel:
        return sel
    ns = (A.current_character() if ns is None else ns) or ""
    out = []
    for skin in cmds.ls(type="skinCluster") or []:
        for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
            t = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
            if A.namespace_of(t) == ns and t not in out:
                out.append(t)
    return out


def _ghost_shader(name, rgb):
    if cmds.objExists(name + "SG"):
        return name + "SG"
    sh = cmds.shadingNode("lambert", asShader=True, name=name)
    cmds.setAttr(sh + ".color", *rgb, type="double3")
    cmds.setAttr(sh + ".transparency", 0.7, 0.7, 0.7, type="double3")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "SG")
    cmds.connectAttr(sh + ".outColor", sg + ".surfaceShader")
    return sg


def ghosts(before=None, after=None, step=None, meshes=None):
    """See-through copies of the character a few frames before (blue) and after (orange) the current one. They
    update when you change keys. Returns how many copies."""
    before = int(A.opt("ghost_before", 2) if before is None else before)
    after = int(A.opt("ghost_after", 2) if after is None else after)
    step = max(1, int(A.opt("ghost_step", 2) if step is None else step))
    meshes = meshes or character_meshes()
    if not meshes:
        raise RuntimeError("no skinned meshes found for this character (or select the meshes).")
    clear_ghosts(quiet=True)
    now = cmds.currentTime(query=True)
    top = cmds.createNode("transform", name=GHOSTS)
    made = 0
    with A.Undo("gusAnimtoolGhosts"):
        for label, a, b, rgb in (("before", now - before * step, now - step, (0.3, 0.55, 1.0)),
                                 ("after", now + step, now + after * step, (1.0, 0.6, 0.2))):
            if (label == "before" and before < 1) or (label == "after" and after < 1):
                continue
            got = cmds.snapshot(meshes, constructionHistory=True, startTime=a, endTime=b, increment=step,
                                update="animCurve", name="gusGhost_" + label) or []
            grp = [g for g in got if cmds.nodeType(g) == "transform"]
            for g in grp:
                cmds.parent(g, top)
                cmds.sets(g, edit=True, forceElement=_ghost_shader("gusGhost_%s_mat" % label, rgb))
                made += len(cmds.listRelatives(g, children=True) or [])
    return made


def clear_ghosts(quiet=False):
    gone = False
    for n in cmds.ls(GHOSTS, long=True) or []:
        cmds.delete(n)
        gone = True
    for n in cmds.ls("gusGhost_*", type="snapshot") or []:
        cmds.delete(n)
    if not gone and not quiet:
        raise RuntimeError("no ghosts to clear.")
    return gone


# ---------------------------------------------------------------------------
# jiggle (Gus_Rigtool chains with the jiggle option)
# ---------------------------------------------------------------------------

def bake_jiggle(start=None, end=None):
    """The jiggle of the character's chains baked to keys over the frame range (it then stays as animation -
    turn 'jiggle' to 0 on the settings control to keep it from adding more). Returns how many groups."""
    ns = A.current_character() or ""
    groups = [g for g in cmds.ls("*.gusJiggle", objectsOnly=True, long=True, recursive=True) or []
              if A.namespace_of(g) == ns]
    if not groups:
        raise RuntimeError("no jiggle in this character (Gus_Rigtool chains built with the Jiggle option).")
    if start is None:
        start, end = A.frame_range()
    with A.Undo("gusAnimtoolBakeJiggle"):
        cmds.bakeResults(groups, time=(start, end), simulation=True, attribute=["rotateX", "rotateY", "rotateZ"])
    return len(groups)
