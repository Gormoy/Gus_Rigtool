exec(open("v2pages.py").read().split("PAGES = []")[0])
# the Animtool's own areas: the animator's order
AREAS[:] = [("pick", "Pick & see", "#4fb3d9", "◉"), ("pose", "Pose", "#d8638c", "◐"), ("keys", "Keys & timing", "#e3a33c", "◆"),
            ("space", "Spaces & props", "#9b74dc", "⇄"), ("limbs", "Limbs", "#36b38a", "⟋"), ("toolbox", "Settings", "#8a9098", "⚙")]
COL.clear(); COL.update({k: c for k, _n, c, _i in AREAS})
WHY = {"pick": "Find and select controls; what you see in the viewport.", "pose": "Shape the pose: in-betweens, mirror, reset, copy.",
       "keys": "Keys and timing: nudge, inbetweens, offsets, tangents, curves.", "space": "Switch spaces with no jump; props in hands.",
       "limbs": "IK / FK, overlap, jiggle.", "toolbox": "Your rig's naming, hotkeys, the bar, backups, update."}
def side(on, slim=False):
    out = '<div class="side%s">' % (" slim" if slim else "")
    if not slim: out += '<div class="sec">Your shot</div>'
    for i, (k, n, c, ic) in enumerate(AREAS):
        if k == "toolbox":
            out += '<div style="margin-top:auto"></div>'
        num = str(i + 1) if k != "toolbox" else "⚙"
        out += '<div class="nav%s" style="%s"><b style="background:%s">%s</b>%s</div>' % (" on" if k == on else "", "border-left-color:%s" % c if k == on else "", c, num, "" if slim else n)
    return out + "</div>"
def charbar():
    return ('<div style="display:flex;gap:8px;align-items:center;padding:8px;background:#24272b;border-bottom:1px solid #000;flex-wrap:wrap">'
            '<span class="chip" style="background:#ffffff14;color:#e9ebee;padding:4px 10px">Hare ▾</span>'
            '<span class="chip" style="background:#ffffff10;color:#cfd2d6">Frames <b style="margin:0 4px">1 – 42</b></span>'
            '<span class="btn">Time slider</span><span style="margin-left:auto" class="btn">Picker</span><span class="btn">Poses</span><span class="btn">Clips</span></div>')
def awin(area, subs, on, s, cards, go, width=660, slim=False, why=None):
    a = COL[area]; ic = [x for x in AREAS if x[0] == area][0][3]; n = [x for x in AREAS if x[0] == area][0][1]
    return ('<div class="win" style="width:%dpx;--a:%s"><div class="top"><div class="search">Search any tool...</div></div>%s<div class="body">%s'
            '<div class="main"><div class="head"><div class="t"><div class="bigic">%s</div><h2>%s</h2></div><div class="why">%s</div>'
            '<div class="subt">%s</div></div><div class="content"><div class="sel">%s</div>%s%s</div></div></div></div>'
            % (width, a, charbar(), side(area, slim), ic, n, why or WHY[area], "".join('<span class="%s">%s</span>' % ("on" if x == on else "", x) for x in subs),
               s, "".join(cards), '<div class="go">%s</div>' % go if go else ""))
def nxt(text, where, b): return '<div class="sug" style="background:color-mix(in srgb,var(--a) 25%%,#24272b);border:1px dashed var(--a);border-radius:8px;padding:8px 10px;display:flex;gap:10px;align-items:center">%s<div><b>Next:</b> %s<div class="tip">%s</div></div><b style="margin-left:auto;background:var(--a);color:#111;border-radius:6px;padding:5px 10px">%s</b></div>' % (icon("bulb", 24, "currentColor"), text, where, b)
C_ = lambda n: chip("ctrl", n)

# --- A. Pose
tween = ('<div class="pic" style="display:block"><div style="display:flex;justify-content:space-between;font-size:12px;color:#a2a7ae"><span>◀ the previous key (fr 10)</span><span>half way</span><span>the next key (fr 20) ▶</span></div>'
         '<div style="position:relative;height:30px;margin:6px 4px"><div style="position:absolute;top:13px;left:0;right:0;height:4px;background:#4a4f57;border-radius:2px"></div>'
         '<div style="position:absolute;top:13px;left:50%;width:22%;height:4px;background:var(--a)"></div><div style="position:absolute;left:72%;top:4px;width:22px;height:22px;border-radius:50%;background:var(--a);border:3px solid #fff3"></div></div>'
         '<div style="display:flex;gap:6px;flex-wrap:wrap">' + "".join('<span class="btn">%s</span>' % x for x in ("-100", "-50", "-25", "0", "25", "50", "100")) + '</div>'
         '<div class="tip" style="margin-top:6px">Drag it: the pose between the keys around this frame. Release: one key, one undo.</div></div>')
figure = ('<div class="pic"><svg viewBox="0 0 120 70"><circle cx="35" cy="12" r="6" fill="none" stroke="#e9ebee" stroke-width="2"/><path d="M35 18v22 M35 40l-8 18 M35 40l8 18 M35 24l-14 -8" stroke="#e9ebee" stroke-width="2.5" fill="none"/><path d="M35 24l12 8" stroke="#4c8fe0" stroke-width="3"/>'
          '<path d="M60 35h10 M66 31l4 4-4 4" stroke="#a2a7ae" stroke-width="2" fill="none"/><circle cx="92" cy="12" r="6" fill="none" stroke="#e9ebee" stroke-width="2"/><path d="M92 18v22 M92 40l-8 18 M92 40l8 18 M92 24l14 -8" stroke="#e9ebee" stroke-width="2.5" fill="none"/><path d="M92 24l-12 8" stroke="#e2504a" stroke-width="3"/></svg>'
          '<div class="n">Mirror: the right side takes the left side\'s pose. Flip: both swap. Reset: back to rest.</div></div>')
A = awin("pose", ["Tween", "Mirror & reset", "Copy pose", "Pose library", "Mirror animation", "Cycles"], "Tween", sel(C_("L_arm_ik_ctrl") + C_("L_hand_ctrl"), "frame 14, between keys 10 and 20"), [
    nxt("left arm controls: give the right arm the same pose", "Pose > Mirror & reset", "Go to Mirror"),
    card(1, "Tween (between the keys)", tween),
    card(2, "Mirror · Flip · Reset", figure + btn("Mirror L → R", "Mirror R → L", "Flip", "Reset selected", "Reset character")),
    card(3, "Copy / paste pose", closed=True, peek="copy · paste · paste mirrored")], "Key the pose at frame 14<small>keeps the curves · one undo</small>")

# --- B. Keys & timing
tl = ('<div class="pic" style="display:block"><svg viewBox="0 0 300 54" style="width:100%;height:54px"><line x1="10" y1="20" x2="290" y2="20" stroke="#4a4f57" stroke-width="2"/>'
      + "".join('<rect x="%d" y="13" width="9" height="14" rx="2" fill="%s"/>' % (x, "#e3a33c" if x > 120 else "#cfd2d6") for x in (20, 70, 120, 170, 220, 270)) +
      '<line x1="128" y1="6" x2="128" y2="34" stroke="#e2504a" stroke-width="2"/><text x="132" y="10" fill="#e2504a" font-size="9">this frame</text>'
      + "".join('<path d="M%d 42 h14 M%d 38 l4 4 -4 4" stroke="#e3a33c" stroke-width="1.6" fill="none"/>' % (x, x + 10) for x in (168, 218, 268)) +
      '</svg><div class="tip">Add inbetween: every key after this frame one frame later (more time). Remove: one earlier.</div></div>')
tang = '<div style="display:flex;gap:6px;flex-wrap:wrap">' + "".join(
    '<span class="btn" style="flex-direction:column;padding:6px 10px"><svg viewBox="0 0 40 20" width="40" height="20"><path d="%s" stroke="currentColor" stroke-width="2" fill="none"/></svg>%s</span>' % (d, n)
    for n, d in (("Auto", "M2 18 C12 18 14 2 20 2 S28 18 38 18"), ("Spline", "M2 18 C10 2 30 2 38 18"), ("Linear", "M2 18 L20 2 L38 18"),
                 ("Flat", "M2 18 C12 18 12 2 20 2 C28 2 28 18 38 18"), ("Stepped", "M2 18 H20 V2 H38"))) + "</div>"
B = awin("keys", ["Nudge & inbetweens", "Offset", "Tangents", "Retime", "Bake / reduce", "Curves"], "Nudge & inbetweens", sel(C_("Hare: 97 controls"), "every key after frame 14"), [
    card(1, "Inbetweens (more / less time)", tl + btn("+ Add inbetween", "− Remove inbetween") + F(("Step", seg(["1", "2", "4"])), ("On", seg(["The selection", "The character", "Everything"], 1)))),
    card(2, "Nudge", btn("◀ One earlier", "One later ▶"), closed=True, peek="selected keys · step 1"),
    card(3, "Tangents", tang)], None)

# --- C. the bar: normal, profiles, edit
def tile(c, t, x=False, add=False):
    if add:
        return '<span style="width:38px;height:38px;border-radius:8px;border:2px dashed #6f93bd;display:grid;place-items:center;color:#6f93bd;font-size:22px">+</span>'
    return '<span style="position:relative;width:38px;height:38px;border-radius:8px;background:%s;display:grid;place-items:center;color:#111;font-weight:800;font-size:12px">%s%s</span>' % (c, t, '<b style="position:absolute;top:-6px;right:-6px;width:16px;height:16px;border-radius:50%;background:#e2504a;color:#fff;font-size:11px;display:grid;place-items:center">×</b>' if x else "")
grp = lambda name, c, items, x=False: '<div style="display:flex;flex-direction:column;gap:3px"><div style="font-size:9.5px;color:%s;letter-spacing:.06em;text-transform:uppercase">%s</div><div style="display:flex;gap:4px">%s</div></div>' % (c, name, "".join(tile(c, t, x) for t in items))
POSE, KEYS, SPACE, PICK, LIMB = COL["pose"], COL["keys"], COL["space"], COL["pick"], COL["limbs"]
bar_normal = ('<div style="display:inline-flex;gap:10px;align-items:flex-end;background:#2b2e33;border-radius:10px;padding:8px 10px;border-top:3px solid #d8638c;box-shadow:0 8px 24px #0009">'
              '<span style="color:#7d838b">⋮⋮</span><span class="chip" style="background:#ffffff14;color:#e9ebee">Blocking ▾</span>'
              + grp("Pose", POSE, ["Tw", "Mi", "Re"]) + grp("Keys", KEYS, ["Ke", "St", "+I", "−I"]) + grp("Space", SPACE, ["At", "Re"]) +
              '<span style="color:#a2a7ae;font-size:18px">✎</span><span style="color:#a2a7ae;font-size:18px">≡</span></div>')
bar_edit = ('<div style="display:inline-flex;gap:10px;align-items:flex-end;background:#2b2e33;border-radius:10px;padding:10px 12px;border:2px dashed #6f93bd">'
            + grp("Pose", POSE, ["Tw", "Mi", "Re"], True) + grp("Keys", KEYS, ["Ke", "St", "+I", "−I"], True) + grp("Space", SPACE, ["At", "Re"], True) + tile("", "", add=True) +
            '<span style="color:#6f93bd;font-size:12px;align-self:center;margin-left:6px">drag a square to move it ·<br>drag the corner ◢ to resize</span><span style="align-self:flex-end;color:#6f93bd">◢</span></div>')
bar_grid = ('<div style="display:inline-grid;grid-template-columns:repeat(3,38px);gap:4px;background:#2b2e33;border-radius:10px;padding:8px;border-top:3px solid #36b38a;box-shadow:0 8px 24px #0009">'
            + "".join(tile(c, t) for c, t in ((LIMB, "IK"), (LIMB, "Ov"), (LIMB, "Ji"), (POSE, "Mi"), (POSE, "Fl"), (POSE, "Re"), (KEYS, "Ke"), (KEYS, "Bk"), (PICK, "Ar"))) + '</div>')
palette = ('<div class="win" style="width:420px;--a:#6f93bd"><div class="main"><div class="head" style="padding-bottom:10px"><div class="t"><div class="bigic">+</div><h2>Add to the bar</h2></div>'
           '<div class="why">Tick what you want on it; drag to place it. Grouped by where they live in the Animtool.</div></div><div class="content">'
           '<div class="search">Search tools...</div>'
           + "".join('<div class="card" style="--a:%s"><h3><i>%s</i>%s<span class="peek" style="margin-left:6px;color:#7d838b;font-weight:400;font-size:12px">%s</span></h3>%s</div>' % (
               c, i + 1, n, "add the whole group" if True else "", "".join('<div class="chk"><b class="%s"></b>%s</div>' % ("y" if on else "", t) for t, on in items))
               for i, (n, c, items) in enumerate([("Pose", POSE, [("Tween slider", True), ("Mirror", True), ("Flip", False), ("Reset", True), ("IK / FK", False)]),
                                                 ("Keys & timing", KEYS, [("Key", True), ("Stepped", True), ("Add inbetween", True), ("Remove inbetween", True), ("Offset − / +", False)]),
                                                 ("Spaces & props", SPACE, [("Attach", True), ("Release", True), ("World space", False)])])) +
           '<div class="go">Done<small>the Blocking profile: 9 tools</small></div></div></div></div>')
profiles = ('<div class="win" style="width:260px"><div class="content" style="padding:10px">'
            '<div class="gl">Profiles</div>'
            + "".join('<div class="nav%s" style="display:flex;gap:8px;align-items:center;padding:6px 8px;border-radius:6px%s">%s<span style="margin-left:auto;color:#7d838b;font-size:12px">%s</span></div>' % (
                " on" if n == "Blocking" else "", ";background:#ffffff12" if n == "Blocking" else "", n, k) for n, k in (
                ("All tools", "57"), ("Blocking", "9 · mine"), ("Polish", "12 · mine"), ("Pose", "group"), ("Keys & timing", "group"), ("Spaces & props", "group"), ("Limbs", "group")))
            + '<div style="border-top:1px solid #4a4f57;margin:8px 0"></div><div class="nav">+ New profile (copy this one)</div><div class="nav">Rename · Delete</div>'
            '<div class="nav">Labels: off · Size: M · A row / column / grid</div></div></div>')

# --- D. narrow
D = awin("pose", ["Tween", "Mirror & reset", "More ▾"], "Mirror & reset", C_("L_arm_ik_ctrl"), [card(1, "Mirror · Flip · Reset", figure + btn("Mirror L → R", "Mirror R → L", "Flip", "Reset"))], "Mirror L → R<small>1 control</small>", width=360, slim=True)

out = '<!doctype html><html><head><meta charset="utf-8"><title>Animtool Look</title><style>%s .sug b.go2{}</style></head><body>' % CSS
out += '<div class="blk"><h1>Gus Animtool, the new look (mock-up · nothing built)</h1><p class="sub">The same principles as the Rigtool: a sidebar in the order an animator works (Pick, Pose, Keys, Spaces, Limbs; Settings its own button), a colour per area, the character and frame range always on top, cards with pictures that show what a tool does, the next step, nothing cut off. Every tool of today stays (57); none are lost.</p>'
out += '<div class="row"><div><div class="cap">A · Pose › Tween (2 arm controls, between keys)</div>%s</div><div><div class="cap">B · Keys & timing › Inbetweens (a timeline picture)</div>%s</div></div></div>' % (A, B)
out += ('<div class="blk"><h1 style="margin-top:20px">The bar: yours to build</h1><p class="sub">Profiles: <b>All tools</b>, one per area (<b>Pose</b>, <b>Keys & timing</b>...), and your own (<b>Blocking</b>, <b>Polish</b>). '
        'Edit (✎): drag squares to move them, × to take one off, + to add, drag the corner to make it longer, a column or a grid. Groups keep their colour, so you see where each tool lives.</p>'
        '<div class="row" style="align-items:flex-start"><div><div class="cap">C1 · The bar (your Blocking profile)</div>%s<div style="height:18px"></div><div class="cap">C2 · ✎ Edit: move, take off (×), add (+), resize (◢)</div>%s'
        '<div style="height:18px"></div><div class="cap">C3 · Another profile as a 3-wide grid (Limbs work)</div>%s</div>'
        '<div><div class="cap">C4 · + Add to the bar (grouped, ticks)</div>%s</div><div><div class="cap">C5 · The profile menu</div>%s</div></div></div>') % (bar_normal, bar_edit, bar_grid, palette, profiles)
out += '<div class="blk"><div class="row"><div><div class="cap">D · Docked narrow: icons only, nothing cut</div>%s</div></div></div>' % D
out += "</body></html>"
open("anim_mock.html", "w").write(out)
