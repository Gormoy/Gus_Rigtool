"""
Gus_Rigtool diagnostic (5.6.29, version 2): how far does the head squash reach?

Paste into Maya's Script Editor (Python tab) with the Hare scene open, run it, and paste the printed report back.
It changes NOTHING: undo is off while it runs, Auto Key is off, and every value it touches goes back (the
Head_Squash switch too - it's turned on for the test when it's off).

Version 2: the fade is measured in the lattice's own units, on every axis (version 1 used the height for all
three - the lattice is wider than it is tall, so the sides were counted wrong), from the base lattice (where the
lattice reaches), and each mesh says which input of the deformer it is and its component tag expression.

For each pose of Head_squash_ctrl it lists, per mesh, the vertices that move:
  inside  - inside the lattice box (the head): expected
  fade    - outside it, within the fade (ears, neck ride along): expected
  BEYOND  - farther than the fade: these should never move (where they are and their lattice weight is listed)
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

CTRL_PATTERNS = ("Head_squash_ctrl", "*:Head_squash_ctrl")
SWITCH_PATTERNS = ("*.Head_Squash",)
TOL = 1e-3


def _one(patterns):
    for p in patterns:
        got = cmds.ls(p, long=True)
        if got:
            return got[0]
    return None


def _points(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return [(p.x, p.y, p.z) for p in om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)]


def _to_local(points, node):
    inv = om.MMatrix(cmds.getAttr(node + ".worldInverseMatrix[0]"))
    return [tuple(om.MPoint(*p) * inv)[:3] for p in points]


def _input_of(mesh, ffd, limit=60):
    """Which input of the deformer feeds this visible mesh (walking up its history), or None."""
    plug = (cmds.listConnections(mesh + ".inMesh", source=True, destination=False, plugs=True) or [None])[0]
    seen = 0
    while plug and seen < limit:
        seen += 1
        node, attr = plug.split(".", 1)
        if node.split("|")[-1] == ffd and attr.startswith("outputGeometry["):
            return int(attr[len("outputGeometry["):].split("]")[0])
        nxt = None
        if cmds.objectType(node, isAType="geometryFilter") and "[" in attr:
            i = attr.split("[")[1].split("]")[0]
            nxt = "%s.input[%s].inputGeometry" % (node, i)
        else:
            for a in ("inMesh", "inputPolymesh", "inputGeometry"):
                if cmds.attributeQuery(a, node=node, exists=True):
                    nxt = "%s.%s" % (node, a)
                    break
        plug = (cmds.listConnections(nxt, source=True, destination=False, plugs=True) or [None])[0] if nxt else None
    return None


def main():
    print("=" * 74)
    print("Head squash reach (Gus_Rigtool diagnostic, version 2)")
    ctrl = _one(CTRL_PATTERNS)
    ffds = [f for f in cmds.ls(type="ffd") or [] if "head_squash" in f.lower()]
    if not ctrl or not ffds:
        print("  not found: control %s, lattice deformer %s" % (ctrl, ffds))
        return
    ffd = ffds[0]
    base = (cmds.listConnections(ffd + ".baseLatticeMatrix", source=True, destination=False) or [None])[0]
    if not base:
        print("  the lattice deformer has no base lattice")
        return
    fade = cmds.getAttr(ffd + ".outsideFalloffDist")
    print("  control: %s   deformer: %s   outside lattice: %s   fade: %.3f (lattice units, the box is 1 wide)" % (
        ctrl.split("|")[-1], ffd, cmds.getAttr(ffd + ".outsideLattice"), fade))
    exprs = {}
    for i in cmds.getAttr(ffd + ".input", multiIndices=True) or []:
        try:
            exprs[i] = cmds.getAttr("%s.input[%d].componentTagExpression" % (ffd, i))
        except Exception:
            exprs[i] = "(no tag attribute)"
    meshes = []
    for m in cmds.ls(type="mesh", noIntermediate=True, long=True) or []:
        i = _input_of(m, ffd)
        if i is not None:
            meshes.append((m, i))
    print("  meshes it deforms (input, tag expression - '' and '*' = the whole mesh):")
    for m, i in meshes:
        print("    input[%d] %-40s %r" % (i, m.split("|")[-1], exprs.get(i)))

    def where(p):
        out = max(max(abs(c) - 0.5, 0.0) for c in p)
        if out <= 0:
            return "inside", ""
        k = max(range(3), key=lambda a: abs(p[a]) - 0.5)
        side = ("+" if p[k] > 0 else "-") + "XYZ"[k]
        return ("fade" if out <= fade + TOL else "BEYOND"), side

    switch = _one(SWITCH_PATTERNS)
    height = cmds.getAttr(base + ".scaleY") or 1.0
    amount = abs(height) * 0.3
    poses = [("squash down", "translateY", -amount), ("stretch up", "translateY", amount),
             ("bend sideways", "translateX", amount), ("bend front", "translateZ", amount)]
    undo_was = cmds.undoInfo(query=True, stateWithoutFlush=True)
    key_was = cmds.autoKeyframe(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    cmds.autoKeyframe(state=False)
    back = []
    try:
        if switch and not cmds.getAttr(switch) and cmds.getAttr(switch, settable=True):
            back.append((switch, cmds.getAttr(switch)))
            cmds.setAttr(switch, 1)
            print("  (%s was off: turned on for the test)" % switch.split("|")[-1])
        rest = {m: _points(m) for m, _i in meshes}
        local = {m: _to_local(rest[m], base) for m, _i in meshes}
        for label, attr, value in poses:
            plug = ctrl + "." + attr
            if not cmds.getAttr(plug, settable=True):
                print("  %s: %s can't be set (locked / driven) - skipped" % (label, attr))
                continue
            v0 = cmds.getAttr(plug)
            back.append((plug, v0))
            cmds.setAttr(plug, v0 + value)
            print("-" * 74)
            print("  %s (%s %+.2f)" % (label, attr, value))
            for m, i in meshes:
                counts = {"inside": 0, "fade": 0, "BEYOND": 0}
                sides, far = {}, []
                for k, (a, b) in enumerate(zip(rest[m], _points(m))):
                    if sum((a[n] - b[n]) ** 2 for n in range(3)) ** 0.5 > TOL:
                        w, side = where(local[m][k])
                        counts[w] += 1
                        if w == "BEYOND":
                            sides[side] = sides.get(side, 0) + 1
                            far.append(k)
                extra = ""
                if far:
                    try:
                        ws = [cmds.percent(ffd, "%s.vtx[%d]" % (m, k), query=True, value=True)[0] for k in far[:50]]
                        extra = "   past the %s side(s); lattice weight %.2f-%.2f" % (
                            ", ".join("%s %d" % kv for kv in sorted(sides.items())), min(ws), max(ws))
                    except Exception:
                        extra = "   past the %s side(s)" % ", ".join("%s %d" % kv for kv in sorted(sides.items()))
                print("    input[%d] %-34s inside %5d   fade %5d   BEYOND %5d%s" % (
                    i, m.split("|")[-1][:34], counts["inside"], counts["fade"], counts["BEYOND"], extra))
            cmds.setAttr(plug, v0)
            back.pop()
    finally:
        for plug, v0 in reversed(back):
            cmds.setAttr(plug, v0)
        cmds.autoKeyframe(state=key_was)
        cmds.undoInfo(stateWithoutFlush=undo_was)
    print("=" * 74)
    print("Nothing was changed. Paste this report back.")


main()
