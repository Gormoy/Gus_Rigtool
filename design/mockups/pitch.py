exec(open("anim_mock.py").read().split("# --- A. Pose")[0])
P_ = COL
def slide(title, sub, body): return '<div class="blk slide"><div class="kick">GUS ANIMTOOL · 5.8 PROPOSAL</div><h1>%s</h1><p class="sub">%s</p>%s</div>' % (title, sub, body)

# ---------------- S1: today vs proposed
today = ('<div class="win" style="width:430px;background:#3c3c3c;border-radius:4px"><div style="background:#2b2b2b;padding:6px 8px;color:#ddd;font-weight:700;font-size:13px">Gus Animtool 5.7.1</div>'
         '<div style="display:flex;flex-wrap:wrap;gap:2px;padding:4px;background:#333">' + "".join('<span style="width:22px;height:22px;background:#555;border-radius:2px"></span>' for _ in range(24)) + '</div>'
         '<div style="background:#2f5a35;color:#ddd;font-size:12px;padding:4px 8px">Select controls, then click. Every action is one undo.</div>'
         '<div style="display:flex;gap:2px;padding:4px 4px 0;font-size:12px;color:#ccc">' + "".join('<span style="background:%s;padding:3px 8px">%s</span>' % ("#4a4a4a" if t == "Keys" else "#333", t) for t in ("Pick", "Pose", "Keys", "Space", "Limbs", "Settings")) + '</div>'
         '<div style="padding:4px">' + "".join('<div style="background:#4a4a4a;color:#ddd;font-size:12px;padding:5px 8px;margin:2px 0">▸ %s</div>' % t for t in (
             "Nudge", "Copy / paste keys", "Inbetweens", "Offset", "Keys", "Tangents", "Retime", "Bake / reduce", "Curves", "Graph Editor keys  (push / pull / negate)", "Rotate order")) +
         '<div style="color:#888;font-size:11px;padding:4px">11 sections in one tab · 24 unlabelled icons · names only</div></div></div>')
probs = ('<div class="lst">' + "".join('<div><b>%s</b>%s</div>' % x for x in (
    ("Hard to find.", " 57 tools in 6 tabs; the Keys tab alone has 11 sections. An animator learns where things are by memory, not by sight."),
    ("Icons without words.", " The 24 toolbar icons are small and unlabelled; several look alike (Mirror / Flip, the tangents)."),
    ("No feedback.", " Nothing says what is selected, which frame or key you're between, or what a button will do before you press it."),
    ("Hidden power.", " Many options live in right-click menus (scope, amounts, 'both hands') - great once known, invisible to a new animator."),
    ("It crops.", " Docked narrow next to the Channel Box (where animators keep it), rows are cut off."))) + '</div>')
S1 = slide("Today vs. the proposal", "Sincerely: today's Animtool is powerful and fast for someone who knows it. It is not easy for someone who doesn't - and a studio has many of those.",
           '<div class="row"><div><div class="cap">Today (Keys tab, what an animator sees)</div>%s</div><div style="max-width:440px"><div class="cap">What gets in the way</div>%s</div></div>' % (today, probs))

# ---------------- S2: principles + borrowed ideas
def pcard(n, t, d, c="#4fb3d9"): return '<div class="pc" style="--c:%s"><b>%s</b><h4>%s</h4><p>%s</p></div>' % (c, n, t, d)
principles = '<div class="grid3">' + "".join(pcard(*x) for x in (
    ("1", "One place per job", "Five areas in the order you animate: Pick & see → Pose → Keys & timing → Spaces & props → Limbs. Each has its colour.", P_["pick"]),
    ("2", "Always know the context", "Character, frame range, what's selected and where you are between keys - always on top.", P_["pose"]),
    ("3", "See it before you press it", "Every button says what it will do ('Key the pose at frame 14'); pictures show what a tool changes.", P_["keys"]),
    ("4", "The power stays one click away", "Right-click options become visible choices on the card (scope, amounts) - the right-click still works.", P_["space"]),
    ("5", "Your bar, your way", "Profiles (Blocking, Polish...), drag, add, remove, row / column / grid.", P_["limbs"]),
    ("6", "Nothing lost, nothing cut", "All 57 tools, the same actions and hotkeys; a test checks every one and every width.", "#8a9098"))) + '</div>'
borrowed = '<div class="grid2">' + "".join('<div class="bw"><span class="dept">%s</span><b>%s</b><p>%s</p></div>' % x for x in (
    ("Editorial (NLE timelines)", "Timing shown as a timeline", "Inbetweens, offsets and retimes show the keys moving on a little timeline - the way editors see a cut ripple."),
    ("Compositing (node colours)", "Colour = family", "Like nodes coloured by type, every tool keeps its area's colour - on the window, the bar, the menus."),
    ("Game engines (context panels)", "Show what fits the selection", "Like a details panel that changes with what you pick: arm controls selected → the arm's tools first (IK/FK, mirror)."),
    ("Music software (transport bar)", "The shot strip", "A strip that never moves: character, frames, play range, Picker / Poses / Clips - like a DAW's transport."),
    ("Layout / previs", "Shot information", "The shot's name and range from the scene file on the strip, so a playblast or a bake can't use the wrong range."),
    ("Pose libraries with thumbnails", "Pictures, not names", "Poses and clips as thumbnails (the pose library already saves pictures) - bigger, searchable, in the Pose area."),
    ("3D apps' radial menus", "A pie on a hotkey (variant)", "Optional: hold a key, the bar's profile opens around the cursor - the same tools, no reach to the bar."),
    ("Accessibility (UI standards)", "Colour is never the only cue", "Each area also has a number and a shape; a high-contrast variant for long days and colour-blind animators."))) + '</div>'
S2 = slide("The principles - and what we borrow from other departments", "No new tools. Better ways to show and reach the 57 we have, taken from places where they already work.",
           '<div class="cap">Six principles</div>%s<div class="cap" style="margin-top:18px">Borrowed (presentation only - nothing new to learn twice)</div>%s' % (principles, borrowed))

# ---------------- S3: more pages
picker_pic = ('<div class="pic" style="display:block"><svg viewBox="0 0 220 120" style="width:100%;height:120px"><circle cx="110" cy="18" r="12" fill="none" stroke="#4fb3d9" stroke-width="2"/>'
              '<rect x="96" y="34" width="28" height="40" rx="6" fill="none" stroke="#4fb3d9" stroke-width="2"/>'
              + "".join('<circle cx="%d" cy="%d" r="6" fill="%s"/>' % (x, y, c) for x, y, c in ((110, 18, "#f0c85a"), (110, 46, "#f0c85a"), (110, 66, "#f0c85a"), (80, 44, "#4c8fe0"), (66, 62, "#4c8fe0"), (140, 44, "#e2504a"), (154, 62, "#e2504a"), (100, 96, "#4c8fe0"), (120, 96, "#e2504a"))) +
              '<rect x="60" y="56" width="14" height="14" rx="3" fill="none" stroke="#fff" stroke-width="2"/></svg><div class="tip">The picker as a small preview: click a dot to select; the white square = selected. Open the full picker from here.</div></div>')
hider = '<div style="display:flex;gap:6px;flex-wrap:wrap">' + "".join('<span class="btn" style="%s">%s</span>' % ("opacity:.5;text-decoration:line-through" if off else "", n) for n, off in (("Body", False), ("Face", False), ("Hands", False), ("Tail", True), ("Ears", False), ("Props", True))) + '</div>'
PICK = awin("pick", ["Picker", "Select", "Sets", "Body parts", "View", "Playblast"], "Picker", sel(C_("L_hand_ctrl"), "1 of 97"), [
    card(1, "Picker", picker_pic + btn("Open the picker", "Edit")), card(2, "Body parts (show / hide)", hider + note("Click: hide / show. Crossed out = hidden.")),
    card(3, "Selection sets", closed=True, peek="mouth · L hand · tail")], None, width=520)
spaces = ('<div class="pic" style="display:block"><div style="display:flex;gap:6px;flex-wrap:wrap">' + "".join('<span class="btn" style="%s">%s</span>' % ("background:#9b74dc;color:#111;font-weight:700" if n == "Chest" else "", n) for n in ("World", "COG", "Chest", "Head")) +
          '</div><div class="tip" style="margin-top:6px">Now: <b>Chest</b>. Click another: it switches with <b>no jump</b> (and keys it, if Key on switch is on).</div></div>')
attach_tl = ('<div class="pic" style="display:block"><svg viewBox="0 0 300 40" style="width:100%;height:40px"><rect x="10" y="14" width="80" height="12" fill="#555"/><rect x="90" y="14" width="110" height="12" fill="#9b74dc"/><rect x="200" y="14" width="90" height="12" fill="#c7a6ff"/>'
             '<text x="95" y="10" fill="#c7a6ff" font-size="9">L hand</text><text x="205" y="10" fill="#c7a6ff" font-size="9">both hands</text></svg><div class="tip">The same coloured stretches you see on the Time Slider: who holds the box, when.</div></div>')
SPACE = awin("space", ["Space switch", "Temporary spaces", "Attach props"], "Space switch", sel(C_("L_wrist_IK_ctrl"), "space: Chest"), [
    card(1, "Space switch (no jump)", spaces), card(2, "Attach: who holds it", attach_tl + btn("Attach", "Release", "Hand-over...")),
    card(3, "Clean-up", closed=True, peek="find keyed jumps · fix")], None, width=520)
ikfk = ('<div class="pic"><svg viewBox="0 0 120 70"><circle cx="15" cy="15" r="5" fill="#36b38a"/><circle cx="55" cy="40" r="5" fill="#36b38a"/><circle cx="100" cy="25" r="5" fill="#36b38a"/><path d="M15 15L55 40L100 25" stroke="#36b38a" stroke-width="3" fill="none"/>'
        '<rect x="92" y="17" width="16" height="16" fill="none" stroke="#fff" stroke-width="2"/><circle cx="55" cy="62" r="4" fill="none" stroke="#fff" stroke-width="2"/></svg><div class="n">Now <b>IK</b> (the hand leads, the elbow points at the pole). Switch: FK - <b>no jump</b>.</div></div>')
LIMB = awin("limbs", ["IK / FK", "Overlap", "Jiggle", "Teach a limb"], "IK / FK", sel(C_("L_hand_ik_ctrl"), "left arm"), [
    card(1, "IK / FK", ikfk + F(("Switch", seg(["This frame", "Over the range"]))) + chk("Key on switch")),
    card(2, "Overlap (follow-through)", closed=True, peek="tail · ears · softer / stiffer")], "Switch the left arm to FK<small>no jump · one undo</small>", width=520)
SET = awin("toolbox", ["Rig profile", "Hotkeys", "The bar", "Backup", "Update"], "The bar", '<span class="then">Settings: the bar, your rig, hotkeys, backups</span>', [
    card(1, "The bar", F(("Profile", seg(["Blocking", "Polish", "All tools"])), ("Shape", seg(["Row", "Column", "Grid"])), ("Size", seg(["S", "M", "L"], 1)), ("Labels", seg(["Off", "On"])))),
    card(2, "Rig profile (this rig, every scene)", closed=True, peek="suffix _ctrl · L_ / R_ · control set")], None, width=520)
S3 = slide("More pages", "Each page the same way: what's selected, a picture that shows the tool, the choices visible, one big button that says what happens.",
           '<div class="row"><div><div class="cap">Pick & see › Picker</div>%s</div><div><div class="cap">Spaces & props › Space switch</div>%s</div></div>'
           '<div class="row" style="margin-top:20px"><div><div class="cap">Limbs › IK / FK</div>%s</div><div><div class="cap">⚙ Settings › The bar</div>%s</div></div>' % (PICK, SPACE, LIMB, SET))

# ---------------- S4: style variants
mirror_card = card(2, "Mirror · Flip · Reset", '<div class="pic"><svg viewBox="0 0 120 70"><circle cx="35" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M35 18v22 M35 40l-8 18 M35 40l8 18 M35 24l-14 -8" stroke="currentColor" stroke-width="2.5" fill="none"/><path d="M35 24l12 8" stroke="#4c8fe0" stroke-width="3"/><path d="M60 35h10 M66 31l4 4-4 4" stroke="currentColor" stroke-width="2" fill="none"/><circle cx="92" cy="12" r="6" fill="none" stroke="currentColor" stroke-width="2"/><path d="M92 18v22 M92 40l-8 18 M92 40l8 18 M92 24l14 -8" stroke="currentColor" stroke-width="2.5" fill="none"/><path d="M92 24l-12 8" stroke="#e2504a" stroke-width="3"/></svg><div class="n">The right side takes the left side\'s pose.</div></div>' + btn("Mirror L → R", "Mirror R → L", "Flip", "Reset"))
def variant(cls, name, why):
    return '<div><div class="cap">%s</div><div class="vt %s" style="--a:%s;width:400px">%s<div class="go">Mirror L → R<small>2 controls</small></div></div><div class="tip" style="width:400px;margin-top:6px">%s</div></div>' % (name, cls, P_["pose"], mirror_card, why)
S4 = slide("Style variants (the same card, four ways)", "One design, four looks you could switch in Settings. My recommendation: Studio as the default, Compact for experienced animators, High contrast available to everyone.",
           '<div class="row">%s%s</div><div class="row" style="margin-top:20px">%s%s</div>' % (
               variant("", "A · Studio (the default)", "Roomy, pictures on, colour per area. Best for learning and for most of the day."),
               variant("compact", "B · Compact (experienced animators)", "Smaller, denser, pictures folded into the '?' - more tools on screen when docked narrow."),
               variant("hc", "C · High contrast (accessible)", "Bigger text, white on black, every area marked by its number and pattern too - not only colour."),
               variant("maya", "D · Maya-native", "Maya's own greys and blue highlight: it looks like part of Maya, for studios that want no visual change.")))

# ---------------- S5: bar variants
def tl2(c, t, lab=None, big=False):
    s = 44 if big else 34
    return '<span style="display:inline-flex;flex-direction:column;align-items:center;gap:2px"><span style="width:%dpx;height:%dpx;border-radius:8px;background:%s;display:grid;place-items:center;color:#111;font-weight:800;font-size:12px">%s</span>%s</span>' % (s, s, c, t, '<span style="font-size:10px;color:#a2a7ae">%s</span>' % lab if lab else "")
T = [(P_["pose"], "Tw", "Tween"), (P_["pose"], "Mi", "Mirror"), (P_["keys"], "Ke", "Key"), (P_["keys"], "St", "Stepped"), (P_["keys"], "+I", "Inbetween"), (P_["space"], "At", "Attach")]
barbox = lambda inner, top=P_["pose"]: '<div style="display:inline-flex;gap:6px;align-items:center;background:#2b2e33;border-radius:10px;padding:8px 10px;border-top:3px solid %s;box-shadow:0 8px 24px #0009;flex-wrap:wrap">%s</div>' % (top, inner)
v1 = barbox('<span style="color:#7d838b">⋮⋮</span>' + "".join(tl2(c, t, lab) for c, t, lab in T) + '<span style="color:#a2a7ae">✎ ≡</span>')
v2 = barbox('<span style="color:#7d838b">⋮⋮</span>' + "".join(tl2(c, t) for c, t, _l in T) + '<span style="color:#a2a7ae">≡</span>')
v3 = '<div style="display:inline-grid;grid-template-columns:repeat(2,34px);gap:4px;background:#2b2e33;border-radius:10px;padding:8px;border-top:3px solid %s">%s</div>' % (P_["keys"], "".join(tl2(c, t) for c, t, _l in T))
pie = ('<svg viewBox="0 0 220 220" width="220" height="220"><circle cx="110" cy="110" r="100" fill="#2b2e33cc" stroke="#4a4f57"/><circle cx="110" cy="110" r="26" fill="#1d1f22" stroke="#4a4f57"/><text x="110" y="114" fill="#a2a7ae" font-size="11" text-anchor="middle">Blocking</text>'
       + "".join('<g><rect x="%d" y="%d" width="36" height="36" rx="8" fill="%s"/><text x="%d" y="%d" font-size="12" font-weight="800" text-anchor="middle" fill="#111">%s</text></g>' % (110 + 68 * __import__("math").cos(a) - 18, 110 + 68 * __import__("math").sin(a) - 18, c, 110 + 68 * __import__("math").cos(a), 110 + 68 * __import__("math").sin(a) + 4, t)
                 for a, (c, t, _l) in zip([i * 2 * 3.14159 / 6 - 1.5708 for i in range(6)], T)) + '</svg>')
hud = ('<div style="width:520px;height:150px;background:linear-gradient(#5b6b7c,#3a4550);border-radius:8px;position:relative;overflow:hidden">'
       '<div style="position:absolute;top:8px;left:50%;transform:translateX(-50%);display:flex;gap:4px;background:#1d1f22cc;border-radius:8px;padding:4px 6px">' + "".join(tl2(c, t) for c, t, _l in T[:5]) + '</div>'
       '<div style="position:absolute;bottom:10px;left:12px;color:#ddd;font-size:12px">the viewport</div></div>')
dock = ('<div style="display:flex;gap:0"><div style="width:44px;background:#2b2e33;border-radius:8px 0 0 8px;padding:6px;display:flex;flex-direction:column;gap:4px;border-left:3px solid %s">%s</div>'
        '<div style="width:170px;background:#444;border-radius:0 8px 8px 0;color:#ccc;font-size:12px;padding:8px">Channel Box<div style="color:#999;margin-top:6px">translateX 0.0<br>translateY 0.0<br>rotateZ 12.4</div></div></div>' % (P_["keys"], "".join(tl2(c, t) for c, t, _l in T)))
S5 = slide("The bar: six ways to keep it", "The same profile shown different ways; each profile remembers its own shape and size (you said yes).",
           '<div class="row" style="align-items:flex-start"><div><div class="cap">1 · Row with labels (learning)</div>%s<div style="height:16px"></div><div class="cap">2 · Compact row (daily)</div>%s<div style="height:16px"></div><div class="cap">3 · Grid (2 wide)</div>%s</div>'
           '<div><div class="cap">4 · Pie on a hotkey (variant)</div>%s<div class="tip" style="width:220px">Hold the key, move toward a tool, let go. The same profile; no reach.</div></div>'
           '<div><div class="cap">5 · On the viewport (HUD)</div>%s<div style="height:16px"></div><div class="cap">6 · Docked beside the Channel Box</div>%s</div></div>' % (v1, v2, v3, pie, hud, dock))

# ---------------- S6: honest risks + plan
risks = '<div class="lst">' + "".join('<div><b>%s</b> %s <span class="fix">→ %s</span></div>' % x for x in (
    ("Muscle memory.", "Animators who know today's tabs will look in the old places.", "the search finds any tool; the old window stays one click away until every area is done; hotkeys don't change."),
    ("Space.", "Pictures and cards take room; animators dock narrow.", "Compact variant, pictures fold into '?', the sidebar shrinks to icons; the bar is where daily work happens."),
    ("The next-step lamp can nag.", "Useful for new people, noise for experts.", "it only suggests, never acts; a switch in Settings turns it off."),
    ("Colour-blind users.", "Areas told apart by colour alone would fail them.", "numbers and shapes on every area; the High-contrast variant."),
    ("Speed in heavy shots.", "A Qt window that follows the selection costs a little on every click.", "only the visible page updates; measured in Test this release (the Rigtool window opens in 0.25 s on your Mac)."),
    ("Pie menu / HUD are new ways in.", "They are not new tools, but they are new things to learn and to maintain.", "variants, off by default; build them only if you want them."),
    ("Maintenance.", "Pictures per tool are more to keep up to date.", "the pages are drawn from the tools' own code (as in the Rigtool); a test checks every tool is there."),
    ("Honest unknown.", "Maya 2025 (PySide6) behaves a bit differently from 2024.", "both are supported; your Test this release runs on 2024 - a 2025 run would be wise before a studio rollout."))) + '</div>'
plan = '<div class="plan">' + "".join('<div style="--c:%s"><b>%s</b><small>%s</small></div>' % x for x in (
    ("#8a9098", "5.8.0", "the frame: shot strip, sidebar, colours, search, next step; Pose area"), (P_["keys"], "5.8.1", "Keys & timing"), (P_["pick"], "5.8.2", "Pick & see"),
    (P_["space"], "5.8.3", "Spaces & props"), (P_["limbs"], "5.8.4", "Limbs + Settings"), ("#6f93bd", "5.8.5", "the bar: profiles, edit, shapes (+ variants you choose)"))) + '</div>'
measure = '<div class="lst">' + "".join('<div><b>%s</b> %s</div>' % x for x in (
    ("Clicks to a tool:", "today 2-4 (tab, section, sometimes a right-click) → 1 with the bar or search, 2 in the window."),
    ("Time to find a tool for a new animator:", "test it: give 10 tasks to someone new, time it on the old and the new window."),
    ("Nothing lost:", "57 of 57 tools, every option, every hotkey - checked by a test, like the Rigtool's 332 controls."))) + '</div>'
S6 = slide("Honest: what could go wrong, and how we handle it", "A pitch that hides the flaws doesn't survive the first week in production.",
           '<div class="row" style="align-items:flex-start"><div style="max-width:760px"><div class="cap">Risks</div>%s</div><div style="max-width:420px"><div class="cap">How we\'d know it works</div>%s</div></div>'
           '<div class="cap" style="margin-top:16px">Rollout (each step: your preview OK → build → your tests; the old window until the end)</div>%s' % (risks, measure, plan))

CSSX = CSS + """
.slide{background:#16181b;border-radius:14px;padding:26px 28px;margin-bottom:26px}.kick{color:#f1c769;font-size:11px;letter-spacing:.14em;font-weight:700}
.slide h1{font-size:26px;margin:6px 0}.lst div{background:#24272b;border-radius:8px;padding:9px 12px;margin:6px 0;font-size:13.5px;line-height:1.5}.lst .fix{color:#8fe07f}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.pc{background:#24272b;border-radius:10px;padding:12px 14px;border-top:4px solid var(--c)}.pc b{background:var(--c);color:#111;border-radius:50%;width:24px;height:24px;display:inline-grid;place-items:center}
.pc h4{margin:8px 0 4px;font-size:15px}.pc p{margin:0;color:#a2a7ae;font-size:13px}
.bw{background:#24272b;border-radius:10px;padding:10px 14px}.bw .dept{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#f1c769;display:block}.bw b{font-size:14.5px}.bw p{margin:3px 0 0;color:#a2a7ae;font-size:13px}
.plan{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:8px 0}.plan div{background:#24272b;border-radius:9px;padding:10px;border-top:4px solid var(--c)}.plan small{color:#a2a7ae;display:block}
.vt{background:var(--panel, #33373d);border-radius:10px;padding:12px}
.vt.compact .card{padding:6px 9px}.vt.compact .card h3{font-size:12.5px;margin-bottom:4px}.vt.compact .pic{display:none}.vt.compact .btn{padding:3px 8px;font-size:12px}.vt.compact .go{padding:6px;font-size:13px}
.vt.hc{background:#000}.vt.hc .card{background:#0b0b0b;border:2px solid #fff;border-left:8px solid var(--a)}.vt.hc .card h3{font-size:17px;color:#fff}.vt.hc .btn{background:#fff;color:#000;font-weight:700;font-size:15px}.vt.hc .pic{background:#111;border:1px solid #888}.vt.hc .n{color:#fff;font-size:14px}.vt.hc .go{border:3px solid #fff;font-size:17px;background-image:repeating-linear-gradient(45deg,transparent 0 8px,#0002 8px 16px)}
.vt.maya{background:#444;border-radius:2px}.vt.maya .card{background:#5d5d5d;border-radius:2px;border-left:none}.vt.maya .card h3 i{background:#5285a6}.vt.maya .btn{background:#5d5d5d;border:1px solid #2b2b2b;border-radius:2px}.vt.maya .pic{background:#3a3a3a;border-radius:2px}.vt.maya .go{background:#5285a6;color:#fff;border-radius:2px;box-shadow:none}
"""
open("pitch.html", "w").write('<!doctype html><html><head><meta charset="utf-8"><title>Animtool Pitch</title><style>%s</style></head><body>%s%s%s%s%s%s</body></html>' % (CSSX, S1, S2, S3, S4, S5, S6))
