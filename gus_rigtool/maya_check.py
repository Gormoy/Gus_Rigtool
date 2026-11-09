"""
The Maya check: runs the main features of Gus_Rigtool and every action of Gus Animtool inside Maya, and writes
a report (what worked, what failed, with the errors) - the things the offline tests can't see.

    import gus_rigtool.maya_check as mc; mc.run()

It opens NEW scenes (it asks first, so you can save). Takes a minute or two. Send the report it shows (also saved
as gus_maya_check.txt in Maya's temp folder) to get anything that failed fixed.
"""

import os
import sys
import tempfile

import time

import math

import maya.cmds as cmds

from gus_rigtool.core import nodes as _nodes

import gus_rigtool

from gus_rigtool.core.report import FAIL, NOTE, OK, Report
from gus_rigtool.core.report import tb as _tb

SKIP_ACTIONS = {"update": "installs a zip", "reload": "reloads the tools", "playblast": "writes a movie (slow)",
                "blast_50": "writes a movie (slow)", "blast_100": "writes a movie (slow)"}


class _Quiet(object):
    """No dialogs while checking: confirm -> its default button, prompts -> Cancel, file pickers -> nothing."""
    def __enter__(self):
        self.saved = {n: getattr(cmds, n) for n in ("confirmDialog", "promptDialog", "fileDialog2")}

        def confirm(*a, **k):
            if k.get("query"):
                return ""
            return k.get("defaultButton") or (k.get("button") or ["OK"])[0]
        cmds.confirmDialog = confirm
        cmds.promptDialog = lambda *a, **k: "" if k.get("query") else "Cancel"
        cmds.fileDialog2 = lambda *a, **k: None
        return self

    def __exit__(self, *exc):
        for n, f in self.saved.items():
            setattr(cmds, n, f)


# ---------------------------------------------------------------------------
# parts
# ---------------------------------------------------------------------------

def _new_scene():
    cmds.file(new=True, force=True)


def _test_mesh(height):
    """A box around the skeleton, symmetric in X, enough points to skin."""
    from gus_rigtool.core import skin_tools
    joints = skin_tools.rig_joints()
    pts = [cmds.xform(j, query=True, worldSpace=True, translation=True) for j in joints]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    w = max(abs(lo[0]), abs(hi[0])) * 2 + height * 0.05
    mesh = cmds.polyCube(name="gusCheck_body", width=w, height=hi[1] - lo[1] + height * 0.05,
                         depth=hi[2] - lo[2] + height * 0.05, subdivisionsX=12, subdivisionsY=30,
                         subdivisionsZ=8)[0]
    cmds.xform(mesh, worldSpace=True, translation=(0, (hi[1] + lo[1]) / 2.0, (hi[2] + lo[2]) / 2.0))
    cmds.makeIdentity(mesh, apply=True, translate=True)
    return mesh


def _qt():
    try:
        from PySide6 import QtCore, QtWidgets
        from shiboken6 import wrapInstance
    except ImportError:
        from PySide2 import QtCore, QtWidgets
        from shiboken2 import wrapInstance
    return QtCore, QtWidgets, wrapInstance


def _cut(ctrl):
    """None if the control shows whole, else how it's cut (a layout around it too small). Scrolling doesn't count.
    A control Maya deleted meanwhile (a page rebuilt) counts as fine."""
    try:
        return _cut_now(ctrl)
    except RuntimeError:                    # "Internal C++ object ... already deleted"
        return None


def _cut_now(ctrl):
    import maya.OpenMayaUI as omui
    QtCore, QtWidgets, wrap = _qt()
    ptr = omui.MQtUtil.findControl(ctrl)
    if not ptr:
        return None
    w = wrap(int(ptr), QtWidgets.QWidget)
    if not w.isVisible():
        return None
    p = w.parentWidget()
    while p is not None:
        up = p.parentWidget()
        if up is not None and isinstance(up.parentWidget(), QtWidgets.QAbstractScrollArea):
            break                                       # p is what scrolls: being off screen is fine
        r = QtCore.QRect(w.mapTo(p, QtCore.QPoint(0, 0)), w.size())
        if r.bottom() > p.height() + 1 or r.right() > p.width() + 1:
            return "%d of %d px high and %d of %d px wide shown" % (
                max(0, min(r.bottom(), p.height()) - r.top()), w.height(),
                max(0, min(r.right(), p.width()) - r.left()), w.width())
        p = up
    return None


def _page_layout(key):
    from gus_rigtool import registry
    from gus_rigtool.core import ui
    cat, _l = registry.category_of(key)
    keys = dict((c, k) for c, _l, k in registry.CATEGORIES)[cat]
    kids = ui._children(ui._tool_tabs(cat))
    return kids[keys.index(key)] if len(kids) > keys.index(key) else None


def _cut_buttons(key, expand=False):
    """[(button label, how it's cut)] on a tool page (expand: open every section first)."""
    from gus_rigtool.core import ui
    _QtCore, QtWidgets, _w = _qt()
    ui.go_to_tool(key)
    page = _page_layout(key)
    if not page:
        return []
    if expand:
        for c in ui.walk(page):
            try:
                if cmds.objectTypeUI(c) == "frameLayout":
                    cmds.frameLayout(c, edit=True, collapse=False)
            except RuntimeError:
                continue
    for _i in range(3):
        QtWidgets.QApplication.processEvents()
    out = []
    for c in ui.walk(page):
        try:
            if not cmds.control(c, exists=True):
                continue                    # gone since the walk (the page was rebuilt)
            kind = cmds.objectTypeUI(c)
        except RuntimeError:
            continue
        if kind in ("button", "checkBox", "optionMenu", "iconTextButton"):
            how = _cut(c)
            if how:
                label = ""
                try:
                    label = cmds.control(c, query=True, annotation=True) if kind != "button" \
                        else cmds.button(c, query=True, label=True)
                except RuntimeError:
                    pass
                out.append((label or c.split("|")[-1], how))
    return out


def _check_cut_buttons(rep):
    """Every button shows whole: Settings with every section open, the other pages as they open."""
    from gus_rigtool import registry
    try:
        _qt()
    except ImportError:
        rep.add(NOTE, "buttons shown whole", "no Qt here: not checked")
        return
    cut = _cut_buttons("settings", expand=True)
    rep.expect("Settings, every section open: no button cut off", not cut,
               "; ".join("'%s' %s" % c for c in cut[:8]))
    others = []
    for key, label, _m, _s in registry.TOOLS:
        if key == "settings":
            continue
        try:
            got = _cut_buttons(key)
        except Exception:
            continue
        others += ["%s: '%s' %s" % (label, b, how) for b, how in got]
    rep.expect("every other page (sections as they open): no button cut off", not others, "; ".join(others[:12]))


def check_windows(rep):
    from gus_rigtool import registry
    from gus_rigtool.core import ui
    rep.start("Gus_Rigtool windows (every tool page builds)")
    errors = []
    real = ui.report_error
    ui.report_error = lambda e, where="": errors.append((where, e, _tb()))
    try:
        t0 = time.time()
        rep.step("main window", ui.open_panel, ui.MAIN_KEY)
        opened = time.time() - t0
        rep.expect("main window opens in under 1.5 s (pages build when shown)", opened < 1.5, "%.2fs" % opened)
        rep.step("every page built (as when you use them all)", ui.build_all_pages)
        for key, label, _m, _s in registry.TOOLS:
            mine = [e for e in errors if e[0].strip("_").endswith(key)]
            rep.add(FAIL if mine else OK, "page: %s" % label,
                    "; ".join("%s\n%s" % (e[1], e[2]) for e in mine))
        rep.step("Guide window", lambda: __import__("gus_rigtool.tools.guide", fromlist=["x"]).show())
        rep.step("Guide as a web page", lambda: __import__("gus_rigtool.tools.guide", fromlist=["x"]).export_html(
            os.path.join(tempfile.gettempdir(), "gus_guide_check.html")))
        for key in ("build", "skin", "checker", "home"):
            rep.step("go to %s" % key, ui.go_to_tool, key)
        rep.guard("button check", _check_cut_buttons, rep)
    finally:
        ui.report_error = real
    left = [e for e in errors if not any(e[0].strip("_").endswith(k) for k, _l, _m, _s in registry.TOOLS)]
    for where, e, tb in left:
        rep.add(FAIL, "window error (%s)" % where, "%s\n%s" % (e, tb))


def check_rig(rep, kind, height):
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import publish
    rep.start("%s rig: build, skin, rebuild, publish" % kind)
    _new_scene()
    if kind == "biped":
        rep.step("biped template", bld.biped, height)
    else:
        rep.step("quadruped template", bld.quadruped, height)
    rep.step("build", bld.build_all, height)
    joints = rep.step("rig joints", lambda: len(__import__("gus_rigtool.core.skin_tools", fromlist=["x"])
                                                .rig_joints()))
    if not joints:
        return None
    mesh = rep.step("test mesh", _test_mesh, height)
    if not mesh:
        return None
    from gus_rigtool.core import joint_labels, skin_io, skin_tools
    rep.step("label joints", joint_labels.label, skin_tools.rig_joints())
    rep.step("bind", skin_tools.bind, [mesh])
    rep.step("joints with no twin", lambda: len([x for x in joint_labels.not_mirrored()]))
    path = os.path.join(tempfile.gettempdir(), "gus_check_weights.json")
    rep.step("export weights", skin_io.export_file, path, [mesh])
    rep.step("import weights", skin_io.import_file, path, {"gusCheck_body": mesh})
    cmds.select(mesh, replace=True)
    from gus_rigtool.core import skin_mirror
    rep.step("mirror weights L>R", skin_mirror.mirror_weights, "L>R")
    if kind == "biped":
        check_fixes(rep, mesh)
    rep.step("back to guides (keeps the skin)", bld.back_to_guides, True)
    rep.step("build again", bld.build_all, height)
    rep.step("still skinned after rebuild", lambda: bool(skin_io.skin_of(mesh)) or _raise("the skin is gone"))
    rep.step("publish", publish.publish)
    rep.step("check the rig", lambda: publish.check()[:2])
    from gus_rigtool.builder import deliver
    rep.step("deliver to a folder", lambda: deliver.deliver(os.path.join(tempfile.gettempdir(),
                                                                       "gus_check_delivery"), "check")["fails"])
    rep.step("unpublish", publish.unpublish)
    rep.step("publish again", publish.publish)
    return mesh


def check_fixes(rep, mesh):
    """Fixes on the test mesh: bend the left elbow, sculpt, apply; on at the pose, off at rest; mirror; delete."""
    from gus_rigtool.core import shape_fixes as F
    ctrl = (cmds.ls("L_radius_FK_ctrl", long=True) or [None])[0]
    joint = (cmds.ls("L_radius_jnt", long=True) or [None])[0]
    if not ctrl or not joint:
        rep.add(NOTE, "fixes", "skipped: no L_radius_FK_ctrl / L_radius_jnt")
        return
    for a in ("rotateY", "rotateZ"):
        try:
            cmds.setAttr(ctrl + "." + a, 70)
            break
        except RuntimeError:
            continue
    sculpt = rep.step("fixes: sculpt copy", F.start, mesh, joint, "L_elbow_check")
    if not sculpt:
        return
    cmds.move(0, 1.0, 0, sculpt + ".vtx[0:20]", relative=True)
    name = rep.step("fixes: apply", F.apply, sculpt)
    if not name:
        return
    on = [w for n, _j, _a, w in F.listing(mesh) if n == name]
    rep.add(OK if on and on[0] > 0.95 else FAIL, "fixes: on at the sculpted bend", "weight %.3f" % (on[0] if on else -1))
    for a in ("rotateX", "rotateY", "rotateZ"):
        try:
            cmds.setAttr(ctrl + "." + a, 0)
        except RuntimeError:
            pass
    off = [w for n, _j, _a, w in F.listing(mesh) if n == name]
    rep.add(OK if off and off[0] < 0.05 else FAIL, "fixes: off at rest", "weight %.3f" % (off[0] if off else -1))
    twin = rep.step("fixes: mirror", F.mirror, mesh, name)
    for n in (name, twin):
        if n:
            rep.step("fixes: delete %s" % n, F.remove, mesh, n)


def _raise(text):
    raise RuntimeError(text)


def check_selftest(rep, height):
    from gus_rigtool.builder import selftest
    rep.start("Rig quality (self-test: Maya solves the rig)")
    try:
        sections = selftest.run(height)
    except Exception as e:
        rep.add(FAIL, "self-test", "%s\n%s" % (e, _tb()))
        return
    text = selftest.report(sections) if not isinstance(sections, str) else sections
    for line in str(text).splitlines():
        line = line.strip()
        if line.startswith("FAIL"):
            rep.add(FAIL, line[4:].strip())
        elif line.startswith("PASS"):
            rep.add(OK, line[4:].strip())


def _animtool():
    try:
        import gus_animtool
        return gus_animtool
    except ImportError:
        path = os.path.join(gus_rigtool.ROOT, "anim")
        if path not in sys.path:
            sys.path.append(path)
        import gus_animtool
        return gus_animtool


def check_animtool(rep):
    rep.start("Gus Animtool: windows and every action (on the published biped)")
    ga = rep.step("import Gus Animtool", _animtool)
    if not ga:
        return
    from gus_animtool import actions as AC
    from gus_animtool import anim as A
    rep.step("main window", ga.show)
    rep.step("toolbar under the Time Slider", lambda: __import__("gus_animtool.toolbar", fromlist=["x"]).show())
    rep.step("Time Slider menu hooked", lambda: __import__("gus_animtool.timeslider", fromlist=["x"]).install())
    ctrls = A.character_controls()
    rep.add(OK if ctrls else FAIL, "character controls found", "%d" % len(ctrls))
    if not ctrls:
        return
    arm = [c for c in ctrls if "arm" in c.lower() and "fk" in c.lower()][:2] or ctrls[:2]
    for f, v in ((1, 0.0), (12, 30.0), (24, 0.0)):
        for c in arm:
            for a in ("rotateX", "rotateZ"):
                try:
                    cmds.setKeyframe(c, attribute=a, time=f, value=v)
                except RuntimeError:
                    pass
    cmds.playbackOptions(minTime=1, maxTime=24)
    keys = [k for k, _l, _t, _g in AC.ACTIONS]
    keys += [k for items in AC.MENUS.values() for _lbl, k in items if k not in keys]
    body_times = []
    for key in keys:
        if key in SKIP_ACTIONS:
            rep.add(NOTE, "action %s" % key, "skipped: %s" % SKIP_ACTIONS[key])
            continue
        cmds.select(arm, replace=True)
        cmds.currentTime(12)
        t0 = time.time()
        rep.step("action %s" % key, AC._call, key)
        if key.startswith(("iso_", "hide_")):
            body_times.append((time.time() - t0, key))
        try:
            cmds.undoInfo(closeChunk=True)                  # in case an action left one open
        except RuntimeError:
            pass
    if body_times:
        worst = max(body_times)
        rep.expect("hide / isolate a body part: under 1 s each", worst[0] < 1.0,
                   "slowest %s %.1fs" % (worst[1], worst[0]))
    cmds.select(arm, replace=True)
    rep.step("undo still works", cmds.undo)


# ---------------------------------------------------------------------------
# recent features - Maya solves them (constraints, skin, follows): what the offline tests can't measure
# ---------------------------------------------------------------------------

def _om():
    import maya.api.OpenMaya as om
    return om


def _L(name):
    """Long name of a node by its (unique) short name, or the name itself if it is already a path."""
    got = cmds.ls(name, long=True) or []
    return got[0] if got else name


def _wm(n):
    return _om().MMatrix(cmds.xform(_L(n), query=True, worldSpace=True, matrix=True))


def _p(n):
    m = cmds.xform(_L(n), query=True, worldSpace=True, matrix=True)
    return _om().MVector(m[12], m[13], m[14])


def _turn(m0, m1):
    """The world-space turn from m0 to m1 (works with -1 scale too)."""
    om = _om()
    return om.MTransformationMatrix(m0.inverse() * m1).rotation(asQuaternion=True)


def _same_turn(a0, a1, b0, b1, tol=1e-3):
    qa, qb = _turn(a0, a1), _turn(b0, b1)
    return abs(abs(qa.x * qb.x + qa.y * qb.y + qa.z * qb.z + qa.w * qb.w) - 1.0) < tol


def _angle(m0, m1):
    import math
    q = _turn(m0, m1)
    return math.degrees(2.0 * math.acos(min(1.0, abs(q.w))))


def _mat_close(a, b, tol=1e-3):
    return all(abs(a.getElement(r, c) - b.getElement(r, c)) < tol for r in range(4) for c in range(4))


def _vec(v):
    return "(%.3f, %.3f, %.3f)" % (v.x, v.y, v.z)


def _surf_pts(srf):
    """World CV positions of the ribbon as it is deformed now: the visible (deformed) shape's CVs, through cmds so
    Maya evaluates it first."""
    om = _om()
    shapes = [x for x in cmds.listRelatives(_L(srf), shapes=True, fullPath=True) or []
              if not cmds.getAttr(x + ".intermediateObject")]
    flat = cmds.xform((shapes[0] if shapes else _L(srf)) + ".cv[*][*]", query=True, worldSpace=True,
                      translation=True) or []
    return [om.MVector(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat) - 2, 3)]


def _moved(a, b):
    return max((x - y).length() for x, y in zip(a, b)) if a and b else 0.0


def _loop_ribbon(name, radius, centre):
    """A ribbon round a loop (like a mouth), facing +Z."""
    c = cmds.circle(name=name + "_crv", normal=(0, 0, 1), radius=radius, sections=16, degree=3,
                    constructionHistory=False)[0]
    a, b = cmds.duplicate(c)[0], cmds.duplicate(c)[0]
    for crv, k in ((a, 0.85), (b, 1.15)):
        cmds.scale(k, k, k, crv)
        cmds.makeIdentity(crv, apply=True, scale=True)
    srf = cmds.loft(a, b, degree=1, uniform=True, constructionHistory=False, name=name)[0]
    cmds.delete(c, a, b)
    cmds.move(centre[0], centre[1], centre[2], srf)
    cmds.makeIdentity(srf, apply=True, translate=True)
    # left as lofted (runs along V): the build has to turn it
    return srf.split("|")[-1]                   # short: the build regroups it


def _strip_ribbon(name, centre, width=6.0):
    """An open ribbon along X (like a lid or a brow), facing +Z."""
    xs = [width * (i / 6.0 - 0.5) for i in range(7)]
    curves = []
    for dy in (-0.25, 0.25):
        curves.append(cmds.curve(degree=3, point=[(x + centre[0], centre[1] + dy, centre[2]) for x in xs]))
    srf = cmds.loft(curves[0], curves[1], degree=1, uniform=True, constructionHistory=False, name=name)[0]
    cmds.delete(curves)
    # left as lofted (runs along V): the build has to turn it
    return srf.split("|")[-1]


def _build_ribbon(srf, prefix, **kw):
    from gus_rigtool.core import ribbon
    ribbon.build_rig(surface=srf, prefix=prefix, num_follicles=12, ctrl_mode="every", ctrl_every=2,
                     include_ends=False, distribution="length", ctrl_radius=0.3, ctrl_distance=0.5,
                     dir_axis="Z", face_axis="Z", fol_jnt_radius=0.1, bind_jnt_radius=0.15, **kw)
    return len(_ribbon_ctrls(srf))


def _spread(srf, ctrls):
    """How far the controls spread, against the ribbon's long side (about 0.7+ when spread along it)."""
    bb = cmds.exactWorldBoundingBox(_L(srf))
    longest = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], 1e-6)
    pts = [_p(c) for c in ctrls]
    far = max([(a - b).length() for a in pts for b in pts] or [0.0])
    return far / longest


def _ribbon_ctrls(srf):
    from gus_rigtool.core import ribbon, utils
    builds = ribbon._find_builds()
    key = ribbon._resolve(_L(srf))
    if key not in builds:
        return []
    ctrls = [ribbon._control_under(o) for _i, o in sorted(ribbon._build_offsets(builds[key]).items())]
    return [utils.uuid(c) for c in ctrls if c]


def _paths(ids):
    from gus_rigtool.core import utils
    return [p for p in (utils.path(i) for i in ids) if p]


def check_ribbons(rep):
    from gus_rigtool.core import ribbon
    rep.start("Ribbons: pivot on the shape, constraints, switch, mirror sides")
    _new_scene()
    srf = rep.step("loop ribbon (like a mouth)", _loop_ribbon, "chkMouth_ribbon", 3.0, (0.0, 0.0, 0.0))
    if not srf or not rep.step("build: pivot on the control shape", _build_ribbon, srf, "chkMouth",
                               pivot_on_shape=True):
        return
    ids = _ribbon_ctrls(srf)
    modes = sorted({ribbon.bind_of(c)[1] for c in _paths(ids)})
    sp = _spread(srf, _paths(_ribbon_ctrls(srf)))
    rep.expect("loop ribbon: the controls spread round it (built along its length)", sp > 0.6,
               "spread %.2f of its size; %s" % (sp, "runs along V" if ribbon.runs_along_v(srf) else "runs along U"))
    rep.expect("bind joints follow by point + orient constraints (no direct links)", modes == ["constraints"],
               "modes: %s" % modes)
    c = max(_paths(ids), key=lambda n: _p(n).x)
    j = ribbon.bind_of(c)[0]
    if not j:
        rep.add(FAIL, "bind joint of %s" % c.split("|")[-1], "none found")
        return
    jid = __import__("gus_rigtool.core.utils", fromlist=["x"]).uuid(j)
    J = lambda: _paths([jid])[0]
    pts0, c0, j0, cw0, jw0 = _surf_pts(srf), _p(c), _p(j), _wm(c), _wm(j)
    cmds.setAttr(c + ".translateY", 0.4)
    d = (_p(J()) - j0) - (_p(c) - c0)
    rep.expect("move a control: its joint moves the same", d.length() < 1e-3, "difference %s" % _vec(d))
    rep.expect("the ribbon follows (skin)", _moved(pts0, _surf_pts(srf)) > 0.05,
               "ribbon moved %.3f" % _moved(pts0, _surf_pts(srf)))
    cmds.setAttr(c + ".translateY", 0)
    cmds.setAttr(c + ".rotateZ", 30)
    rep.expect("rotate a control: its joint turns in place (no swing round the shape)",
               (_p(J()) - j0).length() < 1e-3, "joint moved %.4f" % (_p(J()) - j0).length())
    rep.expect("... and by the same turn as the control", _same_turn(cw0, _wm(c), jw0, _wm(J())),
               "control %.2f deg, joint %.2f deg" % (_angle(cw0, _wm(c)), _angle(jw0, _wm(J()))))
    cmds.setAttr(c + ".rotateZ", 0)
    grp = cmds.ls("chkMouth_ctrls_grp", long=True) or []
    if grp:
        holder = cmds.group(empty=True, name="chk_holder")
        cmds.parent(grp[0], holder)
        cmds.setAttr(holder + ".translateX", 2.0)
        moved = _p(J()) - j0
        rep.expect("parent the controls' group and move it: the joints come along",
                   abs(moved.x - 2.0) < 1e-3 and abs(moved.y) < 1e-3, "joint moved %s" % _vec(moved))
        cmds.setAttr(holder + ".translateX", 0.0)
    # one ribbon round both sides: the right side mirrors the left
    pts0 = _surf_pts(srf)
    rep.step("make the right side mirror the left", ribbon.mirror_sides, srf)
    rep.expect("mirror sides: nothing moved", _moved(pts0, _surf_pts(srf)) < 1e-3,
               "ribbon moved %.4f" % _moved(pts0, _surf_pts(srf)))
    ctrls = _paths(ids)
    c = max(ctrls, key=lambda n: _p(n).x)
    q = _p(c)
    rights = [n for n in ctrls if _p(n).x < -1e-3]
    if rights:
        r = min(rights, key=lambda n: (_p(n) - _om().MVector(-q.x, q.y, q.z)).length())
        a0, b0 = _p(c), _p(r)
        for n in (c, r):
            cmds.setAttr(n + ".translateX", 0.3)
            cmds.setAttr(n + ".translateY", 0.2)
        da, db = _p(c) - a0, _p(r) - b0
        rep.expect("mirror sides: the same values move both sides as mirror images",
                   abs(da.x + db.x) < 1e-3 and abs(da.y - db.y) < 1e-3 and abs(da.z - db.z) < 1e-3,
                   "left %s, right %s" % (_vec(da), _vec(db)))
        for n in (c, r):
            cmds.setAttr(n + ".translateX", 0)
            cmds.setAttr(n + ".translateY", 0)
    # an old style build (joints copy their controls, scale too): Switch to constraints
    strip = rep.step("open ribbon (like a lid)", _strip_ribbon, "chkLid_ribbon", (0.0, 6.0, 0.0))
    if not strip or not rep.step("build: pivot on the shape + scale controls (direct links)", _build_ribbon,
                                 strip, "chkLid", pivot_on_shape=True, pivot_scale=True):
        return
    lids = _ribbon_ctrls(strip)
    sp = _spread(strip, _paths(lids))
    rep.expect("open ribbon: the controls spread along it (built along its length)", sp > 0.6,
               "spread %.2f of its length; %s" % (sp, "runs along V" if ribbon.runs_along_v(strip) else
                                                   "runs along U"))
    modes = sorted({ribbon.bind_of(x)[1] for x in _paths(lids)})
    rep.expect("scale controls: joints copy their controls (scale too)", modes == ["copy + scale"],
               "modes: %s" % modes)
    joints = [ribbon.bind_of(x)[0] for x in _paths(lids)]
    jpos = [_p(x) for x in joints]
    mid = _paths(lids)[len(lids) // 2]
    pts0 = _surf_pts(strip)
    cmds.setAttr(mid + ".translateY", 0.4)
    rep.expect("before the switch: a control moves the ribbon", _moved(pts0, _surf_pts(strip)) > 0.05,
               "ribbon moved %.3f; %s" % (_moved(pts0, _surf_pts(strip)), _skin_detail(strip, ribbon.bind_of(mid)[0])))
    cmds.setAttr(mid + ".translateY", 0)
    pts0 = _surf_pts(strip)
    rep.step("switch to constraints", ribbon.to_constraints, strip)
    modes = sorted({ribbon.bind_of(x)[1] for x in _paths(lids)})
    rep.expect("switched: joints follow by constraints", modes == ["constraints"], "modes: %s" % modes)
    now = [ribbon.bind_of(x)[0] for x in _paths(lids)]
    rep.expect("switched: nothing moved (joints, ribbon)",
               all(a and (_p(a) - b).length() < 1e-3 for a, b in zip(now, jpos)) and
               _moved(pts0, _surf_pts(strip)) < 1e-3, "ribbon moved %.4f" % _moved(pts0, _surf_pts(strip)))
    rep.expect("switched: joint scale 1", all(a and all(abs(v - 1) < 1e-4 for v in cmds.getAttr(a + ".scale")[0])
                                             for a in now))
    x = _paths(lids)[len(lids) // 2]
    pts0 = _surf_pts(strip)
    xj = ribbon.bind_of(x)[0]
    j0 = _p(xj) if xj else None
    cmds.setAttr(x + ".translateY", 0.4)
    hist = cmds.listHistory(_L(strip), pruneDagObjects=True) or []
    skins = [h for h in hist if cmds.nodeType(h) == "skinCluster"]
    infl = cmds.skinCluster(skins[0], query=True, influence=True) if skins else []
    env = cmds.getAttr(skins[0] + ".envelope") if skins else -1
    rep.expect("switched: a control still moves the ribbon", _moved(pts0, _surf_pts(strip)) > 0.05,
               "ribbon moved %.3f; its joint %s moved %.3f; ribbon skins %s (envelope %s); joint in that skin: %s; "
               "%s" % (_moved(pts0, _surf_pts(strip)), _short(xj) if xj else "-",
                       (_p(xj) - j0).length() if xj else -1, skins, env,
                       bool(xj and any(_short(i) == _short(xj) for i in infl)), _skin_detail(strip, xj)))
    cmds.setAttr(x + ".translateY", 0)


def _skin_detail(srf, joint):
    """Where the ribbon's skin puts that joint: its weight on the 3 CVs nearest to it, and who has those CVs."""
    try:
        shapes = [x for x in cmds.listRelatives(_L(srf), shapes=True, fullPath=True) or []
                  if not cmds.getAttr(x + ".intermediateObject")]
        hist = cmds.listHistory(_L(srf), pruneDagObjects=True) or []
        skin = [h for h in hist if cmds.nodeType(h) == "skinCluster"][0]
        cvs = cmds.ls(shapes[0] + ".cv[*][*]", flatten=True) or []
        jp = _p(joint)
        near = sorted(cvs, key=lambda c: (_om().MVector(*cmds.xform(c, query=True, worldSpace=True,
                                                                     translation=True)) - jp).length())[:3]
        out = []
        for c in near:
            names = cmds.skinPercent(skin, c, query=True, transform=None) or []
            vals = cmds.skinPercent(skin, c, query=True, value=True) or []
            w = {_short(n): round(v, 2) for n, v in zip(names, vals) if v > 0.005}
            out.append("%s %s" % (c.split(".")[-1], w))
        return "joint %s at %s; nearest CVs: %s" % (_short(joint), _vec(jp), "; ".join(out))
    except Exception as e:
        return "(skin detail: %s)" % e


def _ctrl(name, pos, rot):
    off = cmds.group(empty=True, name=name + "_offset")
    cmds.xform(off, worldSpace=True, translation=pos, rotation=rot)
    c = cmds.circle(name=name, constructionHistory=False)[0]
    cmds.parent(c, off, relative=True)
    return _L(name)


def check_follow(rep):
    import math
    from gus_rigtool.core import follow
    om = _om()
    rep.start("Follow: pivot and axes")
    _new_scene()
    eye = _ctrl("chkEye_ctrl", (3, 160, 5), (0, 30, 0))
    _ctrl("chkLid_ctrl", (3.2, 161, 6.5), (20, 0, 10))
    loc = cmds.spaceLocator(name="chkPivot_loc")[0]
    cmds.xform(loc, worldSpace=True, translation=(3, 160, 4))
    w0 = _wm("chkLid_ctrl")
    pivot = rep.step("picked pivot (a locator)", follow.point_of, [loc])
    if not pivot:
        return
    if rep.step("add follow: picked pivot, the control's own axes", follow.add, eye, [_L("chkLid_ctrl")],
                ("rotate",), "control", 0.5, pivot=pivot, axes="own") is None:
        return
    rep.expect("added: no jump", _mat_close(w0, _wm("chkLid_ctrl")))
    sp = _wm("chkLid_ctrl_followSpace")
    off = _wm("chkLid_ctrl_offset")
    rep.expect("the follow sits on the pivot", (_p("chkLid_ctrl_followSpace") - om.MVector(3, 160, 4)).length() < 1e-3,
               "at %s" % _vec(_p("chkLid_ctrl_followSpace")))
    rep.expect("the follow has the control's own axes",
               all(abs(sp.getElement(r, k) - off.getElement(r, k)) < 1e-3 for r in range(3) for k in range(3)))

    def turned(deg, space):
        return w0 * space.inverse() * om.MEulerRotation(math.radians(deg), 0, 0).asMatrix() * space
    cmds.setAttr(eye + ".rotateX", 20)
    rep.expect("driver turns 20: the control turns 10 round the pivot, on its axes",
               _mat_close(turned(10, sp), _wm("chkLid_ctrl")),
               "off by %.4f" % (_p("chkLid_ctrl") - om.MVector(turned(10, sp).getElement(3, 0),
                                                              turned(10, sp).getElement(3, 1),
                                                              turned(10, sp).getElement(3, 2))).length())
    cmds.setAttr(eye + ".rotateX", 0)
    rep.step("move follow pivot: the driver's pivot and axes", follow.move_pivot, [_L("chkLid_ctrl")], "driver",
             "driver")
    rep.expect("moved the pivot: no jump", _mat_close(w0, _wm("chkLid_ctrl")))
    sp = _wm("chkLid_ctrl_followSpace")
    rep.expect("the follow is on the driver now", (_p("chkLid_ctrl_followSpace") - _p(eye)).length() < 1e-3)
    cmds.setAttr(eye + ".rotateX", 20)
    rep.expect("driver turns 20: the control turns 10 round the driver",
               _mat_close(turned(10, sp), _wm("chkLid_ctrl")))
    cmds.setAttr(eye + ".rotateX", 0)
    rep.step("remove follow", follow.remove, [_L("chkLid_ctrl")])
    rep.expect("removed: the control is back home", _mat_close(w0, _wm("chkLid_ctrl")))


def _ring(mesh):
    """Edges of the loop round the middle of a sphere whose poles face Z (like a mouth or an eyelid)."""
    om = _om()
    sel = om.MSelectionList()
    sel.add(_L(mesh))
    dag = sel.getDagPath(0)
    bb = cmds.exactWorldBoundingBox(_L(mesh))
    cz = (bb[2] + bb[5]) * 0.5
    it = om.MItMeshEdge(dag)
    best, best_d = None, None
    while not it.isDone():
        a, b = it.point(0, om.MSpace.kWorld), it.point(1, om.MSpace.kWorld)
        if abs(a.z - b.z) < 1e-4:
            d = abs(a.z - cz)
            if best_d is None or d < best_d:
                best, best_d = it.index(), d
        it.next()
    loop = cmds.polySelect(_L(mesh), edgeLoop=best, noSelection=True) or []
    return ["%s.e[%d]" % (_L(mesh), i) for i in loop]


def _row(mesh):
    """The top row of edges of a plane facing Z (like a brow)."""
    om = _om()
    sel = om.MSelectionList()
    sel.add(_L(mesh))
    it = om.MItMeshEdge(sel.getDagPath(0))
    top = cmds.exactWorldBoundingBox(_L(mesh))[4]
    out = []
    while not it.isDone():
        a, b = it.point(0, om.MSpace.kWorld), it.point(1, om.MSpace.kWorld)
        if abs(a.y - top) < 1e-3 and abs(b.y - top) < 1e-3:
            out.append("%s.e[%d]" % (_L(mesh), it.index()))
        it.next()
    return out


def check_face_kit(rep):
    from gus_rigtool.core import face_kit, ribbon
    rep.start("Face kit (on a test head)")
    _new_scene()
    cmds.polySphere(name="chkHead", radius=10)
    cmds.move(0, 160, 0, "chkHead")
    cmds.select(clear=True)
    head = cmds.joint(name="chkHead_jnt", position=(0, 155, 0))
    cmds.select(clear=True)
    eye = cmds.polySphere(name="chkL_eye", radius=1.2)[0]
    cmds.move(3.5, 162, 8.5, eye)
    made = rep.step("eyes", face_kit.eyes, eye, head)
    if not made or "L" not in made:
        return
    lid = cmds.polySphere(name="chkL_lid", radius=1.5, axis=(0, 0, 1), subdivisionsAxis=16,
                          subdivisionsHeight=10)[0]
    cmds.move(3.5, 162, 8.5, lid)
    edges = rep.step("eyelid loop edges", _ring, lid)
    if edges:
        lids = rep.step("eyelids (+ mirror, Blink)", face_kit.eyelids, edges, _L(made["L"].split("|")[-1]))
        if lids:
            eye_ctrl = _L(made["L"].split("|")[-1])
            ctrls = [c for _i, _o, c in face_kit.controls_of(lids[0])]
            before = [_p(c) for c in ctrls]
            sp = _spread(lids[0], ctrls)
            rep.expect("eyelid controls spread round the lid", sp > 0.6, "spread %.2f of its size; heights %s"
                       % (sp, [round(b.y, 2) for b in before]))
            cmds.setAttr(eye_ctrl + ".Blink", 1.0)
            moved = max((_p(c) - b).length() for c, b in zip(ctrls, before)) if ctrls else 0.0
            keyed = len(cmds.listConnections(eye_ctrl + ".Blink", source=False, destination=True) or [])
            centre = face_kit._eye_centre(eye_ctrl)
            plan = face_kit.blink_plan(lids[0], centre)
            rep.expect("Blink 1 closes the lids (controls move)", moved > 0.05,
                       "moved %.3f; %d control(s) checked; Blink drives %d node(s); blink plan now: %d controls, "
                       "%d upper, %d lower, %d pairs, eye centre %s, lid controls' heights %s" % (
                           moved, len(ctrls), keyed, plan[0], plan[1], plan[2], plan[3],
                           [round(v, 2) for v in centre], [round(_p(c).y, 2) for c in ctrls]))
            cmds.setAttr(eye_ctrl + ".Blink", 0.0)
            back = max((_p(c) - b).length() for c, b in zip(ctrls, before)) if ctrls else 0.0
            rep.expect("Blink 0 opens them again", back < 1e-3, "off by %.4f" % back)
            rep.expect("both eyes have lids", len(lids) >= 2, "%d ribbon(s)" % len(lids))
    lips = cmds.polySphere(name="chkLips", radius=2.5, axis=(0, 0, 1), subdivisionsAxis=16,
                           subdivisionsHeight=10)[0]
    cmds.move(0, 153, 9, lips)
    jaw = _ctrl("chkJaw_ctrl", (0, 156, 2), (0, 0, 0))
    edges = rep.step("mouth loop edges", _ring, lips)
    if edges:
        srf = rep.step("mouth (lips follow the jaw by height)", face_kit.mouth, edges, jaw)
        if srf:
            ctrls = [c for _i, _o, c in face_kit.controls_of(srf)]
            modes = sorted({ribbon.bind_of(c)[1] for c in ctrls})
            rep.add("info", "mouth bind joints", ", ".join(modes))
            if ctrls:
                low = min(ctrls, key=lambda c: _p(c).y)
                high = max(ctrls, key=lambda c: _p(c).y)
                a, b = _p(low), _p(high)
                cmds.setAttr(_L("chkJaw_ctrl") + ".rotateX", 20)
                dl, dh = (_p(low) - a).length(), (_p(high) - b).length()
                rep.expect("jaw opens: the lower lip follows more than the upper", dl > dh + 1e-3,
                           "lower %.3f, upper %.3f" % (dl, dh))
                cmds.setAttr(_L("chkJaw_ctrl") + ".rotateX", 0)
    brow = cmds.polyPlane(name="chkL_brow", width=4, height=1, subdivisionsX=6, subdivisionsY=1,
                          axis=(0, 0, 1))[0]
    cmds.move(4, 166, 8, brow)
    edges = rep.step("brow row edges", _row, brow)
    if edges:
        got = rep.step("brows (+ mirror)", face_kit.brows, edges)
        if got:
            rep.expect("both brows", len(got) >= 2, "%d ribbon(s)" % len(got))


def check_correctives(rep, height):
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import guides
    rep.start("Corrective joints (volume at the bends)")
    _new_scene()
    if rep.step("biped template", bld.biped, height) is None and not guides.module_groups():
        return
    n = 0
    for g in guides.module_groups():
        info = guides.read(g)
        if info["type"] in ("arm", "leg", "back_leg", "front_leg"):
            st = info["settings"]
            st.setdefault("options", {})["correctives"] = True
            guides.save_settings(g, st)
            n += 1
    rep.expect("correctives turned on for the arms and legs", n >= 4, "%d module(s)" % n)
    rep.step("build", bld.build_all, height)
    cors = cmds.ls("*_cor*", type="joint", long=True) or []
    rep.expect("corrective joints made", len(cors) >= 12, "%d joint(s)" % len(cors))
    ctrl, joint = _L("L_radius_FK_ctrl"), _L("L_radius_jnt")
    if not cmds.objExists(ctrl) or not cmds.objExists(joint) or not cors:
        rep.add(NOTE, "correctives: elbow bend", "skipped: no L_radius_FK_ctrl / L_radius_jnt")
        return
    cor = min(cors, key=lambda c: (_p(c) - _p(joint)).length())
    j0, c0 = _wm(joint), _wm(cor)
    for a in ("rotateY", "rotateZ"):
        try:
            cmds.setAttr(ctrl + "." + a, 60)
            break
        except RuntimeError:
            continue
    bend, half = _angle(j0, _wm(joint)), _angle(c0, _wm(cor))
    rep.expect("elbow bends: its corrective turns half way", bend > 10 and 0.35 < half / bend < 0.65,
               "elbow %.1f deg, corrective %.1f deg" % (bend, half))


def check_picker(rep):
    rep.start("Automatic picker (on the published biped)")
    try:
        _animtool()
        from gus_animtool import pickmodel as PM
    except Exception as e:
        rep.add(FAIL, "import the picker", "%s\n%s" % (e, _tb()))
        return
    picker = rep.step("make the automatic picker", PM.auto, "")
    if not picker:
        return
    pages = picker.get("pages") or []
    items = [it for pg in pages for it in pg.get("items") or []]
    rep.expect("pages", bool(pages), ", ".join("%s (%d)" % (pg["name"], len(pg.get("items") or [])) for pg in pages))
    sel = [it for it in items if it.get("kind") == "select"]
    missing = [it.get("label") for it in sel if not PM.resolve(it, "")]
    rep.expect("every button selects a control that exists", not missing, ", ".join(map(str, missing[:8])))
    bad = []
    for pg in pages:
        its = [it for it in pg.get("items") or [] if it.get("kind") == "select"]
        for i, a in enumerate(its):
            for b in its[i + 1:]:
                if PM.overlaps(a, b, -0.5):
                    bad.append("%s / %s" % (a.get("label"), b.get("label")))
    rep.expect("no buttons on top of each other", not bad, "%d pair(s): %s" % (len(bad), ", ".join(bad[:6])),
               bad=NOTE)
    rep.guard("controls found automatically", _check_auto_controls, rep)
    rep.guard("speed report", _check_speed, rep)
    rep.guard("a rig referenced after the window opened", _check_late_rig, rep)
    rep.guard("picker saved in the rig", _check_rig_picker, rep, picker)
    rep.guard("picker frames, text, shapes (5.6.21)", _check_picker5621, rep, picker)
    rep.guard("picker: list, look, front view, controls in / out (5.6.23)", _check_picker5623, rep, picker)
    rep.guard("picker: normalize, titles, backgrounds, behind, switches page (5.6.24)", _check_picker5624, rep,
              picker)
    rep.guard("picker: text places, connectors, silhouette, layers, your toolbar (5.6.25)", _check_picker5625, rep,
              picker)
    rep.guard("picker: text never blocks, rename, shapes, limbs, fade, handles, minimap (5.6.26)",
              _check_picker5626, rep, picker)


def _check_picker5621(rep, picker):
    """5.6.21: in the real window - every new shape, a frame and a text drawn; the frame's title selects its
    buttons' controls; a frame dragged carries its buttons; saved and back."""
    import copy as _copy
    from gus_animtool import pickmodel as PM, pickerqt as PQ
    w = rep.step("open the picker window", PQ.show)
    widget = PQ._state.get("widget")
    if not widget:
        rep.add(NOTE, "no picker widget to drive", "skipped")
        return
    widget.picker = _copy.deepcopy(picker)
    widget.index = 0
    page = widget.page()
    sel = [i for i in page["items"] if i.get("kind") == "select"][:len(PM.SHAPES)]
    for it, shape in zip(sel, PM.SHAPES):
        it["shape"] = shape
    fr = PM.group_frame(page, sel[:3], "Left Arm")
    PM.add_text(page, "BODY", 10, 10)
    widget.set_editing(True)
    widget.picked = {fr["id"]}
    rep.step("draw the page (every shape, the frame, the text) in edit mode", widget.canvas.grab)
    widget.set_editing(False)
    rep.step("... and in use", widget.canvas.grab)
    members = PM.frame_members(page, fr)
    rep.step("click the frame's title", widget.select_items, members, PQ.Qt.NoModifier)
    want = set(n for m in members for n in widget.nodes_of(m))
    got = set(cmds.ls(selection=True, long=True) or [])
    rep.expect("... its buttons' controls are selected (%d)" % len(want), bool(want) and want == got)
    before = [(m["x"], m["y"]) for m in members]
    moving = [fr] + members
    PM.move(moving, 25, 10)
    rep.expect("a frame moved carries its buttons", all(abs(m["x"] - x - 25) < 1e-6 and abs(m["y"] - y - 10) < 1e-6
                                                         for m, (x, y) in zip(members, before)))
    # 5.6.22: a turned button with its text below and bigger, a pinned one, a 2D pad - all drawn; the pad sets
    eye = cmds.circle(name="chkPad_ctrl", constructionHistory=False)[0]
    for a in ("lookX", "lookY"):
        cmds.addAttr(eye, longName=a, attributeType="double", minValue=-1, maxValue=1, keyable=True)
    pad = PM.add_slider2d(page, eye, "lookX", "lookY", 20, 20)
    t = [i for i in page["items"] if i.get("kind") == "select"][0]
    t.update({"rot": 30.0, "label_pos": "below", "text_size": 16.0, "border_w": 3.0, "border_rgb": [1, 0, 0]})
    widget.canvas.store_pins([dict(t, pin=True)])
    rep.step("draw the page (turned, pinned, the pad)", widget.canvas.grab)
    PM.set_slider2d(pad, widget.ns, 1.0, 0.25)
    rep.expect("the pad: lookX 1, lookY -0.5", abs(cmds.getAttr(eye + ".lookX") - 1) < 1e-6 and
               abs(cmds.getAttr(eye + ".lookY") + 0.5) < 1e-6)
    widget.set_editing(True)
    widget.picked = {pad["id"]}
    rep.step("the Item panel shows it", widget.refresh_panel)
    widget.set_editing(False)
    back = PM.import_file(_save_tmp(widget.picker))
    kinds = set(i.get("kind") for pg in back["pages"] for i in pg["items"])
    rep.expect("saved and back: the frame and the text are kept", {"frame", "text"} <= kinds)
    if w is not None:
        try:
            PQ.close() if hasattr(PQ, "close") else None
        except Exception:
            pass


def _check_picker5623(rep, picker):
    """5.6.23: in the real window - the mode band, status, the button list (search, undock / dock), your look
    (compact toolbar, light theme, text 200%: put back after), a toggle / long text (fit, run past) / pinned drawn,
    the front view for the picked buttons, a page copy, take out / put back, unpin all, the missing list."""
    import copy as _copy
    import json as _json
    from gus_animtool import anim as A, pickmodel as PM, pickerqt as PQ
    PQ.show()
    w = PQ._state.get("widget")
    if not w:
        rep.add(NOTE, "no picker widget to drive", "skipped")
        return
    keep = _json.dumps(PM.prefs())
    try:
        w.picker = _copy.deepcopy(picker)
        w.index = 0
        w.fill_tabs()
        page = w.page()
        rep.step("draw (animate)", w.canvas.grab)
        rep.expect("mode band: ANIMATE; status line", getattr(w, "_band", "").startswith("ANIMATE") and
                   getattr(w, "_status", "").startswith("Page: "), getattr(w, "_status", ""))
        w.edit_btn.setChecked(True)
        rep.expect("mode band: EDIT", getattr(w, "_band", "").startswith("EDIT"))
        w.list_btn.setChecked(True)
        rep.step("the button list", w.refresh_list)
        rep.expect("... a row per item", w.button_list.count() == len(page["items"]))
        rep.step("search 'arm'", w.filter_list, "arm")
        rep.step("undock the list", w.float_list)
        rep.step("dock it back", w.dock_list)
        w.filter_list("")
        rep.step("your look: compact, light, text 200%, hover outline", w.apply_look,
                 {"compact": True, "theme": "light", "text_scale": 2.0, "hover": "outline"})
        sel = [i for i in page["items"] if i.get("kind") == "select"]
        if len(sel) >= 6:
            sel[0].update({"label": "A very long label for a small button", "text_fit": "fit"})
            sel[1].update({"label": "Runs past the edge", "text_fit": "overflow"})
            sel[2].update({"pin": True})
            w.canvas.store_pins([sel[2]])
        gear = cmds.circle(name="chkToggle_ctrl", constructionHistory=False)[0]
        cmds.addAttr(gear, longName="ikfk", attributeType="double", minValue=0, maxValue=1, keyable=True)
        tg = PM.add_widget(page, "toggle", gear, "ikfk", 10, 10)
        PM.toggle(tg, w.ns)
        rep.expect("a toggle: one click on", cmds.getAttr(gear + ".ikfk") == 1)
        rep.step("draw (edit: long text fitted / running past, pinned badge, the toggle)", w.canvas.grab)
        w.picked = set(i["id"] for i in sel[3:8])
        moved = rep.step("front view for the picked", w.arrange_front, None, True)
        rep.expect("... placed (%s)" % moved, bool(moved))
        n = len(w.picker["pages"])
        rep.step("Page > Duplicate", w.duplicate_page)
        rep.expect("... a copy after it", len(w.picker["pages"]) == n + 1 and w.page()["name"].endswith("(copy)"))
        w.index = 0
        w.set_page(0)
        rep.step("Unpin all", w.unpin_all)
        rep.expect("... no pins left", not PM.pinned(w.picker))
        victim = [i for i in w.page()["items"] if i.get("kind") == "select"][-1]
        node = victim["nodes"][0]
        w.picked = {victim["id"]}
        rep.step("take out a control", w.exclude_picked)
        rows = rep.step("the missing list (with unsure curves)", w.missing_rows, True)
        rep.expect("... the taken-out one isn't missing", rows is not None and node not in
                   [PM.strip(r[0]) for r in rows or []] and node in PM.excluded(w.picker))
        rep.step("put it back", w.include_nodes, [node])
        rep.step("draw again", w.canvas.grab)
        rep.step("report", PM.report, w.picker, w.ns)
        w.edit_btn.setChecked(False)
    finally:
        A.set_opt("picker_prefs", keep)
        try:
            w.look = PM.prefs()
            w._layout_tools()
            w.dirty = False
        except Exception:
            pass


def _check_picker5624(rep, picker):
    """5.6.24: in the real window - normalize a page made far too big, text growing / bigger on a text and a frame
    title (placed above, centred), the outline from the meshes, the front picture captured (playblast) and drawn,
    seen from behind, find, help, keyed dots, hierarchy lines, the Switches page, a space switch, the page as a
    picture, mirror pairs - your look put back after."""
    import copy as _copy
    import json as _json
    import tempfile
    from gus_animtool import anim as A, pickmodel as PM, pickmore as PX, pickerqt as PQ
    PQ.show()
    w = PQ._state.get("widget")
    if not w:
        rep.add(NOTE, "no picker widget to drive", "skipped")
        return
    keep = _json.dumps(PM.prefs())
    try:
        w.picker = _copy.deepcopy(picker)
        w.index = 0
        w.fill_tabs()
        page = w.page()
        for it in page["items"]:
            for k in ("x", "y", "w", "h"):
                it[k] *= 8.0
        page["width"], page["height"] = page.get("width", 400) * 12, page.get("height", 400) * 12
        rep.expect("a page made far too big needs normalizing", PX.needs_normalize(page))
        w.edit_btn.setChecked(True)
        rep.step("Normalize", w.normalize_page)
        rep.expect("... sane now", not PX.needs_normalize(page))
        sel = [i for i in page["items"] if i.get("kind") == "select"]
        w.picked = set(i["id"] for i in sel[:3])
        rep.step("group three, title above, centred, bigger", w.edit, lambda its: PM.group_frame(page, its, "ARM"))
        fr = [i for i in page["items"] if PM.is_frame(i)][0]
        fr.update({"title_pos": "above", "align": "center"})
        rep.step("Text + on the frame and a text", PX.text_bigger, [fr, PM.add_text(page, "BODY", 5, 5)], 1.5)
        rep.step("draw (edit)", w.canvas.grab)
        rep.step("outline from the meshes (any namespace)", w.outline_from_meshes, page)
        rep.expect("... an outline (%d meshes)" % len(PX.rig_meshes(w.ns)), bool(page.get("outline")))
        got = rep.step("front picture (playblast from an orthographic front camera)", w.capture_picture, page)
        rep.expect("... kept in the picker", bool((page.get("picture") or {}).get("data")), str(got or ""))
        w.edit_btn.setChecked(False)
        rep.step("draw (animate: grow text, picture, keyed dots, lines)", w.canvas.grab)
        rep.step("seen from behind", w.toggle_behind, True)
        rep.step("draw from behind", w.canvas.grab)
        rep.step("back to the front", w.toggle_behind, False)
        rep.step("find 'arm'", w.find, "arm")
        rep.step("help", w.toggle_help)
        rep.step("draw with help", w.canvas.grab)
        w.toggle_help()
        w.hide_find()
        rep.step("the Switches page", w.make_switches_page)
        rep.expect("... it has switches", any(i.get("kind") in ("toggle", "enum") for i in w.page()["items"]),
                   "%d item(s)" % len(w.page()["items"]))
        rep.step("draw the Switches page", w.canvas.grab)
        path = os.path.join(tempfile.gettempdir(), "gus_check_picker_page.png")
        rep.step("the page as a picture", w.canvas.render_page, path)
        rep.expect("... written", os.path.exists(path))
        rows = rep.step("mirror pairs report", PX.pair_report, w.ns)
        rep.expect("... ran (%d to look at)" % len(rows or []), rows is not None)
    finally:
        A.set_opt("picker_prefs", keep)
        try:
            w.look = PM.prefs()
            w.dirty = False
        except Exception:
            pass


def _check_picker5625(rep, picker):
    """5.6.25: in the real window - text placed round / in items (a note, a frame title, a button moved by its
    offset), connectors (curved, elbow, bends, heads, a label) drawn, the silhouette picture from the meshes'
    triangles, a layer hidden, your toolbar laid out again; put back after."""
    import copy as _copy
    import json as _json
    from gus_animtool import anim as A, pickmodel as PM, pickmore as PX, pickerqt as PQ
    PQ.show()
    w = PQ._state.get("widget")
    if not w:
        rep.add(NOTE, "no picker widget to drive", "skipped")
        return
    keep = _json.dumps(PM.prefs())
    keep_bar = A.opt("picker_toolbar", "")
    try:
        w.picker = _copy.deepcopy(picker)
        w.index = 0
        w.fill_tabs()
        page = w.page()
        w.edit_btn.setChecked(True)
        sel = [i for i in page["items"] if i.get("kind") == "select"]
        if len(sel) >= 4:
            sel[0].update({"tpos": "below", "tdx": 4.0, "tdy": 2.0})
            sel[1].update({"tpos": "top-left", "plate": True})
            fr = PM.group_frame(page, sel[2:4], "LEGS")
            fr.update({"tpos": "above", "text_size": 18.0})
            PX.add_link(page, sel[0]["id"], sel[1]["id"], label="IK", head_a="dot", width=3.0)
            ln = PX.add_link(page, sel[1]["id"], sel[2]["id"], style="elbow", dash="dash")
            PX.add_bend(page, ln, (sel[1]["x"] + sel[2]["x"]) / 2.0, (sel[1]["y"] + sel[2]["y"]) / 2.0 + 20)
        PX.add_note(page, "Remember:\nkey the heels", 5, 5)
        rep.step("draw (edit: text places, a note, connectors, ports)", w.canvas.grab)
        rep.step("silhouette picture from the meshes' triangles", w.silhouette_picture, page)
        rep.expect("... kept in the picker", (page.get("picture") or {}).get("kind") == "silhouette")
        PX.add_layer(page, "Notes")
        PX.set_layer([i for i in page["items"] if i.get("note")], "Notes")
        rep.step("hide the Notes layer", w.layer_toggle, "Notes")
        w.edit_btn.setChecked(False)
        rep.step("draw (animate: silhouette, connectors, the layer hidden)", w.canvas.grab)
        st, hid = PX.toolbar_state(w._spec_ids())
        PX.section_move(st, "File", -20)
        rep.step("your toolbar laid out (File first)", w.save_toolbar, st, set(hid))
        rep.expect("... File first", w.tools and w.tools[0][0] == "File")
    finally:
        A.set_opt("picker_prefs", keep)
        A.set_opt("picker_toolbar", keep_bar)
        try:
            w.look = PM.prefs()
            w._layout_tools()
            w.dirty = False
        except Exception:
            pass


def _check_picker5626(rep, picker):
    """5.6.26: in the real window - a text over a button doesn't block it, rename, a rig tool shape and the
    control's own curve as shapes, frames per limb, IK / FK fade on a real limb, badges, fold, copy / paste,
    8 handles / turn drawn, the minimap, preview, the panel's sections."""
    import copy as _copy
    import json as _json
    from gus_animtool import anim as A, pickmodel as PM, pickmore as PX, pickerqt as PQ
    PQ.show()
    w = PQ._state.get("widget")
    if not w:
        rep.add(NOTE, "no picker widget to drive", "skipped")
        return
    keep = _json.dumps(PM.prefs())
    try:
        w.picker = _copy.deepcopy(picker)
        w.index = 0
        w.fill_tabs()
        page = w.page()
        sel = [i for i in page["items"] if i.get("kind") == "select" and w.nodes_of(i)]
        if not sel:
            rep.add(NOTE, "no buttons with controls", "skipped")
            return
        t = PM.add_text(page, "OVER", sel[0]["x"] - 5, sel[0]["y"] - 5)
        t["w"], t["h"] = sel[0]["w"] + 10, sel[0]["h"] + 10
        hit = PM.hit_any(page, sel[0]["x"] + sel[0]["w"] / 2, sel[0]["y"] + sel[0]["h"] / 2)
        rep.expect("a text over a button: the click hits the button", hit is sel[0])
        w.edit_btn.setChecked(True)
        w.picked = set(i["id"] for i in sel[:3])
        rep.step("rename (prefix / suffix)", w.rename_items, PX.reading_order(sel[:3]), prefix="L ", suffix=" x")
        rep.step("a rig tool shape (gear)", PX.apply_shape, sel[:1], "gear")
        w.picked = {sel[1]["id"]} if len(sel) > 1 else {sel[0]["id"]}
        rep.step("the control's own curve as the shape", w.shape_from_control, "best")
        rep.step("frames per limb", w.group_by_limb)
        rep.step("copy / paste", lambda: (w.copy_picked(), w.paste()))
        frs = [i for i in page["items"] if PM.is_frame(i)]
        if frs:
            frs[0]["folded"] = True
        w.picked = set(i["id"] for i in sel[:2])
        rep.step("draw (edit: handles, hover, badges, folded)", w.canvas.grab)
        page["width"], page["height"] = page.get("width", 400) * 6, page.get("height", 400) * 6
        rep.step("draw with the minimap", w.canvas.grab)
        rep.step("preview", w.toggle_preview, True)
        rep.step("draw the preview", w.canvas.grab)
        w.toggle_preview(False)
        w.edit_btn.setChecked(False)
        faded = []
        for i in sel:
            try:
                if w.ikfk_faded(i):
                    faded.append(i.get("label"))
            except Exception:
                pass
        rep.add(NOTE, "IK / FK fade: %d faded button(s)" % len(faded), ", ".join(map(str, faded[:8])))
        rep.step("draw (animate: fade, badges)", w.canvas.grab)
    finally:
        A.set_opt("picker_prefs", keep)
        try:
            w.look = PM.prefs()
            w.dirty = False
        except Exception:
            pass


def _save_tmp(picker):
    import tempfile
    from gus_animtool import pickmodel as PM
    path = os.path.join(tempfile.gettempdir(), "gus_check_picker5621.json")
    PM.export_file(picker, path)
    return path


def _check_rig_picker(rep, picker):
    """4.5.2: Save in the rig's own file keeps the picker IN the rig (on its top group, through publish's lock);
    export / import a picker file."""
    import tempfile
    from gus_animtool import pickmodel as PM
    where = rep.step("Save the picker (the rig's own file)", PM.save, picker, "")
    rep.expect("... it's kept in the rig", where == "rig" and PM.where_from("") == "rig",
               "saved: %s, loads from: %s, on %s" % (where, PM.where_from(""), PM.rig_node("")))
    path = os.path.join(tempfile.gettempdir(), "gus_check_picker.json")
    rep.step("Export picker", PM.export_file, picker, path)
    back = rep.step("Import picker", PM.import_file, path)
    rep.expect("... the same pages come back", bool(back) and [p["name"] for p in back["pages"]] ==
               [p["name"] for p in picker["pages"]])


def _check_late_rig(rep):
    """4.5.1: a character added after Gus Animtool's window opened (a referenced rig): clicking its control picks
    it in the character menu - no 'Value is out of range: 2'."""
    from gus_animtool import anim as A
    if not cmds.optionMenu(A.P + "Char", exists=True):
        rep.step("Gus Animtool window (for the character menu)", __import__("gus_animtool").show)
    A.fill_characters()
    ns = "chkLateRig"
    if not cmds.namespace(exists=ns):
        cmds.namespace(add=ns)
    c = cmds.circle(name=ns + ":R_Scapula_Ctrl", constructionHistory=False)[0]
    cmds.addAttr(c, longName="space", attributeType="enum", enumName="world:chest", keyable=True)
    cmds.setAttr(c + ".space", 1)
    try:
        cmds.select(c, replace=True)
        rep.step("click a control of a rig added after the window opened", A._follow_selection)
        rep.expect("... the character menu picks its rig", A.current_character() == ns + ":",
                   "menu shows %r" % A.current_character())
    finally:
        cmds.select(clear=True)
        cmds.delete(c)
        try:
            cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
        except RuntimeError:
            pass
        A.fill_characters()


def _check_speed(rep):
    """4.5.0: the speed report runs on the published biped and leaves the scene as it was."""
    from gus_rigtool.core import speed
    probe = cmds.ls("*_ctrl", type="transform") or []
    before = cmds.xform(probe[0], query=True, worldSpace=True, matrix=True) if probe else None
    keys = cmds.keyframe(probe[:1], query=True, keyframeCount=True) if probe else 0
    text = rep.step("speed report (on the biped)", speed.run, False, False)
    if not text:
        return
    failed = [ln.strip() for ln in text.splitlines() if "failed:" in ln]
    rep.expect("speed report: every action timed", not failed, "; ".join(failed[:6]))
    head = text.split("EVERYTHING")[0].split("SLOW", 1)[-1].splitlines()[1:]
    slow = [ln.strip() for ln in head if ln.strip()]
    rep.add("info", "speed report: slow actions", "; ".join(slow) or "none over 0.5 s")
    if probe:
        rep.expect("speed report: the scene is left as it was (a control, its keys)",
                   cmds.xform(probe[0], query=True, worldSpace=True, matrix=True) == before and
                   cmds.keyframe(probe[:1], query=True, keyframeCount=True) == keys)


def _check_auto_controls(rep):
    """4.4.6: controls found with no suffix set - on the biped (the same as its _ctrl names) and on a hand-made
    rig with no control names at all."""
    from gus_animtool import anim as A
    from gus_animtool import pickmodel as PM
    A._auto_cache.clear()
    named = {t for c in cmds.ls(type="nurbsCurve", long=True, noIntermediate=True) or []
             for t in cmds.listRelatives(c, parent=True, fullPath=True) or []
             if A.namespace_of(t) == "" and t.split("|")[-1].endswith("_ctrl")}
    auto = A.auto_controls("")
    rep.expect("biped: every _ctrl control found automatically", named <= auto,
               "missed: %s" % ", ".join(sorted(x.split("|")[-1] for x in named - auto)[:10]))
    extra = sorted(x.split("|")[-1] for x in auto - named)
    rep.expect("biped: no other curves taken for controls", not extra, "%d: %s" % (len(extra), ", ".join(extra[:12])),
               bad=NOTE)
    # a hand-made rig in its own namespace: no suffixes, a hidden 'no touch' curve, a templated one
    ns = "chkHand"
    if not cmds.namespace(exists=ns):
        cmds.namespace(add=ns)
    top = cmds.group(empty=True, name=ns + ":rig")
    want = []
    for i, nm in enumerate(("hips", "chest", "head", "Lf_arm", "Rt_arm")):
        c = cmds.circle(name=ns + ":" + nm, constructionHistory=False)[0]
        cmds.parent(c, top)
        cmds.move((i - 2) * 3.0, 100 + i * 5.0, 0, c)
        want.append(nm)
    hidden = cmds.group(empty=True, name=ns + ":noTouch", parent=top)
    cmds.setAttr(hidden + ".visibility", 0)
    sp = cmds.circle(name=ns + ":splineCurve", constructionHistory=False)[0]
    cmds.parent(sp, hidden)
    tm = cmds.circle(name=ns + ":guideLine", constructionHistory=False)[0]
    cmds.parent(tm, top)
    cmds.setAttr(tm + ".template", 1)
    A._auto_cache.clear()
    got = sorted(x.split("|")[-1].split(":")[-1] for x in A.auto_controls(ns + ":"))
    rep.expect("hand-made rig: its controls found (no names needed)", got == sorted(want),
               "found %s; %s" % (got, A.found_text(ns + ":")))
    A._pairs_cache.clear()
    rep.expect("hand-made rig: left / right from the names (Lf_ / Rt_)", ("Lf_", "Rt_") in A.auto_pairs(ns + ":"),
               "tokens found: %s" % A.auto_pairs(ns + ":"))
    picker = rep.step("hand-made rig: automatic picker", PM.auto, ns + ":")
    if picker:
        n = sum(len(pg.get("items") or []) for pg in picker["pages"])
        rep.expect("hand-made rig: a button per control", n == len(want), "%d button(s)" % n)
        extra_c = cmds.circle(name=ns + ":tail", constructionHistory=False)[0]
        cmds.parent(extra_c, top)
        added = rep.step("a control added later goes on 'New controls'", PM.add_missing, picker, ns + ":")
        rep.expect("... just that one", added == 1, "added %s" % added)
    cmds.delete(top)



def check_daily_tools(rep):
    from gus_rigtool.core import mirror_links as ML
    from gus_rigtool.core import pivots as PV
    from gus_rigtool.core import utils
    from gus_rigtool.tools import group_maker as gm
    from gus_rigtool.tools import selector as sl
    rep.start("Pivots, Groups, Select, Mirror links")
    _new_scene()
    crate = cmds.polyCube(name="chkCrate", width=2, height=2, depth=2)[0]
    cmds.move(5, 1, 0, crate)
    bb = cmds.exactWorldBoundingBox(crate)
    rep.step("pivot on the bottom centre of the box", PV.set_pivots, [_L(crate)], PV.box_point(bb, 0.5, 0.0, 0.5))
    got = cmds.xform(_L(crate), query=True, worldSpace=True, rotatePivot=True)
    rep.expect("pivot at (5, 0, 0), the crate didn't move", max(abs(a - b) for a, b in zip(got, (5, 0, 0))) < 1e-4
               and abs(cmds.getAttr(_L(crate) + ".translateX") - 5) < 1e-4, "pivot %s" % [round(v, 3) for v in got])
    centre, rows = rep.step("handles from a face", PV.component_frame, ["%s.f[1]" % _L(crate)]) or (None, None)
    if rows:
        verts = cmds.xform(cmds.polyListComponentConversion("%s.f[1]" % _L(crate), toVertex=True), query=True,
                           worldSpace=True, translation=True)
        edge = [verts[3 + k] - verts[k] for k in range(3)]
        dot = lambda a, b: sum(x * y for x, y in zip(a, b))       # noqa: E731
        square = all(abs(dot(rows[i], rows[j]) - (1.0 if i == j else 0.0)) < 1e-6 for i in range(3) for j in range(3))
        rep.expect("face frame: square axes, Y stands on the face", square and abs(dot(rows[1], edge)) < 1e-6)
    # groups
    off = cmds.group(empty=True, name="chkArm_ctrl_offset")
    cmds.xform(off, worldSpace=True, translation=(5, 2, 0), rotation=(0, 30, 0))
    ctl = cmds.circle(name="chkArm_ctrl", constructionHistory=False)[0]
    cmds.parent(ctl, off, relative=True)
    cmds.setAttr(_L("chkArm_ctrl") + ".translateX", 1.0)
    w0 = _wm("chkArm_ctrl")
    rep.step("group above its parent (_sdk)", gm.insert_above_parent, [utils.uuid(_L("chkArm_ctrl"))], ["_sdk"], True)
    rep.expect("the control didn't move; the stack is sdk > offset > control",
               _mat_close(w0, _wm("chkArm_ctrl")) and _L("chkArm_ctrl").split("|")[-3:] ==
               ["chkArm_ctrl_sdk", "chkArm_ctrl_offset", "chkArm_ctrl"])
    rep.step("remove that group", gm.remove_groups, [_L("chkArm_ctrl_sdk")])
    rep.expect("removed: nothing moved", _mat_close(w0, _wm("chkArm_ctrl")) and not cmds.objExists("chkArm_ctrl_sdk"))
    # select: quick set
    rep.step("quick set: save", sl.save_quick_set, "chk", [_L("chkArm_ctrl"), _L(crate)])
    cmds.select(clear=True)
    rep.step("quick set: select again", sl.load_quick_set, "chk")
    rep.expect("quick set selects both", len(cmds.ls(selection=True) or []) == 2)
    sl.delete_quick_set("chk")
    # mirror links: a follow mirrored to the twin moves as its mirror image
    from gus_rigtool.core import follow
    for side, x in (("L", 3), ("R", -3)):
        _ctrl("%s_chkLid_ctrl" % side, (x, 161, 6.5), (0, 0, 0))
        _ctrl("%s_chkEye_ctrl" % side, (x, 160, 5), (0, 0, 0))
    rep.step("follow on the left lid", follow.add, _L("L_chkEye_ctrl"), [_L("L_chkLid_ctrl")], ("rotate",),
             "control", 0.5, pivot=[3, 160, 4], axes="own")
    out = rep.step("mirror the follow onto the right lid", ML.run, [_L("L_chkLid_ctrl")], ["follows"]) or {}
    done = out.get("follows", ([], []))[0]
    rep.expect("the right lid follows the right eye", bool(done), str(out.get("follows")))
    if done:
        a0, b0 = _p("L_chkLid_ctrl"), _p("R_chkLid_ctrl")
        for sd in "LR":
            cmds.setAttr(_L("%s_chkEye_ctrl" % sd) + ".rotateX", 20)
        da, db = _p("L_chkLid_ctrl") - a0, _p("R_chkLid_ctrl") - b0
        rep.expect("both eyes turn: the lids move as mirror images",
                   da.length() > 1e-3 and abs(da.x + db.x) < 1e-3 and abs(da.y - db.y) < 1e-3 and abs(da.z - db.z) < 1e-3,
                   "left %s, right %s" % (_vec(da), _vec(db)))


def check_make_controls(rep):
    from gus_rigtool.core import centre_point as CP
    from gus_rigtool.core import make_controls as MC
    rep.start("Joint at the centre, Make controls")
    _new_scene()
    a = cmds.polySphere(name="chkEyeL", radius=1)[0]
    b = cmds.polySphere(name="chkEyeR", radius=1)[0]
    cmds.move(3, 160, 8, a)
    cmds.move(-3, 160, 8, b)
    cmds.makeIdentity(a, b, apply=True, translate=True)
    sel = ["%s.vtx[*]" % _L(a), "%s.vtx[*]" % _L(b)]
    made = rep.step("one joint per piece (both eyes' vertices)", CP.make, "joint", "piece", "average", "world",
                    False, None, "", sel) or []
    rep.expect("two joints, at the eyes' centres", len(made) == 2 and sorted(round(_p(m).x, 3) for m in made)
               == [-3.0, 3.0] and all(abs(_p(m).y - 160) < 1e-3 for m in made), ", ".join(_short(m) for m in made))
    cmds.select(clear=True)
    j1 = cmds.joint(name="chkArm_jnt", position=(5, 150, 0))
    cmds.joint(name="chkElbow_jnt", position=(25, 150, -2))
    cmds.joint(name="chkWrist_jnt", position=(45, 150, 0))
    cmds.joint(_L(j1), edit=True, orientJoint="xyz", secondaryAxisOrient="yup", children=True, zeroScaleOrient=True)
    joints = [_L(n) for n in ("chkArm_jnt", "chkElbow_jnt", "chkWrist_jnt")]
    w0 = _wm("chkWrist_jnt")
    out = rep.step("controls on a chain (constrain, FK)", MC.make, joints) or []
    rep.expect("three controls, nothing moved", len(out) == 3 and _mat_close(w0, _wm("chkWrist_jnt")))
    if out:
        cmds.setAttr(_L("chkArm_ctrl") + ".rotateY", 30)
        moved = (_p("chkWrist_jnt") - om_vec(w0)).length()
        rep.expect("turn the first control: the whole arm follows (FK)", moved > 1.0, "wrist moved %.3f" % moved)
        cmds.setAttr(_L("chkArm_ctrl") + ".rotateY", 0)
        rep.expect("back at 0: back home", _mat_close(w0, _wm("chkWrist_jnt")))


_short = _nodes.short


def om_vec(m):
    return _om().MVector(m.getElement(3, 0), m.getElement(3, 1), m.getElement(3, 2))


def _mesh_pts(mesh):
    om = _om()
    flat = cmds.xform(_L(mesh) + ".vtx[*]", query=True, worldSpace=True, translation=True) or []
    return [om.MVector(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat) - 2, 3)]


def check_editing(rep):
    """4.3.0: rebuild a ribbon with fewer controls keeping a mesh's weights; switch to copying and back; redo a
    Face part; Repair finds and fixes."""
    from gus_rigtool import scene_check
    from gus_rigtool.core import face_kit, repair, ribbon, ribbon_keep
    rep.start("Editing what's built (rebuild keeps weights, switch, redo, repair)")
    _new_scene()
    strip = rep.step("open ribbon", _strip_ribbon, "chkKeep_ribbon", (0.0, 0.0, 0.0), 6.0)
    if not strip or not rep.step("build (6 controls)", _build_ribbon, strip, "chkKeep"):
        return
    joints = ribbon_keep.bind_joints(_L(strip))
    mesh = cmds.polyPlane(name="chkKeep_mesh", width=6, height=0.6, subdivisionsX=24, subdivisionsY=2,
                          axis=(0, 0, 1))[0]
    skin = rep.step("skin a mesh to the ribbon's joints", lambda: cmds.skinCluster(
        joints, mesh, toSelectedBones=True, name="chkKeep_skin")[0])
    if not skin:
        return
    pts0 = _mesh_pts(mesh)
    builds = ribbon._find_builds()
    st = dict(ribbon._build_settings(builds[_L(strip)]) or {})
    st["ctrl_every"] = 3
    rep.step("rebuild with fewer controls", ribbon.rebuild, st, _L(strip), False)
    n_new = len(_ribbon_ctrls(strip))
    _n, sums, _per = scene_check._skin_weights(skin) if cmds.objExists(skin) else (0, [], [])
    rep.expect("fewer controls now", 0 < n_new < 6, "%d control(s)" % n_new)
    rep.expect("the mesh kept its skin: same place, weights add up to 1", cmds.objExists(skin) and
               _moved(pts0, _mesh_pts(mesh)) < 1e-3 and sums and max(abs(x - 1) for x in sums) < 1e-3,
               "mesh moved %.4f" % _moved(pts0, _mesh_pts(mesh)))
    c = _paths(_ribbon_ctrls(strip))[n_new // 2] if n_new else None
    if c:
        cmds.setAttr(c + ".translateY", 0.5)
        rep.expect("a control still moves the mesh", _moved(pts0, _mesh_pts(mesh)) > 0.05)
        cmds.setAttr(c + ".translateY", 0)
    # switch to copying and back (pivot on the shape)
    loop = rep.step("loop ribbon (pivot on the shape)", _loop_ribbon, "chkSwitch_ribbon", 3.0, (0.0, 10.0, 0.0))
    if loop and rep.step("build", _build_ribbon, loop, "chkSwitch", pivot_on_shape=True):
        pts = _surf_pts(loop)
        rep.step("switch to copying", ribbon.to_copying, loop)
        modes = sorted({ribbon.bind_of(x)[1] for x in _paths(_ribbon_ctrls(loop))})
        rep.expect("joints copy their controls, nothing moved", modes == ["copy"] and _moved(pts, _surf_pts(loop)) < 1e-3,
                   "modes %s" % modes)
        rep.step("switch back to constraints", ribbon.to_constraints, loop)
        modes = sorted({ribbon.bind_of(x)[1] for x in _paths(_ribbon_ctrls(loop))})
        rep.expect("constraints again, nothing moved", modes == ["constraints"] and _moved(pts, _surf_pts(loop)) < 1e-3,
                   "modes %s" % modes)
    # redo a face part
    lips = cmds.polySphere(name="chkRedoLips", radius=2.5, axis=(0, 0, 1), subdivisionsAxis=16,
                           subdivisionsHeight=10)[0]
    cmds.move(0, 30, 9, lips)
    jaw = _ctrl("chkRedoJaw_ctrl", (0, 33, 2), (0, 0, 0))
    edges = _ring(lips)
    srf = rep.step("mouth", face_kit.mouth, edges, jaw)
    if srf:
        n0 = len(face_kit.controls_of(srf))
        made = rep.step("redo the mouth (realistic)", face_kit.redo, srf, style="realistic") or []
        n1 = len(face_kit.controls_of(made[0])) if made else 0
        rep.expect("redone: realistic has more controls", n1 > n0, "%d -> %d" % (n0, n1))
    found = rep.step("repair: look through the scene", repair.find)
    rep.add("info", "repairs found", ", ".join(i.label for i in (found or [])) or "none")


def check_mirror_setup(rep):
    """5.0.3: a hand-made brow setup like the Hare's (brow controls -> parent constraints whose target inputs go
    through multiplyDivide / unitConversion) mirrored onto the right: same values move both sides as mirror
    images."""
    from gus_rigtool.core import mirror_setup as MS
    rep.start("Mirror a setup (a hand-made brow, like the Hare's)")
    _new_scene()
    sides = {"L": 1.0, "R": -1.0}
    for sd, k in sides.items():
        for i, x in ((1, 2.0), (2, 4.0)):
            off = cmds.group(empty=True, name="%s_chkBrow_0%d_ctrl_offset" % (sd, i))
            cmds.move(k * x, 152, 5, off)
            if sd == "R":
                cmds.setAttr(off + ".scaleX", -1)                     # a true mirror, like the ribbon's
            c = cmds.circle(name="%s_chkBrow_0%d_ctrl" % (sd, i), normal=(0, 0, 1), radius=0.5,
                            constructionHistory=False)[0]
            cmds.parent(c, off, relative=True)
        grp = cmds.group(empty=True, name="%s_chkRibbon_ctrls_grp" % sd)
        off = cmds.group(empty=True, name="%s_chkRibbon_fol_11_ctrl_offset" % sd, parent=grp)
        cmds.move(k * 3, 151, 5, off)
        if sd == "R":
            cmds.setAttr(off + ".scaleX", -1)
        parent = off
        if sd == "L":
            parent = cmds.group(empty=True, name="L_chkRibbon_fol_11_ctrl_sdk", parent=off)
        c = cmds.circle(name="%s_chkRibbon_fol_11_ctrl" % sd, normal=(0, 0, 1), radius=0.3,
                        constructionHistory=False)[0]
        cmds.parent(c, parent, relative=True)
    sdk = cmds.ls("L_chkRibbon_fol_11_ctrl_sdk", long=True)[0]
    con = cmds.parentConstraint(["L_chkBrow_01_ctrl", "L_chkBrow_02_ctrl"], sdk, maintainOffset=True)[0]
    for i, (ctrl, f) in enumerate((("L_chkBrow_01_ctrl", 0.2), ("L_chkBrow_02_ctrl", 0.8))):
        md = cmds.createNode("multiplyDivide")
        cmds.setAttr(md + ".input2", f, f, f, type="double3")
        cmds.connectAttr(ctrl + ".translate", md + ".input1")
        cmds.connectAttr(md + ".output", "%s.target[%d].targetTranslate" % (con, i), force=True)
    rep.step("preview", MS.preview, ["L_chkBrow_01_ctrl", "L_chkBrow_02_ctrl"])
    if not rep.step("mirror the setup onto the right", MS.run, ["L_chkBrow_01_ctrl", "L_chkBrow_02_ctrl"]):
        return
    r_sdk = cmds.ls("R_chkRibbon_fol_11_ctrl_sdk", long=True)
    rep.expect("the right _sdk group is made, the right control under it",
               bool(r_sdk) and cmds.ls("R_chkRibbon_fol_11_ctrl", long=True)[0].startswith(r_sdk[0] + "|"))
    if not r_sdk:
        return
    l0, r0 = _p(sdk), _p(r_sdk[0])
    rep.expect("nothing moved when it was mirrored", abs(l0.x + r0.x) < 1e-3 and abs(l0.y - r0.y) < 1e-3)
    for sd in "LR":
        cmds.setAttr("%s_chkBrow_02_ctrl.translateY" % sd, 1.0)
        cmds.setAttr("%s_chkBrow_02_ctrl.translateX" % sd, 0.5)
    dl, dr = _p(sdk) - l0, _p(r_sdk[0]) - r0
    # two brow controls, equal weights: Maya averages them, so one brow moving gives x0.8 of its move x 1/2
    rep.expect("one brow moved on both sides: the sdk groups move as mirror images (x0.8, half: 2 targets)",
               abs(dl.x + dr.x) < 1e-3 and abs(dl.y - dr.y) < 1e-3 and abs(dl.y - 0.4) < 1e-2,
               "left %s, right %s" % (_vec(dl), _vec(dr)))
    for sd in "LR":
        cmds.setAttr("%s_chkBrow_01_ctrl.translateY" % sd, 1.0)
    dl, dr = _p(sdk) - l0, _p(r_sdk[0]) - r0
    rep.expect("both brows moved: the blend (x0.2 and x0.8, averaged) is the same on both sides",
               abs(dl.x + dr.x) < 1e-3 and abs(dl.y - dr.y) < 1e-3 and abs(dl.y - 0.5) < 1e-2,
               "left %s, right %s" % (_vec(dl), _vec(dr)))
    for sd in "LR":
        for i in (1, 2):
            cmds.setAttr("%s_chkBrow_0%d_ctrl.translateY" % (sd, i), 0)
            cmds.setAttr("%s_chkBrow_0%d_ctrl.translateX" % (sd, i), 0)
    n = len(cmds.ls(type="multiplyDivide"))
    rep.step("mirror it again", MS.run, ["L_chkBrow_01_ctrl", "L_chkBrow_02_ctrl"])
    rep.expect("again: replaced, not doubled", len(cmds.ls(type="multiplyDivide")) == n)


def check_knee_bend(rep, height):
    """5.0.2: Bendy legs: a bend control on the knee bends both pieces into it; roundness rounds the corner;
    nothing moves at rest."""
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import guides, modules
    rep.start("Knee bend control (Bendy legs)")
    _new_scene()
    rep.step("biped template", bld.biped, height)
    for g in guides.module_groups():
        i = guides.read(g)
        if i["id"] in ("L:leg", "R:leg"):
            s = modules.MODULES[i["type"]].complete(i["settings"])
            s["options"]["bendy"] = True
            guides.save_settings(g, s)
            guides.update(g, modules.MODULES[i["type"]], s, height)
    if not rep.step("build (Bendy legs)", bld.build_all, height):
        return
    knee = (cmds.ls("L_knee_bend_ctrl", long=True) or [None])[0]
    rep.expect("a bend control on each knee", knee and cmds.ls("R_knee_bend_ctrl"))
    if not knee:
        return
    twists = sorted(cmds.ls("L_femur_twist_*", type="joint", long=True) or [],
                    key=lambda n: n) + sorted(cmds.ls("L_tibia_twist_*", type="joint", long=True) or [])
    rep.expect("twist joints on both pieces", len(twists) >= 4, "%d" % len(twists))
    pts = lambda: [_p(t) for t in twists]
    rest = pts()
    cmds.setAttr("L_ankle_settings_ctrl.ikfk", 0)                       # FK: bend the knee with its control
    fk = cmds.ls("L_tibia_FK_ctrl", long=True)[0]
    ank = cmds.ls("L_ankle_jnt", long=True) or cmds.ls("L_ankle*", type="joint", long=True)
    best = None
    for ax in "XYZ":
        a0 = _p(ank[0])
        cmds.setAttr(fk + ".rotate" + ax, 60)
        d = (_p(ank[0]) - a0).length()
        cmds.setAttr(fk + ".rotate" + ax, 0)
        if best is None or d > best[1]:
            best = (ax, d)
    cmds.setAttr(fk + ".rotate" + best[0], 60)
    bent = pts()
    cmds.setAttr(knee + ".translateZ", 3.0)
    cmds.setAttr(knee + ".translateY", 3.0)
    moved = pts()
    near = [len(twists) // 2 - 1, len(twists) // 2]                    # the twist joints either side of the knee
    rep.expect("move the knee bend control: both pieces bend into it",
               all((moved[i] - bent[i]).length() > 0.1 for i in near),
               "near the knee moved %s" % ["%.3f" % (moved[i] - bent[i]).length() for i in near])
    cmds.setAttr(knee + ".translateZ", 0)
    cmds.setAttr(knee + ".translateY", 0)
    rep.expect("back at 0: as before", max((a - b).length() for a, b in zip(pts(), bent)) < 1e-3)
    cmds.setAttr(knee + ".roundness", 1.0)
    rounded = pts()
    rep.expect("roundness 1 on a bent knee: the corner rounds (the joints by the knee move)",
               max((rounded[i] - bent[i]).length() for i in near) > 0.01,
               "moved %s" % ["%.3f" % (rounded[i] - bent[i]).length() for i in near])
    cmds.setAttr(fk + ".rotate" + best[0], 0)
    rep.expect("straight leg, roundness 1: nothing moved from rest",
               max((a - b).length() for a, b in zip(pts(), rest)) < 1e-3,
               "off by %.4f" % max((a - b).length() for a, b in zip(pts(), rest)))
    cmds.setAttr(knee + ".roundness", 0.0)


def check_jiggle(rep, height):
    """5.0.10: a chain with jiggle keeps undo working (its memory is no longer written with setAttr), still swings
    when what it hangs from turns between frames, and stays put between frames."""
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import chain, modules
    rep.start("Chain jiggle (undo stays clean)")
    _new_scene()
    rep.step("biped template", bld.biped, height)
    mod = modules.MODULES["chain"]
    s = mod.complete(mod.default_settings("C"))
    s["names"]["name"], s["names"]["count"] = "tail", 4
    s["options"]["type"] = "fk"
    s["options"]["jiggle"] = True
    s["attach"] = "spine:hips"
    tail = rep.step("a tail chain with jiggle", bld.add_module, "chain", "C", "tail", height=height,
                    settings_=mod.complete(s))
    if not tail or not rep.step("build (a chain with jiggle)", bld.build_all, height):
        return
    exprs = [e for e in cmds.ls(type="expression") or [] if chain.JIGGLE_TAG in
             (cmds.expression(e, query=True, string=True) or "")]
    rep.expect("a jiggle expression, with no setAttr in it", exprs and not chain.old_jiggles(), "%s" % exprs)
    if not exprs:
        return
    text = cmds.expression(exprs[0], query=True, string=True)
    import re
    grp = re.findall(r"([^\s;]+)\.rotate([XYZ]) = \$gusJiggle", text)
    settings = (cmds.ls("*.jiggle", objectsOnly=True) or [None])[0]
    fk = sorted(cmds.ls("*_FK_ctrl", long=True) or [])
    fk = [c for c in fk if cmds.listRelatives(c, allParents=True, fullPath=True) and
          any("jiggle" in x for x in (cmds.listRelatives(c, allParents=True, fullPath=True) or []))]
    if not grp or not settings or not fk:
        rep.expect("found the jiggle groups, settings and an FK control", False, "%s %s %s" % (grp[:1], settings, fk[:1]))
        return
    g, ax = grp[0]
    ctrl = fk[0]
    cmds.flushUndo()
    cmds.setAttr(ctrl + ".rotateZ", 25)
    cmds.getAttr(g + ".rotate" + ax)                              # the expression runs
    cmds.getAttr(g + ".rotate" + ax)
    cmds.undo()
    rep.expect("move an FK control, Ctrl+Z: the move is undone (with jiggle on the chain)",
               abs(cmds.getAttr(ctrl + ".rotateZ")) < 1e-6, "rotateZ %.3f" % cmds.getAttr(ctrl + ".rotateZ"))
    dm = (cmds.listConnections(exprs[0], source=True, destination=False, type="decomposeMatrix") or [None])[0]
    root = (cmds.listConnections(dm + ".inputMatrix", source=True, destination=False) or [None])[0] if dm else None
    rep.expect("its root comes in through a decomposeMatrix", bool(root))
    if not root:
        return
    cmds.setAttr(settings + ".jiggle", 1.0)
    cmds.currentTime(1)
    cmds.getAttr(g + ".rotate" + ax)
    cmds.currentTime(2)
    cmds.getAttr(g + ".rotate" + ax)
    try:
        cmds.setAttr(root + ".rotateY", 30)
    except RuntimeError:
        rep.expect("can turn its root for the test", False, root)
        return
    cmds.currentTime(3)
    v3 = cmds.getAttr(g + ".rotate" + ax)
    rep.expect("its root turns between frames: the chain swings", abs(v3) > 1e-3, "%.4f" % v3)
    cmds.getAttr(g + ".rotate" + ax)
    rep.expect("same frame again: it stays where it was", abs(cmds.getAttr(g + ".rotate" + ax) - v3) < 1e-6)
    cmds.setAttr(root + ".rotateY", 0)
    # 5.3.2: something above slides sideways (the world control, the COG): it swings too
    mover = None
    up_chain = []
    node = root
    while node:
        up_chain.append(node)
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    for a in up_chain[1:]:
        try:
            if cmds.getAttr(a + ".translateX", settable=True):
                mover = a
                break
        except (RuntimeError, ValueError):
            pass
    if mover:
        x0 = cmds.getAttr(mover + ".translateX")
        cmds.currentTime(10)
        cmds.getAttr(g + ".rotate" + ax)
        cmds.currentTime(11)
        cmds.getAttr(g + ".rotate" + ax)
        cmds.setAttr(mover + ".translateX", x0 + 10)
        cmds.currentTime(12)
        sw = [cmds.getAttr(gg + ".rotate" + a_) for gg, a_ in grp]
        rep.expect("what it hangs from slides sideways between frames: the chain swings (5.3.2)",
                   max(abs(v) for v in sw) > 1e-3, "%s moved 10: %s" % (mover.split("|")[-1],
                                                                       ["%.3f" % v for v in sw]))
        cmds.setAttr(mover + ".translateX", x0)
    rep.expect("limits on the settings control (5.3.2)", cmds.attributeQuery("jiggle_limit_body", node=settings,
                                                                          exists=True))
    cmds.setAttr(settings + ".jiggle", 0.0)
    cmds.currentTime(1)


def check_nodes_find(rep, height):
    """5.1.0: on a freshly built biped, Find loops and At rest find nothing (no false alarms), and Trace reads a
    hand-made chain back to its control with the values."""
    from gus_rigtool.builder import build as bld
    from gus_rigtool.core import networks as NW
    from gus_rigtool.tools import checker as chk
    rep.start("Nodes: trace, at rest, loops, world turn, make a driver")
    _new_scene()
    rep.step("biped template", bld.biped, height)
    if not rep.step("build", bld.build_all, height):
        return
    found = rep.step("find loops on the built rig", NW.loops)
    rep.expect("no loops on a clean build", found == [], "%s" % [[n.split("|")[-1] for n in g[:4]] for g in found or []])
    from gus_rigtool.core import world_turn
    wt = rep.step("world turn test", world_turn.run) or {}
    rep.expect("world turn: the world control found and turnable", wt.get("world") and wt.get("axis"),
               "%s %s" % (wt.get("world"), wt.get("axis")))
    rep.expect("world turn: everything comes along on a clean build", not wt.get("off"),
               "; ".join("%s %s" % (n.split("|")[-1], w) for n, _t, _m, w in (wt.get("off") or [])[:6]))
    # a double transform on purpose: a group under the world that also gets the world's turn by a connection
    world = wt.get("world")
    if world and wt.get("axis"):
        dbl = cmds.createNode("transform", name="gusDouble_grp", parent=world)
        cmds.connectAttr("%s.rotate%s" % (world, wt["axis"]), "%s.rotate%s" % (dbl, wt["axis"]))
        wt2 = world_turn.run(nodes=[cmds.ls(dbl, long=True)[0]])
        rep.expect("world turn: a group turned twice is found (180)", wt2.get("off") and
                   abs(wt2["off"][0][1] - 180) < 2, "%s" % wt2.get("off"))
        cmds.delete(dbl)
    ctrls = [n for n in chk.transforms(None) if chk.is_control(n)]
    moved = rep.step("at rest on every control", NW.at_rest, ctrls) or []
    rep.expect("nothing moved at rest on a clean build", not [m for m in moved if m[2] is not None],
               "%s" % moved[:4])
    a = cmds.createNode("transform", name="gusTrace_ctrl")
    b = cmds.createNode("transform", name="gusTrace_sdk")
    cl = cmds.createNode("clamp")
    cmds.setAttr(cl + ".maxR", 999)
    md = cmds.createNode("multiplyDivide")
    cmds.setAttr(md + ".input2X", -4)
    cmds.connectAttr(a + ".translateY", cl + ".inputR")
    cmds.connectAttr(cl + ".outputR", md + ".input1X")
    cmds.connectAttr(md + ".outputX", b + ".rotateX")
    text = rep.step("trace gusTrace_sdk.rotateX", NW.trace_text, b + ".rotateX") or ""
    rep.expect("trace: back to the control with the values (x -4, clamp 0..999)",
               "gusTrace_ctrl.translateY" in text and "-4" in text and "999" in text, text.replace("\n", " | "))
    cmds.delete(a, b, cl, md)
    # 5.2.0: Make a driver - the brow's translateY up -> rotateX x -4, both sides, real angles in Maya
    from gus_rigtool.core import drivers
    made = []
    for sd in "LR":
        c = cmds.createNode("transform", name="%s_gusDrv_ctrl" % sd)
        cmds.createNode("nurbsCurve", name="%s_gusDrv_ctrlShape" % sd, parent=c)
        made += [c, cmds.createNode("transform", name="%s_gusDrv_sdk" % sd)]
    got = rep.step("make a driver (translateY up -> rotateX x -4, both sides)", drivers.make,
                   "L_gusDrv_ctrl.translateY", [("L_gusDrv_sdk", "rotateX", -4.0)], "positive")
    if got:
        cmds.setAttr("L_gusDrv_ctrl.translateY", 1.0)
        cmds.setAttr("R_gusDrv_ctrl.translateY", 1.0)
        rl, rr = cmds.getAttr("L_gusDrv_sdk.rotateX"), cmds.getAttr("R_gusDrv_sdk.rotateX")
        rep.expect("driver: up 1 turns both _sdk groups -4 degrees", abs(rl + 4) < 1e-3 and abs(rr + 4) < 1e-3,
                   "left %.3f, right %.3f" % (rl, rr))
        cmds.setAttr("L_gusDrv_ctrl.translateY", -1.0)
        rep.expect("driver: down does nothing (positive side only)", abs(cmds.getAttr("L_gusDrv_sdk.rotateX")) < 1e-6)
        cmds.delete(got[0])
    cmds.delete(made)


def check_mirror_ribbon_sdk(rep):
    """5.2.1: a mirrored ribbon's right side is made like the left (constraints, no joints under -1 scaled
    controls); nodes -> set driven key -> nodes gives the same angles."""
    from gus_rigtool.core import ribbon, drivers, sdk_convert as SC
    rep.start("Mirrored ribbon (constraints) and nodes <-> driven key")
    _new_scene()
    srf = rep.step("a sleeve-like loop ribbon on the left", _loop_ribbon, "L_chkSleeve", 2.0, (8.0, 0.0, 0.0))
    if not srf or not rep.step("build (pivot on the joint)", _build_ribbon, srf, "L_chkSleeve"):
        return
    cmds.select(_L(srf))
    if not rep.step("mirror build", ribbon.mirror_build, "X", "R_chkSleeve"):
        return
    right = [k for k in ribbon._find_builds() if "R_chkSleeve" in k]
    ctrls = _paths(_ribbon_ctrls(right[0])) if right else []
    modes = sorted({ribbon.bind_of(c)[1] for c in ctrls})
    rep.expect("right side: joints follow by constraints (not children of the controls)", ctrls and
               "child" not in modes and not ribbon._loose_binds(ctrls), "modes %s" % modes)
    # nodes <-> driven key
    c = cmds.createNode("transform", name="gusConv_ctrl")
    t = cmds.createNode("transform", name="gusConv_sdk")
    if not rep.step("a driver: translateY up x -4 -> rotateX", drivers.make, "gusConv_ctrl.translateY",
                    [("gusConv_sdk", "rotateX", -4.0)], "positive", None, False):
        return
    ang = lambda v: (cmds.setAttr(c + ".translateY", v), cmds.getAttr(t + ".rotateX"))[1]
    before = [ang(v) for v in (-1.0, 0.5, 1.0, 2.0)]
    rep.step("nodes -> driven key", SC.to_sdk, "gusConv_sdk.rotateX")
    after = [ang(v) for v in (-1.0, 0.5, 1.0, 2.0)]
    rep.expect("driven key: the same angles as the nodes", max(abs(a - b) for a, b in zip(before, after)) < 1e-3,
               "nodes %s, key %s" % (before, after))
    cmds.setAttr(c + ".translateY", 0)
    rep.step("driven key -> nodes", SC.to_nodes, "gusConv_sdk.rotateX")
    again = [ang(v) for v in (-1.0, 0.5, 1.0, 2.0)]
    rep.expect("back to nodes: the same angles again", max(abs(a - b) for a, b in zip(before, again)) < 1e-3,
               "nodes %s, again %s" % (before, again))
    cmds.setAttr(c + ".translateY", 0)


def check_cloth(rep):
    """5.3.0: a sleeve skinned like the arm (+ Delta Mush), a ribbon on its cuff (and the other side), the cloth
    layer, a range of motion and its removal, a fix for the bent elbow; the world turn ignores a stray curve."""
    from gus_rigtool.core import cloth, skin_mirror, world_turn
    rep.start("Cloth: skin like the body, cuff ribbon, cloth layer, range of motion, fix")
    _new_scene()
    cmds.select(clear=True)
    sh = cmds.joint(name="L_shoulder_jnt", position=(10, 100, 0))
    el = cmds.joint(name="L_elbow_jnt", position=(30, 100, -1))
    cmds.joint(name="L_wrist_jnt", position=(50, 100, 0))
    cmds.joint(sh, edit=True, orientJoint="xyz", secondaryAxisOrient="yup", children=True, zeroScaleOrient=True)
    arm = cmds.polyCylinder(name="L_arm_geo", radius=3, height=40, axis=(1, 0, 0), subdivisionsAxis=16,
                            subdivisionsHeight=20)[0]
    cmds.move(30, 100, 0, arm)
    arm_skin = cmds.skinCluster([sh, el, "L_wrist_jnt"], arm, toSelectedBones=True, maximumInfluences=3)[0]
    cmds.setAttr(arm_skin + ".normalizeWeights", 2)                       # Post, like the Hare's body
    sleeve = cmds.polyCylinder(name="L_sleeve_geo", radius=3.6, height=30, axis=(1, 0, 0), subdivisionsAxis=16,
                               subdivisionsHeight=12)[0]
    cmds.move(25, 100, 0, sleeve)
    lines = rep.step("skin like the body", cloth.skin_like, _L(arm), [_L(sleeve)])
    sk = skin_mirror.skin_of(_L(sleeve))
    rep.expect("the sleeve has the arm's joints and a Delta Mush", sk and lines and "deltaMush" in str(
        [cmds.nodeType(h) for h in cmds.listHistory(_L(sleeve), pruneDagObjects=True) or []]), str(lines))
    from gus_rigtool.core import skin_tools
    rep.expect("the sleeve's skin is Post like the arm, every vertex adds up to 1 (5.3.1)", sk and
               cmds.getAttr(sk + ".normalizeWeights") == 2 and not skin_tools.bad_sums(sk, _L(sleeve)))
    cuff = ["%s.e[%d]" % (_L(sleeve), i) for i in range(16)]             # the ring at one end
    made = rep.step("a ribbon on the cuff (and the right side)", cloth.edge_ribbon, cuff, "L_chkCuff", 8, 2,
                    None, True)
    rep.expect("the cuff ribbon and its mirror", made and len(made) == 2, str(made))
    if made:
        cmds.setAttr(el + ".rotateY", 40)
        try:
            cloth.cloth_layer(_L(sleeve), [made[0]])
            said = ""
        except RuntimeError as e:
            said = str(e)
        rep.expect("cloth layer on a posed arm: refused (5.3.1)", "at rest" in said, said[:120])
        cmds.setAttr(el + ".rotateY", 0)
        rest = [cmds.pointPosition("%s.vtx[%d]" % (_L(sleeve), i), world=True) for i in range(40)]
        rep.step("cloth layer", cloth.cloth_layer, _L(sleeve), [made[0]])
        now = [cmds.pointPosition("%s.vtx[%d]" % (_L(sleeve), i), world=True) for i in range(40)]
        far = max(sum((a - b) ** 2 for a, b in zip(p, q)) ** 0.5 for p, q in zip(rest, now))
        rep.expect("at rest the sleeve doesn't move after the layer", far < 0.05, "moved up to %.3f" % far)
        n = cmds.polyEvaluate(_L(sleeve), vertex=True)
        sums = [sum(cmds.skinPercent(sk, "%s.vtx[%d]" % (_L(sleeve), i), query=True, value=True))
                for i in range(n)]
        rep.expect("weights still add up to 1 on every vertex", max(abs(x - 1) for x in sums) < 1e-3,
                   "worst %.4f" % max(abs(x - 1) for x in sums))
    for nm, pos in (("L_Shoulder_FK_ctrl", (10, 100, 0)), ("L_Elbow_FK_ctrl", (30, 100, -1))):
        c = cmds.circle(name=nm, normal=(1, 0, 0), radius=5, constructionHistory=False)[0]
        cmds.move(pos[0], pos[1], pos[2], c)
    from gus_rigtool.core import on_top
    if cmds.attributeQuery(on_top.ATTR, node=cmds.listRelatives("L_Shoulder_FK_ctrl", shapes=True)[0], exists=True):
        rep.step("controls in front of the mesh", on_top.apply)
        rep.expect("both controls drawn on top", on_top.count()[0] >= 2, str(on_top.count()))
    got = rep.step("range of motion", cloth.make_rom)
    rep.expect("range of motion keyed", got and cmds.objExists(cloth.ROM_NODE) and
               cmds.keyframe("L_Elbow_FK_ctrl.rotateZ", query=True, keyframeCount=True), str(got))
    rep.step("remove it", cloth.remove_rom)
    rep.expect("removed: no keys left", not cmds.keyframe("L_Elbow_FK_ctrl", query=True, keyframeCount=True))
    cmds.setAttr(el + ".rotateY", 60)
    sculpt = rep.step("fix this pose", cloth.fix_here, _L(sleeve))
    rep.expect("a sculpt copy for the bent elbow", sculpt and "elbow" in str(sculpt), str(sculpt))
    world = cmds.circle(name="World_ctrl", constructionHistory=False)[0]
    for c in ("L_Shoulder_FK_ctrl", "L_Elbow_FK_ctrl"):
        cmds.parent(c, world)
    stray = cmds.circle(name="edgeCurve1", constructionHistory=False)[0]
    pick = world_turn.world_control(cmds.ls([world, stray, "L_Shoulder_FK_ctrl", "L_Elbow_FK_ctrl"], long=True))
    rep.expect("world turn: World_ctrl, not edgeCurve1", pick and pick.endswith("World_ctrl"), str(pick))


def check_fix533(rep):
    """5.3.3: a cape-like chain stops at a body (rotation limits measured against the mesh); duplicate names are
    renamed; jiggle / wave pause."""
    from gus_rigtool.core import body_stop
    from gus_rigtool.tools import checker
    rep.start("Stop at the body, duplicate names")
    _new_scene()
    body = cmds.polyCube(name="chkBody", width=20, height=30, depth=10)[0]
    cmds.move(0, 15, 8, body)                                  # the body in front of the cape (z 3..13)
    ctrls, parent = [], None
    for i, y in enumerate((28, 20, 12)):
        c = cmds.circle(name="chkCape_%02d_ctrl" % (i + 1), normal=(0, 1, 0), radius=2, constructionHistory=False)[0]
        if parent:
            c = cmds.parent(c, parent)[0]
        cmds.xform(c, worldSpace=True, translation=(0, y, 0))
        parent = c
        ctrls.append(cmds.ls(c, long=True)[0])
    lines = rep.step("fit to the body", body_stop.fit, body, ctrls, 0.1)
    rep.expect("each control got a limit towards the body", lines and sum("towards the body" in x for x in lines) == 3,
               str(lines))
    plug = None
    for ax in "XYZ":
        for side in ("min", "max"):
            if cmds.getAttr("%s.%sRot%sLimitEnable" % (ctrls[0], side, ax)):
                plug = (ax, side)
    if plug:
        ax, side = plug
        cmds.setAttr("%s.rotate%s" % (ctrls[0], ax), -170 if side == "min" else 170)
        tip = cmds.xform(ctrls[-1], query=True, worldSpace=True, translation=True)
        rep.expect("turned far towards the body: the chain stays out of it", tip[2] < 3.0 + 0.5, "tip z %.2f" % tip[2])
        cmds.setAttr("%s.rotate%s" % (ctrls[0], ax), 0)
    rep.step("remove the body stop", body_stop.remove, ctrls)
    # duplicate names
    a = cmds.group(empty=True, name="chkA")
    b = cmds.group(empty=True, name="chkB")
    cmds.group(empty=True, name="chkDup", parent=a)
    cmds.group(empty=True, name="chkDup", parent=b)
    dups = checker.find_dup_names(None)
    rep.expect("two chkDup found", len([d for d in dups if d.endswith("chkDup")]) == 2, str(dups))
    rep.step("rename the extra copy", checker.fix_dup_names, dups, False)
    rep.expect("no duplicate names left", not [d for d in checker.find_dup_names(None) if "chkDup" in d])
    # a joint plugged into a skin twice (the Hare's hood): found and merged, nothing moves
    from gus_rigtool.core import skin_tools
    cmds.select(clear=True)
    j1 = cmds.joint(name="chkTw_01_jnt", position=(0, 0, 0))
    cmds.joint(name="chkTw_02_jnt", position=(0, 10, 0))
    box = cmds.polyCube(name="chkTwBox", height=10, subdivisionsHeight=4)[0]
    cmds.move(0, 5, 0, box)
    sk = cmds.skinCluster([j1, "chkTw_02_jnt"], box, toSelectedBones=True)[0]
    cmds.connectAttr(j1 + ".worldMatrix[0]", sk + ".matrix[7]")
    cmds.setAttr(sk + ".bindPreMatrix[7]", cmds.getAttr(sk + ".bindPreMatrix[0]"), type="matrix")
    cmds.skinPercent(sk, box + ".vtx[0]", transformValue=[(j1, 1.0)])
    cmds.setAttr(sk + ".weightList[0].weights[7]", 0.0)
    rest = [cmds.pointPosition("%s.vtx[%d]" % (box, i), world=True) for i in range(6)]
    rep.expect("a joint plugged into the skin twice is found", skin_tools.twice(sk), str(skin_tools.twice(sk)))
    rep.step("merge its slots", skin_tools.merge_twice, sk)
    now = [cmds.pointPosition("%s.vtx[%d]" % (box, i), world=True) for i in range(6)]
    # 5.3.4: always evaluate off on a wave-like expression that drives a locked channel - nothing breaks
    from gus_rigtool.builder import chain
    g = cmds.group(empty=True, name="chkWave_01_wave_grp")
    ex = cmds.expression(string="%s.rotateY = sin(time) * 10;" % g, name="chkWave_wave_expr", alwaysEvaluate=True)
    cmds.setAttr(g + ".rotateY", lock=True)
    rep.step("always evaluate off (locked channel)", chain.stop_always_evaluating, [ex])
    cmds.currentTime(12)
    rep.expect("the expression still drives its group", abs(cmds.getAttr(g + ".rotateY") - math.sin(0.5) * 10) < 1e-3
               and not cmds.expression(ex, query=True, alwaysEvaluate=True) and
               cmds.getAttr(g + ".rotateY", lock=True), "rotateY %.3f" % cmds.getAttr(g + ".rotateY"))
    cmds.currentTime(1)
    rep.expect("merged: each joint once, the box doesn't move", not skin_tools.twice(sk) and
               max(sum((a - b) ** 2 for a, b in zip(p, q)) for p, q in zip(rest, now)) < 1e-6)


def check_limits535(rep):
    """5.3.5: limits on a control stop it; mirrored to a turned twin, tz flips."""
    from gus_rigtool.core import limits
    rep.start("Limits")
    _new_scene()
    lo = cmds.group(empty=True, name="L_chkLim_offset")
    ro = cmds.group(empty=True, name="R_chkLim_offset")
    cmds.setAttr(ro + ".rotateY", 180)
    L = cmds.parent(cmds.circle(name="L_chkLim_ctrl", constructionHistory=False)[0], lo)[0]
    R = cmds.parent(cmds.circle(name="R_chkLim_ctrl", constructionHistory=False)[0], ro)[0]
    rep.step("ty 0..32, tz 0..65 on the left", limits.set_limit, [L], "ty", 0, 32)
    limits.set_limit([L], "tz", 0, 65)
    cmds.setAttr(L + ".translateY", 50)
    rep.expect("moved past the max: it stops at 32", abs(cmds.getAttr(L + ".translateY") - 32) < 1e-6,
               "ty %.2f" % cmds.getAttr(L + ".translateY"))
    rep.step("mirror to the right", limits.mirror, [L])
    rep.expect("the turned twin: tz -65..0, ty 0..32", limits.get(R, "tz") == (-65, 0) and
               limits.get(R, "ty") == (0, 32), limits.describe(R))


def check_page_widths(rep):
    """5.4.0: every page of the main window fits its width in real Maya (no horizontal scroll bar)."""
    from gus_rigtool.core import ui
    rep.start("Pages fit the window")
    ui.open_panel(ui.MAIN_KEY)
    ui.build_all_pages()
    rows = ui.page_widths()
    wide = ["%s %d > %d" % (k, w, v) for k, w, v in rows if v and w > v + 4]
    rep.expect("%d page(s) measured, none wider than the window" % len(rows), rows and not wide, ", ".join(wide))


def check_network550(rep):
    """5.5.0: a driven key saved as a setup and made on another character (keys kept, it drives); unit conversions
    folded; protect / unprotect; the Node Editor shows a network; the rig map opens."""
    import tempfile
    from gus_rigtool.core import network_tools as NT, rig_map, setups
    rep.start("Networks: setups, Node Editor, protect")
    _new_scene()
    made = {}
    for who in ("Hare", "Fox"):
        c = cmds.circle(name=who + "_chkBrow_ctrl", constructionHistory=False)[0]
        g = cmds.group(empty=True, name=who + "_chkBrow_sdk")
        made[who] = (c, g)
    c, g = made["Hare"]
    cmds.setDrivenKeyframe(g + ".rotateX", currentDriver=c + ".translateY", driverValue=0, value=0)
    cmds.setDrivenKeyframe(g + ".rotateX", currentDriver=c + ".translateY", driverValue=1, value=-30)
    tmp = tempfile.mkdtemp()
    got = rep.step("save the Hare's brow", setups.save, [c], "chk_brow", tmp)
    if not got:
        return
    out = rep.step("make it on the Fox", setups.load, "chk_brow", "Hare", "Fox", "", tmp)
    if out:
        fc, fg = made["Fox"]
        cmds.setAttr(fc + ".translateY", 1)
        rep.expect("the Fox's brow ty 1 turns its group -30", abs(cmds.getAttr(fg + ".rotateX") + 30) < 1e-3,
                   "rx %.3f, %s" % (cmds.getAttr(fg + ".rotateX"), out))
        cmds.setAttr(fc + ".translateY", 0.5)
        hv = cmds.getAttr(fg + ".rotateX")
        cmds.setAttr(c + ".translateY", 0.5)
        rep.expect("the same curve (half way: the same value on both)", abs(hv - cmds.getAttr(g + ".rotateX")) < 1e-3,
                   "Fox %.3f, Hare %.3f" % (hv, cmds.getAttr(g + ".rotateX")))
    n = rep.step("protect the networks", NT.protect)
    if n:
        rep.expect("a driven-key curve can't be deleted", not _deletes(cmds.listConnections(g + ".rotateX")[0]))
        rep.step("unprotect", NT.unprotect)
    a = cmds.createNode("unitConversion")
    b = cmds.createNode("unitConversion")
    cmds.setAttr(a + ".conversionFactor", 2.0)
    cmds.setAttr(b + ".conversionFactor", 0.5)
    cmds.connectAttr(c + ".translateZ", a + ".input")
    cmds.connectAttr(a + ".output", b + ".input")
    cmds.connectAttr(b + ".output", g + ".translateZ")
    rep.expect("two unit conversions back to back found", len(NT.double_conversions()) == 1)
    rep.step("fold them", NT.fold_conversions)
    cmds.setAttr(c + ".translateZ", 3)
    rep.expect("folded: still drives the same", abs(cmds.getAttr(g + ".translateZ") - 3) < 1e-6)
    rep.step("show the brow's network in the Node Editor", NT.tidy, [c])
    rep.step("open the rig map", rig_map.show)
    for w in (rig_map.WIN,):
        if cmds.window(w, exists=True):
            cmds.deleteUI(w)


def check_zero551(rep):
    """5.5.1: keep the pose, zero the control - nothing moves."""
    from gus_rigtool.core import zero_pose
    rep.start("Keep the pose, zero the control")
    _new_scene()
    off = cmds.group(empty=True, name="chkZero_offset")
    cmds.move(5, 10, 0, off)
    c = cmds.parent(cmds.circle(name="chkZero_ctrl", constructionHistory=False)[0], off)[0]
    cmds.setAttr(c + ".translateY", 2.5)
    cmds.setAttr(c + ".rotateX", 30)
    m0 = cmds.xform(c, query=True, worldSpace=True, matrix=True)
    rep.step("zero it where it is", zero_pose.apply, [c])
    m1 = cmds.xform(c, query=True, worldSpace=True, matrix=True)
    rep.expect("it reads 0 and didn't move", cmds.getAttr(c + ".translateY") == 0 and
               max(abs(a - b) for a, b in zip(m0, m1)) < 1e-4)


def check_scale560(rep, height):
    """5.6.0: a built biped: Global > World > Local made, nothing moves; scaled x2 everything grows with it; a
    follicle outside the scale is found and fixed."""
    from gus_rigtool.core import scale_check as SC, world_levels as WL
    rep.start("World controls and scale")
    _new_scene()
    from gus_rigtool.builder import build as bld
    rep.step("biped template", bld.biped, height)
    rep.step("build", bld.build_all, height)
    world = rep.step("find the world control", WL.find_world)
    if not world:
        return
    some = [c for c in cmds.ls("*_ctrl", type="transform", long=True) if c != world][:20]
    before = dict((c, cmds.xform(c, query=True, worldSpace=True, matrix=True)) for c in some)
    got = rep.step("Global > World > Local", WL.make, world)
    if not got:
        return
    moved = [c for c in some if max(abs(a - b) for a, b in zip(before[c], cmds.xform(
        cmds.ls(c.split("|")[-1], long=True)[0], query=True, worldSpace=True, matrix=True))) > 1e-4]
    rep.expect("nothing moved", not moved, ", ".join(moved[:5]))
    r = SC.run()
    rep.expect("scaled x2 (on Global): everything grows with it", not r["off"] and not r["meshes"],
               "; ".join("%s %s" % (n.split("|")[-1], t) for n, _k, t in (r["off"] + r["meshes"])[:6]))
    surf = cmds.nurbsPlane(name="chkScale_srf", constructionHistory=False)[0]
    fol = cmds.createNode("follicle")
    ft = cmds.listRelatives(fol, parent=True)[0]
    cmds.connectAttr(surf + ".worldSpace[0]", fol + ".inputSurface")
    cmds.connectAttr(fol + ".outTranslate", ft + ".translate")
    grp = cmds.group(empty=True, name="chkScale_ribbon_grp")
    cmds.setAttr(grp + ".inheritsTransform", 0)
    cmds.parent(ft, grp)
    cmds.parent(cmds.circle(name="chkScale_ctrl", constructionHistory=False)[0], ft)
    rep.expect("a follicle in a group that doesn't pass the scale on: found", len(SC.follicles()) == 1)
    rep.step("fix it", SC.fix_follicles, SC.follicles(), SC.scale_control()[1])
    rep.expect("fixed", not SC.follicles())


def check_scale564(rep, height):
    """5.6.4: a group following World_ctrl by a parent constraint (an IK hand's 'root' space): after Global > World >
    Local its target scale still reads World_ctrl, and at x2 it goes where the scale takes it."""
    from gus_rigtool.core import scale_check as SC, world_levels as WL
    rep.start("Scale: spaces following the world")
    _new_scene()
    from gus_rigtool.builder import build as bld
    rep.step("biped template", bld.biped, height)
    rep.step("build", bld.build_all, height)
    world = rep.step("find the world control", WL.find_world)
    if not world:
        return
    sp = cmds.group(empty=True, name="chk564_space_grp")
    cmds.move(30, 60, 0, sp)
    con = cmds.parentConstraint(world, sp, maintainOffset=True)[0]
    got = rep.step("Global > World > Local", WL.make, world)
    if not got:
        return
    src = cmds.listConnections(con + ".target[0].targetScale", source=True, destination=False) or []
    rep.expect("the constraint's target scale still reads World_ctrl", src and src[0] == "World_ctrl"
               or (src and "World" in src[0]), str(src))
    rep.expect("no constraint target reads another node's scale", not SC.target_scales(), str(SC.target_scales()))
    g = WL.levels()["global"]
    before = cmds.xform(sp, query=True, worldSpace=True, translation=True)
    cmds.setAttr(g + ".globalScale", 2)
    after = cmds.xform(sp, query=True, worldSpace=True, translation=True)
    cmds.setAttr(g + ".globalScale", 1)
    gp = cmds.xform(g, query=True, worldSpace=True, translation=True)
    want = [gp[i] + (before[i] - gp[i]) * 2 for i in range(3)]
    off = max(abs(a - b) for a, b in zip(after, want))
    rep.expect("at x2 it goes where the scale takes it (off %.3f)" % off, off < 0.01)


def check_vis565(rep, height):
    """5.6.5: visibility switches on a built biped: Body_Ctrls off hides the controls' shapes (their groups stay
    shown, nothing moves); Geometry off hides geo_grp; all on again shows everything."""
    from gus_rigtool.core import vis_switch as VS
    rep.start("Visibility switches")
    _new_scene()
    from gus_rigtool.builder import build as bld
    rep.step("biped template", bld.biped, height)
    rep.step("build", bld.build_all, height)
    head = (cmds.ls("*head*_ctrl", type="transform", long=True) or cmds.ls("*Head*_ctrl", type="transform",
                                                                              long=True) or [None])[0]
    if not head:
        rep.expect("a head control", False)
        return
    got = rep.step("make the switches", VS.make, head)
    if not got:
        return
    sw = got["control"]
    body = [c for c in VS.controls() if VS.switch_of(c, sw) == "Body_Ctrls"]
    rep.expect("controls on Body (%d)" % len(body), body)
    if not body:
        return
    c = body[0]
    shape = cmds.listRelatives(c, shapes=True, fullPath=True)[0]
    cmds.setAttr(sw + ".Body_Ctrls", 0)
    rep.expect("Body off: %s's shape hidden, the control itself still visible" % c.split("|")[-1],
               not cmds.getAttr(shape + ".visibility") and cmds.getAttr(c + ".visibility"))
    cmds.setAttr(sw + ".Body_Ctrls", 1)
    rep.expect("Body on: shown again", cmds.getAttr(shape + ".visibility"))
    geo = cmds.ls("geo_grp", long=True)
    if geo:
        cmds.setAttr(sw + ".Geometry", 0)
        rep.expect("Geometry off: geo_grp drawn hidden", not cmds.getAttr(geo[0] + ".overrideVisibility"))
        cmds.setAttr(sw + ".Geometry", 1)
    rep.expect("the switch control is on no switch", VS.switch_of(sw) is None)


def check_space567(rep, height):
    """5.6.7: standard spaces on a built biped (its offset groups are locked, like the Hare's): nothing moves, the
    offsets are locked again, each space chosen at rest doesn't jump, nothing drifts at scale x2."""
    import math
    from gus_rigtool.core import spaces, space_check
    rep.start("Spaces on locked offsets")
    _new_scene()
    from gus_rigtool.builder import build as bld
    rep.step("biped template", bld.biped, height)
    rep.step("build", bld.build_all, height)
    plan = rep.step("standard spaces plan", spaces.standard_plan) or []
    rep.expect("a plan (%d)" % len(plan), plan, str([(c, k) for c, _t, k in plan]))
    if not plan:
        return
    joints = cmds.ls(type="joint", long=True)
    pos = lambda n: cmds.xform(n, query=True, worldSpace=True, translation=True)
    before = dict((j, pos(j)) for j in joints)
    made, failed = spaces.standard(plan)
    rep.expect("all made (%d)" % len(made), not failed, str(failed))
    worst = max(math.sqrt(sum((a - b) ** 2 for a, b in zip(before[j], pos(j)))) for j in joints if cmds.objExists(j))
    rep.expect("no joint moved (worst %.4f)" % worst, worst < 0.01)
    for c in made:
        piece = spaces.piece_of(c)
        rep.expect("%s's group locked again" % piece.split("|")[-1], cmds.getAttr(piece + ".translateX", lock=True)
                   or not cmds.getAttr(piece + ".translateX", settable=False))
        break
    r = space_check.run()
    rep.expect("every space at rest: no jumps", not r["jumps"], str(r["jumps"][:4]))
    rep.expect("at x2: nothing drifts", not r["scale"], str(r["scale"][:4]))


def check_group568(rep, height):
    """5.6.8: a group control moved 1 on X / Y: each control it drives moves weight x that in the world, whatever
    its own axes (lip controls turned 60 degrees); the right corner (mirrored) moves them the mirror way."""
    import math
    from gus_rigtool.core import group_ctrls as GC
    rep.start("Group controls")
    _new_scene()
    head = cmds.circle(name="Head_ctrl", constructionHistory=False)[0]
    cmds.move(0, 150, 0, head)
    cmds.setAttr(head + ".scaleX", 25.826)            # 5.6.10: like the Hare's Head_01_CTRL - scaled unevenly, turned
    cmds.setAttr(head + ".rotateY", 30)
    ctrls = []
    for i, (x, rot) in enumerate(((-4, -60), (0, 0), (4, 60))):
        off = cmds.group(empty=True, name="lip%d_offset" % i, parent=head)
        cmds.xform(off, worldSpace=True, translation=[x, 150, 10])
        cmds.setAttr(off + ".rotateY", rot)
        c = cmds.circle(name="lip%d_ctrl" % i, constructionHistory=False)[0]
        c = cmds.parent(c, off, relative=True)[0]
        ctrls.append(c)
    pos = lambda n: cmds.xform(n, query=True, worldSpace=True, translation=True)
    g = rep.step("make a group control", GC.make, "Lips_ctrl", {"lip0_ctrl": 0.5, "lip1_ctrl": 1.0,
                                                                 "lip2_ctrl": 0.25}, [0, 150, 14], head, 1.0)
    r = rep.step("make a mirrored one", GC.make, "R_Corner_ctrl", {"lip0_ctrl": 1.0}, [-5, 150, 14], head, 1.0,
                 "circle", "R", True)
    if not g or not r:
        return
    before = dict((c, pos(GC._long(c))) for c in ("lip0_ctrl", "lip1_ctrl", "lip2_ctrl"))
    rep.expect("nothing moved when made", True)
    cmds.setAttr(g + ".translateX", 1)
    cmds.setAttr(g + ".translateY", 2)
    for c, w in (("lip0_ctrl", 0.5), ("lip1_ctrl", 1.0), ("lip2_ctrl", 0.25)):
        p = pos(GC._long(c))
        want = [before[c][0] + w, before[c][1] + 2 * w, before[c][2]]
        off = math.sqrt(sum((a - b) ** 2 for a, b in zip(p, want)))
        rep.expect("%s moved %.2f x (1, 2, 0) in the world (off %.4f)" % (c, w, off), off < 1e-3)
    cmds.setAttr(g + ".translateX", 0)
    cmds.setAttr(g + ".translateY", 0)
    cmds.setAttr(r + ".translateX", 1)
    p = pos(GC._long("lip0_ctrl"))
    rep.expect("the mirrored right corner: +1 X moves the lip -1 X in the world (got %.3f)" % (p[0] - before["lip0_ctrl"][0]),
               abs(p[0] - before["lip0_ctrl"][0] + 1.0) < 1e-3)
    wm = cmds.xform(cmds.listRelatives(r, parent=True, fullPath=True)[0], query=True, worldSpace=True, matrix=True)
    sizes = [math.sqrt(sum(v * v for v in wm[k * 4:k * 4 + 3])) for k in range(3)]
    rep.expect("under the stretched head its group is a clean mirror: size 1, 1, 1 (got %s)" % [round(x, 3) for x in sizes],
               max(abs(x - 1) for x in sizes) < 1e-3)
    cmds.setAttr(r + ".translateX", 0)
    g2 = rep.step("a second group control on the same lip (5.6.8 crashed here)", GC.make, "Lips2_ctrl",
                  {"lip1_ctrl": 0.5}, [0, 155, 14], head, 1.0)
    if g2:
        cmds.setAttr(g + ".translateY", 1)
        cmds.setAttr(g2 + ".translateY", 1)
        cmds.setAttr(g + ".rotateZ", 10)
        p = pos(GC._long("lip1_ctrl"))
        rep.expect("both at once: lip1 moved 1 + 0.5 up (got %.3f)" % (p[1] - before["lip1_ctrl"][1]),
                   abs(p[1] - before["lip1_ctrl"][1] - 1.5) < 1e-3)
        from gus_rigtool.core import space_check
        lay = GC.layer_of(GC._long("lip1_ctrl"))
        cmds.setAttr(g + ".rotateZ", 0)
        m0 = cmds.xform(lay, query=True, worldSpace=True, matrix=True)
        cmds.setAttr(g + ".rotateZ", 10)
        turned = space_check._angle(m0, cmds.xform(lay, query=True, worldSpace=True, matrix=True))
        rep.expect("a turn passes through Maya's unit conversion: lip1 turns 10 degrees (got %.3f)" % turned,
                   abs(turned - 10.0) < 0.05)
        for a in ("translateY", "rotateZ"):
            cmds.setAttr(g + "." + a, 0)
        cmds.setAttr(g2 + ".translateY", 0)
        GC.remove(g2)
    GC.remove(g)
    GC.remove(r)
    back = max(math.sqrt(sum((a - b) ** 2 for a, b in zip(pos(GC._long(c)), before[c]))) for c in before)
    rep.expect("removed: the controls where they were, no layers left (%.4f)" % back,
               back < 1e-4 and not cmds.ls("*_groups", type="transform"))


def check_squash5611(rep, height):
    """5.6.11 / 5.6.14: head squash on a ball head with face controls and a body below: nothing moves at rest; down
    squashes (shorter, wider); up stretches; sideways bends the top that way; the body below never moves; the face
    controls keep their colour; off puts everything back; Remove leaves the ball as it was."""
    from gus_rigtool.core import head_squash as HS
    rep.start("Head squash")
    _new_scene()
    head = cmds.circle(name="Head_ctrl", constructionHistory=False, normal=(0, 1, 0), radius=12)[0]
    cmds.move(0, 150, 0, head)
    ball = cmds.polySphere(name="Ball_geo", radius=10, subdivisionsX=24, subdivisionsY=24, constructionHistory=False)[0]
    cmds.move(0, 165, 0, ball)
    for n, p in (("L_Mouth_fol_06_ctrl", (4, 160, 9)), ("R_Mouth_fol_22_ctrl", (-4, 160, 9)),
                 ("L_Brow_ctrl", (4, 170, 9)), ("R_Brow_ctrl", (-4, 170, 9))):
        c = cmds.circle(name=n, constructionHistory=False, radius=0.5)[0]
        cmds.move(p[0], p[1], p[2], c)
        cmds.parent(c, head)
    cmds.setAttr("L_Brow_ctrlShape.overrideEnabled", 1)
    cmds.setAttr("L_Brow_ctrlShape.overrideColor", 13)
    body = cmds.polyCube(name="Body_geo", width=20, height=60, depth=10, constructionHistory=False)[0]
    cmds.move(0, 100, 0, body)                                    # the rest of the body, well below the head
    # 5.6.16: an ear built like the Hare's - FK, IK, tweak, settings in their own branches inside L_Ear_ctrls_grp,
    # the group held by a constraint to the head
    ear_grp = cmds.group(empty=True, name="L_Ear_ctrls_grp", world=True)
    cmds.parentConstraint(head, ear_grp, maintainOffset=True)
    for n, y in (("L_Ear_01_FK_ctrl", 184), ("L_Ear_01_IK_ctrl", 184), ("L_Ear_03_tweak_ctrl", 194),
                 ("L_Ear_settings_ctrl", 188)):            # 5.6.17: the base above the face's box (the Hare's)
        o = cmds.group(empty=True, name=n.replace("_ctrl", "_offset"), parent=ear_grp)
        cmds.xform(o, worldSpace=True, translation=(5, y, 0))
        cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=1)[0], o, relative=True)
    # 5.6.18: an FK chain whose zero is held by the head (the Hare's) - it ignored the follow group
    fz = cmds.group(empty=True, name="L_Ear_02_FK_zero", parent=ear_grp)
    cmds.xform(fz, worldSpace=True, translation=(5, 190, 0))
    cmds.parent(cmds.circle(name="L_Ear_02_FK_ctrl", constructionHistory=False, radius=1)[0], fz, relative=True)
    cmds.parentConstraint(head, fz, maintainOffset=True)
    fk0 = cmds.xform("L_Ear_02_FK_ctrl", query=True, worldSpace=True, translation=True)
    ear = cmds.ls("L_Ear_01_FK_ctrl", long=True)[0]
    tip = cmds.ls("L_Ear_03_tweak_ctrl", long=True)[0]
    ear0 = cmds.xform(ear, query=True, worldSpace=True, translation=True)
    tip0 = cmds.xform(tip, query=True, worldSpace=True, translation=True)
    # 5.6.17: the ball skinned, like the Hare's meshes (Maya copied them for the lattice placed 'after')
    cmds.select(clear=True)
    jnt = cmds.joint(name="head_jnt", position=(0, 150, 0))
    cmds.skinCluster(jnt, ball, toSelectedBones=True)
    shapes = lambda: len(cmds.listRelatives(ball, shapes=True) or [])
    n0 = shapes()
    cmds.setAttr(head + ".scale", 2, 2, 2, type="double3")            # where the ear is with the rig at x2
    ear2 = cmds.xform(ear, query=True, worldSpace=True, translation=True)
    fkx2 = cmds.xform("L_Ear_02_FK_ctrl", query=True, worldSpace=True, translation=True)
    cmds.setAttr(head + ".scale", 1, 1, 1, type="double3")
    box = lambda: cmds.exactWorldBoundingBox(ball)
    b0 = box()
    body0 = cmds.exactWorldBoundingBox(body)
    cv0 = cmds.xform("L_Brow_ctrlShape.cv[0]", query=True, worldSpace=True, translation=True)
    c = rep.step("make", HS.make, head, [ball, body])
    if not c:
        return
    n1 = shapes()
    rep.expect("no extra copy of the mesh kept (shapes %d -> %d: the lattice's one hidden copy at most)" % (n0, n1),
               n1 <= n0 + 1 and not HS.mesh_copies(ball))
    rep.expect("the squash after the skin", HS.after_skin(cmds.ls(ball, long=True)[0]))
    fc, fs = HS.region(head, HS.face_controls())
    rep.expect("the ear's base (y %.1f) above the face's box (top %.1f) - the lattice reaches it" % (
        ear0[1], fc[1] + fs[1] / 2.0), ear0[1] > fc[1] + fs[1] / 2.0)
    cmds.setAttr(head + ".scale", 2, 2, 2, type="double3")
    e2 = cmds.xform(ear, query=True, worldSpace=True, translation=True)
    f2 = cmds.xform(cmds.ls("L_Ear_02_FK_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    cmds.setAttr(head + ".scale", 1, 1, 1, type="double3")
    rep.expect("the rig at x2: the held FK where it would be (off by %.4f)" % max(abs(a - b) for a, b in
                                                                                zip(f2, fkx2)),
               max(abs(a - b) for a, b in zip(f2, fkx2)) < 1e-2)
    rep.expect("the rig at x2: the ear where it would be without the squash (off by %.4f - 5.6.16 drifted)" %
               max(abs(a - b) for a, b in zip(e2, ear2)), max(abs(a - b) for a, b in zip(e2, ear2)) < 1e-2)
    rep.expect("nothing moved at rest", max(abs(a - b) for a, b in zip(b0, box())) < 1e-3)
    h = b0[4] - b0[1]
    cmds.setAttr(c + ".translateY", -h * 0.3)
    b1 = box()
    tall, wide = (b1[4] - b1[1]) / h, (b1[3] - b1[0]) / (b0[3] - b0[0])
    rep.expect("down squashes: shorter (x%.2f), wider (x%.2f)" % (tall, wide), tall < 0.95 and wide > 1.02)
    moved = max(abs(a - b) for a, b in zip(body0, cmds.exactWorldBoundingBox(body)))
    rep.expect("the rest of the body doesn't move (%.5f) - 5.6.13 moved it all" % moved, moved < 1e-4)
    vis = [x for x in cmds.listRelatives("L_Brow_ctrl", shapes=True, fullPath=True) or []
           if not cmds.getAttr(x + ".intermediateObject") and cmds.getAttr(x + ".visibility")]
    rep.expect("the face controls keep their colour and their curve you see, same name (5.6.13 hid them)",
               cmds.getAttr("L_Brow_ctrlShape.overrideColor") == 13 and len(vis) == 1 and
               vis[0].split("|")[-1] == "L_Brow_ctrlShape")
    brow_t0 = cmds.xform("L_Brow_ctrl", query=True, worldSpace=True, translation=True)
    cmds.setAttr(c + ".translateY", h * 0.3)
    rep.expect("up stretches (x%.2f tall)" % ((box()[4] - box()[1]) / h), (box()[4] - box()[1]) / h > 1.05)
    cmds.setAttr(c + ".translateY", 0)
    cmds.setAttr(c + ".translateX", h * 0.3)
    b2 = box()
    rep.expect("sideways (+X) bends the top that way (box moved %.2f on X)" % (((b2[0] + b2[3]) - (b0[0] + b0[3])) / 2),
               ((b2[0] + b2[3]) - (b0[0] + b0[3])) / 2 > 0.1)
    moved = max(abs(a - b) for a, b in zip(body0, cmds.exactWorldBoundingBox(body)))
    rep.expect("bent: the rest of the body still doesn't move (%.5f)" % moved, moved < 1e-4)
    cv1 = cmds.xform("L_Brow_ctrlShape.cv[0]", query=True, worldSpace=True, translation=True)
    rep.expect("5.6.18 bent: the brow control's curve rides the face (moved %.2f on X)" % (cv1[0] - cv0[0]),
               cv1[0] - cv0[0] > 0.1)
    bt = cmds.xform("L_Brow_ctrl", query=True, worldSpace=True, translation=True)
    rep.expect("...the control itself stays (what it drives isn't moved twice) - moved %.5f" %
               max(abs(a - b) for a, b in zip(bt, brow_t0)), max(abs(a - b) for a, b in zip(bt, brow_t0)) < 1e-5)
    rep.expect("...its colour kept while riding", cmds.getAttr("L_Brow_ctrlShape.overrideColor") == 13)
    ex = cmds.xform(cmds.ls("L_Ear_01_FK_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    tx = cmds.xform(cmds.ls("L_Ear_03_tweak_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    rep.expect("bent: the ear rides the top of the head (moved %.2f on X)" % (ex[0] - ear0[0]), ex[0] - ear0[0] > 0.1)
    fk1 = cmds.xform(cmds.ls("L_Ear_02_FK_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    rep.expect("5.6.18 bent: the FK held by the head rides too (moved %.2f on X)" % (fk1[0] - fk0[0]),
               fk1[0] - fk0[0] > 0.1)
    rep.expect("...the whole ear rig together: the tweak too (%.2f), one follow for the ear (%s)" % (
        tx[0] - tip0[0], [e["ctrl"] for e in HS.read().get("ears", [])]), tx[0] - tip0[0] > 0.1 and
        [e["ctrl"] for e in HS.read().get("ears", [])] == ["L_Ear_ctrls_grp"])
    cmds.setAttr(c + ".translateY", -h * 0.3)
    sw = HS.read().get("switch")
    cmds.setAttr(sw, 0)
    rep.expect("off: back to rest", max(abs(a - b) for a, b in zip(b0, box())) < 1e-3)
    cmds.setAttr(sw, 1)
    cmds.setAttr(c + ".translateX", 0)
    cmds.setAttr(c + ".translateY", 0)
    cmds.setAttr(head + ".rotateZ", 30)
    rep.expect("the head turns, the squash at 0: the lattice turns with it and changes nothing (no double move)",
               max(abs(a - b) for a, b in zip(b0, box())) < 1e-3)
    cmds.setAttr(head + ".rotateZ", 0)
    rep.step("remove", HS.remove)
    rep.expect("removed: the ball as it was", max(abs(a - b) for a, b in zip(b0, box())) < 1e-3 and not HS.find())
    ex = cmds.xform(cmds.ls("L_Ear_01_FK_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    rep.expect("removed: the ear back where it was, its controls back in L_Ear_ctrls_grp",
               max(abs(a - b) for a, b in zip(ex, ear0)) < 1e-3 and
               cmds.listRelatives("L_Ear_01_FK_offset", parent=True)[0] == "L_Ear_ctrls_grp")
    rep.expect("removed: the mesh's shapes as before (%d -> %d)" % (n0, shapes()), shapes() == n0)
    fk2 = cmds.xform(cmds.ls("L_Ear_02_FK_ctrl", long=True)[0], query=True, worldSpace=True, translation=True)
    rep.expect("removed: the held FK back under its zero, where it was (%.5f)" % max(abs(a - b) for a, b in
                                                                                    zip(fk2, fk0)),
               max(abs(a - b) for a, b in zip(fk2, fk0)) < 1e-3 and
               cmds.listRelatives("L_Ear_02_FK_ctrl", parent=True)[0] == "L_Ear_02_FK_zero")
    cv2 = cmds.xform("L_Brow_ctrlShape.cv[0]", query=True, worldSpace=True, translation=True)
    rep.expect("removed: the brow curve back where it was (%.5f), one curve, its colour" %
               max(abs(a - b) for a, b in zip(cv2, cv0)),
               max(abs(a - b) for a, b in zip(cv2, cv0)) < 1e-4 and
               len(cmds.listRelatives("L_Brow_ctrl", shapes=True) or []) == 1 and
               cmds.getAttr("L_Brow_ctrlShape.overrideColor") == 13)
    c = rep.step("make again", HS.make, head, [ball, body])
    if c:
        rep.expect("made again: still no extra copies (shapes %d)" % shapes(), shapes() <= n0 + 1 and
                   not HS.mesh_copies(ball))
        rep.step("remove again", HS.remove)
        rep.expect("removed again: shapes as before (%d)" % shapes(), shapes() == n0)


def check_poses5612(rep, height):
    """5.6.12: pose the face, Save as Smile: the face back at rest; Smile_L + Smile_R at 1 put every control back
    exactly where it was posed (a lip turned 90 on Y, moved and turned too); half each at the middle; selection
    sets made."""
    from gus_rigtool.core import face_poses as FP
    rep.start("Face expressions")
    _new_scene()
    head = cmds.circle(name="Head_ctrl", constructionHistory=False, radius=10)[0]
    cmds.move(0, 150, 0, head)
    ctrls = {}
    for n, p, ry in (("L_Mouth_fol_06_ctrl", (4, 150, 10), 0), ("R_Mouth_fol_22_ctrl", (-4, 150, 10), 0),
                     ("Mouth_fol_33_ctrl", (0, 149, 11), 0), ("L_Mouth_fol_02_ctrl", (2, 151, 10.5), 90)):
        off = cmds.group(empty=True, name=n + "_offset", parent=head)
        cmds.xform(off, worldSpace=True, translation=p)
        cmds.setAttr(off + ".rotateY", ry)
        c = cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=0.5)[0], off, relative=True)[0]
        ctrls[n] = c
    # 5.6.19: a chain (the ear's FK) in the pose - each link under the one before
    par = head
    for i, y in ((1, 165), (2, 172), (3, 179)):
        n = "L_Ear_0%d_FK_ctrl" % i
        off = cmds.group(empty=True, name=n + "_offset", parent=par)
        cmds.xform(off, worldSpace=True, translation=(6, y, 0))
        par = cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=0.5)[0], off, relative=True)[0]
        ctrls[n] = par
    holder = cmds.circle(name="Mouth_main_ctrl", constructionHistory=False, radius=3)[0]
    cmds.parent(holder, head)
    wm = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)
    rest = dict((n, wm(n)) for n in ctrls)
    cmds.setAttr("L_Mouth_fol_06_ctrl.translateY", 1)
    cmds.setAttr("R_Mouth_fol_22_ctrl.translateY", 1)
    cmds.setAttr("Mouth_fol_33_ctrl.translateY", 0.4)
    cmds.setAttr("L_Mouth_fol_02_ctrl.translate", 0.3, 0.5, -1, type="double3")
    cmds.setAttr("L_Mouth_fol_02_ctrl.rotate", 10, 5, -8, type="double3")
    cmds.setAttr("L_Ear_01_FK_ctrl.rotate", 0, 5, 20, type="double3")
    cmds.setAttr("L_Ear_02_FK_ctrl.rotateZ", 15)
    cmds.setAttr("L_Ear_03_FK_ctrl.translateX", 0.4)
    posed = dict((n, wm(n)) for n in ctrls)
    # a save that stops part way: taken back (the face as posed)
    from unittest import mock
    from gus_rigtool.core import group_ctrls as GC
    real, calls = GC._add_layer, []
    def boom(node, carries):
        calls.append(node)
        if len(calls) == 3:
            raise RuntimeError("stopped on purpose")
        return real(node, carries)
    with mock.patch.object(GC, "_add_layer", side_effect=boom):
        try:
            FP.save_pose("Mouth_main_ctrl", "Smile", True)
            failed = False
        except RuntimeError:
            failed = True
    back = max(max(abs(a - b) for a, b in zip(wm(n), posed[n])) for n in ctrls)
    rep.expect("5.6.19 a save stopped part way: taken back - the face as posed (%.5f), no Smile" % back,
               failed and back < 1e-4 and not cmds.attributeQuery("Smile_L", node="Mouth_main_ctrl", exists=True))
    got = rep.step("save Smile", FP.save_pose, "Mouth_main_ctrl", "Smile", True)
    if not got:
        return
    back = max(max(abs(a - b) for a, b in zip(wm(n), rest[n])) for n in ctrls)
    rep.expect("the face back at rest (%.5f)" % back, back < 1e-4)
    cmds.setAttr("Mouth_main_ctrl.Smile_L", 1)
    cmds.setAttr("Mouth_main_ctrl.Smile_R", 1)
    for n in ctrls:
        off = max(abs(a - b) for a, b in zip(wm(n), posed[n]))
        rep.expect("%s back where it was posed, turn included (%.5f)" % (n, off), off < 1e-3)
    cmds.setAttr("Mouth_main_ctrl.Smile_R", 0)
    y = wm("Mouth_fol_33_ctrl")[13] - rest["Mouth_fol_33_ctrl"][13]
    rep.expect("only Smile_L: the middle goes half way (%.3f of 0.4)" % y, abs(y - 0.2) < 1e-3)
    rep.expect("only Smile_L: the right corner stays", max(abs(a - b) for a, b in zip(wm("R_Mouth_fol_22_ctrl"),
                                                                                      rest["R_Mouth_fol_22_ctrl"])) < 1e-4)
    cmds.setAttr("Mouth_main_ctrl.Smile_L", 0)
    # 5.6.20: a pose made on top of another - Smile on, the middle up more, saved as Grin: Grin alone gives the
    # face as it was seen
    cmds.setAttr("Mouth_main_ctrl.Smile_L", 1)
    cmds.setAttr("Mouth_main_ctrl.Smile_R", 1)
    cmds.setAttr("Mouth_fol_33_ctrl.translateY", 0.3)
    seen = dict((n, wm(n)) for n in ctrls)
    if rep.step("save Grin on top of Smile", FP.save_pose, "Mouth_main_ctrl", "Grin", False, True):
        rep.expect("after: Smile off too", cmds.getAttr("Mouth_main_ctrl.Smile_L") == 0)
        cmds.setAttr("Mouth_main_ctrl.Grin", 1)
        off = max(max(abs(a - b) for a, b in zip(wm(n), seen[n])) for n in ctrls)
        rep.expect("5.6.20 Grin alone = the face as it was seen (Smile + the change), off by %.5f" % off, off < 1e-3)
        cmds.setAttr("Mouth_main_ctrl.Grin", 0)
        rep.step("remove Grin", FP.remove_pose, "Mouth_main_ctrl", "Grin")
    # a layer that lost a sum node: Refresh / Save repair it
    lay = GC.layer_of(cmds.ls("L_Mouth_fol_06_ctrl", long=True)[0])
    if lay and GC._sum_of(lay, "rotate"):
        cmds.delete(GC._sum_of(lay, "rotate"))
        fixed = GC.repair_layers()
        rep.expect("5.6.20 a broken layer repaired (%s)" % fixed["healed"],
                   GC._sum_of(lay, "translate") and GC._sum_of(lay, "rotate"))
    got = rep.step("edit Smile", FP.edit_pose, "Mouth_main_ctrl", "Smile")
    if got:
        off = max(max(abs(a - b) for a, b in zip(wm(n), posed[n])) for n in ctrls)
        rep.expect("5.6.18 edit: the pose back on its controls, sliders at 0 (off by %.5f)" % off,
                   off < 1e-3 and cmds.getAttr("Mouth_main_ctrl.Smile_L") == 0)
        FP.zero_drivers()
    from gus_rigtool.core import face_sliders as FS
    board = rep.step("sliders board", FS.make, "Mouth_main_ctrl", head)
    if board:
        size = FS.face_box(head)[1][1] * 0.6
        amount, shift = [cmds.ls(k, long=True)[0] for k in board["Smile"]]
        bx = cmds.exactWorldBoundingBox(FS.find())
        fc, fs = FS.face_box(head)
        rep.expect("the board beside the face, not inside it (starts at x %.1f, the face ends at %.1f)" % (
            bx[0], fc[0] + fs[0] / 2.0), bx[0] > fc[0] + fs[0] / 2.0)
        rep.expect("the knobs rest at 0 (amount %s, shift %s) - their offset groups hold the place" % (
            cmds.getAttr(amount + ".translate")[0], cmds.getAttr(shift + ".translate")[0]),
            max(abs(v) for v in cmds.getAttr(amount + ".translate")[0] + cmds.getAttr(shift + ".translate")[0])
            < 1e-6 and abs(cmds.getAttr("Mouth_main_ctrl.Smile_L")) < 1e-6)
        rep.expect("the board within the face's height (%.1f .. %.1f, the face %.1f .. %.1f)" % (
            bx[1], bx[4], fc[1] - fs[1] / 2.0, fc[1] + fs[1] / 2.0),
            bx[1] >= fc[1] - fs[1] / 2.0 - 1e-3 and bx[4] <= fc[1] + fs[1] / 2.0 + 1e-3)
        from gus_rigtool.tools import checker
        frames = [n for n in cmds.listRelatives(FS.find(), allDescendents=True, type="transform", fullPath=True)
                  if "_frame" in n or "_label" in n]
        rep.expect("frames and labels aren't controls for the checker (%d)" % len(frames),
                   frames and not any(checker.is_control(n) for n in frames))
        cmds.setAttr(amount + ".translateY", size)
        rep.expect("amount knob at the top: Smile_L 1, Smile_R 1 (got %.3f, %.3f)" % (
            cmds.getAttr("Mouth_main_ctrl.Smile_L"), cmds.getAttr("Mouth_main_ctrl.Smile_R")),
            abs(cmds.getAttr("Mouth_main_ctrl.Smile_L") - 1) < 1e-4 and
            abs(cmds.getAttr("Mouth_main_ctrl.Smile_R") - 1) < 1e-4)
        cmds.setAttr(shift + ".translateX", cmds.getAttr(shift + ".translateX") + size * 0.25)
        rep.expect("shift knob all the way left: Smile_L 1, Smile_R 0 (got %.3f, %.3f)" % (
            cmds.getAttr("Mouth_main_ctrl.Smile_L"), cmds.getAttr("Mouth_main_ctrl.Smile_R")),
            abs(cmds.getAttr("Mouth_main_ctrl.Smile_L") - 1) < 1e-4 and
            abs(cmds.getAttr("Mouth_main_ctrl.Smile_R")) < 1e-4)
        cmds.setAttr(amount + ".translateY", 0)                             # reset (the only channels open)
        cmds.setAttr(shift + ".translateX", 0)
        rep.expect("reset: the sliders back to 0 (%.3f, %.3f)" % (cmds.getAttr("Mouth_main_ctrl.Smile_L"),
                                                                    cmds.getAttr("Mouth_main_ctrl.Smile_R")),
                   abs(cmds.getAttr("Mouth_main_ctrl.Smile_L")) < 1e-6 and
                   abs(cmds.getAttr("Mouth_main_ctrl.Smile_R")) < 1e-6)
        FS.remove()
    sets = rep.step("selection sets", FP.make_sets, [cmds.ls(n, long=True)[0] for n in ctrls])
    rep.expect("sets in gus_anim_sets (%s)" % sets, sets and cmds.objExists("gus_anim_sets"))
    rep.step("remove", FP.remove_pose, "Mouth_main_ctrl", "Smile")


def check_poses5620(rep):
    """5.6.20: one pose with the lids closed through driven keys (the master's tz -> a group above each lid
    control), the tongue curled by Face_settings_ctrl.curl (-> a group above the tongue control), the ear's FK chain
    and a brow: played back alone, every control exactly where the face showed it."""
    from gus_rigtool.core import face_poses as FP
    rep.start("Expressions - lids, tongue curl, ears, brows in one pose")
    _new_scene()
    head = cmds.circle(name="Head_01_CTRL", constructionHistory=False, radius=10)[0]
    cmds.move(0, 150, 0, head)
    def ctrl(n, pos, parent):
        off = cmds.group(empty=True, name=n + "_offset", parent=parent)
        cmds.xform(off, worldSpace=True, translation=pos)
        return cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=0.5)[0], off, relative=True)[0]
    master = ctrl("L_Upper_Eyelids_ctrl", (5, 158, 11), head)
    sdk = cmds.group(empty=True, name="L_Eyelids_fol_01_ctrl_Upper_Lid", parent=head)
    cmds.xform(sdk, worldSpace=True, translation=(5, 156, 11))
    cmds.parent(cmds.circle(name="L_Eyelids_fol_01_ctrl", constructionHistory=False, radius=0.3)[0], sdk,
                relative=True)
    for dv, v, rx in ((0, 0, 0), (2, -1.5, 40)):
        cmds.setDrivenKeyframe(sdk + ".translateY", currentDriver=master + ".translateZ", driverValue=dv, value=v)
        cmds.setDrivenKeyframe(sdk + ".rotateX", currentDriver=master + ".translateZ", driverValue=dv, value=rx)
    fs = ctrl("Face_settings_ctrl", (12, 150, 0), head)
    cmds.addAttr(fs, longName="curl", attributeType="double", keyable=True)
    cmds.addAttr(fs, longName="ikfk", attributeType="double", keyable=True)
    cg = cmds.group(empty=True, name="Tongue_01_curl_grp", parent=head)
    cmds.xform(cg, worldSpace=True, translation=(0, 146, 6))
    cmds.connectAttr(fs + ".curl", cg + ".rotateZ")
    cmds.parent(cmds.circle(name="Tongue_02_FK_ctrl", constructionHistory=False, radius=0.3)[0], cg)
    cmds.xform("Tongue_02_FK_ctrl", worldSpace=True, translation=(0, 146, 8))
    e1 = ctrl("L_Ear_01_FK_ctrl", (6, 168, 0), head)
    e2 = ctrl("L_Ear_02_FK_ctrl", (6, 176, 0), e1)
    brow = ctrl("L_Brow_ctrl", (4, 162, 10), head)
    ctrl("Mouth_main_ctrl", (0, 146, 14), head)
    names = ["L_Eyelids_fol_01_ctrl", "Tongue_02_FK_ctrl", "L_Ear_01_FK_ctrl", "L_Ear_02_FK_ctrl", "L_Brow_ctrl"]
    wm = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)
    rest = dict((n, wm(n)) for n in names)
    cmds.setAttr(master + ".translateZ", 2)
    cmds.setAttr(fs + ".curl", 30)
    cmds.setAttr(fs + ".ikfk", 1)
    cmds.setAttr(e1 + ".rotateZ", 20)
    cmds.setAttr(e2 + ".rotateZ", 15)
    cmds.setAttr(brow + ".translateY", 0.8)
    seen = dict((n, wm(n)) for n in names)
    got = rep.step("save Wink", FP.save_pose, "Mouth_main_ctrl", "Wink", False, False)
    if not got:
        return
    back = max(max(abs(a - b) for a, b in zip(wm(n), rest[n])) for n in names)
    rep.expect("the face at rest after (%.5f); curl at 0, ikfk kept at 1" % back,
               back < 1e-4 and cmds.getAttr(fs + ".curl") == 0 and cmds.getAttr(fs + ".ikfk") == 1)
    cmds.setAttr("Mouth_main_ctrl.Wink", 1)
    for n in names:
        off = max(abs(a - b) for a, b in zip(wm(n), seen[n]))
        rep.expect("Wink alone: %s where the face showed it (%.5f)" % (n, off), off < 1e-3)


def check_poses5621(rep):
    """5.6.21: a real skinned ribbon - control A bends it and its follicle carries neighbour B. A pose of A up:
    played back alone, A and B exactly where the face showed them (5.6.20 moved B twice)."""
    from gus_rigtool.core import face_poses as FP
    rep.start("Expressions - a ribbon's neighbour isn't moved twice")
    _new_scene()
    head = cmds.circle(name="Head_01_CTRL", constructionHistory=False, radius=10)[0]
    cmds.move(0, 150, 0, head)
    srf = cmds.nurbsPlane(name="Mouth_ribbon_srf", axis=(0, 0, 1), width=10, lengthRatio=0.2, patchesU=4,
                          patchesV=1, constructionHistory=False)[0]
    cmds.move(0, 145, 10, srf)
    ctrls = []
    for n, x in (("L_Mouth_fol_02_ctrl", -4), ("L_Mouth_fol_06_ctrl", 4)):
        off = cmds.group(empty=True, name=n + "_offset", parent=head)
        cmds.xform(off, worldSpace=True, translation=(x, 145, 10))
        c = cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=0.5)[0], off, relative=True)[0]
        cmds.select(clear=True)
        j = cmds.joint(name=n.replace("_ctrl", "_jnt"), position=(x, 145, 10))
        cmds.parentConstraint(c, j, maintainOffset=True)
        ctrls.append((c, j))
    cmds.skinCluster([j for _c, j in ctrls], srf, toSelectedBones=True)
    shape = cmds.listRelatives(srf, shapes=True, fullPath=True)[0]
    fs = cmds.createNode("follicle", name="Mouth_fol_04_folShape")
    ft = cmds.listRelatives(fs, parent=True)[0]
    cmds.connectAttr(shape + ".local", fs + ".inputSurface")
    cmds.connectAttr(shape + ".worldMatrix[0]", fs + ".inputWorldMatrix")
    cmds.connectAttr(fs + ".outTranslate", ft + ".translate")
    cmds.connectAttr(fs + ".outRotate", ft + ".rotate")
    cmds.setAttr(fs + ".parameterU", 0.5)
    cmds.setAttr(fs + ".parameterV", 0.5)
    boff = cmds.group(empty=True, name="Mouth_fol_04_ctrl_offset", parent=head)
    cmds.xform(boff, worldSpace=True, matrix=cmds.xform(ft, query=True, worldSpace=True, matrix=True))
    cmds.parent(cmds.circle(name="Mouth_fol_04_ctrl", constructionHistory=False, radius=0.4)[0], boff, relative=True)
    cmds.parentConstraint(ft, boff, maintainOffset=True)
    off = cmds.group(empty=True, name="Mouth_main_ctrl_offset", parent=head)
    cmds.parent(cmds.circle(name="Mouth_main_ctrl", constructionHistory=False, radius=3)[0], off, relative=True)
    names = ["L_Mouth_fol_02_ctrl", "L_Mouth_fol_06_ctrl", "Mouth_fol_04_ctrl"]
    wm = lambda n: cmds.xform(cmds.ls(n, long=True)[0], query=True, worldSpace=True, matrix=True)
    b0 = wm("Mouth_fol_04_ctrl")
    cmds.setAttr("L_Mouth_fol_06_ctrl.translateY", 1.5)
    seen = dict((n, wm(n)) for n in names)
    rep.expect("the ribbon carries the neighbour (moved %.3f)" % (seen["Mouth_fol_04_ctrl"][13] - b0[13]),
               seen["Mouth_fol_04_ctrl"][13] - b0[13] > 0.1)
    if not rep.step("save Up", FP.save_pose, "Mouth_main_ctrl", "Up", False, False):
        return
    cmds.setAttr("Mouth_main_ctrl.Up", 1)
    for n in names:
        off_ = max(abs(a - b) for a, b in zip(wm(n), seen[n]))
        rep.expect("Up alone: %s where the face showed it - not twice (%.5f)" % (n, off_), off_ < 1e-3)


def check_vis5618(rep):
    """5.6.18: the face's switches onto a gear of yours (Face_Ctrls x each part); a hand-made show / hide attribute
    taken off a gear, what it hid shown again."""
    from gus_rigtool.core import vis_switch as VS
    rep.start("Visibility - face switches on your gear; hand-made switches off")
    _new_scene()
    head = cmds.circle(name="Head_ctrl", constructionHistory=False, radius=10)[0]
    for n in ("L_Brow_ctrl", "L_Mouth_fol_06_ctrl", "Tongue_01_FK_ctrl"):
        cmds.parent(cmds.circle(name=n, constructionHistory=False, radius=1)[0], head)
    gear = cmds.circle(name="Face_settings_ctrl", constructionHistory=False, radius=2)[0]
    cmds.parent(gear, head)
    if not rep.step("make the switches", VS.make, head):
        return
    got = rep.step("face switches -> Face_settings_ctrl", VS.move_face, gear)
    if not got:
        return
    rep.expect("parts %s" % got["parts"], set(got["parts"]) >= {"Brows", "Mouth", "Tongue"})
    cmds.setAttr(gear + ".Brows", 0)
    rep.expect("Brows off: the brow hidden, the mouth not", not cmds.getAttr("L_Brow_ctrlShape.visibility") and
               cmds.getAttr("L_Mouth_fol_06_ctrlShape.visibility"))
    cmds.setAttr(gear + ".Brows", 1)
    cmds.setAttr(gear + ".Face_Ctrls", 0)
    rep.expect("Face_Ctrls off: all the face hidden, the gear itself shown",
               not cmds.getAttr("L_Brow_ctrlShape.visibility") and not cmds.getAttr("Tongue_01_FK_ctrlShape.visibility")
               and cmds.getAttr("Face_settings_ctrlShape.visibility"))
    cmds.setAttr(gear + ".Face_Ctrls", 1)
    wrist = cmds.circle(name="L_wrist_settings_ctrl", constructionHistory=False)[0]
    sleeve = cmds.group(empty=True, name="L_Sleeve_ctrls_grp")
    cmds.addAttr(wrist, longName="_Ctrl_Vis", attributeType="enum", enumName="----")
    cmds.addAttr(wrist, longName="Sleeves", attributeType="double", defaultValue=0, keyable=True)
    cmds.connectAttr(wrist + ".Sleeves", sleeve + ".visibility")
    done = rep.step("remove the hand-made switch", VS.remove_hand_switches, [wrist])
    rep.expect("Sleeves and its heading gone, the sleeve group shown (%s)" % done,
               not cmds.attributeQuery("Sleeves", node=wrist, exists=True) and
               not cmds.attributeQuery("_Ctrl_Vis", node=wrist, exists=True) and cmds.getAttr(sleeve + ".visibility"))
    sw = VS.find()
    rep.expect("5.6.20 the gear open while rigging (translateY settable)", not cmds.getAttr(sw + ".translateY",
                                                                                         lock=True))
    cmds.setAttr(gear + ".Brows", 0)
    got = rep.step("remove all the switches", VS.remove_all)
    rep.expect("removed: the gear gone, the face switches gone, the brow shown (%s)" % got,
               got and not cmds.objExists("Visibility_ctrl") and
               not cmds.attributeQuery("Face_Ctrls", node=gear, exists=True) and
               cmds.getAttr("L_Brow_ctrlShape.visibility"))


def check_vis5622(rep):
    """5.6.22: the clothes one switch each (Collar off: only the collar hides; Secondary_Ctrls off: all of them); a
    switch of your own from the selection on a gear, under its master; Remove all shows everything."""
    from gus_rigtool.core import vis_switch as VS
    rep.start("Visibility - clothes parts, a switch of your own")
    _new_scene()
    head = cmds.circle(name="Head_ctrl", constructionHistory=False, radius=10)[0]
    names = ("Collar_fol_09_ctrl", "Cape_Ribbon_fol_04_ctrl", "L_index_01_FK_ctrl", "L_middle_01_FK_ctrl")
    for n in names:
        cmds.circle(name=n, constructionHistory=False)
    gear = cmds.circle(name="L_wrist_settings_ctrl", constructionHistory=False)[0]
    if not rep.step("make the switches", VS.make, head):
        return
    got = rep.step("clothes: a switch per part", VS.split_secondary)
    sw = VS.find()
    rep.expect("parts %s" % (got or {}).get("parts"), got and {"Collar", "Cape"} <= set(got["parts"]))
    vis = lambda n: cmds.getAttr(n + "Shape.visibility")
    cmds.setAttr(sw + ".Collar", 0)
    rep.expect("Collar off: the collar hidden, the cape not", not vis("Collar_fol_09_ctrl") and
               vis("Cape_Ribbon_fol_04_ctrl"))
    cmds.setAttr(sw + ".Collar", 1)
    cmds.setAttr(sw + ".Secondary_Ctrls", 0)
    rep.expect("Secondary_Ctrls off: all the clothes hidden", not vis("Collar_fol_09_ctrl") and
               not vis("Cape_Ribbon_fol_04_ctrl"))
    cmds.setAttr(sw + ".Secondary_Ctrls", 1)
    cmds.addAttr(gear, longName="Body_Ctrls", attributeType="bool", defaultValue=True, keyable=True)
    rep.step("Fingers: a switch from the selection on the wrist gear", VS.add_switch,
             ["L_index_01_FK_ctrl", "L_middle_01_FK_ctrl"], "Fingers", gear, "Body_Ctrls")
    cmds.setAttr(gear + ".Fingers", 0)
    rep.expect("Fingers off: both fingers hidden", not vis("L_index_01_FK_ctrl") and not vis("L_middle_01_FK_ctrl"))
    cmds.setAttr(gear + ".Fingers", 1)
    cmds.setAttr(gear + ".Body_Ctrls", 0)
    rep.expect("its master off: the fingers hidden too", not vis("L_index_01_FK_ctrl"))
    cmds.setAttr(gear + ".Body_Ctrls", 1)
    cmds.setAttr(sw + ".Collar", 0)
    rep.step("remove all the switches", VS.remove_all)
    rep.expect("removed: every part gone, everything shown", not VS.part_nodes() and
               all(vis(n) for n in names) and not cmds.attributeQuery("Fingers", node=gear, exists=True))


def check_sdk_auto5618(rep):
    """5.6.18: SDK mirror with Auto on a pair mirrored with Z flipped (the Hare's eyelid ribbons): the R driven
    node lands exactly on the mirror of the L one - position and turn."""
    import math
    from gus_rigtool.tools import sdk_tool as T
    rep.start("SDK mirror - Auto flips")
    _new_scene()
    lp = cmds.group(empty=True, name="L_lid_par")
    cmds.xform(lp, worldSpace=True, translation=(3, 5, 1))
    rp = cmds.group(empty=True, name="R_lid_par")
    cmds.xform(rp, worldSpace=True, translation=(-3, 5, 1), rotation=(0, 180, 0))   # x mirrored, z flipped
    ls_ = cmds.group(empty=True, name="L_lid_sdk", parent=lp)
    rs_ = cmds.group(empty=True, name="R_lid_sdk", parent=rp)
    ld = cmds.circle(name="L_lid_drv_ctrl", constructionHistory=False)[0]
    rd = cmds.circle(name="R_lid_drv_ctrl", constructionHistory=False)[0]
    cmds.move(4, 8, 0, ld)
    cmds.move(-4, 8, 0, rd)
    for attr, v in (("translateZ", 2.0), ("rotateX", 30.0), ("rotateY", -20.0), ("translateX", 0.5),
                    ("rotateZ", 12.0)):
        cmds.setDrivenKeyframe(ls_ + "." + attr, currentDriver=ld + ".translateY", driverValue=0, value=0)
        cmds.setDrivenKeyframe(ls_ + "." + attr, currentDriver=ld + ".translateY", driverValue=1, value=v)
    o = dict(T.DEFAULTS, mode=1, attr_filter="All", flip=[], auto=True)
    rows = rep.step("plan", T.plan, o, cmds.ls(ld, long=True)[0])
    if not rows:
        return
    rep.expect("auto rows: tz rx ry flip, tx rz keep (%s)" % [T.row_text(r).split("[")[-1] for r in rows],
               sorted(r["src"]["plug"].split(".")[-1] for r in rows if r["flip"]) ==
               ["rotateX", "rotateY", "translateZ"])
    for r in rows:
        r["replace"] = True
        rep.step("apply " + r["src"]["plug"].split(".")[-1], T.apply_row, r, cmds.ls(ld, long=True)[0])
    cmds.setAttr(ld + ".translateY", 1)
    cmds.setAttr(rd + ".translateY", 1)
    ml = cmds.xform(ls_, query=True, worldSpace=True, matrix=True)
    mr = cmds.xform(rs_, query=True, worldSpace=True, matrix=True)
    pos = abs(ml[12] + mr[12]) + abs(ml[13] - mr[13]) + abs(ml[14] - mr[14])
    axes = []
    for i, want in enumerate((1, 1, -1)):                       # as at rest: x, y the mirror, z the other way
        u = ml[i * 4:i * 4 + 3]
        m = [-u[0], u[1], u[2]]
        w = mr[i * 4:i * 4 + 3]
        axes.append(math.sqrt(sum((a - want * b) ** 2 for a, b in zip(w, m))))
    rep.expect("R lands on the mirror of L: position off %.5f, turn off %.5f" % (pos, max(axes)),
               pos < 1e-3 and max(axes) < 1e-3)


def _deletes(node):
    try:
        cmds.delete(node)
        return True
    except RuntimeError:
        return False


def check_hand_publish(rep):
    """5.0.1: a rig made by hand (no Build) publishes, unpublishes exactly, and delivers."""
    import tempfile
    from gus_rigtool.builder import deliver, publish
    rep.start("Hand-made rig: publish, unpublish, deliver")
    _new_scene()
    top = cmds.group(empty=True, name="Mech_Rig")
    ctrls_grp = cmds.group(empty=True, name="Mech_controls", parent=top)
    cmds.select(clear=True)
    j1 = cmds.joint(name="mech_root_jnt", position=(0, 100, 0))
    cmds.joint(name="mech_arm_jnt", position=(20, 100, 0))
    cmds.parent(j1, top)
    made = []
    for nm, pos in (("hips", (0, 100, 0)), ("arm_CON", (20, 100, 0))):
        off = cmds.group(empty=True, name=nm + "_offset", parent=ctrls_grp)
        cmds.move(pos[0], pos[1], pos[2], off)
        c = cmds.circle(name=nm, normal=(1, 0, 0), radius=5, constructionHistory=False)[0]
        c = cmds.parent(c, off, relative=True)[0]
        made.append(c)
    cmds.parentConstraint(made[0], "mech_root_jnt", maintainOffset=True)
    box = cmds.polyCube(name="mech_body", width=40, height=10, depth=10, subdivisionsX=8)[0]
    cmds.move(10, 100, 0, box)
    cmds.skinCluster(["mech_root_jnt", "mech_arm_jnt"], box, toSelectedBones=True)
    noisy = cmds.group(empty=True, name="noTouch", parent=top)
    cmds.setAttr(noisy + ".visibility", 0)
    cmds.parent(cmds.circle(name="spline_crv", constructionHistory=False)[0], noisy)

    def state():
        out = {}
        for n in cmds.ls(top, dag=True, long=True, type="transform") or []:
            for a in ("translateX", "rotateY", "scaleZ", "visibility"):
                p = n + "." + a
                out[p] = (cmds.getAttr(p, lock=True), cmds.getAttr(p, keyable=True), round(cmds.getAttr(p), 4))
        return out
    before = state()
    found = sorted(c.split("|")[-1] for c in publish.rig_controls())
    rep.expect("its top group and controls are found (no Build)", publish.rig_group() and
               publish.rig_group().endswith("Mech_Rig") and found == ["arm_CON", "hips"],
               "top %s, controls %s" % (publish.rig_group(), found))
    if not rep.step("publish", publish.publish):
        return
    rep.expect("the offsets are locked, the controls are not",
               cmds.getAttr("hips_offset.translateX", lock=True) and not cmds.getAttr("hips.translateX", lock=True))
    rep.expect("the skeleton is hidden, the skin still follows", cmds.getAttr("mech_root_jnt.visibility") == 0)
    rep.expect("bind_joints_set has the skinned joints",
               len(cmds.sets("bind_joints_set", query=True) or []) == 2)
    rep.step("unpublish", publish.unpublish)
    after = state()
    diff = [p for p in before if before[p] != after.get(p)]
    rep.expect("unpublish: every channel and visibility exactly as before", not diff, ", ".join(diff[:6]))
    out = rep.step("deliver to a folder", deliver.deliver, os.path.join(tempfile.gettempdir(), "gus_check_hand"),
                   "mech")
    if out:
        rep.expect("delivered: the rig, the animator tools, the README",
                   os.path.exists(out["scene"]) and os.path.isdir(os.path.join(out["folder"], "animator_tools"))
                   and os.path.exists(os.path.join(out["folder"], "README.txt")))
        rep.expect("delivering leaves your scene unpublished", not publish.is_published())


def run(height=180.0, ask=True, quadruped=True, selftest=True):
    """Everything; returns the report text (also shown in a window and saved)."""
    if ask and cmds.confirmDialog(
            title="Gus_Rigtool - Maya check", button=["Run it", "Cancel"], defaultButton="Run it",
            cancelButton="Cancel", dismissString="Cancel",
            message="This opens NEW scenes (save your work first) and takes a minute or two.") != "Run it":
        return None
    rep = Report("Maya check")
    with _Quiet():
        rep.guard("windows", check_windows, rep)
        rep.guard("biped rig", check_rig, rep, "biped", height)
        rep.guard("Gus Animtool", check_animtool, rep)
        rep.guard("picker", check_picker, rep)
        if quadruped:
            rep.guard("quadruped rig", check_rig, rep, "quadruped", height)
        rep.guard("daily tools", check_daily_tools, rep)
        rep.guard("make controls", check_make_controls, rep)
        rep.guard("ribbons", check_ribbons, rep)
        rep.guard("editing", check_editing, rep)
        rep.guard("follow", check_follow, rep)
        rep.guard("face kit", check_face_kit, rep)
        rep.guard("correctives", check_correctives, rep, height)
        rep.guard("hand-made rig: publish and deliver", check_hand_publish, rep)
        rep.guard("knee bend control", check_knee_bend, rep, height)
        rep.guard("mirror a setup", check_mirror_setup, rep)
        rep.guard("chain jiggle", check_jiggle, rep, height)
        rep.guard("nodes: trace, at rest, loops", check_nodes_find, rep, height)
        rep.guard("mirrored ribbon and nodes <-> driven key", check_mirror_ribbon_sdk, rep)
        rep.guard("cloth", check_cloth, rep)
        rep.guard("stop at the body, duplicate names", check_fix533, rep)
        rep.guard("limits", check_limits535, rep)
        rep.guard("networks: setups, Node Editor, protect", check_network550, rep)
        rep.guard("keep the pose, zero the control", check_zero551, rep)
        rep.guard("world controls and scale", check_scale560, rep, height)
        rep.guard("scale: spaces following the world", check_scale564, rep, height)
        rep.guard("visibility switches", check_vis565, rep, height)
        rep.guard("spaces on locked offsets", check_space567, rep, height)
        rep.guard("group controls", check_group568, rep, height)
        rep.guard("head squash", check_squash5611, rep, height)
        rep.guard("face expressions", check_poses5612, rep, height)
        rep.guard("SDK mirror - Auto flips", check_sdk_auto5618, rep)
        rep.guard("visibility - face switches", check_vis5618, rep)
        rep.guard("visibility - clothes parts, own switches", check_vis5622, rep)
        rep.guard("expressions - lids, curl, ears", check_poses5620, rep)
        rep.guard("expressions - ribbon neighbour", check_poses5621, rep)
        rep.guard("pages fit the window", check_page_widths, rep)
        if selftest:
            rep.guard("self-test", check_selftest, rep, height)
    text = rep.text()
    path = os.path.join(cmds.internalVar(userTmpDir=True), "gus_maya_check.txt")
    try:
        with open(path, "w") as f:
            f.write(text)
    except (IOError, OSError):
        path = None
    print(text)
    try:
        from gus_rigtool.core import ui
        ui.report_window("Gus_Rigtool - Maya check", text + ("\nSaved: %s" % path if path else ""))
    except Exception:
        pass
    return text
