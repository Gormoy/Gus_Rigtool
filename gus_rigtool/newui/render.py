"""
Drawing a recorded page in the 5.7 look (record.py writes it down; this draws it).

Every control keeps its name: a Field answers the tool's own queries and edits (proxy.py sends them here), and
every command runs the tool's own callback - so the page does exactly what it did in the old window.
Sections become numbered cards (closed ones say what's inside), rows wrap instead of cropping, a label / field
pair puts the label above the field when narrow, the main button is the area's big button.
"""

import re

from gus_rigtool.newui import proxy, record, theme, widgets
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
MAIN_BG = (0.26, 0.42, 0.56)
DANGER_WORDS = ("delete", "remove", "back to guides", "clear", "unlink", "forget")
SKIPPED = "skipped"


def _close(a, b, tol=0.02):
    try:
        return all(abs(float(x) - float(y)) < tol for x, y in zip(a, b))
    except (TypeError, ValueError):
        return False


def _hex(rgb):
    try:
        return "#%02x%02x%02x" % tuple(int(max(0.0, min(1.0, float(c))) * 255) for c in rgb[:3])
    except (TypeError, ValueError):
        return None


def _call(fn, *args):
    """A Maya-style callback: Maya gives buttons a bool, check boxes their value, menus the picked label..."""
    if fn is None:
        return None
    if isinstance(fn, str):
        try:
            import maya.mel as mel
            return mel.eval(fn)
        except Exception:
            return None
    try:
        return fn(*args)
    except TypeError:
        return fn()


# --------------------------------------------------------------------------- a named control in the new window
class Field(object):
    """One control of the page: answers query / edit like Maya, keeps its value for the tool's functions."""

    def __init__(self, page, node, widget, kind=None):
        self.page, self.node, self.widget = page, node, widget
        self.kind = kind or node.kind
        self.items = [dict(i) for i in node.items]       # a menu's items (label, command, _name)
        self.list_items = list(node.kw.get("_items", []))
        self.alive = True
        self.card = None
        page.fields[node.name] = self
        proxy.REGISTRY[node.name] = self
        for i in self.items:
            proxy.REGISTRY[i["_name"]] = _Item(self, i)

    # -------------------------------------------------- Maya's calls
    def cmd(self, kind, args, k):
        if kind == "menuItem":
            return self.add_item(k)
        if k.get("exists") or k.get("ex"):
            return self.alive
        if k.get("query") or k.get("q"):
            for key in k:
                if key not in ("query", "q"):
                    return self.query(key)
            return None
        if k.get("edit") or k.get("e"):
            for key, v in k.items():
                if key not in ("edit", "e"):
                    self.edit(key, v)
            return self.node.name
        return self.node.name

    def query(self, key):
        w, kind = self.widget, self.kind
        if key in ("exists", "ex"):
            return self.alive
        if key in ("enable", "en"):
            return w.isEnabled()
        if key in ("manage", "m", "visible", "vis"):
            return not w.isHidden()
        if key in ("label", "l"):
            return self._label()
        if key in ("annotation", "ann"):
            return w.toolTip()
        if key in ("text", "tx"):
            return self._text()
        if key in ("value", "v"):
            if kind in ("optionMenu", "optionMenuGrp"):
                i = self._index()
                return self.items[i].get("label") if 0 <= i < len(self.items) else None
            return self._value()
        if key in ("select", "sl"):
            if isinstance(w, QtWidgets.QRadioButton):
                return w.isChecked()
            return self._index() + 1
        if key in ("numberOfItems", "ni"):
            return len(self.items) if kind in ("optionMenu", "optionMenuGrp") else len(self.list_items)
        if key in ("itemListLong", "ill"):
            return [i["_name"] for i in self.items] or None
        if key in ("itemListShort", "ils"):
            return [i.get("label") for i in self.items] or None
        if key in ("allItems", "ai"):
            return list(self.list_items) or None
        if key in ("selectIndexedItem", "sii"):
            got = [w.row(i) + 1 for i in w.selectedItems()] if isinstance(w, QtWidgets.QListWidget) else []
            return sorted(got) or None
        if key in ("selectItem", "si"):
            got = [i.text() for i in w.selectedItems()] if isinstance(w, QtWidgets.QListWidget) else []
            return got or None
        if key in ("selectTabIndex", "sti"):
            return self.page.tab_index(self.node.name)
        if key in ("childArray", "ca"):
            return [c.name for c in self.node.children] or None
        if key in ("fullPathName", "fpn"):
            return self.node.name
        if key in ("width", "w"):
            return w.width()
        if key in ("height", "h"):
            return w.height()
        if key in ("collapse", "cl"):
            return getattr(w, "closed", False)
        if key in ("rgbValue", "rgb"):
            return list(self.node.kw.get("rgbValue") or self.node.kw.get("rgb") or (1.0, 1.0, 1.0))
        if isinstance(w, _Numbers):
            if key in ("value", "v"):
                return w.values()
            m = re.match(r"v(?:alue)?([1-4])$", key)
            if m:
                return w.get(int(m.group(1)))
        return self.node.kw.get(key)

    def edit(self, key, v):
        w, kind = self.widget, self.kind
        m = re.match(r"v(?:alue)?([1-4])$", key) if isinstance(w, _Numbers) else None
        if m or (isinstance(w, _Numbers) and key in ("value", "v")):
            vals = [v] if m else list(v if isinstance(v, (list, tuple)) else [v])
            for i, x in enumerate(vals):
                w.set(int(m.group(1)) if m else i + 1, x)
            return self.node.name
        if key in ("enable", "en"):
            w.setEnabled(bool(v))
        elif key in ("manage", "m", "visible", "vis"):
            w.setVisible(bool(v))
        elif key in ("label", "l"):
            self._set_label(v)
        elif key in ("annotation", "ann"):
            w.setToolTip(str(v))
        elif key in ("text", "tx"):
            self._set_text(v)
        elif key in ("value", "v"):
            if kind in ("optionMenu", "optionMenuGrp"):
                labels = [i.get("label") for i in self.items]
                if v not in labels:
                    raise RuntimeError("Value is out of range: %s" % v)
                self._set_index(labels.index(v))
            else:
                self._set_value(v)
        elif key in ("select", "sl") and isinstance(w, QtWidgets.QRadioButton):
            w.setChecked(bool(v))
        elif key in ("select", "sl"):
            n = len(self.items) if kind in ("optionMenu", "optionMenuGrp") else None
            if n is not None and not 1 <= int(v) <= n:
                raise RuntimeError("Value is out of range: %s" % v)
            self._set_index(int(v) - 1)
        elif key in ("removeAll", "ra"):
            self.list_items = []
            if isinstance(w, QtWidgets.QListWidget):
                w.clear()
        elif key in ("append", "a"):
            for t in (v if isinstance(v, (list, tuple)) else [v]):
                self.list_items.append(t)
                if isinstance(w, QtWidgets.QListWidget):
                    w.addItem(str(t))
        elif key in ("removeItem", "ri"):
            if v in self.list_items:
                i = self.list_items.index(v)
                self.list_items.pop(i)
                if isinstance(w, QtWidgets.QListWidget):
                    w.takeItem(i)
        elif key in ("removeIndexedItem", "rii"):
            for i in sorted(v if isinstance(v, (list, tuple)) else [v], reverse=True):
                if 0 < i <= len(self.list_items):
                    self.list_items.pop(i - 1)
                    if isinstance(w, QtWidgets.QListWidget):
                        w.takeItem(i - 1)
        elif key in ("selectIndexedItem", "sii"):
            if isinstance(w, QtWidgets.QListWidget):
                for i in (v if isinstance(v, (list, tuple)) else [v]):
                    it = w.item(int(i) - 1)
                    if it is not None:
                        it.setSelected(True)
        elif key in ("selectItem", "si"):
            if isinstance(w, QtWidgets.QListWidget):
                for t in (v if isinstance(v, (list, tuple)) else [v]):
                    for it in w.findItems(str(t), Qt.MatchExactly):
                        it.setSelected(True)
        elif key in ("deselectAll", "da"):
            if isinstance(w, QtWidgets.QListWidget):
                w.clearSelection()
        elif key in ("selectTabIndex", "sti"):
            self.page.set_tab(self.node.name, int(v))
        elif key in ("collapse", "cl"):
            if hasattr(w, "set_closed"):
                w.set_closed(bool(v))
        elif key in ("backgroundColor", "bgc"):
            hx = _hex(v)
            if self.kind == "button" and hx and not self._label():
                w.setStyleSheet("QPushButton { background: %s; border-radius: 5px; }" % hx)
        elif key == "_level":
            w.setStyleSheet("QLabel { background: %s; border-radius: 6px; padding: 6px 8px; }" %
                            theme.LEVEL.get(v, theme.LEVEL["idle"]))
            self.level = v
            card = w.parentWidget()                      # 5.7.4: a step's light marks its card (made / ready)
            while card is not None and not isinstance(card, widgets.Card):
                card = card.parentWidget()
            if card is not None and hasattr(card, "set_state") and not card.property("inner") == "true":
                card.set_state(v)
        elif key in ("rgbValue", "rgb"):
            self.node.kw["rgbValue"] = v
            hx = _hex(v)
            sw = getattr(w, "swatch", w)
            if hx and isinstance(sw, QtWidgets.QAbstractButton):
                sw.setStyleSheet("QPushButton { background: %s; border-radius: 5px; border: 1px solid #0006; }" % hx)
        elif key in ("tabLabel", "tl"):
            pass
        else:
            self.node.kw[key] = v
        return self.node.name

    def delete(self):
        self.alive = False
        proxy.REGISTRY.pop(self.node.name, None)
        try:
            self.widget.deleteLater()
        except RuntimeError:
            pass

    # -------------------------------------------------- menus
    def add_item(self, k):
        if k.get("query") or k.get("edit") or k.get("exists"):
            return None
        self.page.count += 1
        item = dict(k)
        item["_name"] = "%s__item%d" % (self.node.name, self.page.count)
        self.items.append(item)
        proxy.REGISTRY[item["_name"]] = _Item(self, item)
        self._refill()
        return item["_name"]

    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
            self._refill()

    def _refill(self):
        w = self.widget
        if isinstance(w, QtWidgets.QComboBox):
            cur = w.currentIndex()
            w.blockSignals(True)
            w.clear()
            w.addItems([str(i.get("label", "")) for i in self.items])
            w.setCurrentIndex(min(max(cur, 0), len(self.items) - 1))
            w.blockSignals(False)
        elif isinstance(w, widgets.Segmented):        # a menu whose items change: becomes a drop-down list
            combo = _combo(self, self.items, 0)
            lay = w.parentWidget().layout() if w.parentWidget() else None
            if lay is not None:
                i = lay.indexOf(w)
                lay.insertWidget(i, combo) if isinstance(lay, QtWidgets.QBoxLayout) else lay.addWidget(combo)
                w.hide()
            self.widget = combo

    # -------------------------------------------------- values
    def _label(self):
        w = self.widget
        if isinstance(w, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            return w.text().strip()
        return self.node.kw.get("label")

    def _set_label(self, v):
        w = self.widget
        if isinstance(w, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            w.setText(str(v).strip() if isinstance(w, QtWidgets.QAbstractButton) else str(v).lstrip())
        self.node.kw["label"] = v

    def _text(self):
        w = self.widget
        if isinstance(w, QtWidgets.QLineEdit):
            return w.text()
        if isinstance(w, QtWidgets.QPlainTextEdit):
            return w.toPlainText()
        return self.node.kw.get("text", "")

    def _set_text(self, v):
        w = self.widget
        if isinstance(w, QtWidgets.QLineEdit):
            w.setText(str(v))
        elif isinstance(w, QtWidgets.QPlainTextEdit):
            w.setPlainText(str(v))
        self.node.kw["text"] = v

    def _value(self):
        w = self.widget
        if isinstance(w, QtWidgets.QCheckBox):
            return w.isChecked()
        if isinstance(w, QtWidgets.QLineEdit):
            t = w.text().strip()
            try:
                return int(float(t)) if self.kind == "intField" else float(t)
            except ValueError:
                return 0 if self.kind == "intField" else 0.0
        if isinstance(w, _Slider):
            return w.value()
        if isinstance(w, _Numbers):
            return w.values()
        return self.node.kw.get("value")

    def _set_value(self, v):
        w = self.widget
        if isinstance(w, QtWidgets.QCheckBox):
            w.blockSignals(True)
            w.setChecked(bool(v))
            w.blockSignals(False)
        elif isinstance(w, QtWidgets.QLineEdit):
            w.setText(_num_text(v, self.node.kw, self.kind))
        elif isinstance(w, _Slider):
            w.set_value(v)
        self.node.kw["value"] = v

    def _index(self):
        w = self.widget
        if isinstance(w, widgets.Segmented):
            return w.index()
        if isinstance(w, QtWidgets.QComboBox):
            return w.currentIndex()
        return int(self.node.kw.get("select", 1)) - 1

    def _set_index(self, i):
        w = self.widget
        if isinstance(w, widgets.Segmented):
            w.set_index(i)
        elif isinstance(w, QtWidgets.QComboBox):
            w.blockSignals(True)
            w.setCurrentIndex(i)
            w.blockSignals(False)
        self.node.kw["select"] = i + 1


class _Numbers(QtWidgets.QWidget):
    """The number boxes of a floatFieldGrp / intFieldGrp."""

    def __init__(self, kw, integer):
        super(_Numbers, self).__init__()
        self.integer, self.kw = integer, kw
        count = int(kw.get("numberOfFields") or kw.get("nf") or 0) or \
            max([i for i in (1, 2, 3, 4) if ("value%d" % i) in kw or ("v%d" % i) in kw] or [1])
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.boxes = []
        for i in range(count):
            e = QtWidgets.QLineEdit()
            e.setMinimumWidth(52)
            e.setMaximumWidth(90)
            h.addWidget(e)
            self.boxes.append(e)
            self.set(i + 1, kw.get("value%d" % (i + 1), kw.get("v%d" % (i + 1), 0)))

    def get(self, i):
        t = self.boxes[i - 1].text().strip() if 0 < i <= len(self.boxes) else ""
        try:
            return int(float(t)) if self.integer else float(t)
        except ValueError:
            return 0 if self.integer else 0.0

    def set(self, i, v):
        if 0 < i <= len(self.boxes):
            self.boxes[i - 1].setText(_num_text(v, self.kw, "intField" if self.integer else "floatField"))

    def values(self):
        return [self.get(i + 1) for i in range(len(self.boxes))]


class _Item(object):
    """A menu item of a Field (so cmds.deleteUI(item) works on it)."""

    def __init__(self, field, item):
        self.field, self.item = field, item

    def cmd(self, kind, args, k):
        if k.get("exists"):
            return True
        if k.get("query") and (k.get("label") or k.get("l")):
            return self.item.get("label")
        return self.item.get("_name")

    def delete(self):
        proxy.REGISTRY.pop(self.item["_name"], None)
        self.field.remove_item(self.item)


def _num_text(v, kw, kind):
    if kind == "intField" or kind == "intSliderGrp":
        try:
            return str(int(v))
        except (TypeError, ValueError):
            return "0"
    try:
        p = int(kw.get("precision", kw.get("pre", 3)))
        return ("%." + str(max(0, min(p, 6))) + "f") % float(v)
    except (TypeError, ValueError):
        return "0"


class _Slider(QtWidgets.QWidget):
    def __init__(self, kw, integer):
        super(_Slider, self).__init__()
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.integer = integer
        lo, hi = float(kw.get("minValue", kw.get("min", 0))), float(kw.get("maxValue", kw.get("max", 1)))
        self.lo, self.hi = lo, hi
        self.edit = QtWidgets.QLineEdit()
        self.edit.setFixedWidth(64)
        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        h.addWidget(self.edit)
        h.addWidget(self.slider, 1)
        self.set_value(kw.get("value", lo))
        self.slider.valueChanged.connect(lambda i: self.edit.setText(self._fmt(lo + (hi - lo) * i / 1000.0)))

    def _fmt(self, v):
        return str(int(round(v))) if self.integer else "%.3f" % v

    def value(self):
        try:
            v = float(self.edit.text())
        except ValueError:
            v = self.lo
        return int(round(v)) if self.integer else v

    def set_value(self, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = self.lo
        self.edit.setText(self._fmt(v))
        span = (self.hi - self.lo) or 1.0
        self.slider.blockSignals(True)
        self.slider.setValue(int(1000 * (v - self.lo) / span))
        self.slider.blockSignals(False)


def _combo(field, items, current):
    c = QtWidgets.QComboBox()
    c.addItems([str(i.get("label", "")) for i in items])
    c.setCurrentIndex(max(0, current))
    c.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)     # 5.7.3: as wide as its longest choice
    c.setMinimumContentsLength(0)
    cb = field.node.kw.get("changeCommand") or field.node.kw.get("cc")

    def changed(i):
        field.node.kw["select"] = i + 1
        it = field.items[i] if 0 <= i < len(field.items) else {}
        if it.get("command") or it.get("c"):
            _call(it.get("command") or it.get("c"), False)
        _call(cb, it.get("label"))
    c.currentIndexChanged.connect(changed)
    return c


# --------------------------------------------------------------------------- the page
class Page(object):
    """One recorded tool drawn in the new look."""

    def __init__(self, key, rec, accent):
        self.key, self.rec, self.accent = key, rec, accent
        self.fields = {}
        self.cards = []
        self.count = 0
        self.inventory = []                  # (kind, name, label, 'shown' or why not)
        self.tabs = {}                       # tabLayout name -> [(label, QWidget)]
        self.tab_current = {}
        self.on_tab = None                   # the area sets this: (tabLayout name, index) -> show that sub-page

    # -------------------------------------------------- tabs (a tool whose page has pages: Controls)
    def tab_index(self, name):
        return self.tab_current.get(name, 1)

    def set_tab(self, name, i):
        self.tab_current[name] = i
        if self.on_tab:
            self.on_tab(name, i)

    # -------------------------------------------------- drawing
    def build(self, root=None):
        """The page's widget (or, for a page made of pages, the first one: see self.tabs)."""
        w = QtWidgets.QWidget()
        w.setObjectName("gusPage")
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(10)
        self._children(root or self.rec.root, v, ctx={"card": None})
        v.addStretch(1)
        return w

    def _note(self, n, how):
        self.inventory.append((n.kind, n.name, str(n.label() or n.kw.get("annotation") or ""), how))

    def _children(self, node, lay, ctx):
        kids = list(node.children)
        i = 0
        while i < len(kids):
            c = kids[i]
            w = self._node(c, ctx)
            if w is not None:
                if isinstance(lay, widgets.FlowLayout) or isinstance(lay, QtWidgets.QBoxLayout):
                    lay.addWidget(w)
                else:
                    lay.addWidget(w)
            i += 1

    def _node(self, n, ctx):
        kind = n.kind
        fn = getattr(self, "_" + kind, None)
        if fn is None:
            self._note(n, "not drawn: %s isn't known to the new window" % kind)
            w = widgets.label("(%s: %s)" % (kind, n.label()), "faint")
            return w
        w = fn(n, ctx)
        if w is not None:
            ann = n.kw.get("annotation") or n.kw.get("ann")
            if ann and not w.toolTip():
                w.setToolTip(str(ann))
            if n.kw.get("enable") is False or n.kw.get("en") is False:
                w.setEnabled(False)
            if n.kw.get("manage") is False or n.kw.get("visible") is False:
                w.setVisible(False)
            self._popups(n, w)
        return w

    def _popups(self, n, w):
        for pm in n.kw.get("_popups", []):
            items = pm.items
            if not items:
                continue
            w.setContextMenuPolicy(Qt.CustomContextMenu)

            def show(pos, items=items, w=w):
                m = QtWidgets.QMenu(w)
                for it in items:
                    if it.get("divider"):
                        m.addSeparator()
                        continue
                    a = m.addAction(str(it.get("label", "")))
                    a.triggered.connect(lambda _=False, it=it: _call(it.get("command") or it.get("c"), False))
                m.exec_(w.mapToGlobal(pos)) if hasattr(m, "exec_") else m.exec(w.mapToGlobal(pos))
            w.customContextMenuRequested.connect(show)

    # -------------------------------------------------- layouts
    def _box(self, n, ctx):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self._children(n, v, ctx)
        f = Field(self, n, w)
        f.card = ctx.get("card")                    # where a refill draws (proxy.refill)
        return w

    _columnLayout = _box
    _formLayout = _box
    _scrollLayout = _box
    _paneLayout = _box

    def _rowLayout(self, n, ctx):
        kids = n.children
        if (len(kids) == 2 and kids[0].kind == "text" and not kids[0].label() and kids[1].kind == "button" and
                kids[1].label() == "?"):
            for c in kids:
                self._note(c, "the card's own ?")          # ui.section's help row: the card has its own '?'
            return None
        box = widgets.flow_box(6)
        self._children(n, box.layout(), ctx)
        Field(self, n, box)
        return box

    _flowLayout = _rowLayout
    _gridLayout = _rowLayout

    def _rowColumnLayout(self, n, ctx):
        cols = int(n.kw.get("numberOfColumns") or n.kw.get("nc") or 1)
        if cols != 2:
            return self._rowLayout(n, ctx)
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)    # narrow: the label goes above its field
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        kids = list(n.children)
        for i in range(0, len(kids), 2):
            a = self._node(kids[i], ctx)
            b = self._node(kids[i + 1], ctx) if i + 1 < len(kids) else None
            if isinstance(a, QtWidgets.QLabel):
                a.setWordWrap(False)
                _role(a, "dim")
            if a is not None and b is not None:
                form.addRow(a, b)
            elif a is not None:
                form.addRow(a)
        Field(self, n, w)
        return w

    def _frameLayout(self, n, ctx):
        title = str(n.label())
        m = re.match(r"\s*(\d+)\.\s+(.*)$", title)
        number = int(m.group(1)) if m else None
        title = m.group(2) if m else title
        if number is None and n.parent is not None:          # unnumbered sections: their order on the page
            frames = [c for c in n.parent.children if c.kind == "frameLayout"]
            number = frames.index(n) + 1 if n in frames else None
        closed = bool(n.kw.get("collapse") or n.kw.get("cl"))
        if "(advanced)" in title:
            title, closed = title.replace("(advanced)", "").strip(), True
        inside = ctx.get("card") is not None              # 5.7.3: a section inside a card - a lighter panel
        card = widgets.Card(title, None if inside else number, str(n.kw.get("annotation") or ""), closed)
        if inside:
            card.setProperty("inner", "true")
            card.pin.hide()
            widgets.restyle(card)
        else:
            self.cards.append(card)
        inner = {"card": card}
        for c in n.children:
            w = self._node(c, inner)
            if w is not None:
                card.add(w)
        card.peek.setText(_peek(n))
        card.set_closed(closed)
        f = Field(self, n, card)
        f.kind = "frameLayout"
        return card

    def _tabLayout(self, n, ctx):
        labels = dict(n.kw.get("tabLabel") or n.kw.get("tl") or [])
        pages = []
        for c in n.children:
            w = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(10)
            got = self._node(c, ctx)
            if got is not None:
                v.addWidget(got)
            v.addStretch(1)
            pages.append((labels.get(c.name, c.name), w))
        self.tabs[n.name] = pages
        self.tab_current[n.name] = int(n.kw.get("selectTabIndex", 1) or 1)
        Field(self, n, QtWidgets.QWidget(), "tabLayout")
        return None                            # the area shows each one as a sub-page

    # -------------------------------------------------- controls
    def _text(self, n, ctx):
        text = str(n.label())
        if n.kw.get("_light"):
            w = QtWidgets.QLabel(text.strip())               # 5.7.4: what it said while the page was made
            w.setObjectName("gusLight")
            w.setWordWrap(True)
            self._note(n, "shown")
            Field(self, n, w)
            w.setStyleSheet("QLabel { background: %s; border-radius: 6px; padding: 6px 8px; }" %
                            theme.LEVEL.get(n.kw.get("_level"), theme.LEVEL["idle"]))
            return w
        if not text.strip() and not n.name.startswith("text__"):
            w = QtWidgets.QLabel("")                    # a named label the tool fills in later
            w.setWordWrap(True)
            self._note(n, "shown")
            Field(self, n, w)
            return w
        if not text.strip():
            self._note(n, SKIPPED + ": an empty spacer")
            return None
        w = widgets.label(text.strip())
        if n.kw.get("font") == "boldLabelFont":
            f = w.font()
            f.setBold(True)
            w.setFont(f)
        self._note(n, "shown")
        Field(self, n, w)
        return w

    def _button(self, n, ctx):
        text = str(n.label())
        bg = n.kw.get("backgroundColor") or n.kw.get("bgc")
        if text == "?" and n.kw.get("annotation"):
            b = widgets.button("?", "help")
            ann = str(n.kw.get("annotation"))
            b.clicked.connect(lambda _=False: QtWidgets.QMessageBox.information(b, "Help", ann))
        elif bg and _close(bg, MAIN_BG) and (n.kw.get("height") or n.kw.get("h") or 0) >= 30:
            b = widgets.big_button(text)
        elif bg and _close(bg, MAIN_BG):
            b = widgets.button(text, "accent")
        elif any(word in text.lower() for word in DANGER_WORDS):
            b = widgets.button(text, "danger")
        elif bg and not text.strip():
            b = widgets.button("")
            b.setFixedSize(24, 24)
            b.setStyleSheet("QPushButton { background: %s; border-radius: 5px; }" % _hex(bg))
        else:
            b = widgets.button(text)
        cmd = n.kw.get("command") or n.kw.get("c")
        b.clicked.connect(lambda _=False: _call(cmd, False))
        if text and b.property("role") != "big":
            b.setProperty("stretch", True)
        self._note(n, "shown")
        Field(self, n, b)
        return b

    def _iconTextButton(self, n, ctx):
        b = QtWidgets.QToolButton()
        b.setText(str(n.label()))
        img = n.kw.get("image1") or n.kw.get("image") or n.kw.get("i")
        if img:
            pm = QtGui.QPixmap(str(img))
            if not pm.isNull():
                b.setIcon(QtGui.QIcon(pm))
                b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        cmd = n.kw.get("command") or n.kw.get("c")
        b.clicked.connect(lambda _=False: _call(cmd))
        self._note(n, "shown")
        Field(self, n, b)
        return b

    def _checkBox(self, n, ctx):
        c = widgets.WrapCheckBox(str(n.label()))
        c.setChecked(bool(n.kw.get("value") or n.kw.get("v")))
        cc = n.kw.get("changeCommand") or n.kw.get("cc")
        on, off = n.kw.get("onCommand") or n.kw.get("onc"), n.kw.get("offCommand") or n.kw.get("ofc")

        def changed(state):
            v = c.isChecked()
            _call(cc, v)
            _call(on if v else off, v)
        c.stateChanged.connect(changed)
        self._note(n, "shown")
        Field(self, n, c)
        return c

    _symbolCheckBox = _checkBox
    _iconTextCheckBox = _checkBox

    def _optionMenu(self, n, ctx):
        items = n.items
        labels = [str(i.get("label", "")) for i in items]
        current = int(n.kw.get("select", 1) or 1) - 1
        f = Field(self, n, None)
        axis = bool(labels) and all(theme.axis_of(t) for t in labels)
        if 2 <= len(labels) <= 6 and (axis or (len(labels) <= 4 and sum(len(t) for t in labels) <= 40)):
            w = widgets.Segmented(labels, current, axis=axis)
            cb = n.kw.get("changeCommand") or n.kw.get("cc")

            def changed(i):
                n.kw["select"] = i + 1
                it = f.items[i] if 0 <= i < len(f.items) else {}
                if it.get("command") or it.get("c"):
                    _call(it.get("command") or it.get("c"), False)
                _call(cb, it.get("label"))
            w.changed.connect(changed)
        else:
            w = _combo(f, items, current)
        f.widget = w
        self._note(n, "shown")
        lab = n.label()
        if lab:
            box = widgets.flow_box(8)
            box.layout().addWidget(_role(widgets.label(str(lab), wrap=False), "dim"))
            box.layout().addWidget(w)
            return box
        return w

    _optionMenuGrp = _optionMenu

    def _radioButtonGrp(self, n, ctx):
        labels = []
        for k in ("labelArray4", "la4", "labelArray3", "la3", "labelArray2", "la2"):
            if n.kw.get(k):
                labels = [str(x) for x in n.kw[k]]
                break
        if not labels:
            labels = [str(n.kw.get(k)) for k in ("label1", "l1", "label2", "l2", "label3", "l3") if n.kw.get(k)]
        current = int(n.kw.get("select", n.kw.get("sl", 1)) or 1) - 1
        w = widgets.Segmented(labels, current)
        cc = n.kw.get("changeCommand") or n.kw.get("cc")

        def changed(i):
            n.kw["select"] = i + 1
            _call(n.kw.get("onCommand%d" % (i + 1)) or n.kw.get("on%d" % (i + 1)), True)
            _call(cc, True)
        w.changed.connect(changed)
        self._note(n, "shown")
        Field(self, n, w)
        lab = n.label()
        if lab:
            box = widgets.flow_box(8)
            box.layout().addWidget(_role(widgets.label(str(lab), wrap=False), "dim"))
            box.layout().addWidget(w)
            return box
        return w

    def _radioCollection(self, n, ctx):
        g = QtWidgets.QButtonGroup()
        g.setExclusive(True)
        self.groups = getattr(self, "groups", {})
        self.groups[n.name] = g
        self.groups["_last"] = g
        self._note(n, "shown")
        return None

    _iconTextRadioCollection = _radioCollection

    def _radioButton(self, n, ctx):
        r = QtWidgets.QRadioButton(str(n.label()))
        groups = getattr(self, "groups", {})
        g = groups.get(proxy.short(str(n.kw.get("collection") or n.kw.get("cl") or ""))) or groups.get("_last")
        if g is not None:
            g.addButton(r)
        r.setChecked(bool(n.kw.get("select") or n.kw.get("sl")))
        on, cc = n.kw.get("onCommand") or n.kw.get("onc"), n.kw.get("changeCommand") or n.kw.get("cc")
        r.toggled.connect(lambda v: (_call(on, True) if v else None, _call(cc, v)))
        self._note(n, "shown")
        Field(self, n, r)
        return r

    _iconTextRadioButton = _radioButton

    def _textField(self, n, ctx):
        e = QtWidgets.QLineEdit(str(n.kw.get("text") or n.kw.get("tx") or ""))
        ph = n.kw.get("placeholderText") or n.kw.get("pht")
        if ph:
            e.setPlaceholderText(str(ph))
        e.setMinimumWidth(80)
        e.setProperty("stretch", True)
        cc, enter = n.kw.get("changeCommand") or n.kw.get("cc"), n.kw.get("enterCommand") or n.kw.get("ec")
        tc = n.kw.get("textChangedCommand") or n.kw.get("tcc")
        e.editingFinished.connect(lambda: _call(cc, e.text()))
        if enter:
            e.returnPressed.connect(lambda: _call(enter, e.text()))
        if tc:
            e.textChanged.connect(lambda t: _call(tc, t))
        if n.kw.get("editable") is False or n.kw.get("ed") is False:
            e.setReadOnly(True)
        self._note(n, "shown")
        Field(self, n, e)
        return e

    def _number(self, n, ctx, integer):
        e = QtWidgets.QLineEdit()
        e.setFixedWidth(74)
        val = n.kw.get("value", n.kw.get("v", 0))
        if integer:
            e.setValidator(QtGui.QIntValidator())
        else:
            e.setValidator(QtGui.QDoubleValidator())
        e.setText(_num_text(val, n.kw, "intField" if integer else "floatField"))
        cc = n.kw.get("changeCommand") or n.kw.get("cc")
        lo = n.kw.get("minValue", n.kw.get("min"))
        hi = n.kw.get("maxValue", n.kw.get("max"))

        def done():
            try:
                v = float(e.text())
            except ValueError:
                v = float(val or 0)
            if lo is not None:
                v = max(float(lo), v)
            if hi is not None:
                v = min(float(hi), v)
            e.setText(_num_text(v, n.kw, "intField" if integer else "floatField"))
            _call(cc, int(v) if integer else v)
        e.editingFinished.connect(done)
        self._note(n, "shown")
        Field(self, n, e, "intField" if integer else "floatField")
        return e

    def _colorSliderGrp(self, n, ctx):
        """5.7.3: a colour square - click it to choose (Maya's colour slider in the old window)."""
        rgb = n.kw.get("rgbValue") or n.kw.get("rgb") or (1.0, 1.0, 1.0)
        box = widgets.flow_box(8)
        lab = n.label()
        if lab:
            box.layout().addWidget(_role(widgets.label(str(lab), wrap=False), "dim"))
        sw = QtWidgets.QPushButton("")
        sw.setFixedSize(46, 24)
        sw.setCursor(Qt.PointingHandCursor)
        sw.setToolTip("Click to choose the colour")
        box.swatch = sw
        box.layout().addWidget(sw)
        f = Field(self, n, box, "colorSliderGrp")
        f.edit("rgbValue", list(rgb))
        cc = n.kw.get("changeCommand") or n.kw.get("cc") or n.kw.get("dragCommand") or n.kw.get("dc")

        def pick():
            cur = f.query("rgbValue")
            got = QtWidgets.QColorDialog.getColor(QtGui.QColor.fromRgbF(*[float(x) for x in cur[:3]]), sw,
                                                  "Choose the colour")
            if got.isValid():
                f.edit("rgbValue", [got.redF(), got.greenF(), got.blueF()])
                _call(cc, True)
        sw.clicked.connect(lambda _=False: pick())
        self._note(n, "shown")
        return box

    _attrColorSliderGrp = _colorSliderGrp

    def _floatField(self, n, ctx):
        return self._number(n, ctx, False)

    def _intField(self, n, ctx):
        return self._number(n, ctx, True)

    def _slider_grp(self, n, ctx, integer):
        s = _Slider(n.kw, integer)
        cc = n.kw.get("changeCommand") or n.kw.get("cc")
        s.edit.editingFinished.connect(lambda: _call(cc, s.value()))
        s.slider.sliderReleased.connect(lambda: _call(cc, s.value()))
        self._note(n, "shown")
        Field(self, n, s, "intSliderGrp" if integer else "floatSliderGrp")
        lab = n.label()
        if lab:
            box = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(_role(widgets.label(str(lab), wrap=False), "dim"))
            h.addWidget(s, 1)
            return box
        return s

    def _floatSliderGrp(self, n, ctx):
        return self._slider_grp(n, ctx, False)

    def _intSliderGrp(self, n, ctx):
        return self._slider_grp(n, ctx, True)

    def _textScrollList(self, n, ctx):
        lw = QtWidgets.QListWidget()
        lw.addItems([str(t) for t in n.kw.get("append", []) or []] if isinstance(n.kw.get("append"), list) else
                    ([str(n.kw["append"])] if n.kw.get("append") else []))
        lw.addItems([str(t) for t in n.kw.get("_items", [])])
        if n.kw.get("allowMultiSelection") or n.kw.get("ams"):
            lw.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        rows = n.kw.get("numberOfRows") or n.kw.get("nr")
        h = n.kw.get("height") or n.kw.get("h") or (int(rows) * 20 + 8 if rows else 120)
        lw.setMinimumHeight(min(int(h), 260))
        sc, dc = n.kw.get("selectCommand") or n.kw.get("sc"), n.kw.get("doubleClickCommand") or n.kw.get("dcc")
        lw.itemSelectionChanged.connect(lambda: _call(sc))
        if dc:
            lw.itemDoubleClicked.connect(lambda _it: _call(dc))
        self._note(n, "shown")
        f = Field(self, n, lw)
        if isinstance(n.kw.get("append"), (list, tuple)):
            f.list_items = list(n.kw["append"]) + f.list_items
        elif n.kw.get("append"):
            f.list_items = [n.kw["append"]] + f.list_items
        return lw

    def _scrollField(self, n, ctx):
        t = QtWidgets.QPlainTextEdit(str(n.kw.get("text") or ""))
        t.setReadOnly(n.kw.get("editable") is False)
        h = n.kw.get("height") or n.kw.get("h")
        t.setMinimumHeight(min(int(h), 120) if h else 120)       # 5.7.4: its own height (Ribbon's report: 80)
        if h:
            t.setMaximumHeight(max(int(h), 60) * 2)
        self._note(n, "shown")
        Field(self, n, t)
        return t

    def _separator(self, n, ctx):
        line = QtWidgets.QFrame()
        line.setFixedHeight(6)
        self._note(n, "shown")
        return line

    def _canvas(self, n, ctx):
        b = widgets.button("")
        b.setFixedSize(24, 24)
        hx = _hex(n.kw.get("rgbValue") or (1, 1, 1))
        b.setStyleSheet("QPushButton { background: %s; border-radius: 5px; }" % hx)
        cmd = n.kw.get("pressCommand") or n.kw.get("pc")
        b.clicked.connect(lambda _=False: _call(cmd))
        self._note(n, "shown")
        Field(self, n, b)
        return b

    def _image(self, n, ctx):
        lb = QtWidgets.QLabel()
        pm = QtGui.QPixmap(str(n.kw.get("image") or n.kw.get("i") or ""))
        if not pm.isNull():
            lb.setPixmap(pm)
        self._note(n, "shown")
        Field(self, n, lb)
        return lb

    def _group(self, n, ctx, make):
        box = widgets.flow_box(8)
        lab = n.label()
        if lab:
            box.layout().addWidget(_role(widgets.label(str(lab), wrap=False), "dim"))
        w = make()
        box.layout().addWidget(w)
        self._note(n, "shown")
        return box, w

    def _textFieldGrp(self, n, ctx):
        box, e = self._group(n, ctx, lambda: QtWidgets.QLineEdit(str(n.kw.get("text") or "")))
        e.setProperty("stretch", True)
        cc = n.kw.get("changeCommand") or n.kw.get("cc")
        e.editingFinished.connect(lambda: _call(cc, e.text()))
        Field(self, n, e, "textField")
        return box

    _textFieldButtonGrp = _textFieldGrp

    def _number_group(self, n, ctx, integer):
        """A label and 1-4 number boxes (5.7.3: each box answers value1..value4; value is the list, as in Maya)."""
        box, m = self._group(n, ctx, lambda: _Numbers(n.kw, integer))
        Field(self, n, m, "intFieldGrp" if integer else "floatFieldGrp")
        cc = n.kw.get("changeCommand") or n.kw.get("cc")
        if cc:
            for e in m.boxes:
                e.editingFinished.connect(lambda: _call(cc, True))
        return box

    def _floatFieldGrp(self, n, ctx):
        return self._number_group(n, ctx, False)

    def _intFieldGrp(self, n, ctx):
        return self._number_group(n, ctx, True)

    def _checkBoxGrp(self, n, ctx):
        box, c = self._group(n, ctx, lambda: QtWidgets.QCheckBox(str(n.kw.get("label1") or "")))
        c.setChecked(bool(n.kw.get("value1")))
        Field(self, n, c, "checkBox")
        return box


def _forget(field_page, node):
    """The fields made for node's children are gone (the layout is filled again)."""
    for c in node.children:
        _forget(field_page, c)
        f = field_page.fields.pop(c.name, None)
        if f is not None:
            f.alive = False
            for i in f.items:
                proxy.REGISTRY.pop(i.get("_name"), None)
            if proxy.REGISTRY.get(c.name) is f:
                proxy.REGISTRY.pop(c.name, None)


_refills = {"n": 0}


def refill(field, fill):
    """Run fill() with its controls written down (as when the page was recorded), then draw them into the shown
    layout `field`, in place of what it had (proxy.refill)."""
    page, node = field.page, field.node
    _refills["n"] += 1
    rec = record.Recorder("%sr%d_" % (node.name, _refills["n"]))
    rec.live = True
    root = record.Node(node.kind, node.name, node.kw, None)
    rec.root = rec.current = root
    rec.nodes = {node.name: root}
    with record.recording(rec):
        got = fill()
    _forget(page, node)
    lay = field.widget.layout()
    while lay is not None and lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
    node.children = list(root.children)
    for c in node.children:
        c.parent = node
    page._children(node, lay, {"card": field.card})
    for anchor, fn in rec.selection:
        page.rec.selection.append((anchor, fn))
    return got


def _role(w, role):
    w.setProperty("role", role)
    return w


def _peek(frame):
    """What a closed card holds, in one line: its first few buttons, fields and choices."""
    words = []

    def walk(n):
        for c in n.children:
            if len(words) >= 4:
                return
            lab = str(c.label() or "").strip()
            if c.kind in ("button", "checkBox") and lab and lab != "?":
                words.append(lab.split(" (")[0])
            elif c.kind == "text" and lab and c.parent is not None and c.parent.kind == "rowColumnLayout":
                words.append(lab.rstrip(":"))
            walk(c)
    walk(frame)
    return " · ".join(w[:28] for w in words)
