# 5.7.7 preview: two looks for a tool's page, drawn from the tool's REAL page (its own build(), recorded):
#   1 "Classic, clearer"   - close to the old window (Maya section bars, a label column, round radio buttons)
#   2 "New, easier to read" - the cards, but each section says what it does, labels line up, clear choices
# Run from gus_rigtool/tests:  python3 ../../design/mockups/toolbox_styles.py
import os
import re
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GUS_REAL_QT"] = "1"
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
for name in ("scriptJob", "headsUpDisplay", "iconTextCheckBox", "nodeIconButton", "canvas", "image", "palettePort",
             "checkBoxGrp", "textFieldButtonGrp", "radioCollection", "radioButton", "intSlider", "floatSlider",
             "playbackOptions", "workspace", "channelBox", "shelfLayout", "colorIndexSliderGrp",
             "attrColorSliderGrp", "swatchDisplayPort", "iconTextRadioButton", "iconTextRadioCollection"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
from gus_rigtool.newui.qt import QtCore, QtGui, QtWidgets
QtCore.qInstallMessageHandler(lambda *a: None)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from gus_rigtool import registry
from gus_rigtool.newui import record
Qt = QtCore.Qt

real_q = record.Recorder._query                       # (the 5.7.7 fix, stood in here: 3-number boxes)


def _q(self, n, k):
    if n.kind in ("floatFieldGrp", "intFieldGrp") and (k.get("value") or k.get("v")):
        return [n.kw.get("value%d" % i, 0.0) for i in range(1, int(n.kw.get("numberOfFields") or 1) + 1)]
    return real_q(self, n, k)


record.Recorder._query = _q
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screens577")

STYLES = {
    "classic": """
QWidget { background: transparent; color: #eeeeee; font-size: 13px; }
QWidget#page { background: #3d3d3d; }
QLabel { background: transparent; }
QLabel[role="lab"] { color: #d6d6d6; }
QLabel[role="dim"] { color: #a8a8a8; font-size: 12px; }
QFrame#bar { background: #5a5a5a; border-radius: 3px; }
QLabel#barTitle { font-weight: bold; font-size: 13px; color: #ffffff; }
QPushButton { background: #5d5d5d; border: 1px solid #6e6e6e; border-radius: 3px; padding: 5px 10px; }
QPushButton:checked { background: #5285a6; }
QPushButton[role="main"] { background: #4a7fa3; border: 1px solid #6aa0c4; font-weight: bold; padding: 8px; }
QPushButton[role="danger"] { background: #7a3b3b; border: 1px solid #9a5050; }
QPushButton[role="help"] { background: #4b4b4b; border-radius: 9px; padding: 0px; min-width: 18px; max-width: 18px;
                           min-height: 18px; max-height: 18px; font-size: 11px; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #2b2b2b; border: 1px solid #555; border-radius: 2px;
                           padding: 3px 5px; }
QRadioButton, QCheckBox { spacing: 6px; }
QRadioButton::indicator { width: 12px; height: 12px; border-radius: 7px; border: 1.5px solid #9a9a9a;
                          background: #2b2b2b; }
QRadioButton::indicator:checked { background: #8ab4d8; border: 1.5px solid #cfe3f3; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1.5px solid #9a9a9a; background: #2b2b2b; border-radius: 2px; }
QCheckBox::indicator:checked { background: #8ab4d8; border: 1.5px solid #cfe3f3; }
QLabel#light { border-radius: 3px; padding: 6px 8px; }
""",
    "new": """
QWidget { background: transparent; color: #f0f2f4; font-size: 13px; }
QWidget#page { background: #2f3237; }
QLabel { background: transparent; }
QLabel[role="lab"] { color: #c9cdd2; }
QLabel[role="dim"] { color: #a5abb3; font-size: 12px; }
QFrame#card { background: #3a3e45; border-radius: 9px; border: 1px solid #4a4f57; }
QLabel#cardTitle { font-weight: bold; font-size: 15px; }
QLabel#num { background: #6f93bd; color: #111; border-radius: 10px; font-weight: bold; font-size: 11px; }
QPushButton { background: transparent; border: 1px solid #5f656e; border-radius: 6px; padding: 5px 10px; }
QPushButton:hover { background: #474c54; }
QPushButton[role="main"] { background: #6f93bd; color: #111; border: none; font-weight: bold; font-size: 14px;
                           padding: 9px; }
QPushButton[role="danger"] { border: 1px solid #b4544f; color: #f0b0ad; }
QPushButton[role="pill"] { border-radius: 13px; padding: 4px 12px 4px 10px; }
QPushButton[role="pill"]:checked { background: #44597a; border: 1px solid #8fb3df; font-weight: bold; }
QPushButton[role="help"] { border-radius: 9px; padding: 0px; min-width: 18px; max-width: 18px; min-height: 18px;
                           max-height: 18px; font-size: 11px; color: #a5abb3; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #23262a; border: 1px solid #555b63;
                           border-radius: 5px; padding: 4px 6px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid #8a9098; background: #23262a; }
QCheckBox::indicator:checked { background: #6f93bd; border: 1.5px solid #8fb3df; }
QLabel#light { border-radius: 6px; padding: 7px 9px; }
""",
}
# the mixes (Gus: "1 is easier to read, but the design of 2 is good - give me more options combining the two")
_V1_CONTROLS = """
QPushButton { background: #5b5f66; border: 1px solid #6c7178; border-radius: 4px; padding: 5px 10px; }
QPushButton[role="main"] { background: #4f86b8; border: 1px solid #77a8d4; color: white; font-weight: bold;
                           font-size: 14px; padding: 8px; border-radius: 6px; }
QPushButton[role="danger"] { background: #7a3b3b; border: 1px solid #9a5050; }
QPushButton[role="help"] { background: transparent; border: 1px solid #6c7178; border-radius: 9px; padding: 0px;
                           min-width: 18px; max-width: 18px; min-height: 18px; max-height: 18px; font-size: 11px; }
QRadioButton, QCheckBox { spacing: 6px; }
QRadioButton::indicator { width: 12px; height: 12px; border-radius: 7px; border: 1.5px solid #a0a5ad;
                          background: #26292d; }
QRadioButton::indicator:checked { background: #8ab4d8; border: 1.5px solid #d6e7f5; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1.5px solid #a0a5ad; background: #26292d; border-radius: 3px; }
QCheckBox::indicator:checked { background: #8ab4d8; border: 1.5px solid #d6e7f5; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #26292d; border: 1px solid #5a5f67;
                           border-radius: 4px; padding: 4px 6px; }
QLabel#light { border-radius: 5px; padding: 7px 9px; }
"""
STYLES["mixA"] = """
QWidget { background: transparent; color: #f0f2f4; font-size: 13px; }
QWidget#page { background: #2f3237; }
QLabel[role="lab"] { color: #d4d8dd; }
QLabel[role="dim"] { color: #aab0b8; font-size: 12px; }
QFrame#card { background: #3a3e45; border-radius: 9px; border: 1px solid #4a4f57; }
QLabel#cardTitle { font-weight: bold; font-size: 15px; }
QLabel#num { background: #6f93bd; color: #111; border-radius: 10px; font-weight: bold; font-size: 11px; }
""" + _V1_CONTROLS
STYLES["mixB"] = """
QWidget { background: transparent; color: #eeeff1; font-size: 13px; }
QWidget#page { background: #393c41; }
QLabel[role="lab"] { color: #d4d8dd; }
QLabel[role="dim"] { color: #aab0b8; font-size: 12px; }
QFrame#bar { background: #4b5058; border-radius: 4px; border-left: 4px solid #6f93bd; }
QLabel#barTitle { font-weight: bold; font-size: 14px; color: #ffffff; }
QLabel#num { background: #6f93bd; color: #111; border-radius: 9px; font-weight: bold; font-size: 11px; }
""" + _V1_CONTROLS
STYLES["mixC"] = """
QWidget { background: transparent; color: #eef0f2; font-size: 13px; }
QWidget#page { background: #33363b; }
QLabel[role="lab"] { color: #d4d8dd; }
QLabel[role="dim"] { color: #aab0b8; font-size: 12px; }
QLabel#flatTitle { font-weight: bold; font-size: 16px; color: #ffffff; }
QLabel#num { background: transparent; color: #8fb3df; font-weight: bold; font-size: 16px; }
QFrame#rule { background: #4a4f57; }
""" + _V1_CONTROLS
# C2 (2026-11-21, after design/UI_PRINCIPLES.md): Mix C + the new window's colours + less at first look
STYLES["c2"] = """
QWidget { background: transparent; color: #e9ebee; font-size: 13px; }
QWidget#page { background: #33373d; }
QLabel[role="lab"] { color: #c9cdd2; }
QLabel[role="dim"] { color: #a2a7ae; font-size: 12px; }
QLabel#flatTitle { font-weight: bold; font-size: 16px; color: #ffffff; }
QLabel#num { background: ACCENT; color: #111; border-radius: 10px; font-weight: bold; font-size: 11px;
             min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px; }
QFrame#rule { background: #464b53; }
QPushButton { background: #474c54; border: 1px solid #575d66; border-radius: 6px; padding: 5px 10px; }
QPushButton:hover { background: #535962; }
QPushButton[role="main"] { background: ACCENT; color: #111; border: none; font-weight: bold; font-size: 14px;
                           padding: 9px; border-radius: 7px; }
QPushButton[role="danger"] { background: #5a2f2d; border: 1px solid #b4544f; }
QPushButton[role="fold"] { background: transparent; border: none; text-align: left; padding: 3px 0px;
                           color: #a2a7ae; }
QRadioButton, QCheckBox { spacing: 7px; }
QRadioButton::indicator { width: 12px; height: 12px; border-radius: 7px; border: 1.5px solid #8a9098;
                          background: #202326; }
QRadioButton::indicator:checked { background: ACCENT; border: 1.5px solid #e9ebee; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid #8a9098; background: #202326; }
QCheckBox::indicator:checked { background: ACCENT; border: 1.5px solid ACCENT; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #202326; border: 1px solid #4a4f57;
                           border-radius: 5px; padding: 4px 6px; }
QLabel#light { border-radius: 6px; padding: 7px 9px; }
"""
# C3 (Gus: "keep more of this idea, but some tools aren't centred / pushed to the right; push it more to the new
# style"): the new version's cards and joined choice buttons, one left edge for every control
_C3 = """
QWidget { background: transparent; color: #e9ebee; font-size: 13px; }
QWidget#page { background: #2b2e33; }
QLabel[role="lab"] { color: #a2a7ae; font-size: 12px; }
QLabel[role="dim"] { color: #a2a7ae; font-size: 12px; }
QFrame#card { background: #3a3e45; border-radius: 10px; border: none; }
QLabel#cardTitle { font-weight: bold; font-size: 15px; }
QLabel#num { background: ACCENT; color: #111; border-radius: 10px; font-weight: bold; font-size: 11px; }
QPushButton { background: #4a4f57; border: none; border-radius: 6px; padding: 6px 10px; }
QPushButton:hover { background: #575d66; }
QPushButton[role="main"] { background: ACCENT; color: #111; font-weight: bold; font-size: 14px; padding: 9px;
                           border-radius: 8px; }
QPushButton[role="danger"] { background: #5a2f2d; color: #f3c4c1; }
QPushButton[role="seg"] { background: #2b2e33; border: 1px solid #4a4f57; border-radius: 0px; padding: 5px 8px; }
QPushButton[role="seg"][first="true"] { border-top-left-radius: 6px; border-bottom-left-radius: 6px; }
QPushButton[role="seg"][last="true"] { border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
QPushButton[role="seg"]:checked { background: ACCENT; color: #111; font-weight: bold; border: 1px solid ACCENT; }
QPushButton[role="fold"] { background: transparent; border: 1px solid #575d66; border-radius: 12px;
                           padding: 3px 12px; color: #c9cdd2; text-align: left; }
QPushButton[role="chip"] { background: #2b2e33; border: 1px solid #4a4f57; border-radius: 12px; padding: 4px 10px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid #8a9098; background: #202326; }
QCheckBox::indicator:checked { background: ACCENT; border: 1.5px solid ACCENT; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #202326; border: 1px solid #4a4f57;
                           border-radius: 6px; padding: 5px 7px; }
QLabel#light { border-radius: 8px; padding: 8px 10px; }
"""
# C4 (2026-11-21): C3b's layout in Gus's Gemini style (design/references: the 5.8 HTML workspace + style guide)
STYLES["c4"] = """
QWidget { background: transparent; color: #f1f5f9; font-size: 13px; }
QWidget#page { background: #16191e; }
QLabel[role="lab"] { color: #9aa5b5; font-size: 12px; }
QLabel[role="dim"] { color: #9aa5b5; font-size: 12px; }
QFrame#card { background: #242933; border: 1px solid #454f60; border-left: 3px solid ACCENT; border-radius: 6px; }
QFrame#drawerHead { background: rgba(ACCENT_RGB, 0.12); border: none; border-bottom: 1px solid #333a47;
                    border-top-right-radius: 5px; }
QLabel#cardTitle { font-weight: bold; font-size: 12px; color: ACCENT; letter-spacing: 0.5px; }
QLabel#num { color: ACCENT; font-weight: bold; font-size: 12px; }
QPushButton { background: #343c4a; border: 1px solid #454f60; border-radius: 4px; padding: 5px 9px; }
QPushButton:hover { background: #404a5b; }
QPushButton[role="main"] { background: #343c4a; border: 1px solid ACCENT; border-bottom: 3px solid ACCENT;
                           font-weight: bold; font-size: 13px; padding: 8px; }
QPushButton[role="danger"] { background: #343c4a; border: 1px solid #a8504c; color: #f3b5b1; }
QPushButton[role="seg"] { background: #16191e; border: 1px solid #454f60; border-radius: 0px; padding: 5px 8px; }
QPushButton[role="seg"][first="true"] { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }
QPushButton[role="seg"][last="true"] { border-top-right-radius: 4px; border-bottom-right-radius: 4px; }
QPushButton[role="seg"]:checked { background: ACCENT; color: #111; font-weight: bold; border: 1px solid ACCENT; }
QPushButton[role="fold"] { background: #16191e; border: 1px solid #333a47; border-radius: 4px; padding: 4px 10px;
                           color: #9aa5b5; text-align: left; }
QPushButton[role="chip"] { background: #343c4a; border: 1px solid #454f60; border-radius: 4px; padding: 4px 9px;
                           border-bottom: 2px solid ACCENT; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 3px; border: 1px solid #454f60; background: #16191e; }
QCheckBox::indicator:checked { background: ACCENT; border: 1px solid ACCENT; }
QLineEdit, QComboBox, QListWidget, QPlainTextEdit { background: #16191e; border: 1px solid #454f60;
                           border-radius: 4px; padding: 5px 7px; }
QLabel#light { border-radius: 4px; padding: 7px 9px; border: 1px solid #454f60; }
"""
STYLES["c3a"] = _C3
STYLES["c3b"] = _C3
OPT = {"c4": dict(section="drawer", desc=True, choice="seg", quick=True, light="#2b2a20", badge=True, fold=True,
                  closed_desc=False, label="left", fold_lights=True),
       "c3a": dict(section="card", desc=True, choice="seg", quick=True, light="#4b4321", badge=True, fold=True,
                   closed_desc=False, label="top"),
       "c3b": dict(section="card", desc=True, choice="seg", quick=True, light="#4b4321", badge=True, fold=True,
                   closed_desc=False, label="left"),
       "c2": dict(section="flat", desc=True, choice="radio", quick=True, light="#4f4420", badge=True, fold=True,
                  closed_desc=False),
       "classic": dict(section="bar", desc=False, choice="radio", quick=False, light="#5a4a22", badge=False),
       "new": dict(section="card", desc=True, choice="pill", quick=True, light="#4f4420", badge=True),
       "mixA": dict(section="card", desc=True, choice="radio", quick=True, light="#57491f", badge=True),
       "mixB": dict(section="bar", desc=True, choice="radio", quick=True, light="#57491f", badge=True),
       "mixC": dict(section="flat", desc=True, choice="radio", quick=True, light="#57491f", badge=True)}
NAMES = {"mixA": "Mix A - cards, classic controls", "mixB": "Mix B - section bars, new touches",
         "mixC": "Mix C - clean list, no boxes"}
LIGHT = dict((k, v["light"]) for k, v in OPT.items())
OPTION_KINDS = ("radioButtonGrp", "checkBox", "checkBoxGrp")
LABEL_W = 96


def first_sentence(text):
    text = str(text or "").strip()
    m = re.match(r"(.+?(?<!e\.g)\.)(\s+[A-Z(]|$)", text)
    text = m.group(1) if m else text
    if len(text) > 120:
        text = text[:117].rsplit(" ", 1)[0] + "..."
    return text


class Page(object):
    def __init__(self, style, only=None):
        self.style = style
        self.opt = OPT[style]
        self.n = 0
        self.only = only                                   # a sub-page: only these sections

    def build(self, root, title, subtitle, head=True):
        w = QtWidgets.QWidget()
        w.setObjectName("page")
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(9)
        if head:
            v.addWidget(QtWidgets.QLabel("<b style='font-size:18px'>%s</b><br><span style='color:#a8a8a8'>%s</span>"
                                         % (title, subtitle)))
        for c in root.children:
            got = self.node(c)
            if got is not None:
                v.addWidget(got)
        v.addStretch(1)
        return w

    # ------------------------------------------------------------------ one control
    def node(self, n):
        if n.kw.get("manage") is False or n.kw.get("visible") is False:      # hidden for now (another mode's)
            return None
        fn = getattr(self, "_" + n.kind, None)
        return fn(n) if fn else None

    def kids(self, n, lay):
        for c in n.children:
            if self._is_help_row(c):
                continue
            got = self.node(c)
            if got is not None:
                lay.addWidget(got)

    def _is_help_row(self, n):
        return n.kind == "rowLayout" and len(n.children) == 2 and n.children[1].kind == "button" and \
            n.children[1].label() == "?"

    def _box(self, n):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.kids(n, v)
        return w

    _columnLayout = _formLayout = _scrollLayout = _box

    def labelled(self, text, widget):
        pos = self.opt.get("label")
        if pos in ("top", "left") and text:
            w = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(w) if pos == "top" else QtWidgets.QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(3 if pos == "top" else 10)
            lab = QtWidgets.QLabel(text)
            lab.setProperty("role", "lab")
            if pos == "left":
                lab.setFixedWidth(84)
                lab.setWordWrap(True)
                lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lay.addWidget(lab)
            lay.addWidget(widget, 1)
            return w
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lab = QtWidgets.QLabel(text)
        lab.setProperty("role", "lab")
        lab.setFixedWidth(LABEL_W + 14)
        lab.setWordWrap(True)
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lab)
        h.addWidget(widget, 1)
        return w

    def _rowLayout(self, n):
        kids = [c for c in n.children]
        if self.opt.get("fold") and kids and kids[0].kind == "optionMenu" and any(
                str(i.get("label")) == "(presets)" for i in kids[0].items):
            row = QtWidgets.QWidget()                      # C2: presets folded into one small button
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addStretch(1)
            b = QtWidgets.QPushButton("Presets  ▾")
            b.setToolTip("Save / Load / Delete your settings for this tool")
            h.addWidget(b)
            return row
        if kids and kids[0].kind == "text" and str(kids[0].label()).strip() and len(kids) > 1:
            rest = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(rest)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            for c in kids[1:]:
                got = self.node(c)
                if got is not None:
                    h.addWidget(got, 1 if isinstance(got, (QtWidgets.QLineEdit, QtWidgets.QComboBox)) else 0)
            return self.labelled(str(kids[0].label()), rest)
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        for c in kids:
            got = self.node(c)
            if got is not None:
                h.addWidget(got, 1)
        return w

    def _gridLayout(self, n):
        if self.opt.get("choice") == "seg" and n.kind == "gridLayout" and all(c.kind == "button" for c in n.children):
            w = QtWidgets.QWidget()                       # C3: quick buttons as small chips that wrap
            from gus_rigtool.newui import widgets as WG
            lay = WG.FlowLayout(w, 6)
            for c in n.children:
                b = QtWidgets.QPushButton(str(c.label()).replace("&", "&&"))
                b.setProperty("role", "danger" if str(c.label()) == "Clear" else "chip")
                lay.addWidget(b)
            keep = self.opt.get("label")
            self.opt = dict(self.opt, label="top")        # a wrapping row: its name above it, in both C3s
            try:
                return self.labelled("Quick", w)
            finally:
                self.opt = dict(self.opt, label=keep)
        w = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(5)
        cols = int(n.kw.get("numberOfColumns") or n.kw.get("nc") or 3)
        for i, c in enumerate(n.children):
            got = self.node(c)
            if got is not None:
                g.addWidget(got, i // cols, i % cols)
        if self.opt["quick"] and n.kind == "gridLayout" and all(c.kind == "button" for c in n.children):
            return self.labelled("Quick", w)
        return w

    def _rowColumnLayout(self, n):
        kids = list(n.children)
        cols = int(n.kw.get("numberOfColumns") or n.kw.get("nc") or 2)
        if cols == 2 and kids and all(k.kind == "text" for k in kids[0::2]):     # label / value pairs
            w = QtWidgets.QWidget()
            v = QtWidgets.QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(6)
            for lab, ctl in zip(kids[0::2], kids[1::2]):
                got = self.node(ctl)
                if got is not None:
                    v.addWidget(self.labelled(str(lab.label()), got))
            return w
        return self._gridLayout(n)

    def _frameLayout(self, n):
        title = re.sub(r"^\s*\d+\.\s+", "", str(n.label())).replace("(advanced)", "").strip()
        if self.only is not None and n.parent is not None and n.parent.kind not in ("frameLayout",) and \
                not self._inside_frame(n) and title not in self.only:
            return None
        closed = bool(n.kw.get("collapse") or n.kw.get("cl"))
        help_text = str(n.kw.get("annotation") or "")
        inner = n.parent is not None and n.parent.kind != "columnLayout" or (
            n.parent is not None and n.parent.parent is not None and n.parent.parent.kind == "frameLayout")
        if self.opt["section"] == "bar" or (self.opt["section"] == "flat" and inner):
            return self._bar(n, title, closed, help_text, inner)
        if self.opt["section"] == "flat":
            return self._flat(n, title, closed, help_text)
        if self.opt["section"] == "drawer" and not inner:
            return self._drawer(n, title, closed, help_text)
        return self._card(n, title, closed, help_text, inner)

    def _drawer(self, n, title, closed, help_text):
        """Gus's 5.8 drawers: a 3 px rail in the area's colour, a header tinted 12%, the number + the name."""
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        outer = QtWidgets.QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head = QtWidgets.QFrame()
        head.setObjectName("drawerHead")
        h = QtWidgets.QHBoxLayout(head)
        h.setContentsMargins(10, 6, 10, 6)
        self.n += 1
        num = QtWidgets.QLabel("%d" % self.n)
        num.setObjectName("num")
        h.addWidget(num)
        t = QtWidgets.QLabel(title.upper())
        t.setObjectName("cardTitle")
        h.addWidget(t, 1)
        arrow = QtWidgets.QLabel("▸" if closed else "▾")
        arrow.setStyleSheet("color: ACCENT_TEXT;")
        h.addWidget(arrow)
        outer.addWidget(head)
        if closed:
            return card
        body = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(body)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(7)
        has_light = any(c.kw.get("_light") for c in self._walk(n))
        if not has_light:
            self._desc(help_text, v)
        self._folded(n, v)
        outer.addWidget(body)
        return card

    def _walk(self, n):
        for c in n.children:
            yield c
            for g in self._walk(c):
                yield g

    def _inside_frame(self, n):
        p = n.parent
        while p is not None:
            if p.kind == "frameLayout":
                return True
            p = p.parent
        return False

    def _desc(self, help_text, lay, indent=0):
        if help_text and self.opt["desc"]:                 # what this section does, in one line
            d = QtWidgets.QLabel(first_sentence(help_text))
            d.setProperty("role", "dim")
            d.setWordWrap(True)
            d.setContentsMargins(indent, 0, 0, 0)
            lay.addWidget(d)

    def _flat(self, n, title, closed, help_text):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 6)
        v.setSpacing(7)
        rule = QtWidgets.QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        v.addWidget(rule)
        h = QtWidgets.QHBoxLayout()
        self.n += 1
        num = QtWidgets.QLabel("%d" % self.n)
        num.setObjectName("num")
        num.setAlignment(Qt.AlignCenter)
        h.addWidget(num)
        t = QtWidgets.QLabel(title)
        t.setObjectName("flatTitle")
        h.addWidget(t, 1)
        arrow = QtWidgets.QLabel("▸" if closed else "▾")
        arrow.setProperty("role", "dim")
        h.addWidget(arrow)
        v.addLayout(h)
        has_light = self.opt.get("fold") and any(c.kw.get("_light") for c in self._walk(n))
        if (not closed or self.opt.get("closed_desc", True)) and not has_light:
            self._desc(help_text, v)            # (C2: a step whose light says what to select needs no second line)
        if not closed:
            if self.opt.get("fold"):
                self._folded(n, v)
            else:
                self.kids(n, v)
        return w

    # ------------------------------------------------------------------ less at first look (C2)
    def _items(self, n):
        out = []
        for c in n.children:
            if self._is_help_row(c):
                continue
            if c.kind == "columnLayout" and c.parent is n:
                out += self._items(c)
            else:
                out.append(c)
        return out

    def _is_option(self, c):
        if c.kind in OPTION_KINDS or c.kind == "frameLayout":
            return True
        if c.kind == "rowLayout":
            kinds = set(k.kind for k in c.children)
            return bool(kinds) and kinds <= set(OPTION_KINDS + ("text", "optionMenu")) and "optionMenu" not in kinds \
                and kinds != {"text"}
        return False

    def _summary(self, c):
        if c.kind == "radioButtonGrp":
            labels = [l for k in ("labelArray2", "labelArray3", "labelArray4") for l in (c.kw.get(k) or [])]
            sel = int(c.kw.get("select") or 1)
            return labels[sel - 1] if 0 < sel <= len(labels) else ""
        if c.kind == "checkBox" and (c.kw.get("value") or c.kw.get("v")):
            return " ".join(str(c.label()).split()[:3])
        return ""

    def _folded(self, n, v):
        opts = []
        for c in self._items(n):
            if c.kw.get("manage") is False:
                continue
            if self._is_option(c):
                opts.append(c)
                continue
            got = self.node(c)
            if got is not None:
                v.addWidget(got)
        if opts:
            words = [x for x in (self._summary(c) for c in opts) if x]
            text = ("Options  ▸     " + "  ·  ".join(words)) if self.style == "c2" else \
                ("Options (%d)  ▾      %s" % (len(opts), "  ·  ".join(words)))
            b = QtWidgets.QPushButton(text.replace("&", "&&"))
            b.setProperty("role", "fold")
            b.setToolTip("Click to show the %d option(s)" % len(opts))
            # the main button stays last: put the fold just before it
            lay_items = [v.itemAt(i).widget() for i in range(v.count()) if v.itemAt(i).widget() is not None]
            mains = [w for w in lay_items if isinstance(w, QtWidgets.QPushButton) and w.property("role") == "main"]
            at = v.indexOf(mains[0]) if mains else v.count()
            v.insertWidget(at, b)
            if getattr(self, "open_options", False):       # the picture with Options opened
                b.setText(b.text().replace("▾", "▴"))
                for k, c in enumerate(opts):
                    got = self.node(c)
                    if got is not None:
                        v.insertWidget(at + 1 + k, got)

    def _bar(self, n, title, closed, help_text, inner):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        bar = QtWidgets.QFrame()
        bar.setObjectName("bar")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 6, 4)
        if not inner:
            self.n += 1
        if self.opt["badge"] and not inner:
            num = QtWidgets.QLabel(str(self.n))
            num.setObjectName("num")
            num.setFixedSize(18, 18)
            num.setAlignment(Qt.AlignCenter)
            h.addWidget(num)
            t = QtWidgets.QLabel(title + ("   ▸" if closed else ""))
        else:
            t = QtWidgets.QLabel(("▸  " if closed else "▾  ") + ("" if inner else "%d.  " % self.n) + title)
        t.setObjectName("barTitle")
        h.addWidget(t, 1)
        if help_text and not inner:
            b = QtWidgets.QPushButton("?")
            b.setProperty("role", "help")
            h.addWidget(b)
        v.addWidget(bar)
        if not inner:
            self._desc(help_text, v, 6)
        if not closed:
            body = QtWidgets.QWidget()
            bv = QtWidgets.QVBoxLayout(body)
            bv.setContentsMargins(10, 2, 4, 6)
            bv.setSpacing(6)
            self.kids(n, bv)
            v.addWidget(body)
        return w

    def _card(self, n, title, closed, help_text, inner):
        card = QtWidgets.QFrame()
        card.setObjectName("card")
        if inner:
            card.setStyleSheet("QFrame#card { background: #33373d; border: 1px solid #454a51; }")
        v = QtWidgets.QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(8)
        h = QtWidgets.QHBoxLayout()
        h.setSpacing(8)
        if not inner:
            self.n += 1
            num = QtWidgets.QLabel(str(self.n))
            num.setObjectName("num")
            num.setFixedSize(20, 20)
            num.setAlignment(Qt.AlignCenter)
            h.addWidget(num, 0, Qt.AlignTop)
        t = QtWidgets.QLabel(title)
        t.setObjectName("cardTitle")
        if inner:
            t.setStyleSheet("font-size: 13px; font-weight: bold;")
        h.addWidget(t, 1)
        arrow = QtWidgets.QLabel("▸" if closed else "▾")
        arrow.setProperty("role", "dim")
        h.addWidget(arrow)
        v.addLayout(h)
        has_light = self.opt.get("fold") and any(c.kw.get("_light") for c in self._walk(n))
        if not inner and (not closed or self.opt.get("closed_desc", True)) and not has_light:
            self._desc(help_text, v)
        if not closed:
            if self.opt.get("fold") and not inner:
                self._folded(n, v)
            else:
                self.kids(n, v)
        if closed and self.opt.get("fold"):
            v.setContentsMargins(12, 8, 12, 8)
        return card

    def _text(self, n):
        text = str(n.label())
        if n.kw.get("_light"):
            if self.opt.get("fold_lights") and self._inside_frame(n):
                return None                                  # (C4: a step's light folds - its number says it)
            if not text.strip() and self.opt.get("fold"):
                return None                                  # (the tool says nothing yet: no empty box)
            w = QtWidgets.QLabel(text.strip() or "Select the objects to work on.")
            w.setObjectName("light")
            w.setWordWrap(True)
            w.setStyleSheet("QLabel#light { background: %s; }" % LIGHT[self.style])
            return w
        if not text.strip():
            return None
        w = QtWidgets.QLabel(text.strip())
        w.setWordWrap(True)
        if n.kw.get("font") in ("smallPlainLabelFont", "obliqueLabelFont"):
            w.setProperty("role", "dim")
        return w

    def _button(self, n):
        text = str(n.label())
        if text == "?":
            return None
        b = QtWidgets.QPushButton(text.replace("&", "&&"))
        if n.kw.get("backgroundColor") or (n.kw.get("height") or 0) >= 30:
            b.setProperty("role", "main")
        elif text.lower().startswith(("delete", "remove", "clear")):
            b.setProperty("role", "danger")
        return b

    _iconTextButton = _button

    def _checkBox(self, n):
        c = QtWidgets.QCheckBox(str(n.label()).replace("&", "&&"))
        c.setChecked(bool(n.kw.get("value") or n.kw.get("v")))
        return c

    def _radioButtonGrp(self, n):
        labels = [l for k in ("labelArray2", "labelArray3", "labelArray4", "la2", "la3", "la4")
                  for l in (n.kw.get(k) or [])]
        sel = int(n.kw.get("select") or n.kw.get("sl") or 1)
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6 if self.opt["choice"] == "pill" else 14)
        for i, lab in enumerate(labels):
            if self.opt["choice"] == "seg":
                r = QtWidgets.QPushButton(lab.replace("&", "&&"))
                r.setProperty("role", "seg")
                r.setProperty("first", "true" if i == 0 else "false")
                r.setProperty("last", "true" if i == len(labels) - 1 else "false")
                r.setCheckable(True)
                r.setChecked(i + 1 == sel)
                h.setSpacing(0)
                h.addWidget(r, 1)
                continue
            if self.opt["choice"] == "radio":
                r = QtWidgets.QRadioButton(lab.replace("&", "&&"))
                r.setChecked(i + 1 == sel)
            else:
                r = QtWidgets.QPushButton(("●  " if i + 1 == sel else "○  ") + lab.replace("&", "&&"))
                r.setProperty("role", "pill")
                r.setCheckable(True)
                r.setChecked(i + 1 == sel)
            h.addWidget(r)
        h.addStretch(1)
        return self.labelled(str(n.label()), w) if n.label() else w

    def _optionMenu(self, n):
        c = QtWidgets.QComboBox()
        c.addItems([str(i.get("label", "")) for i in n.items] or ["-"])
        c.setCurrentIndex(max(0, int(n.kw.get("select", 1)) - 1))
        return self.labelled(str(n.label()), c) if n.label() else c

    _optionMenuGrp = _optionMenu

    def _textField(self, n):
        e = QtWidgets.QLineEdit(str(n.kw.get("text") or ""))
        e.setPlaceholderText(str(n.kw.get("placeholderText") or ""))
        return e

    def _number(self, n):
        return QtWidgets.QLineEdit("%g" % float(n.kw.get("value") or n.kw.get("v") or 0))

    _floatField = _intField = _number

    def _group(self, n):
        count = int(n.kw.get("numberOfFields") or 1)
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(5)
        if n.kind == "textFieldGrp":
            h.addWidget(QtWidgets.QLineEdit(str(n.kw.get("text") or "")), 1)
        else:
            for i in range(count):
                h.addWidget(QtWidgets.QLineEdit("%g" % float(n.kw.get("value%d" % (i + 1), 0) or 0)))
        return self.labelled(str(n.label()), w) if n.label() else w

    _textFieldGrp = _floatFieldGrp = _intFieldGrp = _group

    def _slider(self, n):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        e = QtWidgets.QLineEdit("%g" % float(n.kw.get("value") or 0))
        e.setFixedWidth(60)
        s = QtWidgets.QSlider(Qt.Horizontal)
        h.addWidget(e)
        h.addWidget(s, 1)
        return self.labelled(str(n.label()), w)

    _floatSliderGrp = _intSliderGrp = _slider

    def _colorSliderGrp(self, n):
        sw = QtWidgets.QPushButton("")
        sw.setFixedSize(46, 22)
        rgb = n.kw.get("rgb") or (0.5, 0.5, 0.5)
        sw.setStyleSheet("background: rgb(%d,%d,%d); border-radius: 4px;" % tuple(int(x * 255) for x in rgb[:3]))
        return self.labelled(str(n.label()), sw)

    def _separator(self, n):
        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #555;")
        return line

    def _textScrollList(self, n):
        lw = QtWidgets.QListWidget()
        lw.addItems([str(t) for t in (n.kw.get("append") or [])] if isinstance(n.kw.get("append"), list) else [])
        lw.setFixedHeight(70)
        return lw

    def _scrollField(self, n):
        t = QtWidgets.QPlainTextEdit(str(n.kw.get("text") or ""))
        t.setFixedHeight(60)
        return t


WINDOW_CSS = """
QWidget#win { background: %(page)s; }
QFrame#side { background: %(side)s; }
QLabel#sideHead { color: #8d939b; font-size: 10px; letter-spacing: 1px; }
QPushButton[role="nav"] { background: transparent; border: none; text-align: left; padding: 6px 8px;
                          border-radius: 5px; color: #d6d9de; font-size: 13px; }
QPushButton[role="nav"]:checked { background: rgba(255,255,255,0.09); color: white; font-weight: bold; }
QPushButton[role="tab"] { background: transparent; border: none; border-radius: 0px; padding: 7px 12px;
                          color: #aab0b8; font-size: 13px; border-bottom: 2px solid transparent; }
QPushButton[role="tab"]:checked { color: white; font-weight: bold; border-bottom: 3px solid %(accent)s; }
QPushButton[role="tab2"] { background: transparent; border: 1px solid transparent; border-radius: 11px;
                           padding: 3px 10px; color: #a2a7ae; font-size: 12px; }
QPushButton[role="tab2"]:checked { border: 1px solid %(accent)s; color: white; font-weight: bold; }
QFrame#sel { background: rgba(0,0,0,0.18); border-radius: 6px; }
"""
PAGE_BG = {"c4": "#16191e", "c3a": "#2b2e33", "c3b": "#2b2e33", "classic": "#3d3d3d", "new": "#2f3237", "mixA": "#2f3237", "mixB": "#393c41", "mixC": "#33363b"}
SIDE_BG = {"c4": "#22262d", "classic": "#333333", "new": "#26292d", "mixA": "#26292d", "mixB": "#2f3236", "mixC": "#2a2d31"}


def window(style, key, page, area="toolbox", tabs=("Select", "Groups", "Mirror", "Rename", "Pivots"),
           current=None, tabs2=None, current2=None):
    """The whole window around a page: the sidebar (areas), the header, the tool tabs, the Selected box."""
    from gus_rigtool.newui import theme
    win = QtWidgets.QWidget()
    win.setObjectName("win")
    h = QtWidgets.QHBoxLayout(win)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    side = QtWidgets.QFrame()
    side.setObjectName("side")
    side.setFixedWidth(178)
    sv = QtWidgets.QVBoxLayout(side)
    sv.setContentsMargins(8, 12, 8, 10)
    sv.setSpacing(2)
    head = QtWidgets.QLabel("YOUR RIG, IN ORDER")
    head.setObjectName("sideHead")
    sv.addWidget(head)
    steps = [a for a in theme.AREAS if a[0] not in ("home", "toolbox", "settings")]
    for i, a in enumerate(steps):
        b = QtWidgets.QPushButton("%d   %s" % (i + 1, a[1].replace("&", "&&")))
        b.setProperty("role", "nav")
        b.setStyleSheet("QPushButton { border-left: 3px solid %s; }" % a[2])
        sv.addWidget(b)
    head2 = QtWidgets.QLabel("ANY TIME")
    head2.setObjectName("sideHead")
    sv.addSpacing(8)
    sv.addWidget(head2)
    for b in side.findChildren(QtWidgets.QPushButton):
        if b.text().split("   ")[-1].replace("&&", "&") == theme.area(area)[1]:
            b.setCheckable(True)
            b.setChecked(True)
    tb = QtWidgets.QPushButton("Toolbox")
    tb.setProperty("role", "nav")
    tb.setCheckable(True)
    tb.setChecked(area == "toolbox")
    tb.setStyleSheet("QPushButton { border-left: 3px solid %s; }" % theme.colour("toolbox"))
    sv.addWidget(tb)
    for t in ("My tools", ):
        b = QtWidgets.QPushButton(t)
        b.setProperty("role", "nav")
        sv.addWidget(b)
    sv.addStretch(1)
    st = QtWidgets.QPushButton("Settings")
    st.setProperty("role", "nav")
    sv.addWidget(st)
    h.addWidget(side)
    main = QtWidgets.QWidget()
    mv = QtWidgets.QVBoxLayout(main)
    mv.setContentsMargins(14, 12, 14, 0)
    mv.setSpacing(6)
    from gus_rigtool.newui import window as W
    title = QtWidgets.QLabel("<b style='font-size:21px'>%s</b>&nbsp;&nbsp;<span style='color:#9aa0a8'>%s</span>" % (
        theme.area(area)[1].replace("&", "&amp;"), W.WHY.get(area, "")))
    title.setWordWrap(True)
    mv.addWidget(title)
    for row, cur, role in ((tabs, current or key.title(), "tab"), (tabs2, current2, "tab2")):
        if not row:
            continue
        lay = QtWidgets.QHBoxLayout()
        lay.setSpacing(4 if role == "tab2" else 0)
        for t in row:
            b = QtWidgets.QPushButton(t.replace("&", "&&"))
            b.setProperty("role", role)
            b.setCheckable(True)
            b.setChecked(t == cur)
            lay.addWidget(b)
        lay.addStretch(1)
        mv.addLayout(lay)
    sel = QtWidgets.QFrame()
    sel.setObjectName("sel")
    sl = QtWidgets.QHBoxLayout(sel)
    sl.setContentsMargins(10, 6, 10, 6)
    sl.addWidget(QtWidgets.QLabel("<span style='color:#8d939b;font-size:10px'>SELECTED</span>&nbsp;&nbsp;nothing"))
    mv.addWidget(sel)
    mv.addWidget(page, 1)
    h.addWidget(main, 1)
    accent = theme.colour(area)
    rgb = ",".join(str(int(accent[i:i + 2], 16)) for i in (1, 3, 5))
    css = STYLES[style].replace("ACCENT_RGB", rgb).replace("ACCENT_TEXT", accent).replace("ACCENT", accent)
    for lab in win.findChildren(QtWidgets.QLabel):
        if "ACCENT_TEXT" in lab.styleSheet():
            lab.setStyleSheet(lab.styleSheet().replace("ACCENT_TEXT", accent))
    if style == "c4":
        css += """
QPushButton[role="tab"] { background: #343c4a; border: 1px solid #454f60; border-radius: 4px; padding: 4px 11px;
                          margin-right: 4px; color: #9aa5b5; font-size: 12px; }
QPushButton[role="tab"]:checked { background: %(a)s; border: 1px solid %(a)s; color: #111; font-weight: bold; }
QPushButton[role="tab2"] { background: transparent; border: 1px solid #333a47; border-radius: 4px; padding: 3px 9px;
                           color: #9aa5b5; font-size: 12px; }
QPushButton[role="tab2"]:checked { border: 1px solid %(a)s; color: #f1f5f9; font-weight: bold; }
QFrame#side { border-right: 1px solid #333a47; }
QFrame#sel { background: #22262d; border: 1px solid #333a47; border-radius: 4px; }
QLabel#foot { background: #22262d; border-top: 1px solid #333a47; color: #9aa5b5; font-size: 11px; padding: 4px 10px; }
""" % {"a": accent}
        foot = QtWidgets.QLabel("<span style='color:%s'>●</span>  nothing selected  ·  %s  ›  %s" % (
            accent, theme.area(area)[1].replace("&", "&amp;"), current2 or current or key.title()))
        foot.setObjectName("foot")
        main.layout().addWidget(foot)
    win.setStyleSheet(css + WINDOW_CSS % {"page": PAGE_BG.get(style, "#33373d"), "side": SIDE_BG.get(style, "#26292d"),
                                          "accent": accent})
    return win


def shoot(key, styles=("classic", "new"), width=520, height=None, whole=False):
    rec = record.record(registry.builder(key), "s_%s_" % key)
    pics = []
    for style in styles:
        p = Page(style)
        w = p.build(rec.root, registry.get(key)[1], registry.get(key)[3], head=not whole)
        w.setStyleSheet(STYLES[style])
        if whole:
            w.layout().setContentsMargins(0, 4, 0, 12)
            w = window(style, key, w)
        w.resize(width, 400)
        w.show()
        app.processEvents()
        h = height or max(w.sizeHint().height(), 400)
        w.resize(width, h)
        app.processEvents()
        path = os.path.join(OUT, "%s_%s_%s.png" % ("window" if whole else "style", key, style))
        w.grab().save(path)
        pics.append(path)
        print(path, h)
    return pics


PAGES = [  # (file name, tool, area, top tabs, current, second-row tabs, current, the sections on that page)
    ("groups", "groups", "toolbox", ("Select", "Groups", "Mirror", "Rename", "Pivots"), "Groups", None, None, None),
    ("groups_open", "groups", "toolbox", ("Select", "Groups", "Mirror", "Rename", "Pivots"), "Groups", None, None,
     None),
    ("mirror", "mirror", "toolbox", ("Select", "Groups", "Mirror", "Rename", "Pivots"), "Mirror", None, None, None),
    ("pivots_move", "pivots", "toolbox", ("Select", "Groups", "Mirror", "Rename", "Pivots"), "Pivots",
     ("Move", "Remember & reset"), "Move", ["Move pivots to", "Bounding box", "From geometry", "Along a chain"]),
    ("face", "face", "build", ("Build", "Face", "Ribbon", "Joints"), "Face",
     ("Build the face", "Ribbons & groups", "Squash & expressions"), "Build the face",
     ["Setup", "Eyes", "Eyelids", "Mouth", "Brows", "Facial strips"]),
    ("skin_bind", "skin", "skin", ("Skin", "Fixes"), "Skin",
     ("Bind", "Copy & mirror", "Save / load", "Clean", "Weights", "Cloth & jiggle"), "Bind", ["Bind"]),
    ("behaviour", "behaviour", "controls", ("Make", "Edit shape", "Behaviour", "Attributes", "Channels", "Spaces",
                                            "Follow", "Stick"), "Behaviour", None, None, None),
]


def shoot_c2(names=None, width=760, style="c2"):
    out = []
    for name, key, area, tabs, cur, tabs2, cur2, only in PAGES:
        if names and name not in names:
            continue
        rec = record.record(registry.builder(key), "c2_%s_" % name)
        p = Page(style, only)
        p.open_options = name.endswith("_open")
        w = p.build(rec.root, "", "", head=False)
        w.layout().setContentsMargins(0, 4, 0, 12)
        win = window(style, key, w, area, tabs, cur, tabs2, cur2)
        win.resize(width, 500)
        win.show()
        app.processEvents()
        win.resize(width, max(win.sizeHint().height(), 560))
        app.processEvents()
        path = os.path.join(OUT, "%s_%s.png" % (style, name))
        win.grab().save(path)
        out.append(path)
        print(path, win.height())
    return out


if __name__ == "__main__":
    if sys.argv[1:2] and sys.argv[1].startswith("c"):
        shoot_c2(sys.argv[2:], style=sys.argv[1])
        sys.exit(0)
    mixes = ("mixA", "mixB", "mixC")
    for key in sys.argv[1:] or ("groups", "mirror", "pivots"):
        shoot(key, mixes)
    shoot("groups", mixes, width=760, whole=True)
