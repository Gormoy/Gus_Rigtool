"""
Publish: make a built rig clean for animators, and undo it again (Unpublish).

    from gus_rigtool.builder import publish; publish.publish(); publish.unpublish()

  lock_groups      : offset / space / rig groups get their channels locked and hidden (animators only see controls)
  lock_fk_translate: FK controls can't translate (off by default)
  hide_locked      : locked channels on controls are hidden from the channel box
  hide_joints      : skeleton_grp hidden (the skin still works)
  geo_reference    : geo_grp not selectable in the viewport (reference display, off by default)
  sets             : rig_ctrls_set (every control, a sub-set per module) and bind_joints_set (to skin)
  default_pose     : each control remembers its current values; Gus Animtool's Reset pose goes back to them
  guides           : 'hide', 'delete' (no going back to guides) or 'leave'

Everything changed is written on rig_grp (gusPublish), so Unpublish puts it back. Back to guides and
Build do an Unpublish first.
"""

import json

import maya.cmds as cmds

from gus_rigtool.builder import controls, guides, names
from gus_rigtool.core import utils

TOOL = "Publish"
TRS = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ"]
DEFAULTS = {"lock_groups": True, "lock_fk_translate": False, "hide_locked": True, "hide_joints": True,
            "geo_reference": False, "sets": True, "default_pose": True, "guides": "hide",
            "protect_networks": False}
GUIDE_CHOICES = ["hide", "delete", "leave"]
POSE_ATTR = "gusDefaultPose"
STATE_ATTR = "gusPublish"


# ---------------------------------------------------------------------------
# finding things
# ---------------------------------------------------------------------------

def _gus_rig():
    found = cmds.ls(names.make("C", "rig", "grp"), long=True) or []
    return found[0] if found else None


def rig_group():
    """The rig's top group: Gus_Rigtool's rig_grp, else (a rig made by hand) the group holding its controls."""
    return _gus_rig() or hand_top()


def is_hand_made():
    """True when the scene's rig wasn't built by Gus_Rigtool (no rig_grp) but has controls."""
    return not _gus_rig() and bool(hand_top())


def _hand_controls():
    """{namespace: [controls]} found the way Gus Animtool finds them (names, sets, tags, curves you can key)."""
    from gus_rigtool.core import speed
    try:
        A = speed._animtool()
    except ImportError:                                  # Gus Animtool not there: no hand-made rig to find
        return {}
    for cache in ("_auto_cache", "_pairs_cache", "_members_cache", "_position_cache"):
        getattr(A, cache, {}).clear()
    return {ns: A.character_controls(ns) for ns in (A.characters() or [""])}


def _top_of(node):
    return "|" + node.strip("|").split("|")[0]


def hand_top():
    """A hand-made rig's top group: the selected top node if it holds controls, else the top node most of the
    scene's controls are under. None when there are no controls."""
    ctrls = [c for cs in _hand_controls().values() for c in cs]
    if not ctrls:
        return None
    sel = cmds.ls(selection=True, long=True) or []
    for s_ in sel:
        top = _top_of(s_)
        if any(c.startswith(top + "|") or c == top for c in ctrls):
            return top
    tops = {}
    for c in ctrls:
        tops[_top_of(c)] = tops.get(_top_of(c), 0) + 1
    return max(tops, key=tops.get)


def _group(name):
    found = cmds.ls(names.make("C", name, "grp"), long=True) or []
    return found[0] if found else None


def _published_top():
    """A top node carrying Publish's record (a published hand-made rig), or None - cheap: top nodes only."""
    for n in cmds.ls(assemblies=True, long=True) or []:
        try:
            if cmds.attributeQuery(STATE_ATTR, node=n, exists=True) and cmds.getAttr(n + "." + STATE_ATTR):
                return n
        except (RuntimeError, ValueError):
            continue
    return None


def is_published():
    rig = _gus_rig() or _published_top()
    return bool(rig and cmds.objExists(rig + "." + STATE_ATTR) and cmds.getAttr(rig + "." + STATE_ATTR))


def _is_ctrl(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    return any(cmds.nodeType(s) == "nurbsCurve" for s in shapes)


def rig_controls():
    """Every control under controls_grp (transforms with a curve shape), and the adopted parts' controls.
    A rig made by hand: its controls under its top group."""
    if not _gus_rig():
        top = hand_top()
        if not top:
            return []
        out = [c for cs in _hand_controls().values() for c in cs if c == top or c.startswith(top + "|")]
        return sorted(set(out), key=lambda x: x.count("|"))
    grp = _group("controls")
    out = []
    for n in (cmds.listRelatives(grp, allDescendents=True, type="transform", fullPath=True) or []) if grp else []:
        if cmds.nodeType(n) == "transform" and _is_ctrl(n):
            out.append(n)
    from gus_rigtool.builder import existing
    out += [c for c in existing.adopted_controls() if c not in out]
    return sorted(out, key=lambda x: x.count("|"))


def _hand_groups(top, ctrls):
    """A hand-made rig: the plain groups above its controls (offsets...), up to its top group. Nothing else."""
    ctrl_set = set(ctrls)
    out = []
    for c in ctrls:
        n = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0]
        while n and n != top and n.startswith(top + "|"):
            if n not in ctrl_set and cmds.nodeType(n) == "transform" and not _is_ctrl(n) and n not in out:
                out.append(n)
            n = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
    return [top] + out


def _hand_joint_roots(top, ctrls):
    """A hand-made rig: the top joint of each chain under its top group - except chains with a control under
    them (hiding the joint would hide the control)."""
    out = []
    for j in cmds.listRelatives(top, allDescendents=True, type="joint", fullPath=True) or []:
        parent = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
        if parent and cmds.nodeType(parent) == "joint":
            continue
        if any(c.startswith(j + "|") for c in ctrls):
            continue
        out.append(j)
    return out


def _ctrl_groups():
    """Plain transforms under controls_grp that aren't controls (offset, space, follow groups)."""
    grp = _group("controls")
    if not grp:
        return []
    out = [grp]
    for n in cmds.listRelatives(grp, allDescendents=True, type="transform", fullPath=True) or []:
        if cmds.nodeType(n) == "transform" and not _is_ctrl(n):
            out.append(n)
    return out


def _is_fk(node):
    fk = names.settings()["variants"].get("fk", "_FK")
    return fk and fk in node.split("|")[-1]


# ---------------------------------------------------------------------------
# remembering what we changed
# ---------------------------------------------------------------------------

class _Log(object):
    def __init__(self):
        self.plugs = {}          # plug: [locked, keyable, channelBox]
        self.attrs = {}          # plug: previous value
        self.sets = []
        self.pose = []

    def channel(self, plug, lock=True, hide=True):
        if not cmds.objExists(plug):
            return
        if plug not in self.plugs:
            self.plugs[plug] = [cmds.getAttr(plug, lock=True), cmds.getAttr(plug, keyable=True),
                                cmds.getAttr(plug, channelBox=True)]
        try:
            if hide:
                cmds.setAttr(plug, keyable=False, channelBox=False)
            if lock:
                cmds.setAttr(plug, lock=True)
        except RuntimeError:
            pass

    def value(self, plug, value):
        if not cmds.objExists(plug):
            return
        if plug not in self.attrs:
            self.attrs[plug] = cmds.getAttr(plug)
        try:
            cmds.setAttr(plug, value)
        except RuntimeError:
            pass

    def dump(self):
        return json.dumps({"plugs": self.plugs, "attrs": self.attrs, "sets": self.sets, "pose": self.pose})


# ---------------------------------------------------------------------------
# publish / unpublish
# ---------------------------------------------------------------------------

def publish(options=None):
    """Clean the built rig. Returns a short summary (list of lines)."""
    o = dict(DEFAULTS)
    o.update(options or {})
    rig = rig_group()
    if not rig or not rig_controls():
        raise RuntimeError("no rig with controls in the scene (Build first, or select your rig's top group).")
    hand = not _gus_rig()
    if is_published():
        unpublish(quiet=True)
    log, done = _Log(), []
    ctrls = rig_controls()
    with utils.undo_chunk("gusrigPublish"):
        if o["default_pose"]:
            for c in ctrls:
                pose = {}
                for a in cmds.listAttr(c, keyable=True) or []:
                    plug = c + "." + a
                    if utils.settable(plug):
                        v = cmds.getAttr(plug)
                        if isinstance(v, (int, float, bool)):
                            pose[a] = float(v)
                controls.add_string(c, POSE_ATTR, json.dumps(pose, sort_keys=True))
                log.pose.append(c)
            done.append("default pose saved on %d controls" % len(ctrls))
        if o["lock_groups"]:
            groups = _hand_groups(rig, ctrls) if hand else \
                _ctrl_groups() + [g for g in (rig, _group("skeleton"), _group("rig_nodes"), _group("geo")) if g]
            for g in groups:
                for a in TRS + ["visibility"]:
                    if g.split("|")[-1] in (names.make("C", "skeleton", "grp"), names.make("C", "rig_nodes", "grp"),
                                            names.make("C", "geo", "grp")) and a == "visibility":
                        log.channel(g + "." + a, lock=False, hide=True)     # still switchable by script
                    else:
                        log.channel(g + "." + a)
            done.append("%d groups locked" % len(groups))
        from gus_rigtool.core import vis_switch           # 5.6.20: the switches gear: open while rigging,
        sw = vis_switch.find()                             # locked for the animators
        if sw and vis_switch.made_by_tool(sw):
            for a in TRS + ["visibility"]:
                log.channel(sw + "." + a)
            done.append("%s locked" % sw.split("|")[-1])
        if o["lock_fk_translate"]:
            fk = [c for c in ctrls if _is_fk(c)]
            for c in fk:
                for a in TRS[:3]:
                    log.channel(c + "." + a)
            done.append("translate locked on %d FK controls" % len(fk))
        if o["hide_locked"]:
            count = 0
            for c in ctrls:
                for a in TRS + ["visibility"]:
                    plug = c + "." + a
                    if cmds.objExists(plug) and cmds.getAttr(plug, lock=True) and \
                            (cmds.getAttr(plug, keyable=True) or cmds.getAttr(plug, channelBox=True)):
                        log.channel(plug, lock=True, hide=True)
                        count += 1
            done.append("%d locked channels hidden" % count)
        skel = _group("skeleton")
        if o["hide_joints"] and hand:
            roots = _hand_joint_roots(rig, ctrls)
            for j in roots:
                log.value(j + ".visibility", 0)
            if roots:
                done.append("joints hidden (%d chain(s))" % len(roots))
        elif o["hide_joints"] and skel:
            log.value(skel + ".visibility", 0)
            done.append("joints hidden")
        geo = _group("geo")
        if o["geo_reference"] and geo:
            log.value(geo + ".overrideEnabled", 1)
            log.value(geo + ".overrideDisplayType", 2)
            done.append("geometry not selectable")
        if o["sets"]:
            done.append(_make_sets(ctrls, log))
        top = guides.top_group(create=False)
        if top and o["guides"] == "hide":
            log.value(top + ".visibility", 0)
            done.append("guides hidden")
        elif top and o["guides"] == "delete":
            cmds.delete(top)
            done.append("guides deleted (no going back to guides)")
        if o.get("protect_networks"):
            from gus_rigtool.core import network_tools
            done.append("%d utility nodes / constraints protected" % network_tools.protect())
        controls.add_string(rig, STATE_ATTR, log.dump())
    utils.info(TOOL, "rig published: " + "; ".join(done) + ".")
    return done


def _make_sets(ctrls, log):
    main = "rig_ctrls_set"
    for s in [main, "bind_joints_set"]:
        if cmds.objExists(s):
            cmds.delete(s)
    subs = []
    grp = _group("controls")
    for g in (cmds.listRelatives(grp, allDescendents=True, type="transform", fullPath=True) or []) if grp else []:
        short = g.split("|")[-1]
        if short.endswith("_ctrls_grp"):
            members = [c for c in ctrls if c.startswith(g + "|")]
            if members:
                name = short[:-len("_grp")] + "_set"
                if cmds.objExists(name):
                    cmds.delete(name)
                subs.append(cmds.sets(members, name=name))
    from gus_rigtool.builder import existing
    for g in existing.adopted_groups():                  # a set per adopted part
        info = existing.read_adopted(g)
        members = []
        for x in info["settings"].get("controls", []):
            members += [c for c in (cmds.ls(x, long=True) or []) if c in ctrls]
        if members:
            name = names.make(info["side"], info["name"] + "_ctrls", "set")
            if cmds.objExists(name):
                cmds.delete(name)
            subs.append(cmds.sets(members, name=name))
    loose = [c for c in ctrls if not any(c in (cmds.sets(s, query=True) or []) for s in subs)]
    main = cmds.sets(loose + subs, name=main) if (loose or subs) else None
    skel = _group("skeleton")
    joints = (cmds.listRelatives(skel, allDescendents=True, type="joint", fullPath=True) or []) if skel else []
    if not _gus_rig():                                   # a hand-made rig: the joints its skins use
        for sk in cmds.ls(type="skinCluster") or []:
            for j in cmds.ls(cmds.skinCluster(sk, query=True, influence=True) or [], long=True, type="joint") or []:
                if j not in joints:
                    joints.append(j)
    jset = cmds.sets(joints, name="bind_joints_set") if joints else None
    log.sets = [x for x in subs + [main, jset] if x]
    return "selection sets: %s (%d module sets), bind_joints_set (%d joints)" % (main, len(subs), len(joints))


def unpublish(quiet=False):
    """Put back everything Publish changed (not deleted guides)."""
    rig = _gus_rig() or _published_top()
    if not is_published():
        if not quiet:
            raise RuntimeError("the rig isn't published.")
        return False
    try:
        state = json.loads(cmds.getAttr(rig + "." + STATE_ATTR))
    except (ValueError, TypeError):
        state = {}
    with utils.undo_chunk("gusrigUnpublish"):
        for plug, (locked, keyable, channel_box) in state.get("plugs", {}).items():
            if cmds.objExists(plug):
                try:
                    cmds.setAttr(plug, lock=False)
                    cmds.setAttr(plug, keyable=keyable)
                    if not keyable:
                        cmds.setAttr(plug, channelBox=channel_box)
                    cmds.setAttr(plug, lock=locked)
                except RuntimeError:
                    pass
        for plug, value in state.get("attrs", {}).items():
            if cmds.objExists(plug):
                try:
                    cmds.setAttr(plug, value)
                except RuntimeError:
                    pass
        for s in state.get("sets", []):
            if cmds.objExists(s):
                cmds.delete(s)
        from gus_rigtool.core import network_tools
        network_tools.unprotect()
        controls.add_string(rig, STATE_ATTR, "")
    if not quiet:
        utils.info(TOOL, "rig unpublished: channels, sets and visibility are back as they were.")
    return True


def check(options=None):
    """Run the Checker on the rig (its own saved options). Returns (fails, warnings, report text)."""
    from gus_rigtool.tools import checker
    o = utils.tool_settings(checker.SETTINGS_KEY, checker.DEFAULTS)
    o.update(options or {})
    rig = rig_group()
    results = checker.run_checks(o, [rig] if rig else [])
    fails = sum(1 for s, _n in results.values() if s in ("FAIL", "ERROR"))
    warns = sum(1 for s, _n in results.values() if s == "WARN")
    return fails, warns, checker.report_text(results)

