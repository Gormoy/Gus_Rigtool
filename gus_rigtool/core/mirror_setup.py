"""
Mirror a setup (5.0.3): copy what you built by hand on one side - constraints, utility nodes (multiplyDivide,
unitConversion, plusMinusAverage, condition...), and the groups / controls they need - onto the other side.

    from gus_rigtool.core import mirror_setup as MS
    print(MS.preview(["L_Brow_01_ctrl", ...]))       # what it will do
    MS.run(["L_Brow_01_ctrl", ...])                   # one undo

How it reads the setup, from the selected nodes:
  - every utility node their outputs reach (through other utility nodes), and every constraint those - or the
    selected nodes - feed: that's the network;
  - the nodes those constraints drive.
Then on the other side:
  1. nodes that don't exist there yet (an _sdk group, an extra control) are made: same type, mirrored place,
     a control's shape mirrored and its colour taken from the other side; children that already exist there
     are moved under them (nothing moves in the world);
  2. the constraints are made on the twins (twin targets, same weights, same skipped axes, maintain offset at
     rest) - a twin's old constraint of the same kind is replaced;
  3. the utility nodes are copied with their values and wired like the originals, side for side.
Twins by name (L_ <-> R_ and your side pairs); a node with no side is used as it is. Running it again replaces
the copies it made before (they're tagged), it never doubles them. The controls must be at rest.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import nodes as _nodes

TAG = "gusMirrorOf"
UTILITY = ("multiplyDivide", "unitConversion", "plusMinusAverage", "condition", "reverse", "remapValue",
           "blendColors", "clamp", "setRange", "multDoubleLinear", "addDoubleLinear", "blendTwoAttr",
           "distanceBetween", "floatMath", "multiply", "sum", "subtract", "divide", "clampRange", "remapColor")
CONSTRAINTS = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint",
               "poleVectorConstraint")
ABBR = {"multiplyDivide": "md", "unitConversion": "uc", "plusMinusAverage": "pma", "condition": "cond",
        "reverse": "rev", "remapValue": "remap", "blendColors": "blend", "clamp": "clamp", "setRange": "range",
        "multDoubleLinear": "mdl", "addDoubleLinear": "adl", "blendTwoAttr": "b2a", "distanceBetween": "dist"}
_SKIP_DST = ("defaultRenderUtilityList", "MayaNodeEditorSavedTabsInfo", "nodeGraphEditorInfo")

_long = _nodes.unique_long


def twin_name(node):
    """The other side's name (whether it exists or not), or None for a node with no side."""
    from gus_rigtool.core import joint_labels
    return joint_labels.twin_name(naming.short_name(node))


def twin(node):
    name = twin_name(node)
    return _long(name) if name else None


def _short(n):
    return naming.short_name(n)


def _type(n):
    return cmds.nodeType(n)


def _is_util(n):
    return _type(n) in UTILITY


def _is_con(n):
    return _type(n) in CONSTRAINTS


def _plugs_out(node):
    """[(src attr, dst node, dst attr)] - real connections only (no node-editor bookkeeping)."""
    out = []
    got = cmds.listConnections(node, source=False, destination=True, plugs=True, connections=True,
                               skipConversionNodes=False) or []
    for i in range(0, len(got) - 1, 2):
        src, dst = got[i], got[i + 1]
        dnode, dattr = dst.split(".", 1)
        if any(k in dnode for k in _SKIP_DST) or src.endswith(".message"):
            continue
        out.append((src.split(".", 1)[1], _long(dnode) or dnode, dattr))
    return out


def _plugs_in(node):
    """[(dst attr on node, src node, src attr)]."""
    out = []
    got = cmds.listConnections(node, source=True, destination=False, plugs=True, connections=True,
                               skipConversionNodes=False) or []
    for i in range(0, len(got) - 1, 2):
        dst, src = got[i], got[i + 1]
        snode, sattr = src.split(".", 1)
        out.append((dst.split(".", 1)[1], _long(snode) or snode, sattr))
    return out


def _driven_of(con):
    """The node a constraint drives."""
    for _sa, dnode, dattr in _plugs_out(con):
        if not _is_con(dnode) and dattr.split("[")[0] in ("translate", "rotate", "scale", "tx", "ty", "tz",
                                                          "rx", "ry", "rz", "sx", "sy", "sz", "translateX",
                                                          "translateY", "translateZ", "rotateX", "rotateY",
                                                          "rotateZ", "scaleX", "scaleY", "scaleZ"):
            return dnode
    parent = cmds.listRelatives(con, parent=True, fullPath=True)
    return parent[0] if parent else None


# ---------------------------------------------------------------------------
# reading the setup
# ---------------------------------------------------------------------------

class Setup(object):
    def __init__(self):
        self.seeds = []          # the selected nodes (one side)
        self.utils = []          # utility nodes, in the order found
        self.cons = []           # constraints
        self.driven = []         # what the constraints drive
        self.missing = []        # nodes the other side needs that don't exist yet (parents first)
        self.problems = []
        self.unused = []         # utility nodes that feed nothing (left out)


def read(nodes):
    """The setup that starts at nodes (see the module's notes). Returns a Setup. Controls found under a group
    the other side is missing (an extra control you added) start their own part of the setup too."""
    seeds = [x for x in (_long(n) for n in nodes) if x]
    s = _read_once(seeds)
    for _i in range(4):
        more = [m for m in s.missing if m not in seeds and cmds.listRelatives(m, shapes=True, type="nurbsCurve")]
        for d in s.driven:                                   # controls an earlier run made (tagged): again too
            for kid in cmds.listRelatives(d, allDescendents=True, type="transform", fullPath=True) or []:
                t = twin(kid)
                if t and t != kid and kid not in seeds and kid not in more and \
                        cmds.attributeQuery(TAG, node=t, exists=True) and \
                        cmds.listRelatives(kid, shapes=True, type="nurbsCurve"):
                    more.append(kid)
        if not more:
            break
        seeds += more
        s = _read_once(seeds)
    s.seeds = [x for x in (_long(n) for n in nodes) if x]
    return s


def _read_once(nodes):
    s = Setup()
    seeds = [x for x in (_long(n) for n in nodes) if x]
    s.seeds = list(seeds)
    queue = list(seeds)
    seen = set(queue)
    while queue:
        n = queue.pop(0)
        for _sa, dnode, _da in _plugs_out(n):
            if dnode in seen or not cmds.objExists(dnode):
                continue
            if _is_util(dnode):
                seen.add(dnode)
                s.utils.append(dnode)
                queue.append(dnode)
            elif _is_con(dnode):
                seen.add(dnode)
                s.cons.append(dnode)
    # a constraint the seeds don't reach directly but whose driven node is a seed (it drives the control)
    for n in seeds:
        for c in cmds.listRelatives(n, children=True, fullPath=True, type="constraint") or []:
            if c not in s.cons and _is_con(c):
                s.cons.append(c)
    # utility nodes that don't lead to a constraint (left-overs) aren't copied
    feeds = {}
    for u in s.utils:
        feeds[u] = [d for _a, d, _da in _plugs_out(u)]
    useful = set()
    changed = True
    while changed:
        changed = False
        for u, outs in feeds.items():
            if u not in useful and any(o in s.cons or o in useful for o in outs):
                useful.add(u)
                changed = True
    s.unused = [u for u in s.utils if u not in useful]
    s.utils = [u for u in s.utils if u in useful]
    for c in s.cons:
        d = _driven_of(c)
        if d and d not in s.driven:
            s.driven.append(d)
    # what the other side needs that isn't there: driven nodes and, above them, their parents
    for d in s.driven:
        chain = []
        n = d
        while n and twin_name(n) and not twin(n):
            chain.append(n)
            n = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
        for x in reversed(chain):
            if x not in s.missing:
                s.missing.append(x)
        if not twin_name(d):
            s.problems.append("%s has no side in its name: it can't be mirrored" % _short(d))
    # controls under a missing group come too (an extra control you added), with their own setups
    more = []
    for m in list(s.missing):
        for kid in cmds.listRelatives(m, allDescendents=True, type="transform", fullPath=True) or []:
            if twin_name(kid) and not twin(kid) and kid not in s.missing and kid not in more \
                    and not _is_con(kid):
                more.append(kid)
    for k in sorted(more, key=lambda x: x.count("|")):
        s.missing.append(k)
    return s


def _at_rest(n):
    for a, v in (("translate", 0.0), ("rotate", 0.0), ("scale", 1.0)):
        try:
            if any(abs(x - v) > 1e-4 for x in cmds.getAttr(n + "." + a)[0]):
                return False
        except (RuntimeError, ValueError, TypeError, IndexError):
            continue
    return True


def _controls_of(s):
    """Every control (a transform with a curve) the setup reads from, on both sides."""
    out = []
    for c in s.cons:
        fn = getattr(cmds, _type(c))
        for t in fn(c, query=True, targetList=True) or []:
            for x in (_long(t), twin(t)):
                if x and x not in out and cmds.listRelatives(x, shapes=True, type="nurbsCurve"):
                    out.append(x)
    for n in s.seeds:
        if n not in out and cmds.listRelatives(n, shapes=True, type="nurbsCurve"):
            out.append(n)
    return out


def preview(nodes):
    """What run() will do, as text."""
    s = read(nodes)
    lines = []
    if s.missing:
        lines.append("Make on the other side (they don't exist yet):")
        lines += ["   %s  (%s)" % (twin_name(m), _type(m)) for m in s.missing]
    if s.cons:
        lines.append("Constraints (%d):" % len(s.cons))
        for c in s.cons:
            d = _driven_of(c)
            t = twin(d) if d else None
            old = [x for x in (cmds.listRelatives(t, children=True, type=_type(c), fullPath=True) or [])] if t else []
            lines.append("   %s on %s%s" % (_type(c), twin_name(d) if d else "?",
                                            "  (replaces its %s)" % _type(c) if old else ""))
    if s.utils:
        kinds = {}
        for u in s.utils:
            kinds[_type(u)] = kinds.get(_type(u), 0) + 1
        lines.append("Utility nodes copied: %s" % ", ".join("%d %s" % (v, k) for k, v in sorted(kinds.items())))
    busy = [c for c in _controls_of(s) if not _at_rest(c)]
    if busy:
        lines.append("Put these at rest first (0 / 0 / 1): %s" % ", ".join(_short(b) for b in busy[:8]))
    if s.unused:
        lines.append("Left out (they don't feed anything): %s" % ", ".join(_short(u) for u in s.unused[:8]))
    lines += ["Note: " + p for p in s.problems]
    return "\n".join(lines) or "Nothing to mirror: select the controls (or nodes) your setup starts from."


# ---------------------------------------------------------------------------
# making it on the other side
# ---------------------------------------------------------------------------

def _style_and_plane(pairs):
    """('true' | 'behavior', axis, centre): the mirror that best matches nodes that already have twins."""
    from gus_rigtool.core import mirror_engine as ME
    axis, centre = ME.plane()
    best, score = "true", None
    for style in ("true", "behavior"):
        err = 0.0
        for a, b in pairs[:6]:
            m = ME.mirror_list(cmds.xform(a, query=True, worldSpace=True, matrix=True), style, axis, centre)
            have = cmds.xform(b, query=True, worldSpace=True, matrix=True)
            err += sum(abs(x - y) for x, y in zip(m[:12], have[:12]))
        if score is None or err < score:
            best, score = style, err
    return best, axis, centre


def _ref_pairs(nodes):
    """Existing (node, twin) pairs near these nodes: their parents and siblings."""
    out = []
    for n in nodes:
        p = n
        while p and len(out) < 6:
            p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
            if p and twin(p) and twin(p) != p:
                for kid in cmds.listRelatives(p, children=True, type="transform", fullPath=True) or []:
                    if twin(kid) and twin(kid) != kid and (kid, twin(kid)) not in out:
                        out.append((kid, twin(kid)))
                        if len(out) >= 6:
                            break
                break
    return out


def _copy_colour(src_shape, dst_shape):
    for a in ("overrideEnabled", "overrideRGBColors", "overrideColor"):
        try:
            cmds.setAttr(dst_shape + "." + a, cmds.getAttr(src_shape + "." + a))
        except (RuntimeError, ValueError, TypeError):
            pass
    try:
        cmds.setAttr(dst_shape + ".overrideColorRGB", *cmds.getAttr(src_shape + ".overrideColorRGB")[0])
    except (RuntimeError, ValueError, TypeError, IndexError):
        pass


def _cv_points(shape):
    """World positions of a curve's points ([] if they can't be read)."""
    try:
        return [cmds.xform(cv, query=True, worldSpace=True, translation=True)
                for cv in cmds.ls(shape + ".cv[*]", flatten=True) or []]
    except (RuntimeError, ValueError):
        return []


def _make_twin(src, style, axis, centre, colour_from):
    """The other side's copy of src (a group or a control): mirrored place, mirrored curves, under the twin of
    its parent. Twins already there among src's children are moved under it (they don't move)."""
    from gus_rigtool.core import mirror_engine as ME
    name = twin_name(src)
    parent = (cmds.listRelatives(src, parent=True, fullPath=True) or [None])[0]
    t_parent = (twin(parent) or parent) if parent else None
    kind = _type(src)
    new = cmds.createNode(kind, name=name, parent=t_parent, skipSelect=True) if t_parent else \
        cmds.createNode(kind, name=name, skipSelect=True)
    new = _long(new) or new
    m = ME.mirror_list(cmds.xform(src, query=True, worldSpace=True, matrix=True), style, axis, centre)
    cmds.xform(new, worldSpace=True, matrix=m)
    for flag in ("rotatePivot", "scalePivot"):                # a pivot moved off the node (a control at 0 whose
        p = cmds.xform(src, query=True, worldSpace=True, **{flag: True})       # pivot sits on the face)
        cmds.xform(new, worldSpace=True, **{flag: ME.reflect_point(p, axis, centre)})
    curves = [sh for sh in cmds.listRelatives(src, shapes=True, fullPath=True, noIntermediate=True) or []
              if _type(sh) == "nurbsCurve"]
    if curves:                                              # a control: its curves, mirrored in the world
        worlds = [_cv_points(sh) for sh in curves]
        dup = cmds.duplicate(src, returnRootsOnly=True)[0]
        dup_shapes = cmds.listRelatives(dup, shapes=True, fullPath=True, type="nurbsCurve") or []
        for i, sh in enumerate(dup_shapes):
            got = cmds.parent(sh, new, shape=True, relative=True)
            moved = cmds.ls(got[0], long=True)[0] if got else (cmds.listRelatives(new, shapes=True,
                                                                                    fullPath=True) or [])[-1]
            pts = worlds[i] if i < len(worlds) else []
            if pts:
                for cv, p in zip(cmds.ls(moved + ".cv[*]", flatten=True) or [], pts):
                    cmds.xform(cv, worldSpace=True, translation=ME.reflect_point(p, axis, centre))
            moved = cmds.rename(moved, _short(new) + ("Shape" if i == 0 else "Shape%d" % i))
            if colour_from:
                _copy_colour(colour_from, moved)
        if cmds.objExists(dup):
            cmds.delete(dup)
    # its children that already exist on the other side go under it, staying where they are
    for kid in cmds.listRelatives(src, children=True, type="transform", fullPath=True) or []:
        tk = twin(kid)
        if tk and (cmds.listRelatives(tk, parent=True, fullPath=True) or [None])[0] != new:
            cmds.parent(tk, new)
    cmds.addAttr(new, longName=TAG, dataType="string")
    cmds.setAttr(new + "." + TAG, _short(src), type="string")
    return _long(name) or new


def _old_copies(src_names):
    """Nodes an earlier run made from these sources (by their tag)."""
    out = []
    for n in cmds.ls("*." + TAG, objectsOnly=True, long=True) or []:
        try:
            if cmds.getAttr(n + "." + TAG) in src_names:
                out.append(n)
        except RuntimeError:
            continue
    return out


def _copy_values(src, dst):
    for a in cmds.listAttr(src, settable=True, scalar=True, multi=True) or []:
        if a in ("caching", "frozen", "isHistoricallyInteresting", "nodeState", "binMembership"):
            continue
        plug = src + "." + a
        try:
            if cmds.listConnections(plug, source=True, destination=False):
                continue
            v = cmds.getAttr(plug)
            if isinstance(v, (list, tuple)):
                continue
            cmds.setAttr(dst + "." + a, v)
        except (RuntimeError, ValueError, TypeError):
            continue


def _side_free(name):
    """'R_Brow_01_ctrl' -> ('R', 'Brow_01'): the side token and a short core."""
    pre, _, rest = name.partition("_")
    if not rest:
        return "", name
    for junk in ("Facial_ribbon_", "_ctrl", "_sdk", "_jnt", "_offset"):
        rest = rest.replace(junk, "")
    return pre, rest


def _util_name(u, twin_of):
    """'R_Brow_01_ty_to_fol_11_md': from what feeds it (and the channel) to what it ends up driving, on the
    copy's side - the same names as Nodes > 'Name utility nodes' (5.0.9)."""
    from gus_rigtool.core import networks
    src, dst = networks.source_of(u), networks.target_of(u)
    if src and dst:
        return networks.compose(twin_of(src[0]) or src[0], src[1], twin_of(dst) or dst, _type(u))
    return twin_name(u) or "%s_mirrored_%s" % (_short(u), ABBR.get(_type(u), _type(u)))


def run(nodes, replace=True):
    """Mirror the setup that starts at nodes onto the other side, in one undo. Returns a summary (lines)."""
    from gus_rigtool.core import ribbon
    s = read(nodes)
    if not s.cons and not s.utils:
        raise RuntimeError("no constraints or utility nodes start from the selection: select the controls (or "
                           "nodes) your setup starts from.")
    busy = [c for c in _controls_of(s) if not _at_rest(c)]
    if busy:
        raise RuntimeError("put the controls at rest first (translate 0, rotate 0, scale 1): %s"
                           % ", ".join(_short(b) for b in busy[:8]))
    summary = []
    with utils.undo_chunk("gusrigMirrorSetup"):
        # earlier copies of this network go first (never doubled)
        old = _old_copies([_short(x) for x in s.utils + s.cons])
        if old:
            cmds.delete([o for o in old if cmds.objExists(o)])
        # 1. what the other side doesn't have yet
        style, axis, centre = _style_and_plane(_ref_pairs(s.missing or s.driven) or
                                               [(x, twin(x)) for x in s.seeds if twin(x)])
        made = []
        for m in s.missing:
            if twin(m):
                continue
            colour = None
            for sib in cmds.listRelatives(cmds.listRelatives(m, parent=True, fullPath=True) or [], children=True,
                                          type="transform", fullPath=True) or []:
                ts = twin(sib)
                sh = cmds.listRelatives(ts, shapes=True, type="nurbsCurve", fullPath=True) if ts else None
                if sh:
                    colour = sh[0]
                    break
            if not colour:                                   # a control's own twin side colour: any twin control
                for a, b in _ref_pairs([m]):
                    sh = cmds.listRelatives(b, shapes=True, type="nurbsCurve", fullPath=True)
                    if sh:
                        colour = sh[0]
                        break
            made.append(_make_twin(m, style, axis, centre, colour))
        if made:
            summary.append("made %d node(s) on the other side: %s" % (len(made), ", ".join(_short(x) for x in made)))
        # 2. the utility nodes (made first, so constraints can be wired to them)
        copies = {}

        def twin_of(n):
            if n in copies:
                return copies[n]
            return twin(n) or (n if not twin_name(n) else None)
        for u in s.utils:
            new = cmds.createNode(_type(u), name=_util_name(u, twin_of), skipSelect=True)
            _copy_values(u, new)
            cmds.addAttr(new, longName=TAG, dataType="string")
            cmds.setAttr(new + "." + TAG, _short(u), type="string")
            copies[u] = new
        # 3. the constraints, on the twins
        n_cons = 0
        for c in s.cons:
            kind = _type(c)
            fn = getattr(cmds, kind)
            d = _driven_of(c)
            td = twin_of(d) if d else None
            targets = [_long(t) or t for t in fn(c, query=True, targetList=True) or []]
            ttargets = [twin_of(t) for t in targets]
            if not td or not all(ttargets):
                s.problems.append("%s on %s: a target or the driven node has no twin" % (kind, _short(d or c)))
                continue
            if replace:
                old_c = cmds.listRelatives(td, children=True, type=kind, fullPath=True) or []
                if old_c:
                    cmds.delete(old_c)
            weights = [cmds.getAttr(c + "." + a) for a in fn(c, query=True, weightAliasList=True) or []]
            flags = ribbon._skip_flags(c, kind) if kind in ribbon.SKIP_PLUGS else {}
            new = fn(ttargets, td, maintainOffset=True, **flags)[0]
            for alias, w in zip(fn(new, query=True, weightAliasList=True) or [], weights):
                cmds.setAttr(new + "." + alias, w)
            try:
                cmds.setAttr(new + ".interpType", cmds.getAttr(c + ".interpType"))
            except (RuntimeError, ValueError):
                pass
            cmds.addAttr(new, longName=TAG, dataType="string")
            cmds.setAttr(new + "." + TAG, _short(c), type="string")
            copies[c] = new
            n_cons += 1
        # 4. wire the copies like the originals, side for side
        n_links = 0
        for u in s.utils + s.cons:
            if u not in copies:
                continue
            for dattr, snode, sattr in _plugs_in(u):
                if _is_con(u) and not _is_util(snode):
                    continue                                 # a constraint's own inputs: made by the command
                src = copies.get(snode) or twin_of(snode)
                if not src:
                    continue
                if _is_con(u):                               # a target input fed by a utility: same target
                    dattr = _retarget(u, copies[u], dattr)
                    if not dattr:
                        continue
                try:
                    cmds.connectAttr("%s.%s" % (src, sattr), "%s.%s" % (copies[u], dattr), force=True)
                    n_links += 1
                except RuntimeError:
                    pass
        summary.append("%d constraint(s), %d utility node(s), %d connection(s) mirrored (%s mirror)"
                       % (n_cons, len(s.utils), n_links, style))
    if s.problems:
        summary += ["skipped: " + p for p in s.problems]
    utils.info("Mirror", "; ".join(summary) + ".")
    return summary


def _retarget(old_con, new_con, dattr):
    """'tg[2].tt' on the original -> the same input of the twin target on the copy."""
    if not dattr.startswith("tg[") and not dattr.startswith("target["):
        return dattr
    idx = int(dattr.split("[", 1)[1].split("]", 1)[0])
    rest = dattr.split("]", 1)[1]
    kind = _type(old_con)
    fn = getattr(cmds, kind)
    old_t = fn(old_con, query=True, targetList=True) or []
    if idx >= len(old_t):
        return None
    want = twin(old_t[idx]) or _long(old_t[idx])
    new_t = [_long(t) or t for t in fn(new_con, query=True, targetList=True) or []]
    if want not in new_t:
        return None
    return "%s[%d]%s" % (dattr.split("[", 1)[0], new_t.index(want), rest)
