"""
Chain: a free chain of joints (tail, ear, antenna, hair strand, tie...).

Types
    fk                FK controls only.
    fk + ik spline    FK and an IK spline (a curve bent by IK controls), IK/FK switch.
    fk + ribbon       FK and a ribbon (joints ride on a surface bent by IK controls), IK/FK switch.

You choose the joints that get FK controls and IK controls ('all', 'auto', or numbers such as
'1, 4, 8' or '1-5'; joint 1 is the first, the end joint is the last number).

    bind joints  <- tweak controls (optional)  <- result: FK or blend(FK, IK)

Settings control (next to the last joint): ikfk, stretch, volume, tweaks, curl, curl_side.
"""

import math

import maya.cmds as cmds

from gus_rigtool.builder import controls, limb, mathx, names, ribbons
from gus_rigtool.builder.module_base import Module, _mirror_specs

TYPES = ["fk", "fk + ik spline", "fk + ribbon"]
CHAIN_ORIENT = {"aim": "X", "up": "Y", "up_mode": "world", "world_up": [0, 1, 0], "behavior_right": True}


# ---------------------------------------------------------------------------
# which joints get controls
# ---------------------------------------------------------------------------

def parse_joints(text, total, default="all", controllable=None):
    """'all' / 'auto' / '1, 4, 8' / '1-5, 7' -> sorted 0-based indices (joint 1 = index 0).
    total: number of joints (with the end joint). controllable: how many may get FK controls."""
    text = (text or default or "").strip().lower()
    last = total - 1
    if text in ("", "all"):
        return list(range(controllable if controllable is not None else total))
    if text == "auto":
        return sorted(set([0, last // 2, last])) if total > 2 else list(range(total))
    out = set()
    for piece in text.replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece[1:]:
            a, b = piece.split("-", 1)
            lo, hi = int(a), int(b)
            out.update(range(min(lo, hi), max(lo, hi) + 1))
        else:
            out.add(int(piece))
    bad = [n for n in out if n < 1 or n > total]
    if bad:
        raise ValueError("joint %s doesn't exist: the chain has joints 1 to %d." % (bad[0], total))
    return sorted(n - 1 for n in out)


def spread(count, total):
    """count controls spread evenly over total joints (first and last included): '1, 4, 7'."""
    count = max(1, min(int(count), total))
    if count == 1:
        return "1"
    idx = sorted(set(int(round(i * (total - 1) / float(count - 1))) for i in range(count)))
    return ", ".join(str(i + 1) for i in idx)


def format_joints(indices):
    return ", ".join(str(i + 1) for i in indices)


# ---------------------------------------------------------------------------
# the module
# ---------------------------------------------------------------------------

class Chain(Module):
    TYPE = "chain"
    LABEL = "Chain (tail, ear...)"
    SIDES = ("C", "L", "R")
    ATTACH = ""
    ORIENT = CHAIN_ORIENT
    CONTROLS = {"fk": ["circle", 0.035], "ik": ["cube", 0.03], "tweak": ["sphere", 0.012],
                "settings": ["gear", 0.015]}
    OPTIONS = {"type": "fk", "fk_joints": "all", "ik_joints": "auto", "end_joint": True, "mid_follow": True,
               "twist": True, "tweaks": True, "stretch": True, "volume": False, "curl": False,
               "exact_match": False, "wave": False, "jiggle": False}
    OPTION_LABELS = {
        "type": ("Chain type", "choice", TYPES),
        "fk_joints": ("FK controls on joints", "joints", None),
        "ik_joints": ("IK controls on joints", "joints", None),
        "end_joint": ("End joint (at the tip)", "bool", None),
        "mid_follow": ("Middle IK controls follow the first and last", "bool", None),
        "twist": ("Twist: turning the end IK controls twists the chain", "bool", None),
        "tweaks": ("Tweak control on every joint", "bool", None),
        "stretch": ("IK spline stretch (attribute on the settings control, on at start)", "bool", None),
        "volume": ("Volume: thinner when stretched (IK spline)", "bool", None),
        "curl": ("Curl / curl_side attributes (bend every FK control at once)", "bool", None),
        "wave": ("Wave: wave / wave_up / wave_speed / wave_length on the settings control (a tail that swings "
                 "by itself as time goes; 0 = off)", "bool", None),
        "jiggle": ("Jiggle: follow-through when what it hangs from moves or turns (ears, tail, cape) - jiggle / "
                   "jiggle_stiffness / jiggle_damping / jiggle_bounce / jiggle_limit_body / jiggle_limit_out on the "
                   "settings control; works on playback (every frame), 0 = off", "bool", None),
        "exact_match": ("Exact IK/FK match (tweak controls take what's left)", "bool", None),
    }
    OPTION_GROUPS = [("Chain", ["type", "end_joint"]),
                     ("Controls", ["fk_joints", "ik_joints", "mid_follow", "tweaks", "curl", "wave", "jiggle"]),
                     ("IK", ["twist", "stretch", "volume", "exact_match"])]
    OPTION_NEEDS = {"options.ik_joints": ("options.type", ('fk + ik spline', 'fk + ribbon')), "options.mid_follow": ("options.type", ('fk + ik spline', 'fk + ribbon')),
                    "options.twist": ("options.type", ('fk + ik spline', 'fk + ribbon')), "options.exact_match": ("options.type", ('fk + ik spline', 'fk + ribbon')),
                    "options.stretch": ("options.type", ("fk + ik spline",)),
                    "options.volume": ("options.type", ("fk + ik spline",))}
    DESCRIPTION = ("A free chain (tail, ear, antenna...). FK, or FK + IK spline / ribbon with an IK/FK switch. "
                   "You choose which joints get FK and IK controls; tweak controls, twist, stretch, curl.")

    def default_settings(self, side="C"):
        s = Module.default_settings(self, side)
        if side in ("L", "R"):                       # ears go up: the world up can't be up too
            s["orient"]["world_up"] = [0, 0, 1]
        return s

    def default_names(self):
        return {"name": "", "count": 6, "pattern": "{name}_{num:02d}", "end": "{name}_end"}

    # -- names ------------------------------------------------------------
    def total(self, s):
        return int(s["names"]["count"]) + (1 if s["options"].get("end_joint", True) else 0)

    def base(self, s, module_name=None):
        return s["names"].get("name") or module_name or "chain"

    def parts(self, s, module_name=None):
        n, name = s["names"], self.base(s, module_name)
        out = []
        for i in range(int(n["count"])):
            try:
                out.append(n["pattern"].format(name=name, num=i + 1))
            except (KeyError, IndexError, ValueError):
                out.append("%s_%02d" % (name, i + 1))
        if s["options"].get("end_joint", True):
            try:
                out.append(n["end"].format(name=name))
            except (KeyError, IndexError, ValueError):
                out.append(name + "_end")
        return out

    def has_ik(self, s):
        return s["options"].get("type", "fk") != "fk"

    def fk_indices(self, s):
        return parse_joints(s["options"].get("fk_joints"), self.total(s), "all", int(s["names"]["count"]))

    def ik_indices(self, s):
        idx = parse_joints(s["options"].get("ik_joints"), self.total(s), "auto")
        if len(idx) < 2:
            raise ValueError("an IK chain needs at least 2 IK controls (e.g. 'auto' or '1, %d')." % self.total(s))
        return idx

    # -- guides -----------------------------------------------------------
    def default_line(self, s, h, side):
        total = self.total(s)
        if side == "C":                                  # a tail: back from the hips
            start, d, length = [0, 0.5 * h, -0.06 * h], [0, 0, -1], 0.35 * h
        else:                                            # an ear: up and out from the head
            start, d, length = [0.04 * h, 0.93 * h, 0], mathx.norm([0.35, 1, 0]), 0.09 * h
        step = length / float(max(1, total - 1))
        return [mathx.add(start, mathx.scale(d, step * i)) for i in range(total)]

    def guide_specs(self, s, h, side):
        parts = self.parts(s)
        pts = self.default_line(s, h, "L" if side == "R" else side)
        try:
            ik = set(self.ik_indices(s)) if self.has_ik(s) else set()
        except ValueError:
            ik = set()
        specs = []
        for i, (part, p) in enumerate(zip(parts, pts)):
            spec = {"role": "j%d" % i, "part": part, "pos": p, "parent": "j%d" % (i - 1) if i else None}
            if i in ik:
                spec["kind"] = "pivot"                  # IK control here: drawn as a diamond
                spec["size"] = 1.6
            elif i == len(parts) - 1 and s["options"].get("end_joint", True):
                spec["size"] = 0.7
            specs.append(spec)
        return _mirror_specs(specs, side) if side == "R" else specs

    def preview_names(self, s, side):
        parts = self.parts(s)
        out = [names.make(side, p, "jnt") for p in parts]
        try:
            out += [names.make(side, parts[i], "ctrl", "fk") for i in self.fk_indices(s)]
            if self.has_ik(s):
                out += [names.make(side, parts[i], "ctrl", "ik") for i in self.ik_indices(s)]
        except ValueError:
            pass
        if s["options"].get("tweaks", True):
            out += [names.make(side, p, "ctrl", "tweak") for p in parts]
        return out

    # -- build ------------------------------------------------------------
    def build(self, ctx):
        return build_chain(ctx, self)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def wave_expression(side, label, settings, groups, side_axis, up_axis, nm):
    """The tail swings by itself: each wave group turns on a sine that runs down the chain.
    Attributes on the settings control: wave (degrees side to side), wave_up (degrees up / down),
    wave_speed (waves per second), wave_length (waves along the chain)."""
    controls.separator(settings, "wave")
    amp = controls.add_float(settings, "wave", 0.0)
    amp_up = controls.add_float(settings, "wave_up", 0.0)
    speed = controls.add_float(settings, "wave_speed", 1.0, 0.0)
    length = controls.add_float(settings, "wave_length", 1.0, 0.0)
    short = lambda plug: plug.split("|")[-1]               # expressions want plain names
    amp, amp_up, speed, length = [short(x) for x in (amp, amp_up, speed, length)]
    lines = []
    n = float(max(1, len(groups)))
    for k, g in enumerate(groups):
        phase = "(time * %s * 6.2832 - %g * %s * 6.2832)" % (speed, k / n, length)
        lines.append("%s.rotate%s = %s * sin%s;" % (short(g), side_axis, amp, phase))
        lines.append("%s.rotate%s = %s * sin%s;" % (short(g), up_axis, amp_up, phase))
    return cmds.expression(string="\n".join(lines), name=nm(label + "_wave", "grp").replace("_grp", "_expr"),
                           alwaysEvaluate=False, unitConversion="all")


def jiggle_expression(label, settings, groups, root, side_axis, up_axis, nm):
    """Follow-through: when what the chain hangs from moves (any direction: starts, stops, turns - whatever moves
    it: its control, the chest, the COG, the world), each jiggle group swings the other way and springs back (more
    towards the tip). A spring per group, stepped once per frame while playing; it rests (offsets 0) when you jump
    in time, scrub backwards, or set jiggle to 0. Attributes on the settings control: jiggle (amount, 0 = off),
    jiggle_stiffness, jiggle_damping, jiggle_bounce (how much moving flops it, next to turning),
    jiggle_limit_body / jiggle_limit_out (degrees the whole chain may swing towards the body / away - 5.3.2)."""
    controls.separator(settings, "jiggle")
    plugs = [controls.add_float(settings, "jiggle", 0.0, 0.0, 3.0),
             controls.add_float(settings, "jiggle_stiffness", 0.15, 0.01, 1.0),
             controls.add_float(settings, "jiggle_damping", 0.2, 0.0, 1.0),
             controls.add_float(settings, "jiggle_bounce", 1.0, 0.0, 10.0)]
    for g in groups:
        if not cmds.attributeQuery("gusJiggle", node=g, exists=True):
            cmds.addAttr(g, longName="gusJiggle", attributeType="bool", defaultValue=True)
    return make_jiggle(label, plugs[0].split(".")[0], groups, root, side_axis, up_axis,
                       nm(label + "_jiggle", "grp").replace("_grp", "_expr"))


JIGGLE_TAG = "// Gus_Rigtool jiggle"
JIGGLE_VERSION = "jiggle 5.6.0"
DEG = 57.29578


def _euler_rows(r):
    """The 3 axes (rows) of an XYZ euler rotation in degrees - as the expression works them out."""
    cx, cy, cz = [math.cos(math.radians(a)) for a in r]
    sx, sy, sz = [math.sin(math.radians(a)) for a in r]
    return [[cy * cz, cy * sz, -sy],
            [sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy],
            [cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy]]


def _local(v, rows):
    return [sum(a * b for a, b in zip(v, row)) for row in rows]


def _wpos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)


def _seg_dist(p, a, b):
    ab = [y - x for x, y in zip(a, b)]
    ll = sum(x * x for x in ab) or 1e-12
    t = max(0.0, min(1.0, sum((pp - aa) * d for pp, aa, d in zip(p, a, ab)) / ll))
    q = [aa + d * t for aa, d in zip(a, ab)]
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(p, q)))


def jiggle_geometry(groups, base, dm, side_axis, up_axis):
    """Measured once when the jiggle is made: per axis, which way the chain's tip goes when its groups turn
    (K: tip offset -> degrees), the tip in the base's axes (T), and which way the body is (+1 / -1 / 0 per axis)."""
    try:
        r = list(cmds.getAttr(dm + ".outputRotate")[0])
    except (RuntimeError, ValueError, TypeError, IndexError):
        r = None
    if not r or len(r) != 3:
        r = cmds.xform(base, query=True, worldSpace=True, rotation=True)
    if r and len(r) == 3:
        rows = _euler_rows(r)
    else:                                                    # no euler to read: the matrix's own axes
        m = cmds.xform(base, query=True, worldSpace=True, matrix=True) or []
        rows = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]]
        if len(m) == 16:
            rows = [[x / (math.sqrt(sum(y * y for y in m[k * 4:k * 4 + 3])) or 1.0) for x in m[k * 4:k * 4 + 3]]
                    for k in range(3)]
    bp = _wpos(base)
    tip_node, far = groups[-1], -1.0
    for n in [groups[-1]] + (cmds.listRelatives(groups[-1], allDescendents=True, type="transform", fullPath=True)
                             or []):
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(_wpos(n), bp)))
        if d > far:
            tip_node, far = n, d
    tip = _wpos(tip_node)
    T = _local([a - b for a, b in zip(tip, bp)], rows)
    if math.sqrt(sum(x * x for x in T)) < 1e-6:
        T = [1.0, 0.0, 0.0]
    K, dirs = {}, {}
    for key, ax in (("side", side_axis), ("up", up_axis)):
        plug = "%s.rotate%s" % (groups[0], ax)
        disp = None
        try:
            if cmds.getAttr(plug, settable=True):
                old = cmds.getAttr(plug)
                cmds.setAttr(plug, old + 10.0)
                moved = _wpos(tip_node)
                cmds.setAttr(plug, old)
                disp = [(a - b) / math.radians(10.0) for a, b in zip(moved, tip)]
        except (RuntimeError, ValueError):
            disp = None
        D = _local(disp, rows) if disp else None
        if not D or math.sqrt(sum(x * x for x in D)) < 1e-6 * max(1.0, far):
            u = [0.0, 0.0, 0.0]
            u["XYZ".index(ax)] = 1.0
            D = [u[1] * T[2] - u[2] * T[1], u[2] * T[0] - u[0] * T[2], u[0] * T[1] - u[1] * T[0]]
        n2 = sum(x * x for x in D) or 1.0
        K[key] = [x / n2 for x in D]
        dirs[key] = [x / math.sqrt(n2) for x in D]
    # the body: joints near the chain's middle, not on the chain itself
    L = math.sqrt(sum(x * x for x in T))
    mid = [(a + b) / 2.0 for a, b in zip(bp, tip)]
    mine = set(cmds.ls(groups, long=True) or [])
    for g in groups:
        mine.update(cmds.listRelatives(g, allDescendents=True, fullPath=True) or [])
    near = []
    for j in cmds.ls(type="joint", long=True) or []:
        if j in mine:
            continue
        p = _wpos(j)
        if math.sqrt(sum((a - b) ** 2 for a, b in zip(p, mid))) < 1.5 * L and _seg_dist(p, bp, tip) > 0.2 * L:
            near.append(p)
    body = {"side": 0, "up": 0}
    if near:
        c = [sum(p[k] for p in near) / len(near) for k in range(3)]
        b = _local([a - m for a, m in zip(c, mid)], rows)
        nb = math.sqrt(sum(x * x for x in b))
        if nb > 1e-6:
            b = [x / nb for x in b]
            scores = dict((k, sum(x * y for x, y in zip(b, dirs[k]))) for k in ("side", "up"))
            best = max(scores, key=lambda k: abs(scores[k]))
            if abs(scores[best]) > 0.3:
                body[best] = 1 if scores[best] > 0 else -1
    return K, T, body


def jiggle_text(label, settings, groups, world, side_axis, up_axis, gid, K=None, T=None, body=None):
    """The jiggle expression (5.3.2). Its memory from one frame to the next is a MEL global array: no setAttr,
    so nothing goes on the undo list and Ctrl+Z keeps working. Where the chain hangs from comes in through a
    decomposeMatrix (connections, so a namespace doesn't break it): its movement (speeding up, slowing down, any
    direction) and its turning push the tip the other way, through the springs. Between frames (moving a control,
    painting weights) only the stored offsets are put back - the springs step once per new frame."""
    short = lambda n: n.split("|")[-1]
    s, w = short(settings), short(world)
    K = K or {"side": [0.0, 0.0, 0.0], "up": [0.0, 0.0, 0.0]}
    T = T or [1.0, 0.0, 0.0]
    body = body or {"side": 0, "up": 0}
    amt, stiff, damp, bounce, lim_b, lim_o = ["%s.%s" % (s, a) for a in (
        "jiggle", "jiggle_stiffness", "jiggle_damping", "jiggle_bounce", "jiggle_limit_body", "jiggle_limit_out")]
    n = len(groups)
    g = "$gusJiggle_%s" % gid
    G = 17                                                   # first spring slot
    size = G + 4 * n
    f = lambda v: "%.6g" % v

    def limits(key):
        if body[key] > 0:
            return "-%s" % lim_o, "%s / %d" % (lim_b, n)
        if body[key] < 0:
            return "-%s / %d" % (lim_b, n), lim_o
        return "-%s" % lim_o, lim_o
    lines = ["%s: %s (%s; memory in the MEL global %s: no attribute written, undo stays clean)"
             % (JIGGLE_TAG, label, JIGGLE_VERSION, g),
             "// groups: %s | side %s | up %s | settings %s | body side %d up %d"
             % (" ".join(short(x) for x in groups), side_axis, up_axis, s, body["side"], body["up"]),
             "global float %s[];" % g,
             "float $f = frame;",
             "int $i;",
             "if (size(%s) < %d) { for ($i = 0; $i < %d; $i++) %s[$i] = 0; %s[0] = -1000000000; }"
             % (g, size, size, g, g),
             "if ($f != %s[0]) {" % g,
             "    float $p[] = {%s.outputTranslateX, %s.outputTranslateY, %s.outputTranslateZ};" % (w, w, w),
             "    float $sc = %s.outputScaleX; if ($sc < 0.000001) $sc = 1;" % w,
             "    for ($i = 0; $i < 3; $i++) $p[$i] = $p[$i] / $sc;",
             "    float $r[] = {%s.outputRotateX, %s.outputRotateY, %s.outputRotateZ};" % (w, w, w),
             "    float $cx = cos(deg_to_rad($r[0])); float $sx = sin(deg_to_rad($r[0]));",
             "    float $cy = cos(deg_to_rad($r[1])); float $sy = sin(deg_to_rad($r[1]));",
             "    float $cz = cos(deg_to_rad($r[2])); float $sz = sin(deg_to_rad($r[2]));",
             "    float $m[] = {$cy * $cz, $cy * $sz, -$sy,",
             "                  $sx * $sy * $cz - $cx * $sz, $sx * $sy * $sz + $cx * $cz, $sx * $cy,",
             "                  $cx * $sy * $cz + $sx * $sz, $cx * $sy * $sz - $sx * $cz, $cx * $cy};",
             "    int $rest = (%s == 0 || abs($f - %s[0] - 1) > 0.01);" % (amt, g),
             "    float $v[] = {$p[0] - %s[1], $p[1] - %s[2], $p[2] - %s[3]};" % (g, g, g),
             "    float $a[] = {0, 0, 0};",
             "    float $w[] = {0, 0, 0};",
             "    if ($rest) { for ($i = 0; $i < 3; $i++) $v[$i] = 0; }",
             "    else {",
             "        if (%s[16] > 0.5) { for ($i = 0; $i < 3; $i++) $a[$i] = $v[$i] - %s[4 + $i]; }" % (g, g),
             "        float $q[]; for ($i = 0; $i < 9; $i++) $q[$i] = %s[7 + $i];" % g,
             "        $w[0] = 0.5 * ($m[3]*$q[6] + $m[4]*$q[7] + $m[5]*$q[8] - $m[6]*$q[3] - $m[7]*$q[4] - $m[8]*$q[5]);",
             "        $w[1] = 0.5 * ($m[6]*$q[0] + $m[7]*$q[1] + $m[8]*$q[2] - $m[0]*$q[6] - $m[1]*$q[7] - $m[2]*$q[8]);",
             "        $w[2] = 0.5 * ($m[0]*$q[3] + $m[1]*$q[4] + $m[2]*$q[5] - $m[3]*$q[0] - $m[4]*$q[1] - $m[5]*$q[2]);",
             "    }",
             "    %s[0] = $f; for ($i = 0; $i < 3; $i++) { %s[1 + $i] = $p[$i]; %s[4 + $i] = $v[$i]; }" % (g, g, g),
             "    for ($i = 0; $i < 9; $i++) %s[7 + $i] = $m[$i];" % g,
             "    %s[16] = !$rest;" % g,
             "    float $al[] = {$a[0]*$m[0] + $a[1]*$m[1] + $a[2]*$m[2], $a[0]*$m[3] + $a[1]*$m[4] + $a[2]*$m[5],",
             "                   $a[0]*$m[6] + $a[1]*$m[7] + $a[2]*$m[8]};",
             "    float $T[] = {%s, %s, %s};" % (f(T[0]), f(T[1]), f(T[2])),
             "    float $d[] = {-(%s * $al[0] + $w[1]*$T[2] - $w[2]*$T[1]), -(%s * $al[1] + $w[2]*$T[0] - $w[0]*$T[2]),"
             % (bounce, bounce),
             "                  -(%s * $al[2] + $w[0]*$T[1] - $w[1]*$T[0])};" % bounce,
             "    float $side = %s * %s * ($d[0] * %s + $d[1] * %s + $d[2] * %s);"
             % (amt, f(DEG), f(K["side"][0]), f(K["side"][1]), f(K["side"][2])),
             "    float $up = %s * %s * ($d[0] * %s + $d[1] * %s + $d[2] * %s);"
             % (amt, f(DEG), f(K["up"][0]), f(K["up"][1]), f(K["up"][2])),
             "    float $os; float $vs; float $ou; float $vu; float $nn;"]
    s_lo, s_hi = limits("side")
    u_lo, u_hi = limits("up")
    for k in range(n):
        b = G + 4 * k
        wgt = 2.0 * (k + 1) / (n * (n + 1.0))               # more towards the tip; the whole chain adds up to 1
        lines += ["    $os = %s[%d]; $vs = %s[%d]; $ou = %s[%d]; $vu = %s[%d];" % (g, b, g, b + 1, g, b + 2, g, b + 3),
                  "    if ($rest) { $os = 0; $vs = 0; $ou = 0; $vu = 0; }",
                  "    else {",
                  "        $vs = $vs * (1 - %s) - %s * $os + $side * %g;" % (damp, stiff, wgt),
                  "        $vu = $vu * (1 - %s) - %s * $ou + $up * %g;" % (damp, stiff, wgt),
                  "        $nn = $os + $vs; if ($nn > %s) { $nn = %s; $vs = 0; } if ($nn < %s) { $nn = %s; $vs = 0; }"
                  " $os = $nn;" % (s_hi, s_hi, s_lo, s_lo),
                  "        $nn = $ou + $vu; if ($nn > %s) { $nn = %s; $vu = 0; } if ($nn < %s) { $nn = %s; $vu = 0; }"
                  " $ou = $nn;" % (u_hi, u_hi, u_lo, u_lo),
                  "    }",
                  "    %s[%d] = $os; %s[%d] = $vs; %s[%d] = $ou; %s[%d] = $vu;" % (g, b, g, b + 1, g, b + 2, g, b + 3)]
    lines.append("}")
    for k, grp in enumerate(groups):
        b = G + 4 * k
        lines += ["%s.rotate%s = %s[%d];" % (short(grp), side_axis, g, b),
                  "%s.rotate%s = %s[%d];" % (short(grp), up_axis, g, b + 2)]
    return "\n".join(lines)


def make_jiggle(label, settings, groups, root, side_axis, up_axis, name):
    """The jiggle expression and the decomposeMatrix that brings in where the chain hangs from (the first jiggle
    group's parent - it moves with everything above, never with the jiggle itself). Returns the expression."""
    import random
    controls.add_float(settings, "jiggle_limit_body", 10.0, 0.0, 180.0)
    controls.add_float(settings, "jiggle_limit_out", 90.0, 0.0, 180.0)
    base = (cmds.listRelatives(groups[0], parent=True, fullPath=True) or [root])[0]
    world = cmds.createNode("decomposeMatrix", name=name.replace("_expr", "_root_dm"), skipSelect=True)
    cmds.connectAttr(base + ".worldMatrix[0]", world + ".inputMatrix")
    K, T, body = jiggle_geometry(groups, base, world, side_axis, up_axis)
    gid = "%s_%06x" % ("".join(ch if ch.isalnum() else "_" for ch in label), random.randrange(16 ** 6))
    return cmds.expression(string=jiggle_text(label, settings, groups, world, side_axis, up_axis, gid, K, T, body),
                           name=name, alwaysEvaluate=False, unitConversion="all")


def _jiggle_exprs():
    out = []
    for e in cmds.ls(type="expression") or []:
        try:
            text = cmds.expression(e, query=True, string=True) or ""
        except RuntimeError:
            continue
        if JIGGLE_TAG in text:
            out.append((e, text))
    return out


def old_jiggles():
    """Jiggle expressions made before 5.0.10 (they write their memory with setAttr: undo stops working)."""
    return [e for e, text in _jiggle_exprs() if "setAttr" in text]


def outdated_jiggles():
    """Jiggle expressions from 5.0.10 - 5.3.1: they don't react to moving sideways / forward, no body limit."""
    return [e for e, text in _jiggle_exprs() if "setAttr" not in text and JIGGLE_VERSION not in text]


def jiggles():
    return [e for e, _t in _jiggle_exprs()]


def motion_exprs():
    """Jiggle and wave expressions (5.3.3)."""
    out = []
    for e in cmds.ls(type="expression") or []:
        try:
            text = cmds.expression(e, query=True, string=True) or ""
        except RuntimeError:
            continue
        if JIGGLE_TAG in text or e.endswith("_wave_expr") or e.endswith("_jiggle_expr"):
            out.append(e)
    return out


def always_evaluating():
    """Jiggle / wave expressions made with 'always evaluate' on (before 5.3.3): they rewrite their groups on every
    evaluation, so a skin on those joints never settles (ngSkinTools hung on the Hare's hood)."""
    out = []
    for e in motion_exprs():
        try:
            if cmds.expression(e, query=True, alwaysEvaluate=True):
                out.append(e)
        except (RuntimeError, TypeError):
            pass
    return out


def _driven_plugs(expr):
    """The channels an expression drives (through Maya's unitConversion nodes)."""
    out = []
    for p in cmds.listConnections(expr, source=False, destination=True, plugs=True) or []:
        node = p.split(".")[0]
        if cmds.nodeType(node) == "unitConversion":
            out += cmds.listConnections(node + ".output", source=False, destination=True, plugs=True) or []
        else:
            out.append(p)
    return out


def stop_always_evaluating(exprs=None):
    """'Always evaluate' off. Maya only offers it through the expression command, which compiles the expression
    again and reconnects what it drives - that failed on a locked channel (the Hare's Tongue_01_wave_grp.rotateY,
    5.3.3) and left the expression broken. 5.3.4: locked channels it drives are unlocked for the edit and locked
    again after."""
    exprs = always_evaluating() if exprs is None else exprs
    for e in exprs:
        locked = []
        for p in _driven_plugs(e):
            try:
                if cmds.getAttr(p, lock=True):
                    cmds.setAttr(p, lock=False)
                    locked.append(p)
            except (RuntimeError, ValueError):
                pass
        try:
            cmds.expression(e, edit=True, alwaysEvaluate=False)
        finally:
            for p in locked:
                try:
                    cmds.setAttr(p, lock=True)
                except (RuntimeError, ValueError):
                    pass
    return len(exprs)


def paused():
    return [e for e in motion_exprs() if cmds.getAttr(e + ".nodeState") == 2]


def pause_motion(pause=True):
    """Every jiggle / wave off (nodeState blocking) while you skin, or back on. Returns how many."""
    exprs = motion_exprs()
    for e in exprs:
        cmds.setAttr(e + ".nodeState", 2 if pause else 0)
    return len(exprs)


def remake_jiggle(expr):
    """Rewrite a jiggle expression the current way (any older one): same groups, axes and settings attributes;
    an old state node / decomposeMatrix is deleted. Returns the new expression."""
    import re
    text = cmds.expression(expr, query=True, string=True)
    label = re.search(r"jiggle: (.+?) \(", text).group(1)
    head = re.search(r"// groups: (.+?) \| side ([XYZ]) \| up ([XYZ]) \| settings (\S+)", text)
    old_dm = [d for d in cmds.listConnections(expr, source=True, destination=False, type="decomposeMatrix") or []]
    root = None
    if head:
        groups = head.group(1).split()
        side_ax, up_ax, sett = head.group(2), head.group(3), head.group(4)
    else:
        side = re.findall(r"([^\s;]+)\.rotate([XYZ]) = \$os;", text)
        up = re.findall(r"([^\s;]+)\.rotate([XYZ]) = \$ou;", text)
        if not side:                                         # 5.0.10: grp.rotateY = $gusJiggle_..[b];
            pairs = re.findall(r"([^\s;]+)\.rotate([XYZ]) = \$gusJiggle_\w+\[(\d+)\];", text)
            side = [(gname, a) for gname, a, _b in pairs[0::2]]
            up = [(gname, a) for gname, a, _b in pairs[1::2]]
        if not side or not up:
            raise RuntimeError("%s: can't read its groups." % expr)
        groups = [grp for grp, _a in side]
        side_ax, up_ax = side[0][1], up[0][1]
        amt = re.search(r"int \$rest = \(([^ ]+) == 0", text).group(1)
        sett = amt.split(".")[0]
        m = re.search(r"xform -q -ws -t ([^`\s]+)`", text)
        root = m.group(1) if m else None
    state = re.search(r"state on ([^\s,)]+)", text)
    name = expr.split("|")[-1]
    cmds.delete(expr)
    for d in old_dm:
        if cmds.objExists(d):
            cmds.delete(d)
    if state and cmds.objExists(state.group(1)):
        cmds.delete(state.group(1))
    return make_jiggle(label, sett, groups, root, side_ax, up_ax, name)


def _third(aim, up):
    return [a for a in "XYZ" if a not in (aim, up)][0]


def _short(nodes):
    return [x.split("|")[-1] for x in nodes]


def _signed_axis(m, direction):
    """The matrix axis ('X', '-Y'...) that points most along direction."""
    best, out = -2.0, "X"
    for a in "XYZ":
        d = mathx.dot(mathx.axis_of(m, a), mathx.norm(direction))
        for sign, name in ((1.0, a), (-1.0, "-" + a)):
            if d * sign > best:
                best, out = d * sign, name
    return out


def build_chain(ctx, mod):
    s, o, side = ctx.settings, ctx.settings["options"], ctx.side
    label = mod.base(s, ctx.info["name"])
    parts = mod.parts(s, ctx.info["name"])
    total = len(parts)
    if total < 2:
        raise RuntimeError("%s: a chain needs at least 2 joints." % label)
    mats = ctx.chain(["j%d" % i for i in range(total)])
    has_ik = mod.has_ik(s)
    kind = o.get("type", "fk")
    fk_idx = mod.fk_indices(s)
    ik_idx = mod.ik_indices(s) if has_ik else []
    face = ctx.aim_face()
    aim, up = ctx.orient["aim"].lstrip("-"), ctx.orient["up"].lstrip("-")
    third = _third(aim, up)
    sn = names.settings()
    nm = lambda part, kind_, variant=None: names.make(side, part, kind_, variant, sn)

    bind = limb.joint_chain(side, parts, mats, ctx.attach_joint or ctx.skeleton, None, ctx.radius)
    out = {"joints": dict(zip(parts, bind)), "spaces": {}, "follow": bind[-1]}

    # helper chains follow what the chain hangs from
    chains = controls.group(nm(label + "_chains", "grp"), ctx.nodes)
    follow = ctx.attach_joint or ctx.module_ctrls
    cmds.parentConstraint(follow, chains, maintainOffset=True)
    cmds.scaleConstraint(follow, chains, maintainOffset=True)

    # settings control, next to the last joint
    settings = None
    if has_ik or o.get("tweaks", True) or o.get("curl") or o.get("wave") or o.get("jiggle"):
        end_m = mats[-1]
        up_dir = mathx.axis_of(end_m, ctx.orient["up"])
        if side == "R" and ctx.orient.get("behavior_right", True):
            up_dir = mathx.scale(up_dir, -1.0)
        s_pos = mathx.add(mathx.position(end_m), mathx.scale(up_dir, ctx.height * 0.04))
        s_off, settings = controls.make(side, label, ctx.shape("settings"), ctx.size("settings"),
                                        mathx.translate_matrix(s_pos), ctx.module_ctrls, "Z", "settings",
                                        lock=("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"))
        cmds.parentConstraint(bind[-1], s_off, maintainOffset=True)
        controls.separator(settings, "chain")
        out["settings_ctrl"] = settings
    blend = controls.add_float(settings, "ikfk", 0.0, 0.0, 1.0) if has_ik else None

    # what the bind joints follow: the tweak controls, else the result directly
    tweaks = []
    if o.get("tweaks", True):
        target = limb.joint_chain(side, parts, mats, chains, "result", ctx.radius * 0.5)
        limb.hide([target[0]])
    else:
        target = bind

    # FK
    fk_src = limb.joint_chain(side, parts, mats, chains, "fk", ctx.radius * 0.7) if has_ik else target
    if has_ik:
        limb.hide([fk_src[0]])
    fk_offs, fk_ctrls, fk_rest = [], [], []
    under = ctx.module_ctrls
    if o.get("curl") and settings:
        curl = controls.add_float(settings, "curl", 0.0)
        curl_side = controls.add_float(settings, "curl_side", 0.0)
    waves, jiggles = [], []
    for k, i in enumerate(fk_idx):
        off, c = controls.make(side, parts[i], ctx.shape("fk"), ctx.size("fk"), mats[i], under, face, "fk")
        if o.get("curl") and settings:
            cg = controls.group(nm(parts[i] + "_curl", "grp"), off, limb.world(off))
            c = cmds.ls(cmds.parent(c, cg)[0], long=True)[0]
            cmds.connectAttr(curl, cg + ".rotate" + third)
            cmds.connectAttr(curl_side, cg + ".rotate" + up)
        if o.get("wave") and settings:
            wg = controls.group(nm(parts[i] + "_wave", "grp"), cmds.listRelatives(c, parent=True, fullPath=True)[0],
                                limb.world(off))
            c = cmds.ls(cmds.parent(c, wg)[0], long=True)[0]
            waves.append(wg)
        if o.get("jiggle") and settings:
            jg = controls.group(nm(parts[i] + "_jiggle", "grp"), cmds.listRelatives(c, parent=True, fullPath=True)[0],
                                limb.world(off))
            c = cmds.ls(cmds.parent(c, jg)[0], long=True)[0]
            jiggles.append(jg)
        if fk_ctrls:                                   # 'length' on the control above moves this one
            prev = fk_ctrls[-1]
            length = controls.add_float(prev, "length", 1.0, 0.01)
            t0 = cmds.getAttr(off + ".translate")[0]
            md = cmds.createNode("multiplyDivide", name=nm(parts[i] + "_length", "grp").replace("_grp", "_md"))
            cmds.setAttr(md + ".input1", *t0)
            for a in "XYZ":
                cmds.connectAttr(length, md + ".input2" + a)
            cmds.connectAttr(md + ".output", off + ".translate")
            fk_rest.append(mathx.distance(mathx.position(mats[fk_idx[k - 1]]), mathx.position(mats[i])))
        cmds.parentConstraint(c, fk_src[i], maintainOffset=False)
        fk_offs.append(off)
        fk_ctrls.append(c)
        under = c
    if waves:
        wave_expression(side, label, settings, waves, up, third, nm)
    if jiggles:
        root = cmds.listRelatives(fk_offs[0], parent=True, fullPath=True)[0] if fk_offs else ctx.module_ctrls
        jiggle_expression(label, settings, jiggles, root, up, third, nm)

    # IK
    ik_ctrls, ikj, ik_grp = [], [], None
    if has_ik:
        ik_grp = controls.group(nm(label + "_ik", "grp"), ctx.module_ctrls)
        ik_offs = []
        for i in ik_idx:
            off, c = controls.make(side, parts[i], ctx.shape("ik"), ctx.size("ik"), mats[i], ik_grp, face, "ik")
            ik_offs.append(off)
            ik_ctrls.append(c)
        if o.get("mid_follow", True) and len(ik_ctrls) > 2:
            pos = [mathx.position(m) for m in mats]
            along = [0.0]
            for a, b in zip(pos[:-1], pos[1:]):
                along.append(along[-1] + mathx.distance(a, b))
            a0, a1 = along[ik_idx[0]], along[ik_idx[-1]]
            for k in range(1, len(ik_ctrls) - 1):
                t = (along[ik_idx[k]] - a0) / ((a1 - a0) or 1.0)
                fol = controls.group(nm(parts[ik_idx[k]] + "_ikFollow", "grp"), ik_grp)
                for con in (cmds.pointConstraint, cmds.orientConstraint):
                    con(ik_ctrls[0], fol, weight=1.0 - t)
                    c2 = con(ik_ctrls[-1], fol, weight=t)
                if cmds.nodeType(c2[0]) == "orientConstraint":
                    cmds.setAttr(c2[0] + ".interpType", 2)
                ik_offs[k] = cmds.ls(cmds.parent(ik_offs[k], fol)[0], long=True)[0]
                ik_ctrls[k] = cmds.listRelatives(ik_offs[k], children=True, type="transform", fullPath=True)[0]

        drv = ribbons.drivers(side, label, [mats[i] for i in ik_idx], ["ik%d" % (k + 1) for k in range(len(ik_idx))],
                              ctx.nodes, ctx.radius * 0.5)
        limb.hide(drv)
        for c, d in zip(ik_ctrls, drv):
            if kind == "fk + ribbon" and not o.get("twist", True):
                cmds.pointConstraint(c, d, maintainOffset=True)
                cmds.orientConstraint(c, d, maintainOffset=True, skip=aim.lower())
            else:
                cmds.parentConstraint(c, d, maintainOffset=True)
        pts = [mathx.position(m) for m in mats]

        if kind == "fk + ribbon":
            ikj = limb.joint_chain(side, parts, mats, chains, "ik", ctx.radius * 0.7, chain=False)
            limb.hide(ikj)
            srf = ribbons.strip(side, label + "_ribbon", pts, [mathx.axis_of(m, third) for m in mats],
                                ctx.height * 0.03, ctx.nodes)
            ribbons.skin(srf, drv)
            fols = controls.group(nm(label + "_ribbonFol", "grp"), ctx.nodes)
            for j, part, p in zip(ikj, parts, pts):
                u, v = ribbons.closest_uv(srf, p)
                fol = ribbons.follicle(side, part + "_rib", srf, u, v, fols)
                cmds.parentConstraint(fol, j, maintainOffset=True)
        else:
            ikj = limb.joint_chain(side, parts, mats, chains, "ik", ctx.radius * 0.7)
            limb.hide([ikj[0]])
            crv = cmds.curve(degree=3 if total >= 3 else 1, editPoint=[tuple(p) for p in pts], name=nm(label, "crv"))
            crv = cmds.ls(cmds.parent(crv, ctx.nodes)[0], long=True)[0]
            cmds.setAttr(crv + ".visibility", 0)
            ribbons.skin_curve(crv, drv, nm(label + "_crv", "grp").replace("_grp", "_skin"))
            h, eff = cmds.ikHandle(startJoint=ikj[0], endEffector=ikj[-1], solver="ikSplineSolver", curve=crv,
                                   createCurve=False, parentCurve=False, name=nm(label, "ik"))
            cmds.rename(eff, nm(label, "ik") + "_eff")
            h = cmds.ls(cmds.parent(h, ctx.nodes)[0], long=True)[0]
            cmds.setAttr(h + ".visibility", 0)
            if o.get("twist", True):
                fwd = _signed_axis(mats[0], mathx.sub(pts[1], pts[0]))
                cmds.setAttr(h + ".dTwistControlEnable", 1)
                cmds.setAttr(h + ".dWorldUpType", 4)                  # object rotation up (start / end)
                cmds.setAttr(h + ".dForwardAxis", {"X": 0, "-X": 1, "Y": 2, "-Y": 3, "Z": 4, "-Z": 5}[fwd])
                cmds.setAttr(h + ".dWorldUpAxis", {"Y": 0, "Z": 3, "X": 6}[up])
                vec = mathx.AXIS_VECTORS[up]
                cmds.setAttr(h + ".dWorldUpVector", *vec)
                cmds.setAttr(h + ".dWorldUpVectorEnd", *vec)
                cmds.connectAttr(drv[0] + ".worldMatrix[0]", h + ".dWorldUpMatrix")
                cmds.connectAttr(drv[-1] + ".worldMatrix[0]", h + ".dWorldUpMatrixEnd")
            _spline_stretch(ctx, side, label, crv, ikj, bind, settings, blend, aim, up, third, o, pts, nm)

        limb.blend(side, target, fk_src, ikj, blend)
        limb.visibility_switch(side, label, blend, fk_offs[:1], [ik_grp])

    # tweaks: the bind joints follow them; they follow the result
    if o.get("tweaks", True):
        tw_grp = controls.group(nm(label + "_tweaks", "grp"), ctx.module_ctrls)
        for i, part in enumerate(parts):
            off, c = controls.make(side, part, ctx.shape("tweak"), ctx.size("tweak"), mats[i], tw_grp, face,
                                   "tweak")
            cmds.parentConstraint(target[i], off, maintainOffset=False)
            cmds.parentConstraint(c, bind[i], maintainOffset=False)
            tweaks.append(c)
        vis = controls.add_bool(settings, "tweaks", True)
        cmds.connectAttr(vis, tw_grp + ".visibility")

    if settings:
        limb.store_meta(settings, gusChain="1", gusBlend="ikfk" if has_ik else "",
                        gusFkCtrls=_short(fk_ctrls), gusFkJoints=_short([fk_src[i] for i in fk_idx]),
                        gusFkRest=[repr(r) for r in fk_rest],
                        gusIkCtrls=_short(ik_ctrls), gusIkIdx=[str(i) for i in ik_idx],
                        gusIkJoints=_short([ikj[i] for i in fk_idx]) if ikj else [],
                        gusIkJointsAtCtrls=_short([ikj[i] for i in ik_idx]) if ikj else [],
                        gusFkJointsAtCtrls=_short([fk_src[i] for i in ik_idx]) if has_ik else [],
                        gusTweaks=_short(tweaks), gusBind=_short(bind),
                        gusExact="1" if o.get("exact_match") else "0",
                        gusScalePlug=ctx.scale_plug or "")
    return out


def _spline_stretch(ctx, side, label, crv, ikj, bind, settings, blend, aim, up, third, o, pts, nm):
    """IK spline: the joints grow with the curve (stretch on / off), and thin out (volume)."""
    on = controls.add_bool(settings, "stretch", bool(o.get("stretch", True)))
    shape = cmds.listRelatives(crv, shapes=True, fullPath=True)[0]
    info = cmds.createNode("curveInfo", name=nm(label + "_crvInfo", "grp").replace("_grp", ""))
    cmds.connectAttr(shape + ".worldSpace[0]", info + ".inputCurve")
    rest = sum(mathx.distance(a, b) for a, b in zip(pts[:-1], pts[1:]))
    try:
        measured = cmds.getAttr(info + ".arcLength")
        if measured and measured > 1e-6:
            rest = measured
    except (RuntimeError, ValueError, TypeError):
        pass
    restm = cmds.createNode("multDoubleLinear", name=nm(label + "_stretchRest", "grp").replace("_grp", ""))
    cmds.setAttr(restm + ".input1", rest)
    if ctx.scale_plug:
        cmds.connectAttr(ctx.scale_plug, restm + ".input2")
    else:
        cmds.setAttr(restm + ".input2", 1.0)
    ratio = cmds.createNode("multiplyDivide", name=nm(label + "_stretchRatio", "grp").replace("_grp", ""))
    cmds.setAttr(ratio + ".operation", 2)
    cmds.connectAttr(info + ".arcLength", ratio + ".input1X")
    cmds.connectAttr(restm + ".output", ratio + ".input2X")
    onoff = cmds.createNode("blendTwoAttr", name=nm(label + "_stretchOnOff", "grp").replace("_grp", ""))
    cmds.setAttr(onoff + ".input[0]", 1.0)
    cmds.connectAttr(ratio + ".outputX", onoff + ".input[1]")
    cmds.connectAttr(on, onoff + ".attributesBlender")
    for j in ikj[1:]:
        plug = "%s.translate%s" % (j, aim)
        mul = cmds.createNode("multDoubleLinear", name=nm(j.split("|")[-1] + "_stretch", "grp").replace("_grp", ""))
        cmds.setAttr(mul + ".input1", cmds.getAttr(plug))
        cmds.connectAttr(onoff + ".output", mul + ".input2")
        cmds.connectAttr(mul + ".output", plug)
    if o.get("volume"):
        vol = controls.add_float(settings, "volume", 1.0, 0.0, 1.0)
        pw = cmds.createNode("multiplyDivide", name=nm(label + "_volumePow", "grp").replace("_grp", ""))
        cmds.setAttr(pw + ".operation", 3)
        cmds.connectAttr(onoff + ".output", pw + ".input1X")
        cmds.setAttr(pw + ".input2X", -0.5)
        amount = cmds.createNode("multDoubleLinear", name=nm(label + "_volumeAmount", "grp").replace("_grp", ""))
        cmds.connectAttr(vol, amount + ".input1")
        cmds.connectAttr(blend, amount + ".input2")              # only in IK
        bl = cmds.createNode("blendTwoAttr", name=nm(label + "_volume", "grp").replace("_grp", ""))
        cmds.setAttr(bl + ".input[0]", 1.0)
        cmds.connectAttr(pw + ".outputX", bl + ".input[1]")
        cmds.connectAttr(amount + ".output", bl + ".attributesBlender")
        for j in bind:
            for a in (up, third):
                cmds.connectAttr(bl + ".output", "%s.scale%s" % (j, a))


# ---------------------------------------------------------------------------
# guides from the selection or a curve
# ---------------------------------------------------------------------------

def positions_from_selection(nodes):
    return [cmds.xform(n, query=True, worldSpace=True, translation=True) for n in nodes]


def positions_from_curve(crv, count):
    """count points spread evenly by length along a curve (ends included)."""
    shapes = cmds.listRelatives(crv, shapes=True, type="nurbsCurve", fullPath=True) or []
    if not shapes:
        raise RuntimeError("select a curve.")
    samples = [cmds.pointOnCurve(shapes[0], parameter=i / 200.0, turnOnPercentage=True, position=True)
               for i in range(201)]
    along = [0.0]
    for a, b in zip(samples[:-1], samples[1:]):
        along.append(along[-1] + mathx.distance(a, b))
    out, k = [], 0
    for i in range(count):
        want = along[-1] * i / float(max(1, count - 1))
        while k < len(along) - 2 and along[k + 1] < want:
            k += 1
        seg = (along[k + 1] - along[k]) or 1.0
        out.append(mathx.lerp(samples[k], samples[k + 1], min(1.0, max(0.0, (want - along[k]) / seg))))
    return out


# ---------------------------------------------------------------------------
# IK / FK matching
# ---------------------------------------------------------------------------

def _meta(s, key):
    return limb._meta(s, key)


def _bind_worlds(s):
    return [limb.world(b) for b in _meta(s, "gusBind") if cmds.objExists(b)]


def _exact(s, before):
    tw = _meta(s, "gusTweaks")
    if controls.get_string(s, "gusExact") != "1" or not tw or len(tw) != len(before):
        return
    for c, m in zip(tw, before):
        limb.set_world(c, m)


def _global_scale(s):
    plug = controls.get_string(s, "gusScalePlug")
    try:
        return float(cmds.getAttr(plug)) if plug and cmds.objExists(plug) else 1.0
    except (RuntimeError, ValueError):
        return 1.0


def match_to_fk(s):
    """FK controls take the IK pose (lengths too), then the chain switches to FK."""
    before = _bind_worlds(s)
    ctrls, ikj = _meta(s, "gusFkCtrls"), _meta(s, "gusIkJoints")
    rest = [float(r) for r in _meta(s, "gusFkRest")]
    gs = _global_scale(s)
    for k in range(len(ctrls) - 1):                       # lengths first (they move the controls below)
        if k < len(rest) and cmds.attributeQuery("length", node=ctrls[k], exists=True) and rest[k] > 1e-9:
            d = mathx.distance(mathx.position(limb.world(ikj[k])), mathx.position(limb.world(ikj[k + 1])))
            cmds.setAttr(ctrls[k] + ".length", d / (rest[k] * gs))
    for c, j in zip(ctrls, ikj):
        limb.set_world(c, limb.world(j), translate=False)
    cmds.setAttr(s + ".ikfk", 0)
    _exact(s, before)


def match_to_ik(s):
    """IK controls take the FK pose (ends first, then the middle ones), then the chain switches to IK."""
    before = _bind_worlds(s)
    ctrls, fkj = _meta(s, "gusIkCtrls"), _meta(s, "gusFkJointsAtCtrls")
    order = [0, len(ctrls) - 1] + list(range(1, len(ctrls) - 1)) if len(ctrls) > 1 else [0]
    for k in order:
        if k < len(fkj):
            limb.set_world(ctrls[k], limb.world(fkj[k]))
    cmds.setAttr(s + ".ikfk", 1)
    _exact(s, before)
