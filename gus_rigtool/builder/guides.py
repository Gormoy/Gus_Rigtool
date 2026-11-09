"""
Guides: small spheres you place on the model, one module per group. The module's settings
(names, options, orientation, controls) are saved on its guide group, so Back to guides /
Build always uses them, and they travel with the scene file.
"""

import json

import maya.cmds as cmds

from gus_rigtool.builder import names
from gus_rigtool.core import colors, curves, shape_data, utils

TOP = "guides"
ATTRS = ("gusModule", "gusName", "gusSide", "gusSettings")
KEEP = ("gusOutputs", "gusShapes", "gusShapeSigs", "gusBuiltGuides")     # what the built rig made / your control shapes


def _str_attr(node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def _get(node, attr, default=""):
    try:
        if cmds.attributeQuery(attr, node=node, exists=True):
            return cmds.getAttr(node + "." + attr) or default
    except RuntimeError:
        pass
    return default


def top_group(create=True):
    name = names.make("C", TOP, "grp")
    found = cmds.ls(name, long=True) or []
    if found:
        return found[0]
    if not create:
        return None
    return cmds.ls(cmds.createNode("transform", name=name), long=True)[0]


def module_groups():
    """Every module guide group in the scene, in creation order."""
    return utils.nodes_with_attr("gusModule", "transform")


def module_id(side, name):
    return "%s:%s" % (side, name)


def read(group):
    """{'group', 'type', 'name', 'side', 'id', 'settings', 'guides': {role: node}}"""
    try:
        settings = json.loads(_get(group, "gusSettings", "{}"))
    except ValueError:
        settings = {}
    guides = {}
    for n in cmds.listRelatives(group, allDescendents=True, type="transform", fullPath=True) or []:
        role = _get(n, "gusRole")
        if role:
            guides[role] = n
    side = _get(group, "gusSide", "C")
    name = _get(group, "gusName")
    return {"group": group, "type": _get(group, "gusModule"), "name": name, "side": side,
            "id": module_id(side, name), "settings": settings, "guides": guides}


def save_settings(group, settings):
    _str_attr(group, "gusSettings", json.dumps(settings))


def positions(group):
    info = read(group)
    return {role: cmds.xform(node, query=True, worldSpace=True, translation=True)
            for role, node in info["guides"].items()}


# ---------------------------------------------------------------------------
# making guides
# ---------------------------------------------------------------------------

def library_shape(name):
    for _cat, items in shape_data.builtin_shapes():
        for n, data in items:
            if n == name:
                return data
    from gus_rigtool.core import ribbon
    return ribbon._library_shape(name)


def _guide_shape(kind, size):
    return shape_data.scale(library_shape("diamond_3d" if kind == "pivot" else "sphere"),
                            size * (0.8 if kind == "pivot" else 1.0))


def _line(a, b, parent, name):
    """A thin line from guide a to guide b that follows them."""
    crv = cmds.curve(degree=1, point=[(0, 0, 0), (0, 0, 0)], name=name)
    shape = cmds.listRelatives(crv, shapes=True, fullPath=True)[0]
    for i, g in enumerate((a, b)):
        dm = cmds.createNode("decomposeMatrix", name=name + "_dm%d" % i)
        cmds.connectAttr(g + ".worldMatrix[0]", dm + ".inputMatrix")
        cmds.connectAttr(dm + ".outputTranslate", shape + ".controlPoints[%d]" % i)
    cmds.setAttr(shape + ".overrideEnabled", 1)
    cmds.setAttr(shape + ".overrideDisplayType", 2)               # reference: not selectable
    cmds.setAttr(crv + ".inheritsTransform", 0)
    return cmds.parent(crv, parent)[0]


def create(module, side, name, settings, height, keep=None, parent=None):
    """
    Make the guide group of a module. keep: {role: world position} to reuse (rebuilt guides,
    mirrored guides, templates).
    """
    settings = module.complete(settings)
    specs = module.guide_specs(settings, height, side)
    group = cmds.createNode("transform", name=names.make(side, name + "_guides", "grp"))
    group = cmds.parent(group, parent or top_group())[0]
    group = cmds.ls(group, long=True)[0]
    _str_attr(group, "gusModule", module.TYPE)
    _str_attr(group, "gusName", name)
    _str_attr(group, "gusSide", side)
    save_settings(group, settings)

    rgb = colors.side_colors()[side]
    size = max(0.2, height * 0.012) * float(settings.get("guide_size", 1.0))
    made = {}
    for spec in specs:
        role, part = spec["role"], spec["part"]
        data = _guide_shape(spec.get("kind", "joint"), size * spec.get("size", 1.0))
        g = curves.create_curve_control(names.make(side, part, "gde"), data,
                                        curves.rgb_style(rgb if spec.get("kind") != "pivot"
                                                         else [v * 0.6 for v in rgb]))
        under = (made.get(spec.get("parent")) if linked() else None) or group
        g = cmds.ls(cmds.parent(g, under)[0], long=True)[0]
        _str_attr(g, "gusRole", role)
        pos = (keep or {}).get(role, spec["pos"])
        cmds.xform(g, worldSpace=True, translation=pos)
        for attr in ("rx", "ry", "rz", "sx", "sy", "sz", "v"):
            cmds.setAttr(g + "." + attr, lock=True, keyable=False, channelBox=False)
        made[role] = cmds.ls(g, long=True)[0]

    lines = cmds.createNode("transform", name=names.make(side, name + "_guideLines", "grp"), parent=group)
    for spec in specs:
        p = spec.get("line_to") or spec.get("parent")
        if p and p in made and spec["role"] in made:
            _line(made[p], made[spec["role"]], lines, names.make(side, spec["part"] + "_line", "crv"))
    if _labels_on():
        for guide in made.values():
            try:
                _label(guide)
            except (RuntimeError, ValueError, TypeError, AttributeError):
                pass
    relink_if_on()
    return group


def _labels_on():
    return bool(utils.tool_settings("build", {}).get("guide_names", False))


def _label(guide):
    """A text label on a guide (its part name), drawn in the viewport, no arrow."""
    part = guide.split("|")[-1]
    suffix = names.settings()["suffixes"].get("gde", "_gde")
    text = part[:-len(suffix)] if part.endswith(suffix) else part
    pos = cmds.xform(guide, query=True, worldSpace=True, translation=True)
    shape = cmds.annotate(guide, text=text, point=pos)
    tr = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    tr = cmds.parent(tr, guide)[0]
    tr = cmds.rename(tr, part + "_label")
    cmds.setAttr(tr + ".translate", 0, 0, 0)
    _str_attr(tr, "gusLabel", "1")
    for sh in cmds.listRelatives(tr, shapes=True, fullPath=True) or []:
        if cmds.attributeQuery("displayArrow", node=sh, exists=True):
            cmds.setAttr(sh + ".displayArrow", 0)
        cmds.setAttr(sh + ".overrideEnabled", 1)
        cmds.setAttr(sh + ".overrideDisplayType", 2)              # not selectable
    return tr


def _guides_in(group):
    return [n for n in (cmds.listRelatives(group, allDescendents=True, type="transform", fullPath=True) or [])
            if cmds.attributeQuery("gusRole", node=n, exists=True)]


def _clear_labels(group):
    labels = [n for n in (cmds.listRelatives(group, allDescendents=True, type="transform", fullPath=True) or [])
              if cmds.attributeQuery("gusLabel", node=n, exists=True)]
    if labels:
        cmds.delete(labels)


def show_names(on=True):
    """Labels with the part names on every guide (on), or none (off). Returns how many."""
    count = 0
    for g in module_groups():
        _clear_labels(g)
        if on:
            for guide in _guides_in(g):
                try:
                    _label(guide)
                    count += 1
                except (RuntimeError, ValueError, TypeError, AttributeError):
                    pass
    return count


def linked():
    """Linked guides: moving one moves the ones below it. Free: each guide moves alone."""
    return utils.tool_settings("build", {}).get("guide_mode", "linked") != "free"


def set_mode(free, height=180.0):
    """Re-parent every module's guides: all straight under their module group (free), or each under
    the guide above it (linked). Nothing moves."""
    from gus_rigtool.builder import modules
    for group in module_groups():
        info = read(group)
        mod = modules.MODULES.get(info["type"])
        if not mod:
            continue
        specs = mod.guide_specs(mod.complete(dict(info["settings"])), height, info["side"])
        for spec in specs:
            g = read(group)["guides"].get(spec["role"])               # paths change as we go
            if not g:
                continue
            target = group
            if not free and spec.get("parent"):
                target = read(group)["guides"].get(spec["parent"]) or group
            current = (cmds.listRelatives(g, parent=True, fullPath=True) or [None])[0]
            if current != cmds.ls(target, long=True)[0]:
                cmds.parent(g, target)


# ---------------------------------------------------------------------------
# symmetry lock: right guides follow the left ones live (a small node network per guide)
# ---------------------------------------------------------------------------

SYM = "gusGuideSymmetry"
MIRROR_X = [-1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def symmetry_nodes():
    return [n for n in (cmds.ls("*." + SYM, objectsOnly=True, long=True) or []) if cmds.objExists(n)]


SYM_ON = "gusSymmetryOn"


def symmetry_on():
    """The lock is on in this scene (written on the guides group)."""
    top = top_group(create=False)
    return bool(top and _get(top, SYM_ON) == "1")


def symmetry_pairs():
    """[(left guide, right guide)] of every L module that has its R twin (same type and name)."""
    infos = [read(g) for g in module_groups()]
    rights = {(i["type"], i["name"]): i for i in infos if i["side"] == "R"}
    out = []
    for i in infos:
        if i["side"] != "L":
            continue
        r = rights.get((i["type"], i["name"]))
        if not r:
            continue
        for role, lg in sorted(i["guides"].items()):
            rg = r["guides"].get(role)
            if rg:
                out.append((lg, rg))
    return out


def _tag(node):
    cmds.addAttr(node, longName=SYM, dataType="string")
    return node


def _drives_translate(guide):
    return bool(cmds.listConnections(guide + ".translate", source=True, destination=False) or
                any(cmds.listConnections("%s.translate%s" % (guide, a), source=True, destination=False)
                    for a in "XYZ"))


def _link(left, right):
    base = right.split("|")[-1]
    mm = _tag(cmds.createNode("multMatrix", name=base + "_sym_mm"))
    dm = _tag(cmds.createNode("decomposeMatrix", name=base + "_sym_dm"))
    cmds.connectAttr(left + ".worldMatrix[0]", mm + ".matrixIn[0]")
    cmds.setAttr(mm + ".matrixIn[1]", MIRROR_X, type="matrix")
    cmds.connectAttr(right + ".parentInverseMatrix[0]", mm + ".matrixIn[2]")
    cmds.connectAttr(mm + ".matrixSum", dm + ".inputMatrix")
    cmds.connectAttr(dm + ".outputTranslate", right + ".translate", force=True)


def _clean_stale():
    """Networks whose left or right guide is gone (re-made by Mirror / new settings): deleted, the right
    guide keeps where it is."""
    for mm in [n for n in symmetry_nodes() if cmds.nodeType(n) == "multMatrix"]:
        dms = cmds.listConnections(mm + ".matrixSum", source=False, destination=True) or []
        has_left = cmds.listConnections(mm + ".matrixIn[0]", source=True, destination=False)
        has_right = any(cmds.listConnections(d + ".outputTranslate", source=False, destination=True)
                        for d in dms)
        if has_left and has_right:
            continue
        for d in dms:
            for dst in cmds.listConnections(d + ".outputTranslate", source=False, destination=True, plugs=True) or []:
                value = cmds.getAttr(dst)
                cmds.disconnectAttr(d + ".outputTranslate", dst)
                if value and isinstance(value[0], (list, tuple)):
                    cmds.setAttr(dst, *value[0])
        cmds.delete([mm] + [d for d in dms if cmds.objExists(d)])
    for d in [n for n in symmetry_nodes() if cmds.nodeType(n) == "decomposeMatrix"]:
        if not cmds.listConnections(d, source=True, destination=False):
            cmds.delete(d)


def link_missing():
    """Link every left / right guide pair that isn't linked yet. Returns how many were linked."""
    _clean_stale()
    n = 0
    for left, right in symmetry_pairs():
        if _drives_translate(right):
            continue
        for attr in ("translate", "translateX", "translateY", "translateZ"):
            try:
                cmds.setAttr(right + "." + attr, lock=False)
            except RuntimeError:
                pass
        _link(left, right)
        n += 1
    return n


def set_symmetry(on):
    """on: right guides follow the left ones (they snap to the mirror of the left now). Off: the networks go,
    the right guides stay where they are. Returns how many guides are linked."""
    nodes = symmetry_nodes()
    if nodes:
        for r in [x for x in nodes if cmds.nodeType(x) == "decomposeMatrix"]:
            for dst in cmds.listConnections(r + ".outputTranslate", source=False, destination=True, plugs=True) or []:
                try:
                    value = cmds.getAttr(dst)
                    cmds.disconnectAttr(r + ".outputTranslate", dst)
                    if value and isinstance(value[0], (list, tuple)):
                        cmds.setAttr(dst, *value[0])
                except RuntimeError:
                    pass
        cmds.delete(symmetry_nodes())
    _str_attr(top_group(), SYM_ON, "1" if on else "0")
    if not on:
        return 0
    return link_missing()


def delete(group):
    if cmds.objExists(group):
        cmds.delete(group)


def update(group, module, settings, height):
    """Re-make a module's guides with new settings (names, joint counts), keeping the positions
    of the roles that still exist. Returns the new group."""
    info = read(group)
    keep = positions(group)
    kept = {a: _get(group, a) for a in KEEP}      # Rebuild selected needs them
    parent = (cmds.listRelatives(group, parent=True, fullPath=True) or [None])[0]
    cmds.delete(group)
    new = create(module, info["side"], info["name"], settings, height, keep=keep, parent=parent)
    for a, v in kept.items():
        if v:
            _str_attr(new, a, v)
    return new


def mirror(group, module, height):
    """Copy a left module's guides to the right (positions reflected across X). Updates the right
    module if it exists. Returns the right group."""
    info = read(group)
    if info["side"] not in ("L", "R"):
        raise RuntimeError("'%s' is a centre module: nothing to mirror." % info["name"])
    other = "R" if info["side"] == "L" else "L"
    keep = {r: [-p[0], p[1], p[2]] for r, p in positions(group).items()}
    kept = {}
    for g in module_groups():
        o = read(g)
        if o["type"] == info["type"] and o["name"] == info["name"] and o["side"] == other:
            kept = {a: _get(g, a) for a in KEEP}           # keep what the built rig made
            cmds.delete(g)
    settings = dict(info["settings"])
    new = create(module, other, info["name"], settings, height, keep=keep,
                 parent=(cmds.listRelatives(group, parent=True, fullPath=True) or [None])[0])
    for a, v in kept.items():
        if v:
            _str_attr(new, a, v)
    return new


def relink_if_on():
    """After guides are re-made (Mirror, new settings): link the new ones when the lock is on."""
    if symmetry_on():
        link_missing()


def set_visible(visible):
    """All the guides shown or hidden (every module group shown again inside)."""
    top = top_group(create=False)
    if top:
        cmds.setAttr(top + ".visibility", bool(visible))
    for g in module_groups():
        cmds.setAttr(g + ".visibility", True)


def show_only(groups):
    """Only these modules' guides are shown (the rest of the guides hidden)."""
    top = top_group(create=False)
    if top:
        cmds.setAttr(top + ".visibility", True)
    keep = set(utils.ls(groups, long=True) or [])
    for g in module_groups():
        cmds.setAttr(g + ".visibility", g in keep)


def shown_only():
    """The module groups shown on their own (show_only), or [] when all / none are shown."""
    top = top_group(create=False)
    if not top or not cmds.getAttr(top + ".visibility"):
        return []
    groups = module_groups()
    shown = [g for g in groups if cmds.getAttr(g + ".visibility")]
    return shown if len(shown) < len(groups) else []


# ---------------------------------------------------------------------------
# guides are never controls: tools that reset / zero things leave them alone
# ---------------------------------------------------------------------------

def is_guide(node):
    try:
        return cmds.attributeQuery("gusRole", node=node, exists=True)
    except (RuntimeError, ValueError, TypeError):
        return False


def _at_origin(p, tol=1e-4):
    return all(abs(v) < tol for v in p)


def remember_built(group):
    """The guides' positions at Build (Back to guides can put them back if something zeroes them)."""
    import json
    _str_attr(group, "gusBuiltGuides", json.dumps({r: [round(v, 6) for v in p] for r, p in positions(group).items()}))


def restore_zeroed(group):
    """Guides found at 0, 0, 0 that weren't there at the last Build go back to where they were built (only when
    most of the module's guides are at the origin - the sign that something zeroed them). Returns how many."""
    import json
    try:
        built = json.loads(_get(group, "gusBuiltGuides") or "{}")
    except ValueError:
        return 0
    info = read(group)
    now = positions(group)
    zeroed = [r for r, p in now.items() if _at_origin(p) and r in built and not _at_origin(built[r])]
    if not zeroed or len(zeroed) * 2 < len(now):
        return 0
    done = 0
    for role in sorted(zeroed, key=lambda r: info["guides"][r].count("|")):     # parents before children
        try:
            cmds.xform(info["guides"][role], worldSpace=True, translation=built[role])
            done += 1
        except (RuntimeError, ValueError, KeyError):
            pass                                                 # driven (symmetry): follows its twin
    return done
