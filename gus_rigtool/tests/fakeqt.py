# A stand-in for PySide (no Qt here): just enough for pickerqt.py to build, paint and take mouse / key events in
# the tests. It checks our code paths (names, data flow), not Qt itself.
import sys
import types


class Signal(object):
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *a):
        for fn in self.slots:
            fn(*a)


class Any(object):
    """Accepts any call / attribute (painter, fonts, layouts...)."""
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Any()

    def __call__(self, *a, **k):
        return Any()

    def __bool__(self):
        return True

    def __int__(self):
        return 0

    def __float__(self):
        return 0.0


class QPointF(object):
    def __init__(self, x=0.0, y=0.0):
        if isinstance(x, QPointF):
            x, y = x._x, x._y
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __add__(self, o):
        return QPointF(self._x + o._x, self._y + o._y)

    def __sub__(self, o):
        return QPointF(self._x - o._x, self._y - o._y)


class QRectF(object):
    def __init__(self, a=None, b=None, w=None, h=None):
        if isinstance(a, QPointF):
            self.l, self.t, self.r, self.b = a.x(), a.y(), b.x(), b.y()
        elif a is None:
            self.l = self.t = self.r = self.b = 0.0
        elif w is not None:
            self.l, self.t, self.r, self.b = a, b, a + w, b + h
        else:
            self.l = self.t = 0.0
            self.r = self.b = 10.0

    def left(self):
        return self.l

    def right(self):
        return self.r

    def top(self):
        return self.t

    def bottom(self):
        return self.b

    def width(self):
        return self.r - self.l

    def height(self):
        return self.b - self.t

    def center(self):
        return QPointF((self.l + self.r) / 2, (self.t + self.b) / 2)

    def adjusted(self, a, b, c, d):
        return QRectF(QPointF(self.l + a, self.t + b), QPointF(self.r + c, self.b + d))

    def contains(self, p):
        return self.l <= p.x() <= self.r and self.t <= p.y() <= self.b


class Enum(object):
    def __init__(self):
        self._n = 1

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        self._n *= 2
        setattr(self, name, self._n)
        return self._n


Qt = Enum()
for _n in ("NoModifier",):
    setattr(Qt, _n, 0)
DRAWN = []                                                   # (kind, text) the painter drew


class QPainter(Any):
    Antialiasing = 1

    def drawText(self, rect, flags, text):
        DRAWN.append(("text", text))

    def fillPath(self, path, colour):
        DRAWN.append(("fill", None))


class QColor(Any):
    @staticmethod
    def fromRgbF(r, g, b, a=1.0):
        c = QColor()
        c.rgb = (r, g, b)
        return c

    def lighter(self, n):
        return self


class QFontMetrics(Any):
    def elidedText(self, text, mode, width):
        return text

    def height(self):
        return 12


class QWidget(object):
    def __init__(self, parent=None, *a):
        self._visible = True
        self._w, self._h = 400, 600

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Any()

    def width(self):
        return self._w

    def height(self):
        return self._h

    def rect(self):
        return QRectF(0, 0, self._w, self._h)

    def setVisible(self, v):
        self._visible = v

    def isVisible(self):
        return self._visible

    def update(self):
        pass

    def objectName(self):
        return "w"


class QPushButton(QWidget):
    def __init__(self, label="", parent=None):
        QWidget.__init__(self)
        self.label = label
        self.clicked = Signal()
        self.toggled = Signal()
        self.checked = False
        BUTTONS.append(self)

    def setText(self, t):
        self.label = t

    def setChecked(self, v):
        self.checked = v
        self.toggled.emit(v)

    def isChecked(self):
        return bool(self.checked)

    def setMenu(self, m):
        self.menu = m


BUTTONS = []
TOOLS = []
MENUS = []


class QToolButton(QPushButton):
    """5.6.21: the picker's quick buttons (icon + word)."""
    MenuButtonPopup = 1
    InstantPopup = 2

    def __init__(self, parent=None):
        super(QToolButton, self).__init__("", parent)
        BUTTONS.remove(self)                                 # kept apart from the push buttons
        TOOLS.append(self)

    def setIcon(self, icon):
        self.icon = icon

    def setToolButtonStyle(self, s):
        pass

    def setPopupMode(self, m):
        pass


class QMenu(object):
    def __init__(self, *a):
        self.actions = []
        self.aboutToShow = Signal()
        MENUS.append(self)

    def clear(self):
        self.actions = []

    def addAction(self, label, fn=None):
        self.actions.append((label, fn))
        return Any()

    def addMenu(self, label):
        m = QMenu()
        self.actions.append((label, m))
        return m

    def addSeparator(self):
        pass

    def exec_(self, *a):
        return None

    def find(self, label):
        for lab, fn in self.actions:
            if lab == label:
                return fn
            if isinstance(fn, QMenu):
                got = fn.find(label)
                if got:
                    return got
        return None


class QComboBox(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.items = []
        self.index = -1
        self.currentIndexChanged = Signal()

    def clear(self):
        self.items, self.index = [], -1

    def addItem(self, label, data=None):
        self.items.append((label, data))
        if self.index < 0:
            self.index = 0

    def setCurrentIndex(self, i):
        self.index = i

    def currentData(self):
        return self.items[self.index][1] if 0 <= self.index < len(self.items) else None

    def count(self):
        return len(self.items)

    def itemData(self, i):
        return self.items[i][1]

    def blockSignals(self, v):
        pass


class QLabel(QWidget):
    def __init__(self, text=""):
        QWidget.__init__(self)
        self.text = text


class QLineEdit(QWidget):
    """5.6.22: the picker's Item panel."""
    def __init__(self, text=""):
        QWidget.__init__(self)
        self._t = text
        self.editingFinished = Signal()

    def text(self):
        return self._t

    def setText(self, t):
        self._t = t

    def hasFocus(self):
        return False


class QDoubleSpinBox(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self._v = 0.0
        self.editingFinished = Signal()

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = float(v)

    def hasFocus(self):
        return False


class QCheckBox(QWidget):
    def __init__(self, label=""):
        QWidget.__init__(self)
        self._on = False
        self.toggled = Signal()

    def isChecked(self):
        return self._on

    def setChecked(self, v):
        self._on = bool(v)


class QTabBar(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.tabs = []
        self.currentChanged = Signal()

    def count(self):
        return len(self.tabs)

    def removeTab(self, i):
        self.tabs.pop(i)

    def addTab(self, t):
        self.tabs.append(t)

    def setCurrentIndex(self, i):
        self.cur = i

    def blockSignals(self, v):
        pass


class QImage(Any):
    """5.6.24: the outline / picture images."""
    Format_ARGB32_Premultiplied = 6
    Format_ARGB32 = 5

    def save(self, *a):
        return True

    def isNull(self):
        return False


class QPlainTextEdit(QWidget):
    def __init__(self, *a):
        QWidget.__init__(self)
        self._t = ""

    def setPlainText(self, t):
        self._t = t

    def toPlainText(self):
        return self._t


class QBuffer(object):
    """5.6.25: pictures to PNG bytes."""
    def open(self, *a):
        return True

    def data(self):
        return b"\x89PNG-fake"


class QIODevice(object):
    WriteOnly = 2


class QSlider(QWidget):
    """5.6.23: the picker's text size."""
    def __init__(self, *a):
        QWidget.__init__(self)
        self._v = 0
        self.valueChanged = Signal()

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = int(v)
        self.valueChanged.emit(self._v)

    def blockSignals(self, v):
        pass


class QListWidgetItem(object):
    """5.6.23: the picker's button list / missing controls."""
    def __init__(self, text=""):
        self._t, self._d, self._hidden, self._check, self._sel = text, {}, False, None, False

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Any()

    def text(self):
        return self._t

    def setData(self, role, v):
        self._d[role] = v

    def data(self, role):
        return self._d.get(role)

    def setHidden(self, v):
        self._hidden = bool(v)

    def isHidden(self):
        return self._hidden

    def flags(self):
        return 0

    def setCheckState(self, v):
        self._check = v

    def checkState(self):
        return self._check

    def setSelected(self, v):
        self._sel = bool(v)


class QListWidget(QWidget):
    def __init__(self, *a):
        QWidget.__init__(self)
        self.rows = []
        self.itemSelectionChanged = Signal()

    def clear(self):
        self.rows = []

    def addItem(self, row):
        self.rows.append(row)

    def count(self):
        return len(self.rows)

    def item(self, i):
        return self.rows[i]

    def selectedItems(self):
        return [r for r in self.rows if r._sel]


class QAbstractItemView(object):
    ExtendedSelection = 3


class QDialog(QWidget):
    answer = [0]                                    # 0: closed / cancelled

    def __init__(self, *a):
        QWidget.__init__(self)

    def exec_(self, *a):
        return QDialog.answer[0]


setattr(QDialog, "exec", QDialog.exec_)


class QDialogButtonBox(object):
    Ok, Cancel = 1, 2

    def __init__(self, *a):
        self.accepted, self.rejected = Signal(), Signal()


class QMessageBox(object):
    Save, Discard, Cancel, Yes, No = 1, 2, 4, 8, 16
    answer = [8]

    @staticmethod
    def question(*a, **k):
        return QMessageBox.answer[0]


class QInputDialog(object):
    text = ["new"]

    @staticmethod
    def getText(*a, **k):
        return QInputDialog.text[0], True

    @staticmethod
    def getMultiLineText(*a, **k):
        return "cmds.select(clear=True)", True


class QColorDialog(object):
    @staticmethod
    def getColor(*a, **k):
        c = Any()
        c.isValid = lambda: True
        c.redF, c.greenF, c.blueF = (lambda: 0.1), (lambda: 0.9), (lambda: 0.2)
        return c


class QFileDialog(object):
    @staticmethod
    def getOpenFileName(*a, **k):
        return "C:/pics/hare_front.png", ""


class Event(object):
    """A mouse / wheel / key event."""
    def __init__(self, x=0, y=0, button=None, mods=0, key=None, delta=0):
        self.p = QPointF(x, y)
        self.b = button
        self.m = mods
        self.k = key
        self.d = delta

    def position(self):
        return self.p

    def pos(self):
        return self.p

    def globalPos(self):
        return self.p

    def button(self):
        return self.b

    def modifiers(self):
        return self.m

    def key(self):
        return self.k

    def angleDelta(self):
        return QPointF(0, self.d)


def install():
    core = types.ModuleType("PySide6.QtCore")
    core.Qt, core.QPointF, core.QRectF = Qt, QPointF, QRectF
    gui = types.ModuleType("PySide6.QtGui")
    gui.QPainter, gui.QColor, gui.QFontMetrics = QPainter, QColor, QFontMetrics
    gui.QPainterPath = gui.QPolygonF = gui.QPen = gui.QPixmap = gui.QIcon = gui.QTransform = gui.QBrush = Any
    gui.QImage = QImage
    core.QBuffer, core.QIODevice = QBuffer, QIODevice
    widgets = types.ModuleType("PySide6.QtWidgets")
    widgets.QWidget = QWidget
    widgets.QPushButton = QPushButton
    widgets.QToolButton = QToolButton
    widgets.QLabel, widgets.QLineEdit, widgets.QDoubleSpinBox, widgets.QCheckBox = QLabel, QLineEdit, \
        QDoubleSpinBox, QCheckBox
    widgets.QMenu = QMenu
    widgets.QComboBox = QComboBox
    widgets.QTabBar = QTabBar
    widgets.QMessageBox = QMessageBox
    widgets.QInputDialog = QInputDialog
    widgets.QColorDialog = QColorDialog
    widgets.QFileDialog = QFileDialog
    widgets.QVBoxLayout = widgets.QHBoxLayout = widgets.QGridLayout = widgets.QFormLayout = Any
    widgets.QScrollArea = Any
    widgets.QPlainTextEdit = QPlainTextEdit
    widgets.QSlider, widgets.QListWidget, widgets.QListWidgetItem = QSlider, QListWidget, QListWidgetItem
    widgets.QAbstractItemView, widgets.QDialog, widgets.QDialogButtonBox = QAbstractItemView, QDialog, \
        QDialogButtonBox
    widgets.QSizePolicy = Any()
    pkg = types.ModuleType("PySide6")
    pkg.QtCore, pkg.QtGui, pkg.QtWidgets = core, gui, widgets
    shib = types.ModuleType("shiboken6")
    shib.wrapInstance = lambda ptr, cls: None
    sys.modules.update({"PySide6": pkg, "PySide6.QtCore": core, "PySide6.QtGui": gui, "PySide6.QtWidgets": widgets,
                        "shiboken6": shib})
