"""
The onion skin's window: ON / Fill / what's showing at the top, presets, then three tabs - Ghosts, Arcs,
Settings. Everything it shows lives in session.py, so the mini bar and this window always agree, and closing
the window leaves the onion skin on.
"""
from onionSkinRenderer.qt import QtCore, QtWidgets, maya_main_window
import onionSkinRenderer.session as session
import onionSkinRenderer.arcs as arcs
from onionSkinRenderer.widgets import (STYLE, Stepper, Segmented, GhostBars, Row, on_button_style, swatch_icon,
                                       group, line)

_WINDOW = None
LABEL_W = 84


def show():
    """Open the window (or bring it to the front)."""
    global _WINDOW
    s = session.get()
    try:
        if _WINDOW is not None and _WINDOW.isVisible():
            _WINDOW.raise_()
            _WINDOW.activateWindow()
            return _WINDOW
    except RuntimeError:                     # the Qt window is already gone
        pass
    _WINDOW = OnionWindow(s)
    _WINDOW.show()
    if s.prefs.get("miniBar"):
        import onionSkinRenderer.minibar as minibar
        minibar.show()
    return _WINDOW


def current():
    return _WINDOW


def close():
    global _WINDOW
    try:
        if _WINDOW is not None:
            _WINDOW.close()
    except RuntimeError:
        pass
    _WINDOW = None


class OnionWindow(QtWidgets.QWidget):
    def __init__(self, s, parent=None):
        super(OnionWindow, self).__init__(parent or maya_main_window())
        self.s = s
        self.setWindowFlags(QtCore.Qt.Window)
        self.setObjectName("onionSkinWindow")
        self.setWindowTitle("Onion Skin")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.resize(410, 800)
        self._build()
        s.listeners.append(self.refresh)
        self.refresh()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self.refreshStatus)
        self._timer.start()

    # ------------------------------------------------------------------ building
    def _build(self):
        s = self.s
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        self.on_btn = QtWidgets.QPushButton()
        self.on_btn.setToolTip("Click once in your camera view, then here: the onion skin shows in that view. "
                               "Click again to turn it off.")
        self.on_btn.clicked.connect(lambda *_: s.toggle())
        self.fill_btn = QtWidgets.QPushButton("Fill")
        self.fill_btn.setToolTip("Take the pictures of the ghosts (and arc frames) now. Esc stops it.")
        self.fill_btn.clicked.connect(lambda *_: self._later(s.fill))
        root.addLayout(line(self.on_btn, self.fill_btn))
        self.on_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.status_lbl = QtWidgets.QLabel()
        self.status_lbl.setProperty("status", True)
        self.status_lbl.setWordWrap(True)
        root.addWidget(self.status_lbl)
        self.camera_lbl = QtWidgets.QLabel()
        self.camera_lbl.setProperty("warn", True)
        self.camera_lbl.setWordWrap(True)
        root.addWidget(self.camera_lbl)

        # presets
        self.presets_box = QtWidgets.QWidget()
        self.presets_lay = QtWidgets.QGridLayout(self.presets_box)
        self.presets_lay.setContentsMargins(0, 0, 0, 0)
        self.presets_lay.setSpacing(4)
        root.addLayout(line("Preset", self.presets_box, label_width=48))

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._ghosts_tab(), "Ghosts")
        self.tabs.addTab(self._arcs_tab(), "Arcs")
        self.tabs.addTab(self._settings_tab(), "Settings")

    def _scroll(self, inner):
        sc = QtWidgets.QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QtWidgets.QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        sc.setWidget(inner)
        return sc

    def _ghosts_tab(self):
        s = self.s
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(2, 6, 2, 2)

        box, lay = group("All ghosts")
        self.opacity_sld = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity_sld.setRange(5, 100)
        self.opacity_sld.setToolTip("All the ghosts lighter or stronger at once (each ghost's own bar still counts)")
        self.opacity_val = QtWidgets.QLabel()
        self.opacity_val.setFixedWidth(28)
        self.opacity_sld.valueChanged.connect(lambda val: (self.opacity_val.setText(str(val)),
                                                           s.setGhostOpacity(val)))
        lay.addLayout(line("Opacity", self.opacity_sld, self.opacity_val, label_width=LABEL_W))
        self.hide_chk = QtWidgets.QCheckBox("Hide ghosts while playing (playback as fast as without)")
        self.hide_chk.setToolTip("While Maya plays, no ghosts are drawn and no pictures taken; they come back when "
                                 "you stop. Arcs still show.")
        self.hide_chk.toggled.connect(lambda on: s.setOption("hideWhilePlaying", bool(on)))
        lay.addWidget(self.hide_chk)
        v.addWidget(box)

        box, lay = group("Before / After")
        self.mode_seg = Segmented([("keys", "Keys"), ("main", "Main keys"), ("frames", "Frames")],
                                  ["Ghosts on the characters' keys", "Only key poses - breakdowns skipped "
                                   "(keys set with Key > Breakdown)", "Ghosts every few frames"])
        self.mode_seg.picked.connect(s.setMode)
        lay.addLayout(line("Ghosts on", self.mode_seg, None, label_width=LABEL_W))
        self.before_stp = Stepper(0, session.MAX_GHOSTS, tip="How many ghosts before your frame")
        self.after_stp = Stepper(0, session.MAX_GHOSTS, tip="How many ghosts after your frame")
        self.before_stp.valueChanged.connect(s.setBefore)
        self.after_stp.valueChanged.connect(s.setAfter)
        lay.addLayout(line("Before", self.before_stp, None, "After", self.after_stp, label_width=LABEL_W))
        self.every_stp = Stepper(1, 24, tip="Frames mode: a ghost every N frames (4 = 4, 8, 12... frames away)")
        self.every_stp.valueChanged.connect(s.setEvery)
        self.every_note = QtWidgets.QLabel("only for Frames")
        self.every_note.setProperty("note", True)
        lay.addLayout(line("Every (frames)", self.every_stp, self.every_note, None, label_width=LABEL_W))
        self.fade_sld = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.fade_sld.setRange(10, 100)
        self.fade_sld.setToolTip("Each ghost further from now is lighter. 100 = no fading.")
        self.fade_val = QtWidgets.QLabel()
        self.fade_val.setFixedWidth(28)
        self.fade_sld.valueChanged.connect(lambda val: (self.fade_val.setText(str(val)), s.setFade(val / 100.0)))
        lay.addLayout(line("Fade further", self.fade_sld, self.fade_val, label_width=LABEL_W))
        self.look_seg = Segmented([(0, "Shaded"), (1, "Flat colour"), (2, "Outline")],
                                  ["Like Harmony's original colours", "Coloured - flat", "Coloured outline"])
        self.look_seg.picked.connect(s.setLook)
        lay.addLayout(line("Look", self.look_seg, None, label_width=LABEL_W))
        v.addWidget(box)

        box, lay = group("Characters")
        self.chars_lay = QtWidgets.QVBoxLayout()
        self.chars_lay.setSpacing(3)
        lay.addLayout(self.chars_lay)
        add = QtWidgets.QPushButton("+ Add selected character")
        add.setToolTip("Select any control of a character (or its meshes), then press this. Two characters: "
                       "one control of each.")
        add.clicked.connect(lambda *_: s.addSelectedCharacters())
        clear = QtWidgets.QPushButton("Clear")
        clear.clicked.connect(s.clearCharacters)
        lay.addLayout(line(add, clear))
        add.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        v.addWidget(box)

        box, lay = group("Light table")
        self.light_chk = QtWidgets.QCheckBox("The others see-through (the one you animate stays solid)")
        self.light_chk.setToolTip("Like a light table: the characters you're not animating become see-through. "
                                  "The one you animate follows your selection.")
        self.light_chk.toggled.connect(lambda on: s.setLight("lightTable", bool(on)))
        lay.addWidget(self.light_chk)
        self.light_sld = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.light_sld.setRange(10, 95)
        self.light_sld.setToolTip("How see-through the others are")
        self.light_val = QtWidgets.QLabel()
        self.light_val.setFixedWidth(28)
        self.light_sld.valueChanged.connect(lambda val: (self.light_val.setText(str(val)),
                                                         s.setLight("lightStrength", val / 100.0)))
        lay.addLayout(line("See-through", self.light_sld, self.light_val, label_width=LABEL_W))
        self.ghostsOf_seg = Segmented([("all", "All characters"), ("active", "Only the one I animate")],
                                      ["Every character's ghosts", "The others' ghosts very faint"])
        self.ghostsOf_seg.picked.connect(lambda v: s.setLight("ghostsOf", v))
        lay.addLayout(line("Ghosts of", self.ghostsOf_seg, None, label_width=LABEL_W))
        self.active_lbl = QtWidgets.QLabel()
        self.active_lbl.setProperty("note", True)
        self.active_lbl.setWordWrap(True)
        lay.addWidget(self.active_lbl)
        v.addWidget(box)

        box, lay = group("Colours")
        self.colour_btns = []
        row = []
        for name, past, future in session.COLOURS:
            b = QtWidgets.QPushButton(name)
            b.setProperty("chip", True)
            b.setCheckable(True)
            b.setIcon(swatch_icon([past, future]))
            b.setToolTip("Past ghosts %s, next ghosts %s" % tuple(name.lower().split(" / ")))
            b.clicked.connect(lambda *_a, p=past, f=future: s.setColours(p, f))
            self.colour_btns.append((b, past, future))
            row.append(b)
        self.mine_btn = QtWidgets.QPushButton("Mine...")
        self.mine_btn.setProperty("chip", True)
        self.mine_btn.setCheckable(True)
        self.mine_btn.setToolTip("Pick your own: first the past colour, then the next colour")
        self.mine_btn.clicked.connect(self.pickColours)
        lay.addLayout(line(*(row + [self.mine_btn, None])))
        v.addWidget(box)

        self.adv_btn = QtWidgets.QToolButton()
        self.adv_btn.setCheckable(True)
        self.adv_btn.setAutoRaise(True)
        self.adv_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.adv_btn.setArrowType(QtCore.Qt.RightArrow)
        self.adv_btn.setText("Advanced: opacity of each ghost")
        v.addWidget(self.adv_btn)
        self.bars = GhostBars()
        self.bars.opacityChanged.connect(s.setOpacity)
        self.bars_note = QtWidgets.QLabel("Drag a bar up or down; all the way down = that ghost off.")
        self.bars_note.setProperty("note", True)
        v.addWidget(self.bars)
        v.addWidget(self.bars_note)

        def advanced(on):
            self.adv_btn.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)
            self.bars.setVisible(on)
            self.bars_note.setVisible(on)
        self.adv_btn.toggled.connect(advanced)
        advanced(False)
        v.addStretch(1)
        return self._scroll(page)

    def _arcs_tab(self):
        s = self.s
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(2, 6, 2, 2)
        box, lay = group("Points")
        self.points_lay = QtWidgets.QVBoxLayout()
        self.points_lay.setSpacing(3)
        lay.addLayout(self.points_lay)
        add = QtWidgets.QPushButton("+ Add selected points")
        add.setToolTip("Select vertices (nose tip, ear tips) or controls, then press this. Up to %d."
                       % arcs.MAX_POINTS)
        add.clicked.connect(lambda *_: s.addArcPoints())
        clear = QtWidgets.QPushButton("Clear")
        clear.clicked.connect(s.clearArcPoints)
        add.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        lay.addLayout(line(add, clear))
        v.addWidget(box)

        box, lay = group("Range")
        self.arcBefore_stp = Stepper(0, 200, tip="How many frames back the line goes")
        self.arcAfter_stp = Stepper(0, 200, tip="How many frames forward the line goes")
        self.arcBefore_stp.valueChanged.connect(lambda n: s.setArcs("arcsBefore", n))
        self.arcAfter_stp.valueChanged.connect(lambda n: s.setArcs("arcsAfter", n))
        lay.addLayout(line("Before", self.arcBefore_stp, None, "After", self.arcAfter_stp, label_width=LABEL_W))
        self.dots_seg = Segmented([(n, str(n)) for n in (1, 2, 3, 4)])
        self.dots_seg.picked.connect(lambda n: s.setArcs("arcsDotEvery", n))
        dots_note = QtWidgets.QLabel("frames")
        self.dots_seg.setToolTip("1 = a dot on every frame. Keys always get a bigger dot, your frame a white one.")
        dots_note.setProperty("note", True)
        lay.addLayout(line("A dot every", self.dots_seg, dots_note, None, label_width=LABEL_W))
        self.arcsShow_chk = QtWidgets.QCheckBox("Show arcs")
        self.arcsShow_chk.toggled.connect(lambda on: s.setArcs("arcsShow", bool(on)))
        lay.addWidget(self.arcsShow_chk)
        v.addWidget(box)
        note = QtWidgets.QLabel("Each point has its own eye, so you can hide one arc without losing it. When you "
                                "change a key, the line is recorded again by itself.")
        note.setProperty("note", True)
        note.setWordWrap(True)
        v.addWidget(note)
        v.addStretch(1)
        return self._scroll(page)

    def _settings_tab(self):
        s = self.s
        page = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(page)
        v.setContentsMargins(2, 6, 2, 2)
        box, lay = group("Speed")
        self.auto_chk = QtWidgets.QCheckBox("Auto fill when you stop on a frame")
        self.auto_chk.setToolTip("The ghosts you need are filled by themselves (never during playback).")
        self.auto_chk.toggled.connect(lambda on: s.setOption("autoFill", bool(on)))
        self.behind_chk = QtWidgets.QCheckBox("Draw behind the character")
        self.behind_chk.setToolTip("Off: ghosts in front of the character, like Harmony.")
        self.behind_chk.toggled.connect(lambda on: s.setOption("drawBehind", bool(on)))
        for w in (self.auto_chk, self.behind_chk):
            lay.addWidget(w)
        v.addWidget(box)

        box, lay = group("Other")
        pin = QtWidgets.QPushButton("+ This frame")
        pin.setToolTip("Pin this frame: its ghost stays wherever you go (in the pinned colour).")
        pin.clicked.connect(lambda *_: s.pinFrame())
        unpin = QtWidgets.QPushButton("Clear")
        unpin.clicked.connect(s.clearPinned)
        lay.addLayout(line("Pinned frames", pin, unpin, None, label_width=LABEL_W))
        self.pinned_lbl = QtWidgets.QLabel()
        self.pinned_lbl.setProperty("note", True)
        lay.addWidget(self.pinned_lbl)
        self.outline_spn = QtWidgets.QSpinBox()
        self.outline_spn.setRange(1, 20)
        self.outline_spn.setToolTip("Thickness of the Outline look, in pixels")
        self.outline_spn.valueChanged.connect(lambda n: s.setOption("outlineWidth", int(n)))
        lay.addLayout(line("Outline width", self.outline_spn, None, label_width=LABEL_W))
        self.buffer_spn = QtWidgets.QSpinBox()
        self.buffer_spn.setRange(10, 2000)
        self.buffer_spn.setToolTip("How many frame pictures are kept in memory. More = fewer refills, more memory.")
        self.buffer_spn.valueChanged.connect(lambda n: s.setOption("maxBuffer", int(n)))
        forget = QtWidgets.QPushButton("Forget pictures")
        forget.setToolTip("Throw away all the ghost pictures (they're taken again when needed)")
        forget.clicked.connect(lambda *_: (s.o.clearOnionSkinBuffer(), s.changed()))
        lay.addLayout(line("Pictures kept", self.buffer_spn, forget, None, label_width=LABEL_W))
        pb = QtWidgets.QPushButton("Playblast with onion skins")
        pb.setToolTip("A pencil test of the playback range with the ghosts and arcs in it.")
        pb.clicked.connect(lambda *_: self._later(s.playblast))
        lay.addWidget(pb)
        mini = QtWidgets.QPushButton("Show the mini bar")
        mini.setToolTip("A small bar over the viewport with ON, Before / After, Keys / Frames, Fill and Arcs. "
                        "You can close this window and keep using it.")
        mini.clicked.connect(self.showMiniBar)
        lay.addWidget(mini)
        v.addWidget(box)
        v.addStretch(1)
        return self._scroll(page)

    # ------------------------------------------------------------------ actions
    def _later(self, fn):
        """Heavy work runs once the click is over (heavy work inside a click can crash Maya)."""
        try:
            import maya.cmds as cmds
            cmds.evalDeferred(fn, lowestPriority=True)
        except Exception:
            fn()

    def showMiniBar(self, *_):
        import onionSkinRenderer.minibar as minibar
        minibar.show()

    def pickColours(self, *_):
        p = self.s.prefs
        past = QtWidgets.QColorDialog.getColor(_qcolor(p["pastTint"]), self, "Colour of the PAST ghosts")
        if not past.isValid():
            self.refresh()
            return
        future = QtWidgets.QColorDialog.getColor(_qcolor(p["futureTint"]), self, "Colour of the NEXT ghosts")
        if not future.isValid():
            self.refresh()
            return
        self.s.setColours(past.getRgb()[:3], future.getRgb()[:3])

    def savePreset(self, *_):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save preset", "Name for these settings:")
        if ok and name:
            if not self.s.savePreset(name):
                QtWidgets.QMessageBox.information(self, "Save preset", "That name is taken by a built-in preset.")

    def presetMenu(self, name, button, pos):
        if self.s.isBuiltin(name):
            return
        menu = QtWidgets.QMenu(self)
        act = menu.addAction("Delete '%s'" % name)
        if menu.exec_(button.mapToGlobal(pos)) is act:
            self.s.deletePreset(name)

    # ------------------------------------------------------------------ refresh from the session
    def refresh(self):
        s, p = self.s, self.s.prefs
        on = s.isOn()
        self.on_btn.setText("Onion skin ON in this view" if on else "Onion skin OFF - click to turn ON")
        self.on_btn.setStyleSheet(on_button_style(on))
        self.refreshStatus()

        # presets
        _clear(self.presets_lay)
        flow = []
        for name in s.presetNames():
            b = QtWidgets.QPushButton(name)
            b.setProperty("chip", True)
            b.setCheckable(True)
            b.setChecked(name == p.get("preset"))
            b.setToolTip("One click: " + _preset_text(name, s))
            b.clicked.connect(lambda *_a, n=name: self.s.applyPreset(n))
            if not s.isBuiltin(name):
                b.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda pos, n=name, btn=b: self.presetMenu(n, btn, pos))
            flow.append(b)
        save = QtWidgets.QPushButton("+ Save mine")
        save.setProperty("chip", True)
        save.setToolTip("Keep the current Ghosts and Arcs settings as a preset (right-click yours to delete)")
        save.clicked.connect(self.savePreset)
        flow.append(save)
        for n, b in enumerate(flow):
            self.presets_lay.addWidget(b, n // 3, n % 3)

        # ghosts
        self.mode_seg.setValue(p["mode"])
        self.before_stp.setValue(p["before"])
        self.after_stp.setValue(p["after"])
        self.every_stp.setValue(p["every"])
        frames = p["mode"] == "frames"
        self.every_stp.setEnabled(frames)
        self.every_note.setVisible(not frames)
        self.fade_sld.blockSignals(True)
        self.fade_sld.setValue(int(round(float(p["fade"]) * 100)))
        self.fade_sld.blockSignals(False)
        self.fade_val.setText(str(self.fade_sld.value()))
        self.look_seg.setValue(int(p["look"]))
        mine = True
        for b, past, future in self.colour_btns:
            same = list(past) == list(p["pastTint"])[:3] and list(future) == list(p["futureTint"])[:3]
            b.setChecked(same)
            mine = mine and not same
        self.mine_btn.setChecked(mine)
        self.bars.setGhosts(p["before"], p["after"],
                            dict((i, s.opacity(i)) for i in range(-session.MAX_GHOSTS, session.MAX_GHOSTS + 1) if i),
                            p["pastTint"], p["futureTint"])
        self._fill_rows(self.chars_lay, [
            (c["name"], "%d mesh%s" % (len(c["meshes"]), "" if len(c["meshes"]) == 1 else "es"), c["visible"],
             (lambda on, i=i: self.s.setCharacterVisible(i, on)), (lambda i=i: self.s.removeCharacter(i)))
            for i, c in enumerate(s.characters)], "No characters yet.")

        # arcs
        a = s.o.arcs
        self._fill_rows(self.points_lay, [
            (_point_name(pt), "control" if pt[1] is None else "vtx %d" % pt[1], pt not in a.hidden,
             (lambda on, pt=pt: self.s.setArcVisible(pt, on)), (lambda pt=pt: self.s.removeArcPoint(pt)))
            for pt in a.points], "No points yet.")
        self.arcBefore_stp.setValue(p["arcsBefore"])
        self.arcAfter_stp.setValue(p["arcsAfter"])
        self.dots_seg.setValue(int(p["arcsDotEvery"]))
        _set_checked(self.arcsShow_chk, p["arcsShow"])

        # settings
        _set_checked(self.hide_chk, p["hideWhilePlaying"])
        _set_slider(self.opacity_sld, self.opacity_val, int(p["opacity"]))
        _set_checked(self.light_chk, p["lightTable"])
        _set_slider(self.light_sld, self.light_val, int(round(float(p["lightStrength"]) * 100)))
        self.ghostsOf_seg.setValue(p["ghostsOf"])
        if len(s.characters) < 2:
            self.active_lbl.setText("Needs two characters or more.")
        else:
            self.active_lbl.setText("Animating: %s  (follows your selection)" % (s.activeName() or "-"))
        _set_checked(self.auto_chk, p["autoFill"])
        _set_checked(self.behind_chk, p["drawBehind"])
        for spn, key in ((self.outline_spn, "outlineWidth"), (self.buffer_spn, "maxBuffer")):
            spn.blockSignals(True)
            spn.setValue(int(p[key]))
            spn.blockSignals(False)
        self.pinned_lbl.setText(", ".join(str(f) for f in s.pinned) if s.pinned else "None pinned.")

    def refreshStatus(self):
        try:
            ok = True
            text = self.s.status()
        except Exception as e:
            ok, text = False, "Status not available: %s" % e
        self.status_lbl.setText(("✓ " if ok and self.s.isOn() else "") + text)
        self.camera_lbl.setText(self.s.cameraNote)
        self.camera_lbl.setVisible(bool(self.s.cameraNote))

    def _fill_rows(self, lay, rows, empty):
        _clear(lay)
        if not rows:
            lab = QtWidgets.QLabel(empty)
            lab.setProperty("note", True)
            lay.addWidget(lab)
        for name, note, visible, on_eye, on_remove in rows:
            lay.addWidget(Row(name, note, visible, on_eye, on_remove))

    def closeEvent(self, event):
        # the onion skin stays on; only this window closes
        try:
            self._timer.stop()
            if self.refresh in self.s.listeners:
                self.s.listeners.remove(self.refresh)
            self.s.save()
        except Exception:
            pass
        global _WINDOW
        if _WINDOW is self:
            _WINDOW = None
        super(OnionWindow, self).closeEvent(event)


def _clear(lay):
    """Empty a layout now (not later: the old rows must not stay on screen)."""
    while lay.count():
        w = lay.takeAt(0).widget()
        if w:
            w.hide()
            w.setParent(None)
            w.deleteLater()


def _qcolor(rgb):
    from onionSkinRenderer.qt import QtGui
    return QtGui.QColor(*list(rgb)[:3])


def _set_slider(sld, label, value):
    sld.blockSignals(True)
    sld.setValue(int(value))
    sld.blockSignals(False)
    label.setText(str(sld.value()))


def _set_checked(box, value):
    box.blockSignals(True)
    box.setChecked(bool(value))
    box.blockSignals(False)


def _point_name(pt):
    node = pt[0].split("|")[-1]
    return node


def _preset_text(name, s):
    v = dict(session.BUILTIN_PRESETS).get(name) or s.prefs["presets"].get(name) or {}
    mode = {"keys": "ghosts on keys", "main": "ghosts on main keys", "frames": "ghosts every %s frame(s)"
            % v.get("every", 1)}.get(v.get("mode"), "")
    text = "%s, %s before / %s after" % (mode, v.get("before", "?"), v.get("after", "?"))
    if v.get("arcs"):
        text += ", arcs %s / %s" % (v.get("arcsBefore", 24), v.get("arcsAfter", 24))
    return text
