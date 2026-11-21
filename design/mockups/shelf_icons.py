"""
5.7.9: the Gus_Rigtool shelf icons in the new look (the Gus_Animtool shelf's style: a dark tile, a line drawing, a
coloured bar along the bottom - the bar in the tool's area colour, as in the new window's sidebar).

    QT_QPA_PLATFORM=offscreen python3 design/mockups/shelf_icons.py            # previews in design/screens579/
    QT_QPA_PLATFORM=offscreen python3 design/mockups/shelf_icons.py --install  # also gus_rigtool/icons/gr_*.png
"""
import os
import sys

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "design", "screens579")
ICONS = os.path.join(ROOT, "gus_rigtool", "icons")

TILE, BAR, LINE = "#23262b", 3, "#e9ebee"
AREA = {"home": "#c9ccd1", "build": "#e0893a", "skin": "#d8638c", "controls": "#36b38a", "connect": "#9b74dc",
        "check": "#e3bd3c", "toolbox": "#6f93bd", "settings": "#8a9098", "quick": "#5aa9c9"}

# the drawings: 24 x 24, lines (an 'A' in a path's id = drawn in the area colour)
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

ORDER = [("home", ["home"]), ("build", ["build", "face", "ribbon", "joints"]), ("skin", ["skin", "fixes"]),
         ("controls", ["controls_tab", "behaviour", "attrs", "channels", "spaces", "follow", "stick"]),
         ("connect", ["constrain", "connect", "nodes", "sdk"]),
         ("check", ["checker", "organize", "publish", "build_rig"]),
         ("toolbox", ["select", "groups", "mirror", "rename", "pivots"]), ("settings", ["settings", "main", "reload"])]
QUICK = ["q_freeze", "q_pivot", "q_history", "q_reset", "q_snap", "q_point", "q_lock", "q_axes", "q_jsize", "q_pose",
         "q_twin", "q_ikfk", "q_alone", "q_offset"]
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


def area_of(key):
    if key.startswith("q_"):
        return "quick"
    for area, keys in ORDER:
        if key in keys:
            return area
    return "settings"


def svg(key, accent):
    body = G[key].replace('id="A"', 'stroke="%s"' % accent)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="1.8" '
            'stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (LINE, body))


def tile(key, size=32):
    """One shelf icon: the dark tile, the drawing, the coloured bar."""
    accent = AREA[area_of(key)]
    big = size * 4
    img = QImage(big, big, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, big, big), big * 0.16, big * 0.16)
    p.fillPath(path, QColor(TILE))
    p.fillRect(QRectF(big * 0.08, big - BAR * 4 - big * 0.04, big * 0.84, BAR * 4), QColor(accent))
    r = QSvgRenderer(QByteArray(svg(key, accent).encode()))
    m = big * 0.15
    r.render(p, QRectF(m, m * 0.7, big - 2 * m, big - 2 * m))
    p.end()
    return img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def strip(groups, title, scale=2, path=None):
    """A picture of a shelf: the groups of icons with a gap between them."""
    s = 32 * scale
    n = sum(len(g) for g in groups)
    w = 16 + n * (s + 6) + (len(groups) - 1) * 18
    img = QImage(w, s + 60, QImage.Format_RGB32)
    img.fill(QColor("#444444"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor("#dddddd"))
    p.setFont(QFont("Sans", 11))
    p.drawText(10, 18, title)
    x = 10
    for gi, g in enumerate(groups):
        for key in g:
            p.drawImage(x, 28, tile(key, s))
            x += s + 6
        if gi < len(groups) - 1:
            p.setPen(QPen(QColor("#777777"), 1))
            p.drawLine(x + 6, 32, x + 6, 28 + s - 4)
            x += 18
    p.end()
    if path:
        img.save(path)
    return img


def sheet(path):
    """Every icon with its name (to read them)."""
    keys = [k for _a, ks in ORDER for k in ks] + QUICK
    cols, cw, ch = 8, 132, 104
    img = QImage(cols * cw + 20, ((len(keys) + cols - 1) // cols) * ch + 20, QImage.Format_RGB32)
    img.fill(QColor("#3a3a3a"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setFont(QFont("Sans", 9))
    for i, k in enumerate(keys):
        x, y = 10 + (i % cols) * cw, 10 + (i // cols) * ch
        p.drawImage(x + (cw - 64) // 2, y, tile(k, 64))
        p.setPen(QColor("#dddddd"))
        p.drawText(QRectF(x, y + 68, cw, 30), Qt.AlignHCenter | Qt.AlignTop,
                   LABEL.get(k, k[2:].replace("_", " ").title()))
    p.end()
    img.save(path)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    os.makedirs(OUT, exist_ok=True)
    groups = [ks for _a, ks in ORDER] + [QUICK]
    strip(groups, "Gus_Rigtool shelf - new look (tools in the sidebar's order, a gap between areas, then the "
          "shortcuts)", 2, os.path.join(OUT, "shelf_rigtool_new.png"))
    strip(groups, "", 1, os.path.join(OUT, "shelf_rigtool_new_1x.png"))
    sheet(os.path.join(OUT, "shelf_icons_sheet.png"))
    if "--install" in sys.argv:
        for k in [k for _a, ks in ORDER for k in ks] + QUICK:
            tile(k, 32).save(os.path.join(ICONS, "gr_%s.png" % k))
            tile(k, 64).save(os.path.join(ICONS, "gr_%s@2x.png" % k))
    del app
    print("previews in", OUT)


if __name__ == "__main__":
    main()
