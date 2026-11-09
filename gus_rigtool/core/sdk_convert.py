"""
Network <-> set driven key (5.2.1).

    from gus_rigtool.core import sdk_convert as SC
    SC.to_sdk("L_Brow_02_sdk.rotateX")      # the clamp / multiply chain -> a set driven key with the same result
    SC.to_nodes("L_Brow_02_sdk.rotateX")    # a straight-line (or one-sided) set driven key -> clamp / multiply

to_sdk reads what the chain gives by moving its driver over a range (Maya does the maths), keeps the corners as
keys (linear), and replaces the chain - so it can be shaped in the Graph Editor. to_nodes works for a key curve that
is straight, or straight on one side and flat on the other (like the brow: nothing down, -4 per unit up); a curved
one is left as it is, with the reason.
"""

import maya.cmds as cmds

from gus_rigtool.core import mirror_setup as MS
from gus_rigtool.core import networks

BIG = 1.0e5
UCURVES = ("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT")


def _short(n):
    return networks._short(n)


def _chain(plug):
    """(driver plug, [utility nodes between]) for a channel fed by utility nodes; (None, []) if not."""
    src = networks._incoming(plug)
    if not src:
        return None, []
    nodes, todo, driver = [], [src.split(".", 1)[0]], None
    while todo:
        n = todo.pop(0)
        if n in nodes:
            continue
        if not MS._is_util(n):
            continue
        nodes.append(n)
        for _dst, snode, sattr in MS._plugs_in(n):
            if MS._is_util(snode):
                todo.append(snode)
            elif driver is None and not MS._is_con(snode) and cmds.nodeType(snode) not in UCURVES:
                driver = "%s.%s" % (snode, sattr)
    return driver, nodes


def _limits(nodes):
    """The finite clamp limits in a chain (corners to sample at)."""
    out = []
    for n in nodes:
        if cmds.nodeType(n) != "clamp":
            continue
        for a in ("minR", "maxR", "minG", "maxG", "minB", "maxB"):
            v = networks._get(n + "." + a)
            if isinstance(v, (int, float)) and abs(v) < BIG:
                out.append(float(v))
    return out


def _sample(driver, target, xs):
    """[(x, value)]: the driver set to each x, the target read (the driver put back; nothing on the undo list)."""
    old = cmds.getAttr(driver)
    undo = cmds.undoInfo(query=True, state=True)
    out = []
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        for x in xs:
            cmds.setAttr(driver, x)
            out.append((x, cmds.getAttr(target)))
    finally:
        cmds.setAttr(driver, old)
        cmds.undoInfo(stateWithoutFlush=undo)
    return out


def _corners(samples, tol=1e-6):
    """Keep the ends and the points where the slope changes."""
    keep = [samples[0]]
    for i in range(1, len(samples) - 1):
        (x0, y0), (x1, y1), (x2, y2) = samples[i - 1], samples[i], samples[i + 1]
        s1 = (y1 - y0) / ((x1 - x0) or 1e-12)
        s2 = (y2 - y1) / ((x2 - x1) or 1e-12)
        if abs(s1 - s2) > tol * max(1.0, abs(s1), abs(s2)):
            keep.append(samples[i])
    keep.append(samples[-1])
    return keep


def plan_sdk(target):
    """(driver plug, chain nodes, keys [(x, y)], pre / post infinity) or raises with the reason."""
    driver, nodes = _chain(target)
    if not driver or not nodes:
        raise RuntimeError("%s isn't driven by utility nodes from a control." % _short(target))
    lims = _limits(nodes)
    reach = max([1.0] + [abs(v) for v in lims])
    xs = sorted(set([round(-reach + 2 * reach * i / 20.0, 9) for i in range(21)] + [0.0] + lims))
    samples = _sample(driver, target, xs)
    keys = _corners(samples)
    first = (samples[1][1] - samples[0][1]) / ((samples[1][0] - samples[0][0]) or 1e-12)
    last = (samples[-1][1] - samples[-2][1]) / ((samples[-1][0] - samples[-2][0]) or 1e-12)
    pre = "constant" if abs(first) < 1e-9 else "linear"
    post = "constant" if abs(last) < 1e-9 else "linear"
    # flat ends: the corner is enough, drop the end key
    if pre == "constant" and len(keys) > 2 and abs(keys[0][1] - keys[1][1]) < 1e-9:
        keys = keys[1:]
    if post == "constant" and len(keys) > 2 and abs(keys[-1][1] - keys[-2][1]) < 1e-9:
        keys = keys[:-1]
    return driver, nodes, keys, pre, post


def _only_for(nodes, target):
    """The chain nodes that feed nothing but this chain (safe to delete)."""
    same = lambda a: (cmds.ls(a, long=True) or [a])[0]
    keep = set(same(n) for n in nodes)
    tnode = same(target.split(".", 1)[0])
    out = []
    for n in nodes:
        outs = [same(d) for _s, d, _a in MS._plugs_out(n)]
        if all(d in keep or d == tnode or cmds.nodeType(d) == "unitConversion" for d in outs):
            out.append(n)
    return out


def to_sdk(target):
    """Replace the chain driving target with a set driven key giving the same result. Returns a summary line."""
    driver, nodes, keys, pre, post = plan_sdk(target)
    cmds.undoInfo(openChunk=True, chunkName="gusrigNodesToSdk")
    try:
        gone = _only_for(nodes, target)
        src = networks._incoming(target)
        if src:
            cmds.disconnectAttr(src, target)
        for x, y in keys:
            cmds.setDrivenKeyframe(target, currentDriver=driver, driverValue=x, value=y,
                                   inTangentType="linear", outTangentType="linear")
        curve = (cmds.listConnections(target, source=True, destination=False, type="animCurve") or
                 cmds.listConnections(target, source=True, destination=False) or [None])[0]
        if curve and cmds.nodeType(curve) in UCURVES:
            cmds.setInfinity(curve, preInfinite=pre, postInfinite=post)
        left = [n for n in gone if cmds.objExists(n)]
        if left:
            cmds.delete(left)
    finally:
        cmds.undoInfo(closeChunk=True)
    return "%s: %d key(s) from %s (was %d node(s))" % (_short(target), len(keys), _short(driver), len(nodes))


def _curve_of(target):
    for n in cmds.listConnections(target, source=True, destination=False, skipConversionNodes=True) or []:
        if cmds.nodeType(n) in UCURVES:
            return n
    return None


def plan_nodes(target):
    """(curve, driver plug, lo, hi, slope, offset) for a straight / one-sided key curve, or raises with the reason:
    target = offset + slope * clamp(driver, lo, hi) (lo / hi None: no limit on that side)."""
    curve = _curve_of(target)
    if not curve:
        raise RuntimeError("%s has no set driven key." % _short(target))
    drv = cmds.listConnections(curve + ".input", source=True, destination=False, plugs=True,
                               skipConversionNodes=True) or []
    if not drv:
        raise RuntimeError("%s's key curve has no driver." % _short(curve))
    xs = cmds.keyframe(curve, query=True, floatChange=True) or []
    ys = cmds.keyframe(curve, query=True, valueChange=True) or []
    if len(xs) < 2:
        raise RuntimeError("%s has fewer than 2 keys." % _short(curve))
    outs = cmds.keyTangent(curve, query=True, outTangentType=True) or []
    ins = cmds.keyTangent(curve, query=True, inTangentType=True) or []
    pts = sorted(zip(xs, ys))
    slopes = [(b[1] - a[1]) / ((b[0] - a[0]) or 1e-12) for a, b in zip(pts, pts[1:])]
    moving = [s for s in slopes if abs(s) > 1e-9]
    if any(abs(s - moving[0]) > 1e-6 * max(1.0, abs(moving[0])) for s in moving) if moving else False:
        raise RuntimeError("%s bends (more than one slope): nodes can't make that curve - keep the key." %
                           _short(curve))
    straight = all(t in ("linear", "flat", "step", "clamped", "auto") for t in ins + outs) and (
        len(pts) == 2 or all(t == "linear" for t in ins[1:-1] + outs[1:-1]))
    if len(pts) > 2 and not all(t == "linear" for t in ins[1:-1] + outs[1:-1]):
        straight = False
    if not straight and len(pts) > 2:
        raise RuntimeError("%s has smooth tangents between keys: nodes would make it straight - keep the key, or "
                           "make its tangents linear first." % _short(curve))
    slope = moving[0] if moving else 0.0
    pre = cmds.setInfinity(curve, query=True, preInfinite=True)[0]
    post = cmds.setInfinity(curve, query=True, postInfinite=True)[0]
    # where it moves: from the first key of the sloped part to the last
    lo = hi = None
    seg = [i for i, s in enumerate(slopes) if abs(s) > 1e-9]
    if seg:
        a, b = pts[seg[0]], pts[seg[-1] + 1]
        if seg[0] > 0 or pre != "linear":
            lo = a[0]
        if seg[-1] < len(slopes) - 1 or post != "linear":
            hi = b[0]
        offset = a[1] - slope * a[0]
    else:
        offset = pts[0][1]
    return curve, drv[0], lo, hi, slope, offset


def to_nodes(target):
    """Replace a straight / one-sided set driven key with clamp + multiply (+ add). Returns a summary line."""
    curve, driver, lo, hi, slope, offset = plan_nodes(target)
    dnode, dattr = driver.split(".", 1)
    tnode, tch = target.split(".", 1)
    short = networks.SHORT.get(dattr, dattr)
    name = lambda kind: _unique(networks.compose(dnode, short, tnode, kind))
    cmds.undoInfo(openChunk=True, chunkName="gusrigSdkToNodes")
    try:
        cmds.delete(curve)
        src = driver
        if lo is not None or hi is not None:
            cl = cmds.createNode("clamp", name=name("clamp"), skipSelect=True)
            cmds.setAttr(cl + ".minR", lo if lo is not None else -BIG * 10)
            cmds.setAttr(cl + ".maxR", hi if hi is not None else BIG * 10)
            cmds.connectAttr(src, cl + ".inputR")
            src = cl + ".outputR"
        md = cmds.createNode("multiplyDivide", name=name("multiplyDivide"), skipSelect=True)
        cmds.setAttr(md + ".operation", 1)
        cmds.setAttr(md + ".input2X", slope)
        cmds.connectAttr(src, md + ".input1X")
        out = md + ".outputX"
        if abs(offset) > 1e-9:
            add = cmds.createNode("addDoubleLinear", name=name("addDoubleLinear"), skipSelect=True)
            cmds.connectAttr(out, add + ".input1")
            cmds.setAttr(add + ".input2", offset)
            out = add + ".output"
        cmds.connectAttr(out, target, force=True)
    finally:
        cmds.undoInfo(closeChunk=True)
    rng = "%s..%s" % ("-" if lo is None else networks._fmt(lo), "+" if hi is None else networks._fmt(hi))
    return "%s: clamp %s, x %s%s" % (_short(target), rng, networks._fmt(slope),
                                      (" + %s" % networks._fmt(offset)) if abs(offset) > 1e-9 else "")


def _unique(name):
    out, i = name, 2
    while cmds.objExists(out):
        out, i = "%s%d" % (name, i), i + 1
    return out


def twin_plug(target):
    node, attr = target.split(".", 1)
    t = MS.twin(node)
    return "%s.%s" % (t, attr) if t else None
