"""
Face: the head's parts, each on its own switch. It hangs from the head (neck:head).

    jaw (+ chin)  upper jaw / snout   mouth master + lips (follow the jaw)   eyes + eye targets
    eyelids (blink, blink height, follow the eye)   brows   cheeks   nose + nostrils   ears
    tongue   teeth

Left / right parts are placed on the left; the right side is their mirror (symmetric face).

Lips follow the jaw: each lip control has 'jaw_follow' (upper 0, corners 0.5, lower 1); the jaw
control's 'lips_seal' pulls every lip to 0.5 so the mouth stays closed while the jaw opens. The
mouth master moves every lip.
"""

import maya.cmds as cmds

from gus_rigtool.builder import controls, limb, mathx, names
from gus_rigtool.builder.module_base import Module

FACE_ORIENT = {"aim": "X", "up": "Y", "up_mode": "world", "world_up": [0, 1, 0], "behavior_right": True}

# guide spots in head units (left side; x out, y up, z forward), from the head joint
OFFSETS = {
    "jaw": [0, -0.15, 0.15], "jaw_end": [0, -0.62, 0.78],
    "upper_jaw": [0, 0.0, 0.2], "upper_jaw_end": [0, -0.25, 0.9],
    "lip_upper": [0, -0.36, 0.86], "lip_lower": [0, -0.5, 0.83], "lip_corner": [0.22, -0.43, 0.74],
    "lip_upper_side": [0.12, -0.37, 0.83], "lip_lower_side": [0.12, -0.49, 0.8],
    "eye": [0.2, 0.25, 0.58], "lid_upper": [0.2, 0.4, 0.74], "lid_lower": [0.2, 0.1, 0.74],
    "brow_inner": [0.08, 0.48, 0.74], "brow_mid": [0.2, 0.53, 0.74], "brow_outer": [0.32, 0.47, 0.62],
    "cheek": [0.32, -0.08, 0.62], "nose": [0, 0.02, 0.98], "nostril": [0.08, -0.06, 0.9],
    "teeth_upper": [0, -0.33, 0.76], "teeth_lower": [0, -0.48, 0.73],
    "ear_base": [0.72, 0.12, 0.0], "ear_tip": [0.9, 0.3, -0.12],
    "tongue_base": [0, -0.38, 0.25], "tongue_tip": [0, -0.42, 0.72],
}
SNOUT = ("jaw_end", "upper_jaw_end", "lip_upper", "lip_lower", "lip_corner", "lip_upper_side", "lip_lower_side",
         "nose", "nostril", "teeth_upper", "teeth_lower", "tongue_tip")
PARTS = ("jaw", "upper_jaw", "lips", "lip_detail", "eyes", "eyelids", "brows", "cheeks", "nose", "ears", "tongue",
         "teeth")


def positions(s, origin, unit, snout=1.0, ears_up=False):
    """{role: world position} for a face of this size: origin = the head joint, unit = head size,
    snout = how long the muzzle is (1 human, ~1.8 dog), ears_up = ears on top (animals)."""
    off = dict(OFFSETS)
    if ears_up:
        off["ear_base"], off["ear_tip"] = [0.35, 0.55, 0.0], [0.45, 1.25, -0.15]
    out = {}
    for role, o in off.items():
        z = o[2] * (snout if role in SNOUT else 1.0)
        out[role] = [origin[0] + o[0] * unit, origin[1] + o[1] * unit, origin[2] + z * unit]
    n = s["names"]
    for key, count in (("ear", int(n.get("ear_joints", 3))), ("tongue", int(n.get("tongue_joints", 4)))):
        a, b = out.pop(key + "_base"), out.pop(key + "_tip")
        for i in range(count + 1):
            out["%s%d" % (key, i)] = mathx.lerp(a, b, i / float(count))
    return out


class Face(Module):
    TYPE = "face"
    LABEL = "Face"
    SIDES = ("C",)
    ATTACH = "neck:head"
    ORIENT = FACE_ORIENT
    CONTROLS = {"jaw": ["half_circle", 0.035], "upper_jaw": ["half_circle", 0.035], "mouth": ["rectangle", 0.03],
                "lip": ["sphere", 0.006], "eyes_target": ["rectangle", 0.03], "eye_target": ["circle", 0.01],
                "lid": ["half_circle", 0.012], "brow": ["triangle", 0.008], "cheek": ["circle", 0.01],
                "nose": ["diamond", 0.01], "nostril": ["circle", 0.005], "ear": ["circle", 0.012],
                "tongue": ["circle", 0.008], "teeth": ["square", 0.012]}
    OPTIONS = {"jaw": True, "upper_jaw": False, "lips": True, "lip_detail": False, "lip_falloff": False, "eyes": True, "eyelids": True,
               "brows": True, "cheeks": True, "nose": True, "ears": True, "tongue": False, "teeth": True}
    OPTION_LABELS = {
        "jaw": ("Jaw (jaw + chin joints; lips_seal on the jaw control)", "bool", None),
        "upper_jaw": ("Upper jaw / snout control (lifts the snout, nose and upper lip)", "bool", None),
        "lips": ("Lips: upper, lower, corners + mouth master (they follow the jaw)", "bool", None),
        "lip_detail": ("More lip controls (upper / lower, left and right)", "bool", None),
        "lip_falloff": ("Side lips follow their corner and the middle lip (half each; 'falloff' on each)", "bool",
                        None),
        "eyes": ("Eyes aimed at eye targets (main target: head / world space)", "bool", None),
        "eyelids": ("Eyelids: blink, blink_height, lids_follow on each eye target", "bool", None),
        "brows": ("Brows: inner, mid, outer on each side", "bool", None),
        "cheeks": ("Cheeks (follow the jaw a little: jaw_follow)", "bool", None),
        "nose": ("Nose tip + nostrils", "bool", None),
        "ears": ("Ears: a chain on each side with curl", "bool", None),
        "tongue": ("Tongue: a chain that follows the jaw", "bool", None),
        "teeth": ("Teeth: upper (head), lower (jaw)", "bool", None),
    }
    OPTION_GROUPS = [("Mouth", ["jaw", "upper_jaw", "lips", "lip_detail", "lip_falloff", "teeth", "tongue"]),
                     ("Eyes and brows", ["eyes", "eyelids", "brows"]), ("Head", ["cheeks", "nose", "ears"])]
    OPTION_NEEDS = {"options.lip_detail": ("options.lips", True), "options.lip_falloff": ("options.lip_detail", True), "options.eyelids": ("options.eyes", True),
                    "names.ear_joints": ("options.ears", True), "names.tongue_joints": ("options.tongue", True)}
    DESCRIPTION = ("The head's parts, each on its own switch: jaw (lips_seal), upper jaw, mouth master and lips "
                   "(jaw_follow), eyes and eye targets, eyelids (blink), brows, cheeks, nose, ears, tongue, teeth. "
                   "Place the left side; the right is its mirror.")

    def default_names(self):
        return {"jaw": "jaw", "jaw_end": "chin", "upper_jaw": "upper_jaw", "upper_jaw_end": "snout",
                "mouth": "mouth", "lip_upper": "lip_upper", "lip_lower": "lip_lower", "lip_corner": "lip_corner",
                "lip_upper_side": "lip_upper_side", "lip_lower_side": "lip_lower_side",
                "eye": "eye", "eye_target": "eye_target", "eyes_target": "eyes_target",
                "lid_upper": "lid_upper", "lid_lower": "lid_lower",
                "brow_inner": "brow_inner", "brow_mid": "brow_mid", "brow_outer": "brow_outer",
                "cheek": "cheek", "nose": "nose", "nostril": "nostril",
                "ear": "ear", "ear_joints": 3, "tongue": "tongue", "tongue_joints": 4,
                "teeth_upper": "teeth_upper", "teeth_lower": "teeth_lower"}

    # -- which guides --------------------------------------------------------
    def roles(self, s):
        o, n = s["options"], s["names"]
        r = []
        if o.get("jaw"):
            r += ["jaw", "jaw_end"]
        if o.get("upper_jaw"):
            r += ["upper_jaw", "upper_jaw_end"]
        if o.get("lips"):
            r += ["lip_upper", "lip_lower", "lip_corner"]
            if o.get("lip_detail"):
                r += ["lip_upper_side", "lip_lower_side"]
        if o.get("eyes"):
            r += ["eye"]
            if o.get("eyelids"):
                r += ["lid_upper", "lid_lower"]
        if o.get("brows"):
            r += ["brow_inner", "brow_mid", "brow_outer"]
        if o.get("cheeks"):
            r += ["cheek"]
        if o.get("nose"):
            r += ["nose", "nostril"]
        if o.get("teeth"):
            r += ["teeth_upper", "teeth_lower"]
        if o.get("ears"):
            r += ["ear%d" % i for i in range(int(n.get("ear_joints", 3)) + 1)]
        if o.get("tongue"):
            r += ["tongue%d" % i for i in range(int(n.get("tongue_joints", 4)) + 1)]
        return r

    def chain_parts(self, s, key):
        n = s["names"]
        count = int(n.get(key + "_joints", 3))
        return ["%s_%02d" % (n[key], i + 1) for i in range(count)] + ["%s_end" % n[key]]

    def part_name(self, s, role):
        n = s["names"]
        for key in ("ear", "tongue"):
            if role.startswith(key) and role[len(key):].isdigit():
                return self.chain_parts(s, key)[int(role[len(key):])]
        return n.get(role, role)

    def guide_specs(self, s, h, side):
        pos = positions(s, [0, 0.89 * h, 0.0], 0.1 * h)
        specs = []
        for role in self.roles(s):
            spec = {"role": role, "part": self.part_name(s, role), "pos": pos[role], "size": 0.45}
            for key in ("ear", "tongue", "jaw", "upper_jaw"):
                if role.startswith(key) and role[len(key):].isdigit() and int(role[len(key):]) > 0:
                    spec["parent"] = "%s%d" % (key, int(role[len(key):]) - 1)
            if role.endswith("_end"):
                spec["parent"] = role[:-4]
            specs.append(spec)
        return specs

    def preview_names(self, s, side):
        o, out = s["options"], []
        for role in self.roles(s):
            part = self.part_name(s, role)
            sided = role not in ("jaw", "jaw_end", "upper_jaw", "upper_jaw_end", "lip_upper", "lip_lower", "nose",
                                 "teeth_upper", "teeth_lower") and not role.startswith("tongue")
            for sd in (("L", "R") if sided else ("C",)):
                out.append(names.make(sd, part, "jnt"))
        if o.get("eyes"):
            out.append(names.make("C", s["names"]["eyes_target"], "ctrl"))
        if o.get("lips"):
            out.append(names.make("C", s["names"]["mouth"], "ctrl"))
        return out

    def build(self, ctx):
        return build_face(ctx, self)


# ===========================================================================
# build
# ===========================================================================

def _lip_falloff(side, part, p, parent, corner, middle, sn):
    """A group above a side lip that moves half as much as its corner and half as much as the middle lip
    (scaled by 'falloff' on the side lip, 0-1). Returns the group (its '<name>_amount' node takes 'falloff')."""
    g = controls.group(names.make(side, part + "_falloff", "grp", None, sn), parent, mathx.translate_matrix(p))
    pma = cmds.createNode("plusMinusAverage", name=g.split("|")[-1] + "_sum")
    for i, src in enumerate((corner, middle)):
        if src:
            cmds.connectAttr(src + ".translate", "%s.input3D[%d]" % (pma, i))
    amt = cmds.createNode("multiplyDivide", name=g.split("|")[-1] + "_amount")
    cmds.connectAttr(pma + ".output3D", amt + ".input1")
    cmds.connectAttr(amt + ".output", g + ".translate")
    return g


def _blend_weights(con, follow_plug, nm):
    """A two-target constraint: first target 1 - f, second target f."""
    w = (cmds.parentConstraint if cmds.nodeType(con) == "parentConstraint" else cmds.orientConstraint)(
        con, query=True, weightAliasList=True)
    rev = cmds.createNode("reverse", name=nm)
    cmds.connectAttr(follow_plug, rev + ".inputX")
    cmds.connectAttr(rev + ".outputX", con + "." + w[0])
    cmds.connectAttr(follow_plug, con + "." + w[1])


def build_face(ctx, mod):
    s, o = ctx.settings, ctx.settings["options"]
    n = s["names"]
    sn = names.settings()
    head_j = ctx.attach_joint or ctx.skeleton
    root = ctx.module_ctrls                                  # follows the head
    r = ctx.radius * 0.35
    out = {"joints": {}, "spaces": {}, "follow": None}

    def P(role, side="L"):
        p = list(ctx.pos(role))
        return [-p[0], p[1], p[2]] if side == "R" else p

    def keep(side, part, j):
        out["joints"][names.make(side, part, "jnt", None, sn)] = j

    def single(side, part, p, joint_parent, ctrl_parent, kind, lock=("v",)):
        m = mathx.translate_matrix(p)
        j = limb.joint_chain(side, [part], [m], joint_parent, None, r)[0]
        off, c = controls.make(side, part, ctx.shape(kind), ctx.size(kind), m, ctrl_parent, "Z", mirror=None,
                               lock=lock)
        cmds.parentConstraint(c, j, maintainOffset=False)
        cmds.scaleConstraint(c, j, maintainOffset=False)
        keep(side, part, j)
        return j, off, c

    def chain(side, pts, parts, joint_parent, world_up):
        kw = {"aim": "X", "up": "Y", "up_mode": "world", "world_up": world_up}
        mats = mathx.mirrored_chain_matrices(pts, True, **kw) if side == "R" else mathx.chain_matrices(pts, **kw)
        joints = limb.joint_chain(side, parts, mats, joint_parent, None, r)
        for p_, j in zip(parts, joints):
            keep(side, p_, j)
        return joints, mats

    def follow_group(side, part, p, jaw_ctrl, upper, default, ctrl_holder):
        """A group at p that follows the head (upper) or the jaw by ctrl.jaw_follow."""
        g = controls.group(names.make(side, part + "_jawFollow", "grp", None, sn), root, mathx.translate_matrix(p))
        if jaw_ctrl:
            con = cmds.parentConstraint(upper, jaw_ctrl, g, maintainOffset=True)[0]
            cmds.setAttr(con + ".interpType", 2)
            ctrl_holder.append((con, default))
        return g

    # -- jaw / upper jaw --------------------------------------------------------
    jaw_j = jaw_ctrl = None
    upper_j, upper_ctrl = head_j, root
    if o.get("upper_jaw"):
        joints, mats = chain("C", [P("upper_jaw"), P("upper_jaw_end")], [n["upper_jaw"], n["upper_jaw_end"]], head_j,
                             [0, 1, 0])
        reach = mathx.distance(P("upper_jaw"), P("upper_jaw_end"))
        _o, upper_ctrl = controls.make("C", n["upper_jaw"], ctx.shape("upper_jaw"), ctx.size("upper_jaw"), mats[0],
                                       root, "Y", mirror=None, shape_offset=(reach * 0.8, 0, 0))
        cmds.parentConstraint(upper_ctrl, joints[0], maintainOffset=False)
        upper_j = joints[0]
    if o.get("jaw"):
        joints, mats = chain("C", [P("jaw"), P("jaw_end")], [n["jaw"], n["jaw_end"]], head_j, [0, 1, 0])
        reach = mathx.distance(P("jaw"), P("jaw_end"))
        _o, jaw_ctrl = controls.make("C", n["jaw"], ctx.shape("jaw"), ctx.size("jaw"), mats[0], root, "Y",
                                     mirror=None, shape_offset=(reach * 0.9, 0, 0))
        cmds.parentConstraint(jaw_ctrl, joints[0], maintainOffset=False)
        jaw_j = joints[0]
        out["spaces"]["jaw"] = jaw_ctrl
    lower_j, lower_ctrl = (jaw_j, jaw_ctrl) if jaw_j else (head_j, root)

    # -- teeth, tongue, nose ---------------------------------------------------
    if o.get("teeth"):
        single("C", n["teeth_upper"], P("teeth_upper"), upper_j, upper_ctrl, "teeth")
        single("C", n["teeth_lower"], P("teeth_lower"), lower_j, lower_ctrl, "teeth")
    if o.get("tongue"):
        count = int(n.get("tongue_joints", 4))
        parts = mod.chain_parts(s, "tongue")
        joints, _m = chain("C", [P("tongue%d" % i) for i in range(count + 1)], parts, lower_j, [0, 1, 0])
        limb.fk_controls("C", joints[:-1], parts[:-1], ctx.shape("tongue"), ctx.size("tongue"), "X", lower_ctrl)
    if o.get("nose"):
        _j, _off, nose = single("C", n["nose"], P("nose"), upper_j, upper_ctrl, "nose")
        for side in ("L", "R"):
            single(side, n["nostril"], P("nostril", side), upper_j, nose, "nostril")

    # -- lips: mouth master + lips that follow the jaw --------------------------
    if o.get("lips"):
        center = mathx.lerp(P("lip_upper"), P("lip_lower"), 0.5)
        space = controls.group(names.make("C", n["mouth"] + "_space", "grp", None, sn), root,
                               mathx.translate_matrix(center))
        if jaw_ctrl:
            con = cmds.parentConstraint(upper_ctrl, jaw_ctrl, space, maintainOffset=True)[0]
            cmds.setAttr(con + ".interpType", 2)
            w = cmds.parentConstraint(con, query=True, weightAliasList=True)
            for alias in w:
                cmds.setAttr(con + "." + alias, 0.5)
        _mo, mouth = controls.make("C", n["mouth"], ctx.shape("mouth"), ctx.size("mouth"),
                                   mathx.translate_matrix(mathx.add(center, [0, 0, ctx.size("mouth") * 1.5])), space,
                                   "Z", mirror=None)
        seal = controls.add_float(jaw_ctrl, "lips_seal", 0.0, 0.0, 1.0) if jaw_ctrl else None
        lips = [("lip_upper", "C", 0.0), ("lip_lower", "C", 1.0), ("lip_corner", "L", 0.5), ("lip_corner", "R", 0.5)]
        if o.get("lip_detail"):
            lips += [(role, side, f) for role, f in (("lip_upper_side", 0.15), ("lip_lower_side", 0.85))
                     for side in ("L", "R")]
        made = {}
        for role, side, default in lips:
            p = P(role, side)
            holder = []
            g = follow_group(side, n[role], p, jaw_ctrl, upper_ctrl, default, holder)
            # the mouth master moves every lip: zero group at the mouth centre that copies its channels
            at = controls.group(names.make(side, n[role] + "_mouthAt", "grp", None, sn), g,
                                mathx.translate_matrix(center))
            drv = controls.group(names.make(side, n[role] + "_mouth", "grp", "drv", sn), at,
                                 mathx.translate_matrix(center))
            for ch in ("translate", "rotate", "scale"):
                cmds.connectAttr(mouth + "." + ch, drv + "." + ch)
            under = drv
            if o.get("lip_falloff") and role in ("lip_upper_side", "lip_lower_side"):
                under = _lip_falloff(side, n[role], p, drv, made.get(("lip_corner", side)),
                                     made.get(("lip_upper" if role == "lip_upper_side" else "lip_lower", "C")), sn)
            j, off, c = single(side, n[role], p, head_j, under, "lip")
            made[(role, side)] = c
            if under is not drv:
                plug = controls.add_float(c, "falloff", 0.5, 0.0, 1.0)     # 0.5: half the corner + half the middle
                for ax in "XYZ":
                    cmds.connectAttr(plug, under.split("|")[-1] + "_amount.input2" + ax)
            if holder:
                follow = controls.add_float(c, "jaw_follow", default, 0.0, 1.0)
                plug = follow
                if seal:                                  # lips_seal pulls every lip to 0.5
                    bl = cmds.createNode("blendTwoAttr", name=names.make(side, n[role] + "_seal", "grp", None, sn)
                                         .replace("_grp", ""))
                    cmds.connectAttr(follow, bl + ".input[0]")
                    cmds.setAttr(bl + ".input[1]", 0.5)
                    cmds.connectAttr(seal, bl + ".attributesBlender")
                    plug = bl + ".output"
                _blend_weights(holder[0][0], plug, names.make(side, n[role] + "_jawFollow", "grp", None, sn)
                               .replace("_grp", "_rev"))

    # -- cheeks (follow the jaw a little), brows -------------------------------
    if o.get("cheeks"):
        for side in ("L", "R"):
            holder = []
            g = follow_group(side, n["cheek"], P("cheek", side), jaw_ctrl, upper_ctrl, 0.3, holder)
            _j, _off, c = single(side, n["cheek"], P("cheek", side), head_j, g, "cheek")
            if holder:
                _blend_weights(holder[0][0], controls.add_float(c, "jaw_follow", 0.3, 0.0, 1.0),
                               names.make(side, n["cheek"] + "_jawFollow", "grp", None, sn).replace("_grp", "_rev"))
    if o.get("brows"):
        for side in ("L", "R"):
            for role in ("brow_inner", "brow_mid", "brow_outer"):
                single(side, n[role], P(role, side), head_j, root, "brow")

    # -- eyes, eye targets, eyelids -------------------------------------------
    if o.get("eyes"):
        eye_l = P("eye")
        dist = max(ctx.size("eyes_target") * 6.0, abs(eye_l[0]) * 6.0)
        main_p = [0.0, eye_l[1], eye_l[2] + dist]
        t_off, target = controls.make("C", n["eyes_target"], ctx.shape("eyes_target"), ctx.size("eyes_target"),
                                      mathx.translate_matrix(main_p), root, "Z", mirror=None)
        for side in ("L", "R"):
            ep = P("eye", side)
            eye_j = limb.joint_chain(side, [n["eye"]], [mathx.translate_matrix(ep)], head_j, None, r)[0]
            keep(side, n["eye"], eye_j)
            _to, et = controls.make(side, n["eye_target"], ctx.shape("eye_target"), ctx.size("eye_target"),
                                    mathx.translate_matrix([ep[0], ep[1], main_p[2]]), target, "Z", mirror=None)
            cmds.aimConstraint(et, eye_j, maintainOffset=True, aimVector=(0, 0, 1), upVector=(0, 1, 0),
                               worldUpType="objectrotation", worldUpVector=(0, 1, 0), worldUpObject=root)
            if not o.get("eyelids"):
                continue
            controls.separator(et, "lids")
            blink = controls.add_float(et, "blink", 0.0, 0.0, 1.0)
            height = controls.add_float(et, "blink_height", 0.5, 0.0, 1.0)
            follow = controls.add_float(et, "lids_follow", 0.3, 0.0, 1.0)
            rest = controls.group(names.make(side, n["eye"] + "_lidRest", "grp", None, sn), root,
                                  mathx.translate_matrix(ep))
            lid_space = controls.group(names.make(side, n["eye"] + "_lidFollow", "grp", None, sn), root,
                                       mathx.translate_matrix(ep))
            con = cmds.parentConstraint(rest, eye_j, lid_space, maintainOffset=True,     # an offset per target
                                        skipTranslate=["x", "y", "z"])[0]
            cmds.setAttr(con + ".interpType", 2)
            _blend_weights(con, follow, names.make(side, n["eye"] + "_lidFollow", "grp", None, sn)
                           .replace("_grp", "_rev"))
            rev_h = cmds.createNode("reverse", name=names.make(side, n["eye"] + "_blinkHeight", "grp", None, sn)
                                    .replace("_grp", "_rev"))
            cmds.connectAttr(height, rev_h + ".inputX")
            for role, share, angle in (("lid_upper", height, 40.0), ("lid_lower", rev_h + ".outputX", -30.0)):
                part = n[role]
                bgrp = controls.group(names.make(side, part + "_blink", "grp", None, sn), lid_space,
                                      mathx.translate_matrix(ep))
                m1 = cmds.createNode("multDoubleLinear", name=names.make(side, part + "_blink", "grp", None, sn)
                                     .replace("_grp", "_mul"))
                cmds.connectAttr(blink, m1 + ".input1")
                cmds.connectAttr(share, m1 + ".input2")
                m2 = cmds.createNode("multDoubleLinear", name=names.make(side, part + "_blinkAngle", "grp", None, sn)
                                     .replace("_grp", "_mul"))
                cmds.connectAttr(m1 + ".output", m2 + ".input1")
                cmds.setAttr(m2 + ".input2", angle * 2.0)          # blink 1, height 0.5: the lids meet
                cmds.connectAttr(m2 + ".output", bgrp + ".rotateX")
                lid_j = limb.joint_chain(side, [part], [mathx.translate_matrix(ep)], head_j, None, r)[0]
                keep(side, part, lid_j)
                reach = mathx.sub(P(role, side), ep)
                _lo, lid = controls.make(side, part, ctx.shape("lid"), ctx.size("lid"), mathx.translate_matrix(ep),
                                         bgrp, "Z", mirror=None, shape_offset=tuple(reach),
                                         lock=("tx", "ty", "tz", "v"))
                cmds.parentConstraint(lid, lid_j, maintainOffset=False)
        _sp, t_off, target = controls.add_spaces("C", n["eyes_target"], target, t_off,
                                                 [("head", root), ("world", ctx.space("world"))], default=0)

    # -- ears -----------------------------------------------------------------
    if o.get("ears"):
        count = int(n.get("ear_joints", 3))
        parts = mod.chain_parts(s, "ear")
        for side in ("L", "R"):
            joints, _m = chain(side, [P("ear%d" % i, side) for i in range(count + 1)], parts, head_j, [0, 0, 1])
            offs, ctrls = limb.fk_controls(side, joints[:-1], parts[:-1], ctx.shape("ear"), ctx.size("ear"), "X",
                                           root)
            if ctrls:
                curl = controls.add_float(ctrls[0], "curl", 0.0)
                for off, c in list(zip([x.split("|")[-1] for x in offs], [x.split("|")[-1] for x in ctrls]))[1:]:
                    off = controls.long(off)
                    drv = controls.group(names.make(side, c.replace("_ctrl", "") + "_curl", "grp", None, sn), off,
                                         limb.world(off))
                    cmds.parent(controls.long(c), drv)
                    cmds.connectAttr(curl, drv + ".rotateZ")
    return out
