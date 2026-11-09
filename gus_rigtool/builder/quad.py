"""
Quadruped legs, six joints each (+ pelvis / scapula above):
    Back leg  : (pelvis) femur, tibia, metatarsus (hock), ball (fetlock), toe (pastern), ball_end
    Front leg : scapula, humerus, radius, metacarpus (wrist), front_ball, front_toe, front_ball_end

    bind joints  <- blend(FK, IK)  (ikfk on the settings control, next to the paw)
    FK           upper, lower, meta, ball controls (+ the scapula / pelvis control)
    IK           paw control with a reverse paw: heel, tip, bank, ball roll (bends at the ball),
                 toe roll (bends at the toe joint), toe tap
                 'hock'  : IK upper -> hock in a hock control that turns around the ball
                           (ankle_bend on the paw adds to it) + IK hock -> ball
                 'spring': Maya's spring IK through the three bones (spring_bias on the paw)
    knee / elbow pole vector, spaces, stretch, bendy twist joints, optional extra toes / digits (curl / spread on
    the settings control) and, on the front leg, auto scapula (the scapula follows the paw).
"""

import math

import maya.cmds as cmds

from gus_rigtool.builder import controls, correctives, limb, mathx, names, ribbons
from gus_rigtool.builder.module_base import LIMB_ORIENT, Module, _mirror_specs

IK_TYPES = ["hock", "spring"]


class _QuadLeg(Module):
    SIDES = ("L", "R")
    ORIENT = LIMB_ORIENT
    FIRST = ""                   # scapula / pelvis
    LEG = []                     # upper, lower, meta, ball, toe, ball_end
    PIVOTS = ["heel", "paw_inner", "paw_outer"]
    CONTROLS = {"first": ["square_pin", 0.035], "fk": ["circle", 0.04], "ik": ["foot", 0.05],
                "hock": ["circle", 0.03], "pv": ["diamond_3d", 0.015], "settings": ["gear", 0.016],
                "bend": ["diamond", 0.022], "toe": ["circle", 0.01]}
    OPTIONS = {"ik_type": "hock", "stretch": False, "bendy": False, "twist_count": 4, "spaces": True,
               "ik_orient": "world", "ik_mirror": True, "no_flip": False, "pin": False,
               "bone_length": False, "toe_count": 0, "toes_from": "toe", "extra_spaces": "", "default_space": "root",
               "correctives": False}
    OPTION_LABELS = {
        "correctives": correctives.OPTION,
        "ik_type": ("Leg IK: hock control (ankle_bend) or spring solver", "choice", IK_TYPES),
        "stretch": ("IK stretch (a 'stretch' switch on the settings control)", "bool", None),
        "bendy": ("Bendy (ribbon with twist joints and bend controls)", "bool", None),
        "twist_count": ("Twist joints per segment (bendy)", "int", None),
        "spaces": ("Space switch on the paw and the pole vector", "bool", None),
        "ik_orient": ("Paw control axes", "choice", ["world", "joint"]),
        "ik_mirror": ("Right paw / pole vector move as the mirror of the left (move both: they mirror)", "bool", None),
        "no_flip": ("No-flip knee / elbow ('knee_mode' slider: 0 pole vector, 1 follows the paw; 'knee_twist')",
                    "bool", None),
        "pin": ("Knee / elbow pin ('pin' slider: it goes onto the pole vector; hock IK, stretch off)", "bool", None),
        "bone_length": ("Length per bone (upper / lower (/ meta) _length sliders; hock IK: stretch off)", "bool",
                        None),
        "extra_spaces": ("Extra spaces (label = node, ...)", "spaces", None),
        "default_space": ("Default space of the paw", "text", None),
        "toe_count": ("Number of toes / digits (0 = none; names and joints per toe in Names)", "count", None),
        "toes_from": ("Toes hang from (they follow it)", "choice", ["toe", "ball"]),
    }
    OPTION_GROUPS = [("Leg IK", ["ik_type", "ik_orient", "ik_mirror", "no_flip", "pin", "bone_length", "spaces", "extra_spaces", "default_space"]), ("Toes", ["toe_count", "toes_from"]),
                     ("Stretch and bendy", ["stretch", "bendy", "twist_count"]),
                     ("Extras", ["pelvis", "auto_scapula", "correctives"])]
    OPTION_NEEDS = {"options.twist_count": ("options.bendy", True), "names.toes": ("options.toe_count", ">0"),
                    "options.toes_from": ("options.toe_count", ">0"),
                    "names.toe_joints": ("options.toe_count", ">0"), "names.toe_pattern": ("options.toe_count", ">0"),
                    "names.toe_end": ("options.toe_count", ">0")}
    DESCRIPTION = ("A six-joint quadruped leg with a paw: FK and IK (hock control + ankle_bend, or spring "
                   "solver), knee / elbow pole vector, reverse paw (heel, ball, toe, tip roll, tap, bank), "
                   "spaces, optional toes, stretch, bendy; pelvis (back) or auto scapula (front).")

    def default_names(self):
        d = {r: r for r in [self.FIRST] + self.LEG + self.PIVOTS}
        d.update({"toes": ["toeA", "toeB", "toeC", "toeD"], "toe_joints": 2, "toe_pattern": "{toe}_{num:02d}",
                  "toe_end": "{toe}_end"})
        return d

    # -- which bones -------------------------------------------------------
    def has_first(self, s):
        return True

    TOE_BASE = "toe"

    def toes_base(self, s):
        """The leg joint the toes hang from: 'toe' (default) or 'ball'."""
        return "ball" if s["options"].get("toes_from") == "ball" else "toe"

    def toe_list(self, s):
        """The toe names to build: the first 'Number of toes' names (more are made up if needed)."""
        o, given = s["options"], list(s["names"].get("toes") or [])
        count = int(o.get("toe_count") or 0)
        if not count and o.get("toes"):                 # settings saved by 2.0.0 (a Toes checkbox)
            count = len(given)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        out = given[:count]
        i = 0
        while len(out) < count:
            name = "%s%s" % (self.TOE_BASE, letters[i % 26] + ("" if i < 26 else str(i // 26)))
            if name not in out:
                out.append(name)
            i += 1
        return out

    def roles(self, s):
        return ([self.FIRST] if self.has_first(s) else []) + list(self.LEG)

    def toe_parts(self, s, toe):
        n = s["names"]
        out = []
        for i in range(int(n.get("toe_joints", 2))):
            try:
                out.append(n["toe_pattern"].format(toe=toe, num=i + 1))
            except (KeyError, IndexError, ValueError):
                out.append("%s_%02d" % (toe, i + 1))
        try:
            out.append(n["toe_end"].format(toe=toe))
        except (KeyError, IndexError, ValueError):
            out.append(toe + "_end")
        return out

    # -- guides --------------------------------------------------------------
    POS = {}                     # role: [x, y, z] x height (left side)

    def guide_specs(self, s, h, side):
        n = s["names"]
        specs, prev = [], None
        for r in self.roles(s):
            specs.append({"role": r, "part": n[r], "pos": [v * h for v in self.POS[r]], "parent": prev})
            prev = r
        for r in self.PIVOTS:
            specs.append({"role": r, "part": n[r], "pos": [v * h for v in self.POS[r]], "parent": "ball",
                          "kind": "pivot"})
        toes = self.toe_list(s)
        if toes:
            base = self.toes_base(s)
            bx, by, bz = self.POS[base]
            for ti, toe in enumerate(toes):
                x = bx + (ti - (len(toes) - 1) / 2.0) * 0.012
                prev = base
                for j, part in enumerate(self.toe_parts(s, toe)):
                    role = "t%d_%d" % (ti, j)
                    specs.append({"role": role, "part": part, "pos": [x * h, by * h * 0.6, (bz + 0.012 * (j + 1)) * h],
                                  "parent": prev, "size": 0.5})
                    prev = role
        return _mirror_specs(specs, side)

    def preview_names(self, s, side):
        n = s["names"]
        out = [names.make(side, n[r], "jnt") for r in self.roles(s)]
        out += [names.make(side, n[r], "ctrl", "fk") for r in self.LEG[:5]]
        out += [names.make(side, n["ball"], "ctrl", "ik"), names.make(side, n[self.LEG[1]], "ctrl", "pv"),
                names.make(side, n["ball"], "ctrl", "settings")]
        if s["options"].get("ik_type", "hock") == "hock":
            out.append(names.make(side, n[self.LEG[2]], "ctrl", "hock"))
        if self.has_first(s):
            out.append(names.make(side, n[self.FIRST], "ctrl", "fk"))
        if True:
            for toe in self.toe_list(s):
                parts = self.toe_parts(s, toe)
                out += [names.make(side, p, "jnt") for p in parts] + \
                       [names.make(side, p, "ctrl", "fk") for p in parts[:-1]]
        if s["options"].get("bendy"):
            out += [names.make(side, "%s_twist_%02d" % (n[r], i + 1), "jnt")
                    for r in self.LEG[:2] for i in range(int(s["options"]["twist_count"]))]
        if s["options"].get("correctives"):
            out += [names.make(side, n[r] + "_cor", "jnt") for r in self.LEG[:4]]
        return out

    def build(self, ctx):
        return build_quad_leg(ctx, self)


class BackLeg(_QuadLeg):
    TYPE = "back_leg"
    LABEL = "Back leg (quadruped)"
    ATTACH = "spine:hips"
    FIRST = "pelvis"
    LEG = ["femur", "tibia", "metatarsus", "ball", "toe", "ball_end"]
    OPTIONS = dict(_QuadLeg.OPTIONS, pelvis=False)
    OPTION_LABELS = dict(_QuadLeg.OPTION_LABELS, pelvis=("Pelvis bone and control above the femur", "bool", None))
    POS = {"pelvis": [0.05, 0.56, -0.31], "femur": [0.10, 0.52, -0.33], "tibia": [0.11, 0.34, -0.26],
           "metatarsus": [0.11, 0.19, -0.40], "ball": [0.11, 0.035, -0.36], "toe": [0.11, 0.015, -0.33],
           "ball_end": [0.11, 0.0, -0.30],
           "heel": [0.11, 0.0, -0.39], "paw_inner": [0.085, 0.0, -0.345], "paw_outer": [0.135, 0.0, -0.345]}

    def has_first(self, s):
        return bool(s["options"].get("pelvis"))


class FrontLeg(_QuadLeg):
    TYPE = "front_leg"
    LABEL = "Front leg (quadruped)"
    ATTACH = "spine:spine_05"
    FIRST = "scapula"
    LEG = ["humerus", "radius", "metacarpus", "ball", "toe", "ball_end"]
    TOE_BASE = "front_toe"
    OPTIONS = dict(_QuadLeg.OPTIONS, auto_scapula=False)
    OPTION_LABELS = dict(_QuadLeg.OPTION_LABELS,
                         auto_scapula=("Auto scapula: follows the paw (auto_scapula 0-1 on the settings control)",
                                       "bool", None))
    def default_names(self):
        """The front paw's names start with 'front_', so they never clash with the back paw's."""
        d = _QuadLeg.default_names(self)
        for r in ("ball", "toe", "ball_end") + tuple(self.PIVOTS):
            d[r] = "front_" + r
        d["toes"] = ["front_" + t for t in d["toes"]]
        return d

    POS = {"scapula": [0.06, 0.64, 0.20], "humerus": [0.10, 0.50, 0.26], "radius": [0.10, 0.32, 0.20],
           "metacarpus": [0.10, 0.10, 0.24], "ball": [0.10, 0.035, 0.26], "toe": [0.10, 0.015, 0.29],
           "ball_end": [0.10, 0.0, 0.32],
           "heel": [0.10, 0.0, 0.235], "paw_inner": [0.075, 0.0, 0.27], "paw_outer": [0.125, 0.0, 0.27]}


# ===========================================================================
# build
# ===========================================================================

def _third(aim, up):
    return [a for a in "XYZ" if a not in (aim, up)][0]


def _local_dir(m, v):
    """World vector v in the axes of matrix m."""
    return tuple(mathx.dot(v, mathx.norm(m[r * 4:r * 4 + 3])) for r in range(3))


def _short(nodes):
    return [x.split("|")[-1] for x in nodes]


def _pivot(side, name, pos, parent):
    g = controls.group(names.make(side, name, "grp"), parent)
    cmds.xform(g, worldSpace=True, rotatePivot=pos, scalePivot=pos)
    return g


def _drive(plug, target, factor=1.0):
    if factor == 1.0:
        cmds.connectAttr(plug, target)
        return
    m = cmds.createNode("multDoubleLinear", name=target.split("|")[-1].replace(".", "_") + "_mul")
    cmds.setAttr(m + ".input2", factor)
    cmds.connectAttr(plug, m + ".input1")
    cmds.connectAttr(m + ".output", target)


def build_quad_leg(ctx, mod):
    side, n, opt = ctx.side, ctx.settings["names"], ctx.settings["options"]
    s = ctx.settings
    roles = mod.roles(s)
    first = 1 if mod.has_first(s) else 0
    up_r, low_r, meta_r, ball_r, toe_r, end_r = mod.LEG
    parts = [n[r] for r in roles]
    mats = ctx.chain(roles, plane_roles=[up_r, low_r, meta_r])
    m = dict(zip(roles, mats))
    face = ctx.aim_face()
    up = ctx.orient["up"].lstrip("-")
    sn = names.settings()
    nm = lambda part, kind, variant=None: names.make(side, part, kind, variant, sn)

    bind = limb.joint_chain(side, parts, mats, ctx.attach_joint or ctx.skeleton, None, ctx.radius)
    leg_parts, leg_mats = parts[first:], mats[first:]

    # scapula / pelvis control: pivot on the bone, shape out at the leg (like the clavicle)
    first_ctrl, first_off = None, None
    if first:
        reach = mathx.distance(mathx.position(mats[0]), mathx.position(mats[1]))
        sign = -1.0 if ctx.orient["aim"].startswith("-") else 1.0
        along = tuple((sign * reach if a == face else 0.0) for a in "XYZ")
        flip = tuple((sign if a == face else 1.0) for a in "XYZ")
        first_off, first_ctrl = controls.make(side, parts[0], ctx.shape("first"), ctx.size("first"), mats[0],
                                              ctx.module_ctrls, face, "fk", shape_offset=along, shape_flip=flip)
        cmds.parentConstraint(first_ctrl, bind[0], maintainOffset=False)

    # FK / IK chains follow the scapula / pelvis joint, else what the leg hangs from
    root_grp = controls.group(nm(leg_parts[0] + "_limb", "grp"), ctx.nodes)
    follow = bind[0] if first else ctx.attach_joint
    if follow:
        cmds.parentConstraint(follow, root_grp, maintainOffset=True)
        cmds.scaleConstraint(follow, root_grp, maintainOffset=True)
    fkj = limb.joint_chain(side, leg_parts, leg_mats, root_grp, "fk", ctx.radius * 0.7)
    ikj = limb.joint_chain(side, leg_parts, leg_mats, root_grp, "ik", ctx.radius * 0.7)
    limb.hide([fkj[0], ikj[0]])
    fk_offs, fk_ctrls = limb.fk_controls(side, fkj[:5], leg_parts[:5], ctx.shape("fk"), ctx.size("fk"), face,
                                         first_ctrl or ctx.module_ctrls)

    # settings control next to the paw
    ball_m = m[ball_r]
    up_dir = mathx.axis_of(ball_m, ctx.orient["up"])
    if side == "R" and ctx.orient.get("behavior_right", True):
        up_dir = mathx.scale(up_dir, -1.0)
    s_pos = mathx.add(mathx.position(m[meta_r]), mathx.scale(up_dir, ctx.height * 0.05))
    s_off, settings = controls.make(side, n[ball_r], ctx.shape("settings"), ctx.size("settings"),
                                    mathx.translate_matrix(s_pos), ctx.module_ctrls, "Z", "settings",
                                    lock=("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"))
    cmds.parentConstraint(bind[first + 3], s_off, maintainOffset=True)
    controls.separator(settings, "IK FK")
    blend = controls.add_float(settings, "ikfk", 0.0, 0.0, 1.0)

    # -- IK: the paw ----------------------------------------------------------
    ik_grp = controls.group(nm(n[ball_r] + "_ik", "grp"), ctx.ik_parent())
    paw_m = list(ball_m) if opt.get("ik_orient") == "joint" else mathx.translate_matrix(mathx.position(ball_m))
    mirrored = limb.mirrors(side, opt)
    ik_off, paw = controls.make(side, n[ball_r], ctx.shape("ik"), ctx.size("ik"), paw_m, ik_grp, "Y", "ik",
                                mirror=None if mirrored else "auto")
    hold = limb.mirror_control(side, n[ball_r] + "_ik", ik_off, paw) if mirrored else paw
    p = {r: ctx.pos(r) for r in (ball_r, toe_r, end_r) + tuple(mod.PIVOTS)}
    ball_pos = p[ball_r]
    if cmds.listRelatives(paw, shapes=True):
        cmds.move(0, -ball_pos[1], 0, paw + ".cv[*]", relative=True, worldSpace=True)    # shape on the ground
    # heel > tip > outer > inner > toe roll (at the toe joint) > ball roll (at the ball) > the leg
    #                             > toe tap (at the toe joint) > IK toe -> tip
    heel = _pivot(side, n[ball_r] + "_heelPivot", p["heel"], hold)
    tip = _pivot(side, n[ball_r] + "_tipPivot", p[end_r], heel)
    outer = _pivot(side, n[ball_r] + "_outerPivot", p["paw_outer"], tip)
    inner = _pivot(side, n[ball_r] + "_innerPivot", p["paw_inner"], outer)
    toe_roll = _pivot(side, n[ball_r] + "_toeRoll", p[toe_r], inner)
    ball_roll = _pivot(side, n[ball_r] + "_ballRoll", ball_pos, toe_roll)
    tap = _pivot(side, n[ball_r] + "_toeTap", p[toe_r], inner)

    controls.separator(paw, "paw")
    attrs = ["heel_roll", "ball_roll", "toe_roll", "tip_roll", "toe_tap", "bank", "heel_twist", "toe_twist"]
    hock_mode = opt.get("ik_type", "hock") == "hock"
    if hock_mode:
        attrs.append("ankle_bend")
    plugs = {a: controls.add_float(paw, a, 0.0) for a in attrs}
    bend = up                                                   # the leg bends around the plane normal
    _drive(plugs["heel_roll"], heel + ".rotateX", -1.0)
    _drive(plugs["ball_roll"], ball_roll + ".rotateX")
    _drive(plugs["toe_roll"], toe_roll + ".rotateX")
    _drive(plugs["tip_roll"], tip + ".rotateX")
    _drive(plugs["toe_tap"], tap + ".rotateX", -1.0)
    _drive(plugs["heel_twist"], heel + ".rotateY")
    _drive(plugs["toe_twist"], tip + ".rotateY")
    sign = -1.0 if side == "L" else 1.0
    cond = cmds.createNode("condition", name=nm(n[ball_r] + "_bank", "grp").replace("_grp", "_cond"))
    cmds.setAttr(cond + ".operation", 2)
    cmds.connectAttr(plugs["bank"], cond + ".firstTerm")
    cmds.connectAttr(plugs["bank"], cond + ".colorIfTrueR")
    cmds.setAttr(cond + ".colorIfFalseR", 0)
    cmds.setAttr(cond + ".colorIfTrueG", 0)
    cmds.connectAttr(plugs["bank"], cond + ".colorIfFalseG")
    _drive(cond + ".outColorR", outer + ".rotateZ", sign)
    _drive(cond + ".outColorG", inner + ".rotateZ", sign)

    pv_pos = mathx.pole_position(*[mathx.position(m[r]) for r in (up_r, low_r, meta_r)])
    pv_off, pv = controls.make(side, n[low_r], ctx.shape("pv"), ctx.size("pv"), mathx.translate_matrix(pv_pos),
                               ik_grp, "Y", "pv", lock=("rx", "ry", "rz", "sx", "sy", "sz", "v"),
                               mirror=None if mirrored else "auto")
    if mirrored:
        cmds.setAttr(pv_off + ".scaleX", -1)
    hock_ctrl = None
    if hock_mode:
        # the hock turns around the ball: ankle_bend group > hock control > IK femur -> hock
        bend_m = list(m[meta_r])
        bend_m[12:15] = ball_pos
        bend_grp = controls.group(nm(n[meta_r] + "_ankleBend", "grp"), ball_roll, bend_m)
        _drive(plugs["ankle_bend"], bend_grp + ".rotate" + bend)
        reach = mathx.sub(mathx.position(m[meta_r]), ball_pos)
        h_off, hock_ctrl = controls.make(side, n[meta_r], ctx.shape("hock"), ctx.size("hock"), bend_m, bend_grp,
                                         face, "hock", shape_offset=_local_dir(bend_m, reach), mirror=None,
                                         lock=("tx", "ty", "tz", "sx", "sy", "sz", "v"))
        # the leg IK handle sits in a 'reach' group at the ball: with stretch on it scales, so the hock
        # moves away from the ball as much as the metatarsus grows (the whole leg stretches evenly)
        reach = controls.group(nm(n[meta_r] + "_hockReach", "grp"), hock_ctrl, bend_m)
        leg_h = limb.ik_handle(side, n[up_r], ikj[0], ikj[2], "ikRPsolver", reach)
        limb.ik_handle(side, n[meta_r], ikj[2], ikj[3], "ikSCsolver", ball_roll)
        hock_point = controls.group(nm(n[meta_r] + "_hockPoint", "grp"), hock_ctrl,
                                    mathx.translate_matrix(mathx.position(m[meta_r])))
        stretch_end = None
        stretch_joints = ikj[0:4]
    else:
        try:
            import maya.mel as mel
            mel.eval("ikSpringSolver")                           # Maya's spring solver (built in)
        except Exception:
            pass
        leg_h = limb.ik_handle(side, n[up_r], ikj[0], ikj[3], "ikSpringSolver", ball_roll)
        bias = controls.add_float(paw, "spring_bias", 0.5, 0.0, 1.0)
        rev = cmds.createNode("reverse", name=nm(n[up_r] + "_springBias", "grp").replace("_grp", "_rev"))
        cmds.connectAttr(bias, rev + ".inputX")
        try:
            cmds.connectAttr(bias, leg_h + ".springAngleBias[0].springAngleBias_FloatValue", force=True)
            cmds.connectAttr(rev + ".outputX", leg_h + ".springAngleBias[1].springAngleBias_FloatValue", force=True)
        except RuntimeError:
            pass
        stretch_end = controls.group(nm(n[ball_r] + "_stretchEnd", "grp"), ball_roll,
                                     mathx.translate_matrix(ball_pos))
        stretch_joints = ikj[0:4]
    cmds.poleVectorConstraint(pv, leg_h)
    limb.ik_handle(side, n[toe_r], ikj[3], ikj[4], "ikSCsolver", toe_roll)       # ball bends at the ball
    limb.ik_handle(side, n[end_r], ikj[4], ikj[5], "ikSCsolver", tap)            # the toe bends at the toe

    if opt.get("no_flip"):
        limb.no_flip(side, n[low_r], leg_h, hold, mathx.position(m[up_r]), pv_pos, settings)
    extras = opt.get("pin") or opt.get("bone_length")
    if hock_mode and opt.get("stretch") and extras:
        from gus_rigtool.core import utils
        utils.warn("Build", "%s (%s): pin / length per bone are left out - with a hock IK they work when stretch "
                   "is off (or use the spring IK)." % (n[ball_r], side))
        extras = False
    lengths = pin = None
    if extras and opt.get("bone_length"):
        lengths = [controls.add_float(settings, a, 1.0, 0.1, 10.0) for a in ("upper_length", "lower_length")]
        if not hock_mode:
            lengths.append(controls.add_float(settings, "meta_length", 1.0, 0.1, 10.0))
    if extras and opt.get("pin"):
        if hock_mode:
            pin = controls.add_float(settings, "pin", 0.0, 0.0, 1.0)
        else:
            from gus_rigtool.core import utils
            utils.warn("Build", "%s (%s): the pin needs the hock IK (the spring IK bends 3 bones)." % (n[ball_r], side))
    if opt.get("stretch") or lengths or pin:
        on = controls.add_bool(settings, "stretch", False) if opt.get("stretch") else None
        start = controls.group(nm(n[up_r] + "_stretchStart", "grp"), root_grp,
                               mathx.translate_matrix(mathx.position(m[up_r])))
        if hock_mode and on:
            ratio = _even_stretch(side, n[ball_r], start, hock_ctrl, hock_point, ikj, on, ctx.scale_plug,
                                  ctx.orient["aim"], nm)
            for ax in "XYZ":
                cmds.connectAttr(ratio, reach + ".scale" + ax)
        elif hock_mode:                                   # femur + tibia reach the hock
            limb.stretch(side, n[ball_r], ikj[0:3], start, hock_point, None, ctx.scale_plug, ctx.orient["aim"],
                         lengths, pin, pv)
        else:
            limb.stretch(side, n[ball_r], stretch_joints, start, stretch_end, on, ctx.scale_plug,
                         ctx.orient["aim"], lengths, pin, pv)

    limb.blend(side, bind[first:], fkj, ikj, blend)
    limb.visibility_switch(side, n[ball_r], blend, [fk_offs[0]], [ik_off, pv_off])

    if opt.get("spaces", True):
        labels = ["world", "root", "cog", "chest"] if mod.TYPE == "front_leg" else ["world", "root", "cog"]
        targets = ctx.space_targets([(lb, ctx.space(lb)) for lb in labels])
        _sp, ik_off, paw = controls.add_spaces(side, n[ball_r] + "_ik", paw, ik_off, targets,
                                               default=ctx.space_default(targets, "root"))
        hold = controls.long(hold.split("|")[-1]) if mirrored else paw
        pv_targets = ctx.space_targets([("paw", hold), ("world", ctx.space("world")), ("root", ctx.space("root"))],
                                        extra=False)
        _sp, pv_off, pv = controls.add_spaces(side, n[low_r] + "_pv", pv, pv_off, pv_targets, default=0)

    # auto scapula: the scapula turns towards the paw (auto_scapula x ikfk)
    if mod.TYPE == "front_leg" and opt.get("auto_scapula") and first_ctrl:
        _auto_scapula(side, n, ctx, mats[0], first_off, first_ctrl, hold, settings, blend, nm)
        first_ctrl = cmds.ls(first_ctrl.split("|")[-1], long=True)[0]

    out = {"joints": dict(zip(parts, bind)), "spaces": {}, "follow": bind[-1], "settings_ctrl": settings}

    if mod.toe_list(s):                              # the toes follow the toe joint (or the ball)
        _toes(ctx, mod, side, n, bind[first + (3 if mod.toes_base(s) == "ball" else 4)], settings, out, nm)

    bends = []
    if opt.get("bendy"):
        parts_ = [n[roles[first]], n[roles[first + 1]]]
        corner = "elbow" if mod.TYPE == "front_leg" else "knee"
        corner = corner + "Corner" if corner in parts_ else corner
        twists, bends = ribbons.bendy_limb(side, parts_, (bind[first], bind[first + 1], bind[first + 2]),
                                           opt["twist_count"], ctx, up, corner)
        for t in twists:
            out["joints"][t.split("|")[-1]] = t

    if opt.get("correctives"):
        # shoulder / hip (the scapula / pelvis, else the spine joint -> the upper leg), knee / elbow, hock / wrist,
        # and the paw's bend (meta -> ball)
        upper = [bind[first - 1]] if first else [ctx.attach_joint]
        chain_ = upper + list(bind[first:first + 4])
        bending = roles[first:first + 4]
        correctives.make(ctx, [(n[r], chain_[i], chain_[i + 1]) for i, r in enumerate(bending)], out)

    paw_name = paw.split("|")[-1]
    limb.store_meta(settings, gusFkCtrls=_short(fk_ctrls), gusFkJoints=_short(fkj), gusIkJoints=_short(ikj),
                    gusIkCtrl=paw_name, gusPvCtrl=pv.split("|")[-1], gusBlend="ikfk", gusFootAttrs=attrs,
                    gusEnd="3", gusHockCtrl=hock_ctrl.split("|")[-1] if hock_ctrl else "",
                    gusTweaks=_short(bends))
    return out


def _auto_scapula(side, n, ctx, scap_m, off, ctrl, paw, settings, blend, nm):
    """A group between the scapula's offset and control, oriented between its rest and 'aimed at the
    paw' (weights from auto_scapula x ikfk)."""
    scap = n["scapula"]
    auto = controls.add_float(settings, "auto_scapula", 0.5, 0.0, 1.0)
    rest = controls.group(nm(scap + "_autoRest", "grp"), ctx.module_ctrls, scap_m)
    aim = controls.group(nm(scap + "_autoAim", "grp"), ctx.module_ctrls, scap_m)
    cmds.aimConstraint(paw, aim, maintainOffset=True, worldUpType="objectrotation",
                       worldUpObject=ctx.module_ctrls)
    drv = controls.group(nm(scap, "grp", "drv"), off, limb.world(off))
    cmds.parent(ctrl, drv)
    con = cmds.parentConstraint(rest, aim, drv, maintainOffset=True, skipTranslate=["x", "y", "z"])[0]
    cmds.setAttr(con + ".interpType", 2)
    w = cmds.parentConstraint(con, query=True, weightAliasList=True)
    amount = cmds.createNode("multDoubleLinear", name=nm(scap + "_auto", "grp").replace("_grp", "_mul"))
    cmds.connectAttr(auto, amount + ".input1")
    cmds.connectAttr(blend, amount + ".input2")
    rev = cmds.createNode("reverse", name=nm(scap + "_auto", "grp").replace("_grp", "_rev"))
    cmds.connectAttr(amount + ".output", rev + ".inputX")
    cmds.connectAttr(rev + ".outputX", con + "." + w[0])
    cmds.connectAttr(amount + ".output", con + "." + w[1])


def _even_stretch(side, part, hip, ball, hock_point, ikj, on_plug, scale_plug, aim, nm):
    """Hock leg stretch: femur, tibia and metatarsus all grow by the same ratio r, so the paw is reached
    and the hock angle stays. The hock handle sits at ball + r * w (w: the hock control's reach), and the
    upper leg (r * S long, S = femur + tibia) must reach it straight:  |v + r w| = r S  (v: hip -> ball)
        (w.w - S^2) r^2 + 2 (v.w) r + v.v = 0   ->   r = (-B - sqrt(B^2 - 4AC)) / 2A   (A < 0)
    r is 1 until the leg can't reach (and when 'stretch' is off). Returns the ratio plug."""
    axis = aim.lstrip("-")
    lengths = [abs(cmds.getAttr("%s.translate%s" % (j, axis))) for j in ikj[1:4]]
    upper = lengths[0] + lengths[1]
    name = lambda kind: nm(part + "_evenStretch" + kind, "grp").replace("_grp", "")

    def pos(node, tag):
        dm = cmds.createNode("decomposeMatrix", name=name("Dm" + tag))
        cmds.connectAttr(node + ".worldMatrix[0]", dm + ".inputMatrix")
        return dm + ".outputTranslate"

    def sub(a, b, tag):
        pm = cmds.createNode("plusMinusAverage", name=name(tag))
        cmds.setAttr(pm + ".operation", 2)
        cmds.connectAttr(a, pm + ".input3D[0]")
        cmds.connectAttr(b, pm + ".input3D[1]")
        return pm + ".output3D"

    def dot(a, b, tag):
        vp = cmds.createNode("vectorProduct", name=name(tag))
        cmds.setAttr(vp + ".operation", 1)
        cmds.setAttr(vp + ".normalizeOutput", 0)
        cmds.connectAttr(a, vp + ".input1")
        cmds.connectAttr(b, vp + ".input2")
        return vp + ".outputX"

    def md(a, b, op, tag):
        n = cmds.createNode("multiplyDivide", name=name(tag))
        cmds.setAttr(n + ".operation", op)
        for plug, value in (("input1X", a), ("input2X", b)):
            if isinstance(value, str):
                cmds.connectAttr(value, n + "." + plug)
            else:
                cmds.setAttr(n + "." + plug, value)
        return n + ".outputX"

    def pma(a, b, op, tag):
        n = cmds.createNode("plusMinusAverage", name=name(tag))
        cmds.setAttr(n + ".operation", op)
        for i, value in enumerate((a, b)):
            if isinstance(value, str):
                cmds.connectAttr(value, "%s.input1D[%d]" % (n, i))
            else:
                cmds.setAttr("%s.input1D[%d]" % (n, i), value)
        return n + ".output1D"

    h, b, p0 = pos(hip, "Hip"), pos(ball, "Ball"), pos(hock_point, "Hock")
    v = sub(b, h, "V")                                   # hip -> ball
    w = sub(p0, b, "W")                                  # ball -> hock (the reach)
    s = upper
    if scale_plug:
        s = md(scale_plug, upper, 1, "S")
    s2 = md(s, s, 1, "S2")
    a_ = pma(dot(w, w, "WW"), s2, 2, "A")                # A = w.w - S^2
    b_ = md(dot(v, w, "VW"), 2.0, 1, "B")                # B = 2 v.w
    c_ = dot(v, v, "VV")                                 # C = v.v
    disc = pma(md(b_, b_, 1, "BB"), md(md(a_, c_, 1, "AC"), 4.0, 1, "AC4"), 2, "Disc")
    clamp0 = cmds.createNode("clamp", name=name("DiscPos"))
    cmds.setAttr(clamp0 + ".maxR", 1e12)
    cmds.connectAttr(disc, clamp0 + ".inputR")
    root = md(clamp0 + ".outputR", 0.5, 3, "Sqrt")
    num = pma(md(b_, -1.0, 1, "NegB"), root, 2, "Num")   # -B - sqrt(disc)
    ratio = md(num, md(a_, 2.0, 1, "A2"), 2, "Ratio")
    big = cmds.createNode("condition", name=name("AtLeast1"))      # r > 1 ? r : 1
    cmds.setAttr(big + ".operation", 2)
    cmds.connectAttr(ratio, big + ".firstTerm")
    cmds.setAttr(big + ".secondTerm", 1.0)
    cmds.connectAttr(ratio, big + ".colorIfTrueR")
    cmds.setAttr(big + ".colorIfFalseR", 1.0)
    onoff = cmds.createNode("blendTwoAttr", name=name("OnOff"))
    cmds.setAttr(onoff + ".input[0]", 1.0)
    cmds.connectAttr(big + ".outColorR", onoff + ".input[1]")
    cmds.connectAttr(on_plug, onoff + ".attributesBlender")
    for j, _length in zip(ikj[1:4], lengths):
        plug = "%s.translate%s" % (j, axis)
        mul = cmds.createNode("multDoubleLinear", name=name("Len_" + j.split("|")[-1]))
        cmds.setAttr(mul + ".input1", cmds.getAttr(plug))
        cmds.connectAttr(onoff + ".output", mul + ".input2")
        cmds.connectAttr(mul + ".output", plug)
    return onoff + ".output"


def _toes(ctx, mod, side, n, ball_joint, settings, out, nm):
    """Toe chains under the ball joint, FK controls that follow it, curl / spread on the settings control."""
    s = ctx.settings
    toes = mod.toe_list(s)
    controls.separator(settings, "toes")
    curl = controls.add_float(settings, "toes_curl", 0.0)
    spread = controls.add_float(settings, "toes_spread", 0.0)
    aim, up = ctx.orient["aim"].lstrip("-"), ctx.orient["up"].lstrip("-")
    bend_axis = _third(aim, up)
    grp = controls.group(nm(n["ball"] + "_toes", "grp"), ctx.module_ctrls)
    cmds.parentConstraint(ball_joint, grp, maintainOffset=True)
    for ti, toe in enumerate(toes):
        parts = mod.toe_parts(s, toe)
        roles = ["t%d_%d" % (ti, j) for j in range(len(parts))]
        mats = ctx.chain(roles)
        bind = limb.joint_chain(side, parts, mats, ball_joint, None, ctx.radius * 0.4)
        offs, ctrls = limb.fk_controls(side, bind[:-1], parts[:-1], ctx.shape("toe"), ctx.size("toe"),
                                       ctx.aim_face(), grp)
        spread_w = (ti - (len(toes) - 1) / 2.0) / max(1.0, (len(toes) - 1) / 2.0)
        for j, (off, ctrl) in enumerate(zip(_short(offs), _short(ctrls))):
            off = controls.long(off)
            drv = controls.group(names.make(side, parts[j], "grp", "drv"), off, limb.world(off))
            cmds.parent(controls.long(ctrl), drv)
            cmds.connectAttr(curl, drv + ".rotate" + bend_axis)
            if j == 0 and abs(spread_w) > 1e-6:
                _drive(spread, drv + ".rotate" + up, spread_w * 0.5)
        for p_, j_ in zip(parts, bind):
            out["joints"][p_] = j_


# ===========================================================================
# IK -> FK help for the hock: turn the hock control so the IK hock lands on the FK one
# ===========================================================================

def _rotation_between(a, b):
    """Row-vector rotation matrix turning direction a onto direction b."""
    a, b = mathx.norm(a), mathx.norm(b)
    axis = mathx.cross(a, b)
    s = mathx.length(axis)
    c = max(-1.0, min(1.0, mathx.dot(a, b)))
    if s < 1e-9:
        return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    x, y, z = [v / s for v in axis]
    ang = math.atan2(s, c)
    cs, sn, t = math.cos(ang), math.sin(ang), 1 - math.cos(ang)
    col = [[t * x * x + cs, t * x * y - sn * z, t * x * z + sn * y],          # column-vector form
           [t * x * y + sn * z, t * y * y + cs, t * y * z - sn * x],
           [t * x * z - sn * y, t * y * z + sn * x, t * z * z + cs]]
    m = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
    for r in range(3):
        for k in range(3):
            m[r * 4 + k] = col[k][r]                                           # transposed: row vectors
    return m


def match_hock(hock, ik_hock_joint, fk_hock_joint, iterations=3):
    """Turn the hock control (pivot at the ball) so the IK hock goes where the FK hock is."""
    from gus_rigtool.core import mirror_engine as me
    for _ in range(iterations):
        hm = limb.world(hock)
        pivot = hm[12:15]
        cur = mathx.sub(mathx.position(limb.world(ik_hock_joint)), pivot)
        want = mathx.sub(mathx.position(limb.world(fk_hock_joint)), pivot)
        if mathx.length(cur) < 1e-9 or mathx.length(want) < 1e-9:
            return
        new = me.mul(hm, _rotation_between(cur, want))
        new[12:15] = pivot
        limb.set_world(hock, new, translate=False)
