"""
Make a driver (5.2.0): one channel of a control drives channels of other nodes - only its positive side, only its
negative side, or both, up to a limit, times an amount - the clamp + multiplyDivide you built by hand on the Hare's
brow, named like Nodes > 'Name utility nodes', and the same on the other side.

    from gus_rigtool.core import drivers as D
    print(D.preview("L_Brow_02_ctrl.translateY", [("L_Brow_02_sdk", "rotateX", -4.0)], side="positive"))
    D.make("L_Brow_02_ctrl.translateY", [("L_Brow_02_sdk", "rotateX", -4.0)], side="positive")
"""

import maya.cmds as cmds

from gus_rigtool.core import mirror_setup as MS
from gus_rigtool.core import networks

SIDES = ("positive", "negative", "both")
BIG = 1.0e6


def _driven(plug):
    src = cmds.listConnections(plug, source=True, destination=False, plugs=True, skipConversionNodes=True) or []
    if not src and plug[-1] in "XYZ":
        src = cmds.listConnections(plug[:-1], source=True, destination=False, plugs=True,
                                   skipConversionNodes=True) or []
    return src[0] if src else None


def _range(side, limit):
    lim = abs(float(limit)) if limit else BIG
    return {"positive": (0.0, lim), "negative": (-lim, 0.0), "both": (-lim, lim)}[side]


def plan(driver_plug, targets, side="positive", limit=None, mirror=True, flip_other=False):
    """[(driver plug, target node, channel, amount, problem or None)] for this side and (mirror) the other."""
    if side not in SIDES:
        raise ValueError("side is one of %s." % ", ".join(SIDES))
    node, attr = driver_plug.split(".", 1)
    if not cmds.objExists(driver_plug):
        raise RuntimeError("%s doesn't exist." % driver_plug)
    rows = []

    def add(dplug, tnode, ch, amount):
        plug = "%s.%s" % (tnode, ch)
        if not cmds.objExists(tnode) or not cmds.objExists(plug):
            rows.append((dplug, tnode, ch, amount, "%s has no %s" % (networks._short(tnode), ch)))
            return
        busy = _driven(plug)
        if busy:
            rows.append((dplug, tnode, ch, amount, "already driven by %s - use a group above it (its _sdk)" %
                         networks._short(busy)))
            return
        rows.append((dplug, tnode, ch, amount, None))

    for tnode, ch, amount in targets:
        add(driver_plug, tnode, ch, float(amount))
    if mirror:
        twin = MS.twin(node)
        if not twin:
            rows.append((driver_plug, None, None, None, "no twin for %s: the other side is not made" %
                         networks._short(node)))
        else:
            for tnode, ch, amount in targets:
                tt = MS.twin(tnode)
                if not tt:
                    rows.append(("%s.%s" % (twin, attr), tnode, ch, amount, "no twin for %s" %
                                 networks._short(tnode)))
                    continue
                add("%s.%s" % (twin, attr), tt, ch, -float(amount) if flip_other else float(amount))
    return rows


def preview(driver_plug, targets, side="positive", limit=None, mirror=True, flip_other=False):
    lo, hi = _range(side, limit)
    rng = "%s side%s" % (side, (" up to %s" % networks._fmt(abs(float(limit)))) if limit else "")
    lines = []
    for dplug, tnode, ch, amount, problem in plan(driver_plug, targets, side, limit, mirror, flip_other):
        if problem:
            lines.append("  skip: %s" % problem)
            continue
        lines.append("  %s (%s) x %s -> %s.%s" % (networks._short(dplug), rng, networks._fmt(amount),
                                                 networks._short(tnode), ch))
    return "\n".join(lines)


def _unique(name):
    out, i = name, 2
    while cmds.objExists(out):
        out, i = "%s%d" % (name, i), i + 1
    return out


def _build(dplug, tnode, ch, amount, side, limit):
    dnode, dattr = dplug.split(".", 1)
    short = networks.SHORT.get(dattr, dattr)
    made = []
    src = dplug
    if side != "both" or limit:
        lo, hi = _range(side, limit)
        cl = cmds.createNode("clamp", name=_unique(networks.compose(dnode, short, tnode, "clamp")), skipSelect=True)
        cmds.setAttr(cl + ".minR", lo)
        cmds.setAttr(cl + ".maxR", hi)
        cmds.connectAttr(src, cl + ".inputR")
        src = cl + ".outputR"
        made.append(cl)
    md = cmds.createNode("multiplyDivide", name=_unique(networks.compose(dnode, short, tnode, "multiplyDivide")),
                         skipSelect=True)
    cmds.setAttr(md + ".operation", 1)
    cmds.setAttr(md + ".input2X", amount)
    cmds.connectAttr(src, md + ".input1X")
    cmds.connectAttr(md + ".outputX", "%s.%s" % (tnode, ch))     # Maya puts a unitConversion in for a rotation
    made.append(md)
    for uc in cmds.listConnections(md + ".outputX", source=False, destination=True, type="unitConversion") or []:
        if networks.is_default_name(uc):
            made.append(cmds.rename(uc, _unique(networks.compose(dnode, short, tnode, "unitConversion"))))
    return made


def make(driver_plug, targets, side="positive", limit=None, mirror=True, flip_other=False):
    """Build it (one undo). Returns (nodes made, lines skipped)."""
    rows = plan(driver_plug, targets, side, limit, mirror, flip_other)
    made, skipped = [], []
    cmds.undoInfo(openChunk=True, chunkName="gusrigMakeDriver")
    try:
        for dplug, tnode, ch, amount, problem in rows:
            if problem:
                skipped.append(problem)
                continue
            made += _build(dplug, tnode, ch, amount, side, limit)
    finally:
        cmds.undoInfo(closeChunk=True)
    return made, skipped
