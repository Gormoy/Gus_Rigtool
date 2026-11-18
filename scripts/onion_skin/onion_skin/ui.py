"""
Onion Skin - the window. Laid out like the onion skin window you used (what to ghost, past / next, look), with
Live on by default.
"""

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
except ImportError:                                         # Maya 2025+
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance

from onion_skin import core, live

WINDOW = {"w": None}
TITLE = "Onion Skin"


def _maya_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None


def _later(fn):
    """Run once the click is over (heavy work inside a click can crash Maya)."""
    return lambda *a: cmds.evalDeferred(fn, lowestPriority=True)


class Window(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent or _maya_window())
        self.setWindowFlags(QtCore.Qt.Window)
        self.setWindowTitle(TITLE)
        self.setObjectName("onionSkinWindow")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.resize(320, 520)
        self._build()
        self._load()
        live.STATE["status"] = self.say
        live.start()

    # ------------------------------------------------------------ layout
    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)

        box = QtWidgets.QGroupBox("What to ghost")
        b = QtWidgets.QVBoxLayout(box)
        hint = QtWidgets.QLabel("A control = its whole character. A mesh or group = those meshes. "
                                "Several characters at once.")
        hint.setWordWrap(True)
        b.addWidget(hint)
        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        b.addWidget(self.list)
        row = QtWidgets.QHBoxLayout()
        for label, fn in (("Add selected", self.add), ("Remove", self.remove), ("Clear list", self.clear_list)):
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(fn)
            row.addWidget(btn)
        b.addLayout(row)
        lay.addWidget(box)

        box = QtWidgets.QGroupBox("Ghosts")
        g = QtWidgets.QFormLayout(box)
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(["Past / next keys", "Every N frames"])
        self.past = QtWidgets.QSpinBox()
        self.past.setRange(0, 5)
        self.next = QtWidgets.QSpinBox()
        self.next.setRange(0, 5)
        self.step = QtWidgets.QSpinBox()
        self.step.setRange(1, 50)
        g.addRow("Show", self.mode)
        g.addRow("Past", self.past)
        g.addRow("Next", self.next)
        g.addRow("Every N frames", self.step)
        lay.addWidget(box)

        box = QtWidgets.QGroupBox("Look")
        k = QtWidgets.QFormLayout(box)
        self.past_color = QtWidgets.QPushButton()
        self.next_color = QtWidgets.QPushButton()
        self.opacity = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity.setRange(5, 100)
        self.fade = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.fade.setRange(10, 100)
        k.addRow("Past colour", self.past_color)
        k.addRow("Next colour", self.next_color)
        k.addRow("Opacity", self.opacity)
        k.addRow("Fade further away", self.fade)
        lay.addWidget(box)

        row = QtWidgets.QHBoxLayout()
        self.live = QtWidgets.QCheckBox("Live")
        self.live.setToolTip("Update when you stop on a frame (never during playback).")
        self.hide_box = QtWidgets.QCheckBox("Hide (for playblasts)")
        row.addWidget(self.live)
        row.addWidget(self.hide_box)
        lay.addLayout(row)
        row = QtWidgets.QHBoxLayout()
        upd = QtWidgets.QPushButton("Update")
        upd.clicked.connect(_later(self.update_now))
        clr = QtWidgets.QPushButton("Clear ghosts")
        clr.clicked.connect(_later(self.clear_ghosts))
        row.addWidget(upd)
        row.addWidget(clr)
        lay.addLayout(row)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.mode.currentIndexChanged.connect(self._changed)
        for w in (self.past, self.next, self.step):
            w.valueChanged.connect(self._changed)
        for w in (self.opacity, self.fade):
            w.sliderReleased.connect(self._changed)
        self.live.toggled.connect(self._changed)
        self.hide_box.toggled.connect(lambda v: core.set_hidden(v))
        self.past_color.clicked.connect(lambda: self._pick("past_color", self.past_color))
        self.next_color.clicked.connect(lambda: self._pick("next_color", self.next_color))

    def _load(self):
        self._loading = True
        self.mode.setCurrentIndex(0 if core.opt("mode") == "keys" else 1)
        self.past.setValue(int(core.opt("past")))
        self.next.setValue(int(core.opt("next")))
        self.step.setValue(int(core.opt("step")))
        self.opacity.setValue(int(round(float(core.opt("opacity")) * 100)))
        self.fade.setValue(int(round(float(core.opt("fade")) * 100)))
        self.live.setChecked(bool(int(core.opt("live"))))
        self._swatch(self.past_color, core.opt("past_color"))
        self._swatch(self.next_color, core.opt("next_color"))
        self.step.setEnabled(self.mode.currentIndex() == 1)
        self._loading = False
        self._refresh_list()

    # ------------------------------------------------------------ actions
    def say(self, text):
        self.status.setText(text)

    def _refresh_list(self):
        self.list.clear()
        for t in core.TARGETS:
            item = QtWidgets.QListWidgetItem(t.split("|")[-1])
            item.setData(QtCore.Qt.UserRole, t)
            self.list.addItem(item)

    def add(self):
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            self.say("select a character's control, a mesh or a group first")
            return
        new = core.add_targets(sel)
        self._refresh_list()
        self.say("added %d" % len(new) if new else "already in the list")
        cmds.evalDeferred(self.update_now, lowestPriority=True)

    def remove(self):
        picked = [i.data(QtCore.Qt.UserRole) for i in self.list.selectedItems()]
        core.remove_targets(picked)
        self._refresh_list()
        cmds.evalDeferred(self.rebuild, lowestPriority=True)

    def clear_list(self):
        core.clear(keep_targets=False)
        self._refresh_list()
        self.say("list and ghosts cleared")

    def update_now(self):
        try:
            got = core.update()
        except RuntimeError as e:
            self.say(str(e))
            return
        self._refresh_list()
        self.say(live.summary(got))

    def rebuild(self):
        if not core.TARGETS:
            core.clear(keep_targets=True)
            self.say("nothing in the list")
            return
        core.clear(keep_targets=True)
        self.update_now()

    def clear_ghosts(self):
        core.clear(keep_targets=True)
        self.say("ghosts cleared (the list is kept - Update brings them back)")

    def _changed(self, *_):
        if getattr(self, "_loading", False):
            return
        core.set_opt("mode", "keys" if self.mode.currentIndex() == 0 else "frames")
        core.set_opt("past", self.past.value())
        core.set_opt("next", self.next.value())
        core.set_opt("step", self.step.value())
        core.set_opt("opacity", self.opacity.value() / 100.0)
        core.set_opt("fade", self.fade.value() / 100.0)
        core.set_opt("live", int(self.live.isChecked()))
        self.step.setEnabled(self.mode.currentIndex() == 1)
        if core.TARGETS:
            cmds.evalDeferred(self.update_now, lowestPriority=True)

    def _swatch(self, btn, rgb):
        btn.setStyleSheet("background-color: rgb(%d, %d, %d);" % tuple(int(c * 255) for c in rgb))

    def _pick(self, name, btn):
        rgb = core.opt(name)
        got = QtWidgets.QColorDialog.getColor(QtGui.QColor.fromRgbF(*rgb), self, "Ghost colour")
        if got.isValid():
            rgb = (got.redF(), got.greenF(), got.blueF())
            core.set_opt(name, rgb)
            self._swatch(btn, rgb)
            if core.TARGETS:
                cmds.evalDeferred(self.update_now, lowestPriority=True)

    def closeEvent(self, event):
        live.stop()
        live.STATE["status"] = None
        try:
            core.clear(keep_targets=False)          # closing leaves nothing of the tool in the scene
        except Exception:
            pass
        WINDOW["w"] = None
        super(Window, self).closeEvent(event)


def show():
    w = WINDOW.get("w")
    if w is not None:
        try:
            w.close()
        except Exception:
            pass
    WINDOW["w"] = Window()
    WINDOW["w"].show()
    return WINDOW["w"]
