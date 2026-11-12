"""
Gus_Rigtool diagnostic (5.6.29, version 2): does each Delta Mush keep its form when the rig is scaled?

Paste into Maya's Script Editor (Python tab) with the Hare scene open, run it, and paste the printed report back.
It changes NOTHING: undo is off while it runs, Auto Key is off, and every value and connection goes back.

Version 2: Delta Mush's displacement can't be set above 1 (version 1 stopped there), so it compares, with the rig
scaled x2 (Global_ctrl.globalScale):
  now        - as the rig is (5.6.27 Repair: displacement fed by the global scale)
  unplugged  - displacement 1 on its own, Scale XYZ as it is
  scale XYZ  - unplugged, and Delta Mush's own Scale XYZ doubled
"off by" is how far the mesh is from a perfect x2 copy of itself (smaller is better; 0.000 = keeps its form).
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
    print("=" * 74)
    print("Delta Mush and the rig's scale (Gus_Rigtool diagnostic, version 2)")
    plug = _plug()
    dms = cmds.ls(type="deltaMush") or []
    if not plug or not dms:
        print("  not found: scale plug %s, delta mush %s" % (plug, dms))
        return
    if not cmds.getAttr(plug, settable=True):
        print("  %s can't be set (locked / driven)" % plug)
        return
    pivot = cmds.xform(plug.split(".")[0], query=True, worldSpace=True, rotatePivot=True)
    s0 = cmds.getAttr(plug)
    saved, shapes = {}, {}
    for dm in dms:
        src = cmds.listConnections(dm + ".displacement", source=True, destination=False, plugs=True) or []
        saved[dm] = {"src": src[0] if src else None, "disp": cmds.getAttr(dm + ".displacement"),
                     "scale": [cmds.getAttr(dm + ".scale" + a) for a in "XYZ"]}
        shapes[dm] = [s for s in (_shape(g) for g in cmds.deformer(dm, query=True, geometry=True) or []) if s]
    undo_was = cmds.undoInfo(query=True, stateWithoutFlush=True)
    key_was = cmds.autoKeyframe(query=True, state=True)
    cmds.undoInfo(stateWithoutFlush=False)
    cmds.autoKeyframe(state=False)
    try:
        rest = {s: _points(s) for ss in shapes.values() for s in ss}

        def off_by(dm):
            out = []
            for s in shapes[dm]:
                worst = 0.0
                for a, b in zip(rest[s], _points(s)):
                    want = [pivot[k] + 2.0 * (a[k] - pivot[k]) for k in range(3)]
                    worst = max(worst, sum((b[k] - want[k]) ** 2 for k in range(3)) ** 0.5)
                out.append("%s %.3f" % (s.split("|")[-1], worst))
            return ", ".join(out) or "(no mesh)"

        for dm in dms:
            info = saved[dm]
            odd = [v for v in info["scale"] if abs(v - 1.0) > 1e-6]
            print("-" * 74)
            print("  %s: displacement %.3g%s, Scale XYZ %s%s" % (
                dm, info["disp"], (" (from %s)" % info["src"].split("|")[-1]) if info["src"] else "",
                ", ".join("%.3g" % v for v in info["scale"]), "   <- Scale XYZ isn't 1" if odd else ""))
            cmds.setAttr(plug, s0 * 2.0)
            print("    %-10s off by: %s" % ("now", off_by(dm)))
            if info["src"]:
                cmds.disconnectAttr(info["src"], dm + ".displacement")
            cmds.setAttr(dm + ".displacement", 1.0)
            print("    %-10s off by: %s" % ("unplugged", off_by(dm)))
            for a, v in zip("XYZ", info["scale"]):
                cmds.setAttr(dm + ".scale" + a, v * 2.0)
            print("    %-10s off by: %s" % ("scale XYZ", off_by(dm)))
            for a, v in zip("XYZ", info["scale"]):
                cmds.setAttr(dm + ".scale" + a, v)
            if info["src"]:
                cmds.connectAttr(info["src"], dm + ".displacement", force=True)
            else:
                cmds.setAttr(dm + ".displacement", info["disp"])
            cmds.setAttr(plug, s0)
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
    print("=" * 74)
    print("Nothing was changed. Paste this report back.")


main()
