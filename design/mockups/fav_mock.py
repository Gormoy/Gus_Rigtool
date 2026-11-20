exec(open("v2pages.py").read().split("PAGES = []")[0])
def favtile(c, t, name, x=False):
    return ('<span style="position:relative;display:inline-flex;align-items:center;gap:6px;background:#2e3237;border-radius:7px;padding:4px 9px 4px 5px;%s">'
            '<span style="width:20px;height:20px;border-radius:5px;background:%s;color:#111;font-weight:800;font-size:10px;display:grid;place-items:center">%s</span>%s%s</span>') % (
        "border:1px dashed #6f93bd;cursor:grab" if x else "", c, t, name,
        '<b style="position:absolute;top:-7px;right:-7px;width:16px;height:16px;border-radius:50%;background:#e2504a;color:#fff;font-size:11px;display:grid;place-items:center">×</b>' if x else "")
FAV = [("#6f93bd", "Se", "Select"), ("#6f93bd", "Gr", "Groups"), ("#36b38a", "Co", "Controls"), ("#e0893a", "Ri", "Ribbon"), ("#e3bd3c", "Ch", "Checker")]
row_normal = ('<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;background:#24272b;padding:8px;border-radius:8px">'
              '<span class="chip" style="background:#ffffff14;color:#e9ebee">Rigging ▾</span>' + "".join(favtile(*f) for f in FAV) +
              '<span class="btn">✎</span><span class="btn">Map</span><span class="btn">Bar</span></div>')
row_edit = ('<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;background:#24272b;padding:10px;border-radius:8px;border:2px dashed #6f93bd">'
            '<span class="chip" style="background:#ffffff14;color:#e9ebee">Rigging ▾</span>' + "".join(favtile(*f, x=True) for f in FAV) +
            '<span style="border:2px dashed #6f93bd;color:#6f93bd;border-radius:7px;padding:3px 10px;font-weight:700">+ Add</span>'
            '<span class="btn" style="background:#6f93bd;color:#111;font-weight:700">Done</span>'
            '<div style="width:100%;color:#6f93bd;font-size:12px">drag a favourite to move it · × takes it off · + adds (grouped by area) · Rigging ▾ = your profiles (Rigging, Face, Skinning...)</div></div>')
prof = ('<div class="win" style="width:250px"><div class="content" style="padding:10px"><div class="gl">Favourites profiles</div>'
        + "".join('<div class="nav%s" style="padding:6px 8px;border-radius:6px%s">%s<span style="float:right;color:#7d838b;font-size:12px">%s</span></div>' % (" on" if n == "Rigging" else "", ";background:#ffffff12" if n == "Rigging" else "", n, k)
                  for n, k in (("All tools", "26"), ("Rigging", "5 · mine"), ("Face", "6 · mine"), ("Skinning", "4 · mine"), ("Build (area)", "group"), ("Controls (area)", "group")))
        + '<div style="border-top:1px solid #4a4f57;margin:8px 0"></div><div class="nav">+ New profile</div><div class="nav">Rename · Delete</div></div></div>')
sidebar = ('<div class="win" style="width:210px;height:560px"><div class="body"><div class="side" style="width:100%">'
           '<div class="nav"><b style="background:#c9ccd1">⌂</b>Home</div><div class="sec">Your rig, in order</div>'
           + "".join('<div class="nav"><b style="background:%s">%d</b>%s</div>' % (c, i + 1, n) for i, (n, c) in enumerate((("Build", "#e0893a"), ("Skin", "#d8638c"), ("Controls", "#36b38a"), ("Connect", "#9b74dc"), ("Check & publish", "#e3bd3c")))) +
           '<div class="sec">Any time</div><div class="nav"><b style="background:#6f93bd">⚒</b>Toolbox</div><div class="nav"><b style="background:#c9ccd1">★</b>My tools ▸</div>'
           '<div style="margin-top:auto"></div><div class="nav on" style="border-left-color:#8a9098"><b style="background:#8a9098">⚙</b>Settings</div></div></div></div>')
skin_subs = ('<div style="display:flex;gap:2px;flex-wrap:wrap;background:linear-gradient(#5a3446,#33373d);padding:10px;border-radius:8px;border-top:4px solid #d8638c">'
             + "".join('<span style="padding:7px 12px;border-radius:7px;%s">%s</span>' % ("background:#33373d;box-shadow:inset 0 3px 0 #d8638c;color:#fff" if s == "Bind" else "color:#a2a7ae", s)
                       for s in ("Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle", "Fixes")) + '</div>'
             '<div class="tip" style="margin-top:6px;max-width:640px">Today\'s 9 Skin cards + Fixes, split by job: Bind · Copy & mirror (Copy skin, Mirror weights) · Save / load · Clean · Weights (Vertex weights, Weight list) · Cloth & jiggle · Fixes. Same cards, same buttons - each sub-page short.</div>')
html = ('<!doctype html><html><head><meta charset="utf-8"><title>Rigtool 5.7.2 Preview</title><style>' + CSS + '</style></head><body>'
        '<div class="blk"><h1>5.7.2 preview: Settings, favourites editing, Skin</h1><p class="sub">Nothing built. The favourites edit the same way as the Animtool bar (one design for both).</p>'
        '<div class="row" style="align-items:flex-start"><div><div class="cap">1 · Settings: its own button, at the bottom of the sidebar</div>' + sidebar + '</div>'
        '<div><div class="cap">2 · The favourites row (profile Rigging)</div>' + row_normal + '<div style="height:16px"></div><div class="cap">3 · ✎ Edit: drag, ×, + Add, Done</div>' + row_edit +
        '<div style="height:16px"></div><div class="cap">5 · Skin: its sub-pages</div>' + skin_subs + '</div><div><div class="cap">4 · Profiles</div>' + prof + '</div></div></div></body></html>')
open("fav_mock.html", "w").write(html)
