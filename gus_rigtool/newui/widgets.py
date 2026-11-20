"""
The 5.7 building blocks: a row that wraps instead of cropping (FlowLayout), the numbered card, segmented buttons,
the big button, the selection chips, the next-step box, the shape grid.
"""

from gus_rigtool.newui import icons, theme
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt


def _set_role(w, role):
    w.setProperty("role", role)
    return w


def restyle(w):
    w.style().unpolish(w)
    w.style().polish(w)


# --------------------------------------------------------------------------- a row that never crops
class FlowLayout(QtWidgets.QLayout):
    """Items left to right; what doesn't fit goes to the next line (Qt's flow layout example). Never wider than
    the panel: nothing is cut off, at any width."""

    def __init__(self, parent=None, spacing=6):
        super(FlowLayout, self).__init__(parent)
        self._items = []
        self._space = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0) if hasattr(Qt, "Orientations") else Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        """All on one line (a row inside a row asks for this; it wraps only when there isn't room)."""
        shown = [it for it in self._items if it.widget() is None or not it.widget().isHidden()]
        if not shown:
            return QtCore.QSize(0, 0)
        m = self.contentsMargins()
        w = sum(it.sizeHint().width() for it in shown) + self._space * (len(shown) - 1)
        h = max(it.sizeHint().height() for it in shown)
        return QtCore.QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

    def minimumSize(self):
        size = QtCore.QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        rows = [[]]
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisibleTo(it.widget().parentWidget()):
                continue
            w = min(it.sizeHint().width(), r.width())
            if it.widget() is not None and it.widget().property("fill"):
                w = r.width()
            nx = x + w + self._space
            if nx - self._space > r.right() + 1 and line > 0:
                x, y, line = r.x(), y + line + self._space, 0
                nx = x + w + self._space
                rows.append([])
            h = it.heightForWidth(w) if it.hasHeightForWidth() else it.sizeHint().height()
            rows[-1].append((it, x, y, w, h))
            x, line = nx, max(line, h)
        if not test:
            for row in rows:                      # a row's items share the free width (equal stretch)
                if not row:
                    continue
                used = sum(w for _i, _x, _y, w, _h in row) + self._space * (len(row) - 1)
                extra = max(0, r.width() - used)
                stretchy = [e for e in row if e[0].widget() is not None and e[0].widget().property("stretch")]
                add = extra // len(stretchy) if stretchy else 0
                shift = 0
                for it, ix, iy, w, h in row:
                    grow = add if (it.widget() is not None and it.widget().property("stretch")) else 0
                    it.setGeometry(QtCore.QRect(ix + shift, iy, w + grow, h))
                    shift += grow
        return y + line - rect.y() + m.bottom()


def flow_box(spacing=6):
    w = QtWidgets.QWidget()
    w.setLayout(FlowLayout(spacing=spacing))
    w.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
    return w


# --------------------------------------------------------------------------- labels and buttons
def label(text, role=None, wrap=True):
    lb = QtWidgets.QLabel(text)
    lb.setWordWrap(wrap)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if role:
        _set_role(lb, role)
    lb.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
    return lb


class WrapButton(QtWidgets.QPushButton):
    """A button whose label wraps onto more lines when the panel is narrow (a plain one is cut off)."""

    def __init__(self, text="", parent=None):
        super(WrapButton, self).__init__(parent)
        self._lb = QtWidgets.QLabel(text, self)
        self._lb.setWordWrap(True)
        self._lb.setAlignment(Qt.AlignCenter)
        self._lb.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.addWidget(self._lb)
        sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def text(self):
        return self._lb.text()

    def setText(self, text):
        self._lb.setText(text)
        self.updateGeometry()

    def _pad(self):
        m = self.layout().contentsMargins()
        return m.left() + m.right(), m.top() + m.bottom()

    def sizeHint(self):
        px, py = self._pad()
        self._lb.ensurePolished()                  # 5.7.1: measured in the window's font (Maya's is wider)
        fm = self._lb.fontMetrics()
        w = fm.horizontalAdvance(self._lb.text()) if hasattr(fm, "horizontalAdvance") else fm.width(self._lb.text())
        return QtCore.QSize(w + px + 18, max(fm.height() + py + 6, 28 if self.property("role") != "big" else 40))

    def minimumSizeHint(self):
        """Never narrower than its longest word (a word can't wrap)."""
        px, py = self._pad()
        fm = self._lb.fontMetrics()
        adv = fm.horizontalAdvance if hasattr(fm, "horizontalAdvance") else fm.width
        word = max([adv(x) for x in self._lb.text().split()] or [0])
        return QtCore.QSize(min(self.sizeHint().width(), word + px + 12), self.sizeHint().height())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        px, py = self._pad()
        h = self._lb.heightForWidth(max(10, w - px)) + py + 6
        return max(h, 28 if self.property("role") != "big" else 40)


class WrapCheckBox(QtWidgets.QCheckBox):
    """A check box whose label wraps when the panel is narrow (Qt's own is cut off). Click anywhere on it."""

    def __init__(self, text="", parent=None):
        super(WrapCheckBox, self).__init__(parent)
        self._lb = QtWidgets.QLabel(text, self)
        self._lb.setWordWrap(True)
        self._lb.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(24, 0, 0, 0)
        lay.addWidget(self._lb)
        sp = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def text(self):
        return self._lb.text()

    def setText(self, text):
        self._lb.setText(text)
        self.updateGeometry()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def sizeHint(self):
        self._lb.ensurePolished()
        fm = self._lb.fontMetrics()
        t = self._lb.text()
        w = fm.horizontalAdvance(t) if hasattr(fm, "horizontalAdvance") else fm.width(t)
        return QtCore.QSize(w + 30, max(20, fm.height() + 4))

    def minimumSizeHint(self):
        return QtCore.QSize(min(self.sizeHint().width(), 90), self.sizeHint().height())

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return max(20, self._lb.heightForWidth(max(10, w - 24)) + 2)


def button(text, role=None, tip=""):
    b = WrapButton(text) if role in (None, "accent", "danger", "big") and text else QtWidgets.QPushButton(text)
    if role:
        _set_role(b, role)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    return b


def big_button(text, tip=""):
    b = button(text, "big", tip)
    b.setProperty("fill", True)
    b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    return b


class Segmented(QtWidgets.QWidget):
    """A few choices side by side, one picked (an optionMenu / radio group). Wraps when narrow."""
    changed = QtCore.Signal(int)

    def __init__(self, labels, current=0, axis=False, parent=None):
        super(Segmented, self).__init__(parent)
        self.setLayout(FlowLayout(spacing=0))
        self.buttons = []
        self.group = QtWidgets.QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(labels):
            b = button(text, "seg")
            b.setCheckable(True)
            a = theme.axis_of(text) if axis else None
            if a:
                b.setStyleSheet("QPushButton:!checked { color: %s; font-weight: bold; } "
                                "QPushButton:checked { background: %s; color: white; }" % (theme.AXIS[a],
                                                                                           theme.AXIS[a]))
            self.group.addButton(b, i)
            self.layout().addWidget(b)
            self.buttons.append(b)
        self.set_index(current)
        self.group.buttonClicked.connect(lambda b: self.changed.emit(self.buttons.index(b)))

    def index(self):
        for i, b in enumerate(self.buttons):
            if b.isChecked():
                return i
        return -1

    def set_index(self, i):
        if 0 <= i < len(self.buttons):
            self.buttons[i].setChecked(True)

    def labels(self):
        return [b.text() for b in self.buttons]


# --------------------------------------------------------------------------- the card
class Card(QtWidgets.QFrame):
    """A numbered section: title, '?', pin; closed it shows what's inside in one line."""
    toggled = QtCore.Signal(bool)
    pin_clicked = QtCore.Signal()

    def __init__(self, title, number=None, help_text="", closed=False, peek="", parent=None):
        super(Card, self).__init__(parent)
        self.setObjectName("gusCard")
        self.title = title
        self.help_text = help_text
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(12, 9, 10, 10)
        v.setSpacing(7)
        head = QtWidgets.QWidget()
        head.setCursor(Qt.PointingHandCursor)
        h = QtWidgets.QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.num = QtWidgets.QLabel(str(number) if number else "")
        self.num.setObjectName("gusNum")
        self.num.setFixedSize(20, 20)
        self.num.setAlignment(Qt.AlignCenter)
        self.num.setVisible(bool(number))
        h.addWidget(self.num, 0, Qt.AlignTop)
        t = QtWidgets.QLabel(title)
        t.setObjectName("gusCardTitle")
        t.setWordWrap(True)
        h.addWidget(t, 1)
        self.peek = QtWidgets.QLabel(peek)
        self.peek.setObjectName("gusPeek")
        self.peek.setWordWrap(True)
        h.addWidget(self.peek, 2)
        self.pin = QtWidgets.QToolButton()
        self.pin.setIcon(icons.icon("pin", 14, theme.FAINT))
        self.pin.setToolTip("Pin: this card stays on top of every page of this area")
        self.pin.setAutoRaise(True)
        self.pin.clicked.connect(self.pin_clicked.emit)
        h.addWidget(self.pin, 0, Qt.AlignTop)
        self.help = QtWidgets.QToolButton()
        self.help.setText("?")
        _set_role(self.help, "help")
        self.help.setVisible(bool(help_text))
        self.help.setToolTip(help_text)
        self.help.clicked.connect(self._show_help)
        h.addWidget(self.help, 0, Qt.AlignTop)
        self.arrow = QtWidgets.QLabel()
        h.addWidget(self.arrow, 0, Qt.AlignTop)
        v.addWidget(head)
        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(7)
        v.addWidget(self.body)
        head.mousePressEvent = lambda e: self.set_closed(not self.closed)
        self.closed = False
        self.set_closed(closed)

    def _show_help(self):
        QtWidgets.QMessageBox.information(self, self.title, self.help_text)

    def set_closed(self, closed):
        self.closed = bool(closed)
        self.body.setVisible(not self.closed)
        self.peek.setVisible(self.closed and bool(self.peek.text()))
        self.arrow.setPixmap(icons.pixmap("open" if self.closed else "more", 12, theme.FAINT))
        self.setProperty("closed", "true" if self.closed else "false")
        restyle(self)
        self.toggled.emit(not self.closed)

    def set_pinned(self, on):
        self.setProperty("pinned", "true" if on else "false")
        self.pin.setIcon(icons.icon("pin", 14, "#ffcf5c" if on else theme.FAINT))
        self.pin.setToolTip("Unpin" if on else "Pin: this card stays on top of every page of this area")
        restyle(self)

    def add(self, w):
        self.body_layout.addWidget(w)
        return w


# --------------------------------------------------------------------------- selection and next step
def kind_of(node):
    """joint / control / mesh / other, for a selected node (Maya)."""
    try:
        import maya.cmds as cmds
        t = cmds.nodeType(node)
        if t == "joint":
            return "joint"
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        types = set(cmds.nodeType(s) for s in shapes)
        if "mesh" in types:
            return "mesh"
        if "nurbsCurve" in types:
            return "control"
    except Exception:
        pass
    return "other"


class Chip(QtWidgets.QLabel):
    def __init__(self, text, kind="other", parent=None):
        super(Chip, self).__init__(parent)
        c = theme.KIND.get(kind, theme.KIND["other"])
        ic = icons.pixmap(kind if kind in icons.PATHS else "other", 14, c, 1.8)
        self.setText(text)
        self.setStyleSheet("QLabel { background: rgba(255,255,255,0.07); color: %s; border-radius: 10px; "
                           "padding: 2px 9px 2px 22px; }" % c)
        self._ic = ic

    def paintEvent(self, e):
        super(Chip, self).paintEvent(e)
        p = QtGui.QPainter(self)
        p.drawPixmap(5, (self.height() - 14) // 2, self._ic)
        p.end()


class SelectedBox(QtWidgets.QFrame):
    """'SELECTED  [joint L_arm] [joint L_elbow] +2   a chain'."""

    def __init__(self, parent=None):
        super(SelectedBox, self).__init__(parent)
        self.setObjectName("gusSel")
        self.setLayout(FlowLayout(spacing=6))
        self.layout().setContentsMargins(10, 7, 10, 7)
        self.set([])

    def set(self, items, what=""):
        lay = self.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        lay.addWidget(label("SELECTED", "sec", wrap=False))
        if not items:
            lay.addWidget(label("nothing", "dim", wrap=False))
        for name, kind in items[:3]:
            lay.addWidget(Chip(name, kind))
        if len(items) > 3:
            lay.addWidget(Chip("+%d" % (len(items) - 3), "other"))
        if what:
            lay.addWidget(label(what, "dim", wrap=False))


class NextStep(QtWidgets.QFrame):
    """The lamp: what to do next with this selection - it only suggests; its button takes you there."""
    go = QtCore.Signal()

    def __init__(self, accent, parent=None):
        super(NextStep, self).__init__(parent)
        self.setObjectName("gusNext")
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(10, 7, 8, 7)
        h.setSpacing(10)
        self.lamp = QtWidgets.QLabel()
        self.lamp.setPixmap(icons.pixmap("bulb", 22, accent))
        h.addWidget(self.lamp, 0, Qt.AlignTop)
        v = QtWidgets.QVBoxLayout()
        v.setSpacing(1)
        self.text = label("")
        self.where = label("", "dim")
        v.addWidget(self.text)
        v.addWidget(self.where)
        h.addLayout(v, 1)
        self.button = button("Show me", "big")
        self.button.clicked.connect(self.go.emit)
        h.addWidget(self.button, 0, Qt.AlignVCenter)
        self.hide()

    def set(self, text, where, button_text):
        self.text.setText("<b>Next:</b> " + text)
        self.where.setText(where)
        self.button.setText(button_text)
        self.setVisible(bool(text))


# --------------------------------------------------------------------------- the shape grid
def _two_lines(text, most=12):
    """A long shape name on two lines (a tile can't wrap by itself)."""
    if len(text) <= most or " " not in text:
        return text
    words = text.split(" ")
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    return " ".join(words[:best]) + "\n" + " ".join(words[best:])


class ShapeGrid(QtWidgets.QWidget):
    """Every shape as a picture with its name, in groups; wraps to the width. Hover / click like the old list."""
    picked = QtCore.Signal(str)
    hovered = QtCore.Signal(str, bool)

    def __init__(self, groups, current=None, image_of=None, parent=None):
        super(ShapeGrid, self).__init__(parent)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search shapes: arrow, cube...")
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)
        self.tiles = {}
        self.heads = []
        for group, names in groups:
            head = label(group.upper(), "sec", wrap=False)
            v.addWidget(head)
            box = flow_box(6)
            for name, text in names:
                b = QtWidgets.QToolButton()
                b.setText(_two_lines(text))
                b.setToolTip(text)
                b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                b.setFixedSize(84, 66)
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                img = image_of(name) if image_of else None
                if img:
                    b.setIcon(QtGui.QIcon(img))
                    b.setIconSize(QtCore.QSize(26, 26))
                b.setStyleSheet("QToolButton { background: #2a2d32; border: 1px solid #444a52; border-radius: 8px; "
                                "font-size: 11px; color: %s; } QToolButton:checked { border: 2px solid palette(highlight); "
                                "color: white; }" % theme.DIM)
                b.clicked.connect(lambda _=False, n=name: self._pick(n))
                b.installEventFilter(self)
                b.setProperty("shape", name)
                box.layout().addWidget(b)
                self.tiles[name] = b
            v.addWidget(box)
            self.heads.append((head, box, [n for n, _t in names]))
        if current:
            self.mark(current)

    def eventFilter(self, obj, event):
        name = obj.property("shape")
        if name and event.type() == QtCore.QEvent.Enter:
            self.hovered.emit(name, True)
        elif name and event.type() == QtCore.QEvent.Leave:
            self.hovered.emit(name, False)
        return False

    def _pick(self, name):
        self.mark(name)
        self.picked.emit(name)

    def mark(self, name):
        for n, b in self.tiles.items():
            b.setChecked(n == name)

    def _filter(self, text):
        t = text.strip().lower().replace(" ", "_")
        for head, box, names in self.heads:
            shown = 0
            for n in names:
                ok = not t or t in n.lower()
                self.tiles[n].setVisible(ok)
                shown += ok
            head.setVisible(bool(shown))
            box.setVisible(bool(shown))
