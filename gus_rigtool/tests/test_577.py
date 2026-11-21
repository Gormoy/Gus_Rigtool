# 5.7.7: the new look (C6) beside today's (Settings > Window > Look), the Toolbox in the new window, and your own
# section order per tab (drag a section's title, or right-click it: Move up / Move down / Move to top / Reset order)
exec(open("test_570.py").read().split("# --- 1.")[0])
from unittest import mock
from gus_rigtool.newui import window as W, widgets
from gus_rigtool import main as M
from gus_rigtool.core import utils

def set_look(name):
    utils.save_setting(theme.LOOK_KEY, name)
    theme.load_look()

# --- 1. the Look switch: today's look unless you choose the new one; it is remembered
utils.save_setting(theme.LOOK_KEY, None)
check("first time: today's look (5.7)", theme.load_look() == "today" and not theme.new_look())
with mock.patch.object(cmds, "evalDeferred", lambda f: None, create=True):
    M.use_look("new")
check("Settings > Window > New look: saved, the window opens again in it", theme.load_look() == "new")
with mock.patch.object(cmds, "evalDeferred", lambda f: None, create=True):
    M.use_look("today")
check("...Today's look: back", theme.load_look() == "today")

# --- 2. both looks: the same controls on every page of the redone areas (nothing lost, nothing twice)
f0 = W.Frame()
tools = []
for key in W.NEW_LOOK:
    for x in W.Area(f0, key).subs:
        if x[0] not in tools:
            tools.append(x[0])
f0.close()
def inventory(key):
    rec = record.record(registry.builder(key), "q7_%s_" % key)
    page = render.Page(key, rec, theme.colour("build"))
    page.widget = page.build()
    return page, sorted(n for _k, n, _l, _h in page.inventory)
lost, twice, folds, chips = [], [], [], 0
for key in tools:
    set_look("today")
    _p, today = inventory(key)
    set_look("new")
    page, new = inventory(key)
    lost += ["%s: %s" % (key, n) for n in today if n not in new]
    twice += ["%s: %s" % (key, n) for n in set(new) if new.count(n) > 1]
    folds += [(key, fo) for fo in page.widget.findChildren(widgets.Fold)]
check("new look: every control of today's look is there, on all %d pages" % len(tools), not lost and len(tools) > 15)
if lost:
    print("   lost:", lost[:10])
check("...and none twice", not twice)

# --- 3. Options folds: closed, with what's set beside them
opts = [(k, fo) for k, fo in folds if fo.title == "Options"]
check("rarely changed choices fold into 'Options (n)' (%s)" % ("on many sections" if len(opts) > 10 else len(opts)),
      len(opts) > 10)
check("...closed at first, the count on the button", all(not fo.body.isVisibleTo(fo) for _k, fo in opts) and
      all("Options (" in fo.button.text() for _k, fo in opts))
said = [fo for _k, fo in opts if fo.words.text().strip()]
check("...the summary says what's set (all but folds of number fields)", len(said) >= len(opts) - 2)
check("...in short words, none twice", all(len(fo.words.text().split("  ·  ")) == len(set(fo.words.text().split(
    "  ·  "))) for fo in said))
k0, fo = opts[0]
fo.toggle()
check("...click: open", fo.body.isVisibleTo(fo))
fo.toggle()
check("Presets in one fold", any(fo.title == "Presets" for _k, fo in folds))

# --- 4. the window in the new look: state tags on the step titles, all steps open, nothing cut off
f = W.Frame(); f.resize(700, 1100); f.show()
f.go(("face", "Build the face"), as_tool=True); app.processEvents()
cards = [c for c in f.areas["build"].findChildren(widgets.Card) if c.isVisibleTo(f)]
tagged = [c for c in cards if c.chip.isVisibleTo(f) and c.chip.text().strip()]
check("Face: step lights shown as a tag on the title line (✓ Made / ● Ready / To do)", len(tagged) >= 5 and
      all(any(w in c.chip.text() for w in ("Made", "Ready", "To do")) for c in tagged))
steps = []
for sub in [("face", "Build the face"), ("ribbon", "Make a ribbon")]:
    f.go(sub, as_tool=True); app.processEvents()
    steps += [c for c in f.areas["build"].pages[sub[0]].cards if c.isVisibleTo(f) and c.chip.text().strip()]
check("all steps open (Face, Ribbon)", steps and not [c.title for c in steps if c.closed])
check("the status line says what's selected and where you are", "selected" in f.status.text() and "›" in
      f.status.text())
f.go(("controls_tab", 2), as_tool=True); app.processEvents()
check("...with the sub-page's name (Controls › Edit shape)", f.status.text().endswith("Edit shape"))

crops = {}
for key in W.NEW_LOOK:
    a = f._area(key)
    for sub in [tuple(x[:2]) for x in a.subs]:
        for width in (300, 420, 700):
            f.resize(width, 1100)
            f.go(sub, as_tool=True)
            for _ in range(3):
                app.processEvents()
            got = W.cut_off(f.areas[key])
            if got:
                crops["%s %s@%d" % (key, sub, width)] = got[:3]
check("new look: nothing cut off on any page, 300 / 420 / 700 px", not crops)
if crops:
    print("  ", list(crops.items())[:4])

# --- 5. the Toolbox in the new window: Select · Groups · Mirror · Rename · Pivots (Move / Remember & reset)
f.resize(700, 1100)
f.go(("select", None), as_tool=True); app.processEvents()
tb = f.areas["toolbox"]
labels = [x[2] for x in tb.subs]
check("Toolbox: Select · Groups · Mirror · Rename · Pivots: Move · Remember & reset", labels ==
      ["Select", "Groups", "Mirror", "Rename", "Move", "Remember & reset"])
for sub in [tuple(x[:2]) for x in tb.subs]:
    f.go(sub, as_tool=True); app.processEvents()
page = tb.pages["mirror"]
check("Mirror is drawn (its number fields read back right)", page.cards)
f.resize(300, 1100)
grp = [s for s in tb.subs if "group" in s[0]][0]
f.go(tuple(grp[:2]), as_tool=True)
for _ in range(3):
    app.processEvents()
check("Groups fits 300 px (a long choice no longer widens it)", not W.cut_off(tb))

# --- 6. your own order: Edit shape, Size and turn above the swap-shape grid (Gus's example)
f.resize(760, 1500)
sub = ("controls_tab", 2)
f.go(sub, as_tool=True); app.processEvents()
a = f.areas["controls"]
first = [c.title for c in a._visual(sub)]
mv = [c for c in a._cards_of(sub) if c.title.startswith("Move the shape")][0]
mv.moved.emit(mv.title, "@Move to top"); app.processEvents()
sz = [c for c in a._cards_of(sub) if c.title.startswith("Size")][0]
sz.moved.emit(sz.title, first[0]); app.processEvents()               # dropped on the grid's title
now = [c.title for c in a._visual(sub)]
check("Move to top, and drop 'Size and turn' on the swap-shape grid: both above it",
      now[0].startswith("Move the shape") and now[1].startswith("Size") and now[2] == first[0])
check("...nothing lost", sorted(now) == sorted(first))
check("...the numbers follow the new order", [c.num.text() for c in a._visual(sub)[:2]] == ["1", "2"])
up = [c for c in a._cards_of(sub) if c.title == now[3]][0]
up.moved.emit(up.title, "@Move up"); app.processEvents()
check("Move up: one place up", [c.title for c in a._visual(sub)][2] == now[3])
dn = [c for c in a._cards_of(sub) if c.title == now[3]][0]
dn.moved.emit(dn.title, "@Move down"); app.processEvents()
check("Move down: back", [c.title for c in a._visual(sub)] == now)
f2 = W.Frame(); f2.resize(760, 1500); f2.show(); f2.go(sub, as_tool=True); app.processEvents()
check("remembered: a new window (restart) shows your order", [c.title for c in f2.areas["controls"]._visual(sub)]
      == now)
other = ("controls_tab", 1)
f2.go(other, as_tool=True); app.processEvents()
check("...per tab: Make keeps the tool's order", [c.title for c in f2.areas["controls"]._visual(other)] ==
      [c.title for c in a._visual(other)] if other in [tuple(x[:2]) for x in a.subs] else True)
f2.go(sub, as_tool=True); app.processEvents()
c = f2.areas["controls"]._cards_of(sub)[0]
c.moved.emit(c.title, "@Reset order"); app.processEvents()
check("Reset order: the tool's own order again", [c.title for c in f2.areas["controls"]._visual(sub)] == first)

set_look("today")
f3 = W.Frame(); f3.resize(760, 1500); f3.show(); f3.go(sub, as_tool=True); app.processEvents()
a3 = f3.areas["controls"]
c = [c for c in a3._cards_of(sub) if c.title.startswith("Size")][0]
c.moved.emit(c.title, "@Move to top"); app.processEvents()
check("today's look: the order works there too", [c.title for c in a3._visual(sub)][0].startswith("Size"))
c.moved.emit(c.title, "@Reset order"); app.processEvents()
print("%d/%d passed" % (sum(ok), len(ok)))
