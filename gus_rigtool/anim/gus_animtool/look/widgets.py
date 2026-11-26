"""
The 5.7 building blocks: a row that wraps instead of cropping (FlowLayout), the numbered card, segmented buttons,
the big button, the selection chips, the next-step box, the shape grid.
"""

from . import icons, theme
from .qt import QtCore, QtGui, QtWidgets

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


class FormLayout(QtWidgets.QLayout):
    """5.7.8: names on the left, controls on the right; when a control wouldn't get the room it needs, every name
    goes above its control (Qt's own form squeezed the control instead, and cut its text)."""

    def __init__(self, parent=None, hspace=10, vspace=6, align=Qt.AlignLeft, label_max=None):
        super(FormLayout, self).__init__(parent)
        self._rows = []                                   # [(label item or None, field item or None)]
        self._items = []
        self._h, self._v, self._align, self._lmax = hspace, vspace, align, label_max
        self.setContentsMargins(0, 0, 0, 0)

    def addRow(self, label, field=None):
        li = QtWidgets.QWidgetItem(label) if label is not None else None
        fi = QtWidgets.QWidgetItem(field) if field is not None else None
        for w in (label, field):
            if w is not None:
                self.addChildWidget(w)
        for it in (li, fi):
            if it is not None:
                self._items.append(it)
        self._rows.append((li, fi))
        self.invalidate()

    def addItem(self, item):
        self._items.append(item)
        self._rows.append((None, item))

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        if not 0 <= i < len(self._items):
            return None
        it = self._items.pop(i)
        self._rows = [(None if l is it else l, None if f is it else f) for l, f in self._rows]
        return it

    def expandingDirections(self):
        return Qt.Orientations(0) if hasattr(Qt, "Orientations") else Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FormLayout, self).setGeometry(rect)
        self._do(rect, False)

    @staticmethod
    def _shown(it):
        return it is not None and (it.widget() is None or not it.widget().isHidden())

    def _label_w(self):
        ws = [l.sizeHint().width() for l, f in self._rows if self._shown(l) and f is not None]
        w = max(ws) if ws else 0
        return min(w, self._lmax) if self._lmax else w

    def _field_min(self):
        ws = [f.minimumSize().width() for l, f in self._rows if self._shown(f) and self._shown(l)]
        return max(ws) if ws else 0

    def sizeHint(self):
        lw = self._label_w()
        w, h = 0, 0
        for l, f in self._rows:
            rw = (lw + self._h if self._shown(l) and f is not None else 0) + (f.sizeHint().width() if
                                                                               self._shown(f) else 0)
            if self._shown(l) and f is None:
                rw = l.sizeHint().width()
            w = max(w, rw)
            h += max(l.sizeHint().height() if self._shown(l) else 0, f.sizeHint().height() if self._shown(f) else 0)
        return QtCore.QSize(w, h)

    def minimumSize(self):
        w = 0
        for l, f in self._rows:
            for it in (l, f):
                if self._shown(it):
                    w = max(w, it.minimumSize().width())
        m = self.contentsMargins()
        return QtCore.QSize(w + m.left() + m.right(), 0)

    def stacked(self, width):
        lw = self._label_w()
        return lw and lw + self._h + self._field_min() > width

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        lw = self._label_w()
        stack = self.stacked(r.width())
        y = r.y()
        first = True
        for l, f in self._rows:
            sl, sf = self._shown(l), self._shown(f)
            if not sl and not sf:
                continue
            if not first:
                y += self._v
            first = False
            if sl and (f is None or not sf):
                h = l.heightForWidth(r.width()) if l.hasHeightForWidth() else l.sizeHint().height()
                if not test:
                    l.setGeometry(QtCore.QRect(r.x(), y, r.width(), h))
                y += h
                continue
            if sf and not sl:
                h = f.heightForWidth(r.width()) if f.hasHeightForWidth() else f.sizeHint().height()
                if not test:
                    f.setGeometry(QtCore.QRect(r.x(), y, r.width(), h))
                y += h
                continue
            if stack:
                lh = l.heightForWidth(r.width()) if l.hasHeightForWidth() else l.sizeHint().height()
                fh = f.heightForWidth(r.width()) if f.hasHeightForWidth() else f.sizeHint().height()
                if not test:
                    l.setGeometry(QtCore.QRect(r.x(), y, r.width(), lh))
                    f.setGeometry(QtCore.QRect(r.x(), y + lh + 2, r.width(), fh))
                y += lh + 2 + fh
            else:
                fw = r.width() - lw - self._h
                fh = f.heightForWidth(fw) if f.hasHeightForWidth() else f.sizeHint().height()
                lh = l.heightForWidth(lw) if l.hasHeightForWidth() else l.sizeHint().height()
                h = max(fh, lh)
                if not test:
                    f.setGeometry(QtCore.QRect(r.x() + lw + self._h, y, fw, fh))
                    lx = r.x() if self._align & Qt.AlignLeft else r.x() + lw - min(lw, l.sizeHint().width())
                    l.setGeometry(QtCore.QRect(lx, y + max(0, (fh - lh) // 2), min(lw, max(lw, 1)), lh))
                y += h
        return y - rect.y() + m.bottom()


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
        self._lb.setTextFormat(Qt.PlainText)          # 5.7.8: 'Shapes follow (<name>Shape)' was read as a tag
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
        self._lb.setTextFormat(Qt.PlainText)          # 5.7.8: 'Shapes follow (<name>Shape)' was read as a tag
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

    def minimumSizeHint(self):
        """Never narrower than its longest word (a word can't wrap - 5.7.7 cut '(<name>Shape)')."""
        self._lb.ensurePolished()
        fm = self._lb.fontMetrics()
        adv = fm.horizontalAdvance if hasattr(fm, "horizontalAdvance") else fm.width
        words = self._lb.text().split() or [""]
        return QtCore.QSize(max(max(adv(w) for w in words) + 30, min(self.sizeHint().width(), 90)),
                            max(20, fm.height() + 4))

    def sizeHint(self):
        self._lb.ensurePolished()
        fm = self._lb.fontMetrics()
        t = self._lb.text()
        w = fm.horizontalAdvance(t) if hasattr(fm, "horizontalAdvance") else fm.width(t)
        return QtCore.QSize(w + 30, max(20, fm.height() + 4))

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


class SegButton(QtWidgets.QPushButton):
    """A choice button: as wide as its words in bold (the picked one turns bold - 5.7.7 cut 'Above the objec')."""

    def sizeHint(self):
        hint = super(SegButton, self).sizeHint()
        f = QtGui.QFont(self.font())
        f.setBold(True)
        need = QtGui.QFontMetrics(f).horizontalAdvance(self.text().replace("&&", "&")) if hasattr(
            QtGui.QFontMetrics, "horizontalAdvance") else QtGui.QFontMetrics(f).width(self.text().replace("&&", "&"))
        return QtCore.QSize(max(hint.width(), need + 24), hint.height())

    def minimumSizeHint(self):
        return self.sizeHint()


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
            b = SegButton(str(text).replace("&", "&&"))      # '&' shown as '&' (not a shortcut mark)
            _set_role(b, "seg")
            b.setCursor(Qt.PointingHandCursor)
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
        return [b.text().replace("&&", "&") for b in self.buttons]


# --------------------------------------------------------------------------- the card
class Peek(QtWidgets.QLabel):
    """A closed card's hint of what's inside: one line that gives way when the window is narrow (ends in ...; the
    whole hint on hover) - 5.7.3, the header of a closed card made a narrow window too wide in Maya."""

    def minimumSizeHint(self):
        return QtCore.QSize(0, super(Peek, self).minimumSizeHint().height())

    def sizeHint(self):
        return QtCore.QSize(min(super(Peek, self).sizeHint().width(), 260), super(Peek, self).sizeHint().height())

    def setText(self, text):
        super(Peek, self).setText(text)
        self.setToolTip(text)

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        r = self.contentsRect()
        p.drawText(r, int(Qt.AlignLeft | Qt.AlignVCenter), self.fontMetrics().elidedText(self.text(), Qt.ElideRight,
                                                                                          r.width()))


class Card(QtWidgets.QFrame):
    """A numbered section: title, '?', pin; closed it shows what's inside in one line."""
    toggled = QtCore.Signal(bool)
    pin_clicked = QtCore.Signal()
    moved = QtCore.Signal(str, str)                   # 5.7.7: (this card's title, the title it goes before / a verb)

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
        self.number, self.state = number, None
        h.addWidget(self.num, 0, Qt.AlignTop)
        t = QtWidgets.QLabel(title)
        self.title_label = t
        t.setObjectName("gusCardTitle")
        t.setWordWrap(True)
        h.addWidget(t, 1)
        self.peek = Peek(peek)
        self.peek.setObjectName("gusPeek")
        h.addWidget(self.peek, 2)
        self.chip = QtWidgets.QLabel("")              # 5.7.7 new look: the step's state (Made / Ready / To do)
        self.chip.setObjectName("gusChip")
        self.chip.hide()
        h.addWidget(self.chip, 0, Qt.AlignVCenter)
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
        self.arr = QtWidgets.QWidget()                 # 5.7.8 Arrange: Up / Down / To top under the title
        ah = QtWidgets.QHBoxLayout(self.arr)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(6)
        self.arr_buttons = []
        for text, verb, tip in (("↑  Up", "Move up", "One place up"), ("↓  Down", "Move down", "One place down"),
                                ("⤒  To top", "Move to top", "First on this page")):
            b = QtWidgets.QPushButton(text)
            _set_role(b, "arrange")
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=verb: self.moved.emit(self.title, "@" + v))
            ah.addWidget(b)
            self.arr_buttons.append(b)
        ah.addStretch(1)
        self.arr.hide()
        v.addWidget(self.arr)
        self.arranging = False
        self.desc = QtWidgets.QLabel("")               # 5.7.7 new look: what the section does, one line
        self.desc.setObjectName("gusDesc")
        self.desc.setWordWrap(True)
        self.desc.hide()
        v.addWidget(self.desc)
        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(7)
        v.addWidget(self.body)
        self.head = head
        head.mousePressEvent = self._head_press
        head.mouseMoveEvent = self._head_move
        head.mouseReleaseEvent = self._head_release
        head.setContextMenuPolicy(Qt.CustomContextMenu)
        head.customContextMenuRequested.connect(self._head_menu)
        self.setAcceptDrops(True)
        self._press = None
        self.closed = False
        self.pinned_on = False
        self.hover_pin = True                         # 5.7.7: the pin shows when the mouse is over the card
        if self.hover_pin:
            self.pin.setVisible(False)
        self.set_closed(closed)

    def set_title(self, title):
        self.title = title
        self.title_label.setText(title)

    def set_arranging(self, on):
        """Arrange (5.7.8): closed to its title, with Up / Down / To top; off: back as it was."""
        if on == self.arranging:
            return
        self.arranging = on
        if on:
            self._was_closed = self.closed
            self.set_closed(True)
        else:
            self.set_closed(getattr(self, "_was_closed", self.closed))
        self.arr.setVisible(on)
        self.peek.setVisible(self.closed and bool(self.peek.text()) and not on)

    def _show_help(self):
        QtWidgets.QMessageBox.information(self, self.title, self.help_text)

    def set_closed(self, closed):
        self.closed = bool(closed)
        self.body.setVisible(not self.closed)
        if hasattr(self, "desc"):
            self.desc.setVisible(bool(self.desc.text()) and not self.closed)
        self.peek.setVisible(self.closed and bool(self.peek.text()))
        self.arrow.setPixmap(icons.pixmap("open" if self.closed else "more", 12, theme.FAINT))
        self.setProperty("closed", "true" if self.closed else "false")
        restyle(self)
        self.toggled.emit(not self.closed)

    # ------------------------------------------------ 5.7.7: your own order - drag by the title, or right-click it
    def _head_press(self, e):
        self._press = e.pos() if e.button() == Qt.LeftButton else None

    def _head_move(self, e):
        if self._press is None or getattr(self, "no_move", False):
            return
        if (e.pos() - self._press).manhattanLength() < 10:
            return
        self._press = None
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setText("gus-card:" + self.title)
        drag.setMimeData(mime)
        drag.setPixmap(self.head.grab())
        drag.exec_(Qt.MoveAction) if hasattr(drag, "exec_") else drag.exec(Qt.MoveAction)

    def _head_release(self, e):
        if self._press is not None and e.button() == Qt.LeftButton and not self.arranging:
            self.set_closed(not self.closed)
        self._press = None

    def _head_menu(self, pos):
        if getattr(self, "no_move", False):
            return
        m = QtWidgets.QMenu(self)
        for verb in ("Move up", "Move down", "Move to top", "Reset order"):
            a = m.addAction(verb)
            a.triggered.connect(lambda _=False, v=verb: self.moved.emit(self.title, "@" + v))
        m.exec_(self.head.mapToGlobal(pos)) if hasattr(m, "exec_") else m.exec(self.head.mapToGlobal(pos))

    def dragEnterEvent(self, e):
        text = e.mimeData().text() if e.mimeData() else ""
        if text.startswith("gus-card:") and text[9:] != self.title:
            e.acceptProposedAction()

    def dropEvent(self, e):
        src = e.mimeData().text()[9:]
        e.acceptProposedAction()
        self.moved.emit(src, self.title)              # the dragged card goes before this one

    def enterEvent(self, e):
        if getattr(self, "hover_pin", False) and not getattr(self, "no_pin", False) and \
                not self.property("inner") == "true":
            self.pin.setVisible(True)
        super(Card, self).enterEvent(e)

    def leaveEvent(self, e):
        if getattr(self, "hover_pin", False) and not self.pinned_on:
            self.pin.setVisible(False)
        super(Card, self).leaveEvent(e)

    def set_pinned(self, on):
        self.pinned_on = bool(on)
        if getattr(self, "hover_pin", False):
            self.pin.setVisible(bool(on))
        self.setProperty("pinned", "true" if on else "false")
        self.pin.setIcon(icons.icon("pin", 14, "#ffcf5c" if on else theme.FAINT))
        self.pin.setToolTip("Unpin" if on else "Pin: this card stays on top of every page of this area")
        restyle(self)

    def add(self, w):
        self.body_layout.addWidget(w)
        return w

    # 5.7.4: a step's state on its number - made: a tick (green), ready (your selection fits): a yellow dot
    def set_number(self, n):
        self.number = n
        self._badge()

    def set_state(self, level):
        self.state = level if level in ("made", "ready") else None
        self._badge()
        if level in theme.CHIP:                        # 5.7.7: the state as a tag on the title line
            bg, fg, word = theme.CHIP[level]
            self.chip.setText(word)
            self.chip.setStyleSheet("QLabel#gusChip { background: %s; color: %s; }" % (bg, fg))
            self.chip.show()

    def set_desc(self, text):
        self.desc.setText(text)
        self.desc.setVisible(bool(text) and not self.closed)

    def _badge(self):
        if not self.number:
            return
        mark = {"made": "✓", "ready": "●"}.get(self.state)
        self.num.setText(mark or str(self.number))
        colour = {"made": theme.OK, "ready": theme.WARN}.get(self.state)
        self.num.setStyleSheet("QLabel#gusNum { background: %s; color: #111; }" % colour if colour else "")
        self.num.setToolTip({"made": "Done", "ready": "Your selection fits: press its button"}.get(self.state, ""))


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


# --------------------------------------------------------------------------- 5.7.4 steps: Face, Ribbon
STATE_COLOUR = {"made": theme.OK, "ready": theme.WARN, "on": "#e0893a", "todo": "#5a6069"}
STATE_WORD = {"made": "made", "ready": "ready - your selection fits", "todo": "not made yet"}


class FaceMap(QtWidgets.QWidget):
    """A face drawn with its parts coloured by state: green made, yellow ready (your selection fits), grey not yet.
    The right side dashed: it's mirrored for you. Click a part: its step."""
    clicked = QtCore.Signal(str)
    PARTS = ("brows", "eyes", "eyelids", "mouth", "strip")

    def __init__(self, parent=None):
        super(FaceMap, self).__init__(parent)
        self.states = dict((p, "todo") for p in self.PARTS)
        self.setMinimumSize(140, 140)
        self.setMaximumSize(200, 200)
        self.setCursor(Qt.PointingHandCursor)
        self._hit = {}

    def sizeHint(self):
        return QtCore.QSize(190, 190)

    def set_states(self, states):
        self.states.update(dict((k, v) for k, v in states.items() if k in self.PARTS))
        self.setToolTip("\n".join("%s: %s" % (p.title(), STATE_WORD.get(self.states[p], "")) for p in self.PARTS))
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 8
        p.translate((self.width() - side) / 2.0, 4)
        p.scale(side / 200.0, side / 200.0)
        p.setPen(QtGui.QPen(QtGui.QColor("#6b7079"), 2))
        p.setBrush(QtGui.QColor("#2a2d32"))
        p.drawEllipse(QtCore.QRectF(28, 8, 144, 184))
        self._hit = {}

        def pen(part, width=5, right=False):
            q = QtGui.QPen(QtGui.QColor(STATE_COLOUR[self.states.get(part, "todo")]), width)
            q.setCapStyle(Qt.RoundCap)
            if right:
                q.setStyle(Qt.DashLine)
            return q
        for right in (False, True):
            m = (lambda x: 200 - x) if right else (lambda x: x)
            brow = QtGui.QPainterPath(QtCore.QPointF(m(52), 64))
            brow.quadTo(QtCore.QPointF(m(72), 52), QtCore.QPointF(m(90), 60))
            p.setPen(pen("brows", 6, right))
            p.setBrush(Qt.NoBrush)
            p.drawPath(brow)
            p.setPen(pen("eyelids", 5, right))
            p.drawEllipse(QtCore.QRectF(m(72) - 18, 80, 36, 20))
            p.setPen(Qt.NoPen)
            p.setBrush(QtGui.QColor(STATE_COLOUR[self.states.get("eyes", "todo")]))
            p.drawEllipse(QtCore.QPointF(m(72), 90), 5, 5)
            p.setBrush(Qt.NoBrush)
            strip = QtGui.QPainterPath(QtCore.QPointF(m(56), 112))
            strip.quadTo(QtCore.QPointF(m(62), 132), QtCore.QPointF(m(74), 142))
            p.setPen(pen("strip", 5, right))
            p.drawPath(strip)
        mouth = QtGui.QPainterPath(QtCore.QPointF(74, 152))
        mouth.quadTo(QtCore.QPointF(100, 140), QtCore.QPointF(126, 152))
        mouth.quadTo(QtCore.QPointF(100, 170), QtCore.QPointF(74, 152))
        p.setPen(pen("mouth", 5))
        p.drawPath(mouth)
        s = side / 200.0
        ox = (self.width() - side) / 2.0
        for part, (x, y, w, h) in (("brows", (48, 46, 46, 22)), ("eyelids", (50, 76, 44, 30)),
                                   ("strip", (48, 108, 32, 38)), ("mouth", (70, 138, 60, 34))):
            self._hit[part] = QtCore.QRectF(ox + x * s, 4 + y * s, w * s, h * s)

    def mousePressEvent(self, e):
        pos = e.position() if hasattr(e, "position") else e.pos()
        for part, r in self._hit.items():
            if r.contains(QtCore.QPointF(pos)):
                self.clicked.emit(part)
                return


class StepStrip(QtWidgets.QFrame):
    """1 Surface -> 2 Joints -> 3 Controls -> 4 Create: each step's state (a tick when done, a yellow dot when your
    selection fits, orange for the step you're on). Click one: its card."""
    clicked = QtCore.Signal(int)

    def __init__(self, labels, parent=None):
        super(StepStrip, self).__init__(parent)
        self.setObjectName("gusSel")
        self.lay = FlowLayout(self, 8)
        self.lay.setContentsMargins(9, 7, 9, 7)
        self.items = []
        for i, text in enumerate(labels):
            b = QtWidgets.QToolButton()
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setAutoRaise(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self.clicked.emit(i))
            self.lay.addWidget(b)
            self.items.append((b, text))
        self.set_states(["todo"] * len(labels))

    def set_states(self, states):
        self.states = list(states)
        for i, ((b, text), st) in enumerate(zip(self.items, states)):
            mark = {"made": "✓", "ready": "●"}.get(st, str(i + 1))
            colour = STATE_COLOUR.get(st, STATE_COLOUR["todo"])
            pm = QtGui.QPixmap(20, 20)
            pm.fill(Qt.transparent)
            q = QtGui.QPainter(pm)
            q.setRenderHint(QtGui.QPainter.Antialiasing)
            q.setPen(Qt.NoPen)
            q.setBrush(QtGui.QColor(colour))
            q.drawEllipse(0, 0, 20, 20)
            q.setPen(QtGui.QColor("#111"))
            f = q.font()
            f.setBold(True)
            f.setPixelSize(11)
            q.setFont(f)
            q.drawText(QtCore.QRect(0, 0, 20, 20), int(Qt.AlignCenter), mark)
            q.end()
            b.setIcon(QtGui.QIcon(pm))
            b.setText(text + ("  →" if i < len(self.items) - 1 else ""))
            b.setToolTip("%s: %s" % (text, STATE_WORD.get(st, "the step you're on" if st == "on" else "")))


class Fold(QtWidgets.QWidget):
    """5.7.7 new look: 'Options (n) ▾  what's set' - the choices you rarely change, one click away (they stay the
    tool's own fields: folded, they still answer the tool)."""

    def __init__(self, title="Options", summary=None, parent=None):
        super(Fold, self).__init__(parent)
        self.title, self.summary = title, summary
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        head = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(head)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        self.button = QtWidgets.QPushButton("")
        _set_role(self.button, "fold")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.clicked.connect(self.toggle)
        h.addWidget(self.button)
        self.words = Peek("")                       # what's set: gives way when narrow (ends in ...)
        self.words.setObjectName("gusPeek")
        h.addWidget(self.words, 1)
        v.addWidget(head)
        self.body = QtWidgets.QWidget()
        self.body_layout = QtWidgets.QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(6)
        v.addWidget(self.body)
        self.count = 0
        self.body.hide()
        self.refresh()

    def add(self, w):
        self.body_layout.addWidget(w)
        self.count += 1
        self.refresh()

    def toggle(self):
        self.body.setVisible(self.body.isHidden())
        self.refresh()

    def refresh(self, *_):
        words = ""
        if self.summary is not None:
            try:
                words = self.summary()
            except Exception:
                words = ""
        arrow = "▾" if self.body.isHidden() else "▴"
        text = "%s (%d)  %s" % (self.title, self.count, arrow) if self.count and self.title == "Options" else \
            "%s  %s" % (self.title, arrow)
        self.button.setText(text.replace("&", "&&"))
        self.words.setText(words if self.body.isHidden() else "")
