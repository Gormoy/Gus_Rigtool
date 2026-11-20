# Design language v2: every area has its own colour; Maya's axis colours; pictures, not only words.
AREAS = [("build","Build","#e0893a","⬢"),("skin","Skin","#d8638c","◍"),("controls","Controls","#36b38a","◎"),
         ("connect","Connect","#9b74dc","⟷"),("check","Check & publish","#e3bd3c","✓"),("toolbox","Toolbox","#6f93bd","⚒")]
COL = {k: c for k, _n, c, _i in AREAS}
S = lambda d, w=1.6: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="%s" stroke-linejoin="round" stroke-linecap="round">%s</svg>' % (w, d)
SH = [("Basic",[("Circle",'<circle cx="12" cy="12" r="8"/>'),("Half circle",'<path d="M4 15a8 8 0 0 1 16 0z"/>'),
        ("Square",'<rect x="5" y="5" width="14" height="14"/>'),("Rectangle",'<rect x="3" y="8" width="18" height="8"/>'),
        ("Diamond",'<path d="M12 3l9 9-9 9-9-9z"/>'),("Triangle",'<path d="M12 4l8 15H4z"/>'),
        ("Star",'<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>'),("Plus",'<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>')]),
      ("3D",[("Cube",'<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9"/>'),("Sphere",'<circle cx="12" cy="12" r="8"/><ellipse cx="12" cy="12" rx="8" ry="3"/>')]),
      ("Arrows",[("Arrow",'<path d="M3 12h16 M14 6l6 6-6 6"/>'),("Double arrow",'<path d="M3 12h18 M7 7l-5 5 5 5 M17 7l5 5-5 5"/>'),
        ("Four way arrow",'<path d="M12 2v20 M2 12h20 M9 5l3-3 3 3 M9 19l3 3 3-3 M5 9l-3 3 3 3 M19 9l3 3-3 3"/>'),("Rotate arrow",'<path d="M19 12a7 7 0 1 1-2-5 M19 3v5h-5"/>')]),
      ("Rig",[("Cog",'<circle cx="12" cy="12" r="3.5"/><path d="M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2"/>'),
        ("Pin",'<circle cx="12" cy="6" r="3.5"/><path d="M12 9.5V22"/>'),("Foot",'<path d="M8 3c4 0 6 3 6 8s2 7 2 9-2 2-5 2-4-2-4-5 0-4-1-7 0-7z"/>'),
        ("Eye",'<path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>')])]
ICON = {"joint":'<circle cx="12" cy="12" r="4"/><path d="M12 16l3 6"/>', "ctrl":'<circle cx="12" cy="12" r="7"/>',"mesh":'<path d="M4 8l8-5 8 5v8l-8 5-8-5z M4 8l8 5 8-5 M12 13v8"/>'}
AX = {"X":"#e2504a","Y":"#5fbf4f","Z":"#4c8fe0"}

CSS = """
:root{--bg:#1d1f22;--win:#2b2e33;--panel:#33373d;--card:#3a3e45;--line:#4a4f57;--txt:#e9ebee;--dim:#a2a7ae;--faint:#7d838b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.4 Inter,system-ui,sans-serif;padding:26px}
h1{font-size:22px;margin:0 0 6px}.sub{color:var(--dim);margin:0 0 20px;max-width:1300px}
.row{display:flex;gap:26px;align-items:flex-start;flex-wrap:wrap}.cap{color:#f1c769;font-weight:600;margin:0 0 8px}
.win{background:var(--win);border-radius:8px;box-shadow:0 8px 30px #0008;overflow:hidden;display:flex;flex-direction:column}
.top{display:flex;gap:8px;padding:8px;background:#24272b;border-bottom:1px solid #000}.search{flex:1;background:#1b1d20;border:1px solid var(--line);border-radius:6px;padding:6px 10px;color:var(--faint)}
.body{display:flex;flex:1;min-height:0}
.side{width:178px;background:#26292d;padding:8px;display:flex;flex-direction:column;gap:2px;border-right:1px solid #000}
.side .sec{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin:8px 6px 2px}
.nav{display:flex;align-items:center;gap:9px;padding:6px 7px;border-radius:6px;color:#cfd2d6;border-left:3px solid transparent}
.nav b{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;font-size:12px;color:#111;font-weight:700}
.nav.on{background:#ffffff10;color:#fff;font-weight:600}
.side.slim{width:52px;align-items:center}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.head{padding:12px 14px 0;border-top:4px solid var(--a);background:linear-gradient(180deg,color-mix(in srgb,var(--a) 22%,transparent),transparent 90%)}
.head .t{display:flex;align-items:center;gap:10px}.head .bigic{width:34px;height:34px;border-radius:9px;background:var(--a);color:#111;display:grid;place-items:center;font-size:19px;font-weight:700}
.head h2{margin:0;font-size:19px}.head .why{color:var(--dim);font-size:13px;margin:2px 0 0 44px}
.subt{display:flex;gap:2px;margin-top:10px;flex-wrap:wrap}.subt span{padding:7px 12px;border-radius:7px 7px 0 0;color:var(--dim);font-weight:500}
.subt span.on{background:var(--panel);color:#fff;box-shadow:inset 0 3px 0 var(--a)}
.content{background:var(--panel);padding:12px 14px 14px;display:flex;flex-direction:column;gap:10px;flex:1}
.sel{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:#24272b;border-radius:8px;padding:8px 10px;font-size:13.5px}
.sel .lab{color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.07em}
.chip{display:inline-flex;align-items:center;gap:5px;padding:2px 9px 2px 5px;border-radius:20px;font-size:12.5px;background:#ffffff12}
.chip svg{width:15px;height:15px}.chip.joint{color:#f0c85a}.chip.ctrl{color:#6fd6b0}.chip.mesh{color:#9ec3f0}
.sel .then{color:var(--dim)}.sel .then b{color:#fff}
.card{background:var(--card);border-radius:9px;padding:10px 12px;border-left:3px solid var(--a)}
.card h3{margin:0 0 8px;font-size:14px;display:flex;align-items:center;gap:8px}
.card h3 i{font-style:normal;width:20px;height:20px;border-radius:50%;background:var(--a);color:#111;font-size:12px;display:grid;place-items:center;font-weight:700}
.card h3 .q{margin-left:auto;color:var(--faint);font-weight:400;font-size:12px;border:1px solid var(--line);border-radius:50%;width:18px;height:18px;display:grid;place-items:center}
.card.closed{border-left-color:var(--line);background:#363a40;padding:8px 12px}.card.closed h3{margin:0;color:#cfd2d6}.card.closed h3 i{background:#5a6069}
.card.closed .peek{color:var(--faint);font-size:12px;font-weight:400;margin-left:6px}
.f{display:grid;grid-template-columns:auto 1fr;gap:7px 10px;align-items:center}.f>label{color:var(--dim);text-align:right;font-size:13px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}.seg span{padding:4px 10px;border-right:1px solid var(--line);background:#2e3237}.seg span:last-child{border:0}
.seg span.on{background:var(--a);color:#111;font-weight:600}
.ax span{font-weight:700}.ax span.on{color:#fff}
.inp{background:#202326;border:1px solid var(--line);border-radius:5px;padding:4px 8px;min-width:60px;display:inline-block}
.btn{display:inline-flex;align-items:center;gap:6px;background:#4a4f57;border-radius:6px;padding:5px 11px;font-size:13px}
.btn svg{width:16px;height:16px}
.chk{display:flex;gap:8px;align-items:center;margin-top:6px;font-size:13.5px}.chk b{width:15px;height:15px;border-radius:4px;border:1.5px solid #8a9098}.chk b.y{background:var(--a);border-color:var(--a)}
.go{background:var(--a);color:#111;font-weight:700;text-align:center;border-radius:8px;padding:11px;font-size:15px;box-shadow:0 3px 0 color-mix(in srgb,var(--a) 60%,#000)}
.go small{display:block;font-weight:500;font-size:12px;opacity:.75}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:6px}
.sh{background:#2a2d32;border:1px solid #444a52;border-radius:8px;padding:7px 2px 5px;text-align:center;font-size:11px;color:var(--dim)}
.sh svg{width:30px;height:30px;color:#e9ebee;display:block;margin:0 auto 3px}
.sh.on{border:2px solid var(--a);background:color-mix(in srgb,var(--a) 18%,#2a2d32);color:#fff}.sh.on svg{color:var(--a)}
.gl{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin:6px 0 4px}
.sw{width:22px;height:22px;border-radius:5px;display:inline-block;border:2px solid #0004}
.pic{display:flex;gap:10px;align-items:center;background:#2a2d32;border-radius:8px;padding:8px;margin-top:6px}
.pic svg{width:120px;height:70px;flex:none}.pic .n{color:var(--dim);font-size:12.5px}
.tip{font-size:12.5px;color:var(--dim)}
.legend{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 22px}.legend div{display:flex;align-items:center;gap:7px;background:#2b2e33;border-radius:8px;padding:6px 12px 6px 6px}
.legend b{width:26px;height:26px;border-radius:7px;display:grid;place-items:center;color:#111}
"""

def side(on, slim=False):
    out = '<div class="side%s">' % (" slim" if slim else "")
    if not slim: out += '<div class="nav"><b style="background:#c9ccd1">⌂</b>Home</div><div class="sec">Your rig, in order</div>'
    for i, (k, n, c, ic) in enumerate(AREAS):
        if k == "toolbox" and not slim: out += '<div class="sec">Any time</div>'
        lab = ("" if slim else n)
        num = str(i + 1) if k != "toolbox" else ic
        out += '<div class="nav%s" style="%s"><b style="background:%s">%s</b>%s</div>' % (" on" if k == on else "", "border-left-color:%s" % c if k == on else "", c, num, lab)
    out += '<div class="nav"><b style="background:#c9ccd1">★</b>%s</div>' % ("" if slim else "My tools")
    return out + "</div>"

def chip(kind, name): return '<span class="chip %s">%s%s</span>' % (kind, S(ICON[kind], 1.8), name)
def seg(opts, on=0, ax=False):
    return '<span class="seg%s">%s</span>' % (" ax" if ax else "", "".join(
        '<span class="%s" style="%s">%s</span>' % ("on" if i == on else "", ("color:%s" % AX[o.strip("+-")] if ax and o.strip("+-") in AX and i != on else ("background:%s" % AX[o.strip("+-")] if ax and i == on else "")), o) for i, o in enumerate(opts)))
def card(n, title, body="", closed=False, peek=""):
    if closed: return '<div class="card closed"><h3><i>%s</i>%s<span class="peek">%s</span><span style="margin-left:auto;color:#8d939b">▸</span></h3></div>' % (n, title, peek)
    return '<div class="card"><h3><i>%s</i>%s<span class="q">?</span></h3>%s</div>' % (n, title, body)
def chk(t, y=True): return '<div class="chk"><b class="%s"></b>%s</div>' % ("y" if y else "", t)

def window(area, title, why, subs, on_sub, sel, cards, go, width=640, slim=False):
    a = COL[area]; ic = [x for x in AREAS if x[0] == area][0][3]
    return ('<div class="win" style="width:%dpx;--a:%s"><div class="top"><div class="search">Search any tool...</div></div><div class="body">%s'
            '<div class="main"><div class="head"><div class="t"><div class="bigic">%s</div><h2>%s</h2></div><div class="why">%s</div>'
            '<div class="subt">%s</div></div><div class="content"><div class="sel">%s</div>%s%s</div></div></div></div>'
            % (width, a, side(area, slim), ic, title, why, "".join('<span class="%s">%s</span>' % ("on" if s == on_sub else "", s) for s in subs),
               sel, "".join(cards), '<div class="go">%s</div>' % go if go else ""))

def shape_grid(on="Circle", hover=None):
    out = ""
    for g, items in SH:
        out += '<div class="gl">%s</div><div class="grid">' % g
        out += "".join('<div class="sh%s">%s%s</div>' % (" on" if n == on else "", S(d), n) for n, d in items)
        out += "</div>"
    return out

FRONT_PIC = ('<div class="pic"><svg viewBox="0 0 120 70"><line x1="10" y1="55" x2="110" y2="55" stroke="#f0c85a" stroke-width="3"/>'
             '<circle cx="40" cy="55" r="5" fill="#f0c85a"/><line x1="40" y1="55" x2="40" y2="20" stroke="#5fbf4f" stroke-width="2" stroke-dasharray="3 3"/>'
             '<path d="M36 26l4-8 4 8" fill="#5fbf4f"/><ellipse cx="40" cy="18" rx="22" ry="7" fill="none" stroke="#36b38a" stroke-width="2.5"/>'
             '<text x="50" y="40" fill="#a2a7ae" font-size="10">1.5 on +Y</text></svg><div class="n">The shape sits <b>1.5</b> above the joint (+Y). '
             'The pivot stays on the joint, so it still turns at the elbow.</div></div>')

CT_SUBS = ["Make", "Edit shape", "Behaviour", "Attributes", "Channels", "Spaces", "Follow", "Stick"]
make = window("controls", "Controls", "Make controls and shape them.", CT_SUBS, "Make",
    '<span class="lab">Selected</span>%s%s%s<span class="then">a chain → <b>an FK chain of 3 controls</b></span>' % (chip("joint","L_arm"), chip("joint","L_elbow"), chip("joint","L_wrist")),
    [card(1, "Pick a shape", '<div class="search" style="margin-bottom:4px">Search shapes: arrow, cube...</div>' + shape_grid("Circle")),
     card(2, "Size and place", '<div class="f"><label>Size</label><div>%s <span class="inp">1.00</span></div><label>Facing</label><div>%s <span class="tip">X: along the bone</span></div>'
          '<label>In front</label><div><span class="inp">1.5</span> %s</div></div>%s' % (seg(["Auto","Fixed"]), seg(["X","Y","Z"],0,True), seg(["+X","-X","+Y","-Y","+Z","-Z"],2,True), FRONT_PIC)),
     card(3, "How it drives", closed=True, peek="Constrain · groups _offset · follow the hierarchy"),
     card(4, "Name and colour", closed=True, peek="colour by side · add the side")],
    'Make 3 controls (Circle)<small>an FK chain on L_arm → L_wrist · one undo</small>')

edit = window("controls", "Controls", "Make controls and shape them.", CT_SUBS, "Edit shape",
    '<span class="lab">Selected</span>%s%s<span class="then">hover a shape: you see it on them</span>' % (chip("ctrl","L_hand_ctrl"), chip("ctrl","R_hand_ctrl")),
    [card(1, "Swap the shape", shape_grid("Four way arrow")),
     card(2, "Move, size, turn", '<div class="f"><label>In front</label><div><span class="inp">1.5</span> %s <span class="btn">Apply</span></div>'
          '<label>Size</label><div><span class="btn">−</span> <span class="btn">+</span> &nbsp; Stretch %s <span class="btn">−</span> <span class="btn">+</span></div>'
          '<label>Turn 90°</label><div>%s</div><label>By hand</label><div><span class="btn">%s Handles on the shape</span> <span class="tip">click away = keep</span></div></div>'
          % (seg(["+X","-X","+Y","-Y","+Z","-Z"],2,True), seg(["X","Y","Z"],1,True), seg(["X","Y","Z"],-1,True), S('<path d="M12 2v20 M2 12h20 M9 5l3-3 3 3 M9 19l3 3 3-3 M5 9l-3 3 3 3 M19 9l3 3-3 3"/>'))),
     card(3, "Look", '<div class="f"><label>Colour</label><div>%s <span class="btn">By side</span></div><label>Line width</label><div><span class="inp">2.0</span></div></div>'
          % " ".join('<span class="sw" style="background:%s"></span>' % c for c in ["#e2504a","#4c8fe0","#f0c85a","#5fbf4f","#b26be0","#ffffff"])),
     card(4, "Copy and mirror", closed=True, peek="1st → others · L → R · save as My shape")],
    'Use Four way arrow on 2 controls<small>only the curves change: keys and connections stay</small>')

skin = window("skin", "Skin", "Bind meshes and fix the weights.", ["Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle"], "Bind",
    '<span class="lab">Selected</span>%s<span class="then">+</span>%s<span class="then">→ <b>bind Hare_Body</b></span>' % (chip("mesh","Hare_Body"), chip("joint","97 joints")),
    [card(1, "Which joints", '<div class="f"><label>Joints</label><div>%s</div><label>Max per vertex</label><div>%s</div></div>%s'
          % (seg(["The rig's skin joints (97)", "Only the selected"]), seg(["2","3","4","6","8"],2), chk("Label the joints (mirror weights by label)"))),
     card(2, "Start from", closed=True, peek="closest joint · heat map · geodesic"),
     card(3, "After binding", closed=True, peek="clean small weights · lock the rest")],
    'Bind Hare_Body to 97 joints<small>4 per vertex · one undo</small>')

narrow = window("controls", "Controls", "Make controls and shape them.", ["Make", "Edit shape", "More ▾"], "Edit shape",
    '%s%s' % (chip("ctrl","L_hand_ctrl"), chip("ctrl","R_hand_ctrl")),
    [card(1, "Swap the shape", shape_grid("Four way arrow")), card(2, "Move, size, turn", closed=True), card(3, "Look", closed=True)],
    'Use Four way arrow<small>on 2 controls</small>', width=380, slim=True)

legend = '<div class="legend">' + "".join('<div><b style="background:%s">%s</b>%s</div>' % (c, ic, n) for _k, n, c, ic in AREAS) + \
         '<div><b style="background:#2b2e33;color:#e2504a">X</b><b style="background:#2b2e33;color:#5fbf4f">Y</b><b style="background:#2b2e33;color:#4c8fe0">Z</b>Maya\'s axis colours</div>' + \
         '<div>%s %s %s what is selected</div></div>' % (chip("joint","joint"), chip("ctrl","control"), chip("mesh","mesh"))

html = ('<!doctype html><html><head><meta charset="utf-8"><title>Rigtool 5.7 Look</title><style>%s</style></head><body>'
        '<h1>5.7 look, version 2: you know where you are at a glance</h1>'
        '<p class="sub">Every area has its own colour: the sidebar, the band at the top, the card numbers and the big button all carry it. '
        'X / Y / Z are always red / green / blue, like Maya. What you selected shows as coloured chips with an icon (joint, control, mesh). '
        'Shapes are pictures again. Pictures explain the harder fields (the "In front" drawing).</p>%s'
        '<div class="row"><div><div class="cap">A · Controls › Make (3 joints selected)</div>%s</div>'
        '<div><div class="cap">B · Controls › Edit shape (2 controls, Four way arrow picked)</div>%s</div></div>'
        '<div class="row" style="margin-top:26px"><div><div class="cap">C · Another area, another colour: Skin › Bind</div>%s</div>'
        '<div><div class="cap">D · The same page in a narrow panel: nothing cut</div>%s<div class="tip" style="width:380px;margin-top:6px">The shapes wrap to fewer columns; the sub-pages that don\'t fit go into "More ▾"; the sidebar shows only its coloured icons.</div></div></div>'
        '</body></html>') % (CSS, legend, make, edit, skin, narrow)
open("v2.html", "w").write(html)
