exec(open("v2pages.py").read().split("PAGES = []")[0])
OR = "#e0893a"; OK_ = "#5fbf4f"; WR = "#e3bd3c"; DIM_ = "#5a6069"
def face_svg(states, w=260):
    c = {"done": OK_, "ready": WR, "todo": DIM_, "on": OR}
    s = states
    return ('<svg viewBox="0 0 200 230" width="%d"><ellipse cx="100" cy="118" rx="78" ry="98" fill="#2a2d32" stroke="#6b7079" stroke-width="2"/>'
            '<path d="M48 70 Q70 58 88 66" stroke="%s" stroke-width="6" fill="none" stroke-linecap="round"/><path d="M112 66 Q130 58 152 70" stroke="%s" stroke-width="6" fill="none" stroke-linecap="round" stroke-dasharray="2 6"/>'
            '<ellipse cx="70" cy="95" rx="18" ry="10" fill="none" stroke="%s" stroke-width="5"/><ellipse cx="130" cy="95" rx="18" ry="10" fill="none" stroke="%s" stroke-width="5" stroke-dasharray="2 6"/>'
            '<circle cx="70" cy="95" r="5" fill="%s"/><circle cx="130" cy="95" r="5" fill="%s"/>'
            '<path d="M70 165 Q100 150 130 165 Q100 185 70 165" fill="none" stroke="%s" stroke-width="5"/>'
            '<path d="M50 120 Q60 140 70 150" stroke="%s" stroke-width="5" fill="none" stroke-linecap="round"/>'
            '<text x="100" y="226" fill="#7d838b" font-size="10" text-anchor="middle">dashed = the right side, mirrored for you</text></svg>') % (
        w, c[s["brows"]], c[s["brows"]], c[s["lids"]], c[s["lids"]], c[s["eyes"]], c[s["eyes"]], c[s["mouth"]], c[s["strips"]])
def legend():
    return ('<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#a2a7ae">' + "".join(
        '<span><b style="display:inline-block;width:10px;height:10px;border-radius:3px;background:%s;margin-right:4px"></b>%s</span>' % x
        for x in ((OK_, "made"), (WR, "ready - your selection fits"), (OR, "the one you're on"), (DIM_, "not made yet"))) + '</div>')
def step(n, name, state, what, sel_line, opts, button, made=None, open_=False):
    col = {"done": OK_, "ready": WR, "todo": DIM_, "on": OR}[state]
    mark = {"done": "✓", "ready": "●", "todo": str(n), "on": str(n)}[state]
    head = ('<div style="display:flex;align-items:center;gap:10px"><b style="width:24px;height:24px;border-radius:50%%;background:%s;color:#111;display:grid;place-items:center">%s</b>'
            '<b style="font-size:14.5px">%s</b><span style="color:#a2a7ae;font-size:12.5px">%s</span><span style="margin-left:auto;color:#7d838b">%s</span></div>') % (
        col, mark, name, made or what if not open_ else "", "▾" if open_ else "▸")
    if not open_:
        return '<div style="background:#363a40;border-radius:9px;padding:9px 12px;border-left:3px solid %s">%s</div>' % (col, head)
    body = ('<div style="margin:8px 0 0 34px;display:flex;flex-direction:column;gap:7px"><div class="tip"><b style="color:#e9ebee">Select:</b> %s</div>'
            '<div style="background:#24272b;border-radius:7px;padding:6px 9px;font-size:12.5px;color:%s">%s</div>%s'
            '<div class="go" style="--a:%s">%s</div></div>') % (what, WR if state == "ready" else "#e2504a", sel_line, opts, OR, button)
    return '<div style="background:#3a3e45;border-radius:9px;padding:10px 12px;border-left:3px solid %s">%s%s</div>' % (OR, head, body)
steps = [
    step(1, "Setup", "done", "", "", "", "", made="Cartoony · Head: head_jnt · Jaw: Jaw_ctrl"),
    step(2, "Eyes", "done", "", "", "", "", made="L / R_Eye_ctrl made · Blink on each"),
    step(3, "Eyelids", "ready", "the edge loop round the LEFT eye (the right one is mirrored)",
         "✓ 24 edges selected - one loop, left of centre", "", "Make eyelids<small>left loop · mirrored to the right · one undo</small>", open_=True),
    step(4, "Mouth", "todo", "the edge loop round the lips", "", "", "", made="the loop round the lips · lip roll & sticky (option)"),
    step(5, "Brows", "todo", "", "", "", "", made="the edges along the LEFT brow · 3 controls per brow"),
    step(6, "Strips", "todo", "", "", "", "", made="any strip: cheek, nasolabial... · name it")]
page = ('<div class="win" style="width:720px;--a:%s"><div class="top"><div class="search">Search any tool...</div></div><div class="body">%s<div class="main">'
        '<div class="head"><div class="t"><div class="bigic">⬢</div><h2>Build</h2></div><div class="why">Modules, face, ribbons and joints.</div>'
        '<div class="subt"><span>Build</span><span class="on">Face</span><span>Ribbon</span><span>Joints</span></div>'
        '<div class="subt" style="margin-top:2px;font-size:13px"><span class="on" style="padding:5px 10px">Build the face</span><span style="padding:5px 10px">Ribbons &amp; groups</span><span style="padding:5px 10px">Squash &amp; expressions</span></div></div>'
        '<div class="content"><div class="sel"><span class="lab">Selected</span>%s<span class="then">24 edges on Hare_Body - a loop, left of centre</span></div>'
        '<div style="display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap"><div style="flex:none">%s%s</div>'
        '<div style="flex:1;min-width:300px;display:flex;flex-direction:column;gap:7px">%s</div></div></div></div></div></div>') % (
    OR, side("build"), chip("mesh", "Hare_Body.e[1203:1226]"), face_svg({"eyes": "done", "lids": "on", "brows": "todo", "mouth": "todo", "strips": "todo"}), legend(), "".join(steps))
made_card = ('<div style="background:#3a3e45;border-radius:9px;padding:10px 12px;border-left:3px solid %s"><div style="display:flex;gap:10px;align-items:center"><b style="width:24px;height:24px;border-radius:50%%;background:%s;color:#111;display:grid;place-items:center">✓</b><b>Eyelids</b><span style="color:#a2a7ae;font-size:12.5px">L / R_Eyelid_Ribbon · 8 controls each</span></div>'
             '<div style="margin:8px 0 0 34px;display:flex;gap:6px;flex-wrap:wrap"><span class="btn">Select its controls</span><span class="btn">Redo (style / count)</span><span class="btn">Open in Ribbon</span></div></div>') % (OK_, OK_)
trio = [("The card when the selection doesn't fit", step(3, "Eyelids", "on", "the edge loop round the LEFT eye", "✗ 2 objects selected - select edges round the left eye (double-click an edge to pick the loop)", "", "Make eyelids<small>needs the loop first</small>", open_=True)),
        ("...when it fits (the lamp turns yellow)", step(3, "Eyelids", "ready", "the edge loop round the LEFT eye", "✓ 24 edges - one loop, left of centre", "", "Make eyelids<small>mirrored to the right · one undo</small>", open_=True)),
        ("...once it's made (the step turns green)", made_card)]
states = '<div class="row" style="align-items:flex-start">' + "".join('<div style="width:360px"><div class="cap">%s</div>%s</div>' % (t, h) for t, h in trio) + '</div>'
html = ('<!doctype html><html><head><meta charset="utf-8"><title>Face Preview</title><style>' + CSS + '</style></head><body><div class="blk">'
        '<h1>Face, made easier to follow (mock-up · nothing built)</h1><p class="sub">Not 7 pages with one button each. One page, <b>Build the face</b>: a face map shows what\'s made, a step list says what to select for each part and checks your selection, the options sit with their part. The rest of Face moves to two short sub-pages. No new tools - the same buttons.</p>'
        '<div class="cap">A · Face › Build the face (eyes made, eyelids next, the loop already selected)</div>' + page +
        '<div class="cap" style="margin-top:22px">B · A step\'s three states</div>' + states + '</div></body></html>')
open("face_mock.html", "w").write(html)
