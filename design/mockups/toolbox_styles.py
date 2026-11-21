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
LIGHT = {"classic": "#5a4a22", "new": "#4f4420"}
LABEL_W = 96


def first_sentence(text):
    text = str(text or "").strip()
    m = re.match(r"(.+?(?<!e\.g)\.)(\s+[A-Z(]|$)", text)
    text = m.group(1) if m else text
    if len(text) > 120:
        text = text[:117].rsplit(" ", 1)[0] + "..."
    return text


class Page(object):
    def __init__(self, style):
        self.style = style
        self.n = 0

    def build(self, root, title, subtitle):
        w = QtWidgets.QWidget()
        w.setObjectName("page")
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(9)
        head = QtWidgets.QLabel("<b style='font-size:18px'>%s</b><br><span style='color:#a8a8a8'>%s</span>" % (
            title, subtitle))
        v.addWidget(head)
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
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lab = QtWidgets.QLabel(text)
        lab.setProperty("role", "lab")
        lab.setFixedWidth(LABEL_W)
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lab)
        h.addWidget(widget, 1)
        return w

    def _rowLayout(self, n):
        kids = [c for c in n.children]
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
        w = QtWidgets.QWidget()
        g = QtWidgets.QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(5)
        cols = int(n.kw.get("numberOfColumns") or n.kw.get("nc") or 3)
        for i, c in enumerate(n.children):
            got = self.node(c)
            if got is not None:
                g.addWidget(got, i // cols, i % cols)
        if self.style == "new":
            return self.labelled("Quick", w)
        return w

    _rowColumnLayout = _gridLayout

    def _frameLayout(self, n):
        title = re.sub(r"^\s*\d+\.\s+", "", str(n.label())).replace("(advanced)", "").strip()
        closed = bool(n.kw.get("collapse") or n.kw.get("cl"))
        help_text = str(n.kw.get("annotation") or "")
        inner = n.parent is not None and n.parent.kind != "columnLayout" or (
            n.parent is not None and n.parent.parent is not None and n.parent.parent.kind == "frameLayout")
        if self.style == "classic":
            return self._bar(n, title, closed, help_text, inner)
        return self._card(n, title, closed, help_text, inner)

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
        t = QtWidgets.QLabel(("▸  " if closed else "▾  ") + ("" if inner else "%d.  " % self.n) + title)
        t.setObjectName("barTitle")
        h.addWidget(t, 1)
        if help_text and not inner:
            b = QtWidgets.QPushButton("?")
            b.setProperty("role", "help")
            h.addWidget(b)
        v.addWidget(bar)
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
        if help_text and not inner:                      # what this section does, in one line
            d = QtWidgets.QLabel(first_sentence(help_text))
            d.setProperty("role", "dim")
            d.setWordWrap(True)
            v.addWidget(d)
        if not closed:
            self.kids(n, v)
        return card

    def _text(self, n):
        text = str(n.label())
        if n.kw.get("_light"):
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
        h.setSpacing(6 if self.style == "new" else 14)
        for i, lab in enumerate(labels):
            if self.style == "classic":
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


def shoot(key, width=520, height=None):
    rec = record.record(registry.builder(key), "s_%s_" % key)
    pics = []
    for style in ("classic", "new"):
        p = Page(style)
        w = p.build(rec.root, registry.get(key)[1], registry.get(key)[3])
        w.setStyleSheet(STYLES[style])
        w.resize(width, 400)
        w.show()
        app.processEvents()
        h = height or max(w.sizeHint().height(), 400)
        w.resize(width, h)
        app.processEvents()
        path = os.path.join(OUT, "style_%s_%s.png" % (key, style))
        w.grab().save(path)
        pics.append(path)
        print(path, h)
    return pics


if __name__ == "__main__":
    for key in sys.argv[1:] or ("groups", "mirror", "pivots"):
        shoot(key)
