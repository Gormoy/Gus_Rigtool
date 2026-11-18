"""
Onion Skin - the test inside real Maya (mayapy, no window). Double-click run_test.bat (Windows) or
run_test.command (Mac). It builds two small keyed characters in an empty scene, never touches your files, and
writes onion_test_results.txt next to this file.
"""
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
OUT = os.path.join(HERE, "onion_test_results.txt")
lines = []
ok = []


def check(label, cond, detail=""):
    ok.append(bool(cond))
    lines.append(("PASS " if cond else "FAIL ") + label + (("   " + detail) if detail else ""))


def bbox(n):
    return cmds.exactWorldBoundingBox(n)


def close(a, b, tol=1e-3):
    return max(abs(x - y) for x, y in zip(a, b)) < tol


def character(ns, root, x, keys):
    """A joint, a skinned cylinder and a keyed control; ns '' = no namespace (under the top group root)."""
    p = ns + ":" if ns else ""
    if ns and not cmds.namespace(exists=ns):
        cmds.namespace(add=ns)
    top = cmds.group(empty=True, name=p + root)
    cmds.select(clear=True)
    j0 = cmds.joint(name=p + "hip_jnt", position=(x, 0, 0))
    cmds.joint(name=p + "top_jnt", position=(x, 6, 0))
    cmds.parent(j0, top)
    geo = cmds.polyCylinder(name=p + "body", height=6, radius=0.6, subdivisionsY=6)[0]
    cmds.move(x, 3, 0, geo)
    cmds.delete(geo, constructionHistory=True)
    cmds.makeIdentity(geo, apply=True)
    geo = cmds.parent(geo, top)[0]
    cmds.skinCluster(p + "hip_jnt", p + "top_jnt", geo, toSelectedBones=True)
    ctrl = cmds.circle(name=p + "ctrl", normal=(0, 1, 0), constructionHistory=False)[0]
    ctrl = cmds.parent(ctrl, top)[0]
    cmds.connectAttr(ctrl + ".rotateZ", p + "hip_jnt.rotateZ")
    for t, v in keys:
        cmds.setKeyframe(ctrl, attribute="rotateZ", time=t, value=v)
    return cmds.ls(ctrl, long=True)[0], cmds.ls(geo, long=True)[0]


def ghost_of(cid, frame):
    from onion_skin import core
    grp = "|%s|%s" % (core.ROOT, core._frame_group(cid, frame))
    meshes = cmds.listRelatives(grp, allDescendents=True, type="mesh", fullPath=True) or [] \
        if cmds.objExists(grp) else []
    return [cmds.listRelatives(m, parent=True, fullPath=True)[0] for m in meshes]


def main():
    global cmds
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    from onion_skin import core, live
    cmds.file(new=True, force=True)
    cmds.undoInfo(state=True)                     # on, so 'nothing went into the undo queue' means something
    cmds.playbackOptions(minTime=1, maxTime=30)
    a_ctrl, a_geo = character("A", "RIG", 0, [(1, 0), (10, 40), (20, -30)])
    b_ctrl, b_geo = character("", "B_RIG", 8, [(5, 20), (15, -45)])
    lines.append("built: %s, %s" % (a_ctrl, b_ctrl))

    # the real poses, measured by going to each frame
    real = {}
    for f in (5, 10, 15, 20):
        cmds.currentTime(f)
        real[("A", f)], real[("B_RIG", f)] = bbox(a_geo), bbox(b_geo)
    cmds.currentTime(12)
    undo_before = cmds.undoInfo(query=True, undoName=True)

    core.set_opt("mode", "keys")
    core.set_opt("past", 1)
    core.set_opt("next", 1)
    core.add_targets([a_ctrl, "B_RIG"])
    got = core.update()
    check("two characters, each at its own keys: A 10 / 20, B 5 / 15",
          got["frames"] == {"A": [10.0, 20.0], "B_RIG": [5.0, 15.0]}, str(got["frames"]))
    for cid, frames in (("A", (10, 20)), ("B_RIG", (5, 15))):
        for f in frames:
            gs = ghost_of(cid, float(f))
            check("%s ghost at %d: there, and in the pose of frame %d" % (cid, f, f),
                  len(gs) == 1 and close(bbox(gs[0]), real[(cid, f)]), str(gs))
    check("the time stayed at 12", cmds.currentTime(query=True) == 12)
    check("nothing went into the undo queue", cmds.undoInfo(query=True, undoName=True) == undo_before,
          "%r / %r" % (undo_before, cmds.undoInfo(query=True, undoName=True)))
    check("ghosts are in the reference layer (seen, not selectable)",
          cmds.getAttr(core.LAYER + ".displayType") == 2)

    cmds.currentTime(14)
    got = core.update()
    check("moving between the same keys: nothing rebuilt", got["made"] == 0 and got["removed"] == 0)

    cmds.setKeyframe(a_ctrl, attribute="rotateZ", time=10, value=70)
    cmds.currentTime(10)
    new10 = bbox(a_geo)
    cmds.currentTime(14)
    check("changing a key: its ghost follows (no rebuild needed)", close(bbox(ghost_of("A", 10.0)[0]), new10))

    core.set_opt("mode", "frames")
    core.set_opt("step", 3)
    core.set_opt("past", 2)
    got = core.update()
    check("every 3 frames, 2 past / 1 next at 14: 11, 8, 17", got["frames"]["A"] == [11.0, 8.0, 17.0],
          str(got["frames"]))
    core.set_opt("mode", "keys")
    core.set_opt("past", 1)
    core.update()

    live.start()
    path = os.path.join(tempfile.gettempdir(), "onion_skin_save_test.ma")
    cmds.file(rename=path)
    cmds.file(save=True, type="mayaAscii", force=True)
    text = open(path).read()
    check("a saved file has no ghosts in it", "onionSkin" not in text)
    got = core.update()
    check("after the save the ghosts come back", got["made"] > 0, str(got))
    live.stop()

    core.clear(keep_targets=False)
    left = [n for n in cmds.ls("onionSkin*") or []]
    check("Clear list: nothing of the tool left in the scene", not left, str(left))
    try:
        os.remove(path)
    except OSError:
        pass
    maya.standalone.uninitialize()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        lines.append("FAIL the test itself stopped:\n" + traceback.format_exc())
        ok.append(False)
    text = "Onion Skin - test in real Maya\n\n" + "\n".join(lines) + \
        "\n\n%d/%d passed\n" % (sum(ok), len(ok))
    with open(OUT, "w") as f:
        f.write(text)
    print(text)
    print("Saved: " + OUT)
