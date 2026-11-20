"""
Your favourite tools (5.7.1): a row at the top of the new window (the old window's My tools row) and a floating
bar you keep anywhere over Maya. One list for both - the same one the old window's My tools used (myTools).

Click: go to that tool. Right-click: Pop out / Move left / Move right / Remove. '+' chooses them; the star on a
page's header adds or removes that page. Map: where everything is.
"""

from gus_rigtool.newui import theme, widgets
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
BAR_KEY = "favBar"
_listeners = []
_bar = {"w": None}


# --------------------------------------------------------------------------- the list
def keys():
    from gus_rigtool.core import ui
    return [k for k in ui.my_tools() if k != "home"]


def set_keys(new):
    from gus_rigtool.core import utils
    out = []
    for k in new:
        if k not in out:
            out.append(k)
    utils.save_setting("myTools", out)
    changed()


def toggle(key):
    from gus_rigtool import registry
    key = registry.resolve(key)[0]
    now = keys()
    set_keys([k for k in now if k != key] if key in now else now + [key])
    return key in keys()


def move(key, step):
    now = keys()
    if key in now:
        i = now.index(key)
        j = max(0, min(len(now) - 1, i + step))
        now[i], now[j] = now[j], now[i]
        set_keys(now)


def changed():
    for fn in list(_listeners):
        try:
            fn()
        except RuntimeError:                     # its widget is gone
            _listeners.remove(fn)


def label(key):
    from gus_rigtool import registry
    try:
        return registry.get(key)[1]
    except KeyError:
        return key


def area_colour(key):
    from gus_rigtool.newui import window
    return theme.colour(window.area_of(key)[0])


def initials(key):
    words = [w for w in label(key).replace("&", " ").split() if w[:1].isalnum()]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    w = words[0] if words else key
    return (w[0].upper() + w[1:2].lower()) if len(w) > 1 else w.upper()


def badge(key, size=22):
    """The tool's coloured square (its area's colour) with its initials - one look everywhere."""
    ratio = 2.0
    px = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setBrush(QtGui.QColor(area_colour(key)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, px.width(), px.height(), 6 * ratio, 6 * ratio)
    p.setPen(QtGui.QColor("#111111"))
    f = QtGui.QFont()
    f.setBold(True)
    f.setPixelSize(int(size * ratio * 0.46))
    p.setFont(f)
    p.drawText(px.rect(), Qt.AlignCenter, initials(key))
    p.end()
    px.setDevicePixelRatio(ratio)
    return px


# --------------------------------------------------------------------------- going there
def go(key):
    from gus_rigtool.newui import window
    w = window._frame.get("w")
    if window.alive(w) and w.isVisible():
        w.go_key(key)
        return w
    return window.show(key)


def pop(key):
    from gus_rigtool.newui import window
    area, tool, page = window.area_of(key)
    if area in window.NEW_LOOK:
        return window.show_pop(tool, page)
    from gus_rigtool.core import ui
    return ui.open_panel(tool)


def menu_for(key, parent):
    m = QtWidgets.QMenu(parent)
    m.addAction("Open %s" % label(key)).triggered.connect(lambda _=False: go(key))
    m.addAction("Pop out (its own panel)").triggered.connect(lambda _=False: pop(key))
    m.addSeparator()
    m.addAction("Move left / up").triggered.connect(lambda _=False: move(key, -1))
    m.addAction("Move right / down").triggered.connect(lambda _=False: move(key, 1))
    m.addAction("Remove from favourites").triggered.connect(lambda _=False: toggle(key))
    return m


def _exec(menu, pos):
    return menu.exec_(pos) if hasattr(menu, "exec_") else menu.exec(pos)


def fav_button(key, text=True, size=22):
    b = QtWidgets.QToolButton()
    b.setIcon(QtGui.QIcon(badge(key, size)))
    b.setIconSize(QtCore.QSize(size, size))
    b.setText(label(key) if text else "")
    b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if text else Qt.ToolButtonIconOnly)
    b.setToolTip("%s - click: open it; right-click: Pop out, move, remove" % label(key))
    b.setAutoRaise(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("QToolButton { color: %s; padding: 3px 6px; border-radius: 6px; } "
                    "QToolButton:hover { background: rgba(255,255,255,0.08); }" % theme.TXT)
    b.clicked.connect(lambda _=False: go(key))
    b.setContextMenuPolicy(Qt.CustomContextMenu)
    b.customContextMenuRequested.connect(lambda pos: _exec(menu_for(key, b), b.mapToGlobal(pos)))
    b.setProperty("fav", key)
    return b


def choose(parent=None):
    """'+': a tick per tool, OK - the favourites (row and bar)."""
    from gus_rigtool import registry
    d = QtWidgets.QDialog(parent)
    d.setWindowTitle("Gus_Rigtool - favourites")
    v = QtWidgets.QVBoxLayout(d)
    v.addWidget(widgets.label("Your favourite tools - at the top of the window and on the floating bar:"))
    box = QtWidgets.QWidget()
    bv = QtWidgets.QVBoxLayout(box)
    mine = set(keys())
    ticks = []
    for k, lab, _m, desc in registry.TOOLS:
        if k == "home":
            continue
        c = QtWidgets.QCheckBox(lab)
        c.setChecked(k in mine)
        c.setToolTip(desc)
        c.setIcon(QtGui.QIcon(badge(k, 18)))
        bv.addWidget(c)
        ticks.append((k, c))
    sc = QtWidgets.QScrollArea()
    sc.setWidget(box)
    sc.setWidgetResizable(True)
    v.addWidget(sc, 1)
    ok = QtWidgets.QPushButton("OK")
    v.addWidget(ok)

    def save():
        ticked = dict(ticks)
        order = [k for k in keys() if k in ticked and ticked[k].isChecked()]       # your order kept, new ones after
        set_keys(order + [k for k, c in ticks if c.isChecked() and k not in order])
        d.accept()
    ok.clicked.connect(save)
    d.resize(320, 520)
    d.ticks = ticks
    d.save = save
    return d


# --------------------------------------------------------------------------- the row in the window
class FavRow(QtWidgets.QWidget):
    """The favourites at the top of the window (the old window's My tools row): names, or icons when narrow."""

    def __init__(self, parent=None):
        super(FavRow, self).__init__(parent)
        self.setLayout(widgets.FlowLayout(spacing=2))
        self.layout().setContentsMargins(8, 2, 8, 4)
        self.slim = False
        self.refresh()
        _listeners.append(self.refresh)

    def set_slim(self, slim):
        if slim != self.slim:
            self.slim = slim
            self.refresh()

    def refresh(self):
        from gus_rigtool.newui.window import _clear
        _clear(self.layout())
        for k in keys():
            self.layout().addWidget(fav_button(k, text=not self.slim, size=18 if not self.slim else 22))
        for text, tip, fn in (("+", "Choose your favourites", lambda: choose(self).exec_() if hasattr(
                QtWidgets.QDialog, "exec_") else choose(self).exec()),
                              ("Map", "Where everything is: every area and page.", _map),
                              ("Bar", "The favourites in a floating bar you keep anywhere over Maya.", show_bar)):
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QToolButton { color: %s; padding: 3px 8px; border-radius: 6px; } "
                            "QToolButton:hover { background: rgba(255,255,255,0.08); }" % theme.DIM)
            b.clicked.connect(lambda _=False, fn=fn: fn())
            self.layout().addWidget(b)


def _map():
    try:
        from gus_rigtool.core import ui
        ui.show_map()
    except Exception:
        pass


# --------------------------------------------------------------------------- the floating bar
def _maya_window():
    try:
        import maya.OpenMayaUI as omui
        from gus_rigtool.newui.qt import shiboken
        return shiboken.wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    except Exception:
        return None


def _global(e):
    try:
        return e.globalPosition().toPoint()
    except AttributeError:
        return e.globalPos()


class FavBar(QtWidgets.QWidget):
    """Your favourite tools in a small bar that stays in front of Maya (like the Animtool bar)."""

    def __init__(self, parent=None):
        super(FavBar, self).__init__(parent or _maya_window())
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        keep = getattr(Qt, "WA_MacAlwaysShowToolWindow", None)
        if keep is not None:
            self.setAttribute(keep, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle("Gus_Rigtool favourites")
        self.setStyleSheet("QWidget { background: %s; color: %s; } QWidget#gusFavBar { border-radius: 9px; "
                           "border-top: 3px solid #36b38a; }" % (theme.WIN, theme.TXT))
        self.setObjectName("gusFavBar")
        self._drag = None
        st = self._state()
        self.vertical = bool(st.get("vertical"))
        self.build()
        if st.get("x", -1) >= 0 and st.get("y", -1) >= 0:
            self.move(int(st["x"]), int(st["y"]))
        _listeners.append(self.build)

    def _state(self):
        from gus_rigtool.core import utils
        return utils.load_setting(BAR_KEY, {}) or {}

    def _save(self, **k):
        from gus_rigtool.core import utils
        st = self._state()
        st.update(k)
        utils.save_setting(BAR_KEY, st)

    def build(self):
        from gus_rigtool.newui.window import _clear
        lay = self.layout()
        if lay is None:
            lay = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight, self)
        _clear(lay)
        lay.setDirection(QtWidgets.QBoxLayout.TopToBottom if self.vertical else QtWidgets.QBoxLayout.LeftToRight)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(3)
        self.handle = QtWidgets.QLabel("⋮⋮" if not self.vertical else "⋯")
        self.handle.setToolTip("Drag to move the bar")
        self.handle.setStyleSheet("QLabel { color: %s; padding: 0 4px; }" % theme.FAINT)
        self.handle.setCursor(Qt.SizeAllCursor)
        lay.addWidget(self.handle)
        self.buttons = {}
        for k in keys():
            b = fav_button(k, text=False, size=26)
            lay.addWidget(b)
            self.buttons[k] = b
        m = QtWidgets.QToolButton()
        m.setText("≡")
        m.setAutoRaise(True)
        m.setToolTip("The bar's menu")
        m.clicked.connect(lambda _=False: _exec(self.menu(), QtGui.QCursor.pos()))
        lay.addWidget(m)
        self.adjustSize()

    def menu(self):
        m = QtWidgets.QMenu(self)
        m.addAction("Open the Gus_Rigtool window").triggered.connect(lambda _=False: go_window())
        m.addAction("Choose the favourites...").triggered.connect(
            lambda _=False: choose(self).exec_() if hasattr(QtWidgets.QDialog, "exec_") else choose(self).exec())
        m.addAction("A column" if not self.vertical else "A row").triggered.connect(lambda _=False: self.flip())
        m.addSeparator()
        m.addAction("Close the bar").triggered.connect(lambda _=False: close_bar())
        return m

    def flip(self):
        self.vertical = not self.vertical
        self._save(vertical=self.vertical)
        self.build()

    def mousePressEvent(self, e):
        if self.handle.geometry().contains(e.pos()):
            self._drag = _global(e) - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(_global(e) - self._drag)

    def mouseReleaseEvent(self, _e):
        if self._drag is not None:
            self._drag = None
            p = self.pos()
            self._save(x=int(p.x()), y=int(p.y()))


def go_window():
    from gus_rigtool.newui import window
    return window.show()


def show_bar():
    from gus_rigtool.newui import window
    b = _bar.get("w")
    if not window.alive(b):
        b = FavBar()
        _bar["w"] = b
    b.show()
    b.raise_()
    FavBar._save(b, open=True)
    return b


def close_bar():
    from gus_rigtool.newui import window
    b = _bar.get("w")
    if window.alive(b):
        FavBar._save(b, open=False)
        b.close()
    _bar["w"] = None
