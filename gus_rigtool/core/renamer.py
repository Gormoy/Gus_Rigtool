"""
Rename many nodes: new base name with numbers, search / replace, prefix / suffix, swap the side,
or fix names to your naming (side token + part + type suffix, from Build > Naming).
plan() makes the list (old -> new) for the preview; apply() renames, children first (by uuid).
"""

import re

import maya.cmds as cmds

from gus_rigtool.core import naming, sides

KIND_SUFFIX = (("joint", "jnt"), ("ikHandle", "ik"), ("nurbsCurve", "ctrl"), ("mesh", "geo"),
               ("nurbsSurface", "srf"), ("locator", "loc"), ("follicle", "fol"))


def nodes_from(selection, hierarchy=False):
    out = []
    for n in selection:
        if n not in out:
            out.append(n)
        if hierarchy:
            for k in reversed(cmds.listRelatives(n, allDescendents=True, type="transform", fullPath=True) or []):
                if k not in out:
                    out.append(k)
    return out


def kind_of(node):
    if cmds.nodeType(node) in ("joint", "ikHandle"):
        return dict(KIND_SUFFIX)[cmds.nodeType(node)]
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
    for s in shapes:
        t = cmds.nodeType(s)
        for nt, k in KIND_SUFFIX:
            if t == nt:
                return k
    return "grp"


def fixed_name(node, name=None):
    """The name your naming would give it: side token + part + type suffix (from name, or the node's)."""
    from gus_rigtool.builder import names
    pairs = sides.default_pairs()
    ns, base = naming.split_namespace(name or node)
    side = naming.side_of(base, pairs) if sides.has_side(base, pairs) else sides.side_of_node(node, pairs)
    part = naming.label_of(base, pairs)
    for _nt, k in KIND_SUFFIX + (("", "grp"), ("", "offset")):     # 'arm_ctrl_ctrl' -> 'arm'
        s = names.settings()["suffixes"].get(k, "_" + k)
        if part.endswith(s) and len(part) > len(s):
            part = part[:-len(s)]
    return ns + names.make(side, part.strip("_") or base, kind_of(node))


def _number(i, pad):
    return str(i).zfill(int(pad))


def new_name(node, index, o):
    ns, base = naming.split_namespace(node)
    name = base
    num = _number(o.get("start", 1) + index * o.get("step", 1), o.get("pad", 2))
    if o.get("base"):
        b = o["base"]
        name = re.sub("#+", lambda m: num.zfill(len(m.group(0))), b) if "#" in b else "%s_%s" % (b, num)
    if o.get("search"):
        name = name.replace(o["search"], o.get("replace", ""))
    name = o.get("prefix", "") + name + o.get("suffix", "")
    if o.get("swap"):
        name = naming.mirror_name(name, sides.default_pairs()) or name
    if o.get("fix"):
        name = naming.split_namespace(fixed_name(node, name))[1]
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if name and name[0].isdigit():
        name = "_" + name
    return ns + name


def plan(nodes, o):
    """[(long name, old short, new short)] - new == old when nothing changes."""
    out = []
    for i, n in enumerate(nodes):
        old = n.split("|")[-1]
        out.append((n, old, new_name(n, i, o)))
    return out


def clashes(rows):
    """New names used twice in the plan."""
    seen, dup = set(), set()
    for _n, old, new in rows:
        if new != old:
            if new in seen:
                dup.add(new)
            seen.add(new)
    return sorted(dup)


def apply(rows, shapes=False):
    """Rename (children first so the paths stay right). Returns [(old, got)] - got may differ from what was
    asked when Maya had to add a number."""
    todo = [(cmds.ls(n, uuid=True)[0], old, new) for n, old, new in rows if new != old]
    todo.sort(key=lambda r: -len((cmds.ls(r[0], long=True) or [""])[0]))
    done = []
    for uid, old, new in todo:
        node = (cmds.ls(uid, long=True) or [None])[0]
        if not node:
            continue
        got = cmds.rename(node, new.split(":")[-1] if ":" in new and ":" not in old else new)
        if shapes:
            node = cmds.ls(uid, long=True)[0]
            for s in cmds.listRelatives(node, shapes=True, fullPath=True) or []:
                if not cmds.getAttr(s + ".intermediateObject"):
                    cmds.rename(s, got.split("|")[-1] + "Shape")
        done.append((old, got.split("|")[-1]))
    return done
