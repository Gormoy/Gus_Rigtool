"""
The picker window (Qt, PySide2 in Maya 2024 or PySide6 in Maya 2025+). Its data and layout are pickmodel.py.

Use:   click a button: select (Shift: add / take away, Ctrl: take away); drag on the background: select every
       button in the box; double-click: the whole limb; right-click: select limb / twin, IK/FK, mirror, reset, key.
       Sliders: drag; check boxes: click. Wheel: zoom; middle drag or Alt + drag: pan; F: frame the page.
Edit:  the Edit button. Click / drag a box to pick buttons, drag them to move (the corner square resizes);
       right-click for shape, colour, label, size, align, distribute, mirror, duplicate, delete, add buttons /
       sliders / commands, background picture. Arrows nudge (Shift: x10), Delete, Ctrl+Z / Ctrl+Y, Ctrl+D,
       Ctrl+S saves (in the rig profile: every scene with this rig gets it).
       5.6.21: quick buttons (align, spread, same size, page centre, mirror, group, ungroup, text, front / back /
       up / down, lock, grid, copy / paste style); frames: a group with a title (click the title: its controls;
       drag it: its buttons come along; Frames menu: show / hide); text; more shapes; Move to page.
5.6.23: a mode band (ANIMATE / EDIT), a status line, one toolbar in sections (Create, Arrange, Style, Controls,
       File; compact: icons only), the button list (search, undock), Look... (your theme, text size, selected /
       hover look, side colours - on this computer), Add selected where the controls sit seen from the front (or
       at the mouse), Missing (add / take out / put back), Front view, Duplicate page, Sides, Set, Toggle, label
       rules, pins shown + Unpin all, Alt+click: the twin, Shift+F: frame the picked / selected.
5.6.24: text that grows (on everything: texts, frame titles - placed, sized, aligned), Normalize a page, the page's
       text size, Fit text, a front picture / the meshes' outline behind (opacity, kept in the picker), Switches and
       Face sliders pages made from the rig, space switches, keyed dots, hierarchy lines, Find (Ctrl+F), help (?),
       My sets, seen from behind, each page's zoom kept, animator lock, templates / style rules, chain numbers,
       line / arc, mirror the layout, scripts with presets, one page to a file, the page as a picture, your keys,
       mirror pairs.
5.6.25: one way to place text (anywhere round / in an item, Ctrl+drag moves the words, wrap, plate), sticky notes,
       connectors (from an item's blue dot; straight / elbow / curved, bends, heads, label, width, colour, dash;
       from the rig's hierarchy), layers, your toolbar (Customize), the silhouette from the meshes' triangles.
5.6.26: a text never blocks a button, rename many, shapes (the rig tool's library, the control's curve, the most
       alike), the controls' colours, frames per limb, IK / FK fade, badges, folding frames, a layer following a
       switch, copy / paste, Alt+drag copies, 8 handles + turn, Shift: one direction, distances / equal gaps,
       minimap, preview, find on every page, page templates, saved versions, another character's pages, undo
       history, Z / Shift+Z, the Item panel in sections (it floats), attributes without the Channel Box.
"""

import copy

import maya.cmds as cmds

try:                                                         # Maya 2025+
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:                                          # Maya 2024
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

from gus_animtool import anim as A
from gus_animtool import pickmodel as PM
from gus_animtool import pickmore as PX

WORKSPACE = "gusAnimtoolPicker"
Qt = QtCore.Qt
_state = {"widget": None}
SNAP_PX = 7.0                                        # snap when this close on screen
HANDLE = 7.0


def _exec(obj, *args):
    fn = getattr(obj, "exec", None) or obj.exec_
    return fn(*args)


def _pos(event):
    try:
        p = event.position()
    except AttributeError:
        p = event.pos()
    return QtCore.QPointF(p.x(), p.y())


def _has(mods, flag):
    try:
        return bool(mods & flag)
    except TypeError:
        return bool(int(mods) & int(flag))


def _colour(rgb, factor=1.0, alpha=255):
    r, g, b = [max(0.0, min(1.0, c * factor)) for c in (list(rgb) + [0.5, 0.5, 0.5])[:3]]
    c = QtGui.QColor.fromRgbF(r, g, b)
    c.setAlpha(alpha)
    return c


def _lighter(rgb):
    return [c * 0.45 + 0.55 for c in rgb]


def _keyed_png(path, key_rgb, shade):
    """5.6.24: the captured front picture: its plain background taken out, the model a flat shade (its shading
    kept a little) - PNG bytes."""
    img = QtGui.QImage(path)
    if img.isNull():
        raise RuntimeError("couldn't read the captured picture %s" % path)
    img = img.convertToFormat(QtGui.QImage.Format_ARGB32)
    kr, kg, kb = [int(round(c * 255)) for c in key_rgb]
    out = QtGui.QImage(img.width(), img.height(), QtGui.QImage.Format_ARGB32)
    out.fill(QtGui.QColor(0, 0, 0, 0))
    for y in range(img.height()):
        for x in range(img.width()):
            c = QtGui.QColor(img.pixel(x, y))
            if abs(c.red() - kr) + abs(c.green() - kg) + abs(c.blue() - kb) < 90:
                continue
            v = 0.55 + 0.45 * (0.3 * c.red() + 0.59 * c.green() + 0.11 * c.blue()) / 255.0
            out.setPixelColor(x, y, QtGui.QColor(min(255, int(shade[0] * v * 1.6)), min(255, int(shade[1] * v * 1.6)),
                                                 min(255, int(shade[2] * v * 1.6)), 255))
    return _image_bytes(out)


def _image_bytes(img):
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.WriteOnly)
    img.save(buf, "PNG")
    ba = buf.data()
    try:
        return bytes(ba.data())
    except (TypeError, AttributeError):
        return bytes(ba)


def _png_bytes(path, longest=1400):
    """A picture file as PNG bytes, at most longest pixels on its long side."""
    img = QtGui.QImage(path)
    if img.isNull():
        raise RuntimeError("couldn't read %s" % path)
    if max(img.width(), img.height()) > longest:
        img = img.scaled(longest, longest, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _image_bytes(img)


_SWATCHES = {}


def _swatch(rgb):
    """5.6.24: a small colour square (the button list)."""
    key = tuple(round(c, 2) for c in (rgb or [0.5, 0.5, 0.5])[:3])
    if key not in _SWATCHES:
        pix = QtGui.QPixmap(12, 12)
        pix.fill(_colour(key))
        _SWATCHES[key] = QtGui.QIcon(pix)
    return _SWATCHES[key]


def _triangles_png(tris, box, height_px, rgb):
    """5.6.25: the meshes' triangles seen from the front, filled, on a clear picture - PNG bytes."""
    x0, y0, x1, y1 = box
    h = max(y1 - y0, 1e-6)
    s = height_px / h
    W, H = max(16, int(round((x1 - x0) * s))), int(height_px)
    img = QtGui.QImage(W, H, QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(QtGui.QColor(0, 0, 0, 0))
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    c = QtGui.QColor(*rgb)
    p.setPen(QtGui.QPen(c, 0.8))                             # a hair of outline: no seams between triangles
    p.setBrush(c)
    for a, b, d in tris:
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF((q[0] - x0) * s, (y1 - q[1]) * s) for q in (a, b, d)]))
    p.end()
    return _image_bytes(img)


def _key_text(event):
    """5.6.24: a key as text ('Ctrl+Shift+G', '?', 'F'), or None for keys the picker doesn't use."""
    k, mods = event.key(), event.modifiers()
    names = {}
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        names[getattr(Qt, "Key_" + c)] = c
    for n in range(1, 13):
        names[getattr(Qt, "Key_F%d" % n)] = "F%d" % n
    names.update({Qt.Key_BracketRight: "]", Qt.Key_BraceRight: "]", Qt.Key_BracketLeft: "[",
                  Qt.Key_BraceLeft: "[", Qt.Key_Question: "?"})
    key = names.get(k)
    if k == Qt.Key_Slash and _has(mods, Qt.ShiftModifier):
        key = "?"
    if key is None:
        return None
    parts = [m for m, flag in (("Ctrl", Qt.ControlModifier), ("Shift", Qt.ShiftModifier), ("Alt", Qt.AltModifier))
             if _has(mods, flag) and not (m == "Shift" and key == "?")]
    return "+".join(parts + [key])


def _text_width(fm, text):
    fn = getattr(fm, "horizontalAdvance", None) or getattr(fm, "width", None)
    try:
        return float(fn(text))
    except Exception:
        return len(text) * 7.0


# ===========================================================================
# 5.6.21: small drawn icons for the quick-edit buttons
# ===========================================================================

_ICONS = {}


def _icon(kind):
    if kind in _ICONS:
        return _ICONS[kind]
    pix = QtGui.QPixmap(16, 16)
    pix.fill(Qt.transparent)
    p = QtGui.QPainter(pix)
    p.setRenderHint(QtGui.QPainter.Antialiasing, True)
    light, accent = QtGui.QColor(215, 215, 220), QtGui.QColor(255, 196, 60)
    p.setPen(QtGui.QPen(light, 1.4))
    bar = lambda x, y, w, h, c=light: p.fillRect(QtCore.QRectF(x, y, w, h), c)
    if kind in ("left", "hcenter", "right"):
        x = {"left": 2, "hcenter": 8, "right": 14}[kind]
        p.setPen(QtGui.QPen(accent, 1.4))
        p.drawLine(QtCore.QPointF(x, 1), QtCore.QPointF(x, 15))
        for y, w in ((3, 10), (9, 6)):
            bx = {"left": 3, "hcenter": 8 - w / 2.0, "right": 13 - w}[kind]
            bar(bx, y, w, 4)
    elif kind in ("top", "vcenter", "bottom"):
        y = {"top": 2, "vcenter": 8, "bottom": 14}[kind]
        p.setPen(QtGui.QPen(accent, 1.4))
        p.drawLine(QtCore.QPointF(1, y), QtCore.QPointF(15, y))
        for x, h in ((3, 10), (9, 6)):
            by = {"top": 3, "vcenter": 8 - h / 2.0, "bottom": 13 - h}[kind]
            bar(x, by, 4, h)
    elif kind == "spreadx":
        for x in (1, 6.5, 12):
            bar(x, 4, 3, 8)
    elif kind == "spready":
        for y in (1, 6.5, 12):
            bar(4, y, 8, 3)
    elif kind == "same":
        bar(1, 4, 6, 8)
        bar(9, 4, 6, 8, accent)
    elif kind == "page":
        p.drawRect(QtCore.QRectF(1.5, 1.5, 13, 13))
        bar(5.5, 5.5, 5, 5, accent)
    elif kind == "group":
        p.drawRoundedRect(QtCore.QRectF(1.5, 1.5, 13, 13), 2, 2)
        bar(2, 2, 12, 4, accent)
    elif kind == "ungroup":
        p.setPen(QtGui.QPen(light, 1.2, Qt.DashLine))
        p.drawRect(QtCore.QRectF(1.5, 1.5, 13, 13))
    elif kind == "text":
        f = p.font()
        f.setBold(True)
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(QtCore.QRectF(0, 0, 16, 16), Qt.AlignCenter, "T")
    elif kind in ("front", "back"):
        a, b = QtCore.QRectF(1, 1, 9, 9), QtCore.QRectF(6, 6, 9, 9)
        first, second = (a, b) if kind == "front" else (b, a)
        p.fillRect(first, QtGui.QColor(110, 110, 118))
        p.fillRect(second, accent)
    elif kind in ("up", "down"):
        pts = [(8, 2), (14, 9), (2, 9)] if kind == "up" else [(8, 14), (14, 7), (2, 7)]
        p.setBrush(light)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*q) for q in pts]))
    elif kind == "lock":
        p.drawArc(QtCore.QRectF(4.5, 1.5, 7, 8), 0, 180 * 16)
        bar(3, 7, 10, 8, accent)
    elif kind == "grid":
        p.setPen(QtGui.QPen(light, 2.0))
        for gx in (3, 8, 13):
            for gy in (3, 8, 13):
                p.drawPoint(QtCore.QPointF(gx, gy))
    elif kind in ("copy", "paste"):                          # 5.6.26: the clipboard
        p.drawRect(QtCore.QRectF(1.5, 1.5, 9, 9))
        p.setBrush(accent if kind == "paste" else light)
        p.drawRect(QtCore.QRectF(5.5, 5.5, 9, 9))
    elif kind in ("copystyle", "pastestyle"):
        p.setBrush(accent if kind == "pastestyle" else Qt.NoBrush)
        p.drawEllipse(QtCore.QRectF(2, 2, 12, 12))
        p.setBrush(light)
        p.drawEllipse(QtCore.QRectF(5.5, 5.5, 5, 5))
    elif kind in ("textup", "textdown"):
        f = p.font()
        f.setBold(True)
        f.setPixelSize(13 if kind == "textup" else 9)
        p.setFont(f)
        p.drawText(QtCore.QRectF(0, 0, 12, 16), Qt.AlignCenter, "A")
        p.setPen(QtGui.QPen(accent, 1.6))
        p.drawLine(QtCore.QPointF(11, 4), QtCore.QPointF(15, 4))
        if kind == "textup":
            p.drawLine(QtCore.QPointF(13, 2), QtCore.QPointF(13, 6))
    elif kind == "pin":
        p.setBrush(accent)
        p.drawEllipse(QtCore.QRectF(4, 1, 8, 8))
        p.drawLine(QtCore.QPointF(8, 9), QtCore.QPointF(8, 15))
    elif kind == "styles":
        for i, c in enumerate((accent, light, QtGui.QColor(120, 170, 230))):
            p.fillRect(QtCore.QRectF(1 + i * 5, 3, 4, 10), c)
    elif kind == "clean":
        p.drawLine(QtCore.QPointF(3, 13), QtCore.QPointF(12, 2))
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(1, 11), QtCore.QPointF(6, 15), QtCore.QPointF(2, 15)]))
    elif kind == "mirror":
        p.setBrush(light)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(7, 2), QtCore.QPointF(7, 14), QtCore.QPointF(1, 14)]))
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(9, 2), QtCore.QPointF(9, 14), QtCore.QPointF(15, 14)]))
    elif kind == "addsel":                                   # 5.6.23
        p.drawEllipse(QtCore.QRectF(1.5, 4.5, 9, 9))
        p.setPen(QtGui.QPen(accent, 2.0))
        p.drawLine(QtCore.QPointF(12, 1), QtCore.QPointF(12, 8))
        p.drawLine(QtCore.QPointF(8.5, 4.5), QtCore.QPointF(15.5, 4.5))
    elif kind == "set":
        p.setBrush(accent)
        p.drawRoundedRect(QtCore.QRectF(1, 5, 14, 6), 3, 3)
    elif kind == "toggle":
        p.drawRoundedRect(QtCore.QRectF(1, 4, 14, 8), 4, 4)
        p.setBrush(accent)
        p.drawEllipse(QtCore.QRectF(8, 5, 6, 6))
    elif kind == "frontview":
        p.drawEllipse(QtCore.QRectF(5.5, 1, 5, 5))
        p.drawLine(QtCore.QPointF(8, 6), QtCore.QPointF(8, 11))
        p.drawLine(QtCore.QPointF(3, 8), QtCore.QPointF(13, 8))
        p.setPen(QtGui.QPen(accent, 1.4))
        p.drawLine(QtCore.QPointF(8, 11), QtCore.QPointF(5, 15))
        p.drawLine(QtCore.QPointF(8, 11), QtCore.QPointF(11, 15))
    elif kind == "snap":
        p.setPen(QtGui.QPen(QtGui.QColor(255, 80, 200), 1.2, Qt.DashLine))
        p.drawLine(QtCore.QPointF(8, 0), QtCore.QPointF(8, 16))
        bar(2, 3, 6, 4)
        bar(8, 9, 6, 4, accent)
    elif kind == "shape":
        p.drawEllipse(QtCore.QRectF(1, 1, 8, 8))
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(11, 6), QtCore.QPointF(15, 14), QtCore.QPointF(7, 14)]))
    elif kind == "colour":
        for i, c in enumerate((QtGui.QColor(230, 80, 80), QtGui.QColor(80, 140, 240), accent)):
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QtCore.QRectF(1 + i * 4, 3 + (i % 2) * 4, 8, 8))
    elif kind == "sides":
        p.fillRect(QtCore.QRectF(1, 3, 4, 10), QtGui.QColor(80, 120, 240))
        p.fillRect(QtCore.QRectF(6, 3, 4, 10), accent)
        p.fillRect(QtCore.QRectF(11, 3, 4, 10), QtGui.QColor(235, 80, 80))
    elif kind == "missing":
        p.setPen(QtGui.QPen(light, 1.2, Qt.DashLine))
        p.drawRect(QtCore.QRectF(1.5, 1.5, 13, 13))
        f = p.font()
        f.setBold(True)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(accent)
        p.drawText(QtCore.QRectF(0, 0, 16, 16), Qt.AlignCenter, "?")
    elif kind == "exclude":
        p.drawEllipse(QtCore.QRectF(1.5, 1.5, 13, 13))
        p.setPen(QtGui.QPen(QtGui.QColor(235, 90, 80), 2.0))
        p.drawLine(QtCore.QPointF(4, 12), QtCore.QPointF(12, 4))
    elif kind == "unpin":
        p.setBrush(accent)
        p.drawEllipse(QtCore.QRectF(4, 1, 8, 8))
        p.drawLine(QtCore.QPointF(8, 9), QtCore.QPointF(8, 15))
        p.setPen(QtGui.QPen(QtGui.QColor(235, 90, 80), 2.0))
        p.drawLine(QtCore.QPointF(2, 14), QtCore.QPointF(14, 2))
    elif kind in ("undo", "redo"):
        p.drawArc(QtCore.QRectF(3, 4, 10, 9), 0 if kind == "undo" else 0, 180 * 16)
        tip = [(1, 8), (6, 8), (3.5, 11)] if kind == "undo" else [(10, 8), (15, 8), (12.5, 11)]
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*q) for q in tip]))
    elif kind == "note":                                     # 5.6.25
        p.fillRect(QtCore.QRectF(2, 2, 12, 12), QtGui.QColor(250, 220, 100))
        p.setPen(QtGui.QPen(QtGui.QColor(60, 60, 60), 1.0))
        for yy in (6, 9, 12):
            p.drawLine(QtCore.QPointF(4, yy), QtCore.QPointF(12, yy))
    elif kind in ("connect", "hierlines"):
        p.setPen(QtGui.QPen(accent, 1.4))
        path = QtGui.QPainterPath()
        path.moveTo(3, 12)
        path.cubicTo(9, 12, 7, 4, 13, 4)
        p.drawPath(path)
        p.setBrush(light)
        p.drawEllipse(QtCore.QRectF(1, 10, 4, 4))
        p.drawEllipse(QtCore.QRectF(11, 2, 4, 4))
        if kind == "hierlines":
            p.drawEllipse(QtCore.QRectF(11, 10, 4, 4))
    elif kind == "layers":
        for k, c in enumerate((light, accent, light)):
            p.setBrush(c)
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(8, 2 + k * 4), QtCore.QPointF(15, 5 + k * 4),
                                           QtCore.QPointF(8, 8 + k * 4), QtCore.QPointF(1, 5 + k * 4)]))
    elif kind == "silhouette":
        p.setBrush(light)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QtCore.QRectF(5.5, 1, 5, 5))
        p.drawRoundedRect(QtCore.QRectF(4, 6, 8, 9), 2, 2)
    elif kind == "background":
        p.drawRect(QtCore.QRectF(1.5, 2.5, 13, 11))
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(3, 12), QtCore.QPointF(7, 6), QtCore.QPointF(10, 10),
                                       QtCore.QPointF(12, 8), QtCore.QPointF(14, 12)]))
    elif kind == "customize":
        for yy, xx in ((4, 10), (8, 5), (12, 8)):
            p.drawLine(QtCore.QPointF(2, yy), QtCore.QPointF(14, yy))
            p.setBrush(accent)
            p.drawEllipse(QtCore.QRectF(xx - 2, yy - 2, 4, 4))
    else:                                                    # labels, more, auto, file...: a letter
        f = p.font()
        f.setBold(True)
        f.setPixelSize(12)
        p.setFont(f)
        p.drawRoundedRect(QtCore.QRectF(1, 1, 14, 14), 3, 3)
        p.setPen(accent)
        p.drawText(QtCore.QRectF(0, 0, 16, 16), Qt.AlignCenter, {"labels": "a", "more": "+", "auto": "A", "file": "F",
                                                                   "space": "@", "script": ">", "mirrorlay": "M",
                                                                   "line": "/", "arc": "(", "normalize": "N",
                                                                   "rules": "R", "fittext": "W", "numbers": "#",
                                                                   "pairs": "=", "selectmenu": "S", "rename": "ab",
                                                                   "gallery": "*", "limbs": "L", "history": "H"}
                    .get(kind, kind[:1].upper()))
    p.end()
    _ICONS[kind] = QtGui.QIcon(pix)
    return _ICONS[kind]


# ===========================================================================
# the canvas: draws a page, handles the mouse
# ===========================================================================

class Canvas(QtWidgets.QWidget):

    def __init__(self, owner):
        super(Canvas, self).__init__()
        self.owner = owner
        self.scale = 1.0
        self.offset = QtCore.QPointF(10, 10)
        self.drag = None                                     # what the mouse is doing
        self.band = None                                     # rubber band (page units)
        self.guides = []                                     # snap lines while moving (page units)
        self.hover = None
        self.images = {}
        self._dx = 0.0                                       # 5.6.22: drawing the side page (page units across)
        self.last_page = None                                # 5.6.23: the mouse on the page (Add selected: at it)
        self.help = False                                    # 5.6.24: the shortcuts over the page (?)
        self._flip_w = None                                  # 5.6.24: seen from behind: the width mirrored
        self.text_rects = {}                                 # 5.6.25: where each item's text went (Ctrl+drag)
        self.gap_lines = []                                  # 5.6.26: distances shown while moving
        self._mini = None                                    # 5.6.26: the minimap's place (screen)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    # -- coordinates --------------------------------------------------------
    def flipped(self):
        """5.6.24: seen from behind (left and right swapped) - animating only."""
        return bool(self.owner.look.get("behind")) and not self.owner.editing

    def _total_w(self):
        page = self.owner.page()
        if not page:
            return PM.PAGE_W
        w = PM.page_size(page)[0]
        dx = self.side_dx()
        if dx is not None:
            w = dx + PM.page_size(self.owner.side_page())[0]
        return w

    def to_page(self, p):
        x = (p.x() - self.offset.x()) / self.scale
        if self.flipped():
            x = self._total_w() - x
        return x, (p.y() - self.offset.y()) / self.scale

    def to_screen(self, x, y):
        px = x + self._dx
        if self.flipped():
            px = (self._flip_w if self._flip_w is not None else self._total_w()) - px
        return QtCore.QPointF(px * self.scale + self.offset.x(), y * self.scale + self.offset.y())

    def _rect(self, x0, y0, x1, y1):
        """A page box on screen (seen from behind: still left < right)."""
        a, b = self.to_screen(x0, y0), self.to_screen(x1, y1)
        return QtCore.QRectF(QtCore.QPointF(min(a.x(), b.x()), min(a.y(), b.y())),
                             QtCore.QPointF(max(a.x(), b.x()), max(a.y(), b.y())))

    def side_dx(self):
        """Where the side page starts (page units), or None."""
        side = self.owner.side_page()
        if side is None or self.owner.editing:
            return None
        return PM.page_size(self.owner.page())[0] + 30.0

    def sync_pins(self, page):
        """5.6.22: pinned buttons keep their place in the window - their page place follows the view."""
        for it in (page or {}).get("items", []):
            if it.get("pin"):
                it["x"], it["y"] = self.to_page(QtCore.QPointF(it.get("px", 10.0), it.get("py", 10.0)))
                it["w"] = max(4.0, it.get("pw", 40.0) / self.scale)
                it["h"] = max(4.0, it.get("ph", 20.0) / self.scale)
                if self.flipped():
                    it["x"] -= it["w"]

    def store_pins(self, items):
        for it in items:
            if it.get("pin"):
                r = self._rect(it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
                it["px"], it["py"] = r.left(), r.top()
                it["pw"], it["ph"] = it["w"] * self.scale, it["h"] * self.scale

    def frame(self, items=None):
        """Fit the page in the window - or (5.6.23) just these items."""
        page = self.owner.page()
        if not page:
            return
        self.sync_pins(page)
        x0 = y0 = 0.0
        pw, ph = PM.page_size(page)
        side = self.owner.side_page()
        if items:
            x0, y0, x1, y1 = PM.bounds(items)
            pad = 12.0
            x0, y0, pw, ph = x0 - pad, y0 - pad, max(x1 - x0 + 2 * pad, 20.0), max(y1 - y0 + 2 * pad, 20.0)
            if self.flipped():
                x0 = self._total_w() - (x0 + pw)
        elif side is not None and not self.owner.editing:      # 5.6.22: two pages side by side
            sw, sh = PM.page_size(side)
            pw, ph = pw + 30.0 + sw, max(ph, sh)
        w, h = max(self.width(), 50), max(self.height(), 50)
        self.scale = max(0.02, min(20.0, min(w / pw, h / ph) * 0.96))
        self.offset = QtCore.QPointF((w - pw * self.scale) * 0.5 - x0 * self.scale,
                                     (h - ph * self.scale) * 0.5 - y0 * self.scale)
        self.update()

    def resizeEvent(self, event):
        if not self.owner.framed:
            self.owner.framed = True
            self.owner.restore_view()
        super(Canvas, self).resizeEvent(event)

    # -- drawing ------------------------------------------------------------
    def _path(self, it):
        r = self._rect(it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
        path = QtGui.QPainterPath()
        shape = it.get("shape", "round")
        pts = PM.shape_points(it)
        if PM.is_frame(it):
            rad = min(10.0 * self.scale, r.height() * 0.2)
            path.addRoundedRect(r, rad, rad)
        elif shape in ("ellipse", "ring"):
            path.addEllipse(r)
            if shape == "ring":
                k = min(r.width(), r.height()) * 0.22
                path.addEllipse(r.adjusted(k, k, -k, -k))      # the hole (odd-even fill)
        elif pts:
            path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(r.left() + u * r.width(), r.top() + v * r.height())
                                             for u, v in pts]))
            path.closeSubpath()
        elif shape == "pill":
            rad = min(r.width(), r.height()) * 0.5
            path.addRoundedRect(r, rad, rad)
        elif shape == "rect" and not it.get("corner"):
            path.addRect(r)
        else:
            rad = min(r.width(), r.height()) * float(it.get("corner", 0.25 if shape == "round" else 0.0))
            path.addRoundedRect(r, rad, rad)
        rot = float(it.get("rot", 0.0) or 0.0)
        if rot:                                              # 5.6.22: a turned button
            t = QtGui.QTransform()
            t.translate(r.center().x(), r.center().y())
            t.rotate(-rot if self.flipped() else rot)
            t.translate(-r.center().x(), -r.center().y())
            path = t.map(path)
        return path, r

    def _image(self, path):
        if path not in self.images:
            pix = QtGui.QPixmap(path)
            self.images[path] = pix if not pix.isNull() else None
        return self.images[path]

    def _picture(self, page):
        """5.6.24: the page's picture (kept in the picker), as a pixmap - cached."""
        pic = page.get("picture") or {}
        data = pic.get("data") or ""
        key = ("pic", len(data), data[:64], data[-64:])
        if key not in self.images:
            pix = QtGui.QPixmap()
            try:
                ok = pix.loadFromData(PX.picture_bytes(page))
            except Exception:
                ok = False
            self.images[key] = pix if ok and not pix.isNull() else None
        return self.images[key]

    def _outline_image(self, sil, colour):
        """5.6.24: the outline as one small picture (a pixel a square) - drawn scaled: never too thin to see."""
        grid = PX.outline_grid(sil)
        if not grid:
            return None, None
        cols, rows, x0, y0 = grid
        key = ("sil", id(sil), len(sil.get("runs") or []), cols, rows, colour.red(), colour.green(), colour.blue())
        if key not in self.images:
            img = QtGui.QImage(int(cols), int(rows), QtGui.QImage.Format_ARGB32_Premultiplied)
            img.fill(QtGui.QColor(0, 0, 0, 0))
            q = QtGui.QPainter(img)
            for y, a, b in sil.get("runs") or []:
                q.fillRect(QtCore.QRectF(a - x0, y - y0, b - a + 1, 1), colour)
            q.end()
            self.images[key] = img
        return self.images[key], grid

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        try:
            self._paint(p, self.width(), self.height())
        finally:
            p.end()
        if self.owner.editing:                               # 5.6.22: the Item panel shows the picked one
            self.owner.refresh_panel()
        self.owner.update_status()

    def _paint(self, p, width, height, export=False):
        page = self.owner.page()
        look = self.owner.look
        th = PM.theme(look.get("theme"))
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        whole = QtCore.QRectF(0, 0, width, height)
        p.fillRect(whole, QtGui.QColor(*th["bg"]))
        if not page:
            p.setPen(QtGui.QColor(160, 160, 160))
            p.drawText(whole, Qt.AlignCenter, "No controls found for this character.\nRefresh, or check the "
                                              "control suffix in Settings.")
            return
        self._flip_w = self._total_w()
        self.text_rects = {}
        pw, ph = PM.page_size(page)
        area = self._rect(0, 0, pw, ph)
        p.fillRect(area, QtGui.QColor(*th["page"]))
        self._paint_back(p, page, th, look)
        chosen = set() if export else self.owner.maya_selection()
        editing = self.owner.editing and not export and not self.owner.preview
        picked = self.owner.picked if editing else set()
        ns = self.owner.ns
        grid = self.owner.grid()
        if editing and grid and grid * self.scale >= 6:          # 5.6.21: the snap grid, as dots
            p.setPen(QtGui.QPen(QtGui.QColor(*th["grid"]), 1.5))
            gx = 0.0
            while gx <= pw:
                gy = 0.0
                while gy <= ph:
                    p.drawPoint(self.to_screen(gx, gy))
                    gy += grid
                gx += grid
        self.sync_pins(page)
        self._paint_links(p, page, look, editing)
        self._draw_items(p, page, chosen, editing, picked, ns, export)
        if editing and self.hover is not None and not PM.is_frame(self.hover):
            self._paint_ports(p, self.hover)                 # 5.6.25: drag from a dot: a connector
        if editing:
            self._paint_handles(p)                           # 5.6.26: 8 handles + turn
            self._paint_gaps(p)
        if not export:
            self._paint_minimap(p, page, width, height, th)
        if self.drag and self.drag.get("what") == "link" and self.drag.get("to") is not None:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 60), 1.5, Qt.DashLine))
            p.drawLine(self.to_screen(*self.drag["from_pt"]), self.to_screen(*self.drag["to"]))
        dx = self.side_dx()
        if dx is not None and not export:                    # 5.6.22: the side page, to the right
            side = self.owner.side_page()
            self._dx = dx
            try:
                sw, sh = PM.page_size(side)
                p.fillRect(self._rect(0, 0, sw, sh), QtGui.QColor(*th["page"]))
                self._paint_back(p, side, th, look)
                p.setPen(QtGui.QColor(*th["text"]))
                p.drawText(self._rect(0, -16, sw, 0), Qt.AlignLeft | Qt.AlignVCenter, side.get("name", ""))
                self._paint_links(p, side, look, False)
                self._draw_items(p, side, chosen, False, set(), ns)
            finally:
                self._dx = 0.0
        if self.band:
            x0, y0, x1, y1 = self.band
            p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1.0, Qt.DashLine))
            p.setBrush(QtGui.QColor(255, 255, 255, 25))
            p.drawRect(self._rect(x0, y0, x1, y1))
        if self.guides:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 80, 200), 1.0, Qt.DashLine))
            for kind, at, a, b in self.guides:
                if kind == "v":
                    p.drawLine(self.to_screen(at, a - 6), self.to_screen(at, b + 6))
                else:
                    p.drawLine(self.to_screen(a - 6, at), self.to_screen(b + 6, at))
        if self.help and not export:
            self._paint_help(p, width, height)

    def _paint_back(self, p, page, th, look):
        """The page's background: your picture file (old), the picture kept in the picker, the outline."""
        pw, ph = PM.page_size(page)
        if page.get("bg"):
            pix = self._image(page["bg"])
            if pix:
                p.drawPixmap(self._rect(0, 0, pw, ph), pix, QtCore.QRectF(pix.rect()))
        pic = page.get("picture")
        if pic and look.get("silhouette", True):
            pix = self._picture(page)
            if pix:
                p.save()
                p.setOpacity(max(0.0, min(1.0, float(pic.get("alpha", 0.5)))))
                p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
                target = self._rect(pic["x"], pic["y"], pic["x"] + pic["w"], pic["y"] + pic["h"])
                src = QtCore.QRectF(pix.rect())
                if self.flipped():
                    p.translate(target.center().x(), 0)
                    p.scale(-1, 1)
                    p.translate(-target.center().x(), 0)
                p.drawPixmap(target, pix, src)
                p.restore()
        sil = page.get("outline")
        if sil and not page.get("bg") and not pic and look.get("silhouette", True):
            c = float(sil.get("cell", 4.0))
            ox, oy = float(sil.get("ox", 0.0)), float(sil.get("oy", 0.0))
            shade = QtGui.QColor(*th["shade"])
            img, grid = self._outline_image(sil, shade)
            if img is not None:
                cols, rows, x0, y0 = grid
                a = max(0.0, min(1.0, float(sil.get("alpha", 0.6)) *
                             (0.5 + 0.5 * float(look.get("silhouette_alpha", 1.0)))))    # 5.6.25: easier to see
                target = self._rect(ox + x0 * c, oy + y0 * c, ox + (x0 + cols) * c, oy + (y0 + rows) * c)
                p.save()
                p.setOpacity(max(0.25, a))
                p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
                if self.flipped():
                    p.translate(target.center().x(), 0)
                    p.scale(-1, 1)
                    p.translate(-target.center().x(), 0)
                p.drawImage(target, img)
                p.restore()

    def _paint_links(self, p, page, look, editing):
        """5.6.25: the page's connectors - straight / elbow / curved, their width, colour, dash, heads, label; the
        picked one gold, with handles on its ends and bends."""
        if not look.get("lines", True) and not editing:
            return
        picked = self.owner.picked_links if editing else set()
        off = PX.layer_off(page)
        for ln in page.get("links") or []:
            if ln["a"] in off or ln["b"] in off:
                continue
            pts = PX.link_points(page, ln)
            if not pts or len(pts) < 2:
                continue
            sp = [self.to_screen(x, y) for x, y in pts]
            w = float(ln.get("width", 1.5) or 1.5)
            colour = _colour(ln.get("rgb") or [0.75, 0.78, 0.85])
            sel = ln["id"] in picked
            pen = QtGui.QPen(QtGui.QColor(255, 210, 60) if sel else colour,
                             max(0.6, w * max(0.5, min(self.scale, 3.0))),
                             {"dash": Qt.DashLine, "dot": Qt.DotLine}.get(ln.get("dash"), Qt.SolidLine))
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPolyline(QtGui.QPolygonF(sp))
            size = (5.0 + w * 2.5) * max(0.5, min(self.scale, 2.0))
            for kind, tip, frm in ((ln.get("head_b"), sp[-1], sp[-2]), (ln.get("head_a"), sp[0], sp[1])):
                hs = PX.head_shape((tip.x(), tip.y()), (frm.x(), frm.y()), kind, size)
                if not hs:
                    continue
                p.setPen(QtGui.QPen(pen.color(), max(1.0, w)))
                if hs[0] == "dot":
                    p.setBrush(pen.color())
                    p.drawEllipse(QtCore.QPointF(*hs[1][0]), hs[1][1], hs[1][1])
                elif hs[0] == "poly":
                    p.setBrush(pen.color())
                    p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(*q) for q in hs[1]]))
                else:
                    p.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(*q) for q in hs[1]]))
                p.setBrush(Qt.NoBrush)
            if ln.get("label"):
                pt, _d = PX.point_at([(q.x(), q.y()) for q in sp], float(ln.get("label_at", 0.5)))
                f = p.font()
                f.setPointSizeF(max(6.0, float(ln.get("label_size", 9.0)) * max(0.6, min(self.scale, 2.0))))
                p.setFont(f)
                fm = QtGui.QFontMetrics(f)
                tw, lh = _text_width(fm, ln["label"]), float(fm.height() or 12)
                box = QtCore.QRectF(pt[0] - tw / 2 - 4, pt[1] - lh / 2, tw + 8, lh)
                p.fillRect(box, QtGui.QColor(28, 29, 33, 215))
                p.setPen(colour)
                p.drawText(box, Qt.AlignCenter, ln["label"])
            if sel:                                           # handles: its two ends (round), its bends (square)
                p.setPen(QtGui.QPen(QtGui.QColor(20, 20, 20), 1.0))
                p.setBrush(QtGui.QColor(255, 210, 60))
                for q in (sp[0], sp[-1]):
                    p.drawEllipse(q, 4.5, 4.5)
                for b in ln.get("bends") or []:
                    q = self.to_screen(*b)
                    p.drawRect(QtCore.QRectF(q.x() - 4, q.y() - 4, 8, 8))
                p.setBrush(Qt.NoBrush)

    def _ports(self, it):
        """5.6.25: the four dots on an item's sides (screen) - drag from one: a connector."""
        r = self._rect(it["x"], it["y"], it["x"] + it["w"], it["y"] + it["h"])
        return {"top": QtCore.QPointF(r.center().x(), r.top()), "bottom": QtCore.QPointF(r.center().x(), r.bottom()),
                "left": QtCore.QPointF(r.left(), r.center().y()), "right": QtCore.QPointF(r.right(), r.center().y())}

    def _paint_ports(self, p, it):
        p.setPen(QtGui.QPen(QtGui.QColor(20, 20, 20), 1.0))
        p.setBrush(QtGui.QColor(110, 200, 255))
        for q in self._ports(it).values():
            p.drawEllipse(q, 4.0, 4.0)
        p.setBrush(Qt.NoBrush)

    def _port_at(self, it, sp, tol=7.0):
        for side, q in self._ports(it).items():
            if abs(q.x() - sp.x()) <= tol and abs(q.y() - sp.y()) <= tol:
                return side
        return None

    def _link_handle(self, page, sp, tol=7.0):
        """('a' | 'b' | bend index, link) of a picked connector's handle under the mouse, or None."""
        for ln in page.get("links") or []:
            if ln["id"] not in self.owner.picked_links:
                continue
            pts = PX.link_points(page, ln)
            if not pts:
                continue
            for i, b in enumerate(ln.get("bends") or []):
                q = self.to_screen(*b)
                if abs(q.x() - sp.x()) <= tol and abs(q.y() - sp.y()) <= tol:
                    return i, ln
            for end, q in (("a", self.to_screen(*pts[0])), ("b", self.to_screen(*pts[-1]))):
                if abs(q.x() - sp.x()) <= tol and abs(q.y() - sp.y()) <= tol:
                    return end, ln
        return None

    def _paint_help(self, p, width, height):
        keys = PX.shortcuts()
        lines = ["Picker - keys (Keys... changes them)", ""]
        lines += ["%-14s %s" % (k, a) for a, k in sorted(keys.items(), key=lambda kv: kv[0])]
        lines += ["", "Click: select   Shift: add / take away   Ctrl: take away   Alt+click: the twin",
                  "Drag: a box   Wheel: zoom   Middle / Alt+drag: pan   Double-click empty: frame",
                  "Right-click: key, reset, twin, limb...   ? : this help"]
        box = QtCore.QRectF(12, 12, max(200.0, width - 24), max(120.0, min(height - 24, 18.0 * len(lines) + 20)))
        p.fillRect(box, QtGui.QColor(20, 20, 24, 225))
        p.setPen(QtGui.QColor(235, 235, 240))
        f = p.font()
        f.setPointSizeF(9.0)
        p.setFont(f)
        for i, line in enumerate(lines):
            p.drawText(QtCore.QRectF(box.left() + 12, box.top() + 10 + 17 * i, box.width() - 24, 17),
                       Qt.AlignLeft | Qt.AlignVCenter, line)

    def _draw_items(self, p, page, chosen, editing, picked, ns, export=False):
        look = self.owner.look
        th = PM.theme(look.get("theme"))
        ts_scale = float(look.get("text_scale", 1.0) or 1.0) * float(page.get("text_scale", 1.0) or 1.0)
        hidden = PM.hidden_ids(page)
        off = PX.layer_off(page) | PX.folded_ids(page)       # 5.6.25: hidden layers; 5.6.26: folded frames
        badges = look.get("badges", True)
        keyed = look.get("keyed", True) and not editing and not export
        order = [i for i in page["items"] if not i.get("pin")] + [i for i in page["items"] if i.get("pin")]
        for it in order:
            if (it["id"] in hidden and not editing) or it["id"] in off:
                continue
            if PM.is_frame(it):
                self._paint_frame(p, it, page, chosen, it["id"] in picked and editing, it["id"] in hidden, ts_scale)
                continue
            if PM.is_text(it):
                self._paint_text(p, it, it["id"] in picked and editing, it["id"] in hidden, ts_scale)
                continue
            path, r = self._path(it)
            nodes = self.owner.nodes_of(it)
            kind = it.get("kind")
            on = bool(nodes) and any(n in chosen for n in nodes)
            missing = kind != "command" and not nodes
            rgb = it.get("rgb") or [0.5, 0.5, 0.5]
            v = PM.slider_value(it, ns) if kind in ("slider", "check", "toggle") else None
            lo, hi = float(it.get("min", 0)), float(it.get("max", 1))
            flip = kind == "toggle" and v is not None and abs(v - hi) < abs(v - lo)     # 5.6.23: a toggle on
            if flip:
                rgb = it.get("on_rgb") or [0.36, 0.78, 0.45]
            bright = on and look.get("sel_fill", True)
            faded = not editing and not export and self.owner.ikfk_faded(it)    # 5.6.26: the limb's other mode
            fill = _colour(_lighter(rgb) if bright else rgb, 1.0 if bright else 0.82,
                           90 if missing else (70 if faded else 255))
            hovered = it is self.hover and not editing
            if hovered and look.get("hover", "lighter") in ("lighter", "both"):
                fill = fill.lighter(125)
            p.fillPath(path, fill)
            if kind in ("slider", "check"):
                frac = 0.0 if v is None or hi == lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))
                if kind == "slider":
                    p.fillRect(QtCore.QRectF(r.left(), r.top(), r.width() * frac, r.height()),
                               _colour(_lighter(rgb), 1.0, 220))
                elif frac > 0.5:
                    p.fillRect(r.adjusted(4, 4, -4, -4), QtGui.QColor(235, 235, 235))
            if kind == "toggle":                               # the switch's knob: right when on
                rad = max(2.5, r.height() * 0.28)
                cx = r.right() - r.height() * 0.5 if flip else r.left() + r.height() * 0.5
                p.setPen(Qt.NoPen)
                p.setBrush(QtGui.QColor(245, 245, 245) if flip else QtGui.QColor(150, 152, 158))
                p.drawEllipse(QtCore.QPointF(cx, r.center().y()), rad, rad)
                p.setBrush(Qt.NoBrush)
            if kind == "slider2d":                             # 5.6.22: a pad - its handle drives two attributes
                f2 = PM.slider2d_value(it, ns) or (0.5, 0.5)
                p.setPen(QtGui.QPen(QtGui.QColor(30, 30, 34, 160), 1.0))
                p.drawLine(QtCore.QPointF(r.center().x(), r.top()), QtCore.QPointF(r.center().x(), r.bottom()))
                p.drawLine(QtCore.QPointF(r.left(), r.center().y()), QtCore.QPointF(r.right(), r.center().y()))
                hp = QtCore.QPointF(r.left() + f2[0] * r.width(), r.bottom() - f2[1] * r.height())
                rad = max(3.0, min(r.width(), r.height()) * 0.09)
                p.setBrush(QtGui.QColor(245, 245, 245))
                p.drawEllipse(hp, rad, rad)
                p.setBrush(Qt.NoBrush)
            border = it.get("border_rgb")
            pen = QtGui.QPen(_colour(look.get("sel_rgb") or [1, 1, 1]) if on else
                             (_colour(border) if border else QtGui.QColor(*th["edge"])),
                             float(look.get("sel_width", 2.0)) if on else float(it.get("border_w", 1.0) or 1.0))
            if it.get("border_w") == 0 and not on:
                pen = QtGui.QPen(Qt.NoPen)
            if hovered and look.get("hover", "lighter") in ("outline", "both"):
                pen = QtGui.QPen(_colour(look.get("hover_rgb") or [0.55, 0.85, 1.0]), 2.0)
            if it["id"] in self.owner.search_ids:             # 5.6.23: found by the search
                pen = QtGui.QPen(QtGui.QColor(80, 230, 255), 2.5)
            if editing and missing:                           # its control isn't in the scene
                pen = QtGui.QPen(QtGui.QColor(235, 80, 70), 1.5, Qt.DashLine)
            if editing and it.get("pin"):                     # 5.6.23: pinned - doesn't zoom
                pen = QtGui.QPen(QtGui.QColor(70, 210, 200), 1.5, Qt.DashLine)
            if editing and it is self.hover and it["id"] not in picked:     # 5.6.26: what a click would pick
                pen = QtGui.QPen(QtGui.QColor(150, 220, 255), 1.5, Qt.DashLine)
            if editing and it["id"] in picked:
                pen = QtGui.QPen(QtGui.QColor(255, 210, 60), 2.0, Qt.DashLine)
            p.setPen(pen)
            p.drawPath(path)
            text = it.get("label") or ""
            if kind == "toggle":
                text = (it.get("label_on") if flip else it.get("label_off")) or text
            if kind == "slider" and v is not None:
                text = "%s  %.2f" % (text, v)
            if kind == "enum":                                # 5.6.24: a space switch - its choice now
                k = PX.enum_value(it, ns)
                ch = it.get("choices") or []
                text = "%s: %s  v" % (text, ch[k] if k is not None and 0 <= k < len(ch) else "?")
            self._paint_label(p, it, r, text, rgb, on, ts_scale)
            bd = PX.badge_of(it) if badges else ""
            if bd and r.height() >= 9:                         # 5.6.26: IK / FK / PV / S in its corner
                f = p.font()
                bpt = max(5.0, min(8.0, r.height() * 0.32))
                f.setPointSizeF(bpt)
                f.setBold(True)
                p.setFont(f)
                bw = max(10.0, len(bd) * bpt * 0.8 + 4)
                plate = QtCore.QRectF(r.right() - bw * 0.6, r.top() - bpt * 0.6, bw, bpt * 1.5)
                p.fillRect(plate, QtGui.QColor(25, 25, 30, 210))
                p.setPen(QtGui.QColor(255, 220, 120))
                p.drawText(plate, Qt.AlignCenter, bd)
                f.setBold(False)
                p.setFont(f)
            if keyed and nodes and kind == "select":         # 5.6.24: keyed here (dot) / animated (ring)
                now, anim = self.owner.keyed(nodes[0])
                if anim:
                    rad = max(2.5, min(4.0, r.height() * 0.2))
                    c = QtCore.QPointF(r.left() + rad, r.top() + rad)
                    p.setPen(QtGui.QPen(QtGui.QColor(230, 60, 60), 1.4))
                    p.setBrush(QtGui.QColor(230, 60, 60) if now else Qt.NoBrush)
                    p.drawEllipse(c, rad, rad)
                    p.setBrush(Qt.NoBrush)
            if editing and it.get("locked"):
                self._lock_badge(p, r)
            if editing and it.get("pin"):
                self._pin_badge(p, r)

    def _paint_label(self, p, it, r, text, rgb, on, k=1.0):
        """A button's text: its size (x the page's and your text size), colour, place (5.6.25: anywhere round or
        in it, moved by Ctrl+drag), wrap; too long inside: grow (runs past on a plate), cut, fit, overflow."""
        ts = float(it.get("text_size") or 0.0)
        size = ((ts * self.scale * 0.75) if ts else r.height() * 0.42) * k
        if not text or size < 3.0:
            return
        place = PX.text_place(it)
        fit = it.get("text_fit") or "grow"
        lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
        inside = place not in ("above", "below", "outside-left", "outside-right")
        dark = QtGui.QColor(15, 15, 15) if (lum > 0.45 or on) else QtGui.QColor(240, 240, 240)
        colour = _colour(it["text_rgb"]) if it.get("text_rgb") else (
            dark if inside else QtGui.QColor(*PM.theme(self.owner.look.get("theme"))["text"]))
        self._place_text(p, it, r, text, size, colour, bool(it.get("bold")), fit=fit if inside else "grow",
                         plate=it.get("plate"), dark_plate=inside)

    def _wrap(self, fm, text, width):
        """Lines of text no wider than width (words kept whole; your own line breaks kept)."""
        out = []
        for para in (text or "").replace("\\n", "\n").split("\n"):
            words = para.split(" ")
            line = ""
            for wd in words:
                trial = (line + " " + wd) if line else wd
                if width and _text_width(fm, trial) > width and line:
                    out.append(line)
                    line = wd
                else:
                    line = trial
            out.append(line)
        return out or [""]

    def _place_text(self, p, it, r, text, size, colour, bold, fit="grow", plate=None, dark_plate=False,
                    wrap_w=None, default=None):
        """5.6.25: text at its place on r (screen), moved by its own offset; records where it went (Ctrl+drag)."""
        place = default if (default and not it.get("tpos")) else PX.text_place(it)
        if place == "hidden" or not text:
            return
        f = p.font()
        f.setPointSizeF(max(3.0, size))
        f.setBold(bold)
        fm = QtGui.QFontMetrics(f)
        if fit == "fit" and place == "center":
            wide = _text_width(fm, text)
            if wide > r.width() - 4:
                f.setPointSizeF(max(3.0, f.pointSizeF() * (r.width() - 4) / max(wide, 1.0)))
                fm = QtGui.QFontMetrics(f)
        p.setFont(f)
        if wrap_w is None and it.get("wrap"):
            wrap_w = max(10.0, (float(it["wrap"]) * self.scale if float(it["wrap"]) > 1 else r.width() - 8))
        lines = self._wrap(fm, text, wrap_w)
        if fit == "cut" and place == "center" and len(lines) == 1:
            lines = [fm.elidedText(lines[0], Qt.ElideRight, int(max(r.width() - 4, 4)))]
        lh = float(fm.height() or 12)
        tw = max([_text_width(fm, ln_) for ln_ in lines] + [1.0])
        th = lh * len(lines)
        left, top, align = PX.text_box(place, r.left(), r.top(), r.right(), r.bottom(), tw, th, 3.0)
        left += float(it.get("tdx") or 0.0) * self.scale
        top += float(it.get("tdy") or 0.0) * self.scale
        box = QtCore.QRectF(left, top, tw, th)
        if plate or (dark_plate and fit == "grow" and place == "center" and tw > r.width() - 2):
            p.fillRect(box.adjusted(-3, -1, 3, 1), _colour(plate, 1.0, 200) if isinstance(plate, list) else
                       QtGui.QColor(20, 20, 24, 160))
        p.setPen(colour)
        qa = {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(it.get("align") if it.get("align") in (
            "left", "right", "center") and PM.is_text(it) else align, Qt.AlignHCenter)
        for i, ln_ in enumerate(lines):
            p.drawText(QtCore.QRectF(left - 2, top + i * lh, tw + 4, lh), qa | Qt.AlignVCenter, ln_)
        f.setBold(False)
        p.setFont(f)
        self.text_rects[it["id"]] = box

    def _pin_badge(self, p, r):
        p.drawPixmap(QtCore.QPointF(r.right() - 6, r.top() - 8), _icon("pin").pixmap(12, 12))

    def _lock_badge(self, p, r):
        b = QtCore.QRectF(r.left() - 3, r.top() - 3, 9, 9)
        p.fillRect(b, QtGui.QColor(230, 90, 70))
        p.setPen(QtGui.QColor(255, 255, 255))
        p.drawRect(b)

    def _paint_frame(self, p, it, page, chosen, picked, hidden, k=1.0):
        """A frame - a see-through rounded panel and its title: in a bar (aligned left / centre / right), or
        (5.6.25) anywhere round or in it like any text, moved by Ctrl+drag; how many of its controls are
        selected."""
        if it.get("folded"):                                 # 5.6.26: folded - just its title
            it = dict(it, h=PM.title_h(it), tpos="bar")
        path, r = self._path(it)
        rgb = it.get("rgb") or [0.33, 0.45, 0.6]
        alpha = max(0.0, min(1.0, float(it.get("alpha", 0.35))))
        p.fillPath(path, _colour(rgb, 1.0, int(255 * alpha * (0.4 if hidden else 1.0))))
        members = PM.frame_members(page, it)
        nodes = [n for m in members for n in self.owner.nodes_of(m)]
        n_on = sum(1 for n in set(nodes) if n in chosen)
        place = PX.text_place(it)
        ts = float(it.get("text_size") or 0.0)
        tr = PM.title_rect(it) if place == "bar" else None
        bar = self._rect(tr[0], tr[1], tr[0] + tr[2], tr[1] + tr[3]) if tr else None
        if bar is not None:
            bar = QtCore.QRectF(bar.left(), bar.top(), bar.width(), min(bar.height(), r.height()))
            tp = QtGui.QPainterPath()
            rad = min(10.0 * self.scale, r.height() * 0.2)
            tp.addRoundedRect(bar, rad, rad)
            tp.addRect(bar.adjusted(0, bar.height() * 0.5, 0, 0))
            title = _colour(_lighter(rgb) if n_on else rgb, 1.0, int(255 * (0.45 if hidden else 0.95)))
            if it is self.hover and not self.owner.editing:
                title = title.lighter(120)
            p.fillPath(tp.simplified(), title)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 60), 2.0, Qt.DashLine) if picked else
                 QtGui.QPen(_colour(rgb, 0.6, 255), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        text = (it.get("label") or "") + ("  (hidden)" if hidden else "")
        if n_on and not self.owner.editing:
            text += "   %d/%d" % (n_on, len(set(nodes)))
        lum = 0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]
        if bar is not None and bar.height() > 5:
            size = (ts * self.scale * 0.75) if ts else min(11.0, bar.height() * 0.55)
            colour = _colour(it["text_rgb"]) if it.get("text_rgb") else (
                QtGui.QColor(15, 15, 15) if lum > 0.55 else QtGui.QColor(245, 245, 245))
            f = p.font()
            f.setBold(bool(it.get("bold", True)))
            f.setPointSizeF(max(4.0, size * k))
            p.setFont(f)
            p.setPen(colour)
            al = {"left": Qt.AlignLeft, "right": Qt.AlignRight, "center": Qt.AlignHCenter}.get(
                it.get("align") or "left", Qt.AlignLeft)
            shown = QtGui.QFontMetrics(f).elidedText(text, Qt.ElideRight, int(max(bar.width() - 24, 10)))
            p.drawText(QtCore.QRectF(bar.right() - 16, bar.top(), 14, bar.height()), Qt.AlignCenter,
                       "<" if it.get("folded") else "v")     # 5.6.26: the fold arrow (right end)
            p.drawText(bar.adjusted(7 + float(it.get("tdx") or 0) * self.scale, float(it.get("tdy") or 0) *
                                    self.scale, -20 + float(it.get("tdx") or 0) * self.scale,
                                    float(it.get("tdy") or 0) * self.scale), Qt.AlignVCenter | al, shown)
            f.setBold(False)
            p.setFont(f)
            self.text_rects[it["id"]] = bar
        elif place != "bar":
            size = (ts * self.scale * 0.75) if ts else PM.TITLE_SIZE * self.scale * 0.75
            colour = _colour(it["text_rgb"]) if it.get("text_rgb") else \
                QtGui.QColor(*PM.theme(self.owner.look.get("theme"))["text"])
            self._place_text(p, it, r, text, size * k, colour, bool(it.get("bold", True)), plate=it.get("plate"))
        if self.owner.editing and it.get("locked"):
            self._lock_badge(p, r)

    def _paint_text(self, p, it, picked, hidden, k=1.0):
        """A text - or (5.6.25) a sticky note: its colour behind, several lines wrapped to it, text from its
        top-left; its place anywhere (Ctrl+drag moves the words)."""
        path, r = self._path(it)
        rgb = it.get("rgb") or [0.92, 0.92, 0.92]
        if it.get("note"):
            p.fillPath(path, _colour(rgb, 1.0, 110 if hidden else 245))
            p.setPen(QtGui.QPen(_colour(rgb, 0.7, 255), 1.0))
            p.drawPath(path)
        size = float(it.get("size", 14.0)) * self.scale * 0.75 * k
        colour = _colour(it.get("text_rgb") or (rgb if not it.get("note") else [0.1, 0.1, 0.1]), 1.0,
                         110 if hidden else 255)
        self._place_text(p, it, r, it.get("label") or "", size, colour, bool(it.get("bold", True)),
                         plate=it.get("plate"), wrap_w=(r.width() - 8) if it.get("note") else None)
        if self.owner.editing:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 60), 1.5, Qt.DashLine) if picked else
                     QtGui.QPen(QtGui.QColor(120, 120, 130), 1.0, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)
            if it.get("locked"):
                self._lock_badge(p, r)

    def render_page(self, path, width_px=1600):
        """5.6.24: the whole page as a picture (a cheat sheet for the animators)."""
        page = self.owner.page()
        if not page:
            raise RuntimeError("no page to export.")
        pw, ph = PM.page_size(page)
        k = width_px / max(pw, 1.0)
        img = QtGui.QImage(int(width_px), int(max(16, ph * k)), QtGui.QImage.Format_ARGB32_Premultiplied)
        keep = (self.scale, QtCore.QPointF(self.offset), self.help, self.band, self.hover)
        self.scale, self.offset, self.help, self.band, self.hover = k, QtCore.QPointF(0, 0), False, None, None
        p = QtGui.QPainter(img)
        try:
            self._paint(p, int(width_px), int(max(16, ph * k)), export=True)
        finally:
            p.end()
            self.scale, self.offset, self.help, self.band, self.hover = keep
        if not img.save(path):
            raise RuntimeError("couldn't write %s" % path)
        return path

    # -- mouse --------------------------------------------------------------
    def _sel_items(self):
        page = self.owner.page()
        return [i for i in PM.by_id(page, self.owner.picked) if not i.get("pin")] if page else []

    def _sel_box(self):
        """5.6.26: the picked as one box (page units), or None."""
        items = self._sel_items()
        return PM.bounds(items) if items else None

    def _handles(self):
        """{'nw' ... 'se', 'rot': screen point} of the picked's box (rot: one item only)."""
        box = self._sel_box()
        if box is None:
            return {}
        r = self._rect(*box)
        cx, cy = r.center().x(), r.center().y()
        out = {"nw": (r.left(), r.top()), "n": (cx, r.top()), "ne": (r.right(), r.top()), "e": (r.right(), cy),
               "se": (r.right(), r.bottom()), "s": (cx, r.bottom()), "sw": (r.left(), r.bottom()),
               "w": (r.left(), cy)}
        if len(self._sel_items()) == 1 and not PM.is_frame(self._sel_items()[0]):
            out["rot"] = (cx, r.top() - 16)
        return dict((k, QtCore.QPointF(*v)) for k, v in out.items())

    def _handle_at(self, sp, tol=6.0):
        for k, q in self._handles().items():
            if abs(q.x() - sp.x()) <= tol and abs(q.y() - sp.y()) <= tol:
                return k
        return None

    def _on_handle(self, sp):
        """(kept for older callers) the picked item when the mouse is on a resize handle."""
        k = self._handle_at(sp)
        items = self._sel_items()
        return items[0] if k and k != "rot" and items else None

    def _on_fold(self, frame, x, y):
        """On a frame's fold arrow (the right end of its title bar)."""
        tr = PM.title_rect(dict(frame, tpos="bar") if frame.get("folded") else frame)
        if not tr or PX.text_place(frame) != "bar" and not frame.get("folded"):
            return False
        return tr[0] + tr[2] - 16.0 / max(self.scale, 1e-6) <= x <= tr[0] + tr[2] and tr[1] <= y <= tr[1] + tr[3]

    def _paint_gaps(self, p):
        """5.6.26: while moving - the distances to the nearest buttons around."""
        if not self.gap_lines:
            return
        p.setPen(QtGui.QPen(QtGui.QColor(255, 120, 200), 1.0))
        f = p.font()
        f.setPointSizeF(8.0)
        p.setFont(f)
        for _side, gap, (x0, y0, x1, y1) in self.gap_lines:
            a, b = self.to_screen(x0, y0), self.to_screen(x1, y1)
            p.drawLine(a, b)
            mid = QtCore.QPointF((a.x() + b.x()) * 0.5, (a.y() + b.y()) * 0.5)
            box = QtCore.QRectF(mid.x() - 16, mid.y() - 8, 32, 14)
            p.fillRect(box, QtGui.QColor(60, 20, 50, 200))
            p.drawText(box, Qt.AlignCenter, "%g" % gap)

    def _paint_minimap(self, p, page, width, height, th):
        """5.6.26: a small map of the whole page (bottom right) when it doesn't fit - the window's frame on it;
        click it to go there."""
        self._mini = None
        if not self.owner.look.get("minimap", True):
            return
        pw, ph = PM.page_size(page)
        area = self._rect(0, 0, pw, ph)
        if area.width() <= width * 1.15 and area.height() <= height * 1.15:
            return
        mw = 120.0
        mh = max(30.0, min(160.0, mw * ph / max(pw, 1.0)))
        k = min(mw / max(pw, 1.0), mh / max(ph, 1.0))
        box = QtCore.QRectF(width - mw - 8, height - mh - 8, pw * k, ph * k)
        p.fillRect(box.adjusted(-2, -2, 2, 2), QtGui.QColor(20, 20, 24, 210))
        p.fillRect(box, QtGui.QColor(*th["page"]))
        for it in page["items"]:
            if PM.is_frame(it):
                continue
            p.fillRect(QtCore.QRectF(box.left() + it["x"] * k, box.top() + it["y"] * k, max(1.5, it["w"] * k),
                                     max(1.5, it["h"] * k)), _colour(it.get("rgb") or [0.6, 0.6, 0.6]))
        x0, y0 = self.to_page(QtCore.QPointF(0, 0))
        x1, y1 = self.to_page(QtCore.QPointF(width, height))
        view = QtCore.QRectF(box.left() + min(x0, x1) * k, box.top() + y0 * k, abs(x1 - x0) * k, (y1 - y0) * k)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 60), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(view)
        self._mini = (box, k)

    def _minimap_hit(self, sp):
        if not self._mini:
            return False
        box, k = self._mini
        if not box.contains(sp):
            return False
        px, py = (sp.x() - box.left()) / k, (sp.y() - box.top()) / k
        here = self.to_screen(px, py)
        self.offset = QtCore.QPointF(self.offset.x() + self.width() * 0.5 - here.x(),
                                     self.offset.y() + self.height() * 0.5 - here.y())
        self.update()
        return True

    def _paint_handles(self, p):
        hs = self._handles()
        if not hs:
            return
        box = self._sel_box()
        if len(self._sel_items()) > 1:
            p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 60), 1.0, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self._rect(*box))
        p.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1.0))
        for k, q in hs.items():
            if k == "rot":
                p.setBrush(QtGui.QColor(120, 220, 160))
                p.drawEllipse(q, 4.5, 4.5)
                p.drawLine(q, QtCore.QPointF(q.x(), q.y() + 12))
            else:
                p.setBrush(QtGui.QColor(255, 210, 60))
                p.drawRect(QtCore.QRectF(q.x() - 3.5, q.y() - 3.5, 7, 7))
        p.setBrush(Qt.NoBrush)

    def _resize_to(self, d, x, y, mods):
        """5.6.26: the picked's box dragged by a handle: Shift keeps its proportions, Alt from its middle; every
        picked item scales with the box."""
        ox0, oy0, ox1, oy1 = d["box"]
        h = d["handle"]
        nx0, ny0, nx1, ny1 = ox0, oy0, ox1, oy1
        if "w" in h:
            nx0 = x
        if "e" in h:
            nx1 = x
        if h.startswith("n"):
            ny0 = y
        if h.startswith("s"):
            ny1 = y
        if _has(mods, Qt.AltModifier):                       # from the middle
            cx, cy = (ox0 + ox1) * 0.5, (oy0 + oy1) * 0.5
            if "w" in h or "e" in h:
                half = abs((nx1 if "e" in h else nx0) - cx)
                nx0, nx1 = cx - half, cx + half
            if h.startswith("n") or h.startswith("s"):
                half = abs((ny1 if h.startswith("s") else ny0) - cy)
                ny0, ny1 = cy - half, cy + half
        ow, oh = max(ox1 - ox0, 1e-6), max(oy1 - oy0, 1e-6)
        sx, sy = (nx1 - nx0) / ow, (ny1 - ny0) / oh
        if _has(mods, Qt.ShiftModifier):                     # keep the proportions
            k = max(abs(sx) if h not in ("n", "s") else 0, abs(sy) if h not in ("e", "w") else 0) or 1.0
            sx = sy = k
            if h in ("nw", "w", "sw"):
                nx0 = ox1 - ow * k
            if h in ("nw", "n", "ne"):
                ny0 = oy1 - oh * k
        sx, sy = max(sx, 0.05), max(sy, 0.05)
        for i in PM.by_id(self.owner.page(), set(d["rects"])):
            rx, ry, rw, rh = d["rects"][i["id"]]
            i["x"] = round(nx0 + (rx - ox0) * sx, 2)
            i["y"] = round(ny0 + (ry - oy0) * sy, 2)
            i["w"] = round(max(4.0, rw * sx), 2)
            i["h"] = round(max(4.0, rh * sy), 2)

    def mousePressEvent(self, event):
        sp = _pos(event)
        x, y = self.to_page(sp)
        page = self.owner.page()
        button, mods = event.button(), event.modifiers()
        if self.help:
            self.help = False
            self.update()
            return
        if self.owner.preview:                               # 5.6.26: a click ends the preview
            self.owner.toggle_preview(False)
            return
        if button == Qt.LeftButton and self._minimap_hit(sp):
            return
        if button == Qt.MiddleButton or (button == Qt.LeftButton and _has(mods, Qt.AltModifier) and
                                         not self.owner.editing):
            alt = button == Qt.LeftButton and not self.owner.editing and page is not None
            self.drag = {"what": "pan", "start": sp, "offset": QtCore.QPointF(self.offset),
                         "twin": PM.hit_any(page, x, y) if alt else None}    # 5.6.23: Alt+click - the twin
            return
        if button == Qt.RightButton or not page:
            return
        self.sync_pins(page)
        it = PM.hit_any(page, x, y, self.owner.editing)
        dx = self.side_dx()
        if it is None and dx is not None and x >= dx:         # 5.6.22: the page beside it
            page = self.owner.side_page()
            it = PM.hit_any(page, x - dx, y)
        if self.owner.editing:
            if _has(mods, Qt.ControlModifier):               # 5.6.25: Ctrl+drag a text: move the words
                for iid, box in list(self.text_rects.items()):
                    if box.contains(sp):
                        t = (PM.by_id(self.owner.page(), {iid}) or [None])[0]
                        if t is not None and not t.get("locked"):
                            self.drag = {"what": "text", "item": t, "start": (x, y), "pushed": False,
                                         "orig": (float(t.get("tdx") or 0.0), float(t.get("tdy") or 0.0))}
                            self.owner.picked = {iid}
                            self.update()
                            return
            hov = self.hover if self.hover is not None and not PM.is_frame(self.hover) else None
            side = self._port_at(hov, sp) if hov is not None else None
            if side:                                         # 5.6.25: from a dot: a connector
                pt = PX.side_point(hov, side, (0.0, 0.0))[:2]
                self.drag = {"what": "link", "item": hov, "side": side, "from_pt": pt, "to": None}
                return
            hd = self._link_handle(self.owner.page(), sp)
            if hd is not None:                               # a picked connector's end or bend
                self.drag = {"what": "linkend", "which": hd[0], "link": hd[1], "pushed": False}
                return
            hk = self._handle_at(sp)
            if hk == "rot":                                  # 5.6.26: turn it
                self.drag = {"what": "rotate", "item": self._sel_items()[0], "pushed": False}
                return
            if hk is not None:                               # 5.6.26: 8 handles - the picked scale as one box
                items = self._sel_items()
                self.drag = {"what": "resize", "item": items[0], "start": (x, y), "pushed": False,
                             "handle": hk, "box": PM.bounds(items),
                             "rects": dict((i["id"], (i["x"], i["y"], i["w"], i["h"])) for i in items),
                             "sizes": {i["id"]: (i["w"], i["h"]) for i in items}}
                self.owner.anchor = items[0]["id"]
                return
            if it is not None and _has(mods, Qt.AltModifier):   # 5.6.26: Alt+drag: copies, moved
                if it["id"] not in self.owner.picked:
                    self.owner.picked = {it["id"]}
                self.owner.remember("Alt+drag copies")
                made = PM.duplicate(page, PM.by_id(page, self.owner.picked), 0.0, 0.0)
                self.owner.picked = set(i["id"] for i in made)
                self.drag = {"what": "move", "start": (x, y), "last": (x, y), "pushed": True,
                             "orig": {i["id"]: (i["x"], i["y"]) for i in made}}
                self.owner.changed()
                self.update()
                return
            if it is not None and PM.is_frame(it) and self._on_fold(it, x, y):
                self.owner.remember("fold")                  # 5.6.26: the arrow folds / opens it
                it["folded"] = not it.get("folded")
                self.owner.changed()
                self.update()
                return
            if it is not None:
                if _has(mods, Qt.ShiftModifier):
                    self.owner.picked ^= {it["id"]}
                elif it["id"] not in self.owner.picked:
                    self.owner.picked = {it["id"]}
                    self.owner.picked_links = set()
                self.owner.anchor = it["id"]
                moving = PM.by_id(page, self.owner.picked)
                for fr in [m for m in moving if PM.is_frame(m) and not m.get("locked")]:
                    moving += [i for i in PM.frame_members(page, fr) if i not in moving]   # a frame carries its own
                self.drag = {"what": "move", "start": (x, y), "last": (x, y), "pushed": False,
                             "orig": {i["id"]: (i["x"], i["y"]) for i in moving}}
                self.update()
                return
            ln = PX.hit_link(self.owner.page(), x, y, 5.0 / max(self.scale, 1e-6))
            if ln is not None:                               # 5.6.25: a connector
                if _has(mods, Qt.ControlModifier) and ln["id"] in self.owner.picked_links:
                    self.owner.remember()
                    PX.add_bend(self.owner.page(), ln, x, y)  # Ctrl+click: a bend (a Nuke dot)
                    self.owner.changed()
                elif _has(mods, Qt.ShiftModifier):
                    self.owner.picked_links ^= {ln["id"]}
                else:
                    self.owner.picked_links = {ln["id"]}
                    self.owner.picked = set()
                self.update()
                return
            if not _has(mods, Qt.ShiftModifier):
                self.owner.picked = set()
                self.owner.picked_links = set()
            self.drag = {"what": "band", "start": (x, y), "mods": mods}
            self.band = (x, y, x, y)
            self.update()
            return
        if it is not None and it.get("kind") in ("check", "toggle"):     # 5.6.24: a toggle flips (didn't)
            self.owner.run(lambda: PM.toggle(it, self.owner.ns))
            self.update()
            return
        if it is not None and it.get("kind") == "slider":
            cmds.undoInfo(openChunk=True, chunkName="gusAnimtoolPickerSlider")
            self.drag = {"what": "slider", "item": it}
            self._slide(it, sp)
            return
        if it is not None and it.get("kind") == "enum":       # 5.6.24: a space switch - its choices
            self.owner.enum_menu(it, event)
            return
        if it is not None and it.get("kind") == "slider2d":   # 5.6.22: drag the pad's handle
            cmds.undoInfo(openChunk=True, chunkName="gusAnimtoolPickerPad")
            self.drag = {"what": "pad", "item": it, "dx": dx if page is not self.owner.page() else 0.0}
            self._pad(it, sp, self.drag["dx"])
            return
        if it is not None and it.get("kind") == "command":
            self.owner.run_command(it)
            return
        if it is not None and PM.is_frame(it) and self._on_fold(it, x, y):
            it["folded"] = not it.get("folded")              # 5.6.26: animators fold / open too (not saved)
            self.update()
            return
        if it is not None and PM.is_frame(it):                # its title: every control in it
            self.owner.run(lambda: self.owner.select_items(PM.frame_members(page, it), mods))
            return
        if it is not None and PM.is_text(it):
            return
        if it is not None:
            self.owner.run(lambda: self.owner.click(it, mods))
            return
        self.drag = {"what": "band", "start": (x, y), "mods": mods}
        self.band = (x, y, x, y)

    def _pad(self, it, sp, dx=0.0):
        self._dx = dx
        try:
            _path, r = self._path(it)
        finally:
            self._dx = 0.0
        fx = (sp.x() - r.left()) / max(r.width(), 1.0)
        if self.flipped():
            fx = 1.0 - fx
        fy = (r.bottom() - sp.y()) / max(r.height(), 1.0)
        self.owner.run(lambda: PM.set_slider2d(it, self.owner.ns, fx, fy))
        self.update()

    def _slide(self, it, sp):
        _path, r = self._path(it)
        frac = (sp.x() - r.left()) / max(r.width(), 1.0)
        if self.flipped():
            frac = 1.0 - frac
        self.owner.run(lambda: PM.set_slider(it, self.owner.ns, frac))
        self.update()

    def mouseMoveEvent(self, event):
        sp = _pos(event)
        x, y = self.to_page(sp)
        self.last_page = (x, y)
        d = self.drag
        if not d:
            page = self.owner.page()
            over = PM.hit_any(page, x, y, self.owner.editing) if page else None
            if over is None and self.owner.editing and self.hover is not None and \
                    self._port_at(self.hover, sp):           # its dots sit on the edge: keep it
                over = self.hover
            if over is not self.hover:
                self.hover = over
                self.setToolTip(self.owner.hover_card(over) if over is not None else "")
                self.update()
            return
        if d["what"] == "pan":
            self.offset = d["offset"] + (sp - d["start"])
        elif d["what"] == "text":                             # 5.6.25: the words moved on their item
            if not d["pushed"]:
                self.owner.remember()
                d["pushed"] = True
            t = d["item"]
            t["tdx"] = round(d["orig"][0] + x - d["start"][0], 2)
            t["tdy"] = round(d["orig"][1] + y - d["start"][1], 2)
            self.owner.changed()
        elif d["what"] == "link":
            d["to"] = (x, y)
        elif d["what"] == "linkend":
            if isinstance(d["which"], int):                   # a bend follows the mouse
                if not d["pushed"]:
                    self.owner.remember()
                    d["pushed"] = True
                d["link"]["bends"][d["which"]] = [round(x, 2), round(y, 2)]
                self.owner.changed()
            else:
                d["to"] = (x, y)
        elif d["what"] == "slider":
            self._slide(d["item"], sp)
        elif d["what"] == "pad":
            self._pad(d["item"], sp, d.get("dx", 0.0))
        elif d["what"] == "band":
            self.band = (d["start"][0], d["start"][1], x, y)
        elif d["what"] == "move":
            if not d["pushed"]:
                self.owner.remember()
                d["pushed"] = True
            page = self.owner.page()
            items = PM.by_id(page, set(d["orig"]))
            for i in items:                                  # from where they started: no drift
                i["x"], i["y"] = d["orig"].get(i["id"], (i["x"], i["y"]))
            dx, dy = x - d["start"][0], y - d["start"][1]
            if _has(event.modifiers(), Qt.ShiftModifier):    # 5.6.26: Shift: only across or only down
                if abs(dx) >= abs(dy):
                    dy = 0.0
                else:
                    dx = 0.0
            self.guides = []
            others = [o for o in page["items"] if o["id"] not in d["orig"] and not PM.is_frame(o)]
            if bool(self.owner.look.get("snap", True)) != _has(event.modifiers(), Qt.ControlModifier):
                tol = SNAP_PX / max(self.scale, 1e-6)
                dx, dy, self.guides = PM.snap(items, others + PX.centre_targets(page), dx, dy, tol)
                b0 = PM.bounds(items)
                ex, ey = PX.equal_nudge((b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy), others, tol)
                dx, dy = dx + ex, dy + ey                     # half way between two neighbours: equal gaps
            PM.move(items, dx, dy)
            b1 = PM.bounds(items)
            self.gap_lines = PX.gaps(b1, others)              # 5.6.26: the distances to the neighbours
            d["snapped"] = bool(self.guides)                 # lined up with a button: the grid doesn't move it
            d["last"] = (x, y)
            self.owner.changed()
        elif d["what"] == "resize":
            if not d["pushed"]:
                self.owner.remember("resize")
                d["pushed"] = True
            self._resize_to(d, x, y, event.modifiers())
            self.owner.changed()
        elif d["what"] == "rotate":                           # 5.6.26: Shift: 15 degree steps
            if not d["pushed"]:
                self.owner.remember("turn")
                d["pushed"] = True
            it = d["item"]
            import math
            cx, cy = it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5
            ang = math.degrees(math.atan2(x - cx, -(y - cy)))
            if _has(event.modifiers(), Qt.ShiftModifier):
                ang = round(ang / 15.0) * 15.0
            it["rot"] = round(ang % 360.0, 1)
            self.owner.changed()
        self.update()

    def hideEvent(self, event):
        """Closed or hidden while dragging a slider: the undo chunk must still be closed (else Maya's undo
        stays inside it)."""
        if self.drag and self.drag.get("what") in ("slider", "pad"):
            self.drag = None
            cmds.undoInfo(closeChunk=True)
        try:
            super(Canvas, self).hideEvent(event)
        except Exception:
            pass

    def mouseReleaseEvent(self, event):
        d, self.drag = self.drag, None
        self.guides = []
        self.gap_lines = []
        if not d:
            return
        if d["what"] in ("link", "linkend"):                 # 5.6.25: dropped on an item: connect
            x, y = self.to_page(_pos(event))
            page = self.owner.page()
            target = PM.hit_any(page, x, y, True) if page else None
            if d["what"] == "link" and target is not None and target is not d["item"]:
                self.owner.remember()
                ln = PX.add_link(page, d["item"]["id"], target["id"], a_side=d["side"])
                self.owner.picked_links = {ln["id"]}
                self.owner.picked = set()
                self.owner.changed()
            elif d["what"] == "linkend" and d["which"] in ("a", "b") and target is not None:
                ln = d["link"]
                other = ln["b"] if d["which"] == "a" else ln["a"]
                if target["id"] != other:
                    self.owner.remember()
                    ln[d["which"]] = target["id"]
                    ln[d["which"] + "_side"] = "auto"
                    self.owner.changed()
        if d["what"] in ("slider", "pad"):
            cmds.undoInfo(closeChunk=True)
        elif d["what"] == "pan" and d.get("twin") is not None:
            sp = _pos(event)
            if abs(sp.x() - d["start"].x()) + abs(sp.y() - d["start"].y()) < 4:
                it = d["twin"]
                self.owner.run(lambda: self.owner.click_twin(it))
        elif d["what"] == "band":
            x0, y0, x1, y1 = self.band or (0, 0, 0, 0)
            self.band = None
            items = PM.in_rect(self.owner.page(), x0, y0, x1, y1)
            if self.owner.editing:
                self.owner.picked |= set(i["id"] for i in items)
            else:
                self.owner.select_items(items, d["mods"])
        elif d["what"] == "move" and self.owner.grid() and not d.get("snapped"):
            PM.move(PM.by_id(self.owner.page(), set(d.get("orig") or self.owner.picked)), 0, 0, self.owner.grid())
        if d["what"] in ("move", "resize"):                   # pinned ones keep their new place in the window
            self.store_pins(PM.by_id(self.owner.page(), set(d.get("orig") or self.owner.picked)))
            self.owner.refresh_list()
            self.owner.hier = None
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        x, y = self.to_page(_pos(event))
        page = self.owner.page()
        if self.owner.editing:                                # a frame's title / a text: rename it
            it = PM.hit_any(page, x, y, True) if page else None
            if it is not None and (PM.is_text(it) or (PM.is_frame(it) and PM.on_title(it, x, y))):
                self.owner.picked = {it["id"]}
                self.owner.relabel()
            elif it is None:
                self.frame()
            return
        it = PM.hit_any(page, x, y) if page else None
        if it is None:                                        # 5.6.24: empty space - the whole page
            self.frame()
            return
        if it.get("kind") == "slider2d":                      # double-click a pad: back to the middle (rest)
            self.owner.run(lambda: PM.reset_slider2d(it, self.owner.ns))
            self.update()
            return
        if it.get("kind") == "select":
            self.owner.run(lambda: (self.owner.click(it, Qt.NoModifier), A.select_set("limb")))

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        if not steps:
            return
        sp = _pos(event)
        x0 = (sp.x() - self.offset.x()) / self.scale
        y0 = (sp.y() - self.offset.y()) / self.scale
        self.scale = max(0.02, min(20.0, self.scale * (1.15 ** steps)))
        self.offset = QtCore.QPointF(sp.x() - x0 * self.scale, sp.y() - y0 * self.scale)
        self.update()

    def contextMenuEvent(self, event):
        x, y = self.to_page(QtCore.QPointF(event.pos().x(), event.pos().y()))
        self.owner.context_menu(event.globalPos(), x, y)

    def keyPressEvent(self, event):
        if not self.owner.key(event):
            super(Canvas, self).keyPressEvent(event)


# ===========================================================================
# the window
# ===========================================================================

_CLIPBOARD = {}                                          # 5.6.26: Ctrl+C / Ctrl+V (this Maya session)


class _ShapeButton(QtWidgets.QToolButton):
    """5.6.26: a shape in the gallery - hovering tries it on the picked buttons, leaving puts them back."""

    def __init__(self, name, on_enter, on_leave):
        super(_ShapeButton, self).__init__()
        self.name, self._enter, self._leave = name, on_enter, on_leave
        self.setIconSize(QtCore.QSize(34, 34))
        self.setFixedSize(76, 62)

    def enterEvent(self, event):
        try:
            self._enter()
        except Exception:
            pass

    def leaveEvent(self, event):
        try:
            self._leave()
        except Exception:
            pass


_SHAPE_ICONS = {}


def _shape_icon(name):
    """A shape drawn small (the gallery)."""
    if name not in _SHAPE_ICONS:
        got = PX.find_shape(name)
        pix = QtGui.QPixmap(40, 40)
        pix.fill(QtGui.QColor(0, 0, 0, 0))
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtGui.QPen(QtGui.QColor(30, 30, 34), 1.2))
        p.setBrush(QtGui.QColor(110, 180, 255))
        r = QtCore.QRectF(4, 4, 32, 32)
        pts = got[1] if got else None
        if pts:
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(r.left() + u * r.width(), r.top() + v * r.height())
                                           for u, v in pts]))
        elif name in ("ellipse", "round", "ring"):
            p.drawEllipse(r if name != "round" else r.adjusted(2, 2, -2, -2))
        elif name == "pill":
            p.drawRoundedRect(r.adjusted(0, 8, 0, -8), 8, 8)
        else:
            p.drawRect(r)
        p.end()
        _SHAPE_ICONS[name] = QtGui.QIcon(pix)
    return _SHAPE_ICONS[name]


class _Floating(QtWidgets.QWidget):
    """5.6.23: the button list (5.6.26: or the Item panel) in its own small window; closing it docks it back."""

    def __init__(self, owner, title="Picker - buttons", on_close=None):
        super(_Floating, self).__init__(owner, Qt.Tool)
        self.owner = owner
        self.on_close = on_close
        self.setWindowTitle(title)
        QtWidgets.QVBoxLayout(self).setContentsMargins(2, 2, 2, 2)

    def closeEvent(self, event):
        (self.on_close or self.owner.dock_list)()
        try:
            super(_Floating, self).closeEvent(event)
        except Exception:
            pass


class Picker(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(Picker, self).__init__(parent)
        self.ns = ""
        self._gap = 4.0
        self.anchor = None
        self.picker = None
        self.index = 0
        self.editing = False
        self.picked = set()
        self.picked_links = set()                            # 5.6.25: picked connectors (Edit)
        self.anchor = None                                   # the button clicked last (Same size matches it)
        self.framed = False
        self.dirty = False
        self.history = PM.History()
        self.side = None                                     # 5.6.22: the page shown beside (its index), or None
        self._panel_busy = False
        self._panel_for = None                               # 5.6.23: the picked the Item panel shows
        self._nodes = {}
        self._sel = None
        self._missing_n = 0
        self.preview = False                                 # 5.6.26: Edit, seen as the animators see it
        PX.SWITCH_READER[0] = self._switch_value
        self._ikfk = {}
        self._found_pages = {}
        self.views = {}                                      # 5.6.24: each page's zoom / pan (this session)
        self.hier = None
        self._keyed = {}
        self._my_btns = []
        self.search_ids = set()                              # 5.6.23: buttons matching the list's search
        self.look = PM.prefs()                               # 5.6.23: your settings (this computer)
        self.list_window = None
        self.panel_window = None                             # 5.6.26: the Item panel floating
        self.tools = []                                      # (section, QToolButton)
        self.setObjectName("gusAnimtoolPickerWidget")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(3)

        # 5.6.23: the mode band - always clear whether you're animating or editing (and what's not saved)
        self.band = QtWidgets.QLabel("")
        self.band.setAlignment(Qt.AlignCenter)
        self.band.setMinimumHeight(20)
        bandrow = QtWidgets.QHBoxLayout()                     # 5.6.26: Undo / Redo / Preview always there
        bandrow.addWidget(self.band, 1)
        self.band_tools = []
        for word, tip, fn in (("Undo", "Undo the last picker edit (Z, Ctrl+Z)", lambda: self.undo()),
                              ("Redo", "Redo (Shift+Z, Ctrl+Y)", lambda: self.redo()),
                              ("History", "Your recent edits - go back several at once", lambda: self.history_dialog()),
                              ("Preview", "See the page as the animators will (P) - click the page to come back",
                               lambda: self.toggle_preview())):
            b = QtWidgets.QToolButton()
            b.setText(word)
            b.setToolTip(tip)
            b.clicked.connect((lambda f=fn: lambda *_: f())())
            b.setVisible(False)
            bandrow.addWidget(b)
            self.band_tools.append(b)
        lay.addLayout(bandrow)

        top = QtWidgets.QHBoxLayout()
        self.chars = QtWidgets.QComboBox()
        self.chars.setToolTip("The character (namespace).")
        self.chars.currentIndexChanged.connect(lambda *_: self.load())
        top.addWidget(self.chars, 1)
        for label, tip, fn in (("Refresh", "Read the rig again (new controls, other characters).", self.refresh),
                               ("Frame", "Fit the page in the window (F; Shift+F: the picked / selected).",
                                lambda: self.canvas.frame())):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            top.addWidget(b)
        self.side_btn = QtWidgets.QPushButton("Side by side")
        self.side_btn.setToolTip("Show another page beside this one (Body with Face...).")
        sm = QtWidgets.QMenu(self.side_btn)
        sm.aboutToShow.connect(lambda: self.fill_side_menu(sm))
        self.side_btn.setMenu(sm)
        top.addWidget(self.side_btn)
        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setToolTip("Edit the picker: move, resize, colour, shape, add buttons... (Save keeps it).")
        self.edit_btn.toggled.connect(self.set_editing)
        top.addWidget(self.edit_btn)
        lay.addLayout(top)

        view = QtWidgets.QHBoxLayout()                       # 5.6.23: the view - text size, the list, your look
        aa = QtWidgets.QLabel("Text")
        aa.setToolTip("The size of every button's text (yours, on this computer).")
        view.addWidget(aa)
        self.text_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.text_slider.setRange(50, 300)
        self.text_slider.setValue(int(round(float(self.look.get("text_scale", 1.0)) * 100)))
        self.text_slider.setToolTip("Text size for every button: 50% - 300% (yours, on this computer).")
        self.text_slider.valueChanged.connect(lambda v: self.set_text_scale(v / 100.0))
        view.addWidget(self.text_slider, 1)
        self.text_pct = QtWidgets.QLabel("%d%%" % self.text_slider.value())
        view.addWidget(self.text_pct)
        self.list_btn = QtWidgets.QPushButton("List")
        self.list_btn.setCheckable(True)
        self.list_btn.setToolTip("The button list: every button on the page, search, pins / locks.")
        self.list_btn.toggled.connect(self.show_list)
        view.addWidget(self.list_btn)
        look = QtWidgets.QPushButton("Look...")
        look.setToolTip("Your picker look: theme, selected / hover colours, compact toolbar, silhouette, side "
                        "colours, where new buttons go (on this computer, never in the rig).")
        look.clicked.connect(self.look_dialog)
        view.addWidget(look)
        self.behind_btn = QtWidgets.QPushButton("Back")          # 5.6.24
        self.behind_btn.setCheckable(True)
        self.behind_btn.setToolTip("See the page from behind: left and right swapped (for animating from the back).")
        self.behind_btn.setChecked(bool(self.look.get("behind")))
        self.behind_btn.toggled.connect(lambda on: self.toggle_behind(on))
        view.addWidget(self.behind_btn)
        self.layers_btn = QtWidgets.QPushButton("Layers")       # 5.6.25
        self.layers_btn.setToolTip("Show / hide the page's layers (Edit: new layer, put the picked on one, lock).")
        lm = QtWidgets.QMenu(self.layers_btn)
        lm.aboutToShow.connect(lambda: self.fill_layers_menu(lm))
        self.layers_btn.setMenu(lm)
        view.addWidget(self.layers_btn)
        helpb = QtWidgets.QPushButton("?")
        helpb.setToolTip("The keys and clicks (?)")
        helpb.clicked.connect(self.toggle_help)
        view.addWidget(helpb)
        lay.addLayout(view)

        findrow = QtWidgets.QHBoxLayout()                     # 5.6.24: find (Ctrl+F) - Enter selects what's found
        self.find_box = QtWidgets.QLineEdit()
        self.find_box.setPlaceholderText("Find (name or text) - Enter selects, Edit: picks")
        self.find_box.textChanged.connect(self.find_everywhere)
        self.find_box.returnPressed.connect(self.find_go)
        self.find_box.setVisible(False)
        findrow.addWidget(self.find_box, 1)
        self.find_close = QtWidgets.QToolButton()
        self.find_close.setText("x")
        self.find_close.clicked.connect(self.hide_find)
        self.find_close.setVisible(False)
        findrow.addWidget(self.find_close)
        lay.addLayout(findrow)

        tabs = QtWidgets.QHBoxLayout()
        self.tabs = QtWidgets.QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.currentChanged.connect(self.set_page)
        tabs.addWidget(self.tabs, 1)
        self.add_page_btn = QtWidgets.QPushButton("Page")
        self.add_page_btn.setToolTip("New / duplicate / rename / delete a page, its background and silhouette.")
        pm = QtWidgets.QMenu(self.add_page_btn)
        pm.aboutToShow.connect(lambda: self.fill_page_menu(pm))
        self.add_page_btn.setMenu(pm)
        self.add_page_btn.setVisible(False)
        tabs.addWidget(self.add_page_btn)
        lay.addLayout(tabs)

        self.new_btn = QtWidgets.QPushButton("")
        self.new_btn.setToolTip("Controls the rig has that no button selects: see them, add them where they sit, or "
                                "take out the ones you don't need.")
        self.new_btn.setStyleSheet("background-color: #2f5f86;")
        self.new_btn.clicked.connect(self.missing_dialog)
        self.new_btn.setVisible(False)
        lay.addWidget(self.new_btn)
        self.clean_btn = QtWidgets.QPushButton("")              # 5.6.22: duplicates / gone controls
        self.clean_btn.setStyleSheet("background-color: #86602f;")
        self.clean_btn.clicked.connect(self.clean_up)
        self.clean_btn.setVisible(False)
        lay.addWidget(self.clean_btn)
        self.pin_btn = QtWidgets.QPushButton("")                # 5.6.23: pinned buttons don't zoom - say so
        self.pin_btn.setToolTip("Pinned buttons stay still in the window when you zoom or pan. Click: unpin them "
                                "all (they stay where they are on the page).")
        self.pin_btn.setStyleSheet("background-color: #2f7a77;")
        self.pin_btn.clicked.connect(self.unpin_all)
        self.pin_btn.setVisible(False)
        lay.addWidget(self.pin_btn)
        self.norm_btn = QtWidgets.QPushButton("")               # 5.6.24: a page far too big / small
        self.norm_btn.setToolTip("The page is much bigger (or smaller) than its buttons: the text can't show at the "
                                 "zoom it needs. Normalize keeps the layout, in sane units, the page fitted.")
        self.norm_btn.setStyleSheet("background-color: #5b4f86;")
        self.norm_btn.clicked.connect(self.normalize_page)
        self.norm_btn.setVisible(False)
        lay.addWidget(self.norm_btn)

        self.canvas = Canvas(self)
        self.mid = QtWidgets.QHBoxLayout()                     # the list, the canvas, the Item panel
        self.mid.setContentsMargins(0, 0, 0, 0)
        self.list_box = self._build_list()
        self.mid.addWidget(self.list_box)
        self.mid.addWidget(self.canvas, 1)
        self.panel = self._build_panel()
        self.panel.setVisible(False)
        self.mid.addWidget(self.panel)
        lay.addLayout(self.mid, 1)

        # 5.6.23: one toolbar in sections (Create / Arrange / Style / Controls / File) - icon + word, or icons only
        self.edit_bar = QtWidgets.QWidget()
        self.tool_grid = QtWidgets.QGridLayout(self.edit_bar)
        self.tool_grid.setContentsMargins(0, 0, 0, 0)
        self.tool_grid.setSpacing(2)
        self.quick_bar = self.edit_bar                       # (5.6.21 name)
        self.section_labels = {}
        self.tool_by_id = {}                                 # 5.6.25: your toolbar: tools by id
        for section, cells in self._tool_spec():
            for icon, word, tip, fn, menu in cells:
                b = QtWidgets.QToolButton()
                b.setIcon(_icon(icon))
                b.setText(word)
                b.setToolTip("%s - %s" % (word, tip))
                b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                if fn is not None:
                    b.clicked.connect(fn)
                if menu is not None:
                    m = QtWidgets.QMenu(b)
                    m.aboutToShow.connect((lambda mm=m, f=menu: lambda: f(mm))())
                    b.setMenu(m)
                    b.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup if fn is not None else
                                   QtWidgets.QToolButton.InstantPopup)
                b.word = word
                b.tool_id = icon
                self.tools.append((section, b))
                self.tool_by_id[icon] = b
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setToolTip("Keep it. In the rig's own file: saved INTO the rig (everyone gets it). With a "
                                 "referenced rig: yours, on this computer. Ctrl+S")
        self.save_btn.clicked.connect(self.save)
        self._layout_tools()
        self.edit_bar.setVisible(False)
        lay.addWidget(self.edit_bar)

        self.use_bar = QtWidgets.QWidget()
        ub = QtWidgets.QGridLayout(self.use_bar)
        ub.setContentsMargins(0, 0, 0, 0)
        ub.setSpacing(2)
        for i, (label, tip, fn) in enumerate((
                ("All", "Every control of the character.", lambda: self.select_scope("all")),
                ("Left", "Every left control.", lambda: self.select_scope("L")),
                ("Right", "Every right control.", lambda: self.select_scope("R")),
                ("Page", "Every control on this page.", lambda: self.select_scope("page")),
                ("Twin", "The other side of the selection (Alt+click a button: its twin).",
                 lambda: A.select_twin("other")),
                ("IK / FK", "Switch the selected limbs, no jump.", lambda: A.switch("toggle")),
                ("Reset", "The selection back to rest.", lambda: A.reset_pose("selection")),
                ("Key", "Key the selection.", self.key))):
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect((lambda f=fn: lambda: self.run(f))())
            ub.addWidget(b, i // 4, i % 4)
        self.frames_btn = QtWidgets.QPushButton("Frames")      # 5.6.21: show / hide the page's frames
        self.frames_btn.setToolTip("Show or hide each frame of this page (and its buttons).")
        fm = QtWidgets.QMenu(self.frames_btn)
        fm.aboutToShow.connect(lambda: self.fill_frames_menu(fm))
        self.frames_btn.setMenu(fm)
        ub.addWidget(self.frames_btn, 2, 0, 1, 2)
        self.sets_btn = QtWidgets.QPushButton("My sets")         # 5.6.24: yours, on this computer
        self.sets_btn.setToolTip("Your own quick selection sets for this rig (on this computer): save the "
                                 "selection, click one to select it.")
        sm2 = QtWidgets.QMenu(self.sets_btn)
        sm2.aboutToShow.connect(lambda: self.fill_mysets_menu(sm2))
        self.sets_btn.setMenu(sm2)
        ub.addWidget(self.sets_btn, 2, 2, 1, 2)
        lay.addWidget(self.use_bar)
        self.my_row = QtWidgets.QHBoxLayout()
        lay.addLayout(self.my_row)

        self.status = QtWidgets.QLabel("")                    # 5.6.23: what's on the page, at a glance
        self.status.setStyleSheet("color: #a8adb5; padding: 1px 3px;")
        lay.addWidget(self.status)
        self.set_band()
        self.fill_characters()
        self.list_btn.setChecked(bool(self.look.get("list_shown", True)))
        if self.look.get("list_float") and self.list_btn.isChecked():
            self.float_list()

    # -- 5.6.23: the toolbar -------------------------------------------------
    SECTIONS = (("Create", ("addsel", "set", "toggle", "space", "script", "text", "note", "more")),
                ("Select", ("selectmenu", "copy", "paste", "rename")),
                ("Arrange", ("group", "ungroup", "limbs", "front", "back", "up", "down", "lock", "pin", "mirror",
                             "mirrorlay", "frontview", "normalize")),
                ("Align & space", ("left", "hcenter", "right", "top", "vcenter", "bottom", "spreadx", "spready",
                                   "line", "arc", "page", "grid", "snap")),
                ("Size & text", ("same", "fittext", "textup", "textdown", "numbers", "labels")),
                ("Style", ("gallery", "shape", "colour", "sides", "copystyle", "pastestyle", "styles", "rules")),
                ("Connect", ("connect", "hierlines")),
                ("Background & layers", ("silhouette", "background", "layers")),
                ("Controls", ("missing", "exclude", "clean", "unpin", "pairs")),
                ("File", ("undo", "redo", "history", "auto", "file", "customize")))

    def _tool_spec(self):
        """5.6.25: the usual toolbar - like tools together; your own order: Customize."""
        cells = dict((c[0], c) for _s, cs in self._tool_cells() for c in cs)
        old = cells
        cells = {}
        for t, c in old.items():                              # 5.6.26: copy / paste style get their own ids
            t2 = {"copy": "copystyle", "paste": "pastestyle"}.get(t, t)
            cells[t2] = (t2,) + tuple(c[1:])
        cells["colour"] = ("colour", "Colour", "the picked buttons' colour (the arrow: like their controls, by side, "
                           "Maya's colours)", self.recolour, self.fill_colour_menu)
        cells.update(dict((c[0], c) for c in (
            ("selectmenu", "Select", "same shape / colour / size / layer, everything in a group, invert", None,
             self.fill_select_menu),
            ("copy", "Copy", "the picked (Ctrl+C) - paste on any page or picker", self.copy_picked, None),
            ("paste", "Paste", "what you copied (Ctrl+V; Ctrl+Shift+V: in place)", lambda: self.paste(), None),
            ("rename", "Rename", "the picked's text at once: prefix, suffix, find / replace, numbers, case (F2)",
             self.rename_dialog, None),
            ("gallery", "Shapes", "every shape drawn - the rig tool's too; the control's own curve; the most "
             "alike", self.shape_gallery, None),
            ("limbs", "Limbs", "a frame round each limb's buttons (from the rig's IK / FK limbs)", self.group_by_limb,
             None),
            ("history", "History", "your recent edits - go back several at once", self.history_dialog, None),
            ("note", "Note", "a sticky note: a coloured text with several lines", lambda: self.add_note(), None),
            ("connect", "Connect", "the picked chained by connectors (or drag from an item's blue dot to another; "
             "Ctrl+click a picked connector: a bend)", self.connect_picked, None),
            ("hierlines", "Lines from rig", "connectors from the rig's hierarchy (parent -> child) - editable after",
             self.lines_from_hierarchy, None),
            ("silhouette", "Silhouette", "the meshes seen from the front behind the page, kept in the picker",
             lambda: self.run(lambda: self.silhouette_picture()), None),
            ("background", "Background", "the page's background: silhouette, viewport picture, outline, your "
             "picture, opacity, place", self.background_dialog, None),
            ("layers", "Layers", "show / hide / lock layers; new layer; put the picked on one", None,
             self.fill_layers_menu),
            ("customize", "Customize", "your toolbar: sections, order, hide tools (on this computer)",
             self.customize_toolbar, None))))
        out = []
        for section, ids in self.SECTIONS:
            out.append((section, [cells[t] for t in ids if t in cells]))
        placed = set(t for _s, ids in self.SECTIONS for t in ids)
        rest = [c for t, c in cells.items() if t not in placed]
        if rest:
            out[-1][1].extend(rest)
        return out

    def _tool_cells(self):
        """[(section, [(icon, word, tip, click, menu filler)])]."""
        al = lambda how: (lambda: self.edit(lambda its: PM.align(its, how)))
        return [
            ("Create", [
                ("addsel", "Add selected", "a button per control selected in Maya - where it sits seen from the "
                 "front (the arrow: or at the mouse)", lambda: self.add_selected(), self.fill_add_menu),
                ("set", "Set", "one button that selects all the picked buttons' controls", self.add_set, None),
                ("toggle", "Toggle", "a button that flips an attribute on / off (pick it in the Channel Box)",
                 lambda: self.add_widget("toggle"), None),
                ("text", "Text", "a title / text you can place anywhere", lambda: self.add_text(), None),
                ("group", "Group", "a frame with a title round the picked (Ctrl+G) - its title selects them all",
                 self.group, None),
                ("ungroup", "Ungroup", "take the picked frame away - the buttons stay (Ctrl+Shift+G)",
                 self.ungroup, None),
                ("space", "Space", "a space switch: an enum attribute (Follow, Space...) picked in the Channel Box - "
                 "click it to choose, the control stays where it is", lambda: self.add_enum(), None),
                ("script", "Script", "a button that runs a script: ready-made ones, a test run",
                 lambda: self.script_dialog(), None),
                ("more", "More", "slider, check box, 2D slider; the Switches / Face sliders pages", None,
                 self.fill_more_menu)]),
            ("Arrange", [
                ("left", "Left", "line up on the left", al("left"), None),
                ("hcenter", "Centre", "one column, centred", al("hcenter"), None),
                ("right", "Right", "line up on the right", al("right"), None),
                ("top", "Top", "line up at the top", al("top"), None),
                ("vcenter", "Middle", "one row, centred", al("vcenter"), None),
                ("bottom", "Bottom", "line up at the bottom", al("bottom"), None),
                ("spreadx", "Spread", "even spacing across (first to last)",
                 lambda: self.edit(lambda its: PM.distribute(its, "x")), None),
                ("spready", "Spread", "even spacing down (first to last)",
                 lambda: self.edit(lambda its: PM.distribute(its, "y")), None),
                ("same", "Same size", "the size of the button clicked last", self.same_size, None),
                ("page", "Page centre", "the picked, as a block, in the middle of the page",
                 lambda: self.edit(lambda its: PM.centre_on_page(self.page(), its)), None),
                ("frontview", "Front view", "buttons where their controls sit seen from Maya's front view - the "
                 "picked, or the pages you choose", self.front_view_dialog, None),
                ("mirror", "Mirror", "a twin on the other side", self.mirror, None),
                ("mirrorlay", "Mirror page", "every button of one side placed as the mirror of its twin",
                 None, self.fill_mirror_menu),
                ("line", "Line", "the picked evenly on a line, first to last", self.arrange_line, None),
                ("arc", "Arc", "the picked evenly on an arc (fingers as a fan)", self.arrange_arc, None),
                ("front", "Front", "bring to front (Ctrl+Shift+])", lambda: self.order("front"), None),
                ("back", "Back", "send to back (Ctrl+Shift+[)", lambda: self.order("back"), None),
                ("up", "Up", "one step up (Ctrl+])", lambda: self.order("up"), None),
                ("down", "Down", "one step down (Ctrl+[)", lambda: self.order("down"), None),
                ("grid", "Grid", "snap to a grid (dots) - the arrow: its size", self.toggle_grid,
                 self.fill_grid_menu),
                ("snap", "Snap", "line up with the other buttons while dragging (on / off; Ctrl while dragging "
                 "does the other)", self.toggle_snap, None),
                ("normalize", "Normalize", "the page in sane units, fitted to its buttons (it opens big in the "
                 "window) - the layout stays", self.normalize_page, None)]),
            ("Style", [
                ("shape", "Shape", "round, square, ellipse, diamond, pill, ring, star, arrows, outline...", None,
                 self.fill_shape_menu),
                ("colour", "Colour", "the picked buttons' colour", self.recolour, None),
                ("sides", "Sides", "colour by side: your left / middle / right colours (the picked, or the page)",
                 self.colour_sides, None),
                ("copy", "Copy style", "shape, colour, size, text style of the picked one", self.copy_style, None),
                ("paste", "Paste style", "onto the picked ones", self.paste_style, None),
                ("styles", "Templates", "ready-made and your saved styles: apply one; save the picked one's",
                 None, self.fill_styles_menu),
                ("rules", "Rules", "style rules: name pattern = template (*_FK_ctrl = FK dot...)", self.rules_dialog,
                 None),
                ("textup", "Text +", "bigger letters on the picked", lambda: self.text_size(1.2), None),
                ("textdown", "Text -", "smaller letters on the picked", lambda: self.text_size(1 / 1.2), None),
                ("fittext", "Fit text", "buttons as wide as their text (the picked, or the page)", self.fit_text,
                 None),
                ("numbers", "Numbers", "chains numbered 1, 2, 3 ('Ear FK 1') - the picked, or the page",
                 self.chain_numbers, None),
                ("lock", "Lock", "lock / unlock the picked - they can't be moved by accident (Ctrl+L)",
                 self.toggle_lock, None),
                ("pin", "Pin", "pin / unpin the picked: they stay still in the window when you zoom or pan",
                 self.toggle_pin, None)]),
            ("Controls", [
                ("missing", "Missing", "controls with no button: add them where they sit, or take them out",
                 self.missing_dialog, None),
                ("exclude", "Take out", "the picked buttons' controls off the picker for good (not missing, left "
                 "out by Auto layout) - Missing > Taken out puts them back", self.exclude_picked, None),
                ("clean", "Clean up", "buttons twice on a page, buttons for controls that are gone",
                 self.clean_up, None),
                ("labels", "Labels", "your rules for the buttons' text (take out words, 01 -> 1, Capitals)",
                 self.label_dialog, None),
                ("unpin", "Unpin all", "every pinned button back on the page (they zoom again)",
                 self.unpin_all, None),
                ("pairs", "Pairs", "mirror pairs: the controls whose twin isn't found or isn't where it should be "
                 "- link them", self.pairs_dialog, None)]),
            ("File", [
                ("undo", "Undo", "Ctrl+Z", self.undo, None),
                ("redo", "Redo", "Ctrl+Y", self.redo, None),
                ("auto", "Auto layout", "throw this picker away and lay it out again (taken-out controls stay "
                 "out)", self.auto, None),
                ("file", "Picker", "export / import the picker or one page, a page as a picture, your keys", None,
                 self.picker_menu)])]

    def _spec_ids(self):
        return [(section, [c[0] for c in cells]) for section, cells in self._tool_spec()]

    def _layout_tools(self):
        """The toolbar's buttons in YOUR sections and order (Customize...): icon + word, or (compact) icons only;
        hidden tools left out."""
        compact = bool(self.look.get("compact"))
        cols = 18 if compact else 8                          # compact: each section on one row
        for i in reversed(range(int(self.tool_grid.count() or 0))):      # laid out again: emptied first
            self.tool_grid.takeAt(i)
        layout = PX.toolbar_layout(self._spec_ids())
        shown = set(t for _s, ids in layout for t in ids)
        for t, b in self.tool_by_id.items():
            b.setVisible(t in shown)
        for lab in self.section_labels.values():
            lab.setVisible(False)
        row = 0
        self.tools = []
        for section, ids in layout:
            if section not in self.section_labels:
                head = QtWidgets.QLabel(section)
                head.setStyleSheet("color: #9aa0aa; font-size: 9px;")
                self.section_labels[section] = head
            head = self.section_labels[section]
            head.setVisible(True)
            rows = max(1, (len(ids) + cols - 1) // cols)
            self.tool_grid.addWidget(head, row, 0, rows, 1)  # the section's name, left
            for i, t in enumerate(ids):
                b = self.tool_by_id[t]
                b.setToolButtonStyle(Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon)
                self.tool_grid.addWidget(b, row + i // cols, 1 + i % cols)
                self.tools.append((section, b))
            row += rows
        self.tool_grid.addWidget(self.save_btn, row, 0, 1, cols + 1)

    def fill_add_menu(self, menu):
        menu.clear()
        at = self.look.get("add_at", "front")
        for label, key in (("Where they sit (front view)", "front"), ("At the mouse", "mouse")):
            a = menu.addAction(("> " if at == key else "   ") + label)
            a.triggered.connect((lambda k=key: lambda *_: self.set_look("add_at", k))())
        menu.addSeparator()
        menu.addAction("One button for all the selected...", lambda: self.add_group())

    def fill_more_menu(self, menu):
        menu.clear()
        menu.addAction("Slider (Channel Box attribute)", lambda: self.add_widget("slider"))
        menu.addAction("Check box (Channel Box attribute)", lambda: self.add_widget("check"))
        menu.addAction("2D slider (two Channel Box attributes)", lambda: self.add_pad())
        menu.addAction("Space switch (Channel Box enum attribute)", lambda: self.add_enum())
        menu.addAction("Script button...", lambda: self.script_dialog())
        menu.addSeparator()
        menu.addAction("Make the Switches page (visibility, IK / FK, spaces)", self.make_switches_page)
        menu.addAction("Make the Face sliders page", self.make_face_page)

    def fill_grid_menu(self, menu):
        menu.clear()
        for g in (0, 4, 8, 16, 32):
            menu.addAction("off" if not g else "%d" % g, (lambda v=g: lambda: self.set_grid(v))())

    def fill_shape_menu(self, menu):
        menu.clear()
        for s in PM.SHAPES:
            menu.addAction(s, (lambda x=s: lambda: self.edit(lambda its: PM.set_value(its, "shape", x)))())

    def fill_page_menu(self, menu):
        menu.clear()
        menu.addAction("New page...", self.new_page)
        if self.page():
            menu.addAction("Duplicate this page (try things on the copy)", self.duplicate_page)
            menu.addAction("Normalize this page (sane units, fitted)", self.normalize_page)
            menu.addAction("Page text size...", self.page_text_size)
            menu.addAction("Background (front picture, outline, opacity)...", self.background_dialog)
            menu.addSeparator()
            menu.addAction("Make the Switches page", self.make_switches_page)
            menu.addAction("Make the Face sliders page", self.make_face_page)
            menu.addSeparator()
            self.page_menu(menu)

    # -- 5.6.23: the button list ---------------------------------------------
    def _build_list(self):
        box = QtWidgets.QWidget()
        box.setMinimumWidth(150)
        box.setMaximumWidth(260)
        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(2)
        head = QtWidgets.QHBoxLayout()
        self.list_title = QtWidgets.QLabel("Buttons")
        head.addWidget(self.list_title, 1)
        self.float_btn = QtWidgets.QToolButton()
        self.float_btn.setText("Undock")
        self.float_btn.setToolTip("The list in its own window (close it to dock it back).")
        self.float_btn.clicked.connect(lambda: self.dock_list() if self.list_window is not None else
                                       self.float_list())
        head.addWidget(self.float_btn)
        v.addLayout(head)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search (name or text)...")
        self.search.textChanged.connect(self.filter_list)
        v.addWidget(self.search)
        self.button_list = QtWidgets.QListWidget()
        self.button_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.button_list.itemSelectionChanged.connect(self.list_picked)
        v.addWidget(self.button_list, 1)
        box.setVisible(False)
        return box

    def show_list(self, on):
        self.set_look("list_shown", bool(on))
        if self.list_window is not None:
            self.list_window.setVisible(bool(on))
        else:
            self.list_box.setVisible(bool(on))
        if on:
            self.refresh_list()

    def float_list(self):
        if self.list_window is not None:
            return
        self.list_window = _Floating(self)
        self.list_window.layout().addWidget(self.list_box)
        self.list_box.setMaximumWidth(16777215)
        self.list_box.setVisible(True)
        self.float_btn.setText("Dock")
        self.list_window.resize(240, 420)
        self.list_window.show()
        self.set_look("list_float", True)

    def dock_list(self):
        if self.list_window is None:
            return
        win, self.list_window = self.list_window, None
        self.mid.insertWidget(0, self.list_box)
        self.list_box.setMaximumWidth(260)
        self.list_box.setVisible(self.list_btn.isChecked())
        self.float_btn.setText("Undock")
        self.set_look("list_float", False)
        try:
            win.hide()
            win.deleteLater()
        except Exception:
            pass

    def list_rows(self):
        """[(id, text, flags)] - 5.6.26: an outline: each frame, its buttons under it (indented), then the rest;
        top to bottom as on the page."""
        page = self.page()
        if not page:
            return []
        order = lambda its: sorted(its, key=lambda i: (round(i["y"] / 8.0), i["x"]))

        def row(it, indent=""):
            kind = it.get("kind", "select")
            nodes = ", ".join(it.get("nodes") or [])
            text = it.get("label") or nodes or kind
            if kind == "frame":
                text = "[%s] %s" % ("folded" if it.get("folded") else "group", text)
            elif kind == "text":
                text = "[%s] %s" % ("note" if it.get("note") else "text", text.replace("\n", " "))
            elif kind not in ("select",):
                text = "[%s] %s" % (kind, text)
            if nodes and nodes != it.get("label"):
                text += "   (%s)" % nodes
            flags = [f for f, on in (("pin", it.get("pin")), ("lock", it.get("locked")),
                                     ("missing", kind != "command" and it.get("nodes") and not self.nodes_of(it)))
                     if on]
            if it.get("layer"):
                text += "   {%s}" % it["layer"]
            return it["id"], indent + text, flags
        rows, placed = [], set()
        for fr in order([i for i in page["items"] if PM.is_frame(i)]):
            rows.append(row(fr))
            placed.add(fr["id"])
            for m in order([m for m in PM.frame_members(page, fr) if m["id"] not in placed]):
                rows.append(row(m, "      "))
                placed.add(m["id"])
        for it in order([i for i in page["items"] if i["id"] not in placed]):
            rows.append(row(it))
        return rows

    def refresh_list(self):
        lst = getattr(self, "button_list", None)
        if lst is None or not (self.list_btn.isChecked() if hasattr(self, "list_btn") else False):
            return
        self._list_busy = True
        try:
            lst.clear()
            for iid, text, flags in self.list_rows():
                row = QtWidgets.QListWidgetItem(text)
                row.setData(Qt.UserRole, iid)
                if "missing" in flags:
                    row.setForeground(QtGui.QBrush(QtGui.QColor(235, 110, 100)))
                if flags:
                    row.setIcon(_icon("pin" if "pin" in flags else "lock" if "lock" in flags else "exclude"))
                    row.setToolTip(", ".join(flags))
                else:                                          # 5.6.24: its colour
                    it = (PM.by_id(self.page(), {iid}) or [{}])[0]
                    row.setIcon(_swatch(it.get("on_rgb") if it.get("kind") == "toggle" else it.get("rgb")))
                lst.addItem(row)
            page = self.page()
            self.list_title.setText("Buttons - %s (%d)" % (page["name"], len(page["items"])) if page else "Buttons")
        finally:
            self._list_busy = False
        self.filter_list(self.search.text())

    def filter_list(self, text):
        text = (text or "").strip().lower()
        lst = self.button_list
        self.search_ids = set()
        for i in range(lst.count()):
            row = lst.item(i)
            hit = not text or text in row.text().lower()
            row.setHidden(not hit)
            if hit and text:
                self.search_ids.add(row.data(Qt.UserRole))
        self.canvas.update()

    def list_picked(self):
        if getattr(self, "_list_busy", False):
            return
        ids = set(r.data(Qt.UserRole) for r in self.button_list.selectedItems())
        if not ids:
            return
        items = PM.by_id(self.page(), ids) if self.page() else []
        if self.editing:
            self.picked = ids
        else:
            self.run(lambda: self.select_items(items, Qt.NoModifier))
        self.canvas.update()

    # -- 5.6.23: your look ---------------------------------------------------
    def set_look(self, key, value):
        self.look[key] = value
        PM.set_pref(key, value)
        if key == "compact":
            self._layout_tools()
        self.canvas.update()

    def set_text_scale(self, value):
        value = max(0.5, min(3.0, float(value)))
        self.set_look("text_scale", round(value, 2))
        self.text_pct.setText("%d%%" % int(round(value * 100)))

    def set_band(self):
        if self.editing:
            text = "EDIT  -  drag to move, corner to resize, right-click for more, Ctrl+S saves%s" % (
                "    -    NOT SAVED" if self.dirty else "")
            style = "background-color: #c8761c; color: #111; font-weight: bold; border-radius: 3px;"
        else:
            text = "ANIMATE  -  click to select (Shift adds, Ctrl takes away, Alt: the twin), wheel zooms, F frames"
            style = "background-color: #3c3f45; color: #d8dbe0; border-radius: 3px;"
        if getattr(self, "_band", None) == text:
            return
        self.band.setText(text)
        self.band.setStyleSheet(style)
        self._band = text

    def update_status(self):
        page = self.page()
        if getattr(self, "status", None) is None:
            return
        if not page:
            self.status.setText("")
            return
        n_pin = sum(1 for i in page["items"] if i.get("pin"))
        parts = ["Page: %s" % page["name"], "%d buttons" % len(page["items"])]
        if self.editing:
            parts.append("%d picked" % len(self.picked))
        if n_pin:
            parts.append("%d pinned (don't zoom)" % n_pin)
        if self._missing_n:
            parts.append("%d missing" % self._missing_n)
        if self.search_ids:
            parts.append("%d found" % len(self.search_ids))
        parts.append("zoom %d%%" % int(round(self.canvas.scale * 100)))
        text = "   |   ".join(parts)
        if getattr(self, "_status", None) != text:            # (set while painting: only when it changes)
            self.status.setText(text)
            self._status = text

    def look_dialog(self):
        """Your look: theme, toolbar, text, selected / hover, silhouette, snap, grid, side colours, new buttons."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Picker look (yours, on this computer)")
        form = QtWidgets.QFormLayout(d)
        L = self.look
        theme = QtWidgets.QComboBox()
        for t in sorted(PM.THEMES):
            theme.addItem(t, t)
        theme.setCurrentIndex(sorted(PM.THEMES).index(L.get("theme", "dark")) if L.get("theme") in PM.THEMES else 0)
        compact = QtWidgets.QCheckBox("icons only (a smaller toolbar)")
        compact.setChecked(bool(L.get("compact")))
        text = QtWidgets.QDoubleSpinBox()
        text.setRange(0.5, 3.0)
        text.setSingleStep(0.1)
        text.setValue(float(L.get("text_scale", 1.0)))
        width = QtWidgets.QDoubleSpinBox()
        width.setRange(0.5, 6.0)
        width.setValue(float(L.get("sel_width", 2.0)))
        fill = QtWidgets.QCheckBox("brighter when selected")
        fill.setChecked(bool(L.get("sel_fill", True)))
        hover = QtWidgets.QComboBox()
        for h in PM.HOVERS:
            hover.addItem(h, h)
        hover.setCurrentIndex(PM.HOVERS.index(L.get("hover")) if L.get("hover") in PM.HOVERS else 0)
        sil = QtWidgets.QCheckBox("show the silhouette behind the buttons")
        sil.setChecked(bool(L.get("silhouette", True)))
        sil_a = QtWidgets.QDoubleSpinBox()
        sil_a.setRange(0.0, 1.0)
        sil_a.setSingleStep(0.1)
        sil_a.setValue(float(L.get("silhouette_alpha", 0.6)))
        snap = QtWidgets.QCheckBox("line up with other buttons while dragging")
        snap.setChecked(bool(L.get("snap", True)))
        lines = QtWidgets.QCheckBox("show the connectors while animating")
        lines.setChecked(bool(L.get("lines", True)))
        keyed = QtWidgets.QCheckBox("keyed dots (red: a key on this frame; ring: animated)")
        keyed.setChecked(bool(L.get("keyed", True)))
        behind = QtWidgets.QCheckBox("seen from behind (left and right swapped)")
        behind.setChecked(bool(L.get("behind")))
        badges = QtWidgets.QCheckBox("badges (IK, FK, PV, S) in the buttons' corner")
        badges.setChecked(bool(L.get("badges", True)))
        fade = QtWidgets.QCheckBox("fade the limb's IK buttons in FK (and FK in IK)")
        fade.setChecked(bool(L.get("ikfk_fade", True)))
        mini = QtWidgets.QCheckBox("a small map of the page when it doesn't fit")
        mini.setChecked(bool(L.get("minimap", True)))
        allow = QtWidgets.QCheckBox("let me edit a rig's picker (rigger / lead) - animators: off")
        allow.setChecked(bool(L.get("allow_edit")))
        ignore = QtWidgets.QLineEdit(A.opt("picker_unsure_ignore", PX.UNSURE_IGNORE))
        add_at = QtWidgets.QComboBox()
        add_at.addItem("where they sit (front view)", "front")
        add_at.addItem("at the mouse", "mouse")
        add_at.setCurrentIndex(1 if L.get("add_at") == "mouse" else 0)
        colours = {"sel_rgb": list(L.get("sel_rgb") or [1, 1, 1]), "hover_rgb": list(L.get("hover_rgb") or [.5, .8, 1])}
        sides = dict((k, list(v)) for k, v in (L.get("side_rgb") or PM.PREFS["side_rgb"]).items())

        def colour_btn(key, holder, label):
            b = QtWidgets.QPushButton(label)

            def paint():
                c = _colour(holder[key])
                b.setStyleSheet("background-color: rgb(%d, %d, %d);" % (c.red(), c.green(), c.blue()))

            def pick():
                c = QtWidgets.QColorDialog.getColor(_colour(holder[key]), d, label)
                if c.isValid():
                    holder[key] = [c.redF(), c.greenF(), c.blueF()]
                    paint()
            b.clicked.connect(lambda *_: pick())
            paint()
            return b
        form.addRow("Theme", theme)
        form.addRow("Toolbar", compact)
        form.addRow("Text size (x)", text)
        form.addRow("Selected outline", colour_btn("sel_rgb", colours, "colour"))
        form.addRow("Selected outline width", width)
        form.addRow("", fill)
        form.addRow("Hover", hover)
        form.addRow("Hover colour", colour_btn("hover_rgb", colours, "colour"))
        form.addRow("Silhouette", sil)
        form.addRow("Silhouette strength", sil_a)
        form.addRow("Snap", snap)
        form.addRow("", lines)
        form.addRow("", keyed)
        form.addRow("", behind)
        form.addRow("", badges)
        form.addRow("", fade)
        form.addRow("", mini)
        form.addRow("Edit", allow)
        form.addRow("Missing: never list", ignore)
        form.addRow("New buttons go", add_at)
        row = QtWidgets.QHBoxLayout()
        for k, label in (("L", "Left"), ("C", "Middle"), ("R", "Right")):
            row.addWidget(colour_btn(k, sides, label))
        form.addRow("Side colours", row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        if not _exec(d):
            return
        self.apply_look({"theme": theme.currentData(), "compact": compact.isChecked(), "text_scale": text.value(),
                         "sel_rgb": colours["sel_rgb"], "sel_width": width.value(), "sel_fill": fill.isChecked(),
                         "hover": hover.currentData(), "hover_rgb": colours["hover_rgb"],
                         "silhouette": sil.isChecked(), "silhouette_alpha": sil_a.value(), "snap": snap.isChecked(),
                         "add_at": add_at.currentData(), "side_rgb": sides, "lines": lines.isChecked(),
                         "keyed": keyed.isChecked(), "behind": behind.isChecked(), "badges": badges.isChecked(),
                         "ikfk_fade": fade.isChecked(), "minimap": mini.isChecked(),
                         "allow_edit": allow.isChecked()})
        A.set_opt("picker_unsure_ignore", ignore.text())

    def apply_look(self, values):
        for k, v in values.items():
            if k in PM.PREFS and v is not None:
                self.look[k] = v
                PM.set_pref(k, v)
        self.text_slider.blockSignals(True)
        self.text_slider.setValue(int(round(float(self.look.get("text_scale", 1.0)) * 100)))
        self.text_slider.blockSignals(False)
        self.text_pct.setText("%d%%" % int(round(float(self.look.get("text_scale", 1.0)) * 100)))
        self._layout_tools()
        if getattr(self, "behind_btn", None) is not None:
            self.behind_btn.blockSignals(True)
            self.behind_btn.setChecked(bool(self.look.get("behind")))
            self.behind_btn.blockSignals(False)
        self.edit_btn.setVisible(self.can_edit() or self.editing)
        self.canvas.update()
        A.message("picker look saved (yours, on this computer).")

    # -- data ---------------------------------------------------------------
    def fill_characters(self):
        self.chars.blockSignals(True)
        self.chars.clear()
        keep = A.current_character()
        chars = A.characters() or [""]
        for c in chars:
            self.chars.addItem(c or A.ROOT, c)
        if keep in chars:
            self.chars.setCurrentIndex(chars.index(keep))
        self.chars.blockSignals(False)
        self.load()

    def load(self, make=True):
        if self.dirty and self.picker is not None and self._ask_save() is None:
            return
        self.ns = self.chars.currentData() or ""
        try:
            self.picker = PM.load(self.ns, make=make)
        except Exception as e:                               # never leave the window empty without a word
            A.message("picker: %s" % e, "warn")
            self.picker = {"version": PM.VERSION, "pages": []}
        self.history = PM.History()
        self.dirty = False
        self.picked = set()
        self._nodes = {}
        try:
            got = int(A.opt("picker_side", -1))
        except (TypeError, ValueError):
            got = -1
        self.side = got if 0 <= got < len(self.picker["pages"]) else None
        if getattr(self, "side_btn", None) is not None:
            self.side_btn.setText("Side by side" if self.side is None else "Beside: %s" %
                                  self.picker["pages"][self.side]["name"])
        self.fill_tabs()
        self.framed = False
        self.canvas.frame()
        n = sum(len(p["items"]) for p in self.picker["pages"])
        found = ""
        try:
            found = "; " + A.found_text(self.ns)
        except Exception:
            pass
        src = {"yours": "your own (saved on this computer)", "rig": "the rig's", "auto": "automatic"}
        try:
            src_text = src[PM.where_from(self.ns)]
        except Exception:
            src_text = "?"
        A.message("picker: %d button(s)%s, %s%s." % (n, (" in " + self.ns) if self.ns else "", src_text, found))
        self.hier = None
        self._keyed = {}
        self._ikfk = {}
        self.picked_links = set()
        if getattr(self, "edit_btn", None) is not None:      # 5.6.24: animators don't edit the rig's picker
            self.edit_btn.setVisible(self.can_edit())
        self.show_missing()
        self.refresh_list()
        if getattr(self, "my_row", None) is not None:
            self.fill_my_bar()

    def show_missing(self):
        try:
            n = len(PM.missing(self.picker, self.ns))
        except Exception:
            n = 0
        self._missing_n = n
        self.new_btn.setText("%d control(s) aren't on the picker - see them, add them, or take them out" % n)
        self.new_btn.setVisible(n > 0)
        pins = len(PM.pinned(self.picker or {}))                 # 5.6.23: pinned buttons don't zoom - say so
        self.pin_btn.setText("%d pinned button(s) stay still when you zoom - click to unpin them all" % pins)
        self.pin_btn.setVisible(pins > 0)
        try:
            dup, old = len(PM.duplicates(self.picker)), len(PM.stale(self.picker, self.ns))
        except Exception:
            dup, old = 0, 0
        self.clean_btn.setText("%d button(s) twice on a page, %d for controls that are gone - clean up" % (dup, old))
        self.clean_btn.setVisible(dup + old > 0)
        self.show_norm()

    def show_norm(self):
        """5.6.24: in Edit, a bar when the page is far too big / small for its buttons."""
        if getattr(self, "norm_btn", None) is None:
            return
        page = self.page()
        need = bool(page) and self.editing and PX.needs_normalize(page)
        self.norm_btn.setText("'%s' is far bigger (or smaller) than its buttons - the text can't show. Click: "
                              "Normalize (the layout stays)" % (page or {}).get("name", ""))
        self.norm_btn.setVisible(need)

    def add_missing(self):
        """(5.6.22) every missing control onto the page 'New controls'."""
        self.remember()
        added = self.run(lambda: PM.add_missing(self.picker, self.ns)) or 0
        if added:
            self.changed()
            self.fill_tabs()
            names = [p["name"] for p in self.picker["pages"]]
            if PM.NEW_PAGE in names:
                self.set_page(names.index(PM.NEW_PAGE))
                self.tabs.setCurrentIndex(names.index(PM.NEW_PAGE))
            self.canvas.frame()
            A.message("%d button(s) added on the page '%s' - Save keeps them." % (added, PM.NEW_PAGE))
        self.show_missing()

    def refresh(self):
        self._nodes = {}
        self.fill_characters()

    def fill_tabs(self):
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for p in self.picker["pages"]:
            self.tabs.addTab(p["name"])
        self.index = max(0, min(self.index, len(self.picker["pages"]) - 1))
        self.tabs.setCurrentIndex(self.index)
        self.tabs.blockSignals(False)
        self._update_save()

    def page(self):
        pages = (self.picker or {}).get("pages") or []
        return pages[self.index] if 0 <= self.index < len(pages) else None

    def set_page(self, i):
        self.keep_view()                                     # 5.6.24: each page keeps its zoom / pan
        self.index = i
        self.picked = set()
        self.picked_links = set()
        self.hier = None
        self.restore_view()
        self.refresh_list()
        self.show_norm()

    def nodes_of(self, it):
        key = (it["id"], tuple(it.get("nodes") or []))
        if key not in self._nodes:
            self._nodes[key] = PM.resolve(it, self.ns)
        return self._nodes[key]

    def maya_selection(self):
        if self._sel is None:
            self._sel = set(cmds.ls(selection=True, long=True) or [])
        return self._sel

    def selection_changed(self):
        self._sel = None
        self._keyed = {}
        self.canvas.update()

    # -- using it -----------------------------------------------------------
    def run(self, fn):
        try:
            return fn()
        except (RuntimeError, ValueError) as e:
            A.message(str(e), "warn")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            A.message("picker error: %s (details in the Script Editor)" % e, "warn")
        return None

    def click(self, it, mods):
        nodes = self.nodes_of(it)
        if not nodes:
            raise RuntimeError("%s isn't in this character - Refresh, or Edit to fix the button." %
                               ", ".join(it.get("nodes") or []))
        if _has(mods, Qt.ShiftModifier) and _has(mods, Qt.ControlModifier):
            cmds.select(nodes, add=True)
        elif _has(mods, Qt.ShiftModifier):
            cmds.select(nodes, toggle=True)
        elif _has(mods, Qt.ControlModifier):
            cmds.select(nodes, deselect=True)
        else:
            cmds.select(nodes, replace=True)

    def click_twin(self, it):
        """5.6.23: Alt+click - the other side's control (the button's twin, else the mirrored name)."""
        names = []
        for n in self.nodes_of(it):
            got = A.twin_of(n)                          # by name, your link, else by position
            if got:
                names.append(got)
        if not names:
            raise RuntimeError("%s has no twin." % ", ".join(it.get("nodes") or []))
        cmds.select(names, replace=True)

    def select_items(self, items, mods):
        nodes = []
        for it in items:
            if it.get("kind") == "select":
                nodes += [n for n in self.nodes_of(it) if n not in nodes]
        if _has(mods, Qt.ControlModifier) and not _has(mods, Qt.ShiftModifier):
            if nodes:
                cmds.select(nodes, deselect=True)
        elif _has(mods, Qt.ShiftModifier):
            if nodes:
                cmds.select(nodes, add=True)
        elif nodes:
            cmds.select(nodes, replace=True)
        else:
            cmds.select(clear=True)

    def select_scope(self, which):
        if which == "page":
            self.select_items(self.page()["items"] if self.page() else [], Qt.NoModifier)
            return
        nodes = A.character_controls(self.ns)
        if which in ("L", "R"):
            nodes = [n for n in nodes if A.side_of(n) == which]
        if not nodes:
            raise RuntimeError("nothing to select.")
        cmds.select(nodes, replace=True)

    def run_command(self, it):
        code = it.get("code") or ""

        def go():
            cmds.select(self.nodes_of(it) or [], replace=True) if it.get("nodes") else None
            exec(code, {"cmds": cmds, "A": A, "ns": self.ns, "nodes": self.nodes_of(it), "picker": self})
        self.run(go)

    # -- editing ------------------------------------------------------------
    def grid(self):
        return float(A.opt("picker_grid", 0) or 0)

    def set_editing(self, on):
        self.editing = bool(on)
        self.picked = set()
        self.picked_links = set()
        self.edit_bar.setVisible(self.editing)
        self.panel.setVisible(self.editing)
        if getattr(self, "panel_window", None) is not None:
            self.panel_window.setVisible(self.editing)
        self.use_bar.setVisible(not self.editing)
        self.add_page_btn.setVisible(self.editing)
        for b in getattr(self, "band_tools", []):
            b.setVisible(self.editing)
        self.preview = False
        self.set_band()
        self.show_norm()
        self.hier = None
        self.canvas.update()

    def remember(self, note=""):
        self.history.push(self.picker, note)

    def changed(self):
        self.dirty = True                                    # (the control cache is keyed by the names: kept)
        self._update_save()
        if not self.canvas.drag:                             # (dragging: the list catches up on release)
            self.refresh_list()
            self.hier = None

    def _update_save(self):
        if getattr(self, "save_btn", None) is not None:
            self.save_btn.setText("Save *" if self.dirty else "Save")
            self.save_btn.setStyleSheet("background-color: #b07a1c;" if self.dirty else "")
        if getattr(self, "band", None) is not None:
            self.set_band()

    def picked_items(self):
        return PM.by_id(self.page(), self.picked) if self.page() else []

    def edit(self, fn, need=True):
        items = self.picked_items()
        if need and not items:
            A.message("pick buttons first (click / drag a box in Edit mode).", "warn")
            return
        self.remember()
        self.run(lambda: fn(items))
        self.changed()
        self.canvas.update()

    def undo(self):
        got = self.history.undo(self.picker)
        if got is not None:
            self.picker = got
            self.changed()
            self.fill_tabs()
            self.canvas.update()

    def redo(self):
        got = self.history.redo(self.picker)
        if got is not None:
            self.picker = got
            self.changed()
            self.fill_tabs()
            self.canvas.update()

    def save(self):
        def go():
            where = PM.save(self.picker, self.ns)
            try:                                             # 5.6.26: a numbered copy (Picker > Saved versions)
                PX.save_backup(A.rig_name(self.ns), self.picker)
            except Exception:
                pass
            self.dirty = False
            self._update_save()
            if where == "rig":
                A.message("picker saved IN the rig - save the rig file: every scene that references it gets "
                          "this picker.")
            else:
                A.message("picker saved for you on this computer (rig '%s'). Export picker... takes it to another "
                          "computer." % A.rig_name(self.ns))
        self.run(go)

    def export_picker(self):
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, "Export picker", "%s_picker.json"
                                                         % A.rig_name(self.ns), "Picker (*.json)")
        if path:
            self.run(lambda: PM.export_file(self.picker, path))
            A.message("picker exported: %s" % path)

    def import_picker(self):
        path, _f = QtWidgets.QFileDialog.getOpenFileName(self, "Import picker", "", "Picker (*.json)")
        if not path:
            return
        got = self.run(lambda: PM.import_file(path))
        if got:
            self.remember()
            self.picker = got
            self.changed()
            self.index = 0
            self.fill_tabs()
            self.canvas.frame()
            self.show_missing()
            A.message("picker imported - Save keeps it.")

    def back_to_rig(self):
        if not PM.own_picker(self.ns):
            A.message("you have no picker of your own for this rig: it's already the %s one."
                      % ("rig's" if PM.rig_picker(self.ns) else "automatic"), "warn")
            return
        if QtWidgets.QMessageBox.question(self, "Back to the rig's picker", "Forget your own picker for this rig "
                                          "on this computer and use the %s one?" % (
                                              "rig's" if PM.rig_picker(self.ns) else "automatic")) != \
                QtWidgets.QMessageBox.Yes:
            return
        self.run(lambda: PM.forget(self.ns))
        self.dirty = False
        self.load()

    def picker_menu(self, menu):
        menu.clear()
        menu.addAction("Saved versions (go back)...", self.restore_dialog)
        menu.addAction("Pages from another character...", self.copy_from_character)
        tm = menu.addMenu("Page templates")
        self.fill_templates_menu(tm)
        menu.addAction("Export this page...", self.export_page)
        menu.addAction("Import a page...", self.import_page)
        menu.addAction("This page as a picture (cheat sheet)...", self.cheat_sheet)
        menu.addAction("Keys...", self.keys_dialog)
        menu.addSeparator()
        menu.addAction("Export picker... (take it to another computer)", self.export_picker)
        menu.addAction("Import picker...", self.import_picker)
        menu.addAction("Back to the rig's picker (forget mine)", self.back_to_rig)

    def _ask_save(self):
        r = QtWidgets.QMessageBox.question(self, "Gus Animtool picker", "Save the picker changes first?",
                                           QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard |
                                           QtWidgets.QMessageBox.Cancel)
        if r == QtWidgets.QMessageBox.Cancel:
            return None
        if r == QtWidgets.QMessageBox.Save:
            self.save()
        self.dirty = False
        return True

    def auto(self):
        if QtWidgets.QMessageBox.question(self, "Auto layout", "Lay the picker out automatically again?\n(Your "
                                          "edits go - Undo brings them back until you close the window.)") != \
                QtWidgets.QMessageBox.Yes:
            return
        self.remember()
        keep = PM.excluded(self.picker)
        self.picker = self.run(lambda: PM.auto(self.ns, exclude=keep)) or self.picker
        self.changed()
        self.index = 0
        self.fill_tabs()
        self.canvas.frame()

    def new_page(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New page", "Name:")
        if not ok:
            return
        self.remember()
        PM.add_page(self.picker, name)
        self.changed()
        self.index = len(self.picker["pages"]) - 1
        self.fill_tabs()
        self.canvas.frame()

    def page_menu(self, menu):
        page = self.page()
        if not page:
            return
        menu.addAction("Rename this page...", self.rename_page)
        menu.addAction("Background picture...", self.background)
        if page.get("bg"):
            menu.addAction("No background picture", lambda: self._edit_page(lambda p: p.update({"bg": ""})))
        if len(self.picker["pages"]) > 1:
            menu.addAction("Delete this page", self.delete_page)

    def _edit_page(self, fn):
        self.remember()
        fn(self.page())
        self.changed()
        self.canvas.update()

    def rename_page(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Rename page", "Name:", text=self.page()["name"])
        if ok and name.strip():
            self._edit_page(lambda p: p.update({"name": name.strip()}))
            self.fill_tabs()

    def delete_page(self):
        if QtWidgets.QMessageBox.question(self, "Delete page", "Delete the page '%s'?" % self.page()["name"]) != \
                QtWidgets.QMessageBox.Yes:
            return
        self.remember()
        self.picker["pages"].pop(self.index)
        self.index = max(0, self.index - 1)
        self.changed()
        self.fill_tabs()
        self.canvas.frame()

    def background(self):
        got, _f = QtWidgets.QFileDialog.getOpenFileName(self, "Background picture", "",
                                                        "Pictures (*.png *.jpg *.jpeg *.bmp *.tif)")
        if got:
            self._edit_page(lambda p: p.update({"bg": got.replace("\\", "/")}))

    def add_selected(self, x=None, y=None):
        """5.6.23: a button per control selected in Maya - any curve, found as a control or not - where it sits seen
        from the front (on the page's scale), or at (x, y) / the mouse. Ones already on the page are picked."""
        sel = A.selected()
        if not sel:
            A.message("select controls in Maya first.", "warn")
            return
        page = self.page()
        if page is None:
            return
        at = (x, y) if x is not None else None
        if at is None and self.look.get("add_at") == "mouse" and self.canvas.last_page is not None:
            at = self.canvas.last_page
        have = dict((n, it) for it in page["items"] for n in it.get("nodes") or [])
        already = [have[PM.strip(n)] for n in sel if PM.strip(n) in have]
        self.remember()
        made = self.run(lambda: PM.add_controls(self.picker, page, sel, self.ns, at=at)) or []
        self.picked = set(i["id"] for i in made + already)
        if not self.editing and made:
            self.edit_btn.setChecked(True)
            self.picked = set(i["id"] for i in made + already)
        self.changed()
        self.show_missing()
        self.canvas.update()
        A.message("%d button(s) added%s%s - Save keeps them." % (
            len(made), " at the mouse" if at else " where they sit (front view)",
            ("; %d already on this page (picked)" % len(already)) if already else ""))

    def add_group(self, x=None, y=None):
        sel = A.selected()
        if not sel:
            A.message("select the controls the button selects.", "warn")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "One button for these controls", "Label:")
        if not ok:
            return
        self.remember()
        it = PM.add_group_button(self.page(), sel, name or "group", x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()

    def add_widget(self, kind, x=None, y=None):
        """A slider / check box / toggle for an attribute: the one picked in the Channel Box, else (5.6.26) one
        chosen from the control's list."""
        got = self.choose_attr(None if kind == "slider" else ("bool", "enum", "double", "long", "float"),
                               {"toggle": "Toggle", "check": "Check box"}.get(kind, "Slider"))
        if not got:
            return
        self.remember("add a %s" % kind)
        it = PM.add_widget(self.page(), kind, got[0], got[1], x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()

    def add_enum(self, x=None, y=None):
        """5.6.24: a space switch for an enum attribute (5.6.26: picked in the Channel Box, or chosen)."""
        got = self.choose_attr(("enum",), "Space switch")
        if not got:
            return
        self.remember("add a space switch")
        it = self.run(lambda: PX.add_enum(self.page(), got[0], got[1], x, y))
        if it:
            self.picked = {it["id"]}
            self.changed()
            self.canvas.update()

    def add_command(self, x=None, y=None):
        label, ok = QtWidgets.QInputDialog.getText(self, "Command button", "Label:")
        if not ok or not label:
            return
        code, ok = QtWidgets.QInputDialog.getMultiLineText(self, "Command button", "Python (cmds, A, ns, nodes "
                                                           "are there):", "")
        if not ok:
            return
        self.remember()
        it = PM.add_command(self.page(), label, code, x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()

    def space(self, axis):
        gap, ok = QtWidgets.QInputDialog.getDouble(self, "Space evenly", "Gap between the buttons:",
                                                   self._gap, 0.0, 500.0, 1)
        if ok:
            self._gap = gap
            self.edit(lambda its: PM.space(its, gap, axis))

    def same_size(self):
        page = self.page()
        ref = PM.by_id(page, {self.anchor}) if (page and self.anchor in self.picked) else []
        if not ref:
            A.message("click the button to match last (it stays picked), then Same size.", "warn")
            return
        self.edit(lambda its: PM.same_size(its, ref[0]))

    def recolour(self):
        items = self.picked_items()
        if not items:
            A.message("pick buttons first.", "warn")
            return
        c = QtWidgets.QColorDialog.getColor(_colour(items[0].get("rgb") or [0.5] * 3), self, "Button colour")
        if c.isValid():
            self.edit(lambda its: PM.set_value(its, "rgb", [c.redF(), c.greenF(), c.blueF()]))

    def relabel(self):
        items = self.picked_items()
        if not items:
            A.message("pick buttons first.", "warn")
            return
        if PM.is_text(items[0]):                             # 5.6.25: texts and notes: several lines
            text, ok = QtWidgets.QInputDialog.getMultiLineText(self, "Text", "Text (several lines):",
                                                               items[0].get("label", ""))
        else:
            text, ok = QtWidgets.QInputDialog.getText(self, "Label", "Text (empty: none; \\n: a new line):",
                                                      text=items[0].get("label", ""))
        if ok:
            self.edit(lambda its: PM.set_value(its, "label", text))

    def mirror(self):
        self.edit(lambda its: PM.mirror(self.page(), its, self.ns))

    # -- 5.6.21: frames, text, order, lock, grid, style, pages ---------------
    def group(self):
        items = [i for i in self.picked_items() if not PM.is_frame(i)]
        if not items:
            A.message("pick the buttons to group first.", "warn")
            return
        title, ok = QtWidgets.QInputDialog.getText(self, "Group", "Title:", text="Group")
        if not ok:
            return

        def go(its):
            fr = PM.group_frame(self.page(), its, title.strip() or "Group")
            self.picked = {fr["id"]}
        self.edit(go)

    def ungroup(self):
        frames = [i for i in self.picked_items() if PM.is_frame(i)]
        if not frames:
            A.message("pick a frame first (click its title).", "warn")
            return
        self.edit(lambda its: PM.ungroup(self.page(), frames))
        self.picked = set()
        self.canvas.update()

    def add_text(self, x=None, y=None):
        text, ok = QtWidgets.QInputDialog.getText(self, "Text", "Text:", text="TITLE")
        if not ok or not text.strip():
            return
        self.remember()
        it = PM.add_text(self.page(), text.strip(), x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()

    def order(self, how):
        self.edit(lambda its: PM.order(self.page(), its, how))

    def toggle_lock(self):
        items = self.picked_items()
        lock = not all(i.get("locked") for i in items)
        self.edit(lambda its: PM.set_value(its, "locked", lock))
        A.message("%s %d item(s)." % ("locked" if lock else "unlocked", len(items)))

    def toggle_grid(self):
        size = float(A.opt("picker_grid_size", 8.0) or 8.0)
        self.set_grid(0 if self.grid() else size)

    def set_grid(self, size):
        if size:
            A.set_opt("picker_grid_size", float(size))
        A.set_opt("picker_grid", float(size))
        A.message("snap to grid: %s." % ("off" if not size else "every %g" % size))
        self.canvas.update()

    def copy_style(self):
        items = self.picked_items()
        if not items:
            A.message("pick the button whose style to copy.", "warn")
            return
        ref = PM.by_id(self.page(), {self.anchor}) if self.anchor in self.picked else items
        self._style = PM.copy_style(ref[0])
        A.message("style copied - pick buttons, then Paste style.")

    def paste_style(self):
        if not getattr(self, "_style", None):
            A.message("copy a style first.", "warn")
            return
        self.edit(lambda its: PM.paste_style(its, self._style))

    def move_to_page(self, name=None):
        items = self.picked_items()
        if not items:
            A.message("pick buttons first.", "warn")
            return
        if name is None:
            name, ok = QtWidgets.QInputDialog.getText(self, "Move to a new page", "Page name:")
            if not ok or not name.strip():
                return
            name = name.strip()
        self.remember()
        src = self.page()
        frames = [i for i in items if PM.is_frame(i)]
        for fr in frames:                                    # a frame goes with its buttons
            items += [i for i in PM.frame_members(src, fr) if i not in items]
        PM.move_to_page(self.picker, src, items, name)
        self.picked = set()
        self.changed()
        self.fill_tabs()
        self.canvas.update()
        A.message("%d item(s) moved to the page '%s'." % (len(items), name))

    def transparency(self):
        frames = [i for i in self.picked_items() if PM.is_frame(i)]
        if not frames:
            return
        v, ok = QtWidgets.QInputDialog.getInt(self, "Frame", "See-through (0 = solid, 100 = only the outline):",
                                              int(round(100 - 100 * float(frames[0].get("alpha", 0.35)))), 0, 100)
        if ok:
            self.edit(lambda its: PM.set_value([i for i in its if PM.is_frame(i)], "alpha", (100 - v) / 100.0))

    # -- 5.6.22 -------------------------------------------------------------
    def side_page(self):
        pages = (self.picker or {}).get("pages") or []
        if self.side is None or not (0 <= self.side < len(pages)) or self.side == self.index:
            return None
        return pages[self.side]

    def fill_side_menu(self, menu):
        menu.clear()
        a = menu.addAction("(off)")
        a.triggered.connect(lambda *_: self.set_side(None))
        for i, pg in enumerate((self.picker or {}).get("pages") or []):
            if i != self.index:
                b = menu.addAction(pg["name"])
                b.triggered.connect((lambda k=i: lambda *_: self.set_side(k))())

    def set_side(self, i):
        self.side = i
        A.set_opt("picker_side", -1 if i is None else int(i))
        self.side_btn.setText("Side by side" if i is None else "Beside: %s" % self.picker["pages"][i]["name"])
        self.canvas.frame()

    def text_size(self, factor):
        """Bigger / smaller letters on the picked - buttons, frame titles and texts (5.6.24: all of them)."""
        self.edit(lambda its: PX.text_bigger(its, factor))

    def toggle_pin(self):
        items = self.picked_items()
        if not items:
            A.message("pick buttons first.", "warn")
            return
        on = not all(i.get("pin") for i in items)

        def go(its):
            for i in its:
                if on and not i.get("pin"):
                    i["pin"] = True
                    self.canvas.store_pins([i])
                elif not on:
                    i.pop("pin", None)
        self.edit(go)
        A.message("%s %d button(s)%s." % ("pinned" if on else "unpinned", len(items),
                                         " - they stay where they are in the window" if on else ""))

    def clean_up(self):
        dup, old = PM.duplicates(self.picker), PM.stale(self.picker, self.ns)
        if not dup and not old:
            A.message("nothing to clean: no button twice on a page, none for a control that's gone.")
            return
        lines = ["twice: %s (%s)" % (", ".join(it.get("nodes") or []), pg["name"]) for pg, it in dup[:12]]
        lines += ["gone: %s (%s)" % (", ".join(it.get("nodes") or []), pg["name"]) for pg, it in old[:12]]
        if QtWidgets.QMessageBox.question(self, "Clean up the picker", "These buttons go:\n\n%s\n\n(Undo brings "
                                          "them back; Save keeps it.)" % "\n".join(lines)) != \
                QtWidgets.QMessageBox.Yes:
            return
        self.remember()
        a, b = PM.cleanup(self.picker, self.ns)
        self.picked = set()
        self.changed()
        self.show_missing()
        self.canvas.update()
        A.message("%d duplicate button(s) and %d for gone controls removed - Save keeps it." % (a, b))

    def fill_styles_menu(self, menu):
        menu.clear()
        got = PM.styles()
        for name in sorted(got):
            a = menu.addAction("Apply: " + name)
            a.triggered.connect((lambda st=got[name]: lambda *_: self.edit(lambda its: PM.paste_style(its, st)))())
        if got:
            menu.addSeparator()
        menu.addAction("Save the picked one's style as...", self.save_style)
        if got:
            dm = menu.addMenu("Delete a style")
            for name in sorted(got):
                dm.addAction(name, (lambda n=name: lambda: PM.delete_style(n))())

    def save_style(self):
        items = self.picked_items()
        if not items:
            A.message("pick the button whose style to keep.", "warn")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Save style", "Name (FK blue, IK orange...):")
        if ok and name.strip():
            ref = PM.by_id(self.page(), {self.anchor}) if self.anchor in self.picked else items
            PM.save_style(name.strip(), PM.copy_style(ref[0]))
            A.message("style '%s' saved (on this computer) - Styles > Apply." % name.strip())

    def add_pad(self, x=None, y=None):
        sel = A.selected()
        attrs = cmds.channelBox("mainChannelBox", query=True, selectedMainAttributes=True) or []
        if not sel or len(attrs) < 2:
            A.message("select a control and pick TWO attributes in the Channel Box (across, then up).", "warn")
            return
        node = sel[0]
        longs = []
        for a in attrs[:2]:
            try:
                got = cmds.attributeQuery(a, node=node, longName=True)
            except RuntimeError:
                got = None
            longs.append(got if isinstance(got, str) and got else a)
        self.remember()
        it = PM.add_slider2d(self.page(), node, longs[0], longs[1], x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()

    # -- 5.6.23: sets, sides, snap, take out, pins, pages, front view, missing, labels ----
    def add_set(self):
        items = [i for i in self.picked_items() if i.get("kind") == "select"]
        if not items:
            A.message("pick the buttons whose controls the set selects.", "warn")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Selection set", "Its text (Brows, Mouth ribbon...):",
                                                  text="Set")
        if not ok:
            return

        def go(its):
            it = PM.add_set_button(self.page(), [i for i in its if i.get("kind") == "select"], name)
            self.picked = {it["id"]}
        self.edit(go)

    def colour_sides(self):
        items = self.picked_items() or (self.page() or {}).get("items", [])
        if not items:
            return
        self.edit(lambda _its: A.message("%d button(s) coloured by side." % PM.colour_by_side(
            items, self.look.get("side_rgb"))), need=False)

    def toggle_snap(self):
        on = not self.look.get("snap", True)
        self.set_look("snap", on)
        A.message("line up with the other buttons while dragging: %s (Ctrl while dragging does the other)."
                  % ("on" if on else "off"))

    def exclude_picked(self):
        nodes = []
        for it in self.picked_items():
            if it.get("kind") == "select":
                nodes += [n for n in it.get("nodes") or [] if n not in nodes]
        if not nodes:
            A.message("pick the buttons whose controls to take out.", "warn")
            return
        self.exclude_nodes(nodes)

    def exclude_nodes(self, nodes):
        self.remember()
        gone = PM.exclude(self.picker, nodes)
        self.picked = set()
        self.changed()
        self.show_missing()
        self.canvas.update()
        A.message("%d control(s) taken out (%d button(s) went): not missing any more, Auto layout leaves them out - "
                  "Missing > Taken out puts them back. Save keeps it." % (len(nodes), gone))

    def include_nodes(self, nodes):
        self.remember()
        PM.include(self.picker, nodes)
        self.changed()
        self.show_missing()
        A.message("%d control(s) back on the list (missing until you add them)." % len(nodes))

    def unpin_all(self):
        n = len(PM.pinned(self.picker or {}))
        if not n:
            A.message("no pinned buttons.")
            return
        self.remember()
        self.canvas.sync_pins(self.page())
        PM.unpin_all(self.picker)
        self.changed()
        self.show_missing()
        self.canvas.update()
        A.message("%d button(s) unpinned - they zoom with the page again (where they are now). Save keeps it." % n)

    def duplicate_page(self):
        if not self.page():
            return
        self.remember()
        self.index = PM.duplicate_page(self.picker, self.index)
        self.picked = set()
        self.changed()
        self.fill_tabs()
        self.canvas.frame()
        A.message("page '%s' made - try things there, the original stays as it is." % self.page()["name"])

    def arrange_front(self, pages=None, picked_only=False, silhouette=False):
        """The buttons where their controls sit seen from the front: the picked ones, or every button on pages
        (indexes). Returns how many moved."""
        pos_of = PM.pos_finder(self.ns)
        self.remember()
        moved = 0
        if picked_only:
            moved = PM.arrange_front(self.page(), self.picked_items(), pos_of)
        else:
            points = None
            for i in pages or [self.index]:
                pg = self.picker["pages"][i]
                try:
                    moved += PM.arrange_front(pg, pg["items"], pos_of)
                except RuntimeError as e:
                    A.message("%s: %s" % (pg["name"], e), "warn")
                    continue
                if silhouette:
                    if points is None:
                        try:
                            points = PM.mesh_points(self.ns)
                        except Exception:
                            points = []
                    PM.page_silhouette(pg, points, pos_of)
        self.changed()
        self.canvas.update()
        A.message("%d button(s) placed as Maya's front view sees their controls - Undo takes it back, Save keeps it."
                  % moved)
        return moved

    def front_view_dialog(self):
        if not self.page():
            return
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Arrange as the front view")
        v = QtWidgets.QVBoxLayout(d)
        v.addWidget(QtWidgets.QLabel("Buttons go where their controls sit seen from Maya's front view (the page's "
                                     "scale kept), then they're nudged apart.\nLocked and pinned buttons stay. "
                                     "Tip: Page > Duplicate this page first to try it on a copy."))
        only = QtWidgets.QCheckBox("Only the %d picked button(s) on this page" % len(self.picked))
        only.setChecked(bool(self.picked))
        only.setEnabled(bool(self.picked))
        v.addWidget(only)
        v.addWidget(QtWidgets.QLabel("Or every button on these pages:"))
        boxes = []
        for i, pg in enumerate(self.picker["pages"]):
            c = QtWidgets.QCheckBox(pg["name"])
            c.setChecked(i == self.index and not self.picked)
            boxes.append(c)
            v.addWidget(c)
        sil = QtWidgets.QCheckBox("Silhouette behind (the meshes seen from the front)")
        sil.setChecked(True)
        v.addWidget(sil)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        if not _exec(d):
            return
        pages = [i for i, c in enumerate(boxes) if c.isChecked()]
        if not only.isChecked() and not pages:
            A.message("tick a page (or the picked buttons).", "warn")
            return
        self.run(lambda: self.arrange_front(pages, only.isChecked(), sil.isChecked()))

    def missing_rows(self, unsure=False):
        """[(control, page it'd go to, found as a control)] - with unsure: curves not found as controls too."""
        nodes = list(PM.missing(self.picker, self.ns))
        extra = list(PM.candidates(self.picker, self.ns)) if unsure else []
        if not nodes and not extra:
            return []
        try:
            where = PM.guess_pages(nodes + extra, PM.read_rig(self.ns), self.ns)
        except Exception:
            where = {}
        return [(n, where.get(n, "Body"), True) for n in nodes] + [(n, where.get(n, "Body"), False) for n in extra]

    def add_from_missing(self, nodes, here=False):
        if not nodes:
            return {}
        self.remember()
        got = self.run(lambda: PM.add_to_pages(self.picker, nodes, self.ns,
                                               page=self.page() if here else None)) or {}
        self.changed()
        self.fill_tabs()
        self.show_missing()
        self.canvas.update()
        A.message("added: %s - Save keeps them." % (", ".join("%d on %s" % (n, p) for p, n in sorted(got.items()))
                                                     or "nothing"))
        return got

    def missing_dialog(self):
        """Controls with no button: add the checked ones where they sit (their own page or this one), or take them
        out; the taken-out ones can be put back."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Controls not on the picker")
        d.resize(420, 520)
        v = QtWidgets.QVBoxLayout(d)
        info = QtWidgets.QLabel("")
        v.addWidget(info)
        flt = QtWidgets.QLineEdit()
        flt.setPlaceholderText("Filter...")
        v.addWidget(flt)
        unsure = QtWidgets.QCheckBox("Also curves not found as controls (hidden, no control name, nothing to key)")
        v.addWidget(unsure)
        lst = QtWidgets.QListWidget()
        v.addWidget(lst, 1)
        where = QtWidgets.QComboBox()
        where.addItem("onto their own page (Face, Clothes... as Auto layout sorts them)", False)
        where.addItem("onto this page: %s" % (self.page() or {}).get("name", ""), True)
        v.addWidget(where)
        row = QtWidgets.QHBoxLayout()
        v.addLayout(row)
        v.addWidget(QtWidgets.QLabel("Taken out (excluded) - they stay off the picker:"))
        out_lst = QtWidgets.QListWidget()
        out_lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        v.addWidget(out_lst)
        row2 = QtWidgets.QHBoxLayout()
        v.addLayout(row2)

        def fill():
            lst.clear()
            rows = self.missing_rows(unsure.isChecked())
            text = flt.text().strip().lower()
            for node, pg, found in rows:
                name = PM.strip(node)
                if text and text not in name.lower():
                    continue
                r = QtWidgets.QListWidgetItem("[%s] %s%s" % (pg, name, "" if found else "   (not found as a control)"))
                r.setData(Qt.UserRole, node)
                r.setFlags(r.flags() | Qt.ItemIsUserCheckable)
                r.setCheckState(Qt.Checked if found else Qt.Unchecked)
                lst.addItem(r)
            out_lst.clear()
            for n in PM.excluded(self.picker):
                r = QtWidgets.QListWidgetItem(n)
                r.setData(Qt.UserRole, n)
                out_lst.addItem(r)
            info.setText("%d control(s) with no button (%d checked). Checked ones: Add puts them where they sit seen "
                         "from the front; Take out keeps them off for good." % (
                             sum(1 for _n, _p, f in rows if f), len(checked())))

        def checked():
            return [lst.item(i).data(Qt.UserRole) for i in range(lst.count())
                    if lst.item(i).checkState() == Qt.Checked]

        def every(state):
            for i in range(lst.count()):
                lst.item(i).setCheckState(state)
        for label, fn in (("Add checked", lambda: (self.add_from_missing(checked(), bool(where.currentData())),
                                                   fill())),
                          ("Take out checked", lambda: (self.exclude_nodes(checked()) if checked() else None, fill())),
                          ("All", lambda: every(Qt.Checked)), ("None", lambda: every(Qt.Unchecked))):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect((lambda f=fn: lambda *_: f())())
            row.addWidget(b)
        back = QtWidgets.QPushButton("Put back the selected")
        back.clicked.connect(lambda *_: (self.include_nodes([r.data(Qt.UserRole) for r in out_lst.selectedItems()])
                                         if out_lst.selectedItems() else None, fill()))
        row2.addWidget(back)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(d.accept)
        row2.addWidget(close)
        flt.textChanged.connect(lambda *_: fill())
        unsure.toggled.connect(lambda *_: fill())
        fill()
        self._missing_ui = {"dialog": d, "list": lst, "out": out_lst, "fill": fill, "checked": checked,
                            "unsure": unsure, "where": where}
        _exec(d)

    def label_dialog(self):
        """Your label rules: words taken out, 01 -> 1, Capitals - for new buttons, and Apply for the picked (or the
        page)."""
        rules = PM.label_rules()
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Button text rules (yours)")
        form = QtWidgets.QFormLayout(d)
        words = QtWidgets.QLineEdit(rules.get("words", ""))
        words.setPlaceholderText("fol, ribbon, FK, 01...")
        zeros = QtWidgets.QCheckBox("01 -> 1")
        zeros.setChecked(bool(rules.get("zeros")))
        caps = QtWidgets.QCheckBox("Capitals")
        caps.setChecked(bool(rules.get("caps")))
        preview = QtWidgets.QLabel("")
        sample = [n for it in (self.page() or {}).get("items", [])[:40] if it.get("kind") == "select"
                  for n in (it.get("nodes") or [])[:1]][:6]

        def show(*_):
            r = {"words": words.text(), "zeros": zeros.isChecked(), "caps": caps.isChecked()}
            old = PM.label_rules
            PM.label_rules = lambda: r
            try:
                preview.setText("\n".join("%s  ->  %s" % (n, PM.label_of(n)) for n in sample) or "(no buttons)")
            finally:
                PM.label_rules = old
        words.textChanged.connect(show)
        zeros.toggled.connect(show)
        caps.toggled.connect(show)
        form.addRow("Take out these words", words)
        form.addRow("", zeros)
        form.addRow("", caps)
        form.addRow("Preview", preview)
        show()
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        apply_now = QtWidgets.QCheckBox("Also redo the text of the picked buttons (or this page's) now")
        apply_now.setChecked(True)
        form.addRow("", apply_now)
        if not _exec(d):
            return
        PM.set_label_rules({"words": words.text(), "zeros": zeros.isChecked(), "caps": caps.isChecked()})
        if apply_now.isChecked():
            items = self.picked_items() or (self.page() or {}).get("items", [])
            self.edit(lambda _its: A.message("%d button(s) got their text again." % PM.relabel(items)), need=False)
        else:
            A.message("rules saved - new buttons use them.")

    # -- 5.6.24: view per page, hierarchy lines, keyed state, hover card, space menus ----------------
    def restore_view(self):
        """The page's view as you left it (this session), else framed."""
        got = self.views.get((self.ns, self.index))
        if got:
            self.canvas.scale, self.canvas.offset = got[0], QtCore.QPointF(got[1], got[2])
            self.canvas.update()
        else:
            self.canvas.frame()

    def keep_view(self):
        if self.page() is not None:
            c = self.canvas
            self.views[(self.ns, self.index)] = (c.scale, c.offset.x(), c.offset.y())

    def hier_links(self, page):
        """[(parent item, child item)] for the page (kept until the page changes)."""
        key = (id(page), len(page["items"]))
        if self.hier is None or self.hier[0] != key:
            try:
                links = PX.hierarchy_links(page["items"], lambda it: (self.nodes_of(it) or [None])[0])
            except Exception:
                links = []
            self.hier = (key, links)
        return self.hier[1]

    def keyed(self, node):
        """(keyed on this frame, animated) - kept until the time / selection changes."""
        if node not in self._keyed:
            try:
                t = cmds.currentTime(query=True)
            except Exception:
                t = 0.0
            self._keyed[node] = PX.keyed_state(node, t)
        return self._keyed[node]

    def time_changed(self):
        self._keyed = {}
        self.canvas.update()

    def hover_card(self, it):
        """The tooltip: what the button is and does."""
        if PM.is_frame(it):
            return "%s\nclick the title: its %d button(s)' controls\nright-click: select / key / reset them all" % (
                it.get("label"), len(PM.frame_members(self.page(), it)))
        if it.get("tooltip"):
            return it["tooltip"]
        kind = it.get("kind", "select")
        nodes = self.nodes_of(it)
        lines = [it.get("label") or ", ".join(it.get("nodes") or [])]
        if kind == "select":
            names = ", ".join(it.get("nodes") or [])
            if names != lines[0]:
                lines.append(names)
            if nodes:
                side = {"L": "left", "R": "right"}.get(PM.side_of_item(it), "middle")
                now, anim = self.keyed(nodes[0])
                lines.append("%s side%s" % (side, " - keyed on this frame" if now else (" - animated" if anim
                                                                                         else "")))
            else:
                lines.append("not in this character")
            lines.append("click: select  Shift: add  Ctrl: take away  Alt: the twin  double-click: the limb")
        elif kind in ("toggle", "check", "slider", "enum"):
            lines.append("%s.%s" % (", ".join(it.get("nodes") or []), it.get("attr")))
            lines.append({"toggle": "click: on / off", "check": "click: on / off", "slider": "drag: the value",
                          "enum": "click: pick (the control stays where it is)"}[kind])
        elif kind == "command":
            lines.append("click: runs its script")
        return "\n".join(lines)

    def enum_menu(self, it, event=None):
        """A space switch: its choices; the control stays where it is (no jump)."""
        menu = QtWidgets.QMenu(self)
        now = PX.enum_value(it, self.ns)
        for i, name in enumerate(it.get("choices") or []):
            a = menu.addAction(("> " if i == now else "   ") + name)
            a.triggered.connect((lambda k=i: lambda *_: self._set_enum(it, k))())
        self._last_menu = menu
        pos = event.globalPos() if event is not None and hasattr(event, "globalPos") else None
        _exec(menu, pos) if pos is not None else _exec(menu)

    def _set_enum(self, it, index):
        cmds.undoInfo(openChunk=True, chunkName="gusAnimtoolPickerSpace")
        try:
            self.run(lambda: PX.set_enum(it, self.ns, index, keep_place=True))
        finally:
            cmds.undoInfo(closeChunk=True)
        self.canvas.update()

    # -- 5.6.24: find (Ctrl+F), help, my sets, behind ------------------------
    def show_find(self):
        self.find_box.setVisible(True)
        self.find_close.setVisible(True)
        self.find_box.setFocus()

    def hide_find(self):
        self.find_box.setText("")
        self.find_box.setVisible(False)
        self.find_close.setVisible(False)
        self.search_ids = set()
        self.canvas.update()

    def find(self, text):
        """The buttons whose text or control has text in it - lit on the page."""
        text = (text or "").strip().lower()
        page = self.page() or {"items": []}
        self.search_ids = set(i["id"] for i in page["items"] if text and (
            text in (i.get("label") or "").lower() or any(text in n.lower() for n in i.get("nodes") or [])))
        self.canvas.update()
        return self.search_ids

    def find_go(self):
        """Enter in the find box: select what's found (Edit: pick it); none here: the next page with some."""
        got = getattr(self, "_found_pages", {}) or {}
        if not self.search_ids and got:
            later = [k for k in sorted(got) if k > self.index] or sorted(got)
            self.tabs.setCurrentIndex(later[0])
            self.set_page(later[0])
            self.search_ids = set(got[later[0]])
        items = PM.by_id(self.page(), self.search_ids) if self.page() else []
        if self.editing:
            self.picked = set(i["id"] for i in items)
        else:
            self.run(lambda: self.select_items(items, Qt.NoModifier))
        self.canvas.update()

    def toggle_help(self):
        self.canvas.help = not self.canvas.help
        self.canvas.update()

    def fill_mysets_menu(self, menu):
        menu.clear()
        rig = A.rig_name(self.ns)
        got = PX.my_sets(rig)
        for name in sorted(got):
            a = menu.addAction(name)
            a.triggered.connect((lambda n=name: lambda *_: self.run(lambda: self.select_my_set(n)))())
        if got:
            menu.addSeparator()
        menu.addAction("Save the selection as a set...", self.save_my_set)
        if got:
            dm = menu.addMenu("Delete a set")
            for name in sorted(got):
                dm.addAction(name, (lambda n=name: lambda: (PX.save_my_set(rig, n, None), self.fill_my_bar()))())

    def select_my_set(self, name):
        names = PX.my_sets(A.rig_name(self.ns)).get(name) or []
        nodes = [n for n in (A.resolve(x, self.ns) for x in names) if n]
        if not nodes:
            raise RuntimeError("none of the set's controls are in this character.")
        cmds.select(nodes, replace=True)

    def save_my_set(self):
        sel = A.selected()
        if not sel:
            A.message("select the controls first.", "warn")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "My set", "Name (yours, on this computer):")
        if ok and name.strip():
            PX.save_my_set(A.rig_name(self.ns), name.strip(), sel)
            self.fill_my_bar()
            A.message("set '%s' saved: %d control(s) - My sets selects them." % (name.strip(), len(sel)))

    def fill_my_bar(self):
        """Your sets as a row of buttons under the page (up to 8)."""
        for b in getattr(self, "_my_btns", []):
            try:
                b.setParent(None)
                b.deleteLater()
            except Exception:
                pass
        self._my_btns = []
        got = PX.my_sets(A.rig_name(self.ns))
        for name in sorted(got)[:8]:
            b = QtWidgets.QPushButton(name)
            b.setToolTip("Your set: %s" % ", ".join(got[name][:12]))
            b.clicked.connect((lambda n=name: lambda *_: self.run(lambda: self.select_my_set(n)))())
            self.my_row.addWidget(b)
            self._my_btns.append(b)

    def toggle_behind(self, on=None):
        on = (not self.look.get("behind")) if on is None else bool(on)
        self.set_look("behind", on)
        self.canvas.frame()
        A.message("seen from %s." % ("behind (left and right swapped)" if on else "the front"))

    def can_edit(self):
        """Animators don't edit the rig's picker (Look... > let me edit); the rigger always can."""
        try:
            return bool(self.look.get("allow_edit")) or PM.rig_editable(self.ns) or PM.where_from(self.ns) != "rig"
        except Exception:
            return True

    # -- 5.6.24: sizes ------------------------------------------------------
    def normalize_page(self):
        page = self.page()
        if not page:
            return
        self.remember()
        k = PX.normalize(page)
        self.changed()
        self.hier = None
        self.canvas.frame()
        self.show_missing()
        A.message("page '%s' normalized (x%.2f): the same layout in sane units, the page fitted to its buttons. "
                  "Save keeps it." % (page["name"], k))

    def page_text_size(self):
        page = self.page()
        if not page:
            return
        v, ok = QtWidgets.QInputDialog.getDouble(self, "Page text size", "Text size on this page (x) - the animators' "
                                                 "own Text slider multiplies it:",
                                                 float(page.get("text_scale", 1.0)), 0.3, 5.0, 2)
        if ok:
            self._edit_page(lambda p: p.update({"text_scale": round(v, 2)}))

    def fit_text(self):
        items = self.picked_items() or (self.page() or {}).get("items", [])
        k = float(self.look.get("text_scale", 1.0)) * float((self.page() or {}).get("text_scale", 1.0))
        self.edit(lambda _its: A.message("%d button(s) made as wide as their text." % PX.fit_to_text(items, k)),
                  need=False)

    # -- 5.6.24: backgrounds -------------------------------------------------
    def capture_picture(self, page=None):
        """A flat picture of the model from Maya's front view, behind the page, lined up with its buttons."""
        import os
        import tempfile
        page = page or self.page()
        fit = PM.fit_view(page["items"], PM.pos_finder(self.ns))
        if fit is None:
            raise RuntimeError("the page needs at least two buttons whose controls are in the scene to line it up.")
        path = os.path.join(tempfile.gettempdir(), "gus_picker_front.png")
        got, centre, w, h = PX.capture_front(path, self.ns)
        data = _keyed_png(got, PX.KEY_RGB, PM.theme(self.look.get("theme"))["shade"])
        rect = PX.picture_rect_from_camera(fit, centre, w, h)
        self.remember()
        PX.set_picture(page, data, rect, kind="capture", alpha=float((page.get("picture") or {}).get("alpha", 0.5)))
        self.changed()
        self.canvas.update()
        A.message("front picture behind '%s' - Page > Background... sets its opacity. Save keeps it (the animators "
                  "get it)." % page["name"])

    def own_picture(self, page=None):
        page = page or self.page()
        got, _f = QtWidgets.QFileDialog.getOpenFileName(self, "Picture behind the page", "",
                                                        "Pictures (*.png *.jpg *.jpeg *.bmp *.tif)")
        if not got:
            return
        data = _png_bytes(got, 1400)
        pw, ph = PM.page_size(page)
        self.remember()
        PX.set_picture(page, data, {"x": 0.0, "y": 0.0, "w": pw, "h": ph}, kind="picture", alpha=0.6)
        self.changed()
        self.canvas.update()

    def outline_from_meshes(self, page=None):
        page = page or self.page()
        self.remember()
        ok = PX.page_outline(page, PX.mesh_points(self.ns), PM.pos_finder(self.ns))
        self.changed()
        self.canvas.update()
        if not ok:
            raise RuntimeError("no outline: no meshes skinned to this character's joints, or fewer than two "
                               "buttons to line it up with.")
        A.message("outline from the meshes behind '%s' (any namespace)." % page["name"])

    def background_dialog(self):
        """The page's background: the front picture / your picture / the meshes' outline, opacity, place."""
        page = self.page()
        if not page:
            return
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Background - %s" % page["name"])
        form = QtWidgets.QFormLayout(d)
        pic = page.get("picture") or {}
        sil = page.get("outline") or {}
        alpha = QtWidgets.QDoubleSpinBox()
        alpha.setRange(0.0, 1.0)
        alpha.setSingleStep(0.05)
        alpha.setValue(float(pic.get("alpha", 0.5)))
        oalpha = QtWidgets.QDoubleSpinBox()
        oalpha.setRange(0.0, 1.0)
        oalpha.setSingleStep(0.05)
        oalpha.setValue(float(sil.get("alpha", 0.6)))
        boxes = {}
        for k in ("x", "y", "w", "h"):
            f = QtWidgets.QDoubleSpinBox()
            f.setRange(-100000.0, 100000.0)
            f.setValue(float(pic.get(k, 0.0)))
            boxes[k] = f
        form.addRow(QtWidgets.QLabel("Picture: %s" % ({"capture": "the viewport", "picture": "yours",
                                                      "silhouette": "the meshes' silhouette"}.get(
            pic.get("kind"), "none"))))
        form.addRow("Picture opacity", alpha)
        for k, label in (("x", "Picture x"), ("y", "Picture y"), ("w", "Picture width"), ("h", "Picture height")):
            form.addRow(label, boxes[k])
        form.addRow("Outline opacity", oalpha)
        row = QtWidgets.QHBoxLayout()
        for label, fn in (("Silhouette", lambda: self.run(lambda: self.silhouette_picture(page))),
                          ("Viewport picture", lambda: self.run(lambda: self.capture_picture(page))),
                          ("Your picture...", lambda: self.run(lambda: self.own_picture(page))),
                          ("Outline", lambda: self.run(lambda: self.outline_from_meshes(page))),
                          ("Remove all", lambda: self._edit_page(lambda p: [p.pop(k, None) for k in
                                                                           ("picture", "outline", "bg")]))):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect((lambda f=fn: lambda *_: (f(), d.accept()))())
            row.addWidget(b)
        form.addRow(row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        self._bg_ui = {"alpha": alpha, "oalpha": oalpha, "boxes": boxes}
        if not _exec(d):
            return
        self.set_background(page, alpha.value(), oalpha.value(), dict((k, f.value()) for k, f in boxes.items()))

    def set_background(self, page, alpha=None, outline_alpha=None, rect=None):
        self.remember()
        if page.get("picture"):
            if alpha is not None:
                page["picture"]["alpha"] = round(alpha, 3)
            if rect and rect.get("w", 0) > 0 and rect.get("h", 0) > 0:
                page["picture"].update(dict((k, round(v, 2)) for k, v in rect.items()))
        if page.get("outline") and outline_alpha is not None:
            page["outline"]["alpha"] = round(outline_alpha, 3)
        self.changed()
        self.canvas.update()

    # -- 5.6.24: pages made from the rig ------------------------------------
    def make_switches_page(self):
        self.remember()
        page = self.run(lambda: PX.switches_page(self.picker, self.ns))
        if page is not None:
            self._goto_page(page)
            A.message("Switches page: %d switch(es) of the rig - visibility, IK / FK, spaces. Made again any time "
                      "(your own buttons there stay). Save keeps it." % sum(
                          1 for i in page["items"] if i.get("kind") in ("toggle", "enum", "check")))

    def make_face_page(self):
        self.remember()
        page = self.run(lambda: PX.face_sliders_page(self.picker, self.ns))
        if page is not None:
            self._goto_page(page)
            A.message("Face sliders page: %d slider(s). Made again any time. Save keeps it." % sum(
                1 for i in page["items"] if i.get("kind") == "slider"))

    def _goto_page(self, page):
        self.changed()
        self.index = self.picker["pages"].index(page)
        self.fill_tabs()
        self.picked = set()
        self.hier = None
        self.canvas.frame()

    # -- 5.6.24: templates, rules, numbers, line / arc, mirror layout -------
    def rules_dialog(self):
        """Style rules: name pattern = template (first match wins) - for new buttons and Apply."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Style rules (yours)")
        v = QtWidgets.QVBoxLayout(d)
        v.addWidget(QtWidgets.QLabel("One rule a line:  pattern = template   (first match wins)\n"
                                     "e.g.   *_fk_ctrl = FK dot     *_fol_* = Tweak dot     *settings* = Settings\n"
                                     "Templates: " + ", ".join(sorted(PX.all_styles()))))
        edit = QtWidgets.QPlainTextEdit()
        edit.setPlainText("\n".join("%s = %s" % r for r in PX.style_rules()))
        v.addWidget(edit)
        now = QtWidgets.QCheckBox("Apply to the picked buttons (or the whole page) now")
        now.setChecked(True)
        v.addWidget(now)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        if not _exec(d):
            return
        self.save_rules(edit.toPlainText(), now.isChecked())

    def save_rules(self, text, apply_now=True):
        rules = []
        for line in (text or "").splitlines():
            if "=" in line:
                pat, st = [x.strip() for x in line.split("=", 1)]
                if pat and st:
                    rules.append((pat, st))
        PX.set_style_rules(rules)
        if apply_now:
            items = self.picked_items() or (self.page() or {}).get("items", [])
            self.edit(lambda _its: A.message("%d rule(s) kept; %d button(s) styled." % (
                len(rules), PX.apply_style_rules(items, rules))), need=False)
        return rules

    def chain_numbers(self):
        items = self.picked_items() or (self.page() or {}).get("items", [])
        self.edit(lambda _its: A.message("%d button(s) numbered along their chain." % PX.chain_numbers(items)),
                  need=False)

    def arrange_line(self):
        self.edit(lambda its: PX.on_line(its))

    def arrange_arc(self):
        v, ok = QtWidgets.QInputDialog.getDouble(self, "On an arc", "How much it bows (0.3; minus: the other way):",
                                                 0.3, -2.0, 2.0, 2)
        if ok:
            self.edit(lambda its: PX.on_arc(its, v))

    def mirror_layout(self, from_side="L"):
        page = self.page()
        if not page:
            return
        self.edit(lambda _its: A.message("%d button(s) placed as the mirror of the %s side." % (
            PX.mirror_layout(page, from_side), {"L": "left", "R": "right"}[from_side])), need=False)

    def fill_mirror_menu(self, menu):
        menu.clear()
        menu.addAction("Left side -> right side", lambda: self.mirror_layout("L"))
        menu.addAction("Right side -> left side", lambda: self.mirror_layout("R"))

    # -- 5.6.24: scripts, page files, cheat sheet, shortcuts -----------------
    PRESETS = (("(empty)", ""),
               ("Select this page", "picker.select_scope('page')"),
               ("Key every control", "cmds.setKeyframe(A.character_controls(ns))"),
               ("Reset the selection", "A.reset_pose('selection')"),
               ("IK / FK switch (the selected limbs)", "A.switch('toggle')"),
               ("Mirror the pose left -> right", "A.mirror_pose('L>R')"),
               ("Select the button's controls and key them", "cmds.setKeyframe(nodes)"))

    def script_dialog(self, item=None, x=None, y=None):
        """A command button's script: presets, a test run, its text."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Script button")
        v = QtWidgets.QVBoxLayout(d)
        label = QtWidgets.QLineEdit((item or {}).get("label") or "")
        label.setPlaceholderText("Its text")
        v.addWidget(label)
        presets = QtWidgets.QComboBox()
        for name, code in self.PRESETS:
            presets.addItem(name, code)
        v.addWidget(presets)
        v.addWidget(QtWidgets.QLabel("Python - there for you: cmds, A (Gus Animtool), ns, nodes (the button's "
                                     "controls), picker (this window)"))
        code = QtWidgets.QPlainTextEdit()
        code.setPlainText((item or {}).get("code") or "")
        v.addWidget(code)
        presets.currentIndexChanged.connect(lambda *_: (code.setPlainText(presets.currentData()),
                                                        label.setText(label.text() or presets.currentText())))
        test = QtWidgets.QPushButton("Test run")
        test.clicked.connect(lambda *_: self.run_command({"code": code.toPlainText(), "nodes": []}))
        v.addWidget(test)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        if not _exec(d):
            return
        self.set_script(item, label.text().strip() or "Script", code.toPlainText(), x, y)

    def set_script(self, item, label, code, x=None, y=None):
        self.remember()
        if item is None:
            item = PM.add_command(self.page(), label, code, x, y)
        else:
            item["label"], item["code"] = label, code
        self.picked = {item["id"]}
        self.changed()
        self.canvas.update()
        return item

    def export_page(self):
        page = self.page()
        if not page:
            return
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, "Export this page", "%s_%s_page.json" % (
            A.rig_name(self.ns), page["name"]), "Picker page (*.json)")
        if path:
            self.run(lambda: PX.export_page(page, path))
            A.message("page exported: %s" % path)

    def import_page(self):
        path, _f = QtWidgets.QFileDialog.getOpenFileName(self, "Import a page", "", "Picker page (*.json)")
        if not path:
            return
        self.remember()
        i = self.run(lambda: PX.import_page(self.picker, path))
        if i is not None:
            self.index = i
            self.changed()
            self.fill_tabs()
            self.canvas.frame()
            self.show_missing()
            A.message("page imported - its buttons find this character's controls by name. Save keeps it.")

    def cheat_sheet(self):
        page = self.page()
        if not page:
            return
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, "Page as a picture", "%s_%s.png" % (
            A.rig_name(self.ns), page["name"]), "PNG (*.png)")
        if path:
            self.run(lambda: self.canvas.render_page(path))
            A.message("page saved as a picture: %s" % path)

    def keys_dialog(self):
        keys = PX.shortcuts()
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Picker keys (yours)")
        form = QtWidgets.QFormLayout(d)
        fields = {}
        for action in sorted(keys):
            f = QtWidgets.QLineEdit(keys[action])
            fields[action] = f
            form.addRow(action, f)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        if not _exec(d):
            return
        PX.set_shortcuts(dict((a, PX.norm_key(f.text())) for a, f in fields.items() if f.text().strip()))
        A.message("picker keys saved (yours).")

    # -- 5.6.24: mirror pairs ------------------------------------------------
    PROBLEMS = {"none": "no twin", "off": "its twin isn't at the mirrored place",
                "position": "paired only by where it sits"}

    def pairs_dialog(self):
        """The controls whose twin isn't found, or isn't where it should be - link them."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Mirror pairs")
        d.resize(560, 480)
        v = QtWidgets.QVBoxLayout(d)
        info = QtWidgets.QLabel("")
        v.addWidget(info)
        show_pos = QtWidgets.QCheckBox("Also the ones paired only by where they sit (they work)")
        v.addWidget(show_pos)
        lst = QtWidgets.QListWidget()
        lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        v.addWidget(lst, 1)
        row = QtWidgets.QHBoxLayout()
        v.addLayout(row)

        def fill():
            lst.clear()
            rows = self.run(lambda: PX.pair_report(self.ns)) or []
            shown = [r for r in rows if show_pos.isChecked() or r["problem"] != "position"]
            for r in shown:
                text = "%s  -  %s%s%s" % (A.short(r["node"]), self.PROBLEMS[r["problem"]],
                                          ("  (now: %s)" % A.short(r["twin"])) if r["twin"] and
                                          r["problem"] == "off" else "",
                                          ("   ->  suggested: %s" % A.short(r["suggest"])) if r["suggest"] else "")
                item = QtWidgets.QListWidgetItem(text)
                item.setData(Qt.UserRole, r)
                lst.addItem(item)
            info.setText("%d control(s) to look at (of %d off the middle line). Link: they become each other's "
                         "twin for mirror, flip, select twin and the picker." % (
                             len(shown), len(rows)))

        def link_suggested():
            done = 0
            for it in lst.selectedItems():
                r = it.data(Qt.UserRole)
                if r.get("suggest"):
                    self.run(lambda r=r: A.link_twins(r["node"], r["suggest"]))
                    done += 1
            A.message("%d pair(s) linked." % done)
            fill()

        def link_selected():
            sel = A.selected()
            if len(sel) != 2:
                A.message("select exactly two controls in Maya (the pair).", "warn")
                return
            self.run(lambda: A.link_twins(sel[0], sel[1]))
            A.message("%s and %s linked as twins." % (A.short(sel[0]), A.short(sel[1])))
            fill()

        def select_rows():
            nodes = [it.data(Qt.UserRole)["node"] for it in lst.selectedItems()]
            if nodes:
                cmds.select(nodes, replace=True)
        for label, fn in (("Link to the suggestion", link_suggested), ("Link the two selected in Maya",
                                                                       link_selected),
                          ("Select in Maya", select_rows), ("Close", d.accept)):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect((lambda f=fn: lambda *_: f())())
            row.addWidget(b)
        show_pos.toggled.connect(lambda *_: fill())
        fill()
        self._pairs_ui = {"list": lst, "fill": fill, "link_suggested": link_suggested, "info": info}
        _exec(d)

    # -- 5.6.25: connectors ------------------------------------------------------
    def picked_link_items(self):
        page = self.page() or {}
        return [ln for ln in page.get("links") or [] if ln["id"] in self.picked_links]

    def link_set(self, key, value, links=None):
        """A connector setting on the picked connectors (style, width, rgb, dash, head_a / head_b, label,
        label_at, a_side / b_side, bends)."""
        links = self.picked_link_items() if links is None else links
        if not links:
            return
        self.remember()
        for ln in links:
            ln[key] = value
        self.changed()
        self.canvas.update()

    def link_colour(self, links=None):
        links = self.picked_link_items() if links is None else links
        if not links:
            return
        c = QtWidgets.QColorDialog.getColor(_colour(links[0].get("rgb") or [0.75, 0.78, 0.85]), self,
                                            "Connector colour")
        if c.isValid():
            self.link_set("rgb", [c.redF(), c.greenF(), c.blueF()], links)

    def link_label(self, links=None):
        links = self.picked_link_items() if links is None else links
        if not links:
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "Connector", "Its label (empty: none):",
                                                  text=links[0].get("label", ""))
        if ok:
            self.link_set("label", text, links)

    def fill_link_menu(self, menu, ln, x=None, y=None):
        """A connector's right-click menu: shape, width, colour, dash, heads, ends' sides, label, bends, delete."""
        menu.clear()
        one = [ln]
        sm = menu.addMenu("Shape")
        for st in PX.LINK_STYLES:
            sm.addAction(("> " if ln.get("style") == st else "   ") + st,
                         (lambda v=st: lambda: self.link_set("style", v, one))())
        wm = menu.addMenu("Width")
        for v in (0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
            wm.addAction(("> " if float(ln.get("width", 1.5)) == v else "   ") + "%g" % v,
                         (lambda w=v: lambda: self.link_set("width", w, one))())
        menu.addAction("Colour...", lambda: self.link_colour(one))
        dm = menu.addMenu("Line")
        for v in PX.LINK_DASHES:
            dm.addAction(("> " if (ln.get("dash") or "solid") == v else "   ") + v,
                         (lambda d=v: lambda: self.link_set("dash", d, one))())
        for key, label in (("head_a", "Start"), ("head_b", "End")):
            hm = menu.addMenu(label)
            for v in PX.LINK_HEADS:
                hm.addAction(("> " if (ln.get(key) or "none") == v else "   ") + v,
                             (lambda k=key, h=v: lambda: self.link_set(k, h, one))())
        for key, label in (("a_side", "Leaves from"), ("b_side", "Arrives at")):
            am = menu.addMenu(label)
            for v in PX.LINK_SIDES:
                am.addAction(("> " if (ln.get(key) or "auto") == v else "   ") + v,
                             (lambda k=key, s_=v: lambda: self.link_set(k, s_, one))())
        menu.addAction("Label...", lambda: self.link_label(one))
        if x is not None:
            menu.addAction("Add a bend here  (Ctrl+click)", lambda: (self.remember(), PX.add_bend(
                self.page(), ln, x, y), self.changed(), self.canvas.update()))
        if ln.get("bends"):
            menu.addAction("Straighten (no bends)", lambda: self.link_set("bends", [], one))
        menu.addAction("Swap its ends", lambda: (self.remember(), ln.update({"a": ln["b"], "b": ln["a"],
                                                                              "head_a": ln.get("head_b"),
                                                                              "head_b": ln.get("head_a")}),
                                                 self.changed(), self.canvas.update()))
        menu.addSeparator()
        menu.addAction("Delete  (Del)", self.delete)

    def lines_from_hierarchy(self):
        page = self.page()
        if not page:
            return
        self.remember()
        n = self.run(lambda: PX.links_from_hierarchy(page, lambda it: (self.nodes_of(it) or [None])[0]))
        self.changed()
        self.canvas.update()
        A.message("%s connector(s) from the rig's hierarchy - pick one to change it; made again replaces these "
                  "(yours stay)." % n)

    def connect_picked(self):
        """The picked items chained by connectors, in the order they sit (left to right / top down)."""
        items = sorted([i for i in self.picked_items() if not PM.is_frame(i)], key=lambda i: (i["x"], i["y"]))
        if len(items) < 2:
            A.message("pick two or more items to connect (or drag from an item's blue dot to another).", "warn")
            return
        self.remember()
        made = [PX.add_link(self.page(), a["id"], b["id"]) for a, b in zip(items, items[1:])]
        self.picked_links = set(ln["id"] for ln in made)
        self.changed()
        self.canvas.update()

    # -- 5.6.25: layers, notes, the silhouette picture -----------------------
    def fill_layers_menu(self, menu):
        menu.clear()
        page = self.page()
        if not page:
            return
        for L in page.get("layers") or []:
            a = menu.addAction(("[x] " if L.get("shown", True) else "[  ] ") + L["name"] +
                               ("   (locked)" if L.get("locked") else ""))
            a.triggered.connect((lambda n=L["name"]: lambda *_: self.layer_toggle(n))())
        if not page.get("layers"):
            menu.addAction("(no layers on this page)")
        if not self.editing:
            return
        menu.addSeparator()
        menu.addAction("New layer (the picked go on it)...", self.new_layer)
        put = menu.addMenu("Put the picked on")
        put.addAction("(no layer)", lambda: self.edit(lambda its: PX.set_layer(its, None)))
        for L in page.get("layers") or []:
            put.addAction(L["name"], (lambda n=L["name"]: lambda: self.edit(lambda its: PX.set_layer(its, n)))())
        follow = menu.addMenu("Follows a rig switch")
        for L in page.get("layers") or []:
            follow.addAction(L["name"] + (("   (%s)" % L["switch"]) if L.get("switch") else ""),
                             (lambda n=L["name"]: lambda: self.link_layer_to_switch(n))())
        lock = menu.addMenu("Lock / unlock")
        rm = menu.addMenu("Delete a layer (its items stay)")
        for L in page.get("layers") or []:
            lock.addAction(L["name"], (lambda n=L["name"]: lambda: self.layer_toggle(n, "locked"))())
            rm.addAction(L["name"], (lambda n=L["name"]: lambda: self._edit_page(
                lambda p: PX.remove_layer(p, n)))())

    def layer_toggle(self, name, key="shown"):
        L = PX.layer(self.page(), name)
        if L is None:
            return
        if self.editing:
            self.remember()
        L[key] = not L.get(key, key == "shown")
        if self.editing:
            self.changed()
        self.picked -= PX.layer_off(self.page()) | (PX.layer_locked(self.page()) if self.editing else set())
        self.canvas.update()

    def new_layer(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New layer", "Its name (Background, Notes, Body...):")
        if not ok or not name.strip():
            return
        page = self.page()
        self.remember()
        PX.add_layer(page, name.strip())
        PX.set_layer(self.picked_items(), name.strip())
        self.changed()
        self.canvas.update()

    def add_note(self, x=None, y=None):
        self.remember()
        it = PX.add_note(self.page(), "Note", x, y)
        self.picked = {it["id"]}
        self.changed()
        self.canvas.update()
        self.relabel()

    def silhouette_picture(self, page=None):
        """5.6.25: the meshes seen from the front, drawn from their triangles (not a playblast: colour management,
        the viewport, namespaces don't matter) - a crisp shape behind the page, kept in the picker."""
        page = page or self.page()
        fit = PM.fit_view(page["items"], PM.pos_finder(self.ns))
        if fit is None:
            raise RuntimeError("the page needs at least two buttons whose controls are in the scene to line it up.")
        tris = PX.mesh_triangles(self.ns)
        if not tris:
            raise RuntimeError("no meshes found for this character (skinned to its joints).")
        box = PX.tri_box(tris)
        data = _triangles_png(tris, box, 900, (150, 156, 168))
        centre = ((box[0] + box[2]) * 0.5, (box[1] + box[3]) * 0.5)
        rect = PX.picture_rect_from_camera(fit, centre, box[2] - box[0], box[3] - box[1])
        self.remember()
        PX.set_picture(page, data, rect, kind="silhouette",
                       alpha=float((page.get("picture") or {}).get("alpha", 0.45)))
        self.changed()
        self.canvas.update()
        A.message("silhouette picture behind '%s' (%d triangles) - Page > Background... sets its opacity. Save keeps "
                  "it (the animators get it)." % (page["name"], len(tris)))

    # -- 5.6.25: your toolbar ----------------------------------------------------
    def customize_toolbar(self):
        """Your toolbar (on this computer): sections in your order, tools moved / hidden, sections renamed."""
        spec = self._spec_ids()
        state, hidden = PX.toolbar_state(spec)
        words = dict((t, b.word) for t, b in self.tool_by_id.items())
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Customize the toolbar (yours)")
        d.resize(560, 520)
        v = QtWidgets.QVBoxLayout(d)
        v.addWidget(QtWidgets.QLabel("Pick a tool, then move it up / down or to another section; untick it to hide "
                                     "it. Sections: move, rename, add."))
        row = QtWidgets.QHBoxLayout()
        v.addLayout(row, 1)
        secs = QtWidgets.QListWidget()
        tools = QtWidgets.QListWidget()
        row.addWidget(secs, 1)
        row.addWidget(tools, 2)
        ui = {"state": state, "hidden": set(hidden)}

        def fill_secs(keep=None):
            secs.clear()
            for name, _ids in ui["state"]:
                secs.addItem(QtWidgets.QListWidgetItem(name))
            idx = keep if keep is not None else 0
            if secs.count():
                secs.item(min(idx, secs.count() - 1)).setSelected(True)
                secs.setCurrentRow(min(idx, secs.count() - 1))
            fill_tools()

        def cur_sec():
            r = secs.currentRow()
            return ui["state"][r] if 0 <= r < len(ui["state"]) else None

        def fill_tools(keep=None):
            tools.clear()
            sec = cur_sec()
            for t in (sec[1] if sec else []):
                it = QtWidgets.QListWidgetItem(words.get(t, t))
                it.setData(Qt.UserRole, t)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked if t in ui["hidden"] else Qt.Checked)
                it.setIcon(_icon(t))
                tools.addItem(it)
            if keep is not None and sec and keep in sec[1]:
                tools.setCurrentRow(sec[1].index(keep))

        def cur_tool():
            r = tools.currentRow()
            return tools.item(r).data(Qt.UserRole) if 0 <= r < tools.count() else None

        def sync_hidden(*_):
            for i in range(tools.count()):
                t = tools.item(i).data(Qt.UserRole)
                if tools.item(i).checkState() == Qt.Checked:
                    ui["hidden"].discard(t)
                else:
                    ui["hidden"].add(t)

        def tool_step(k):
            t = cur_tool()
            if t:
                sync_hidden()
                PX.toolbar_move(ui["state"], t, step=k)
                fill_tools(t)

        def tool_to():
            t = cur_tool()
            if not t:
                return
            names = [s_[0] for s_ in ui["state"]]
            name, ok = QtWidgets.QInputDialog.getItem(d, "Move to", "Section:", names, 0, False)
            if ok:
                sync_hidden()
                PX.toolbar_move(ui["state"], t, to_section=name)
                fill_tools()

        def sec_step(k):
            sec = cur_sec()
            if sec:
                PX.section_move(ui["state"], sec[0], k)
                fill_secs([s_[0] for s_ in ui["state"]].index(sec[0]))

        def sec_rename():
            sec = cur_sec()
            if not sec:
                return
            name, ok = QtWidgets.QInputDialog.getText(d, "Rename", "Section name:", text=sec[0])
            if ok and name.strip() and name.strip() not in [s_[0] for s_ in ui["state"]]:
                sec[0] = name.strip()
                fill_secs(secs.currentRow())

        def sec_add():
            name, ok = QtWidgets.QInputDialog.getText(d, "New section", "Its name (Favourites...):")
            if ok and name.strip() and name.strip() not in [s_[0] for s_ in ui["state"]]:
                ui["state"].append([name.strip(), []])
                fill_secs(len(ui["state"]) - 1)

        def reset():
            ui["state"], h = PX.toolbar_state(spec, {})
            ui["hidden"] = set(h)
            fill_secs()
        buttons = QtWidgets.QHBoxLayout()
        v.addLayout(buttons)
        for label, fn in (("Tool up", lambda: tool_step(-1)), ("Tool down", lambda: tool_step(1)),
                          ("Tool to section...", tool_to), ("Section up", lambda: sec_step(-1)),
                          ("Section down", lambda: sec_step(1)), ("Rename section", sec_rename),
                          ("New section", sec_add), ("Back to the usual", reset)):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect((lambda f=fn: lambda *_: f())())
            buttons.addWidget(b)
        secs.currentRowChanged.connect(lambda *_: (sync_hidden(), fill_tools()))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        fill_secs()
        self._toolbar_ui = {"state": ui, "secs": secs, "tools": tools, "tool_step": tool_step,
                            "sec_step": sec_step, "sync": sync_hidden}
        if not _exec(d):
            return
        sync_hidden()
        self.save_toolbar(ui["state"], ui["hidden"])

    def save_toolbar(self, state, hidden):
        PX.set_toolbar({"sections": [[s_, list(ids)] for s_, ids in state], "hidden": sorted(hidden)})
        self._layout_tools()
        A.message("your toolbar saved (on this computer).")

    # -- 5.6.26: attributes without the Channel Box ------------------------------
    def choose_attr(self, kinds=None, title="Attribute"):
        """(control, attribute): the one picked in the Channel Box; else a list of the selected control's (or the
        picked button's) attributes to choose from. None when cancelled / nothing."""
        sel = A.selected()
        if not sel and self.editing:
            for it in self.picked_items():
                got = self.nodes_of(it)
                if got:
                    sel = got[:1]
                    break
        if not sel:
            A.message("select a control (or pick its button) first.", "warn")
            return None
        node = sel[0]
        try:
            attrs = cmds.channelBox("mainChannelBox", query=True, selectedMainAttributes=True) or []
        except Exception:
            attrs = []
        if attrs:
            try:
                long_attr = cmds.attributeQuery(attrs[0], node=node, longName=True)
            except RuntimeError:
                long_attr = attrs[0]
            return node, (long_attr if isinstance(long_attr, str) and long_attr else attrs[0])
        names = []
        for a in PX._user_attrs(node):
            info = PX._attr_info(node, a)
            if info and (kinds is None or info[0] in kinds):
                names.append(a)
        if not names:
            A.message("%s has no %s attributes to use." % (A.short(node), "/".join(kinds or ["user"])), "warn")
            return None
        got, ok = QtWidgets.QInputDialog.getItem(self, title, "Attribute of %s:" % A.short(node), names, 0, False)
        return (node, got) if ok and got else None

    # -- 5.6.26: rename many ---------------------------------------------------
    def rename_dialog(self):
        """Rename the picked buttons' text (or the page's) at once: prefix, suffix, find / replace, cut, case,
        numbers - with a preview."""
        items = PX.reading_order([i for i in (self.picked_items() or (self.page() or {}).get("items", []))
                                  if not PM.is_frame(i) or True])
        if not items:
            return
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Rename %d item(s)" % len(items))
        form = QtWidgets.QFormLayout(d)
        f = {}
        for key, label in (("prefix", "Prefix"), ("suffix", "Suffix"), ("find", "Find"), ("replace", "Replace with")):
            f[key] = QtWidgets.QLineEdit()
            form.addRow(label, f[key])
        for key, label in (("cut_start", "Cut from the start"), ("cut_end", "Cut from the end")):
            f[key] = QtWidgets.QSpinBox()
            f[key].setRange(0, 99)
            form.addRow(label, f[key])
        case = QtWidgets.QComboBox()
        for c in ("as it is", "UPPER", "lower", "Title"):
            case.addItem(c, {"UPPER": "upper", "lower": "lower", "Title": "title"}.get(c))
        form.addRow("Case", case)
        num = QtWidgets.QCheckBox("number them")
        start, step, pad = QtWidgets.QSpinBox(), QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        start.setRange(0, 9999)
        start.setValue(1)
        step.setRange(1, 100)
        step.setValue(1)
        pad.setRange(1, 4)
        pad.setValue(1)
        where = QtWidgets.QComboBox()
        where.addItem("at the end", "end")
        where.addItem("at the start", "start")
        row = QtWidgets.QHBoxLayout()
        for w_ in (num, start, step, pad, where):
            row.addWidget(w_)
        form.addRow("Numbers (start, step, digits)", row)
        preview = QtWidgets.QLabel("")
        form.addRow("Preview", preview)

        def values():
            return dict(prefix=f["prefix"].text(), suffix=f["suffix"].text(), find=f["find"].text(),
                        replace=f["replace"].text(), cut_start=f["cut_start"].value(), cut_end=f["cut_end"].value(),
                        case=case.currentData(), number=(start.value(), step.value(), pad.value(),
                                                         where.currentData()) if num.isChecked() else None)

        def show(*_):
            new = PX.rename_labels([i.get("label") or "" for i in items], **values())
            preview.setText("\n".join("%s  ->  %s" % (i.get("label") or "", n) for i, n in
                                      list(zip(items, new))[:8]) + ("\n..." if len(items) > 8 else ""))
        for w_ in list(f.values()):
            (w_.textChanged if hasattr(w_, "textChanged") and isinstance(w_, QtWidgets.QLineEdit)
             else w_.valueChanged).connect(show)
        for w_ in (start, step, pad):
            w_.valueChanged.connect(show)
        case.currentIndexChanged.connect(show)
        where.currentIndexChanged.connect(show)
        num.toggled.connect(show)
        show()
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        self._rename_ui = {"fields": f, "values": values}
        if _exec(d):
            self.rename_items(items, **values())

    def rename_items(self, items, **how):
        new = PX.rename_labels([i.get("label") or "" for i in items], **how)
        self.remember("rename")
        for it, n in zip(items, new):
            it["label"] = n
        self.changed()
        self.canvas.update()
        A.message("%d item(s) renamed." % len(items))
        return new

    # -- 5.6.26: shapes --------------------------------------------------------
    def shape_gallery(self):
        """Every shape drawn - the picker's and the rig tool's library - search, favourites, recent; the control's
        own curve; the shapes most like it. Hover: tried on the picked; click: kept."""
        items = [i for i in self.picked_items() if not PM.is_frame(i) and not PM.is_text(i)]
        if not items:
            A.message("pick buttons first - then choose their shape.", "warn")
            return
        before = [(i, i.get("shape"), list(i.get("points") or []), i.get("shape_name")) for i in items]
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Shapes")
        d.resize(520, 560)
        v = QtWidgets.QVBoxLayout(d)
        top = QtWidgets.QHBoxLayout()
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Search shapes...")
        top.addWidget(search, 1)
        v.addLayout(top)
        own = QtWidgets.QHBoxLayout()
        own.addWidget(QtWidgets.QLabel("Its control's curve:"))
        for view in ("best", "front", "side", "top"):
            b = QtWidgets.QPushButton(view)
            b.setToolTip("The button the shape of its control's curve, seen from %s." % (
                "the side that shows it best" if view == "best" else "the " + view))
            b.clicked.connect((lambda vw=view: lambda *_: (self.shape_from_control(vw), d.accept()))())
            own.addWidget(b)
        v.addLayout(own)
        sim = QtWidgets.QLabel("")
        v.addWidget(sim)
        grid_holder = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_holder)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_holder)
        v.addWidget(scroll, 1)
        favs = list(self.look.get("shape_favs") or [])
        recent = list(self.look.get("shape_recent") or [])
        cells = []

        def apply(name):
            restore()                                     # (a hover tried it: undo goes back to before)
            self.remember("shape")
            PX.apply_shape(items, name)
            rec = [name] + [r for r in recent if r != name]
            self.set_look("shape_recent", rec[:12])
            self.changed()
            self.canvas.update()
            before[:] = [(i, i.get("shape"), list(i.get("points") or []), i.get("shape_name")) for i in items]
            d.accept()

        def restore():
            for it, sh, pts, nm in before:
                it["shape"] = sh
                if pts:
                    it["points"] = pts
                else:
                    it.pop("points", None)
                if nm:
                    it["shape_name"] = nm
                else:
                    it.pop("shape_name", None)
            self.canvas.update()

        def fav(name):
            got = list(self.look.get("shape_favs") or [])
            got = [x for x in got if x != name] if name in got else got + [name]
            self.set_look("shape_favs", got)
            fill()

        def fill(*_):
            for b in cells:
                b.setParent(None)
            del cells[:]
            text = search.text().strip().lower()
            groups = []
            if not text:
                if favs or self.look.get("shape_favs"):
                    groups.append(("Favourites", [x for x in (self.look.get("shape_favs") or [])]))
                if recent:
                    groups.append(("Recent", recent))
            for cat, entries in PX.library():
                names = [n for n, _p, _a in entries if not text or text in n.lower()]
                if names:
                    groups.append((cat, names))
            r = 0
            for cat, names in groups:
                head = QtWidgets.QLabel(cat)
                grid.addWidget(head, r, 0, 1, 6)
                cells.append(head)
                r += 1
                for k, name in enumerate(names):
                    b = _ShapeButton(name, lambda nm=name: (PX.apply_shape(items, nm), self.canvas.update()),
                                     restore)
                    b.setIcon(_shape_icon(name))
                    b.setText(name.replace("_", " "))
                    b.setToolTip("%s - click: use it; right-click: favourite" % name)
                    b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                    b.clicked.connect((lambda nm=name: lambda *_: apply(nm))())
                    b.setContextMenuPolicy(Qt.CustomContextMenu)
                    b.customContextMenuRequested.connect((lambda nm=name: lambda *_: fav(nm))())
                    grid.addWidget(b, r + k // 6, k % 6)
                    cells.append(b)
                r += (len(names) + 5) // 6
        search.textChanged.connect(fill)
        fill()
        pts = self._control_points(items[0])
        if pts:
            got, _a = PX.view_points(pts, PX.best_view(pts))
            near = PX.similar(got)
            sim.setText("Most like its control: " + ", ".join(n for n, _s in near[:5]))
            self._similar = near
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
        bb.rejected.connect(d.reject)
        v.addWidget(bb)
        self._gallery_ui = {"apply": apply, "restore": restore, "fill": fill, "fav": fav}
        if not _exec(d):
            restore()

    def _control_points(self, it):
        nodes = self.nodes_of(it)
        if not nodes:
            return None
        try:
            return PM._outline(nodes[0])
        except Exception:
            return None

    def shape_from_control(self, view="best"):
        """The picked buttons the shape of their own control's curve (seen from the front / side / top)."""
        def go(its):
            n = 0
            for it in its:
                pts = self._control_points(it)
                if not pts:
                    continue
                got, _aspect = PX.view_points(pts, PX.best_view(pts) if view == "best" else view)
                if got:
                    it["shape"], it["points"] = "poly", got
                    it.pop("shape_name", None)
                    n += 1
            A.message("%d button(s) shaped like their control." % n)
        self.edit(go)

    # -- 5.6.26: colours, limbs, layers that follow the rig -----------------------
    def fill_colour_menu(self, menu):
        menu.clear()
        menu.addAction("Pick a colour...", self.recolour)
        menu.addAction("Like their controls (the rig's colours)", self.colour_like_controls)
        menu.addAction("By side (your colours)", self.colour_sides)
        pal = menu.addMenu("Maya's colours")
        for i, rgb in enumerate(PX.MAYA_PALETTE):
            a = pal.addAction("%d" % (i + 1))
            a.setIcon(_swatch(rgb))
            a.triggered.connect((lambda c=rgb: lambda *_: self.edit(lambda its: PM.set_value(its, "rgb", list(c))))())

    def colour_like_controls(self):
        items = self.picked_items() or (self.page() or {}).get("items", [])

        def colour_of(name):
            got = A.resolve(name, self.ns)
            return A._colour(got) if got else None
        self.edit(lambda _its: A.message("%d button(s) took their control's colour." % PX.match_colours(
            items, colour_of)), need=False)

    def group_by_limb(self):
        page = self.page()
        if not page:
            return
        limbs = []
        for s in A.with_attr("gusBlend", self.ns):
            try:
                names = [A.short(n) for n in A.limb_controls(s)]
            except Exception:
                continue
            limbs.append((PX.limb_title(s), names))
        if not limbs:
            A.message("no limbs with an IK/FK switch found in this character.", "warn")
            return
        self.edit(lambda _its: A.message("%d limb frame(s) made." % len(PX.group_by_limb(page, limbs))), need=False)

    def link_layer_to_switch(self, name):
        """The layer shows when a rig attribute is on (pick it in the Channel Box): a visibility switch."""
        got = self.choose_attr(("bool", "enum", "double", "long"), "The rig switch this layer follows")
        if not got:
            return
        L = PX.layer(self.page(), name)
        self.remember("layer switch")
        L["switch"] = "%s.%s" % (A.short(got[0]), got[1])
        self.changed()
        self.canvas.update()
        A.message("layer '%s' follows %s." % (name, L["switch"]))

    def _switch_value(self, plug):
        node, attr = plug.split(".", 1)
        got = A.resolve(node, self.ns)
        if not got:
            return 1.0
        try:
            return float(cmds.getAttr(got + "." + attr))
        except (RuntimeError, ValueError, TypeError):
            return 1.0

    def ikfk_faded(self, it):
        """True when the button's control belongs to the limb's mode that's off (IK while in FK...)."""
        nodes = self.nodes_of(it)
        if not nodes or it.get("kind") != "select" or not self.look.get("ikfk_fade", True):
            return False
        n = nodes[0]
        if n not in self._ikfk:
            info = None
            try:
                s = A.settings_of(n)
                if s:
                    fk = set(A.limb_controls(s, "fk"))
                    ik = set(A.limb_controls(s, "ik"))
                    info = (s, "fk" if n in fk else ("ik" if n in ik else None))
            except Exception:
                info = None
            self._ikfk[n] = info
        info = self._ikfk[n]
        if not info or not info[1]:
            return False
        try:
            in_fk = A._in_fk(info[0])
        except Exception:
            return False
        return (info[1] == "ik" and in_fk) or (info[1] == "fk" and not in_fk)

    # -- 5.6.26: select similar, clipboard, duplicate offset ------------------------
    def select_similar(self, what):
        page = self.page()
        items = self.picked_items()
        if not page or not items:
            return
        a = items[0]
        test = {"shape": lambda i: i.get("shape") == a.get("shape") and i.get("shape_name") == a.get("shape_name"),
                "colour": lambda i: i.get("rgb") == a.get("rgb"),
                "size": lambda i: abs(i["w"] - a["w"]) < 0.5 and abs(i["h"] - a["h"]) < 0.5,
                "layer": lambda i: i.get("layer") == a.get("layer"),
                "kind": lambda i: i.get("kind", "select") == a.get("kind", "select")}[what]
        self.picked = set(i["id"] for i in page["items"] if not PM.is_frame(i) and test(i))
        self.canvas.update()

    def select_invert(self):
        page = self.page()
        if page:
            self.picked = set(i["id"] for i in page["items"]) - self.picked
            self.canvas.update()

    def select_in_group(self):
        page = self.page()
        got = set()
        for fr in [i for i in self.picked_items() if PM.is_frame(i)]:
            got.update(m["id"] for m in PM.frame_members(page, fr))
        if got:
            self.picked = got
            self.canvas.update()

    def fill_select_menu(self, menu):
        menu.clear()
        for what, label in (("shape", "Same shape"), ("colour", "Same colour"), ("size", "Same size"),
                            ("layer", "Same layer"), ("kind", "Same kind")):
            menu.addAction(label, (lambda w_=what: lambda: self.select_similar(w_))())
        menu.addAction("Everything in the picked group(s)", self.select_in_group)
        menu.addAction("Invert", self.select_invert)
        menu.addAction("Everything  (Ctrl+A)", lambda: (setattr(self, "picked", set(
            i["id"] for i in (self.page() or {}).get("items", []))), self.canvas.update()))

    def copy_picked(self):
        items = self.picked_items()
        if items:
            _CLIPBOARD["clip"] = PX.copy_items(self.page(), items)
            A.message("%d item(s) copied - Ctrl+V pastes (any page, any picker in this Maya)." % len(items))

    def paste(self, in_place=False):
        clip = _CLIPBOARD.get("clip")
        if not clip or not self.page():
            return
        self.remember("paste")
        made = PX.paste_items(self.page(), clip, 0.0 if in_place else 12.0, 0.0 if in_place else 12.0)
        self.picked = set(i["id"] for i in made)
        self.changed()
        self.canvas.update()

    def duplicate(self):
        """Ctrl+D: a copy - moved as far as you moved the last copy (5.6.26), else a little."""
        dx, dy = self._dup_step()

        def go(its):
            made = PM.duplicate(self.page(), its, dx, dy)
            self._dup = (dict((a["id"], b["id"]) for a, b in zip(its, made)),
                         dict((b["id"], (b["x"], b["y"])) for b in made), (dx, dy))
            self.picked = set(i["id"] for i in made)
        self.edit(go)

    def _dup_step(self):
        """The offset the last copy ended up at from its original (you moved it), else 12, 12."""
        last = getattr(self, "_dup", None)
        page = self.page()
        if not last or not page:
            return 12.0, 12.0
        pairs, placed, step = last
        by = dict((i["id"], i) for i in page["items"])
        for src, dst in pairs.items():
            a, b = by.get(src), by.get(dst)
            if a is not None and b is not None and dst in self.picked:
                return round(b["x"] - a["x"], 2), round(b["y"] - a["y"], 2)
        return 12.0, 12.0

    # -- 5.6.26: backups, another character's layout, templates, undo history ----
    def restore_dialog(self):
        rows = PX.backups(A.rig_name(self.ns))
        if not rows:
            A.message("no saved versions yet (each Save keeps one, on this computer).")
            return
        names = ["%s   -   %d page(s), %d item(s)" % (when, pg, n) for _p, when, pg, n in rows]
        got, ok = QtWidgets.QInputDialog.getItem(self, "Picker history", "Go back to (Save keeps it again):",
                                                 names, 0, False)
        if ok and got:
            self.restore_backup(rows[names.index(got)][0])

    def restore_backup(self, path):
        self.remember("restore a saved version")
        self.picker = PX.load_backup(path)
        PM._sync_ids(self.picker)
        self.index = 0
        self.changed()
        self.fill_tabs()
        self.canvas.frame()
        A.message("an older version is back - Save keeps it, Undo takes it away.")

    def copy_from_character(self):
        others = [c for c in A.characters() if c != self.ns]
        if not others:
            A.message("no other character in this scene.", "warn")
            return
        got, ok = QtWidgets.QInputDialog.getItem(self, "Another character's picker",
                                                 "Copy its pages (the buttons find these controls by name):",
                                                 [c or "(no namespace)" for c in others], 0, False)
        if not ok:
            return
        other = others[[c or "(no namespace)" for c in others].index(got)]
        src = PM.load(other, make=False)
        if not src:
            A.message("that character has no saved picker.", "warn")
            return
        self.add_pages_from(src)

    def add_pages_from(self, src):
        self.remember("pages from another character")
        n = 0
        for pg in src.get("pages", []):
            raw = copy.deepcopy(pg)
            name = raw.get("name") or "Page"
            raw["name"] = "__copying__"
            self.picker["pages"].append(raw)
            PM._sync_ids(self.picker)
            i = PM.duplicate_page(self.picker, len(self.picker["pages"]) - 1, name=name)
            self.picker["pages"].pop(i - 1)
            n += 1
        self.changed()
        self.fill_tabs()
        self.show_missing()
        A.message("%d page(s) copied - Save keeps them." % n)
        return n

    def fill_templates_menu(self, menu):
        menu.clear()
        got = PX.templates()
        if self.page():
            menu.addAction("Save this page as a template...", self.save_template)
        for name in sorted(got):
            menu.addAction("New page from '%s'" % name, (lambda n=name: lambda: self.page_from_template(n))())
        if got:
            dm = menu.addMenu("Delete a template")
            for name in sorted(got):
                dm.addAction(name, (lambda n=name: lambda: PX.delete_template(n))())

    def save_template(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Page template", "Its name (yours, on this computer):",
                                                  text=self.page()["name"])
        if ok and name.strip():
            PX.save_template(self.page(), name.strip())
            A.message("template '%s' saved." % name.strip())

    def page_from_template(self, name):
        self.remember("page from a template")
        self.index = PX.page_from_template(self.picker, name)
        self.changed()
        self.fill_tabs()
        self.canvas.frame()
        self.show_missing()

    def history_dialog(self):
        steps = self.history.steps()
        if not steps:
            A.message("nothing to undo yet.")
            return
        names = ["%d. %s  %s" % (k + 1, t, what) for k, (t, what) in enumerate(steps)][::-1]
        got, ok = QtWidgets.QInputDialog.getItem(self, "Undo history", "Go back to before:", names, 0, False)
        if ok and got:
            k = int(got.split(".", 1)[0]) - 1
            self.undo_to(k)

    def undo_to(self, k):
        got = self.history.back_to(self.picker, k)
        if got is not None:
            self.picker = got
            self.changed()
            self.fill_tabs()
            self.canvas.update()

    # -- 5.6.26: preview as the animators see it; find on every page ------------------
    def toggle_preview(self, on=None):
        self.preview = (not self.preview) if on is None else bool(on)
        self.canvas.update()

    def find_everywhere(self, text):
        """The find box: here, and how many on the other pages (Enter goes there when none here)."""
        got = PX.find_all(self.picker or {}, text)
        self.search_ids = set(got.get(self.index, []))
        self._found_pages = got
        others = sum(len(v) for k, v in got.items() if k != self.index)
        try:
            self.find_box.setToolTip("%d here, %d on other pages" % (len(self.search_ids), others))
        except Exception:
            pass
        self.canvas.update()
        return got

    # -- the Item panel ------------------------------------------------------
    PANEL = (("label", "Text", "text"), ("tooltip", "Note for animators", "text"),
             ("badge", "Badge (- none)", "text"), ("x", "X", "num"), ("y", "Y", "num"),
             ("w", "Width", "num"), ("h", "Height", "num"), ("rot", "Turn", "num"), ("shape", "Shape", "shape"),
             ("rgb", "Colour", "colour"), ("alpha", "Solid (frames)", "frac"), ("border_rgb", "Border colour", "colour"),
             ("border_w", "Border width", "num"), ("corner", "Corners", "frac"), ("text_size", "Text size (0 auto)",
                                                                                   "num"),
             ("text_rgb", "Text colour", "colour"), ("bold", "Bold", "check"), ("tpos", "Text place", "tpos"),
             ("tdx", "Text moved x (Ctrl+drag)", "num"), ("tdy", "Text moved y", "num"),
             ("align", "Lines align", "align"), ("wrap", "Wrap (0 no, 1 its width)", "num"),
             ("plate", "Plate behind text", "check"),
             ("text_fit", "Text too long", "fit"), ("on_rgb", "On colour (toggle)", "colour"),
             ("label_on", "Text when on", "text"), ("label_off", "Text when off", "text"),
             ("locked", "Locked", "check"), ("pin", "Pinned", "check"))
    PANEL_SECTIONS = (("Place & size", ("x", "y", "w", "h", "rot")),
                      ("Text", ("label", "text_size", "text_rgb", "bold", "tpos", "tdx", "tdy", "align", "wrap",
                                "plate", "text_fit")),
                      ("Look", ("shape", "rgb", "alpha", "border_rgb", "border_w", "corner")),
                      ("For animators", ("tooltip", "badge")),
                      ("Toggle", ("on_rgb", "label_on", "label_off")),
                      ("Lock / pin", ("locked", "pin")),
                      ("Connector", ("ln_style", "ln_width", "ln_rgb", "ln_dash", "ln_head_a", "ln_head_b",
                                     "ln_a_side", "ln_b_side", "ln_label", "ln_label_at")))
    LINK_PANEL = (("ln_style", "Connector", "lstyle"), ("ln_width", "Line width", "num"),
                  ("ln_rgb", "Line colour", "colour"), ("ln_dash", "Line", "ldash"), ("ln_head_a", "Start", "lhead"),
                  ("ln_head_b", "End", "lhead"), ("ln_a_side", "Leaves from", "lside"),
                  ("ln_b_side", "Arrives at", "lside"), ("ln_label", "Label", "text"),
                  ("ln_label_at", "Label along", "frac"))
    PLACES = ("center", "above", "below", "left", "right")
    FITS = ("grow", "cut", "fit", "overflow")            # 5.6.24: grow (the default) runs past the edge, on a plate
    ALIGNS = ("left", "center", "right")
    CHOICES = {"shape": PM.SHAPES, "place": PLACES, "fit": FITS, "title": PM.TITLE_PLACES, "align": ALIGNS,
               "tpos": PX.TEXT_PLACES, "lstyle": PX.LINK_STYLES, "ldash": PX.LINK_DASHES, "lhead": PX.LINK_HEADS,
               "lside": PX.LINK_SIDES}
    DEFAULT_CHOICE = {"shape": "round", "place": "center", "fit": "grow", "title": "bar", "align": "center",
                      "tpos": "center", "lstyle": "curved", "ldash": "solid", "lhead": "none", "lside": "auto"}

    def _panel_field(self, key, kind):
        if kind == "text":
            f = QtWidgets.QLineEdit()
            f.editingFinished.connect((lambda k=key, ff=f: lambda: self.panel_set(k, ff.text()))())
        elif kind in ("num", "frac"):
            f = QtWidgets.QDoubleSpinBox()
            f.setRange(0.0 if kind == "frac" or key in ("w", "h", "text_size", "border_w", "wrap", "ln_width")
                       else -9999.0, 1.0 if kind == "frac" else 9999.0)
            f.setDecimals(2)
            f.setSingleStep(0.05 if kind == "frac" else 1.0)
            f.editingFinished.connect((lambda k=key, ff=f: lambda: self.panel_set(k, ff.value()))())
        elif kind in self.CHOICES:
            f = QtWidgets.QComboBox()
            for v in self.CHOICES[kind]:
                f.addItem(v, v)
            f.currentIndexChanged.connect((lambda k=key, ff=f: lambda *_: self.panel_set(k, ff.currentData()))())
        elif kind == "colour":
            f = QtWidgets.QPushButton("")
            f.clicked.connect((lambda k=key: lambda *_: self.panel_colour(k))())
        else:
            f = QtWidgets.QCheckBox("")
            f.toggled.connect((lambda k=key: lambda on: self.panel_set(k, bool(on)))())
        return f

    def _build_panel(self):
        """5.6.26: the Item panel in sections that fold (only the ones for what's picked show); it can float."""
        outer = QtWidgets.QWidget()
        outer.setFixedWidth(236)
        ov = QtWidgets.QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(1)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("Item"), 1)
        self.panel_float_btn = QtWidgets.QToolButton()
        self.panel_float_btn.setText("Undock")
        self.panel_float_btn.setToolTip("The panel in its own window (close it to dock it back).")
        self.panel_float_btn.clicked.connect(lambda *_: self.dock_panel() if self.panel_window is not None
                                             else self.float_panel())
        head.addWidget(self.panel_float_btn)
        ov.addLayout(head)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        ov.addWidget(scroll, 1)
        w = QtWidgets.QWidget()
        scroll.setWidget(w)
        col = QtWidgets.QVBoxLayout(w)
        col.setContentsMargins(2, 0, 0, 0)
        col.setSpacing(1)
        self.fields = {}
        self.panel_sections = {}
        kinds = dict((k, (label, kind)) for k, label, kind in list(self.PANEL) + list(self.LINK_PANEL))
        opened = set(self.look.get("panel_open") if self.look.get("panel_open") is not None else [])
        for name, keys in self.PANEL_SECTIONS:
            hb = QtWidgets.QToolButton()
            hb.setCheckable(True)
            hb.setChecked(name in opened)
            hb.setText(("v  " if name in opened else ">  ") + name)
            hb.setStyleSheet("QToolButton { border: none; font-weight: bold; text-align: left; }")
            hb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            box = QtWidgets.QWidget()
            g = QtWidgets.QGridLayout(box)
            g.setContentsMargins(4, 0, 0, 4)
            g.setSpacing(2)
            for row, key in enumerate(keys):
                if key not in kinds:
                    continue
                label, kind = kinds[key]
                g.addWidget(QtWidgets.QLabel(label), row, 0)
                f = self._panel_field(key, kind)
                self.fields[key] = (kind, f)
                g.addWidget(f, row, 1)
            box.setVisible(name in opened)
            hb.toggled.connect((lambda n=name, bx=box, b_=hb: lambda on: self._panel_section(n, bx, b_, on))())
            col.addWidget(hb)
            col.addWidget(box)
            self.panel_sections[name] = (hb, box)
        col.addStretch(1)
        return outer

    def _panel_section(self, name, box, head, on):
        box.setVisible(bool(on))
        head.setText(("v  " if on else ">  ") + name)
        got = [n for n in (self.look.get("panel_open") or []) if n != name]
        self.set_look("panel_open", got + ([name] if on else []))

    def float_panel(self):
        if self.panel_window is not None:
            return
        self.panel_window = _Floating(self, "Picker - item", self.dock_panel)
        self.panel_window.layout().addWidget(self.panel)
        self.panel.setVisible(True)
        self.panel_float_btn.setText("Dock")
        self.panel_window.resize(260, 520)
        self.panel_window.show()
        self.set_look("panel_float", True)

    def dock_panel(self):
        if self.panel_window is None:
            return
        win, self.panel_window = self.panel_window, None
        self.mid.addWidget(self.panel)
        self.panel.setVisible(self.editing)
        self.panel_float_btn.setText("Undock")
        self.set_look("panel_float", False)
        try:
            win.hide()
            win.deleteLater()
        except Exception:
            pass

    def refresh_panel(self):
        items = self.picked_items() if self.editing else []
        links = self.picked_link_items() if self.editing else []
        self._panel_busy = True
        try:
            self.panel.setEnabled(bool(items or links))
            self._panel_for = tuple(sorted(self.picked)) if items else None
            for name, (hb, box) in getattr(self, "panel_sections", {}).items():   # 5.6.26: only what applies
                show = bool(links) if name == "Connector" else (
                    any(i.get("kind") == "toggle" for i in items) if name == "Toggle" else bool(items))
                hb.setVisible(show)
                box.setVisible(show and hb.isChecked())
            if not items and not links:
                return
            it = items[0] if items else {}
            ln = links[0] if links else {}
            for key, (kind, f) in self.fields.items():
                linkf = key.startswith("ln_")
                f.setEnabled(bool(ln) if linkf else bool(items))
                if (linkf and not ln) or (not linkf and not items):
                    continue
                v = ln.get(key[3:]) if linkf else it.get(key)
                if key == "text_size" and PM.is_text(it):      # 5.6.24: a text's own size
                    v = it.get("size", 14.0)
                if key == "tpos":
                    v = PX.text_place(it)
                if key == "ln_width" and v is None:
                    v = 1.5
                if key == "ln_label_at" and v is None:
                    v = 0.5
                if kind == "text":
                    if not f.hasFocus():
                        f.setText(v or "")
                elif kind in ("num", "frac"):
                    if not f.hasFocus():
                        dflt = {"alpha": 0.35, "border_w": 1.0, "corner": 0.25 if it.get("shape", "round") == "round"
                                else 0.0}.get(key, 0.0)
                        f.setValue(float(dflt if v is None else v))
                elif kind in self.CHOICES:
                    want = v or self.DEFAULT_CHOICE[kind]
                    for i in range(f.count()):
                        if f.itemData(i) == want:
                            f.setCurrentIndex(i)
                elif kind == "colour":
                    rgb = v or ([0.08, 0.08, 0.09] if key == "border_rgb" else [0.9, 0.9, 0.9] if key == "text_rgb"
                                else [0.36, 0.78, 0.45] if key == "on_rgb" else [0.75, 0.78, 0.85] if linkf
                                else [0.5, 0.5, 0.5])
                    c = _colour(rgb)
                    f.setStyleSheet("background-color: rgb(%d, %d, %d);" % (c.red(), c.green(), c.blue()))
                    f.setText("" if v else "auto")
                else:
                    f.setChecked(bool(v))
        finally:
            self._panel_busy = False

    def panel_set(self, key, value):
        if key.startswith("ln_"):                             # 5.6.25: the picked connector
            if not self._panel_busy and self.picked_link_items():
                self.link_set(key[3:], value)
            return
        if self._panel_busy or not self.picked_items():
            return
        if self._panel_for is not None and self._panel_for != tuple(sorted(self.picked)):
            return                          # 5.6.23: a field left after picking others: not onto the new ones
        first = self.picked_items()[0]
        if key in ("x", "y", "w", "h", "rot", "tdx", "tdy", "wrap") and \
                abs(float(first.get(key) or 0.0) - float(value)) < 1e-6:
            return                          # unchanged (a field just losing focus)
        if key == "pin":
            if bool(value) != all(i.get("pin") for i in self.picked_items()):
                self.toggle_pin()
            return
        if key in ("x", "y"):                              # a block of picked: the first goes there, the rest along
            items = self.picked_items()
            d = float(value) - items[0][key]
            self.edit(lambda its: PM.move(its, d if key == "x" else 0.0, d if key == "y" else 0.0))
            self.canvas.store_pins(items)
            return
        if key == "text_size":                              # 5.6.24: texts keep theirs as 'size'

            def go(its):
                for i in its:
                    if PM.is_text(i):
                        if float(value) > 0:
                            i["size"] = float(value)
                    else:
                        i["text_size"] = float(value)
            self.edit(go)
            return
        self.edit(lambda its: PM.set_value(its, key, value))

    def panel_colour(self, key):
        if key.startswith("ln_"):
            self.link_colour()
            return
        items = self.picked_items()
        if not items:
            return
        c = QtWidgets.QColorDialog.getColor(_colour(items[0].get(key) or [0.5] * 3), self, key)
        if c.isValid():
            self.edit(lambda its: PM.set_value(its, key, [c.redF(), c.greenF(), c.blueF()]))

    def fill_frames_menu(self, menu):
        menu.clear()
        page = self.page()
        frames = [i for i in (page or {}).get("items", []) if PM.is_frame(i)]
        if not frames:
            menu.addAction("(no frames on this page - Edit > Group makes one)").setEnabled(False)
            return
        for fr in frames:
            a = menu.addAction(fr.get("label") or "Group")
            a.setCheckable(True)
            a.setChecked(not fr.get("hidden"))
            a.toggled.connect((lambda f=fr: lambda on: self._show_frame(f, on))())

    def _show_frame(self, fr, on):
        fr["hidden"] = not on                               # a view setting: Save keeps it
        self.changed()
        self.canvas.update()

    def delete(self):
        page = self.page()
        if self.picked_links and page:                       # 5.6.25: the picked connectors too
            self.remember()
            page["links"] = [ln for ln in page.get("links") or [] if ln["id"] not in self.picked_links]
            self.picked_links = set()
            self.changed()
        if self.picked:
            self.edit(lambda its: PM.delete(self.page(), its))
        self.picked = set()
        self.canvas.update()

    def key(self, event=None):
        """The Key button (no event), or a key pressed on the canvas (True when used)."""
        if event is None:
            sel = A.selected()
            if not sel:
                raise RuntimeError("select controls first.")
            cmds.setKeyframe(sel)
            A.message("keyed %d control(s)." % len(sel))
            return True
        k, mods = event.key(), event.modifiers()
        if self.editing:
            step = (self.grid() or 8.0) if _has(mods, Qt.ControlModifier) else (
                10.0 if _has(mods, Qt.ShiftModifier) else 1.0)            # 5.6.26: Ctrl: a grid step
            arrows = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0), Qt.Key_Up: (0, -step),
                      Qt.Key_Down: (0, step)}
            if k in arrows:
                self.edit(lambda its: PM.move(its, *arrows[k]))
                return True
            if k in (Qt.Key_Delete, Qt.Key_Backspace):
                self.delete()
                return True
        if k == Qt.Key_Escape and (self.canvas.help or self.search_ids):
            self.canvas.help = False
            self.hide_find()
            return True
        action = PX.action_for(_key_text(event) or "")      # 5.6.24: your keys (Picker > Keys...)
        if action is None:
            return False
        page = self.page() or {"items": []}
        anywhere = {"frame": lambda: self.canvas.frame(),
                    "frame picked": lambda: self.canvas.frame((self.picked_items() if self.editing else [
                        i for i in page["items"] if any(n in self.maya_selection() for n in self.nodes_of(i))])
                        or None),
                    "find": self.show_find, "help": self.toggle_help}
        if action in anywhere:
            anywhere[action]()
            return True
        if not self.editing:
            if action == "key":
                self.run(self.key)
                return True
            return False
        edit = {"undo": self.undo, "redo": self.redo, "duplicate": self.duplicate, "save": self.save,
                "undo (Maya)": self.undo, "redo (Maya)": self.redo, "copy": self.copy_picked,
                "paste": self.paste, "paste in place": lambda: self.paste(True), "preview": self.toggle_preview,
                "rename": self.rename_dialog,
                "group": self.group, "ungroup": self.ungroup, "to front": lambda: self.order("front"),
                "up one": lambda: self.order("up"), "to back": lambda: self.order("back"),
                "down one": lambda: self.order("down"), "lock": self.toggle_lock,
                "pick all": lambda: (setattr(self, "picked", set(i["id"] for i in page["items"])),
                                     self.canvas.update())}
        if action in edit:
            edit[action]()
            return True
        return False

    def context_menu(self, gpos, x, y):
        menu = QtWidgets.QMenu(self)
        page = self.page()
        it = PM.hit_any(page, x, y, self.editing) if page else None
        ln = PX.hit_link(page, x, y, 5.0 / max(self.canvas.scale, 1e-6)) if (page and self.editing and
                                                                            it is None) else None
        if ln is not None:                                   # 5.6.25: a connector's own menu
            self.picked_links = {ln["id"]}
            self.picked = set()
            self.canvas.update()
            self.fill_link_menu(menu, ln, x, y)
            self._last_menu = menu
            _exec(menu, gpos)
            return
        if self.editing:
            if it is not None and it["id"] not in self.picked:
                self.picked = {it["id"]}
                self.canvas.update()
            if self.picked:
                shape = menu.addMenu("Shape")
                for s in PM.SHAPES:
                    shape.addAction(s, (lambda v=s: lambda: self.edit(lambda its: PM.set_value(its, "shape", v)))())
                menu.addAction("Colour...", self.recolour)
                menu.addAction("Label...", self.relabel)
                size = menu.addMenu("Size")
                size.addAction("Bigger", lambda: self.edit(lambda its: PM.resize(its, 1.2)))
                size.addAction("Smaller", lambda: self.edit(lambda its: PM.resize(its, 1 / 1.2)))
                size.addAction("Same size as the first", lambda: self.edit(
                    lambda its: PM.resize(its[1:], w=its[0]["w"], h=its[0]["h"])))
                align = menu.addMenu("Align / distribute")
                for s in ("left", "right", "top", "bottom", "hcenter", "vcenter"):
                    align.addAction(s, (lambda v=s: lambda: self.edit(lambda its: PM.align(its, v)))())
                align.addAction("distribute across", lambda: self.edit(lambda its: PM.distribute(its, "x")))
                align.addAction("distribute down", lambda: self.edit(lambda its: PM.distribute(its, "y")))
                order = menu.addMenu("Order")
                for label, how in (("Bring to front  (Ctrl+Shift+])", "front"), ("Up one  (Ctrl+])", "up"),
                                   ("Down one  (Ctrl+[)", "down"), ("Send to back  (Ctrl+Shift+[)", "back")):
                    order.addAction(label, (lambda h=how: lambda: self.order(h))())
                menu.addAction("Group (frame with a title)...  (Ctrl+G)", self.group)
                if any(PM.is_frame(i) for i in self.picked_items()):
                    menu.addAction("Ungroup  (Ctrl+Shift+G)", self.ungroup)
                    menu.addAction("Frame see-through...", self.transparency)
                    hidden = any(i.get("hidden") for i in self.picked_items() if PM.is_frame(i))
                    menu.addAction("Show the frame" if hidden else "Hide the frame (and its buttons)",
                                   lambda: self.edit(lambda its: PM.set_value(
                                       [i for i in its if PM.is_frame(i)], "hidden", not hidden)))
                if any(PM.is_text(i) for i in self.picked_items()):
                    tx = menu.addMenu("Text")
                    for label, how in (("left", "left"), ("centre", "center"), ("right", "right")):
                        tx.addAction(label, (lambda h=how: lambda: self.edit(
                            lambda its: PM.set_value([i for i in its if PM.is_text(i)], "align", h)))())
                    tx.addAction("bold on / off", lambda: self.edit(lambda its: [i.update({"bold": not i.get(
                        "bold", True)}) for i in its if PM.is_text(i)]))
                menu.addAction("Lock / unlock  (Ctrl+L)", self.toggle_lock)
                menu.addAction("Pin / unpin (stays in the window)", self.toggle_pin)
                sty = menu.addMenu("Saved styles")
                self.fill_styles_menu(sty)
                st = menu.addMenu("Style")
                st.addAction("Copy style", self.copy_style)
                st.addAction("Paste style", self.paste_style)
                mv = menu.addMenu("Move to page")
                for pg in self.picker["pages"]:
                    if pg is not page:
                        mv.addAction(pg["name"], (lambda n=pg["name"]: lambda: self.move_to_page(n))())
                mv.addAction("New page...", lambda: self.move_to_page(None))
                menu.addAction("Mirror to the other side", self.mirror)
                menu.addAction("Use the selected controls", lambda: self.edit(lambda its: PM.set_value(
                    its, "nodes", [PM.strip(n) for n in A.selected()])))
                menu.addAction("Selection set from these...", self.add_set)
                menu.addAction("Colour by side", self.colour_sides)
                menu.addAction("Arrange as the front view", lambda: self.run(
                    lambda: self.arrange_front(picked_only=True)))
                menu.addAction("Duplicate  (Ctrl+D)", self.duplicate)
                menu.addAction("Delete  (Del)", self.delete)
                menu.addAction("Take out (delete, and keep the control off the picker)", self.exclude_picked)
                cmd = [i for i in self.picked_items() if i.get("kind") == "command"]
                if cmd:
                    menu.addAction("Edit the script...", lambda: self.script_dialog(cmd[0]))
                menu.addSeparator()
            add = menu.addMenu("Add here")
            add.addAction("A button per selected control", lambda: self.add_selected(x, y))
            add.addAction("One button for the selected controls...", lambda: self.add_group(x, y))
            add.addAction("Slider (Channel Box attribute)", lambda: self.add_widget("slider", x, y))
            add.addAction("Check box (Channel Box attribute)", lambda: self.add_widget("check", x, y))
            add.addAction("Command button...", lambda: self.add_command(x, y))
            add.addAction("Text / title...", lambda: self.add_text(x, y))
            add.addAction("2D slider (two Channel Box attributes)", lambda: self.add_pad(x, y))
            add.addAction("Toggle (Channel Box attribute)", lambda: self.add_widget("toggle", x, y))
            add.addAction("Space switch (Channel Box enum attribute)", lambda: self.add_enum(x, y))
            add.addAction("Sticky note", lambda: self.add_note(x, y))
            if len(self.picked) > 1:
                menu.addAction("Connect the picked (a chain)", self.connect_picked)
            menu.addAction("Connectors from the rig's hierarchy", self.lines_from_hierarchy)
            lay = menu.addMenu("Layers")
            self.fill_layers_menu(lay)
            add.addAction("Script button...", lambda: self.script_dialog(None, x, y))
            menu.addSeparator()
            menu.addAction("Missing controls...", self.missing_dialog)
            menu.addAction("Arrange pages as the front view...", self.front_view_dialog)
            menu.addAction("Duplicate this page (try things on the copy)", self.duplicate_page)
            if PM.pinned(self.picker or {}):
                menu.addAction("Unpin all", self.unpin_all)
            self.page_menu(menu)
            menu.addAction("Auto layout...", self.auto)
            self.picker_menu(menu.addMenu("Picker file"))
        else:
            if it is not None and PM.is_frame(it):            # 5.6.24: a frame - all its controls
                members = PM.frame_members(page, it)
                self.run(lambda: self.select_items(members, Qt.NoModifier))
                menu.addAction("Select all in '%s'" % (it.get("label") or "the frame"),
                               lambda: self.run(lambda: self.select_items(members, Qt.NoModifier)))
            elif it is not None and it.get("kind") == "select" and not any(
                    n in self.maya_selection() for n in self.nodes_of(it)):
                self.run(lambda: self.click(it, Qt.NoModifier))
            menu.addAction("Key  (S)", lambda: self.run(self.key))     # 5.6.24: what animators use most, first
            menu.addAction("Reset", lambda: self.run(lambda: A.reset_pose("selection")))
            menu.addAction("Select the twin", lambda: self.run(lambda: A.select_twin("other")))
            menu.addAction("Add the twin", lambda: self.run(lambda: A.select_twin("both")))
            menu.addAction("Select the limb", lambda: self.run(lambda: A.select_set("limb")))
            menu.addSeparator()
            menu.addAction("IK / FK switch", lambda: self.run(lambda: A.switch("toggle")))
            menu.addAction("Mirror pose left -> right", lambda: self.run(lambda: A.mirror_pose("L>R")))
            menu.addAction("Mirror pose right -> left", lambda: self.run(lambda: A.mirror_pose("R>L")))
            menu.addAction("Flip pose", lambda: self.run(A.flip_pose))
            menu.addSeparator()
            menu.addAction("Find...  (Ctrl+F)", self.show_find)
            sets = menu.addMenu("My sets")
            self.fill_mysets_menu(sets)
            menu.addAction("Seen from behind" if not self.look.get("behind") else "Seen from the front",
                           lambda: self.behind_btn.setChecked(not self.look.get("behind")))
            menu.addAction("Frame the selected  (Shift+F)", lambda: self.canvas.frame([
                i for i in page["items"] if any(n in self.maya_selection() for n in self.nodes_of(i))] or None)
                if page else None)
            if self.can_edit():
                menu.addAction("Edit the picker", lambda: self.edit_btn.setChecked(True))
        menu.addAction("Frame  (F)", self.canvas.frame)
        menu.addAction("Keys and clicks  (?)", self.toggle_help)
        _exec(menu, gpos)


# ===========================================================================
# the dockable window
# ===========================================================================

def build():
    """The window's content (Maya runs this when it opens / restores the workspace control)."""
    ptr = None
    try:
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.findControl(WORKSPACE)
    except (ImportError, RuntimeError):
        pass
    host = wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None
    w = Picker(host)
    if host is not None:
        if host.layout() is None:
            QtWidgets.QVBoxLayout(host)
        host.layout().addWidget(w)
    _state["widget"] = w
    try:
        cmds.scriptJob(event=["SelectionChanged", lambda: _alive() and _state["widget"].selection_changed()],
                       parent=WORKSPACE)
        cmds.scriptJob(event=["timeChanged", lambda: _alive() and _state["widget"].time_changed()], parent=WORKSPACE)
    except (RuntimeError, TypeError):
        pass
    return w


def _alive():
    w = _state.get("widget")
    if w is None:
        return False
    try:
        w.objectName()
        return True
    except RuntimeError:                                     # the window was closed
        _state["widget"] = None
        return False


def show():
    if cmds.workspaceControl(WORKSPACE, exists=True):
        cmds.deleteUI(WORKSPACE)
    _state["widget"] = None
    cmds.workspaceControl(WORKSPACE, label="Gus Animtool - Picker", floating=True, retain=False, initialWidth=430,
                          initialHeight=640, minimumWidth=260,
                          uiScript="import gus_animtool.pickerqt as _p; _p.build()")
    if not _alive():
        build()
    return WORKSPACE


def diagnose(shot=True):
    """5.6.24: what the open picker has, lacks and looks like - printed (and returned); a screenshot of the window
    in the temp folder. Run:  import gus_animtool.pickerqt as P; P.diagnose()"""
    import collections
    import json
    import os
    import tempfile
    import gus_animtool
    w = _state.get("widget") if _alive() else None
    ns = w.ns if w else A.current_character()
    pk = w.picker if w else (PM.load(ns, make=False) or {})
    out = ["== Gus Animtool %s | picker from: %s | window open: %s | unsaved: %s" % (
        gus_animtool.__version__, PM.where_from(ns), bool(w), bool(w and w.dirty)),
        "== your look: %s" % json.dumps(PM.prefs())]
    for pg in pk.get("pages", []):
        its = pg.get("items", [])
        kinds = collections.Counter(i.get("kind", "select") for i in its)
        w_, h_ = PM.page_size(pg)
        out.append("-- %-14s %3d items %s | page %.0f x %.0f, usual button %.0f | normalize: %s | page text x%s | "
                   "picture: %s | outline: %s | connectors %d | layers %s" % (
                       pg["name"], len(its), dict(kinds), w_, h_, PM.typical_size(its), PX.needs_normalize(pg),
                       pg.get("text_scale", 1.0), (pg.get("picture") or {}).get("kind") or bool(pg.get("picture")),
                       bool(pg.get("outline")), len(pg.get("links") or []),
                       ", ".join("%s%s" % (L["name"], "" if L.get("shown", True) else " (hidden)")
                                 for L in pg.get("layers") or []) or "-"))
    if w:
        out.append("== view: zoom %.3f | behind %s | list %s" % (w.canvas.scale, w.look.get("behind"),
                                                               w.list_btn.isChecked()))
    out.append("== meshes for the outline / picture: %d" % len(PX.rig_meshes(ns)))
    r = PM.report(pk, ns) if pk else {}
    for k in ("missing", "unsure", "excluded", "pinned", "duplicates", "gone"):
        v = r.get(k) or []
        out.append("   %-10s %3d  %s" % (k, len(v), ", ".join(map(str, v[:12]))))
    try:
        rows = PX.pair_report(ns)
        bad = [x for x in rows if x["problem"] != "position"]
        out.append("== mirror pairs to look at: %d (%s)" % (len(bad), ", ".join(
            "%s: %s" % (A.short(x["node"]), x["problem"]) for x in bad[:12])))
    except Exception as e:
        out.append("== mirror pairs: %s" % e)
    if w and shot:
        path = os.path.join(tempfile.gettempdir(), "gus_picker_view.png")
        try:
            w.grab().save(path)
            out.append("== screenshot: %s" % path)
        except Exception as e:
            out.append("== screenshot failed: %s" % e)
    text = "\n".join(out)
    print(text)
    return text
