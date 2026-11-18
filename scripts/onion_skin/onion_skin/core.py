"""
Onion Skin - the logic (no window here). Ghosts are real 3D copies of the meshes at other frames (Maya snapshot
nodes), so every camera sees them, for every character, with nothing to switch on in a viewport.

    from onion_skin import core
    core.add_targets(cmds.ls(selection=True))     # meshes, groups or controls
    core.update()                                  # ghosts around the current frame
    core.clear()                                   # all ghosts gone

Nothing here goes into the undo queue, and the ghosts are taken out of the scene just before it is saved.
"""

import maya.cmds as cmds

ROOT = "onionSkin_ghosts"            # the group that holds every ghost
LAYER = "onionSkin_layer"            # display layer: not selectable, one click to hide
PREFIX = "onionSkin_"
TAG = "onionSkinGhost"               # mark on every node this tool makes
CURVE_TYPES = ("animCurveTL", "animCurveTA", "animCurveTU")

DEFAULTS = {"past": 1, "next": 1, "mode": "keys", "step": 2, "opacity": 0.5, "fade": 0.6, "live": 1,
            "past_color": (0.25, 0.5, 1.0), "next_color": (1.0, 0.55, 0.15)}
OPTION = "onionSkin_"                # optionVar prefix
TARGETS = []                         # what you added (long names)
_BUILT = {}                          # (character id, frame) -> [nodes made for it]


# ---------------------------------------------------------------- settings (kept between sessions)
def opt(name):
    key = OPTION + name
    if cmds.optionVar(exists=key):
        v = cmds.optionVar(query=key)
        if name.endswith("_color"):
            try:
                return tuple(float(x) for x in str(v).split())[:3]
            except ValueError:
                return DEFAULTS[name]
        return v
    return DEFAULTS[name]


def set_opt(name, value):
    key = OPTION + name
    if name.endswith("_color"):
        cmds.optionVar(stringValue=(key, " ".join("%g" % c for c in value)))
    elif name == "mode":
        cmds.optionVar(stringValue=(key, value))
    elif isinstance(value, float):
        cmds.optionVar(floatValue=(key, value))
    else:
        cmds.optionVar(intValue=(key, int(value)))


# ---------------------------------------------------------------- what to ghost
def _long(n):
    got = cmds.ls(n, long=True)
    return got[0] if got else None


def _namespace(node):
    short = node.split("|")[-1]
    return short.split(":")[0] if ":" in short else ""


def scope_of(node):
    """('ns', name) for a referenced character, else ('root', its top group)."""
    ns = _namespace(node)
    if ns:
        return ("ns", ns)
    return ("root", "|" + node.lstrip("|").split("|")[0])


def _in_scope(node, scope):
    kind, name = scope
    if kind == "ns":
        return node.split("|")[-1].startswith(name + ":") or any(
            p.startswith(name + ":") for p in node.split("|") if p)
    return node == name or node.startswith(name + "|")


def _visible_mesh_transforms(shapes):
    out = []
    for s in cmds.ls(shapes, long=True, noIntermediate=True, visible=True) or []:
        if cmds.nodeType(s) != "mesh":
            continue
        t = (cmds.listRelatives(s, parent=True, fullPath=True) or [None])[0]
        if t and t not in out and not t.startswith("|" + ROOT):
            out.append(t)
    return out


def meshes_of(target):
    """The meshes a target stands for: a mesh itself; a group, the meshes inside; a control, its whole character
    (the meshes in its namespace, or under its top group)."""
    t = _long(target)
    if not t:
        return []
    if cmds.nodeType(t) == "mesh":
        t = cmds.listRelatives(t, parent=True, fullPath=True)[0]
    own = cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or []
    if own:
        return _visible_mesh_transforms(own)
    under = cmds.listRelatives(t, allDescendents=True, type="mesh", fullPath=True) or []
    if under:
        return _visible_mesh_transforms(under)
    scope = scope_of(t)                                    # a control: its character
    if scope[0] == "ns":
        shapes = [s for s in cmds.ls(scope[1] + ":*", type="mesh", long=True, recursive=True) or []]
    else:
        shapes = cmds.listRelatives(scope[1], allDescendents=True, type="mesh", fullPath=True) or []
    return _visible_mesh_transforms(shapes)


def all_meshes(targets=None):
    out = []
    for t in (TARGETS if targets is None else targets):
        for m in meshes_of(t):
            if m not in out:
                out.append(m)
    return out


def add_targets(nodes):
    """Add to the list (long names). Returns what was new."""
    new = []
    for n in nodes or []:
        ln = _long(n)
        if ln and ln not in TARGETS and not ln.startswith("|" + ROOT):
            TARGETS.append(ln)
            new.append(ln)
    return new


def remove_targets(nodes):
    gone = []
    for n in nodes or []:
        ln = _long(n) or n
        if ln in TARGETS:
            TARGETS.remove(ln)
            gone.append(ln)
    return gone


def clear_targets():
    del TARGETS[:]


# ---------------------------------------------------------------- which frames
def key_times(targets=None):
    """Every key time of the characters' own animation (their animated nodes), sorted - no selection needed."""
    scopes = []
    for t in (TARGETS if targets is None else targets):
        ln = _long(t)
        if ln:
            s = scope_of(ln)
            if s not in scopes:
                scopes.append(s)
    times = set()
    for curve in cmds.ls(type=list(CURVE_TYPES)) or []:
        if not any(_in_scope(d, s) for d in _driven(curve) for s in scopes):
            continue
        times.update(cmds.keyframe(curve, query=True, timeChange=True) or [])
    return sorted(times)


def _driven(curve, depth=3):
    """The nodes a curve animates - through a blend node (pairBlend, animation layers) if there is one."""
    out, todo = [], [curve]
    for _i in range(depth):
        nxt = []
        for n in todo:
            for d in cmds.listConnections(n + ".output" if n == curve else n, source=False, destination=True,
                                          skipConversionNodes=True) or []:
                ln = _long(d) or d
                if cmds.objectType(ln, isAType="dagNode"):
                    if ln not in out:
                        out.append(ln)
                elif d not in nxt:
                    nxt.append(d)
        todo = nxt
        if not todo:
            break
    return out


def frames_needed(now, past, nxt, mode="keys", step=2, keys=None):
    """[(frame, 'past' | 'next', how far: 1, 2...)] around now. Keys mode: the keys before / after now (from
    keys); frames mode: every step frames."""
    out = []
    if mode == "keys":
        keys = sorted(set(keys or []))
        before = [k for k in keys if k < now - 1e-6][::-1][:past]
        after = [k for k in keys if k > now + 1e-6][:nxt]
    else:
        step = max(1, int(step))
        before = [now - step * i for i in range(1, past + 1)]
        after = [now + step * i for i in range(1, nxt + 1)]
    out += [(f, "past", i + 1) for i, f in enumerate(before)]
    out += [(f, "next", i + 1) for i, f in enumerate(after)]
    return out


def plan(wanted, built):
    """(to make, to remove) - ghosts still wanted are kept. Items are (character id, frame)."""
    w, b = set(wanted), set(built)
    return sorted(w - b), sorted(b - w)


def _cid(scope):
    """A short id for a character, usable in node names."""
    kind, name = scope
    raw = name if kind == "ns" else name.strip("|").split("|")[0]
    return "".join(c if c.isalnum() else "_" for c in raw)


def characters(targets=None):
    """{character id: (scope, [targets])} - each character gets its own ghosts and its own keys."""
    out = {}
    for t in (TARGETS if targets is None else targets):
        ln = _long(t)
        if not ln:
            continue
        sc = scope_of(ln)
        out.setdefault(_cid(sc), (sc, []))[1].append(ln)
    return out


# ---------------------------------------------------------------- ghosts
class _NoUndo(object):
    """Ghost work stays out of the undo queue (Ctrl+Z only undoes your animation)."""
    def __enter__(self):
        self.was = cmds.undoInfo(query=True, stateWithoutFlush=True)
        cmds.undoInfo(stateWithoutFlush=False)

    def __exit__(self, *exc):
        cmds.undoInfo(stateWithoutFlush=self.was)


def _tag(node):
    try:
        if not cmds.attributeQuery(TAG, node=node, exists=True):
            cmds.addAttr(node, longName=TAG, attributeType="bool", defaultValue=True)
    except RuntimeError:
        pass


def _root():
    if not cmds.objExists(ROOT):
        cmds.createNode("transform", name=ROOT, skipSelect=True)
        _tag(ROOT)
        try:
            cmds.setAttr(ROOT + ".hiddenInOutliner", True)
        except RuntimeError:
            pass
    if not cmds.objExists(LAYER):
        cmds.createDisplayLayer(name=LAYER, empty=True, noRecurse=True)
        cmds.setAttr(LAYER + ".displayType", 2)            # reference: seen, not selectable
        _tag(LAYER)
    if ROOT not in (cmds.editDisplayLayerMembers(LAYER, query=True, fullNames=False) or []):
        cmds.editDisplayLayerMembers(LAYER, ROOT, noRecurse=True)
    return ROOT


def _material(side, far):
    """A see-through material per side and distance (fading further away)."""
    name = "%s%s%d_mat" % (PREFIX, side, far)
    color = opt(side + "_color")
    see = 1.0 - float(opt("opacity")) * (float(opt("fade")) ** (far - 1))
    if not cmds.objExists(name):
        cmds.shadingNode("lambert", asShader=True, name=name, skipSelect=True)
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=name + "SG")
        cmds.connectAttr(name + ".outColor", sg + ".surfaceShader")
        _tag(name)
        _tag(sg)
    cmds.setAttr(name + ".color", *color, type="double3")
    cmds.setAttr(name + ".incandescence", *[c * 0.5 for c in color], type="double3")
    cmds.setAttr(name + ".transparency", see, see, see, type="double3")
    return name + "SG"


def _frame_group(cid, frame):
    return "%s%s_f%s" % (PREFIX, cid, ("%g" % frame).replace(".", "_").replace("-", "m"))


def _make(cid, frame, meshes):
    """The meshes at frame, as ghosts in their own group. Returns the nodes made."""
    grp = cmds.createNode("transform", name=_frame_group(cid, frame), parent=_root(), skipSelect=True)
    grp = cmds.ls(grp, long=True)[0]
    _tag(grp)
    made = [grp]
    for m in meshes:
        try:
            got = cmds.snapshot(m, startTime=frame, endTime=frame, increment=1, update="animCurve",
                                constructionHistory=True, name=PREFIX + "snap") or []
        except RuntimeError:
            continue
        for g in got:
            _tag(g)
            if cmds.nodeType(g) == "transform":
                g = cmds.ls(cmds.parent(g, grp)[0], long=True)[0]
            made.append(g)
    return made


def _remove(nodes):
    alive = [n for n in nodes if cmds.objExists(n)]
    if alive:
        cmds.delete(alive)


def _paint(key, side, far):
    """Colour a frame's ghosts (its side can change when the time moves past it)."""
    nodes = _BUILT.get(key) or []
    if not nodes or not cmds.objExists(nodes[0]):
        return
    shapes = cmds.listRelatives(nodes[0], allDescendents=True, type="mesh", fullPath=True) or []
    if shapes:
        cmds.sets(shapes, edit=True, forceElement=_material(side, far))


def update(now=None):
    """Ghosts around now (the current frame), each character at its own keys: new ones made, ones no longer
    needed removed, colours set. Returns {'made', 'removed', 'frames': {character: [...]}, 'notes': [...]}.
    Raises when there is nothing to ghost."""
    if not TARGETS:                                  # nothing in the list: the selection goes in (Live follows it)
        add_targets([n for n in cmds.ls(selection=True, long=True) or [] if not n.startswith("|" + ROOT)])
    targets = list(TARGETS)
    if not targets:
        raise RuntimeError("add something first: select a character's control, mesh or group > Add selected.")
    now = cmds.currentTime(query=True) if now is None else now
    mode = opt("mode")
    wanted, meshes_by, frames_by, notes = [], {}, {}, []
    for cid, (_scope, ts) in characters(targets).items():
        meshes = all_meshes(ts)
        if not meshes:
            notes.append("%s: no visible meshes" % cid)
            continue
        keys = key_times(ts) if mode == "keys" else None
        if mode == "keys" and not keys:
            notes.append("%s: no keys found" % cid)
        got = frames_needed(now, int(opt("past")), int(opt("next")), mode, int(opt("step")), keys)
        meshes_by[cid] = meshes
        frames_by[cid] = [f for f, _s, _d in got]
        wanted += [((cid, round(f, 3)), side, far) for f, side, far in got]
    if not meshes_by:
        raise RuntimeError("no visible meshes found for what's in the list.")
    with _NoUndo():
        make, remove = plan([k for k, _s, _d in wanted], list(_BUILT))
        for k in remove:
            _remove(_BUILT.pop(k, []))
        for k in make:
            _BUILT[k] = _make(k[0], k[1], meshes_by[k[0]])
        for k, side, far in wanted:
            _paint(k, side, far)
    return {"made": len(make), "removed": len(remove), "frames": frames_by, "notes": notes}


def rebuild():
    """Everything made again (after the list or the meshes changed)."""
    clear(keep_targets=True)
    return update()


def clear(keep_targets=True):
    """Every ghost, material and the layer gone (nothing of this tool is left in the scene)."""
    with _NoUndo():
        for nodes in _BUILT.values():
            _remove(nodes)
        _BUILT.clear()
        left = [n for n in cmds.ls("%s*" % PREFIX) or [] if cmds.objExists(n)]
        tagged = [n for n in cmds.ls("*.%s" % TAG, objectsOnly=True) or []]
        for n in (ROOT, LAYER):
            if cmds.objExists(n):
                left.append(n)
        gone = sorted(set(left + tagged), key=lambda x: -x.count("|"))
        for n in gone:
            if cmds.objExists(n):
                try:
                    cmds.delete(n)
                except RuntimeError:
                    pass
    if not keep_targets:
        clear_targets()


def set_hidden(hidden):
    if cmds.objExists(LAYER):
        cmds.setAttr(LAYER + ".visibility", not hidden)


def built_frames():
    return sorted(_BUILT)
