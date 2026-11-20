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


FACTS = [zero_threshold, empty_ls, undo_state, key_moves, controllers, bookmarks, node_types]


def facts(rep):
    rep.start("Maya facts (how Maya really behaves - info only)")
    rep.add(INFO, "Maya", "%s, %s" % (cmds.about(version=True), cmds.about(operatingSystem=True)))
    for fn in FACTS:
        rep.guard(fn.__name__, fn, rep)


def text():
    rep = Report("Maya facts")
    facts(rep)
    return rep.text()
