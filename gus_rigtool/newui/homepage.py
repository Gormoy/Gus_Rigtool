"""
5.7.9: Home in the new window - where you are in the rig and what to do next. The same logic as the legacy look's
Home (tools/home.py: state, advice, suggest); drawn as the new window's sections, so Arrange works here too.

  Next step        what to do now, and its button
  1 Guides ... 5 Check & publish   each with its state (Done / Next / To do / Any time) and Go
  For what's selected   the things you'd likely do with it
  Any time         Toolbox, the Guide, the Map
"""

from gus_rigtool.newui import theme, widgets
from gus_rigtool.newui.qt import QtCore, QtWidgets

Qt = QtCore.Qt
STAGE_AREA = {"guides": "build", "build": "build", "skin": "skin", "controls": "controls", "finish": "check"}
TAG = {"done": ("#2f5a35", "#c8efcd", "✓ Done"), "next": ("#5c5418", "#f3e3a0", "● Next"),
       "todo": ("#3f444c", "#c9cdd2", "To do"), "any": ("#2c4256", "#bcd6ef", "Any time")}


def _go(tool, section=None):
    from gus_rigtool.core import ui
    try:
        ui.go_to_tool(tool, section)
    except Exception as e:
        ui.report_error(e, "home_go")


class HomePage(QtWidgets.QWidget):
    def __init__(self, area=None, parent=None):
        super(HomePage, self).__init__(parent)
        from gus_rigtool import registry
        self.area = area
        self.cards = []
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        # next step
        self.next_card = widgets.Card("Next step", None, "What to do now in this scene - it changes as you go.")
        self.next_card.no_pin = True
        self.advice = widgets.label("", wrap=True)
        self.advice.setObjectName("gusHomeAdvice")
        self.next_card.add(self.advice)
        self.next_button = widgets.big_button("")
        self.next_button.clicked.connect(lambda _=False: self._go_next())
        self.next_card.add(self.next_button)
        v.addWidget(self.next_card)
        self.cards.append(self.next_card)
        # the five steps
        self.steps = {}
        for i, (key, title, desc, tool, sec) in enumerate(registry.STAGES):
            card = widgets.Card(title, i + 1, desc)
            card.set_desc(desc)
            accent = theme.colour(STAGE_AREA.get(key, "home"))
            card.setStyleSheet("QFrame#gusCard { border-left: 3px solid %s; }" % accent)
            go = QtWidgets.QPushButton("Go  ›")
            go.setCursor(Qt.PointingHandCursor)
            go.setToolTip("Open %s" % registry.get(tool)[1])
            go.clicked.connect(lambda _=False, t=tool, s=sec: _go(t, s))
            card.add(go)
            card.go = go
            v.addWidget(card)
            self.cards.append(card)
            self.steps[key] = card
        # for what's selected
        self.sel_card = widgets.Card("For what's selected", None, "What you'd likely do with the selection.")
        self.sel_card.no_pin = True
        self.sel_what = widgets.label("", "dim")
        self.sel_card.add(self.sel_what)
        self.sel_box = widgets.flow_box(6)
        self.sel_card.add(self.sel_box)
        v.addWidget(self.sel_card)
        self.cards.append(self.sel_card)
        # any time
        anyt = widgets.Card("Any time", None, "Small tools for any step, the guide and where everything is.")
        anyt.no_pin = True
        row = widgets.flow_box(6)
        for text, tip, fn in (("Toolbox  ›", "Select, Groups, Mirror, Rename, Pivots", lambda: _go("select")),
                              ("The Guide", "Rigging with Gus_Rigtool, step by step", _guide),
                              ("Map", "Where everything is: every area and page", _map),
                              ("Refresh", "Look at the scene again", self.refresh)):
            b = QtWidgets.QPushButton(text)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("stretch", True)
            b.clicked.connect(lambda _=False, fn=fn: fn())
            row.layout().addWidget(b)
        anyt.add(row)
        v.addWidget(anyt)
        self.cards.append(anyt)
        v.addStretch(1)
        self._next = None
        self.refresh()

    # ---- the scene
    def refresh(self):
        from gus_rigtool import registry
        from gus_rigtool.tools import home
        try:
            st, nxt = home.state()
        except Exception:
            st, nxt = {}, None
        self._next = nxt
        self.advice.setText(home.advice(nxt))
        stages = dict((k, (t, tool, sec)) for k, t, _d, tool, sec in registry.STAGES)
        if nxt in stages:
            title, tool, sec = stages[nxt]
            self.next_button.setText("%s  ›" % title)
            self.next_button.setStyleSheet("QPushButton { background: %s; color: #111; }" %
                                           theme.colour(STAGE_AREA.get(nxt, "home")))
            self.next_button.show()
        else:
            self.next_button.hide()
        for key, card in self.steps.items():
            s = st.get(key, "todo")
            bg, fg, word = TAG[s]
            card.chip.setText(word)
            card.chip.setStyleSheet("QLabel#gusChip { background: %s; color: %s; }" % (bg, fg))
            card.chip.show()
            card.go.setText("Start  ›" if s == "next" else "Go  ›")
            card.go.setProperty("role", "accent" if s == "next" else "")
            widgets.restyle(card.go)
        self.refresh_selection()

    def refresh_selection(self):
        from gus_rigtool import registry
        from gus_rigtool.tools import home
        from gus_rigtool.newui.window import _clear
        try:
            what, items = home.suggest()
        except Exception:
            what, items = "Nothing selected", []
        self.sel_what.setText("Selected: %s" % what)
        _clear(self.sel_box.layout())
        for label, tool, sec in items:
            b = QtWidgets.QPushButton("%s  ›" % label)
            b.setCursor(Qt.PointingHandCursor)
            try:
                b.setToolTip("Open %s" % registry.get(tool)[1])
            except KeyError:
                pass
            b.setProperty("stretch", True)
            b.clicked.connect(lambda _=False, t=tool, s=sec: _go(t, s))
            self.sel_box.layout().addWidget(b)

    def _go_next(self):
        from gus_rigtool import registry
        for k, _t, _d, tool, sec in registry.STAGES:
            if k == self._next:
                _go(tool, sec)
                return


def _guide():
    try:
        __import__("gus_rigtool.tools.guide", fromlist=["x"]).show()
    except Exception:
        pass


def _map():
    try:
        from gus_rigtool.core import ui
        ui.show_map()
    except Exception:
        pass
