"""
Gus_Rigtool diagnostic (5.6.28): how far does the head squash reach?

Paste into Maya's Script Editor (Python tab) with the Hare scene open, run it, and paste the printed report back.
It changes NOTHING: undo is off while it runs, Auto Key is off, and every value it touches goes back.

For each pose of Head_squash_ctrl (squash, stretch, bend sideways, bend front) it lists, per mesh, the vertices
that move, split into:
  inside   - inside the lattice box (the head): expected
  fade     - just outside it, within the fade (ears, neck ride along): expected
  BEYOND   - farther than the fade: these should never move
It also prints each Head_squash input's component tag expression ("" = the whole mesh).
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

CTRL_PATTERNS = ("Head_squash_ctrl", "*:Head_squash_ctrl")
TOL = 1e-3


def _one(patterns, kind=None):
    for p in patterns:
        got = cmds.ls(p, type=kind, long=True) if kind else cmds.ls(p, long=True)
        if got:
            return got[0]
    return None


def _points(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return [(p.x, p.y, p.z) for p in om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)]


def _final_shape(geo):
    """The mesh you see, for a deformer's output geometry."""
    shape = geo
    if cmds.nodeType(shape) != "mesh":
        kids = cmds.listRelatives(shape, shapes=True, noIntermediate=True, fullPath=True) or []
        shape = kids[0] if kids else None
    return shape


def main():
    ctrl = _one(CTRL_PATTERNS)
    ffds = [f for f in cmds.ls(type="ffd") or [] if "head_squash" in f.lower()]
    lats = [x for x in cmds.ls(type="lattice", long=True) or [] if "head_squash" in x.lower()]
    print("=" * 70)
    print("Head squash reach (Gus_Rigtool 5.6.28 diagnostic)")
    if not ctrl or not ffds or not lats:
        print("  not found: control %s, lattice deformer %s, lattice %s" % (ctrl, ffds, lats))
        return
    ffd = ffds[0]
    lat_t = cmds.listRelatives(lats[0], parent=True, fullPath=True)[0]
    bb = cmds.exactWorldBoundingBox(lat_t)
    lo, hi = bb[:3], bb[3:]
    height = hi[1] - lo[1]
    fade = cmds.getAttr(ffd + ".outsideFalloffDist") * height
    print("  control: %s   deformer: %s   outside lattice mode: %s   fade: %.2f" % (
        ctrl.split("|")[-1], ffd, cmds.getAttr(ffd + ".outsideLattice"), fade))
    for i in cmds.getAttr(ffd + ".input", multiIndices=True) or []:
        try:
            expr = cmds.getAttr("%s.input[%d].componentTagExpression" % (ffd, i))
        except Exception:
            expr = "(no tag attribute)"
        print("  input[%d] component tag expression: %r" % (i, expr))
    try:
        geos = cmds.deformer(ffd, query=True, geometry=True) or []
    except Exception:
        geos = cmds.lattice(ffd, query=True, geometry=True) or []
    shapes = [s for s in (_final_shape(g) for g in geos) if s and cmds.nodeType(s) == "mesh"]

    def where(p):
        out = max(max(lo[k] - p[k], p[k] - hi[k], 0.0) for k in range(3))
        return "inside" if out <= 0 else ("fade" if out <= fade + TOL else "BEYOND")

    amount = height * 0.3
    poses = [("squash down", "translateY", -amount), ("stretch up", "translateY", amount),
             ("bend sideways", "translateX", amount), ("bend front", "translateZ", amount)]
    undo_was = cmds.undoInfo(query=True, stateWithoutFlush=True)
    key_was = cmds.autoKeyframe(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    cmds.autoKeyframe(state=False)
    back = []
    try:
        rest = {s: _points(s) for s in shapes}
        for label, attr, value in poses:
            plug = ctrl + "." + attr
            if not cmds.getAttr(plug, settable=True):
                print("  %s: %s can't be set (locked / driven) - skipped" % (label, attr))
                continue
            v0 = cmds.getAttr(plug)
            back.append((plug, v0))
            cmds.setAttr(plug, v0 + value)
            print("-" * 70)
            print("  %s (%s %+.2f)" % (label, attr, value))
            for s in shapes:
                now = _points(s)
                counts = {"inside": 0, "fade": 0, "BEYOND": 0}
                lowest = None
                for a, b in zip(rest[s], now):
                    if sum((a[k] - b[k]) ** 2 for k in range(3)) ** 0.5 > TOL:
                        w = where(a)
                        counts[w] += 1
                        if w == "BEYOND" and (lowest is None or a[1] < lowest):
                            lowest = a[1]
                print("    %-32s inside %5d   fade %5d   BEYOND %5d%s" % (
                    s.split("|")[-1], counts["inside"], counts["fade"], counts["BEYOND"],
                    ("   (lowest at y %.1f)" % lowest) if lowest is not None else ""))
            cmds.setAttr(plug, v0)
            back.pop()
    finally:
        for plug, v0 in back:
            cmds.setAttr(plug, v0)
        cmds.autoKeyframe(state=key_was)
        cmds.undoInfo(stateWithoutFlush=undo_was)
    print("=" * 70)
    print("Nothing was changed. Paste this report back.")


main()
