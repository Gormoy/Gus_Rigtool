"""
Build the rig from the guides, go back to the guides, templates.

    rig_grp
      geo_grp          your model (put it here)
      skeleton_grp     bind joints (skin to these)
      controls_grp     world > root > every module's controls
      rig_nodes_grp    IK handles, FK / IK chains, ribbons... (hidden)
    guides_grp         the guides (hidden after Build)
"""

import hashlib
import json
import os

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.builder import controls, guides, mathx, modules, names, skin_keep
from gus_rigtool.core import mirror_engine as me
from gus_rigtool.core import curves, utils

TOOL = "Build"
SETTINGS_KEY = "build"
DEFAULTS = {"height": 180.0, "joint_radius": 1.0,
            "keep_skin": True,          # save the skin before joints are deleted, put it back after Build
            "guide_mode": "linked",     # 'linked': moving a guide moves the ones below; 'free': alone
            "keep_shapes": True, "keep_skin_bound": False, "keep_rig_data": True,
            "label_joints": True,       # control shapes you changed come back after Rebuild / Build
            "controls_on_top": True}     # 5.3.1: body controls drawn in front of the mesh


def settings():
    return utils.tool_settings(SETTINGS_KEY, DEFAULTS)


# ---------------------------------------------------------------------------
# what each module gets to build with
# ---------------------------------------------------------------------------

class Ctx(object):
    def __init__(self, info, height, groups, outputs, spaces):
        self.info = info
        self.mod = modules.MODULES[info["type"]]
        self.settings = self.mod.complete(dict(info["settings"]))
        self.side = info["side"]
        self.height = height
        self.radius = float(settings().get("joint_radius", 1.0)) * height / 180.0
        self.positions = guides.positions(info["group"])
        self.orient = self.settings["orient"]
        self.groups = groups
        self.outputs = outputs
        self.spaces = spaces
        self.skeleton = groups["skeleton"]
        self.skeleton_extra = groups["skeleton"]
        self.controls_grp = groups["controls"]
        self.world_ctrl = spaces.get("world")
        self.root_ctrl = spaces.get("root")
        self.scale_plug = (self.world_ctrl + ".globalScale") if self.world_ctrl and \
            cmds.attributeQuery("globalScale", node=self.world_ctrl, exists=True) else None
        self.attach_joint, self.attach_output, self.attach_follow = self._attach()
        tag = names.make(self.side, info["name"], "grp")
        self.nodes = controls.group(tag.replace("_grp", "_nodes_grp"), groups["nodes"])
        self.module_ctrls = self._ctrl_group(tag.replace("_grp", "_ctrls_grp"))

    # -- attach -------------------------------------------------------------
    def _attach(self):
        spec = self.settings.get("attach") or ""
        if ":" not in spec:
            return None, None, None
        mod_name, part = spec.split(":", 1)
        out = None
        for side in (self.side, "C"):
            out = self.outputs.get(guides.module_id(side, mod_name))
            if out:
                break
        if not out:
            utils.warn(TOOL, "%s (%s): attach '%s' - no module '%s' built before it; it goes under the root."
                       % (self.info["name"], self.side, spec, mod_name))
            return None, None, None
        joint = out["joints"].get(part)
        if joint is None and out["joints"]:
            utils.warn(TOOL, "%s (%s): attach '%s' - '%s' has no joint '%s' (it has: %s)."
                       % (self.info["name"], self.side, spec, mod_name, part, ", ".join(sorted(out["joints"])[:6])))
        return joint, out, out.get("follow")

    def _ctrl_group(self, name):
        parent = self.root_ctrl or self.controls_grp
        if self.attach_joint is None and self.attach_follow and cmds.objExists(self.attach_follow):
            parent = self.attach_follow                    # e.g. the spine under the root control
        g = controls.group(name, parent)
        if self.attach_joint:
            cmds.parentConstraint(self.attach_joint, g, maintainOffset=True)
            cmds.scaleConstraint(self.attach_joint, g, maintainOffset=True)
        return g

    # -- helpers for modules ------------------------------------------------
    def _missing(self, roles):
        missing = [r for r in roles if r not in self.positions]
        if missing:
            raise RuntimeError("%s (%s): its guides don't match its settings (missing %s). Pick it in the list "
                               "and press 'Apply (update guides)'." % (self.info["name"], self.side,
                                                                      ", ".join(missing[:4])))

    def pos(self, role):
        self._missing([role])
        return self.positions[role]

    def chain(self, roles, plane_roles=None):
        """World matrices of joints at these guides, with the module's orientation settings.
        Right side with 'behavior': worked out as the left twin, then mirrored back, so both sides
        follow the same rules and the same rotate values mirror."""
        self._missing(list(roles) + list(plane_roles or []))
        pts = [self.positions[r] for r in roles]
        plane = [self.positions[r] for r in (plane_roles or [])]
        o = self.orient
        behavior = self.side == "R" and o.get("behavior_right", True)
        if behavior:
            pts = [[-p[0], p[1], p[2]] for p in pts]
            plane = [[-p[0], p[1], p[2]] for p in plane]
        kw = {"aim": o["aim"], "up": o["up"], "up_mode": o["up_mode"], "world_up": o["world_up"]}
        if o["up_mode"] == "plane" and len(plane) >= 3:
            n = mathx.plane_normal(plane)
            if n is not None:
                kw["up_vectors"] = [n] * len(pts)
        mats = mathx.chain_matrices(pts, **kw)
        if behavior:
            mats = [me.mirror_list(m, "behavior", 0) for m in mats]
        return mats

    def aim_face(self):
        return self.orient["aim"].lstrip("-")

    def shape(self, kind):
        """The shape name, or (name, [rx, ry, rz]) when the settings turn it."""
        entry = self.settings["controls"].get(kind) or ["circle", 0.05]
        if len(entry) > 2 and entry[2] and any(abs(float(r)) > 1e-6 for r in entry[2]):
            return (entry[0], list(entry[2]))
        return entry[0]

    def size(self, kind):
        return float((self.settings["controls"].get(kind) or ["circle", 0.05])[1]) * self.height

    def space(self, label):
        node = self.spaces.get(label)
        return node if node and cmds.objExists(node) else None

    def space_targets(self, builtin, extra=True):
        """[(label, node)]: the builder's spaces that exist, then your 'Extra spaces' (label = node).
        Missing ones are reported; a node already in the list isn't added twice."""
        out, used = [], set()
        for label, node in builtin:
            if node and cmds.objExists(node) and node not in used:
                out.append((label, node))
                used.add(node)
        text = (self.settings.get("options", {}).get("extra_spaces") or "") if extra else ""
        for item in text.replace(";", ",").split(","):
            if "=" not in item:
                continue
            label, name = [x.strip() for x in item.split("=", 1)]
            found = cmds.ls(name, long=True) or []
            if not label or len(found) != 1:
                utils.warn(TOOL, "%s (%s): space '%s': %s." % (self.info["name"], self.side, label,
                           ("'%s' not found" % name) if not found else ("several nodes are called '%s'" % name)))
                continue
            if found[0] in used:
                continue
            out.append((label, found[0]))
            used.add(found[0])
        return out

    def space_default(self, targets, fallback):
        """Index of the 'Default space' option (or fallback) among the targets."""
        labels = [lb for lb, _n in targets]
        want = (self.settings.get("options", {}).get("default_space") or fallback).strip()
        if want in labels:
            return labels.index(want)
        if want != fallback:
            utils.warn(TOOL, "%s (%s): default space '%s' isn't there (%s) - using %s." % (
                self.info["name"], self.side, want, ", ".join(labels), fallback if fallback in labels else
                labels[0] if labels else "-"))
        return labels.index(fallback) if fallback in labels else 0

    def ik_parent(self):
        return self.root_ctrl or self.controls_grp


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------

def _top(name, parent=None):
    full = names.make("C", name, "grp")
    found = cmds.ls(full, long=True) or []
    if found:
        return found[0]
    return controls.group(full, parent)


def rig_groups():
    rig = _top("rig")
    g = {"rig": rig, "geo": _top("geo", rig), "skeleton": _top("skeleton", rig),
         "controls": _top("controls", rig), "nodes": _top("rig_nodes", rig)}
    cmds.setAttr(g["nodes"] + ".visibility", 0)
    return g


# ---------------------------------------------------------------------------
# build / back
# ---------------------------------------------------------------------------

def _infos():
    out = []
    for g in guides.module_groups():
        info = guides.read(g)
        if info["type"] in modules.MODULES:
            out.append(info)
    return out


def _ordered(infos):
    """Modules in build order: whatever a module hangs from comes first."""
    by_id = {i["id"]: i for i in infos}
    done, order = set(), []

    def visit(info, depth=0):
        if info["id"] in done or depth > 20:
            return
        spec = info["settings"].get("attach", "")
        if ":" in spec:
            mod_name = spec.split(":", 1)[0]
            for side in (info["side"], "C"):
                parent = by_id.get(guides.module_id(side, mod_name))
                if parent and parent["id"] != info["id"]:
                    visit(parent, depth + 1)
                    break
        done.add(info["id"])
        order.append(info)

    for t in modules.ORDER:
        for info in infos:
            if info["type"] == t:
                visit(info)
    return order


def is_built():
    return any(cmds.attributeQuery("gusOutputs", node=g, exists=True) and
               controls.get_string(g, "gusOutputs") for g in guides.module_groups())


def preview(infos=None):
    """Every main name the build will make: [(module label, name, exists already)]."""
    out = []
    for info in infos or _infos():
        mod = modules.MODULES[info["type"]]
        s = mod.complete(dict(info["settings"]))
        for n in mod.preview_names(s, info["side"]):
            out.append((info["id"], n, bool(cmds.ls(n))))
    return out


def _short(x):
    return x.split("|")[-1] if isinstance(x, str) else x


# ---------------------------------------------------------------------------
# your control shapes survive Rebuild selected / Back to guides + Build
# ---------------------------------------------------------------------------

def _ctrl_nodes(uuids):
    suffix = names.settings()["suffixes"].get("ctrl", "_ctrl")
    out = []
    for n in utils.ls(sorted(uuids), long=True) or []:
        if cmds.nodeType(n) == "transform" and n.endswith(suffix) and curves.curve_shapes(n):
            out.append(n)
    return out


def _signature(node):
    data = curves.read_shape(node)
    flat = [[round(float(v), 3) for p in c["points"] for v in p] for c in data]
    return hashlib.md5(json.dumps(flat).encode("utf-8")).hexdigest()[:12]


def _json_attr(node, attr):
    try:
        return json.loads(controls.get_string(node, attr) or "{}")
    except ValueError:
        return {}


def _shapes_after_build(group, created):
    """Remember each control's shape as built, then put back the shapes you changed before."""
    if not settings().get("keep_shapes", True):
        return
    custom = _json_attr(group, "gusShapes")
    sigs = {}
    for n in _ctrl_nodes(created):
        short = _short(n)
        try:
            sigs[short] = _signature(n)
            if short in custom:
                curves.set_shape(n, custom[short]["shape"], custom[short].get("style"))
        except Exception:                                   # a shape we can't read: leave it
            continue
    controls.add_string(group, "gusShapeSigs", json.dumps(sigs))


def _save_custom_shapes(infos):
    """Before a module's controls are deleted: keep the shapes that differ from how they were built."""
    if not settings().get("keep_shapes", True):
        return 0
    count = 0
    for info in infos:
        st = _stored(info)
        if not st:
            continue
        sigs = _json_attr(info["group"], "gusShapeSigs")
        custom = _json_attr(info["group"], "gusShapes")
        for n in _ctrl_nodes(st["created"]):
            short = _short(n)
            if short not in sigs:
                continue
            try:
                if _signature(n) != sigs[short]:
                    custom[short] = {"shape": curves.read_shape(n), "style": curves.read_style(n)}
                    count += 1
                else:
                    custom.pop(short, None)
            except Exception:
                continue
        controls.add_string(info["group"], "gusShapes", json.dumps(custom))
    return count


def forget_shapes(groups):
    """The picked modules go back to their default control shapes at the next Rebuild / Build."""
    for g in groups:
        controls.add_string(g, "gusShapes", "{}")
        controls.add_string(g, "gusShapeSigs", "{}")     # the current shapes aren't kept either
    return len(groups)


def _build_one(info, height, groups, outputs, spaces):
    """Build one module; remember what it made (outputs + every node created) on its guide group."""
    before = set(cmds.ls(uuid=True) or [])
    ctx = Ctx(info, height, groups, outputs, spaces)
    out = ctx.mod.build(ctx) or {}
    out.setdefault("joints", {})
    out["nodes_grp"], out["ctrls_grp"] = ctx.nodes, ctx.module_ctrls
    outputs[info["id"]] = out
    spaces.update(out.get("spaces", {}))
    created = sorted(set(cmds.ls(uuid=True) or []) - before)
    stored = {"joints": {k: _short(v) for k, v in out["joints"].items()},
              "spaces": {k: _short(v) for k, v in out.get("spaces", {}).items()},
              "follow": _short(out.get("follow")), "settings_ctrl": _short(out.get("settings_ctrl")),
              "nodes_grp": _short(ctx.nodes), "ctrls_grp": _short(ctx.module_ctrls), "created": created}
    controls.add_string(info["group"], "gusOutputs", json.dumps(stored))
    guides.remember_built(info["group"])
    _shapes_after_build(info["group"], created)
    return out


def _find_one(name):
    if not name:
        return None
    found = cmds.ls(name, long=True) or []
    return found[0] if len(found) == 1 else None


def _stored(info):
    """What a built module made, with names turned back into paths (missing ones dropped)."""
    text = controls.get_string(info["group"], "gusOutputs")
    if not text:
        return None
    data = json.loads(text)
    joints = {k: _find_one(v) for k, v in data.get("joints", {}).items()}
    spaces = {k: _find_one(v) for k, v in data.get("spaces", {}).items()}
    return {"joints": {k: v for k, v in joints.items() if v},
            "spaces": {k: v for k, v in spaces.items() if v},
            "follow": _find_one(data.get("follow")), "settings_ctrl": _find_one(data.get("settings_ctrl")),
            "created": data.get("created", [])}


def _module_joints(stored_list):
    """Every joint these built modules made: the main ones and the extras (twist, bendy, ribbon...)."""
    out = []
    for st in stored_list:
        if not st:
            continue
        found = list(st["joints"].values())
        for n in utils.ls(st.get("created") or [], long=True) or []:
            if not cmds.objExists(n) or cmds.nodeType(n) != "joint":
                continue
            found.append(n)
            found += cmds.listRelatives(n, allDescendents=True, type="joint", fullPath=True) or []
        for j in found:
            j = (cmds.ls(j, long=True) or [None])[0]
            if j and j not in out:
                out.append(j)
    return out


def is_module_built(info):
    return bool(controls.get_string(info["group"], "gusOutputs"))


def _waiting():
    """Module groups at their guides while the rest of the rig is built."""
    groups = guides.module_groups()
    built = [g for g in groups if controls.get_string(g, "gusOutputs")]
    return [g for g in groups if g not in built] if built else []


def _restore_skin():
    if settings().get("keep_skin", True) and skin_keep.pending():
        waiting = _waiting()
        if waiting:                        # some joints aren't back yet: their weights would be lost
            utils.info(TOOL, "the skin comes back once every module is built again (%s still at its guides)."
                       % ", ".join(guides.read(g)["id"] for g in waiting))
            return
        skin_keep.report(*skin_keep.restore())


def _guides_after_build():
    waiting = _waiting()
    if waiting:
        guides.show_only(waiting)
    else:
        guides.set_visible(False)


def _parent_id(info, by_id):
    spec = info["settings"].get("attach", "")
    if ":" not in spec:
        return None
    mod_name = spec.split(":", 1)[0]
    for side in (info["side"], "C"):
        pid = guides.module_id(side, mod_name)
        if pid in by_id and pid != info["id"]:
            return pid
    return None


def dependents(ids):
    """The modules ids plus every module hanging from them (and from those...)."""
    infos = _infos()
    by_id = {i["id"]: i for i in infos}
    out = list(ids)
    changed = True
    while changed:
        changed = False
        for info in infos:
            if info["id"] not in out and _parent_id(info, by_id) in out:
                out.append(info["id"])
                changed = True
    return out


def unbuilt_parents(ids):
    """Modules the given ones hang from (directly or further up) that aren't built and aren't in ids."""
    infos = _infos()
    by_id = {i["id"]: i for i in infos}
    out = []
    for mid in ids:
        pid = _parent_id(by_id[mid], by_id) if mid in by_id else None
        while pid and pid not in ids:
            if not is_module_built(by_id[pid]) and pid not in out:
                out.append(pid)
            pid = _parent_id(by_id[pid], by_id)
    return out


def _confirm_skin_loss(joints):
    if settings().get("keep_skin", True):
        return True
    if not skin_keep.skins_on(joints):
        return True
    answer = cmds.confirmDialog(
        title="The skin will be lost", button=["Delete the joints", "Cancel"], defaultButton="Cancel",
        cancelButton="Cancel", dismissString="Cancel",
        message="Your model is skinned to some of these joints, and 'Keep the skin' is off.\n"
                "Deleting the joints loses the skin. Turn 'Keep the skin' on (Build tab, step 4) to keep it.")
    return answer == "Delete the joints"


# ---------------------------------------------------------------------------
# the engine: every button is 'take down' some modules and / or 'put up' some modules
# ---------------------------------------------------------------------------

def _unpublish():
    """A published rig goes back to normal before it changes (Publish again when done)."""
    from gus_rigtool.builder import publish
    if publish.is_published():
        publish.unpublish(quiet=True)
        utils.info(TOOL, "the rig was published: unpublished first (Publish again when you're done).")


def _take_down(infos, note="the next Build"):
    """Delete what these built modules made; their skin and changed control shapes are saved first.
    note: when the skin comes back (None: right away, in the same step)."""
    _unpublish()
    stored = [(i, _stored(i)) for i in infos]
    stored = [(i, st) for i, st in stored if st]
    if not stored:
        return
    kept = _save_custom_shapes([i for i, _st in stored])
    if kept:
        utils.info(TOOL, "%d control shape(s) you changed will come back." % kept)
    joints = _module_joints([st for _i, st in stored])          # main joints and extras (twist, ribbon...)
    if settings().get("keep_skin", True) and joints:
        saved = skin_keep.save(joints, bound=settings().get("keep_skin_bound", False))
        if saved:
            utils.info(TOOL, "skin saved for %s%s." % (", ".join(saved[:5]),
                                                      ": it comes back with " + note if note else ""))
    created = sorted(set(u for _i, st in stored for u in st["created"]))
    from gus_rigtool.builder import hookups              # your own work hanging from these modules
    builder = set(u for i in _infos() for u in ((_stored(i) or {}).get("created") or []))
    for name in ("rig", "geo", "skeleton", "controls", "rig_nodes"):   # the rig's own groups and their links
        for g in cmds.ls(names.make("C", name, "grp"), long=True) or []:
            kids = cmds.listRelatives(g, children=True, type="constraint", fullPath=True) or []
            builder.update(cmds.ls([g] + kids, uuid=True) or [])
    if settings().get("keep_rig_data", True):          # your attributes / space switches on its controls
        from gus_rigtool.builder import rig_data
        for i, st in stored:
            rig_data.keep_before_take_down(i["group"], _ctrl_nodes(st["created"]))
    for i, st in stored:
        rec = hookups.capture(st["created"], builder)
        if any(rec.values()):
            hookups.save(i["group"], rec)
    nodes = [n for n in (utils.ls(created, long=True) or []) if cmds.objExists(n)]
    if nodes:
        cmds.delete(nodes)
    for i, _st in stored:
        controls.add_string(i["group"], "gusOutputs", "")


def _put_up(targets, height):
    """Build these modules (in order), with the modules already built as what they hang from."""
    _unpublish()
    outputs, spaces = {}, {}
    ids = set(i["id"] for i in targets)
    for info in _infos():
        if info["id"] not in ids:
            st = _stored(info)
            if st:
                outputs[info["id"]] = st
                spaces.update(st["spaces"])
    from gus_rigtool.builder import existing             # adopted parts: modules can hang from them too
    for g in existing.adopted_groups():
        info = existing.read_adopted(g)
        st = _stored(info)
        if st and info["id"] not in outputs:
            outputs[info["id"]] = st
            for k, v in st["spaces"].items():                # spaces your adopted part offers
                spaces.setdefault(k, v)
    groups = rig_groups()
    for info in _ordered(targets):
        _build_one(info, height, groups, outputs, spaces)
    from gus_rigtool.builder import hookups, rig_data
    for info in _ordered(targets):                       # your attributes and space switches first
        made, notes = rig_data.put_back_after_build(info["group"])
        if made:
            utils.info(TOOL, "%s: %d of your attribute(s) / space switch(es) made again." % (info["id"], made))
        for n in notes[:6]:
            utils.warn(TOOL, "%s: %s" % (info["id"], n))
    for info in _ordered(targets):                       # your hook-ups back on the new nodes
        done, notes = hookups.restore(info["group"])
        hookups.report(info["id"], done, notes)
    skel = groups["skeleton"]
    if spaces.get("root") and not cmds.listRelatives(skel, type="parentConstraint"):
        cmds.parentConstraint(spaces["root"], skel, maintainOffset=True)
        cmds.scaleConstraint(spaces["root"], skel, maintainOffset=True)
    _guides_after_build()
    if settings().get("label_joints", True):            # side labels: skin mirroring pairs left / right exactly
        from gus_rigtool.core import joint_labels
        skel_joints = cmds.listRelatives(skel, allDescendents=True, type="joint", fullPath=True) or []
        joint_labels.label(skel_joints)
    if settings().get("controls_on_top", True):         # body controls in front of the mesh (face ones not)
        from gus_rigtool.core import on_top
        from gus_rigtool.tools import checker
        ctrls = [c for c in cmds.listRelatives(groups["controls"], allDescendents=True, type="transform",
                                               fullPath=True) or [] if checker.is_control(c)]
        on_top.apply(ctrls, on=True, skip_face=True)
    _restore_skin()
    cmds.select(clear=True)
    return outputs


def _check_names(targets):
    """Names the build will make that already exist (and aren't made by these modules)."""
    created = set(u for i in targets for u in ((_stored(i) or {}).get("created") or []))
    clashes = [n for _m, n, exists in preview(targets)
               if exists and not (set(cmds.ls(n, uuid=True) or []) & created)]
    if clashes:
        raise RuntimeError("these names already exist in the scene: %s%s. Rename them or change the "
                           "naming." % (", ".join(clashes[:5]), " ..." if len(clashes) > 5 else ""))


def build_all(height=None):
    """Build every module that isn't built yet (all of them on a new rig). One undo."""
    height = float(height or settings()["height"])
    infos = _infos()
    if not infos:
        raise RuntimeError("no guides yet: add modules (or the Biped template) first.")
    targets = [i for i in infos if not is_module_built(i)]
    if not targets:
        raise RuntimeError("every module is built. Pick modules and press Build picked to rebuild them, "
                           "or Back to guides.")
    _check_names(targets)
    from gus_rigtool.builder import custom_steps
    ids = [i["id"] for i in targets]
    with utils.undo_chunk("gusrigBuild"):
        custom_steps.run("pre", ids)
        outputs = _put_up(targets, height)
        custom_steps.run("post", ids, rig_groups())
    count = sum(len(outputs[i["id"]]["joints"]) for i in targets)
    utils.info(TOOL, "built %d module(s), %d bind joints. Skin your model to skeleton_grp's joints." %
               (len(targets), count))
    return outputs


def build_picked(ids, height=None, with_parents=False):
    """
    Build or rebuild only these modules (and the modules hanging from them): a built one is deleted
    and built again from its guides and settings, one at its guides is built. with_parents: also
    build the modules they hang from that aren't built yet. One undo. Returns the module ids.
    """
    height = float(height or settings()["height"])
    infos = _infos()
    by_id = {i["id"]: i for i in infos}
    ids = [i for i in ids if i in by_id]
    targets = dependents(ids)                  # the picked and what hangs from them...
    if with_parents:                           # ...plus, only, the unbuilt modules they hang from
        targets = [p for p in unbuilt_parents(ids) if p not in targets] + targets
    if not targets:
        raise RuntimeError("pick a module in the list.")
    if any(by_id[t]["type"] == "root" and is_module_built(by_id[t]) for t in targets):
        if back_to_guides():                               # the root carries everything: rebuild it all
            build_all(height)
            return [i["id"] for i in infos]
        return []
    target_infos = [by_id[t] for t in targets]
    _check_names(target_infos)
    built = [i for i in target_infos if is_module_built(i)]
    if not _confirm_skin_loss([j for i in built for j in (_stored(i) or {"joints": {}})["joints"].values()]):
        return []
    from gus_rigtool.builder import custom_steps
    with utils.undo_chunk("gusrigBuildPicked"):
        custom_steps.run("pre", targets)
        _take_down(built, None)
        _put_up(target_infos, height)
        custom_steps.run("post", targets, rig_groups())
    rebuilt = set(i["id"] for i in built)
    order = [i["id"] for i in _ordered(target_infos)]
    done = [("rebuilt", [t for t in order if t in rebuilt]), ("built", [t for t in order if t not in rebuilt])]
    utils.info(TOOL, " ".join("%s: %s." % (word, ", ".join(ids_)) for word, ids_ in done if ids_))
    return targets


rebuild_selected = build_picked          # the old name (1.7 and before)


def back_to_guides_selected(ids, force=False):
    """
    Only these modules (and the modules hanging from them) go back to their guides: their rig is
    deleted (skin and changed control shapes saved), their guides shown. Build picked or Build
    brings them back. Returns the module ids sent back.
    """
    infos = _infos()
    by_id = {i["id"]: i for i in infos}
    targets = dependents([i for i in ids if i in by_id])
    if not targets:
        raise RuntimeError("pick a module in the list.")
    if any(by_id[t]["type"] == "root" for t in targets):
        return [i["id"] for i in infos] if back_to_guides(force) else []   # the root carries everything
    built = [by_id[t] for t in targets if is_module_built(by_id[t])]
    joints = _module_joints([_stored(i) for i in built])
    if built and not force and not _confirm_skin_loss(joints):
        return []
    with utils.undo_chunk("gusrigBackToGuidesSelected"):
        _take_down(built, "Build picked / Build")
        guides.show_only([by_id[t]["group"] for t in targets])
        fixed = sum(guides.restore_zeroed(by_id[t]["group"]) for t in targets)
    if fixed:
        utils.warn(TOOL, "%d guide(s) had been moved to the centre since the Build - put back where they were "
                   "built." % fixed)
    utils.info(TOOL, "back to the guides: %s. Adjust them, then Build picked (or Build)." % ", ".join(targets))
    return targets


def guides_from_rig():
    """While the rig is built: every guide onto its joint (same name), the foot / paw pivots onto their pivot
    groups. For guides that got lost (moved, zeroed) after building. Returns (moved, not found)."""
    moved, missing = 0, []
    with utils.undo_chunk("gusrigGuidesFromRig"):
        for info in _infos():
            mod = modules.MODULES[info["type"]]
            s = mod.complete(info["settings"])
            n = s.get("names", {})
            specs = mod.guide_specs(s, float(settings()["height"]), info["side"])
            depth = lambda sp: (info["guides"].get(sp["role"]) or "").count("|")      # noqa: E731
            for spec in sorted(specs, key=depth):                    # parents before children (linked guides)
                g = info["guides"].get(spec["role"])
                if not g:
                    continue
                target = _guide_target(info["side"], spec, n)
                if not target:
                    missing.append("%s:%s" % (info["id"], spec["role"]))
                    continue
                try:
                    cmds.xform(g, worldSpace=True, translation=target)
                    moved += 1
                except (RuntimeError, ValueError):
                    pass                                         # driven by symmetry: follows its twin
    return moved, missing


def _guide_target(side, spec, n):
    """Where a guide belongs on the built rig: its joint, or (pivots) its pivot group's pivot."""
    if spec.get("kind") == "pivot":
        role = spec["role"]
        key = "heel" if "heel" in role else ("inner" if "inner" in role else ("outer" if "outer" in role else role))
        for r in ("ankle", "ball"):                              # legs: <ankle>_heelPivot; paws: <ball>_heelPivot
            if not n.get(r):
                continue
            found = cmds.ls(names.make(side, "%s_%sPivot" % (n[r], key), "grp"), long=True) or []
            if len(found) == 1:
                return cmds.xform(found[0], query=True, worldSpace=True, rotatePivot=True)
        return None
    for sd in ([side, "L"] if side == "C" else [side]):           # the face's sided parts are placed on the left
        found = cmds.ls(names.make(sd, spec["part"], "jnt"), long=True) or []
        if found:
            skel = [f for f in found if "|skeleton_grp|" in f + "|"]    # the bind joint before any copy
            return cmds.xform((skel or found)[0], query=True, worldSpace=True, translation=True)
    return None


def back_to_guides(force=False):
    """Delete the built rig (skeleton, controls, rig nodes), show the guides again. geo_grp is kept.
    With 'Keep the skin' the weights are saved first and put back by the next Build."""
    g = {k: (cmds.ls(names.make("C", n, "grp"), long=True) or [None])[0]
         for k, n in (("skeleton", "skeleton"), ("controls", "controls"), ("nodes", "rig_nodes"))}
    joints = (cmds.listRelatives(g["skeleton"], allDescendents=True, type="joint", fullPath=True) or []) \
        if g["skeleton"] else []
    for grp in (g["controls"], g["nodes"]):                    # joints the modules keep elsewhere (ribbons...)
        if grp:
            joints += [j for j in cmds.listRelatives(grp, allDescendents=True, type="joint", fullPath=True) or []
                       if j not in joints]
    joints += [j for j in _module_joints([_stored(i) for i in _infos() if is_module_built(i)]) if j not in joints]
    if not force and not _confirm_skin_loss(joints):
        return False
    with utils.undo_chunk("gusrigBackToGuides"):
        if settings().get("keep_skin", True) and joints:       # every skinned joint, built by us or not
            saved = skin_keep.save(joints, bound=settings().get("keep_skin_bound", False))
            if saved:
                utils.info(TOOL, "skin saved for %s: it comes back with the next Build." % ", ".join(saved[:5]))
        _take_down([i for i in _infos() if is_module_built(i)])
        for grp in g.values():                                 # anything else left in the rig groups
            if grp:
                for kids in (cmds.listRelatives(grp, type="constraint", fullPath=True),
                             cmds.listRelatives(grp, children=True, fullPath=True)):
                    kids = [k for k in (kids or []) if cmds.objExists(k)]
                    if kids:
                        cmds.delete(kids)
        guides.set_visible(True)
        fixed = sum(guides.restore_zeroed(i["group"]) for i in _infos())
    if fixed:
        utils.warn(TOOL, "%d guide(s) had been moved to the centre since the Build - put back where they were "
                   "built." % fixed)
    utils.info(TOOL, "back to the guides: adjust them, then Build again.")
    return True


# ---------------------------------------------------------------------------
# modules and templates
# ---------------------------------------------------------------------------

def _attach_spot(spec, side):
    """World position of the guide an attach spec ('module:part') points to, or None."""
    if ":" not in (spec or ""):
        return None
    mod_name, part = spec.split(":", 1)
    for sd in (side, "C", "L"):
        for g in guides.module_groups():
            info = guides.read(g)
            if info["name"] != mod_name or info["side"] != sd:
                continue
            names_ = info["settings"].get("names", {})
            for role, node in info["guides"].items():
                if role == part or names_.get(role) == part:
                    return cmds.xform(node, query=True, worldSpace=True, translation=True)
    return None


def add_module(mtype, side="C", name=None, height=None, settings_=None, keep=None, snap=False):
    """snap: place the new guides at the guide they hang from (e.g. fingers at a front paw)."""
    height = float(height or settings()["height"])
    mod = modules.MODULES[mtype]
    if side not in mod.SIDES:
        side = mod.SIDES[0]
    name = name or mtype
    for g in guides.module_groups():
        info = guides.read(g)
        if info["name"] == name and info["side"] == side:
            raise RuntimeError("there is already a %s module called '%s' on side %s." % (mtype, name, side))
    if settings_ is None:                                # your saved defaults for this kind of module
        saved = utils.load_setting("build_module_" + mtype, {})
        settings_ = dict(saved) if saved else None
    s = mod.complete(settings_ or mod.default_settings(side))
    if mtype == "chain" and not s["names"].get("name"):
        s["names"]["name"] = name                       # the chain's joints are named after the module
    if snap and keep is None and mtype != "chain":
        spot = _attach_spot(s.get("attach"), side)
        if spot:
            specs = mod.guide_specs(s, height, side)
            if specs:
                first = specs[0]["pos"]
                delta = [a - b for a, b in zip(spot, first)]
                keep = {sp["role"]: [p + d for p, d in zip(sp["pos"], delta)] for sp in specs}
    return guides.create(mod, side, name, s, height, keep=keep)


def biped(height=None):
    """Root, spine, neck, left arm / leg / fingers, then their right twins."""
    height = float(height or settings()["height"])
    if guides.module_groups():
        raise RuntimeError("there are guides already. Delete them first (or add modules one by one).")
    with utils.undo_chunk("gusrigBiped"):
        for mtype, side in (("root", "C"), ("spine", "C"), ("neck", "C"), ("face", "C"), ("arm", "L"), ("leg", "L"),
                            ("fingers", "L")):
            s = None
            if mtype == "face" and not utils.load_setting("build_module_face", {}):
                mod = modules.MODULES["face"]
                s = mod.complete(mod.default_settings("C"))
                s["options"].update(ears=False, upper_jaw=False, tongue=True)
            g = add_module(mtype, side, height=height, settings_=s)
            if side == "L":
                guides.mirror(g, modules.MODULES[mtype], height)
    utils.info(TOOL, "Biped guides made for a %g tall character. Place the left side, then Mirror guides." % height)


# animal presets of the quadruped template: proportions (x the head's height) and counts
ANIMALS = {
    "dog": {"spine_y": 0.57, "body": 1.0, "leg_y": 1.0, "neck": 3, "neck_rise": 0.06, "tail": 8, "tail_drop": 0.02,
            "toes": 4, "snout": 1.8},
    "horse": {"spine_y": 0.66, "body": 1.15, "leg_y": 1.18, "neck": 5, "neck_rise": 0.055, "tail": 6,
              "tail_drop": 0.05, "toes": 0, "snout": 2.6},
    "cat": {"spine_y": 0.52, "body": 0.95, "leg_y": 0.9, "neck": 2, "neck_rise": 0.07, "tail": 12, "tail_drop": 0.01,
            "toes": 4, "snout": 1.1},
    "rabbit": {"spine_y": 0.42, "body": 0.8, "leg_y": 0.72, "neck": 2, "neck_rise": 0.08, "tail": 3,
               "tail_drop": 0.0, "toes": 4, "snout": 1.2},
}
ANIMAL_NAMES = ["dog", "horse", "cat", "rabbit"]


def _quad_positions(h, a=None):
    """Guide spots of the quadruped template's centre modules (nose at +Z), for an animal preset."""
    a = a or ANIMALS["dog"]
    y, k = a["spine_y"], a["body"]
    spine = [[0, y * h, (-0.33 + 0.13 * i) * h * k] for i in range(5)]           # hips to shoulders
    n = a["neck"]
    neck = [[0, (y + 0.05 + a["neck_rise"] * i * 3.0 / n) * h, (0.27 * k + 0.06 * i * 3.0 / n) * h]
            for i in range(n)]
    head = [0, neck[-1][1] + 0.06 * h, neck[-1][2] + 0.06 * h]
    tail = [[0, (y - 0.01 - a["tail_drop"] * i) * h, (-0.38 * k - 0.05 * i * 8.0 / max(a["tail"], 1)) * h]
            for i in range(a["tail"] + 1)]
    return {
        "root": {"root": [0, 0, 0]},
        "spine": dict({"hips": [0, (y - 0.02) * h, -0.30 * h * k]}, **{"c%d" % i: p for i, p in enumerate(spine)}),
        "neck": dict({"c%d" % i: p for i, p in enumerate(neck)}, head=head),
        "tail": {"j%d" % i: p for i, p in enumerate(tail)},
    }


def _leg_positions(mod, s, h, a):
    """The leg's default guide spots stretched for the animal: taller legs, longer body (the ground stays)."""
    out = {}
    for sp in mod.guide_specs(s, h, "L"):
        x, y, z = sp["pos"]
        out[sp["role"]] = [x * a["body"], y * a["leg_y"], z * a["body"]]
    return out


def quadruped(height=None, animal="dog"):
    """Root, horizontal ribbon spine, neck / head, tail, front and back legs (left, then mirrored).
    animal: dog, horse, cat or rabbit (proportions and counts)."""
    height = float(height or settings()["height"])
    if guides.module_groups():
        raise RuntimeError("there are guides already. Delete them first (or add modules one by one).")
    a = ANIMALS.get(animal, ANIMALS["dog"])
    pos = _quad_positions(height, a)
    horizontal = {"aim": "X", "up": "Y", "up_mode": "world", "world_up": [0, 1, 0], "behavior_right": True}
    with utils.undo_chunk("gusrigQuadruped"):
        add_module("root", "C", height=height, keep=pos["root"])
        mod = modules.MODULES["spine"]
        s = mod.complete(mod.default_settings("C"))
        s["names"]["chain"] = ["spine_01", "spine_02", "spine_03", "spine_04", "spine_05"]
        s["options"]["joint_count"] = 5
        s["options"]["type"] = "ribbon"
        s["orient"] = dict(horizontal)
        add_module("spine", "C", height=height, settings_=s, keep=pos["spine"])
        mod = modules.MODULES["neck"]
        s = mod.complete(mod.default_settings("C"))
        s["names"]["chain"] = ["neck_%02d" % (i + 1) for i in range(a["neck"])]
        s["options"]["joint_count"] = a["neck"]
        s["attach"] = "spine:spine_05"
        s["orient"] = dict(horizontal)
        add_module("neck", "C", height=height, settings_=mod.complete(s), keep=pos["neck"])
        from gus_rigtool.builder import face
        mod = modules.MODULES["face"]
        s = mod.complete(utils.load_setting("build_module_face", {}) or mod.default_settings("C"))
        if not utils.load_setting("build_module_face", {}):
            s["options"].update(upper_jaw=True, tongue=True, ears=True)
        add_module("face", "C", height=height, settings_=s,
                   keep=face.positions(s, pos["neck"]["head"], 0.07 * height, snout=a["snout"], ears_up=True))
        mod = modules.MODULES["chain"]
        s = mod.complete(mod.default_settings("C"))
        s["names"]["name"], s["names"]["count"] = "tail", a["tail"]
        s["options"]["type"] = "fk + ik spline" if a["tail"] >= 5 else "fk"
        s["attach"] = "spine:hips"
        add_module("chain", "C", "tail", height=height, settings_=s, keep=pos["tail"])
        for mtype in ("front_leg", "back_leg"):
            mod = modules.MODULES[mtype]
            saved = utils.load_setting("build_module_" + mtype, {})
            s = mod.complete(dict(saved) if saved else mod.default_settings("L"))
            if not saved:
                s["options"]["toe_count"] = a["toes"]
            s = mod.complete(s)
            g = add_module(mtype, "L", height=height, settings_=s, keep=_leg_positions(mod, s, height, a))
            guides.mirror(g, modules.MODULES[mtype], height)
    utils.info(TOOL, "Quadruped (%s) guides made for a %g tall character (head height, nose towards +Z). Place the "
               "left side, then Mirror guides." % (animal, height))


def mirror_all(height=None):
    """Every left module's guides copied to the right."""
    height = float(height or settings()["height"])
    count = 0
    with utils.undo_chunk("gusrigMirrorGuides"):
        for g in guides.module_groups():
            info = guides.read(g)
            if info["side"] == "L":
                guides.mirror(g, modules.MODULES[info["type"]], height)
                count += 1
    utils.info(TOOL, "mirrored %d left module(s) to the right." % count)


def templates_dir():
    path = os.path.join(gus_rigtool.ROOT, "data", "templates")
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def save_template(path, height=None):
    data = {"version": gus_rigtool.__version__, "height": float(height or settings()["height"]), "modules": [],
            "names": names.settings()}
    for g in guides.module_groups():
        info = guides.read(g)
        data["modules"].append({"type": info["type"], "name": info["name"], "side": info["side"],
                                "settings": info["settings"], "positions": guides.positions(g)})
    with open(path, "w") as f:
        json.dump(data, f, indent=1)
    return len(data["modules"])


def load_template(path, use_names=True):
    with open(path) as f:
        data = json.load(f)
    if guides.module_groups():
        raise RuntimeError("there are guides already. Delete them first, then load the template.")
    if use_names and data.get("names"):
        utils.save_setting(names.SETTINGS_KEY, data["names"])
    with utils.undo_chunk("gusrigLoadTemplate"):
        for m in data["modules"]:
            add_module(m["type"], m["side"], m["name"], data.get("height"), m["settings"], keep=m["positions"])
    return len(data["modules"])
