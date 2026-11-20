exec(open("face_mock.py").read().split("steps = [")[0])
def card_step(n, name, state, sel_line, body, button, open_=True, summary=""):
    col = {"done": OK_, "ready": WR, "todo": DIM_, "on": OR}[state]
    mark = {"done": "✓", "ready": "●", "todo": str(n), "on": str(n)}[state]
    head = ('<div style="display:flex;align-items:center;gap:10px"><b style="width:24px;height:24px;border-radius:50%%;background:%s;color:#111;display:grid;place-items:center">%s</b>'
            '<b style="font-size:14.5px">%s</b><span style="color:#a2a7ae;font-size:12.5px">%s</span><span style="margin-left:auto;color:#7d838b">%s</span></div>') % (col, mark, name, summary, "▾" if open_ else "▸")
    if not open_:
        return '<div style="background:#363a40;border-radius:9px;padding:9px 12px;border-left:3px solid %s">%s</div>' % (col, head)
    selc = "#e2504a" if sel_line.startswith("✗") else (OK_ if state == "done" else WR)
    return ('<div style="background:#3a3e45;border-radius:9px;padding:10px 12px;border-left:3px solid %s">%s<div style="margin:8px 0 0 34px;display:flex;flex-direction:column;gap:8px">%s%s%s</div></div>') % (
        OR, head, body, '<div style="background:#24272b;border-radius:7px;padding:6px 9px;font-size:12.5px;color:%s">%s</div>' % (selc, sel_line) if sel_line else "",
        '<div class="go" style="--a:%s">%s</div>' % (OR, button) if button else "")
def choice(opts, on=0): return '<span class="seg">' + "".join('<span class="%s" style="%s">%s</span>' % ("on" if i == on else "", "background:%s;color:#111;font-weight:700" % OR if i == on else "", o) for i, o in enumerate(opts)) + '</span>'
def frow(lab, ctl): return '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><span style="color:#a2a7ae;min-width:96px;text-align:right">%s</span>%s</div>' % (lab, ctl)
def pic(svg, text): return '<div class="pic"><svg viewBox="0 0 160 70" style="width:160px;height:70px;flex:none">%s</svg><div class="n">%s</div></div>' % (svg, text)
lid_two = ('<path d="M20 40 Q60 8 100 40" stroke="#4fb3d9" stroke-width="2.5" fill="none"/><path d="M20 40 Q60 62 100 40" stroke="#4fb3d9" stroke-width="2.5" fill="none"/>'
           '<path d="M26 36 Q60 14 94 36 L94 44 Q60 56 26 44Z" fill="#e0893a33" stroke="#e0893a" stroke-width="1.5"/><circle cx="60" cy="40" r="7" fill="#5fbf4f"/>'
           '<text x="108" y="22" fill="#4fb3d9" font-size="9">upper curve</text><text x="108" y="60" fill="#4fb3d9" font-size="9">lower curve</text>')
strip_two = ('<path d="M15 20 Q70 35 145 25" stroke="#4fb3d9" stroke-width="2.5" fill="none"/><path d="M15 40 Q70 55 145 45" stroke="#4fb3d9" stroke-width="2.5" fill="none"/>'
             '<path d="M15 20 Q70 35 145 25 L145 45 Q70 55 15 40Z" fill="#e0893a33" stroke="#e0893a" stroke-width="1.2"/>' + "".join('<circle cx="%d" cy="%d" r="4" fill="#36b38a"/>' % (x, y) for x, y in ((30, 33), (60, 39), (95, 41), (130, 37))))
eyelids = card_step(3, "Eyelids", "ready", "✓ 2 curves selected: L_lid_up_crv, L_lid_low_crv - left of centre",
    frow("Make it from", choice(["Two curves (you place them)", "An edge loop"], 0)) +
    pic(lid_two, "Draw (or <b>Edge to curve</b>) the line <b>above</b> and <b>below</b> the lid, select both: the ribbon is lofted between them - you decide its width and shape. Mirrored to the right.") +
    frow("Controls", inp("8") + " " + choice(["Even", "More at the corners"], 0)),
    "Make eyelids<small>from your 2 curves · mirrored to the right · one undo</small>", summary="")
strips = card_step(6, "Strips (cheek, nasolabial...)", "on", "✗ 1 curve selected - select the two curves along the strip (one each side)",
    frow("Make it from", choice(["Two curves", "Edges"], 0)) + pic(strip_two, "Two curves along the strip, one on each side: the ribbon between them; controls along it.") +
    frow("Name", inp("L_cheek", 150)) + frow("Controls", inp("4")), "Make the strip<small>needs the two curves</small>")
face_steps = [card_step(1, "Setup", "done", "", "", "", open_=False, summary="Cartoony · Head: head_jnt · Jaw: Jaw_ctrl"),
              card_step(2, "Eyes", "done", "", "", "", open_=False, summary="L / R_Eye_ctrl made · Blink on each"),
              eyelids,
              card_step(4, "Mouth", "todo", "", "", "", open_=False, summary="two curves or the loop round the lips · lip roll & sticky"),
              card_step(5, "Brows", "todo", "", "", "", open_=False, summary="two curves or edges along the LEFT brow · 3 controls"),
              strips]
facepage = ('<div class="win" style="width:760px;--a:%s"><div class="body">%s<div class="main">'
            '<div class="head"><div class="t"><div class="bigic">⬢</div><h2>Build</h2></div>'
            '<div class="subt"><span>Build</span><span class="on">Face</span><span>Ribbon</span><span>Joints</span></div>'
            '<div class="subt" style="margin-top:2px;font-size:13px"><span class="on" style="padding:5px 10px">Build the face</span><span style="padding:5px 10px">Ribbons &amp; groups</span><span style="padding:5px 10px">Squash &amp; expressions</span></div></div>'
            '<div class="content"><div class="sel"><span class="lab">Selected</span>%s%s<span class="then">2 curves, left of centre</span></div>'
            '<div style="display:flex;gap:14px;align-items:flex-start"><div style="flex:none;width:210px">%s%s</div>'
            '<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:7px">%s</div></div></div></div></div></div>') % (
    OR, side("build"), chip("ctrl", "L_lid_up_crv"), chip("ctrl", "L_lid_low_crv"),
    face_svg({"eyes": "done", "lids": "ready", "brows": "todo", "mouth": "todo", "strips": "on"}, 200), legend(), "".join(face_steps))

# ---------------- Ribbon as steps
rib_pic = ('<path d="M10 25 Q80 5 150 25 L150 45 Q80 25 10 45Z" fill="#e0893a22" stroke="#e0893a" stroke-width="1.5"/>' +
           "".join('<circle cx="%d" cy="%d" r="3.5" fill="#f0c85a"/>' % (x, 35 - 10 * (1 - ((x - 80) / 70.0) ** 2)) for x in range(18, 150, 16)) +
           "".join('<circle cx="%d" cy="%d" r="8" fill="none" stroke="#36b38a" stroke-width="2"/>' % (x, 35 - 10 * (1 - ((x - 80) / 70.0) ** 2) - 12) for x in (18, 66, 114, 146)) +
           '<text x="10" y="66" fill="#a2a7ae" font-size="9">joints (yellow) · controls (green) · the ribbon</text>')
srf_body = (frow("Use", choice(["The selected surface", "Make one"], 1)) +
            frow("Make it from", choice(["Two curves (loft)", "An edge (curve + width)", "A plane"], 0)) +
            pic('<path d="M10 20 Q80 5 150 20" stroke="#4fb3d9" stroke-width="2.5" fill="none"/><path d="M10 50 Q80 35 150 50" stroke="#4fb3d9" stroke-width="2.5" fill="none"/><path d="M10 20 Q80 5 150 20 L150 50 Q80 35 10 50Z" fill="#e0893a33"/>',
                "Two curves selected: lofted between them. Check / fix curves first if they run opposite ways (it says so).") +
            '<div style="display:flex;gap:6px;flex-wrap:wrap"><span class="btn">Edge to curve</span><span class="btn">Check / fix curves</span><span class="btn">Swap U/V</span><span class="btn">Flip normals</span></div>')
rib_steps = [card_step(1, "Surface", "ready", "✓ 2 curves selected: cape_L_crv, cape_R_crv - same direction, 8 spans", srf_body, "Loft the surface<small>Cape_srf · along U</small>"),
             card_step(2, "Joints along it (follicles)", "todo", "", "", "", open_=False, summary="0 = auto (one per span) · even · joints on"),
             card_step(3, "Controls", "todo", "", "", "", open_=False, summary="every 2 joints · circle · size 1 · 3 in front"),
             card_step(4, "Create and mirror", "todo", "", pic(rib_pic, "What you'll get: 9 joints, 4 controls."), "", open_=False, summary="Create · mirror X · rebuild")]
progress = ('<div style="display:flex;gap:12px;align-items:center;background:#24272b;border-radius:8px;padding:8px 10px;flex-wrap:wrap">' +
            "".join('<span style="display:flex;gap:6px;align-items:center"><b style="width:20px;height:20px;border-radius:50%%;background:%s;color:#111;display:grid;place-items:center;font-size:11px">%s</b>%s</span>%s' % (c, m, t, "<span style='color:#5a6069'>→</span>" if k < 3 else "")
                    for k, (c, m, t) in enumerate(((WR, "1", "Surface"), (DIM_, "2", "Joints"), (DIM_, "3", "Controls"), (DIM_, "4", "Create")))) + '</div>')
ribpage = ('<div class="win" style="width:760px;--a:' + OR + '"><div class="body">' + side("build") + '<div class="main">'
           '<div class="head"><div class="t"><div class="bigic">⬢</div><h2>Build</h2></div>'
           '<div class="subt"><span>Build</span><span>Face</span><span class="on">Ribbon</span><span>Joints</span></div>'
           '<div class="subt" style="margin-top:2px;font-size:13px"><span class="on" style="padding:5px 10px">Make a ribbon</span><span style="padding:5px 10px">Builds in the scene</span></div></div>'
           '<div class="content"><div class="sel"><span class="lab">Selected</span>' + chip("ctrl", "cape_L_crv") + chip("ctrl", "cape_R_crv") + '<span class="then">2 curves</span></div>'
           + progress + "".join(rib_steps) + '</div></div></div></div>')
ribdone = card_step(4, "Create and mirror", "on", "✓ Cape_srf ready · 9 joints · 4 controls",
                    pic(rib_pic, "9 joints, 4 controls; the preview dots show in the viewport.") + frow("Mirror", choice(["X", "Y", "Z"], 0) + " " + inp("R_", 60)) +
                    '<div style="display:flex;gap:6px;flex-wrap:wrap"><span class="btn">Rebuild</span><span class="btn">Mirror build</span><span class="btn" style="background:#5a2f2d">Delete build</span><span class="btn">More (symmetric, constraints, replace surface)...</span></div>',
                    "Create the ribbon<small>Cape_srf · 9 joints · 4 controls · one undo</small>")
html = ('<!doctype html><html><head><meta charset="utf-8"><title>Face and Ribbon</title><style>' + CSS + '</style></head><body>'
        '<div class="blk"><h1>Face › Build the face - from two curves (mock-up)</h1><p class="sub">Eyelids and strips: <b>Two curves</b> first (you place the line above and below, the ribbon is lofted between them); <b>an edge loop</b> stays as the other way. The step checks your selection (2 curves, which side) and the button says what will happen. Mouth and brows can take two curves too.</p>' + facepage + '</div>'
        '<div class="blk" style="margin-top:20px"><h1>Ribbon as steps (mock-up)</h1><p class="sub">Surface → Joints → Controls → Create, in order, with a progress strip on top. Surface checks what you selected (two curves: same direction? how many spans?). Every button of today stays - the rarer ones under More.</p>'
        '<div class="row" style="align-items:flex-start"><div>' + ribpage + '</div><div style="width:420px"><div class="cap">The last step, open</div>' + ribdone + '</div></div></div></body></html>')
open("face_ribbon_mock.html", "w").write(html)
