"""
The Review Notes window (the Review shelf button): draw, write, save, and the list of the scene's notes.

    import reviewNotes.window as w; w.show()
"""

import os

import maya.cmds as cmds

from reviewNotes import controller, drawtool, sketch, store
from reviewNotes.qt import QtCore, QtGui, QtWidgets, maya_main_window

WINDOW = None
COLOURS = (("Red", (1.0, 0.30, 0.26)), ("Yellow", (1.0, 0.82, 0.25)), ("Green", (0.30, 0.89, 0.63)),
           ("Blue", (0.50, 0.71, 1.0)), ("White", (1.0, 1.0, 1.0)))
TOOL_NAMES = (("pen", "Pen"), ("curve", "Curve"), ("arrow", "Arrow"), ("circle", "Circle"), ("eraser", "Eraser"))
STATUS_NEXT = {"open": "in progress", "in progress": "done", "done": "open"}
TOOL_HINTS = {
    "pen": "Drag to draw a free line.",
    "curve": "Click = corner, click-drag = smooth point. Click the first point to close. Drag points or handles "
             "to adjust; Ctrl-drag breaks a handle. End curve when done.",
    "arrow": "Drag from the tail to the head.",
    "circle": "Drag across the box the circle fits in.",
    "eraser": "Click on a stroke of this drawing to remove it.",
}
STYLE = """
QWidget#reviewNotesWindow { background: #3a3a3a; }
QLabel#title { font-weight: 600; font-size: 13px; }
QLabel#hint, QLabel#path { color: #9a9a9a; }
QPushButton { padding: 4px 8px; }
QPushButton:checked { background: #5285a6; color: white; }
QPushButton#draw { padding: 7px; font-weight: 600; }
QPushButton#draw:checked { background: #a8382f; }
QPushButton#save { background: #a8382f; color: white; font-weight: 600; }
"""


def _frames(n):
    end = n["frame"] + n["hold"] - 1
    return str(n["frame"]) if end == n["frame"] else "%d-%d" % (n["frame"], end)


class ReviewWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ReviewWindow, self).__init__(parent)
        self.setObjectName("reviewNotesWindow")
        self.setWindowTitle("Review Notes")
        self.setWindowFlags(QtCore.Qt.Tool)
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(340)
        self._stamp = None
        self._notes = []
        self._build()
        drawtool._listeners.append(self.sync)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.sync()
        self.reload()

    # ---------------- layout ----------------
    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.draw_btn = QtWidgets.QPushButton("Draw on the view")
        self.draw_btn.setObjectName("draw")
        self.draw_btn.setCheckable(True)
        self.draw_btn.clicked.connect(self._toggle_draw)
        lay.addWidget(self.draw_btn)
        self.state = QtWidgets.QLabel("")
        self.state.setObjectName("hint")
        self.state.setWordWrap(True)
        lay.addWidget(self.state)

        tools = QtWidgets.QHBoxLayout()
        tools.setSpacing(2)
        self.tool_group = QtWidgets.QButtonGroup(self)
        self.tool_buttons = {}
        for key, label in TOOL_NAMES:
            b = QtWidgets.QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self._set_tool(k))
            self.tool_group.addButton(b)
            self.tool_buttons[key] = b
            tools.addWidget(b)
        lay.addLayout(tools)
        self.tool_hint = QtWidgets.QLabel("")
        self.tool_hint.setObjectName("hint")
        self.tool_hint.setWordWrap(True)
        lay.addWidget(self.tool_hint)

        row = QtWidgets.QHBoxLayout()
        self.colour_buttons = []
        for name, rgb in COLOURS:
            b = QtWidgets.QPushButton("")
            b.setToolTip(name)
            b.setCheckable(True)
            b.setFixedSize(22, 22)
            b.setStyleSheet("QPushButton { background: rgb(%d,%d,%d); border-radius: 11px; border: 2px solid #222; }"
                            "QPushButton:checked { border: 2px solid white; }" % tuple(int(c * 255) for c in rgb))
            b.clicked.connect(lambda _=False, c=rgb, btn=b: self._set_colour(c, btn))
            self.colour_buttons.append(b)
            row.addWidget(b)
        row.addSpacing(10)
        row.addWidget(QtWidgets.QLabel("Size"))
        self.size = QtWidgets.QSpinBox()
        self.size.setRange(1, 10)
        self.size.setValue(sketch.SKETCH.width)
        self.size.valueChanged.connect(self._set_size)
        row.addWidget(self.size)
        row.addStretch(1)
        self.end_curve_btn = QtWidgets.QPushButton("End curve")
        self.end_curve_btn.clicked.connect(drawtool.end_curve)
        row.addWidget(self.end_curve_btn)
        lay.addLayout(row)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setPlaceholderText("What should change here?")
        self.text.setFixedHeight(60)
        lay.addWidget(self.text)
        row = QtWidgets.QHBoxLayout()
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems(list(store.TYPES))
        row.addWidget(self.kind)
        row.addWidget(QtWidgets.QLabel("for"))
        self.hold = QtWidgets.QSpinBox()
        self.hold.setRange(1, 200)
        self.hold.setValue(6)
        row.addWidget(self.hold)
        row.addWidget(QtWidgets.QLabel("frames"))
        row.addStretch(1)
        clear = QtWidgets.QPushButton("Clear")
        clear.setToolTip("Throw away the drawing (not saved yet)")
        clear.clicked.connect(drawtool.clear)
        row.addWidget(clear)
        save = QtWidgets.QPushButton("Save note")
        save.setObjectName("save")
        save.clicked.connect(self.save)
        row.addWidget(save)
        lay.addLayout(row)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        lay.addWidget(line)

        row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Notes")
        title.setObjectName("title")
        row.addWidget(title)
        row.addStretch(1)
        self.filter = QtWidgets.QComboBox()
        self.filter.addItems(["All", "Open", "This camera"])
        self.filter.currentIndexChanged.connect(lambda *_: self._fill())
        row.addWidget(self.filter)
        lay.addLayout(row)

        self.list = QtWidgets.QTreeWidget()
        self.list.setHeaderLabels(["Frames", "Camera", "Type", "Status", "Note"])
        self.list.setRootIsDecorated(False)
        self.list.setAlternatingRowColors(True)
        self.list.setMinimumHeight(160)
        self.list.itemDoubleClicked.connect(lambda *_: self._go())
        lay.addWidget(self.list, 1)

        row = QtWidgets.QHBoxLayout()
        for label, fn, tip in (("Go to", self._go, "Its frame, through its camera (or double-click the note)"),
                               ("Status", self._next_status, "open > in progress > done"),
                               ("Delete", self._delete, "Remove the note from the review file")):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        self.nearby = QtWidgets.QCheckBox("Nearby")
        self.nearby.setToolTip("Notes a few frames before / after, faint (orange coming, blue passed)")
        self.nearby.setChecked(True)
        self.nearby.toggled.connect(lambda v: self._node_attr("showNearby", v))
        row.addWidget(self.nearby)
        self.only_open = QtWidgets.QCheckBox("Only open")
        self.only_open.toggled.connect(lambda v: self._node_attr("onlyOpen", v))
        row.addWidget(self.only_open)
        lay.addLayout(row)

        self.path = QtWidgets.QLabel("")
        self.path.setObjectName("path")
        self.path.setWordWrap(True)
        lay.addWidget(self.path)

        self.tool_buttons[sketch.SKETCH.tool].setChecked(True)
        self.colour_buttons[0].setChecked(True)
        shortcut = getattr(QtWidgets, "QShortcut", None) or QtGui.QShortcut      # PySide2 / PySide6
        shortcut(QtGui.QKeySequence("Ctrl+Return"), self, self.save)
        self._read_node_settings()

    def _read_node_settings(self):
        shape = controller.node()
        if shape:
            for box, attr in ((self.nearby, "showNearby"), (self.only_open, "onlyOpen")):
                box.blockSignals(True)
                box.setChecked(bool(cmds.getAttr("%s.%s" % (shape, attr))))
                box.blockSignals(False)

    # ---------------- drawing ----------------
    def _toggle_draw(self):
        drawtool.on() if self.draw_btn.isChecked() else drawtool.off()
        self.sync()

    def _set_tool(self, key):
        drawtool.set_tool(key)
        if not drawtool.is_on():
            drawtool.on()

    def _set_colour(self, rgb, button):
        for b in self.colour_buttons:
            b.setChecked(b is button)
        sketch.SKETCH.color = list(rgb)

    def _set_size(self, v):
        sketch.SKETCH.width = int(v)

    def save(self):
        note = drawtool.save(self.text.toPlainText(), self.kind.currentText(), self.hold.value())
        if note:
            self.text.clear()
            self.reload(force=True)

    def sync(self):
        """The buttons and the line under Draw follow what's happening."""
        s = sketch.SKETCH
        on = drawtool.is_on()
        self.draw_btn.setChecked(on)
        self.draw_btn.setText("Drawing - click to stop" if on else "Draw on the view")
        self.tool_buttons[s.tool].setChecked(True)
        self.tool_hint.setText(TOOL_HINTS[s.tool] if on else "")
        self.end_curve_btn.setEnabled(s.curve is not None)
        n = len(s.all_strokes())
        if n:
            self.state.setText("Not saved yet: %d stroke(s) on %s, frame %s. Write a line, then Save note."
                               % (n, s.camera, s.frame))
        elif on:
            self.state.setText("Draw in the view you want the note on (Alt still moves the camera).")
        else:
            self.state.setText("")

    # ---------------- the notes ----------------
    def _tick(self):
        if not self.isVisible():
            return
        self.sync()
        self.reload()

    def reload(self, force=False):
        path = controller.review_path()
        stamp = (path, os.path.getmtime(path) if path and os.path.isfile(path) else None)
        if stamp == self._stamp and not force:
            return
        self._stamp = stamp
        try:
            self._notes = store.read(path)["notes"] if path else []
            self.path.setText(path or "Save the scene first: the notes go in a file next to it.")
        except store.ReviewFileError as e:
            self._notes = []
            self.path.setText(str(e))
        self._fill()

    def _fill(self):
        mode = self.filter.currentText()
        cam = controller.current_camera()
        keep = self._selected_id()
        self.list.clear()
        for n in sorted(self._notes, key=lambda n: (n["frame"], n["id"])):
            if mode == "Open" and n["status"] == "done":
                continue
            if mode == "This camera" and n["camera"] != cam:
                continue
            item = QtWidgets.QTreeWidgetItem([_frames(n), n["camera"], n["type"], n["status"],
                                              n["text"] or "(drawing only)"])
            item.setData(0, QtCore.Qt.UserRole, n["id"])
            item.setToolTip(4, n["text"])
            if n["status"] == "done":
                for c in range(5):
                    item.setForeground(c, QtGui.QBrush(QtGui.QColor(130, 130, 130)))
            self.list.addTopLevelItem(item)
            if n["id"] == keep:
                self.list.setCurrentItem(item)
        for c in range(4):
            self.list.resizeColumnToContents(c)

    def _selected_id(self):
        item = self.list.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def _selected(self):
        nid = self._selected_id()
        return next((n for n in self._notes if n["id"] == nid), None)

    def _go(self):
        n = self._selected()
        if not n:
            return
        cmds.currentTime(n["frame"])
        if cmds.objExists(n["camera"]):
            panel = controller.current_panel()
            if panel:
                cmds.lookThru(panel, n["camera"])
        else:
            controller._tell("the camera %s isn't in this scene." % n["camera"], warn=True)

    def _next_status(self):
        n = self._selected()
        if n:
            store.update_note(controller.review_path(), n["id"], status=STATUS_NEXT[n["status"]])
            self.reload(force=True)

    def _delete(self):
        n = self._selected()
        if not n:
            return
        ask = QtWidgets.QMessageBox.question(self, "Review Notes", "Delete note %s (%s, frames %s)?"
                                             % (n["id"], n["camera"], _frames(n)))
        if ask == QtWidgets.QMessageBox.Yes:
            store.delete_note(controller.review_path(), n["id"])
            self.reload(force=True)

    def _node_attr(self, attr, value):
        shape = controller.node()
        if shape:
            with controller.NoUndo():
                cmds.setAttr("%s.%s" % (shape, attr), bool(value))

    def closeEvent(self, event):
        if self.sync in drawtool._listeners:
            drawtool._listeners.remove(self.sync)
        self.timer.stop()
        super(ReviewWindow, self).closeEvent(event)


def show():
    global WINDOW
    close()
    WINDOW = ReviewWindow(maya_main_window())
    WINDOW.show()
    WINDOW.raise_()
    return WINDOW


def close():
    global WINDOW
    if WINDOW is not None:
        try:
            WINDOW.close()
            WINDOW.deleteLater()
        except RuntimeError:
            pass
    WINDOW = None
