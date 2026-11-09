"""
Connect attributes: one driver to many driven nodes, by the same names or in order, with an optional
node in between (multiply, reverse, negative). Break incoming connections. Report what drives what.
"""

import maya.cmds as cmds

from gus_rigtool.core import nodes as _nodes

MIDDLES = ["direct", "multiply", "reverse (1 - x)", "negative (-x)"]


def channel_box_attrs():
    """The attributes picked in the Channel Box (main, shape and inputs sections)."""
    out = []
    for flag in ("selectedMainAttributes", "selectedShapeAttributes", "selectedHistoryAttributes"):
        try:
            out += cmds.channelBox("mainChannelBox", query=True, **{flag: True}) or []
        except (RuntimeError, TypeError):
            pass
    return out


def parse(text):
    return [a.strip().lstrip(".") for a in (text or "").replace(";", ",").replace(" ", ",").split(",") if a.strip()]


def pairs(src_attrs, dst_attrs):
    """[(src, dst)]: same names when dst is empty, else in order (lists must be the same length, or one
    source to many)."""
    if not src_attrs:
        raise ValueError("type the driver's attributes (or pick them in the Channel Box).")
    if not dst_attrs:
        return [(a, a) for a in src_attrs]
    if len(src_attrs) == 1:
        return [(src_attrs[0], d) for d in dst_attrs]
    if len(src_attrs) != len(dst_attrs):
        raise ValueError("%d driver attribute(s) but %d driven: give as many, or one driver." % (
            len(src_attrs), len(dst_attrs)))
    return list(zip(src_attrs, dst_attrs))


_short = _nodes.short


def _middle(kind, src, dst_node, dst_attr, factor):
    base = "%s_%s" % (_short(dst_node).split(":")[-1], dst_attr)
    if kind == 1:
        n = cmds.createNode("multDoubleLinear", name=base + "_mult")
        cmds.connectAttr(src, n + ".input1")
        cmds.setAttr(n + ".input2", float(factor))
        return n + ".output"
    if kind == 2:
        n = cmds.createNode("reverse", name=base + "_rev")
        cmds.connectAttr(src, n + ".inputX")
        return n + ".outputX"
    if kind == 3:
        n = cmds.createNode("multDoubleLinear", name=base + "_neg")
        cmds.connectAttr(src, n + ".input1")
        cmds.setAttr(n + ".input2", -1.0)
        return n + ".output"
    return src


def connect(driver, driven, attr_pairs, middle=0, factor=1.0):
    """Connect driver.src -> each driven.dst. Returns (made, problems)."""
    made, problems = 0, []
    for node in driven:
        for s, d in attr_pairs:
            src, dst = driver + "." + s, node + "." + d
            if not cmds.objExists(src):
                problems.append("%s has no '%s'" % (_short(driver), s))
                continue
            if not cmds.objExists(dst):
                problems.append("%s has no '%s'" % (_short(node), d))
                continue
            if src.split(".")[0] == dst.split(".")[0] and s == d:
                continue
            try:
                if cmds.getAttr(dst, lock=True):
                    problems.append("%s.%s is locked" % (_short(node), d))
                    continue
                plug = _middle(middle, src, node, d, factor)
                cmds.connectAttr(plug, dst, force=True)
                made += 1
            except RuntimeError as e:
                problems.append("%s.%s: %s" % (_short(node), d, str(e).strip()))
    return made, problems


def pattern_pairs(src_pattern, dst_pattern):
    """5.2.0: 'L_Brow_0*_ctrl.translateY' -> 'L_Brow_0*_sdk.rotateX': [(src plug, dst plug)], matched by what the *
    stands for (01 with 01, 02 with 02...); no * in the names: in order. Raises when nothing matches."""
    import re

    def split(p):
        if "." not in p:
            raise ValueError("write node.attribute, e.g. L_Brow_0*_ctrl.translateY")
        return p.split(".", 1)

    sn, sa = split(src_pattern.strip())
    dn, da = split(dst_pattern.strip())
    srcs = cmds.ls(sn, long=True) or []
    dsts = cmds.ls(dn, long=True) or []
    if not srcs or not dsts:
        raise ValueError("nothing matches %s" % (sn if not srcs else dn))

    def key(pattern, node):
        rx = "^" + "(.*?)".join(re.escape(x) for x in pattern.split("*")) + "$"
        m = re.match(rx, _short(node))
        return m.groups() if m else None
    if "*" in sn and "*" in dn:
        by = {}
        for d in dsts:
            k = key(dn, d)
            if k is not None:
                by.setdefault(k, d)
        out = [(s + "." + sa, by[key(sn, s)] + "." + da) for s in srcs if key(sn, s) in by]
    else:
        if len(srcs) == 1:
            out = [(srcs[0] + "." + sa, d + "." + da) for d in dsts]
        elif len(srcs) == len(dsts):
            out = [(s + "." + sa, d + "." + da) for s, d in zip(srcs, dsts)]
        else:
            raise ValueError("%d driver(s) but %d driven: use * in both names to pair them" % (len(srcs), len(dsts)))
    if not out:
        raise ValueError("no pairs: the * parts of the two names don't match")
    return out


def connect_pairs(plug_pairs, middle=0, factor=1.0):
    """Connect [(src plug, dst plug)] with the middle node. Returns (made, problems)."""
    made, problems = 0, []
    for src, dst in plug_pairs:
        node, attr = dst.split(".", 1)
        if not cmds.objExists(src) or not cmds.objExists(dst):
            problems.append("%s or %s doesn't exist" % (src, dst))
            continue
        try:
            plug = _middle(middle, src, node, attr, factor)
            cmds.connectAttr(plug, dst, force=True)
            made += 1
        except RuntimeError as e:
            problems.append("%s: %s" % (_short(node), str(e).strip()))
    return made, problems


def break_incoming(nodes, attr_names):
    """Disconnect what drives these attributes (keys too). Returns how many connections went."""
    n = 0
    for node in nodes:
        for a in attr_names:
            plug = node + "." + a
            if not cmds.objExists(plug):
                continue
            pairs_ = cmds.listConnections(plug, source=True, destination=False, plugs=True, connections=True,
                                          skipConversionNodes=True) or []
            for dst, src in zip(pairs_[0::2], pairs_[1::2]):
                try:
                    cmds.disconnectAttr(src, dst)
                    n += 1
                except RuntimeError:
                    pass
    return n


NOISE = ("message", "instObjGroups", "objectGroups", "drawOverride", "worldMatrix", "parentMatrix",
         "parentInverseMatrix", "isHistoricallyInteresting", "hyperLayout", "lockInfo")


def _noisy(*plugs):
    return any(any(w in p.split(".", 1)[-1] for w in NOISE) for p in plugs)


def report(nodes):
    lines = []
    for node in nodes:
        lines.append(_short(node))
        ins = cmds.listConnections(node, source=True, destination=False, plugs=True, connections=True,
                                   skipConversionNodes=True) or []
        outs = cmds.listConnections(node, source=False, destination=True, plugs=True, connections=True,
                                    skipConversionNodes=True) or []
        got = False
        for dst, src in zip(ins[0::2], ins[1::2]):
            if _noisy(dst, src):
                continue
            lines.append("    <- %-22s from %s" % (dst.split(".", 1)[1], _short(src.split(".")[0]) + "." +
                                                   src.split(".", 1)[1]))
            got = True
        for src, dst in zip(outs[0::2], outs[1::2]):
            if _noisy(src, dst):
                continue
            lines.append("    -> %-22s to   %s" % (src.split(".", 1)[1], _short(dst.split(".")[0]) + "." +
                                                   dst.split(".", 1)[1]))
            got = True
        if not got:
            lines.append("    (no connections)")
    return "\n".join(lines)
