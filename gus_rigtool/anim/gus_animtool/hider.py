"""
Hider: show / hide body parts - their controls, and meshes you add to a part - to focus on one area.

Parts are found from the controls' names and sides (Head & face, Torso, L / R arm, L / R hand, L / R leg,
Tail & ears) and saved in the rig profile, where you can change them (Add selected / Remove selected), so every
scene with this rig has them. Hiding uses the shapes' LOD visibility, so the rig's own visibility switches and
keys are never touched.
"""

import maya.cmds as cmds

from gus_animtool import anim as A

PARTS = ["Head & face", "Torso", "L arm", "R arm", "L hand", "R hand", "L leg", "R leg", "Tail & ears"]
WORDS = {
    "hand": ["thumb", "index", "middle", "ring", "pinky", "finger", "fing", "palm", "cup", "fist"],
    "tail": ["tail", "ear"],
    "head": ["head", "neck", "eye", "brow", "lid", "jaw", "lip", "mouth", "nose", "nostril", "cheek", "tongue",
             "teeth", "chin", "face", "squint", "smile", "pupil", "whisker"],
    "arm": ["arm", "clav", "shoulder", "scap", "humer", "elbow", "radius", "ulna", "wrist", "forearm", "hand"],
    "leg": ["leg", "thigh", "femur", "knee", "tibia", "ankle", "foot", "toe", "ball", "heel", "hip_", "hock"],
}


_bare = A.bare


def part_of(node):
    """The part a control belongs to, by its name and side."""
    low = _bare(node).lower()
    side = A.side_of(node)
    for kind in ("hand", "tail", "head", "arm", "leg"):
        if any(w in low for w in WORDS[kind]):
            if kind in ("hand", "arm", "leg"):
                return "%s %s" % ("R" if side == "R" else "L", kind)
            return "Tail & ears" if kind == "tail" else "Head & face"
    return "Torso"


def auto_parts(ns=None):
    out = {p: {"controls": [], "geo": []} for p in PARTS}
    for n in A.character_controls(ns):
        out[part_of(n)]["controls"].append(_bare(n))
    return out


def parts(ns=None):
    """{part: {'controls': [names], 'geo': [names]}} - the rig profile's, else found from the names."""
    saved = A.profile(ns).get("hider")
    return saved if isinstance(saved, dict) and saved else auto_parts(ns)


def save(data, ns=None):
    _table_cache.clear()                                       # the parts changed
    prof = dict(A.profile(ns))
    prof["hider"] = data
    return A.save_profile(prof, ns)


_table_cache = {}


def _resolve_all(names, ns):
    """Long names of the stored names in this character, in one go (namespace first, then as they are)."""
    if not names:
        return []
    found = cmds.ls([ns + n for n in names], long=True) or [] if ns else []
    if ns and len(found) < len(names):                         # some only exist without the namespace
        have = {A.bare(f) for f in found}
        found += cmds.ls([n for n in names if n not in have], long=True) or []
    elif not ns:
        found = cmds.ls(names, long=True) or []
    return found


def _table(what="controls", ns=None):
    """{part: [shapes]} for one action: worked out once (it reads every control's side), reused for a moment."""
    import time
    ns = (A.current_character() if ns is None else ns) or ""
    key = (ns, what)
    hit = _table_cache.get(key)
    if hit and time.time() - hit[0] < 0.5:
        return hit[1]
    keys = ["controls", "geo"] if what == "both" else [what]
    out = {}
    for part, v in parts(ns).items():
        nodes = _resolve_all([n for k in keys for n in (v.get(k) or [])], ns)
        out[part] = (cmds.listRelatives(nodes, shapes=True, fullPath=True, noIntermediate=True) or []) \
            if nodes else []
    _table_cache[key] = (time.time(), out)
    return out


def _nodes(part, what, ns=None):
    ns = (A.current_character() if ns is None else ns) or ""
    p = parts(ns).get(part) or {}
    keys = ["controls", "geo"] if what == "both" else [what]
    return _resolve_all([n for k in keys for n in (p.get(k) or [])], ns)


def _shapes(nodes):
    return (cmds.listRelatives(nodes, shapes=True, fullPath=True, noIntermediate=True) or []) if nodes else []


def _shown(shapes):
    return not shapes or any(cmds.getAttr(s + ".lodVisibility") for s in shapes)


def _set(shapes, on):
    for s in shapes:
        try:
            cmds.setAttr(s + ".lodVisibility", bool(on))
        except RuntimeError:
            pass
    return len(shapes)


def is_shown(part, what="controls", ns=None):
    return _shown(_table(what, ns).get(part, []))


def show(part, on, what="controls", ns=None):
    """Show (on) or hide a part. Returns how many shapes."""
    return _set(_table(what, ns).get(part, []), on)


def toggle(part, what="controls", ns=None):
    on = not is_shown(part, what, ns)
    show(part, on, what, ns)
    return on


def isolate(part, what="controls", ns=None):
    """Only this part shown (again: everything back)."""
    table = _table(what, ns)
    mine = table.get(part, [])
    others = [p for p, shapes in table.items() if p != part and shapes]          # parts with something in
    if not _shown(mine) or any(_shown(table[p]) for p in others):
        for p in others:
            _set(table[p], False)
        _set(mine, True)
        return True
    return show_all(what, ns) and False


def show_all(what="both", ns=None):
    for shapes in _table(what, ns).values():
        _set(shapes, True)
    return True


def add_selected(part, ns=None):
    """The selected controls (curves) and meshes join this part (and leave the others). Returns how many."""
    sel = A.selected()
    if not sel:
        raise RuntimeError("select controls or meshes to put in %s." % part)
    data = {p: {"controls": list(v.get("controls", [])), "geo": list(v.get("geo", []))}
            for p, v in parts(ns).items()}
    data.setdefault(part, {"controls": [], "geo": []})
    n = 0
    for node in sel:
        kind = "geo" if cmds.listRelatives(node, shapes=True, type="mesh") else "controls"
        name = _bare(node)
        for v in data.values():
            for k in ("controls", "geo"):
                if name in v[k]:
                    v[k].remove(name)
        data[part][kind].append(name)
        n += 1
    save(data, ns)
    return n


def remove_selected(part, ns=None):
    sel = [_bare(n) for n in A.selected()]
    data = {p: {"controls": list(v.get("controls", [])), "geo": list(v.get("geo", []))}
            for p, v in parts(ns).items()}
    gone = 0
    for k in ("controls", "geo"):
        before = len(data.get(part, {}).get(k, []))
        data.setdefault(part, {"controls": [], "geo": []})[k] = [x for x in data[part][k] if x not in sel]
        gone += before - len(data[part][k])
    save(data, ns)
    return gone


def reset(ns=None):
    """Back to the parts found from the names."""
    prof = dict(A.profile(ns))
    prof.pop("hider", None)
    A.save_profile(prof, ns)
    return auto_parts(ns)
