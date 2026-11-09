"""
Utility node networks (5.0.9): the nodes a control drives through multiplyDivide, clamp, unitConversion...
and constraints - read them, name them, select them.

    from gus_rigtool.core import networks as NW
    NW.read(["L_Brow_02_ctrl"])        # {'utils': [...], 'cons': [...], 'driven': [...]}
    NW.plan()                          # [(old name, new name)] for utility nodes still called multiplyDivide13...
    NW.rename(NW.plan())               # one undo

Names say what feeds the node and what it ends up driving: L_Brow_02_ty_to_fol_11_sdk_md
(control, channel, target, kind). Nodes you named yourself, nodes in a referenced file and nodes with nothing in
or nothing out are left alone.
"""

import re

import maya.cmds as cmds

from gus_rigtool.core import mirror_setup as MS
from gus_rigtool.core import naming

UTILITY = MS.UTILITY
CONSTRAINTS = MS.CONSTRAINTS
ABBR = dict(MS.ABBR, floatMath="fm", multiply="mult", sum="sum", subtract="sub", divide="div",
            clampRange="clamp", remapColor="remapc")
SHORT = {"translate": "t", "rotate": "r", "scale": "s", "visibility": "v"}
for _a in ("translate", "rotate", "scale"):
    for _x in "XYZ":
        SHORT[_a + _x] = SHORT[_a] + _x.lower()
JUNK = ("_ctrl", "_Ctrl", "_CTRL", "_jnt", "_JNT", "_offset", "_grp", "_GRP")


def _short(n):
    return naming.short_name(n)


def _bare(n):
    return _short(n).split(":")[-1]


def _referenced(n):
    try:
        return bool(cmds.referenceQuery(n, isNodeReferenced=True))
    except (RuntimeError, ValueError):
        return False


def is_default_name(n):
    """multiplyDivide13, unitConversion260, clamp1: Maya's type + number."""
    return bool(re.match(r"^%s\d*$" % re.escape(cmds.nodeType(n)), _bare(n)))


def _attr_short(node, attr):
    a = attr.split("[")[0].split(".")[-1]
    if a in SHORT:
        return SHORT[a]
    try:
        return cmds.attributeQuery(a, node=node, shortName=True)
    except (RuntimeError, ValueError, TypeError):
        return a


def source_of(node, _seen=None):
    """(the first real node feeding node - through other utility nodes -, its channel), or None."""
    seen = _seen if _seen is not None else {node}
    for _dst, snode, sattr in MS._plugs_in(node):
        if snode in seen:
            continue
        seen.add(snode)
        if MS._is_util(snode):
            got = source_of(snode, seen)
            if got:
                return got
        elif not MS._is_con(snode):
            return snode, _attr_short(snode, sattr)
    return None


def target_of(node, _seen=None):
    """What node finally drives: the node a constraint moves, or the first real node. None if nothing."""
    seen = _seen if _seen is not None else {node}
    for _sattr, dnode, _dattr in MS._plugs_out(node):
        if dnode in seen:
            continue
        seen.add(dnode)
        if MS._is_util(dnode):
            got = target_of(dnode, seen)
            if got:
                return got
        elif MS._is_con(dnode):
            return MS._driven_of(dnode)
        else:
            return dnode
    return None


def _core(n):
    """(side, core): 'L_Facial_ribbon_fol_11_ctrl_sdk' -> ('L', 'fol_11_ctrl_sdk'); 'Brows_ctrl' -> ('', 'Brows')."""
    from gus_rigtool.core import joint_labels
    base = _bare(n)
    base = re.sub(r"_(%s)\d*$" % "|".join(CONSTRAINTS), "", base)
    side, rest = joint_labels.split_side(base)
    side = "" if side == "C" else side
    for junk in JUNK:
        if rest.endswith(junk) and len(rest) > len(junk):
            rest = rest[:-len(junk)]
    rest = rest.replace("Facial_ribbon_", "")
    return side, rest


def compose(src, attr, dst, kind):
    """The name for a utility node of type kind, fed by src.attr, ending at dst."""
    s1, a = _core(src)
    s2, b = _core(dst)
    left = (s1 + "_" if s1 else "") + a + ("_" + attr if attr else "")
    right = (s2 + "_" if s2 and s2 != s1 else "") + b
    return "%s_to_%s_%s" % (left, right, ABBR.get(kind, kind))


def name_for(node):
    """The name node should have, or None (nothing in / nothing out)."""
    src, dst = source_of(node), target_of(node)
    if not src or not dst:
        return None
    return compose(src[0], src[1], dst, cmds.nodeType(node))


def candidates(nodes=None):
    """Utility nodes still called by their type + number (not referenced). nodes: only these (else the scene)."""
    pool = nodes if nodes is not None else (cmds.ls(type=list(UTILITY)) or [])
    out = []
    for n in pool:
        if cmds.objExists(n) and cmds.nodeType(n) in UTILITY and is_default_name(n) and not _referenced(n):
            out.append(n)
    return out


def plan(nodes=None):
    """[(old, new)] for the candidates that can be named; names are unique (in the scene and in the plan)."""
    taken, out = set(), []
    for n in sorted(candidates(nodes)):
        want = name_for(n)
        if not want:
            continue
        new, i = want, 2
        while new in taken or (cmds.objExists(new) and _bare(new) != _bare(n)):
            new, i = "%s%d" % (want, i), i + 1
        taken.add(new)
        out.append((n, new))
    return out


def rename(pairs):
    """Rename [(old, new)] in one undo. Returns [(old, new as named)]."""
    done = []
    cmds.undoInfo(openChunk=True, chunkName="gusrigNameUtilities")
    try:
        for old, new in pairs:
            if cmds.objExists(old):
                done.append((old, cmds.rename(old, new)))
    finally:
        cmds.undoInfo(closeChunk=True)
    return done


def read(nodes):
    """The network starting at nodes: {'utils': utility nodes, 'cons': constraints, 'driven': what the
    constraints / last utility nodes move}, each in the order found."""
    out = {"utils": [], "cons": [], "driven": []}
    seen = set()
    todo = [n for n in (nodes or []) if cmds.objExists(n)]
    while todo:
        n = todo.pop(0)
        for _sattr, dnode, _dattr in MS._plugs_out(n):
            if dnode in seen:
                continue
            if MS._is_util(dnode):
                seen.add(dnode)
                out["utils"].append(dnode)
                todo.append(dnode)
            elif MS._is_con(dnode):
                seen.add(dnode)
                out["cons"].append(dnode)
                d = MS._driven_of(dnode)
                if d and d not in out["driven"]:
                    out["driven"].append(d)
            elif n not in (nodes or []) and dnode not in out["driven"]:
                out["driven"].append(dnode)              # a utility node's output straight into a node
    return out


# ---------------------------------------------------------------------------------------------------------------
# 5.1.0: trace a channel, compare sides, at rest, loops
# ---------------------------------------------------------------------------------------------------------------

_SKIP_ATTR = ("message",)


def _fmt(v):
    if isinstance(v, (list, tuple)):
        if len(v) == 1 and isinstance(v[0], (list, tuple)):
            v = v[0]
        return "(" + ", ".join(_fmt(x) for x in v) + ")"
    if isinstance(v, float):
        return ("%.4f" % v).rstrip("0").rstrip(".") or "0"
    return str(v)


def _get(plug):
    try:
        return cmds.getAttr(plug)
    except (RuntimeError, ValueError, TypeError):
        return None


MD_OPS = ["no operation", "multiply", "divide", "power"]
PMA_OPS = ["no operation", "sum", "subtract", "average"]
COND_OPS = ["==", "!=", ">", ">=", "<", "<="]


def describe(node):
    """The values that matter on a utility / driver node, in a few words."""
    t = cmds.nodeType(node)
    g = lambda a: _get(node + "." + a)
    try:
        if t == "multiplyDivide":
            op = g("operation")
            op = MD_OPS[int(1 if op is None else op)]
            return "%s by %s" % (op, _fmt([g("input2" + x) for x in "XYZ"]))
        if t == "clamp":
            return "clamp %s .. %s" % (_fmt([g("min" + x) for x in "RGB"]), _fmt([g("max" + x) for x in "RGB"]))
        if t == "unitConversion":
            return "x %s" % _fmt(g("conversionFactor"))
        if t == "plusMinusAverage":
            return PMA_OPS[int(g("operation") or 0)]
        if t == "condition":
            return "if first %s %s" % (COND_OPS[int(g("operation") or 0)], _fmt(g("secondTerm")))
        if t == "setRange":
            return "%s..%s -> %s..%s" % (_fmt(g("oldMin")), _fmt(g("oldMax")), _fmt(g("min")), _fmt(g("max")))
        if t == "remapValue":
            return "%s..%s -> %s..%s" % (_fmt(g("inputMin")), _fmt(g("inputMax")), _fmt(g("outputMin")),
                                          _fmt(g("outputMax")))
        if t in ("multDoubleLinear", "addDoubleLinear"):
            return "%s %s" % ("x" if t == "multDoubleLinear" else "+", _fmt(g("input2")))
        if t == "blendColors":
            return "blend %s" % _fmt(g("blender"))
        if t == "reverse":
            return "1 - x"
        if t.startswith("animCurveU"):
            n = cmds.keyframe(node, query=True, keyframeCount=True) or 0
            return "set driven key, %d key(s)" % n
        if t.startswith("animCurveT"):
            return "animation keys"
        if t == "expression":
            return "expression"
    except (RuntimeError, ValueError, TypeError, IndexError):
        pass
    return t


def _con_targets(con):
    """[(target, weight)] of a constraint."""
    fn = getattr(cmds, cmds.nodeType(con), None)
    out = []
    try:
        targets = fn(con, query=True, targetList=True) or []
        aliases = fn(con, query=True, weightAliasList=True) or []
    except (RuntimeError, TypeError):
        return out
    for i, t in enumerate(targets):
        w = _get(con + "." + aliases[i]) if i < len(aliases) else None
        out.append((t, w))
    return out


def _incoming(plug):
    """The plug feeding plug (also through its compound parent: rotate for rotateX), or None."""
    node, attr = plug.split(".", 1)
    for p in (plug, node + "." + re.sub(r"[XYZ]$", "", attr)):
        try:
            src = cmds.listConnections(p, source=True, destination=False, plugs=True,
                                       skipConversionNodes=False) or []
        except (RuntimeError, ValueError):
            src = []
        if src:
            return src[0]
    return None


def trace(plug, depth=0, seen=None, out=None, limit=40):
    """What drives plug, back to the controls: [(depth, line, node)]. A tree, deepest first-found."""
    seen = set() if seen is None else seen
    out = [] if out is None else out
    src = _incoming(plug)
    if not src:
        if depth == 0:
            out.append((0, "%s: nothing drives it (value %s)" % (_short(plug), _fmt(_get(plug))), plug.split(".")[0]))
        return out
    node = src.split(".", 1)[0]
    kind = cmds.nodeType(node)
    line = "%s <- %s.%s  [%s]" % (plug.split(".", 1)[1], _short(node), src.split(".", 1)[1], describe(node))
    out.append((depth, line, node))
    if node in seen or len(out) > limit:
        if node in seen:
            out.append((depth + 1, "(seen above)", node))
        return out
    seen.add(node)
    if kind in CONSTRAINTS:
        for t, w in _con_targets(node):
            out.append((depth + 1, "target %s  weight %s" % (_short(t), _fmt(w)), t))
        for _dst, snode, sattr in MS._plugs_in(node):           # targets fed by utility nodes (the brow's x0.8)
            if MS._is_util(snode) or cmds.nodeType(snode).startswith("animCurveU"):
                trace("%s.%s" % (node, _dst), depth + 1, seen, out, limit)
    elif MS._is_util(node) or kind.startswith("animCurveU") or kind in ("blendWeighted", "pairBlend"):
        for dst, _snode, _sattr in MS._plugs_in(node):
            trace("%s.%s" % (node, dst), depth + 1, seen, out, limit)
    return out


def trace_text(plug):
    rows = trace(plug)
    return "\n".join("  " * d + line for d, line, _n in rows)


# ---- compare sides -----------------------------------------------------------------------------------------------

def _signature(ctrl):
    """{key: values} of the network a control drives. key: (kind, channel, target without its side); a node
    fed by another control keys under that control."""
    out = {}
    net = read([ctrl])
    for u in net["utils"]:
        src, dst = source_of(u), target_of(u)
        if not src:
            continue
        _s, a = _core(src[0])
        _s2, b = _core(dst) if dst else ("", "-")
        key = (cmds.nodeType(u), a, src[1], b)
        i = 2
        while key in out:
            key = key[:3] + ("%s #%d" % (b, i),)
            i += 1
        out[key] = (u, describe(u))
    for c in net["cons"]:
        d = MS._driven_of(c)
        _s, b = _core(d) if d else ("", "-")
        ws = tuple(sorted((_core(t)[1], round(w, 4) if isinstance(w, float) else w) for t, w in _con_targets(c)))
        out[(cmds.nodeType(c), "", "", b)] = (c, "weights %s" % ", ".join("%s %s" % (t, _fmt(w)) for t, w in ws))
    return out


def compare_sides(controls):
    """[(control, twin, what differs)] between each control's network and its twin's."""
    rows = []
    for c in controls:
        twin = MS.twin(c) if hasattr(MS, "twin") else None
        if not twin:
            rows.append((c, None, "no twin found"))
            continue
        a, b = _signature(c), _signature(twin)
        for k in sorted(set(a) | set(b), key=str):
            what = "%s %s%s -> %s" % (k[0], k[1], ("." + k[2]) if k[2] else "", k[3])
            if k not in b:
                rows.append((c, twin, "only on %s: %s (%s)%s" % (_short(c), what, a[k][1], _fed_instead(a[k][0],
                                                                                                         twin))))
            elif k not in a:
                rows.append((c, twin, "only on %s: %s (%s)" % (_short(twin), what, b[k][1])))
            elif a[k][1] != b[k][1]:
                rows.append((c, twin, "%s: %s vs %s" % (what, a[k][1], b[k][1])))
    return rows


def _fed_instead(node, twin_ctrl):
    """' - R_Brow_04_sdk is fed by R_Brow_02_ctrl instead' when the twin's target is driven by another control."""
    dst = target_of(node) if MS._is_util(node) else MS._driven_of(node)
    tdst = MS.twin(dst) if dst else None
    if not tdst:
        return ""
    who = set()
    for _d, snode, _a in MS._plugs_in(tdst):
        if MS._is_util(snode):
            src = source_of(snode)
            if src:
                who.add(_short(src[0]))
    who.discard(_short(twin_ctrl))
    return (" - %s is fed by %s instead" % (_short(tdst), ", ".join(sorted(who)))) if who else ""


def compare_text(controls):
    rows = compare_sides(controls)
    if not rows:
        return "The two sides match: same nodes, same values."
    return "\n".join("%s / %s:  %s" % (_short(c), _short(t) if t else "-", w) for c, t, w in rows)


# ---- at rest -------------------------------------------------------------------------------------------------------

REST = {"translate": 0.0, "rotate": 0.0, "scale": 1.0}


def at_rest(controls):
    """With the controls at rest: channels a network fed by a control's translate / rotate moves that aren't at their
    rest value (0 for translate / rotate, 1 for scale) - an offset left in (a plusMinusAverage with a constant,
    a condition's other value...).
    [(plug, value, rest, the control pulling it)]. Controls not at rest are skipped (returned as (ctrl, None...))."""
    busy = [c for c in controls if not MS._at_rest(c)]
    out = [(c, None, None, "not at rest") for c in busy]
    net = read([c for c in controls if c not in busy])
    seen = set()
    moves = set(["t", "r"] + [a + x for a in "tr" for x in "xyz"])
    for u in net["utils"]:
        src = source_of(u)
        if not src or src[1] not in moves:
            continue                    # fed by a custom attribute (length, follow...): its rest value is the design
        for sattr, dnode, dattr in MS._plugs_out(u):
            base = re.sub(r"[XYZ]$", "", dattr.split("[")[0])
            if base not in REST or MS._is_util(dnode) or MS._is_con(dnode):
                continue
            plug = "%s.%s" % (dnode, dattr)
            if plug in seen:
                continue
            seen.add(plug)
            v = _get(plug)
            vals = v[0] if isinstance(v, list) and v and isinstance(v[0], tuple) else (v if isinstance(v, (list, tuple))
                                                                                      else [v])
            if any(x is not None and abs(x - REST[base]) > 1e-4 for x in vals):
                out.append((plug, v, REST[base], _short(src[0])))
    return out


# ---- loops ---------------------------------------------------------------------------------------------------------

LOOP_TYPES = ("transform", "joint", "follicle", "decomposeMatrix", "multMatrix", "composeMatrix", "blendMatrix",
              "pickMatrix", "aimMatrix", "uvPin", "proximityPin", "pointOnSurfaceInfo", "closestPointOnSurface",
              "pointOnCurveInfo", "motionPath", "skinCluster", "blendShape", "mesh", "nurbsSurface", "expression",
              "blendWeighted", "pairBlend")


CYCLE_SEP = "--gusCycle--"


def loops():
    """Groups of nodes that really feed each other in a circle, as Maya sees them (5.1.1: Maya's own cycleCheck,
    which knows which attributes depend on which - a control's 'space' attribute driving its parent group is not a
    loop). [[node, ...]]. Without cycleCheck: a node-level look (rougher)."""
    fn = getattr(cmds, "cycleCheck", None)
    if fn is not None:
        try:
            plugs = fn(all=True, list=True, listSeparator=CYCLE_SEP, firstPlugPerNode=True, timeLimit=20) or []
        except (RuntimeError, TypeError):
            plugs = None
        if plugs is not None:
            if isinstance(plugs, bool):
                return []
            out, cur = [], []
            for p in list(plugs) + [CYCLE_SEP]:
                if p == CYCLE_SEP:
                    if cur:
                        out.append(cur)
                    cur = []
                    continue
                n = (cmds.ls(p.split(".", 1)[0], long=True) or [p.split(".", 1)[0]])[0]
                if n not in cur:
                    cur.append(n)
            return [g for g in out if g]
    return _graph_loops()


def _graph_loops():
    """Groups of nodes that feed each other in a circle, node by node (no cycleCheck)."""
    kinds = set(LOOP_TYPES) | set(UTILITY) | set(CONSTRAINTS)
    nodes = []
    for k in sorted(kinds) + ["animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT"]:
        try:
            nodes += cmds.ls(type=k, long=True) or []
        except (RuntimeError, ValueError, TypeError):      # a type this Maya doesn't have
            pass
    nodes = list(dict.fromkeys(nodes))
    names = set(nodes)
    edges = dict((n, set()) for n in nodes)
    driven_by = {}
    for n in nodes:
        if MS._is_con(n):
            d = MS._driven_of(n)
            driven_by[n] = (cmds.ls(d, long=True) or [d])[0] if d else None
    for n in nodes:
        try:
            pairs = cmds.listConnections(n, source=True, destination=False, plugs=True, connections=True,
                                         skipConversionNodes=False) or []
        except (RuntimeError, ValueError):
            continue
        for i in range(0, len(pairs) - 1, 2):
            dst, src = pairs[i], pairs[i + 1]
            dattr = dst.split(".", 1)[1]
            if dattr.split("[")[0] in _SKIP_ATTR or src.endswith(".message"):
                continue
            s = (cmds.ls(src.split(".", 1)[0], long=True) or [None])[0]
            if MS._is_con(n) and (dattr.startswith("constraint") or s == driven_by.get(n)):
                continue                                # the constrained node's own inputs: not a loop
            if s in names and s != n:
                edges[s].add(n)
        kids = cmds.listRelatives(n, children=True, fullPath=True) or []
        for k in kids:
            if k in names and cmds.nodeType(k) in ("transform", "joint"):
                edges[n].add(k)
    # strongly connected groups (iterative Tarjan)
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(edges[start]))]
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on.add(start)
        while work:
            v, it = work[-1]
            nxt = next(it, None)
            if nxt is not None:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on.add(nxt)
                    work.append((nxt, iter(edges[nxt])))
                elif nxt in on:
                    low[v] = min(low[v], index[nxt])
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    out.append(comp)
    return out
