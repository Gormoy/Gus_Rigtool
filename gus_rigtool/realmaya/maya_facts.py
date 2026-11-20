"""
Maya facts (5.6.46): how Maya really behaves where Gus_Rigtool / Gus Animtool depend on it - each one something
the tool once got wrong by assuming. They run inside both test runs (the Terminal one: run_maya_tests.py, and Test
this release in Maya's window) and only report (info lines): the answers go into MAYA_FACTS.md and the fake Maya.

    from gus_rigtool.realmaya import maya_facts; print(maya_facts.text())
"""

import maya.cmds as cmds

from gus_rigtool.core.report import INFO, Report


def _warnings_while(fn):
    """The warnings Maya prints while fn runs (its own output callback)."""
    got = []
    cb = None
    try:
        import maya.OpenMaya as om1
        cb = om1.MCommandMessage.addCommandOutputCallback(lambda msg, kind, *_: got.append(msg))
    except Exception:
        return None, fn()
    try:
        out = fn()
    finally:
        try:
            om1.MMessage.removeCallback(cb)
        except Exception:
            pass
    return [g for g in got if "zero" in g.lower() or "warning" in g.lower()], out


def zero_threshold(rep):
    """Below which divisor does a multiplyDivide warn 'divide by zero'? (5.6.43: 0.000001 did.)"""
    out = []
    for d in (1e-6, 5e-6, 1e-5, 2e-5, 1e-4, 1e-3):
        md = cmds.createNode("multiplyDivide")
        cmds.setAttr(md + ".operation", 2)
        cmds.setAttr(md + ".input1X", 0.0)
        cmds.setAttr(md + ".input2X", d)
        t = cmds.createNode("transform")
        cmds.connectAttr(md + ".outputX", t + ".translateX")
        warned, _ = _warnings_while(lambda: cmds.getAttr(t + ".translateX"))
        out.append("%g: %s" % (d, "warns" if warned else ("?" if warned is None else "quiet")))
        cmds.delete(md, t)
    rep.add(INFO, "multiplyDivide 'divide by zero' by divisor", ", ".join(out))


def empty_ls(rep):
    n = len(cmds.ls([]) or [])
    rep.add(INFO, "cmds.ls([]) - an empty list", "lists %d node(s)%s" % (n, " (EVERYTHING)" if n else " (nothing)"))
    m = cmds.polyCube(constructionHistory=False)[0]          # 5.6.47: with flags (the onion skin's real case?)
    for label, kw in (("type='mesh'", dict(type="mesh")), ("long=True", dict(long=True)),
                      ("dag=True", dict(dag=True)), ("objectsOnly=True", dict(objectsOnly=True))):
        try:
            got = cmds.ls([], **kw) or []
            rep.add(INFO, "cmds.ls([], %s)" % label, "lists %d node(s)" % len(got))
        except Exception as e:
            rep.add(INFO, "cmds.ls([], %s)" % label, "%s: %s" % (type(e).__name__, e))
    try:
        got = cmds.listRelatives([], allDescendents=True) or []
        rep.add(INFO, "cmds.listRelatives([], allDescendents=True)", "lists %d node(s)" % len(got))
    except Exception as e:
        rep.add(INFO, "cmds.listRelatives([], allDescendents=True)", "%s: %s" % (type(e).__name__, e))
    cmds.delete(m)


def undo_state(rep):
    rep.add(INFO, "undo on / batch (no window)", "%s / %s" % (cmds.undoInfo(query=True, state=True),
                                                              cmds.about(batch=True)))


def key_moves(rep):
    """What refuses 'keyframe -edit -relative -timeChange'? (5.6.44: 'Cannot move keys'.)"""
    t = cmds.createNode("transform")
    for f in (1, 2, 5):
        cmds.setKeyframe(t, attribute="translateX", time=f, value=f)
    curve = cmds.listConnections(t + ".translateX", source=True, destination=False)[0]
    said = []
    for label, kw in (("over a key that stays (default option)", dict(time=(2, 2), timeChange=3)),
                      ("over a key that stays (option over)", dict(time=(2, 2), timeChange=3, option="over"))):
        try:
            cmds.keyframe(curve, edit=True, relative=True, **kw)
            said.append("%s: moved, now %s" % (label, cmds.keyframe(curve, query=True, timeChange=True)))
        except RuntimeError as e:
            said.append("%s: %s" % (label, str(e).strip()))
        cmds.undo() if cmds.undoInfo(query=True, state=True) else None
    for label, fn in (("a locked channel (setAttr -lock)", lambda: cmds.setAttr(t + ".translateX", lock=True)),):
        fn()                                                 # 5.6.47: what refused in Gus's shot?
        try:
            cmds.keyframe(curve, edit=True, relative=True, time=(4, 10), timeChange=1, option="over")
            said.append("%s: moved" % label)
        except RuntimeError as e:
            said.append("%s: %s" % (label, str(e).strip()))
        cmds.setAttr(t + ".translateX", lock=False)
    try:                                                     # a curve in an animation layer
        layer = cmds.animLayer("gusFactsLayer")
        cmds.animLayer(layer, edit=True, attribute=t + ".translateY")
        cmds.setKeyframe(t, attribute="translateY", time=1, value=1, animLayer=layer)
        cmds.setKeyframe(t, attribute="translateY", time=5, value=2, animLayer=layer)
        lc = [c for c in cmds.ls(type="animCurve") or [] if "gusFactsLayer" in c] or []
        if lc:
            cmds.keyframe(lc[0], edit=True, relative=True, time=(4, 10), timeChange=1, option="over")
            said.append("a curve in an animation layer: moved")
        else:
            said.append("a curve in an animation layer: (no curve found to try)")
    except RuntimeError as e:
        said.append("a curve in an animation layer: %s" % str(e).strip())
    try:                                                     # a time range that holds no key
        cmds.keyframe(curve, edit=True, relative=True, time=(100, 200), timeChange=1, option="over")
        said.append("a time range with no keys: no error")
    except RuntimeError as e:
        said.append("a time range with no keys: %s" % str(e).strip())
    cmds.lockNode(curve, lock=True)
    try:
        cmds.keyframe(curve, edit=True, relative=True, time=(4, 10), timeChange=1, option="over")
        said.append("a locked curve: moved (lockNode doesn't stop it)")
    except RuntimeError as e:
        said.append("a locked curve: %s" % str(e).strip())
    cmds.lockNode(curve, lock=False)
    cmds.delete(t)
    for s in said:
        rep.add(INFO, "moving keys", s)


def mesh_points(rep):
    """5.6.47 (shape editor: fit to the body, lie on the skin): the nearest point and its normal on a mesh."""
    import maya.api.OpenMaya as om
    m = cmds.polySphere(radius=2, constructionHistory=False)[0]
    sel = om.MSelectionList()
    sel.add(cmds.listRelatives(m, shapes=True, fullPath=True)[0])
    fn = om.MFnMesh(sel.getDagPath(0))
    p, nrm, _face = None, None, None
    try:
        p, nrm, _face = fn.getClosestPointAndNormal(om.MPoint(5, 0, 0), om.MSpace.kWorld)
        rep.add(INFO, "the nearest point on a mesh (radius 2 sphere, from x=5)",
                "%s, normal %s" % ([round(v, 3) for v in (p.x, p.y, p.z)], [round(v, 3) for v in (nrm.x, nrm.y, nrm.z)]))
    except Exception as e:
        rep.add(INFO, "the nearest point on a mesh", "%s: %s" % (type(e).__name__, e))
    try:
        hit = fn.closestIntersection(om.MFloatPoint(0, 0, 0), om.MFloatVector(0, 0, 1), om.MSpace.kWorld, 100, False)
        rep.add(INFO, "a ray from the centre along +Z hits the mesh at", str([round(v, 3) for v in hit[0]][:3]))
    except Exception as e:
        rep.add(INFO, "a ray along +Z", "%s: %s" % (type(e).__name__, e))
    cmds.delete(m)


def controllers(rep):
    a = cmds.circle(constructionHistory=False)[0]
    b = cmds.circle(constructionHistory=False)[0]
    b = cmds.parent(b, a)[0]
    try:
        cmds.controller(a)
        cmds.controller(b)
        cmds.controller(b, a, parent=True)
        got = cmds.controller(b, query=True, parent=True)
        rep.add(INFO, "controller -query -parent answers", "%r (%s)" % (got, type(got).__name__))
        rep.add(INFO, "the tag node of a control", str(cmds.listConnections(a + ".message", type="controller")))
    except Exception as e:
        rep.add(INFO, "controllers", "%s: %s" % (type(e).__name__, e))
    cmds.delete(a)


def bookmarks(rep):
    try:
        if not cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True):
            cmds.loadPlugin("timeSliderBookmark", quiet=True)
        import maya.plugin.timeSliderBookmark.timeSliderBookmark as tsb
        b = tsb.createBookmark(name="gusFactsCheck", start=1, stop=5, color=(1, 0, 0))
        rep.add(INFO, "Time Slider bookmarks", "made: %s; its name attribute: %r" % (
            b, cmds.getAttr(b + ".name") if b and cmds.objExists(b) else None))
        if b and cmds.objExists(b):
            cmds.delete(b)
    except Exception as e:
        rep.add(INFO, "Time Slider bookmarks", "%s: %s" % (type(e).__name__, e))


def node_types(rep):
    have = [t for t in ("blendMatrix", "multMatrix", "pickMatrix", "aimMatrix", "uvPin", "proximityPin")
            if t in (cmds.allNodeTypes() or [])]
    rep.add(INFO, "matrix / pin nodes this Maya has", ", ".join(have))


def curve_replace(rep):
    """5.6.48 (other rigs' controls, referenced or locked): can a control's curve be deleted, and can it be rebuilt in
    place with 'curve -replace' - plain, with history, locked (lockNode), from a referenced file?"""
    import os
    import tempfile
    square = dict(degree=1, point=[(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1), (-1, 0, -1)])

    def try_it(label, ctrl):
        shape = cmds.listRelatives(ctrl, shapes=True, fullPath=True)[0]
        try:
            cmds.curve(shape, replace=True, **square)
            got = "rebuilt: %d CVs now" % len(cmds.ls(shape + ".cv[*]", flatten=True) or [])
        except Exception as e:
            got = "REFUSED (%s)" % str(e).strip().splitlines()[0]
        try:
            cmds.delete(cmds.listRelatives(ctrl, shapes=True, fullPath=True)[0])
            gone = "can be deleted"
        except Exception as e:
            gone = "can't be deleted (%s)" % str(e).strip().splitlines()[0]
        rep.add(INFO, "curve -replace: " + label, "%s; the curve %s" % (got, gone))

    plain = cmds.circle(constructionHistory=False)[0]
    try_it("a plain control", plain)
    hist = cmds.circle(constructionHistory=True)[0]
    try_it("a control with history (makeNurbCircle)", hist)
    locked = cmds.circle(constructionHistory=False)[0]
    cmds.lockNode(cmds.listRelatives(locked, shapes=True, fullPath=True)[0], lock=True)
    try_it("a locked curve (lockNode)", locked)
    for sh in cmds.listRelatives(locked, shapes=True, fullPath=True) or []:
        cmds.lockNode(sh, lock=False)
    for n in (plain, hist, locked):
        if cmds.objExists(n):
            cmds.delete(n)
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "gus_fact_ctrl.ma").replace("\\", "/")
    try:
        c = cmds.circle(name="factRef_ctrl", constructionHistory=False)[0]
        cmds.select(c, replace=True)
        cmds.file(path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(c)
        cmds.file(path, reference=True, namespace="gusFact")
        try_it("a control from a referenced file", "gusFact:factRef_ctrl")
        cmds.file(path, removeReference=True)
    except Exception as e:
        rep.add(INFO, "curve -replace: a control from a referenced file", "%s: %s" % (type(e).__name__, e))
    finally:
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass


def loft_curves(rep):
    """5.7.4 (Face and Ribbon from two curves): the curve commands the tool uses - a point a fraction along a curve,
    a closed curve made from points, turning a curve round, a loft between two curves under a moved group."""
    import math
    arc = cmds.curve(degree=3, editPoint=[(math.cos(a), math.sin(a), 0) for a in (0, 0.8, 1.6, 2.4, 3.14159)],
                     name="gusFact_arc")
    try:
        mid = cmds.pointOnCurve(arc, parameter=0.5, turnOnPercentage=True, position=True)
        rep.add(INFO, "pointOnCurve: half way along a half circle (percentage on)",
                "[%.3f, %.3f, %.3f] - expected about [0, 1, 0]" % tuple(mid))
        start = cmds.pointOnCurve(arc, parameter=0.0, turnOnPercentage=True, position=True)
        cmds.reverseCurve(arc, constructionHistory=False, replaceOriginal=True)
        start2 = cmds.pointOnCurve(arc, parameter=0.0, turnOnPercentage=True, position=True)
        rep.add(INFO, "reverseCurve -replaceOriginal: where it starts, before / after",
                "[%.2f, %.2f, %.2f] / [%.2f, %.2f, %.2f]" % (tuple(start) + tuple(start2)))
        pts = [(math.cos(2 * math.pi * i / 8), math.sin(2 * math.pi * i / 8), 0) for i in range(8)]
        loop = cmds.curve(degree=3, periodic=True, point=pts + pts[:3], knot=list(range(-2, 8 + 3)), name="gusFact_loop")
        shape = cmds.listRelatives(loop, shapes=True, fullPath=True)[0]
        rep.add(INFO, "a closed curve from 8 points (periodic, the first 3 again)",
                "form %s (2 = periodic), %d spans" % (cmds.getAttr(shape + ".form"), cmds.getAttr(shape + ".spans")))
        grp = cmds.group(empty=True, name="gusFact_moved")
        cmds.move(0, 10, 0, grp)
        a = cmds.curve(degree=1, point=[(0, 0, 0), (4, 0, 0)], name="gusFact_a")
        b = cmds.curve(degree=1, point=[(0, 1, 0), (4, 1, 0)], name="gusFact_b")
        cmds.parent(a, b, grp, relative=True)
        srf = cmds.loft(a, b, degree=1, uniform=True, constructionHistory=False, name="gusFact_loft")[0]
        box = cmds.exactWorldBoundingBox(srf)
        rep.add(INFO, "loft of two curves under a group moved 10 up: the surface's height",
                "%.2f to %.2f (10 to 11 = it uses where the curves are in the world)" % (box[1], box[4]))
        for n in (srf, grp, loop):
            cmds.delete(n)
    finally:
        if cmds.objExists(arc):
            cmds.delete(arc)


FACTS = [zero_threshold, empty_ls, undo_state, key_moves, mesh_points, controllers, bookmarks, node_types,
         curve_replace, loft_curves]


def facts(rep):
    rep.start("Maya facts (how Maya really behaves - info only)")
    rep.add(INFO, "Maya", "%s, %s" % (cmds.about(version=True), cmds.about(operatingSystem=True)))
    for fn in FACTS:
        rep.guard(fn.__name__, fn, rep)


def text():
    rep = Report("Maya facts")
    facts(rep)
    return rep.text()
