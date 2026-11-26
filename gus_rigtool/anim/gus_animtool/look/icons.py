"""Line icons (5.7): drawn as SVG in the area's colour - sharp at any size; no emoji (Gus)."""

from .qt import QtCore, QtGui, QtSvg

PATHS = {
    "home": '<path d="M4 11l8-7 8 7 M6 10v10h12V10"/>',
    "build": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/>',
    "skin": '<circle cx="12" cy="12" r="8"/><path d="M8 6v12 M12 4v16 M16 6v12"/>',
    "controls": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    "connect": '<path d="M3 12h18 M7 7l-5 5 5 5 M17 7l5 5-5 5"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
    "toolbox": '<path d="M4 8h16v11H4z M9 8V5h6v3 M4 13h16"/>',
    "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3 M12 18.5v3 M2.5 12h3 M18.5 12h3 M5.3 5.3l2.1 2.1 '
            'M16.6 16.6l2.1 2.1 M5.3 18.7l2.1-2.1 M16.6 7.4l2.1-2.1"/><circle cx="12" cy="12" r="6.5"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "spine": '<circle cx="12" cy="4" r="2"/><rect x="9" y="8" width="6" height="3" rx="1"/>'
             '<rect x="9" y="13" width="6" height="3" rx="1"/><rect x="9" y="18" width="6" height="3" rx="1"/>',
    "arm": '<circle cx="4" cy="6" r="2"/><circle cx="12" cy="10" r="2"/><circle cx="19" cy="17" r="2"/>'
           '<path d="M6 7l4 2 M13.5 11.5l4 4"/>',
    "leg": '<circle cx="10" cy="3" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="10" cy="20" r="2"/>'
           '<path d="M10.4 5l1.2 5 M11.6 14l-1.2 4 M12 20h7"/>',
    "tail": '<path d="M3 18c5 0 6-10 11-10s5 6 8 4"/><circle cx="3" cy="18" r="1.6"/><circle cx="9" cy="12" r="1.6"/>'
            '<circle cx="15" cy="8" r="1.6"/><circle cx="21" cy="11" r="1.6"/>',
    "ears": '<path d="M8 21c-3-5-4-12-2-17 3 3 4 10 4 17 M16 21c0-7 1-14 4-17 2 5 1 12-2 17"/>',
    "head": '<circle cx="12" cy="10" r="7"/><path d="M9 21h6"/>',
    "bulb": '<path d="M9 18h6 M10 21h4 M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
    "pin": '<path d="M15 3l6 6-3 1-4 4 1 4-2 2-4-4-5 5 M9 13L5 9l2-2 4 1 4-4z"/>',
    "brush": '<path d="M18 3l3 3-9 9-3-3z M9 12c-3 0-5 2-5 5 0 1-1 2-2 2 2 2 7 2 8-1 1-2 0-4-1-6z"/>',
    "joint": '<circle cx="12" cy="9" r="4"/><path d="M12 13l3 8"/>',
    "control": '<circle cx="12" cy="12" r="7"/>',
    "mesh": '<path d="M4 8l8-5 8 5v8l-8 5-8-5z M4 8l8 5 8-5 M12 13v8"/>',
    "other": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5"/>',
    "more": '<path d="M6 9l6 6 6-6"/>',
    "open": '<path d="M9 6l6 6-6 6"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14 M12 17.5v.5"/>',
}


def svg(name, color="#e9ebee", width=1.7):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
            'stroke-width="%s" stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (color, width,
                                                                                          PATHS.get(name, "")))


def pixmap(name, size=20, color="#e9ebee", width=1.7, ratio=2.0):
    """The icon drawn at size x size (sharp on a Retina screen)."""
    px = int(size * ratio)
    img = QtGui.QPixmap(px, px)
    img.fill(QtCore.Qt.transparent)
    r = QtSvg.QSvgRenderer(QtCore.QByteArray(svg(name, color, width).encode("utf-8")))
    p = QtGui.QPainter(img)
    r.render(p)
    p.end()
    img.setDevicePixelRatio(ratio)
    return img


def icon(name, size=20, color="#e9ebee", width=1.7):
    return QtGui.QIcon(pixmap(name, size, color, width))
