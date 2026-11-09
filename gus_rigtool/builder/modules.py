"""
The builder's modules: Root, Spine, Neck, Arm, Leg, Fingers, Chain (chain.py), Back / Front leg (quad.py).

Each module knows its default settings (names, options, orientation, controls), where its guides
go, and how to build itself from the guide positions. Every name is customizable; the defaults
use your naming (humerus, radius, femur, tibia, index_01...).
"""

import math

import maya.cmds as cmds

from gus_rigtool.builder import controls, correctives, limb, mathx, names, ribbons
from gus_rigtool.builder.module_base import (  # noqa: F401  (old imports of these keep working)
    FINGER_ORIENT, LIMB_ORIENT, SPINE_ORIENT, Module, _chain_roles, _mirror_specs)


# ===========================================================================
# Root
# ===========================================================================

class Root(Module):
    TYPE = "root"
    LABEL = "Root"
    DESCRIPTION = ("World and root controls (world has globalScale). Everything else hangs from them. "
                   "Option: a root bind joint for game engines.")
    CONTROLS = {"world": ["root", 0.3], "root": ["circle", 0.24]}
    OPTIONS = {"root_joint": False}
    OPTION_LABELS = {"root_joint": ("Root bind joint (for game engines)", "bool", None)}

    def default_names(self):
        return {"world": "world", "root": "root"}

    def guide_specs(self, settings, height, side):
        return [{"role": "root", "part": settings["names"]["root"], "pos": [0, 0, 0], "size": 2.0}]

    def preview_names(self, s, side):
        n = s["names"]
        return [names.make("C", n["world"], "ctrl"), names.make("C", n["root"], "ctrl")] + \
            ([names.make("C", n["root"], "jnt")] if s["options"]["root_joint"] else [])

    def build(self, ctx):
        n = ctx.settings["names"]
        pos = ctx.pos("root")
        w_off, world = controls.make("C", n["world"], ctx.shape("world"), ctx.size("world"),
                                     mathx.translate_matrix(pos), ctx.controls_grp, "Y", lock=("v",))
        scale = controls.add_float(world, "globalScale", 1.0, 0.001)
        for a in ("sx", "sy", "sz"):
            cmds.connectAttr(scale, world + "." + a)
            cmds.setAttr(world + "." + a, keyable=False, channelBox=False)
        r_off, root = controls.make("C", n["root"], ctx.shape("root"), ctx.size("root"),
                                    mathx.translate_matrix(pos), world, "Y")
        ctx.world_ctrl, ctx.root_ctrl, ctx.scale_plug = world, root, scale
        out = {"joints": {}, "spaces": {"world": world, "root": root}, "follow": root}
        if ctx.settings["options"]["root_joint"]:
            j = limb.joint_chain("C", [n["root"]], [mathx.translate_matrix(pos)], ctx.skeleton, None, ctx.radius)[0]
            cmds.parentConstraint(root, j, maintainOffset=False)
            cmds.scaleConstraint(root, j, maintainOffset=False)
            out["joints"][n["root"]] = j
        return out


# ===========================================================================
# Spine
# ===========================================================================

class Spine(Module):
    TYPE = "spine"
    LABEL = "Spine"
    ATTACH = "root:root"
    CONTROLS = {"cog": ["cog", 0.15], "hips": ["circle", 0.11], "fk": ["circle", 0.1],
                "mid": ["circle", 0.1], "chest": ["circle", 0.12]}
    OPTIONS = {"type": "fk", "joint_count": 4, "stretch": False, "volume": False}
    OPTION_LABELS = {"type": ("Spine type", "choice", ["fk", "ik_spline", "ribbon"]),
                     "joint_count": ("Number of spine joints (names in Names)", "int", None),
                     "stretch": ("Stretch (ik_spline: a 'stretch' switch on the chest; a ribbon always stretches)",
                                 "bool", None),
                     "volume": ("Squash and stretch volume ('volume' slider on the chest: thinner when long, "
                                "fatter when short)", "bool", None)}
    OPTION_GROUPS = [("Spine", ["type", "joint_count"]), ("Squash and stretch", ["stretch", "volume"])]
    OPTION_NEEDS = {"options.stretch": ("options.type", ("ik_spline",)),
                    "options.volume": ("options.type", ("ik_spline", "ribbon"))}
    SIZED = [("chain", "joint_count", "spine_%02d")]
    DESCRIPTION = ("Hips, the spine chain, COG and chest. fk: an FK control per joint. ik_spline / ribbon: hips, "
                   "mid and chest controls bend it (the mid control never moves the hips or the chest).")

    def default_names(self):
        return {"chain": ["spine", "abdomen", "sternum", "shoulder"], "hips": "hips", "cog": "COG",
                "chest": "chest", "mid": "spine_mid"}

    def guide_specs(self, s, h, side):
        chain = s["names"]["chain"]
        specs = [{"role": "hips", "part": s["names"]["hips"], "pos": [0, 0.53 * h, 0.0], "kind": "pivot"}]
        n = len(chain)
        for i, part in enumerate(chain):
            t = i / float(max(1, n - 1))
            specs.append({"role": "c%d" % i, "part": part, "pos": [0, h * (0.555 + 0.225 * t), -0.005 * h],
                          "parent": "c%d" % (i - 1) if i else None})
        return specs

    def preview_names(self, s, side):
        n = s["names"]
        out = [names.make("C", p, "jnt") for p in [n["hips"]] + n["chain"]]
        out += [names.make("C", n["cog"], "ctrl"), names.make("C", n["hips"], "ctrl")]
        if s["options"]["type"] == "fk":
            out += [names.make("C", p, "ctrl", "fk") for p in n["chain"][1:]]
        else:
            out += [names.make("C", n["mid"], "ctrl"), names.make("C", n["chest"], "ctrl")]
        return out

    def build(self, ctx):
        n = ctx.settings["names"]
        chain = n["chain"]
        roles = ["c%d" % i for i in range(len(chain))]
        mats = ctx.chain(roles)
        bind = limb.joint_chain("C", chain, mats, ctx.attach_joint or ctx.skeleton, None, ctx.radius)
        hips_m = list(mats[0])
        hips_m[12:15] = ctx.pos("hips")
        hips = limb.joint_chain("C", [n["hips"]], [hips_m], bind[0], None, ctx.radius)[0]

        cog_off, cog = controls.make("C", n["cog"], ctx.shape("cog"), ctx.size("cog"),
                                     mathx.translate_matrix(mathx.position(mats[0])), ctx.module_ctrls, "Y")
        h_off, hips_ctrl = controls.make("C", n["hips"], ctx.shape("hips"), ctx.size("hips"), hips_m, cog,
                                         ctx.aim_face())
        cmds.parentConstraint(hips_ctrl, hips, maintainOffset=True)
        out = {"joints": dict(zip(chain, bind)), "spaces": {"cog": cog}, "follow": cog}
        out["joints"][n["hips"]] = hips
        kind = ctx.settings["options"]["type"]

        if kind == "fk" or len(bind) < 3:
            cmds.parentConstraint(cog, bind[0], maintainOffset=True)
            offs, ctrls = limb.fk_controls("C", bind[1:], chain[1:], ctx.shape("fk"), ctx.size("fk"),
                                           ctx.aim_face(), cog)
            out["spaces"]["chest"] = ctrls[-1] if ctrls else cog
            return out

        # IK spline or ribbon: three drivers (hips, middle, chest) bend the spine
        mid_m = list(mats[len(mats) // 2])
        mid_m[12:15] = mathx.lerp(mathx.position(mats[0]), mathx.position(mats[-1]), 0.5)
        c_off, chest = controls.make("C", n["chest"], ctx.shape("chest"), ctx.size("chest"), mats[-1], cog,
                                     ctx.aim_face())
        m_off, mid = controls.make("C", n["mid"], ctx.shape("mid"), ctx.size("mid"), mid_m, cog, ctx.aim_face())
        cmds.pointConstraint(hips_ctrl, chest, m_off, maintainOffset=True)
        cmds.orientConstraint(hips_ctrl, chest, m_off, maintainOffset=True)
        drv = ribbons.drivers("C", "spine", [mats[0], mid_m, mats[-1]], ["start", "mid", "end"], ctx.nodes,
                              ctx.radius * 0.5)
        limb.hide(drv)
        for c, d in zip((hips_ctrl, mid, chest), drv):
            cmds.parentConstraint(c, d, maintainOffset=True)
        out["spaces"]["chest"] = chest

        if kind == "ribbon":
            pts = [mathx.position(m) for m in mats]
            srf = ribbons.strip("C", "spine_ribbon", pts, [[1, 0, 0]] * len(pts), ctx.height * 0.06, ctx.nodes)
            ribbons.skin(srf, drv)
            fols = controls.group(names.make("C", "spine_ribbonFol", "grp"), ctx.nodes)
            for j, part, p in zip(bind, chain, pts):
                u, v = ribbons.closest_uv(srf, p)
                fol = ribbons.follicle("C", part, srf, u, v, fols)
                cmds.parentConstraint(fol, j, maintainOffset=True)
            if ctx.settings["options"].get("volume"):
                ratio = _spine_ratio_drivers(drv, ctx)
                _spine_volume(bind, chest, ratio, ctx)
            return out

        # IK spline
        h, eff, crv = cmds.ikHandle(startJoint=bind[0], endEffector=bind[-1], solver="ikSplineSolver",
                                    createCurve=True, simplifyCurve=True, numSpans=2,
                                    name=names.make("C", "spine", "ik"))
        crv = cmds.rename(crv, names.make("C", "spine", "crv"))
        cmds.parent(h, crv, ctx.nodes)
        cmds.setAttr(h + ".visibility", 0)
        cmds.setAttr(crv + ".visibility", 0)
        ribbons.skin_curve(crv, drv, names.make("C", "spine_crv", "grp").replace("_grp", "_skin"))
        aim, up = ctx.orient["aim"], ctx.orient["up"]
        fwd = {"X": 0, "-X": 1, "Y": 2, "-Y": 3, "Z": 4, "-Z": 5}[aim]
        upi = {"Y": 0, "-Y": 1, "Z": 3, "-Z": 4, "X": 6, "-X": 7}[up]
        vec = mathx.AXIS_VECTORS[up.lstrip("-")]
        cmds.setAttr(h + ".dTwistControlEnable", 1)
        cmds.setAttr(h + ".dWorldUpType", 4)
        cmds.setAttr(h + ".dForwardAxis", fwd)
        cmds.setAttr(h + ".dWorldUpAxis", upi)
        cmds.setAttr(h + ".dWorldUpVector", *vec)
        cmds.setAttr(h + ".dWorldUpVectorEnd", *vec)
        cmds.connectAttr(drv[0] + ".worldMatrix[0]", h + ".dWorldUpMatrix")
        cmds.connectAttr(drv[2] + ".worldMatrix[0]", h + ".dWorldUpMatrixEnd")
        o = ctx.settings["options"]
        if o.get("stretch") or o.get("volume"):
            ratio = _spine_ratio_curve(crv, ctx)
            if o.get("stretch"):
                on = controls.add_bool(chest, "stretch", True)
                axis = ctx.orient["aim"].lstrip("-")
                onoff = cmds.createNode("blendTwoAttr", name=names.make("C", "spine_stretchOnOff", "grp")
                                        .replace("_grp", ""))
                cmds.setAttr(onoff + ".input[0]", 1.0)
                cmds.connectAttr(ratio, onoff + ".input[1]")
                cmds.connectAttr(on, onoff + ".attributesBlender")
                for j in bind[1:]:
                    plug = "%s.translate%s" % (j, axis)
                    mul = cmds.createNode("multDoubleLinear", name=names.make(
                        "C", j.split("|")[-1] + "_stretch", "grp").replace("_grp", "_mul"))
                    cmds.setAttr(mul + ".input1", cmds.getAttr(plug))
                    cmds.connectAttr(onoff + ".output", mul + ".input2")
                    cmds.connectAttr(mul + ".output", plug, force=True)
                ratio = onoff + ".output"                 # stretch off: no volume change either
            if o.get("volume"):
                _spine_volume(bind, chest, ratio, ctx)
        return out


def _spine_ratio_drivers(drv, ctx):
    """Ribbon spine: (hips -> mid -> chest driver length) / its rest length (rig scale taken out)."""
    nm = lambda k: names.make("C", "spine_len" + k, "grp").replace("_grp", "")
    total = cmds.createNode("plusMinusAverage", name=nm("Sum"))
    rest = 0.0
    for i, (a, b) in enumerate(zip(drv, drv[1:])):
        d = cmds.createNode("distanceBetween", name=nm("Dist%d" % i))
        for k, node in enumerate((a, b)):
            dm = cmds.createNode("decomposeMatrix", name=nm("Dm%d%d" % (i, k)))
            cmds.connectAttr(node + ".worldMatrix[0]", dm + ".inputMatrix")
            cmds.connectAttr(dm + ".outputTranslate", d + ".point%d" % (k + 1))
        cmds.connectAttr(d + ".distance", "%s.input1D[%d]" % (total, i))
        rest += mathx.distance(limb.world(a)[12:15], limb.world(b)[12:15])
    return _ratio(total + ".output1D", rest, ctx, nm)


def _spine_ratio_curve(crv, ctx):
    """IK spline spine: curve length / its rest length (rig scale taken out)."""
    nm = lambda k: names.make("C", "spine_len" + k, "grp").replace("_grp", "")
    shape = cmds.listRelatives(crv, shapes=True, fullPath=True)[0]
    info = cmds.createNode("curveInfo", name=nm("Info"))
    cmds.connectAttr(shape + ".worldSpace[0]", info + ".inputCurve")
    rest = cmds.getAttr(info + ".arcLength") or 1.0
    return _ratio(info + ".arcLength", rest, ctx, nm)


def _ratio(length_plug, rest, ctx, nm):
    restm = cmds.createNode("multDoubleLinear", name=nm("Rest"))
    cmds.setAttr(restm + ".input1", max(rest, 1e-6))
    if ctx.scale_plug:
        cmds.connectAttr(ctx.scale_plug, restm + ".input2")
    else:
        cmds.setAttr(restm + ".input2", 1.0)
    div = cmds.createNode("multiplyDivide", name=nm("Ratio"))
    cmds.setAttr(div + ".operation", 2)
    cmds.connectAttr(length_plug, div + ".input1X")
    cmds.connectAttr(restm + ".output", div + ".input2X")
    return div + ".outputX"


def _spine_volume(bind, chest, ratio, ctx):
    """Thinner when the spine is longer, fatter when shorter: side scale = ratio ^ -0.5, most in the middle
    joints, by 'volume' on the chest control."""
    nm = lambda k: names.make("C", "spine_volume" + k, "grp").replace("_grp", "")
    vol = controls.add_float(chest, "volume", 1.0, 0.0, 2.0)
    power = cmds.createNode("multiplyDivide", name=nm("Pow"))
    cmds.setAttr(power + ".operation", 3)
    cmds.connectAttr(ratio, power + ".input1X")
    cmds.setAttr(power + ".input2X", -0.5)
    aim = ctx.orient["aim"].lstrip("-")
    sides = [a for a in "XYZ" if a != aim]
    count = len(bind)
    for i, j in enumerate(bind):
        t = i / float(max(1, count - 1))
        w = math.sin(math.pi * t) if count > 2 else 1.0
        if w < 1e-3:
            continue
        amount = cmds.createNode("multDoubleLinear", name=nm("Amount%d" % i))
        cmds.connectAttr(vol, amount + ".input1")
        cmds.setAttr(amount + ".input2", w)
        bl = cmds.createNode("blendTwoAttr", name=nm("%d" % i))
        cmds.setAttr(bl + ".input[0]", 1.0)
        cmds.connectAttr(power + ".outputX", bl + ".input[1]")
        cmds.connectAttr(amount + ".output", bl + ".attributesBlender")
        for a in sides:
            cmds.connectAttr(bl + ".output", "%s.scale%s" % (j, a), force=True)


# ===========================================================================
# Neck / Head
# ===========================================================================

class Neck(Module):
    TYPE = "neck"
    LABEL = "Neck / Head"
    ATTACH = "spine:shoulder"
    CONTROLS = {"fk": ["circle", 0.06], "head": ["circle", 0.08]}
    OPTIONS = {"head_spaces": True, "head_axes": "neck", "head_end": False, "joint_count": 1, "extra_spaces": "",
               "default_space": "neck"}
    SIZED = [("chain", "joint_count", "neck_%02d")]
    OPTION_LABELS = {
        "head_spaces": ("Head follows: neck / chest / world (space switch)", "bool", None),
        "head_axes": ("Head joint axes (neck = like the neck joints)", "choice", ["neck", "world", "aim at head end"]),
        "head_end": ("Head end joint", "bool", None),
        "joint_count": ("Number of neck joints (names in Names)", "int", None),
        "extra_spaces": ("Extra head spaces (label = node, ...)", "spaces", None),
        "default_space": ("Default head space", "text", None),
    }
    OPTION_GROUPS = [("Neck and head", ["joint_count", "head_spaces", "extra_spaces", "default_space", "head_axes",
                                        "head_end"])]
    DESCRIPTION = "Neck joints with FK controls and the head control (spaces: neck / chest / world)."

    def default_names(self):
        return {"chain": ["neck"], "head": "head", "head_end": "head_end"}

    def _uses_end(self, s):
        o = s["options"]
        return bool(o.get("head_end")) or o.get("head_axes") == "aim at head end"

    def guide_specs(self, s, h, side):
        chain = s["names"]["chain"]
        specs = []
        n = len(chain)
        for i, part in enumerate(chain):
            t = i / float(n)
            specs.append({"role": "c%d" % i, "part": part, "pos": [0, h * (0.82 + 0.07 * t), -0.006 * h],
                          "parent": "c%d" % (i - 1) if i else None})
        specs.append({"role": "head", "part": s["names"]["head"], "pos": [0, h * 0.89, 0.0],
                      "parent": "c%d" % (n - 1)})
        if self._uses_end(s):
            specs.append({"role": "head_end", "part": s["names"]["head_end"], "pos": [0, h * 0.99, 0.0],
                          "parent": "head", "size": 0.7})
        return specs

    def preview_names(self, s, side):
        n = s["names"]
        parts = n["chain"] + [n["head"]] + ([n["head_end"]] if s["options"].get("head_end") else [])
        return [names.make("C", p, "jnt") for p in parts] + \
            [names.make("C", p, "ctrl", "fk") for p in n["chain"]] + [names.make("C", n["head"], "ctrl")]

    def build(self, ctx):
        n, o = ctx.settings["names"], ctx.settings["options"]
        nc = len(n["chain"])
        uses_end = self._uses_end(ctx.settings)
        roles = ["c%d" % i for i in range(nc)] + ["head"] + (["head_end"] if uses_end else [])
        mats = ctx.chain(roles)
        head_m = list(mats[nc])
        if o.get("head_axes", "neck") == "world":
            head_m = mathx.translate_matrix(ctx.pos("head"))       # the world's axes: no twist
        elif o.get("head_axes") == "neck":
            head_m = list(mats[nc - 1]) if nc else head_m
            head_m[12:15] = ctx.pos("head")
        mats[nc] = head_m
        parts = n["chain"] + [n["head"]]
        if o.get("head_end"):
            end_m = list(head_m)
            end_m[12:15] = ctx.pos("head_end")
            parts.append(n["head_end"])
            mats = mats[:nc + 1] + [end_m]
        else:
            mats = mats[:nc + 1]
        bind = limb.joint_chain("C", parts, mats, ctx.attach_joint or ctx.skeleton, None, ctx.radius)
        offs, ctrls = limb.fk_controls("C", bind[:nc], n["chain"], ctx.shape("fk"), ctx.size("fk"),
                                       ctx.aim_face(), ctx.module_ctrls)
        under = ctrls[-1] if ctrls else ctx.module_ctrls
        head_face = "Y" if o.get("head_axes", "neck") == "world" else ctx.aim_face()
        h_off, head = controls.make("C", n["head"], ctx.shape("head"), ctx.size("head"), head_m, under, head_face)
        cmds.parentConstraint(head, bind[nc], maintainOffset=False)
        if o.get("head_spaces", True):
            targets = ctx.space_targets([("neck", under), ("chest", ctx.space("chest")),
                                         ("world", ctx.space("world"))])
            _sp, h_off, head = controls.add_spaces("C", n["head"], head, h_off, targets, kind="orient",
                                                   default=ctx.space_default(targets, "neck"))
        return {"joints": dict(zip(parts, bind)), "spaces": {"neck": under, "head": head}, "follow": head}


# ===========================================================================
# Arm and Leg (shared limb code)
# ===========================================================================

class _Limb(Module):
    SIDES = ("L", "R")
    ORIENT = LIMB_ORIENT
    OPTIONS = {"stretch": False, "bendy": False, "twist_count": 4, "spaces": True, "ik_orient": "world",
               "extra_spaces": "", "default_space": "root", "soft_ik": False, "pin": False,
               "bone_length": False, "ik_mirror": True, "no_flip": False, "correctives": False}
    OPTION_LABELS = {
        "correctives": correctives.OPTION,
        "stretch": ("IK stretch (a 'stretch' switch on the settings control)", "bool", None),
        "soft_ik": ("Soft IK (a 'soft_ik' slider on the settings control: no pop when straight)", "bool", None),
        "pin": ("Elbow / knee pin (a 'pin' slider: the elbow / knee goes onto the pole vector)", "bool", None),
        "bone_length": ("Length per bone ('upper_length' / 'lower_length' sliders, IK)", "bool", None),
        "no_flip": ("No-flip knee / elbow ('knee_mode' slider: 0 pole vector, 1 follows the foot / hand; "
                    "'knee_twist' turns it)", "bool", None),
        "bendy": ("Bendy (ribbon with twist joints and bend controls)", "bool", None),
        "twist_count": ("Twist joints per segment (bendy)", "int", None),
        "spaces": ("Space switch on the IK control and pole vector", "bool", None),
        "ik_orient": ("IK control axes", "choice", ["world", "joint"]),
        "ik_mirror": ("Right IK / pole vector move as the mirror of the left (move both: they mirror)", "bool", None),
        "extra_spaces": ("Extra spaces (label = node, ...)", "spaces", None),
        "default_space": ("Default space of the IK control", "text", None),
    }
    OPTION_GROUPS = [("IK / FK", ["ik_orient", "ik_mirror", "spaces", "extra_spaces", "default_space", "stretch", "soft_ik",
                                  "pin", "bone_length", "no_flip"]),
                     ("Bendy", ["bendy", "twist_count"]), ("Volume", ["correctives"])]
    OPTION_NEEDS = {"options.twist_count": ("options.bendy", True), "options.extra_spaces": ("options.spaces", True),
                    "options.default_space": ("options.spaces", True)}
    DESCRIPTION = ("FK and IK chains blended into the bind chain (ikfk on the settings control), pole vector, "
                   "spaces, optional stretch and bendy twist joints. Legs: a reverse foot (heel / ball / toe "
                   "roll, bank, twists).")
    ROLES = []            # bind chain roles, top to bottom
    IK_START, IK_END = 0, 2

    def default_names(self):
        return dict(zip(self.ROLES, self.ROLES))


class Arm(_Limb):
    TYPE = "arm"
    LABEL = "Arm"
    ATTACH = "spine:shoulder"
    ROLES = ["clavicle", "humerus", "radius", "wrist", "hand"]
    IK_START, IK_END = 1, 3
    CONTROLS = {"clavicle": ["square_pin", 0.03], "fk": ["circle", 0.04], "ik": ["cube", 0.03],
                "pv": ["diamond_3d", 0.015], "settings": ["gear", 0.018], "bend": ["diamond", 0.025]}
    OPTIONS = dict(_Limb.OPTIONS, wrist_axes="forearm", clavicle_points="front")
    OPTION_LABELS = dict(_Limb.OPTION_LABELS, **{
        "wrist_axes": ("Wrist axes", "choice", ["forearm", "aim at hand"]),
        "clavicle_points": ("Clavicle shape points", "choice", ["front", "along the arm", "up"]),
    })
    OPTION_GROUPS = [("Arm", ["wrist_axes", "clavicle_points"])] + _Limb.OPTION_GROUPS

    def guide_specs(self, s, h, side):
        n = s["names"]
        pos = {"clavicle": [0.017, 0.79, 0.011], "humerus": [0.094, 0.778, -0.011], "radius": [0.25, 0.778, -0.028],
               "wrist": [0.389, 0.778, 0.0], "hand": [0.433, 0.778, 0.0]}
        specs, prev = [], None
        for r in self.ROLES:
            specs.append({"role": r, "part": n[r], "pos": [v * h for v in pos[r]], "parent": prev})
            prev = r
        return _mirror_specs(specs, side)

    def preview_names(self, s, side):
        n = s["names"]
        out = [names.make(side, n[r], "jnt") for r in self.ROLES]
        out += [names.make(side, n["clavicle"], "ctrl", "fk")]
        out += [names.make(side, n[r], "ctrl", "fk") for r in ("humerus", "radius", "wrist")]
        out += [names.make(side, n["wrist"], "ctrl", "ik"), names.make(side, n["radius"], "ctrl", "pv"),
                names.make(side, n["wrist"], "ctrl", "settings")]
        if s["options"]["bendy"]:
            out += [names.make(side, "%s_twist_%02d" % (n[r], i + 1), "jnt")
                    for r in ("humerus", "radius") for i in range(int(s["options"]["twist_count"]))]
        if s["options"].get("correctives"):
            out += [names.make(side, n[r] + "_cor", "jnt") for r in ("humerus", "radius", "wrist")]
        return out

    def build(self, ctx):
        return build_limb(ctx, self, kind="arm")


class Leg(_Limb):
    TYPE = "leg"
    LABEL = "Leg"
    ATTACH = "spine:hips"
    ROLES = ["femur", "tibia", "ankle", "ball", "ball_end"]
    PIVOTS = ["heel", "foot_inner", "foot_outer"]
    IK_START, IK_END = 0, 2
    CONTROLS = {"fk": ["circle", 0.05], "ik": ["foot", 0.06], "pv": ["diamond_3d", 0.015],
                "settings": ["gear", 0.018], "bend": ["diamond", 0.025]}

    def default_names(self):
        d = dict(zip(self.ROLES, self.ROLES))
        d.update({"heel": "heel", "foot_inner": "foot_inner", "foot_outer": "foot_outer"})
        return d

    def guide_specs(self, s, h, side):
        n = s["names"]
        pos = {"femur": [0.056, 0.528, 0.0], "tibia": [0.056, 0.289, 0.011], "ankle": [0.056, 0.05, -0.011],
               "ball": [0.056, 0.011, 0.056], "ball_end": [0.056, 0.0, 0.094], "heel": [0.056, 0.0, -0.033],
               "foot_inner": [0.028, 0.0, 0.045], "foot_outer": [0.083, 0.0, 0.045]}
        specs, prev = [], None
        for r in self.ROLES:
            specs.append({"role": r, "part": n[r], "pos": [v * h for v in pos[r]], "parent": prev})
            prev = r
        for r in self.PIVOTS:
            specs.append({"role": r, "part": n[r], "pos": [v * h for v in pos[r]], "parent": "ankle",
                          "kind": "pivot"})
        return _mirror_specs(specs, side)

    def preview_names(self, s, side):
        n = s["names"]
        out = [names.make(side, n[r], "jnt") for r in self.ROLES]
        out += [names.make(side, n[r], "ctrl", "fk") for r in ("femur", "tibia", "ankle", "ball")]
        out += [names.make(side, n["ankle"], "ctrl", "ik"), names.make(side, n["tibia"], "ctrl", "pv"),
                names.make(side, n["ankle"], "ctrl", "settings")]
        if s["options"]["bendy"]:
            out += [names.make(side, "%s_twist_%02d" % (n[r], i + 1), "jnt")
                    for r in ("femur", "tibia") for i in range(int(s["options"]["twist_count"]))]
        if s["options"].get("correctives"):
            out += [names.make(side, n[r] + "_cor", "jnt") for r in ("femur", "tibia", "ankle")]
        return out

    def build(self, ctx):
        return build_limb(ctx, self, kind="leg")


def build_limb(ctx, mod, kind):
    side, n, opt = ctx.side, ctx.settings["names"], ctx.settings["options"]
    roles = mod.ROLES
    parts = [n[r] for r in roles]
    ik_roles = roles[mod.IK_START:mod.IK_END + 1]
    mats = ctx.chain(roles, plane_roles=ik_roles)
    first = 1 if kind == "arm" else 0                       # the arm's clavicle is FK only
    if kind == "arm" and opt.get("wrist_axes", "forearm") == "forearm":
        # the wrist (and hand) keep the forearm's axes: no twist, the FK wrist turns like the elbow
        for i in (3, 4):
            m = list(mats[2])
            m[12:15] = mathx.position(mats[i])
            mats[i] = m

    bind = limb.joint_chain(side, parts, mats, ctx.attach_joint or ctx.skeleton, None, ctx.radius)
    # FK and IK chains (no clavicle) follow the joint above them
    root_grp = controls.group(names.make(side, n[roles[first]] + "_limb", "grp"), ctx.nodes)
    follow = bind[0] if kind == "arm" else ctx.attach_joint     # arm: the clavicle; leg: the hips
    if follow:
        cmds.parentConstraint(follow, root_grp, maintainOffset=True)
        cmds.scaleConstraint(follow, root_grp, maintainOffset=True)
    fkj = limb.joint_chain(side, parts[first:], mats[first:], root_grp, "fk", ctx.radius * 0.7)
    ikj = limb.joint_chain(side, parts[first:], mats[first:], root_grp, "ik", ctx.radius * 0.7)
    limb.hide([fkj[0], ikj[0]])

    face = ctx.aim_face()
    under = ctx.module_ctrls
    if kind == "arm":
        # pivot on the clavicle, the shape out at the shoulder (humerus), pointing along the arm
        reach = mathx.distance(mathx.position(mats[0]), mathx.position(mats[1]))
        sign = -1.0 if ctx.orient["aim"].startswith("-") else 1.0      # the humerus is down the aim axis
        along = tuple((sign * reach if a == face else 0.0) for a in "XYZ")
        flip = tuple((sign if a == face else 1.0) for a in "XYZ")
        points = opt.get("clavicle_points", "front")
        if points == "along the arm":
            c_off, clav = controls.make(side, n["clavicle"], ctx.shape("clavicle"), ctx.size("clavicle"),
                                        mats[0], under, face, "fk", shape_offset=along, shape_flip=flip)
        else:
            # the pin points to the character's front (+Z) or up, whatever the joint's axes are
            world_dir = [0.0, 0.0, 1.0] if points == "front" else [0.0, 1.0, 0.0]
            local = [mathx.dot(world_dir, mathx.norm(mats[0][r * 4:r * 4 + 3])) for r in range(3)]
            shape = ctx.shape("clavicle")
            name, turn = (shape[0], shape[1]) if isinstance(shape, (list, tuple)) else (shape, None)
            if turn and [round(float(x)) for x in turn] == [90, 0, 0]:
                turn = None                                 # the old default turn (along the arm only)
            c_off, clav = controls.make(side, n["clavicle"], (name, turn) if turn else name,
                                        ctx.size("clavicle"), mats[0], under, "Y", "fk", mirror=None,
                                        shape_dir=local)
        cmds.parentConstraint(clav, bind[0], maintainOffset=False)
        under = clav
    fk_count = 3 if kind == "arm" else 4
    fk_offs, fk_ctrls = limb.fk_controls(side, fkj[:fk_count], parts[first:first + fk_count], ctx.shape("fk"),
                                         ctx.size("fk"), face, under)

    # settings control, next to the wrist / ankle
    end_i = mod.IK_END
    end_m = mats[end_i]
    up_dir = mathx.axis_of(end_m, ctx.orient["up"])
    if side == "R" and ctx.orient.get("behavior_right", True):
        up_dir = mathx.scale(up_dir, -1.0)                # behavior axes are turned round: mirror the spot
    s_pos = mathx.add(mathx.position(end_m), mathx.scale(up_dir, ctx.height * 0.06))
    s_off, settings = controls.make(side, n[roles[end_i]], ctx.shape("settings"), ctx.size("settings"),
                                    mathx.translate_matrix(s_pos), ctx.module_ctrls, "Z", "settings",
                                    lock=("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"))
    cmds.parentConstraint(bind[end_i], s_off, maintainOffset=True)
    controls.separator(settings, "IK FK")
    blend = controls.add_float(settings, "ikfk", 0.0, 0.0, 1.0)

    # IK
    ik_grp = controls.group(names.make(side, n[roles[end_i]] + "_ik", "grp"), ctx.ik_parent())
    if opt["ik_orient"] == "joint":
        ik_m = list(end_m)
    else:
        ik_m = mathx.translate_matrix(mathx.position(end_m))
    mirrored = limb.mirrors(side, opt)
    ik_off, ik_ctrl = controls.make(side, n[roles[end_i]], ctx.shape("ik"), ctx.size("ik"), ik_m, ik_grp,
                                    "Y" if kind == "leg" else face, "ik", mirror=None if mirrored else "auto")
    hold = limb.mirror_control(side, n[roles[end_i]] + "_ik", ik_off, ik_ctrl) if mirrored else ik_ctrl
    ik_i = end_i - first
    handle = limb.ik_handle(side, n[roles[end_i]], ikj[mod.IK_START - first], ikj[ik_i])
    pv_pos = mathx.pole_position(*[mathx.position(mats[i]) for i in range(mod.IK_START, mod.IK_END + 1)])
    pv_off, pv = controls.make(side, n[roles[mod.IK_START + 1]], ctx.shape("pv"), ctx.size("pv"),
                               mathx.translate_matrix(pv_pos), ik_grp, "Y", "pv",
                               lock=("rx", "ry", "rz", "sx", "sy", "sz", "v"), mirror=None if mirrored else "auto")
    if mirrored:
        cmds.setAttr(pv_off + ".scaleX", -1)
    cmds.poleVectorConstraint(pv, handle)
    foot_attrs = []
    if kind == "arm":
        cmds.parent(handle, hold)
        cmds.orientConstraint(hold, ikj[ik_i], maintainOffset=True)
        end_target = hold
    else:
        end_target, foot_attrs = _reverse_foot(ctx, n, mats, ik_ctrl, ikj, handle, hold)
    if opt.get("no_flip"):
        limb.no_flip(side, n[roles[mod.IK_START + 1]], handle, hold, mathx.position(mats[mod.IK_START]), pv_pos,
                     settings)

    on = start = None
    if opt["stretch"] or opt.get("soft_ik") or opt.get("pin") or opt.get("bone_length"):
        # measure from a point at the shoulder / hip that follows the limb's root but is not turned by
        # the IK (measuring from the IK joint itself makes a loop: the IK reads what the stretch writes)
        start = controls.group(names.make(side, n[roles[mod.IK_START]] + "_stretchStart", "grp"), root_grp,
                               mathx.translate_matrix(mathx.position(mats[mod.IK_START])))
    lengths = pin = None
    if opt.get("bone_length"):
        lengths = [controls.add_float(settings, "upper_length", 1.0, 0.1, 10.0),
                   controls.add_float(settings, "lower_length", 1.0, 0.1, 10.0)]
    if opt.get("pin"):
        pin = controls.add_float(settings, "pin", 0.0, 0.0, 1.0)
    if opt["stretch"]:
        on = controls.add_bool(settings, "stretch", False)
    if opt["stretch"] or lengths or pin:
        limb.stretch(side, n[roles[end_i]], ikj[mod.IK_START - first:ik_i + 1], start,
                     end_target, on, ctx.scale_plug, ctx.orient["aim"], lengths, pin, pv)
    if opt.get("soft_ik"):
        soft = controls.add_float(settings, "soft_ik", 0.0, 0.0, 1.0)
        length = sum(mathx.distance(mathx.position(mats[i]), mathx.position(mats[i + 1]))
                     for i in range(mod.IK_START, mod.IK_END))
        limb.soft_ik(side, n[roles[end_i]], start, handle, length, soft, ctx.scale_plug, on)

    limb.blend(side, bind[first:], fkj, ikj, blend)
    limb.visibility_switch(side, n[roles[end_i]], blend, [fk_offs[0]], [ik_off, pv_off])

    if opt["spaces"]:
        targets = ctx.space_targets([(label, ctx.space(label)) for label in
                                     (["world", "root", "cog", "chest"] if kind == "arm" else ["world", "root", "cog"])])
        _sp, ik_off, ik_ctrl = controls.add_spaces(side, n[roles[end_i]] + "_ik", ik_ctrl, ik_off, targets,
                                                   default=ctx.space_default(targets, "root"))
        hold = controls.long(hold.split("|")[-1]) if mirrored else ik_ctrl
        pv_targets = ctx.space_targets([("limb", hold), ("world", ctx.space("world")),
                                        ("root", ctx.space("root"))], extra=False)
        _sp, pv_off, pv = controls.add_spaces(side, n[roles[mod.IK_START + 1]] + "_pv", pv, pv_off, pv_targets,
                                              default=0)

    short = lambda nodes: [x.split("|")[-1] for x in nodes]       # names: paths change when re-parented
    limb.store_meta(settings, gusFkCtrls=short(fk_ctrls), gusFkJoints=short(fkj), gusIkJoints=short(ikj),
                    gusIkCtrl=ik_ctrl.split("|")[-1], gusPvCtrl=pv.split("|")[-1], gusBlend="ikfk",
                    gusFootAttrs=foot_attrs, gusEnd=str(ik_i))

    out = {"joints": dict(zip(parts, bind)), "spaces": {}, "follow": bind[-1], "settings_ctrl": settings}
    if opt["bendy"]:
        a = mod.IK_START
        parts_ = [n[roles[a]], n[roles[a + 1]]]
        corner = "knee" if kind == "leg" else "elbow"
        corner = corner + "Corner" if corner in parts_ else corner
        twists, bends = ribbons.bendy_limb(side, parts_, (bind[a], bind[a + 1], bind[mod.IK_END]),
                                           opt["twist_count"], ctx, ctx.orient["up"].lstrip("-"), corner)
        for t in twists:
            out["joints"][t.split("|")[-1]] = t
        limb.store_meta(settings, gusTweaks=short(bends))
    if opt.get("correctives"):
        # arm: shoulder (clavicle -> humerus), elbow, wrist; leg: hip (hips -> femur), knee, ankle
        upper = [bind[0]] if kind == "arm" else [ctx.attach_joint]
        chain_ = upper + list(bind[first:first + 3])
        bending = roles[first:first + 3]
        correctives.make(ctx, [(n[r], chain_[i], chain_[i + 1]) for i, r in enumerate(bending)], out)
    return out


def _reverse_foot(ctx, n, mats, foot, ikj, leg_handle, under=None):
    """Heel / toe / bank / ball pivots under the IK foot control. Returns (ankle target, attrs)."""
    side = ctx.side
    p = {r: ctx.pos(r) for r in ("ankle", "ball", "ball_end", "heel", "foot_inner", "foot_outer")}
    # foot shape on the ground, under the foot
    ank = p["ankle"]
    cmds.move(0, -ank[1], (p["ball"][2] - ank[2]) * 0.4, foot + ".cv[*]", relative=True, objectSpace=True) \
        if cmds.listRelatives(foot, shapes=True) else None

    def piv(name, pos, parent):
        g = controls.group(names.make(side, n["ankle"] + "_" + name, "grp"), parent)
        cmds.xform(g, worldSpace=True, rotatePivot=pos, scalePivot=pos)
        return g

    heel = piv("heelPivot", p["heel"], under or foot)
    toe = piv("toePivot", p["ball_end"], heel)
    outer = piv("outerPivot", p["foot_outer"], toe)
    inner = piv("innerPivot", p["foot_inner"], outer)
    ball = piv("ballRoll", p["ball"], inner)
    tap = piv("toeTap", p["ball"], inner)
    cmds.parent(leg_handle, ball)
    limb.ik_handle(side, n["ball"], ikj[2], ikj[3], "ikSCsolver", inner)
    limb.ik_handle(side, n["ball_end"], ikj[3], ikj[4], "ikSCsolver", tap)
    target = controls.group(names.make(side, n["ankle"] + "_ikTarget", "grp"), ball, mathx.translate_matrix(ank))

    controls.separator(foot, "foot")
    attrs = ["heel_roll", "ball_roll", "toe_roll", "toe_tap", "bank", "heel_twist", "toe_twist"]
    plugs = {a: controls.add_float(foot, a, 0.0) for a in attrs}

    def drive(plug, target_plug, factor=1.0):
        if factor == 1.0:
            cmds.connectAttr(plug, target_plug)
        else:
            m = cmds.createNode("multDoubleLinear", name=(target_plug.split("|")[-1].replace(".", "_") + "_mul"))
            cmds.setAttr(m + ".input2", factor)
            cmds.connectAttr(plug, m + ".input1")
            cmds.connectAttr(m + ".output", target_plug)

    drive(plugs["heel_roll"], heel + ".rotateX", -1.0)        # + lifts the toes
    drive(plugs["ball_roll"], ball + ".rotateX")              # + lifts the heel
    drive(plugs["toe_roll"], toe + ".rotateX")                # + up on the toe tip
    drive(plugs["toe_tap"], tap + ".rotateX", -1.0)           # + lifts the toes
    drive(plugs["heel_twist"], heel + ".rotateY")
    drive(plugs["toe_twist"], toe + ".rotateY")
    # bank: + rolls onto the outer edge, - onto the inner edge (both sides)
    sign = -1.0 if side == "L" else 1.0
    cond = cmds.createNode("condition", name=names.make(side, n["ankle"] + "_bank", "grp").replace("_grp", "_cond"))
    cmds.setAttr(cond + ".operation", 2)                      # bank > 0
    cmds.connectAttr(plugs["bank"], cond + ".firstTerm")
    cmds.connectAttr(plugs["bank"], cond + ".colorIfTrueR")
    cmds.setAttr(cond + ".colorIfFalseR", 0)
    cmds.setAttr(cond + ".colorIfTrueG", 0)
    cmds.connectAttr(plugs["bank"], cond + ".colorIfFalseG")
    drive(cond + ".outColorR", outer + ".rotateZ", sign)
    drive(cond + ".outColorG", inner + ".rotateZ", sign)
    return target, attrs


# ===========================================================================
# Fingers
# ===========================================================================

class Fingers(Module):
    TYPE = "fingers"
    LABEL = "Fingers"
    SIDES = ("L", "R")
    ATTACH = "arm:hand"
    ORIENT = FINGER_ORIENT
    CONTROLS = {"fk": ["circle", 0.012]}
    OPTIONS = {"metacarpal": False, "end_joints": True, "curl_attrs": False, "finger_count": 5, "thumb_joints": 3}
    SIZED = [("fingers", "finger_count", "finger%d")]
    OPTION_LABELS = {
        "metacarpal": ("Metacarpal joints (e.g. index_meta)", "bool", None),
        "end_joints": ("End joints at the finger tips", "bool", None),
        "curl_attrs": ("Curl / spread attributes on the arm's (or leg's) settings control", "bool", None),
        "finger_count": ("Number of fingers (names in Names)", "int", None),
        "thumb_joints": ("Joints in the thumb", "int", None),
    }
    OPTION_GROUPS = [("Fingers", ["finger_count", "thumb_joints", "metacarpal", "end_joints", "curl_attrs"])]
    DESCRIPTION = "An FK chain per finger (names in Names), hanging from the hand; optional curl / spread."

    def default_names(self):
        return {"fingers": ["thumb", "index", "middle", "ring", "pinky"], "joints": 3,
                "joint_pattern": "{finger}_{num:02d}", "meta_pattern": "{finger}_meta",
                "end_pattern": "{finger}_end"}

    def finger_parts(self, s, finger):
        n = s["names"]
        count = int(s["options"].get("thumb_joints", 3) if finger == "thumb" else n.get("joints", 3))
        parts = [n["joint_pattern"].format(finger=finger, num=i + 1) for i in range(count)]
        if s["options"]["metacarpal"] and finger != "thumb":
            parts = [n["meta_pattern"].format(finger=finger)] + parts
        return parts

    def guide_specs(self, s, h, side):
        n = s["names"]
        specs = []
        fingers = n["fingers"]
        base_x = 0.445
        for fi, finger in enumerate(fingers):
            parts = self.finger_parts(s, finger)
            thumb = finger == "thumb"
            z = 0.02 if thumb else 0.012 - 0.008 * (fi - (1 if "thumb" in fingers else 0))
            x0 = 0.405 if thumb else base_x
            step = 0.016 if thumb else 0.018 - 0.002 * max(0, fi - 2)
            prev = None
            for i, part in enumerate(parts + [n["end_pattern"].format(finger=finger)]):
                role = "%s%d" % (finger, i)
                pos = [x0 + step * i, 0.775 - (0.006 * i if thumb else 0.0), z + (0.008 * i if thumb else 0.0)]
                specs.append({"role": role, "part": part, "pos": [v * h for v in pos], "parent": prev,
                              "size": 0.5})
                prev = role
        return _mirror_specs(specs, side)

    def preview_names(self, s, side):
        out = []
        for finger in s["names"]["fingers"]:
            parts = self.finger_parts(s, finger)
            out += [names.make(side, p, "jnt") for p in parts] + [names.make(side, p, "ctrl", "fk") for p in parts]
            if s["options"]["end_joints"]:
                out.append(names.make(side, s["names"]["end_pattern"].format(finger=finger), "jnt"))
        return out

    def build(self, ctx):
        s, side = ctx.settings, ctx.side
        out = {"joints": {}, "spaces": {}, "follow": None}
        settings_ctrl = ctx.attach_output.get("settings_ctrl") if ctx.attach_output else None
        curl = s["options"]["curl_attrs"] and settings_ctrl and cmds.objExists(settings_ctrl)
        if curl:
            controls.separator(settings_ctrl, "fingers")
            spread = controls.add_float(settings_ctrl, "spread", 0.0)
        bend_axis = "XYZ".replace(ctx.orient["aim"].lstrip("-"), "").replace(ctx.orient["up"].lstrip("-"), "")
        for finger in s["names"]["fingers"]:
            parts = self.finger_parts(s, finger)
            roles = ["%s%d" % (finger, i) for i in range(len(parts) + 1)]
            mats = ctx.chain(roles)
            all_parts = parts + ([s["names"]["end_pattern"].format(finger=finger)] if s["options"]["end_joints"] else [])
            bind = limb.joint_chain(side, all_parts, mats[:len(all_parts)], ctx.attach_joint or ctx.skeleton, None,
                                    ctx.radius * 0.4)
            offs, ctrls = limb.fk_controls(side, bind[:len(parts)], parts, ctx.shape("fk"), ctx.size("fk"),
                                           ctx.aim_face(), ctx.module_ctrls)
            if curl:
                plug = controls.add_float(settings_ctrl, finger + "_curl", 0.0)
                has_meta = bool(s["options"]["metacarpal"]) and finger != "thumb"
                others = [f for f in s["names"]["fingers"] if f != "thumb"]
                off_names = [x.split("|")[-1] for x in offs]           # paths change as we go
                ctrl_names = [x.split("|")[-1] for x in ctrls]
                for i, (off, ctrl) in enumerate(zip(off_names, ctrl_names)):
                    # a driven group between the offset group and the control
                    off = controls.long(off)
                    drv = controls.group(names.make(side, parts[i], "grp", "drv"), off,
                                         limb.world(off))
                    cmds.parent(controls.long(ctrl), drv)
                    if not (has_meta and i == 0):                        # every joint curls (not the palm)
                        cmds.connectAttr(plug, drv + ".rotate" + bend_axis, force=True)
                    if i == 0 and finger != "thumb" and len(others) > 1:
                        # spread: centred on the fingers there are (thumb or not), outer ones open most
                        k = others.index(finger)
                        w = (k - (len(others) - 1) / 2.0) / max(1.0, (len(others) - 1) / 2.0)
                        if abs(w) > 1e-6:
                            m = cmds.createNode("multDoubleLinear", name=names.make(
                                side, finger + "_spread", "grp").replace("_grp", "_mul"))
                            cmds.setAttr(m + ".input2", w * 0.5)
                            cmds.connectAttr(spread, m + ".input1")
                            cmds.connectAttr(m + ".output", drv + ".rotate" + ctx.orient["up"].lstrip("-"))
            for p, j in zip(all_parts, bind):
                out["joints"][p] = j
        return out


from gus_rigtool.builder.chain import Chain  # noqa: E402
from gus_rigtool.builder.quad import BackLeg, FrontLeg  # noqa: E402
from gus_rigtool.builder.face import Face  # noqa: E402

MODULES = {m.TYPE: m() for m in (Root, Spine, Neck, Face, Arm, Leg, Fingers, Chain, BackLeg, FrontLeg)}
ORDER = ["root", "spine", "neck", "face", "leg", "arm", "fingers", "back_leg", "front_leg", "chain"]
