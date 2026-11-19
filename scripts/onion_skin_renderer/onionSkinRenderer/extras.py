"""
(noPyMEL copy) What this copy adds to the onion skin:
- meshes_for(selection): a control stands for its whole character (the meshes in its namespace, or under its top
  group); a group for the meshes inside it; a mesh for itself. So selecting controls and pressing + just works.
- character_keys(onion objects): every key of those characters' own animation, sorted - for the past / next key
  ghosts, so nothing needs to stay selected and several characters work at once.
"""

import maya.cmds as cmds

CURVE_TYPES = ["animCurveTL", "animCurveTA", "animCurveTU"]
_CACHE = {}                 # characters (scopes) -> (how many curves the scene had, their curves)


def _long(n):
    got = cmds.ls(n, long=True)
    return got[0] if got else None


def scope_of(node):
    """('ns', namespace) for a referenced character, else ('root', its top group)."""
    short = node.split("|")[-1]
    if ":" in short:
        return ("ns", short.split(":")[0])
    return ("root", "|" + node.lstrip("|").split("|")[0])


def in_scope(node, scope):
    kind, name = scope
    if kind == "ns":
        return any(p.startswith(name + ":") for p in node.split("|") if p)
    return node == name or node.startswith(name + "|")


def _visible_mesh_transforms(shapes):
    out = []
    if not shapes:                    # ls([]) lists EVERYTHING in Maya - an empty list must stay empty
        return out
    for s in cmds.ls(shapes, long=True, noIntermediate=True, visible=True) or []:
        if cmds.nodeType(s) != "mesh":
            continue
        t = (cmds.listRelatives(s, parent=True, fullPath=True) or [None])[0]
        if t and t not in out:
            out.append(t)
    return out


def meshes_for(nodes):
    """The visible meshes the selection stands for (long names)."""
    out = []
    for n in nodes or []:
        t = _long(n)
        if not t:
            continue
        if cmds.nodeType(t) == "mesh":
            t = cmds.listRelatives(t, parent=True, fullPath=True)[0]
        own = cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or []
        under = [] if own else cmds.listRelatives(t, allDescendents=True, type="mesh", fullPath=True) or []
        if own or under:
            found = _visible_mesh_transforms(own or under)
        else:                                               # a control: its character
            found = scope_meshes(scope_of(t))
            if not found:                                   # meshes in another group (a rig not referenced):
                found = skinned_meshes(scope_of(t))         # the ones its joints deform
        for m in found:
            if m not in out:
                out.append(m)
    return out


def scope_meshes(sc):
    if sc[0] == "ns":
        shapes = cmds.ls(sc[1] + ":*", type="mesh", long=True, recursive=True) or []
    else:
        shapes = cmds.listRelatives(sc[1], allDescendents=True, type="mesh", fullPath=True) or []
    return _visible_mesh_transforms(shapes)


def skinned_meshes(sc):
    """The visible meshes skinned to joints of this character (when the model sits in another group than the rig,
    as in a rigging scene)."""
    shapes = []
    for skin in cmds.ls(type="skinCluster") or []:
        try:
            joints = cmds.skinCluster(skin, query=True, influence=True) or []
        except (RuntimeError, ValueError):
            continue
        if any(in_scope(_long(j) or j, sc) for j in joints):
            shapes += cmds.skinCluster(skin, query=True, geometry=True) or []
    return _visible_mesh_transforms(cmds.ls(shapes, long=True) or []) if shapes else []


def rig_scope_of(node):
    """The character a node belongs to, seen from its rig: a mesh skinned to a rig in another group gets that rig's
    group (its keys are there)."""
    ln = _long(node) or node
    sc = scope_of(ln)
    if sc[0] == "ns":
        return sc
    shapes = [ln] if cmds.nodeType(ln) == "mesh" else cmds.listRelatives(ln, shapes=True, type="mesh",
                                                                         fullPath=True) or []
    try:
        for sh in shapes:
            history = cmds.listHistory(sh, pruneDagObjects=True) or []
            if not history:               # careful: ls([], type=...) would list EVERY skinCluster in the scene
                continue
            for skin in cmds.ls(history, type="skinCluster") or []:
                joints = cmds.skinCluster(skin, query=True, influence=True) or []
                if joints:
                    return scope_of(_long(joints[0]) or joints[0])
    except Exception:
        pass                                     # no skin to follow: the mesh's own group
    return sc


def _driven(curve, depth=3):
    """The DAG nodes a curve animates - through a blend node (pairBlend, animation layers) if there is one."""
    out, todo, first = [], [curve], True
    for _i in range(depth):
        nxt = []
        for n in todo:
            for d in cmds.listConnections(n + ".output" if first else n, source=False, destination=True,
                                          skipConversionNodes=True) or []:
                ln = _long(d) or d
                if cmds.objectType(ln, isAType="dagNode"):
                    if ln not in out:
                        out.append(ln)
                elif d not in nxt:
                    nxt.append(d)
        first = False
        todo = nxt
        if not todo:
            break
    return out


def _curves_for(scopes):
    """The animation curves of these characters (kept until the characters or the scene's curves change)."""
    all_curves = cmds.ls(type=CURVE_TYPES) or []
    key = tuple(sorted(scopes))
    got = _CACHE.get(key)
    if got is None or got[0] != len(all_curves):
        if len(_CACHE) > 20:
            _CACHE.clear()
        got = _CACHE[key] = (len(all_curves), [c for c in all_curves
                                               if any(in_scope(d, s) for d in _driven(c) for s in scopes)])
    return got[1]


def _main_key_times(curve):
    """A curve's key times without its breakdown keys."""
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    try:
        flags = cmds.keyframe(curve, query=True, breakdown=True) or []
    except (RuntimeError, TypeError):
        return times
    if len(flags) == len(times) and all(isinstance(f, (bool, int)) or f in (0.0, 1.0) for f in flags):
        return [t for t, b in zip(times, flags) if not b]
    return [t for t in times if t not in set(flags)]          # some versions answer with the breakdown times


def scope_keys(scopes, main_only=False):
    """Every key time of these characters (scopes from scope_of / rig_scope_of), sorted."""
    scopes = [tuple(s) for s in scopes or []]
    if not scopes:
        return []
    curves = [c for c in _curves_for(scopes) if cmds.objExists(c)]
    if not curves:
        return []
    if main_only:
        times = set()
        for c in curves:
            times.update(_main_key_times(c))
        return sorted(times)
    return sorted(set(cmds.keyframe(curves, query=True, timeChange=True) or []))


def character_keys(object_names, main_only=False):
    """Every key time of the characters these objects belong to, sorted ([] when none). A mesh counts for the rig
    that deforms it (its keys are on the rig's controls). main_only: a frame counts only where some curve has a
    main key there (breakdowns skipped - check your extremes like a 2D key pass)."""
    scopes = []
    for n in object_names or []:
        sc = rig_scope_of(n)
        if sc not in scopes:
            scopes.append(sc)
    return scope_keys(scopes, main_only)


def around(keys, now, count=4):
    """(past keys, nearest LAST; next keys, nearest first) - the order the onion skin uses."""
    past = [k for k in keys if k < now - 1e-6][-count:]
    nxt = [k for k in keys if k > now + 1e-6][:count]
    return past, nxt
