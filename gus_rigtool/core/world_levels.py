"""
World controls (5.6.0): Global_ctrl (scale) > World_ctrl > Local_ctrl, from the World_ctrl the rig has.

    from gus_rigtool.core import world_levels
    world_levels.make()                     # the world control found by itself, or world_levels.make("World_ctrl")

- Global_ctrl: above World_ctrl's group, the same shape a bit bigger. The rig's one scale ('globalScale') moves
  here: everything that read World_ctrl.globalScale (stretchy limbs, IK spline, jiggle chains...) reads it from
  Global_ctrl, which scales.
- World_ctrl: moves and turns only (its follows / space switches still point at it).
- Local_ctrl: under World_ctrl, a bit smaller; what was under World_ctrl goes under it.
One undo; nothing moves.
"""

import re

import maya.cmds as cmds

from gus_rigtool.core import curves, naming, shape_data, utils

GLOBAL, LOCAL = "Global_ctrl", "Local_ctrl"
LEVEL_ATTR = "gusWorldLevel"
SCALE_ATTR = "globalScale"
_SCALES = ("scaleX", "scaleY", "scaleZ")


def _short(n):
    return naming.short_name(n)


def find_world():
    from gus_rigtool.core import on_top
    from gus_rigtool.core import world_turn as WT
    w = WT.world_control(on_top.controls())
    if not w:
        raise RuntimeError("no world control found: select it.")
    return w


def levels():
    """{'global': node, 'world': node, 'local': node} - the ones made here (tagged)."""
    out = {}
    for n in cmds.ls("*." + LEVEL_ATTR, objectsOnly=True, long=True) or []:
        out[cmds.getAttr(n + "." + LEVEL_ATTR)] = n
    return out


def _tag(n, level):
    if not cmds.attributeQuery(LEVEL_ATTR, node=n, exists=True):
        cmds.addAttr(n, longName=LEVEL_ATTR, dataType="string")
    cmds.setAttr(n + "." + LEVEL_ATTR, level, type="string")


def _hide(n, attrs):
    for a in attrs:
        try:
            cmds.setAttr("%s.%s" % (n, a), lock=True, keyable=False, channelBox=False)
        except RuntimeError:
            pass


def _new_control(name, like, factor, parent, matrix):
    """An offset group + control at matrix under parent, with like's shape scaled by factor. (offset, ctrl)."""
    off = cmds.createNode("transform", name=naming.unique(name + "_offset"), skipSelect=True)
    if parent:
        off = cmds.parent(off, parent, relative=True)[0]
    off = cmds.ls(off, long=True)[0]
    cmds.xform(off, worldSpace=True, matrix=matrix)
    data = curves.read_shape(like) or shape_data.circle_curve(1.0)
    ctrl = curves.create_curve_control(naming.unique(name), shape_data.scale(data, factor), curves.read_style(like))
    ctrl = cmds.parent(ctrl, off, relative=True)[0]
    return off, cmds.ls(ctrl, long=True)[0]


def _at_rest(n):
    for a, v in (("translate", 0.0), ("rotate", 0.0)):
        for ax in "XYZ":
            if abs(cmds.getAttr("%s.%s%s" % (n, a, ax)) - v) > 1e-6:
                return False
    return True


def plan(world=None):
    """What make() will do, as lines (and raises when it can't)."""
    world = cmds.ls(world or find_world(), long=True)[0]
    got = levels()
    if got.get("global") or got.get("local"):
        raise RuntimeError("the world controls are made already (%s)." % ", ".join(_short(x) for x in got.values()))
    for name in (GLOBAL, LOCAL):
        taken = [_short(t) for t in cmds.ls(type="transform") or []
                 if re.match(r"^%s\d*$" % re.escape(name), _short(t).split(":")[-1])]
        if taken:
            raise RuntimeError("%s already exists (%s) - delete or rename it first." % (name, ", ".join(taken)))
    from gus_rigtool.builder import publish
    if publish.is_published():
        raise RuntimeError("the rig is published: Unpublish first.")
    if not _at_rest(world):
        raise RuntimeError("put %s back at 0 first (move / turn)." % _short(world))
    kids = [k for k in cmds.listRelatives(world, children=True, type="transform", fullPath=True) or []
            if "constraint" not in cmds.nodeType(k).lower()]
    readers = _scale_readers(world)
    readers = (readers or []) + _channel_readers(world) if (readers is not None or _channel_readers(world)) \
        else None
    return ["%s: new, above %s - the scale (%s)" % (GLOBAL, _short(world), SCALE_ATTR),
            "%s: moves and turns only%s" % (_short(world), ", its scale moved to %s (%d thing(s) read it)" % (
                GLOBAL, len(readers)) if readers is not None else ""),
            "%s: new, under %s - %d thing(s) under %s move under it" % (LOCAL, _short(world), len(kids),
                                                                       _short(world))]


_CHANNELS = [0]


def _from(dst, plug):
    """dst is fed by exactly this plug (not one of its children)."""
    s = cmds.listConnections(dst, source=True, destination=False, plugs=True) or []
    return bool(s) and s[0].split(".", 1)[1] == plug.split(".", 1)[1]


def _is_constraint(plug):
    """5.6.4: a constraint's input (its target's scale): it must keep reading World_ctrl's own scale - pointed at the
    global scale, the constraint counts it twice (the Hare's IK hands in 'root' space went off at x2)."""
    try:
        return "constraint" in cmds.nodeType(plug.split(".")[0]).lower()
    except RuntimeError:
        return False


def _channel_readers(world):
    """Plugs fed by World_ctrl's own scale channels (5.6.3) - not constraints (5.6.4)."""
    out = []
    for a in _SCALES + ("scale",):                 # the compound lists its children's connections too: once each
        for d in cmds.listConnections("%s.%s" % (world, a), source=False, destination=True, plugs=True,
                                      skipConversionNodes=True) or []:
            if d not in out and not _is_constraint(d):
                out.append(d)
    return out


def _scale_readers(world):
    """Plugs fed by world.globalScale other than the world's own scale (None: no globalScale)."""
    if not cmds.attributeQuery(SCALE_ATTR, node=world, exists=True):
        return None
    out = []
    for dst in cmds.listConnections(world + "." + SCALE_ATTR, source=False, destination=True, plugs=True) or []:
        node, attr = dst.split(".", 1)
        if (cmds.ls(node, long=True) or [node])[0] == world and attr in _SCALES + ("sx", "sy", "sz"):
            continue
        out.append(dst)
    return out


def make(world=None, global_name=GLOBAL, local_name=LOCAL):
    """Global > World > Local (see the module notes). Returns {'global', 'world', 'local', 'moved', 'readers'}."""
    plan(world)
    world = cmds.ls(world or find_world(), long=True)[0]
    wm = cmds.xform(world, query=True, worldSpace=True, matrix=True)
    wid = utils.uuid(world)
    try:
        return _make(world, wm, wid, global_name, local_name)
    except Exception:
        try:                                               # 5.6.1: nothing half-made (a second Global_ctrl1...)
            if "gusrigWorldLevels" in (cmds.undoInfo(query=True, undoName=True) or ""):
                cmds.undo()
        except RuntimeError:
            pass
        raise


def _make(world, wm, wid, global_name, local_name):
    with utils.undo_chunk("gusrigWorldLevels"):
        par = (cmds.listRelatives(world, parent=True, fullPath=True) or [None])[0]
        is_offset = par and len(cmds.listRelatives(par, children=True, type="transform") or []) == 1 and \
            not curves.curve_shapes(par)
        top = par if is_offset else world                 # what goes under Global_ctrl: World's group, or World
        above = (cmds.listRelatives(top, parent=True, fullPath=True) or [None])[0]
        g_off, g = _new_control(global_name, world, 1.25, above, wm)
        gid = utils.uuid(g)
        cmds.parent(top, g)
        world = utils.path(wid)
        g = utils.path(gid)

        # the scale moves to Global
        old = cmds.getAttr(world + "." + SCALE_ATTR) if cmds.attributeQuery(SCALE_ATTR, node=world,
                                                                                exists=True) else 1.0
        cmds.addAttr(g, longName=SCALE_ATTR, attributeType="double", defaultValue=1.0, minValue=0.001,
                     keyable=True)
        cmds.setAttr(g + "." + SCALE_ATTR, old)
        for a in _SCALES:
            cmds.connectAttr(g + "." + SCALE_ATTR, "%s.%s" % (g, a))
        _hide(g, _SCALES)
        readers = _scale_readers(world) or []
        if cmds.attributeQuery(SCALE_ATTR, node=world, exists=True):
            for dst in readers:
                cmds.connectAttr(g + "." + SCALE_ATTR, dst, force=True)
            for a in _SCALES:
                plug = "%s.%s" % (world, a)
                src = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
                if src:
                    cmds.setAttr(plug, lock=False)
                    cmds.disconnectAttr(src[0], plug)
                cmds.setAttr(plug, lock=False)
                cmds.setAttr(plug, 1.0)
            old_plug = _short(world) + "." + SCALE_ATTR
            for n in cmds.ls("*.gusScalePlug", objectsOnly=True, long=True) or []:     # chains remember it
                v = cmds.getAttr(n + ".gusScalePlug") or ""
                if v and v.split("|")[-1] == old_plug:
                    cmds.setAttr(n + ".gusScalePlug", _short(g) + "." + SCALE_ATTR, type="string")
            cmds.deleteAttr(world + "." + SCALE_ATTR)
        # 5.6.3: everything that read World_ctrl's own scale channels (the Hare's ribbons: 1268 plugs) reads
        # Global_ctrl's - World_ctrl stays at 1 from now on, so they'd never grow
        channels = 0
        done = set()
        for a in _SCALES + ("scale",):
            for dst in cmds.listConnections("%s.%s" % (world, a), source=False, destination=True, plugs=True,
                                            skipConversionNodes=True) or []:
                if dst.split(".")[0] in (_short(g), g) or dst in done or _is_constraint(dst):
                    continue
                done.add(dst)
                if a == "scale" and not _from(dst, world + ".scale"):
                    continue                       # a child's connection, listed under the compound
                src = g + "." + (SCALE_ATTR if a != "scale" else "scale")
                try:
                    cmds.connectAttr(src, dst, force=True)
                    channels += 1
                except RuntimeError:
                    pass
        _CHANNELS[0] = channels
        _hide(world, _SCALES)

        # Local under World, with what was under World
        kids = [k for k in cmds.listRelatives(world, children=True, type="transform", fullPath=True) or []
                if "constraint" not in cmds.nodeType(k).lower()]
        kid_ids = [utils.uuid(k) for k in kids]
        l_off, loc = _new_control(local_name, world, 0.8, world, wm)
        lid = utils.uuid(loc)
        for k in kid_ids:
            cmds.parent(utils.path(k), utils.path(lid))
        loc = utils.path(lid)
        _hide(loc, _SCALES)
        for n, level in ((g, "global"), (utils.path(wid), "world"), (loc, "local")):
            _tag(n, level)
    return {"global": utils.path(gid), "world": utils.path(wid), "local": utils.path(lid), "moved": len(kids),
            "readers": len(readers) + _CHANNELS[0]}
