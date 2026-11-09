"""
Organize the Outliner: look at every top-level item, work out what it is, propose where it goes,
move it there when you say so - and put it all back with Restore.

    from gus_rigtool.core import organize
    rows = organize.analyze()          # [{'node', 'dest', 'why', 'kind'}] - nothing moves
    organize.apply(rows)               # one undo; the old place is remembered on each node
    organize.restore()                 # everything back where it was

Destinations: geo, skeleton, controls, rig_nodes (the rig groups, same names as the builder's),
leave (don't touch), delete (empty groups only). Only top-level items move, never things inside
your hierarchies, and nothing moves in the viewport.
"""

import fnmatch

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

TOOL = "Organize"
DESTS = ["geo", "skeleton", "controls", "rig_nodes", "leave", "delete"]
DEST_LABELS = {"geo": "geo_grp", "skeleton": "skeleton_grp", "controls": "controls_grp",
               "rig_nodes": "rig_nodes_grp (hidden)", "leave": "leave where it is", "delete": "delete (empty)"}
FROM_ATTR = "gusOrganizedFrom"          # the parent an item had before Organize ('' = the world)
INHERIT_ATTR = "gusOrganizedInherit"    # its inheritsTransform before (skinned meshes get 0)
DEFAULTS = {
    "prefix": "",                      # e.g. Hare -> Hare_rig_grp (empty: rig_grp, like the builder)
    "names": {"rig": "rig", "geo": "geo", "skeleton": "skeleton", "controls": "controls",
              "rig_nodes": "rig_nodes"},
    "hide_rig_nodes": True,
    "rules": "",                       # one per line: pattern = destination   (e.g. *_proxy = geo)
    "never": "",                       # names never moved (space or comma separated, wildcards ok)
    "ribbons": "controls",             # where _ribbon_grp builds go
    "colors": False,                   # Outliner colour per rig group
    "geo_layer": False,                # a 'geo_layer' display layer set to reference
    "sort": "none",                    # none / name / side : order inside each rig group
}
COLORS = {"geo": (0.55, 0.85, 0.55), "skeleton": (0.95, 0.85, 0.4), "controls": (0.45, 0.75, 1.0),
          "rig_nodes": (0.65, 0.65, 0.65)}
RIG_TYPES = ("ikHandle", "follicle", "locator", "clusterHandle", "nurbsSurface", "ikEffector", "hairSystem",
             "nucleus", "deltaMush", "wire")
SCENE_TYPES = ("camera", "light", "imagePlane", "ambientLight", "directionalLight", "pointLight", "spotLight",
               "areaLight", "volumeLight")


def _short(n):
    return naming.short_name(n)


# ---------------------------------------------------------------------------
# group names
# ---------------------------------------------------------------------------

def group_name(key, o):
    base = o.get("names", {}).get(key, key)
    prefix = (o.get("prefix") or "").strip()
    if key == "rig" and not prefix:
        from gus_rigtool.builder import names
        return names.make("C", "rig", "grp")
    if not prefix:
        from gus_rigtool.builder import names
        return names.make("C", base, "grp")
    return "%s_%s_grp" % (prefix, base)


def managed_groups(o):
    return [group_name(k, o) for k in ("rig", "geo", "skeleton", "controls", "rig_nodes")]


def _ensure_groups(o):
    """The rig group and its four children (existing ones are reused)."""
    def get(name, parent=None):
        found = cmds.ls(name, long=True) or []
        if found:
            return found[0]
        n = cmds.createNode("transform", name=name)
        if parent:
            n = cmds.parent(n, parent)[0]
        return cmds.ls(n, long=True)[0]
    rig = get(group_name("rig", o))
    out = {"rig": rig}
    for k in ("geo", "skeleton", "controls", "rig_nodes"):
        out[k] = get(group_name(k, o), rig)
    if o.get("hide_rig_nodes", True):
        cmds.setAttr(out["rig_nodes"] + ".visibility", 0)
    return out


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def top_level():
    """Transforms (and joints) directly in the world, minus Maya's startup cameras."""
    out = []
    for n in cmds.ls(assemblies=True, long=True) or []:
        shapes = cmds.listRelatives(n, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(s) == "camera" and cmds.camera(s, query=True, startupCamera=True) for s in shapes):
            continue
        out.append(n)
    return out


def _content(node):
    """Counts of what is inside a hierarchy (shape types, joints, controls)."""
    kids = [node] + (cmds.listRelatives(node, allDescendents=True, fullPath=True) or [])
    c = {"mesh": 0, "ctrl": 0, "joint": 0, "rig": 0, "scene": 0, "curve_other": 0, "transforms": 0,
         "skinned": 0, "driven_mesh": 0}
    for k in kids:
        t = cmds.nodeType(k)
        if t == "joint":
            c["joint"] += 1
        elif t == "transform":
            c["transforms"] += 1
        elif t == "mesh":
            if cmds.getAttr(k + ".intermediateObject"):
                continue
            c["mesh"] += 1
            hist = cmds.listHistory(k, pruneDagObjects=True) or []
            if utils.ls(hist, type="skinCluster"):
                c["skinned"] += 1
            elif utils.ls(hist, type="geometryFilter"):
                c["driven_mesh"] += 1
        elif t == "nurbsCurve":
            if cmds.getAttr(k + ".intermediateObject"):
                continue
            parent = _short(cmds.listRelatives(k, parent=True, fullPath=True)[0])
            used_by_ik = cmds.listConnections(k, type="ikHandle") or []
            if parent.endswith(("_crv", "_curve", "Curve")) or used_by_ik:
                c["curve_other"] += 1
            else:
                c["ctrl"] += 1
        elif t in RIG_TYPES:
            c["rig"] += 1
        elif t in SCENE_TYPES:
            c["scene"] += 1
    return c


def _driven(node):
    """True when a top-level item follows something (constraint / connection on its transform)."""
    for a in ("translate", "rotate", "translateX", "rotateX", "worldMatrix"):
        if cmds.listConnections(node + "." + a, source=True, destination=False, skipConversionNodes=True):
            return True
    return bool(cmds.listConnections(node, source=True, destination=False, type="constraint"))


def _rule_dest(name, o):
    for line in (o.get("rules") or "").splitlines():
        if "=" not in line:
            continue
        pat, dest = [x.strip() for x in line.split("=", 1)]
        if pat and dest in DESTS and fnmatch.fnmatch(name, pat):
            return dest, "your rule '%s'" % pat
    return None


def _never(name, o):
    pats = [p for p in (o.get("never") or "").replace(",", " ").split() if p]
    return any(fnmatch.fnmatch(name, p) for p in pats)


def classify(node, o):
    """(destination, why, kind) for one top-level item."""
    name = _short(node)
    if _never(name, o):
        return "leave", "in your 'never move' list", "kept"
    if name in managed_groups(o):
        return "leave", "a rig group itself", "rig group"
    if name in ("guides_grp", "legacy_grp") or cmds.objExists(node + ".gusModule"):
        return "leave", "a Gus_Rigtool group (guides / backup)", "tool"
    rule = _rule_dest(name, o)
    if rule:
        return rule[0], rule[1], "rule"
    if cmds.objExists(node + ".rrbGroup"):
        return o.get("ribbons", "controls"), "a ribbon build (_ribbon_grp)", "ribbon"
    c = _content(node)
    if c["scene"] and not (c["mesh"] or c["ctrl"] or c["joint"]):
        return "leave", "camera / light", "scene"
    if not (c["mesh"] or c["ctrl"] or c["joint"] or c["rig"] or c["curve_other"] or c["scene"]):
        if c["transforms"] <= 1 and not cmds.listConnections(node):
            return "leave", "empty group (you can pick delete)", "empty"
        return "leave", "only empty groups inside - not sure what it is", "unknown"
    if c["ctrl"]:
        extra = " (also %d mesh(es))" % c["mesh"] if c["mesh"] else ""
        return "controls", "%d control(s) inside%s" % (c["ctrl"], extra), "controls"
    if c["joint"] and not c["mesh"]:
        return "skeleton", "%d joint(s)" % c["joint"], "skeleton"
    if c["mesh"]:
        rigged = c["skinned"] or c["driven_mesh"] or _driven(node)
        why = "%d mesh(es)%s" % (c["mesh"], ", %d skinned" % c["skinned"] if c["skinned"] else "")
        if not rigged:
            why += " - NOT rigged yet (nothing deforms or moves it)"
        return "geo", why, "geo"
    if c["rig"] or c["curve_other"]:
        why = "rig machinery (%d IK / follicle / locator / helper node(s))" % (c["rig"] + c["curve_other"])
        return "rig_nodes", why, "rig"
    return "leave", "not sure what it is", "unknown"


def analyze(o=None):
    """The plan: [{'node', 'name', 'dest', 'why', 'kind'}] for every top-level item. Nothing moves."""
    o = dict(DEFAULTS, **(o or {}))
    rows = []
    for n in top_level():
        dest, why, kind = classify(n, o)
        rows.append({"node": n, "name": _short(n), "dest": dest, "why": why, "kind": kind})
    order = {"controls": 0, "skeleton": 1, "geo": 2, "rig_nodes": 3, "leave": 4, "delete": 5}
    rows.sort(key=lambda r: (order.get(r["dest"], 9), r["name"].lower()))
    return rows


def plan_text(rows, o=None):
    o = dict(DEFAULTS, **(o or {}))
    L = []
    for r in rows:
        where = DEST_LABELS[r["dest"]] if r["dest"] in ("leave", "delete") else group_name(r["dest"], o)
        L.append("%-28s -> %-22s  %s" % (r["name"][:28], where, r["why"]))
    return "\n".join(L)


# ---------------------------------------------------------------------------
# apply / restore
# ---------------------------------------------------------------------------

def _remember(node, inherit):
    if not cmds.attributeQuery(FROM_ATTR, node=node, exists=True):
        cmds.addAttr(node, longName=FROM_ATTR, dataType="string")
        cmds.setAttr(node + "." + FROM_ATTR, "", type="string")        # it came from the world
        cmds.addAttr(node, longName=INHERIT_ATTR, attributeType="bool")
        cmds.setAttr(node + "." + INHERIT_ATTR, bool(inherit))


def _skinned(node):
    for s in [node] + (cmds.listRelatives(node, allDescendents=True, fullPath=True, type="mesh") or []):
        if cmds.nodeType(s) == "mesh" and utils.ls(cmds.listHistory(s, pruneDagObjects=True) or [],
                                                   type="skinCluster"):
            return True
    return False


def _side(name):
    from gus_rigtool.core import sides
    return {"L": 1, "C": 0, "R": 2}.get(naming.side_of(name, sides.default_pairs()) or "C", 0)


def apply(rows, o=None):
    """Move the items as the rows say (one undo). Returns a list of what happened."""
    o = dict(DEFAULTS, **(o or {}))
    notes = []
    todo = [r for r in rows if r["dest"] not in ("leave",) and cmds.objExists(r["node"])]
    if not todo:
        return ["nothing to move."]
    with utils.undo_chunk("gusrigOrganize"):
        groups = _ensure_groups(o) if any(r["dest"] != "delete" for r in todo) else {}
        for r in todo:
            node = r["node"]
            if r["dest"] == "delete":
                if r["kind"] != "empty":
                    notes.append("not deleted (not empty): %s" % r["name"])
                    continue
                cmds.delete(node)
                notes.append("deleted empty group %s" % r["name"])
                continue
            target = groups[r["dest"]]
            if node == target or target.startswith(node + "|"):
                continue
            inherit = cmds.getAttr(node + ".inheritsTransform")
            _remember(node, inherit)
            moved = cmds.ls(cmds.parent(node, target)[0], long=True)[0]
            if _skinned(moved) and cmds.getAttr(moved + ".inheritsTransform"):
                cmds.setAttr(moved + ".inheritsTransform", 0)          # a skinned mesh must never move twice
                notes.append("%s -> %s (inherits transform off: it's skinned)" % (r["name"], _short(target)))
            else:
                notes.append("%s -> %s" % (r["name"], _short(target)))
        if groups and o.get("colors"):
            for k, rgb in COLORS.items():
                g = groups[k]
                try:
                    cmds.setAttr(g + ".useOutlinerColor", 1)
                    cmds.setAttr(g + ".outlinerColor", *rgb)
                except RuntimeError:
                    pass
        if groups and o.get("geo_layer"):
            layer = "geo_layer"
            if not cmds.objExists(layer):
                layer = cmds.createDisplayLayer(name=layer, empty=True)
            cmds.editDisplayLayerMembers(layer, groups["geo"], noRecurse=True)
            cmds.setAttr(layer + ".displayType", 2)
            notes.append("geo_grp in display layer geo_layer (reference: not selectable)")
        if groups and o.get("sort", "none") != "none":
            for k in ("geo", "skeleton", "controls", "rig_nodes"):
                kids = cmds.listRelatives(groups[k], children=True, fullPath=True) or []
                key = (lambda x: _short(x).lower()) if o["sort"] == "name" else \
                    (lambda x: (_side(_short(x)), _short(x).lower()))
                for kid in sorted(kids, key=key):
                    cmds.reorder(kid, back=True)
    utils.info(TOOL, "organized %d item(s)." % len([n for n in notes if "->" in n]))
    return notes


def organized_nodes():
    return cmds.ls("*." + FROM_ATTR, recursive=True, objectsOnly=True, long=True) or []


def restore():
    """Everything Organize moved goes back where it was (the rig groups stay, empty or not)."""
    back = []
    with utils.undo_chunk("gusrigOrganizeRestore"):
        for n in organized_nodes():
            if not cmds.objExists(n):
                continue
            src = cmds.getAttr(n + "." + FROM_ATTR) or ""
            inherit = cmds.getAttr(n + "." + INHERIT_ATTR) if cmds.attributeQuery(INHERIT_ATTR, node=n,
                                                                                    exists=True) else True
            if src and cmds.objExists(src):
                n2 = cmds.parent(n, src)[0]
            else:
                parent = cmds.listRelatives(n, parent=True, fullPath=True)
                n2 = cmds.parent(n, world=True)[0] if parent else n
            n2 = cmds.ls(n2, long=True)[0]
            cmds.setAttr(n2 + ".inheritsTransform", bool(inherit))
            for a in (FROM_ATTR, INHERIT_ATTR):
                if cmds.attributeQuery(a, node=n2, exists=True):
                    cmds.deleteAttr(n2 + "." + a)
            back.append(_short(n2))
    utils.info(TOOL, "restored %d item(s) to where they were." % len(back))
    return back
