"""
Gus_Rigtool diagnostic (5.6.28): which Delta Mush attribute keeps the form when the rig is scaled?

Paste into Maya's Script Editor (Python tab) with the Hare scene open, run it, and paste the printed report back.
It changes NOTHING: undo is off while it runs, Auto Key is off, and every value and connection goes back.

The rig is scaled x2 (Global_ctrl.globalScale) and each Delta Mush mesh is compared with a perfect x2 copy of
itself, for three set-ups:
  now           - as the rig is (5.6.27 Repair: displacement follows the global scale)
  displacement  - displacement = 2, Scale XYZ = 1
  scale XYZ     - displacement = 1, Scale XYZ = 2  (Maya's own attribute for scaled rigs)
"off by" is how far the mesh is from the perfect x2 copy (smaller is better; 0.00 = keeps its form).
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

SCALE_PLUGS = ("Global_ctrl.globalScale", "*:Global_ctrl.globalScale")


def _plug():
    for p in SCALE_PLUGS:
        node, attr = p.split(".")
        got = cmds.ls(node, long=True)
        if got and cmds.attributeQuery(attr, node=got[0], exists=True):
            return got[0] + "." + attr
    return None


def _points(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return [(p.x, p.y, p.z) for p in om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)]


def _shape(geo):
    if cmds.nodeType(geo) == "mesh":
        return geo
    kids = cmds.listRelatives(geo, shapes=True, noIntermediate=True, fullPath=True) or []
    return kids[0] if kids else None


def main():
    print("=" * 70)
    print("Delta Mush and the rig's scale (Gus_Rigtool 5.6.28 diagnostic)")
    plug = _plug()
    dms = cmds.ls(type="deltaMush") or []
    if not plug or not dms:
        print("  not found: scale plug %s, delta mush %s" % (plug, dms))
        return
    ctrl = plug.split(".")[0]
    pivot = cmds.xform(ctrl, query=True, worldSpace=True, rotatePivot=True)
    if not cmds.getAttr(plug, settable=True):
        print("  %s can't be set (locked / driven)" % plug)
        return
    undo_was = cmds.undoInfo(query=True, stateWithoutFlush=True)
    key_was = cmds.autoKeyframe(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    cmds.autoKeyframe(state=False)
    s0 = cmds.getAttr(plug)
    saved = {}
    for dm in dms:
        src = cmds.listConnections(dm + ".displacement", source=True, destination=False, plugs=True) or []
        saved[dm] = {"src": src[0] if src else None, "disp": cmds.getAttr(dm + ".displacement"),
                     "scale": [cmds.getAttr(dm + ".scale" + a) for a in "XYZ"]}
    try:
        shapes = {}
        for dm in dms:
            geos = cmds.deformer(dm, query=True, geometry=True) or []
            shapes[dm] = [s for s in (_shape(g) for g in geos) if s]
        rest = {s: _points(s) for ss in shapes.values() for s in ss}

        def off_by(dm, label):
            for s in shapes[dm]:
                worst = 0.0
                for a, b in zip(rest[s], _points(s)):
                    want = [pivot[k] + 2.0 * (a[k] - pivot[k]) for k in range(3)]
                    worst = max(worst, sum((b[k] - want[k]) ** 2 for k in range(3)) ** 0.5)
                print("    %-14s %-26s off by %.3f" % (label, s.split("|")[-1], worst))

        for dm in dms:
            info = saved[dm]
            print("-" * 70)
            print("  %s: displacement %.3g%s, Scale XYZ %s" % (
                dm, info["disp"], (" (from %s)" % info["src"]) if info["src"] else "",
                ", ".join("%.3g" % v for v in info["scale"])))
            cmds.setAttr(plug, s0 * 2.0)
            off_by(dm, "now")
            if info["src"]:
                cmds.disconnectAttr(info["src"], dm + ".displacement")
            for label, disp, scale in (("displacement", 2.0, 1.0), ("scale XYZ", 1.0, 2.0)):
                cmds.setAttr(dm + ".displacement", disp)
                for a in "XYZ":
                    cmds.setAttr(dm + ".scale" + a, scale)
                off_by(dm, label)
            cmds.setAttr(plug, s0)
            cmds.setAttr(dm + ".displacement", info["disp"])
            for a, v in zip("XYZ", info["scale"]):
                cmds.setAttr(dm + ".scale" + a, v)
            if info["src"]:
                cmds.connectAttr(info["src"], dm + ".displacement", force=True)
    finally:
        cmds.setAttr(plug, s0)
        for dm, info in saved.items():
            try:
                for a, v in zip("XYZ", info["scale"]):
                    cmds.setAttr(dm + ".scale" + a, v)
                if info["src"]:
                    if not cmds.isConnected(info["src"], dm + ".displacement"):
                        cmds.connectAttr(info["src"], dm + ".displacement", force=True)
                else:
                    cmds.setAttr(dm + ".displacement", info["disp"])
            except RuntimeError as e:
                print("  COULD NOT PUT BACK %s: %s - tell Claude" % (dm, e))
        cmds.autoKeyframe(state=key_was)
        cmds.undoInfo(stateWithoutFlush=undo_was)
    print("=" * 70)
    print("Nothing was changed. Paste this report back.")


main()
