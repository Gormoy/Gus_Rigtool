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
NEW_LOOK = ("controls", "skin", "settings", "build", "connect", "check", "toolbox")
EXTRA_TOOLS = {"check": ["publish"]}             # 5.7.6: pages only the new window has (Publish moved from Build)
MOVED_OUT = {"build": "publish"}                 # ...and the tool whose page no longer shows it   # the areas in the new look (5.7.0 Controls, 5.7.2 Skin,
#                                                        5.7.3 Build)
# a tool whose page has its own tabs: each tab a sub-page (5.7.3 Build) - its tabLayout's name, the tabs' labels
TABBED = {"build": ("Tabs", ["Rig builder", "Animation", "Existing rig", "Advanced"])}
TWO_ROWS = ("build", "skin", "connect", "toolbox")                     # tools on the top row, the chosen tool's sub-pages under it
# a long tool page shown as several sub-pages: (label, the card titles on it) - 5.7.2 Skin (Gus's picture)
SPLITS = {"skin": [("Bind", ["Bind"]), ("Copy & mirror", ["Copy skin", "Mirror weights"]),
                   ("Save / load", ["Save / load weights"]), ("Clean", ["Clean"]),
                   ("Weights", ["Vertex weights", "Weight list"]), ("Cloth & jiggle", ["Cloth", "Jiggle and wave"])],
          # 5.7.4 (Gus's picture): Face as steps on one page, the rest on two short ones; Ribbon as steps
          "face": [("Build the face", ["Setup", "Eyes", "Eyelids", "Mouth", "Brows", "Facial strips"]),
                   ("Ribbons & groups", ["Face ribbons", "Group controls (mouth)"]),
                   ("Squash & expressions", ["Head squash", "Expressions and selection sets"])],
          "ribbon": [("Make a ribbon", ["Surface", "Follicles", "Controls", "Build and mirror"]),
                     ("Builds in the scene", ["Builds in the scene"])],
          # 5.7.5 (Gus: "its ok")
          "nodes": [("See & trace", ["Name utility nodes", "Select the setup", "Trace a channel", "Node Editor"]),
                    ("Make a driver", ["Make a driver", "Setups library"]),
                    ("Find & clean", ["Find problems", "Clean up"])],
          # 5.7.7 (Gus left it to me: the only long Toolbox page)
          "pivots": [("Move", ["Move pivots to", "Bounding box", "From geometry", "Along a chain"]),
                     ("Remember & reset", ["Remember / mirror", "Reset"])]}
# 5.7.8 (Gus: "ok"): a page that was one section, in a few, so it can be arranged - (tool, the section's title):
# its new title, then [(a new section's title, what moves into it: a button's words or a name's words)]
CARD_SPLITS = {
    ("skin", "Bind"): ("Bind", [("Add joints", ["Add joints to the skin"])]),
    ("skin", "Save / load weights"): ("Save weights", [("Load weights", ["Old exports by", "Import weights"])]),
    ("skin", "Clean"): ("Prune", [("Limit influences", ["Influences per vertex", "Limit"]),
                                  ("Remove unused joints", ["Remove unused"])]),
    ("publish", "Publish (clean rig for animators)"): ("Publish (clean rig for animators)",
                                                       [("Deliver to animators", ["Deliver to animators"])]),
    ("stick", "Stick to skin"): ("Stick", [("Find what's stuck", ["Select stuck", "Show follow joints"])]),
}
SPLITS["skin"][0] = ("Bind", ["Bind", "Add joints"])
SPLITS["skin"][2] = ("Save / load", ["Save weights", "Load weights"])
SPLITS["skin"][3] = ("Clean", ["Prune", "Limit influences", "Remove unused joints"])
# 5.7.5: plain names for the tabs (the old window keeps its own)
TOOL_LABEL = {"connect": "Connections", "sdk": "Driven keys"}


def tool_label(tool):
    from gus_rigtool import registry
    return TOOL_LABEL.get(tool) or registry.get(tool)[1]
FACE_STEPS = {"brows": "Brows", "eyes": "Eyes", "eyelids": "Eyelids", "mouth": "Mouth", "strip": "Facial strips"}
RIBBON_STEPS = ["Surface", "Follicles", "Controls", "Build and mirror"]
OLD_PAGE = ()                                    # 5.7.8: none - Settings is drawn in the new look too
CATEGORY = {"home": "home", "build": "build", "skin": "skin", "controls": "controls", "connect": "links",
            "check": "finish", "toolbox": "toolbox", "settings": "settings"}
WHY = {"home": "Where you are in the rig, and the next step.",
       "build": "Modules, face, ribbons and joints: the rig's skeleton and parts.",
       "skin": "Bind meshes and fix the weights.",
       "controls": "Make controls and shape them; how they behave, their attributes, spaces and follows.",
       "connect": "Constraints, connections, nodes and driven keys.",
       "check": "Find problems, tidy up and hand the rig over.",
       "toolbox": "Small tools for any moment.",
       "settings": "Update, your defaults, the window, side colours, the shelf - one place."}
SLIM = 560                                       # narrower than this: the sidebar shows its icons only
SHORT = 640                                      # lower than this: Recent and Help fold away
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
    if tool == "settings":                       # 5.7.2: Settings is its own button (not in the Toolbox)
        return "settings", tool, page
    for area, extra in EXTRA_TOOLS.items():
        if tool in extra:
            return area, tool, page
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

    def __init__(self, frame, key, only=None, prefix="q7_"):
        super(Area, self).__init__()
        from gus_rigtool import registry
        self.frame, self.key, self.pfx = frame, key, prefix
        self.accent = theme.colour(key)
        self.tools = ["settings"] if key == "settings" else [
            t for t in dict((c, k) for c, _l, k in registry.CATEGORIES).get(CATEGORY[key], []) if t != "settings"]
        self.tools += EXTRA_TOOLS.get(key, [])
        if only:
            self.tools = [t for t in self.tools if t in only]
        self.subs = []                          # [(tool key, page or None, label)]
        for t in self.tools:
            if t == "controls_tab" and key in NEW_LOOK:
                self.subs += [("controls_tab", 1, "Make"), ("controls_tab", 2, "Edit shape")]
            elif t in SPLITS and key in NEW_LOOK:
                self.subs += [(t, label, label) for label, _titles in SPLITS[t]]
            elif t in TABBED and key in NEW_LOOK:
                self.subs += [(t, i + 1, label) for i, label in enumerate(TABBED[t][1])]
            else:
                self.subs.append((t, None, tool_label(t)))
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
        self.arranging = False
        self.arrange_bar = QtWidgets.QFrame()          # 5.7.8: Arrange - put this page's sections in your order
        self.arrange_bar.setObjectName("gusArrangeBar")
        ab = QtWidgets.QVBoxLayout(self.arrange_bar)
        ab.setContentsMargins(10, 8, 10, 8)
        ab.setSpacing(6)
        ab.addWidget(widgets.label("Arrange this page: Up / Down / To top on each section (or drag a section by "
                                   "its title). Your order is kept for this page.", wrap=True))
        brow = widgets.flow_box(6)
        reset = QtWidgets.QPushButton("Reset order")
        reset.setToolTip("Back to the tool's own order")
        reset.clicked.connect(lambda _=False: self.current and self.move_card(tuple(self.current[:2]), "",
                                                                             "@Reset order"))
        done = QtWidgets.QPushButton("Done")
        widgets._set_role(done, "accent")
        done.clicked.connect(lambda _=False: self.arrange(False))
        brow.layout().addWidget(reset)
        brow.layout().addWidget(done)
        ab.addWidget(brow)
        self.arrange_bar.hide()
        self.inner.addWidget(self.arrange_bar)
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
        self._orig = {}                         # 5.7.8.1: each sub-page's own order (its first drawing)

    # -------------------------------------------------- pages
    def default_sub(self, tool, page=None):
        """The sub-page to show for a tool: the one asked for, else the one you used last, else its first."""
        mine = [tuple(x[:2]) for x in self.subs if x[0] == tool]
        if (tool, page) in mine:
            return (tool, page)
        last = _state()["sub"].get(self.key)
        if last and tuple(last) in mine:
            return tuple(last)
        return mine[0] if mine else (tool, page)

    def page_widget(self, sub):
        tool, page = sub[0], sub[1]
        if tool in SPLITS:
            page = None                         # one page, its cards shown a sub-page at a time
        if (tool, page) in self.widgets:
            return self.widgets[(tool, page)]
        if self.key in NEW_LOOK and tool not in OLD_PAGE:
            self._build_new(tool)
        else:
            w = OldPage(tool)
            self.widgets[(tool, page)] = w
            self.body.addWidget(w)
        return self.widgets.get((tool, page))

    def _build_new(self, tool):
        from gus_rigtool import registry
        from gus_rigtool.core import ui
        mod = registry.module(tool)
        prefix = self.prefix(tool)
        ui._view["tool"] = tool                 # Simple view: the tool's advanced sections start closed, as before
        moved = tool in MOVED_OUT and hasattr(mod, "SKIP_PUBLISH")
        if moved:
            mod.SKIP_PUBLISH["on"] = True       # its Publish section is on Check & publish > Publish
        try:
            rec = record.record(registry.builder(tool), prefix)
        finally:
            ui._view["tool"] = None
            if moved:
                mod.SKIP_PUBLISH["on"] = False
        page = render.Page(tool, rec, self.accent)
        self.pages[tool] = page
        if tool == "controls_tab":
            self._controls_tab(page, mod, prefix)
        elif tool in TABBED:
            self._tabbed(page, tool, prefix)
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
        _split_cards(page, tool)
        if tool == "face":
            self._face_map(page)
        if tool == "ribbon":
            self._step_strip(page)
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
            card.no_pin = True
            if i == 1:                                   # 5.7.8: Edit shape's 'Select the controls to change',
                for x in _loose_before_cards(w):         # its button and 'Keep their size and place' belong to
                    card.add(x)                          # the swap: they move with it
            card.add(grid)
            w.layout().insertWidget(0, card)
            w.layout().setContentsMargins(0, 0, 0, 0)
            self.grids.append(grid)
            self.widgets[("controls_tab", i + 1)] = w
            self.body.addWidget(w)

    # 5.7.4: the face map (Face > Build the face) and the step strip (Ribbon > Make a ribbon)
    def _top_of(self, tool, w):
        page_w = self.widgets.get((tool, None))
        if page_w is not None:
            page_w.layout().insertWidget(0, w)
        return w

    def _face_map(self, page):
        card = widgets.Card("Your face", None, "Each part in its colour: green made, yellow your selection fits "
                            "(press its button), grey not made yet. The right side (dashed) is mirrored for you. "
                            "Click a part: its step.")
        card.pin.hide()
        card.no_pin = True
        row = widgets.flow_box(14)                     # narrow: the key goes under the face
        self.face_map = widgets.FaceMap()
        row.layout().addWidget(self.face_map)
        key = QtWidgets.QWidget()
        legend = QtWidgets.QVBoxLayout(key)
        legend.setContentsMargins(0, 8, 0, 0)
        for st, word in (("made", "made"), ("ready", "your selection fits"), ("todo", "not made yet")):
            lab = widgets.label("<span style='color:%s'>■</span>  %s" % (widgets.STATE_COLOUR[st], word), "dim")
            legend.addWidget(lab)
        legend.addStretch(1)
        row.layout().addWidget(key)
        card.add(row)
        self.face_map.clicked.connect(lambda part: self._scroll_to_card(page, FACE_STEPS.get(part)))
        self.face_card = self._top_of("face", card)

    def _step_strip(self, page):
        self.strip = widgets.StepStrip(["Surface", "Joints", "Controls", "Create"])
        self.strip.clicked.connect(lambda i: self._scroll_to_card(page, RIBBON_STEPS[i]))
        self._top_of("ribbon", self.strip)

    def _scroll_to_card(self, page, title):
        for card in page.cards:
            if card.title == title:
                card.set_closed(False)
                self.scroll.ensureWidgetVisible(card, 0, 40)
                return card

    def _update_steps(self):
        """The face map / step strip from the scene and the selection (on each selection change)."""
        cur = self.current or (None, None)
        if getattr(self, "face_map", None) is not None and cur[0] == "face":
            try:
                from gus_rigtool.tools import face_kit_tool as FT
                self.face_map.set_states(FT.part_states())
            except Exception:
                pass
        if getattr(self, "strip", None) is not None and cur[0] == "ribbon":
            try:
                from gus_rigtool.tools import ribbon_tool as RT
                self.strip.set_states(RT.step_states())
            except Exception:
                pass

    def _tabbed(self, page, tool, prefix):
        """A tool with its own tabs (Build): what is above them (its status light) stays on every sub-page; each
        tab is a sub-page."""
        w = page.build()
        w.layout().setContentsMargins(0, 0, 0, 0)
        name = prefix + TABBED[tool][0]
        w.tab_name = name
        w.tab_pages = [pw for _l, pw in page.tabs.get(name, [])]
        for pw in w.tab_pages:
            w.layout().insertWidget(w.layout().count() - 1, pw)
        for i in range(max(1, len(w.tab_pages))):
            self.widgets[(tool, i + 1)] = w
        page.on_tab = lambda _name, i, t=tool: self.frame.go((t, i))
        self.body.addWidget(w)

    def _show_tab(self, page, w, i):
        for j, pw in enumerate(getattr(w, "tab_pages", [])):
            pw.setVisible(j + 1 == i)
        name = getattr(w, "tab_name", "")
        if page.tab_current.get(name) != i:
            page.tab_current[name] = i
            node = page.rec.find(name)
            cc = node.kw.get("changeCommand") or node.kw.get("cc") if node is not None else None
            if cc:
                try:
                    render._call(cc)
                except Exception:
                    pass

    def prefix(self, tool):
        return "%s%s_" % (self.pfx, tool)

    def _show_cards(self, page, sub):
        """A split page: only this sub-page's cards, numbered 1, 2... (nothing left out: a card no sub-page names
        shows on the first)."""
        groups = SPLITS[sub[0]]
        named = set(t for _l, ts in groups for t in ts)
        want = dict(groups).get(sub[1], [])
        first = sub[1] == groups[0][0]
        n = 0
        for card in page.cards:
            if self.pinned and card is self.pinned[0]:
                continue
            on = card.title in want or (first and card.title not in named)
            card.setVisible(on)
            if on and getattr(card, "number", None):
                n += 1
                card.set_number(n)

    def _mark_all(self, name):
        for g in getattr(self, "grids", []):
            g.mark(name)

    def arrange(self, on):
        """5.7.8: Arrange on / off - each section closed to its title, with Up / Down / To top."""
        if on and self.current and isinstance(self.widgets.get(tuple(self.current[:2])), OldPage):
            return
        self.arranging = bool(on)
        self.arrange_bar.setVisible(self.arranging)
        if self.current:
            for c in self._cards_of(self.current):
                if not getattr(c, "no_move", False):
                    c.set_arranging(self.arranging)
        if self.arranging:
            self.scroll.ensureWidgetVisible(self.arrange_bar)
        _arrange_label(self.frame)

    def show_sub(self, sub):
        if self.arranging:
            self.arrange(False)
        sub = tuple(sub[:2])
        target = self.page_widget(sub)
        for key, w in self.widgets.items():
            w.setVisible(w is target)
        if isinstance(target, OldPage):
            target.fill()
        self.current = sub
        page = self.pages.get(sub[0])
        if page is not None and sub[0] in SPLITS:
            self._show_cards(page, sub)
        if getattr(self, "face_card", None) is not None:
            self.face_card.setVisible(tuple(sub) == ("face", SPLITS["face"][0][0]))
        if getattr(self, "strip", None) is not None:
            self.strip.setVisible(tuple(sub) == ("ribbon", SPLITS["ribbon"][0][0]))
        if page is not None and sub[0] in TABBED and sub[1]:
            self._show_tab(page, target, sub[1])
        if page is not None and sub[0] == "controls_tab" and sub[1]:
            name = self.prefix("controls_tab") + "Pages"
            if page.tab_current.get(name) != sub[1]:
                page.tab_current[name] = sub[1]
                try:
                    from gus_rigtool.tools import controls_tab as CT
                    CT._w(CT._on_page)()
                except Exception:
                    pass
        self._place_pin()
        self._apply_order(sub)
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
        self._update_steps()

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
        self.frame.go((tool, sub), as_tool=True)

    # -------------------------------------------------- pinning
    # -------------------------------------------------- 5.7.7: your own order of the sections, per page
    def _order_key(self, sub):
        return "%s|%s" % (sub[0], sub[1])

    def _cards_of(self, sub):
        """The cards shown on this sub-page (the tool's, and the window's own - the shape grid, the face map)."""
        w = self.widgets.get(tuple(sub)) or self.widgets.get((sub[0], None))
        if w is None:
            return []
        def shown(c):                                   # not hidden, nor inside a hidden part (another tab's page)
            while c is not None and c is not w:
                if c.isHidden():
                    return False
                c = c.parentWidget()
            return True
        return [c for c in w.findChildren(widgets.Card) if c.property("inner") != "true" and
                not (self.pinned and c is self.pinned[0]) and shown(c)]

    def _apply_order(self, sub):
        key = self._order_key(sub)
        if key not in self._orig:                      # 5.7.8.1: the tool's own order, for an instant Reset
            self._orig[key] = [c.title for c in self._visual(sub)]
        want = _state().get("order", {}).get(key)
        for card in self._cards_of(sub):
            if not getattr(card, "order_hooked", False):
                card.moved.connect(lambda src, to: self.move_card(tuple(self.current[:2]), src, to))
                card.order_hooked = True
        if want:
            self._place(sub, want)

    def _place(self, sub, titles):
        """Put the cards in this order. Only the cards move (into the place of the card they go before or after);
        everything else on the page keeps its place."""
        cards = dict((c.title, c) for c in self._cards_of(sub))
        seq = [cards[t] for t in titles if t in cards]
        seq += [c for c in self._visual(sub) if c not in seq]
        for i, c in enumerate(seq):
            vis = self._visual(sub)
            if i == 0:
                if vis and vis[0] is not c:
                    self._move_next_to(c, vis[0], after=False)
            elif vis.index(c) != vis.index(seq[i - 1]) + 1:
                self._move_next_to(c, seq[i - 1], after=True)
        page = self.pages.get(sub[0])
        if page is not None:
            rank = dict((id(c), i) for i, c in enumerate(self._visual(sub)))
            pos = dict((id(c), i) for i, c in enumerate(page.cards))
            page.cards.sort(key=lambda c: (rank.get(id(c), len(rank) + pos[id(c)])))
            if sub[0] in SPLITS:
                self._show_cards(page, sub)
            else:
                page.renumber()

    @staticmethod
    def _move_next_to(card, other, after):
        lay = other.parentWidget().layout() if other.parentWidget() else None
        if not isinstance(lay, QtWidgets.QBoxLayout):
            return
        old = card.parentWidget().layout() if card.parentWidget() else None
        if old is not None:
            old.removeWidget(card)
        lay.insertWidget(lay.indexOf(other) + (1 if after else 0), card)
        card.show()

    def move_card(self, sub, src, to):
        """Drag a card onto another (it goes before it), or Move up / down / to top, Reset order."""
        s = _state()
        order = s.setdefault("order", {})
        key = self._order_key(sub)
        titles = [c.title for c in self._visual(sub)]
        if to == "@Reset order":
            order.pop(key, None)
            _save_state(s)
            if key in self._orig:                      # 5.7.8.1: back at once (5.7.8 drew the page again)
                self._place(sub, self._orig[key])
                return
            was = self.arranging
            if was:
                self.arrange(False)
            if self.current and tuple(self.current[:2]) == tuple(sub[:2]):
                self.frame.rebuild(sub[0])
            if was:
                self.arrange(True)
            return
        if src not in titles:
            return
        i = titles.index(src)
        titles.pop(i)
        if to == "@Move up":
            titles.insert(max(0, i - 1), src)
        elif to == "@Move down":
            titles.insert(min(len(titles), i + 1), src)
        elif to == "@Move to top":
            titles.insert(0, src)
        elif to in titles:
            titles.insert(titles.index(to), src)
        else:
            titles.insert(i, src)
        order[key] = titles
        _save_state(s)
        self._place(sub, titles)

    def _visual(self, sub):
        """The cards in the order they're shown (by where they sit in the page's layouts, top to bottom)."""
        def path(w):
            out = []
            while w is not None and w.parentWidget() is not None:
                p = w.parentWidget()
                lay = p.layout()
                out.insert(0, lay.indexOf(w) if lay is not None else 0)
                if p is self:
                    break
                w = p
            return out
        return sorted(self._cards_of(sub), key=path)

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


def _split_cards(page, tool):
    """5.7.8: CARD_SPLITS - a section's buttons / named fields into new sections right after it (nothing is lost:
    the same widgets move, so the tool reads and fills them as before)."""
    for card in list(page.cards):
        spec = CARD_SPLITS.get((tool, card.title))
        if not spec:
            continue
        new_title, parts = spec
        lay = card.parentWidget().layout() if card.parentWidget() else None
        if not isinstance(lay, QtWidgets.QBoxLayout):
            continue
        at = lay.indexOf(card)
        made = []
        for title, marks in parts:
            units = [u for u in (_unit_for(card, m) for m in marks) if u]
            if not units:
                continue
            new = widgets.Card(title, len(page.cards) + 1, card.help_text)
            buttons = None
            for kind, a, b in units:
                if kind == "row":
                    box = QtWidgets.QWidget()
                    form = widgets.FormLayout(box, align=Qt.AlignLeft if theme.new_look() else Qt.AlignRight,
                                              label_max=render.LABEL_W if theme.new_look() else None)
                    form.addRow(a, b)
                    new.add(box)
                elif kind == "button":
                    if buttons is None:
                        buttons = widgets.flow_box(6)
                        new.add(buttons)
                    a.setProperty("stretch", True)
                    buttons.layout().addWidget(a)
                else:
                    new.add(a)
            at += 1
            lay.insertWidget(at, new)
            page.cards.insert(page.cards.index(card) + 1 + len(made), new)
            made.append(new)
        if made:
            card.set_title(new_title)
        page.renumber()


def _unit_for(card, mark):
    """What to move for a mark: ('button', the button), ('row', its name, its field) or ('widget', w); the unit is
    taken out of where it is."""
    for w in card.body.findChildren(QtWidgets.QWidget):
        text = w.text() if hasattr(w, "text") and callable(w.text) else ""
        if not text or not str(text).replace("&&", "&").startswith(mark):
            continue
        parent = w.parentWidget()
        lay = parent.layout() if parent is not None else None
        if isinstance(w, QtWidgets.QAbstractButton):
            if lay is not None:
                lay.removeWidget(w)
            return ("button", w, None)
        if isinstance(w, QtWidgets.QLabel) and isinstance(lay, widgets.FormLayout):
            for l, f in lay._rows:
                if l is not None and l.widget() is w and f is not None:
                    field = f.widget()
                    lay.takeAt(lay._items.index(f))
                    lay.takeAt(lay._items.index(l))
                    if not [x for x in lay._items]:
                        parent.hide()
                    return ("row", w, field)
        if isinstance(w, QtWidgets.QLabel) and lay is not None:      # a label beside its field in a row
            items = [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget() is not None]
            i = items.index(w) if w in items else -1
            if 0 <= i < len(items) - 1:
                field = items[i + 1]
                lay.removeWidget(w)
                lay.removeWidget(field)
                if len(items) == 2:
                    parent.hide()
                return ("row", w, field)
    return None


def _loose_before_cards(w):
    """The widgets before a page's first section, in the layout that holds its sections (taken out of it)."""
    first = [c for c in w.findChildren(widgets.Card) if c.property("inner") != "true"]
    if not first:
        return []
    lay = first[0].parentWidget().layout() if first[0].parentWidget() else None
    if lay is None:
        return []
    out = []
    for k in range(lay.indexOf(first[0])):
        it = lay.itemAt(k)
        if it is not None and it.widget() is not None and not isinstance(it.widget(), widgets.Card):
            out.append(it.widget())
    for x in out:
        lay.removeWidget(x)
    return out


def selection():
    """(kinds, short names, edges) of what's selected."""
    try:
        import maya.cmds as mc
        from gus_rigtool.core import utils
        nodes = utils.selected_transforms()
        edges = len([e for e in mc.ls(selection=True, flatten=True) or [] if ".e[" in e])
    except Exception:
        return [], [], 0
    return [widgets.kind_of(n) for n in nodes], [n.split("|")[-1] for n in nodes], edges


def _subtitle(tool):
    from gus_rigtool import registry
    try:
        return registry.get(tool)[3] if tool else ""
    except KeyError:
        return ""


def _head_buttons(owner):
    """The old window's header buttons: Guide, Simple / Full view, What's new, Update..., and Pop out."""
    from gus_rigtool.core import ui
    box = widgets.flow_box(4)
    simple = ui.view_mode() == "simple"
    items = [("☆ Favourite", "Add this page to your favourites (the row at the top, and the floating bar) - "
              "click again to take it off.", lambda: _star(owner)),
             ("Pop out", "Open this page in its own panel (several can be open side by side).",
              lambda: owner.pop_out()),
             ("Arrange", "Put this page's sections in your own order: Up / Down / To top on each section "
              "(or drag a section by its title). Kept for this page.", lambda: _arrange(owner)),
             ("Guide", "A step-by-step guide to rigging with Gus_Rigtool.", lambda: ui._guide()),
             ("Full view" if simple else "Simple view", "Simple: advanced sections folded away. Full: everything "
              "as you left it.", lambda: _toggle_view(owner)),
             ("What's new", "What changed in this version.", lambda: ui.whats_new()),
             ("Update...", "Install a newer Gus_Rigtool zip (it restarts by itself).", lambda: ui._update())]
    for text, tip, fn in items:
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton { background: rgba(0,0,0,0.25); padding: 3px 8px; font-size: 12px; }")
        b.clicked.connect(lambda _=False, fn=fn: fn())
        box.layout().addWidget(b)
    box.setMaximumWidth(330)
    return box


def _arrange(owner):
    a = owner.areas.get(owner.area) if hasattr(owner, "areas") else None
    if a is None or not hasattr(a, "arrange"):
        return
    if not a.arranging and a.current and isinstance(a.widgets.get(tuple(a.current[:2])), OldPage):
        _set_status(owner, "This page can't be arranged yet.", "info")
        return
    a.arrange(not a.arranging)


def _arrange_label(owner):
    a = owner.areas.get(owner.area) if hasattr(owner, "areas") else None
    on = bool(a is not None and getattr(a, "arranging", False))
    for b in owner.head_buttons.findChildren(QtWidgets.QPushButton):
        if b.text() in ("Arrange", "Done arranging"):
            b.setText("Done arranging" if on else "Arrange")


def _star(owner):
    from gus_rigtool.newui import favourites
    a = owner.areas.get(owner.area) if hasattr(owner, "areas") else None
    tool = a.current[0] if a is not None and a.current else None
    if not tool:
        return
    on = favourites.toggle(tool)
    _set_status(owner, "%s %s your favourites." % (favourites.label(tool), "added to" if on else "taken off"),
                "ok")
    _star_label(owner)


def _star_label(owner):
    from gus_rigtool.newui import favourites
    a = owner.areas.get(owner.area) if hasattr(owner, "areas") else None
    tool = a.current[0] if a is not None and a.current else None
    for b in owner.head_buttons.findChildren(QtWidgets.QPushButton):
        if "Favourite" in b.text():
            b.setText("★ Favourite" if tool in favourites.keys() else "☆ Favourite")


def _toggle_view(owner):
    from gus_rigtool.core import ui, utils
    utils.save_setting("viewMode", "full" if ui.view_mode() == "simple" else "simple")
    _set_status(owner, "%s view: the pages open that way from now on (reopen the window to see it)." % (
        "Simple" if ui.view_mode() == "simple" else "Full"), "info")


def _status_bar(owner):
    """The status line, with 'Copy error report' after an error (as in the old window)."""
    from gus_rigtool.core import ui
    bar = QtWidgets.QWidget()
    h = QtWidgets.QHBoxLayout(bar)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    owner.status = QtWidgets.QLabel("  Ready.")
    owner.status.setObjectName("gusStatus")
    owner.status.setWordWrap(True)
    h.addWidget(owner.status, 1)
    owner.copy_error = QtWidgets.QPushButton("Copy error report")
    owner.copy_error.setToolTip("Copy what went wrong - paste it in your message to get it fixed.")
    owner.copy_error.clicked.connect(lambda _=False: ui.copy_error())
    owner.copy_error.setVisible(bool(ui._last_error["text"]))
    h.addWidget(owner.copy_error)
    return bar


def _set_status(owner, message, level):
    from gus_rigtool.core import ui
    owner.status.setText("  " + message)
    owner.status.setStyleSheet("QLabel { background: %s; padding: 4px 8px; }" % theme.LEVEL.get(level,
                                                                                         theme.LEVEL["info"]))
    owner.copy_error.setVisible(bool(ui._last_error["text"]))


def alive(w):
    try:
        from gus_rigtool.newui.qt import shiboken
        return w is not None and shiboken.isValid(w)
    except Exception:
        return w is not None


def cut_off(area):
    """What sticks out past the right edge of an area's page (the 'nothing is cut off' check): [(kind, text)]."""
    vp = area.scroll.viewport()
    bad = []
    for w in area.scroll.widget().findChildren(QtWidgets.QWidget):
        if not w.isVisibleTo(area.scroll.widget()) or w.width() <= 0:
            continue
        p = w.mapTo(vp, QtCore.QPoint(w.width(), 0))
        text = w.text() if hasattr(w, "text") and callable(w.text) else ""
        if p.x() > vp.width() + 1:
            bad.append((type(w).__name__, str(text or w.objectName())[:40]))
        elif isinstance(w, QtWidgets.QAbstractButton) and text and not _fits(w, text):
            bad.append((type(w).__name__ + " text", str(text)[:40]))
        elif isinstance(w, QtWidgets.QComboBox) and not _combo_fits(w):
            bad.append(("drop-down text", str(w.currentText())[:40]))
    return bad


def _combo_fits(w):
    """A drop-down shows its whole choice (5.7.3: 'One per spa...' was cut) - the one it shows (5.7.7: its list
    opens as wide as the longest)."""
    fm = w.fontMetrics()
    adv = fm.horizontalAdvance if hasattr(fm, "horizontalAdvance") else fm.width
    room = w.width() - 28                            # the arrow and the padding
    return adv(w.currentText()) <= room + 1


def _fits(w, text):
    """A button's text isn't cut off: its longest word fits on it (a wrapping one), or all of it (the others)."""
    lb = getattr(w, "_lb", None)
    fm = (lb or w).fontMetrics()
    adv = (lambda t: fm.horizontalAdvance(t)) if hasattr(fm, "horizontalAdvance") else (lambda t: fm.width(t))
    if lb is not None:
        room = lb.width()
        return all(adv(word) <= room + 1 for word in str(text).replace("\n", " ").split())
    if isinstance(w, QtWidgets.QToolButton):
        return True                                  # the shape tiles: two lines, their own size
    room = w.contentsRect().width() - 8
    return all(adv(line) <= room + 1 for line in str(text).replace("&&", "&").split("\n"))


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
        theme.load_look()                       # 5.7.7: today's look or the new one (Settings > Window)
        super(Frame, self).__init__(parent)
        import gus_rigtool
        self.setObjectName("gusFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.areas = {}
        self.area = None
        self.slim = False
        self.side_hidden = bool(_state().get("side_hidden", False))
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
        from gus_rigtool.newui import favourites
        self.favs = favourites.FavRow()
        self.favs.setStyleSheet("background: #24272b;")
        root.addWidget(self.favs)
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
        trow.setSpacing(12)                              # 5.7.8: a gap between the icon and the area's name
        self.head_icon = QtWidgets.QLabel()
        self.head_icon.setFixedSize(34, 34)
        self.head_icon.setAlignment(Qt.AlignCenter)
        trow.addWidget(self.head_icon)
        self.head_title = QtWidgets.QLabel("")
        self.head_title.setObjectName("gusTitle")
        trow.addWidget(self.head_title, 1)
        self.head_buttons = _head_buttons(self)
        trow.addWidget(self.head_buttons, 0, Qt.AlignTop)
        hv.addLayout(trow)
        self.head_why = widgets.label("", "dim")
        hv.addWidget(self.head_why)
        self.tabs = widgets.flow_box(2)
        self.tabs.layout().setContentsMargins(0, 8, 0, 0)
        hv.addWidget(self.tabs)
        self.tabs2 = widgets.flow_box(2)                 # 5.7.3: the chosen tool's sub-pages (Build, Skin)
        self.tabs2.setObjectName("gusTabs2")
        self.tabs2.layout().setContentsMargins(0, 2, 0, 0)
        hv.addWidget(self.tabs2)
        main.addWidget(self.head)
        self.subtitle = widgets.label("", "dim")
        self.subtitle.setContentsMargins(14, 6, 14, 0)
        self.subtitle.setStyleSheet("QLabel { background: %s; }" % theme.PANEL)
        main.addWidget(self.subtitle)
        self.stack = QtWidgets.QStackedWidget()
        main.addWidget(self.stack, 1)
        main.addWidget(_status_bar(self))
        body.addLayout(main, 1)
        root.addLayout(body, 1)
        self.setWindowTitle("Gus_Rigtool %s" % gus_rigtool.__version__)
        from gus_rigtool.core import ui
        ui.STATUS_HOOKS.append(self.set_status)
        ui.REBUILD_HOOKS.append(self.rebuild)
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
        self.side_toggle = QtWidgets.QToolButton()      # 5.7.8: hide the sidebar to a thin strip of icons
        self.side_toggle.setAutoRaise(True)
        self.side_toggle.setCursor(Qt.PointingHandCursor)
        self.side_toggle.setStyleSheet("QToolButton { color: %s; font-size: 15px; padding: 0px 6px; }" % theme.DIM)
        self.side_toggle.clicked.connect(self.toggle_side)
        lay.addWidget(self.side_toggle, 0, Qt.AlignRight)
        steps = [a for a in theme.AREAS if a[0] not in ("home", "toolbox", "settings")]
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
        b = self._nav_button("settings", "Settings")         # 5.7.2: its own button, at the bottom
        b.clicked.connect(lambda: self.go(("settings", None)))
        lay.addWidget(b)
        self.nav["settings"] = b
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
        lay = self.recent_box
        _clear(lay)
        for area, tool, page in _state()["recent"][:3]:
            try:
                label = "%s › %s" % (theme.area(area)[1], "Edit shape" if (tool, page) == ("controls_tab", 2) else
                                     "Make" if (tool, page) == ("controls_tab", 1) else
                                     page if isinstance(page, str) else tool_label(tool))
            except KeyError:
                continue
            b = QtWidgets.QPushButton(label.replace("&", "&&"))
            b.setProperty("role", "nav")
            b.clicked.connect(lambda _=False, t=(tool, page): self.go(t, as_tool=True))
            lay.addWidget(b)
        self._apply_slim()

    # -------------------------------------------------- going places
    def go_key(self, key, section=None):
        """Show a tool (any key, old ones too), with one of its sections open."""
        area, tool, page = area_of(key)
        self.go((tool, page), section, as_tool=True)

    def go(self, where, section=None, as_tool=False):
        """where: (area key, None) - its remembered sub-page - or (tool key, page). as_tool (5.7.5): it's a tool
        even when an area has its name ('connect': the Connections tool, not the Connect area)."""
        first, page = where
        if first in CATEGORY and page is None and not as_tool:   # an area ('skin' is also a tool: with a page
            #                                                       it's the tool)
            area = first
            sub = _state()["sub"].get(area)
            area_obj = self._area(area)
            sub = tuple(sub) if sub and any(tuple(s[:2]) == tuple(sub) for s in area_obj.subs) else \
                tuple(area_obj.subs[0][:2]) if area_obj.subs else (None, None)
        else:
            area, tool, _p = area_of(first)
            area_obj = self._area(area)
            sub = area_obj.default_sub(tool, page)
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
        self.subtitle.setText(_subtitle(sub[0]))
        self._breadcrumb()
        _star_label(self)
        _arrange_label(self)
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
        _clear(self.tabs2.layout())
        if area_obj.key in TWO_ROWS and len(area_obj.tools) > 1:
            tools = [(t, None, tool_label(t)) for t in area_obj.tools]
            self._tab_row(self.tabs.layout(), tools, (sub[0], None),
                          lambda t, p: self.go(area_obj.default_sub(t), as_tool=True), "tab")
            mine = [s for s in area_obj.subs if s[0] == sub[0]]
            self.tabs2.setVisible(len(mine) > 1)
            if len(mine) > 1:
                self._tab_row(self.tabs2.layout(), mine, sub, lambda t, p: self.go((t, p), as_tool=True), "tab2")
            return
        self.tabs2.setVisible(False)
        self._tab_row(self.tabs.layout(), area_obj.subs, sub, lambda t, p: self.go((t, p), as_tool=True), "tab")

    def _tab_row(self, lay, shown, sub, go, role):
        """One row of tabs (with More ▾ for the rest when the window is narrow)."""
        _clear(lay)
        narrow = self.width() and self.width() < 520
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
            b.setProperty("role", role)
            b.setCheckable(True)
            b.setChecked((t, p) == tuple(sub[:2]))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=t, p=p: go(t, p))
            lay.addWidget(b)
        if more:
            m = QtWidgets.QToolButton()
            m.setText("More ▾")
            m.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            menu = QtWidgets.QMenu(m)
            for t, p, label in more:
                a = menu.addAction(label)
                a.triggered.connect(lambda _=False, t=t, p=p: go(t, p))
            m.setMenu(menu)
            m.setStyleSheet("QToolButton { background: transparent; color: %s; padding: 7px 10px; }" % theme.DIM)
            lay.addWidget(m)

    # -------------------------------------------------- selection, status, size
    def selection(self):
        return selection()

    def on_selection(self, *_):
        a = self.areas.get(self.area)
        if a is not None:
            a.refresh_selection()
        self._breadcrumb()

    def _breadcrumb(self):
        """New look: the status line says what's selected and where you are (until a tool says something)."""
        if not theme.new_look() or not hasattr(self, "status"):
            return
        text = self.status.text().strip()
        if text and text != "Ready." and not text.startswith("●"):
            return
        a = self.areas.get(self.area)
        if a is None or not a.current:
            return
        try:
            kinds, names, _e = self.selection()
        except Exception:
            names = []
        sel = "nothing selected" if not names else ("%s selected" % names[0].split("|")[-1] if len(names) == 1
                                                    else "%d selected" % len(names))
        sub = [x[2] for x in a.subs if tuple(x[:2]) == tuple(a.current[:2])]
        sub = sub[0] if sub else tool_label(a.current[0])
        self.status.setText("  ●  %s   ·   %s  ›  %s" % (sel, theme.area(self.area)[1], sub))
        self.status.setStyleSheet("QLabel { background: #24272b; color: %s; padding: 4px 8px; }" % theme.DIM)

    def set_status(self, message, level="info"):
        _set_status(self, message, level)

    def pop_out(self):
        """The page shown, in its own panel (several can be open side by side) - like the old window's Pop out."""
        a = self.areas.get(self.area)
        if a is None or not a.current:
            return
        tool = a.current[0]
        if self.area in NEW_LOOK:
            return show_pop(tool, a.current[1])
        from gus_rigtool.core import ui
        ui.open_panel(tool)                   # pages not redone yet: their own panel, as before

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

    def toggle_side(self):
        s = _state()
        self.side_hidden = s["side_hidden"] = not self.side_hidden
        _save_state(s)
        self._apply_slim()

    def _apply_slim(self):
        hidden = self.side_hidden
        slim = self.width() < SLIM or hidden
        self.slim = slim
        if hasattr(self, "side_toggle"):
            self.side_toggle.setText("›" if hidden else "‹")
            self.side_toggle.setToolTip("Show the sidebar" if hidden else "Hide the sidebar (a thin strip of icons)")
            self.side_toggle.setVisible(hidden or self.width() >= SLIM)
        self.favs.set_slim(slim)
        self.side.setFixedWidth(54 if slim else 196)
        for b in list(self.nav.values()) + [self.mine]:
            b.setText("" if slim else b.property("full"))
        short = self.height() < SHORT                # a short window: Recent and Help fold away (the preview)
        for w in self.sec_labels:
            w.setVisible(not slim)
        for w in [self.recent_head, self.help_head, self.help_btn]:
            w.setVisible(not slim and not short)
        for i in range(self.recent_box.count()):
            it = self.recent_box.itemAt(i)
            if it.widget():
                it.widget().setVisible(not slim and not short)

    # -------------------------------------------------- search
    def _search_setup(self):
        from gus_rigtool import registry
        self.entries = {}
        for key, label, _m, sub in registry.TOOLS:
            area, _t, _p = area_of(key)
            self.entries["%s  —  %s" % (label, theme.area(area)[1])] = (key, None)
        for stage in registry.STAGES:
            self.entries["%s  —  %s" % (stage[4], stage[1])] = (stage[3], stage[4])
        for area, extra in EXTRA_TOOLS.items():           # 5.7.6: Publish
            for key in extra:
                self.entries["%s  —  %s" % (registry.get(key)[1], theme.area(area)[1])] = (key, None)
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
    if mc.workspaceControl(WS, exists=True) and alive(_frame.get("w")):
        try:
            mc.workspaceControl(WS, edit=True, restore=True, label="Gus_Rigtool %s" % gus_rigtool.__version__)
        except RuntimeError:
            pass
    else:
        if mc.workspaceControl(WS, exists=True):
            mc.deleteUI(WS)
        _frame["w"] = None
        mc.workspaceControl(WS, label="Gus_Rigtool %s" % gus_rigtool.__version__, retain=False, floating=True,
                            initialWidth=640, initialHeight=820, minimumWidth=260, widthProperty="preferred",
                            uiScript="import gus_rigtool.newui.window as _w; _w.restore()")
        if not alive(_frame.get("w")):        # 5.7.1: Maya fills it itself (the uiScript) - only when it didn't
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
    have = [f for f in host.findChildren(Frame) if alive(f)]
    if have:                                   # 5.7.1: already filled (it opened twice in 5.7.0)
        for extra in have[1:]:
            extra.setParent(None)
            extra.deleteLater()
        _frame["w"] = have[0]
        return have[0]
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
    try:                                       # the favourites bar, if you left it open
        from gus_rigtool.core import utils
        from gus_rigtool.newui import favourites
        if (utils.load_setting(favourites.BAR_KEY, {}) or {}).get("open"):
            favourites.show_bar()
    except Exception:
        pass
    return frame


def close():
    import maya.cmds as mc
    if mc.workspaceControl(WS, exists=True):
        mc.deleteUI(WS)
    _frame["w"] = None


# --------------------------------------------------------------------------- Pop out (5.7.1)
class PopFrame(QtWidgets.QWidget):
    """One page in its own panel - several can be open side by side (the old window's Pop out)."""

    def __init__(self, tool, page=None, parent=None):
        super(PopFrame, self).__init__(parent)
        from gus_rigtool import registry
        self.setObjectName("gusFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        area_key, tool, _p = area_of(tool)
        self.tool, self.area = tool, area_key
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.head = QtWidgets.QFrame()
        self.head.setObjectName("gusHead")
        hv = QtWidgets.QVBoxLayout(self.head)
        hv.setContentsMargins(12, 8, 12, 0)
        title = QtWidgets.QLabel(registry.get(tool)[1])
        title.setObjectName("gusTitle")
        hv.addWidget(title)
        hv.addWidget(widgets.label(_subtitle(tool), "dim"))
        self.tabs = widgets.flow_box(2)
        self.tabs.layout().setContentsMargins(0, 6, 0, 0)
        hv.addWidget(self.tabs)
        v.addWidget(self.head)
        self.body = Area(self, area_key, only=[tool], prefix="q7p_")
        v.addWidget(self.body, 1)
        v.addWidget(_status_bar(self))
        self.setStyleSheet(theme.stylesheet(self.body.accent))
        from gus_rigtool.core import ui
        ui.STATUS_HOOKS.append(self.set_status)
        self.go((tool, page or (1 if tool == "controls_tab" else None)))

    def go(self, where, section=None):
        tool, page = where
        if tool != self.tool:                    # another tool: the main window
            w = _frame.get("w")
            if alive(w):
                w.go(where, section)
            return
        sub = self.body.default_sub(tool, page)
        self.body.show_sub(sub)
        _clear(self.tabs.layout())
        if len(self.body.subs) > 1:
            for t, p, label in self.body.subs:
                b = QtWidgets.QPushButton(label.replace("&", "&&"))
                b.setProperty("role", "tab")
                b.setCheckable(True)
                b.setChecked((t, p) == tuple(sub))
                b.clicked.connect(lambda _=False, t=t, p=p: self.go((t, p)))
                self.tabs.layout().addWidget(b)

    def selection(self):
        return selection()

    def on_selection(self, *_):
        self.body.refresh_selection()

    def set_status(self, message, level="info"):
        _set_status(self, message, level)


def pop_name(tool):
    return "gusRigtool57Pop_" + tool


def show_pop(tool, page=None):
    """A tool's page in its own panel (the new look). Several can be open."""
    import maya.cmds as mc
    from gus_rigtool import registry
    name = pop_name(tool)
    if mc.workspaceControl(name, exists=True):
        mc.deleteUI(name)
    _pops.pop(tool, None)
    mc.workspaceControl(name, label="%s - Gus_Rigtool" % registry.get(tool)[1], retain=False, floating=True,
                        initialWidth=460, initialHeight=760, minimumWidth=260,
                        uiScript="import gus_rigtool.newui.window as _w; _w.restore_pop(%r, %r)" % (tool, page))
    if not alive(_pops.get(tool)):
        restore_pop(tool, page)
    return _pops.get(tool)


_pops = {}


def restore_pop(tool, page=None):
    import maya.cmds as mc
    from gus_rigtool.newui.qt import maya_widget
    host = maya_widget(pop_name(tool), "control")
    if host is None:
        return None
    have = [f for f in host.findChildren(PopFrame) if alive(f)]
    if have:
        _pops[tool] = have[0]
        return have[0]
    pop = PopFrame(tool, page)
    if host.layout() is None:
        QtWidgets.QVBoxLayout(host)
    host.layout().setContentsMargins(0, 0, 0, 0)
    host.layout().addWidget(pop)
    _pops[tool] = pop
    try:
        mc.scriptJob(event=["SelectionChanged", pop.on_selection], parent=pop_name(tool))
    except RuntimeError:
        pass
    pop.on_selection()
    return pop
