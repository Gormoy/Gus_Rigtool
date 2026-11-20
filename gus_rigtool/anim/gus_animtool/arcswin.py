"""
The Arcs panel (5.6.42): every arc in the scene (show / hide, its own colour, remove; click the name to select the
control), the range (the whole shot or around your frame), the look (line, dots, key dots, frame numbers), editing
(handles on the selected key, timing beads) and speed (a point every 1 / 2 / 4 frames). Settings are kept for next
time; the arcs change straight away.
"""
import sys

import maya.cmds as cmds

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

from gus_animtool import anim as A
from gus_animtool import arctrail as T

_WIN = None
STYLE = """
QPushButton[main="true"] { background:#5285a6; color:white; }
QPushButton[seg="true"] { background:#4b4b4b; border:1px solid #666; padding:3px 9px; border-radius:0px; }
QPushButton[seg="true"]:checked { background:#5285a6; color:white; }
QLabel[note="true"] { color:#9a9a9a; }
QFrame[row="true"] { background:#2b2b2b; border-radius:3px; }
"""
LABEL_W = 120


def _maya_window():
    try:
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None
    except Exception:
        return None


def show():
    global _WIN
    try:
        if _WIN is not None and _WIN.isVisible():
            _WIN.raise_()
            _WIN.refresh()
            return _WIN
    except RuntimeError:
        pass
    _WIN = ArcsWindow()
    _WIN.show()
    return _WIN


def _do(fn, *args, **kw):
    """An action from the panel: problems become a message, never an error box."""
    try:
        return fn(*args, **kw)
    except (RuntimeError, ValueError) as e:
        A.message(str(e), "warn")
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        A.message("error: %s (details in the Script Editor)" % e, "warn")
    return None


def _line(label, *widgets):
    lay = QtWidgets.QHBoxLayout()
    lab = QtWidgets.QLabel(label)
    lab.setFixedWidth(LABEL_W)
    lay.addWidget(lab)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w)
    return lay


class ArcsWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ArcsWindow, self).__init__(parent or _maya_window())
        # the Mac: a tool window stays in front of Maya
        self.setWindowFlags(QtCore.Qt.Tool if sys.platform == "darwin" else QtCore.Qt.Window)
        keep = getattr(QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
        if keep is not None:
            self.setAttribute(keep, True)
        self.setWindowTitle("Arcs")
        self.setObjectName("gusAnimtoolArcsWindow")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.resize(430, 640)
        self.jobs = []
        self._build()
        self.refresh()
        try:
            self.jobs = [cmds.scriptJob(event=[e, self._later_refresh]) for e in ("SceneOpened", "NewSceneOpened")]
        except Exception:
            self.jobs = []

    # ---------------------------------------------------------------- building
    def _build(self):
        v = QtWidgets.QVBoxLayout(self)
        box = QtWidgets.QGroupBox("Arcs in this scene")
        bl = QtWidgets.QVBoxLayout(box)
        self.rows = QtWidgets.QVBoxLayout()
        self.rows.setSpacing(3)
        bl.addLayout(self.rows)
        add = QtWidgets.QPushButton("+ Arc on the selection")
        add.setProperty("main", True)
        add.setToolTip("An arc on each selected control (over the shot, or around your frame)")
        add.clicked.connect(self.add)
        clear = QtWidgets.QPushButton("Clear all")
        clear.clicked.connect(self.clear)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(add, 1)
        row.addWidget(clear)
        bl.addLayout(row)
        tip = QtWidgets.QLabel("Click a name: it's selected. The colour square: that arc's own colour.")
        tip.setProperty("note", True)
        bl.addWidget(tip)
        v.addWidget(box)

        box = QtWidgets.QGroupBox("Range")
        bl = QtWidgets.QVBoxLayout(box)
        self.shot_btn, self.around_btn = self._seg(["The whole shot", "Around my frame"])
        self.shot_btn.clicked.connect(lambda *_: self.set("arcs_around", False))
        self.around_btn.clicked.connect(lambda *_: self.set("arcs_around", True))
        bl.addLayout(_line("Show", self.shot_btn, self.around_btn, None))
        self.frames = QtWidgets.QSpinBox()
        self.frames.setRange(1, 500)
        self.frames.setToolTip("Frames before and after your frame")
        self.frames.valueChanged.connect(lambda n: self.set("arcs_frames", int(n)))
        bl.addLayout(_line("Frames before / after", self.frames, None))
        v.addWidget(box)

        box = QtWidgets.QGroupBox("Look (all arcs)")
        bl = QtWidgets.QVBoxLayout(box)
        self.sliders = {}
        for key, label, lo, hi, tip in (("arcs_thick", "Line thickness", 1, 8, "How thick the line is"),
                                        ("arcs_dot", "Frame dots", 1, 15, "The size of the dot on each frame"),
                                        ("arcs_key", "Key dots", 1, 20, "The size of the dot on each key")):
            sld = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            sld.setRange(lo, hi)
            sld.setToolTip(tip)
            val = QtWidgets.QLabel()
            val.setFixedWidth(24)
            sld.valueChanged.connect(lambda n, k=key, lab=val: (lab.setText(str(n)), self.set(k, float(n))))
            self.sliders[key] = (sld, val)
            bl.addLayout(_line(label, sld, val))
        self.dots_chk = QtWidgets.QCheckBox("Frame dots (spacing)")
        self.dots_chk.toggled.connect(lambda on: self.set("arcs_dots", bool(on)))
        self.numbers_chk = QtWidgets.QCheckBox("Frame numbers")
        self.numbers_chk.toggled.connect(lambda on: self.set("arcs_numbers", bool(on)))
        bl.addWidget(self.dots_chk)
        bl.addWidget(self.numbers_chk)
        v.addWidget(box)

        box = QtWidgets.QGroupBox("Editing")
        bl = QtWidgets.QVBoxLayout(box)
        self.handles_chk = QtWidgets.QCheckBox("Handles on the selected key")
        self.handles_chk.setToolTip("Select a key dot on an arc: its bezier handles show, to bend the arc")
        self.handles_chk.toggled.connect(lambda on: self.set("arcs_handles", bool(on)))
        bl.addWidget(self.handles_chk)
        beads = QtWidgets.QPushButton("Make the selection's curves weighted...")
        beads.setToolTip("Timing beads (ease in / out on the arc) need weighted tangents. Asks first.")
        beads.clicked.connect(self.beads)
        bl.addLayout(_line("Timing beads", beads, None))
        brk = QtWidgets.QPushButton("Break")
        brk.setToolTip("The selected key's two handles move on their own (Maya joins them by default)")
        brk.clicked.connect(lambda *_: self.handles(False))
        join = QtWidgets.QPushButton("Join again")
        join.setToolTip("The selected key's handles move together again")
        join.clicked.connect(lambda *_: self.handles(True))
        bl.addLayout(_line("Key handles", brk, join))
        note = QtWidgets.QLabel("Asks first. The beads only show on weighted curves.")
        note.setProperty("note", True)
        bl.addWidget(note)
        v.addWidget(box)

        box = QtWidgets.QGroupBox("Speed")
        bl = QtWidgets.QVBoxLayout(box)
        self.step_btns = {}
        btns = self._seg(["1", "2", "4"])
        for n, b in zip((1, 2, 4), btns):
            b.clicked.connect(lambda *_a, k=n: self.set("arcs_step", k))
            self.step_btns[n] = b
        note = QtWidgets.QLabel("frames (heavy rigs: 2 or 4)")
        note.setProperty("note", True)
        bl.addLayout(_line("A point every", *(list(btns) + [note, None])))
        v.addWidget(box)
        v.addStretch(1)

    def _seg(self, labels):
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        out = []
        for lab in labels:
            b = QtWidgets.QPushButton(lab)
            b.setCheckable(True)
            b.setProperty("seg", True)
            group.addButton(b)
            out.append(b)
        return out

    # ---------------------------------------------------------------- refresh
    def refresh(self):
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        arcs = T.arcs()
        if not arcs:
            lab = QtWidgets.QLabel("No arcs yet: select controls, then + Arc on the selection.")
            lab.setProperty("note", True)
            self.rows.addWidget(lab)
        for n, _trails in arcs:
            self.rows.addWidget(self._row(n))
        around = T.opt("arcs_around")
        self.shot_btn.setChecked(not around)
        self.around_btn.setChecked(around)
        self._quiet(self.frames, lambda: self.frames.setValue(T.opt("arcs_frames")))
        self.frames.setEnabled(around)
        for key, (sld, val) in self.sliders.items():
            self._quiet(sld, lambda s=sld, k=key: s.setValue(int(round(T.opt(k)))))
            val.setText(str(sld.value()))
        for chk, key in ((self.dots_chk, "arcs_dots"), (self.numbers_chk, "arcs_numbers"),
                         (self.handles_chk, "arcs_handles")):
            self._quiet(chk, lambda c=chk, k=key: c.setChecked(T.opt(k)))
        step = T.opt("arcs_step")
        for n, b in self.step_btns.items():
            b.setChecked(n == step)

    def _quiet(self, w, fn):
        w.blockSignals(True)
        try:
            fn()
        finally:
            w.blockSignals(False)

    def _row(self, n):
        row = QtWidgets.QFrame()
        row.setProperty("row", True)
        lay = QtWidgets.QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 4, 2)
        hidden = n in T._state["hidden"]
        eye = QtWidgets.QToolButton()
        eye.setCheckable(True)
        eye.setChecked(not hidden)
        eye.setAutoRaise(True)
        eye.setText("\U0001F441")
        eye.setToolTip("Show / hide this arc (it's kept)")
        eye.toggled.connect(lambda on: (T.set_visible(n, on), self.refresh()))
        swatch = QtWidgets.QToolButton()
        r, g, b = [int(c * 255) for c in T.colour_of(n)]
        swatch.setStyleSheet("background: rgb(%d,%d,%d); border: 1px solid #222; border-radius: 3px;" % (r, g, b))
        swatch.setFixedSize(16, 16)
        swatch.setToolTip("This arc's colour - click to change it")
        swatch.clicked.connect(lambda *_: self.pick_colour(n))
        name = QtWidgets.QPushButton(A.short(n) + ("  (hidden)" if hidden else ""))
        name.setFlat(True)
        name.setStyleSheet("text-align: left; padding: 0px;")
        name.setToolTip("Select this control")
        name.clicked.connect(lambda *_: cmds.select(n, replace=True))
        note = QtWidgets.QLabel(T.note_of(n))
        note.setProperty("note", True)
        x = QtWidgets.QToolButton()
        x.setAutoRaise(True)
        x.setText("✕")
        x.setToolTip("Remove this arc")
        x.clicked.connect(lambda *_: (T.remove(n), self.refresh()))
        if hidden:
            for w in (name, swatch):
                eff = QtWidgets.QGraphicsOpacityEffect(w)
                eff.setOpacity(0.5)
                w.setGraphicsEffect(eff)
        lay.addWidget(eye)
        lay.addWidget(swatch)
        lay.addWidget(name, 1)
        lay.addWidget(note)
        lay.addWidget(x)
        return row

    def _later_refresh(self, *_):
        try:
            cmds.evalDeferred(self.refresh, lowestPriority=True)
        except Exception:
            pass

    # ---------------------------------------------------------------- actions
    def set(self, key, value):
        _do(T.set_option, key, value)
        self.refresh()

    def add(self):
        got = _do(T.show, cmds.ls(selection=True, long=True) or [])
        if got:
            A.message(got + ".")
        self.refresh()

    def clear(self):
        _do(T.clear)
        self.refresh()

    def handles(self, join):
        from gus_animtool import actions as AC
        AC.run("arcs_join" if join else "arcs_break")

    def beads(self):
        n = _do(T.make_weighted, cmds.ls(selection=True, long=True) or [])
        if n:
            A.message("%d curve(s) now weighted: the timing beads show on their arcs." % n)
        self.refresh()

    def pick_colour(self, n):
        r, g, b = [int(c * 255) for c in T.colour_of(n)]
        got = QtWidgets.QColorDialog.getColor(QtGui.QColor(r, g, b), self, "The arc of %s" % A.short(n))
        if got.isValid():
            _do(T.set_colour, n, (got.redF(), got.greenF(), got.blueF()))
        self.refresh()

    def closeEvent(self, event):
        for j in self.jobs:
            try:
                if cmds.scriptJob(exists=j):
                    cmds.scriptJob(kill=j, force=True)
            except Exception:
                pass
        global _WIN
        if _WIN is self:
            _WIN = None
        super(ArcsWindow, self).closeEvent(event)
