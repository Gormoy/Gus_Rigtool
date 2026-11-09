"""
Network tools (5.5.0): a control's node network - the utility nodes / driven-key curves between drivers and what
they drive - tidied in the Node Editor, protected for delivery, Maya's back-to-back unit conversions folded away,
and the heaviest parts of the rig listed.

    from gus_rigtool.core import network_tools as NT
    NT.network(["L_Brow_02_ctrl"])      # {'nodes': [...], 'drivers': [...], 'driven': [...]}
    NT.tidy(["L_Brow_02_ctrl"])         # graphed and laid out in the Node Editor
    NT.protect(); NT.unprotect()        # lock / unlock utility nodes and constraints (Publish)
    NT.fold_conversions()               # unitConversion -> unitConversion back to back: connected directly
    NT.heaviest()                       # [(part, nodes, {type: count})] biggest first
"""

import json
import re

import maya.cmds as cmds

from gus_rigtool.core import mirror_setup as MS
from gus_rigtool.core import naming, utils

CURVES = ("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT")
PROTECT_NODE = "gusProtected"


def _short(n):
    return naming.short_name(n)


def _long(n):
    return (cmds.ls(n, long=True) or [n])[0]


def _kind(n):
    try:
        return cmds.nodeType(n)
    except RuntimeError:
        return ""


def _middle(n):
    """A node that sits inside a network: utility nodes, driven-key curves, blendWeighted."""
    k = _kind(n)
    return k in MS.UTILITY or k in CURVES or k == "blendWeighted"


def network(nodes, limit=400):
    """Every network node reachable from the given nodes through other network nodes, both ways, plus the nodes
    at its ends: {'nodes': network nodes, 'drivers': nodes feeding it, 'driven': nodes it feeds}."""
    seen, todo = [], []
    ends_in, ends_out = [], []
    for n in nodes:
        for _a, src, _sa in MS._plugs_in(n):
            todo.append(src)
        for _sa, dst, _da in MS._plugs_out(n):
            todo.append(dst)
        if _middle(n):
            todo.append(n)
    while todo and len(seen) < limit:
        n = todo.pop(0)
        n = _long(n)
        if n in seen or not _middle(n):
            continue
        seen.append(n)
        for _a, src, _sa in MS._plugs_in(n):
            if _middle(src):
                todo.append(src)
            elif _long(src) not in ends_in:
                ends_in.append(_long(src))
        for _sa, dst, _da in MS._plugs_out(n):
            if _middle(dst):
                todo.append(dst)
            elif _long(dst) not in ends_out:
                ends_out.append(_long(dst))
    return {"nodes": seen, "drivers": ends_in, "driven": ends_out}


def _editor():
    """The Node Editor's editor (opened if it isn't)."""
    eds = [e for e in (cmds.getPanel(scriptType="nodeEditorPanel") or [])]
    if not eds:
        raise RuntimeError("no Node Editor panel")
    panel = eds[0]
    try:
        cmds.scriptedPanel(panel, edit=True, tearOff=True)
    except RuntimeError:
        pass
    return panel + "NodeEditorEd"


def tidy(nodes):
    """The network of the given nodes in the Node Editor, alone, laid out left (drivers) to right (driven).
    Returns (network nodes, drivers, driven)."""
    net = network(nodes)
    if not net["nodes"]:
        raise RuntimeError("no utility nodes / driven keys around %s." % ", ".join(_short(n) for n in nodes))
    show = net["drivers"] + net["nodes"] + net["driven"]
    try:
        cmds.NodeEditorWindow()
    except (RuntimeError, AttributeError):
        pass
    ed = _editor()
    cmds.nodeEditor(ed, edit=True, rootNode="")                 # clear the graph
    for n in show:
        cmds.nodeEditor(ed, edit=True, addNode=n)
    for flag in ("layout", "frameAll"):                          # tidied left to right, then framed
        try:
            cmds.nodeEditor(ed, edit=True, **{flag: True})
        except (RuntimeError, TypeError):
            pass
    return net["nodes"], net["drivers"], net["driven"]


# ---- protect (delivery) ---------------------------------------------------------------------------------------

def protectable():
    """Utility nodes, driven-key curves and constraints of the rig (not referenced, not already locked)."""
    out = []
    for n in cmds.ls(type=list(MS.UTILITY) + list(CURVES) + list(MS.CONSTRAINTS), long=True) or []:
        if _kind(n) in CURVES and not cmds.listConnections(n + ".input", source=True, destination=False):
            continue                                       # time curves (animation) aren't rig
        try:
            if cmds.referenceQuery(n, isNodeReferenced=True):
                continue
        except RuntimeError:
            pass
        try:
            if cmds.lockNode(n, query=True, lock=True)[0]:
                continue
        except (RuntimeError, IndexError, TypeError):
            pass
        out.append(n)
    return out


def protect():
    """Lock them (can't be deleted, renamed or reparented by accident); remembered for unprotect. Returns how many."""
    nodes = protectable()
    for n in nodes:
        cmds.lockNode(n, lock=True)
    if not cmds.objExists(PROTECT_NODE):
        cmds.createNode("network", name=PROTECT_NODE, skipSelect=True)
    if not cmds.attributeQuery("gusLocked", node=PROTECT_NODE, exists=True):
        cmds.addAttr(PROTECT_NODE, longName="gusLocked", dataType="string")
    old = json.loads(cmds.getAttr(PROTECT_NODE + ".gusLocked") or "[]")
    cmds.setAttr(PROTECT_NODE + ".gusLocked", json.dumps(sorted(set(old) | set(_short(n) for n in nodes))),
                 type="string")
    cmds.lockNode(PROTECT_NODE, lock=True)
    return len(nodes)


def unprotect():
    if not cmds.objExists(PROTECT_NODE):
        return 0
    names = json.loads(cmds.getAttr(PROTECT_NODE + ".gusLocked") or "[]")
    n = 0
    for name in names:
        for x in cmds.ls(name, long=True) or []:
            cmds.lockNode(x, lock=False)
            n += 1
    cmds.lockNode(PROTECT_NODE, lock=False)
    cmds.delete(PROTECT_NODE)
    return n


# ---- unit conversions -----------------------------------------------------------------------------------------

def double_conversions():
    """[(first uc, second uc, source plug, [destination plugs])]: a unitConversion feeding only another one whose
    factors cancel out (degrees -> radians -> degrees) - the source can feed the destinations straight."""
    out = []
    for uc in cmds.ls(type="unitConversion") or []:
        outs = cmds.listConnections(uc + ".output", source=False, destination=True, plugs=True) or []
        if len(outs) != 1 or _kind(outs[0].split(".")[0]) != "unitConversion" or not outs[0].endswith(".input"):
            continue
        uc2 = outs[0].split(".")[0]
        try:
            f = cmds.getAttr(uc + ".conversionFactor") * cmds.getAttr(uc2 + ".conversionFactor")
        except (RuntimeError, ValueError, TypeError):
            continue
        if abs(f - 1.0) > 1e-6:
            continue
        src = (cmds.listConnections(uc + ".input", source=True, destination=False, plugs=True) or [None])[0]
        dsts = cmds.listConnections(uc2 + ".output", source=False, destination=True, plugs=True) or []
        if src and dsts:
            out.append((uc, uc2, src, dsts))
    return out


def fold_conversions():
    """Every double conversion: the source connected straight to the destinations, the two nodes deleted. One
    undo. Returns how many pairs."""
    pairs = double_conversions()
    with utils.undo_chunk("gusrigFoldConversions"):
        for uc, uc2, src, dsts in pairs:
            for d in dsts:
                cmds.connectAttr(src, d, force=True)
            for n in (uc2, uc):
                if cmds.objExists(n):
                    cmds.delete(n)
    return len(pairs)


# ---- heaviest parts -------------------------------------------------------------------------------------------

DEFAULT_NAME = re.compile(r"^(%s)\d*$" % "|".join(
    ["unitConversion", "multiplyDivide", "plusMinusAverage", "condition", "reverse", "clamp", "blendColors",
     "remapValue", "setRange", "multDoubleLinear", "addDoubleLinear", "distanceBetween", "decomposeMatrix",
     "composeMatrix", "multMatrix", "blendWeighted", "pairBlend", "animCurveU[LATU]", "floatMath", "expression",
     "[a-zA-Z]+Constraint", "follicle", "ikHandle"]))


def _part(name):
    """'L_Brow_02_ty_to_Brow_02_sdk_md' -> 'L_Brow'; 'Cape_jiggle_expr' -> 'Cape'; 'unitConversion253' ->
    '(default names)' (5.5.1: Maya's own names say nothing about where the node is)."""
    short = _short(name).split(":")[-1]
    if DEFAULT_NAME.match(short):
        return "(default names)"
    tokens = [t for t in short.split("_") if t]
    side = tokens[0] if tokens and tokens[0] in ("L", "R", "C", "M") else ""
    rest = tokens[1:] if side else tokens
    word = next((re.sub(r"\d+$", "", t) for t in rest if re.sub(r"\d+$", "", t)), "other")
    return (side + "_" if side else "") + word


def heaviest(top=10):
    """[(part, total nodes, {type: count})] - utility nodes, driven-key curves, constraints, expressions and
    follicles counted by the part of the rig their name belongs to (L_Brow, Cape, Mouth...), biggest first."""
    kinds = list(MS.UTILITY) + list(CURVES) + list(MS.CONSTRAINTS) + ["expression", "follicle", "ikHandle"]
    parts = {}
    for n in cmds.ls(type=kinds) or []:
        k = _kind(n)
        if k in CURVES and not cmds.listConnections(n + ".input", source=True, destination=False):
            continue
        p = parts.setdefault(_part(n), {})
        p[k] = p.get(k, 0) + 1
    rows = [(p, sum(c.values()), c) for p, c in parts.items()]
    rows.sort(key=lambda r: -r[1])
    return rows[:top]


def heaviest_text(top=10):
    rows = heaviest(top)
    return "\n".join("%-14s %4d   %s" % (p, n, ", ".join("%s %d" % (k, v) for k, v in
                                                        sorted(c.items(), key=lambda x: -x[1])[:4]))
                     for p, n, c in rows)
