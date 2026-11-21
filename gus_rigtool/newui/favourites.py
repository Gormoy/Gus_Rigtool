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


LAYOUTS = (("row", "Row", "One row"), ("2r", "2R", "Two rows"), ("col", "Col", "One column"),
           ("grid", "Grid", "A square block"))
SIZE_MIN, SIZE_MAX, SIZE_DEFAULT = 24, 52, 34


class FavBar(QtWidgets.QWidget):
    """Your favourite tools in a bar that stays in front of Maya (5.7.9: Gus's mock-up layout, the Rigtool's
    colours): the profiles as pills, Row / 2R / Col / Grid, the size (slider or Ctrl + wheel), labels on / off,
    the tiles (a corner triangle: right-click has its options); right-click a tile: its options in a strip under
    the bar. It never takes the keyboard from Maya, and shrinks to stay on the screen."""

    def __init__(self, parent=None):
        super(FavBar, self).__init__(parent or _maya_window())
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        keep = getattr(Qt, "WA_MacAlwaysShowToolWindow", None)
        if keep is not None:
            self.setAttribute(keep, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowTitle("Gus_Rigtool favourites")
        self.setObjectName("gusFavBar")
        self.setStyleSheet(_BAR_QSS % _QSS_VALUES())
        self._drag = None
        self.editing = False
        self.strip_key = None
        self.shrunk = False
        QtWidgets.QVBoxLayout(self)
        self.build()
        st = self._state()
        if st.get("x", -1) >= 0 and st.get("y", -1) >= 0:
            self.move(int(st["x"]), int(st["y"]))
        _listeners.append(self.build)

    # ---- what's remembered
    def _state(self):
        from gus_rigtool.core import utils
        return utils.load_setting(BAR_KEY, {}) or {}

    def _save(self, **k):
        from gus_rigtool.core import utils
        st = self._state()
        st.update(k)
        utils.save_setting(BAR_KEY, st)

    def shape(self):
        """This profile's layout (5.7.2: each profile keeps its own; 5.7.1's 'vertical' read as a column)."""
        st = self._state()
        got = (st.get("shapes") or {}).get(current())
        if got is True:
            return "col"
        if got in (None, False):
            return "col" if (got is None and st.get("vertical")) else "row"
        return got if got in [x[0] for x in LAYOUTS] else "row"

    @property
    def vertical(self):
        return self.shape() == "col"

    def set_shape(self, shape):
        shapes = dict(self._state().get("shapes", {}))
        shapes[current()] = shape
        self._save(shapes=shapes)
        self.build()

    def flip(self):
        self.set_shape("row" if self.vertical else "col")

    def wanted_size(self):
        return max(SIZE_MIN, min(SIZE_MAX, int(self._state().get("size", SIZE_DEFAULT))))

    def set_size(self, px):
        self._save(size=max(SIZE_MIN, min(SIZE_MAX, int(px))))
        self.build()

    def labels(self):
        return bool(self._state().get("labels", False))

    # ---- drawing
    def build(self):
        from gus_rigtool.newui.window import _clear
        root = self.layout()
        _clear(root)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        root.setContentsMargins(7, 5, 7, 6)
        root.setSpacing(5)
        shape = self.shape()
        lab = self.labels()                              # a column: one even width for everything (5.7.9, Gus)
        self.rail = max((max(self.wanted_size() + 6, 52) if lab else self.wanted_size() + 6), 50)
        self.chrome = self._chrome(shape)
        root.addWidget(self.chrome)
        self.tiles = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.tiles)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(2)
        self.grid.setAlignment((Qt.AlignHCenter if shape == "col" else Qt.AlignLeft) | Qt.AlignTop)
        if shape == "col":
            self.tiles.setFixedWidth(self.rail)
        root.addWidget(self.tiles)
        if not hasattr(self, "strip"):
            self.strip = QtWidgets.QFrame(self, Qt.Tool | Qt.FramelessWindowHint)
            self.strip.setObjectName("gusFavStrip")
            self.strip.setAttribute(Qt.WA_StyledBackground, True)
            self.strip.setFocusPolicy(Qt.NoFocus)
            keep = getattr(Qt, "WA_MacAlwaysShowToolWindow", None)
            if keep is not None:
                self.strip.setAttribute(keep, True)
            QtWidgets.QVBoxLayout(self.strip).setContentsMargins(9, 6, 9, 8)
            self.strip.hide()
        self.size_px = self.wanted_size()
        self._fill_tiles(shape, self.size_px)
        self._fit(shape)
        self.adjustSize()
        self.setFixedSize(self.sizeHint())               # exactly its tiles (a window can keep a wider minimum)
        if self.strip_key in keys():
            self.show_strip(self.strip_key)
        else:
            self.hide_strip()

    def _chrome(self, shape):
        box = QtWidgets.QWidget()
        col = shape == "col"
        lay = QtWidgets.QVBoxLayout(box) if col else QtWidgets.QHBoxLayout(box)    # a row: one line
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3 if col else 4)
        top = QtWidgets.QWidget()
        th = QtWidgets.QHBoxLayout(top)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(4)
        self.handle = QtWidgets.QLabel("::")
        self.handle.setToolTip("Drag to move the bar")
        self.handle.setObjectName("gusFavGrip")
        self.handle.setCursor(Qt.SizeAllCursor)
        th.addWidget(self.handle)
        self.readout = QtWidgets.QLabel("")
        self.readout.setObjectName("gusFavPx")
        th.addWidget(self.readout)
        m = self._small("=", "The bar's menu: open the window, choose favourites, edit, close",
                        lambda: _exec(self.menu(), QtGui.QCursor.pos()))
        th.addWidget(m)
        lay.addWidget(top)
        self.pills = QtWidgets.QWidget()                  # the profiles: yours and the one picked, the rest in ▾
        pl = QtWidgets.QVBoxLayout(self.pills) if col else QtWidgets.QHBoxLayout(self.pills)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(3)
        builtins, mine = profiles()
        shown = [n for n in mine][:4]
        if current() not in shown:
            shown.append(current())
        for name in shown:
            pill = self._pill(name)
            if col:                                       # the mock-up's short pills (BLK, POL...)
                words = [w for w in name.replace("&", " ").split() if w]
                pill.setText("".join(w[0] for w in words).upper()[:3] if len(words) > 1 else name[:3].upper())
            pl.addWidget(pill)
        more = self._small("▾", "Every profile: All tools, one per area, yours - and New / Rename / Delete",
                           lambda: _exec(profile_menu(self), QtGui.QCursor.pos()))
        pl.addWidget(more)
        lay.addWidget(self.pills)
        modes = QtWidgets.QWidget()
        ml = QtWidgets.QGridLayout(modes)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(1)
        self.mode_buttons = {}
        for i, (key, text, tip) in enumerate(LAYOUTS):
            b = self._small({"row": "R", "2r": "2", "col": "C", "grid": "G"}[key] if col else text, tip,
                            lambda k=key: self.set_shape(k), checkable=True)
            b.setChecked(key == shape)
            self.mode_buttons[key] = b
            ml.addWidget(b, i // 2 if col else 0, i % 2 if col else i)
        lb = self._small("Aa" if col else "Lbl", "Names under the tiles", lambda: (self._save(labels=not self.labels()),
                                                                 self.build()), checkable=True)
        lb.setChecked(self.labels())
        ml.addWidget(lb, 2 if col else 0, 0 if col else 5, 1, 2 if col else 1)
        lay.addWidget(modes)
        if col:                                           # a column: everything the rail's width, evenly
            for w in list(self.mode_buttons.values()) + [lb]:
                w.setStyleSheet("QToolButton { padding: 2px 0px; }")
        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.slider.setRange(SIZE_MIN, SIZE_MAX)
        self.slider.setSingleStep(2)
        self.slider.setPageStep(4)
        self.slider.setValue(self.wanted_size())
        self.slider.setFixedWidth(self.rail if col else 80)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.setToolTip("The tiles' size (or Ctrl + mouse wheel over the bar)")
        self.slider.sliderReleased.connect(lambda: self.set_size(self.slider.value()))
        lay.addWidget(self.slider)
        if editable():
            lay.addWidget(self._small(("✓" if col else "Done") if self.editing else ("✎" if col else "Edit"),
                                      "Edit this profile: × takes one off; "
                                      "choose more in the menu", lambda: self.set_editing(not self.editing)))
        if col:
            box.setFixedWidth(self.rail)
            for b in box.findChildren(QtWidgets.QToolButton):
                if b.parentWidget() is not top:
                    b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                    b.setMinimumWidth(0)
            th.setSpacing(1)
            self.readout.setAlignment(Qt.AlignCenter)
            th.setStretch(1, 1)
            for b in box.findChildren(QtWidgets.QToolButton):
                b.setStyleSheet(b.styleSheet() + " QToolButton { padding: 2px 0px; }")
        return box

    def _small(self, text, tip, fn, checkable=False):
        b = QtWidgets.QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setFocusPolicy(Qt.NoFocus)
        b.setCursor(Qt.PointingHandCursor)
        b.setObjectName("gusFavSmall")
        b.clicked.connect(lambda _=False: fn())
        return b

    def _pill(self, name):
        n = len(keys_of(name))
        b = self._small("%s %d" % (name, n), "Show the profile '%s' (%d tools)" % (name, n),
                        lambda: set_current(name), checkable=True)
        b.setChecked(name == current())
        b.setObjectName("gusFavPill")
        area = [a for a in theme.AREAS if a[1] == name]
        b.setStyleSheet("QToolButton#gusFavPill { border-left: 3px solid %s; }" %
                        (area[0][2] if area else theme.colour("toolbox")))
        return b

    def _columns(self, shape, n):
        if shape == "col":
            return 1
        if shape == "2r":
            return max(1, (n + 1) // 2)
        if shape == "grid":
            import math
            return max(1, int(math.ceil(math.sqrt(n))))
        return max(1, n)

    def _fill_tiles(self, shape, px):
        from gus_rigtool.newui import tiles
        from gus_rigtool.newui.window import _clear
        _clear(self.grid)
        self.buttons = {}
        ks = keys()
        cols = self._columns(shape, len(ks))
        lab = self.labels()
        cell = max(px + 6, 52) if lab else px + 4
        for i, k in enumerate(ks):
            b = QtWidgets.QToolButton()
            b.setObjectName("gusFavTile")
            b.setFocusPolicy(Qt.NoFocus)                    # never takes Space / S / the viewport keys from Maya
            b.setIcon(QtGui.QIcon(tiles.pixmap(k, px, tiles.has_options(k))))
            b.setIconSize(QtCore.QSize(px, px))
            b.setToolButtonStyle(Qt.ToolButtonIconOnly)
            b.setFixedWidth(cell)
            b.setToolTip("%s - click: open it; right-click: its options" % label(k))
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("fav", k)
            b.clicked.connect(lambda _=False, k=k: go(k))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _pos, k=k: self.show_strip(k))
            self.buttons[k] = b
            w = b
            if lab:                                         # the name under it, on up to two lines (5.7.9, Gus)
                w = QtWidgets.QWidget()
                tv = QtWidgets.QVBoxLayout(w)
                tv.setContentsMargins(0, 0, 0, 0)
                tv.setSpacing(1)
                tv.addWidget(b, 0, Qt.AlignHCenter)
                name = QtWidgets.QLabel(label(k))
                name.setObjectName("gusFavName")
                name.setWordWrap(True)
                name.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
                name.setFixedWidth(cell)
                name.setFixedHeight(name.fontMetrics().lineSpacing() * 2 + 2)
                tv.addWidget(name)
            if self.editing:
                inner = w
                w = QtWidgets.QWidget()
                g = QtWidgets.QGridLayout(w)
                g.setContentsMargins(0, 0, 0, 0)
                g.addWidget(inner, 0, 0)
                x = QtWidgets.QToolButton()
                x.setText("×")
                x.setProperty("remove", k)
                x.setFocusPolicy(Qt.NoFocus)
                x.setToolTip("Take %s off this profile" % label(k))
                x.setStyleSheet("QToolButton { color: white; background: #e2504a; border-radius: 7px; "
                                "min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; padding: 0; }")
                x.clicked.connect(lambda _=False, k=k: toggle(k))
                g.addWidget(x, 0, 0, Qt.AlignTop | Qt.AlignRight)
            self.grid.addWidget(w, i // cols, i % cols)
        self.readout.setText(("%d%s" if self.vertical else "%dpx%s") % (px, "*" if px < self.wanted_size() else ""))

    def _fit(self, shape):
        """Never off the screen: smaller tiles (2 px a step, down to 22) until the bar fits 92% x 85% of it."""
        scr = QtWidgets.QApplication.primaryScreen() if hasattr(QtWidgets.QApplication, "primaryScreen") else None
        try:
            geo = (self.screen() if hasattr(self, "screen") and self.screen() else scr).availableGeometry()
        except Exception:
            return
        px = self.size_px
        while px > 22 and (self.sizeHint().width() > geo.width() * 0.92 or
                           self.sizeHint().height() > geo.height() * 0.85):
            px -= 2
            self._fill_tiles(shape, px)
            self.adjustSize()
        self.size_px = px
        self.shrunk = px < self.wanted_size()

    # ---- right-click: the tool's options under the bar
    def show_strip(self, key):
        from gus_rigtool.newui.window import _clear
        from gus_rigtool.newui import tiles
        self.strip_key = key
        lay = self.strip.layout()
        _clear(lay)
        self.strip.setStyleSheet(_BAR_QSS % _QSS_VALUES() + "QFrame#gusFavStrip { border: 1px solid %s; "
                                 "border-left: 3px solid %s; }" % (theme.LINE, tiles.colour(key)))
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("<b>%s</b>  options" % label(key))
        head.addWidget(title, 1)
        head.addWidget(self._small("×", "Close the options", self.hide_strip))
        lay.addLayout(head)
        rows = option_rows(key, stacked=self.vertical and STACKED_BESIDE["on"])
        body = QtWidgets.QWidget()
        bl = QtWidgets.QGridLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setHorizontalSpacing(14)
        bl.setVerticalSpacing(4)
        cols = 1 if self.vertical else 2
        for i, w in enumerate(rows[:MAX_STRIP]):
            bl.addWidget(w, i // cols, i % cols)
        if not rows:
            bl.addWidget(widgets.label("No options to set for %s." % label(key), "dim"), 0, 0)
        lay.addWidget(body)
        foot = widgets.flow_box(4)
        foot.layout().addWidget(self._small("Open its page", "Open %s in the window" % label(key),
                                            lambda: go(key)))
        if len(rows) > MAX_STRIP:
            foot.layout().addWidget(self._small("All %d in Settings..." % len(rows), "Every option of %s, in "
                                                "Settings" % label(key), lambda: open_settings(key)))
        foot.layout().addWidget(self._small("Pop out", "Its own panel", lambda: pop(key)))
        if editable():
            foot.layout().addWidget(self._small("Remove", "Take it off this profile", lambda: toggle(key)))
        lay.addWidget(foot)
        if self.vertical and STACKED_BESIDE["on"]:     # beside a column: narrow - the buttons two by two
            btns = foot.findChildren(QtWidgets.QToolButton)
            grid = QtWidgets.QWidget()
            gl = QtWidgets.QGridLayout(grid)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setSpacing(4)
            for i, bt in enumerate(btns):
                if bt.text().startswith("All "):
                    bt.setText("All %d  ›" % len(rows))
                bt.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                gl.addWidget(bt, i // 2, i % 2)
            lay.replaceWidget(foot, grid)
            foot.deleteLater()
            self.strip.setFixedWidth(220)
        else:
            self.strip.setMinimumWidth(0)
            self.strip.setMaximumWidth(16777215)
        self.strip.adjustSize()
        self.place_strip()
        self.strip.show()

    def place_strip(self):
        """Right under the bar (beside it when the bar is a column), kept on the screen."""
        if not self.strip.isVisible() and self.strip_key is None:
            return
        self.strip.adjustSize()
        g = QtCore.QRect(self.pos(), self.sizeHint().expandedTo(self.size()))
        if self.vertical:
            x, y = g.left() + g.width() + 4, g.top()
        else:
            x, y = g.left(), g.top() + g.height() + 4
        try:
            geo = QtWidgets.QApplication.primaryScreen().availableGeometry()
            x = max(geo.left(), min(x, geo.right() - self.strip.width()))
            if y + self.strip.height() > geo.bottom():
                y = max(geo.top(), g.top() - self.strip.height() - 4) if not self.vertical else \
                    geo.bottom() - self.strip.height()
        except Exception:
            pass
        self.strip.move(int(x), int(y))

    def hide_strip(self):
        self.strip_key = None
        if hasattr(self, "strip"):
            self.strip.hide()

    def moveEvent(self, e):
        super(FavBar, self).moveEvent(e)
        if hasattr(self, "strip") and self.strip.isVisible():
            self.place_strip()

    def hideEvent(self, e):
        if hasattr(self, "strip"):
            self.strip.hide()
        super(FavBar, self).hideEvent(e)

    def menu(self):
        m = QtWidgets.QMenu(self)
        m.addAction("Open the Gus_Rigtool window").triggered.connect(lambda _=False: go_window())
        if editable():
            m.addAction("Done editing" if self.editing else "Edit (× takes one off)").triggered.connect(
                lambda _=False: self.set_editing(not self.editing))
        m.addAction("Choose the favourites...").triggered.connect(
            lambda _=False: choose(self).exec_() if hasattr(QtWidgets.QDialog, "exec_") else choose(self).exec())
        m.addSeparator()
        m.addAction("Close the bar").triggered.connect(lambda _=False: close_bar())
        return m

    def set_editing(self, on):
        self.editing = bool(on) and editable()
        self.build()

    # ---- moving it, Ctrl + wheel
    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            step = 2 if e.angleDelta().y() > 0 else -2
            self.set_size(self.wanted_size() + step)
            e.accept()
            return
        super(FavBar, self).wheelEvent(e)

    def mousePressEvent(self, e):
        if self.handle.isVisible() and self.handle.rect().contains(self.handle.mapFrom(self, e.pos())):
            self._drag = _global(e) - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(_global(e) - self._drag)

    def mouseReleaseEvent(self, _e):
        if self._drag is not None:
            self._drag = None
            p = self.pos()
            self._save(x=int(p.x()), y=int(p.y()))


def _QSS_VALUES():
    return {"WIN": theme.WIN, "TXT": theme.TXT, "DIM": theme.DIM, "LINE": theme.LINE, "ACC": theme.colour("toolbox"),
            "FIELD": theme.FIELD}


STACKED_BESIDE = {"on": False}                      # beside a column: names above their boxes (narrower)
MAX_STRIP = 8                                       # options shown in the strip (the rest: 'All in Settings')

_BAR_QSS = """
QWidget#gusFavBar { background: %(WIN)s; border: 1px solid %(LINE)s; border-radius: 9px; }
QWidget#gusFavBar QWidget { color: %(TXT)s; }
QLabel#gusFavGrip { color: %(DIM)s; padding: 0 3px; font-weight: bold; }
QLabel#gusFavPx { color: %(DIM)s; font-size: 11px; padding: 0 3px; }
QToolButton#gusFavSmall, QToolButton#gusFavPill { background: #2b2f35; border: 1px solid %(LINE)s; border-radius: 5px;
    padding: 2px 7px; font-size: 11px; color: %(TXT)s; }
QToolButton#gusFavSmall:checked, QToolButton#gusFavPill:checked { background: %(ACC)s; color: #111; font-weight: bold; }
QToolButton#gusFavSmall:hover, QToolButton#gusFavPill:hover { border-color: %(ACC)s; }
QLabel#gusFavName { font-size: 10px; color: %(TXT)s; }
QToolButton#gusFavTile { background: transparent; border: none; padding: 1px; font-size: 10px; color: %(TXT)s; }
QToolButton#gusFavTile:hover { background: rgba(255,255,255,0.08); border-radius: 6px; }
QFrame#gusFavStrip { background: %(WIN)s; border-radius: 7px; }
QFrame#gusFavStrip QWidget { color: %(TXT)s; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { background: %(FIELD)s; color: %(TXT)s; border: 1px solid %(LINE)s;
    border-radius: 4px; padding: 2px 6px; min-height: 18px; }
QSlider::groove:horizontal { height: 4px; background: #16191e; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px; background: %(ACC)s; }
"""


def option_rows(key, stacked=False):
    """A tool's saved options as small controls (the ones its section in Settings shows); a change is saved at
    once and the tool's open page picks it up."""
    from gus_rigtool import registry
    from gus_rigtool.core import utils
    try:
        mod = registry.module(key)
    except Exception:
        return []
    schema = getattr(mod, "SCHEMA", None) or []
    if not schema:
        return []
    values = utils.tool_settings(mod.SETTINGS_KEY, mod.DEFAULTS)
    out = []
    for name, text, kind, choices in schema:
        value = values.get(name, mod.DEFAULTS.get(name))

        def save(v, name=name):
            utils.update_setting(mod.SETTINGS_KEY, name, v)
            _applied(key)
        if kind == "bool":
            w = QtWidgets.QCheckBox(text)
            w.setChecked(bool(value))
            w.toggled.connect(lambda on, save=save: save(bool(on)))
        else:
            w = QtWidgets.QWidget()
            h = QtWidgets.QVBoxLayout(w) if stacked else QtWidgets.QHBoxLayout(w)   # stacked: the name above
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(1 if stacked else 4)
            h.addWidget(widgets.label(text, "dim", wrap=False))
            if kind == "choice":
                c = QtWidgets.QComboBox()
                c.addItems([str(x) for x in choices])
                try:
                    c.setCurrentIndex(int(value) - 1)
                except (TypeError, ValueError):
                    pass
                c.currentIndexChanged.connect(lambda i, save=save: save(i + 1))
            elif kind == "float":
                c = QtWidgets.QDoubleSpinBox()
                c.setDecimals(3)
                c.setRange(-1e6, 1e6)
                c.setValue(float(value or 0))
                c.editingFinished.connect(lambda c=c, save=save: save(float(c.value())))
            elif kind == "int":
                c = QtWidgets.QSpinBox()
                c.setRange(-100000, 100000)
                c.setValue(int(value or 0))
                c.editingFinished.connect(lambda c=c, save=save: save(int(c.value())))
            else:
                c = QtWidgets.QLineEdit(str(value or ""))
                c.editingFinished.connect(lambda c=c, save=save: save(c.text().strip()))
            h.addWidget(c)
        w.setFocusPolicy(Qt.NoFocus) if kind == "bool" else None
        w.setProperty("option", name)
        out.append(w)
    return out


def _applied(key):
    """The tool's open page picks up the changed option (drawn again)."""
    try:
        from gus_rigtool.newui import window
        f = window._frame.get("w")
        if window.alive(f):
            f.rebuild(key)
    except Exception:
        pass


def open_settings(key):
    """Settings, open at this tool's section."""
    from gus_rigtool.newui import window
    w = window.show("settings")
    try:
        card = w.areas["settings"].find_card(label(key))
        if card is not None:
            card.set_closed(False)
            w.areas["settings"].scroll.ensureWidgetVisible(card)
    except Exception:
        pass
    return w


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
