"""
The real-Maya tests (5.6.35), run by run_maya_tests.py inside mayapy. Each one builds its own small scene; the
last one opens your scene and never saves it. Order: what broke lately first (a-c), then the whole rig (d-f).
"""

import os
import sys

import maya.cmds as cmds

from gus_rigtool.core.report import INFO, NOTE, OK

APPENDIX = {}                            # extra text for the end of the results file (your scene's report)
TOL = 1e-3


def _wm(n):
    return cmds.xform(n, query=True, worldSpace=True, matrix=True)


def _pos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)


def _diff(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


def _lock(node, attrs):
    for a in attrs:
        for x in "XYZ":
            cmds.setAttr("%s.%s%s" % (node, a, x), lock=True)


def _ctrl(name, parent=None):
    c = cmds.circle(name=name, normal=(1, 0, 0), constructionHistory=False)[0]
    if parent:
        c = cmds.parent(c, parent)[0]
    return cmds.ls(c, long=True)[0]


def _joint(name, pos=(0, 0, 0)):
    cmds.select(clear=True)
    return cmds.ls(cmds.joint(name=name, position=pos), long=True)[0]


def _cube(name):
    m = cmds.polyCube(name=name)[0]
    cmds.delete(m, constructionHistory=True)          # no polyCube node: no 'history' of its own
    return cmds.ls(m, long=True)[0]


# --- a -----------------------------------------------------------------------------------------------------------
def pupils(rep):
    """The Hare's pupils: the control's own rotate feeds the eyeball's orient constraint."""
    from gus_rigtool.core import safe, zero_pose
    rep.start("a. Keep the pose: a control whose rotate drives an eye (the pupils)")
    head = cmds.group(empty=True, name="Head_grp")
    cmds.setAttr(head + ".rotateY", 20)
    rest = cmds.group(empty=True, name="L_Pupil_ctrl_rest", parent=head)
    ctrl = _ctrl("L_Pupil_ctrl", rest)
    for a, v in (("translateZ", 9.7461), ("rotateX", -720.0), ("rotateY", -37.6547), ("rotateZ", 720.0)):
        cmds.setAttr(ctrl + "." + a, v)
    _lock(ctrl, ("translate", "rotate"))
    eye = _joint("L_Eyeball_jnt")
    cmds.orientConstraint(ctrl, eye, maintainOffset=True)
    eye_mesh = cmds.polySphere(name="L_Eye_geo", radius=1)[0]
    cmds.delete(eye_mesh, constructionHistory=True)
    cmds.skinCluster(eye, eye_mesh, toSelectedBones=True)
    before = _wm(eye)
    fed = zero_pose.feeds(ctrl)
    rep.expect("what its own values feed is found (rotate -> the eye's orient constraint)",
               any("orientConstraint" in d for _p, d in fed), str(fed[:3]))
    kept, got = safe.run(lambda: zero_pose.apply([ctrl]), label="gusMayaTest", states=("rest",))
    done, skipped = got if kept else ([], [])
    rep.expect("Keep the pose leaves it and says why", kept and not done and skipped and
               "drive" in skipped[0][1], str(got)[:200])
    rep.expect("the eye didn't turn", _diff(_wm(eye), before) < TOL, "moved %.5f" % _diff(_wm(eye), before))
    # what 5.6.33 did (the pose into a group above, the locked channels zeroed): does it turn the eye in Maya?
    g = cmds.group(empty=True, name="L_Pupil_ctrl_rest1", parent=rest)
    cmds.xform(g, worldSpace=True, matrix=_wm(rest))
    m = _wm(ctrl)
    ctrl = cmds.ls(cmds.parent(ctrl, g)[0], long=True)[0]
    for a in ("translate", "rotate"):
        for x in "XYZ":
            p = "%s.%s%s" % (ctrl, a, x)
            cmds.setAttr(p, lock=False)
            cmds.setAttr(p, 0)
    from gus_rigtool.core import world_turn as WT
    cmds.xform(g, worldSpace=True, matrix=WT._mul(WT._inv(cmds.xform(ctrl, query=True, objectSpace=True,
                                                                         matrix=True)), m))
    moved = _diff(_wm(eye), before)
    rep.add(INFO, "what 5.6.33 did, by hand: the control stays put (%.5f), the eye moves %.5f" %
            (_diff(_wm(ctrl), m), moved), "how Maya's orient constraint reads a control's own rotate")
    # a plain control still zeroes and nothing moves
    cmds.file(new=True, force=True)
    grp = cmds.group(empty=True, name="Arm_grp")
    arm = _ctrl("Arm_ctrl", grp)
    cmds.setAttr(arm + ".translateX", 3.0)
    cmds.setAttr(arm + ".rotateZ", 25.0)
    m = _wm(arm)
    kept, got = safe.run(lambda: zero_pose.apply([arm]), label="gusMayaTest", states=("rest",))
    arm = cmds.ls("Arm_ctrl", long=True)[0]
    rep.expect("a plain control: zeroed, its group took the pose, it stayed where it was",
               kept and got[0] and abs(cmds.getAttr(arm + ".translateX")) < TOL and _diff(_wm(arm), m) < TOL,
               str(got)[:200])


# --- b -----------------------------------------------------------------------------------------------------------
def history(rep):
    """The bandages: the Clothes switch reaches the mesh through its skin's on / off - not model history."""
    from gus_rigtool.tools import checker
    rep.start("b. Non-deformer history (the bandages)")
    for t in ("condition", "plusMinusAverage", "reverse"):
        rep.add(INFO, "Maya's classification of %s" % t, str(cmds.getClassification(t)))
    band = _cube("Bandage_test")
    j = _joint("band_jnt")
    skin = cmds.skinCluster(j, band, toSelectedBones=True)[0]
    pma = cmds.createNode("plusMinusAverage", name="Clothes_test_pma")
    cond = cmds.createNode("condition", name="Clothes_test_hidden")
    cmds.connectAttr(pma + ".output1D", cond + ".firstTerm")
    cmds.connectAttr(cond + ".outColorR", skin + ".nodeState")
    shape = cmds.listRelatives(band, shapes=True, noIntermediate=True, fullPath=True)[0]
    got = checker._non_deformer_history(shape)
    rep.expect("a skinned mesh whose skin the Clothes switch turns off: no history", got == [], str(got))
    smooth = _cube("Smooth_test")
    cmds.polySmooth(smooth)
    shape = cmds.listRelatives(smooth, shapes=True, noIntermediate=True, fullPath=True)[0]
    got = checker._non_deformer_history(shape)
    rep.expect("a smoothed mesh: its polySmoothFace is found", any("polySmooth" in cmds.nodeType(h) for h in got),
               str(got))


# --- c -----------------------------------------------------------------------------------------------------------
def squash_leftovers(rep):
    """The Hare's half-removed head squash on a published rig (Publish locks the nodes)."""
    from gus_rigtool.core import head_squash as HS
    from gus_rigtool.core import network_tools
    rep.start("c. Remove head squash on a published rig (locked nodes)")
    head = _ctrl("Head_ctrl")
    grp = cmds.group(empty=True, name="L_Ear_ctrls_grp", parent=head)
    cmds.setAttr(grp + ".translateX", 3.0)
    follow = cmds.group(empty=True, name="L_Ear_ctrls_grp_squash_follow", parent=grp)
    cmds.setAttr(follow + ".translateY", 0.5)
    ear = _ctrl("L_Ear_01_ctrl", follow)
    cmds.setAttr(ear + ".translateY", 2.0)
    ear_j = _joint("L_Ear_01_jnt")
    cmds.parentConstraint(ear, ear_j, maintainOffset=True)
    off = cmds.createNode("reverse", name="Head_squash_off")
    md = cmds.createNode("multiplyDivide", name="Head_squash_factor_md")
    cmds.connectAttr(md + ".outputX", cmds.ls(follow, long=True)[0] + ".scaleY")
    other = cmds.createNode("multiplyDivide", name="Other_md")
    before = _pos("L_Ear_01_ctrl"), _pos(ear_j)
    rep.step("Publish's locks on (network_tools.protect)", network_tools.protect)
    rep.add(INFO, "locked now", ", ".join(n for n in (off, md, other) if cmds.lockNode(n, query=True, lock=True)[0]))
    rep.expect("the leftovers found", sorted(HS._short(n) for n in HS.leftovers()) ==
               ["Head_squash_factor_md", "Head_squash_off", "L_Ear_ctrls_grp_squash_follow"],
               str([HS._short(n) for n in HS.leftovers()]))
    rep.step("Remove head squash", HS.remove)
    rep.expect("they're gone (5.6.31 stopped at 'Cannot delete locked node')",
               not cmds.objExists("Head_squash_off") and not cmds.objExists("Head_squash_factor_md") and
               not cmds.objExists("L_Ear_ctrls_grp_squash_follow"))
    rep.expect("the ear control and its joint stayed where they were",
               cmds.objExists("L_Ear_01_ctrl") and _diff(_pos("L_Ear_01_ctrl"), before[0]) < TOL and
               _diff(_pos(ear_j), before[1]) < TOL)
    rep.expect("what stays is still locked", cmds.lockNode(other, query=True, lock=True)[0])
    rep.step("Publish's locks off (network_tools.unprotect)", network_tools.unprotect)


# --- d e f: the whole rig --------------------------------------------------------------------------------------
def _animtool():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "anim")
    if path not in sys.path:
        sys.path.append(path)
    from gus_animtool import anim as A
    return A


def _joint_spots():
    from gus_rigtool.core import skin_tools
    return {j: _pos(j) for j in skin_tools.rig_joints()}


def _moved(a, b):
    return max([_diff(a[j], b[j]) for j in a if j in b] or [0.0])


def rig(rep):
    """e. The biped built, skinned, published, unpublished (the self-test's own steps, without windows)."""
    from gus_rigtool import maya_check
    STATE["mesh"] = maya_check.check_rig(rep, "biped", 180.0)
    rep.start("e. Publish / Unpublish")
    from gus_rigtool.builder import publish
    rep.expect("the rig is published at the end", publish.is_published())


def scene_check_run(rep):
    """d. Check this scene from start to end on the built biped."""
    from gus_rigtool import scene_check
    rep.start("d. Check this scene (the whole run, on the biped)")
    got = rep.step("Check this scene's report", scene_check.report)
    if not got:
        return
    crashed = [r for r in got.rows if "check itself crashed" in r[2]]
    rep.expect("no section crashed", not crashed, "; ".join("%s: %s" % (r[0], r[3].splitlines()[0])
                                                          for r in crashed)[:600])
    rep.add(INFO, "its result", got.text().splitlines()[3] if len(got.text().splitlines()) > 3 else "")


ARM = ("clav", "humer", "radius", "ulna", "wrist", "hand", "elbow", "arm")


def _settle():
    """5.6.36: make Maya work everything out before measuring (no window: nothing asks it to)."""
    try:
        cmds.dgdirty(allPlugs=True)
    except Exception:
        pass
    cmds.currentTime(cmds.currentTime(query=True), update=True)


def _arm_spots():
    return {j: p for j, p in _joint_spots().items() if any(k in j.split("|")[-1].lower() for k in ARM)}


def ikfk_mirror(rep):
    """f. Animtool on the biped: IK/FK switch with no jump, mirror pose - on the left wrist's IK control (5.6.35
    took the pole vector control by mistake and measured before Maya had caught up)."""
    rep.start("f. IK/FK switch and mirror pose (Gus Animtool, on the biped)")
    A = rep.step("Gus Animtool", _animtool)
    if not A:
        return
    ctrls = A.character_controls()
    ik = [c for c in ctrls if c.split("|")[-1].lower().startswith("l_") and "ik" in c.lower() and
          ("wrist" in c.lower() or "hand" in c.lower()) and "pv" not in c.split("|")[-1].lower()]
    rep.add(OK if ik else NOTE, "the left wrist's IK control", ik[0].split("|")[-1] if ik else "not found")
    if not ik:
        return
    c = ik[0]
    cmds.currentTime(1)
    try:
        cmds.move(-3, 4, 6, c, relative=True, worldSpace=True)
    except RuntimeError as e:
        rep.add(NOTE, "move the IK control", str(e))
    _settle()
    spots = _arm_spots()
    rep.add(INFO, "arm joints measured", "%d" % len(spots))
    cmds.select(c, replace=True)
    rep.step("switch to FK", A.switch, "fk")
    _settle()
    rep.expect("to FK: no arm joint jumped", _moved(spots, _arm_spots()) < 0.01,
               "the most a joint moved: %.4f" % _moved(spots, _arm_spots()))
    cmds.select(c, replace=True)
    rep.step("switch to IK", A.switch, "ik")
    _settle()
    rep.expect("back to IK: no arm joint jumped", _moved(spots, _arm_spots()) < 0.01,
               "the most a joint moved: %.4f" % _moved(spots, _arm_spots()))

    def mirror_gap():
        now = _arm_spots()
        gaps = []
        for j, p in now.items():
            short = j.split("|")[-1]
            if short.startswith("L_"):
                twin = [k for k in now if k.split("|")[-1] == "R_" + short[2:]]
                if twin:
                    q = now[twin[0]]
                    gaps.append(_diff((p[0], p[1], p[2]), (-q[0], q[1], q[2])))
        return max(gaps or [0.0])
    gap0 = mirror_gap()
    cmds.select(c, replace=True)
    rep.step("mirror pose L>R", A.mirror_pose, "L>R")
    _settle()
    gap1 = mirror_gap()
    rep.expect("the right arm now mirrors the left", gap1 < 0.05 and gap1 < gap0,
               "left / right gap before %.3f, after %.3f" % (gap0, gap1))


def rig_selftest(rep):
    """g. 5.6.36: the self-test's rig checks (biped and quadruped: IK/FK match, mirror, soft IK, spaces, stretch...),
    the same 80 checks Settings > Self-test runs - they need no window."""
    from gus_rigtool.builder import selftest
    rep.start("g. Rig self-test (the builder's own checks)")
    text = rep.step("self-test", selftest.run) or ""
    fails = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("FAIL")]
    head = text.splitlines()[0] if text else ""
    rep.expect("no check failed", text and not fails, "; ".join(fails[:8]) or head)
    for ln in text.splitlines()[1:2]:
        rep.add(INFO, "its result", ln.strip())


STATE = {}


def project_of(path):
    """The project folder: the one above 'scenes' (TTTBMW_Hare_Rigging), or the scene's own folder."""
    parts = os.path.abspath(path).replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].lower() == "scenes":
            return "/".join(parts[:i])
    return os.path.dirname(os.path.abspath(path)).replace("\\", "/")


def local_path(wanted, project):
    """5.6.36: a reference saved on one computer (H:/Assignments/.../TTTBMW_Hare_Rigging//assets/x.mb) found on this
    one: the same place inside this project folder, or the file in its assets / scenes folder. None if not found."""
    if not wanted:
        return None
    w = wanted.replace("\\", "/")
    while "//" in w[1:]:
        w = w[0] + w[1:].replace("//", "/")
    if os.path.isfile(w):
        return w
    name = project.rstrip("/").split("/")[-1]
    key = "/" + name + "/"
    if key in w:
        got = project.rstrip("/") + "/" + w.split(key, 1)[1]
        if os.path.isfile(got):
            return got
    for sub in ("assets", "scenes", ""):
        got = os.path.join(project, sub, os.path.basename(w)).replace("\\", "/")
        if os.path.isfile(got):
            return got
    return None


def _load_references(rep, project):
    """Each reference loaded from this computer's copy of the project (the Windows drive's path fixed)."""
    for rn in cmds.ls(type="reference") or []:
        if rn == "sharedReferenceNode" or "_UNKNOWN_REF_NODE_" in rn:
            continue
        try:
            wanted = cmds.referenceQuery(rn, filename=True, unresolvedName=True, withoutCopyNumber=True)
        except RuntimeError:
            continue
        got = local_path(wanted, project)
        if not got:
            rep.add(NOTE, "model file not found on this computer", "%s (looked in %s)" % (wanted, project))
            continue
        try:
            cmds.file(got, loadReference=rn, prompt=False)
            rep.add(OK, "model file loaded", got)
        except RuntimeError as e:
            rep.add(NOTE, "model file %s" % got, str(e)[:200])


def eye_dry_run(rep):
    """5.6.36: what 5.6.33's Keep the pose did to the pupils, done on your scene to see what moves - then undone,
    and the scene is closed without saving anyway."""
    from gus_rigtool.core import world_turn as WT
    pupils = [n for n in ("L_Pupil_ctrl", "R_Pupil_ctrl") if len(cmds.ls(n)) == 1]
    if not pupils:
        rep.add(INFO, "eye dry run", "no L_Pupil_ctrl / R_Pupil_ctrl in this scene")
        return
    joints = cmds.ls(type="joint", long=True) or []
    meshes = [cmds.listRelatives(m, parent=True, fullPath=True)[0]
              for m in cmds.ls(type="mesh", noIntermediate=True, long=True) or []]

    def look():
        _settle()
        out = {j: _pos(j) for j in joints}
        for m in meshes:
            try:
                out[m] = cmds.exactWorldBoundingBox(m)
            except RuntimeError:
                pass
        return out
    before = look()
    cmds.undoInfo(state=True)
    cmds.undoInfo(openChunk=True, chunkName="gusEyeDryRun")
    try:
        for c in pupils:
            c = cmds.ls(c, long=True)[0]
            p = cmds.listRelatives(c, parent=True, fullPath=True)[0]
            m = _wm(c)
            g = cmds.createNode("transform", name=c.split("|")[-1] + "_dryrun", parent=p, skipSelect=True)
            c = cmds.ls(cmds.parent(c, g, relative=True)[0], long=True)[0]
            for a in ("translate", "rotate"):
                for x in "XYZ":
                    plug = "%s.%s%s" % (c, a, x)
                    if cmds.listConnections(plug, source=True, destination=False):
                        continue
                    cmds.setAttr(plug, lock=False)
                    cmds.setAttr(plug, 0)
            cmds.xform(g, worldSpace=True, matrix=WT._mul(WT._inv(cmds.xform(c, query=True, objectSpace=True,
                                                                                 matrix=True)), m))
        after = look()
    finally:
        cmds.undoInfo(closeChunk=True)
    moved = sorted(((_diff(before[k], after[k]), k.split("|")[-1]) for k in before if k in after), reverse=True)
    moved = [(d, n) for d, n in moved if d > TOL]
    rep.add(INFO if not moved else NOTE, "eye dry run: 5.6.33's Keep the pose on %s" % ", ".join(pupils),
            "nothing moved" if not moved else "moved: " + ", ".join("%s %.3f" % (n, d) for d, n in moved[:10]))
    try:
        cmds.undo()
    except RuntimeError:
        pass


def hare(rep, path):
    """Your scene: opened (its model file found on this computer), Check this scene run, the eye dry run, closed -
    never saved."""
    from gus_rigtool import scene_check
    rep.start("Your scene (opened, never saved)")
    if not os.path.isfile(path):
        rep.add(NOTE, "your scene", "not found: %s" % path)
        return
    project = project_of(path)
    try:
        cmds.workspace(project, openWorkspace=True)
    except RuntimeError:
        try:
            cmds.workspace(directory=project)
        except RuntimeError:
            pass
    rep.add(INFO, "project", project)
    rep.step("open it (the model file not yet)", lambda: cmds.file(path, open=True, force=True, ignoreVersion=True,
                                                                   prompt=False, loadReferenceDepth="none")
             and os.path.basename(path))
    _load_references(rep, project)
    got = rep.step("Check this scene", scene_check.report)
    if got:
        crashed = [r for r in got.rows if "check itself crashed" in r[2] or "check crashed" in r[2]]
        rep.expect("no section crashed", not crashed, "; ".join("%s: %s" % (r[0], r[3].splitlines()[0])
                                                              for r in crashed)[:600])
        APPENDIX["scene"] = "\n\n==== Check this scene on your scene ====\n" + got.text()
    rep.guard("eye dry run", eye_dry_run, rep)
    cmds.file(new=True, force=True)                  # closed without saving
    rep.add(INFO, "closed without saving", path)


CASES = [("a. pupils", pupils), ("b. history", history), ("c. head squash leftovers", squash_leftovers),
         ("e. biped: build, publish, unpublish", rig), ("d. Check this scene", scene_check_run),
         ("f. IK/FK and mirror", ikfk_mirror), ("g. rig self-test", rig_selftest)]
WHOLE_RIG = ("d. Check this scene", "f. IK/FK and mirror")      # they run on the biped e built - no new scene
# (g makes its own scenes)
