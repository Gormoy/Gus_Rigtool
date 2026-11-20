"""
The 5.7 window: the sidebar (your rig's steps, the toolbox), a coloured header per area with its sub-pages, what
you have selected and the next step, the pages - and a status line.

    from gus_rigtool.newui import window; window.show()            # gr.show() opens it (unless the old one is on)

The Controls area is drawn in the new look; the other areas show today's pages inside this window until they
are redone (5.7.1 ...). Toolbox > Settings > Window brings the old window back.
"""


from gus_rigtool.newui import icons, nextstep, record, render, theme, widgets
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
_QAction = getattr(QtWidgets, "QAction", None) or QtGui.QAction       # PySide2: QtWidgets; PySide6: QtGui
WS = "gusRigtool57Window"
STATE_KEY = "newWindow"
NEW_LOOK = ("controls",)                         # the areas drawn in the new look (5.7.0: Controls)
CATEGORY = {"home": "home", "build": "build", "skin": "skin", "controls": "controls", "connect": "links",
            "check": "finish", "toolbox": "toolbox"}
WHY = {"home": "Where you are in the rig, and the next step.",
       "build": "Modules, face, ribbons and joints: the rig's skeleton and parts.",
       "skin": "Bind meshes and fix the weights.",
       "controls": "Make controls and shape them; how they behave, their attributes, spaces and follows.",
       "connect": "Constraints, connections, nodes and driven keys.",
       "check": "Find problems, tidy up and hand the rig over.",
       "toolbox": "Small tools for any moment."}
SLIM = 560                                       # narrower than this: the sidebar shows its icons only
_frame = {"w": None}


def _state():
    from gus_rigtool.core import utils
    s = utils.load_setting(STATE_KEY, {}) or {}
    s.setdefault("sub", {})
    s.setdefault("recent", [])
    s.setdefault("pinned", {})
    return s


def _save_state(s):
    from gus_rigtool.core import utils
    utils.save_setting(STATE_KEY, s)


def in_maya():
    try:
        import maya.OpenMayaUI                  # noqa: F401
        return True
    except ImportError:
        return False


def area_of(key):
    """(area, tool key, page) for a tool key (old keys - shapes, makectrl - included)."""
    from gus_rigtool import registry
    tool, page = registry.resolve(key)
    cat, _l = registry.category_of(tool)
    for a, c in CATEGORY.items():
        if c == cat:
            return a, tool, page
    return "home", tool, page


# --------------------------------------------------------------------------- a page from today's window
class OldPage(QtWidgets.QWidget):
    """Today's page of a tool, inside the new window (areas not redone yet). In Maya it's the real page."""

    def __init__(self, key, parent=None):
        super(OldPage, self).__init__(parent)
        self.key = key
        self.filled = False
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)

    def fill(self):
        if self.filled:
            return
        self.filled = True
        if not in_maya():
            self.layout().addWidget(widgets.label("Today's %s page (shown here in Maya)." % self.key, "dim"))
            return
        import maya.cmds as mc
        from gus_rigtool.core import ui
        from gus_rigtool.newui.qt import maya_widget
        here = mc.setParent(query=True)
        try:
            mc.setParent(WS)
            col = mc.columnLayout(adjustableColumn=True)
            ui._build_tool(self.key, "n7_%s_" % self.key)
            w = maya_widget(col, "layout")
            if w is not None:
                self.layout().addWidget(w)
        finally:
            try:
                mc.setParent(here)
            except RuntimeError:
                pass


# --------------------------------------------------------------------------- one area
class Area(QtWidgets.QWidget):
    """An area's pages (one shown at a time) under its header."""

    def __init__(self, frame, key):
        super(Area, self).__init__()
        from gus_rigtool import registry
        self.frame, self.key = frame, key
        self.accent = theme.colour(key)
        self.tools = dict((c, k) for c, _l, k in registry.CATEGORIES).get(CATEGORY[key], [])
        self.subs = []                          # [(tool key, page or None, label)]
        for t in self.tools:
            if t == "controls_tab" and key in NEW_LOOK:
                self.subs += [("controls_tab", 1, "Make"), ("controls_tab", 2, "Edit shape")]
            else:
                self.subs.append((t, None, registry.get(t)[1]))
        self.pages = {}                         # tool key -> render.Page (new look)
        self.widgets = {}                       # (tool, page) -> QWidget
        self.current = None
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        inner = QtWidgets.QWidget()
        inner.setObjectName("gusPage")
        self.inner = QtWidgets.QVBoxLayout(inner)
        self.inner.setContentsMargins(12, 10, 12, 4)
        self.inner.setSpacing(10)
        self.selbox = widgets.SelectedBox()
        self.next = widgets.NextStep(self.accent)
        self.next.go.connect(self._go_next)
        self.pin_slot = QtWidgets.QVBoxLayout()
        self.pin_slot.setContentsMargins(0, 0, 0, 0)
        self.inner.addWidget(self.selbox)
        self.inner.addWidget(self.next)
        self.inner.addLayout(self.pin_slot)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.inner.addLayout(self.body)
        self.inner.addStretch(1)
        self.scroll.setWidget(inner)
        v.addWidget(self.scroll)
        self._target = None
        self.pinned = None                      # (card, its own layout, its index there)

    # -------------------------------------------------- pages
    def page_widget(self, sub):
        tool, page = sub[0], sub[1]
        if (tool, page) in self.widgets:
            return self.widgets[(tool, page)]
        if self.key in NEW_LOOK:
            self._build_new(tool)
        else:
            w = OldPage(tool)
            self.widgets[(tool, page)] = w
            self.body.addWidget(w)
        return self.widgets.get((tool, page))

    def _build_new(self, tool):
        from gus_rigtool import registry
        mod = registry.module(tool)
        prefix = "q7_%s_" % tool
        rec = record.record(mod.build, prefix)
        page = render.Page(tool, rec, self.accent)
        self.pages[tool] = page
        if tool == "controls_tab":
            self._controls_tab(page, mod, prefix)
        else:
            w = page.build()
            w.layout().setContentsMargins(0, 0, 0, 0)
            self.widgets[(tool, None)] = w
            self.body.addWidget(w)
        for fn in rec.deferred:
            try:
                fn()
            except Exception:
                pass
        self._pin_from_state(tool)
        for card in page.cards:
            card.pin_clicked.connect(lambda c=card, t=tool: self.toggle_pin(c, t))

    def _controls_tab(self, page, CT, prefix):
        """Controls: its shape list becomes the shape grid; its two pages (Make, Edit shape) two sub-pages."""
        tabs = page.rec.find(prefix + "Pages")
        lst = page.rec.find(prefix + "Split")
        if lst is not None and lst.children:
            for n in _walk(lst.children[0]):
                page._note(n, "the shape grid (every shape, as a picture)")
        page._tabLayout(tabs, {"card": None})
        page.on_tab = lambda name, i: self.frame.go(("controls_tab", i))
        from gus_rigtool.core import shape_data
        pick = CT._w(lambda name: CT.pick(name))
        hover = CT._w(lambda name, entering: CT._hover(name, entering))
        delete = CT._w(lambda name: CT._delete_mine(name))
        self.grids = []
        for i, (label, w) in enumerate(page.tabs.get(prefix + "Pages", [])):
            groups = [(cat, [(n, shape_data.label(n)) for n in names]) for cat, names in CT.shape_names()]
            grid = widgets.ShapeGrid(groups, CT.picked(), CT._thumb)
            grid.picked.connect(lambda n, g=grid: (self._mark_all(n), pick(n)))
            grid.hovered.connect(lambda n, on: hover(n, on))
            for n in CT.shape_names()[-1][1]:                       # My shapes: right-click > Delete
                tile = grid.tiles.get(n)
                if tile is not None:
                    tile.setContextMenuPolicy(Qt.ActionsContextMenu)
                    act = _QAction('Delete "%s"' % n, tile)
                    act.triggered.connect(lambda _=False, n=n: delete(n))
                    tile.addAction(act)
            card = widgets.Card("Pick a shape" if i == 0 else "Swap the shape (hover: see it on them)", None,
                                "Click a shape: on Make it makes the controls at once; on Edit shape it goes on "
                                "the selected controls. Hover (Edit shape): you see it on them first.")
            card.pin.hide()
            card.add(grid)
            w.layout().insertWidget(0, card)
            w.layout().setContentsMargins(0, 0, 0, 0)
            self.grids.append(grid)
            self.widgets[("controls_tab", i + 1)] = w
            self.body.addWidget(w)

    def _mark_all(self, name):
        for g in getattr(self, "grids", []):
            g.mark(name)

    def show_sub(self, sub):
        sub = tuple(sub[:2])
        target = self.page_widget(sub)
        for key, w in self.widgets.items():
            w.setVisible(w is target)
        if isinstance(target, OldPage):
            target.fill()
        self.current = sub
        page = self.pages.get(sub[0])
        if page is not None and sub[0] == "controls_tab" and sub[1]:
            name = "q7_controls_tab_Pages"
            if page.tab_current.get(name) != sub[1]:
                page.tab_current[name] = sub[1]
                try:
                    from gus_rigtool.tools import controls_tab as CT
                    CT._w(CT._on_page)()
                except Exception:
                    pass
        self._place_pin()
        self.refresh_selection()
        self.scroll.verticalScrollBar().setValue(0)

    # -------------------------------------------------- selection
    def refresh_selection(self):
        kinds, names, edges = self.frame.selection()
        self.selbox.set(list(zip(names, kinds)), _what(kinds))
        got = nextstep.suggest(kinds, self.current or (None, None), edges)
        if got:
            text, where, button, target = got
            self._target = target
            self.next.set(text, where, button)
        else:
            self._target = None
            self.next.set("", "", "")
        page = self.pages.get((self.current or (None,))[0])
        if page is not None:
            for _anchor, fn in page.rec.selection:
                try:
                    fn()
                except Exception:
                    pass

    def _go_next(self):
        if not self._target:
            return
        tool, sub = self._target
        if (tool, sub) == tuple(self.current or ()):
            for w in self.widgets.get(tuple(self.current), QtWidgets.QWidget()).findChildren(QtWidgets.QPushButton):
                if w.property("role") == "big" and w.isVisible():
                    self.scroll.ensureWidgetVisible(w)
                    w.setFocus()
                    break
            return
        self.frame.go((tool, sub))

    # -------------------------------------------------- pinning
    def toggle_pin(self, card, tool):
        s = _state()
        if self.pinned and self.pinned[0] is card:
            self._unpin()
            s["pinned"].pop(self.key, None)
        else:
            if self.pinned:
                self._unpin()
            lay = card.parentWidget().layout() if card.parentWidget() else None
            self.pinned = (card, lay, lay.indexOf(card) if lay is not None else -1)
            card.set_pinned(True)
            s["pinned"][self.key] = [tool, card.title]
            self._place_pin()
        _save_state(s)

    def _unpin(self):
        card, lay, idx = self.pinned
        card.set_pinned(False)
        if lay is not None:
            lay.insertWidget(max(0, idx), card)
        self.pinned = None

    def _place_pin(self):
        if self.pinned:
            card = self.pinned[0]
            self.pin_slot.addWidget(card)
            card.show()

    def _pin_from_state(self, tool):
        want = _state()["pinned"].get(self.key)
        if not want or want[0] != tool or self.pinned:
            return
        for card in self.pages[tool].cards:
            if card.title == want[1]:
                lay = card.parentWidget().layout() if card.parentWidget() else None
                self.pinned = (card, lay, lay.indexOf(card) if lay is not None else -1)
                card.set_pinned(True)
                return

    def find_card(self, title):
        for page in self.pages.values():
            for card in page.cards:
                if card.title.lower().startswith(title.lower()) or title.lower() in card.title.lower():
                    return card
        return None


def cut_off(area):
    """What sticks out past the right edge of an area's page (the 'nothing is cut off' check): [(kind, text)]."""
    vp = area.scroll.viewport()
    bad = []
    for w in area.scroll.widget().findChildren(QtWidgets.QWidget):
        if not w.isVisibleTo(area.scroll.widget()) or w.width() <= 0:
            continue
        p = w.mapTo(vp, QtCore.QPoint(w.width(), 0))
        if p.x() > vp.width() + 1:
            text = w.text() if hasattr(w, "text") and callable(w.text) else w.objectName()
            bad.append((type(w).__name__, str(text)[:40]))
    return bad


def _walk(n):
    yield n
    for c in n.children:
        for x in _walk(c):
            yield x


def _what(kinds):
    if not kinds:
        return ""
    if all(k == "joint" for k in kinds):
        return "a chain" if len(kinds) > 1 else "a joint"
    if all(k == "control" for k in kinds):
        return "%d control(s)" % len(kinds) if len(kinds) > 3 else ""
    return ""


# --------------------------------------------------------------------------- the frame
class Frame(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Frame, self).__init__(parent)
        import gus_rigtool
        self.setObjectName("gusFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.areas = {}
        self.area = None
        self.slim = False
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        top = QtWidgets.QWidget()
        top.setStyleSheet("background: #24272b;")
        th = QtWidgets.QHBoxLayout(top)
        th.setContentsMargins(8, 7, 8, 7)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search any tool...")
        self.search.addAction(icons.icon("search", 16, theme.FAINT), QtWidgets.QLineEdit.LeadingPosition)
        th.addWidget(self.search, 1)
        self._search_setup()
        root.addWidget(top)
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.side = QtWidgets.QWidget()
        self.side.setObjectName("gusSide")
        self.side.setAttribute(Qt.WA_StyledBackground, True)
        self.side_layout = QtWidgets.QVBoxLayout(self.side)
        self.side_layout.setContentsMargins(8, 8, 8, 8)
        self.side_layout.setSpacing(2)
        self.nav = {}
        self._build_side()
        body.addWidget(self.side)
        main = QtWidgets.QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.head = QtWidgets.QFrame()
        self.head.setObjectName("gusHead")
        hv = QtWidgets.QVBoxLayout(self.head)
        hv.setContentsMargins(14, 10, 14, 0)
        hv.setSpacing(2)
        trow = QtWidgets.QHBoxLayout()
        self.head_icon = QtWidgets.QLabel()
        self.head_icon.setFixedSize(34, 34)
        self.head_icon.setAlignment(Qt.AlignCenter)
        trow.addWidget(self.head_icon)
        self.head_title = QtWidgets.QLabel("")
        self.head_title.setObjectName("gusTitle")
        trow.addWidget(self.head_title, 1)
        hv.addLayout(trow)
        self.head_why = widgets.label("", "dim")
        hv.addWidget(self.head_why)
        self.tabs = widgets.flow_box(2)
        self.tabs.layout().setContentsMargins(0, 8, 0, 0)
        hv.addWidget(self.tabs)
        main.addWidget(self.head)
        self.stack = QtWidgets.QStackedWidget()
        main.addWidget(self.stack, 1)
        self.status = QtWidgets.QLabel("  Ready.")
        self.status.setObjectName("gusStatus")
        self.status.setWordWrap(True)
        main.addWidget(self.status)
        body.addLayout(main, 1)
        root.addLayout(body, 1)
        self.setWindowTitle("Gus_Rigtool %s" % gus_rigtool.__version__)
        from gus_rigtool.core import ui
        ui.STATUS_HOOKS[:] = [h for h in ui.STATUS_HOOKS if getattr(h, "__self__", None) is not None and
                              getattr(h, "__self__", None) is not _frame.get("w")] + [self.set_status]
        ui.REBUILD_HOOKS[:] = [self.rebuild]
        s = _state()
        self.go((s.get("area") or "controls", None))

    # -------------------------------------------------- sidebar
    def _nav_button(self, key, label, number=None):
        b = QtWidgets.QPushButton(label.replace("&", "&&"))
        b.setProperty("role", "nav")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        c = theme.colour(key) if key in CATEGORY else "#c9ccd1"
        b.setIcon(QtGui.QIcon(_badge(number, theme.area(key)[3] if key in CATEGORY else key, c)))
        b.setIconSize(QtCore.QSize(22, 22))
        b.setToolTip(label)
        b.setProperty("full", label.replace("&", "&&"))
        return b

    def _build_side(self):
        lay = self.side_layout
        steps = [a for a in theme.AREAS if a[0] not in ("home", "toolbox")]
        self.sec_labels = []
        b = self._nav_button("home", "Home")
        b.clicked.connect(lambda: self.go(("home", None)))
        lay.addWidget(b)
        self.nav["home"] = b
        sec = widgets.label("YOUR RIG, IN ORDER", "sec", wrap=False)
        self.sec_labels.append(sec)
        lay.addWidget(sec)
        for i, a in enumerate(steps):
            b = self._nav_button(a[0], a[1], i + 1)
            b.clicked.connect(lambda _=False, k=a[0]: self.go((k, None)))
            lay.addWidget(b)
            self.nav[a[0]] = b
        sec = widgets.label("ANY TIME", "sec", wrap=False)
        self.sec_labels.append(sec)
        lay.addWidget(sec)
        b = self._nav_button("toolbox", "Toolbox")
        b.clicked.connect(lambda: self.go(("toolbox", None)))
        lay.addWidget(b)
        self.nav["toolbox"] = b
        mine = self._nav_button("star", "My tools ▸")
        mine.setCheckable(False)
        mine.clicked.connect(self._my_tools)
        lay.addWidget(mine)
        self.mine = mine
        self.recent_head = widgets.label("RECENT", "sec", wrap=False)
        lay.addWidget(self.recent_head)
        self.recent_box = QtWidgets.QVBoxLayout()
        lay.addLayout(self.recent_box)
        self.help_head = widgets.label("HELP", "sec", wrap=False)
        lay.addWidget(self.help_head)
        self.help_btn = QtWidgets.QPushButton("Guide · What's new")
        self.help_btn.setProperty("role", "nav")
        self.help_btn.clicked.connect(self._help)
        lay.addWidget(self.help_btn)
        lay.addStretch(1)
        self.side.setFixedWidth(196)

    def _my_tools(self):
        from gus_rigtool import registry
        from gus_rigtool.core import utils
        m = QtWidgets.QMenu(self)
        keys = utils.load_setting("myTools", None) or registry.MY_TOOLS
        for k in keys:
            try:
                label = registry.get(registry.resolve(k)[0])[1]
            except KeyError:
                continue
            a = m.addAction(label)
            a.triggered.connect(lambda _=False, k=k: self.go_key(k))
        m.exec_(QtGui.QCursor.pos()) if hasattr(m, "exec_") else m.exec(QtGui.QCursor.pos())

    def _help(self):
        try:
            from gus_rigtool.core import ui
            ui.whats_new()
        except Exception:
            pass

    def _refresh_recent(self):
        from gus_rigtool import registry
        lay = self.recent_box
        _clear(lay)
        for area, tool, page in _state()["recent"][:3]:
            try:
                label = "%s › %s" % (theme.area(area)[1], "Edit shape" if (tool, page) == ("controls_tab", 2) else
                                     "Make" if (tool, page) == ("controls_tab", 1) else registry.get(tool)[1])
            except KeyError:
                continue
            b = QtWidgets.QPushButton(label.replace("&", "&&"))
            b.setProperty("role", "nav")
            b.clicked.connect(lambda _=False, t=(tool, page): self.go(t))
            lay.addWidget(b)
        self._apply_slim()

    # -------------------------------------------------- going places
    def go_key(self, key, section=None):
        """Show a tool (any key, old ones too), with one of its sections open."""
        area, tool, page = area_of(key)
        if tool == "controls_tab" and not page:
            page = _state()["sub"].get("controls", ["controls_tab", 1])[1] or 1
        self.go((tool, page), section)

    def go(self, where, section=None):
        """where: (area key, None) - its remembered sub-page - or (tool key, page)."""
        first, page = where
        if first in CATEGORY:
            area = first
            sub = _state()["sub"].get(area)
            area_obj = self._area(area)
            sub = tuple(sub) if sub and any(tuple(s[:2]) == tuple(sub) for s in area_obj.subs) else \
                tuple(area_obj.subs[0][:2]) if area_obj.subs else (None, None)
        else:
            area, tool, _p = area_of(first)
            area_obj = self._area(area)
            sub = (tool, page if tool == "controls_tab" else None)
            if tool == "controls_tab" and not page:
                sub = ("controls_tab", 1)
        self.area = area
        self.stack.setCurrentWidget(area_obj)
        self.setStyleSheet(theme.stylesheet(area_obj.accent))
        for k, b in self.nav.items():
            b.setChecked(k == area)
            b.setStyleSheet("QPushButton { border-left: 3px solid %s; }" % theme.colour(k) if k == area else "")
        a = theme.area(area)
        self.head_icon.setPixmap(_badge(None, a[3], a[2], 34))
        self.head_title.setText(a[1])
        self.head_why.setText(WHY.get(area, ""))
        if sub[0]:
            area_obj.show_sub(sub)
        self._fill_tabs(area_obj, sub)
        s = _state()
        s["area"] = area
        if sub[0]:
            s["sub"][area] = list(sub)
            rec = [area, sub[0], sub[1]]
            s["recent"] = [rec] + [r for r in s["recent"] if r != rec][:5]
        _save_state(s)
        self._refresh_recent()
        if section:
            card = area_obj.find_card(section)
            if card is not None:
                card.set_closed(False)
                area_obj.scroll.ensureWidgetVisible(card)

    def _area(self, key):
        if key not in self.areas:
            a = Area(self, key)
            self.areas[key] = a
            self.stack.addWidget(a)
        return self.areas[key]

    def _fill_tabs(self, area_obj, sub):
        lay = self.tabs.layout()
        _clear(lay)
        narrow = self.width() and self.width() < 520
        shown = area_obj.subs
        more = []
        if narrow and len(shown) > 3:
            keep = [s for s in shown[:2]]
            cur = [s for s in shown if tuple(s[:2]) == tuple(sub)]
            if cur and cur[0] not in keep:
                keep.append(cur[0])
            more = [s for s in shown if s not in keep]
            shown = keep
        for t, p, label in shown:
            b = QtWidgets.QPushButton(label.replace("&", "&&"))
            b.setProperty("role", "tab")
            b.setCheckable(True)
            b.setChecked((t, p) == tuple(sub))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=t, p=p: self.go((t, p)))
            lay.addWidget(b)
        if more:
            m = QtWidgets.QToolButton()
            m.setText("More ▾")
            m.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            menu = QtWidgets.QMenu(m)
            for t, p, label in more:
                a = menu.addAction(label)
                a.triggered.connect(lambda _=False, t=t, p=p: self.go((t, p)))
            m.setMenu(menu)
            m.setStyleSheet("QToolButton { background: transparent; color: %s; padding: 7px 10px; }" % theme.DIM)
            lay.addWidget(m)

    # -------------------------------------------------- selection, status, size
    def selection(self):
        """(kinds, short names, edges) of what's selected."""
        try:
            import maya.cmds as mc
            from gus_rigtool.core import utils
            nodes = utils.selected_transforms()
            edges = len([e for e in mc.ls(selection=True, flatten=True) or [] if ".e[" in e])
        except Exception:
            return [], [], 0
        return [widgets.kind_of(n) for n in nodes], [n.split("|")[-1] for n in nodes], edges

    def on_selection(self, *_):
        a = self.areas.get(self.area)
        if a is not None:
            a.refresh_selection()

    def set_status(self, message, level="info"):
        self.status.setText("  " + message)
        self.status.setStyleSheet("QLabel { background: %s; padding: 4px 8px; }" % theme.LEVEL.get(level,
                                                                                                theme.LEVEL["info"]))

    def rebuild(self, key):
        """A tool asked for its page again (My shapes changed...): drawn again."""
        area, tool, _p = area_of(key)
        a = self.areas.get(area)
        if a is None or tool not in a.pages:
            return
        for k in [k for k in a.widgets if k[0] == tool]:
            w = a.widgets.pop(k)
            w.setParent(None)
            w.deleteLater()
        a.pages.pop(tool, None)
        if a.current and a.current[0] == tool:
            a.show_sub(a.current)

    def resizeEvent(self, e):
        super(Frame, self).resizeEvent(e)
        self._apply_slim()
        a = self.areas.get(self.area)
        if a is not None and a.current:
            self._fill_tabs(a, a.current)

    def _apply_slim(self):
        slim = self.width() < SLIM
        self.slim = slim
        self.side.setFixedWidth(54 if slim else 196)
        for b in list(self.nav.values()) + [self.mine]:
            b.setText("" if slim else b.property("full"))
        for w in self.sec_labels + [self.recent_head, self.help_head, self.help_btn]:
            w.setVisible(not slim)
        for i in range(self.recent_box.count()):
            it = self.recent_box.itemAt(i)
            if it.widget():
                it.widget().setVisible(not slim)

    # -------------------------------------------------- search
    def _search_setup(self):
        from gus_rigtool import registry
        self.entries = {}
        for key, label, _m, sub in registry.TOOLS:
            area, _t, _p = area_of(key)
            self.entries["%s  —  %s" % (label, theme.area(area)[1])] = (key, None)
        for stage in registry.STAGES:
            self.entries["%s  —  %s" % (stage[4], stage[1])] = (stage[3], stage[4])
        self.entries["Edit shape  —  Controls"] = ("shapes", None)
        self.entries["Make controls  —  Controls"] = ("makectrl", None)
        comp = QtWidgets.QCompleter(sorted(self.entries))
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.search.setCompleter(comp)
        comp.activated.connect(self._search_go)
        self.search.returnPressed.connect(lambda: self._search_go(self.search.text()))

    def _search_go(self, text):
        got = self.entries.get(text)
        if not got:
            low = text.strip().lower()
            for k, v in self.entries.items():
                if low and low in k.lower():
                    got = v
                    break
        if got:
            self.go_key(got[0], got[1])
            QtCore.QTimer.singleShot(0, self.search.clear)


def _clear(lay):
    """Take every widget out of a layout now (not later: they'd still be drawn under the new ones)."""
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()


def _badge(number, icon_name, color, size=22):
    """The sidebar's coloured square: a number (the rig's steps) or a line icon."""
    ratio = 2.0
    px = QtGui.QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.transparent)
    p = QtGui.QPainter(px)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setBrush(QtGui.QColor(color))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, px.width(), px.height(), 6 * ratio, 6 * ratio)
    if number:
        p.setPen(QtGui.QColor("#111111"))
        f = QtGui.QFont()
        f.setBold(True)
        f.setPixelSize(int(size * ratio * 0.55))
        p.setFont(f)
        p.drawText(px.rect(), Qt.AlignCenter, str(number))
    else:
        inner = icons.pixmap(icon_name, int(size * 0.7 * ratio), "#111111", 2.0, 1.0)
        off = (px.width() - inner.width()) // 2
        p.drawPixmap(off, off, inner)
    p.end()
    px.setDevicePixelRatio(ratio)
    return px


# --------------------------------------------------------------------------- in Maya
def show(key=None, section=None):
    """Open (or bring forward) the new window; key: a tool to show."""
    import maya.cmds as mc
    import gus_rigtool
    if mc.workspaceControl(WS, exists=True) and _frame.get("w") is not None:
        try:
            mc.workspaceControl(WS, edit=True, restore=True, label="Gus_Rigtool %s" % gus_rigtool.__version__)
        except RuntimeError:
            pass
    else:
        if mc.workspaceControl(WS, exists=True):
            mc.deleteUI(WS)
        mc.workspaceControl(WS, label="Gus_Rigtool %s" % gus_rigtool.__version__, retain=False, floating=True,
                            initialWidth=640, initialHeight=820, minimumWidth=260, widthProperty="preferred",
                            uiScript="import gus_rigtool.newui.window as _w; _w.restore()")
        restore()
    w = _frame.get("w")
    if w is not None and key:
        w.go_key(key, section)
    return w


def restore():
    """Fill the window (Maya also runs this when it reopens the window at start-up)."""
    import maya.cmds as mc
    import gus_rigtool
    from gus_rigtool.newui.qt import maya_widget
    try:
        mc.workspaceControl(WS, edit=True, label="Gus_Rigtool %s" % gus_rigtool.__version__)
    except RuntimeError:
        pass
    host = maya_widget(WS, "control")
    if host is None:
        return None
    frame = Frame()
    if host.layout() is None:
        QtWidgets.QVBoxLayout(host)
    host.layout().setContentsMargins(0, 0, 0, 0)
    host.layout().addWidget(frame)
    _frame["w"] = frame
    try:
        mc.scriptJob(event=["SelectionChanged", frame.on_selection], parent=WS)
    except RuntimeError:
        pass
    frame.on_selection()
    return frame


def close():
    import maya.cmds as mc
    if mc.workspaceControl(WS, exists=True):
        mc.deleteUI(WS)
    _frame["w"] = None
