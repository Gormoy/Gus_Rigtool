"""
(noPyMEL copy) What this copy adds to the onion skin:
- meshes_for(selection): a control stands for its whole character (the meshes in its namespace, or under its top
  group); a group for the meshes inside it; a mesh for itself. So selecting controls and pressing + just works.
- character_keys(onion objects): every key of those characters' own animation, sorted - for the past / next key
  ghosts, so nothing needs to stay selected and several characters work at once.
"""

import maya.cmds as cmds

CURVE_TYPES = ["animCurveTL", "animCurveTA", "animCurveTU"]
_CACHE = {"scopes": None, "count": -1, "curves": []}


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
            sc = scope_of(t)
            if sc[0] == "ns":
                shapes = cmds.ls(sc[1] + ":*", type="mesh", long=True, recursive=True) or []
            else:
                shapes = cmds.listRelatives(sc[1], allDescendents=True, type="mesh", fullPath=True) or []
            found = _visible_mesh_transforms(shapes)
        for m in found:
            if m not in out:
                out.append(m)
    return out


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
    if _CACHE["scopes"] != key or _CACHE["count"] != len(all_curves):
        _CACHE["scopes"], _CACHE["count"] = key, len(all_curves)
        _CACHE["curves"] = [c for c in all_curves if any(in_scope(d, s) for d in _driven(c) for s in scopes)]
    return _CACHE["curves"]


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


def character_keys(object_names, main_only=False):
    """Every key time of the characters these objects belong to, sorted ([] when none). main_only: a frame counts
    only where some curve has a main key there (breakdowns skipped - check your extremes like a 2D key pass)."""
    scopes = []
    for n in object_names or []:
        ln = _long(n) or n
        sc = scope_of(ln)
        if sc not in scopes:
            scopes.append(sc)
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


def around(keys, now, count=4):
    """(past keys, nearest LAST; next keys, nearest first) - the order the onion skin uses."""
    past = [k for k in keys if k < now - 1e-6][-count:]
    nxt = [k for k in keys if k > now + 1e-6][:count]
    return past, nxt
