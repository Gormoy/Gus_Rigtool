# 5.6.11: head squash - a lattice round the head (fitted round the face controls, up over the skull), after the
# skin, the meshes + the face controls' curves in it (not the face ribbons: the face would squash twice), squash +
# 2 bends on the lattice driven by Head_squash_ctrl (up / down, sideways, front-back, x its sliders, / the head's
# height), an on / off on Visibility_ctrl stopping every deformer, undone if anything moved at rest, Remove cleans up;
# the scene check finds a squash that comes before the skin
import sys
exec(open("fakemaya.py").read())
from gus_rigtool.core import head_squash as HS, vis_switch as VS
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)
src = lambda p: cmds.listConnections(p, source=True, destination=False, plugs=True) or []
def mk(name, parent=None, pos=(0, 0, 0)):
    t = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    cmds.createNode("nurbsCurve", name=name + "Shape", parent=t)
    cmds.xform(t, worldSpace=True, translation=pos)
    return cmds.ls(t, long=True)[0]

head = mk("Head_ctrl", None, (0, 70, 0))
for n, p in (("L_Mouth_fol_06_ctrl", (4, 78, 11)), ("R_Mouth_fol_22_ctrl", (-4, 78, 11)), ("Mouth_fol_33_ctrl", (0, 76, 12)),
             ("L_Brow_ctrl", (4, 92, 10)), ("L_Eyelids_fol_01_ctrl", (4, 88, 10))):
    mk(n, head, p)
body = cmds.createNode("transform", name="Hare_Body"); cmds.createNode("mesh", name="Hare_BodyShape", parent=body)
sw = mk("Visibility_ctrl", head, (0, 120, 0))
cmds.addAttr(sw, longName=VS.MARK, attributeType="bool")

def _nurbs_plane(name=None, **k):                   # (5.6.15: the ears' riders - Maya's plane, stood in)
    t = cmds.createNode("transform", name=name)
    cmds.createNode("nurbsSurface", name=name + "Shape", parent=t)
    return [t]
cmds.nurbsPlane = _nurbs_plane
cmds.percent = lambda *a, **k: None
made = {"lattice": None}
LATTICE_FLAGS = {"divisions", "objectCentered", "ldivisions", "after", "before", "frontOfChain", "name", "position",
                 "scale", "rotation", "outsideLattice", "outsideFalloffDistance", "commonParent", "geometry",
                 "parallel", "split", "exclusive", "freezeMapping", "removeTweaks", "latticeReset"}
def lattice(members, **k):                          # Maya's own flags only (5.6.12 used one it doesn't have)
    bad = set(k) - LATTICE_FLAGS
    if bad:
        raise TypeError("Invalid flag '%s'" % sorted(bad)[0])
    made["lattice"] = (list(members), k)
    ffd = cmds.createNode("ffd", name="Head_squashFfd")
    lat = cmds.createNode("transform", name="Head_squashLattice")
    base = cmds.createNode("transform", name="Head_squashBase")
    return [ffd, lat, base]
nl = []
def nonLinear(target, type=None, name=None):
    d = cmds.createNode("nonLinear", name=name)
    for a in ("lowBound", "highBound", "maxExpandPos", "expand", "factor", "curvature", "nodeState"):
        cmds.addAttr(d, longName=a, attributeType="double")
    h = cmds.createNode("transform", name=name + "Handle")
    nl.append((type, d, h))
    return [d, h]
for n in ("Head_squashFfd",):
    pass
with mock.patch.object(cmds, "lattice", side_effect=lattice, create=True), \
        mock.patch.object(cmds, "nonLinear", side_effect=nonLinear, create=True), \
        mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=lambda name, *a, **k: mk(name)), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}), \
        mock.patch.object(HS, "_points", return_value={}), \
        mock.patch.object(cmds, "createNode", side_effect=lambda t, **k: _cn(t, **k)):
    pass
_real_cn = cmds.createNode
def _cn(t, **k):
    n = _real_cn(t, **k)
    if t == "ffd":
        cmds.addAttr(n, longName="nodeState", attributeType="double")
    return n
for n, p in (("L_Ear_01_FK_ctrl", (6, 200, -2)), ("L_Ear_04_FK_ctrl", (8, 330, -4)), ("L_Eye_ctrl", (4, 88, 160)),
             ("Eyes_ctrl", (0, 88, 160))):
    mk(n, head, p)
check("not in the face for the box: the ears, the eye aim targets", not any(
    c.split("|")[-1] in ("L_Ear_01_FK_ctrl", "L_Ear_04_FK_ctrl", "L_Eye_ctrl", "Eyes_ctrl") for c in HS.face_controls()))
lines = HS.plan(head, ["Hare_Body"])
print("\n".join(lines))
check("the plan: a lattice round the head fading out past it, the meshes, the rest of the body not in it",
      "fades out" in lines[0] and "Hare_Body" in lines[1] and "can't move" in lines[2])
centre, size = HS.region(head, HS.face_controls())
check("the box: from below the mouth (%.1f) up well over the brows (%.1f)" % (centre[1] - size[1] / 2,
                                                                              centre[1] + size[1] / 2),
      centre[1] - size[1] / 2 < 76 and centre[1] + size[1] / 2 > 92 + 10)
with mock.patch.object(cmds, "lattice", side_effect=lattice, create=True), \
        mock.patch.object(cmds, "nonLinear", side_effect=nonLinear, create=True), \
        mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=lambda name, *a, **k: mk(name)), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}), \
        mock.patch.object(HS, "_points", return_value={}), \
        mock.patch.object(cmds, "createNode", side_effect=_cn):
    c = HS.make(head, ["Hare_Body"])
members, kw = made["lattice"]
h = HS.region(head, HS.face_controls())[1][1]
hl = HS._with_ears(*HS.region(head, HS.face_controls()))[1][1]        # 5.6.17: the box takes in the ears' bases
check("the lattice: the body (no control curves - 5.6.14) + the ears' planes, placed without 'after' (5.6.17: "
      "that made Maya copy the mesh), fading out past it",
      [m for m in members if "squash_srf" not in m and HS.RIDER not in m] == ["|Hare_Body"] and not kw.get("after") and cmds.getAttr("Head_squashFfd.outsideLattice") == 2)
riders = HS.read().get("riders", [])
print(sorted(x.split("|")[-1] for x, _c in riders))
check("5.6.18: each face control's curve has a hidden copy in the lattice feeding it (the control's own curve "
      "isn't in it - its colour, switch and connections stay)",
      riders and all(cp in members and x not in members and not cmds.getAttr(cp + ".visibility") and
                     (cmds.listConnections(x + ".create", source=True, destination=False) or [""])[0].split("|")[-1]
                     == cp.split("|")[-1] for x, cp in riders) and
      not any(x.split("|")[-2].lower().startswith(("l_ear", "r_ear", "eyes")) for x, _c in riders))
check("the fade in the lattice's own units (it's 1 tall): a third of the face's height over the box's (%.2f), not "
      "%.1f scene units" % (0.35 * h / hl, 0.35 * h),
      abs(cmds.getAttr("Head_squashFfd.outsideFalloffDist") - 0.35 * h / hl) < 1e-6)
check("Head_squash_ctrl under the head (in Head_squash_grp)", "|Head_ctrl|Head_squash_grp|" in c)
sq = [d for t, d, _h in nl if t == "squash"][0]
bx, bz = [d for t, d, _h in nl if t == "bend"]
def chain(plug):
    out, cur = [], plug
    for _i in range(3):
        s = src(cur)
        if not s:
            break
        out.append(s[0])
        node = s[0].split(".")[0]
        nxt = [node + "." + p for p in ("input1X", "input1") if src(node + "." + p)]
        cur = nxt[0] if nxt else None
        if not cur:
            break
    return out
check("up / down -> the squash", chain(sq + ".factor")[-1] == "Head_squash_ctrl.translateY")
check("sideways -> bend X, front-back -> bend Z", chain(bx + ".curvature")[-1] == "Head_squash_ctrl.translateX" and
      chain(bz + ".curvature")[-1] == "Head_squash_ctrl.translateZ")
check("bulge -> the squash's expand", src(sq + ".expand") == ["Head_squash_ctrl.bulge"])
check("on / off on Visibility_ctrl stops the lattice and all three", cmds.attributeQuery("Head_Squash", node=sw,
                                                                                         exists=True) and
      all(src(d + ".nodeState") and src(d + ".nodeState")[0].startswith("Head_squash_off") for d in
          ("Head_squashFfd", sq, bx, bz)))
check("its sliders", all(cmds.attributeQuery(a, node=c, exists=True) for a in ("squash", "bulge", "bend")))
try:
    HS.make(head, ["Hare_Body"])
    check("a second one: refused", False)
except RuntimeError:
    check("a second one: refused", True)

# only the head's vertices go in (5.6.13 moved the whole body)
c0, sz = HS.region(head, HS.face_controls())
pts = [(0, 30, 0), (0, 31, 0), (0, c0[1], c0[2]), (1, c0[1] + 1, c0[2]), (0, 40, 0), (2, c0[1] - 1, c0[2])]
with mock.patch.object(HS, "_points", return_value={"|Hare_Body": pts}):
    got = HS._members(["|Hare_Body"], c0, sz, 0.35 * sz[1])["|Hare_Body"]
print(got)
check("the vertices in the lattice: the head's (2, 3, 5), not the body's (0, 1, 4)", got[0] == ["|Hare_Body.vtx[2:3]",
                                                                                              "|Hare_Body.vtx[5]"]
      and got[1:] == (3, 6))

# the scene check: before / after the skin
with mock.patch.object(cmds, "listHistory", return_value=["Head_squashFfd", "skinCluster10", "Hare_BodyShapeOrig"]), \
        mock.patch.object(cmds, "nodeType", side_effect=lambda n: {"skinCluster10": "skinCluster"}.get(n, "ffd")):
    check("lattice after the skin: fine", HS.after_skin("Hare_Body"))
with mock.patch.object(cmds, "listHistory", return_value=["skinCluster10", "Head_squashFfd", "Hare_BodyShapeOrig"]), \
        mock.patch.object(cmds, "nodeType", side_effect=lambda n: {"skinCluster10": "skinCluster"}.get(n, "ffd")):
    check("lattice before the skin: found", not HS.after_skin("Hare_Body"))

HS.remove()
check("removed: the face curves let go, their copies gone (5.6.18)",
      all(not cmds.listConnections(x + ".create", source=True, destination=False) and not cmds.objExists(cp)
          for x, cp in riders))
check("removed: the control, its group, the switch, the nodes", not HS.find() and not cmds.objExists("Head_squash_grp")
      and not cmds.attributeQuery("Head_Squash", node=sw, exists=True) and not cmds.objExists("Head_squash_off"))

# a failure half way (a deformer refused): nothing left behind - 5.6.12 left Head_squash_grp
def bad_nl(*a, **k):
    raise RuntimeError("nonLinear: refused")
with mock.patch.object(cmds, "lattice", side_effect=lattice, create=True), \
        mock.patch.object(cmds, "nonLinear", side_effect=bad_nl, create=True), \
        mock.patch.object(HS, "_points", return_value={}), \
        mock.patch.object(cmds, "createNode", side_effect=_cn):
    try:
        HS.make(head, ["Hare_Body"])
    except RuntimeError:
        pass
check("failed half way: no Head_squash_grp, no lattice left", not cmds.objExists("Head_squash_grp") and
      not cmds.objExists("Head_squashLattice"))
cmds.createNode("transform", name="Head_squash_grp")                 # what 5.6.12 left in the Hare
HS._clean_leftover()
check("a leftover Head_squash_grp (no control in it) is cleaned before Make", not cmds.objExists("Head_squash_grp"))

# repair: a control whose curve went through the lattice (5.6.11 - 5.6.13)
t = cmds.createNode("transform", name="L_Brow_fix_ctrl")
orig = cmds.createNode("nurbsCurve", name="L_Brow_fix_ctrlShapeOrig", parent=t)
shown = cmds.createNode("nurbsCurve", name="L_Brow_fix_ctrlShape1", parent=t)
for n, inter in ((orig, 1), (shown, 0)):
    for a in ("intermediateObject", "overrideEnabled", "overrideColor"):
        if not cmds.attributeQuery(a, node=n, exists=True):
            cmds.addAttr(n, longName=a, attributeType="long")
    cmds.setAttr(n + ".intermediateObject", inter)
cmds.setAttr(orig + ".overrideEnabled", 1); cmds.setAttr(orig + ".overrideColor", 13)
cmds.connectAttr(sw + ".Face_Ctrls" if cmds.attributeQuery("Face_Ctrls", node=sw, exists=True) else sw + ".visibility",
                 orig + ".visibility")
real_delete = cmds.delete
with mock.patch.object(cmds, "delete", side_effect=lambda *a, **k: None if k.get("constructionHistory")
                       else real_delete(*a, **k)):
    n = HS.repair_curves([cmds.ls(t, long=True)[0]])
left = cmds.listRelatives(t, shapes=True) or []
print(left)
check("repaired: the colour on the curve you see, the switch on it, the hidden copy gone, its name back",
      n == 1 and left == ["L_Brow_fix_ctrlShape"] and cmds.getAttr("L_Brow_fix_ctrlShape.overrideColor") == 13 and
      cmds.getAttr("L_Brow_fix_ctrlShape.overrideEnabled") == 1 and src("L_Brow_fix_ctrlShape.visibility"))

# moved at rest: undone
cc = tuple(c0)
calls = [{"|Hare_Body": [cc]}, {"|Hare_Body": [cc]}, {"|Hare_Body": [(cc[0], cc[1] + 0.5, cc[2])]}]
undone = []
with mock.patch.object(cmds, "lattice", side_effect=lattice, create=True), \
        mock.patch.object(cmds, "nonLinear", side_effect=nonLinear, create=True), \
        mock.patch("gus_rigtool.core.curves.create_curve_control", side_effect=lambda name, *a, **k: mk(name)), \
        mock.patch("gus_rigtool.core.curves.read_shape", return_value=[]), \
        mock.patch("gus_rigtool.core.curves.read_style", return_value={}), \
        mock.patch.object(HS, "_points", side_effect=lambda m: calls.pop(0)), \
        mock.patch.object(cmds, "createNode", side_effect=_cn), \
        mock.patch.object(cmds, "undo", side_effect=lambda *a: undone.append(1), create=True), \
        mock.patch.object(cmds, "undoInfo", side_effect=lambda *a, **k: "gusrigHeadSquash" if k.get("undoName")
                          else True):
    try:
        HS.make(head, ["Hare_Body"])
        check("moved at rest: undone", False)
    except RuntimeError as e:
        check("moved at rest: undone, said so (%s)" % str(e)[:40], undone == [1])
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
