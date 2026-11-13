"""
Clothes switch (5.6.29): Visibility_ctrl.Clothes - Full / Hidden - for the heavy clothes meshes (the Hare's Hood,
Shirt, Pants, bandages). Hidden: the meshes aren't drawn and their deformers (skin, delta mush...) are switched
off, so Maya doesn't work them out - the rig moves faster while blocking. Full: everything as it was.
5.6.30: and a Full / Hidden per piece (Hood_Geo, Shirt_Geo, Pants_Geo, Bandages_Geo...): a piece is hidden when its
own switch or Clothes is on Hidden. (The belt stays out: it isn't in the names.)

Only deformers that move nothing but the switched meshes are switched off (a head squash or a lattice shared
with the body is left alone). Nothing moves when it's made: at Full the meshes and deformers are as before.

    from gus_rigtool.core import clothes_switch as CS
    CS.make(CS.suggest())                    # on Visibility_ctrl (Build > Visibility switches first)
    with CS.hidden(): ...                    # for timing: hidden for a moment, then back
"""

import contextlib
import json
import re

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

ATTR = "Clothes"                         # the switch: 0 Full, 1 Hidden
ENUM = "Full:Hidden"
DATA = "gusClothesSwitch"                # on the switch control: what it drives (JSON)
PARTS = (("Hood", r"hood"), ("Shirt", r"shirt"), ("Pants", r"pants|trouser"), ("Bandages", r"bandage"),
         ("Skirt", r"skirt"), ("Jacket", r"jacket|coat|cloak"), ("Dress", r"dress"))      # 5.6.30: bandages too
PATTERN = "|".join(rx for _p, rx in PARTS)
PART_SUFFIX = "_Geo"                     # Hood_Geo... (not "Hood": that's the controls' switch per part)


def part_of(mesh):
    """The piece a mesh belongs to (Hood, Shirt, Pants, Bandages...), from its name; "Other" when none fits."""
    short = _short(mesh)
    for part, rx in PARTS:
        if re.search(rx, short, re.IGNORECASE):
            return part
    return "Other"


def _switch_control():
    from gus_rigtool.core import vis_switch
    return vis_switch.find()


def _short(n):
    return naming.short_name(n).split(":")[-1]


def _transform(m):
    if cmds.nodeType(m) == "mesh":
        return cmds.listRelatives(m, parent=True, fullPath=True)[0]
    return (cmds.ls(m, long=True) or [m])[0]


def _shapes(t):
    return cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True, noIntermediate=True) or []


def _all_shapes(t):
    return set(cmds.listRelatives(t, shapes=True, type="mesh", fullPath=True) or [])


def _deformers(t):
    out = []
    for s in _shapes(t):
        for h in cmds.listHistory(s, pruneDagObjects=True) or []:
            if cmds.objectType(h, isAType="geometryFilter") and h not in out and cmds.nodeType(h) != "tweak":
                out.append(h)
    return out


def _deforms(dfm):
    try:
        return [cmds.ls(g, long=True)[0] for g in cmds.deformer(dfm, query=True, geometry=True) or []
                if cmds.ls(g, long=True)]
    except (RuntimeError, ValueError, TypeError):
        return None


def suggest():
    """Skinned meshes whose name says clothes (hood, shirt, pants...)."""
    out = []
    for s in cmds.ls(type="mesh", noIntermediate=True, long=True) or []:
        t = _transform(s)
        if t in out or not re.search(PATTERN, _short(t), re.IGNORECASE):
            continue
        if any(cmds.nodeType(h) == "skinCluster" for h in cmds.listHistory(s, pruneDagObjects=True) or []):
            out.append(t)
    return out


def plan(meshes):
    """(meshes, [(deformer, why it's left on)], deformers switched off) - what make() would drive."""
    meshes = [_transform(m) for m in meshes]
    mine = set()
    for t in meshes:
        mine |= _all_shapes(t)
    switched, kept = [], []
    for t in meshes:
        for d in _deformers(t):
            if d in switched or any(d == k for k, _w in kept):
                continue
            geos = _deforms(d)
            if geos is None:
                kept.append((d, "Maya can't say what it deforms"))
            elif any(g not in mine for g in geos):
                kept.append((d, "it deforms other meshes too"))
            elif cmds.listConnections(d + ".nodeState", source=True, destination=False):
                kept.append((d, "something else switches it already"))
            else:
                switched.append(d)
    return meshes, kept, switched


def _by_part(meshes):
    out = {}
    for m in meshes:
        out.setdefault(part_of(m), []).append(m)
    return out


def describe(meshes):
    meshes, kept, switched = plan(meshes)
    lines = ["Visibility_ctrl.Clothes (Full / Hidden) and one per piece:"]
    for part, ms in sorted(_by_part(meshes).items()):
        lines.append("  %s%s: %s" % (part, PART_SUFFIX, ", ".join(_short(m) for m in ms)))
    lines.append("  switched off with them: %s" % (", ".join(_short(d) for d in switched) or "none"))
    lines.append("  (not in it: anything not listed - select the meshes to choose them yourself)")
    if kept:
        lines.append("  left on: %s" % "; ".join("%s (%s)" % (_short(d), w) for d, w in kept))
    return lines


def read(sw=None):
    sw = sw or _switch_control()
    if not sw or not cmds.attributeQuery(DATA, node=sw, exists=True):
        return {}
    try:
        return json.loads(cmds.getAttr(sw + "." + DATA) or "{}")
    except ValueError:
        return {}


def make(meshes, sw=None):
    """The switch on Visibility_ctrl (or sw), driving the meshes' visibility and their own deformers. Made again
    when it's there (the old one goes first). Returns read()."""
    sw = sw or _switch_control()
    if not sw:
        raise RuntimeError("make the visibility switches first (Build > Visibility switches).")
    if not meshes:
        raise RuntimeError("select the clothes meshes (or none: Hood, Shirt, Pants... are found by name).")
    meshes, _kept, switched = plan(meshes)
    with utils.undo_chunk("gusrigClothesSwitch"):
        if read(sw):
            remove(sw)
        if not cmds.attributeQuery(ATTR, node=sw, exists=True):
            cmds.addAttr(sw, longName=ATTR, attributeType="enum", enumName=ENUM, defaultValue=0, keyable=True)
        shown, busy, nodes, parts = [], [], [], {}
        for part, ms in sorted(_by_part(meshes).items()):
            attr = part + PART_SUFFIX
            if not cmds.attributeQuery(attr, node=sw, exists=True):
                cmds.addAttr(sw, longName=attr, attributeType="enum", enumName=ENUM, defaultValue=0, keyable=True)
            # hidden when Clothes or this piece is on Hidden: (Clothes + piece) > 0
            pma = cmds.createNode("plusMinusAverage", name="Clothes_%s_pma" % part, skipSelect=True)
            cond = cmds.createNode("condition", name="Clothes_%s_hidden" % part, skipSelect=True)
            rev = cmds.createNode("reverse", name="Clothes_%s_rev" % part, skipSelect=True)
            cmds.connectAttr(sw + "." + ATTR, pma + ".input1D[0]")
            cmds.connectAttr(sw + "." + attr, pma + ".input1D[1]")
            cmds.connectAttr(pma + ".output1D", cond + ".firstTerm")
            cmds.setAttr(cond + ".operation", 2)                      # greater than 0
            cmds.setAttr(cond + ".colorIfTrueR", 1)
            cmds.setAttr(cond + ".colorIfFalseR", 0)
            cmds.connectAttr(cond + ".outColorR", rev + ".inputX")
            nodes += [pma, cond, rev]
            mine = set()
            for t in ms:
                mine |= _all_shapes(t)
                plug = t + ".visibility"
                if cmds.listConnections(plug, source=True, destination=False) or not cmds.getAttr(plug, settable=True):
                    busy.append(t)
                    continue
                cmds.connectAttr(rev + ".outputX", plug, force=True)
                shown.append(t)
            dfm = [d for d in switched if set(_deforms(d) or []) <= mine]
            for d in dfm:
                cmds.connectAttr(cond + ".outColorR", d + ".nodeState", force=True)
            parts[part] = {"attr": attr, "meshes": [t for t in ms if t in shown], "deformers": dfm}
        done = set(d for p in parts.values() for d in p["deformers"])
        for d in switched:                             # one deformer across two pieces: the master alone
            if d not in done:
                cmds.connectAttr(sw + "." + ATTR, d + ".nodeState", force=True)
        data = {"meshes": shown, "deformers": switched, "nodes": nodes, "parts": parts, "skipped": busy}
        if not cmds.attributeQuery(DATA, node=sw, exists=True):
            cmds.addAttr(sw, longName=DATA, dataType="string")
        cmds.setAttr(sw + "." + DATA, json.dumps(data), type="string")
    return data


def remove(sw=None):
    """The switch goes: meshes shown, deformers on, the attribute deleted. Returns True when there was one."""
    sw = sw or _switch_control()
    data = read(sw)
    if not data and not (sw and cmds.attributeQuery(ATTR, node=sw, exists=True)):
        return False
    with utils.undo_chunk("gusrigClothesSwitchRemove"):
        for t in data.get("meshes", []):
            if cmds.objExists(t):
                for src in cmds.listConnections(t + ".visibility", source=True, destination=False, plugs=True) or []:
                    cmds.disconnectAttr(src, t + ".visibility")
                cmds.setAttr(t + ".visibility", 1)
        for d in data.get("deformers", []):
            if cmds.objExists(d):
                for src in cmds.listConnections(d + ".nodeState", source=True, destination=False, plugs=True) or []:
                    cmds.disconnectAttr(src, d + ".nodeState")
                cmds.setAttr(d + ".nodeState", 0)
        gone = [n for n in data.get("nodes", []) + [data.get("reverse")] if n and cmds.objExists(n)]
        if gone:
            cmds.delete(gone)
        attrs = [ATTR, DATA] + [p.get("attr") for p in data.get("parts", {}).values()]
        for a in attrs:
            if a and cmds.attributeQuery(a, node=sw, exists=True):
                cmds.deleteAttr(sw + "." + a)
    return True


@contextlib.contextmanager
def hidden(sw=None):
    """For timing: the clothes hidden for a moment, then the switch as it was. Nothing when there's no switch."""
    sw = sw or _switch_control()
    plug = sw + "." + ATTR if sw and cmds.attributeQuery(ATTR, node=sw, exists=True) else None
    was = cmds.getAttr(plug) if plug else None
    try:
        if plug and cmds.getAttr(plug, settable=True):
            cmds.setAttr(plug, 1)
        yield bool(plug)
    finally:
        if plug and was is not None:
            cmds.setAttr(plug, was)
