"""
Existing rigs: work with any rig, part by part.

  scan(nodes)          what a part is made of: controls, joints, IK handles, pole vectors, IK/FK switch
                       attributes, skinned meshes, and what in the scene hangs from it.
  adopt(...)           keep a part as it is: it joins the module list as 'adopted' (IK/FK match,
                       Publish, mirror pose, Gus Animtool) - nothing in the scene moves.
  place_on_joints(...) a builder module whose guides sit on the old joints (rebuild a part).
  hookups / replace    after the new part is built: the skin moves from the old joints to the new ones,
                       what hung from the old part is reconnected, the old part goes into legacy_grp.
  remove_backup()      delete legacy_grp when you're happy.
"""

import json

import maya.cmds as cmds

from gus_rigtool.builder import guides, limb, mathx, modules, names
from gus_rigtool.core import mirror_engine as me
from gus_rigtool.core import nodes as _nodes
from gus_rigtool.core import naming, utils

TOOL = "Existing rig"
ADOPT_ATTR = "gusAdopted"
TAUGHT_NODE = "gusAnim_taught"            # shared with Gus Animtool (same data)
LEGACY = "legacy_grp"
SWITCH_WORDS = ("ikfk", "fkik", "ik_fk", "fk_ik", "ikblend", "fkblend", "ik_blend", "blend", "ikfkswitch")
CONSTRAINTS = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint",
               "poleVectorConstraint")
UCURVES = ("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT")
SKIP_TYPES = ("skinCluster", "dagPose", "objectSet", "displayLayer", "nodeGraphEditorInfo", "hyperLayout",
              "network")
SKIP_ATTRS = ("message", "instObjGroups", "drawOverride", "lockInfluenceWeights", "objectColorRGB", "bindPose")


def _short(n):
    return naming.short_name(n) if n else n


_long = _nodes.unique_long


def _is_ctrl(n):
    return cmds.nodeType(n) == "transform" and bool(
        cmds.listRelatives(n, shapes=True, type="nurbsCurve", fullPath=True))


# ===========================================================================
# scan
# ===========================================================================

def _below(nodes):
    out = []
    for n in nodes:
        out.append(n)
        out += cmds.listRelatives(n, allDescendents=True, type="transform", fullPath=True) or []
    seen = set()
    return [x for x in out if not (x in seen or seen.add(x))]


def driven_joints(ctrl):
    """Joints a control moves: constraints / direct connections from it, and joints right under it."""
    out = []
    for con in set(cmds.listConnections(ctrl, source=False, destination=True, type="constraint") or []):
        if cmds.nodeType(con) not in CONSTRAINTS:
            continue
        for d in cmds.listConnections(con, source=False, destination=True) or []:
            d = _long(d)
            if d and cmds.nodeType(d) == "joint" and d not in out:
                out.append(d)
    for a in ("rotate", "translate"):
        for d in cmds.listConnections(ctrl + "." + a, source=False, destination=True, skipConversionNodes=True) or []:
            d = _long(d)
            if d and cmds.nodeType(d) == "joint" and d not in out:
                out.append(d)
    for j in cmds.listRelatives(ctrl, children=True, type="joint", fullPath=True) or []:
        if j not in out:
            out.append(j)
    return out


def switch_attrs(ctrls):
    """[(control, attr)] that look like an IK/FK switch."""
    out = []
    for c in ctrls:
        for a in cmds.listAttr(c, keyable=True, userDefined=True) or []:
            low = a.lower().replace(" ", "")
            if any(w in low for w in SWITCH_WORDS):
                out.append((c, a))
    return out


def _ik_handles(nodes):
    """IK handles that belong to the part: under it, or constrained / parented to its controls."""
    found = []
    inside = set(nodes)
    for h in cmds.ls(type="ikHandle", long=True) or []:
        parent = (cmds.listRelatives(h, parent=True, fullPath=True) or [None])[0]
        sources = set()
        for con in set(cmds.listConnections(h, source=True, destination=False, type="constraint") or []):
            for t in cmds.listConnections(con + ".target", source=True, destination=False) or []:
                sources.add(_long(t))
        ancestors = []
        p = parent
        while p:
            ancestors.append(p)
            p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
        owner = next((a for a in ancestors if a in inside and _is_ctrl(a)), None) or \
            next((s for s in sources if s in inside and _is_ctrl(s)), None)
        if owner or h in inside:
            found.append((h, owner))
    return found


def _ik_info(handle):
    start = cmds.ikHandle(handle, query=True, startJoint=True)
    eff = cmds.ikHandle(handle, query=True, endEffector=True)
    end = None
    for c in cmds.listConnections(eff + ".translateX", source=True, destination=False) or []:
        if cmds.nodeType(c) == "joint":
            end = c
    chain = []
    if start and end:
        j = _long(end)
        start_l = _long(start)
        while j:
            chain.insert(0, j)
            if j == start_l:
                break
            j = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
    pv = None
    for con in set(cmds.listConnections(handle, source=True, destination=False, type="poleVectorConstraint")
                   or []):
        for t in cmds.listConnections(con + ".target", source=True, destination=False) or []:
            pv = _long(t)
    return chain, pv


def scan(nodes=None):
    """What the selected part is made of. nodes: controls, joints or top groups (default: the selection)."""
    nodes = nodes or cmds.ls(selection=True, long=True, type="transform") or []
    if not nodes:
        raise RuntimeError("select the part: its controls, joints or top group.")
    every = _below(nodes)
    ctrls = [n for n in every if _is_ctrl(n)]
    joints = [n for n in every if cmds.nodeType(n) == "joint"]
    for c in ctrls:
        for j in driven_joints(c):
            if j not in joints:
                joints.append(j)
    limbs = []
    for h, owner in _ik_handles(every):
        chain, pv = _ik_info(h)
        limbs.append({"handle": h, "ik": owner, "pv": pv if pv in every else pv, "ik_joints": chain})
    switches = switch_attrs(ctrls)
    skins = _skins_on(joints)
    return {"nodes": nodes, "controls": ctrls, "joints": joints, "limbs": limbs, "switches": switches,
            "skins": skins, "hookups": hookups(joints + ctrls, every)}


def _skins_on(joints):
    out = []
    for skin in cmds.ls(type="skinCluster") or []:
        infl = set(utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or [])
        if infl & set(joints):
            out.append(skin)
    return out


def report(info):
    """Readable text of a scan."""
    L = ["Controls (%d):" % len(info["controls"])]
    L += ["  " + _short(c) for c in info["controls"][:40]]
    if len(info["controls"]) > 40:
        L.append("  ... and %d more" % (len(info["controls"]) - 40))
    L += ["", "Joints they move (%d):" % len(info["joints"])]
    L += ["  " + _short(j) for j in info["joints"][:40]]
    L += ["", "IK limbs (%d):" % len(info["limbs"])]
    for lb in info["limbs"]:
        L.append("  IK control %s, pole vector %s, IK joints: %s" % (
            _short(lb["ik"]) or "?", _short(lb["pv"]) or "-", ", ".join(_short(j) for j in lb["ik_joints"])))
    L += ["", "IK/FK switch attributes:"] + ["  %s.%s" % (_short(c), a) for c, a in info["switches"]] or ["  none"]
    L += ["", "Skins using these joints: " + (", ".join(info["skins"]) or "none")]
    L += ["", "Hanging from this part (outside it):"] + (hookup_lines(info["hookups"]) or ["  nothing"])
    return "\n".join(L)


# ===========================================================================
# hook-ups: what outside the part depends on it
# ===========================================================================

def hookups(part_nodes, inside=None):
    """[{'kind', 'node', 'what', 'detail'}]: children, constraints, driven keys and other connections from
    the part's nodes to things outside it."""
    region = set(inside or [])                      # the part's own hierarchy (under its top groups)
    inside = region | set(part_nodes)
    out = []
    for n in part_nodes:
        if not cmds.objExists(n):
            continue
        for kid in cmds.listRelatives(n, children=True, type="transform", fullPath=True) or []:
            if kid not in inside and not _in(kid, region):
                if cmds.nodeType(kid) in CONSTRAINTS and n in set(_long(d) for d in cmds.listConnections(
                        kid, source=False, destination=True) or []):
                    continue                         # the node's own constraint: it goes with the old part
                out.append({"kind": "child", "node": n, "what": kid, "detail": ""})
        for con in set(cmds.listConnections(n, source=False, destination=True, type="constraint") or []):
            con = _long(con)
            if not con or con in inside or _in(con, region) or cmds.nodeType(con) not in CONSTRAINTS:
                continue
            driven = set(_long(d) for d in cmds.listConnections(con, source=False, destination=True) or [])
            driven.discard(con)
            if any(d and d not in inside for d in driven):
                out.append({"kind": "constraint", "node": n, "what": con,
                            "detail": ", ".join(sorted(_short(d) for d in driven if d))})
        for src, dst in _pairs(cmds.listConnections(n, source=False, destination=True, plugs=True,
                                                    connections=True, skipConversionNodes=True) or []):
            dn = _long(dst.split(".")[0])
            if not dn or dn in inside or _in(dn, region):
                continue
            kind = cmds.nodeType(dn)
            if kind in CONSTRAINTS or kind in SKIP_TYPES or kind.startswith("ikHandle"):
                continue
            if src.split(".", 1)[1].split("[")[0] in SKIP_ATTRS:
                continue
            out.append({"kind": "sdk" if kind in UCURVES else "connection", "node": n, "what": dst,
                        "detail": src.split(".", 1)[1]})
    return out


def _pairs(flat):
    return list(zip(flat[0::2], flat[1::2]))


def _in(node, inside):
    return any(node.startswith(x + "|") for x in inside if x)


def hookup_lines(items):
    words = {"child": "parented under", "constraint": "constraint target of", "sdk": "drives the driven key",
             "connection": "connected to"}
    out = []
    for h in items:
        if h["kind"] == "constraint":
            out.append("  %s is a target of %s (moves %s)" % (_short(h["node"]), _short(h["what"]), h["detail"]))
        elif h["kind"] == "child":
            out.append("  %s %s %s" % (_short(h["what"]), words["child"], _short(h["node"])))
        else:
            out.append("  %s.%s %s %s" % (_short(h["node"]), h["detail"], words[h["kind"]],
                                          _short(h["what"].split(".")[0]) + "." + h["what"].split(".", 1)[1]))
    return out


# ===========================================================================
# adopt: keep a part as it is, known by the tool
# ===========================================================================

def adopted_groups():
    return utils.nodes_with_attr(ADOPT_ATTR, "transform")


def read_adopted(group):
    try:
        data = json.loads(cmds.getAttr(group + "." + ADOPT_ATTR) or "{}")
    except (ValueError, RuntimeError):
        data = {}
    side, name = data.get("side", "C"), data.get("name", _short(group))
    return {"group": group, "type": "adopted", "name": name, "side": side, "id": "%s:%s" % (side, name),
            "settings": data, "guides": {}}


def is_adopted(group):
    return bool(group and cmds.objExists(group) and cmds.attributeQuery(ADOPT_ATTR, node=group, exists=True))


def taught_data():
    if not cmds.objExists(TAUGHT_NODE):
        return {}
    try:
        return json.loads(cmds.getAttr(TAUGHT_NODE + ".limbs") or "{}")
    except (ValueError, RuntimeError):
        return {}


def _write_taught(data):
    if not cmds.objExists(TAUGHT_NODE):
        cmds.createNode("network", name=TAUGHT_NODE)
        cmds.addAttr(TAUGHT_NODE, longName="limbs", dataType="string")
    cmds.setAttr(TAUGHT_NODE + ".limbs", json.dumps(data, sort_keys=True), type="string")


def _strip(n):
    return _short(n).split(":")[-1] if n else ""


def teach_limb(name, fk, joints, ik, pv, switch, fk_value=0.0, ik_value=1.0):
    """Save an IK/FK limb (3 FK controls, the 3 joints they move, IK control, pole vector, 'node.attr').
    The rig must be in a pose where FK and IK line up. Same data as Gus Animtool's Teach a limb."""
    if len(fk) != 3 or len(joints) != 3:
        raise RuntimeError("limb '%s': 3 FK controls and 3 joints (upper, middle, end), please." % name)
    if not ik:
        raise RuntimeError("limb '%s': the IK control is missing." % name)
    if switch and not cmds.objExists(switch):
        raise RuntimeError("limb '%s': the switch attribute '%s' doesn't exist." % (name, switch))
    if abs(float(fk_value) - float(ik_value)) < 1e-9:
        raise RuntimeError("limb '%s': the FK and IK values of the switch must differ." % name)
    js = [limb.world(j) for j in joints]
    d = {"fk": [_strip(x) for x in fk], "joints": [_strip(x) for x in joints], "ik": _strip(ik),
         "pv": _strip(pv) if pv else "",
         "switch": (_strip(switch.split(".")[0]) + "." + switch.split(".", 1)[1]) if switch else "",
         "fk_value": float(fk_value), "ik_value": float(ik_value),
         "fk_off": [me.mul(limb.world(c), me.inverse(j)) for c, j in zip(fk, js)],
         "ik_off": me.mul(limb.world(ik), me.inverse(js[2]))}
    data = taught_data()
    data[name] = d
    _write_taught(data)
    return d


def suggest_spaces(info):
    """{label: control} a scanned part could offer as spaces: hips (moves its first joint), chest (its
    last), cog (a control above both), and the scene's world / root controls by name."""
    out = {}
    ctrls = info.get("controls") or []
    joints = sorted(info.get("joints") or [], key=lambda j: j.count("|"))
    by_joint = {}
    for c in ctrls:
        for j in driven_joints(c):
            by_joint.setdefault(j, c)
    driving = [j for j in joints if j in by_joint]
    if driving:
        hips, chest = by_joint[driving[0]], by_joint[driving[-1]]
        out["hips"] = hips
        if chest != hips:
            out["chest"] = chest
            p = (cmds.listRelatives(hips, parent=True, fullPath=True) or [None])[0]
            while p:
                if _is_ctrl(p) and chest.startswith(p + "|"):
                    out["cog"] = p
                    break
                p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
    world = root = None
    for c in cmds.ls(type="nurbsCurve", long=True) or []:
        t_ = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0]
        low = _strip(t_).lower() if t_ else ""
        if not low:
            continue
        if "world" in low and not world:
            world = t_
        elif any(w in low for w in ("root", "main", "global", "master")) and not root:
            root = t_
    if root:
        out["root"] = root
        if world:
            out["world"] = world
    elif world:
        out["root"] = world                  # one top control: it's the root the limbs follow
    return {k: v for k, v in out.items() if v}


def spaces_text(spaces):
    return ", ".join("%s = %s" % (k, _strip(v)) for k, v in sorted(spaces.items()))


def parse_spaces(text):
    out = {}
    for item in (text or "").replace(";", ",").split(","):
        if "=" in item:
            k, v = [x.strip() for x in item.split("=", 1)]
            if k and v:
                out[k] = v
    return out


def adopt(name, side, controls, limbs=None, joints=None, spaces=None):
    """A hand-made part joins the module list as 'adopted'. limbs: [dict(name, fk, joints, ik, pv, switch,
    fk_value, ik_value)]. joints: {part name: joint} other builder modules can hang from (attach).
    spaces: {label: node} builder modules can follow (chest, cog, root...), found by their label."""
    if not name:
        raise RuntimeError("give the part a name.")
    if not controls:
        raise RuntimeError("no controls: select the part and Scan it first.")
    for g in adopted_groups():
        if read_adopted(g)["id"] == "%s:%s" % (side, name):
            raise RuntimeError("there is already an adopted part '%s' on side %s." % (name, side))
    with utils.undo_chunk("gusrigAdopt"):
        taught = []
        for lb in limbs or []:
            teach_limb(lb["name"], lb["fk"], lb["joints"], lb["ik"], lb.get("pv"), lb.get("switch"),
                       lb.get("fk_value", 0.0), lb.get("ik_value", 1.0))
            taught.append(lb["name"])
        jmap = dict(joints or {})
        if not jmap:
            for c in controls:
                for j in driven_joints(c):
                    jmap.setdefault(_strip(j), _strip(j))
        sp = {}
        for label, node in (spaces or {}).items():
            found = cmds.ls(node, long=True) or []
            if len(found) != 1:
                raise RuntimeError("space '%s': %s." % (label, ("'%s' not found" % node) if not found else
                                                          "several nodes are called '%s'" % node))
            sp[label] = _strip(found[0])
        data = {"name": name, "side": side, "controls": [_strip(c) for c in controls], "limbs": taught,
                "spaces": sp}
        group = cmds.createNode("transform", name=names.make(side, name + "_adopted", "grp"))
        group = cmds.parent(group, guides.top_group())[0]
        group = cmds.ls(group, long=True)[0]
        cmds.addAttr(group, longName=ADOPT_ATTR, dataType="string")
        cmds.setAttr(group + "." + ADOPT_ATTR, json.dumps(data, sort_keys=True), type="string")
        # what builder modules can hang from (attach 'name:part'), like a built module's outputs
        cmds.addAttr(group, longName="gusOutputs", dataType="string")
        cmds.setAttr(group + ".gusOutputs", json.dumps({"joints": jmap, "spaces": sp, "follow": None,
                                                        "settings_ctrl": None, "created": []}), type="string")
    utils.info(TOOL, "adopted '%s' (%s): %d controls, %d IK/FK limb(s)%s." % (
        name, side, len(controls), len(taught), (", spaces: " + ", ".join(sorted(sp))) if sp else ""))
    return group


def forget_adopted(group):
    info = read_adopted(group)
    data = taught_data()
    for n in info["settings"].get("limbs", []):
        data.pop(n, None)
    _write_taught(data)
    cmds.delete(group)
    utils.info(TOOL, "'%s' is no longer adopted (nothing in the rig changed)." % info["name"])


def adopted_controls():
    out = []
    for g in adopted_groups():
        for c in read_adopted(g)["settings"].get("controls", []):
            found = cmds.ls(c, long=True) or []
            if len(found) == 1 and found[0] not in out:
                out.append(found[0])
    return out


# ---------------------------------------------------------------------------
# taught limbs: IK/FK match with no jump (same maths as Gus Animtool)
# ---------------------------------------------------------------------------

def taught_of(node):
    name = _strip(node)
    ns = _short(node).rsplit(":", 1)[0] + ":" if ":" in _short(node) else ""
    for limb_name, d in taught_data().items():
        if name in d["fk"] + [d["ik"], d.get("pv", ""), d.get("switch", "").split(".")[0]]:
            return limb_name, d, ns
    return None


def _r(name, ns):
    return _long(ns + name) or _long(name) if name else None


def taught_match(node, to):
    """to 'fk' / 'ik' / 'toggle' for the taught limb node belongs to. Returns the mode used, or None."""
    found = taught_of(node)
    if not found:
        return None
    _name, d, ns = found
    plug = None
    if d.get("switch"):
        sw = _r(d["switch"].split(".")[0], ns)
        plug = sw + "." + d["switch"].split(".", 1)[1] if sw else None
    if to == "toggle":
        v = cmds.getAttr(plug) if plug else d["fk_value"]
        to = "ik" if abs(v - d["fk_value"]) <= abs(v - d["ik_value"]) else "fk"
    js = [limb.world(_r(j, ns)) for j in d["joints"]]
    if to == "fk":
        for c, j, off in zip(d["fk"], js, d["fk_off"]):
            limb.set_world(_r(c, ns), me.mul(off, j), translate=False)
        if plug:
            cmds.setAttr(plug, d["fk_value"])
    else:
        limb.set_world(_r(d["ik"], ns), me.mul(d["ik_off"], js[2]))
        pv = _r(d.get("pv"), ns)
        if pv:
            a, b, c = [mathx.position(m) for m in js]
            cmds.xform(pv, worldSpace=True, translation=mathx.pole_position(a, b, c))
        if plug:
            cmds.setAttr(plug, d["ik_value"])
    return to


# ===========================================================================
# place a builder module on old joints
# ===========================================================================

# the guide roles that sit on joints, in the order you select the joints (None: worked out per module)
JOINT_ROLES = {
    "root": ["root"],
    "leg": ["femur", "tibia", "ankle", "ball", "ball_end"],
    "arm": ["clavicle", "humerus", "radius", "wrist", "hand"],
    "back_leg": ["femur", "tibia", "metatarsus", "ball", "toe", "ball_end"],
    "front_leg": ["scapula", "humerus", "radius", "metacarpus", "ball", "toe", "ball_end"],
    "spine": None, "neck": None, "chain": None,
}
OPTIONAL_END = {"leg": "ball_end", "arm": "hand", "back_leg": "ball_end", "front_leg": "ball_end"}


def placeable():
    return [t for t in modules.ORDER if t in JOINT_ROLES]


def joint_hint(mtype):
    roles = JOINT_ROLES.get(mtype)
    if mtype == "spine":
        return "hips, then the spine joints up to the chest (3 or more)"
    if mtype == "neck":
        return "the neck joints, then the head (2 or more)"
    if mtype == "chain":
        return "the chain's joints, root to tip (2 or more)"
    if not roles:
        return "not supported"
    end = OPTIONAL_END.get(mtype)
    return ", ".join(roles) + ((" (%s optional)" % end) if end else "")


def _settings_for(mod, mtype, side, n_joints, name):
    s = mod.complete(mod.default_settings(side))
    if mtype == "spine":
        if n_joints < 3:
            raise RuntimeError("spine: select the hips and at least 2 spine joints.")
        s["options"]["joint_count"] = n_joints - 1
    elif mtype == "neck":
        if n_joints < 2:
            raise RuntimeError("neck: select at least 1 neck joint and the head.")
        s["options"]["joint_count"] = n_joints - 1
    elif mtype == "chain":
        if n_joints < 2:
            raise RuntimeError("chain: select at least 2 joints.")
        s["options"]["end_joint"] = True
        s["names"]["count"] = n_joints - 1
        s["names"]["name"] = s["names"].get("name") or name
    return mod.complete(s)


def role_order(mod, mtype, s, side, height):
    specs = mod.guide_specs(s, height, side)
    if JOINT_ROLES.get(mtype):
        return list(JOINT_ROLES[mtype]), specs
    joints = [sp["role"] for sp in specs if sp.get("kind") != "pivot"]
    if mtype == "spine":
        return ["hips"] + joints, specs
    return joints, specs


def placement(mtype, side, name, joints, height):
    """(settings, {role: position}, {role: old joint}) for a module whose guides sit on the joints."""
    if mtype not in JOINT_ROLES:
        raise RuntimeError("%s can't be placed on joints." % modules.MODULES[mtype].LABEL)
    mod = modules.MODULES[mtype]
    side = side if side in mod.SIDES else mod.SIDES[0]
    s = _settings_for(mod, mtype, side, len(joints), name)
    roles, specs = role_order(mod, mtype, s, side, height)
    end = OPTIONAL_END.get(mtype)
    if len(joints) not in (len(roles), len(roles) - (1 if end else 0)):
        raise RuntimeError("%s: select %s - you selected %d joint(s)." % (mod.LABEL, joint_hint(mtype), len(joints)))
    pos = {r: cmds.xform(j, query=True, worldSpace=True, translation=True) for r, j in zip(roles, joints)}
    on = {r: _strip(j) for r, j in zip(roles, joints)}
    if end and end not in pos:                       # no end joint: carry on the last bone by half its length
        a, b = pos[roles[-3]], pos[roles[-2]]
        pos[end] = mathx.add(b, mathx.scale(mathx.sub(b, a), 0.5))
    by_role = {sp["role"]: sp for sp in specs}
    for sp in specs:                                 # pivots (heel, paw sides...) follow their parent guide
        r = sp["role"]
        if r in pos:
            continue
        parent = sp.get("parent")
        if parent in pos and parent in by_role:
            delta = mathx.sub(pos[parent], by_role[parent]["pos"])
            pos[r] = mathx.add(sp["pos"], delta)
    s["placed_on"] = on
    s["placed_uuid"] = {r: (cmds.ls(j, uuid=True) or [""])[0] for r, j in zip(roles, joints)}   # names may repeat
    s["placed_pos"] = {r: pos[r] for r in on}
    return s, pos, on


def twin_joints(joints):
    """The other side's joints, by name (your side pairs): L_index_01 -> R_index_01."""
    from gus_rigtool.core import sides
    out = []
    for j in joints:
        twin = naming.mirror_name(_short(j), sides.default_pairs())
        found = cmds.ls(twin, long=True) or [] if twin else []
        if len(found) != 1:
            raise RuntimeError("no twin for %s (%s)." % (_short(j), "no side in its name" if not twin else
                                                         ("'%s' not found" % twin) if not found else
                                                         "several nodes are called '%s'" % twin))
        out.append(found[0])
    return out


def place_many(rows, height=None):
    """rows: [{'type', 'side', 'name', 'joints'}] -> their guide groups, one undo. Every row is checked first,
    so nothing is made when one is wrong."""
    from gus_rigtool.builder import build as bld
    height = float(height or bld.settings()["height"])
    for i, r in enumerate(rows):
        try:
            placement(r["type"], r["side"], r["name"] or r["type"], r["joints"], height)
        except RuntimeError as e:
            raise RuntimeError("row %d (%s %s): %s" % (i + 1, r["side"], r["name"] or r["type"], e))
    out = []
    with utils.undo_chunk("gusrigPlaceMany"):
        for r in rows:
            out.append(place_on_joints(r["type"], r["side"], r["name"] or r["type"], r["joints"], height))
    return out


def place_on_joints(mtype, side, name, joints=None, height=None):
    """Add a builder module with its guides on the selected joints (in order). Returns its guide group."""
    from gus_rigtool.builder import build as bld
    joints = joints or cmds.ls(orderedSelection=True, long=True, type="joint") or \
        cmds.ls(selection=True, long=True, type="joint") or []
    if not joints:
        raise RuntimeError("select the old joints in order (%s)." % joint_hint(mtype))
    height = float(height or bld.settings()["height"])
    name = name or mtype
    s, pos, on = placement(mtype, side, name, joints, height)
    g = bld.add_module(mtype, side, name, height, s, keep=pos)
    utils.info(TOOL, "%s placed on %d joint(s): %s. Check the settings, then Build picked." % (
        name, len(on), ", ".join("%s=%s" % (r, j) for r, j in list(on.items())[:6])))
    return g


# ===========================================================================
# replace: old joints -> new joints (skin, hook-ups), old part into the backup
# ===========================================================================

def joint_map(group):
    """{old joint: new bind joint} of a module placed on joints (built)."""
    info = guides.read(group)
    s = info["settings"]
    on = s.get("placed_on") or {}
    if not on:
        raise RuntimeError("%s wasn't placed on joints (3 Existing rig > Place on joints)." % info["name"])
    mod = modules.MODULES[info["type"]]
    specs = mod.guide_specs(mod.complete(dict(s)), 100.0, info["side"])
    part = {sp["role"]: sp["part"] for sp in specs}
    out = {}
    lost = []
    for role, old in on.items():
        o = _old_joint(old, (s.get("placed_uuid") or {}).get(role), (s.get("placed_pos") or {}).get(role))
        new = _long(names.make(info["side"], part.get(role, role), "jnt"))
        if o and new and o != new:
            out[o] = new
        elif not o:
            lost.append(old)
    _lost[group] = lost
    return out


_lost = {}            # guide group -> old joints joint_map couldn't find (shown before Replace)


def lost_joints(groups):
    return [j for g in groups for j in _lost.get(g, [])]


def _old_joint(name, uuid=None, pos=None):
    """The old joint a module was placed on: by uuid (survives renames / duplicate names), else the only joint
    with that name, else the joint with that name at the same spot."""
    if uuid:
        found = cmds.ls(uuid, long=True) or []
        if found:
            return found[0]
    found = cmds.ls(name, long=True, type="joint") or []
    if len(found) == 1:
        return found[0]
    if found and pos:
        near = sorted(found, key=lambda j: mathx.distance(cmds.xform(j, query=True, worldSpace=True,
                                                                      translation=True), pos))
        if mathx.distance(cmds.xform(near[0], query=True, worldSpace=True, translation=True), pos) < 1e-3:
            return near[0]
    return None


def _driver_of(new_joint):
    """What moves a new bind joint (to hang things from): itself (the builder's bind joints follow the rig)."""
    return new_joint


def plan_replace(group, old_tops):
    """What Replace will do, without doing it: {'map', 'ctrl_map', 'hookups', 'skins', 'unmapped'}.
    group: one rebuilt module, or a list of them (replaced together)."""
    from gus_rigtool.builder import build as bld
    groups = group if isinstance(group, (list, tuple)) else [group]
    if not groups:
        raise RuntimeError("pick the rebuilt modules in the list.")
    jmap = {}
    for g in groups:
        info = guides.read(g)
        if not bld.is_module_built(info):
            raise RuntimeError("build %s first (Build picked), then Replace." % info["name"])
        jmap.update(joint_map(g))
    old_tops = [t for t in (_long(x) for x in old_tops or []) if t]
    region = set(_below(old_tops))
    part = region | set(jmap)
    old_ctrls = [n for n in part if _is_ctrl(n)]
    ctrl_map = {}
    for c in old_ctrls:
        for j in driven_joints(c):
            if j in jmap:
                ctrl_map[c] = _driver_of(jmap[j])
                break
    hk = hookups(list(jmap) + old_ctrls, region)
    skins = _skins_on(list(jmap))
    weighted = set()
    for sk in skins:
        weighted |= set(utils.ls(cmds.skinCluster(sk, query=True, weightedInfluence=True) or [], long=True) or [])
    unmapped = sorted(j for j in weighted if j in part and j not in jmap)
    return {"map": jmap, "ctrl_map": ctrl_map, "hookups": hk, "skins": skins, "unmapped": unmapped,
            "tops": old_tops, "part": part, "lost": lost_joints(groups)}


def plan_lines(p):
    L = ["Old joint -> new joint:"] + ["  %s -> %s" % (_short(a), _short(b)) for a, b in sorted(p["map"].items())]
    if p["ctrl_map"]:
        L += ["", "Old control -> follows (for what hangs from it):"]
        L += ["  %s -> %s" % (_short(a), _short(b)) for a, b in sorted(p["ctrl_map"].items())]
    L += ["", "Skins that move to the new joints: " + (", ".join(p["skins"]) or "none")]
    if p.get("lost"):
        L += ["", "WARNING - old joints the modules were placed on that can't be found (renamed / deleted?):"]
        L += ["  " + j for j in p["lost"]]
    if p["unmapped"]:
        L += ["", "WARNING - old joints with skin weights but no new joint (they stay on the old joint):"]
        L += ["  " + _short(j) for j in p["unmapped"]]
    L += ["", "Hook-ups (outside the part):"] + (hookup_lines(p["hookups"]) or ["  nothing"])
    L += ["", "Old part going into %s (hidden): " % LEGACY + (", ".join(_short(t) for t in p["tops"]) or
                                                               "only the old joints")]
    return L


def _components(skin):
    out = []
    for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
        t = g if cmds.nodeType(g) == "transform" else (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
        is_mesh = cmds.nodeType(g) == "mesh" or bool(cmds.listRelatives(t, shapes=True, type="mesh"))
        out.append(t + (".vtx[*]" if is_mesh else ".cv[*]"))
    return out


def move_influence(skin, old, new):
    """Every weight of old goes to new (new is added to the skin first if needed), then old leaves the skin."""
    infl = utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []
    old, new = _long(old) or old, _long(new) or new
    if new not in infl:
        cmds.skinCluster(skin, edit=True, addInfluence=new, weight=0.0, lockWeights=False)
    for a in (old, new):
        if cmds.attributeQuery("liw", node=a, exists=True):
            cmds.setAttr(a + ".liw", 0)
    comps = _components(skin)
    if comps:
        cmds.skinPercent(skin, comps, transformMoveWeights=[old, new])
    cmds.skinCluster(skin, edit=True, removeInfluence=old)


def legacy_skin_plan(tolerance=None):
    """Skins that still use joints in legacy_grp: {skin: [(old joint, new joint or None)]}. The new joint is the
    builder's bind joint (skeleton_grp) at the same spot (the guides were placed on the old joints)."""
    legacy = cmds.ls(LEGACY, long=True) or []
    if not legacy:
        return {}
    from gus_rigtool.core import skin_tools
    from gus_rigtool.builder import build as bld
    tol = tolerance if tolerance is not None else max(1e-3, float(bld.settings()["height"]) * 0.002)
    new_joints = [(j, cmds.xform(j, query=True, worldSpace=True, translation=True)) for j in skin_tools.rig_joints()]
    by_uuid = {}
    for g in guides.module_groups():                      # placed modules know exactly
        try:
            for o, n in joint_map(g).items():
                by_uuid[o] = n
        except RuntimeError:
            continue
    plan = {}
    for skin in cmds.ls(type="skinCluster") or []:
        rows = []
        for j in utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []:
            if not j.startswith(legacy[0] + "|"):
                continue
            new = by_uuid.get(j)
            if not new:
                p = cmds.xform(j, query=True, worldSpace=True, translation=True)
                close = sorted(((mathx.distance(p, q), "twist" in n.split("|")[-1].lower(), n.count("|"), n)
                                for n, q in new_joints), key=lambda x: x[:3])
                if close and close[0][0] <= tol:
                    side = naming.side_of(_short(j))
                    same = [c for c in close if c[0] <= tol and naming.side_of(_short(c[3])) == side]
                    new = (same or close)[0][3]
            rows.append((j, new))
        if rows:
            plan[skin] = rows
    return plan


def legacy_plan_lines(plan):
    L = []
    for skin, rows in sorted(plan.items()):
        L.append("%s:" % skin)
        for o, n in rows:
            L.append("  %-28s -> %s" % (_short(o), _short(n) if n else "NO MATCH (left as it is - use Skin 6 Move "
                                                                     "weights)"))
    return L or ["No skin uses joints in legacy_grp."]


def repair_legacy_skin(plan=None):
    """Move the weights of legacy joints to their new joints (one undo). Returns (moved, not matched)."""
    plan = plan if plan is not None else legacy_skin_plan()
    moved, left = 0, []
    with utils.undo_chunk("gusrigLegacySkin"):
        for skin, rows in plan.items():
            for o, n in rows:
                if not n:
                    left.append(_short(o))
                    continue
                move_influence(skin, o, n)
                moved += 1
    return moved, left


def swap_influences(jmap, skins=None):
    """Each skin's old joint is swapped for its new joint (same weights; the mesh doesn't move).
    Returns [(skin, old, new)] done and [(skin, old, why)] skipped."""
    done, skipped = [], []
    for skin in skins or _skins_on(list(jmap)):
        infl = utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []
        for old, new in jmap.items():
            if old not in infl:
                continue
            if new in infl:                              # both in the skin: move the weights over
                try:
                    move_influence(skin, old, new)
                    done.append((skin, old, new))
                except RuntimeError as e:
                    skipped.append((skin, old, str(e).strip()))
                continue
            plugs = cmds.listConnections(old + ".worldMatrix[0]", source=False, destination=True, plugs=True,
                                         type="skinCluster") or []
            for p in plugs:
                if p.split(".")[0] != skin.split("|")[-1] or "[" not in p:
                    continue
                index = p[p.rindex("[") + 1:p.rindex("]")]
                cmds.connectAttr(new + ".worldMatrix[0]", "%s.matrix[%s]" % (skin, index), force=True)
                inv = me.inverse(limb.world(new))
                cmds.setAttr("%s.bindPreMatrix[%s]" % (skin, index), *inv, type="matrix")
                if cmds.attributeQuery("lockInfluenceWeights", node=new, exists=True):
                    try:
                        cmds.connectAttr(new + ".lockInfluenceWeights", "%s.lockWeights[%s]" % (skin, index),
                                         force=True)
                    except RuntimeError:
                        pass
                done.append((skin, old, new))
    return done, skipped


def _retarget_constraint(con, old, new):
    """Swap one target of a constraint, keeping where the constrained node is (maintain offset)."""
    kind = cmds.nodeType(con)
    fn = getattr(cmds, kind)
    driven = [d for d in set(cmds.listConnections(con, source=False, destination=True) or [])
              if _long(d) != _long(con)]
    if not driven:
        return False
    target = _long(driven[0])
    if kind == "poleVectorConstraint":
        fn(new, target, weight=1.0)
    else:
        fn(new, target, maintainOffset=True, weight=1.0)
    try:
        fn(old, target, edit=True, remove=True)
    except RuntimeError:
        pass
    return True


def replace(group, old_tops, dry_run=False):
    """Swap the skin to the new joints, reconnect what hung from the old part, put the old part into
    legacy_grp (hidden). Returns (plan, notes)."""
    p = plan_replace(group, old_tops)
    if dry_run:
        return p, []
    notes = []
    follow = dict(p["map"])
    follow.update(p["ctrl_map"])
    with utils.undo_chunk("gusrigReplace"):
        done, skipped = swap_influences(p["map"], p["skins"])
        notes += ["skin %s: %s -> %s" % (s, _short(o), _short(n)) for s, o, n in done]
        notes += ["skin %s: %s NOT moved (%s)" % (s, _short(o), why) for s, o, why in skipped]
        for h in p["hookups"]:
            new = follow.get(h["node"])
            if not new:
                notes.append("not reconnected (no match): " + hookup_lines([h])[0].strip())
                continue
            try:
                if h["kind"] == "child":
                    cmds.parent(h["what"], new)
                    notes.append("re-parented %s under %s" % (_short(h["what"]), _short(new)))
                elif h["kind"] == "constraint":
                    if _retarget_constraint(h["what"], h["node"], new):
                        notes.append("constraint %s now follows %s" % (_short(h["what"]), _short(new)))
                elif h["kind"] in ("sdk", "connection"):
                    attr = h["detail"]
                    if cmds.attributeQuery(attr.split(".")[0].split("[")[0], node=new, exists=True):
                        cmds.connectAttr(new + "." + attr, h["what"], force=True)
                        notes.append("%s now comes from %s.%s" % (h["what"], _short(new), attr))
                    else:
                        notes.append("redo by hand: %s.%s -> %s (%s has no '%s')" % (
                            _short(h["node"]), attr, h["what"], _short(new), attr))
            except RuntimeError as e:
                notes.append("could not reconnect %s: %s" % (_short(h["what"]), e))
        legacy = cmds.ls(LEGACY, long=True) or [cmds.ls(cmds.createNode("transform", name=LEGACY), long=True)[0]]
        legacy = legacy[0]
        cmds.setAttr(legacy + ".visibility", 0)
        moved = []
        tops = list(p["tops"])
        for j in p["map"]:                          # old joints whose parent isn't an old joint too
            parent = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
            if parent not in p["map"] and not any(j.startswith(t + "|") for t in tops):
                tops.append(j)
        for t in tops:
            t = _long(t.split("|")[-1]) or _long(t)
            if t and cmds.objExists(t) and not t.startswith(legacy + "|"):
                try:
                    moved.append(cmds.parent(t, legacy)[0])
                except RuntimeError as e:
                    notes.append("could not move %s into %s: %s" % (_short(t), LEGACY, e))
        notes.append("into %s (hidden): %s" % (LEGACY, ", ".join(_short(m) for m in moved) or "nothing"))
    utils.info(TOOL, "replaced: %d joint(s) swapped in the skin, old part in %s." % (len(done), LEGACY))
    return p, notes


def remove_backup():
    found = cmds.ls(LEGACY, long=True) or []
    if not found:
        raise RuntimeError("there is no %s." % LEGACY)
    left = []
    for skin in cmds.ls(type="skinCluster") or []:
        infl = utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], long=True) or []
        left += [j for j in infl if j.startswith(found[0] + "|")]
    if left:
        raise RuntimeError("%d joint(s) in %s still drive a skin (%s). Move their weights first."
                           % (len(left), LEGACY, ", ".join(_short(j) for j in left[:4])))
    cmds.delete(found[0])
    utils.info(TOOL, "%s deleted." % LEGACY)


def toggle_backup():
    found = cmds.ls(LEGACY, long=True) or []
    if not found:
        raise RuntimeError("there is no %s." % LEGACY)
    v = not cmds.getAttr(found[0] + ".visibility")
    cmds.setAttr(found[0] + ".visibility", v)
    return v
