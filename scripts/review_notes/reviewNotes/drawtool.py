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


def _press(*_):
    try:
        view = _view()
        cam = _camera(view)
        s = sketch.SKETCH
        if s.camera and s.camera != cam:
            cmds.inViewMessage(amg="This drawing is on <hl>%s</hl>: save it or clear it first." % s.camera,
                               pos="topCenter", fade=True)
            return
        s.start(cam, int(round(cmds.currentTime(query=True))))
        s.press(_mouse_on_gate(view), _ctrl())
        _refresh()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


def _drag(*_):
    try:
        s = sketch.SKETCH
        if s.camera and s.camera != _camera(_view()):
            return
        s.move(_mouse_on_gate(_view()), _ctrl())
        _refresh()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


def _release(*_):
    try:
        s = sketch.SKETCH
        if s.camera and s.camera != _camera(_view()):
            return
        s.release(_mouse_on_gate(_view()), _ctrl())
        _refresh()
        changed()
    except Exception as e:
        print("Review Notes: drawing failed (%s)" % e)


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
    changed()
    return True


def off():
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
