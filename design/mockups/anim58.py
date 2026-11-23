"""
5.8 preview: the Animtool in the Rigtool's new look - the bar with profiles and the right-click options strip, the
window, the pie, the narrow dock and its rail, search (Ctrl+K), the new settings. Nothing built: a picture for Gus.
Uses the real Animtool icons (anim/gus_animtool/icons/ga_*.png) and the tools' real option names.

    python3 anim58.py        -> anim58.html; screenshot each .blk at device scale 2 (design/screens58/)
"""
import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "..", "..", "gus_rigtool", "anim", "gus_animtool", "icons")

CAT = {  # the categories, their colour (the icons' bottom bar) and their tools
    "pick": ("Pick & see", "#e15c8f", ["picker", "arcs", "arcs_panel", "ghosts", "hide_ctrls", "hider", "isolate", "playblast"]),
    "pose": ("Pose", "#5cc270", ["mirror", "flip", "reset", "twin", "ikfk"]),
    "tween": ("Tween", "#9e70eb", ["tween_prev", "tween_next"]),
    "keys": ("Keys & tangents", "#f0ae33", ["key", "blocking", "nudge_left", "nudge_right", "tan_auto", "tan_spline",
                                            "tan_linear", "tan_flat", "tan_step"]),
    "timing": ("Timing & cycles", "#33bdb3", ["copy_keys", "paste_keys", "inbetween_add", "inbetween_remove", "offset_minus",
                                              "offset_plus", "offset_back", "mirror_cycle", "cycle_continue", "cycle_place",
                                              "cycle_forward", "bake_keys", "reduce_keys", "overlap", "stretch", "reverse",
                                              "time_scale"]),
    "curves": ("Graph curves", "#f57b3d", ["pull", "push", "negate", "smooth", "noise", "redundant", "euler"]),
    "space": ("Spaces & props", "#48c2eb", ["temp_world", "temp_pivot", "bake_back", "attach", "release", "attach_window"]),
    "open": ("Windows", "#4c93e7", ["main", "poses", "clips"]),
}
NAME = {"main": "Gus Animtool", "picker": "Picker", "poses": "Poses", "clips": "Clips", "tween_prev": "Tween ◀",
        "tween_next": "Tween ▶", "nudge_left": "Nudge ◀", "nudge_right": "Nudge ▶", "key": "Key", "tan_auto": "Auto",
        "tan_spline": "Spline", "tan_linear": "Linear", "tan_flat": "Flat", "tan_step": "Stepped",
        "blocking": "Blocking / spline", "mirror": "Mirror", "flip": "Flip", "reset": "Reset", "twin": "Twin",
        "ikfk": "IK / FK", "copy_keys": "Copy keys", "paste_keys": "Paste keys", "inbetween_add": "Add inbetween",
        "inbetween_remove": "Remove inbetween", "offset_minus": "Offset −", "offset_plus": "Offset +",
        "offset_back": "Back to original", "mirror_cycle": "Mirror cycle", "cycle_continue": "Continue cycle",
        "cycle_place": "Cycle in place", "cycle_forward": "Cycle forward", "bake_keys": "Bake keys",
        "reduce_keys": "Reduce keys", "overlap": "Overlap", "stretch": "Slower / faster", "reverse": "Reverse",
        "time_scale": "Time scale", "pull": "Pull", "push": "Push", "negate": "Negate", "smooth": "Smooth",
        "noise": "Noise", "redundant": "Redundant", "euler": "Euler", "temp_world": "World space",
        "temp_pivot": "Temp pivot", "bake_back": "Bake back", "attach": "Attach", "release": "Release",
        "arcs": "Arcs", "hide_ctrls": "Controls", "isolate": "Isolate", "hider": "Body parts", "ghosts": "Ghosts",
        "playblast": "Playblast", "attach_window": "Attach window", "arcs_panel": "Arcs panel"}
COLOUR = {k: c for _n, c, ks in CAT.values() for k in ks}
ORDER = [k for _n, _c, ks in CAT.values() for k in ks]
OKABE = {"pick": "#cc79a7", "pose": "#009e73", "tween": "#9a8cd9", "keys": "#e69f00", "timing": "#56b4e9",
         "curves": "#d55e00", "space": "#0072b2", "open": "#bbbbbb"}

# the profiles I suggest (Gus: "name them differently and suggest new ones")
PROFILES = [
    ("Blocking", "BLK", "Poses on stepped keys: key, tween, mirror, reset, inbetweens, IK/FK.",
     ["key", "blocking", "tan_step", "tween_prev", "tween_next", "mirror", "flip", "reset", "copy_keys", "paste_keys",
      "inbetween_add", "inbetween_remove", "ikfk"]),
    ("Splining", "SPL", "From stepped to smooth: tangents, nudge, offsets, clean curves.",
     ["blocking", "tan_auto", "tan_spline", "tan_flat", "tan_linear", "nudge_left", "nudge_right", "offset_minus",
      "offset_plus", "offset_back", "euler", "redundant"]),
    ("Polish", "POL", "The last pass: overlap, push / pull, arcs, ghosts, a little noise.",
     ["overlap", "push", "pull", "negate", "smooth", "noise", "arcs", "arcs_panel", "ghosts", "tween_prev",
      "tween_next"]),
    ("Spaces & props", "SPC", "Hands on props, world space, temp pivots, IK/FK - no jumps.",
     ["attach", "release", "attach_window", "temp_world", "temp_pivot", "bake_back", "ikfk", "twin", "key"]),
    ("Cycles", "CYC", "Walks and runs: mirror the half, repeat, in place / forward, retime.",
     ["mirror_cycle", "cycle_continue", "cycle_place", "cycle_forward", "offset_minus", "offset_plus", "stretch",
      "time_scale", "reverse"]),
    ("Review", "REV", "Look at the shot: picker, arcs, ghosts, hide, isolate, playblast.",
     ["picker", "poses", "arcs", "ghosts", "hide_ctrls", "hider", "isolate", "playblast"]),
    ("Clean-up", "CLN", "Baked or mocap keys: bake, reduce, smooth, Euler, redundant keys.",
     ["bake_keys", "reduce_keys", "smooth", "euler", "redundant", "copy_keys", "paste_keys"]),
    ("All tools", "ALL", "Every tool, by category (opens as a grid).", ORDER),
]

_png = {}


def png(key):
    if key not in _png:
        path = os.path.join(ICONS, "ga_%s.png" % key)
        _png[key] = "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()
    return _png[key]


OPTS = {"tween_prev", "tween_next", "key", "mirror", "reset", "copy_keys", "paste_keys", "inbetween_add",
        "inbetween_remove", "offset_minus", "offset_plus", "offset_back", "time_scale", "arcs", "ghosts", "attach",
        "release", "mirror_cycle", "blocking", "bake_keys", "reduce_keys", "overlap", "stretch", "cycle_continue",
        "hider", "playblast", "nudge_left", "nudge_right", "push", "pull", "noise"}


def tile(key, px=34, label=False, on=False, okabe=False, cat=None):
    c = COLOUR[key]
    if okabe:
        c = OKABE[[k for k, v in CAT.items() if key in v[2]][0]]
    corner = '<i class="corner"></i>' if key in OPTS else ""
    lab = '<span class="lab">%s</span>' % NAME[key] if label else ""
    w = max(px + 6, 54) if label else px + 4
    return ('<span class="tile%s" style="width:%dpx" title="%s"><span class="tb" style="width:%dpx;height:%dpx;'
            'border-bottom-color:%s"><img src="%s" style="width:%dpx;height:%dpx">%s</span>%s</span>'
            % (" on" if on else "", w, NAME[key], px, px, c, png(key), px - 6, px - 6, corner, lab))


def tweener(px=34, vertical=False):
    if vertical:
        return ('<span class="tween v"><b>TWEEN</b><span class="pct">+25%%</span><span style="display:flex;gap:6px">'
                '<span class="vtrack"><span class="vfill"></span><span class="vknob"></span></span><span class="ticks v">%s</span></span>'
                '<span class="over">150%%</span></span>'
                % "".join("<i>%s</i>" % t for t in ("+75", "+50", "+25", "0", "−25", "−50", "−75")))
    w = max(108, int(px * 4.1))
    return ('<span class="tween" style="width:%dpx;height:%dpx"><span class="trow"><b>TWEEN</b><span class="pct">+25%%</span>'
            '<span class="over">100%%</span></span><span class="track"><span class="fill"></span><span class="knob"></span>'
            '</span><span class="ticks">%s</span></span>' % (w, max(30, px + 4), "<i></i>" * 7))


def chrome(shape="row", prof="BLK", n=13, short=False, px=34):
    S = {"row": "R", "2r": "2", "col": "C", "grid": "G"}
    segs = "".join('<span class="seg%s">%s</span>' % (" on" if s == shape else "", S[s] if short else
                   {"row": "Row", "2r": "2R", "col": "Col", "grid": "Grid"}[s]) for s in ("row", "2r", "col", "grid"))
    return ('<div class="chrome"><span class="grip">::</span><span class="px">%dpx</span><span class="btn sq">=</span>'
            '<span class="pill on">%s %d</span><span class="btn sq">▾</span>%s<span class="seg">%s</span>'
            '<span class="slider"><span></span></span><span class="btn sq">%s</span></div>'
            % (px, prof, n, segs, "Aa" if short else "Lbl", "✎" if short else "Edit"))


def bar_row(keys, px=34, label=False, strip=None, prof="BLK"):
    tiles = []
    for k in keys:
        tiles.append(tile(k, px, label, on=(k == strip)))
        if k == "tween_prev":
            tiles.append(tweener(px))
    return ('<div class="bar">%s<div class="tiles">%s</div></div>' % (chrome("row", prof, len(keys), px=px), "".join(tiles)))


def strip(key, rows, buttons=("Open its page", "Pop out", "Remove")):
    body = "".join('<div class="orow"><span>%s</span>%s</div>' % (a, b) for a, b in rows)
    return ('<div class="strip" style="border-left-color:%s"><div class="sh"><span><b>%s</b> options</span>'
            '<span class="btn sq">×</span></div><div class="ogrid">%s</div><div class="obtns">%s</div></div>'
            % (COLOUR[key], NAME[key], body, "".join('<span class="btn">%s</span>' % b for b in buttons)))


def dd(v, w=150):
    return '<span class="dd" style="min-width:%dpx">%s<b>▾</b></span>' % (w, v)


def chk(t, on=False):
    return '<span class="chk%s"><i></i>%s</span>' % (" on" if on else "", t)


def segs(items, on):
    return '<span class="segs">%s</span>' % "".join('<span class="%s">%s</span>' % ("on" if i == on else "", i)
                                                    for i in items)


CSS = """
:root{--bg:#1d2024;--panel:#2a2d32;--card:#30343a;--line:#454a52;--text:#e9ebee;--dim:#a2a7ae;--acc:#6f93bd}
*{box-sizing:border-box} body{margin:0;background:#3a3f46;font:13px/1.35 -apple-system,'Segoe UI',Inter,Arial,sans-serif;color:var(--text)}
.blk{padding:22px 26px;background:#3a3f46;display:inline-block;min-width:1100px}
h1{font-size:20px;margin:0 0 4px} .sub{color:#c9cdd2;margin:0 0 16px;max-width:1000px}
.cap{font-weight:700;margin:0 0 6px;color:#f3f4f6} .cap small{font-weight:400;color:#c3c7cc}
.row{display:flex;gap:26px;align-items:flex-start;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;justify-content:center;background:#33373d;border:1px solid #4a4f57;border-radius:6px;padding:4px 10px;color:var(--text);white-space:nowrap}
.btn.sq{padding:4px 8px;min-width:26px}
.bar{display:inline-block;background:var(--panel);border:1px solid #4a4f57;border-radius:10px;padding:6px 8px 7px}
.chrome{display:flex;gap:5px;align-items:center;margin-bottom:6px;font-size:12px}
.grip{color:#8b9097;font-weight:700;padding:0 4px;letter-spacing:-1px} .px{color:#c9cdd2;padding:0 4px}
.pill{background:#33373d;border:1px solid #4a4f57;border-radius:6px;padding:4px 10px;font-weight:600}
.pill.on{background:var(--acc);color:#10151b;border-color:var(--acc)}
.seg{background:#33373d;border:1px solid #4a4f57;border-radius:6px;padding:4px 9px} .seg.on{background:var(--acc);color:#10151b}
.slider{width:70px;height:4px;background:#555b63;border-radius:2px;position:relative;margin:0 6px}
.slider span{position:absolute;left:45%;top:-6px;width:14px;height:14px;border-radius:50%;background:var(--acc)}
.tiles{display:flex;gap:2px;align-items:flex-end;flex-wrap:wrap}
.tile{display:inline-flex;flex-direction:column;align-items:center;gap:2px}
.tb{position:relative;display:grid;place-items:center;background:#23262b;border-radius:6px;border-bottom:3px solid}
.tb img{image-rendering:auto;border-radius:4px}
.tile.on .tb{outline:2px solid #fff;outline-offset:-1px}
.corner{position:absolute;right:2px;bottom:2px;width:0;height:0;border-left:6px solid transparent;border-bottom:6px solid #fff}
.lab{font-size:10.5px;line-height:1.15;text-align:center;color:#d5d8dc;height:24px;overflow:hidden;width:100%}
.tween{display:inline-flex;flex-direction:column;justify-content:center;gap:2px;background:#23262b;border-radius:6px;padding:3px 7px;border-bottom:3px solid #9e70eb;margin:0 2px}
.trow{display:flex;gap:6px;align-items:center;font-size:9.5px} .trow b{letter-spacing:.5px} .pct{color:#c8b3f5}
.over{margin-left:auto;border:1px solid #555;border-radius:4px;padding:0 3px;font-size:9px;color:#bbb}
.track{position:relative;height:4px;background:#4a4f57;border-radius:2px;margin:3px 0}
.fill{position:absolute;left:50%;width:12%;height:4px;background:#9e70eb} .knob{position:absolute;left:58%;top:-5px;width:13px;height:13px;border-radius:50%;background:#c8b3f5}
.ticks{display:flex;gap:3px} .ticks i{flex:1;height:3px;background:#3d4249;border-radius:2px}
.tween.v{width:64px;height:auto;align-items:center;padding:6px 4px}
.vtrack{position:relative;width:4px;height:90px;background:#4a4f57;border-radius:2px;margin:4px 0}
.vfill{position:absolute;bottom:50%;height:12%;width:4px;background:#9e70eb}.vknob{position:absolute;bottom:58%;left:-5px;width:13px;height:13px;border-radius:50%;background:#c8b3f5}
.ticks.v{flex-direction:column;justify-content:space-between;font-size:8.5px;color:#bbb;height:90px;margin:4px 0} .ticks.v i{font-style:normal;background:none;height:auto}
.strip{display:inline-block;background:var(--panel);border:1px solid #4a4f57;border-left:4px solid;border-radius:10px;padding:10px 14px;margin-top:4px;min-width:420px}
.sh{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:14px}
.ogrid{display:grid;grid-template-columns:1fr 1fr;gap:8px 18px}
.orow{display:flex;align-items:center;gap:10px;justify-content:space-between} .orow>span:first-child{color:#dfe2e6;white-space:nowrap}
.obtns{display:flex;gap:6px;margin-top:10px}
.dd{display:inline-flex;justify-content:space-between;gap:8px;background:#24272b;border:1px solid #4a4f57;border-radius:5px;padding:4px 8px}
.dd b{color:#888;font-weight:400}
.chk{display:inline-flex;gap:7px;align-items:center;white-space:nowrap} .chk i{width:15px;height:15px;border:1px solid #777;background:#fff;border-radius:2px}
.chk.on i{background:var(--acc);border-color:var(--acc);box-shadow:inset 0 0 0 3px #2a2d32}
.segs{display:inline-flex;border:1px solid #4a4f57;border-radius:6px;overflow:hidden}.segs span{white-space:nowrap;padding:4px 10px;background:#33373d;border-left:1px solid #4a4f57}
.segs span:first-child{border-left:none}.segs span.on{background:var(--acc);color:#10151b;font-weight:600}
.note{color:#c3c7cc;font-size:12px;margin-top:6px;max-width:520px}
/* profiles */
.plist{background:var(--panel);border:1px solid #4a4f57;border-radius:10px;padding:8px;width:520px}
.prow{display:flex;gap:10px;align-items:center;padding:6px 6px;border-radius:6px;border-left:3px solid transparent}
.prow.on{background:#ffffff10;border-left-color:var(--acc)}
.prow .sh2{font-weight:800;width:34px;color:#cfe0f2;font-size:12px}.prow .nm{width:110px;font-weight:600}
.prow .ds{color:#b9bec4;font-size:12px;flex:1}.prow .ct{color:#8f959c;font-size:12px}
.minis{display:flex;gap:1px;margin-top:3px} .minis img{width:16px;height:16px;border-radius:3px}
/* window */
.win{background:var(--bg);border:1px solid #000;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.wtop{display:flex;gap:8px;align-items:center;padding:8px;background:#24272b;border-bottom:1px solid #000}
.search{flex:1;background:#1a1c1f;border:1px solid #3d4249;border-radius:7px;padding:5px 10px;color:#8f959c}
.wbody{display:flex;min-height:0;flex:1}
.side{width:150px;background:#24272b;padding:8px 6px;display:flex;flex-direction:column;gap:2px;border-right:1px solid #000}
.nav{display:flex;gap:8px;align-items:center;padding:6px 6px;border-radius:6px;border-left:3px solid transparent;color:#d0d3d7}
.nav b{width:20px;height:20px;border-radius:5px;display:grid;place-items:center;color:#111;font-size:11px}
.nav.on{background:#ffffff10;color:#fff;font-weight:600}
.secl{color:#7d838b;font-size:11px;text-transform:uppercase;letter-spacing:.6px;margin:6px 6px 2px}
.main{flex:1;padding:10px;display:flex;flex-direction:column;gap:9px;min-width:0}
.head{border-radius:9px;padding:10px 12px}
.head h2{margin:0;font-size:17px}.why{color:#c9cdd2;font-size:12px;margin-top:2px}
.subt{display:flex;gap:2px;flex-wrap:wrap;margin-top:8px}.subt span{padding:5px 10px;border-radius:7px;color:#a2a7ae}
.subt span.on{background:#33373d;color:#fff}
.card{background:var(--card);border:1px solid #3d4249;border-radius:9px;padding:10px 12px;border-left:3px solid}
.card h3{margin:0 0 6px;font-size:13.5px;display:flex;gap:8px;align-items:center}
.card h3 .n{width:18px;height:18px;border-radius:50%;display:grid;place-items:center;color:#111;font-size:11px}
.tip{color:#a9aeb4;font-size:11.5px}
.bigtrack{position:relative;height:6px;background:#4a4f57;border-radius:3px;margin:12px 4px}
.bigtrack .f{position:absolute;left:50%;width:14%;height:6px;background:#9e70eb}.bigtrack .k{position:absolute;left:61%;top:-8px;width:22px;height:22px;border-radius:50%;background:#c8b3f5;border:3px solid #ffffff33}
.flow{display:flex;gap:5px;flex-wrap:wrap}
.sel{background:#24272b;border-radius:7px;padding:6px 9px;font-size:12px;color:#c9cdd2;display:flex;gap:6px;align-items:center}
.sel b{color:#fff}.dot{width:8px;height:8px;border-radius:50%;background:#5cc270;display:inline-block}
/* pie */
.pie{position:relative;width:470px;height:470px}
.ring{position:absolute;inset:40px;border-radius:50%;background:rgba(22,25,30,.92);border:1px solid #454f60}
.inner{position:absolute;left:50%;top:50%;width:150px;height:150px;margin:-75px;border-radius:50%;border:2px dashed #6f93bd88;display:grid;place-items:center;text-align:center;color:#c9cdd2;font-size:12px}
.inner b{display:block;font-size:15px;color:#fff}
.pt{position:absolute;display:flex;flex-direction:column;align-items:center;gap:3px;width:90px;margin-left:-45px;margin-top:-30px}
.pt .tb{width:40px;height:40px}.pt .tb img{width:34px;height:34px}
.pt .nm{background:#111418;border:1px solid #3b4048;border-radius:10px;padding:1px 8px;font-size:11.5px;white-space:nowrap}
.pt.hot .tb{outline:2px solid #fff}.pt.hot .nm{background:#f0ae33;color:#111;font-weight:700}
.ptop{position:absolute;left:50%;top:0;transform:translateX(-50%);display:flex;gap:4px}
.ptop span{background:#24272b;border:1px solid #4a4f57;border-radius:6px;padding:3px 8px;font-size:11.5px}.ptop span.on{background:var(--acc);color:#111;font-weight:700}
.pbot{position:absolute;left:50%;bottom:0;transform:translateX(-50%);display:flex;gap:3px;background:#24272b;border:1px solid #4a4f57;border-radius:8px;padding:4px}
/* dock */
.dock{width:242px;background:#1f2226;border:1px solid #000;border-radius:8px;overflow:hidden;font-size:12px}
.dh{padding:6px;background:#24272b;border-bottom:1px solid #000;display:flex;flex-direction:column;gap:5px}
.dpills{display:flex;gap:3px}.dpills span{flex:1;text-align:center;background:#33373d;border:1px solid #4a4f57;border-radius:5px;padding:3px 0;font-size:11px;font-weight:700}
.dpills span.on{background:var(--acc);color:#111}
.qs{display:flex;gap:3px;justify-content:space-between}.qs .tb{width:32px;height:32px}.qs .tb img{width:26px;height:26px}
.drawer{margin:5px 6px;border-radius:7px;border:1px solid #3d4249;border-left:3px solid;overflow:hidden}
.dhd{padding:5px 8px;font-weight:700;font-size:11.5px;display:flex;justify-content:space-between}
.split{display:flex;gap:3px;margin:3px 6px}.split .a{flex:3;background:#30343a;border:1px solid #444a52;border-radius:5px;padding:4px 7px;display:flex;gap:6px;align-items:center}
.split .a img{width:16px;height:16px;border-radius:3px}.split .b{flex:1;background:#2a2d32;border:1px solid #444a52;border-radius:5px;padding:4px;text-align:center;color:#bbb;font-size:10.5px}
.dfoot{display:flex;justify-content:space-between;padding:4px 8px;background:#24272b;border-top:1px solid #000;color:#b9bec4;font-size:11px}
.rail{width:72px;background:#1f2226;border:1px solid #000;border-radius:8px;padding:6px 0;display:flex;flex-direction:column;align-items:center;gap:3px}
.rail .tb{width:40px;height:40px}.rail .tb img{width:34px;height:34px}
/* search */
.k{background:var(--panel);border:1px solid #4a4f57;border-radius:12px;width:460px;padding:10px;box-shadow:0 14px 40px #0008}
.kin{background:#1a1c1f;border:1px solid var(--acc);border-radius:8px;padding:8px 10px;font-size:15px}
.kr{display:flex;gap:9px;align-items:center;padding:6px 8px;border-radius:7px}.kr.on{background:#ffffff12}
.kr img{width:24px;height:24px;border-radius:4px}.kr .c{margin-left:auto;font-size:11px;padding:1px 7px;border-radius:9px;color:#111;font-weight:600}
.kr .h{color:#8f959c;font-size:11.5px}
.shelf{display:flex;gap:2px;background:#444;padding:4px 6px;border-radius:4px;align-items:center;flex-wrap:nowrap}
.shelf img{width:26px;height:26px}.shelf .sep{width:1px;height:30px;background:#777;margin:0 4px}
"""


def blk(title, sub, body):
    return '<div class="blk"><h1>%s</h1><p class="sub">%s</p>%s</div>' % (title, sub, body)


def page():
    blocking = PROFILES[0][3]
    # 1. the bar
    tween_strip = strip("tween_prev", [
        ("Mode", segs(["Between keys", "From rest", "Mirror"], "Between keys")), ("", chk("Key it", True)),
        ("Overshoot", segs(["100%", "150%"], "100%")), ("Hotkeys", '<span class="tip">Alt+Shift+, / Alt+Shift+.</span>')])
    inb_strip = strip("inbetween_add", [("Step", dd("1 frame", 100)), ("Scope", dd("Selected controls", 150))])
    b1 = ('<div class="cap">1 · Row, profile Blocking - the Tween slider sits between Tween ◀ and ▶. '
          '<small>Right-click Tween ◀: its options open under the bar (right-click again: closed).</small></div>'
          + bar_row(blocking, strip="tween_prev") + '<br>' + tween_strip
          + '<div style="height:18px"></div><div class="cap">2 · Same bar, names on (Lbl) <small>- names on 2 lines, '
          'icons stay in line</small></div>' + bar_row(blocking[:9], 34, True)
          + '<div style="height:18px"></div><div class="cap">3 · Right-click Add inbetween <small>- the same strip, '
          'its real options (Step, Scope). One strip at a time.</small></div>' + bar_row(blocking, 28, strip="inbetween_add")
          + '<br>' + inb_strip)
    col = ('<div class="bar" style="width:auto"><div class="chrome" style="flex-direction:column;align-items:stretch">'
           '<div style="display:flex;gap:4px"><span class="grip">::</span><span class="px">34px</span><span class="btn sq">=</span></div>'
           '<div style="display:flex;gap:3px">' + "".join('<span class="seg%s">%s</span>' % (" on" if s == "C" else "", s) for s in "R2CG") + '</div>'
           + "".join('<span class="pill%s" style="border-left:3px solid %s">%s %d</span>' % (" on" if p[1] == "BLK" else "", "#9aa", p[1], len(p[3])) for p in PROFILES[:4])
           + '<span class="btn">▾ more</span></div><div style="display:grid;grid-template-columns:repeat(2,38px);gap:2px">'
           + "".join(tile(k, 34) for k in blocking[:6]) + '</div><div style="display:flex;justify-content:center;margin:4px 0">'
           + tweener(34, True) + '</div><div style="display:grid;grid-template-columns:repeat(2,38px);gap:2px">'
           + "".join(tile(k, 34) for k in blocking[6:]) + '</div></div>')
    grid = ('<div class="bar">' + chrome("grid", "ALL", len(ORDER), short=True, px=30) + '<div style="display:grid;'
            'grid-template-columns:repeat(13,34px);gap:2px">' + "".join(tile(k, 30) for k in ORDER) + '</div></div>')
    bar_blk = blk("5.8 preview · 1. The Animtool bar (the Rigtool favourites design)",
                  "The same bar as Gus_Rigtool's favourites: profiles, Row / 2R / Col / Grid, the size (24-52 px, or Ctrl + wheel), "
                  "names on / off, ✎ edit. The white corner = right-click has options. The real Animtool icons; the real option names.",
                  '<div class="row"><div>' + b1 + '</div></div><div style="height:22px"></div><div class="row"><div>'
                  '<div class="cap">4 · Column <small>(the vertical Tween with its ticks)</small></div>' + col + '</div><div>'
                  '<div class="cap">5 · Grid, profile All tools (' + str(len(ORDER)) + ') <small>- by category, never scrolls; shrinks if the screen is small</small></div>'
                  + grid + '</div></div>')
    # 2. profiles
    plist = '<div class="plist">' + "".join(
        '<div class="prow%s"><span class="sh2">%s</span><div style="flex:1"><div style="display:flex;gap:8px">'
        '<span class="nm">%s</span><span class="ds">%s</span><span class="ct">%d</span></div><div class="minis">%s</div></div></div>'
        % (" on" if i == 0 else "", s, n, d, len(ks), "".join('<img src="%s">' % png(k) for k in ks[:20]))
        for i, (n, s, d, ks) in enumerate(PROFILES)) + ('<div style="border-top:1px solid #4a4f57;margin:6px 0"></div>'
        '<div class="prow">+ New profile · Rename · Delete · Reset to these</div></div>')
    prof_blk = blk("2. The profiles I suggest (you can rename, add, remove)",
                   "8 to start. Each one remembers its own shape and size (Blocking as a row, All tools as a grid...). Your own profiles too.",
                   plist)
    # 3. window
    acc = "#5cc270"
    side = ('<div class="side">' + "".join('<div class="nav%s" style="%s"><b style="background:%s">%s</b>%s</div>' % (
        " on" if n == "Pose" else "", "border-left-color:%s" % c if n == "Pose" else "", c, i, n)
        for i, (n, c) in enumerate((("Pick & see", "#e15c8f"), ("Pose", acc), ("Keys & timing", "#f0ae33"),
                                    ("Spaces & props", "#48c2eb"), ("Limbs", "#33bdb3")), 1))
        + '<div style="margin-top:auto"></div><div class="nav"><b style="background:#8a9098">⚙</b>Settings</div></div>')
    cards = (
        '<div class="card" style="border-left-color:#9e70eb"><h3><span class="n" style="background:#9e70eb">1</span>Tween</h3>'
        + segs(["Between keys", "From rest", "Mirror"], "Between keys") + ' &nbsp;' + chk("Key it", True)
        + '<div class="bigtrack"><span class="f"></span><span class="k"></span></div><div class="flow">'
        + "".join('<span class="btn">%s</span>' % v for v in ("−100", "−50", "−25", "25", "50", "100"))
        + '</div><div class="tip" style="margin-top:6px">Drag: the pose between the keys around this frame. Let go: one key, one undo.</div></div>'
        '<div class="card" style="border-left-color:%s"><h3><span class="n" style="background:%s">2</span>Mirror · flip · reset</h3>'
        '<div class="flow"><span class="btn">Mirror L → R</span><span class="btn">R → L</span><span class="btn">Flip</span>'
        '<span class="btn">Reset</span><span class="btn">Reset all</span></div></div>'
        '<div class="card" style="border-left-color:%s;opacity:.85"><h3><span class="n" style="background:%s">3</span>Copy · paste pose ▸</h3></div>'
        % (acc, acc, acc, acc))
    win = ('<div class="win" style="width:490px;height:600px"><div class="wtop"><div class="search">Search any tool... (Ctrl+K)</div>'
           '<span class="btn sq">≡</span></div><div class="wbody">' + side + '<div class="main">'
           '<div class="head" style="background:linear-gradient(#2f4434,#2a2d32);border-top:3px solid %s"><h2>Pose</h2>'
           '<div class="why">Shape the pose: tween, mirror, reset, copy.</div><div class="subt"><span class="on">Tween & mirror</span>'
           '<span>Copy & paste</span><span>Mirror animation</span></div></div><div class="sel"><span class="dot"></span>'
           '<b>L_hand_ik_ctrl</b> · Hare · frame 14</div>' % acc + cards + '</div></div></div>')
    win_blk = blk("3. The Animtool window in the new look",
                  "The same frame as Gus_Rigtool: sidebar (Pick & see, Pose, Keys & timing, Spaces & props, Limbs, ⚙ Settings), "
                  "cards, Arrange, your section order, hide the sidebar. The old window stays as \"Legacy look\".",
                  '<div class="row">' + win + '<div class="note" style="max-width:420px"><b>Where today\'s sections go</b><br><br>'
                  '<b>Pick & see</b>: Picker and poses · Select · Selection sets · Body parts · View (arcs, ghosts) · Playblast<br><br>'
                  '<b>Pose</b>: Tween · Mirror / flip / reset · Copy / paste pose · Mirror animation<br><br>'
                  '<b>Keys & timing</b>: Keys · Tangents · Nudge · Copy / paste keys · Inbetweens · Offset · Retime · Cycles · '
                  'Bake / reduce · Curves · Push / pull / negate<br><br><b>Spaces & props</b>: Space switch · its key cleanup · '
                  'Temporary spaces · Attach props · Rotate order<br><br><b>Limbs</b>: IK / FK · Overlap · Jiggle · Teach a limb<br><br>'
                  '<b>⚙ Settings</b>: Options · Rig profile · Hotkeys · Bar, shelf and window · Crash backup · Update</div></div>')
    # 4. pie
    import math
    pie_keys = [("key", "N"), ("tween_next", "NE"), ("mirror", "E"), ("reset", "SE"), ("blocking", "S"),
                ("flip", "SW"), ("tween_prev", "W"), ("ikfk", "NW")]
    pts = ""
    for i, (k, _d) in enumerate(pie_keys):
        a = math.radians(-90 + 45 * i)
        x, y = 235 + 150 * math.cos(a), 235 + 150 * math.sin(a)
        pts += ('<div class="pt%s" style="left:%dpx;top:%dpx"><span class="tb" style="border-bottom-color:%s"><img src="%s"></span>'
                '<span class="nm">%s</span></div>' % (" hot" if k == "mirror" else "", x, y, COLOUR[k], png(k), NAME[k]))
    pie = ('<div class="pie"><div class="ring"></div><div class="inner"><div><b>Blocking</b>let go over a tool<br>to run it<br>'
           '<span style="color:#8f959c">1-8 switch profile</span></div></div>' + pts
           + '<div class="ptop">' + "".join('<span class="%s">%d %s</span>' % ("on" if i == 0 else "", i + 1, p[1]) for i, p in enumerate(PROFILES[:7]))
           + '</div><div class="pbot">' + "".join(tile(k, 26) for k in ("copy_keys", "paste_keys", "inbetween_add", "inbetween_remove", "tan_step")) + '</div></div>')
    pie_blk = blk("4. The pie: hold ` (backtick) over the viewport",
                  "Hold the key, move toward a tool, let go = it runs. Each tool's NAME UNDER its icon. Top: the profiles (press 1-8). "
                  "Bottom: the rest of the profile (more than 8 tools). Right-click a tool: the pie stays open with its options. "
                  "Needs a Maya fact first (does the hold-and-release key work in your Maya), then a try-it script and your screenshot.",
                  pie)
    # 5. dock + rail
    drawers = ""
    for key, open_rows in (("pose", [("mirror", "R → L"), ("flip", ""), ("reset", "All")]),
                           ("keys", [("key", "All"), ("blocking", "Scope"), ("tan_step", ""), ("nudge_left", "Step")]),
                           ("space", None), ("timing", None), ("curves", None), ("pick", None)):
        n, c, ks = CAT[key]
        drawers += ('<div class="drawer" style="border-left-color:%s"><div class="dhd" style="background:%s1f;color:%s">'
                    '<span>%s (%d)</span><span>%s</span></div>' % (c, c, c, n.upper(), len(ks), "▾" if open_rows else "▸"))
        for k, b in open_rows or []:
            drawers += ('<div class="split"><span class="a"><img src="%s">%s</span>%s</div>'
                        % (png(k), NAME[k], '<span class="b">%s</span>' % b if b else ""))
        drawers += '</div>' if not open_rows else '<div style="height:4px"></div></div>'
    dock = ('<div class="dock"><div class="dh"><div class="dpills">' + "".join('<span class="%s">%s</span>' % ("on" if i == 0 else "", p[1]) for i, p in enumerate(PROFILES[:4]))
            + '<span>▾</span><span>?</span><span>CB</span></div><div class="qs">' + "".join(tile(k, 32) for k in ("arcs", "hide_ctrls", "isolate", "hider", "ghosts", "playblast"))
            + '</div></div><div style="padding:6px 6px 0"><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3px">'
            + "".join('<span class="btn" style="border-top:2px solid %s;flex-direction:column;padding:3px 2px;font-size:11px;white-space:normal;text-align:center"><img src="%s" style="width:20px;height:20px;border-radius:3px">%s</span>' % (COLOUR[k], png(k), NAME[k]) for k in ("key", "mirror", "reset", "tween_prev", "inbetween_add", "inbetween_remove"))
            + '</div><div style="margin:6px 0">' + tweener(52).replace("width:213px", "width:100%") + '</div></div>' + drawers
            + '<div class="dfoot"><span><b style="color:#5cc270">●</b> L_hand_ik · f14 · IK</span><span>%d tools</span>' % len(ORDER) + '</div></div>')
    rail = '<div class="rail">' + "".join(tile(k, 40) for k in blocking[:8]) + '</div>'
    dock_blk = blk("5. The narrow dock (242 px) and its rail",
                   "Docked at the right of Maya. Top: profiles, search (?), colour-blind colours (CB), the Pick & see strip. Then your 6 pinned "
                   "tools, the Tween slider, and every tool in drawers by category; a tool with options shows its button on the right (75 / 25). "
                   "Made thinner than 135 px it turns into the rail: the profile's first 8 tools in one column.",
                   '<div class="row">' + dock + '<div><div class="cap">The rail (72 px)</div>' + rail + '</div></div>')
    # 6. search + settings + shelf
    res = [("offset_plus", "Offset +", "every key of the selection 1 frame later"),
           ("offset_minus", "Offset −", "1 frame earlier"), ("offset_back", "Back to original", "undo all offsets"),
           ("overlap", "Overlap", "follow-through, base to tip"), ("hide_ctrls", "Controls", "hide / show the controls")]
    srch = ('<div class="k"><div class="kin">off<span style="color:#6f93bd">|</span></div><div style="height:6px"></div>' + "".join(
        '<div class="kr%s"><img src="%s"><div><div>%s</div><div class="h">%s</div></div><span class="c" style="background:%s">%s</span></div>'
        % (" on" if i == 0 else "", png(k), n, h, COLOUR[k], [v[0] for v in CAT.values() if k in v[2]][0]) for i, (k, n, h) in enumerate(res))
        + '<div class="tip" style="margin-top:6px;padding:0 6px">↑ ↓ choose · Enter runs it · Shift+Enter opens its page · Esc closes</div></div>')
    sett = ('<div class="win" style="width:420px;padding:12px;gap:10px">'
            '<div class="card" style="border-left-color:#8a9098"><h3>Colours</h3>' + segs(["Normal", "Colour-blind safe"], "Normal")
            + '<div style="display:flex;gap:14px;margin-top:10px;flex-wrap:wrap">'
            + "".join('<span style="display:flex;flex-direction:column;gap:3px;align-items:center;font-size:10.5px;color:#bbb">'
                      '<span style="display:flex;gap:2px"><i style="width:22px;height:8px;background:%s;border-radius:2px"></i>'
                      '<i style="width:22px;height:8px;background:%s;border-radius:2px"></i></span>%s</span>' % (c, OKABE[k], n.split(" ")[0])
                      for k, (n, c, _ks) in CAT.items())
            + '</div><div class="tip" style="margin-top:6px">left: normal · right: colour-blind safe (Okabe-Ito) - for the bar, '
            'pie, dock, shelf and window.</div></div><div class="card" style="border-left-color:#8a9098"><h3>The pie</h3>'
            '<div class="orow"><span>Hold this key</span>' + segs(["` backtick", "F1", "\\"], "` backtick") + '</div>'
            '<div class="orow" style="margin-top:6px"><span>Pie size</span>' + segs(["Small", "Normal", "Big"], "Normal") + '</div>'
            '<div class="tip" style="margin-top:6px">Uses the Gus_Animtool hotkey set (Maya\'s own can\'t change). '
            'Off until you turn it on.</div></div></div>')
    shelf = '<div class="shelf">'
    for i, (_k, (_n, _c, ks)) in enumerate(CAT.items()):
        if i:
            shelf += '<span class="sep"></span>'
        shelf += "".join('<img src="%s">' % png(k) for k in ks)
    shelf += '</div>'
    misc_blk = blk("6. Search, Settings, the shelf",
                   "Ctrl+K anywhere in the Animtool (or ? on the dock): type a few letters, Enter runs the tool.",
                   '<div class="row"><div><div class="cap">Search (Ctrl+K)</div>' + srch + '</div><div><div class="cap">'
                   'Settings > new parts</div>' + sett + '</div></div><div style="height:20px"></div><div class="cap">The '
                   'Gus_Animtool shelf: one row, a line between categories, the same order as the bar and the window</div>'
                   '<div>' + shelf + '</div>')
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Animtool 5.8 Preview</title><style>' + CSS
            + '</style></head><body>' + bar_blk + prof_blk + win_blk + pie_blk + dock_blk + misc_blk + '</body></html>')


if __name__ == "__main__":
    open(os.path.join(HERE, "anim58.html"), "w").write(page())
    print("anim58.html")
