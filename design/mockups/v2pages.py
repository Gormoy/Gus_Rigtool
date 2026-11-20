exec(open("v2.py").read().split("CT_SUBS =")[0])
exec(open("icons.py").read())
def F(*rows):
    return '<div class="f">' + "".join('<label>%s</label><div>%s</div>' % r for r in rows) + "</div>"
def inp(v, w=None): return '<span class="inp"%s>%s</span>' % (' style="min-width:%dpx"' % w if w else "", v)
def btn(*bs): return '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">' + "".join('<span class="btn">%s</span>' % b for b in bs) + "</div>"
def pick(v): return inp(v, 150) + ' <span class="btn">Use selected</span>'
def tiles(items):
    return '<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(96px,1fr))">' + "".join(
        '<div class="sh%s" style="font-size:12px;color:#e9ebee"><div style="color:var(--a);height:30px">%s</div>%s<div style="color:%s;font-size:11px">%s</div></div>'
        % (" on" if on else "", icon(ic), n, c, st) for ic, n, st, c, on in items) + "</div>"
def tags(*t): return " ".join('<span class="chip %s">%s</span>' % (k, n) for k, n in t)
def note(t): return '<div class="tip" style="margin-top:6px">%s</div>' % t
def steps(*t):
    return '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">' + " → ".join(
        '<span class="chip" style="%s">%d · %s</span>' % ("background:var(--a);color:#111;font-weight:600" if i == 0 else "", i + 1, x) for i, x in enumerate(t)) + "</div>"
J = lambda n: chip("joint", n); C = lambda n: chip("ctrl", n); M = lambda n: chip("mesh", n)
def sel(chips, then): return '<span class="lab">Selected</span>%s<span class="then">%s</span>' % (chips, then)

AREA_INFO = {"build": ("Build", "Modules, face, ribbons and joints: the rig's skeleton and parts."),
             "skin": ("Skin", "Bind meshes and fix the weights."), "controls": ("Controls", "Make controls and shape them."),
             "connect": ("Connect", "Constraints, connections, nodes and driven keys."),
             "check": ("Check & publish", "Find problems, tidy up and hand the rig over."),
             "toolbox": ("Toolbox", "Small tools for any moment.")}
def W(area, subs, on, s, cards, go):
    t, why = AREA_INFO[area]
    return window(area, t, why, subs, on, s, cards, go)

PAGES = []
def add(area, cap, html_): PAGES.append((area, cap, html_))
BS = ["Modules", "World & visibility", "Settings", "Face", "Ribbon", "Joints"]
add("build", "Build › Modules", W("build", BS, "Modules", sel(J("L_clavicle_guide"), "→ <b>the picked module: L_arm</b>"), [
    card(1, "Start: a template or one module", F(("Template", seg(["Biped", "Quadruped", "Empty"]))) + btn("Add a module ▾")),
    card(2, "Modules in the scene (click one to pick it)", tiles([("spine", "C_spine", "✓ built", "#5fbf4f", False), ("arm", "L_arm", "✓ built", "#5fbf4f", True),
        ("arm", "R_arm", "✓ built", "#5fbf4f", False), ("leg", "L_leg", "✓ built", "#5fbf4f", False), ("tail", "tail", "○ guides", "#e3bd3c", False), ("ears", "ears", "○ guides", "#e3bd3c", False)])),
    card(3, "Guides", btn("Show guides", "Mirror guides L → R", "Back to guides")),
    card(4, "Settings of the picked module", closed=True, peek="L_arm: twist joints 5 · IK/FK · stretch"),
    card(5, "Keep when rebuilding · Custom steps · Naming", closed=True, peek="your edits survive a rebuild")],
    "Build 2 modules not built yet<small>tail, ears · one undo</small>"))
add("build", "Build › World & visibility", W("build", BS, "World & visibility", sel("", "the whole rig"), [
    card(1, "World controls", F(("Levels", seg(["1", "2", "3"], 1)), ("Size", inp("auto"))) + chk("Turn the world (root) with the COG")),
    card(2, "Visibility switches", chk("Body controls") + chk("Face controls") + chk("Clothes: a Full / Hidden switch per piece") + chk("Joints (for the rigger)", False)),
    card(3, "IK / FK switch", chk("No jump when switching (matching)")),
    card(4, "Animator tools (Gus Animtool)", btn("Open Gus Animtool", "Make animator tools..."))], "Make the world controls (2 levels)<small>and the visibility switches</small>"))
add("build", "Build › Face (its own sub-pages)", W("build", ["Setup", "Eyes", "Eyelids", "Mouth", "Brows", "Strips", "More ▾"], "Mouth",
    sel(M("Hare_Body · 24 edges"), "→ <b>the lip loops</b>"), [
    card(1, "Mouth", F(("Upper lip", pick("12 edges")), ("Lower lip", pick("12 edges")), ("Controls", seg(["5", "7", "9"]))) + chk("Corners follow the jaw") +
         '<div class="pic"><svg viewBox="0 0 120 70"><path d="M15 35 Q60 10 105 35" stroke="#e0893a" stroke-width="3" fill="none"/><path d="M15 35 Q60 60 105 35" stroke="#e0893a" stroke-width="3" fill="none"/>'
         + "".join('<circle cx="%d" cy="%d" r="4" fill="#36b38a"/>' % (x, y) for x, y in ((15, 35), (37, 25), (60, 22), (83, 25), (105, 35), (37, 45), (60, 48), (83, 45))) +
         '</svg><div class="n">5 controls on each lip; the corners are shared.</div></div>'),
    card(2, "Group controls (mouth)", closed=True, peek="the whole mouth · the corners · upper / lower lip")],
    "Make the mouth (5 controls per lip)<small>one undo</small>"))
add("build", "Build › Ribbon", W("build", ["Make", "Builds in the scene"], "Make", sel('<span class="chip">Cape_srf</span>', "a NURBS surface, 1 × 8 spans"), [
    card(1, "Surface", F(("Surface", pick("Cape_srf")), ("Along", seg(["U", "V"])))),
    card(2, "Joints and controls", F(("Joints", inp("8")), ("Controls", inp("4")), ("In front", inp("0.5") + " " + seg(["+X", "-X", "+Y", "-Y", "+Z", "-Z"], 2, True)))
         + chk("Evenly spaced") + chk("Pivot on the controls (face)", False)),
    card(3, "Build and mirror", chk("Mirror to the other side") + chk("Not symmetric (keep this side only)", False))],
    "Create the ribbon<small>8 joints, 4 controls</small>"))
add("build", "Build › Joints", W("build", ["Chain", "At the centre"], "Chain", sel('<span class="chip">Tail_crv</span>', "a curve, 14 units long"), [
    card(1, "Placement", F(("Joints", inp("10")), ("Spacing", seg(["Even", "By CVs"])))),
    card(2, "Orientation", F(("Aim", seg(["X", "Y", "Z"], 0, True)), ("Up", seg(["X", "Y", "Z", "World"], 1, True)))),
    card(3, "Naming", F(("Name", inp("tail_##_jnt", 150))) + note("tail_01_jnt · tail_02_jnt · … tail_10_jnt")),
    card(4, "IK spline", closed=True, peek="a spline IK with controls on the curve")], "Create 10 joints<small>along Tail_crv</small>"))

SS = ["Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle", "Fixes"]
add("skin", "Skin › Copy & mirror", W("skin", SS, "Copy & mirror", sel(M("Hare_Body") + M("Hare_Shirt"), "→ <b>from Hare_Body to Hare_Shirt</b>"), [
    card(1, "Copy skin", F(("Match by", seg(["Closest point", "UVs", "Same mesh"]))) + chk("Use the same joints")),
    card(2, "Mirror weights", F(("Across", seg(["X", "Y", "Z"], 0, True)), ("Direction", seg(["L → R", "R → L"])))),
    card(3, "Joints labelled?", closed=True, peek="mirroring by label is safer")], "Copy the skin to Hare_Shirt<small>closest point · one undo</small>"))
add("skin", "Skin › Weights", W("skin", SS, "Weights", sel(M("Hare_Body · 12 vertices"), ""), [
    card(1, "Vertex weights", F(("Joint", inp("L_elbow_jnt", 150)), ("Value", inp("0.75") + ' <span class="btn">Set</span> <span class="btn">+0.1</span> <span class="btn">−0.1</span>'))),
    card(2, "Weight list (the selected vertices)", '<div class="pic" style="display:block">' + "".join(
        '<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><span style="width:110px;color:#f0c85a">%s</span><span style="flex:1;height:10px;background:#1b1d20;border-radius:5px"><span style="display:block;height:10px;width:%d%%;background:#d8638c;border-radius:5px"></span></span><span>%.2f</span></div>' % (n, v * 100, v)
        for n, v in (("L_elbow_jnt", .62), ("L_shoulder_jnt", .28), ("L_forearm_jnt", .10))) + "</div>"),
    card(3, "Clean", closed=True, peek="small weights · max influences · unused joints")], None))
add("skin", "Skin › Cloth & jiggle", W("skin", SS, "Cloth & jiggle", sel(M("Shirt"), "skinned, 22 joints"), [
    card(1, "Cloth: three steps", steps("Skin like the body", "Its own joints", "Blend") + btn("1 · Skin like the body")),
    card(2, "Jiggle and wave", F(("Kind", seg(["Jiggle", "Wave"])), ("Amount", inp("0.5")))) ], "Skin Shirt like the body<small>step 1 of 3</small>"))
add("skin", "Skin › Fixes", W("skin", SS, "Fixes", sel(J("L_elbow_jnt (bent 90°)") + M("Hare_Body"), ""), [
    card(1, "Sculpt a fix", steps("Pose the joint", "Sculpt", "Done") + note("It turns on by itself as the joint bends.")),
    card(2, "Fixes on the mesh", tags(("joint", "L_elbow 90°"), ("joint", "R_elbow 90°")) + btn("Mirror", "Delete"))], "Sculpt a fix<small>L_elbow at 90°</small>"))

CS = ["Make", "Edit shape", "Behaviour", "Attributes", "Channels", "Spaces", "Follow", "Stick"]
add("controls", "Controls › Edit shape › On the body (new in 5.6.48)", W("controls", CS, "Edit shape", sel(C("L_wrist_ctrl") + M("Hare_Body"), "→ <b>shape it on Hare_Body</b>"), [
    card(1, "On the body", F(("Gap", inp("20") + " % off the skin")) + btn("◎ Fit to the body", "⌇ Lie on the skin", "⬭ Shape from edges") +
         '<div class="pic"><svg viewBox="0 0 120 70"><rect x="35" y="15" width="50" height="40" rx="18" fill="#3b4048" stroke="#9ec3f0"/><rect x="27" y="8" width="66" height="54" rx="26" fill="none" stroke="#36b38a" stroke-width="2.5"/></svg><div class="n">Fit: the ring wraps the wrist, 20% off the skin.</div></div>'),
    card(2, "Move, size, turn", closed=True, peek="in front · size · stretch · turn 90° · handles"), card(3, "Look", closed=True, peek="colour · line width · by side"),
    card(4, "Copy and mirror", closed=True, peek="1st → others · L → R · save as My shape")], None))
add("controls", "Controls › Behaviour", W("controls", CS, "Behaviour", sel(C("L_wrist_IK_ctrl"), ""), [
    card(1, "Limits", F(("Channel", seg(["Translate", "Rotate", "Scale"], 1)), ("Axis", seg(["X", "Y", "Z"], 2, True)), ("Min / max", inp("-45") + " " + inp("90")))),
    card(2, "In front of the mesh", chk("Always drawn on top (face controls skipped)")),
    card(3, "Stop at the body", closed=True, peek="the control can't go into the mesh"), card(4, "Rest here", closed=True, peek="keep the pose, zero the controls"),
    card(5, "Not a control", closed=True, peek="remove the control role")], "Limit rotate Z: −45 to 90<small>on 1 control</small>"))
add("controls", "Controls › Attributes", W("controls", CS, "Attributes", sel(C("L_wrist_settings_ctrl"), "14 attributes"), [
    card(1, "Add / edit", F(("Name", inp("finger_curl", 140)), ("Kind", seg(["Number", "On / off", "Choice", "Separator"])), ("Min / max", inp("-10") + " " + inp("10")))),
    card(2, "Order (drag)", '<div class="pic" style="display:block">' + "".join('<div style="padding:3px 6px;border-bottom:1px solid #3a3e45">⋮⋮ %s</div>' % a for a in ("ikfk", "stretch", "soft_ik", "spread", "thumb_curl")) + "</div>"),
    card(3, "Copy to other controls", closed=True)], "Add finger_curl<small>to 1 control</small>"))
add("controls", "Controls › Channels", W("controls", CS, "Channels", sel(C("12 controls"), ""), [
    card(1, "Lock and hide", '<div class="pic" style="display:block"><table style="border-spacing:10px 4px">' +
         "<tr><td></td>" + "".join('<td style="color:%s;font-weight:700">%s</td>' % (AX[a], a) for a in "XYZ") + "</tr>" +
         "".join("<tr><td>%s</td>%s</tr>" % (n, "".join('<td><b class="chkb" style="display:inline-block;width:15px;height:15px;border-radius:4px;%s"></b></td>' % ("background:#36b38a" if v else "border:1.5px solid #8a9098") for v in vals))
                 for n, vals in (("Translate", (0, 0, 0)), ("Rotate", (0, 0, 0)), ("Scale", (1, 1, 1)))) + "</table></div>" + chk("Visibility")),
    card(2, "Default set", closed=True), card(3, "Copy / check", closed=True)], "Lock + hide scale, visibility<small>on 12 controls</small>"))
add("controls", "Controls › Spaces", W("controls", CS, "Spaces", sel(C("L_wrist_IK_ctrl"), "no space switch yet"), [
    card(1, "Follows", tags(("ctrl", "COG"), ("ctrl", "Chest"), ("ctrl", "root")) + btn("Add selected", "Remove") + F(("Follows", seg(["Position + rotation", "Rotation only"])))),
    card(2, "This control's switch", closed=True, peek="the attribute and its menu")], "Make the space switch<small>3 spaces</small>"))
add("controls", "Controls › Follow & Stick", W("controls", CS, "Follow", sel(C("3 lip controls") + C("Jaw_ctrl"), "→ <b>the lips follow the jaw</b>"), [
    card(1, "Add follow", F(("How much", inp("0.5"))) + chk("Fade along the lip (corners less)")),
    card(2, "Weights", closed=True), card(3, "Follows in the scene", closed=True)], "The lips follow Jaw_ctrl<small>3 controls</small>"))

NS = ["Constraints", "Connect", "Nodes", "Driven keys"]
add("connect", "Connect › Constraints", W("connect", NS, "Constraints", sel(C("Prop_ctrl") + '<span class="chip">Axe_grp</span>', "→ <b>Axe_grp follows Prop_ctrl</b>"), [
    card(1, "Make", F(("Kind", seg(["Parent", "Point", "Orient", "Scale", "Aim"]))) + chk("Keep the offset")),
    card(2, "Swap target", closed=True), card(3, "Check / remove", closed=True)], "Constrain Axe_grp to Prop_ctrl<small>parent · keep offset</small>"))
add("connect", "Connect › Connect", W("connect", NS, "Connect", sel(C("Settings_ctrl") + '<span class="chip">2 nodes</span>', ""), [
    card(1, "Connect", F(("From", inp("Settings_ctrl.ikfk", 150)), ("To", inp(".blender", 150)), ("× factor", inp("1.0")))),
    card(2, "By name pattern", closed=True, peek="L_* → R_*"), card(3, "Break / check", closed=True)], "Connect to 2 nodes"))
add("connect", "Connect › Nodes", W("connect", ["Find", "Make", "Library", "Clean up"], "Find", sel('<span class="chip">L_arm_ik_blend</span>', "part of a 12-node setup"), [
    card(1, "Select the setup", btn("Select the whole setup", "Show in the Node Editor")),
    card(2, "Trace a channel", F(("Channel", inp("L_arm_jnt.rotateZ", 150))) + steps("L_arm_ik_blend", "L_arm_jnt.rotateZ") + btn("Trace")),
    card(3, "Find problems", closed=True, peek="unconnected · cycles · unused")], None))
add("connect", "Connect › Driven keys", W("connect", NS, "Driven keys", sel(C("L_fingers_ctrl.curl") + J("12 joints"), ""), [
    card(1, "Driver", F(("Driver", pick("L_fingers_ctrl.curl")))),
    card(2, "Driven keys", '<div class="pic" style="display:block">' + "".join('<div style="display:flex;gap:10px;margin:2px 0"><b style="width:40px">%s</b><span>%s</span></div>' % r for r in (("0", "rest"), ("5", "half curl"), ("10", "full curl"))) + "</div>"),
    card(3, "Copy · Flip · Nodes ↔ driven keys", closed=True)], "Apply to 12 joints"))

KS = ["Checker", "Check this scene", "Publish", "Organize"]
add("check", "Check › Checker", W("check", KS, "Checker", sel("", "the whole rig"), [
    card(1, "Result", '<div style="display:flex;gap:8px;flex-wrap:wrap"><span class="chip" style="background:#5fbf4f33;color:#8fe07f">● 41 ok</span><span class="chip" style="background:#e3bd3c33;color:#f1d36a">● 3 warnings</span><span class="chip" style="background:#e2504a33;color:#ff8a84">● 0 problems</span></div>' + note("Warnings: 2 controls not zeroed · 1 joint not labelled") + btn("Go there", "Repair")),
    card(2, "Checks to run", closed=True, peek="34 of 36"), card(3, "Batch (many files)", closed=True)], "Check the rig<small>about 6 s</small>"))
add("check", "Check › Publish (its only home)", W("check", KS, "Publish", sel("", "Ready: 3 warnings, none blocking"), [
    card(1, "Publish (a clean rig for animators)", chk("Save the default pose and the mirror table") + chk("Lock and protect the rig's nodes", False) + chk("Hide the guides and helpers", False)),
    card(2, "Deliver", closed=True, peek="zip the rig + Gus Animtool")], "Publish the rig<small>Unpublish brings it back</small>"))
add("check", "Check › Organize", W("check", KS, "Organize", sel("", "the Outliner: 214 top-level items"), [
    card(1, "Analyze", note("What's where, and what doesn't belong.")), card(2, "The plan", note("Moves shown before anything moves.")),
    card(3, "Rules", closed=True), card(4, "Extras (off by default)", closed=True)], "Analyze the Outliner"))

TS = ["Select", "Groups", "Mirror", "Rename", "Pivots", "Settings"]
add("toolbox", "Toolbox › Select", W("toolbox", TS, "Select", sel('<span class="chip">HARE_RIG</span>', "a group"), [
    card(1, "Select inside", btn(*[icon(i, 16) + " " + n for i, n in (("arm", "Joints"), ("rig", "Controls"), ("head", "Meshes"), ("spine", "Groups"))])), card(2, "Related", btn("Its twin", "Its skin", "Its control")),
    card(3, "Filters", closed=True), card(4, "Quick sets and recent", closed=True)], None))
add("toolbox", "Toolbox › Mirror", W("toolbox", TS, "Mirror", sel(C("L_arm_ctrl") + C("+4"), "left side"), [
    card(1, "Mirror", F(("What", seg(["Shapes", "Controls", "Joints", "Geometry"])), ("Across", seg(["X", "Y", "Z"], 0, True)))),
    card(2, "Pose and twins", closed=True), card(3, "Links · attrs · pivots", closed=True)], "Mirror 5 controls L → R"))
add("toolbox", "Toolbox › Rename", W("toolbox", TS, "Rename", sel(J("8 joints"), ""), [
    card(1, "Names", F(("Name", inp("tail_##", 140)), ("Start", inp("1")), ("Side", seg(["Keep", "L_", "R_", "C_"])))),
    card(2, "Preview", '<div class="pic" style="display:block;font-size:12.5px">' + "".join('<div><s style="color:#7d838b">joint%d</s> → <b>tail_%02d_jnt</b></div>' % (i, i) for i in (1, 2, 3)) + "<div>…</div></div>")],
    "Rename 8 joints"))
add("toolbox", "Toolbox › Settings", W("toolbox", TS, "Settings", sel("", "Gus_Rigtool 5.7.0 · Gus Animtool 5.7.0"), [
    card(1, "Update", btn("Update from a zip...", "What's new")), card(2, "Defaults", note("Every option of every tool, and your defaults.")),
    card(3, "Side colours (their only home)", '<span class="sw" style="background:#4c8fe0"></span> L &nbsp; <span class="sw" style="background:#e2504a"></span> R &nbsp; <span class="sw" style="background:#f0c85a"></span> centre'),
    card(4, "Shelf shortcuts", closed=True), card(5, "Self-test", closed=True)], None))

CSS2 = CSS + ".pages{display:grid;grid-template-columns:repeat(2,640px);gap:24px}.areah{font-size:20px;margin:26px 0 10px;display:flex;align-items:center;gap:10px}.areah b{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;color:#111}"
html2 = '<!doctype html><html><head><meta charset="utf-8"><title>Rigtool 5.7 Pages</title><style>%s</style></head><body>' % CSS2
html2 += '<h1>5.7: every page in the version-2 look (preview; nothing built yet)</h1><p class="sub">Each area keeps its colour on every page. Pictures where they help: module tiles with their state, the lip controls, weight bars, the lock grid in X / Y / Z colours, rename before → after. Publish and Side colours each live in one place only. Every button of today\'s pages stays; closed cards say what\'s inside.</p>'
for area, (n, c) in [(a[0], (a[1], a[2])) for a in AREAS]:
    items = [p for p in PAGES if p[0] == area]
    ic = [x for x in AREAS if x[0] == area][0][3]
    html2 += '<div class="blk"><div class="areah"><b style="background:%s">%s</b>%s</div><div class="pages">%s</div></div>' % (
        c, ic, n, "".join('<div><div class="cap">%s</div>%s</div>' % (cap, h) for _a, cap, h in items))
open("v2pages.html", "w").write(html2 + "</body></html>")
