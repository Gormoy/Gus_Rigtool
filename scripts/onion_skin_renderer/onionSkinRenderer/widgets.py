"""Small widgets the onion skin's window and mini bar share: a - / + counter, a row of switch buttons, the ghost
opacity bars and a list row (eye, name, note, remove)."""
from onionSkinRenderer.qt import QtCore, QtGui, QtWidgets

ACCENT = "#5285a6"
GREEN = "#4f9a4f"
STYLE = """
QPushButton[seg="true"] { background:#4b4b4b; border:1px solid #666; padding:3px 9px; border-radius:0px; }
QPushButton[seg="true"]:checked { background:%(a)s; color:white; }
QPushButton[chip="true"] { border:1px solid #666; border-radius:10px; padding:2px 10px; background:#4a4a4a; }
QPushButton[chip="true"]:checked { background:%(a)s; border-color:%(a)s; color:white; }
QPushButton[step="true"] { min-width:22px; max-width:22px; padding:2px 0px; }
QLabel[note="true"] { color:#9a9a9a; }
QLabel[status="true"] { background:#2b2b2b; border-radius:3px; padding:5px 8px; color:#bfe3bf; }
QLabel[warn="true"] { color:rgb(255,170,60); }
QFrame[row="true"] { background:#2b2b2b; border-radius:3px; }
""" % {"a": ACCENT}


def on_button_style(on, big=True):
    pad = "9px 6px" if big else "4px 10px"
    size = "14px" if big else "12px"
    if on:
        return ("QPushButton { background:%s; color:white; font-weight:bold; font-size:%s; padding:%s; "
                "border-radius:3px; }" % (GREEN, size, pad))
    return ("QPushButton { background:#5d5d5d; color:#eee; font-weight:bold; font-size:%s; padding:%s; "
            "border-radius:3px; }" % (size, pad))


class Stepper(QtWidgets.QWidget):
    """-  [ n ]  +"""
    valueChanged = QtCore.Signal(int)

    def __init__(self, low, high, value=0, tip="", parent=None):
        super(Stepper, self).__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.minus = QtWidgets.QPushButton("−")
        self.plus = QtWidgets.QPushButton("+")
        for b in (self.minus, self.plus):
            b.setProperty("step", True)
            b.setAutoRepeat(True)
        self.spin = QtWidgets.QSpinBox()
        self.spin.setRange(low, high)
        self.spin.setValue(value)
        self.spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.spin.setAlignment(QtCore.Qt.AlignCenter)
        self.spin.setFixedWidth(36)
        if tip:
            for w in (self, self.spin, self.minus, self.plus):
                w.setToolTip(tip)
        lay.addWidget(self.minus)
        lay.addWidget(self.spin)
        lay.addWidget(self.plus)
        self.minus.clicked.connect(lambda *_: self.spin.setValue(self.spin.value() - 1))
        self.plus.clicked.connect(lambda *_: self.spin.setValue(self.spin.value() + 1))
        self.spin.valueChanged.connect(self.valueChanged.emit)

    def value(self):
        return self.spin.value()

    def setValue(self, v):
        self.spin.blockSignals(True)
        self.spin.setValue(int(v))
        self.spin.blockSignals(False)


class Segmented(QtWidgets.QWidget):
    """A row of buttons, one pressed at a time (like Keys | Main keys | Frames)."""
    picked = QtCore.Signal(object)

    def __init__(self, items, tips=None, parent=None):
        super(Segmented, self).__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for n, (value, label) in enumerate(items):
            b = QtWidgets.QPushButton(label)
            b.setCheckable(True)
            b.setProperty("seg", True)
            if tips and n < len(tips) and tips[n]:
                b.setToolTip(tips[n])
            self.group.addButton(b)
            lay.addWidget(b)
            self.buttons[value] = b
            b.clicked.connect(lambda *_a, v=value: self.picked.emit(v))

    def setValue(self, value):
        for v, b in self.buttons.items():
            b.blockSignals(True)
            b.setChecked(v == value)
            b.blockSignals(False)

    def value(self):
        return next((v for v, b in self.buttons.items() if b.isChecked()), None)


class GhostBars(QtWidgets.QWidget):
    """One bar per ghost (-before ... +after): drag a bar up or down for its opacity; to the bottom = off."""
    opacityChanged = QtCore.Signal(int, int)

    def __init__(self, parent=None):
        super(GhostBars, self).__init__(parent)
        self.before, self.after = 2, 2
        self.values = {}
        self.past, self.future = QtGui.QColor(40, 120, 255), QtGui.QColor(255, 130, 20)
        self._drag = None
        self.setMinimumHeight(78)
        self.setToolTip("Drag a bar up or down to set that ghost's opacity. All the way down = that ghost off.")

    def setGhosts(self, before, after, values, past, future):
        self.before, self.after = int(before), int(after)
        self.values = dict(values)
        self.past, self.future = QtGui.QColor(*past[:3]), QtGui.QColor(*future[:3])
        self.update()

    def indices(self):
        return list(range(-self.before, 0)) + [0] + list(range(1, self.after + 1))

    def _geometry(self):
        idx = self.indices()
        w = self.width() - 8
        slot = w / float(max(len(idx), 1))
        return idx, slot, self.height() - 16

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#2b2b2b"))
        idx, slot, top = self._geometry()
        font = p.font()
        font.setPointSize(7)
        p.setFont(font)
        for n, i in enumerate(idx):
            x = 4 + n * slot
            v = 100 if i == 0 else self.values.get(i, 0)
            h = max(3, int((top - 6) * v / 100.0))
            if i == 0:
                col = QtGui.QColor(221, 221, 221, 70)
            elif v == 0:
                col = QtGui.QColor("#555555")
            else:
                col = self.past if i < 0 else self.future
            p.fillRect(QtCore.QRectF(x + 2, top - h, max(slot - 4, 2), h), col)
            p.setPen(QtGui.QColor("#9a9a9a"))
            p.drawText(QtCore.QRectF(x, top + 1, slot, 14), QtCore.Qt.AlignCenter,
                       "now" if i == 0 else ("%+d" % i))
        p.end()

    def _hit(self, pos):
        idx, slot, top = self._geometry()
        n = int((pos.x() - 4) // max(slot, 1))
        if 0 <= n < len(idx) and idx[n] != 0:
            return idx[n], top
        return None, top

    def _set(self, pos, index=None):
        i, top = self._hit(pos)
        i = index if index is not None else i
        if i is None:
            return None
        v = int(round(max(0.0, min(1.0, (top - pos.y()) / float(max(top - 6, 1)))) * 100))
        v = 0 if v < 6 else v
        if self.values.get(i) != v:
            self.values[i] = v
            self.update()
            self.opacityChanged.emit(i, v)
        return i

    def mousePressEvent(self, e):
        self._drag = self._set(e.pos())

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self._set(e.pos(), self._drag)

    def mouseReleaseEvent(self, _e):
        self._drag = None


class Row(QtWidgets.QFrame):
    """eye | name | note | x  - a character or an arc point."""

    def __init__(self, name, note, visible, on_eye, on_remove, parent=None):
        super(Row, self).__init__(parent)
        self.setProperty("row", True)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 4, 2)
        self.eye = QtWidgets.QToolButton()
        self.eye.setCheckable(True)
        self.eye.setChecked(visible)
        self.eye.setAutoRaise(True)
        self.eye.setText("\U0001F441")
        self.eye.setToolTip("Show / hide (kept in the list)")
        self.eye.toggled.connect(on_eye)
        self.name = QtWidgets.QLabel(name if visible else name + "  (hidden)")
        self.note = QtWidgets.QLabel(note)
        self.note.setProperty("note", True)
        x = QtWidgets.QToolButton()
        x.setAutoRaise(True)
        x.setText("✕")
        x.setToolTip("Remove from the list")
        x.clicked.connect(lambda *_: on_remove())
        if not visible:
            for w in (self.name, self.eye):
                eff = QtWidgets.QGraphicsOpacityEffect(w)
                eff.setOpacity(0.45)
                w.setGraphicsEffect(eff)
        lay.addWidget(self.eye)
        lay.addWidget(self.name, 1)
        lay.addWidget(self.note)
        lay.addWidget(x)


def swatch_icon(colours, size=12):
    pix = QtGui.QPixmap(size * len(colours) + 2 * (len(colours) - 1), size)
    pix.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pix)
    for n, c in enumerate(colours):
        p.fillRect(n * (size + 2), 0, size, size, QtGui.QColor(*c[:3]))
    p.end()
    return QtGui.QIcon(pix)


def group(title):
    box = QtWidgets.QGroupBox(title)
    lay = QtWidgets.QVBoxLayout(box)
    lay.setSpacing(5)
    return box, lay


def line(*widgets, **kw):
    lay = QtWidgets.QHBoxLayout()
    lay.setSpacing(kw.get("spacing", 6))
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, str):
            lab = QtWidgets.QLabel(w)
            if kw.get("label_width"):
                lab.setFixedWidth(kw["label_width"])
            lay.addWidget(lab)
        elif isinstance(w, QtWidgets.QLayout):
            lay.addLayout(w)
        else:
            lay.addWidget(w)
    return lay
