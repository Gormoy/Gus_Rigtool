"""
Rig data: what you added to a rig, saved and put back.

  export / import (Build > Keep when rebuilding): control shapes and colours, your own attributes, set
      driven keys and space switches (Spaces tool) of the rig's controls, to a .json file - and back onto a
      rebuilt rig, matched by name.
  keep across a rebuild (on by default, 'Keep my attributes and space switches'): before a module is taken
      down, the attributes you added to its controls and the space switches made with the Spaces tool are
      written on its guide group; after it is built again they are made again (before your hook-ups are put
      back, so driven keys and connections find their attributes).
"""

import json

import maya.cmds as cmds

from gus_rigtool.builder import controls
from gus_rigtool.core import attrs, curves, naming, spaces, utils
from gus_rigtool.core import nodes as _nodes

TOOL = "Rig data"
ATTR = "gusRigData"
SKIP_PREFIX = ("gus", "rrb")


_short = _nodes.short


def _one(name):
    found = cmds.ls(name, long=True) or []
    return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------------------
# attributes and space switches (also used across rebuilds)
# ---------------------------------------------------------------------------

def my_attrs(node):
    """[{'name', 'info', 'value', 'separator'}] of a control's own attributes (not Gus_Rigtool's notes)."""
    out = []
    for a in attrs.user_attrs(node):
        if a.startswith(SKIP_PREFIX) or a == spaces.META:
            continue
        i = attrs.info(node, a)
        try:
            v = cmds.getAttr(node + "." + a)
        except (RuntimeError, ValueError):
            v = None
        if isinstance(v, (list, tuple)):
            v = None
        out.append({"name": a, "info": i, "value": v, "separator": attrs.is_separator(node, a)})
    return out


def _add_attr(node, item):
    a, i = item["name"], item["info"]
    if cmds.attributeQuery(a, node=node, exists=True):
        return False
    if item.get("separator"):
        cmds.addAttr(node, longName=a, niceName=i.get("nice") or a, attributeType="enum", enumName="------",
                     keyable=False)
        cmds.setAttr(node + "." + a, channelBox=True)
        cmds.setAttr(node + "." + a, lock=True)
        return True
    t = i.get("type") or "double"
    kw = {"longName": a, "keyable": bool(i.get("keyable", True))}
    if t in ("string", "matrix"):
        kw["dataType"] = t
    else:
        kw["attributeType"] = t
    for key, flag in (("min", "minValue"), ("max", "maxValue"), ("default", "defaultValue")):
        if i.get(key) is not None and t not in ("string", "matrix"):
            kw[flag] = i[key]
    if t == "enum":
        kw["enumName"] = i.get("enum") or "off:on"
    if i.get("nice") and i["nice"] != a:
        kw["niceName"] = i["nice"]
    cmds.addAttr(node, **kw)
    if not kw["keyable"] and i.get("channel_box"):
        cmds.setAttr(node + "." + a, channelBox=True)
    return True


def _set_value(node, item):
    v = item.get("value")
    plug = node + "." + item["name"]
    if v is None or item.get("separator") or not utils.settable(plug):
        return
    try:
        if item["info"].get("type") == "string":
            cmds.setAttr(plug, v, type="string")
        else:
            cmds.setAttr(plug, v)
    except (RuntimeError, ValueError, TypeError):
        pass


def put_attrs(node, items, values=True):
    """Make the attributes the node doesn't have (and their values). Returns how many were made."""
    made = 0
    for item in items:
        try:
            if _add_attr(node, item):
                made += 1
                if values:
                    _set_value(node, item)
        except RuntimeError:
            continue
    return made


def _space_record(ctrl):
    data = spaces.read(ctrl)
    if not data:
        return None
    try:
        data["value"] = int(cmds.getAttr(ctrl + "." + data["attr"]))
    except (RuntimeError, ValueError):
        data["value"] = 0
    return data


def _remake_space(ctrl, data):
    targets = [(lb, n) for lb, n in data.get("targets", []) if _one(n)]
    missing = [n for _lb, n in data.get("targets", []) if not _one(n)]
    if len(targets) < 2:
        raise RuntimeError("its targets are gone (%s)" % ", ".join(missing))
    if spaces.read(ctrl) or cmds.attributeQuery(data["attr"], node=ctrl, exists=True):
        return False
    spaces.make(ctrl, targets, data.get("kind", "parent"), data["attr"], data.get("value", 0))
    return True


# ---------------------------------------------------------------------------
# across a rebuild
# ---------------------------------------------------------------------------

def keep_before_take_down(group, ctrls):
    """Write the module's controls' own attributes and Spaces-tool switches on its guide group, and take the
    switches off (their groups sit between builder nodes, they are made again after the build)."""
    rec = {}
    for c in ctrls:
        if not cmds.objExists(c):
            continue
        item = {"attrs": my_attrs(c)}
        sp = _space_record(c)
        if sp:
            item["space"] = sp
            try:
                spaces.remove(c)
            except RuntimeError:
                pass
            item["attrs"] = [a for a in item["attrs"] if a["name"] != sp["attr"]]
        from gus_rigtool.core import sticky
        st = sticky.read(c)
        if st:
            try:
                item["sticky"] = {"mesh": st["mesh"], "amount": cmds.getAttr(c + ".stick"),
                                  "rotate": bool(st.get("rotate")), "ignore": st.get("ignore") or []}
                sticky.unstick(c)
            except RuntimeError:
                pass
            c = _one(_short(c)) or c
            item["attrs"] = [a for a in item["attrs"] if a["name"] not in ("stick", sticky.META)]
        if item["attrs"] or sp or item.get("sticky"):
            rec[_short(c)] = item
    old = _load(group)
    old.update(rec)
    controls.add_string(group, ATTR, json.dumps(old))
    return len(rec)


def _load(group):
    try:
        return json.loads(controls.get_string(group, ATTR) or "{}") or {}
    except ValueError:
        return {}


def put_back_after_build(group):
    """The attributes you added and your space switches back on the rebuilt controls. Returns (made, notes)."""
    rec = _load(group)
    if not rec:
        return 0, []
    made, notes = 0, []
    for name, item in rec.items():
        c = _one(name)
        if not c:
            notes.append("%s isn't made any more: its attributes / space switch are left out" % name)
            continue
        made += put_attrs(c, item.get("attrs", []))
        if item.get("space"):
            try:
                if _remake_space(c, item["space"]):
                    made += 1
            except RuntimeError as e:
                notes.append("%s: space switch not made again - %s" % (name, e))
        if item.get("sticky"):
            from gus_rigtool.core import sticky
            try:
                sticky.stick([c], item["sticky"]["mesh"], item["sticky"].get("amount", 1.0),
                             rotate=item["sticky"].get("rotate", False),
                             ignore=[j for j in item["sticky"].get("ignore", []) if cmds.objExists(j)])
                made += 1
            except RuntimeError as e:
                notes.append("%s: not stuck to the skin again - %s" % (name, e))
    controls.add_string(group, ATTR, "")
    return made, notes


# ---------------------------------------------------------------------------
# set driven keys
# ---------------------------------------------------------------------------

def _curve_targets(curve):
    """The plugs a driven-key curve drives (straight, or through a blendWeighted)."""
    out = []
    for p in cmds.listConnections(curve + ".output", source=False, destination=True, plugs=True,
                                  skipConversionNodes=True) or []:
        node = p.split(".")[0]
        if cmds.nodeType(node) == "blendWeighted":
            out += cmds.listConnections(node + ".output", source=False, destination=True, plugs=True,
                                        skipConversionNodes=True) or []
        else:
            out.append(p)
    return out


def driven_keys(nodes):
    """[{'driver', 'driven', 'keys': [[driver value, value, in tangent, out tangent]], 'pre', 'post'}] for every
    driven-key curve that drives these nodes (or their parent groups)."""
    watch = set()
    for n in nodes:
        watch.add(_short(n))
        p = cmds.listRelatives(n, parent=True, fullPath=True)
        while p and not curves.curve_shapes(p[0]):
            watch.add(_short(p[0]))
            p = cmds.listRelatives(p[0], parent=True, fullPath=True)
    out, seen = [], set()
    for kind in ("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT"):
        for curve in cmds.ls(type=kind) or []:
            if curve in seen:
                continue
            seen.add(curve)
            src = cmds.listConnections(curve + ".input", source=True, destination=False, plugs=True,
                                       skipConversionNodes=True) or []
            if not src:
                continue
            for dst in _curve_targets(curve):
                if _short(dst.split(".")[0]) not in watch:
                    continue
                dv = cmds.keyframe(curve, query=True, floatChange=True) or []
                vals = cmds.keyframe(curve, query=True, valueChange=True) or []
                itt = cmds.keyTangent(curve, query=True, inTangentType=True) or ["auto"] * len(dv)
                ott = cmds.keyTangent(curve, query=True, outTangentType=True) or ["auto"] * len(dv)
                out.append({"driver": _short(src[0].split(".")[0]) + "." + src[0].split(".", 1)[1],
                            "driven": _short(dst.split(".")[0]) + "." + dst.split(".", 1)[1],
                            "keys": [[a, b, c, d] for a, b, c, d in zip(dv, vals, itt, ott)],
                            "pre": cmds.getAttr(curve + ".preInfinity"), "post": cmds.getAttr(curve + ".postInfinity")})
    return out


def put_driven_keys(items, replace=True):
    made, notes = 0, []
    for it in items:
        drv_node, drv_attr = it["driver"].split(".", 1)
        dst_node, dst_attr = it["driven"].split(".", 1)
        drv, dst = _one(drv_node), _one(dst_node)
        if not drv or not dst:
            notes.append("%s -> %s: %s not found" % (it["driver"], it["driven"], drv_node if not drv else dst_node))
            continue
        driver, driven = drv + "." + drv_attr, dst + "." + dst_attr
        if not cmds.objExists(driver) or not cmds.objExists(driven):
            notes.append("%s -> %s: an attribute is missing" % (it["driver"], it["driven"]))
            continue
        if replace:
            for c in cmds.listConnections(driven, source=True, destination=False, type="animCurve") or []:
                src = cmds.listConnections(c + ".input", source=True, destination=False, plugs=True) or []
                if src and _short(src[0].split(".")[0]) == _short(drv) and src[0].split(".", 1)[1] == drv_attr:
                    cmds.delete(c)
        for dv, v, itt, ott in it["keys"]:
            cmds.setDrivenKeyframe(driven, currentDriver=driver, driverValue=dv, value=v,
                                   inTangentType=itt, outTangentType=ott)
        made += 1
    return made, notes


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------

def collect(ctrls):
    data = {"version": 1, "controls": {}, "driven_keys": driven_keys(ctrls)}
    for c in ctrls:
        item = {"attrs": my_attrs(c)}
        try:
            shape, style = curves.read_shape(c), curves.read_style(c)
            json.dumps([shape, style])                  # only what can be written to the file
            item["shape"], item["style"] = shape, style
        except Exception:
            pass
        sp = _space_record(c)
        if sp:
            item["space"] = sp
            item["attrs"] = [a for a in item["attrs"] if a["name"] != sp["attr"]]
        data["controls"][_short(c)] = item
    return data


def export(path, ctrls=None):
    from gus_rigtool.builder import publish
    ctrls = ctrls or publish.rig_controls()
    if not ctrls:
        raise RuntimeError("no rig controls found (build the rig, or select controls).")
    data = collect(ctrls)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return len(data["controls"]), len(data["driven_keys"])


def import_(path, shapes=True, attrs_=True, sdks=True, space_switches=True):
    """Put a rig data file back on the rig, by control name. Returns (summary dict, notes)."""
    with open(path) as f:
        data = json.load(f)
    got = {"shapes": 0, "attributes": 0, "space switches": 0, "driven keys": 0}
    notes = []
    with utils.undo_chunk("gusrigRigData"):
        for name, item in data.get("controls", {}).items():
            c = _one(name)
            if not c:
                notes.append("%s: not in the scene" % naming.short_name(name))
                continue
            if shapes and item.get("shape"):
                try:
                    curves.set_shape(c, item["shape"], item.get("style"))
                    got["shapes"] += 1
                except Exception as e:
                    notes.append("%s: shape not set (%s)" % (name, e))
            if attrs_:
                got["attributes"] += put_attrs(c, item.get("attrs", []))
            if space_switches and item.get("space"):
                try:
                    if _remake_space(c, item["space"]):
                        got["space switches"] += 1
                except RuntimeError as e:
                    notes.append("%s: space switch not made - %s" % (name, e))
        if sdks:
            n, sdk_notes = put_driven_keys(data.get("driven_keys", []))
            got["driven keys"] = n
            notes += sdk_notes
    return got, notes
