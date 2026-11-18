"""
The mini bar: a small strip that floats over Maya - ON, Before - / +, After - / +, Keys / Main / Frames, Fill,
Arcs, and a gear that opens the big window. Drag it by its left edge; it remembers where you left it.
"""
from onionSkinRenderer.qt import QtCore, QtWidgets, maya_main_window
import onionSkinRenderer.session as session
from onionSkinRenderer.widgets import STYLE, Stepper, Segmented, on_button_style

_BAR = None


def show():
    global _BAR
    s = session.get()
    try:
        if _BAR is not None and _BAR.isVisible():
            _BAR.raise_()
            return _BAR
    except RuntimeError:
        pass
    _BAR = MiniBar(s)
    _BAR.show()
    s.prefs["miniBar"] = True
    s.saveSoon()
    return _BAR


def current():
    return _BAR


def close():
    global _BAR
    try:
        if _BAR is not None:
            _BAR.close()
    except RuntimeError:
        pass
    _BAR = None


class MiniBar(QtWidgets.QWidget):
    def __init__(self, s, parent=None):
        super(MiniBar, self).__init__(parent or maya_main_window())
        self.s = s
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("onionSkinMiniBar")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE + "QWidget#onionSkinMiniBar { border:1px solid #222; }")
        self._dragFrom = None

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 6, 4)
        lay.setSpacing(5)
        self.handle = QtWidgets.QLabel("⋮⋮")
        self.handle.setToolTip("Drag here to move the bar")
        self.handle.setCursor(QtCore.Qt.SizeAllCursor)
        self.on_btn = QtWidgets.QPushButton("ON")
        self.on_btn.setToolTip("Onion skin on / off in the view you last clicked")
        self.on_btn.clicked.connect(lambda *_: s.toggle())
        self.before_stp = Stepper(0, session.MAX_GHOSTS, tip="Ghosts before your frame")
        self.after_stp = Stepper(0, session.MAX_GHOSTS, tip="Ghosts after your frame")
        self.before_stp.valueChanged.connect(s.setBefore)
        self.after_stp.valueChanged.connect(s.setAfter)
        self.mode_seg = Segmented([("keys", "Keys"), ("main", "Main"), ("frames", "Frames")],
                                  ["Ghosts on the keys", "Only main keys (no breakdowns)", "Ghosts every few frames"])
        self.mode_seg.picked.connect(s.setMode)
        fill = QtWidgets.QPushButton("Fill")
        fill.setToolTip("Take the pictures of the ghosts now (Esc stops)")
        fill.clicked.connect(lambda *_: _later(s.fill))
        self.arcs_btn = QtWidgets.QPushButton("Arcs")
        self.arcs_btn.setCheckable(True)
        self.arcs_btn.setProperty("chip", True)
        self.arcs_btn.setToolTip("Show / hide the arcs (choose the points in the window's Arcs tab)")
        self.arcs_btn.clicked.connect(lambda on: s.setArcs("arcsShow", bool(on)))
        gear = QtWidgets.QPushButton("⚙")
        gear.setToolTip("Open the onion skin window")
        gear.clicked.connect(self.openWindow)
        for b in (fill, gear):
            b.setMaximumWidth(44 if b is fill else 30)
        x = QtWidgets.QToolButton()
        x.setAutoRaise(True)
        x.setText("✕")
        x.setToolTip("Close the mini bar (the onion skin stays as it is)")
        x.clicked.connect(self.closeByUser)

        def note(t):
            lab = QtWidgets.QLabel(t)
            lab.setProperty("note", True)
            return lab

        def sep():
            f = QtWidgets.QFrame()
            f.setFrameShape(QtWidgets.QFrame.VLine)
            f.setStyleSheet("color:#666;")
            return f

        for w in (self.handle, self.on_btn, sep(), note("Before"), self.before_stp, note("After"), self.after_stp,
                  sep(), self.mode_seg, sep(), fill, self.arcs_btn, gear, x):
            lay.addWidget(w)
        s.listeners.append(self.refresh)
        self.refresh()
        self.adjustSize()
        pos = s.prefs.get("miniBarPos")
        if pos:
            self.move(int(pos[0]), int(pos[1]))
        else:
            parent = self.parentWidget()
            if parent is not None:
                g = parent.geometry()
                self.move(g.x() + (g.width() - self.width()) // 2, g.y() + 90)

    def refresh(self):
        s, p = self.s, self.s.prefs
        on = s.isOn()
        self.on_btn.setText("ON" if on else "OFF")
        self.on_btn.setStyleSheet(on_button_style(on, big=False))
        self.before_stp.setValue(p["before"])
        self.after_stp.setValue(p["after"])
        self.mode_seg.setValue(p["mode"])
        self.arcs_btn.blockSignals(True)
        self.arcs_btn.setChecked(bool(p["arcsShow"]))
        self.arcs_btn.blockSignals(False)
        self.arcs_btn.setEnabled(bool(s.o.arcs.points) or bool(p["arcsShow"]))

    def openWindow(self, *_):
        import onionSkinRenderer.window as window
        window.show()

    # drag by the handle
    def mousePressEvent(self, e):
        if self.handle.geometry().contains(e.pos()):
            self._dragFrom = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragFrom is not None:
            self.move(e.globalPos() - self._dragFrom)

    def mouseReleaseEvent(self, _e):
        if self._dragFrom is not None:
            self._dragFrom = None
            self.s.prefs["miniBarPos"] = [self.x(), self.y()]
            self.s.saveSoon()

    def closeByUser(self, *_):
        self.s.prefs["miniBar"] = False
        self.s.saveSoon()
        self.close()

    def closeEvent(self, event):
        try:
            if self.refresh in self.s.listeners:
                self.s.listeners.remove(self.refresh)
        except Exception:
            pass
        global _BAR
        if _BAR is self:
            _BAR = None
        super(MiniBar, self).closeEvent(event)


def _later(fn):
    try:
        import maya.cmds as cmds
        cmds.evalDeferred(fn, lowestPriority=True)
    except Exception:
        fn()
