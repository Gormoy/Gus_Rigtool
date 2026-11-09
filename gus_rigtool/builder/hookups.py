"""
Keep your own work through a rebuild: things outside a module that hang from it, or that it feeds,
are written down before the module is taken down and put back on the new nodes (same names) after
it is built again.

  children     your nodes parented under the module's joints / controls (a prop under the wrist): they
               wait in the world (same place) and go back under the node with the same name
  connections  anything between the module's nodes and yours, both ways: constraints you made that
               use its controls as targets, set driven keys driven by its attributes, twin links,
               nodes you connected to it...

Connections between builder modules, skins (kept by Keep the skin) and sets are left to the builder.
What is waiting is stored on the module's guide group (gusHookups), so Back to guides + Build works too.
"""

import json

import maya.cmds as cmds

from gus_rigtool.builder import controls
from gus_rigtool.core import utils
from gus_rigtool.core import nodes as _nodes

ATTR = "gusHookups"
SKIP_TYPES = ("skinCluster", "dagPose", "objectSet", "displayLayer", "nodeGraphEditorInfo", "hyperLayout",
              "defaultRenderUtilityList", "renderLayer", "shadingEngine", "groupId", "groupParts", "tweak")


REMAKE = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint")
TRS = ("translate", "rotate", "scale")
CHANNELS = ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ")


def remake_constraint(con, driven, rest):
    """Your constraint on a rebuilt node, made again with maintain offset at the node's new rest: same kind,
    targets, weights (and what drives them - space switches), interpolation and free axes, same name.
    rest: the node's channel values as built (before the old constraint moved it)."""
    kind = cmds.nodeType(con)
    fn = getattr(cmds, kind)
    from gus_rigtool.core import constraints as cons
    targets = [t for t in cons.targets_of(con) if cmds.objExists(t)]
    if not targets:
        raise RuntimeError("its targets are gone")
    aliases = fn(con, query=True, weightAliasList=True) or []
    weights = []
    for a in aliases:
        plug = con + "." + a
        src = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
        weights.append((cmds.getAttr(plug), src[0] if src else None))
    interp = cmds.getAttr(con + ".interpType") if cmds.attributeQuery("interpType", node=con, exists=True) else None
    used = set()
    pairs = cmds.listConnections(con, source=False, destination=True, plugs=True, connections=True) or []
    for _s, d in zip(pairs[0::2], pairs[1::2]):
        if _short(d.split(".")[0]) == _short(driven):
            a = d.split(".", 1)[1]
            used.update([a + x for x in "XYZ"] if a in TRS else [a])
    name = _short(con)
    cmds.delete(con)
    for a, v in rest.items():                       # back to how the build made it
        try:
            if cmds.getAttr(driven + "." + a, settable=True):
                cmds.setAttr(driven + "." + a, v)
        except RuntimeError:
            pass
    free = lambda base: [x.lower() for x in "XYZ" if (base + x) not in used]
    kw = {"maintainOffset": True}
    if kind == "parentConstraint":
        if used and len(free("translate")) < 3 and free("translate"):
            kw["skipTranslate"] = free("translate")
        if used and len(free("rotate")) < 3 and free("rotate"):
            kw["skipRotate"] = free("rotate")
        if used and len(free("translate")) == 3:
            kw["skipTranslate"] = ["x", "y", "z"]
        if used and len(free("rotate")) == 3:
            kw["skipRotate"] = ["x", "y", "z"]
    else:
        base = {"pointConstraint": "translate", "orientConstraint": "rotate", "scaleConstraint": "scale"}[kind]
        if used and free(base) and len(free(base)) < 3:
            kw["skip"] = free(base)
    new = fn(targets, driven, **kw)[0]
    if interp is not None:
        try:
            cmds.setAttr(new + ".interpType", interp)
        except RuntimeError:
            pass
    for a, (value, src) in zip(fn(new, query=True, weightAliasList=True) or [], weights):
        try:
            if src:
                cmds.connectAttr(src, new + "." + a, force=True)
            else:
                cmds.setAttr(new + "." + a, value)
        except RuntimeError:
            pass
    if name and _short(new) != name and not cmds.objExists(name):
        cmds.rename(new, name)
    return True


_short = _nodes.short


def _uuid(n):
    found = cmds.ls(n, uuid=True) or []
    return found[0] if found else None


def capture(created, builder):
    """created: uuids of the module's nodes; builder: uuids of every builder-made node (all modules).
    Returns the record (children are moved to the world now so the delete doesn't take them)."""
    nodes = [n for n in (utils.ls(created, long=True) or []) if cmds.objExists(n)]
    mine = set(created)
    rec = {"children": [], "out": [], "in": []}
    for n in nodes:
        if cmds.nodeType(n) in SKIP_TYPES:
            continue
        name = _short(n)
        for kid in cmds.listRelatives(n, children=True, type="transform", fullPath=True) or []:
            ku = _uuid(kid)
            if ku and ku not in mine and ku not in builder:
                rec["children"].append({"uuid": ku, "parent": name})
        pairs = cmds.listConnections(n, source=False, destination=True, plugs=True, connections=True,
                                     skipConversionNodes=True) or []
        for src, dst in zip(pairs[0::2], pairs[1::2]):
            dn = dst.split(".")[0]
            du = _uuid(dn)
            if not du or du in mine or du in builder or cmds.nodeType(dn) in SKIP_TYPES:
                continue
            rec["out"].append({"src": name + "." + src.split(".", 1)[1], "dst_uuid": du,
                               "dst_attr": dst.split(".", 1)[1]})
        pairs = cmds.listConnections(n, source=True, destination=False, plugs=True, connections=True,
                                     skipConversionNodes=True) or []
        for dst, src in zip(pairs[0::2], pairs[1::2]):
            sn = src.split(".")[0]
            su = _uuid(sn)
            if not su or su in mine or su in builder or cmds.nodeType(sn) in SKIP_TYPES:
                continue
            rec["in"].append({"src_uuid": su, "src_attr": src.split(".", 1)[1],
                              "dst": name + "." + dst.split(".", 1)[1]})
    for c in rec["children"]:                       # out of the way of the delete, same place in the world
        kid = cmds.ls(c["uuid"], long=True) or []
        if kid:
            try:
                cmds.parent(kid[0], world=True)
            except RuntimeError:
                pass
    return rec


def save(group, rec):
    old = load(group)
    for k in ("children", "out", "in"):
        old[k] = old.get(k, []) + rec.get(k, [])
    controls.add_string(group, ATTR, json.dumps(old))


def load(group):
    try:
        return json.loads(controls.get_string(group, ATTR) or "{}") or {}
    except ValueError:
        return {}


def _one(name):
    found = cmds.ls(name, long=True) or []
    return found[0] if len(found) == 1 else None


def restore(group):
    """Put the waiting hook-ups back on the rebuilt nodes. Returns (done, failed) counts and notes."""
    rec = load(group)
    if not rec:
        return 0, []
    done, notes = 0, []
    for c in rec.get("children", []):
        kid, parent = (cmds.ls(c["uuid"], long=True) or [None])[0], _one(c["parent"])
        if not kid:
            continue
        if not parent:
            notes.append("%s: '%s' is gone - it stays in the world" % (_short(kid), c["parent"]))
            continue
        try:
            cmds.parent(kid, parent)
            done += 1
        except RuntimeError as e:
            notes.append("%s: %s" % (_short(kid), e))
    for o in rec.get("out", []):
        node, attr = o["src"].split(".", 1)
        src, dst = _one(node), (cmds.ls(o["dst_uuid"], long=True) or [None])[0]
        if not dst:
            continue
        if not src:
            notes.append("%s -> %s: '%s' is gone" % (o["src"], _short(dst) + "." + o["dst_attr"], node))
            continue
        try:
            cmds.connectAttr(src + "." + attr, dst + "." + o["dst_attr"], force=True)
            done += 1
        except RuntimeError as e:
            notes.append("%s -> %s.%s: %s" % (o["src"], _short(dst), o["dst_attr"], str(e).strip()))
    remake, rest = {}, {}
    for i in rec.get("in", []):                   # your constraints driving a rebuilt node: re-made after
        node, attr = i["dst"].split(".", 1)
        dst, src = _one(node), (cmds.ls(i["src_uuid"], long=True) or [None])[0]
        if dst and src and cmds.nodeType(src) in REMAKE and attr.split(".")[0].rstrip("XYZ") in TRS:
            remake.setdefault(src, dst)
            if dst not in rest:
                rest[dst] = {a: cmds.getAttr(dst + "." + a) for a in CHANNELS if cmds.objExists(dst + "." + a)}
    for i in rec.get("in", []):
        node, attr = i["dst"].split(".", 1)
        dst, src = _one(node), (cmds.ls(i["src_uuid"], long=True) or [None])[0]
        if not src:
            continue
        if not dst:
            notes.append("%s.%s -> %s: '%s' is gone" % (_short(src), i["src_attr"], i["dst"], node))
            continue
        try:
            if not cmds.attributeQuery(attr.split(".")[0].split("[")[0], node=dst, exists=True):
                notes.append("%s: '%s' has no attribute '%s' any more" % (i["dst"], node, attr))
                continue
            cmds.connectAttr(src + "." + i["src_attr"], dst + "." + attr, force=True)
            done += 1
        except RuntimeError as e:
            notes.append("%s.%s -> %s: %s" % (_short(src), i["src_attr"], i["dst"], str(e).strip()))
    for con, dst in remake.items():
        try:
            if remake_constraint(con, dst, rest.get(dst, {})):
                notes.append("RE-MADE:%s: constraint re-made at the new spot (fresh offset)" % _short(dst))
        except RuntimeError as e:
            notes.append("%s: constraint not re-made (%s) - it keeps its old offset" % (_short(dst), str(e).strip()))
    controls.add_string(group, ATTR, "")
    return done, notes


def report(module_id, done, notes):
    if done:
        utils.info("Build", "%s: %d of your hook-up(s) put back (children, constraints, driven keys...)."
                   % (module_id, done))
    remade = [n[len("RE-MADE:"):] for n in notes if n.startswith("RE-MADE:")]
    for n in remade:
        utils.info("Build", "%s: %s" % (module_id, n))
    notes = [n for n in notes if not n.startswith("RE-MADE:")]
    for n in notes[:8]:
        utils.warn("Build", "%s: not put back - %s" % (module_id, n))
