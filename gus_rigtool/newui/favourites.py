"""
Your favourite tools (5.7.1): a row at the top of the new window (the old window's My tools row) and a floating
bar you keep anywhere over Maya. One list for both - the same one the old window's My tools used (myTools).

Click: go to that tool. Right-click: Pop out / Move left / Move right / Remove. '+' chooses them; the star on a
page's header adds or removes that page. Map: where everything is.

Profiles (5.7.2, the same design as the Animtool bar): All tools, one per area, and your own (My tools = the old
window's list). The row and the bar show the profile picked; Edit (pencil): drag to move, x to take off, + Add.
"""

from gus_rigtool.newui import theme, widgets
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
BAR_KEY = "favBar"
_listeners = []
_bar = {"w": None}


PROFILES_KEY = "favProfiles"
MINE = "My tools"                              # the old window's My tools list (myTools), kept in step


# --------------------------------------------------------------------------- profiles
def _store():
    from gus_rigtool.core import ui, utils
    st = utils.load_setting(PROFILES_KEY, {}) or {}
    st.setdefault("current", MINE)
    st.setdefault("mine", {})
    st["mine"][MINE] = [k for k in ui.my_tools() if k != "home"]          # always the old window's list
    return st


def _save_store(st):
    from gus_rigtool.core import utils
    utils.save_setting(PROFILES_KEY, st)


def builtin():
    """{profile: tools} that come with the tool: All tools, and one per area (in the sidebar's order)."""
    from gus_rigtool import registry
    from gus_rigtool.newui import window
    out = {"All tools": [k for k, _l, _m, _d in registry.TOOLS if k != "home"]}
    for key, lab, _c, _i, _cats in theme.AREAS:
        if key in ("home",):
            continue
        tools = [k for k, _l, _m, _d in registry.TOOLS if k != "home" and window.area_of(k)[0] == key]
        if tools:
            out[lab] = tools
    return out


def profiles():
    """(the built-in profile names, your own profile names)."""
    return list(builtin()), list(_store()["mine"])


def current():
    name = _store()["current"]
    b, m = profiles()
    return name if name in b or name in m else MINE


def set_current(name):
    st = _store()
    st["current"] = name
    _save_store(st)
    changed()


def editable(name=None):
    return (name or current()) in _store()["mine"]


def new_profile(name, copy_from=None):
    st = _store()
    name = (name or "").strip()
    if not name or name in st["mine"] or name in builtin():
        raise RuntimeError("a profile needs a new name.")
    st["mine"][name] = list(keys_of(copy_from or current()))
    st["current"] = name
    _save_store(st)
    changed()
    return name


def rename_profile(old, new):
    st = _store()
    new = (new or "").strip()
    if old == MINE or old not in st["mine"]:
        raise RuntimeError("'%s' can't be renamed." % old)
    if not new or new in st["mine"] or new in builtin():
        raise RuntimeError("a profile needs a new name.")
    st["mine"][new] = st["mine"].pop(old)
    if st["current"] == old:
        st["current"] = new
    _save_store(st)
    changed()


def delete_profile(name):
    st = _store()
    if name == MINE or name not in st["mine"]:
        raise RuntimeError("'%s' can't be deleted." % name)
    st["mine"].pop(name)
    if st["current"] == name:
        st["current"] = MINE
    _save_store(st)
    changed()


def keys_of(name):
    st = _store()
    if name in st["mine"]:
        return list(st["mine"][name])
    return list(builtin().get(name, st["mine"][MINE]))


# --------------------------------------------------------------------------- the list
def keys():
    """The tools of the profile shown."""
    return keys_of(current())


def set_keys(new):
    """The profile shown gets these tools (a built-in one can't change: 'My tools' gets them)."""
    from gus_rigtool.core import utils
    out = []
    for k in new:
        if k not in out and k != "home":
            out.append(k)
    st = _store()
    name = st["current"] if st["current"] in st["mine"] else MINE
    st["mine"][name] = out
    st["current"] = name
    _save_store(st)
    if name == MINE:
        utils.save_setting("myTools", out)            # the old window's My tools row: the same list
    changed()


def toggle(key):
    from gus_rigtool import registry
    key = registry.resolve(key)[0]
    now = keys() if editable() else keys_of(MINE)
    set_keys([k for k in now if k != key] if key in now else now + [key])
    return key in keys()


def move_to(key, index):
    """Drag in Edit: key goes to place index."""
    now = keys()
    if key not in now or not editable():
        return
    now.remove(key)
    now.insert(max(0, min(len(now), index)), key)
    set_keys(now)


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


def profile_menu(parent):
    """The profiles: pick one; New (a copy of this one), Rename, Delete."""
    m = QtWidgets.QMenu(parent)
    b, mine = profiles()
    cur = current()
    for name in mine:
        a = m.addAction(name)
        a.setCheckable(True)
        a.setChecked(name == cur)
        a.triggered.connect(lambda _=False, n=name: set_current(n))
    m.addSeparator()
    for name in b:
        a = m.addAction("%s  (%d)" % (name, len(keys_of(name))))
        a.setCheckable(True)
        a.setChecked(name == cur)
        a.triggered.connect(lambda _=False, n=name: set_current(n))
    m.addSeparator()
    m.addAction("New profile (a copy of this one)...").triggered.connect(lambda _=False: _ask_new(parent))
    if editable() and cur != MINE:
        m.addAction("Rename '%s'..." % cur).triggered.connect(lambda _=False: _ask_rename(parent))
        m.addAction("Delete '%s'" % cur).triggered.connect(lambda _=False: delete_profile(cur))
    return m


def _ask(parent, title, text, value=""):
    got, ok = QtWidgets.QInputDialog.getText(parent, title, text, QtWidgets.QLineEdit.Normal, value)
    return got if ok else None


def _ask_new(parent):
    name = _ask(parent, "New profile", "Its name (a copy of '%s'):" % current())
    if name:
        new_profile(name)


def _ask_rename(parent):
    name = _ask(parent, "Rename the profile", "New name:", current())
    if name:
        rename_profile(current(), name)


def profile_button(parent=None):
    b = QtWidgets.QToolButton(parent)
    b.setText(current() + " ▾")
    b.setToolTip("Your favourites profiles: All tools, one per area, your own")
    b.setAutoRaise(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("QToolButton { background: rgba(255,255,255,0.08); color: %s; padding: 3px 9px; "
                    "border-radius: 10px; }" % theme.TXT)
    b.clicked.connect(lambda _=False: _exec(profile_menu(b), b.mapToGlobal(QtCore.QPoint(0, b.height()))))
    return b


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
    v.addWidget(widgets.label("'%s' - tick the tools you want (at the top of the window and on the floating bar):" %
                              (current() if editable() else MINE)))
    box = QtWidgets.QWidget()
    bv = QtWidgets.QVBoxLayout(box)
    mine = set(keys())
    ticks = []
    from gus_rigtool.newui import window
    for akey, alab, acol, _i, _cats in theme.AREAS:                    # grouped by area, in the sidebar's order
        tools = [(k, lab, desc) for k, lab, _m, desc in registry.TOOLS if k != "home" and
                 window.area_of(k)[0] == akey]
        if not tools:
            continue
        head = widgets.label(alab.upper(), wrap=False)
        head.setStyleSheet("QLabel { color: %s; font-size: 11px; font-weight: bold; margin-top: 6px; }" % acol)
        bv.addWidget(head)
        for k, lab, desc in tools:
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
        self.editing = False
        self._drag = None
        self.refresh()
        _listeners.append(self.refresh)

    def set_editing(self, on):
        self.editing = bool(on) and editable()
        self.refresh()

    def drop(self, key, onto):
        """Edit: drop the favourite key onto another one - it takes that one's place."""
        now = keys()
        if onto in now:
            move_to(key, now.index(onto))

    def eventFilter(self, obj, event):
        key = obj.property("fav")
        if self.editing and key:
            if event.type() == QtCore.QEvent.MouseButtonPress:
                self._drag = key
                return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and self._drag:
                under = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
                while under is not None and not under.property("fav"):
                    under = under.parentWidget()
                start, self._drag = self._drag, None
                if under is not None and under.property("fav") != start:
                    self.drop(start, under.property("fav"))
                return True
        return False

    def set_slim(self, slim):
        if slim != self.slim:
            self.slim = slim
            self.refresh()

    def refresh(self):
        from gus_rigtool.newui.window import _clear
        _clear(self.layout())
        self.profile = profile_button()
        self.layout().addWidget(self.profile)
        for k in keys():
            b = fav_button(k, text=not self.slim, size=18 if not self.slim else 22)
            if self.editing:
                b.setStyleSheet(b.styleSheet() + " QToolButton { border: 1px dashed #6f93bd; }")
                b.setToolTip("Drag onto another favourite to move it")
                b.installEventFilter(self)
                box = QtWidgets.QWidget()
                h = QtWidgets.QHBoxLayout(box)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(0)
                h.addWidget(b)
                x = QtWidgets.QToolButton()
                x.setText("×")
                x.setToolTip("Take %s off this profile" % label(k))
                x.setProperty("remove", k)
                x.setStyleSheet("QToolButton { color: white; background: #e2504a; border-radius: 8px; "
                                "min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px; "
                                "padding: 0px; font-weight: bold; }")
                x.clicked.connect(lambda _=False, k=k: toggle(k))
                h.addWidget(x, 0, Qt.AlignTop)
                self.layout().addWidget(box)
            else:
                self.layout().addWidget(b)
        if self.editing:
            items = (("+ Add", "Tick the tools you want, grouped by area", lambda: choose(self).exec_() if hasattr(
                QtWidgets.QDialog, "exec_") else choose(self).exec()),
                     ("Done", "Finish editing", lambda: self.set_editing(False)))
        else:
            items = (("✎", "Edit this profile: drag to move, × to take off, + to add" if editable() else
                      "Built-in profiles can't change - pick 'New profile' in the profile menu to make your own",
                      lambda: self.set_editing(True)),
                     ("Map", "Where everything is: every area and page.", _map),
                     ("Bar", "The favourites in a floating bar you keep anywhere over Maya.", show_bar))
        for text, tip, fn in items:
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
        self.editing = False
        self.vertical = False
        self.build()
        st = self._state()
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
        st = self._state()                       # 5.7.2: each profile keeps its own shape
        shapes = st.get("shapes")                # none yet: the bar's one shape from 5.7.1
        self.vertical = bool(shapes.get(current(), False) if shapes else st.get("vertical", False))
        lay.setDirection(QtWidgets.QBoxLayout.TopToBottom if self.vertical else QtWidgets.QBoxLayout.LeftToRight)
        lay.setContentsMargins(6, 5, 6, 5)
        lay.setSpacing(3)
        self.handle = QtWidgets.QLabel("⋮⋮" if not self.vertical else "⋯")
        self.handle.setToolTip("Drag to move the bar")
        self.handle.setStyleSheet("QLabel { color: %s; padding: 0 4px; }" % theme.FAINT)
        self.handle.setCursor(Qt.SizeAllCursor)
        lay.addWidget(self.handle)
        self.profile = profile_button()
        lay.addWidget(self.profile)
        self.buttons = {}
        for k in keys():
            b = fav_button(k, text=False, size=26)
            self.buttons[k] = b
            if self.editing:
                box = QtWidgets.QWidget()
                g = QtWidgets.QGridLayout(box)
                g.setContentsMargins(0, 0, 0, 0)
                g.addWidget(b, 0, 0)
                x = QtWidgets.QToolButton()
                x.setText("×")
                x.setProperty("remove", k)
                x.setToolTip("Take %s off this profile" % label(k))
                x.setStyleSheet("QToolButton { color: white; background: #e2504a; border-radius: 7px; "
                                "min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; padding: 0; }")
                x.clicked.connect(lambda _=False, k=k: toggle(k))
                g.addWidget(x, 0, 0, Qt.AlignTop | Qt.AlignRight)
                lay.addWidget(box)
            else:
                lay.addWidget(b)
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
        if editable():
            m.addAction("Done editing" if self.editing else "Edit (× takes one off)").triggered.connect(
                lambda _=False: self.set_editing(not self.editing))
        m.addAction("Choose the favourites...").triggered.connect(
            lambda _=False: choose(self).exec_() if hasattr(QtWidgets.QDialog, "exec_") else choose(self).exec())
        m.addAction("A column" if not self.vertical else "A row").triggered.connect(lambda _=False: self.flip())
        m.addSeparator()
        m.addAction("Close the bar").triggered.connect(lambda _=False: close_bar())
        return m

    def set_editing(self, on):
        self.editing = bool(on) and editable()
        self.build()

    def flip(self):
        st = self._state()
        shapes = dict(st.get("shapes", {}))
        shapes[current()] = not self.vertical
        self._save(shapes=shapes)
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
