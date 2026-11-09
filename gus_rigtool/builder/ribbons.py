"""
Ribbon pieces for the builder: a NURBS strip through points, follicles that ride on it, and the
driver joints that bend it. Used by the ribbon spine and the bendy limbs.
"""

import maya.cmds as cmds

from gus_rigtool.builder import controls, limb, mathx, names


def strip(side, part, points, side_vectors, width, parent):
    """A ribbon through points, width wide along side_vectors (one per point). U runs along."""
    s = names.settings()
    half = width * 0.5
    a = [mathx.add(p, mathx.scale(mathx.norm(v), half)) for p, v in zip(points, side_vectors)]
    b = [mathx.add(p, mathx.scale(mathx.norm(v), -half)) for p, v in zip(points, side_vectors)]
    # smooth (cubic) curves through the points, lofted straight across: follicles find their spot
    # with closest point, so it doesn't matter which way U and V run
    deg = 3 if len(points) >= 3 else 1
    c1 = cmds.curve(degree=deg, editPoint=[tuple(p) for p in a])
    c2 = cmds.curve(degree=deg, editPoint=[tuple(p) for p in b])
    srf = cmds.loft(c1, c2, degree=1, uniform=True, constructionHistory=False,
                    name=names.make(side, part, "srf", None, s))[0]
    cmds.delete(c1, c2)
    srf = cmds.parent(srf, parent)[0] if parent else srf
    srf = cmds.ls(srf, long=True)[0]
    cmds.setAttr(srf + ".visibility", 0)
    return srf


def _shape(srf):
    return cmds.listRelatives(srf, shapes=True, type="nurbsSurface", fullPath=True)[0]


def closest_uv(srf, point):
    cpos = cmds.createNode("closestPointOnSurface")
    cmds.connectAttr(_shape(srf) + ".worldSpace[0]", cpos + ".inputSurface")
    cmds.setAttr(cpos + ".inPosition", *point)
    u, v = cmds.getAttr(cpos + ".parameterU"), cmds.getAttr(cpos + ".parameterV")
    cmds.delete(cpos)
    shape = _shape(srf)
    (u0, u1), = cmds.getAttr(shape + ".minMaxRangeU")
    (v0, v1), = cmds.getAttr(shape + ".minMaxRangeV")
    return (u - u0) / ((u1 - u0) or 1.0), (v - v0) / ((v1 - v0) or 1.0)        # follicles use 0-1


def follicle(side, part, srf, u, v, parent):
    shape = cmds.createNode("follicle")
    fol = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    fol = cmds.rename(fol, names.make(side, part, "fol"))
    shape = cmds.listRelatives(fol, shapes=True, fullPath=True)[0]
    sshape = _shape(srf)
    cmds.connectAttr(sshape + ".local", shape + ".inputSurface")
    cmds.connectAttr(sshape + ".worldMatrix[0]", shape + ".inputWorldMatrix")
    cmds.connectAttr(shape + ".outTranslate", fol + ".translate")
    cmds.connectAttr(shape + ".outRotate", fol + ".rotate")
    cmds.setAttr(shape + ".parameterU", u)
    cmds.setAttr(shape + ".parameterV", v)
    cmds.setAttr(shape + ".visibility", 0)
    if parent:
        fol = cmds.parent(fol, parent)[0]
    return cmds.ls(fol, long=True)[0]


def drivers(side, part, matrices, labels, parent, radius):
    """Driver joints (one per matrix) that skin the ribbon. Not bind joints."""
    out = []
    for m, label in zip(matrices, labels):
        j = limb.joint_chain(side, [part + "_" + label], [m], parent, "drv", radius, chain=False)[0]
        out.append(j)
    return out


def skin(srf, joints):
    """Skin a ribbon (or curve) to its driver joints with clean weights: each driver's influence
    fades to exactly zero at its neighbours, so the ends only follow their own driver."""
    sk = cmds.skinCluster(joints, srf, toSelectedBones=True, maximumInfluences=2, dropoffRate=4.0,
                          name=srf.split("|")[-1] + "_skin")[0]
    even_weights(sk, srf, joints)
    return sk


def skin_curve(crv, joints, name):
    sk = cmds.skinCluster(joints, crv, toSelectedBones=True, maximumInfluences=2, name=name)[0]
    even_weights(sk, crv, joints)
    return sk


def _param_on(points, p):
    """0-1 position of point p along the polyline through points (closest spot)."""
    lengths = [mathx.distance(a, b) for a, b in zip(points[:-1], points[1:])]
    total = sum(lengths) or 1.0
    best, best_d, done = 0.0, None, 0.0
    for a, b, ln in zip(points[:-1], points[1:], lengths):
        ab = mathx.sub(b, a)
        t = mathx.dot(mathx.sub(p, a), ab) / max(mathx.dot(ab, ab), 1e-12)
        t = min(1.0, max(0.0, t))
        d = mathx.distance(p, mathx.add(a, mathx.scale(ab, t)))
        if best_d is None or d < best_d:
            best, best_d = (done + t * ln) / total, d
        done += ln
    return best


def _cvs(geo):
    """[(cv, row along the length, rows)]: a ribbon runs along U (two CVs across, in V)."""
    shape = (cmds.listRelatives(geo, shapes=True, fullPath=True, noIntermediate=True) or [geo])[0]
    if cmds.nodeType(shape) == "nurbsSurface":
        du, dv = cmds.getAttr(shape + ".degreeUV")[0]
        su, sv = cmds.getAttr(shape + ".spansUV")[0]
        nu, nv = int(su + du), int(sv + dv)
        if nv > nu:                                      # the length runs along V
            return [("%s.cv[%d][%d]" % (shape, u, v), v, nv) for u in range(nu) for v in range(nv)]
        return [("%s.cv[%d][%d]" % (shape, u, v), u, nu) for u in range(nu) for v in range(nv)]
    if cmds.nodeType(shape) == "nurbsCurve":
        n = int(cmds.getAttr(shape + ".spans") + cmds.getAttr(shape + ".degree"))
        return [("%s.cv[%d]" % (shape, i), i, n) for i in range(n)]
    return []


def even_weights(sk, geo, joints):
    """Weights by position along the drivers: between two neighbouring drivers they cross-fade
    linearly; past the first / last driver only that driver counts. The first and last two CV rows
    belong to the end drivers alone, so the ends don't even turn when a middle driver moves."""
    try:
        cvs = _cvs(geo)
        if not cvs or len(joints) < 2:
            return
        dpos = [mathx.position(limb.world(j)) for j in joints]
        order = sorted(range(len(joints)), key=lambda i: _param_on(dpos, dpos[i]))
        joints = [joints[i] for i in order]
        dpos = [dpos[i] for i in order]
        dpar = [_param_on(dpos, p) for p in dpos]
        for cv, row, rows in cvs:
            t = _param_on(dpos, cmds.xform(cv, query=True, worldSpace=True, translation=True))
            if rows >= 6 and row < 2:
                t = dpar[0]
            elif rows >= 6 and row >= rows - 2:
                t = dpar[-1]
            weights = [0.0] * len(joints)
            if t <= dpar[0]:
                weights[0] = 1.0
            elif t >= dpar[-1]:
                weights[-1] = 1.0
            else:
                for k in range(len(joints) - 1):
                    if dpar[k] <= t <= dpar[k + 1]:
                        f = (t - dpar[k]) / ((dpar[k + 1] - dpar[k]) or 1.0)
                        weights[k], weights[k + 1] = 1.0 - f, f
                        break
            cmds.skinPercent(sk, cv, transformValue=list(zip(joints, weights)))
    except (RuntimeError, ValueError, TypeError, AttributeError):
        pass                                         # keep Maya's own weights


def _blend_orient(drv, own, other, amount_plug, name):
    """drv turns with own, and with other by amount x 0.5 (amount 1: half way - the corner's bisector).
    A parent constraint with no translate: one offset per target, so nothing moves at rest."""
    con = cmds.parentConstraint(own, other, drv, maintainOffset=True, skipTranslate=["x", "y", "z"],
                                name=name + "_round_con")[0]
    cmds.setAttr(con + ".interpType", 2)
    w_own, w_other = cmds.parentConstraint(con, query=True, weightAliasList=True)
    half = cmds.createNode("multDoubleLinear", name=name + "_round_half")
    cmds.connectAttr(amount_plug, half + ".input1")
    cmds.setAttr(half + ".input2", 0.5)
    rest = cmds.createNode("plusMinusAverage", name=name + "_round_rest")
    cmds.setAttr(rest + ".operation", 2)                       # 1 - half
    cmds.setAttr(rest + ".input1D[0]", 1.0)
    cmds.connectAttr(half + ".output", rest + ".input1D[1]")
    cmds.connectAttr(half + ".output", con + "." + w_other)
    cmds.connectAttr(rest + ".output1D", con + "." + w_own)
    return con


def bendy_limb(side, parts, joints, twist_count, ctx, up_axis, corner):
    """Two bendy pieces (upper and lower bone) and a bend control ON the middle joint (knee / elbow): moving it
    bends both pieces into it; its 'roundness' (0-1) turns the two ends at the joint towards each other, so the
    corner rounds. parts: the upper / lower bone names; joints: (upper, middle, end) bind joints; corner: the
    control's name ('knee', 'elbow'). Returns (twist joints, [the three bend controls])."""
    a, mid, b = joints
    off, knee = controls.make(side, corner, ctx.shape("bend"), ctx.size("bend") * 1.4, limb.world(mid),
                              ctx.module_ctrls, "X", "bend", lock=("rx", "ry", "rz", "sx", "sy", "sz", "v"))
    cmds.parentConstraint(mid, off, maintainOffset=True)        # it follows the knee; zero at rest
    roundness = controls.add_float(knee, "roundness", 0.0, 0.0, 1.0)
    t1, bend1 = bendy_segment(side, parts[0], a, mid, twist_count, ctx, False, up_axis, end_at=knee,
                              round_with=(mid, roundness))
    t2, bend2 = bendy_segment(side, parts[1], mid, b, twist_count, ctx, True, up_axis, start_at=knee,
                              round_with=(a, roundness))
    return t1 + t2, [bend1, knee, bend2]


def bendy_segment(side, part, a_jnt, b_jnt, twist_count, ctx, twist_from_end, up_axis="Y", start_at=None,
                  end_at=None, round_with=None):
    """
    A bendy piece between bind joints a_jnt and b_jnt: a ribbon with a mid 'bend' control and
    twist_count twist joints riding on it. The end follows b_jnt's twist when twist_from_end.
    start_at / end_at: a control the start / end follows instead of its joint (a knee bend control).
    round_with: (the other bone's joint, roundness plug) - that end turns towards the other bone by roundness.
    Returns (twist joints, bend control).
    """
    wa, wb = limb.world(a_jnt), limb.world(b_jnt)
    pa, pb = mathx.position(wa), mathx.position(wb)
    length = mathx.distance(pa, pb)
    up = mathx.axis_of(wa, up_axis)
    pts = [mathx.lerp(pa, pb, t / 4.0) for t in range(5)]
    srf = strip(side, part + "_bendy", pts, [up] * 5, length * 0.15, ctx.nodes)

    mids = list(wa)
    mids[12:15] = mathx.lerp(pa, pb, 0.5)
    ends = list(wa)
    ends[12:15] = pb
    drv = drivers(side, part + "_bendy", [wa, mids, ends], ["start", "mid", "end"], ctx.nodes, ctx.radius * 0.5)
    limb.hide(drv)
    tag = names.make(side, part + "_bendy", "grp").replace("_grp", "")
    if start_at:                                            # the start rides on a knee / elbow bend control
        cmds.pointConstraint(start_at, drv[0], maintainOffset=False)
        if round_with:
            _blend_orient(drv[0], a_jnt, round_with[0], round_with[1], tag + "_start")
        else:
            cmds.orientConstraint(a_jnt, drv[0], maintainOffset=True)
    else:
        cmds.parentConstraint(a_jnt, drv[0], maintainOffset=True)
    cmds.pointConstraint(end_at or b_jnt, drv[2], maintainOffset=False)
    own = b_jnt if twist_from_end else a_jnt
    if end_at and round_with:
        _blend_orient(drv[2], own, round_with[0], round_with[1], tag + "_end")
    else:
        cmds.orientConstraint(own, drv[2], maintainOffset=True)
    skin(srf, drv)

    # bend control halfway, following both ends
    off, bend = controls.make(side, part, ctx.shape("bend"), ctx.size("bend"), mids, ctx.module_ctrls, "X",
                              "bend", lock=("rx", "ry", "rz", "sx", "sy", "sz", "v"))
    cmds.pointConstraint(drv[0], drv[2], off, maintainOffset=False)
    cmds.orientConstraint(drv[0], off, maintainOffset=True)
    cmds.parentConstraint(bend, drv[1], maintainOffset=True)

    twists = []
    fol_grp = controls.group(names.make(side, part + "_bendyFol", "grp"), ctx.nodes)
    for i in range(int(twist_count)):
        t = (i + 0.5) / float(twist_count)
        p = mathx.lerp(pa, pb, t)
        u, v = closest_uv(srf, p)
        fol = follicle(side, "%s_twist_%02d" % (part, i + 1), srf, u, v, fol_grp)
        m = list(wa)
        m[12:15] = p
        tj = limb.joint_chain(side, ["%s_twist_%02d" % (part, i + 1)], [m], ctx.skeleton_extra, None,
                              ctx.radius * 0.6, chain=False)[0]
        cmds.parentConstraint(fol, tj, maintainOffset=True)
        twists.append(tj)
    return twists, bend
