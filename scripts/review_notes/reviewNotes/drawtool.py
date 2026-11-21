"""
Drawing in Maya: a Maya tool (draggerContext), so Alt still moves the camera and nothing covers the view.
Maya tells us about press / drag / release; where the mouse is comes from the view itself (its own pixels,
right on a Retina screen too), turned into gate space and handed to the drawing in progress (sketch.SKETCH).
The REVIEW_NOTES node draws that drawing live, over the view, until it's saved or cleared.

    import reviewNotes.drawtool as d
    d.on() / d.off() / d.toggle()
    d.save("Push the peak higher", kind="change", hold=6)
"""

import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from reviewNotes import controller, draw, nodedraw, sketch, store

CONTEXT = "reviewNotesDrawCtx"
_listeners = []              # the window: told when the drawing or the notes change


def changed():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            _listeners.remove(fn)


def _view():
    return omui.M3dView.active3dView()


def _camera(view):
    path = view.getCamera()
    path.pop()
    return path.partialPathName().split("|")[-1]


def _mouse_on_gate(view):
    """Where the mouse is, in gate space - read from the view's own widget, in the view's own pixels."""
    from reviewNotes.qt import QtGui, QtWidgets, shiboken
    widget = shiboken.wrapInstance(int(view.widget()), QtWidgets.QWidget)
    local = widget.mapFromGlobal(QtGui.QCursor.pos())
    k = view.portWidth() / float(max(1, widget.width()))      # 2 on a Retina screen
    x, y = local.x() * k, (widget.height() - local.y()) * k
    return draw.from_screen(x, y, nodedraw.view_gate(view))


def _ctrl():
    try:
        return "ctrl" in (cmds.draggerContext(CONTEXT, query=True, modifier=True) or "")
    except Exception:
        return False


def _refresh():
    cmds.refresh(currentView=True, force=True)


_last_click = {"time": 0.0, "at": None}


def _double_click(p):
    """A second click at the same place within a third of a second."""
    import time
    now = time.time()
    last = _last_click["at"]
    double = last is not None and now - _last_click["time"] < 0.35 and sketch.dist(last, p) < sketch.HIT * 2
    _last_click["time"], _last_click["at"] = (0.0, None) if double else (now, p)
    return double


def _erase_saved(cam, frame, points, radius, first):
    """The eraser on SAVED notes shown here (this camera, on this frame): only what it rubs over goes.
    One save per mouse event; the .bak is made only when you press (it keeps the file from before)."""
    path = controller.review_path()
    if not path:
        return False
    try:
        notes = store.read(path)["notes"]
    except store.ReviewFileError:
        return False
    names = draw.camera_names(cam)
    changes = {}
    for n in notes:
        if draw.camera_matches(n["camera"], names) and draw.note_state(n, frame, 0) == "now" and n["strokes"]:
            strokes, hit = n["strokes"], False
            for q in points:
                strokes, changed = sketch.cut(strokes, q, radius)
                hit = hit or changed
            if hit:
                changes[n["id"]] = strokes
    return bool(changes) and store.set_strokes(path, changes, backup=first) > 0


def _use(p, pressing):
    s = sketch.SKETCH
    view = _view()
    cam = _camera(view)
    frame = int(round(cmds.currentTime(query=True)))
    if s.tool == "eraser":                                # along the whole drag, the drawing's strokes first
        if pressing:
            s._last_erase = p
        points = [p] if pressing else s._erase_path(p)
        for q in points:
            s._erase(q)
        if _erase_saved(cam, frame, points, sketch.eraser_radius(s.width), pressing):
            changed()
        return
    if s.camera and (s.camera != cam or s.frame != frame):
        if pressing:
            cmds.inViewMessage(amg="This drawing is on <hl>%s, frame %s</hl>: save it or clear it first."
                               % (s.camera, s.frame), pos="topCenter", fade=True)
        return "elsewhere"
    if pressing:
        if s.tool == "curve" and s.curve and _double_click(p):
            s.end_curve()
            return
        s.start(cam, frame)
        s.press(p, _ctrl())
    else:
        s.move(p, _ctrl())


def _press(*_):
    try:
        _use(_mouse_on_gate(_view()), True)
        _refresh()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


def _drag(*_):
    try:
        _use(_mouse_on_gate(_view()), False)
        _refresh()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


def _release(*_):
    try:
        s = sketch.SKETCH
        p = _mouse_on_gate(_view())
        if s.tool != "eraser" and s.camera == _camera(_view()) and s.frame == int(round(cmds.currentTime(query=True))):
            s.release(p, _ctrl())
        _refresh()
        changed()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


# ---------------- Enter / Esc while drawing ----------------
_keys = {"filter": None}


def _make_key_filter():
    from reviewNotes.qt import QtCore, QtWidgets

    class KeyFilter(QtCore.QObject):
        """Enter: end the curve (or save the note). Esc: throw the curve (or the drawing) away.
        Only while the drawing tool is on, and never while you type in a text field."""

        def eventFilter(self, obj, event):
            try:
                if event.type() != QtCore.QEvent.KeyPress or not is_on():
                    return False
                focus = QtWidgets.QApplication.focusWidget()
                if isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit,
                                      QtWidgets.QAbstractSpinBox)):
                    return False
                key = event.key()
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if sketch.SKETCH.curve is not None:
                        end_curve()
                    else:
                        hk_save()
                    return True
                if key == QtCore.Qt.Key_Escape:
                    if sketch.SKETCH.curve is not None:
                        cancel_curve()
                    elif not sketch.SKETCH.empty():
                        clear()
                    else:
                        return False
                    return True
            except Exception:
                return False
            return False
    return KeyFilter()


def _keys_on():
    try:
        from reviewNotes.qt import QtWidgets
        if _keys["filter"] is None:
            _keys["filter"] = _make_key_filter()
            QtWidgets.QApplication.instance().installEventFilter(_keys["filter"])
    except Exception as e:
        print("Review Notes: Enter / Esc won't work while drawing (%s)" % e)


def _keys_off():
    try:
        from reviewNotes.qt import QtWidgets
        if _keys["filter"] is not None:
            QtWidgets.QApplication.instance().removeEventFilter(_keys["filter"])
    except Exception:
        pass
    _keys["filter"] = None


def _make_context():
    flags = dict(pressCommand=_press, dragCommand=_drag, releaseCommand=_release, cursor="crossHair",
                 space="screen", undoMode="step")
    if cmds.draggerContext(CONTEXT, exists=True):
        cmds.draggerContext(CONTEXT, edit=True, **flags)
    else:
        cmds.draggerContext(CONTEXT, name=CONTEXT, image1="pencil.png", **flags)


def is_on():
    try:
        return cmds.currentCtx() == CONTEXT
    except Exception:
        return False


def on():
    """Draw on the view: the notes' node made if needed, then the drawing tool."""
    if not controller.review_path():
        controller._tell("save the scene first: the notes go in a file next to it.", warn=True)
        return False
    controller.ensure_node()
    _make_context()
    cmds.setToolTo(CONTEXT)
    _keys_on()
    changed()
    return True


def off():
    _keys_off()
    if is_on():
        cmds.setToolTo("selectSuperContext")
    sketch.SKETCH.end_curve()
    _refresh()
    changed()


def toggle():
    return off() if is_on() else on()


def set_tool(tool):
    sketch.SKETCH.set_tool(tool)
    _refresh()
    changed()


def end_curve():
    sketch.SKETCH.end_curve()
    _refresh()
    changed()


def cancel_curve():
    sketch.SKETCH.cancel_curve()
    _refresh()
    changed()


def clear():
    sketch.SKETCH.clear()
    _refresh()
    changed()


def save(text="", kind="change", hold=6):
    """The drawing (and / or the text) as a new note on its camera and frame. Returns the note or None."""
    path = controller.review_path()
    if not path:
        controller._tell("save the scene first: the notes go in a file next to it.", warn=True)
        return None
    s = sketch.SKETCH
    strokes = s.finish()
    text = (text or "").strip()
    if not strokes and not text:
        controller._tell("draw something or write a line first.", warn=True)
        return None
    camera = s.camera or controller.current_camera()
    frame = s.frame if s.frame is not None else int(round(cmds.currentTime(query=True)))
    _, version = store.split_version(cmds.file(query=True, sceneName=True))
    try:
        note = store.add_note(path, store.make_note(camera, frame, hold, kind, text, strokes, scene_version=version))
    except store.ReviewFileError as e:
        controller._tell(str(e), warn=True)
        return None
    s.clear()
    controller.ensure_node()
    _refresh()
    changed()
    controller._tell("note %s saved on %s, frames %d-%d." % (note["id"], camera, frame, frame + note["hold"] - 1))
    return note


# hotkeys (Hotkey Editor > Custom Scripts > Review Notes)
def hk_toggle():
    toggle()


def hk_end_curve():
    end_curve()


def hk_save():
    """Saves with what's written in the window (if it's open)."""
    try:
        from reviewNotes import window
        if window.WINDOW is not None:
            window.WINDOW.save()
            return
    except Exception:
        pass
    save()
