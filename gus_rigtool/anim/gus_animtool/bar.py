"""
The Animtool bar (5.6.43): every Animtool tool in a small strip that floats over Maya - the same icons and
right-click menus as the toolbar, plus the Attach window and the Arcs panel one click away. Drag it by its handle;
the arrows button turns it from a row into a column; it remembers where you left it and how it was.

    import gus_animtool.bar as b; b.show()
"""
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

from gus_animtool import actions as AC
from gus_animtool import anim as A

_BAR = None
NAME = "gusAnimtoolBar"
SIZE = 26                       # a button
LINES = 2                       # a row: 2 lines of icons
COLUMNS = 3                     # a column: 3 columns (not too tall for a laptop screen)
# the windows, right after their tool (not actions of their own on the shelf / toolbar: on the bar only)
EXTRA = {"release": "attach_window", "arcs": "arcs_panel"}
EXTRA_INFO = {"attach_window": ("Attach window", "The Attach window: what's attached, who holds it over time, its "
                                                 "changes"),
              "arcs_panel": ("Arcs panel", "The Arcs panel: every arc, its colour, range, look")}
STYLE = """
QWidget#gusAnimtoolBar { background:#3c3c3c; border:1px solid #222; }
QToolButton { border:none; border-radius:3px; padding:1px; }
QToolButton:hover { background:#5a5a5a; }
QToolButton:pressed { background:#5285a6; }
QLabel#handle { color:#888; }
"""


def _maya_window():
    try:
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None
    except Exception:
        return None


def all_keys():
    """Every tool, in the toolbar's order, the windows right after their tool; the bar's own button left out."""
    out = []
    for k, _l, _t, _g in AC.ACTIONS:
        if k == "bar":
            continue
        out.append(k)
        if k in EXTRA:
            out.append(EXTRA[k])
    return out


def keys():
    """What the bar shows: your choice (Options > Choose buttons...), else every tool."""
    every = all_keys()
    got = A.opt("bar_keys", "")
    if not got:
        return every
    chosen = set(k for k in got.split(",") if k)
    return [k for k in every if k in chosen] or every


def set_keys(chosen):
    """Keep this choice (empty or all: every tool, so new tools show up too)."""
    every = all_keys()
    chosen = [k for k in every if k in set(chosen)]
    A.set_opt("bar_keys", "" if not chosen or len(chosen) == len(every) else ",".join(chosen))


def group_of(key):
    for k, extra in EXTRA.items():
        if key == extra:
            return AC.info(k)[3]
    return AC.info(key)[3]


def label_tip(key):
    if key in EXTRA_INFO:
        return EXTRA_INFO[key]
    _k, label, tip, _g = AC.info(key)
    return label, tip


def split(items, lines=LINES):
    """The groups shared out over lines, a group never cut in two, the lines about as long."""
    groups, last = [], None
    for k in items:
        g = group_of(k)
        if g != last:
            groups.append([])
            last = g
        groups[-1].append(k)
    total = len(items)
    out, cur, done = [], [], 0
    for g in groups:
        target = total * (len(out) + 1) / float(lines)
        if cur and len(out) < lines - 1 and abs(done + len(g) - target) > abs(done - target):
            out.append(cur)
            cur = []
        cur.append(g)
        done += len(g)
    out.append(cur)
    return out


def show():
    global _BAR
    try:
        if _BAR is not None and _BAR.isVisible():
            _BAR.raise_()
            return _BAR
    except RuntimeError:
        pass
    _BAR = Bar()
    _BAR.show()
    return _BAR


def close():
    global _BAR
    try:
        if _BAR is not None:
            _BAR.close()
    except RuntimeError:
        pass
    _BAR = None


def _global(e):
    try:
        return e.globalPosition().toPoint()
    except AttributeError:
        return e.globalPos()


class Bar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Bar, self).__init__(parent or _maya_window())
        # a tool window: stays in front of Maya (on the Mac too, even when Maya isn't the active app)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        _keep_shown = getattr(QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
        if _keep_shown is not None:
            self.setAttribute(_keep_shown, True)
        self.setObjectName(NAME)
        self.setWindowTitle("Gus Animtool bar")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet(STYLE)
        self._dragFrom = None
        self.vertical = bool(A.opt("bar_vertical", 0))
        self.buttons = {}
        self.tween = None
        self._build()
        x, y = int(A.opt("bar_x", -1)), int(A.opt("bar_y", -1))
        if x >= 0 and y >= 0:
            self.move(x, y)

    # ------------------------------------------------------------------ building
    def _clear(self):
        lay = self.layout()
        if lay is None:
            return
        QtWidgets.QWidget().setLayout(lay)          # the old layout and its buttons go with a throwaway widget

    def _build(self):
        self._clear()
        self.buttons, self.tween = {}, None
        v = self.vertical
        outer = QtWidgets.QHBoxLayout(self) if v else QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(3, 3, 3, 3)
        outer.setSpacing(2)
        top = QtWidgets.QVBoxLayout() if not v else QtWidgets.QHBoxLayout()
        head = QtWidgets.QHBoxLayout() if not v else QtWidgets.QVBoxLayout()
        head.setSpacing(2)
        self.handle = QtWidgets.QLabel("::" if not v else "..")
        self.handle.setObjectName("handle")
        self.handle.setToolTip("Drag here to move the bar")
        self.handle.setCursor(QtCore.Qt.SizeAllCursor)
        self.handle.setAlignment(QtCore.Qt.AlignCenter)
        self.handle.setFixedSize(14 if not v else SIZE, SIZE if not v else 14)
        head.addWidget(self.handle)
        flip = self._small("<>" if not v else "^v", "A row / a column", self.flip)
        menu = self._small("=", "Options", self.options)
        shut = self._small("x", "Close the bar (it opens again with the Animtool window - Options to stop that)",
                           self.close)
        for w in (flip, menu, shut):
            head.addWidget(w)
        head.addStretch(1)
        body = QtWidgets.QHBoxLayout() if not v else QtWidgets.QVBoxLayout()
        body.setSpacing(2)
        body.addLayout(head)
        lines = QtWidgets.QVBoxLayout() if not v else QtWidgets.QHBoxLayout()
        lines.setSpacing(1)
        for line in split(keys(), COLUMNS if v else LINES):
            lay = QtWidgets.QHBoxLayout() if not v else QtWidgets.QVBoxLayout()
            lay.setSpacing(1)
            for gi, group in enumerate(line):
                if gi:
                    sep = QtWidgets.QFrame()
                    sep.setFrameShape(QtWidgets.QFrame.VLine if not v else QtWidgets.QFrame.HLine)
                    sep.setStyleSheet("color:#2a2a2a;")
                    lay.addWidget(sep)
                for k in group:
                    lay.addWidget(self._button(k))
                    if k == "tween_prev":
                        lay.addWidget(self._tween_slider())
            lay.addStretch(1)
            lines.addLayout(lay)
        body.addLayout(lines)
        top.addLayout(body)
        outer.addLayout(top)
        self.adjustSize()

    def _small(self, text, tip, fn):
        b = QtWidgets.QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setFixedSize(SIZE - 6, SIZE - 6)
        b.clicked.connect(lambda *_: fn())
        return b

    def _button(self, key):
        label, tip = label_tip(key)
        b = QtWidgets.QToolButton()
        b.setObjectName("gusAnimtoolBar_" + key)
        path = AC.icon(key)
        if path.endswith("pythonFamily.png"):
            b.setText(label[:3])
        else:
            b.setIcon(QtGui.QIcon(path))
            b.setIconSize(QtCore.QSize(SIZE - 4, SIZE - 4))
        b.setFixedSize(SIZE, SIZE)
        menu = AC.MENUS.get(key, [])
        b.setToolTip("%s: %s%s" % (label, tip, " (right-click for more)" if menu else ""))
        b.clicked.connect(lambda *_: AC.run(key))
        if menu:
            b.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, k=key, w=b: self._menu(k, w, pos))
        self.buttons[key] = b
        return b

    def menu_for(self, key):
        m = QtWidgets.QMenu(self)
        for label, sub in AC.MENUS.get(key, []):
            act = m.addAction(label)
            act.triggered.connect(lambda *_, s=sub: AC.run(s))
        return m

    def _menu(self, key, widget, pos):
        self.menu_for(key).exec_(widget.mapToGlobal(pos))

    def _tween_slider(self):
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal if not self.vertical else QtCore.Qt.Vertical)
        s.setRange(-100, 100)
        s.setValue(0)
        if self.vertical:
            s.setFixedHeight(90)
        else:
            s.setFixedWidth(90)
        s.setToolTip("Tween: drag to see it, let go to apply (mode: the window's Pose tab).")
        s.sliderMoved.connect(self._tween_drag)
        s.sliderReleased.connect(self._tween_release)
        self.tween = s
        return s

    # ------------------------------------------------------------------ the tween
    def _tween_drag(self, value):
        from gus_animtool import tween as T
        from gus_animtool import ui
        try:
            mode = int(A.opt("tween_mode", 1)) - 1
            T.drag(ui._tween_nodes(), mode, ui._amount(value, mode))
        except (RuntimeError, ValueError) as e:
            A.message(str(e), "warn")

    def _tween_release(self):
        from gus_animtool import tween as T
        from gus_animtool import ui
        value = self.tween.value()
        try:
            mode = int(A.opt("tween_mode", 1)) - 1
            if T._drag.get("start") is None:
                T.apply(ui._tween_nodes(), mode, ui._amount(value, mode))
            else:
                T.release(mode, ui._amount(value, mode))
        except (RuntimeError, ValueError) as e:
            A.message(str(e), "warn")
        finally:
            self.tween.setValue(0)

    # ------------------------------------------------------------------ options
    def flip(self):
        self.vertical = not self.vertical
        A.set_opt("bar_vertical", int(self.vertical))
        self._build()

    def options(self):
        m = QtWidgets.QMenu(self)
        auto = m.addAction("Open the bar with the Animtool window")
        auto.setCheckable(True)
        auto.setChecked(bool(A.opt("bar_auto", 1)))
        auto.toggled.connect(lambda on: A.set_opt("bar_auto", int(bool(on))))
        m.addAction("The Animtool window").triggered.connect(lambda *_: AC.run("main"))
        m.addAction("A row / a column").triggered.connect(lambda *_: self.flip())
        m.addAction("Choose buttons...").triggered.connect(lambda *_: self.choose())
        m.addSeparator()
        m.addAction("Copy the last problem").triggered.connect(lambda *_: copy_last_problem())
        m.addAction("Test this release (in this Maya)...").triggered.connect(lambda *_: test_this_release())
        m.exec_(QtGui.QCursor.pos())

    def choose(self):
        """A tick per tool; OK keeps the choice and rebuilds the bar."""
        d = Chooser(self)
        if d.exec_():
            set_keys(d.chosen())
            self._build()
        return d

    # ------------------------------------------------------------------ moving
    def mousePressEvent(self, e):
        if self.handle.geometry().contains(e.pos()):
            self._dragFrom = _global(e) - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragFrom is not None:
            self.move(_global(e) - self._dragFrom)

    def mouseReleaseEvent(self, _e):
        if self._dragFrom is not None:
            self._dragFrom = None
            self._remember()

    def _remember(self):
        p = self.pos()
        A.set_opt("bar_x", int(p.x()))
        A.set_opt("bar_y", int(p.y()))

    def closeEvent(self, e):
        self._remember()
        super(Bar, self).closeEvent(e)


class Chooser(QtWidgets.QDialog):
    """Which tools the bar shows: a tick per tool (its icon and name), All / None, OK."""

    def __init__(self, parent=None):
        super(Chooser, self).__init__(parent)
        self.setWindowTitle("Bar buttons")
        self.resize(300, 560)
        lay = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel("Tick the tools the bar shows.")
        lay.addWidget(note)
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(inner)
        col.setSpacing(1)
        shown = set(keys())
        self.boxes = []
        for k in all_keys():
            label, tip = label_tip(k)
            b = QtWidgets.QCheckBox(label)
            b.setToolTip(tip)
            path = AC.icon(k)
            if not path.endswith("pythonFamily.png"):
                b.setIcon(QtGui.QIcon(path))
            b.setChecked(k in shown)
            col.addWidget(b)
            self.boxes.append((k, b))
        col.addStretch(1)
        area.setWidget(inner)
        lay.addWidget(area)
        row = QtWidgets.QHBoxLayout()
        for text, on in (("All", True), ("None", False)):
            btn = QtWidgets.QPushButton(text)
            btn.clicked.connect(lambda *_, v=on: [b.setChecked(v) for _k, b in self.boxes])
            row.addWidget(btn)
        row.addStretch(1)
        ok = QtWidgets.QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)

    def chosen(self):
        return [k for k, b in self.boxes if b.isChecked()]


def copy_last_problem():
    """The last warning / error, with the details and the versions, on the clipboard - paste it in a message."""
    text = A.problem_report()
    if not text:
        A.message("no problem since Maya started - nothing to copy.")
        return ""
    QtWidgets.QApplication.clipboard().setText(text)
    A.message("the last problem is on the clipboard - paste it in your message.")
    return text


def test_this_release():
    """The checks that need Maya's window (Gus_Rigtool's realmaya/window_checks.py), on a new empty scene."""
    try:
        from gus_rigtool.realmaya import window_checks
    except ImportError as e:
        A.message("Test this release needs Gus_Rigtool (%s)." % e, "warn")
        return None
    return window_checks.run()
