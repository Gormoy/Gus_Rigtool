"""
5.7.9: the tools' tiles - the shelf icons and the favourites bar, one drawing for both (the Gus_Animtool shelf's
style, Gus's mock-up: a dark tile, a line drawing, a bar along the bottom in the tool's area colour; a small white
corner triangle when right-click gives the tool's options).
"""

from gus_rigtool.newui.qt import QtCore, QtGui, QtSvg

Qt = QtCore.Qt
TILE, LINE = "#23262b", "#e9ebee"
QUICK_COLOUR = "#5aa9c9"

# the drawings, 24 x 24, lines; id="A": drawn in the area's colour
G = {
    "main": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 4v16 M8 9h13"/>',
    "home": '<path d="M4 11l8-7 8 7 M6 10v10h12V10 M10 20v-5h4v5"/>',
    "build": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5"/>',
    "build_rig": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path id="A" d="M9 12l2 2 4-4"/>',
    "face": '<circle cx="12" cy="12" r="8.5"/><circle id="A" cx="9" cy="10" r="1.2"/>'
            '<circle id="A" cx="15" cy="10" r="1.2"/><path d="M8.5 14.5c2 2 5 2 7 0"/>',
    "ribbon": '<path d="M3 8c4-4 7 4 11 0s5-1 7 0 M3 16c4-4 7 4 11 0s5-1 7 0"/>'
              '<path id="A" d="M6 7v8 M10.5 9v8 M15 7v8 M19 8v8"/>',
    "joints": '<circle cx="5" cy="18" r="2.2"/><circle cx="12" cy="11" r="2.2"/><circle cx="19" cy="5" r="2.2"/>'
              '<path d="M6.6 16.4l3.8-3.8 M13.6 9.4l3.8-3"/>',
    "skin": '<path d="M5 6c3-2 11-2 14 0v12c-3 2-11 2-14 0z"/><path id="A" d="M9 5v14 M12 4.5v15 M15 5v14"/>',
    "fixes": '<path d="M4 18l7-7 7 4"/><circle cx="11" cy="11" r="2"/><path id="A" d="M17 4v4 M15 6h4"/>',
    "controls_tab": '<circle cx="12" cy="12" r="8"/><circle id="A" cx="12" cy="12" r="3"/>',
    "behaviour": '<circle cx="12" cy="13" r="7"/><path id="A" d="M12 13l5-5 M5 4l3 3 M19 4l-3 3"/>',
    "attrs": '<path d="M4 6h10 M4 11h10 M4 16h7"/><path id="A" d="M17 13v6 M14 16h6"/>',
    "channels": '<path d="M4 6h16 M4 11h16 M4 16h9"/><rect id="A" x="15" y="14.5" width="5" height="5" rx="1"/>'
                '<path id="A" d="M16 14.5v-1.5a1.5 1.5 0 0 1 3 0v1.5"/>',
    "spaces": '<circle cx="7" cy="12" r="3.5"/><circle cx="17" cy="12" r="3.5"/>'
              '<path id="A" d="M10.5 9.5c1.5-1.5 1.5-1.5 3 0 M13.5 14.5c-1.5 1.5-1.5 1.5-3 0"/>',
    "follow": '<circle cx="5" cy="17" r="2"/><path d="M7 15c4-6 8-8 13-8"/><path id="A" d="M16 4l4 3-4 3"/>',
    "stick": '<path d="M3 17c4-3 7 2 11-1s5-2 7-1"/><circle id="A" cx="12" cy="9" r="3.2"/><path d="M12 12.2v3"/>',
    "constrain": '<rect x="3" y="9" width="9" height="6" rx="3"/><rect x="12" y="9" width="9" height="6" rx="3"/>'
                 '<path id="A" d="M9 12h6"/>',
    "connect": '<circle cx="5" cy="12" r="2.5"/><circle cx="19" cy="12" r="2.5"/>'
               '<path id="A" d="M7.5 12h9 M13 9l3 3-3 3"/>',
    "nodes": '<rect x="3" y="4" width="7" height="5" rx="1"/><rect x="14" y="10" width="7" height="5" rx="1"/>'
             '<rect x="3" y="15" width="7" height="5" rx="1"/><path id="A" d="M10 6.5c3 0 2 6 4 6 M10 17.5c3 0 2-5 4-5"/>',
    "sdk": '<path d="M3 19c5 0 6-12 9-12s4 6 9 6"/><path id="A" d="M12 4.5l2.5 2.5-2.5 2.5-2.5-2.5z"/>',
    "checker": '<rect x="4" y="4" width="16" height="16" rx="3"/><path id="A" d="M8 12l3 3 5-6"/>',
    "organize": '<path d="M5 4v16 M5 8h5 M5 14h5 M10 11v6 M10 17h5"/><rect id="A" x="14" y="5" width="6" height="5" rx="1"/>',
    "publish": '<path d="M4 9l8-4 8 4v9l-8 3-8-3z M4 9l8 4 8-4 M12 13v8"/><path id="A" d="M12 2v6 M9.5 4.5L12 2l2.5 2.5"/>',
    "select": '<path d="M6 3l12 8-5.5 1.2L15 19l-2.5 1-2.6-6.6L6 17z"/>',
    "groups": '<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="7" y="7" width="10" height="10" rx="1.5"/>'
              '<rect id="A" x="10" y="10" width="4" height="4" rx="1"/>',
    "mirror": '<path d="M10 5L4 19h6z"/><path id="A" d="M14 5l6 14h-6z"/><path d="M12 3v2 M12 8v2 M12 13v2 M12 18v2"/>',
    "rename": '<path d="M4 17l4-11 4 11 M5.5 13h5"/><path id="A" d="M16 5v14 M14 5h4 M14 19h4"/>',
    "pivots": '<rect x="4" y="4" width="16" height="16" rx="2"/><path id="A" d="M12 8v8 M8 12h8"/>'
              '<circle id="A" cx="12" cy="12" r="1.5"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3 M12 18.5v3 M2.5 12h3 M18.5 12h3 M5.3 5.3l2.1 2.1 '
                'M16.6 16.6l2.1 2.1 M5.3 18.7l2.1-2.1 M16.6 7.4l2.1-2.1"/>',
    "reload": '<path d="M19 12a7 7 0 1 1-2.1-5"/><path id="A" d="M19 4v4h-4"/>',
    # the shortcuts
    "q_freeze": '<path d="M12 3v18 M4.2 7.5l15.6 9 M4.2 16.5l15.6-9"/>'
                '<path id="A" d="M10 4.5l2 2 2-2 M10 19.5l2-2 2 2"/>',
    "q_pivot": '<rect x="4" y="4" width="16" height="16" rx="2"/><circle id="A" cx="12" cy="12" r="2.2"/>',
    "q_history": '<circle cx="11" cy="12" r="7.5"/><path d="M11 8v4l3 2"/><path id="A" d="M17 15l4 4 M21 15l-4 4"/>',
    "q_reset": '<path d="M5 12a7 7 0 1 0 2-5"/><path id="A" d="M5 4v4h4"/><circle cx="12" cy="12" r="2"/>',
    "q_snap": '<path d="M6 4v8a6 6 0 0 0 12 0V4 M6 4h4v8a2 2 0 0 0 4 0V4h4"/><path id="A" d="M6 8h4 M14 8h4"/>',
    "q_point": '<path d="M12 4v16 M4 12h16 M6.5 6.5l11 11 M17.5 6.5l-11 11"/><circle id="A" cx="12" cy="12" r="2"/>',
    "q_lock": '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>'
              '<path id="A" d="M12 14v2.5"/>',
    "q_axes": '<path stroke="#e2504a" d="M5 19h14 M16 16l3 3-3 3"/><path stroke="#5fbf4f" d="M5 19V5 M2 8l3-3 3 3"/>'
              '<path stroke="#4c8fe0" d="M5 19l8-8"/>',
    "q_jsize": '<circle cx="12" cy="12" r="4"/><path id="A" d="M3 12h3 M18 12h3 M3 12l2-2 M3 12l2 2 M21 12l-2-2 '
               'M21 12l-2 2"/>',
    "q_pose": '<circle cx="7" cy="6" r="2"/><path d="M7 8v6 M4 11h6 M7 14l-2 5 M7 14l2 5"/>'
              '<circle id="A" cx="17" cy="6" r="2"/><path id="A" d="M17 8v6 M14 11h6 M17 14l-2 5 M17 14l2 5"/>',
    "q_twin": '<circle cx="6" cy="12" r="3"/><circle id="A" cx="18" cy="12" r="3"/>'
              '<path d="M12 4v3 M12 10v4 M12 17v3"/>',
    "q_ikfk": '<path d="M4 18l6-8 8 4"/><circle cx="10" cy="10" r="1.6"/><path id="A" d="M15 4h5 M18 2l2 2-2 2"/>',
    "q_alone": '<rect x="3" y="9" width="7" height="7" rx="1"/><circle cx="17" cy="17" r="2"/><circle cx="17" cy="9" r="2"/>'
               '<path id="A" d="M6.5 6V3 M5 4.5L6.5 3 8 4.5"/>',
    "q_offset": '<rect x="3" y="3" width="18" height="18" rx="2"/><rect id="A" x="8" y="8" width="8" height="8" rx="1.5"/>',
}

LABEL = {"main": "Main", "home": "Home", "build": "Build", "face": "Face", "ribbon": "Ribbon", "joints": "Joints",
         "skin": "Skin", "fixes": "Fixes", "controls_tab": "Controls", "behaviour": "Behaviour", "attrs": "Attributes",
         "channels": "Channels", "spaces": "Spaces", "follow": "Follow", "stick": "Stick to skin",
         "constrain": "Constraints", "connect": "Connections", "nodes": "Nodes", "sdk": "Driven keys",
         "checker": "Checker", "organize": "Organize", "publish": "Publish", "build_rig": "Build rig",
         "select": "Select", "groups": "Groups", "mirror": "Mirror", "rename": "Rename", "pivots": "Pivots",
         "settings": "Settings", "reload": "Reload",
         "q_freeze": "Freeze", "q_pivot": "Center pivot", "q_history": "Delete history", "q_reset": "Reset",
         "q_snap": "Snap", "q_point": "Loc at sel", "q_lock": "Lock/Hide", "q_axes": "Joint axes",
         "q_jsize": "Joint size", "q_pose": "Mirror pose", "q_twin": "Select twin", "q_ikfk": "IK/FK",
         "q_alone": "Move alone", "q_offset": "Offset grp"}


def colour(key):
    """The tile's bar: its area's colour (the shortcuts: light blue)."""
    if key.startswith("q_"):
        return QUICK_COLOUR
    from gus_rigtool.newui import theme, window
    try:
        return theme.colour(window.area_of(key)[0])
    except Exception:
        return theme.colour("settings")


def svg(key, accent):
    body = G.get(key, '<rect x="5" y="5" width="14" height="14" rx="2"/>').replace('id="A"', 'stroke="%s"' % accent)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
            'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (LINE, body))


def image(key, size=32, options=False, ratio=1.0, bar=None):
    """The tile as a QImage of size x size (x ratio for a sharp Retina picture)."""
    accent = bar or colour(key)
    big = int(size * ratio * 4)
    img = QtGui.QImage(big, big, QtGui.QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(0, 0, big, big), big * 0.16, big * 0.16)
    p.fillPath(path, QtGui.QColor(TILE))
    bar_h = max(2.0, round(big * 0.09))
    p.fillRect(QtCore.QRectF(big * 0.08, big - bar_h - big * 0.04, big * 0.84, bar_h), QtGui.QColor(accent))
    m = big * 0.15
    QtSvg.QSvgRenderer(QtCore.QByteArray(svg(key, accent).encode("utf-8"))).render(
        p, QtCore.QRectF(m, m * 0.7, big - 2 * m, big - 2 * m))
    if options:                                   # right-click has its options: the corner triangle
        t = big * 0.17
        x1, y1 = big - big * 0.07, big - bar_h - big * 0.08
        tri = QtGui.QPolygonF([QtCore.QPointF(x1, y1 - t), QtCore.QPointF(x1, y1), QtCore.QPointF(x1 - t, y1)])
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor("#ffffff"))
        p.drawPolygon(tri)
    p.end()
    return img.scaled(int(size * ratio), int(size * ratio), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def pixmap(key, size=32, options=False):
    """For a button: sharp on a Retina screen."""
    px = QtGui.QPixmap.fromImage(image(key, size, options, ratio=2.0))
    px.setDevicePixelRatio(2.0)
    return px


def has_options(key):
    """Right-click gives options: the tool saves options (its section in Settings)."""
    try:
        from gus_rigtool import registry
        return bool(getattr(registry.module(key), "SCHEMA", None))
    except Exception:
        return False
