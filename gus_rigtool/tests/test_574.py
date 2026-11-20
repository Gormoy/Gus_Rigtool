# 5.7.4: Face and Ribbon as steps. Face parts from two curves (Gus's way: their ends meet - one loop round the eye /
# lips - or side by side - lofted between them; the edge way stays), 'Make it from' remembered per part, a light on
# each step that checks your selection, the face map, the steps' ticks; Ribbon: Surface > Joints > Controls >
# Create with a strip on top, the Surface light checks the curves, the rarer buttons under More, Builds in the scene
# its own page
exec(open("test_570.py").read().split("# --- 1.")[0])
import math
from gus_rigtool.newui import window as W, widgets
from gus_rigtool.core import face_kit as FK, utils
from gus_rigtool.tools import face_kit_tool as FT, ribbon_tool as RT

# --- stand-in curves: points along each (the fake Maya has no geometry)
SHAPES = {}
def make_curve(name, fn, closed=False):
    t = cmds.curve(name=name, point=[(0, 0, 0)])
    SHAPES[cmds.ls(t, long=True)[0]] = (fn, closed)
    return cmds.ls(t, long=True)[0]
def _geo(c):
    c = cmds.ls(c, long=True)[0] if cmds.ls(c, long=True) else c
    return SHAPES[c]
cmds.pointOnCurve = lambda c, parameter=0.0, turnOnPercentage=True, position=True: list(_geo(c)[0](parameter))
FK._closed = lambda c: _geo(c)[1]
upper = make_curve("L_lid_up_crv", lambda t: (4 + 2 * math.cos(math.pi * t), 50 + 1.0 * math.sin(math.pi * t), 10))
lower = make_curve("L_lid_low_crv", lambda t: (4 + 2 * math.cos(math.pi * t), 50 - 1.0 * math.sin(math.pi * t), 10))
lower_rev = make_curve("L_lid_low_rev", lambda t: (4 - 2 * math.cos(math.pi * t), 50 - 1.0 * math.sin(math.pi * t), 10))
cheek_a = make_curve("L_cheek_a", lambda t: (3 + 2 * t, 45 - 3 * t, 11))
cheek_b = make_curve("L_cheek_b", lambda t: (3.6 + 2 * t, 45 - 3 * t, 11))
cheek_b_rev = make_curve("L_cheek_brev", lambda t: (5.6 - 2 * t, 42 + 3 * t, 11))
ring_in = make_curve("L_ring_in", lambda t: (4 + 1.5 * math.cos(2 * math.pi * t), 50 + math.sin(2 * math.pi * t), 10), True)
ring_out = make_curve("L_ring_out", lambda t: (4 + 2.2 * math.cos(-2 * math.pi * t), 50 + 1.5 * math.sin(-2 * math.pi * t), 10), True)
right_a = make_curve("R_cheek_a", lambda t: (-3 - 2 * t, 45 - 3 * t, 11))
right_b = make_curve("R_cheek_b", lambda t: (-3.6 - 2 * t, 45 - 3 * t, 11))
mouth_up = make_curve("mouth_up", lambda t: (-3 + 6 * t, 40 + math.sin(math.pi * t), 12))
mouth_low = make_curve("mouth_low", lambda t: (-3 + 6 * t, 40 - math.sin(math.pi * t), 12))

# --- 1. how two curves make a ribbon
p = FK.curve_pair([upper, lower])
check("the line above and below the lid (their ends meet at the corners): one loop round the eye, on the left",
      p["kind"] == "loop" and not p["reverse"] and p["side"] == "L")
check("...the lower one drawn the other way: still one loop (it's turned)", FK.curve_pair([upper, lower_rev])["kind"]
      == "loop" and FK.curve_pair([upper, lower_rev])["reverse"])
p = FK.curve_pair([cheek_a, cheek_b])
check("two curves along a cheek: side by side (lofted between them), same direction", p["kind"] == "sides" and
      not p["reverse"])
check("...one drawn the other way: it's turned before the loft", FK.curve_pair([cheek_a, cheek_b_rev])["reverse"])
p = FK.curve_pair([ring_in, ring_out])
check("two rings round the eye: side by side, closed, the outer one turning the other way - turned",
      p["kind"] == "sides" and p["closed"] and p["reverse"])
check("which side: left / right / the middle (the mouth)", FK.curve_pair([right_a, right_b])["side"] == "R" and
      FK.curve_pair([mouth_up, mouth_low])["side"] == "C")
cmds.select(upper, cheek_a, "persp" if cmds.objExists("persp") else upper)
check("the curves among the selection (not other things)", FK.selected_curves()[:2] == [upper, cheek_a])
try:
    cmds.select(upper)
    FK._curves(True)
    check("one curve selected: refused, saying how many", False)
except RuntimeError as e:
    check("one curve selected: refused, saying how many - '%s'" % e, "1 selected" in str(e))

# --- 2. the ribbon from them
made = []
real_curve, real_loft, real_rev = cmds.curve, cmds.loft, getattr(cmds, "reverseCurve", None)
cmds.curve = lambda *a, **k: made.append(("curve", k.get("periodic"), len(k.get("point") or []))) or real_curve(*a, **k)
cmds.loft = lambda *a, **k: made.append(("loft",) + tuple(x.split("|")[-1] for x in a)) or real_loft(*a, **k)
cmds.reverseCurve = lambda c, **k: made.append(("reverse", c.split("|")[-1]))
from unittest import mock
with mock.patch.object(FK, "_band", lambda curve, name, width=None: (made.append(("band", curve.split("|")[-1])) or
                                                                      ("|" + name, True))), \
        mock.patch.object(FK.ribbon, "along_u", lambda s: None):
    FK.strip_from_curves([upper, lower], "L_Eyelid_Ribbon")
    loop = [m for m in made if m[0] == "curve"]
    check("lid lines: one closed curve through both (the corners once), then the thin band either side, as from "
          "an edge loop", loop and loop[0][1] is True and loop[0][2] == 26 + 3 and ("band", "L_Eyelid_Ribbon_crv")
          in made)
    del made[:]
    FK.strip_from_curves([cheek_a, cheek_b_rev], "L_cheek_Ribbon")
    check("side by side: copies lofted (the one drawn the other way turned first); your curves are kept",
          ("reverse", "L_cheek_Ribbon_crvB") in made and ("loft", "L_cheek_Ribbon_crvA", "L_cheek_Ribbon_crvB") in made
          and cmds.objExists(cheek_a) and cmds.objExists(cheek_b_rev) and not cmds.objExists("L_cheek_Ribbon_crvA"))
cmds.curve, cmds.loft = real_curve, real_loft
for n in ("L_cheek_Ribbon", "L_Eyelid_Ribbon"):
    if cmds.objExists(n):
        cmds.delete(n)

# --- 3. a part made from two curves remembers them (Redo makes it again from them)
got = {}
with mock.patch.object(FK, "build_ribbon", lambda name, edges, *a, **k: got.update(name=name, edges=edges,
                                                                                  curves=k.get("curves")) or
                       cmds.ls(cmds.createNode("transform", name=name), long=True)[0]), \
        mock.patch.object(FK, "mirror", lambda srf: None):
    cmds.select(cheek_a, cheek_b)
    FK.facial(None, "cheek", "L", "cartoony", True, curves=True)
check("Make strip from two curves: the ribbon between your two curves", got["curves"] == [cheek_a, cheek_b] and
      got["edges"] == [])
data = FK.part_of("L_cheek_Ribbon")
check("...it remembers the curves it was made from (for Redo)", data["curves"] == ["L_cheek_a", "L_cheek_b"])
calls = []
with mock.patch.object(FK, "facial", lambda edges, *a, **k: calls.append(k.get("curves")) or []), \
        mock.patch.object(FK.ribbon, "_find_builds", lambda: {}), \
        mock.patch.object(FK.ribbon, "_mirrors_of", lambda k, b: []), \
        mock.patch.object(FK.ribbon_keep, "park", lambda k: None) if hasattr(FK, "ribbon_keep") else mock.patch.object(
            utils, "info", utils.info):
    from gus_rigtool.core import ribbon_keep
    with mock.patch.object(ribbon_keep, "park", lambda k: None), mock.patch.object(ribbon_keep, "restore",
                                                                                lambda *a: None):
        FK.redo("L_cheek_Ribbon")
check("...Redo: made again from the same two curves", calls == [["L_cheek_a", "L_cheek_b"]])

# --- 4. the Face tab: Make it from (remembered), each step's light
f = W.Frame(); f.resize(700, 1400); f.show(); f.go(("face", "Build the face"))
for _ in range(3):
    app.processEvents()
a = f.areas["build"]
fp = a.pages["face"]
check("Face's own pages: Build the face · Ribbons & groups · Squash & expressions",
      [b.text() for b in f.tabs2.findChildren(QtWidgets.QPushButton)] ==
      ["Build the face", "Ribbons && groups", "Squash && expressions"])
shown = [c.title for c in fp.cards if c.isVisibleTo(a)]
check("Build the face: Setup, Eyes, Eyelids, Mouth, Brows, Facial strips - in order", shown ==
      ["Setup", "Eyes", "Eyelids", "Mouth", "Brows", "Facial strips"])
check("...the face map on top (only on this page)", a.face_card.isVisibleTo(a))
seg = fp.fields[FT.N("From_eyelids")].widget
check("each part: Make it from Two curves | Edges - Two curves first", [b.text() for b in seg.findChildren(
    QtWidgets.QPushButton)] == ["Two curves", "Edges"] and seg.index() == 0)
seg.buttons[1].click() if hasattr(seg, "buttons") else [b for b in seg.findChildren(QtWidgets.QPushButton)][1].click()
app.processEvents()
check("...Edges on the eyelids: remembered (for next time), the others still Two curves",
      utils.load_setting(FT.SETTINGS_KEY, {}).get("from_eyelids") == "edges" and
      utils.load_setting(FT.SETTINGS_KEY, {}).get("from_mouth") == "curves")
eye = cmds.createNode("transform", name="L_Eye_ctrl")
cmds.select(cheek_a, cheek_b); a.refresh_selection(); app.processEvents()
strip_light = fp.fields[FT.N("Step_strip")]
check("Strips: two curves on the left selected - the light says they fit (side by side) and the step gets a "
      "yellow dot", "2 curves" in strip_light._label() and "side by side" in strip_light._label() and
      [c for c in fp.cards if c.title == "Facial strips"][0].num.text() == "●")
cmds.select(right_a, right_b); a.refresh_selection(); app.processEvents()
check("...the RIGHT side's curves: says to select the left (the right is mirrored)", "LEFT" in strip_light._label()
      and strip_light.level == "warn")
cmds.select(cheek_a); a.refresh_selection(); app.processEvents()
check("...one curve: says to select two", "1 curve" in strip_light._label())
cmds.select(mouth_up, mouth_low); a.refresh_selection(); app.processEvents()
check("Mouth: the lines above and below the lips - their ends meet: one loop",
      "one loop" in fp.fields[FT.N("Step_mouth")]._label())
real_ls = cmds.ls
cmds.ls = lambda *x, **k: ["Head_geo.e[%d]" % i for i in range(12)] if k.get("selection") else real_ls(*x, **k)
try:
    a.refresh_selection(); app.processEvents()
finally:
    cmds.ls = real_ls
check("Eyelids on Edges: 12 edges selected - ready", fp.fields[FT.N("Step_eyelids")].level == "ready" and
      "12 edges" in fp.fields[FT.N("Step_eyelids")]._label())
cmds.select(clear=True)
with mock.patch.object(FT, "_made_parts", lambda: {"strip": ["L_cheek_Ribbon", "R_cheek_Ribbon"]}):
    a.refresh_selection(); app.processEvents()
    check("a part that's made: 'Made: L_cheek_Ribbon, R_cheek_Ribbon' and a tick on its step",
          "Made: L_cheek_Ribbon" in strip_light._label() and [c for c in fp.cards if c.title == "Facial strips"][0]
          .num.text() == "✓")
    check("...the face map: strips green (made)", a.face_map.states["strip"] == "made")
got = {}
with mock.patch.object(FK, "facial", lambda edges, *a, **k: got.update(edges=edges, curves=k.get("curves"))), \
        mock.patch.object(FK, "group", lambda head=None: "face_kit_grp"):
    [b for b in [c for c in fp.cards if c.title == "Facial strips"][0].findChildren(QtWidgets.QPushButton)
     if b.text().startswith("Make strip")][0].click()
check("Make strip (Two curves): the tool's own Make, from the two selected curves", got.get("curves") is True)
f.go(("face", "Ribbons & groups")); app.processEvents()
check("Ribbons & groups: Face ribbons, Group controls - no face map", [c.title for c in fp.cards if c.isVisibleTo(a)]
      == ["Face ribbons", "Group controls (mouth)"] and not a.face_card.isVisibleTo(a))

# --- 5. Ribbon as steps
f.go(("ribbon", "Make a ribbon")); app.processEvents()
rp = a.pages["ribbon"]
check("Ribbon's own pages: Make a ribbon · Builds in the scene",
      [b.text() for b in f.tabs2.findChildren(QtWidgets.QPushButton)] == ["Make a ribbon", "Builds in the scene"])
check("...the steps strip on top: Surface, Joints, Controls, Create", a.strip.isVisibleTo(a) and
      [t for _b, t in a.strip.items] == ["Surface", "Joints", "Controls", "Create"])
cmds.getAttr = (lambda real: lambda plug, *x, **k: 8 if plug.endswith(".spans") else real(plug, *x, **k))(cmds.getAttr)
cmds.select(cheek_a, cheek_b_rev)
RT._last_preview["key"] = None
a.refresh_selection(); app.processEvents()
l1 = rp.fields[RT.N("L1")]
check("Surface: two curves selected, one drawn the other way - the light says so (Loft fixes it on copies)",
      "runs the other way" in l1._label() and l1.level == "warn")
cmds.select(cheek_a, cheek_b); RT._last_preview["key"] = None; a.refresh_selection(); app.processEvents()
check("...the same way, 8 spans each: ready (a yellow dot on Surface, on the strip too)",
      l1.level == "ready" and [c for c in rp.cards if c.title == "Surface"][0].num.text() == "●" and
      a.strip.states[0] == "ready")
inner = [c.title for c in a.findChildren(widgets.Card) if c.property("inner") == "true" and c.isVisibleTo(a)]
check("Surface: Two curves (check, fix, loft) first and open; Make a plane, Edge to curve folded under it",
      inner[:4] == ["Two curves: check, fix, loft", "Loft options", "Make a plane", "Edge to curve"])
more = [c for c in a.findChildren(widgets.Card) if c.title.startswith("More:")]
names = [b.text() for b in more[0].findChildren(QtWidgets.QPushButton)] if more else []
check("Create and mirror: the rarer buttons under More (every one kept)", more and more[0].closed and
      "Replace the surface (new surface, then the ribbon)" in names and
      "Switch to constraints (joints copying their controls)" in names and
      "Organize existing builds (one _ribbon_grp each)" in names)
f.go(("ribbon", "Builds in the scene")); app.processEvents()
check("Builds in the scene: its own page (no steps strip)", [c.title for c in rp.cards if c.isVisibleTo(a)] ==
      ["Builds in the scene"] and not a.strip.isVisibleTo(a))
print("%d/%d passed" % (sum(ok), len(ok)))
