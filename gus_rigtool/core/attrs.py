"""
Attribute helpers for the Attributes tool: list, reorder, add, rename, delete, edit, copy.

Reordering uses the trick from attributesReorder.py by Romain Fleischer: deleting an attribute and
undoing the delete puts it back - with its value, keys and connections - at the END of the list.
Doing that to the attributes in the wanted order gives the wanted order. Only the attributes from
the first one that moved are touched. Undo must be on (it is checked), and every attribute is checked
after (it exists, same connections) before going on.
"""

import maya.cmds as cmds

KINDS = ["float", "int", "bool", "enum", "separator"]
_TYPE_OF = {"float": "double", "int": "long", "bool": "bool", "enum": "enum"}
SEPARATOR_NICE = "------ %s"


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def user_attrs(node):
    """The node's own (user defined) attributes, top level only, in their Channel Box order."""
    out = []
    for a in cmds.listAttr(node, userDefined=True) or []:
        if "." in a or a in out:
            continue
        try:
            if cmds.attributeQuery(a, node=node, listParent=True):
                continue                                # a child of a compound (myVectorX...)
        except (RuntimeError, TypeError):
            pass
        out.append(a)
    return out


def kind(node, attr):
    try:
        return cmds.getAttr(node + "." + attr, type=True) or ""
    except (RuntimeError, ValueError):
        return ""


def nice(node, attr):
    try:
        return cmds.attributeQuery(attr, node=node, niceName=True) or attr
    except (RuntimeError, TypeError):
        return attr


def enum_names(node, attr):
    try:
        return ((cmds.attributeQuery(attr, node=node, listEnum=True) or [""])[0] or "").split(":")
    except (RuntimeError, TypeError):
        return []


def is_separator(node, attr):
    """A divider line in the Channel Box: an enum whose only value is dashes (or a '---' nice name)."""
    if kind(node, attr) != "enum":
        return False
    names = [n.strip() for n in enum_names(node, attr) if n.strip()]
    if names and all(set(n) <= set("-_= ") for n in names):
        return True
    return str(nice(node, attr)).strip().startswith("---")


def label(node, attr):
    if is_separator(node, attr):
        n = str(nice(node, attr))
        return n if n.startswith("---") else "------ " + attr.lstrip("_")
    return "%s   (%s)" % (attr, kind(node, attr) or "?")


def info(node, attr):
    """{'type', 'min', 'max', 'default', 'enum', 'keyable', 'channel_box', 'nice'} - None where not set."""
    plug = node + "." + attr
    out = {"type": kind(node, attr), "min": None, "max": None, "default": None, "enum": "", "nice": nice(node, attr),
           "keyable": True, "channel_box": False}
    q = lambda **k: cmds.attributeQuery(attr, node=node, **k)
    try:
        if q(minExists=True):
            out["min"] = (q(minimum=True) or [None])[0]
        if q(maxExists=True):
            out["max"] = (q(maximum=True) or [None])[0]
        out["default"] = (q(listDefault=True) or [None])[0]
    except (RuntimeError, TypeError):
        pass
    if out["type"] == "enum":
        out["enum"] = ":".join(enum_names(node, attr))
    try:
        out["keyable"] = bool(cmds.getAttr(plug, keyable=True))
        out["channel_box"] = bool(cmds.getAttr(plug, channelBox=True))
    except (RuntimeError, ValueError):
        pass
    return out


def _conns(node, attr):
    plug = node + "." + attr
    ins = cmds.listConnections(plug, source=True, destination=False, plugs=True, connections=True) or []
    outs = cmds.listConnections(plug, source=False, destination=True, plugs=True, connections=True) or []
    pairs = set()
    for dst, src in zip(ins[0::2], ins[1::2]):
        pairs.add(("in", src, dst.split(".", 1)[1]))
    for src, dst in zip(outs[0::2], outs[1::2]):
        pairs.add(("out", src.split(".", 1)[1], dst))
    return pairs


# ---------------------------------------------------------------------------
# order
# ---------------------------------------------------------------------------

def full_order(current, wanted):
    """wanted (some of the node's attributes, in order) + the node's others after, in their order."""
    head = [a for a in wanted if a in current]
    return head + [a for a in current if a not in head]


def to_move(current, wanted):
    """The attributes that must go round the delete / undo trick: from the first one out of place."""
    wanted = full_order(current, wanted)
    i = 0
    while i < len(current) and current[i] == wanted[i]:
        i += 1
    return wanted[i:]


def move(order, picked, where):
    """New order with the picked attributes moved: 'up', 'down', 'top', 'bottom'. Picked stay together
    in their order for top / bottom; up / down move each one step (blocks stop at the ends)."""
    order = list(order)
    picked = [a for a in order if a in picked]
    if not picked:
        return order
    if where == "top":
        return picked + [a for a in order if a not in picked]
    if where == "bottom":
        return [a for a in order if a not in picked] + picked
    if where == "up":
        for i in range(1, len(order)):
            if order[i] in picked and order[i - 1] not in picked:
                order[i - 1], order[i] = order[i], order[i - 1]
        return order
    if where == "down":
        for i in range(len(order) - 2, -1, -1):
            if order[i] in picked and order[i + 1] not in picked:
                order[i + 1], order[i] = order[i], order[i + 1]
        return order
    raise ValueError(where)


def apply_order(node, wanted):
    """Put the node's attributes in this order (attributes it doesn't have are skipped, the ones not
    listed keep their order after). Returns how many attributes went round. Not one Ctrl+Z: keep the old
    order (user_attrs) to put it back."""
    current = user_attrs(node)
    moving = to_move(current, wanted)
    if not moving:
        return 0
    if not cmds.undoInfo(query=True, state=True):
        raise RuntimeError("undo is turned off in Maya - the reorder needs it (Edit > Undo, or "
                           "cmds.undoInfo(state=True)). Nothing was changed.")
    short = node.split("|")[-1]
    for a in moving:
        plug = node + "." + a
        before = _conns(node, a)
        locked = bool(cmds.getAttr(plug, lock=True))
        if locked:
            cmds.setAttr(plug, lock=False)
        cmds.deleteAttr(plug)
        cmds.undo()
        if not cmds.attributeQuery(a, node=node, exists=True):
            raise RuntimeError("%s.%s did not come back after the undo - press Ctrl+Z once to get it back, "
                               "and stop here." % (short, a))
        if locked:
            cmds.setAttr(plug, lock=True)
        lost = before - _conns(node, a)
        for way, x, y in lost:                                         # should never happen: put it back
            try:
                if way == "in":
                    cmds.connectAttr(x, node + "." + y, force=True)
                else:
                    cmds.connectAttr(node + "." + x, y, force=True)
            except RuntimeError:
                raise RuntimeError("%s.%s lost a connection (%s) in the reorder." % (short, a, x if way == "in"
                                                                                     else y))
    return len(moving)


# ---------------------------------------------------------------------------
# add / rename / delete / edit / copy
# ---------------------------------------------------------------------------

def _num(text):
    text = ("%s" % text).strip() if text is not None else ""
    if not text:
        return None
    return float(text)


def add(node, name, kind_, minimum=None, maximum=None, default=None, enum="", keyable=True):
    """Add one attribute. kind_: float / int / bool / enum / separator. Returns the attribute name."""
    name = name.strip()
    if not name:
        raise ValueError("type a name for the attribute.")
    if kind_ == "separator":
        attr = "_" + name.replace(" ", "_").strip("_")
        if cmds.attributeQuery(attr, node=node, exists=True):
            raise RuntimeError("%s already has '%s'." % (node.split("|")[-1], attr))
        cmds.addAttr(node, longName=attr, niceName=SEPARATOR_NICE % name, attributeType="enum",
                     enumName="------", keyable=False)
        cmds.setAttr(node + "." + attr, channelBox=True)
        cmds.setAttr(node + "." + attr, lock=True)
        return attr
    if not name.replace("_", "a").isalnum() or name[0].isdigit():
        raise ValueError("'%s': use letters, numbers and _ (not first a number)." % name)
    if cmds.attributeQuery(name, node=node, exists=True):
        raise RuntimeError("%s already has '%s'." % (node.split("|")[-1], name))
    kw = {"longName": name, "attributeType": _TYPE_OF[kind_], "keyable": keyable}
    mn, mx, df = _num(minimum), _num(maximum), _num(default)
    if kind_ == "enum":
        items = [x.strip() for x in (enum or "").replace(",", ":").split(":") if x.strip()]
        if not items:
            raise ValueError("type the enum names (e.g. off:on or world, root, chest).")
        kw["enumName"] = ":".join(items)
        if df is not None:
            kw["defaultValue"] = int(df)
    elif kind_ == "bool":
        if df is not None:
            kw["defaultValue"] = bool(df)
    else:
        if mn is not None:
            kw["minValue"] = mn
        if mx is not None:
            kw["maxValue"] = mx
        if df is not None:
            kw["defaultValue"] = df
    if mn is not None and mx is not None and mn > mx:
        raise ValueError("min is bigger than max.")
    cmds.addAttr(node, **kw)
    if not keyable:
        cmds.setAttr(node + "." + name, channelBox=True)
    return name


def rename(node, old, new):
    new = new.strip()
    if not new or not new.replace("_", "a").isalnum() or new[0].isdigit():
        raise ValueError("'%s': use letters, numbers and _ (not first a number)." % new)
    if cmds.attributeQuery(new, node=node, exists=True):
        raise RuntimeError("%s already has '%s'." % (node.split("|")[-1], new))
    cmds.renameAttr(node + "." + old, new)
    return new


def delete(node, attr):
    plug = node + "." + attr
    if cmds.getAttr(plug, lock=True):
        cmds.setAttr(plug, lock=False)
    cmds.deleteAttr(plug)


def edit(node, attr, minimum=None, maximum=None, default=None, enum=None):
    """Change min / max / default (blank = leave), and enum names. Returns what changed."""
    plug = node + "." + attr
    t = kind(node, attr)
    done = []
    mn, mx, df = _num(minimum), _num(maximum), _num(default)
    if t in ("double", "float", "long", "short", "byte", "doubleLinear", "doubleAngle"):
        if mn is not None:
            cmds.addAttr(plug, edit=True, hasMinValue=True, minValue=mn)
            done.append("min %g" % mn)
        if mx is not None:
            cmds.addAttr(plug, edit=True, hasMaxValue=True, maxValue=mx)
            done.append("max %g" % mx)
    if df is not None and t != "string":
        cmds.addAttr(plug, edit=True, defaultValue=df)
        done.append("default %g" % df)
    if enum and t == "enum":
        items = [x.strip() for x in enum.replace(",", ":").split(":") if x.strip()]
        if items:
            cmds.addAttr(plug, edit=True, enumName=":".join(items))
            done.append("names %s" % ":".join(items))
    return done


def clear_limit(node, attr, which):
    plug = node + "." + attr
    if which == "min":
        cmds.addAttr(plug, edit=True, hasMinValue=False)
    else:
        cmds.addAttr(plug, edit=True, hasMaxValue=False)


def copy(source, target, attrs, connections=False):
    """Copy attributes (definition, value, and incoming connections if asked) from source to target.
    Attributes target already has only get the value. Returns (added, updated) names."""
    added, updated = [], []
    for a in attrs:
        sp, tp = source + "." + a, target + "." + a
        i = info(source, a)
        if not cmds.attributeQuery(a, node=target, exists=True):
            if is_separator(source, a):
                cmds.addAttr(target, longName=a, niceName=i["nice"], attributeType="enum", enumName="------",
                             keyable=False)
                cmds.setAttr(tp, channelBox=True)
                cmds.setAttr(tp, lock=True)
                added.append(a)
                continue
            t = i["type"]
            kw = {"longName": a, "keyable": i["keyable"]}
            if t in ("string", "matrix", "stringArray", "doubleArray"):
                kw["dataType"] = t
            else:
                kw["attributeType"] = t or "double"
            if i["nice"] and i["nice"] != a:
                kw["niceName"] = i["nice"]
            if i["min"] is not None:
                kw["minValue"] = i["min"]
            if i["max"] is not None:
                kw["maxValue"] = i["max"]
            if i["default"] is not None and t not in ("string",):
                kw["defaultValue"] = i["default"]
            if t == "enum":
                kw["enumName"] = i["enum"]
            cmds.addAttr(target, **kw)
            if not i["keyable"] and i["channel_box"]:
                cmds.setAttr(tp, channelBox=True)
            added.append(a)
        else:
            updated.append(a)
        try:
            src = cmds.listConnections(sp, source=True, destination=False, plugs=True) or []
            if connections and src:
                cmds.connectAttr(src[0], tp, force=True)
            elif utils_settable(tp) and i["type"] != "message":
                v = cmds.getAttr(sp)
                if i["type"] == "string":
                    cmds.setAttr(tp, v or "", type="string")
                elif not isinstance(v, (list, tuple)):
                    cmds.setAttr(tp, v)
        except (RuntimeError, ValueError, TypeError):
            pass
    return added, updated


def utils_settable(plug):
    from gus_rigtool.core import utils
    return utils.settable(plug)
