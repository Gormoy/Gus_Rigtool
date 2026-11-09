"""
Follow: controls follow part of a driver's motion (lips follow the jaw, lids follow the eyes...).

For each follower control:
    <offset's parent>
      <ctrl>_followSpace      sits at the pivot (driver / picked point / the control) with the axes
                              (driver's / the control's own / world), never moves
        <ctrl>_follow         rotate / translate = driver's channels x weight
          <ctrl's offset>     (unchanged)
            <ctrl>
The weight is a 'follow' attribute (0-1) on the control, or '<ctrl>_follow' on the driver.
A joint that copies the control's channels (ribbon 'pivot on the control shape') gets the same
follow above its own offset group, so control and joint stay together.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import nodes as _nodes

TOOL = "Follow"
META = "gusFollow"           # on the follow group: "driver|weight plug|channels|space|md nodes"


def _short(n):
    return naming.short_name(n)


_long = _nodes.long_name


_parent = _nodes.parent_of


def control_of(group, stored=""):
    """5.0.8: the control a follow group carries - the stored name when it's still that control, else the
    control found under the group (renamed since: L_Mouth_fol_02_ctrl was Mouth_fol_02_ctrl). None if gone."""
    def name(n):                                            # short when unique, else the full path
        return _short(n) if len(cmds.ls(_short(n)) or []) == 1 else n
    found = cmds.ls(stored, long=True) if stored else []
    if len(found) == 1 and follow_group_of(found[0]) == _long(group):
        return stored
    best = None
    for t in cmds.listRelatives(group, allDescendents=True, type="transform", fullPath=True) or []:
        if cmds.listRelatives(t, shapes=True, type="nurbsCurve", noIntermediate=True) and \
                follow_group_of(t) == _long(group):
            if best is None or t.count("|") < best.count("|"):
                best = t
    return name(best) if best else None


def _parse(group):
    if not cmds.attributeQuery(META, node=group, exists=True):
        return None
    parts = (cmds.getAttr(group + "." + META) or "").split("|")
    if len(parts) < 5:
        return None
    return parts


def _meta(group):
    parts = _parse(group)
    if parts is None:
        return None
    m = {"driver": parts[0], "weight": parts[1], "channels": parts[2].split(","), "space": parts[3],
         "nodes": [p for p in parts[4].split(",") if p], "ctrl": parts[5] if len(parts) > 5 else "",
         "source": (parts[7] if len(parts) > 7 and parts[7] else parts[0]),
         "pivot": (parts[8] if len(parts) > 8 and parts[8] else "driver"),
         "axes": (parts[9] if len(parts) > 9 and parts[9] else "driver")}
    stored = m["ctrl"]
    try:
        now = control_of(group, stored)
    except (RuntimeError, ValueError):
        now = None
    m["stored_ctrl"] = stored
    if now and now != stored:                               # renamed since: the weight may sit on it too
        m["ctrl"] = now
        node, _dot, attr = m["weight"].partition(".")
        if stored and node == stored and not cmds.objExists(m["weight"]):
            m["weight"] = now + "." + attr
    elif not now and stored and not cmds.objExists(stored):
        m["ctrl"] = ""                                      # really gone
    return m


def update_record(group):
    """Write a renamed control (and its weight plug) back into the follow record. Returns True if it changed."""
    parts, m = _parse(group), _meta(group)
    if not parts or not m or not m["ctrl"] or len(parts) < 6:
        return False
    if parts[5] == m["ctrl"] and parts[1] == m["weight"]:
        return False
    parts[5], parts[1] = m["ctrl"], m["weight"]
    cmds.setAttr(group + "." + META, "|".join(parts), type="string")
    return True


def follow_group_of(ctrl):
    """The follow group above a control (between its offset and the space group), or None."""
    node = ctrl
    for _ in range(4):
        node = _parent(node)
        if not node:
            return None
        if cmds.attributeQuery(META, node=node, exists=True):
            return node
    return None


def remap_of(ctrl):
    """The remapValue node of a following control, or None."""
    g = follow_group_of(_long(ctrl) or ctrl)
    m = _meta(g) if g else None
    for n in (m or {}).get("nodes", []):
        if cmds.objExists(n) and cmds.nodeType(n) == "remapValue":
            return n
    return None


def describe(ctrl):
    """Plain words for how a control follows: 'no curve', 'curve on the weight', or the opening range."""
    rm = remap_of(ctrl)
    if not rm:
        return "no curve"
    src = cmds.listConnections(rm + ".inputValue", source=True, destination=False, plugs=True) or []
    if src and ".rotate" in src[0]:
        c = _long(ctrl) or ctrl
        try:
            a, b = cmds.getAttr(c + ".followStart"), cmds.getAttr(c + ".followEnd")
        except (RuntimeError, ValueError):
            a = b = "?"
        axis = src[0][-1]
        return "curve by jaw opening: %s to %s deg on %s" % (a, b, axis)
    return "curve on the weight"


def all_follows():
    """[(ctrl, driver, weight plug, channels, source)] for every follow in the scene. A control renamed since
    the follow was made is found under its follow group (and the record updated); one that's gone is listed
    as '(control not found, was X)'."""
    out = []
    for g in utils.nodes_with_attr(META, "transform"):
        try:
            m = _meta(g)
            if m and m["ctrl"] and m["ctrl"] != m["stored_ctrl"]:
                update_record(g)
        except Exception:
            m = None
        if not m:
            continue
        ctrl = m["ctrl"] or "(control not found, was %s)" % (m["stored_ctrl"] or _short(g))
        out.append((ctrl, m["driver"], m["weight"], m["channels"], m["source"]))
    return out


def _weight_plug(driver, ctrl, attr_on, default, share_twins, made):
    """The 0-1 weight attribute for ctrl (made if needed). attr_on 'driver': one 'follow'
    attribute on the driver, shared by all its followers."""
    if share_twins:
        from gus_rigtool.core import mirror_engine
        twin = mirror_engine.twin_of(ctrl)
        if twin:
            g = follow_group_of(twin)
            m = _meta(g) if g else None
            if m and m["driver"] == _short(driver):
                return m["weight"]
    node, attr = (ctrl, "follow") if attr_on == "control" else (driver, "follow")
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="double", minValue=0.0, maxValue=1.0,
                     defaultValue=float(default), keyable=True)
        made.append("%s.%s" % (_short(node), attr))
    cmds.setAttr("%s.%s" % (node, attr), float(default))
    return "%s.%s" % (_short(node), attr)


PIVOTS = ("driver", "picked", "control")
AXES = ("driver", "own", "world")


_wm = _nodes.world_matrix


def point_of(items):
    """World centre of objects and / or components (vertices, cvs...): the picked pivot."""
    pts = []
    for it in items or []:
        if "." in it:
            for c in cmds.ls(it, flatten=True) or []:
                v = cmds.xform(c, query=True, worldSpace=True, translation=True)
                pts += [v[i:i + 3] for i in range(0, len(v) - 2, 3)]
        elif cmds.objExists(it):
            pts.append(_wm(it)[12:15])
    if not pts:
        raise RuntimeError("no pivot picked: select a locator, joint, object or vertices and press << next to Pivot.")
    return [sum(p[i] for p in pts) / len(pts) for i in range(3)]


def _pivot_spec(pivot):
    """'driver', 'control' or 'x,y,z' (stored in the follow's meta)."""
    if pivot in ("driver", "control"):
        return pivot
    return ",".join("%.6g" % v for v in pivot)


def _frame(pivot, axes, src, ctrl, offset):
    """World matrix of a follow space: position from pivot ('driver' / 'control' / [x, y, z]),
    axes from 'driver' / 'own' (the offset it goes above) / 'world'. Scale 1."""
    if pivot == "driver":
        pos = _wm(src)[12:15]
    elif pivot == "control":
        pos = _wm(ctrl)[12:15]
    elif isinstance(pivot, str):
        pos = [float(v) for v in pivot.split(",")]
    else:
        pos = list(pivot)
    if axes == "world":
        rows = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    else:
        m = _wm(src if axes == "driver" else offset)
        rows = []
        for r in range(3):
            v = m[r * 4:r * 4 + 3]
            ln = sum(x * x for x in v) ** 0.5 or 1.0
            rows.append([x / ln for x in v])
    return rows[0] + [0.0] + rows[1] + [0.0] + rows[2] + [0.0] + list(pos) + [1.0]


def _insert(target_offset, label, driver, weight, channels, frame=None):
    """Space + follow groups above target_offset, driven by driver x weight. frame: the space's
    world matrix (None = at the driver). Returns the follow group."""
    dm = frame or _wm(driver)
    up = _parent(target_offset)
    space = cmds.createNode("transform", name=label + "_followSpace")
    cmds.xform(space, worldSpace=True, matrix=dm)
    if up:
        space = cmds.parent(space, up)[0]
    space = _long(space)
    fol = cmds.createNode("transform", name=label + "_follow", parent=space)
    fol = _long(fol)
    cmds.parent(target_offset, fol)                      # keeps its place in the world
    nodes = []
    for ch in channels:
        md = cmds.createNode("multiplyDivide", name=label + "_follow_" + ch)
        cmds.connectAttr("%s.%s" % (driver, ch), md + ".input1")
        for axis in "XYZ":
            cmds.connectAttr(weight, "%s.input2%s" % (md, axis))
        cmds.connectAttr(md + ".output", "%s.%s" % (fol, ch))
        nodes.append(md)
    return fol, space, nodes


REMAPS = ("none", "weight", "opening")


def _remap(label, ctrl, driver, weight, mode, axis, start, end, made):
    """
    A remapValue between the weight and the multiply (returns the plug the multiply uses).
    'weight' : in = the follow weight, out = the weight reshaped by the curve (edit it in the
               Attribute Editor).
    'opening': in = the driver's rotate<axis>; from followStart to followEnd (degrees, on the
               control) the weight grows from 0 to 'follow' along the curve.
    """
    rm = cmds.createNode("remapValue", name=label + "_follow_remap")
    if mode == "weight":
        cmds.connectAttr(weight, rm + ".inputValue")
        cmds.setAttr(rm + ".inputMin", 0.0)
        cmds.setAttr(rm + ".inputMax", 1.0)
        cmds.setAttr(rm + ".outputMin", 0.0)
        cmds.setAttr(rm + ".outputMax", 1.0)
    else:
        for attr, value in (("followStart", start), ("followEnd", end)):
            if not cmds.attributeQuery(attr, node=ctrl, exists=True):
                cmds.addAttr(ctrl, longName=attr, attributeType="double", defaultValue=float(value), keyable=True)
                made.append("%s.%s" % (_short(ctrl), attr))
            cmds.setAttr("%s.%s" % (ctrl, attr), float(value))
        cmds.connectAttr("%s.rotate%s" % (driver, axis), rm + ".inputValue")
        cmds.connectAttr(ctrl + ".followStart", rm + ".inputMin")
        cmds.connectAttr(ctrl + ".followEnd", rm + ".inputMax")
        cmds.setAttr(rm + ".outputMin", 0.0)
        cmds.connectAttr(weight, rm + ".outputMax")
    return rm, rm + ".outValue"


def _copiers(ctrl):
    """Joints that copy this control's channels (ribbon 'pivot on the control shape'): their offsets."""
    out = []
    for plug in ("translate", "rotate"):
        for dst in cmds.listConnections("%s.%s" % (ctrl, plug), source=False, destination=True) or []:
            dst = _long(dst)
            if dst and cmds.nodeType(dst) in ("joint", "transform") and _parent(dst):
                off = _parent(dst)
                if off not in out:
                    out.append(off)
    return out


def add(driver, followers, channels=("rotate",), attr_on="driver", weight=1.0, share_twins=False,
        remap="none", axis="X", start=0.0, end=30.0, source=None, pivot="driver", axes="driver"):
    """Make followers follow the driver. remap: 'none', 'weight' (shape the weight with a curve) or
    'opening' (the weight grows with the source's rotate<axis> from start to end degrees).
    source: the node whose rotation / translation is followed and whose pivot is used (e.g. the
    jaw joint); None = the driver. The driver holds the weight attribute.
    pivot: 'driver' (its pivot), 'control' (each follower's own place) or [x, y, z] (see point_of).
    axes: 'driver' (turn like the driver), 'own' (the follower's axes - e.g. eyelids) or 'world'.
    Returns (done, skipped)."""
    if axes not in AXES:
        raise RuntimeError("axes must be one of %s." % ", ".join(AXES))
    if isinstance(pivot, str) and pivot not in ("driver", "control"):
        raise RuntimeError("pivot must be 'driver', 'control' or a point [x, y, z].")
    driver = _long(driver)
    if not driver:
        raise RuntimeError("the driver doesn't exist.")
    src = _long(source) if source else driver
    if not src:
        raise RuntimeError("'Rotation from' node '%s' doesn't exist." % source)
    moved = [a for a in ("translate", "rotate") if a in channels and
             any(abs(v) > 1e-4 for v in cmds.getAttr(src + "." + a)[0])]
    if moved:
        raise RuntimeError("put %s at rest first (its %s is not 0), so the followers don't jump."
                           % (_short(src), " and ".join(moved)))
    done, skipped = [], []
    with utils.undo_chunk("gusrigFollowAdd"):
        for ctrl in followers:
            ctrl = _long(ctrl)
            if not ctrl or ctrl in (driver, src):
                continue
            if follow_group_of(ctrl):
                skipped.append(_short(ctrl) + " (already follows)")
                continue
            offset = _parent(ctrl)
            if not offset:
                skipped.append(_short(ctrl) + " (no offset group above it)")
                continue
            made = []
            plug = _weight_plug(driver, ctrl, attr_on, weight, share_twins, made)
            label = _short(ctrl)
            pre = []
            use = plug
            if remap in ("weight", "opening"):
                rm, use = _remap(label, ctrl, src, plug, remap, axis.upper(), start, end, made)
                pre.append(rm)
            fol, space, nodes = _insert(offset, label, src, use, channels,
                                        _frame(pivot, axes, src, ctrl, offset))
            nodes = pre + nodes
            extra = []
            for i, off in enumerate(_copiers(_long(ctrl.split("|")[-1]) or ctrl)):
                f2, s2, n2 = _insert(off, "%s_jnt%d" % (label, i), src, use, channels,
                                     _frame(pivot, axes, src, ctrl, off))
                extra += [_short(s2)] + n2
            cmds.addAttr(fol, longName=META, dataType="string")
            cmds.setAttr(fol + "." + META, "|".join([
                _short(driver), plug, ",".join(channels), _short(space), ",".join(nodes + extra),
                _short(ctrl), ",".join(made), _short(src) if src != driver else "",
                _pivot_spec(pivot), axes]), type="string")
            done.append(_short(ctrl) + (" (made %s)" % _short(pre[0]) if pre else ""))
    return done, skipped


def remove(controls):
    """Stop controls following: their groups, nodes and weight attributes go; the controls go back
    to where they sit when the driver is at rest."""
    count = 0
    with utils.undo_chunk("gusrigFollowRemove"):
        for ctrl in controls:
            ctrl = _long(ctrl)
            g = follow_group_of(ctrl) if ctrl else None
            m = _meta(g) if g else None
            if not m:
                continue
            raw = cmds.getAttr(g + "." + META).split("|")
            made = [p for p in (raw[6] if len(raw) > 6 else "").split(",") if p]
            if m["weight"] == "%s.follow" % m["driver"] and m["weight"] not in made:
                made.append(m["weight"])     # the shared one: goes with the last follow that uses it
            spaces = [m["space"]] + [n for n in m["nodes"] if n.endswith("_followSpace")]
            for node in m["nodes"]:
                if cmds.objExists(node) and cmds.nodeType(node) in ("multiplyDivide", "remapValue"):
                    cmds.delete(node)
            for sp in spaces:                               # back to rest, then lift the offsets out
                sp = _long(sp)
                if not sp:
                    continue
                fol = (cmds.listRelatives(sp, children=True, type="transform", fullPath=True) or [None])[0]
                up = _parent(sp)
                if fol:
                    for attr in ("translate", "rotate"):
                        cmds.setAttr(fol + "." + attr, 0, 0, 0)
                    for kid in cmds.listRelatives(fol, children=True, type="transform", fullPath=True) or []:
                        if up:
                            cmds.parent(kid, up)
                        else:
                            cmds.parent(kid, world=True)
                cmds.delete(sp)
            for plug in made:
                node, attr = plug.split(".", 1)
                if cmds.objExists(plug) and not any(f[2] == plug for f in all_follows()):
                    cmds.deleteAttr(node, attribute=attr)
            count += 1
    return count


def _spaces(m):
    return [x for x in [_long(m["space"])] + [_long(n) for n in m["nodes"] if n.endswith("_followSpace")] if x]


def move_pivot(controls, pivot="driver", axes="driver"):
    """Move the follow of these controls to a new pivot / axes. Controls and joints stay where
    they are (no jump, skin untouched). The driver must be at rest. Returns the count."""
    if axes not in AXES:
        raise RuntimeError("axes must be one of %s." % ", ".join(AXES))
    count = 0
    with utils.undo_chunk("gusrigFollowPivot"):
        for ctrl in controls:
            ctrl = _long(ctrl)
            g = follow_group_of(ctrl) if ctrl else None
            m = _meta(g) if g else None
            if not m:
                continue
            src = _long(m["source"]) or _long(m["driver"])
            if not src:
                raise RuntimeError("%s: its driver %s is gone." % (_short(ctrl), m["source"]))
            for sp in _spaces(m):
                fol = (cmds.listRelatives(sp, children=True, type="transform", fullPath=True) or [None])[0]
                if not fol:
                    continue
                if any(abs(v) > 1e-4 for a in ("translate", "rotate") for v in cmds.getAttr(fol + "." + a)[0]):
                    raise RuntimeError("put %s at rest first (follow of %s is not 0), so nothing jumps."
                                       % (_short(src), _short(ctrl)))
                kids = cmds.listRelatives(fol, children=True, type="transform", fullPath=True) or []
                keep = [(k, _wm(k)) for k in kids]
                cmds.xform(sp, worldSpace=True, matrix=_frame(pivot, axes, src, ctrl, kids[0] if kids else sp))
                for k, wm in keep:
                    cmds.xform(k, worldSpace=True, matrix=wm)
            raw = cmds.getAttr(g + "." + META).split("|")
            raw += [""] * (10 - len(raw))
            raw[8], raw[9] = _pivot_spec(pivot), axes
            cmds.setAttr(g + "." + META, "|".join(raw), type="string")
            count += 1
    return count


def forget_space(node):
    """node is about to be deleted: if it is (or holds) a follow space made for a copy joint, delete the
    nodes that drive its follow group and drop it from its follow's record."""
    node = _long(node)
    if not node:
        return 0
    groups = [node] + (cmds.listRelatives(node, allDescendents=True, type="transform", fullPath=True) or [])
    spaces = [_short(g) for g in groups if _short(g).endswith("_followSpace")]
    if not spaces:
        return 0
    dropped = []
    for sp in spaces:
        fol = (cmds.listRelatives(_long(sp), children=True, type="transform", fullPath=True) or [None])[0]
        for ch in ("translate", "rotate"):
            for md in (cmds.listConnections("%s.%s" % (fol, ch), source=True, destination=False) or []) if fol else []:
                if cmds.objExists(md) and cmds.nodeType(md) == "multiplyDivide":
                    dropped.append(_short(md))
                    cmds.delete(md)
    gone = set(spaces + dropped)
    for g in utils.nodes_with_attr(META, "transform"):
        raw = (cmds.getAttr(g + "." + META) or "").split("|")
        if len(raw) < 5:
            continue
        keep = [n for n in raw[4].split(",") if n and n not in gone]
        if len(keep) != len([n for n in raw[4].split(",") if n]):
            raw[4] = ",".join(keep)
            cmds.setAttr(g + "." + META, "|".join(raw), type="string")
    return len(spaces)


def settings_of(ctrl):
    """Everything add() needs to make this control's follow again: {driver, source, channels, attr_on, weight,
    remap, axis, start, end, pivot, axes}, or None."""
    c = _long(ctrl) or ctrl
    g = follow_group_of(c)
    m = _meta(g) if g else None
    if not m:
        return None
    attr_on = "driver" if m["weight"] == "%s.follow" % m["driver"] else "control"
    try:
        weight = cmds.getAttr(m["weight"])
    except (RuntimeError, ValueError):
        weight = 1.0
    remap, axis, start, end = "none", "X", 0.0, 30.0
    rm = remap_of(c)
    if rm:
        srcs = cmds.listConnections(rm + ".inputValue", source=True, destination=False, plugs=True) or []
        if srcs and ".rotate" in srcs[0]:
            remap, axis = "opening", srcs[0][-1]
            try:
                start, end = cmds.getAttr(c + ".followStart"), cmds.getAttr(c + ".followEnd")
            except (RuntimeError, ValueError):
                pass
        else:
            remap = "weight"
    pivot = m.get("pivot", "driver")
    if pivot not in ("driver", "control"):
        pivot = [float(v) for v in pivot.split(",")]
    return {"driver": m["driver"], "source": m["source"], "channels": list(m["channels"]), "attr_on": attr_on,
            "weight": weight, "remap": remap, "axis": axis, "start": start, "end": end, "pivot": pivot,
            "axes": m.get("axes", "driver")}


def _add_with(spec, ctrl):
    return add(spec["driver"], [ctrl], tuple(spec["channels"]), spec["attr_on"], spec["weight"], False,
               spec["remap"], spec["axis"], spec["start"], spec["end"],
               spec["source"] if spec["source"] != spec["driver"] else None, spec["pivot"], spec["axes"])


def _at_rest(spec):
    for node in {spec["driver"], spec["source"]}:
        n = _long(node)
        if n and any(abs(v) > 1e-4 for a in ("translate", "rotate") for v in cmds.getAttr(n + "." + a)[0]):
            raise RuntimeError("put %s at rest first, so nothing jumps." % _short(n))


def update(controls, **changes):
    """Change existing follows in place (weight, channels, remap / axis / start / end, pivot, axes, driver,
    source, attr_on): each is made again with the new values, no jump. Returns the count."""
    done = 0
    with utils.undo_chunk("gusrigFollowUpdate"):
        for ctrl in controls:
            spec = settings_of(ctrl)
            if not spec:
                continue
            spec.update({k: v for k, v in changes.items() if v is not None})
            _at_rest(spec)
            short = _short(_long(ctrl) or ctrl)
            remove([ctrl])
            _add_with(spec, _long(short))
            done += 1
    return done


def copy(source, targets, replace=True):
    """targets follow like source does (same driver, weight, curve, pivot rule, axes). Returns (done, skipped)."""
    spec = settings_of(source)
    if not spec:
        raise RuntimeError("%s doesn't follow anything." % _short(source))
    _at_rest(spec)
    done, skipped = [], []
    with utils.undo_chunk("gusrigFollowCopy"):
        for t in targets:
            short = _short(_long(t) or t)
            if follow_group_of(_long(t) or t):
                if not replace:
                    skipped.append(short + " (already follows)")
                    continue
                remove([t])
            d, sk = _add_with(spec, _long(short))
            done += d
            skipped += sk
    return done, skipped


def set_weight(controls, value):
    """Set the follow weight of these controls (their own, or the one on the driver)."""
    done = 0
    for ctrl in controls:
        g = follow_group_of(_long(ctrl) or ctrl)
        m = _meta(g) if g else None
        if m and cmds.objExists(m["weight"]):
            cmds.setAttr(m["weight"], float(value))
            done += 1
    return done
