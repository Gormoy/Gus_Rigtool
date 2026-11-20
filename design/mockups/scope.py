exec(open("v2pages.py").read().split("PAGES = []")[0])
CSS3 = CSS + """
.new{position:relative}.badge{position:absolute;top:-10px;right:-8px;background:#ff5fa2;color:#111;font-weight:800;font-size:12px;border-radius:12px;padding:2px 9px;z-index:3;box-shadow:0 2px 6px #0008}
.sug{background:linear-gradient(90deg,color-mix(in srgb,var(--a) 30%,#24272b),#24272b);border:1px dashed var(--a);border-radius:8px;padding:8px 10px;display:flex;align-items:center;gap:10px}
.sug b.go2{margin-left:auto;background:var(--a);color:#111;border-radius:6px;padding:5px 10px}
.pin{color:#ffcf5c}.open{border:2px solid var(--a);border-radius:9px;padding:8px;margin-top:6px;background:#2a2d32}
.lbl{font-size:13px;color:#cfd2d6;margin:6px 0 4px}
.plan{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;margin:8px 0 20px}
.plan div{background:#2b2e33;border-radius:9px;padding:10px;border-top:4px solid var(--c)}.plan small{color:#a2a7ae;display:block}
.rec{display:grid;grid-template-columns:auto 1fr auto;gap:6px 14px;background:#2b2e33;border-radius:10px;padding:12px 16px;max-width:1300px;margin-bottom:20px;align-items:center}
.rec .y{color:#8fe07f;font-weight:700}.rec .l{color:#f1d36a;font-weight:700}.rec .n{color:#a2a7ae}
"""
def badge(n): return '<span class="badge">%s</span>' % n
def wrap(n, h): return '<div class="new">%s%s</div>' % (badge(n), h)

# 1. module settings under the tile
mod_settings = ('<div class="open"><div class="lbl"><b>L_arm</b> settings (opens under the tile you click)</div>' +
                F(("Twist joints", seg(["3", "5", "7"], 1)), ("Kind", seg(["FK", "IK", "IK / FK"], 2)), ("Stretch", seg(["Off", "On"], 1))) + "</div>")
A = W("build", ["Modules", "World & visibility", "Settings", "Face", "Ribbon", "Joints"], "Modules", sel(J("L_clavicle_guide"), "→ <b>L_arm</b>"), [
    card(2, "Modules in the scene (click one)", tiles([("spine", "C_spine", "✓ built", "#5fbf4f", False), ("arm", "L_arm", "✓ built", "#5fbf4f", True),
        ("arm", "R_arm", "✓ built", "#5fbf4f", False), ("leg", "L_leg", "✓ built", "#5fbf4f", False)]) + wrap("1", mod_settings))],
    "Rebuild L_arm<small>its settings changed</small>")

# 2. next step suggestion
def sugg(text, where, btn_): return '<div class="sug"><span style="color:var(--a);flex:none">%s</span><div><b>Next:</b> %s<div class="tip">%s</div></div><b class="go2">%s</b></div>' % (icon("bulb", 26), text, where, btn_)
B = W("controls", ["Make", "Edit shape", "Behaviour", "Attributes", "Channels", "Spaces", "Follow", "Stick"], "Make",
      sel(J("L_arm") + J("L_elbow") + J("L_wrist"), "a chain"), [
    wrap("2", sugg("make an FK chain of controls on these 3 joints", "you're on the right page - the big button does it", "Show me")),
    card(1, "Pick a shape", '<div class="tip">(the shape list, as before)</div>'),
    card(2, "Size and place", closed=True, peek="auto · facing X · in front 0")],
    "Make 3 controls (Circle)<small>an FK chain · one undo</small>")
B2 = '<div style="--a:#d8638c;width:640px">' + wrap("2", sugg("<b>Hare_Body</b> and <b>97 joints</b> selected: bind the skin", "Skin › Bind — one click takes you there", "Go to Skin › Bind")) + "</div>"

# 3. pinned card
look = ('<div class="card" style="border-left-color:#ffcf5c;background:#3d3a30"><h3><i style="background:#ffcf5c">' + icon("pin", 13, "#111", 2.2) + '</i>Look <span class="pin" style="display:inline-flex;gap:4px;align-items:center">' + icon("pin", 16, "#ffcf5c") + ' pinned</span>'
        '<span class="q">unpin</span></h3>' + F(("Colour", " ".join('<span class="sw" style="background:%s"></span>' % c for c in ["#e2504a", "#4c8fe0", "#f0c85a", "#5fbf4f", "#b26be0", "#ffffff"])),
        ("Line width", inp("2.0"))) + '<div class="tip">Pinned: it stays on top of every Controls page</div></div>')
Cw = W("controls", ["Make", "Edit shape", "Behaviour", "Attributes", "Channels", "Spaces", "Follow", "Stick"], "Behaviour", sel(C("L_wrist_IK_ctrl"), ""), [
    wrap("3", look), card(1, "Limits", F(("Channel", seg(["Translate", "Rotate", "Scale"], 1)), ("Min / max", inp("-45") + " " + inp("90")))),
    card(2, "In front of the mesh", closed=True), card(3, "Stop at the body", closed=True)], "Limit rotate<small>on 1 control</small>")

# 4. Maya's Skin Tools
D = W("skin", ["Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle", "Fixes"], "Weights", sel(M("Hare_Body · 12 vertices"), ""), [
    wrap("4", card(1, "Paint weights", btn(icon("brush", 16) + " Open Maya's Skin Tools (layers)") + note("Only shows on a Maya that has them. On Maya 2024: Maya's Paint Skin Weights, as today."))),
    card(2, "Vertex weights", F(("Joint", inp("L_elbow_jnt", 150)), ("Value", inp("0.75") + ' <span class="btn">Set</span>')))], None)

# 5. one look: bar + arcs window
bar = ('<div style="background:#2b2e33;border-radius:10px;padding:6px;display:flex;gap:4px;align-items:center;box-shadow:0 6px 20px #0008;border-top:3px solid #6f93bd">' +
       "".join('<span style="width:34px;height:34px;border-radius:7px;background:%s;display:grid;place-items:center;color:#111;font-weight:700">%s</span>' % (c, t)
               for c, t in (("#e3bd3c", "K"), ("#36b38a", "⇋"), ("#36b38a", "↺"), ("#9b74dc", "IK"), ("#d8638c", "◠"), ("#e0893a", "⚓"), ("#6f93bd", "▶"))) +
       '<span style="color:#a2a7ae;padding:0 6px">≡</span></div>')
arcs = ('<div class="win" style="width:300px;--a:#d8638c"><div class="main"><div class="head"><div class="t"><div class="bigic">◠</div><h2>Arcs</h2></div>'
        '<div class="why">The trail of the selected controls.</div><div class="subt"><span class="on">Show</span><span>Editing</span><span>Style</span></div></div>'
        '<div class="content"><div class="sel">%s</div>%s<div class="go">Show the arc<small>frames 1-42</small></div></div></div></div>' % (C("L_hand_ctrl"), card(1, "Range", F(("Frames", inp("1") + " to " + inp("42"))))))
E = '<div style="display:flex;flex-direction:column;gap:14px">%s<div style="display:flex;gap:14px">%s</div></div>' % (bar, arcs)

# old window switch
F_ = W("toolbox", ["Select", "Groups", "Mirror", "Rename", "Pivots", "Settings"], "Settings", sel("", "Gus_Rigtool 5.7.0"), [
    card(1, "Window", '<div class="f"><label>Use</label><div>%s</div></div>' % seg(["The new window", "The old window (5.6)"]) +
         note("The old window stays until every area of the new one has passed your tests. Switch any time - your options carry over.")),
    card(2, "Update", closed=True), card(3, "Defaults", closed=True)], None)

rec = ('<div class="rec">'
       '<span class="y">YES · 5.7</span><span><b>1 · Settings under the tile</b> — one click from the module to its settings; nothing to hunt for.</span><span class="n">small</span>'
       '<span class="y">YES · 5.7</span><span><b>2 · Next step</b> — what a beginner needs most; it only suggests, never does anything by itself.</span><span class="n">medium</span>'
       '<span class="y">YES · 5.7</span><span><b>3 · Pin a card</b> — your most-used card on top of every page of that area.</span><span class="n">small</span>'
       '<span class="l">LATER</span><span><b>4 · Maya\'s Skin Tools</b> — a link only, on a Maya that has them; your Maya 2024 keeps today\'s painting.</span><span class="n">tiny</span>'
       '<span class="l">5.8</span><span><b>5 · One look everywhere</b> — the Animtool, the bar, Arcs, Attach: after the Rigtool window is proven (animators use them mid-shot).</span><span class="n">large</span>'
       '</div>')
plan = '<div class="plan">' + "".join('<div style="--c:%s"><b>%s</b><small>%s</small></div>' % r for r in (
    ("#cfd2d6", "5.7.0", "the frame: sidebar, search, colours, Selected box, next step, pin, old-window switch + Controls area"),
    ("#d8638c", "5.7.1", "Skin"), ("#e0893a", "5.7.2", "Build (tiles + settings under them), Face, Ribbon, Joints"),
    ("#9b74dc", "5.7.3", "Connect"), ("#e3bd3c", "5.7.4", "Check & publish"), ("#6f93bd", "5.7.5", "Toolbox — then the old window can go"),
    ("#ff5fa2", "5.8", "one look for the Animtool, bar, Arcs, Attach, onion skin"))) + "</div>"

out = '<!doctype html><html><head><meta charset="utf-8"><title>Rigtool 5.7 Scope</title><style>%s</style></head><body>' % CSS3
out += '<div class="blk"><h1>5.7: the scope, in pictures</h1><p class="sub">The pink numbers are the five ideas. My recommendation as a rigger and designer:</p>%s<div class="cap">The order of the releases (each one: your preview OK → build → your tests)</div>%s</div>' % (rec, plan)
out += '<div class="blk"><div class="row"><div><div class="cap">1 · Build › Modules: click a tile, its settings open right under it</div>%s</div><div><div class="cap">2 · The next step: Controls › Make with a chain selected</div>%s<div style="height:14px"></div><div class="cap">2 · …and on another page it takes you where to go</div>%s</div></div></div>' % (A, B, B2)
out += '<div class="blk"><div class="row"><div><div class="cap">3 · A pinned card: "Look" stays on top of every Controls page</div>%s</div><div><div class="cap">4 · Skin › Weights: Maya\'s Skin Tools, only where Maya has them</div>%s</div></div></div>' % (Cw, D)
out += '<div class="blk"><div class="row"><div><div class="cap">5 · (5.8) one look: the Animtool bar and the Arcs window in the same style</div>%s</div><div><div class="cap">Safety: Toolbox › Settings › use the old window, any time</div>%s</div></div></div>' % (E, F_)
open("scope.html", "w").write(out + "</body></html>")
