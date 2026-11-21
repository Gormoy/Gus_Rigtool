# 5.7.8.1: Reset order at once (no redrawing of the page), and Test this release keeps your own order (5.7.8's
# checks wiped it - and took it for the tool's order: the one FAIL); the order checks go over every page once
exec(open("test_5721.py").read().split('with mock.patch.object(QT, "maya_widget"')[0])
import copy, time
from gus_rigtool.newui import theme
from gus_rigtool.core import utils

def settle():
    for _ in range(3):
        app.processEvents()

# --- 1. Reset order: at once, the page not drawn again
utils.save_setting(W.STATE_KEY, {})
f = W.Frame(); f.resize(700, 1200); f.show()
sub = ("controls_tab", 2)
f.go(sub, as_tool=True); settle()
a = f.areas["controls"]
first = [c.title for c in a._visual(sub)]
cards = list(a._cards_of(sub))
last = a._visual(sub)[-1]
last.moved.emit(last.title, "@Move to top"); settle()
with mock.patch.object(W.Frame, "rebuild", lambda self, key: (_ for _ in ()).throw(AssertionError("redrawn"))):
    last.moved.emit(last.title, "@Reset order"); settle()
check("Reset order: the tool's own order at once (the page isn't drawn again - 5.7.8 did, slowly)",
      [c.title for c in a._visual(sub)] == first and all(c in cards for c in a._cards_of(sub)))
f2 = W.Frame(); f2.resize(700, 1200); f2.show()
f2.go(sub, as_tool=True); settle()
a2 = f2.areas["controls"]
c = a2._visual(sub)[-1]
c.moved.emit(c.title, "@Move to top"); settle()
f3 = W.Frame(); f3.resize(700, 1200); f3.show(); f3.go(sub, as_tool=True); settle()
a3 = f3.areas["controls"]
a3._cards_of(sub)[0].moved.emit(a3._cards_of(sub)[0].title, "@Reset order"); settle()
check("...also in a window opened with your order already on it (Reset goes to the tool's order, not yours)",
      [c.title for c in a3._visual(sub)] == first)
for fr in (f, f2, f3):
    fr.close()

# --- 2. Test this release keeps your order, and its order checks pass with your order on
mine = list(reversed(first))
st = W._state(); st["order"] = {"controls_tab|2": mine}; W._save_state(st)
yours = copy.deepcopy(W._state()["order"])
t = time.time()
with mock.patch.object(QT, "maya_widget", lambda name, kind="layout": hosts.get(name)):
    rep = Report("x")
    WC.new_look(rep)
    WC.arrange(rep)
took = time.time() - t
fails = [r[2] for r in rep.rows if r[1] == FAIL]
check("the new-look and arrange checks pass with your own order on Edit shape (5.7.8: 1 FAIL)", not fails)
if fails:
    print("  ", fails[:5])
check("...your order is put back after them", W._state().get("order") == yours)
names = [r[2] for r in rep.rows]
check("...every page goes through once (in your look), the other look only Edit shape",
      len([n for n in names if "work on every page" in n]) == 1 and
      len([n for n in names if n.endswith("an Arrange button in the header")]) == 2)
check("...the order isn't checked twice (it's in 'arrange' only now)", not [n for n in names if
                                                                          "right-click > Move to top" in n])
print("%d/%d passed" % (sum(ok), len(ok)))
