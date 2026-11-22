"""
The real-Maya tests (5.6.35), run by run_maya_tests.py inside mayapy. Each one builds its own small scene; the
last one opens your scene and never saves it. Order: what broke lately first (a-c), then the whole rig (d-f).
"""

import os
import sys

import maya.cmds as cmds

from gus_rigtool.core.report import FAIL, INFO, NOTE, OK

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
    from gus_rigtool.core import rig_checks as checker   # (5.7.10: the checks, not the page)
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
    took the pole vector control by mistake and measured before Maya had caught up), both arms in IK first."""
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
    # 5.6.37: the biped's arms start in FK - both into IK first (at rest: nothing moves), or moving the IK control
    # moves nothing and 'to FK' rightly snaps the arm to it (5.6.36 read that as a 6-unit jump)
    twin = [x for x in ctrls if x.split("|")[-1].lower() == "r_" + c.split("|")[-1][2:].lower()]
    cmds.select([c] + twin[:1], replace=True)
    rest = _arm_spots()
    rep.step("both arms to IK", A.switch, "ik")
    _settle()
    rep.expect("to IK at rest: nothing moved", _moved(rest, _arm_spots()) < 0.01,
               "the most a joint moved: %.4f" % _moved(rest, _arm_spots()))
    try:
        cmds.move(-3, 4, 6, c, relative=True, worldSpace=True)
        # 5.6.38: the switch keyed the control (Key on switch): unkeyed, the next update put it back and the arm
        # never moved - 5.6.37's 'no jump' passes measured nothing
        cmds.setKeyframe(c, attribute=["translate", "rotate"])
    except RuntimeError as e:
        rep.add(NOTE, "move the IK control", str(e))
    _settle()
    spots = _arm_spots()
    went = _moved(rest, spots)
    if not rep.expect("the left arm followed its IK control (or there's nothing to measure)", went > 0.5,
                      "it moved %.3f" % went):
        return
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
    # 5.6.39: what the mirror wrote, read before Maya updates (the right control is keyed from the switch: an
    # unkeyed value goes back at the next update) - then keyed, so the arm keeps it
    vals = [[round(v, 3) for v in cmds.getAttr(x + "." + a)[0]] for x in [c] + twin[:1] for a in ("translate",
                                                                                                 "rotate")]
    rep.add(INFO, "values right after the mirror (left translate, rotate / right translate, rotate)", str(vals))
    if twin:
        cmds.setKeyframe(twin[0], attribute=["translate", "rotate"])
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


def scale_pair(left, right, tol=0.25):
    """5.6.39: (moved vertices, biggest move) of each side -> a note when one side does much less (the Hare's left
    pupil moved 62 stray vertices above the eye, the right one its pupil), else None."""
    (ln, lm), (rn, rm) = left, right
    if not ln and not rn:
        return None
    if not ln or not rn:
        return "one side moves nothing (left %d vertices, right %d)" % (ln, rn)
    big = max(lm, rm)
    if abs(lm - rm) > tol * big:
        return "the two sides don't match: left moves up to %.3f, right %.3f (%d / %d vertices)" % (lm, rm, ln, rn)
    return None


def _shown_meshes_of(joint):
    out = []
    for k in set(cmds.listConnections(joint, type="skinCluster") or []):
        for g in cmds.skinCluster(k, query=True, geometry=True) or []:
            t = (cmds.listRelatives(g, parent=True, fullPath=True) or [None])[0]
            for sh in cmds.listRelatives(t, shapes=True, fullPath=True, noIntermediate=True) or [] if t else []:
                if sh not in out:
                    out.append(sh)
    return out


def _scale_effect(ctrl, shapes, factor=1.5):
    before = {sh: cmds.xform(sh + ".vtx[*]", query=True, worldSpace=True, translation=True) for sh in shapes}
    was = cmds.getAttr(ctrl + ".scaleX")
    cmds.setAttr(ctrl + ".scaleX", was * factor)
    _settle()
    n, most = 0, 0.0
    for sh in shapes:
        a, b = before[sh], cmds.xform(sh + ".vtx[*]", query=True, worldSpace=True, translation=True)
        for i in range(0, min(len(a), len(b)), 3):
            d = max(abs(a[i + k] - b[i + k]) for k in range(3))
            if d > 1e-4:
                n += 1
                most = max(most, d)
    cmds.setAttr(ctrl + ".scaleX", was)
    _settle()
    return n, most


def scale_twins(rep):
    """5.6.39: each left control whose scale drives a joint (the pupils) scaled with its right twin: the meshes you
    see must change, and about the same on both sides. Put back after; the scene is never saved."""
    pairs = []
    for c in cmds.ls("L_*", type="transform") or []:
        dst = [d for d in cmds.listConnections(c + ".scale", source=False, destination=True) or []
               if cmds.nodeType(d) == "joint"]
        twin = "R_" + c[2:]
        if dst and len(cmds.ls(twin)) == 1 and cmds.getAttr(c + ".scaleX", settable=True) and \
                cmds.getAttr(twin + ".scaleX", settable=True):
            rd = [d for d in cmds.listConnections(twin + ".scale", source=False, destination=True) or []
                  if cmds.nodeType(d) == "joint"]
            if rd:
                pairs.append((c, twin, dst[0], rd[0]))
    if not pairs:
        rep.add(INFO, "scale controls", "no left control whose scale drives a joint")
        return
    for lc, rc, lj, rj in pairs:
        left = _scale_effect(lc, _shown_meshes_of(lj))
        right = _scale_effect(rc, _shown_meshes_of(rj))
        why = scale_pair(left, right)
        rep.add(NOTE if why else OK, "%s / %s scaled: the meshes follow alike" % (lc, rc),
                why or "left %d vertices (up to %.3f), right %d (up to %.3f)" % (left[0], left[1], right[0],
                                                                                  right[1]))


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
    rep.guard("scale controls, left and right", scale_twins, rep)
    cmds.file(new=True, force=True)                  # closed without saving
    rep.add(INFO, "closed without saving", path)


# --- h: the Animtool's arcs (5.6.40) -----------------------------------------------------------------------------
def arcs(rep):
    """h. Arcs (5.6.42, the plain arc again): Maya's trail on an IK hand, an FK wrist and a control moved by its
    parent - one orange line, its settings read back, the options (around my frame, handles), no arc nodes left for
    a save, your selection kept, weighted tangents only when asked."""
    _animtool()
    from gus_animtool import arctrail
    from gus_animtool import anim as A
    rep.start("h. Arcs (Animtool): the plain arc, its options, saving")
    cmds.playbackOptions(minTime=1, maxTime=48)
    hand = _ctrl("L_hand_ik_ctrl")
    for f, x in ((1, 0.0), (12, 4.0), (24, 6.0), (48, 0.0)):
        cmds.setKeyframe(hand, attribute="translateX", time=f, value=x)
        cmds.setKeyframe(hand, attribute="translateY", time=f, value=x * 0.5)
    wrist = _ctrl("L_wrist_fk_ctrl", parent=cmds.group(empty=True, name="L_elbow_fk"))
    for f, r in ((1, 0.0), (24, 60.0), (48, 0.0)):
        cmds.setKeyframe(wrist, attribute="rotateZ", time=f, value=r)
    _lock(wrist, ["translate"])
    mover = cmds.group(empty=True, name="prop_space")
    for f, x in ((1, 0.0), (48, 10.0)):
        cmds.setKeyframe(mover, attribute="translateZ", time=f, value=x)
    led = _ctrl("L_prop_ctrl", parent=mover)
    cmds.currentTime(24)
    cmds.select(hand, replace=True)
    said = rep.step("Arcs on the hand, the wrist and the prop control", arctrail.show, [hand, wrist, led])
    rep.add(INFO, "the message", str(said))
    rep.expect("your selection is still yours (not a new arc)",
               cmds.ls(selection=True, long=True) == [cmds.ls(hand, long=True)[0]], str(cmds.ls(selection=True)))
    rep.expect("an arc for each of the three", all(arctrail._trails_of(n) for n in (hand, wrist, led)),
               str(arctrail.trails()))
    made = arctrail._trails_of(hand)
    shapes = [sh for m in made for sh in (cmds.listRelatives(m, shapes=True, fullPath=True) or [m])]
    for sh in shapes:
        rep.add(INFO, "%s (%s): its settings" % (sh.split("|")[-1], cmds.nodeType(sh)),
                ", ".join(sorted(a for a in (cmds.listAttr(sh) or []) if any(
                    w in a.lower() for w in ("frame", "trail", "color", "tangent", "fade", "bead", "mode")))))
    done = []
    for sh in shapes:
        done += arctrail.style(sh)
    rep.add(INFO, "settings the Animtool set", ", ".join(sorted(set(done))) or "none")
    rep.expect("the orange line and the dots are set", "trailColor" in done and "showFrameMarkers" in done, bad=NOTE)
    A.set_opt("arcs_around", True)
    A.set_opt("arcs_handles", True)
    arctrail.restyle()
    vals = {}
    for sh in shapes:
        for a in ("preFrame", "postFrame", "showInTangent"):
            if cmds.attributeQuery(a, node=sh, exists=True):
                vals[a] = cmds.getAttr(sh + "." + a)
    rep.add(INFO, "around my frame + handles on", str(vals))
    rep.expect("Range around my frame: 24 before / after", vals.get("preFrame") == 24, bad=NOTE)
    A.set_opt("arcs_around", False)
    A.set_opt("arcs_handles", False)
    arctrail.restyle()
    # the Arcs panel: each arc its own colour, hide one, a point every 2 frames (the arcs made again)
    arctrail.set_colour(led, (0.2, 0.9, 0.3))
    col = [cmds.getAttr(sh + ".trailColor")[0] for t in arctrail._trails_of(led)
           for sh in (cmds.listRelatives(t, shapes=True, fullPath=True) or [])
           if cmds.attributeQuery("trailColor", node=sh, exists=True)]
    rep.expect("the prop control's arc in its own colour (green)", bool(col) and abs(col[0][1] - 0.9) < 1e-3,
               str(col), bad=NOTE)
    arctrail.set_visible(wrist, False)
    rep.expect("the wrist's arc hidden (kept)", all(not cmds.getAttr(t + ".visibility")
                                                    for t in arctrail._trails_of(wrist)))
    arctrail.set_option("arcs_step", 2)
    rep.expect("a point every 2 frames: the three arcs made again, the wrist's still hidden",
               all(arctrail._trails_of(n) for n in (hand, wrist, led)) and
               all(not cmds.getAttr(t + ".visibility") for t in arctrail._trails_of(wrist)))
    arctrail.set_option("arcs_step", 1)
    arctrail._before_save()
    rep.expect("before a save: no arc nodes left in the scene", not cmds.ls(arctrail.GROUP) and
               not cmds.ls(type="motionTrail"), str(cmds.ls(type="motionTrail")))
    rep.expect("... and it remembers to put them back", len(arctrail._state["saved"] or []) == 3)
    arctrail._remake(arctrail._state["saved"] or [])
    arctrail._state["saved"] = None
    rep.expect("after the save: the arcs are back", bool(arctrail._trails_of(hand)))
    curves = cmds.listConnections(hand + ".translateX", source=True, destination=False, type="animCurve")
    before = cmds.keyTangent(curves, query=True, weightedTangents=True)
    n = rep.step("timing beads: make the hand's curves weighted (no question here)", arctrail.make_weighted, [hand],
                 ask=False)
    rep.expect("the hand's curves are weighted now (were not)", before == [False] and n == 2 and
               cmds.keyTangent(curves, query=True, weightedTangents=True) == [True])
    undo_on = cmds.undoInfo(query=True, state=True)
    rep.add(INFO, "Ctrl+Z here: undo on / what Ctrl+Z would undo",
            "%s / %r" % (undo_on, cmds.undoInfo(query=True, undoName=True)))
    cmds.undo()
    if undo_on:
        rep.expect("Ctrl+Z: not weighted again", cmds.keyTangent(curves, query=True, weightedTangents=True) == [False],
                   bad=NOTE)
    else:
        rep.add(INFO, "Ctrl+Z not tried", "Maya without a window has undo off - try it in Maya (Arcs panel > Timing "
                                          "beads, then Ctrl+Z)")
    arctrail.clear()
    rep.expect("Clear: the arcs are gone", not cmds.ls(arctrail.GROUP))


# --- i: Attach (5.6.41) ---------------------------------------------------------------------------------------------
def attach_case(rep):
    """i. Attach: no loop (the follower follows exactly on every frame), the hand follows a prop, two things on one
    holder, a hand-over with no jump, both hands, delete a change, the bookmarks, a loop refused, Bake."""
    _animtool()
    from gus_animtool import attach as AT
    rep.start("i. Attach (Animtool): follows exactly, hand-over, both hands, bookmarks")
    cmds.playbackOptions(minTime=1, maxTime=60)
    rig = cmds.group(empty=True, name="rig_grp")
    arm = cmds.group(empty=True, name="L_wrist_IK_offset", parent=rig)
    lhand = _ctrl("L_wrist_IK_ctrl", parent=arm)
    rhand = _ctrl("R_wrist_IK_ctrl", parent=rig)
    box = _ctrl("Box_ctrl")
    cup = _ctrl("Cup_ctrl")
    prop = _ctrl("Stick_ctrl")
    for n, k in ((lhand, ((1, 0, 0, 0), (30, 6, 3, 0), (60, 0, 6, 2))), (rhand, ((1, -4, 0, 0), (60, -1, 4, 5))),
                 (prop, ((1, 0, 0, 5), (60, 8, 2, 5)))):
        for f, x, y, z in k:
            for a, v in (("translateX", x), ("translateY", y), ("translateZ", z)):
                cmds.setKeyframe(n, attribute=a, time=f, value=v)
        cmds.setKeyframe(n, attribute="rotateY", time=1, value=0)
        cmds.setKeyframe(n, attribute="rotateY", time=60, value=90)
    cmds.currentTime(10)
    AT.attach(box, lhand)
    AT.attach(cup, lhand)
    cmds.currentTime(10)
    rel = {n: A_rel(n, lhand) for n in (box, cup)}
    worst = 0.0
    for f in range(10, 50):
        cmds.currentTime(f)
        for n in (box, cup):
            worst = max(worst, _diff(A_rel(n, lhand), rel[n]))
    rep.expect("a box and a cup on the same hand: both follow it exactly, every frame 10-49", worst < TOL, "%.5f" % worst)
    d = AT.read(box)
    src = cmds.listConnections(d["holders"][1]["mm"] + ".matrixIn[2]", source=True, destination=False, plugs=True)
    rep.expect("no loop: the box's own parentInverseMatrix isn't used", not src or "parentInverse" not in src[0],
               str(src))
    cmds.currentTime(20)
    AT.attach(lhand, prop)                                        # the hand follows the stick (the way Gus needs it)
    # 5.6.44: the hand has keys of its own - they keep working on top (by design: 'you can still move it'), so
    # what follows the stick exactly is the space it's held in (offset parent x parent), not the hand itself
    rel_h = _held_rel(lhand, prop)
    worst = 0.0
    for f in range(20, 60):
        cmds.currentTime(f)
        worst = max(worst, _diff(_held_rel(lhand, prop), rel_h))
    rep.expect("the IK hand's held space follows the stick exactly, frames 20-59 (its own keys work on top)",
               worst < TOL, "%.5f" % worst)
    for n in (lhand,):
        AT.remove(n)
    cmds.currentTime(30)
    before = _pos(box)
    AT.hand_over(box, rhand, frames=4)
    cmds.currentTime(30)
    rep.expect("hand-over at 30: no jump at its start", _diff(_pos(box), before) < TOL,
               "%.5f" % _diff(_pos(box), before))
    cmds.currentTime(34)
    rel_r = A_rel(box, rhand)
    cmds.currentTime(45)
    rep.expect("after the hand-over the box follows the right hand exactly", _diff(A_rel(box, rhand), rel_r) < TOL)
    cmds.currentTime(50)
    before = _pos(box)
    AT.both(box, lhand)
    cmds.currentTime(50)
    rep.expect("both hands at 50: no jump", _diff(_pos(box), before) < TOL)
    cmds.currentTime(55)
    rep.add(INFO, "both hands: the box at 55", "%s (left %s, right %s)" % (
        [round(v, 3) for v in _pos(box)], [round(v, 3) for v in _pos(lhand)], [round(v, 3) for v in _pos(rhand)]))
    rep.add(INFO, "where the box is held", AT.describe(box))
    marks = [b for b in (cmds.ls(type="timeSliderBookmark") or [])
             if (cmds.getAttr(b + ".name") or "").startswith("gusAttach_Box")]
    if cmds.about(batch=True):
        rep.add(INFO, "coloured stretches on the Time Slider", "%d here - they need the Maya window (Maya without a "
                "window has no Time Slider): look at them in Maya" % len(marks))
    else:
        rep.expect("coloured stretches on the Time Slider for the box", len(marks) >= 2, str(len(marks)), bad=NOTE)
    n = len(AT.events(box))
    AT.delete_change(box, 50)
    rep.expect("delete the 'both' change: one change fewer", len(AT.events(box)) == n - 1)
    try:
        AT.attach(rhand, box)
        refused = ""
    except RuntimeError as e:
        refused = str(e)
    rep.expect("a loop is refused (the right hand can't follow the box it holds)", "loop" in refused, refused)
    cmds.currentTime(40)
    at40 = _pos(box)
    rep.step("Bake the box", AT.bake, box, 1, 60)
    cmds.currentTime(40)
    rep.expect("baked: the attach gone, the box where it was (frame 40)", not AT.read(box) and
               _diff(_pos(box), at40) < 1e-2, "%.5f" % _diff(_pos(box), at40))


def attach_quiet(rep):
    """j. Attach (5.6.43): Gus's shot - the IK wrist, no keys of its own, attached to a prop at frame 30. No
    'divide by zero' warnings (5.6.41-42 printed one every frame where nothing held it), the wrist where it is
    before frame 30 and following the prop after; an old attach (floor 0.000001) repaired."""
    _animtool()
    from gus_animtool import attach as AT
    rep.start("j. Attach without 'divide by zero' (the IK wrist on a prop, from frame 30)")
    cmds.playbackOptions(minTime=1, maxTime=60)
    rig = cmds.group(empty=True, name="rig_grp")
    arm = cmds.group(empty=True, name="L_wrist_IK_offset", parent=rig)
    cmds.setAttr(arm + ".translate", 3, 4, 0)
    wrist = _ctrl("L_wrist_IK_ctrl", parent=arm)
    axe = _ctrl("Axe_CTRL_01")
    for f, x, y, z, ry in ((1, 0, 0, 5, 0), (60, 10, 3, 5, 120)):
        for a, v in (("translateX", x), ("translateY", y), ("translateZ", z), ("rotateY", ry)):
            cmds.setKeyframe(axe, attribute=a, time=f, value=v)
    warnings = []
    cb = None
    try:
        import maya.OpenMaya as om1
        def _out(msg, kind, *_):
            if "divide by zero" in msg:
                warnings.append(msg)
        cb = om1.MCommandMessage.addCommandOutputCallback(_out)
    except Exception as e:
        rep.add(INFO, "warnings can't be counted here", str(e))
    try:
        cmds.currentTime(10)
        free10 = _pos(wrist)
        cmds.currentTime(30)
        AT.attach(wrist, axe)
        for f in range(1, 61):
            cmds.currentTime(f)
            cmds.getAttr(wrist + ".worldMatrix[0]")
        cmds.currentTime(10)
        rep.expect("before frame 30 the wrist stays where it was (not 'unpredictable')",
                   _diff(_pos(wrist), free10) < TOL, "%.5f" % _diff(_pos(wrist), free10))
        cmds.currentTime(30)
        rel = A_rel(wrist, axe)
        worst = 0.0
        for f in range(30, 61):
            cmds.currentTime(f)
            worst = max(worst, _diff(A_rel(wrist, axe), rel))
        rep.expect("from frame 30 the wrist follows the axe exactly", worst < TOL, "%.5f" % worst)
        d = AT.read(wrist)
        floors = [cmds.getAttr(n + ".minR") for n in d["norm"] if cmds.nodeType(n) == "clamp"]
        rep.expect("every divider's floor 0.001", floors and min(floors) >= 0.001 - 1e-9, str(floors))
        for n in d["norm"]:
            if cmds.nodeType(n) == "clamp":
                cmds.setAttr(n + ".minR", 1e-6)                     # as 5.6.41-42 made it
        rep.expect("Repair fixes a 5.6.41-42 attach", AT.repair() >= 2)
        del warnings[:]
        for f in range(1, 61):
            cmds.currentTime(f)
            cmds.getAttr(wrist + ".worldMatrix[0]")
        if cb is not None:
            rep.expect("no 'divide by zero' warnings over the whole shot", not warnings, "%d warning(s)" % len(warnings))
    finally:
        if cb is not None:
            try:
                om1.MMessage.removeCallback(cb)
            except Exception:
                pass


def _held_rel(n, holder):
    """The space n is held in (its offset parent matrix x its parent's world), in holder's space."""
    import maya.api.OpenMaya as om
    held = om.MMatrix(cmds.getAttr(n + ".offsetParentMatrix"))
    parent = cmds.listRelatives(n, parent=True, fullPath=True)
    if parent:
        held = held * om.MMatrix(_wm(parent[0]))
    m = held * om.MMatrix(_wm(holder)).inverse()
    return [m[12], m[13], m[14], m[0], m[1], m[2]]


def inbetween_case(rep):
    """k. Add / Remove inbetween (5.6.44): Gus got "Cannot move keys" and nothing moved. Two keyed controls, one
    curve locked (Maya refuses to move it): the others move, the locked one is named."""
    _animtool()
    from gus_animtool import anim as A
    from gus_animtool import keys as K
    rep.start("k. Add / Remove inbetween (Animtool): moves, and one refused curve doesn't stop the rest")
    cmds.playbackOptions(minTime=1, maxTime=40)
    arm = _ctrl("Arm_ctrl")
    leg = _ctrl("Leg_ctrl")
    for n in (arm, leg):
        for f, v in ((1, 0.0), (10, 2.0), (20, 5.0), (30, 1.0)):
            cmds.setKeyframe(n, attribute="translateX", time=f, value=v)
    times = lambda n: cmds.keyframe(n + ".translateX", query=True, timeChange=True)
    cmds.select([arm, leg])
    cmds.currentTime(10)
    n = rep.step("Add inbetween at frame 10 (selection)", K.inbetween, 1, "selection")
    rep.expect("the keys after 10 moved one later", times(arm) == [1, 10, 21, 31] and times(leg) == [1, 10, 21, 31],
               "%s / %s" % (times(arm), times(leg)))
    n = rep.step("Remove inbetween at frame 10", K.inbetween, -1, "selection")
    rep.expect("back where they were", times(arm) == [1, 10, 20, 30], str(times(arm)))
    curve = cmds.listConnections(leg + ".translateX", source=True, destination=False)[0]
    cmds.lockNode(curve, lock=True)
    said = []
    real = A.message
    A.message = lambda t, level="ok": said.append((t, level))
    try:
        try:
            n = K.inbetween(1, "selection")
            err = ""
        except RuntimeError as e:
            n, err = 0, str(e)
    finally:
        A.message = real
        cmds.lockNode(curve, lock=False)
    rep.add(INFO, "a locked curve: what Maya and the tool said", "%s | %s" % (err or "-", said[-1][0] if said else "-"))
    rep.expect("one curve locked: the other still moves", times(arm) == [1, 10, 21, 31], str(times(arm)))
    if times(leg) == [1, 10, 20, 30]:
        rep.expect("...and the locked one is named", said and curve.split("|")[-1] in said[-1][0], str(said))
    else:
        rep.add(INFO, "Maya moved the locked curve anyway (lockNode doesn't stop key edits here)", str(times(leg)))


def shape_editing(rep):
    """n. The Controls tab's shape editing (5.6.47), measured on real curve points: in front along an axis (the
    pivot stays), pivot on the shape, stretch on one axis, shape handles (Done / Cancel), keep size on a new shape."""
    from gus_rigtool.core import curves, make_controls as MC, shape_data, shape_edit as SE
    rep.start("n. Shape editing (Controls tab): in front, pivot on the shape, stretch, handles")
    cmds.select(clear=True)
    j = cmds.joint(name="Check_arm_jnt", position=(0, 0, 0))
    out = MC.make([j], shape="circle", size=1.0, front=2.0, front_axis="+Y", pivot_on_shape=False)
    ctrl = out[0][1]
    pts = [p for s in curves.world_positions(ctrl) for p in s]
    mid = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    rep.expect("in front +Y 2, the pivot on the joint: the shape's centre 2 up, the control at the joint",
               abs(mid[1] - 2.0) < 0.05 and _diff(_pos(ctrl), (0, 0, 0)) < TOL, "centre %s, control %s" % (
                   [round(v, 3) for v in mid], [round(v, 3) for v in _pos(ctrl)]))
    cmds.select(clear=True)
    j2 = cmds.joint(name="Check_leg_jnt", position=(5, 0, 0))
    out = MC.make([j2], shape="circle", size=1.0, front=2.0, front_axis="+Y", pivot_on_shape=True)
    rep.expect("pivot on the shape: the control itself 2 up", _diff(_pos(out[0][1]), (5, 2, 0)) < TOL,
               str([round(v, 3) for v in _pos(out[0][1])]))
    before = [p for s in curves.world_positions(ctrl) for p in s]
    SE.stretch([ctrl], "Z", 2.0)
    after = [p for s in curves.world_positions(ctrl) for p in s]
    span = lambda ps, i: max(p[i] for p in ps) - min(p[i] for p in ps)
    rep.expect("stretch Z x2: twice as long on Z, the same on X", abs(span(after, 2) - 2 * span(before, 2)) < 1e-3 and
               abs(span(after, 0) - span(before, 0)) < 1e-3)
    hs = SE.handles_start([ctrl])
    cmds.setAttr(hs[0] + ".translateX", 1.5)
    SE.handles_done()
    moved = [p for s in curves.world_positions(ctrl) for p in s]
    rep.expect("shape handle moved 1.5, Done: the shape moved 1.5, the control's channels still 0",
               abs((sum(p[0] for p in moved) - sum(p[0] for p in after)) / len(moved) - 1.5) < 1e-3 and
               _diff(cmds.getAttr(ctrl + ".translate")[0], (0, 0, 0)) < TOL and not cmds.ls("*" + SE.HANDLE + "*"))
    hs = SE.handles_start([ctrl])
    cmds.setAttr(hs[0] + ".translateX", 9.0)
    SE.handles_cancel()
    rep.expect("Cancel: nothing changed", [p for s in curves.world_positions(ctrl) for p in s] == moved)
    old = curves.read_shape(ctrl)
    SE.use_shape([ctrl], shape_data.builtin_shapes()[0][1][2][1], keep_size=True)      # a square
    c0, h0 = shape_data.bounds(old)
    c1, h1 = shape_data.bounds(curves.read_shape(ctrl))
    rep.expect("a new shape, keep size: the same size and place", abs(h0 - h1) < 1e-3 and _diff(c0, c1) < 1e-3)


def body_shapes(rep):
    """o. Shapes on the body (5.6.48), measured on real meshes: fit to the body (a sphere of radius 2 around the
    control), lie on the skin, shape from an edge loop (a cylinder's middle ring), a new control on a control, a
    locked control's shape changed in place."""
    from gus_rigtool.core import curves, make_controls as MC, shape_data, shape_edit as SE
    from gus_rigtool.tools import controls_tab as CT
    rep.start("o. Shapes on the body: fit, lie on the skin, from edges, a control on a control, locked controls")
    dist = lambda p, c=(0, 0, 0): sum((p[i] - c[i]) ** 2 for i in range(3)) ** 0.5
    ball = cmds.polySphere(name="Check_ball_geo", radius=2.0, subdivisionsX=40, subdivisionsY=40,
                           constructionHistory=False)[0]
    cmds.select(clear=True)
    j = cmds.joint(name="Check_ball_jnt", position=(0, 0, 0))
    ctrl = MC.make([j], shape="circle", size=0.5)[0][1]
    got, missed = SE.fit_to_body([ctrl], ball, 0.2)
    ds = [dist(p) for s in curves.world_positions(ctrl) for p in s]
    rep.expect("fit to the body, gap 20%: every point 2.4 from the centre (the skin at 2)", not missed and
               all(abs(d - 2.4) < 0.05 for d in ds), "%.3f to %.3f, %d missed" % (min(ds), max(ds), missed))
    cmds.select(clear=True)
    j2 = cmds.joint(name="Check_cheek_jnt", position=(3, 0, 0))
    cheek = MC.make([j2], shape="circle", size=0.5, face="X")[0][1]
    SE.lie_on_skin([cheek], ball, 0.2)
    ds = [dist(p) for s in curves.world_positions(cheek) for p in s]
    rep.expect("lie on the skin, gap 20%: every point just off the skin (about 2.1)",
               all(2.02 < d < 2.2 for d in ds), "%.3f to %.3f" % (min(ds), max(ds)))
    can = cmds.polyCylinder(name="Check_can_geo", radius=1.0, height=2.0, subdivisionsAxis=20,
                            subdivisionsHeight=2, constructionHistory=False)[0]
    ring = []
    for e in cmds.ls(can + ".e[*]", flatten=True):
        vs = cmds.ls(cmds.polyListComponentConversion(e, toVertex=True), flatten=True)
        if all(abs(cmds.pointPosition(v, world=True)[1]) < 1e-4 for v in vs):
            ring.append(e)
    made = SE.from_edges(ring, [], 0.2)
    pts = [p for s in curves.world_positions(made[0]) for p in s]
    rs = [(p[0] ** 2 + p[2] ** 2) ** 0.5 for p in pts]
    rep.expect("shape from edges (the can's middle ring, gap 20%): a new control around the can, about 1.2 out",
               len(ring) == 20 and all(1.05 < r < 1.35 for r in rs) and all(abs(p[1]) < 0.05 for p in pts),
               "%d edges; radius %.3f to %.3f" % (len(ring), min(rs), max(rs)))
    new = CT.on_controls([ctrl], dict(CT.DEFAULTS))
    rep.expect("Make on a selected control: a new control at its place, the old one unchanged",
               len(new) == 1 and new[0] != ctrl and _diff(_pos(new[0]), _pos(ctrl)) < TOL and cmds.objExists(ctrl)
               and not cmds.listConnections(ctrl, source=True, destination=False, type="constraint"), str(new))
    shape = curves.curve_shapes(cheek)[0]
    cmds.lockNode(shape, lock=True)
    try:
        SE.use_shape([cheek], shape_data.builtin_shapes()[0][1][2][1], keep_size=True)        # a square
        n_cv = len(cmds.ls(curves.curve_shapes(cheek)[0] + ".cv[*]", flatten=True) or [])
        rep.expect("a locked control (lockNode): its shape changed in place to the square", n_cv in (4, 5),
                   "%d CVs" % n_cv)
    except Exception as e:
        rep.add(FAIL, "a locked control (lockNode): its shape changed", "%s: %s" % (type(e).__name__, e))
    finally:
        for sh in curves.curve_shapes(cheek):
            cmds.lockNode(sh, lock=False)


def face_curves(rep):
    """p. Face from two curves (5.7.4): the line above and below an eye (their ends meet) - one loop round it; two
    curves along a cheek, one drawn the other way, under a moved group - the ribbon between them, where they are;
    a strip made and mirrored from them; Redo from the same curves."""
    import math
    from gus_rigtool.core import face_kit as FK
    rep.start("p. Face from two curves: the lid lines, a cheek strip, mirrored, Redo")
    cmds.file(new=True, force=True)

    def arc(name, sign):
        return cmds.curve(degree=3, name=name, editPoint=[(4 + 2 * math.cos(a), 50 + sign * 1.0 * math.sin(a), 10)
                                                          for a in [math.pi * i / 6 for i in range(7)]])
    up, low = arc("Check_lid_up_crv", 1), arc("Check_lid_low_crv", -1)
    how = FK.curve_pair([up, low])
    rep.expect("the line above and below the eye: their ends meet - one loop, on the left", how["kind"] == "loop" and
               how["side"] == "L", str(how))
    srf, looped = FK.strip_from_curves([up, low], "Check_Eyelid_Ribbon")
    box = cmds.exactWorldBoundingBox(srf)
    rep.expect("...a ribbon round the eye: as wide as the lines (x 2 to 6), between them (y 49 to 51)",
               1.6 < box[0] < 2.3 and 5.7 < box[3] < 6.4 and 48.7 < box[1] < 49.3 and 50.7 < box[4] < 51.3,
               "x %.2f to %.2f, y %.2f to %.2f" % (box[0], box[3], box[1], box[4]))
    rep.expect("...your two curves are still there", cmds.objExists(up) and cmds.objExists(low))
    grp = cmds.group(empty=True, name="Check_curves_grp")
    cmds.move(0, 0, 2, grp)
    a = cmds.curve(degree=3, name="Check_cheek_a", editPoint=[(3 + 0.5 * i, 45 - 0.8 * i, 9) for i in range(5)])
    b = cmds.curve(degree=3, name="Check_cheek_b", editPoint=[(3.6 + 0.5 * i, 45 - 0.8 * i, 9) for i in range(5)][::-1])
    cmds.parent(a, b, grp, relative=True)
    how = FK.curve_pair([a, b])
    rep.expect("two curves along a cheek, one drawn the other way: side by side, it's turned", how["kind"] == "sides"
               and how["reverse"], str(how))
    srf2, _l = FK.strip_from_curves([a, b], "Check_cheek_Ribbon")
    box = cmds.exactWorldBoundingBox(srf2)
    rep.expect("...lofted between them where they are (the group moved them 2 forward: z 11)",
               abs(box[2] - 11) < 0.05 and abs(box[5] - 11) < 0.05 and 2.9 < box[0] < 3.1 and 5.5 < box[3] < 5.7,
               "x %.2f to %.2f, z %.2f to %.2f" % (box[0], box[3], box[2], box[5]))
    try:
        u = cmds.getAttr(cmds.listRelatives(srf2, shapes=True, fullPath=True)[0] + ".minMaxRangeU")[0]
        p0 = cmds.pointOnSurface(srf2, parameterU=u[0], parameterV=0.5, position=True)
        p1 = cmds.pointOnSurface(srf2, parameterU=u[1], parameterV=0.5, position=True)
        rep.expect("...it runs along U, top to bottom of the cheek (no twist: one end at each end)",
                   abs(p0[1] - p1[1]) > 2.5, "U ends at y %.2f / %.2f" % (p0[1], p1[1]))
    except Exception as e:
        rep.add(FAIL, "...it runs along U", "%s: %s" % (type(e).__name__, e))
    for n in (srf, srf2):
        cmds.delete(n)
    try:
        made = FK.facial(None, "check", "L", "cartoony", True, curves=[a, b])
        ctrls = [c for m in made for _i, _o, c in FK.controls_of(m)]
        rep.expect("Make strip from the two curves: L_ and R_check_Ribbon, controls on both sides",
                   len(made) == 2 and len(ctrls) >= 4, "%s, %d controls" % (", ".join(made), len(ctrls)))
        again = FK.redo(made[0])
        rep.expect("Redo: made again from the same two curves", len(again) == 2,
                   ", ".join(str(x) for x in again))
    except Exception as e:
        rep.add(FAIL, "Make strip from two curves", "%s: %s" % (type(e).__name__, e))


def A_rel(n, holder):
    """n's world position in holder's space (what 'follows exactly' keeps)."""
    import maya.api.OpenMaya as om
    m = om.MMatrix(_wm(n)) * om.MMatrix(_wm(holder)).inverse()
    return [m[12], m[13], m[14], m[0], m[1], m[2]]


def controllers(rep):
    """l. The one control maker (5.6.45), on the biped e built: every control a Maya controller, pick-walk up goes
    to the control above; a plain curve made by hand tagged by Checker > Tag all controls."""
    from gus_rigtool.core import control_maker as CM
    from gus_rigtool.core import rig_checks as checker   # (5.7.10: the checks, not the page)
    rep.start("l. Every control a Maya controller, pick-walk (the biped)")
    ctrls = [c for c in cmds.ls(type="transform", long=True) or [] if checker.is_control(c)]
    untagged = [c for c in ctrls if not CM.is_tagged(c)]
    rep.expect("every control the Builder made is a Maya controller", ctrls and not untagged,
               "%d of %d untagged: %s" % (len(untagged), len(ctrls), ", ".join(c.split("|")[-1] for c in untagged[:6])))
    walked = []
    for c in ctrls:
        above = CM._tagged_above(c)
        if not above:
            continue
        try:
            got = cmds.controller(c, query=True, parent=True)
        except (RuntimeError, TypeError):
            got = None
        walked.append((c, above, got))
    linked = [w for w in walked if w[2] and w[1].split("|")[-1] in str(w[2])]
    rep.add(INFO, "controls with a control above them / linked to it", "%d / %d" % (len(walked), len(linked)))
    rep.expect("pick-walk up: each goes to the control above it", walked and len(linked) == len(walked),
               "; ".join("%s -> %s (wanted %s)" % (c.split("|")[-1], g, a.split("|")[-1])
                         for c, a, g in walked if (c, a, g) not in linked)[:300])
    loose = cmds.circle(name="Handmade_ctrl", constructionHistory=False)[0]
    rep.expect("a curve made by hand: not tagged by itself", not CM.is_tagged(loose))
    n, _l = CM.tag_all([cmds.ls(loose, long=True)[0]])
    rep.expect("Tag all controls tags it", n == 1 and CM.is_tagged(loose))
    cmds.delete(loose)


def maya_facts_case(rep):
    """m. Maya facts (5.6.46): how Maya behaves where the tool depends on it - info only, for MAYA_FACTS.md."""
    from gus_rigtool.realmaya import maya_facts
    maya_facts.facts(rep)


CASES = [("a. pupils", pupils), ("b. history", history), ("c. head squash leftovers", squash_leftovers),
         ("e. biped: build, publish, unpublish", rig), ("d. Check this scene", scene_check_run),
         ("l. controllers", controllers), ("f. IK/FK and mirror", ikfk_mirror), ("g. rig self-test", rig_selftest), ("h. arcs", arcs),
         ("i. attach", attach_case), ("j. attach, no divide by zero", attach_quiet),
         ("k. add / remove inbetween", inbetween_case), ("n. shape editing", shape_editing),
         ("o. shapes on the body", body_shapes),
         ("p. face from two curves", face_curves),
         ("m. Maya facts", maya_facts_case)]
WHOLE_RIG = ("d. Check this scene", "f. IK/FK and mirror", "l. controllers")      # they run on the biped e built - no new scene
# (g makes its own scenes)
