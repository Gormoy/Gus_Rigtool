"""
The Attach window (5.6.41): what's attached in the scene; for the one you pick, who holds it over time (a coloured
strip - click it to go there) and its changes (Go / Frame... / Delete); and the actions. The values themselves live
on the follower's Hold channels (Channel Box) - this window shows them over time and doesn't repeat them.
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
from gus_animtool import attach as AT

_WIN = None
STYLE = """
QPushButton[main="true"] { background:#5285a6; color:white; }
QLabel[note="true"] { color:#9a9a9a; }
QFrame[row="true"] { background:#2b2b2b; border-radius:3px; }
"""


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
    _WIN = AttachWindow()
    _WIN.show()
    return _WIN


def _rgb(c):
    return QtGui.QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))


def _do(fn, *args, **kw):
    """An action from the window: problems become a message, never an error box."""
    try:
        got = fn(*args, **kw)
        return got
    except (RuntimeError, ValueError) as e:
        A.message(str(e), "warn")
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        A.message("error: %s (details in the Script Editor)" % e, "warn")
    return None


class Strip(QtWidgets.QWidget):
    """Who holds it over time: a coloured bar per stretch, the current frame as a white line. Click: go there."""

    def __init__(self, parent=None):
        super(Strip, self).__init__(parent)
        self.segs, self.lo, self.hi, self.now = [], 1.0, 100.0, 1.0
        self.setMinimumHeight(40)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Who holds it over time. Click to go to that frame.")

    def set_data(self, segs, lo, hi, now):
        self.segs, self.lo, self.hi, self.now = segs, float(lo), float(max(hi, lo + 1)), float(now)
        self.update()

    def _x(self, f):
        return 4 + (self.width() - 8) * (f - self.lo) / (self.hi - self.lo)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        bar = QtCore.QRectF(4, 2, self.width() - 8, 22)
        p.fillRect(bar, QtGui.QColor("#2b2b2b"))
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        for s in self.segs:
            x0 = max(self._x(s["start"]), bar.left())
            x1 = min(self._x(s["end"] if s["end"] is not None else self.hi + 1), bar.right())
            if x1 <= x0:
                continue
            r = QtCore.QRectF(x0, bar.top(), x1 - x0, bar.height())
            if s["main"] is None:
                col = QtGui.QColor("#3a3a3a")
            else:
                col = _rgb(AT.colour(s["main"]))
            if s["handover"] or len([w for w in s["holds"].values() if w > 1e-4]) > 1:
                brush = QtGui.QBrush(col, QtCore.Qt.BDiagPattern)
                p.fillRect(r, col.darker(140))
                p.fillRect(r, brush)
            else:
                p.fillRect(r, col)
            p.setPen(QtGui.QColor("white"))
            p.drawText(r, QtCore.Qt.AlignCenter, s["label"] if x1 - x0 > 40 else "")
        p.setPen(QtGui.QColor("#9a9a9a"))
        p.drawText(QtCore.QRectF(4, 26, 80, 12), QtCore.Qt.AlignLeft, "%g" % self.lo)
        p.drawText(QtCore.QRectF(self.width() - 84, 26, 80, 12), QtCore.Qt.AlignRight, "%g" % self.hi)
        if self.lo <= self.now <= self.hi:
            p.setPen(QtGui.QPen(QtGui.QColor("white"), 2))
            x = self._x(self.now)
            p.drawLine(QtCore.QPointF(x, 0), QtCore.QPointF(x, 26))
        p.end()

    def mousePressEvent(self, e):
        pos = e.pos()
        f = self.lo + (pos.x() - 4) / float(max(self.width() - 8, 1)) * (self.hi - self.lo)
        cmds.currentTime(round(f))


class AttachWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(AttachWindow, self).__init__(parent or _maya_window())
        # the Mac: a tool window stays in front of Maya (a plain window goes behind it when Maya is clicked)
        self.setWindowFlags(QtCore.Qt.Tool if sys.platform == "darwin" else QtCore.Qt.Window)
        _keep_shown = getattr(QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
        if _keep_shown is not None:
            self.setAttribute(_keep_shown, True)
        self.setWindowTitle("Attach")
        self.setObjectName("gusAnimtoolAttachWindow")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.resize(540, 600)
        self.current = None
        self.jobs = []
        self._build()
        self.refresh()
        try:
            self.jobs = [cmds.scriptJob(event=["timeChanged", self._time_changed]),
                         cmds.scriptJob(event=["SelectionChanged", self._selection_changed])]
        except Exception:
            self.jobs = []

    # ---------------------------------------------------------------- building
    def _build(self):
        v = QtWidgets.QVBoxLayout(self)
        box = QtWidgets.QGroupBox("Attached in this scene")
        bl = QtWidgets.QVBoxLayout(box)
        self.list = QtWidgets.QTreeWidget()
        self.list.setHeaderHidden(True)
        self.list.setColumnCount(2)
        self.list.setRootIsDecorated(False)
        self.list.setMaximumHeight(130)
        self.list.itemClicked.connect(self._picked)
        bl.addWidget(self.list)
        v.addWidget(box)

        self.time_box = QtWidgets.QGroupBox("Over time")
        tl = QtWidgets.QVBoxLayout(self.time_box)
        self.strip = Strip()
        tl.addWidget(self.strip)
        self.changes = QtWidgets.QVBoxLayout()
        self.changes.setSpacing(3)
        tl.addLayout(self.changes)
        self.note = QtWidgets.QLabel()
        self.note.setProperty("note", True)
        self.note.setWordWrap(True)
        tl.addWidget(self.note)
        v.addWidget(self.time_box)

        box = QtWidgets.QGroupBox("Do (select what follows, then the holder)")
        g = QtWidgets.QGridLayout(box)
        actions = [("Attach", "From this frame it follows the second one (no jump)", self.attach, True),
                   ("Hand-over...", "From what holds it now to the second one, over a few frames (both carry it "
                                    "in between)", self.hand_over, False),
                   ("Both hands", "Held by what holds it now and the second one, 50 / 50", self.both, False),
                   ("Release", "From this frame it stays where it is", self.release, False),
                   ("Bake", "Plain keys every frame of the range; the attach goes", self.bake, False),
                   ("Repair", "Attaches from 5.6.40: stop their stutter (nothing moves)", self.repair, False)]
        for n, (label, tip, fn, main) in enumerate(actions):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            if main:
                b.setProperty("main", True)
            b.clicked.connect(lambda *_a, f=fn: f())
            g.addWidget(b, n // 3, n % 3)
        v.addWidget(box)
        tip = QtWidgets.QLabel("The amounts are the Hold channels in the Channel Box (key them like any channel). "
                               "Its own Translate / Rotate still work on top: you can still move it.")
        tip.setProperty("note", True)
        tip.setWordWrap(True)
        v.addWidget(tip)
        v.addStretch(1)

    # ---------------------------------------------------------------- refresh
    def refresh(self):
        self.list.clear()
        nodes = AT.attached()
        if self.current not in nodes:
            sel = [n for n in A.selected() if n in nodes]
            self.current = sel[0] if sel else (nodes[0] if nodes else None)
        for n in nodes:
            data = AT.read(n)
            if AT.is_old(data):
                note = "from 5.6.40: Repair or Bake"
            else:
                ev = AT.events(n)
                segs = AT.timeline(n)
                now = cmds.currentTime(query=True)
                here = [s for s in segs if s["start"] <= now and (s["end"] is None or now < s["end"])]
                note = "%d change%s - now: %s" % (len(ev), "" if len(ev) == 1 else "s",
                                                  here[0]["label"] if here else "its own parent")
            item = QtWidgets.QTreeWidgetItem([A.short(n), note])
            item.setData(0, QtCore.Qt.UserRole, n)
            self.list.addTopLevelItem(item)
            if n == self.current:
                self.list.setCurrentItem(item)
        self.list.resizeColumnToContents(0)
        self._fill_time()

    def _fill_time(self):
        while self.changes.count():
            w = self.changes.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        n = self.current
        if not n or not cmds.objExists(n):
            self.time_box.setTitle("Over time")
            self.strip.set_data([], 1, 100, 1)
            self.note.setText("Nothing attached yet: select what follows, then what it holds on to, then Attach.")
            return
        self.time_box.setTitle("%s over time" % A.short(n))
        lo, hi = A.frame_range()
        segs = AT.timeline(n)
        self.strip.set_data(segs, lo, hi, cmds.currentTime(query=True))
        data = AT.read(n)
        for seg in segs:
            if seg["label"] == "its own parent" and seg is segs[0]:
                continue
            self.changes.addWidget(self._row(n, seg))
        notes = []
        if AT.is_old(data):
            notes.append("This attach is from 5.6.40: Repair stops its stutter; Bake it and Attach again to get "
                         "the Hold channels.")
        if "ik" in A.short(n).lower():
            notes.append("An IK control: only the IK follows. Attach while the arm is in IK, or Bake before "
                         "switching to FK.")
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))

    def _row(self, n, seg):
        row = QtWidgets.QFrame()
        row.setProperty("row", True)
        lay = QtWidgets.QHBoxLayout(row)
        lay.setContentsMargins(6, 2, 4, 2)
        frame = QtWidgets.QLabel("%g" % seg["start"])
        frame.setFixedWidth(48)
        dot = QtWidgets.QLabel()
        dot.setFixedSize(10, 10)
        col = AT.colour(seg["main"]) if seg["main"] is not None else (0.23, 0.23, 0.23)
        dot.setStyleSheet("background: rgb(%d,%d,%d); border-radius: 2px;" % tuple(int(c * 255) for c in col))
        text = seg["label"]
        if seg["handover"] and seg["end"] is not None:
            text += " (%g frames)" % (seg["end"] - seg["start"])
        label = QtWidgets.QLabel(text)
        lay.addWidget(frame)
        lay.addWidget(dot)
        lay.addWidget(label, 1)
        for name, tip, fn in (("Go", "Go to this frame", lambda: cmds.currentTime(seg["start"])),
                              ("Frame...", "Move this change to another frame (taken again there: no jump)",
                               lambda: self.move(n, seg["start"])),
                              ("Delete", "Take this change away; the other frames keep what they have",
                               lambda: self.delete(n, seg["start"]))):
            b = QtWidgets.QPushButton(name)
            b.setToolTip(tip)
            b.clicked.connect(lambda *_a, f=fn: f())
            lay.addWidget(b)
        return row

    def _picked(self, item, *_):
        n = item.data(0, QtCore.Qt.UserRole)
        self.current = n
        try:
            cmds.select(n, replace=True)
        except Exception:
            pass
        self._fill_time()

    def _time_changed(self, *_):
        try:
            self.strip.now = cmds.currentTime(query=True)
            self.strip.update()
        except RuntimeError:
            pass

    def _selection_changed(self, *_):
        try:
            nodes = AT.attached()
            sel = [n for n in A.selected() if n in nodes]
            if sel and sel[0] != self.current:
                self.current = sel[0]
                self.refresh()
        except RuntimeError:
            pass

    # ---------------------------------------------------------------- actions
    def _after(self, got):
        self.refresh()
        return got

    def attach(self):
        return self._after(_do(AT.attach))

    def hand_over(self):
        frames, ok = QtWidgets.QInputDialog.getInt(self, "Hand-over", "Over how many frames?", AT.HANDOVER_FRAMES,
                                                   1, 200)
        if ok:
            return self._after(_do(AT.hand_over, frames=frames))
        return None

    def both(self):
        return self._after(_do(AT.both))

    def release(self):
        return self._after(_do(AT.release))

    def bake(self):
        cmds.evalDeferred(lambda: self._after(_do(AT.bake)), lowestPriority=True)

    def repair(self):
        got = _do(AT.repair)
        if got is not None:
            A.message("repaired %d attach link(s): no more stutter." % got)
        return self._after(got)

    def move(self, n, frame):
        new, ok = QtWidgets.QInputDialog.getInt(self, "Move this change", "To which frame?", int(frame), -100000,
                                                100000)
        if ok and new != int(frame):
            self._after(_do(AT.move_change, n, frame, new))

    def delete(self, n, frame):
        self._after(_do(AT.delete_change, n, frame))

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
        super(AttachWindow, self).closeEvent(event)
