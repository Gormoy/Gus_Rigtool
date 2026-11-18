"""
The onion skin's state and actions, shared by the big window (window.py) and the mini bar (minibar.py).
It lives on its own: closing the windows keeps the onion skin on; the ON button turns it off.

Settings are kept in settings.txt (version 3). Older settings (version 2) are read and moved over.
"""
import os
import json
import maya.cmds as cmds

import onionSkinRenderer.core as core
import onionSkinRenderer.extras as extras
import onionSkinRenderer.arcs as arcs

SETTINGS_VERSION = 3
SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.txt")
MAX_GHOSTS = 12
MODES = ("keys", "main", "frames")
LOOKS = ("Shaded", "Flat colour", "Outline")
COLOURS = (("Blue / Orange", [40, 120, 255], [255, 130, 20]),
           ("Red / Green", [220, 50, 50], [50, 170, 50]))       # Harmony's: previous red, next green
BUILTIN_PRESETS = (
    ("Blocking (keys)", {"mode": "keys", "before": 2, "after": 2, "every": 1, "arcs": False}),
    ("Spacing", {"mode": "frames", "before": 3, "after": 3, "every": 1, "arcs": False}),
    ("Arcs ±24", {"mode": "frames", "before": 6, "after": 6, "every": 4, "arcs": True,
                      "arcsBefore": 24, "arcsAfter": 24}),
)
DEFAULTS = {
    "mode": "keys", "before": 1, "after": 1, "every": 1, "fade": 0.6, "look": 0,
    "pastTint": [40, 120, 255], "futureTint": [255, 130, 20], "pinnedTint": [125, 0, 0],
    "drawBehind": False, "autoFill": True, "hideWhilePlaying": True, "outlineWidth": 3, "maxBuffer": 200,
    "autoClearBuffer": True, "opacities": {}, "presets": {}, "preset": "",
    "arcsBefore": 24, "arcsAfter": 24, "arcsDotEvery": 1, "arcsShow": True,
    "miniBar": False, "miniBarPos": None,
    "opacity": 100, "lightTable": False, "lightStrength": 0.5, "ghostsOf": "all",
}


def default_opacity(index):
    return int(75 / abs(index)) if index else 100


def migrate(old):
    """Settings of any version -> version 3 (unknown keys dropped, missing ones from DEFAULTS)."""
    d = dict(DEFAULTS)
    d["opacities"], d["presets"] = {}, {}
    if not old:
        return d
    if old.get("settingsVersion", 0) >= 3:
        for k in DEFAULTS:
            if k in old:
                d[k] = old[k]
        return d
    active = [int(f) for f in old.get("activeRelativeFrames", [-1, 1])]
    d["before"] = max([-f for f in active if f < 0] or [0])
    d["after"] = max([f for f in active if f > 0] or [0])
    if not old.get("displayKeyframes", True):
        d["mode"] = "frames"
    elif old.get("mainKeysOnly"):
        d["mode"] = "main"
    d["every"] = int(old.get("relativeStep", 1))
    for new, key in (("pastTint", "rPastTint"), ("futureTint", "rFutureTint"), ("pinnedTint", "aTint"),
                     ("look", "onionType"), ("drawBehind", "drawBehind"), ("fade", "fade"),
                     ("autoFill", "autoFill"), ("outlineWidth", "outlineWidth"), ("maxBuffer", "maxBufferSize"),
                     ("autoClearBuffer", "autoClearBuffer"), ("arcsBefore", "arcsBefore"),
                     ("arcsAfter", "arcsAfter"), ("arcsDotEvery", "arcsDotEvery"), ("arcsShow", "arcsShow")):
        if key in old:
            d[new] = old[key]
    return d


def _key(scope):
    return "%s:%s" % scope


def _scene_meshes(exclude=()):
    """The visible meshes of the scene, without those of these characters (the light table's background)."""
    out = []
    for shape in cmds.ls(type=("mesh", "nurbsSurface"), long=True, noIntermediate=True) or []:
        t = (cmds.listRelatives(shape, parent=True, fullPath=True) or [None])[0]
        if t and t not in out and not any(extras.in_scope(t, sc) for sc in exclude):
            out.append(t)
    return out


def character_name(scope):
    kind, name = scope
    return name if kind == "ns" else name.split("|")[-1]


_SESSION = None


def get():
    """The one session (made the first time)."""
    global _SESSION
    if _SESSION is None:
        _SESSION = Session()
    return _SESSION


def current():
    return _SESSION


def shutdown():
    """Everything off (the installer calls this before an update)."""
    global _SESSION
    if _SESSION is not None:
        try:
            _SESSION.close()
        finally:
            _SESSION = None


class Session(object):
    def __init__(self):
        if core.OSR_INSTANCE is None:
            core.initializeOverride()
        self.o = core.OSR_INSTANCE
        self.prefs = migrate(self._read())
        self.characters = []          # [{"scope", "name", "meshes", "visible"}]
        self.active = None            # the character you're animating (light table)
        self.pinned = []              # frames always shown
        self.listeners = []           # windows: called after every change
        self.cameraNote = ""
        self._filling = False
        self._pending = False
        self._saveTimer = None
        self._arcTimer = None
        self.jobs = []
        self._apply_all()
        self._start_jobs()

    # ---------------------------------------------------------------- settings
    def _read(self):
        try:
            with open(SETTINGS) as f:
                return json.load(f)
        except (IOError, OSError, ValueError):
            return None

    def save(self):
        data = dict(self.prefs)
        data["settingsVersion"] = SETTINGS_VERSION
        try:
            with open(SETTINGS, "w") as f:
                json.dump(data, f, indent=1, sort_keys=True)
        except (IOError, OSError) as e:
            print("onionSkinRenderer: settings not saved: %s" % e)

    def saveSoon(self):
        """Many small changes (a slider being dragged): one save a moment after the last."""
        try:
            from onionSkinRenderer.qt import QtCore
            if self._saveTimer is None:
                self._saveTimer = QtCore.QTimer()
                self._saveTimer.setSingleShot(True)
                self._saveTimer.setInterval(800)
                self._saveTimer.timeout.connect(self.save)
            self._saveTimer.start()
        except Exception:
            self.save()

    def changed(self):
        self.saveSoon()
        for fn in list(self.listeners):
            try:
                fn()
            except Exception as e:
                print("onionSkinRenderer: window not refreshed: %s" % e)

    def _apply_all(self):
        p, o = self.prefs, self.o
        o.setMaxBuffer(int(p["maxBuffer"]))
        o.setOutlineWidth(int(p["outlineWidth"]))
        o.setAutoClearBuffer(bool(p["autoClearBuffer"]))
        o.setTint(list(p["pastTint"]), "relative_pastTint_btn")
        o.setTint(list(p["futureTint"]), "relative_futureTint_btn")
        o.setTint(list(p["pinnedTint"]), "absolute_tint_btn")
        o.setOnionSkinDisplayMode(int(p["look"]))
        o.setDrawBehind(bool(p["drawBehind"]))
        o.setFade(float(p["fade"]))
        o.setRelativeStep(int(p["every"]))
        o.hideWhilePlaying = bool(p["hideWhilePlaying"])
        o.setGlobalOpacity(int(p["opacity"]))
        a = o.arcs
        a.before, a.after = int(p["arcsBefore"]), int(p["arcsAfter"])
        a.dotEvery, a.show = int(p["arcsDotEvery"]), bool(p["arcsShow"])
        self._apply_mode()
        self._apply_ghosts()

    # ---------------------------------------------------------------- on / off
    def isOn(self):
        return core.onionPanel() is not None

    def toggle(self):
        """The onion skin on in the viewport you last clicked (off in the others), or off."""
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
            visible = [q for q in cmds.getPanel(visiblePanels=True) or [] if cmds.getPanel(typeOf=q) == "modelPanel"]
            panel = visible[0] if visible else None
        if not panel:
            print("onionSkinRenderer: click in your camera's viewport first")
            return
        self.o.clearOnionSkinBuffer(False)
        if cmds.modelEditor(panel, query=True, rendererOverrideName=True) == "onionSkinRenderer":
            cmds.modelEditor(panel, edit=True, rendererOverrideName="")
        else:
            for other in cmds.getPanel(type="modelPanel") or []:
                if other != panel and cmds.modelEditor(other, query=True,
                                                       rendererOverrideName=True) == "onionSkinRenderer":
                    cmds.modelEditor(other, edit=True, rendererOverrideName="")
            cmds.modelEditor(panel, edit=True, rendererOverrideName="onionSkinRenderer")
        self.checkCamera()
        self.changed()
        if self.isOn():
            self.scheduleAutoFill()

    def checkCamera(self):
        cam = core.onionCamera()
        if cam and core.cameraMoves(cam):
            self.cameraNote = ("%s moves (animated or constrained): the ghosts are pictures of the view, so they "
                               "drift with the camera. The arcs are fine." % cam.split("|")[-1])
        else:
            self.cameraNote = ""

    def status(self):
        """One line for the windows: what is showing, what is waiting."""
        if not self.isOn():
            return "Onion skin is off. Click in your camera view, then press ON."
        if not self.characters:
            return "Add a character: select one of its controls, then + Add selected character."
        if not any(c["visible"] for c in self.characters):
            return "All characters' ghosts are hidden (their eyes)."
        o = self.o
        try:
            showing, waiting = o.countGhosts()
        except Exception:
            showing, waiting = 0, 0
        text = "%d ghost%s showing" % (showing, "" if showing == 1 else "s")
        if waiting:
            text += " · %d waiting (%s)" % (waiting, "they fill when you stop" if self.prefs["autoFill"]
                                                else "press Fill")
        a = o.arcs
        if a.points and a.show:
            text += " · %d arc%s" % (len(a.points), "" if len(a.points) == 1 else "s")
        if self.prefs["lightTable"] and o.lightTableOn():
            text += " · light table (%s)" % self.activeName()
        return text

    # ---------------------------------------------------------------- ghosts
    def setMode(self, mode):
        if mode in MODES:
            self.prefs["preset"] = ""
            self.prefs["mode"] = mode
            self._apply_mode()
            self.changed()
            self.scheduleAutoFill()

    def _apply_mode(self):
        mode = self.prefs["mode"]
        self.o.mainKeysOnly = mode == "main"
        self.o.setRelativeDisplayMode(mode != "frames")
        self._arcKeys()

    def setBefore(self, n):
        self.prefs["preset"] = ""
        self.prefs["before"] = max(0, min(MAX_GHOSTS, int(n)))
        self._apply_ghosts()
        self.changed()
        self.scheduleAutoFill()

    def setAfter(self, n):
        self.prefs["preset"] = ""
        self.prefs["after"] = max(0, min(MAX_GHOSTS, int(n)))
        self._apply_ghosts()
        self.changed()
        self.scheduleAutoFill()

    def opacity(self, index):
        return int(self.prefs["opacities"].get(str(index), default_opacity(index)))

    def setOpacity(self, index, pct):
        """One ghost's opacity (the bars); 0 = that ghost off."""
        self.prefs["opacities"][str(index)] = max(0, min(100, int(pct)))
        self._apply_ghosts()
        self.changed()

    def _apply_ghosts(self):
        b, a = int(self.prefs["before"]), int(self.prefs["after"])
        wanted = [i for i in list(range(-b, 0)) + list(range(1, a + 1)) if self.opacity(i) > 0]
        self.o.setGhostSlots(dict((i, self.opacity(i)) for i in wanted))

    def setGhostOpacity(self, pct):
        """Opacity of all the ghosts at once (on top of each ghost's own)."""
        self.prefs["opacity"] = max(5, min(100, int(pct)))
        self.o.setGlobalOpacity(self.prefs["opacity"])
        self.changed()

    def setEvery(self, n):
        self.prefs["preset"] = ""
        self.prefs["every"] = max(1, min(24, int(n)))
        self.o.setRelativeStep(self.prefs["every"])
        self.changed()
        self.scheduleAutoFill()

    def setFade(self, value):
        self.prefs["preset"] = ""
        self.prefs["fade"] = max(0.1, min(1.0, float(value)))
        self.o.setFade(self.prefs["fade"])
        self.changed()

    def setLook(self, index):
        self.prefs["preset"] = ""
        self.prefs["look"] = int(index)
        self.o.setOnionSkinDisplayMode(int(index))
        self.changed()

    def setColours(self, past, future):
        self.prefs["pastTint"], self.prefs["futureTint"] = list(past)[:3], list(future)[:3]
        self.o.setTint(self.prefs["pastTint"], "relative_pastTint_btn")
        self.o.setTint(self.prefs["futureTint"], "relative_futureTint_btn")
        self.changed()

    def setOption(self, key, value):
        """The Settings tab's options."""
        self.prefs[key] = value
        o = self.o
        if key == "drawBehind":
            o.setDrawBehind(bool(value))
        elif key == "hideWhilePlaying":
            o.hideWhilePlaying = bool(value)
        elif key == "outlineWidth":
            o.setOutlineWidth(int(value))
        elif key == "maxBuffer":
            o.setMaxBuffer(int(value))
        elif key == "autoFill" and value:
            self.scheduleAutoFill()
        self.changed()

    # ---------------------------------------------------------------- presets
    def presetNames(self):
        return [n for n, _p in BUILTIN_PRESETS] + sorted(self.prefs["presets"])

    def isBuiltin(self, name):
        return name in [n for n, _p in BUILTIN_PRESETS]

    def presetValues(self):
        p = self.prefs
        return {"mode": p["mode"], "before": p["before"], "after": p["after"], "every": p["every"],
                "fade": p["fade"], "look": p["look"], "arcs": bool(p["arcsShow"]),
                "arcsBefore": p["arcsBefore"], "arcsAfter": p["arcsAfter"]}

    def applyPreset(self, name):
        values = dict(BUILTIN_PRESETS).get(name) or self.prefs["presets"].get(name)
        if not values:
            return
        p = self.prefs
        for k in ("mode", "before", "after", "every", "fade", "look", "arcsBefore", "arcsAfter"):
            if k in values:
                p[k] = values[k]
        if "arcs" in values:
            p["arcsShow"] = bool(values["arcs"])
        p["preset"] = name
        self._apply_all()
        self.changed()
        self.scheduleAutoFill()

    def savePreset(self, name):
        name = (name or "").strip()
        if not name or self.isBuiltin(name):
            return False
        self.prefs["presets"][name] = self.presetValues()
        self.prefs["preset"] = name
        self.changed()
        return True

    def deletePreset(self, name):
        if self.prefs["presets"].pop(name, None) is not None:
            if self.prefs["preset"] == name:
                self.prefs["preset"] = ""
            self.changed()

    # ---------------------------------------------------------------- characters
    def addSelectedCharacters(self):
        """The selection's characters (a control = its whole character's meshes). Returns how many were added."""
        sel = cmds.ls(selection=True, long=True) or []
        meshes = extras.meshes_for(sel)
        if not meshes:
            print("onionSkinRenderer: select a control (or a mesh) of a character first")
            return 0
        added = 0
        for m in meshes:
            scope = extras.scope_of(m)
            char = next((c for c in self.characters if c["scope"] == scope), None)
            if char is None:
                char = {"scope": scope, "name": character_name(scope), "meshes": [], "visible": True}
                self.characters.append(char)
                added += 1
            if m not in char["meshes"]:
                char["meshes"].append(m)
        self._apply_characters()
        self.changed()
        self.scheduleAutoFill()
        return added

    def setCharacterVisible(self, index, visible):
        if 0 <= index < len(self.characters):
            self.characters[index]["visible"] = bool(visible)
            self._apply_characters()
            self.changed()
            self.scheduleAutoFill()

    def removeCharacter(self, index):
        if 0 <= index < len(self.characters):
            self.characters.pop(index)
            self._apply_characters()
            self.changed()

    def clearCharacters(self, *_):
        self.characters = []
        self._apply_characters()
        self.changed()

    def _apply_characters(self):
        """Each character gets its own pictures and its own keys; the eye hides its ghosts (its picture is
        still taken - the light table needs it)."""
        self.o.setCharacters([(_key(c["scope"]), c["meshes"], c["visible"]) for c in self.characters])
        if self.active not in [_key(c["scope"]) for c in self.characters]:
            self.active = _key(self.characters[0]["scope"]) if self.characters else None
        self._apply_light()

    # ---------------------------------------------------------------- light table
    def activeName(self):
        c = next((c for c in self.characters if _key(c["scope"]) == self.active), None)
        return c["name"] if c else ""

    def selectionChanged(self, *_):
        """The character you're animating follows your selection (a control or mesh of one of the characters)."""
        if not self.characters:
            return
        for n in cmds.ls(selection=True, long=True) or []:
            sc = extras.scope_of(n.split(".")[0])
            if any(c["scope"] == sc for c in self.characters):
                if _key(sc) != self.active:
                    self.active = _key(sc)
                    self._apply_light()
                    self.changed()
                return

    def setLight(self, key, value):
        """lightTable / lightStrength / ghostsOf."""
        self.prefs[key] = value
        self._apply_light()
        self.changed()

    def _apply_light(self):
        p = self.prefs
        background = []
        faded = [c["scope"] for c in self.characters if _key(c["scope"]) != self.active]
        if p["lightTable"] and len(self.characters) > 1:
            background = _scene_meshes(exclude=faded)
        self.o.setLightTable(p["lightTable"], float(p["lightStrength"]), self.active, p["ghostsOf"] == "active",
                             background)

    def objectNames(self):
        return [m for c in self.characters if c["visible"] for m in c["meshes"]]

    # ---------------------------------------------------------------- pinned frames
    def pinFrame(self, frame=None):
        f = int(round(cmds.currentTime(query=True) if frame is None else frame))
        if f not in self.pinned:
            self.pinned.append(f)
            self.pinned.sort()
            self.o.setPinned(dict((x, 50) for x in self.pinned))
            self.changed()

    def clearPinned(self, *_):
        self.pinned = []
        self.o.setPinned({})
        self.changed()

    # ---------------------------------------------------------------- arcs
    def addArcPoints(self):
        a = self.o.arcs
        new = [p for p in arcs.from_selection() if p not in a.points]
        if not new:
            print("onionSkinRenderer: select vertices (or controls) first, then + Add selected points")
            return 0
        total = a.points + new
        if len(total) > arcs.MAX_POINTS:
            print("onionSkinRenderer: arcs - only the first %d points are kept" % arcs.MAX_POINTS)
        a.setPoints(total)
        self._arcKeys()
        self.changed()
        self.scheduleAutoFill()
        return len(new)

    def removeArcPoint(self, point):
        self.o.arcs.removePoint(point)
        self.o.refresh()
        self.changed()

    def setArcVisible(self, point, visible):
        self.o.arcs.setVisible(point, visible)
        self.o.refresh()
        self.changed()

    def clearArcPoints(self, *_):
        self.o.arcs.clear()
        self.o.refresh()
        self.changed()

    def setArcs(self, key, value):
        """arcsShow / arcsBefore / arcsAfter / arcsDotEvery."""
        if key != "arcsDotEvery":
            self.prefs["preset"] = ""
        self.prefs[key] = value
        a = self.o.arcs
        a.show = bool(self.prefs["arcsShow"])
        a.before, a.after = int(self.prefs["arcsBefore"]), int(self.prefs["arcsAfter"])
        a.dotEvery = int(self.prefs["arcsDotEvery"])
        self.o.refresh()
        self.changed()
        self.scheduleAutoFill()

    def _arcKeys(self):
        a = self.o.arcs
        try:
            a.keys = set(extras.character_keys([n for n, _v in a.points], self.o.mainKeysOnly)) if a.points else set()
        except Exception:
            a.keys = set()

    # ---------------------------------------------------------------- filling
    def _start_jobs(self):
        self.jobs = [cmds.scriptJob(event=["timeChanged", self.scheduleAutoFill])]
        for e in ("SceneOpened", "NewSceneOpened"):
            self.jobs.append(cmds.scriptJob(event=[e, self.newScene]))
        self.jobs.append(cmds.scriptJob(event=["SelectionChanged", self.selectionChanged]))
        try:
            from onionSkinRenderer.qt import QtCore
            self._arcTimer = QtCore.QTimer()
            self._arcTimer.setSingleShot(True)
            self._arcTimer.setInterval(600)
            self._arcTimer.timeout.connect(self.scheduleAutoFill)
            self.o.arcs.onDirty = self._arcTimer.start
        except Exception:
            self.o.arcs.onDirty = self.scheduleAutoFill

    def newScene(self, *_):
        """Another scene: its characters, points and pinned frames are gone."""
        self.characters = []
        self._apply_characters()
        self.o.arcs.clear()
        self.pinned = []
        self.o.setPinned({})
        self.changed()

    def scheduleAutoFill(self, *_):
        a = self.o.arcs
        arcsWait = a.points and a.show
        if self._filling or self._pending or not (self.prefs["autoFill"] or arcsWait):
            return
        self._pending = True
        cmds.evalDeferred(self.autoFill, lowestPriority=True)

    def autoFill(self):
        self._pending = False
        try:
            if cmds.play(query=True, state=True) or not core.onionPanel():
                return
            missing = []
            if self.prefs["autoFill"]:
                self.o.setRelativeFrames(None)
                missing = [f for f in self.o.neededFrames() if f not in self.o.onionSkinBuffer]
            a = self.o.arcs
            arcFrames = a.toRecord(cmds.currentTime(query=True))
        except Exception:
            return
        if missing or arcFrames:
            if arcFrames and a.stale:
                self._arcKeys()
            self.visit(missing, arcFrames)
        elif a.points and a.show:
            a.record(cmds.currentTime(query=True))
            self.o.refresh()
        self.changed()

    def visit(self, frames, arcFrames=(), label="Filling ghosts"):
        """Visit frames (the onion skin takes their picture; the arcs record where their points are), then back.
        Frames only the arcs need aren't drawn (faster). Many frames: a progress bar, Esc stops. The time always
        comes back to your frame."""
        self._filling = True
        a = self.o.arcs
        now = cmds.currentTime(query=True)
        pictures = set(frames)
        arcSet = set(arcFrames)
        todo = sorted(pictures | arcSet)
        recorded = []
        progress = len(todo) > 8 and not cmds.about(batch=True)
        stopped = False
        try:
            if progress:
                cmds.progressWindow(title="Onion skin", status="%s... 0 / %d   (Esc to stop)" % (label, len(todo)),
                                    isInterruptable=True, progress=0, maxValue=len(todo))
            for n, f in enumerate(todo):
                if progress and cmds.progressWindow(query=True, isCancelled=True):
                    stopped = True
                    break
                cmds.currentTime(f, update=True)
                if a.points and a.show:
                    a.record(f)
                    recorded.append(f)
                if f in pictures:
                    cmds.refresh(force=True)
                if progress:
                    cmds.progressWindow(edit=True, progress=n + 1,
                                        status="%s... %d / %d   (Esc to stop)" % (label, n + 1, len(todo)))
            if arcSet and not stopped:
                a.finish(recorded)
        finally:
            if progress:
                cmds.progressWindow(endProgress=True)
            cmds.currentTime(now, update=True)
            if a.points and a.show:
                a.record(now)
            cmds.refresh(force=True)
            self._filling = False
        return not stopped

    def fill(self):
        if not core.onionPanel():
            print("onionSkinRenderer: turn the onion skin ON in your camera view first")
            return
        try:
            self.o.setRelativeFrames(None)
        except Exception as e:
            print(e)
        frames = self.o.neededFrames()
        a = self.o.arcs
        arcFrames = a.toRecord(cmds.currentTime(query=True))
        if not frames and not arcFrames:
            print("onionSkinRenderer: nothing to fill")
        else:
            self.visit(frames, arcFrames)
        self.changed()

    def playblast(self):
        """A pencil test: the playback range with the ghosts (and arcs) in it."""
        panel = core.onionPanel()
        if not panel:
            print("onionSkinRenderer: turn the onion skin ON in your camera view first")
            return None
        start = cmds.playbackOptions(query=True, minTime=True)
        end = cmds.playbackOptions(query=True, maxTime=True)
        frames = [start + i for i in range(int(end - start) + 1)]
        if self.o.getMaxBuffer() < len(frames) + 10:
            self.o.setMaxBuffer(len(frames) + 10)
        a = self.o.arcs
        arcFrames = []
        if a.points and a.show:
            arcFrames = sorted(set(a.window(start)) | set(frames) | set(a.window(end)))
            arcFrames = [f for f in arcFrames if a.stale or f not in a.cache]
        if not self.visit(frames, arcFrames, "Taking the pictures"):
            print("onionSkinRenderer: playblast stopped")
            return None
        try:
            cmds.setFocus(panel)
        except RuntimeError:
            pass
        self._filling = True
        try:
            try:
                got = cmds.playblast(startTime=start, endTime=end, viewer=True, percent=100, showOrnaments=True,
                                     forceOverwrite=True, editorPanelName=panel)
            except TypeError:
                got = cmds.playblast(startTime=start, endTime=end, viewer=True, percent=100, showOrnaments=True,
                                     forceOverwrite=True)
        finally:
            self._filling = False
        print("onionSkinRenderer: playblast with onion skins: %s" % got)
        return got

    def keysOfOnion(self):
        return extras.character_keys(self.objectNames(), self.o.mainKeysOnly)

    # ---------------------------------------------------------------- the end
    def close(self):
        for job in self.jobs:
            try:
                if cmds.scriptJob(exists=job):
                    cmds.scriptJob(kill=job, force=True)
            except Exception:
                pass
        self.jobs = []
        for t in (self._arcTimer, self._saveTimer):
            try:
                t.stop()
            except Exception:
                pass
        self.o.arcs.onDirty = None
        self.listeners = []
        self.save()
        for p in cmds.getPanel(type="modelPanel") or []:
            try:
                if cmds.modelEditor(p, query=True, rendererOverrideName=True) == "onionSkinRenderer":
                    cmds.modelEditor(p, edit=True, rendererOverrideName="")
            except Exception:
                pass
        core.uninitializeOverride()
