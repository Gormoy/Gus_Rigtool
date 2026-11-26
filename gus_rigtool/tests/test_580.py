# 5.8.0: the Animtool's groundwork. The one list of tools completed (categories and colours - the icons' own -, the
# two windows only the bar shows, every tool's right-click options with the tools' own defaults, the profiles of
# the preview); the new look's building blocks moved into the Animtool (gus_animtool/look), Gus_Rigtool using the
# very same modules from its own copy; the picker updated a moment after a change and not while playing; the
# Animtool window's title set every time it's built.
exec(open("test_570.py").read().split("# --- 1.")[0])
import re
from unittest import mock
sys.path.insert(0, os.path.join(ROOT, "anim"))
from gus_animtool import actions as AC, anim as A, bar as B, ui as AUI
ANIM = os.path.join(ROOT, "anim", "gus_animtool")

# --- 1. the new look in the Animtool, one copy for both tools
from gus_rigtool.newui import theme, widgets, icons
from gus_rigtool.newui import qt as nqt
look = os.path.join(ANIM, "look")
check("Gus_Rigtool's theme / widgets / icons / qt are the Animtool's own files (one copy)",
      all(os.path.samefile(m.__file__, os.path.join(look, n + ".py"))
          for m, n in ((theme, "theme"), (widgets, "widgets"), (icons, "icons"), (nqt, "qt"))))
check("...the very same module whichever name is used (a change in one is a change in the other)",
      sys.modules["gus_rigtool.newui.theme"] is sys.modules["gus_rigtool._look.theme"])
check("...Gus_Rigtool's old names are only pointers now", all(
    len(open(os.path.join(ROOT, "newui", n + ".py")).read().splitlines()) < 10 for n in ("qt", "theme", "widgets",
                                                                                          "icons")))
from gus_animtool.look import theme as at, widgets as aw
check("the Animtool loads them itself too (an animator's copy has no Gus_Rigtool)",
      os.path.samefile(at.__file__, theme.__file__) and hasattr(aw, "Card"))
check("...nothing in the look folder needs Gus_Rigtool (no import of it)", not any(
    re.search(r"^\s*(from|import) gus_rigtool", open(os.path.join(look, f)).read(), re.M)
    for f in os.listdir(look) if f.endswith(".py")))

# --- 2. the one list
every = AC.every("bar")
cats = dict((k, (n, c, cb)) for k, n, c, cb in AC.CATEGORIES)
check("every tool has a category (8: Pick & see, Pose, Tween, Keys & tangents, Timing & cycles, Graph curves, "
      "Spaces & props, Windows)", len(AC.CATEGORIES) == 8 and all(AC.category(k) in cats for k in every))
try:
    from PIL import Image
    off = []
    for k in every:
        path = os.path.join(ANIM, "icons", "ga_%s.png" % k)
        px = Image.open(path).convert("RGB").getpixel((16, 29))
        want = AC.colour(k).lstrip("#")
        want = tuple(int(want[i:i + 2], 16) for i in (0, 2, 4))
        if max(abs(a - b) for a, b in zip(px, want)) > 12:
            off.append(k)
    check("...its colour is its icon's own (the line under each icon)", not off)
    for k in off:
        print("   colour differs:", k)
except ImportError:
    check("...its colour is its icon's own (the line under each icon)", True)
check("...and a colour-blind safe colour", all(AC.colour(k, True).startswith("#") for k in every) and
      AC.colour("mirror", True) != AC.colour("mirror"))
check("the two windows only the bar shows are in the list, right after their tool",
      every[every.index("release") + 1] == "attach_window" and every[every.index("arcs") + 1] == "arcs_panel" and
      "attach_window" not in AC.every("shelf"))
check("the bar reads the one list (its own copy is gone)", B.all_keys() == every and
      B.EXTRA == {"release": "attach_window", "arcs": "arcs_panel"} and B.group_of("arcs_panel") == "view")
known = set(every) | {"bar"}
used = {"toolbar": AC.TOOLBAR_DEFAULT, "window icons": AUI.QUICK, "menus": list(AC.MENUS),
        "options": list(AC.OPTIONS), "profiles": [k for _n, _s, ks in AC.PROFILES for k in ks]}
missing = dict((w, [k for k in ks if k not in known]) for w, ks in used.items())
check("every tool the toolbar, the window's icons, the menus, the options and the profiles name exists",
      not any(missing.values()))
for w, ks in missing.items():
    if ks:
        print("   %s: %s" % (w, ks))
check("the profiles of the preview: Blocking, Splining, Polish, Spaces & props, Cycles, Review, Clean-up",
      [n for n, _s, _k in AC.PROFILES] == ["Blocking", "Splining", "Polish", "Spaces & props", "Cycles", "Review",
                                            "Clean-up"] and len(AC.PROFILES[0][2]) == 13)

# --- 3. the right-click options: real options, the tools' own defaults
src = "".join(open(os.path.join(ANIM, f)).read() for f in os.listdir(ANIM) if f.endswith(".py") and
              f != "actions.py")
wrong = []
for name, default in AC.OPTION_DEFAULTS.items():
    found = set(re.findall(r'opt\("%s", (-?[0-9.]+)\)' % name, src))
    if not found or any(float(f) != float(default) for f in found):
        wrong.append((name, default, sorted(found)))
check("every option in the right-click strips is one the tools really use, with the same default (%d options)"
      % len(AC.OPTION_DEFAULTS), not wrong and set(o[0] for v in AC.OPTIONS.values() for o in v) ==
      set(AC.OPTION_DEFAULTS))
for w in wrong:
    print("   option %s: %s here, %s in the tools" % w)
opts = {"inbetween_step": 3}
with mock.patch.object(A, "opt", lambda k, d: opts.get(k, d)):
    got = AC.options("inbetween_remove")
check("a tool's options with what's set now (Remove inbetween = Add's: step 3, scope 1)",
      [(o[0], o[4]) for o in got] == [("inbetween_step", 3), ("inbetween_scope", 1)])

# --- 4. the picker: a moment after a change, not while playing
from gus_animtool.look import later as L
calls = []
class Stub(object):
    pass
from gus_animtool import pickerqt as PQ
p = Stub()
p.selection_changed = lambda: calls.append("selection")
p.time_changed = lambda: calls.append("time")
p.changed_later = lambda what: PQ.Picker.changed_later(p, what)
p._catch_up = lambda: PQ.Picker._catch_up(p)
with mock.patch.object(L, "in_maya", lambda: False):
    p.changed_later("time")
    p.changed_later("selection")
check("outside Maya (the tests): at once", calls == ["time", "selection"])
timers = []
class FakeTimer(object):
    def __init__(self, owner=None):
        self.ms = []
        self.timeout = type("S", (), {"connect": lambda s, fn: setattr(self, "fire", fn)})()
        timers.append(self)
    def setSingleShot(self, on):
        pass
    def start(self, ms):
        self.ms.append(ms)
del calls[:]
playing = {"on": False}
with mock.patch.object(L, "in_maya", lambda: True), mock.patch.object(L.QtCore, "QTimer", FakeTimer), \
        mock.patch.object(L, "playing", lambda: playing["on"]):
    p._later = None
    for _ in range(5):
        p.changed_later("selection")                     # a drag-select: 5 changes
    t = timers[-1]
    check("in Maya: 5 quick changes -> one timer, restarted (80 ms after the last one), nothing yet",
          len(timers) == 1 and t.ms == [80] * 5 and calls == [])
    t.fire()
    check("...then one update", calls == ["selection"])
    playing["on"] = True
    p.changed_later("time"); p.changed_later("time")
    t.fire()
    check("while playing: no update, it looks again in 300 ms", calls == ["selection"] and t.ms[-1] == 300)
    playing["on"] = False
    t.fire()
    check("playback stopped: it catches up once", calls == ["selection", "time"])
pq = open(os.path.join(ANIM, "pickerqt.py")).read()
check("the picker's Maya hooks (selection, every frame) go through it",
      'changed_later("selection")' in pq and 'changed_later("time")' in pq and
      "_state[\"widget\"].time_changed()]" not in pq)

# --- 5. the window's title, Test this release
ui_src = open(os.path.join(ANIM, "ui.py")).read()
b = ui_src[ui_src.index("def build():"):]
check("the Animtool window's title is set every time it's built (5.7.12's Test this release: an old title)",
      b.index('label="Gus Animtool %s" % gus_animtool.__version__') < b.index('if cmds.formLayout(P + "Root", '
                                                                            'exists=True):'))
wc = open(os.path.join(ROOT, "realmaya", "window_checks.py")).read()
check("Test this release: the picker waits while playing, catches up after", "def picker_waits" in wc and
      '("picker waits", picker_waits)' in wc)
print("%d/%d passed" % (sum(ok), len(ok)))
