"""
In-Maya self-test: builds a biped and a quadruped in new scenes and measures what the rig really
does (Maya solves the constraints and IK here, which the offline tests can't).

    import gus_rigtool.builder.selftest as st; print(st.run())

Checks (numbers in Maya units; the limit is in brackets):
    spine mid      the mid spine control bends the middle joints but the hips and chest stay still
    IK/FK match    after Switch to FK / to IK the FK and IK joints are in the same place
    lips           a lip corner follows the jaw at 0.5 (the jaw_follow default)
    toes           the toes stay on the toe joint when the paw rolls
    head axes      the head joint has the neck's axes (head_axes = neck)
    stretch        quadruped legs: the ball stays on the paw and femur / tibia / metatarsus stretch evenly
"""

import platform

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.builder import build as bld
from gus_rigtool.builder import controls, guides, limb, mathx, modules, names
from gus_rigtool.core import mirror_engine as me
from gus_rigtool.core import utils

TOL = 0.01
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


class _Skip(Exception):
    pass


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _one(name):
    found = cmds.ls(name, long=True) or []
    if not found:
        raise _Skip("'%s' not found" % name)
    return found[0]


def _pos(node):
    return mathx.position(limb.world(node))


def _in(m, p):
    """p in m's space (so we can see whether p stayed on m)."""
    return me.mul(mathx.translate_matrix(p), me.inverse(m))[12:15]


def _out(m, local):
    return me.mul(mathx.translate_matrix(local), m)[12:15]


def _snapshot(nodes):
    """Keyable values of nodes, to put the pose back after a check."""
    out = []
    for n in nodes:
        for a in cmds.listAttr(n, keyable=True) or []:
            plug = n + "." + a
            if utils.settable(plug):
                try:
                    v = cmds.getAttr(plug)
                except (RuntimeError, ValueError):
                    continue
                if isinstance(v, (int, float, bool)):
                    out.append((plug, v))
    return out


def _restore(snap):
    for plug, v in snap:
        try:
            cmds.setAttr(plug, v)
        except RuntimeError:
            pass


def _infos(mtype):
    out = []
    for g in guides.module_groups():
        info = guides.read(g)
        if info["type"] == mtype:
            out.append(info)
    return out


def _settings(info):
    return modules.MODULES[info["type"]].complete(dict(info["settings"]))


def _row(rows, status, name, value=None, note=""):
    rows.append((status, name, value, note))


def _measure(rows, name, value, limit=TOL, note=""):
    _row(rows, PASS if value <= limit else FAIL, name, value, note or "limit %g" % limit)


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

def check_spine(rows, height):
    for info in _infos("spine"):
        s = _settings(info)
        if s["options"].get("type", "fk") == "fk":
            _row(rows, SKIP, "spine mid", note="spine type is fk (no mid control)")
            continue
        n = s["names"]
        try:
            mid = _one(names.make("C", n["mid"], "ctrl"))
            hips = _one(names.make("C", n["hips"], "jnt"))
            chest = _one(names.make("C", n["chain"][-1], "jnt"))
            middle = [_one(names.make("C", p, "jnt")) for p in n["chain"][1:-1]]
        except _Skip as e:
            _row(rows, SKIP, "spine mid", note=str(e))
            continue
        before = [_pos(x) for x in [hips, chest] + middle]
        snap = _snapshot([mid])
        cmds.setAttr(mid + ".translateZ", height * 0.05)
        cmds.setAttr(mid + ".rotateX", 15)
        after = [_pos(x) for x in [hips, chest] + middle]
        _restore(snap)
        _measure(rows, "spine mid: hips stay", mathx.distance(before[0], after[0]))
        _measure(rows, "spine mid: chest stays", mathx.distance(before[1], after[1]))
        moved = max([mathx.distance(a, b) for a, b in zip(before[2:], after[2:])] or [0.0])
        _row(rows, PASS if moved > TOL else FAIL, "spine mid: middle joints move", moved, "must be > %g" % TOL)


def _limb_settings():
    out = []
    for n in utils.nodes_with_attr("gusBlend"):
        if controls.get_string(n, "gusBlend") and not controls.get_string(n, "gusChain"):
            out.append(n)
    return out


def check_ikfk(rows, height):
    found = _limb_settings()
    if not found:
        _row(rows, SKIP, "IK/FK match", note="no limbs")
    for s in found:
        label = s.split("|")[-1]
        blend = s + "." + controls.get_string(s, "gusBlend")
        fkc = [_one(x) for x in limb._meta(s, "gusFkCtrls") if cmds.ls(x)]
        ikc = [_one(x) for x in limb._meta(s, "gusIkCtrl") + limb._meta(s, "gusPvCtrl") + limb._meta(s, "gusHockCtrl")
               if cmds.ls(x)]
        fkj = [_one(x) for x in limb._meta(s, "gusFkJoints") if cmds.ls(x)]
        ikj = [_one(x) for x in limb._meta(s, "gusIkJoints") if cmds.ls(x)]
        try:
            end = int(controls.get_string(s, "gusEnd") or 2)
        except ValueError:
            end = 2
        if not (fkc and ikc and len(fkj) > end and len(ikj) > end):
            _row(rows, SKIP, "IK/FK match %s" % label, note="limb data incomplete")
            continue
        snap = _snapshot([s] + fkc + ikc)
        # to FK: move the IK control, then switch
        cmds.setAttr(blend, 1)
        ik = ikc[0]
        p = _pos(ik)
        cmds.xform(ik, worldSpace=True, translation=[p[0], p[1] + height * 0.04, p[2] + height * 0.03])
        limb.match_fk_to_ik(s)
        d = max(mathx.distance(_pos(a), _pos(b)) for a, b in zip(fkj[:end + 1], ikj[:end + 1]))
        _measure(rows, "IK/FK match %s: to FK" % label, d)
        _restore(snap)
        # to IK: bend the FK chain, then switch
        cmds.setAttr(blend, 0)
        for c in fkc[:end]:
            for ax in "XYZ":
                if utils.settable(c + ".rotate" + ax):
                    cmds.setAttr(c + ".rotate" + ax, 12)
        limb.match_ik_to_fk(s)
        d_end = mathx.distance(_pos(fkj[end]), _pos(ikj[end]))
        d_mid = max(mathx.distance(_pos(a), _pos(b)) for a, b in zip(fkj[1:end], ikj[1:end])) if end > 1 else 0.0
        _measure(rows, "IK/FK match %s: to IK (end)" % label, d_end)
        _measure(rows, "IK/FK match %s: to IK (knee / elbow)" % label, d_mid)
        _restore(snap)


def check_lips(rows, height):
    for info in _infos("face"):
        s = _settings(info)
        if not (s["options"].get("jaw") and s["options"].get("lips")):
            _row(rows, SKIP, "lips follow the jaw", note="no jaw or lips")
            continue
        n = s["names"]
        try:
            jaw_c = _one(names.make("C", n["jaw"], "ctrl"))
            jaw_j = _one(names.make("C", n["jaw"], "jnt"))
            corner = _one(names.make("L", n["lip_corner"], "jnt"))
            lower = _one(names.make("C", n["lip_lower"], "jnt"))
        except _Skip as e:
            _row(rows, SKIP, "lips follow the jaw", note=str(e))
            continue
        follow = cmds.getAttr(names.make("L", n["lip_corner"], "ctrl") + ".jaw_follow") \
            if cmds.objExists(names.make("L", n["lip_corner"], "ctrl") + ".jaw_follow") else 0.5
        m0 = limb.world(jaw_j)
        c0, l0 = _pos(corner), _pos(lower)
        snap = _snapshot([jaw_c])
        for ax, v in (("X", 12), ("Y", 8), ("Z", 6)):        # any turn: we compare with a rigid follow
            if utils.settable(jaw_c + ".rotate" + ax):
                cmds.setAttr(jaw_c + ".rotate" + ax, v)
        m1 = limb.world(jaw_j)
        c1, l1 = _pos(corner), _pos(lower)
        _restore(snap)
        full_c = _out(m1, _in(m0, c0))
        full_l = _out(m1, _in(m0, l0))
        if mathx.distance(full_c, c0) < 1e-6:
            _row(rows, SKIP, "lips follow the jaw", note="the jaw control didn't turn the jaw")
            continue
        ratio = mathx.distance(c1, c0) / mathx.distance(full_c, c0)
        _measure(rows, "lips: corner follows the jaw at %.2f" % follow, abs(ratio - follow), 0.05,
                 "measured %.3f" % ratio)
        _measure(rows, "lips: lower lip follows the jaw fully", mathx.distance(l1, full_l))


def check_toes(rows, height):
    any_ = False
    for mtype in ("back_leg", "front_leg"):
        mod = modules.MODULES[mtype]
        for info in _infos(mtype):
            s = _settings(info)
            toes = mod.toe_list(s)
            if not toes:
                continue
            any_ = True
            side, n = info["side"], s["names"]
            label = "%s %s" % (side, info["name"])
            try:
                base = _one(names.make(side, n[mod.toes_base(s)], "jnt"))
                firsts = [_one(names.make(side, mod.toe_parts(s, t)[0], "jnt")) for t in toes]
                settings_c = _one(names.make(side, n["ball"], "ctrl", "settings"))
                paw = _one(limb._meta(settings_c, "gusIkCtrl")[0])
            except (_Skip, IndexError) as e:
                _row(rows, SKIP, "toes %s" % label, note=str(e) or "no paw control")
                continue
            m0 = limb.world(base)
            local = [_in(m0, _pos(f)) for f in firsts]
            snap = _snapshot([settings_c, paw])
            blend = controls.get_string(settings_c, "gusBlend")
            if blend:
                cmds.setAttr(settings_c + "." + blend, 1)
            for attr, v in (("toe_roll", 30), ("tip_roll", 20), ("toe_tap", 25), ("ball_roll", 15)):
                if cmds.objExists(paw + "." + attr):
                    cmds.setAttr(paw + "." + attr, v)
            m1 = limb.world(base)
            d = max(mathx.distance(_out(m1, lc), _pos(f)) for lc, f in zip(local, firsts))
            _restore(snap)
            _measure(rows, "toes %s stay on the %s joint" % (label, mod.toes_base(s)), d)
    if not any_:
        _row(rows, SKIP, "toes", note="no legs with toes")


def check_head(rows, height):
    for info in _infos("neck"):
        s = _settings(info)
        if s["options"].get("head_axes", "neck") != "neck":
            _row(rows, SKIP, "head axes", note="head_axes is '%s'" % s["options"].get("head_axes"))
            continue
        n = s["names"]
        try:
            head = limb.world(_one(names.make("C", n["head"], "jnt")))
            neck = limb.world(_one(names.make("C", n["chain"][-1], "jnt")))
        except _Skip as e:
            _row(rows, SKIP, "head axes", note=str(e))
            continue
        worst = max(1.0 - mathx.dot(mathx.norm(head[r * 4:r * 4 + 3]), mathx.norm(neck[r * 4:r * 4 + 3]))
                    for r in range(3))
        _measure(rows, "head axes match the neck", worst, 0.0001, "1 - cos(angle), worst axis")


def check_stretch(rows, height):
    """Quadruped legs with stretch on: pull the paw away, the ball stays on the paw and all 3 bones
    (femur, tibia, metatarsus / humerus, radius, metacarpus) grow by the same ratio."""
    any_ = False
    for mtype in ("back_leg", "front_leg"):
        mod = modules.MODULES[mtype]
        for info in _infos(mtype):
            s = _settings(info)
            if not s["options"].get("stretch"):
                continue
            any_ = True
            side, n = info["side"], s["names"]
            label = "%s %s" % (side, info["name"])
            try:
                joints = [_one(names.make(side, n[r], "jnt")) for r in mod.LEG[:4]]
                settings_c = _one(names.make(side, n["ball"], "ctrl", "settings"))
                paw = _one(limb._meta(settings_c, "gusIkCtrl")[0])
            except (_Skip, IndexError) as e:
                _row(rows, SKIP, "stretch %s" % label, note=str(e) or "no paw control")
                continue
            p0 = [_pos(j) for j in joints]
            rest = [mathx.distance(a, b) for a, b in zip(p0, p0[1:])]
            snap = _snapshot([settings_c, paw])
            blend = controls.get_string(settings_c, "gusBlend")
            if blend:
                cmds.setAttr(settings_c + "." + blend, 1)
            cmds.setAttr(settings_c + ".stretch", 1)
            pull = mathx.scale(mathx.norm(mathx.sub(p0[3], p0[0])), sum(rest) * 0.4)
            pp = _pos(paw)
            cmds.xform(paw, worldSpace=True, translation=mathx.add(pp, pull))
            p1 = [_pos(j) for j in joints]
            ratios = [mathx.distance(a, b) / max(r, 1e-9) for a, b, r in zip(p1, p1[1:], rest)]
            _restore(snap)
            _measure(rows, "stretch %s: ball stays on the paw" % label, mathx.distance(p1[3], mathx.add(p0[3], pull)))
            _measure(rows, "stretch %s: bones stretch evenly" % label, max(ratios) - min(ratios), 0.001,
                     "ratios %s" % ", ".join("%.3f" % r for r in ratios))
    if not any_:
        _row(rows, SKIP, "stretch", note="no quadruped legs with stretch")


def _rel(child, parent):
    """child's rotation in its parent's space (3x3 rows)."""
    m = me.mul(limb.world(child), me.inverse(limb.world(parent)))
    return [m[0:3], m[4:7], m[8:11]]


def _turned(a, b):
    """Degrees between two rotations (3x3 rows)."""
    import math
    tr = sum(sum(x * y for x, y in zip(a[r], b[r])) for r in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def check_fingers(rows, height):
    """Curl turns every joint of every finger (not a metacarpal); spread opens the outer fingers."""
    found = False
    for info in _infos("fingers"):
        s = _settings(info)
        if not s["options"].get("curl_attrs"):
            continue
        mod = modules.MODULES["fingers"]
        side = info["side"]
        settings_c = None
        for c in utils.nodes_with_attr("spread"):
            if any(cmds.attributeQuery(f + "_curl", node=c, exists=True) for f in s["names"]["fingers"]) \
                    and c.split("|")[-1].startswith(side):
                settings_c = c
        if not settings_c:
            _row(rows, SKIP, "fingers %s" % side, note="no curl attributes found")
            continue
        found = True
        for finger in s["names"]["fingers"]:
            parts = mod.finger_parts(s, finger)
            meta = bool(s["options"]["metacarpal"]) and finger != "thumb"
            try:
                js = [_one(names.make(side, p_, "jnt")) for p_ in parts]
            except _Skip as e:
                _row(rows, SKIP, "fingers %s %s" % (side, finger), note=str(e))
                continue
            parents = [(cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0] for j in js]
            before = [_rel(j, p_) for j, p_ in zip(js, parents)]
            snap = _snapshot([settings_c])
            cmds.setAttr(settings_c + "." + finger + "_curl", 30)
            after = [_rel(j, p_) for j, p_ in zip(js, parents)]
            _restore(snap)
            still = [parts[i] for i, (b, a) in enumerate(zip(before, after))
                     if _turned(b, a) < 5.0 and not (meta and i == 0)]
            _row(rows, PASS if not still else FAIL, "fingers %s %s: curl turns every joint" % (side, finger),
                 None, ("not turning: " + ", ".join(still)) if still else "%d joint(s)" % len(js))
        others = [f for f in s["names"]["fingers"] if f != "thumb"]
        if len(others) > 1:
            try:
                a = _one(names.make(side, mod.finger_parts(s, others[0])[-1], "jnt"))
                b = _one(names.make(side, mod.finger_parts(s, others[-1])[-1], "jnt"))
            except _Skip:
                continue
            d0 = mathx.distance(_pos(a), _pos(b))
            snap = _snapshot([settings_c])
            cmds.setAttr(settings_c + ".spread", 20)
            d1 = mathx.distance(_pos(a), _pos(b))
            _restore(snap)
            _row(rows, PASS if d1 > d0 + 1e-3 else FAIL, "fingers %s: spread opens the outer fingers" % side,
                 d1 - d0, "distance gained between %s and %s" % (others[0], others[-1]))
    if not found:
        _row(rows, SKIP, "fingers", note="no fingers with curl attributes")


def check_soft_ik(rows, height):
    """Arms with soft IK: pulled exactly straight, the wrist stays short of the IK control by the soft amount
    (no pop) - and close in, the wrist is on the control."""
    import math
    found = False
    for info in _infos("arm"):
        s = _settings(info)
        if not s["options"].get("soft_ik"):
            continue
        found = True
        side, n = info["side"], s["names"]
        label = "%s %s" % (side, info["name"])
        try:
            hum, rad, wri = [_one(names.make(side, n[r], "jnt")) for r in ("humerus", "radius", "wrist")]
            settings_c = _one(names.make(side, n["wrist"], "ctrl", "settings"))
            ik = _one(limb._meta(settings_c, "gusIkCtrl")[0])
        except (_Skip, IndexError) as e:
            _row(rows, SKIP, "soft IK %s" % label, note=str(e) or "no IK control")
            continue
        a, b, c = _pos(hum), _pos(rad), _pos(wri)
        L = mathx.distance(a, b) + mathx.distance(b, c)
        direction = mathx.norm(mathx.sub(c, a))
        snap = _snapshot([settings_c, ik])
        cmds.setAttr(settings_c + ".ikfk", 1)
        cmds.setAttr(settings_c + ".soft_ik", 0.4)
        cmds.xform(ik, worldSpace=True, translation=mathx.add(a, mathx.scale(direction, L)))
        got = mathx.distance(_pos(hum), _pos(wri))
        s_ = 0.4 * L * 0.25
        want = (L - s_) + s_ * (1 - math.exp(-1.0))
        cmds.xform(ik, worldSpace=True, translation=mathx.add(a, mathx.scale(direction, L * 0.7)))
        near = mathx.distance(_pos(wri), mathx.add(a, mathx.scale(direction, L * 0.7)))
        _restore(snap)
        _measure(rows, "soft IK %s: straight pull stays soft" % label, abs(got - want), 0.01 * L,
                 "wrist at %.3f of the length, wanted %.3f" % (got / L, want / L))
        _measure(rows, "soft IK %s: close in, the wrist is on the control" % label, near)
    if not found:
        _row(rows, SKIP, "soft IK", note="no arms with soft IK")


def check_pin_length(rows, height):
    """Legs with pin / length per bone: pinned, the knee sits on the pole vector; upper_length 1.5 makes the
    thigh 1.5 times longer."""
    found = False
    for info in _infos("leg"):
        s = _settings(info)
        o = s["options"]
        if not (o.get("pin") or o.get("bone_length")):
            continue
        found = True
        side, n = info["side"], s["names"]
        label = "%s %s" % (side, info["name"])
        try:
            fem, tib = [_one(names.make(side, n[r], "jnt")) for r in ("femur", "tibia")]
            settings_c = _one(names.make(side, n["ankle"], "ctrl", "settings"))
            pv = _one(limb._meta(settings_c, "gusPvCtrl")[0])
        except (_Skip, IndexError) as e:
            _row(rows, SKIP, "pin / length %s" % label, note=str(e) or "no pole vector")
            continue
        snap = _snapshot([settings_c, pv])
        cmds.setAttr(settings_c + ".ikfk", 1)
        if o.get("bone_length"):
            rest = mathx.distance(_pos(fem), _pos(tib))
            cmds.setAttr(settings_c + ".upper_length", 1.5)
            got = mathx.distance(_pos(fem), _pos(tib))
            cmds.setAttr(settings_c + ".upper_length", 1.0)
            _measure(rows, "length per bone %s: upper_length 1.5" % label, abs(got - rest * 1.5), 0.01 * rest,
                     "thigh %.3f of its length, wanted 1.5" % (got / rest if rest else 0))
        if o.get("pin"):
            cmds.setAttr(settings_c + ".pin", 1)
            p = mathx.add(_pos(pv), [0.0, -height * 0.02, 0.0])
            cmds.xform(pv, worldSpace=True, translation=p)
            _measure(rows, "pin %s: the knee is on the pole vector" % label, mathx.distance(_pos(tib), p),
                     note="")
        _restore(snap)
    if not found:
        _row(rows, SKIP, "pin / length", note="no legs with pin or length per bone")


def check_ik_mirror(rows, height):
    """Right IK controls that mirror the left: the same values put them at mirror places (move both = mirror)."""
    found = False
    for c in [t for t in cmds.ls(type="transform", long=True) or [] if t.endswith("_ik_hold_grp")]:
        ctrl = cmds.listRelatives(c, parent=True, fullPath=True)
        if not ctrl:
            continue
        r = ctrl[0]
        from gus_rigtool.core import naming, sides
        twin = naming.mirror_name(r.split("|")[-1], sides.default_pairs())
        l = (cmds.ls(twin, long=True) or [None])[0] if twin else None
        if not l:
            continue
        found = True
        snap = _snapshot([l, r])
        for node in (l, r):
            for a, v in (("tx", height * 0.03), ("ty", height * 0.02), ("ry", 15.0)):
                if cmds.getAttr(node + "." + a, settable=True):
                    cmds.setAttr(node + "." + a, v)
        pl, pr = _pos(l), _pos(r)
        _restore(snap)
        _measure(rows, "IK mirror %s: same values, mirror places" % r.split("|")[-1],
                 mathx.distance(pl, [-pr[0], pr[1], pr[2]]))
    if not found:
        _row(rows, SKIP, "IK mirror", note="no mirrored right IK controls")


def _rot_diff(a, b):
    return max(1.0 - mathx.dot(mathx.norm(a[r * 4:r * 4 + 3]), mathx.norm(b[r * 4:r * 4 + 3])) for r in range(3))


def check_head_spaces(rows, height):
    """At rest, every head space gives the same head: switching never turns it (one offset per target)."""
    for info in _infos("neck"):
        n = _settings(info)["names"]
        try:
            head = _one(names.make("C", n["head"], "ctrl"))
            joint = _one(names.make("C", n["head"], "jnt"))
        except _Skip as e:
            _row(rows, SKIP, "head spaces", note=str(e))
            continue
        if not cmds.attributeQuery("space", node=head, exists=True):
            _row(rows, SKIP, "head spaces", note="no head space switch")
            continue
        snap = _snapshot([head])
        rest = limb.world(joint)
        count = len((cmds.attributeQuery("space", node=head, listEnum=True) or [""])[0].split(":"))
        worst = 0.0
        for i in range(count):
            cmds.setAttr(head + ".space", i)
            worst = max(worst, _rot_diff(rest, limb.world(joint)),
                        mathx.distance(rest[12:15], limb.world(joint)[12:15]) / max(height, 1e-6))
        _restore(snap)
        _measure(rows, "head spaces: switching at rest doesn't turn the head", worst, 0.0001,
                 "1 - cos(angle) or move / height, worst space")


def check_no_flip(rows, height):
    """Legs with no-flip: knee_mode 1 at rest keeps the knee (no pop); turning the foot turns the knee."""
    found = False
    for info in _infos("leg"):
        s = _settings(info)
        if not s["options"].get("no_flip"):
            continue
        found = True
        side, n = info["side"], s["names"]
        label = "%s %s" % (side, info["name"])
        try:
            tib = _one(names.make(side, n["tibia"], "jnt"))
            settings_c = _one(names.make(side, n["ankle"], "ctrl", "settings"))
            ik = _one(limb._meta(settings_c, "gusIkCtrl")[0])
        except (_Skip, IndexError) as e:
            _row(rows, SKIP, "no-flip %s" % label, note=str(e) or "no IK control")
            continue
        snap = _snapshot([settings_c, ik])
        cmds.setAttr(settings_c + ".ikfk", 1)
        k0 = _pos(tib)
        cmds.setAttr(settings_c + ".knee_mode", 1)
        k1 = _pos(tib)
        cmds.setAttr(ik + ".ry", 40)
        k2 = _pos(tib)
        _restore(snap)
        _measure(rows, "no-flip %s: knee_mode 1 at rest, no pop" % label, mathx.distance(k0, k1))
        moved = mathx.distance(k1, k2)
        _row(rows, PASS if moved > 0.01 else FAIL, "no-flip %s: turning the foot turns the knee" % label, moved,
             "must be > 0.01")
    if not found:
        _row(rows, SKIP, "no-flip", note="no legs with no-flip")


def check_spine_volume(rows, height):
    """Spines with volume: stretched (chest pulled away), the middle joints get thinner."""
    found = False
    for info in _infos("spine"):
        s = _settings(info)
        if not s["options"].get("volume") or s["options"].get("type", "fk") == "fk":
            continue
        found = True
        n = s["names"]
        try:
            chest = _one(names.make("C", n["chest"], "ctrl"))
            mid_j = _one(names.make("C", n["chain"][len(n["chain"]) // 2], "jnt"))
            hips = _pos(_one(names.make("C", n["chain"][0], "jnt")))
        except _Skip as e:
            _row(rows, SKIP, "spine volume", note=str(e))
            continue
        snap = _snapshot([chest])
        p = _pos(chest)
        cmds.xform(chest, worldSpace=True, translation=mathx.add(p, mathx.scale(mathx.sub(p, hips), 0.3)))
        m = limb.world(mid_j)
        side = min(mathx.length(m[4:7]), mathx.length(m[8:11]), mathx.length(m[0:3]))
        _restore(snap)
        _row(rows, PASS if side < 0.99 else FAIL, "spine volume: stretched, the middle gets thinner", side,
             "side scale, must be < 0.99")
    if not found:
        _row(rows, SKIP, "spine volume", note="no spine with volume")


def check_rebuild_constraint(rows, height):
    """A constraint of yours on a builder group (the clavicle's offset, held by a locator): move the guide,
    rebuild - the part goes to the new guide (the constraint is re-made with a fresh offset)."""
    infos = [i for i in _infos("arm") if i["side"] == "L"]
    if not infos:
        _row(rows, SKIP, "rebuild keeps your constraint", note="no left arm")
        return
    info = infos[0]
    n = _settings(info)["names"]
    try:
        off = _one(names.make("L", n["clavicle"], "offset", "fk"))
    except _Skip as e:
        _row(rows, SKIP, "rebuild keeps your constraint", note=str(e))
        return
    loc = cmds.spaceLocator(name="selftest_holder")[0]
    cmds.parentConstraint(loc, off, maintainOffset=True)
    bld.back_to_guides_selected([info["id"]], force=True)
    g = guides.read(info["group"])["guides"]["clavicle"]
    p = cmds.xform(g, query=True, worldSpace=True, translation=True)
    target = [p[0], p[1] + height * 0.03, p[2]]
    cmds.xform(g, worldSpace=True, translation=target)
    bld.build_picked([info["id"]], height)
    j = _one(names.make("L", n["clavicle"], "jnt"))
    _measure(rows, "rebuild keeps your constraint: the clavicle goes to its moved guide", mathx.distance(_pos(j), target))


CHECKS = [check_spine, check_ikfk, check_lips, check_toes, check_head, check_stretch, check_fingers,
          check_soft_ik, check_pin_length, check_ik_mirror, check_head_spaces, check_no_flip,
          check_spine_volume, check_rebuild_constraint]


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def _one_template(kind, height, rows):
    cmds.file(new=True, force=True)
    (bld.biped if kind == "biped" else bld.quadruped)(height)
    for g in guides.module_groups():                 # the spine with a mid control, so its check runs
        info = guides.read(g)
        if info["type"] == "spine" and info["settings"].get("options", {}).get("type", "fk") == "fk":
            s = _settings(info)
            s["options"]["type"] = "ribbon"
            s["options"]["volume"] = True                 # so its check runs
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES["spine"], s, height)
        if info["type"] in ("back_leg", "front_leg") and not info["settings"].get("options", {}).get("stretch"):
            s = _settings(info)                      # stretch on, so its check runs
            s["options"]["stretch"] = True
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES[info["type"]], s, height)
        if info["type"] == "arm" and not info["settings"].get("options", {}).get("soft_ik"):
            s = _settings(info)                      # soft IK on, so its check runs
            s["options"]["soft_ik"] = True
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES["arm"], s, height)
        if info["type"] == "leg" and not info["settings"].get("options", {}).get("pin"):
            s = _settings(info)                      # pin + length per bone on, so their check runs
            s["options"]["pin"] = True
            s["options"]["bone_length"] = True
            s["options"]["no_flip"] = True
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES["leg"], s, height)
        if info["type"] == "fingers" and not info["settings"].get("options", {}).get("curl_attrs"):
            s = _settings(info)                      # curl / spread on, so their check runs
            s["options"]["curl_attrs"] = True
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES["fingers"], s, height)
    bld.build_all(height)
    for check in CHECKS:
        try:
            check(rows, height)
        except Exception as e:                       # one broken check never hides the others
            _row(rows, FAIL, "%s crashed" % check.__name__, note="%s: %s" % (type(e).__name__, e))


def run(height=180.0, templates=("biped", "quadruped")):
    """Builds each template in a NEW scene (the current one is closed without saving) and returns the report."""
    sections = []
    for kind in templates:
        rows = []
        try:
            _one_template(kind, height, rows)
        except Exception as e:
            _row(rows, FAIL, "%s build" % kind, note="%s: %s" % (type(e).__name__, e))
        sections.append((kind, rows))
    return report(sections)


def report(sections):
    try:
        maya_v = cmds.about(version=True)
    except Exception:
        maya_v = "?"
    lines = ["Gus_Rigtool %s self-test - Maya %s - %s" % (gus_rigtool.__version__, maya_v, platform.system())]
    counts = {PASS: 0, FAIL: 0, SKIP: 0}
    for kind, rows in sections:
        lines.append("")
        lines.append("== %s" % kind)
        for status, name, value, note in rows:
            counts[status] += 1
            val = "" if value is None else "  %.4f" % value
            lines.append("  %-4s  %s%s%s" % (status, name, val, ("  (%s)" % note) if note else ""))
    lines.insert(1, "%d passed, %d failed, %d skipped" % (counts[PASS], counts[FAIL], counts[SKIP]))
    return "\n".join(lines)
