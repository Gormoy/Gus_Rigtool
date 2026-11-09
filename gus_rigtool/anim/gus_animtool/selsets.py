"""
Selection sets: named groups of controls (e.g. 'mouth', 'L hand'), saved in the rig profile - so every scene
with this rig has them, whatever the namespace.
"""

import maya.cmds as cmds

from gus_animtool import anim as A


RIG_SETS = "gus_anim_sets"       # sets the rig carries (Gus_Rigtool: Face > Expressions > Make selection sets)


def _rig_sets(ns=None):
    """{name: set} of the sets inside the character's gus_anim_sets (they travel with the rig file)."""
    ns = (A.current_character() if ns is None else ns) or ""
    holder = (ns + ":" if ns else "") + RIG_SETS
    out = {}
    try:
        if cmds.objExists(holder):
            for st in cmds.sets(holder, query=True) or []:
                if cmds.nodeType(st) == "objectSet":
                    out[A.short(st).split(":")[-1]] = st
    except (RuntimeError, ValueError):
        pass
    return out


def names(ns=None):
    """Your sets (the rig profile) and the rig's own (5.6.12)."""
    return sorted(set((A.profile(ns).get("sets") or {}).keys()) | set(_rig_sets(ns).keys()))


def save(name, nodes=None, ns=None):
    name = (name or "").strip()
    if not name:
        raise RuntimeError("type a name for the set.")
    nodes = nodes if nodes is not None else A.selected()
    if not nodes:
        raise RuntimeError("select the controls first.")
    data = dict(A.profile(ns))
    sets = dict(data.get("sets") or {})
    sets[name] = sorted(set(A.short(n).split(":")[-1] for n in nodes))
    data["sets"] = sets
    A.save_profile(data, ns)
    return len(sets[name])


def remove(name, ns=None):
    data = dict(A.profile(ns))
    sets = dict(data.get("sets") or {})
    if sets.pop(name, None) is None:
        raise RuntimeError("no set named %s." % name)
    data["sets"] = sets
    A.save_profile(data, ns)


def members(name, ns=None):
    ns = (A.current_character() if ns is None else ns) or ""
    found = []
    for n in (A.profile(ns).get("sets") or {}).get(name, []):
        got = A.resolve(n, ns)
        if got:
            found.append(got)
    if not found and name in _rig_sets(ns):
        found = cmds.ls(cmds.sets(_rig_sets(ns)[name], query=True) or [], long=True) or []
    return found


def select(name, add=False, ns=None):
    found = members(name, ns)
    if not found:
        raise RuntimeError("none of the set's controls are in this character.")
    cmds.select(found, add=add, replace=not add)
    return len(found)
