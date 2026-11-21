# -*- coding: utf-8 -*-
"""
Gus Animtool 5.8 — Complete Interactive Maya UI/UX Test v3 (Dummy Actions Only)
===============================================================================
1:1 Maya PySide2 (2024) & PySide6 (2025-2027) parity with the approved v3.1 design.

HOW TO RUN IN MAYA:
  Option A: Drag and drop this .py file straight into Maya's viewport.
  Option B: Open this .py file in Maya Script Editor (Python tab) and click Run.

Everything included (zero placeholders, all 58 tools wired as safe dummy triggers):
  1. Single-Row Maya Shelf ("Gus_Animtool_58"):
       - Exports all 58 real rendered dark tiles (29 vector icons + 29 text badges
         with 3px category bars) to temp PNGs and lines them up in 1 shelf row
         with vertical dividers between the 8 color-coded groups.
  2. Proportional Floating Bar (Row / 2R / Col / Grid):
       - Persistent layout mode across profile switches (ALL 58 defaults to Grid).
       - Auto-shrinks icons down to 22px (*) so NOTHING ever scrolls.
       - Zero dead space when Lbl is OFF (cell_w = px + 4); uniform 2-line cells
         when Lbl is ON (toggling Lbl never shifts icons horizontally).
       - Proportional Inline Tweener (scales cleanly with 24-52px icon size).
       - Full-Information Column Mode (~74px, Zero Color-Only Cues): keeps
         Row|Col|Grd, Lbl, Pie, named profile pills with counts, and a full
         vertical Tweener with % readout, 100%/150% overshoot, and 7 ticks.
       - Ctrl + Mouse Wheel over the bar to resize icons smoothly (24-52px).
       - Right-click any tile -> attached Tool Settings micro-strip.
  3. Hotbox-Style Radial Pie Menu:
       - Native Maya hold-and-release ` (backtick) hotkey (autoSave=False, safe
         cleanup; switchable to F1 or \ in the bar's "=" menu if needed).
       - Dark circular ring backdrop + dashed inner ring painted directly in
         RadialPieMenu.paintEvent (zero Qt child-compositing bugs over Viewport 2.0).
       - Top 1-5 profile tabs, 8-compass ring with dark label pills, bottom
         overflow strip, and right-click Tool Settings micro-strip.
  4. High-Contrast 242px Narrow Dock (workspaceControl beside Channel Box):
       - Sunken #16191e background, #242933 cards, #454f60 borders, #343c4a buttons.
       - Fixed header (BLK | POL | SPC | ? | CB) + 6-icon Pick & View strip.
       - Scrollable body with 3x2 Pinned Grid, full-width Tweener, and ALL 58 tools
         across 8 collapsible drawers with 10%-tinted headers & 75/25 split buttons.
       - Fixed 22px bottom telemetry bar + auto-collapse to 88px Micro-Rail (<135px).
"""

from __future__ import print_function
import math
import os
import sys
import tempfile
import types

try:
    import maya.cmds as cmds
    import maya.mel as mel
    import maya.OpenMayaUI as omui
    IN_MAYA = True
except ImportError:
    cmds = None
    mel = None
    omui = None
    IN_MAYA = False

# Cross-version PySide6 / PySide2 shim
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    IS_QT6 = True
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
    IS_QT6 = False


# ---------------------------------------------------------------------------
# Cross-Version Qt Helpers (PySide2 & PySide6)
# ---------------------------------------------------------------------------
def _evt_global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()


def _maya_main_window():
    if not IN_MAYA:
        return None
    try:
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            return wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        pass
    return None


def _screen_geometry(widget=None):
    app = QtWidgets.QApplication.instance()
    if not app:
        return QtCore.QRect(0, 0, 1920, 1080)
    screen = None
    if widget is not None and hasattr(widget, "screen"):
        screen = widget.screen()
    if screen is None and hasattr(app, "screenAt"):
        screen = app.screenAt(QtGui.QCursor.pos())
    if screen is None:
        screen = app.primaryScreen()
    return screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1920, 1080)


def _blend_hex(fg_hex, bg_hex, alpha=0.12):
    """Blends fg_hex over bg_hex at alpha (0..1) for crisp 10%-tinted QSS headers."""
    fg = QtGui.QColor(fg_hex)
    bg = QtGui.QColor(bg_hex)
    r = int(round(fg.red() * alpha + bg.red() * (1.0 - alpha)))
    g = int(round(fg.green() * alpha + bg.green() * (1.0 - alpha)))
    b = int(round(fg.blue() * alpha + bg.blue() * (1.0 - alpha)))
    return "#%02x%02x%02x" % (r, g, b)


def _toast(text, accent="#3898c8"):
    print("[Gus Animtool 5.8 UI Test v3] " + text)
    if IN_MAYA:
        try:
            cmds.inViewMessage(
                amg='<span style="color:%s;font-weight:bold;">Animtool 5.8</span> &nbsp; %s' % (accent, text),
                pos="botCenter",
                fade=True,
                fadeStayTime=1200,
                fadeOutTime=300,
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# High-Contrast Balanced Dark + Okabe-Ito Color-Blind Safe Tokens
# ---------------------------------------------------------------------------
THEMES = {
    "default": {
        "bg": "#16191e",
        "panel": "#22262d",
        "card": "#242933",
        "btn": "#343c4a",
        "btn_hover": "#404a5b",
        "border": "#454f60",
        "border_subtle": "#333a47",
        "text": "#f1f5f9",
        "muted": "#9aa5b5",
        "active": "#3898c8",
        "cat": {
            "open": "#4fb3d9",
            "pose": "#d66b8c",
            "keys": "#d9a13b",
            "timing": "#38b2ac",
            "curves": "#e07a3c",
            "limbs": "#3ea87c",
            "space": "#907ad6",
            "view": "#cf6ba9",
        },
    },
    "okabe": {
        "bg": "#16191e",
        "panel": "#22262d",
        "card": "#242933",
        "btn": "#343c4a",
        "btn_hover": "#404a5b",
        "border": "#454f60",
        "border_subtle": "#333a47",
        "text": "#f1f5f9",
        "muted": "#9aa5b5",
        "active": "#56b4e9",
        "cat": {
            "open": "#56b4e9",
            "pose": "#cc79a7",
            "keys": "#e69f00",
            "timing": "#0072b2",
            "curves": "#d55e00",
            "limbs": "#009e73",
            "space": "#f0e442",
            "view": "#cc79a7",
        },
    },
}

# ---------------------------------------------------------------------------
# All 58 Approved Tools (29 Graphic Icons + 29 Bold Typographic Badges)
# ---------------------------------------------------------------------------
ACTIONS = [
    # Launchers (5)
    ("main", "Gus Animtool", "open", "text", "GA", False, ""),
    ("picker", "Picker", "open", "icon", "picker", False, ""),
    ("poses", "Poses", "open", "icon", "poses", False, ""),
    ("clips", "Clips", "open", "icon", "clips", False, ""),
    ("bar", "Floating Bar", "open", "icon", "bar", False, ""),
    # 1 - Pose & Mirror (6)
    ("tween_prev", "Tween <", "pose", "icon", "tween_prev", True, "Alt+Shift+,"),
    ("tween_next", "Tween >", "pose", "icon", "tween_next", True, "Alt+Shift+."),
    ("mirror", "Mirror Pose", "pose", "icon", "mirror", True, ""),
    ("flip", "Flip Pose", "pose", "icon", "flip", False, ""),
    ("reset", "Reset Pose", "pose", "icon", "reset", True, ""),
    ("twin", "Select Twin", "pose", "text", "TWIN", False, ""),
    # 2 - Keys & Tangents (9)
    ("key", "Key Keep", "keys", "icon", "key", True, ""),
    ("nudge_left", "Nudge <", "keys", "icon", "nudge_left", True, "Alt+,"),
    ("nudge_right", "Nudge >", "keys", "icon", "nudge_right", True, "Alt+."),
    ("tan_auto", "Auto Tangent", "keys", "icon", "tan_auto", False, ""),
    ("tan_spline", "Spline Tangent", "keys", "icon", "tan_spline", False, ""),
    ("tan_linear", "Linear Tangent", "keys", "icon", "tan_linear", False, ""),
    ("tan_flat", "Flat Tangent", "keys", "icon", "tan_flat", False, ""),
    ("tan_step", "Stepped Tangent", "keys", "icon", "tan_step", False, ""),
    ("blocking", "Blocking / Spline", "keys", "text", "BLK", True, ""),
    # 3 - Timing, Offset & Cycles (16)
    ("copy_keys", "Copy Keys", "timing", "icon", "copy", True, ""),
    ("paste_keys", "Paste Keys", "timing", "icon", "paste", True, ""),
    ("inbetween_add", "Add Inbetween", "timing", "text", "+INB", True, "Alt+]"),
    ("inbetween_remove", "Remove Inbetween", "timing", "text", "-INB", True, "Alt+["),
    ("offset_minus", "Offset -", "timing", "text", "OFF-", True, ""),
    ("offset_plus", "Offset +", "timing", "text", "OFF+", True, ""),
    ("offset_back", "Back Original", "timing", "text", "ORIG", True, ""),
    ("mirror_cycle", "Mirror Cycle", "timing", "text", "MCYC", True, ""),
    ("cycle_continue", "Continue Cycle", "timing", "text", "CYC+", True, ""),
    ("cycle_place", "Cycle In Place", "timing", "text", "INPL", False, ""),
    ("cycle_forward", "Cycle Forward", "timing", "text", "FWD", False, ""),
    ("bake_keys", "Bake Keys", "timing", "text", "BAKE", True, ""),
    ("reduce_keys", "Reduce Keys", "timing", "text", "RED", True, ""),
    ("stretch", "Slower / Faster", "timing", "text", "STR", True, ""),
    ("reverse", "Reverse Keys", "timing", "text", "REV", False, ""),
    ("time_scale", "Time Scale", "timing", "text", "x1.2", True, ""),
    # 4 - Graph Curves (7)
    ("pull", "Pull Keys", "curves", "icon", "pull", False, "Alt+-"),
    ("push", "Push Keys", "curves", "icon", "push", False, "Alt+="),
    ("negate", "Negate Keys", "curves", "text", "NEG", False, "Alt+Shift+-"),
    ("smooth", "Smooth Curve", "curves", "icon", "smooth", True, ""),
    ("noise", "Add Noise", "curves", "icon", "noise", True, ""),
    ("redundant", "Clean Redundant", "curves", "text", "CLN", False, ""),
    ("euler", "Euler Filter", "curves", "text", "EUL", False, ""),
    # 5 - Limbs (2)
    ("ikfk", "IK / FK Switch", "limbs", "text", "IK/FK", True, ""),
    ("overlap", "Overlap Chain", "limbs", "text", "OVL", True, ""),
    # 6 - Spaces & Props (6)
    ("temp_world", "World Space", "space", "icon", "world", False, ""),
    ("temp_pivot", "Temp Pivot", "space", "icon", "pivot", False, ""),
    ("bake_back", "Bake Back", "space", "text", "BK<-", False, ""),
    ("attach", "Attach Prop", "space", "icon", "attach", True, ""),
    ("release", "Release Prop", "space", "icon", "release", True, ""),
    ("attach_window", "Attach Window", "space", "text", "ATT=", False, ""),
    # 7 - Pick & View (7)
    ("arcs", "Motion Arcs", "view", "icon", "arcs", True, ""),
    ("arcs_panel", "Arcs Panel", "view", "text", "ARC=", False, ""),
    ("hide_ctrls", "Hide Controls", "view", "icon", "hide", False, ""),
    ("isolate", "Isolate Sel", "view", "icon", "isolate", False, ""),
    ("hider", "Body Parts", "view", "text", "PART", True, ""),
    ("ghosts", "Ghosts / Onion", "view", "icon", "ghosts", True, ""),
    ("playblast", "Playblast", "view", "icon", "playblast", True, ""),
]

ACTION_MAP = {a[0]: {
    "key": a[0], "label": a[1], "cat": a[2], "kind": a[3],
    "glyph": a[4], "has_settings": a[5], "hotkey": a[6]
} for a in ACTIONS}

ALL_KEYS = [a[0] for a in ACTIONS]

# All 8 Dock Drawers (ordered for animator workflow; covers 58/58 actions)
DOCK_CATEGORIES = [
    ("pose", "● 1 POSE"),
    ("keys", "■ 2 KEYS & TANGENTS"),
    ("limbs", "◆ 3 LIMBS"),
    ("space", "▢ 4 SPACES & PROPS"),
    ("timing", "▲ 5 TIMING & CYCLES"),
    ("curves", "〰 6 GRAPH CURVES"),
    ("view", "◉ 7 PICK & VIEW"),
    ("open", "⊞ 8 LAUNCHERS"),
]

SPLIT_CAPS = {
    "mirror": "R->L",
    "reset": "All",
    "key": "All",
    "blocking": "Spline",
    "inbetween_add": "-Inb",
    "offset_plus": "Casc",
    "bake_keys": "1/2/4",
    "reduce_keys": "Tol",
    "ikfk": "Rng",
    "overlap": "Cyc",
    "attach": "Win",
    "release": "Bake",
    "arcs": "Panel",
    "playblast": "50%",
}

TOOL_SETTINGS = {
    "inbetween_add": ("Inbetween", [("Step", ["1", "2", "4"], 0), ("Scope", ["Sel", "Char", "All"], 1)]),
    "inbetween_remove": ("Inbetween", [("Step", ["1", "2", "4"], 0), ("Scope", ["Sel", "Char", "All"], 1)]),
    "offset_minus": ("Offset", [("Step", ["1", "2", "4"], 0), ("Mode", ["Same", "Cascade"], 0)]),
    "offset_plus": ("Offset", [("Step", ["1", "2", "4"], 0), ("Mode", ["Same", "Cascade"], 1)]),
    "offset_back": ("Offset Reset", [("Action", ["Reset Sel", "Reset All", "Keep as Orig"], 0)]),
    "mirror": ("Mirror Pose", [("Direction", ["L -> R", "R -> L"], 0), ("Range", ["This Frame", "Time Range"], 0)]),
    "reset": ("Reset Pose", [("Scope", ["Selection", "Whole Character"], 0)]),
    "key": ("Key", [("Mode", ["Keep Curve", "Key All Attrs"], 0)]),
    "blocking": ("Blocking / Spline", [("Mode", ["Stepped", "Spline"], 0), ("Scope", ["Char", "Sel"], 0)]),
    "nudge_left": ("Nudge", [("Step", ["1", "2", "4"], 0)]),
    "nudge_right": ("Nudge", [("Step", ["1", "2", "4"], 0)]),
    "tween_prev": ("Tween", [("Overshoot", ["100%", "150%"], 0), ("Step", ["25%", "33%", "50%"], 1)]),
    "tween_next": ("Tween", [("Overshoot", ["100%", "150%"], 0), ("Step", ["25%", "33%", "50%"], 1)]),
    "ikfk": ("IK / FK Switch", [("Range", ["This Frame", "Over Range"], 0), ("Key", ["Key on Switch", "No Key"], 0)]),
    "overlap": ("Overlap", [("Feel", ["Soft", "Normal", "Stiff"], 1), ("Loop", ["Off", "Cycle"], 0)]),
    "attach": ("Attach", [("Action", ["Attach", "Hand-Over (4f)", "Both Hands", "Attach Win"], 0)]),
    "release": ("Release", [("Action", ["Release", "Bake Sel", "Bake All", "Remove"], 0)]),
    "arcs": ("Motion Arcs", [("Range", ["Shot", "Around 24f"], 0), ("Handles", ["Off", "On"], 0), ("Action", ["Clear", "Arcs Panel"], 0)]),
    "bake_keys": ("Bake Keys", [("Every", ["1f", "2f", "4f"], 0)]),
    "reduce_keys": ("Reduce Keys", [("Tolerance", ["0.5%", "1%", "3%"], 1)]),
    "stretch": ("Slower / Faster", [("Scale", ["50%", "75%", "125%", "150%", "200%"], 3)]),
    "time_scale": ("Time Scale", [("Factor", ["x0.5", "x0.75", "x1.25", "x1.5", "x2.0"], 2)]),
    "hider": ("Body Parts", [("Target", ["Controls", "Geo", "Both"], 0), ("Part", ["Show All", "Head", "Arms", "Legs", "Tail"], 0)]),
    "playblast": ("Playblast", [("Size", ["50%", "100%"], 1)]),
    "smooth": ("Smooth", [("Strength", ["Light", "Medium", "Heavy"], 1)]),
    "noise": ("Noise", [("Amount", ["0.02", "0.05", "0.15"], 1)]),
    "copy_keys": ("Copy Keys", [("Scope", ["Frame/Range", "Whole Anim"], 0)]),
    "paste_keys": ("Paste Keys", [("Mode", ["Replace", "Merge", "Whole Anim"], 0)]),
    "mirror_cycle": ("Mirror Cycle", [("Loop", ["Loop Curves", "No Loop"], 0)]),
    "cycle_continue": ("Continue Cycle", [("Repeat", ["+1", "+3", "+7", "Curves Only"], 1)]),
    "ghosts": ("Ghosts", [("Action", ["Make Ghosts", "Clear Ghosts"], 0)]),
}

DEFAULT_PROFILES = [
    {
        "id": "blocking", "short": "BLK", "name": "Blocking", "cat": "keys",
        "keys": ["key", "mirror", "tween_prev", "tween_next", "inbetween_add", "inbetween_remove",
                 "tan_step", "ikfk", "flip", "attach", "reset"],
    },
    {
        "id": "polish", "short": "POL", "name": "Polish", "cat": "pose",
        "keys": ["tween_prev", "tween_next", "nudge_left", "nudge_right", "tan_auto", "tan_spline",
                 "pull", "push", "smooth", "euler", "arcs", "overlap"],
    },
    {
        "id": "spaces", "short": "SPC", "name": "Spaces & Props", "cat": "space",
        "keys": ["attach", "release", "attach_window", "temp_world", "temp_pivot", "bake_back", "ikfk", "key"],
    },
    {
        "id": "rigcheck", "short": "RIG", "name": "Rig Check", "cat": "limbs",
        "keys": ["picker", "poses", "mirror", "flip", "reset", "twin", "ikfk", "hide_ctrls", "isolate", "hider"],
    },
    {
        "id": "all58", "short": "ALL 58", "name": "All Tools (58)", "cat": "open",
        "keys": list(ALL_KEYS),
    },
]


# ---------------------------------------------------------------------------
# Procedural Vector Icon + Text Badge Renderer (Used by Bar, Pie, Dock & Shelf!)
# ---------------------------------------------------------------------------
def render_tile_pixmap(action_key, size, theme_name="default", bake_card_bg=False):
    """
    Renders a crisp vector icon or bold typographic badge with a 3px category bar
    and 5px RMB triangle. Set bake_card_bg=True when exporting PNGs for Maya's Shelf.
    """
    act = ACTION_MAP[action_key]
    theme = THEMES[theme_name]
    accent = QtGui.QColor(theme["cat"].get(act["cat"], "#3898c8"))

    dpr = 1 if bake_card_bg else 2
    w = max(20, int(size))
    pm = QtGui.QPixmap(w * dpr, w * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(QtCore.Qt.GlobalColor.transparent if IS_QT6 else QtCore.Qt.transparent)

    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing if IS_QT6 else QtGui.QPainter.Antialiasing)

    if bake_card_bg:
        p.setPen(QtGui.QPen(QtGui.QColor(theme["border"]), max(1.0, w * 0.03)))
        p.setBrush(QtGui.QColor(theme["btn"]))
        r = max(4.0, w * 0.16)
        p.drawRoundedRect(QtCore.QRectF(1, 1, w - 2, w - 2), r, r)

    bar_h = max(2, int(round(w * 0.09)))
    p.setPen(QtCore.Qt.PenStyle.NoPen if IS_QT6 else QtCore.Qt.NoPen)
    p.setBrush(accent)
    p.drawRoundedRect(QtCore.QRectF(3, w - bar_h - 2, w - 6, bar_h), 1.5, 1.5)

    if act["has_settings"]:
        tri_sz = max(5.0, w * 0.16)
        tri = QtGui.QPolygonF([
            QtCore.QPointF(w - 3, w - bar_h - 3),
            QtCore.QPointF(w - 3 - tri_sz, w - bar_h - 3),
            QtCore.QPointF(w - 3, w - bar_h - 3 - tri_sz),
        ])
        p.setBrush(QtGui.QColor("#cbd5e1"))
        p.drawPolygon(tri)

    fg = QtGui.QColor(theme["text"])
    area = QtCore.QRectF(3, 3, w - 6, w - bar_h - 6)

    if act["kind"] == "text":
        text = act["glyph"]
        font = QtGui.QFont("Arial", 9)
        font.setBold(True)
        base_px = max(7, int(w * (0.31 if len(text) <= 3 else 0.25 if len(text) == 4 else 0.21)))
        font.setPixelSize(base_px)
        p.setFont(font)
        p.setPen(fg)
        p.drawText(area, QtCore.Qt.AlignmentFlag.AlignCenter if IS_QT6 else QtCore.Qt.AlignCenter, text)
    else:
        p.save()
        side = min(area.width(), area.height())
        ox = area.center().x() - side / 2.0
        oy = area.center().y() - side / 2.0
        p.translate(ox, oy)
        p.scale(side / 24.0, side / 24.0)
        pen = QtGui.QPen(fg, 1.8)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap if IS_QT6 else QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin if IS_QT6 else QtCore.Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush if IS_QT6 else QtCore.Qt.NoBrush)
        _draw_glyph(p, act["glyph"], fg, accent)
        p.restore()

    p.end()
    return pm


def _draw_glyph(p, g, fg, accent):
    if g == "picker":
        p.drawEllipse(QtCore.QPointF(12, 6), 2.5, 2.5)
        p.drawRoundedRect(QtCore.QRectF(9, 10, 6, 7), 1.2, 1.2)
        p.drawLine(4, 11, 8, 12); p.drawLine(20, 11, 16, 12)
        p.drawLine(10, 17, 9, 22); p.drawLine(14, 17, 15, 22)
    elif g == "poses":
        for x in (4, 13):
            for y in (4, 13):
                p.drawRoundedRect(QtCore.QRectF(x, y, 7, 7), 1.2, 1.2)
    elif g == "clips":
        p.drawRoundedRect(QtCore.QRectF(3, 5, 18, 14), 2, 2)
        tri = QtGui.QPolygonF([QtCore.QPointF(10, 9), QtCore.QPointF(16, 12), QtCore.QPointF(10, 15)])
        p.setBrush(fg); p.drawPolygon(tri)
    elif g == "bar":
        p.drawRoundedRect(QtCore.QRectF(2, 8, 20, 8), 2.5, 2.5)
        p.setBrush(accent)
        for x in (5, 10.5, 16):
            p.drawRect(QtCore.QRectF(x, 10.5, 3, 3))
    elif g == "tween_prev":
        p.drawLine(4, 12, 20, 12)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(9, 12), 3, 3)
        p.drawLine(7, 7, 4, 12); p.drawLine(7, 17, 4, 12)
    elif g == "tween_next":
        p.drawLine(4, 12, 20, 12)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(15, 12), 3, 3)
        p.drawLine(17, 7, 20, 12); p.drawLine(17, 17, 20, 12)
    elif g == "mirror":
        dash = QtGui.QPen(accent, 1.5, QtCore.Qt.PenStyle.DashLine if IS_QT6 else QtCore.Qt.DashLine)
        p.setPen(dash); p.drawLine(12, 3, 12, 21)
        p.setPen(QtGui.QPen(fg, 1.8))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(9, 6), QtCore.QPointF(4, 18), QtCore.QPointF(9, 18)]))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(15, 6), QtCore.QPointF(20, 18), QtCore.QPointF(15, 18)]))
    elif g == "flip":
        p.drawLine(5, 8, 19, 8); p.drawLine(15, 5, 19, 8); p.drawLine(15, 11, 19, 8)
        p.drawLine(19, 16, 5, 16); p.drawLine(9, 13, 5, 16); p.drawLine(9, 19, 5, 16)
    elif g == "reset":
        p.drawArc(QtCore.QRectF(5, 5, 14, 14), 40 * 16, 290 * 16)
        p.drawLine(17, 5, 19, 9); p.drawLine(15, 9, 19, 9)
    elif g == "key":
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(12, 4), QtCore.QPointF(20, 12), QtCore.QPointF(12, 20), QtCore.QPointF(4, 12)
        ]))
    elif g == "nudge_left":
        p.drawLine(10, 6, 4, 6); p.drawLine(7, 3, 4, 6); p.drawLine(7, 9, 4, 6)
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(14, 10), QtCore.QPointF(19, 15), QtCore.QPointF(14, 20), QtCore.QPointF(9, 15)
        ]))
    elif g == "nudge_right":
        p.drawLine(14, 6, 20, 6); p.drawLine(17, 3, 20, 6); p.drawLine(17, 9, 20, 6)
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([
            QtCore.QPointF(10, 10), QtCore.QPointF(15, 15), QtCore.QPointF(10, 20), QtCore.QPointF(5, 15)
        ]))
    elif g == "tan_auto":
        path = QtGui.QPainterPath(QtCore.QPointF(3, 18))
        path.cubicTo(10, 18, 14, 6, 21, 6)
        p.drawPath(path)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(12, 12), 2.2, 2.2)
    elif g == "tan_spline":
        path = QtGui.QPainterPath(QtCore.QPointF(3, 18))
        path.quadTo(12, 2, 21, 18)
        p.drawPath(path)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(12, 10), 2.2, 2.2)
    elif g == "tan_linear":
        p.drawLine(3, 18, 12, 6); p.drawLine(12, 6, 21, 18)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(12, 6), 2.2, 2.2)
    elif g == "tan_flat":
        p.drawLine(3, 18, 8, 9); p.drawLine(8, 9, 16, 9); p.drawLine(16, 9, 21, 18)
        p.setPen(QtGui.QPen(accent, 1.8)); p.drawLine(6, 9, 18, 9)
    elif g == "tan_step":
        p.drawLine(3, 18, 11, 18); p.drawLine(11, 18, 11, 7); p.drawLine(11, 7, 21, 7)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(11, 7), 2, 2)
    elif g == "copy":
        p.drawRoundedRect(QtCore.QRectF(4, 4, 11, 13), 1.5, 1.5)
        p.drawRoundedRect(QtCore.QRectF(9, 8, 11, 13), 1.5, 1.5)
    elif g == "paste":
        p.drawRoundedRect(QtCore.QRectF(5, 6, 14, 15), 1.5, 1.5)
        p.drawRoundedRect(QtCore.QRectF(9, 3, 6, 4), 1, 1)
    elif g == "pull":
        p.drawLine(3, 12, 21, 12)
        p.setPen(QtGui.QPen(accent, 2.0))
        p.drawLine(12, 3, 12, 9); p.drawLine(9, 6, 12, 9); p.drawLine(15, 6, 12, 9)
        p.drawLine(12, 21, 12, 15); p.drawLine(9, 18, 12, 15); p.drawLine(15, 18, 12, 15)
    elif g == "push":
        p.drawLine(3, 12, 21, 12)
        p.setPen(QtGui.QPen(accent, 2.0))
        p.drawLine(12, 9, 12, 3); p.drawLine(9, 6, 12, 3); p.drawLine(15, 6, 12, 3)
        p.drawLine(12, 15, 12, 21); p.drawLine(9, 18, 12, 21); p.drawLine(15, 18, 12, 21)
    elif g == "smooth":
        path = QtGui.QPainterPath(QtCore.QPointF(3, 12))
        path.cubicTo(7, 3, 11, 21, 15, 12)
        path.quadTo(18, 6, 21, 12)
        p.drawPath(path)
    elif g == "noise":
        pts = [(3, 12), (6, 6), (9, 17), (12, 5), (15, 18), (18, 8), (21, 12)]
        for i in range(len(pts) - 1):
            p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    elif g == "world":
        p.drawEllipse(QtCore.QPointF(12, 12), 8, 8)
        p.drawEllipse(QtCore.QPointF(12, 12), 4, 8)
        p.drawLine(4, 12, 20, 12)
    elif g == "pivot":
        p.drawLine(12, 4, 12, 20); p.drawLine(4, 12, 20, 12)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(12, 12), 2.5, 2.5)
    elif g == "attach":
        p.drawRoundedRect(QtCore.QRectF(3, 8, 10, 8), 4, 4)
        p.setPen(QtGui.QPen(accent, 1.9))
        p.drawRoundedRect(QtCore.QRectF(11, 8, 10, 8), 4, 4)
    elif g == "release":
        p.drawRoundedRect(QtCore.QRectF(2, 8, 8, 8), 3.5, 3.5)
        p.drawRoundedRect(QtCore.QRectF(14, 8, 8, 8), 3.5, 3.5)
        p.setPen(QtGui.QPen(accent, 1.8))
        p.drawLine(12, 4, 12, 7); p.drawLine(12, 17, 12, 20)
    elif g == "arcs":
        path = QtGui.QPainterPath(QtCore.QPointF(4, 18))
        path.quadTo(12, 2, 20, 18)
        p.drawPath(path)
        p.setBrush(accent)
        for x, y in ((4, 18), (8, 11), (12, 8), (16, 11), (20, 18)):
            p.drawEllipse(QtCore.QPointF(x, y), 1.8, 1.8)
    elif g == "hide":
        p.drawArc(QtCore.QRectF(3, 6, 18, 12), 0, 180 * 16)
        p.drawArc(QtCore.QRectF(3, 6, 18, 12), 180 * 16, 180 * 16)
        p.drawEllipse(QtCore.QPointF(12, 12), 2.5, 2.5)
        p.setPen(QtGui.QPen(accent, 2.0)); p.drawLine(4, 19, 20, 5)
    elif g == "isolate":
        p.drawLine(4, 8, 4, 4); p.drawLine(4, 4, 8, 4)
        p.drawLine(20, 8, 20, 4); p.drawLine(20, 4, 16, 4)
        p.drawLine(4, 16, 4, 20); p.drawLine(4, 20, 8, 20)
        p.drawLine(20, 16, 20, 20); p.drawLine(20, 20, 16, 20)
        p.setBrush(accent); p.drawEllipse(QtCore.QPointF(12, 12), 3, 3)
    elif g == "ghosts":
        for i, x in enumerate((6, 12, 18)):
            c = accent if i == 1 else fg
            p.setPen(QtGui.QPen(c, 1.6))
            p.drawEllipse(QtCore.QPointF(x, 8), 2, 2)
            p.drawLine(x, 10, x, 19)
    elif g == "playblast":
        p.drawRoundedRect(QtCore.QRectF(3, 5, 18, 14), 2, 2)
        p.setBrush(accent)
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(10, 9), QtCore.QPointF(16, 12), QtCore.QPointF(10, 15)]))


# ---------------------------------------------------------------------------
# Shared State Controller
# ---------------------------------------------------------------------------
class MockState(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self):
        super(MockState, self).__init__()
        self.profiles = [dict(p, keys=list(p["keys"])) for p in DEFAULT_PROFILES]
        self.active_profile_idx = 0
        self.layout_mode = "row"        # "row" | "2r" | "col" | "grid" (persists across profiles)
        self.show_labels = False
        self.target_icon_size = 34      # 24..52 px (auto-shrinks down to 22px if needed)
        self.theme_name = "default"     # "default" | "okabe"
        self.pie_hotkey = "grave"       # "grave" (`) | "F1" | "\\"
        self.tween_val = 0
        self.tween_max = 100
        self.settings_values = {}

    def profile_color(self, prof=None):
        prof = prof or self.active_profile()
        return THEMES[self.theme_name]["cat"].get(prof["cat"], THEMES[self.theme_name]["active"])

    def active_profile(self):
        return self.profiles[self.active_profile_idx]

    def set_profile(self, idx):
        if 0 <= idx < len(self.profiles):
            self.active_profile_idx = idx
            if self.profiles[idx]["id"] == "all58" and self.layout_mode in ("row", "col"):
                self.layout_mode = "grid"
            self.changed.emit()

    def set_layout_mode(self, mode):
        self.layout_mode = mode
        self.changed.emit()

    def set_labels(self, on):
        self.show_labels = bool(on)
        self.changed.emit()

    def set_icon_size(self, px):
        self.target_icon_size = max(24, min(52, int(px)))
        self.changed.emit()

    def set_theme(self, name):
        self.theme_name = name
        self.changed.emit()

    def toggle_tool_in_active(self, key, on):
        keys = self.active_profile()["keys"]
        if on and key not in keys:
            keys.append(key)
        elif not on and key in keys:
            keys.remove(key)
        self.changed.emit()

    def add_profile(self, name):
        short = (name[:4].upper() if name else "NEW")
        self.profiles.append({
            "id": "custom_%d" % len(self.profiles),
            "short": short,
            "name": name or "Custom",
            "cat": "open",
            "keys": list(self.active_profile()["keys"]),
        })
        self.active_profile_idx = len(self.profiles) - 1
        self.changed.emit()


# ---------------------------------------------------------------------------
# Proportional Fixed-Cell Tool Tile (Zero Dead Space when Lbl=OFF)
# ---------------------------------------------------------------------------
class ToolTile(QtWidgets.QWidget):
    leftClicked = QtCore.Signal(str)
    rightClicked = QtCore.Signal(str)

    def __init__(self, action_key, icon_px, show_label, cell_w, theme_name="default",
                 label_pill=False, parent=None):
        super(ToolTile, self).__init__(parent)
        self.action_key = action_key
        act = ACTION_MAP[action_key]
        theme = THEMES[theme_name]
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus
        self.setFocusPolicy(no_focus)

        self.setFixedWidth(cell_w)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(2)
        align_h = QtCore.Qt.AlignmentFlag.AlignHCenter if IS_QT6 else QtCore.Qt.AlignHCenter

        self.btn = QtWidgets.QToolButton()
        self.btn.setFocusPolicy(no_focus)
        self.btn.setFixedSize(icon_px, icon_px)
        self.btn.setIcon(QtGui.QIcon(render_tile_pixmap(action_key, icon_px, theme_name)))
        self.btn.setIconSize(QtCore.QSize(icon_px, icon_px))
        tip = "<b>%s</b>" % act["label"]
        if act["hotkey"]:
            tip += " (%s)" % act["hotkey"]
        if act["has_settings"]:
            tip += "<br><i>Right-click for tool settings</i>"
        self.btn.setToolTip(tip)
        self.btn.setStyleSheet(
            "QToolButton{background:%s;border:1px solid %s;border-radius:6px;padding:0px;}"
            "QToolButton:hover{background:%s;border-color:%s;}"
            % (theme["btn"], theme["border"], theme["btn_hover"], theme["active"])
        )
        self.btn.clicked.connect(lambda: self.leftClicked.emit(self.action_key))
        self.btn.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu if IS_QT6 else QtCore.Qt.CustomContextMenu
        )
        self.btn.customContextMenuRequested.connect(lambda _p: self.rightClicked.emit(self.action_key))
        lay.addWidget(self.btn, 0, align_h)

        if show_label:
            lbl = QtWidgets.QLabel(act["label"])
            lbl.setWordWrap(True)
            lbl.setAlignment(
                (QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if IS_QT6 else (QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
            )
            lbl.setFixedWidth(max(44, cell_w - 2))
            lbl.setFixedHeight(22)
            if label_pill:
                lbl.setStyleSheet(
                    "color:%s;font-size:9px;background:rgba(22,25,30,238);"
                    "border:1px solid %s;border-radius:4px;padding:1px 3px;"
                    % (theme["text"], theme["border"])
                )
            else:
                lbl.setStyleSheet("color:%s;font-size:9px;background:transparent;" % theme["muted"])
            lay.addWidget(lbl, 0, align_h)


# ---------------------------------------------------------------------------
# Proportional Inline Tweener (Horizontal scales with px; Full-Info Vertical in Col)
# ---------------------------------------------------------------------------
class InlineTweener(QtWidgets.QFrame):
    def __init__(self, state, icon_px=34, vertical=False, full_width=False, theme_name="default", parent=None):
        super(InlineTweener, self).__init__(parent)
        self.state = state
        theme = THEMES[theme_name]
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus
        self.setFocusPolicy(no_focus)
        self.setStyleSheet(
            "QFrame{background:%s;border:1px solid %s;border-bottom:2px solid %s;border-radius:6px;}"
            % (theme["bg"], theme["border"], theme["cat"]["pose"])
        )

        if vertical:
            # Full-Information Vertical Tweener: % readout + 100%/150% overshoot + 7 clickable ticks + slider
            self.setFixedSize(64, 128)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(4, 3, 4, 4)
            lay.setSpacing(2)

            top = QtWidgets.QHBoxLayout()
            top.setSpacing(2)
            self.val_lbl = QtWidgets.QLabel("%+d%%" % state.tween_val)
            self.val_lbl.setStyleSheet("color:%s;font-size:9px;font-weight:bold;border:none;" % theme["cat"]["pose"])
            self.ovr_btn = QtWidgets.QPushButton("%d%%" % state.tween_max)
            self.ovr_btn.setFocusPolicy(no_focus)
            self.ovr_btn.setFixedSize(28, 14)
            self.ovr_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-size:8px;}"
                % (theme["btn"], theme["text"], theme["border"])
            )
            self.ovr_btn.clicked.connect(self._toggle_overshoot)
            top.addWidget(self.val_lbl)
            top.addStretch(1)
            top.addWidget(self.ovr_btn)
            lay.addLayout(top)

            body = QtWidgets.QHBoxLayout()
            body.setSpacing(3)

            ticks_col = QtWidgets.QVBoxLayout()
            ticks_col.setSpacing(1)
            for v in (75, 50, 25, 0, -25, -50, -75):
                b = QtWidgets.QPushButton("%+d" % v if v != 0 else "0")
                b.setFocusPolicy(no_focus)
                b.setFixedSize(22, 12)
                b.setToolTip("Tween %+d%%" % v)
                b.setStyleSheet(
                    "QPushButton{background:%s;color:%s;border:none;border-radius:2px;font-size:7px;font-weight:bold;padding:0;}"
                    "QPushButton:hover{background:%s;color:#111;}"
                    % (theme["btn_hover"] if v == 0 else theme["btn"], theme["text"] if v == 0 else theme["muted"], theme["cat"]["pose"])
                )
                b.clicked.connect(lambda _c=False, val=v: self.sld.setValue(val))
                ticks_col.addWidget(b)
            body.addLayout(ticks_col)

            orient = QtCore.Qt.Orientation.Vertical if IS_QT6 else QtCore.Qt.Vertical
            self.sld = QtWidgets.QSlider(orient)
            self.sld.setFocusPolicy(no_focus)
            self.sld.setRange(-state.tween_max, state.tween_max)
            self.sld.setValue(state.tween_val)
            self.sld.valueChanged.connect(self._on_change)
            body.addWidget(self.sld, 1)
            lay.addLayout(body, 1)
        else:
            # Horizontal Tweener — scales smoothly with icon_px!
            compact = (not full_width and icon_px <= 28)
            if full_width:
                self.setFixedHeight(48)
            else:
                self.setFixedWidth(max(108, int(round(icon_px * 4.1))))
                self.setFixedHeight(max(30, icon_px + 4))

            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(5, 2, 5, 2)
            lay.setSpacing(1 if compact else 2)

            top = QtWidgets.QHBoxLayout()
            top.setSpacing(3)
            t_lbl = QtWidgets.QLabel("TW" if compact else "TWEEN")
            t_lbl.setStyleSheet("color:%s;font-size:9px;font-weight:bold;border:none;" % theme["muted"])
            self.val_lbl = QtWidgets.QLabel("%+d%%" % state.tween_val)
            self.val_lbl.setStyleSheet("color:%s;font-size:9px;font-weight:bold;border:none;" % theme["cat"]["pose"])
            self.ovr_btn = QtWidgets.QPushButton("%d%%" % state.tween_max)
            self.ovr_btn.setFocusPolicy(no_focus)
            self.ovr_btn.setFixedSize(34, 14)
            self.ovr_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-size:8px;}"
                % (theme["btn"], theme["text"], theme["border"])
            )
            self.ovr_btn.clicked.connect(self._toggle_overshoot)
            top.addWidget(t_lbl)
            top.addWidget(self.val_lbl)
            top.addStretch(1)
            top.addWidget(self.ovr_btn)
            lay.addLayout(top)

            orient = QtCore.Qt.Orientation.Horizontal if IS_QT6 else QtCore.Qt.Horizontal
            self.sld = QtWidgets.QSlider(orient)
            self.sld.setFocusPolicy(no_focus)
            self.sld.setRange(-state.tween_max, state.tween_max)
            self.sld.setValue(state.tween_val)
            self.sld.valueChanged.connect(self._on_change)
            lay.addWidget(self.sld)

            if not compact:
                ticks = QtWidgets.QHBoxLayout()
                ticks.setSpacing(2)
                for v in (-75, -50, -25, 0, 25, 50, 75):
                    b = QtWidgets.QPushButton()
                    b.setFocusPolicy(no_focus)
                    b.setFixedHeight(5)
                    b.setToolTip("Tween %+d%%" % v)
                    b.setStyleSheet(
                        "QPushButton{background:%s;border:none;border-radius:2px;}QPushButton:hover{background:%s;}"
                        % (theme["btn_hover"] if v == 0 else theme["btn"], theme["cat"]["pose"])
                    )
                    b.clicked.connect(lambda _c=False, val=v: self.sld.setValue(val))
                    ticks.addWidget(b)
                lay.addLayout(ticks)

    def _on_change(self, v):
        self.state.tween_val = v
        self.val_lbl.setText("%+d%%" % v)
        _toast("Dummy Tween -> %+d%%" % v, THEMES[self.state.theme_name]["cat"]["pose"])

    def _toggle_overshoot(self):
        self.state.tween_max = 150 if self.state.tween_max == 100 else 100
        self.sld.setRange(-self.state.tween_max, self.state.tween_max)
        self.ovr_btn.setText("%d%%" % self.state.tween_max)


# ---------------------------------------------------------------------------
# Right-Click Tool Settings Micro-Strip
# ---------------------------------------------------------------------------
class SettingsMicroStrip(QtWidgets.QFrame):
    closed = QtCore.Signal()

    def __init__(self, state, parent=None):
        super(SettingsMicroStrip, self).__init__(parent)
        self.state = state
        self.current_key = None
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus
        self.setFocusPolicy(no_focus)
        self.lay = QtWidgets.QHBoxLayout(self)
        self.lay.setContentsMargins(7, 4, 7, 4)
        self.lay.setSpacing(6)
        self.hide()

    def show_for(self, key):
        self.current_key = key
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme = THEMES[self.state.theme_name]
        act = ACTION_MAP[key]
        accent = theme["cat"].get(act["cat"], theme["active"])
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus
        self.setStyleSheet(
            "QFrame{background:%s;border:1px solid %s;border-left:3px solid %s;border-radius:6px;}"
            % (theme["bg"], theme["border"], accent)
        )

        spec = TOOL_SETTINGS.get(key)
        title = QtWidgets.QLabel(spec[0] if spec else act["label"])
        title.setStyleSheet("color:%s;font-weight:bold;font-size:10px;border:none;" % accent)
        self.lay.addWidget(title)

        if not spec:
            note = QtWidgets.QLabel("1-click tool (no extra settings)")
            note.setStyleSheet("color:%s;font-size:10px;border:none;" % theme["muted"])
            self.lay.addWidget(note)
        else:
            saved = self.state.settings_values.setdefault(key, {})
            for opt_name, choices, default_idx in spec[1]:
                cur = saved.get(opt_name, default_idx)
                lbl = QtWidgets.QLabel(opt_name + ":")
                lbl.setStyleSheet("color:%s;font-size:10px;border:none;" % theme["muted"])
                self.lay.addWidget(lbl)
                for idx, ch in enumerate(choices):
                    b = QtWidgets.QPushButton(ch)
                    b.setFocusPolicy(no_focus)
                    active = (idx == cur)
                    b.setStyleSheet(
                        "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:2px 6px;font-size:10px;font-weight:%s;}"
                        "QPushButton:hover{border-color:%s;}"
                        % (accent if active else theme["btn"], "#111" if active else theme["text"],
                           accent if active else theme["border"], "bold" if active else "normal", accent)
                    )
                    b.clicked.connect(lambda _c=False, k=key, on=opt_name, i=idx, c=ch: self._pick(k, on, i, c))
                    self.lay.addWidget(b)

        self.lay.addStretch(1)
        x = QtWidgets.QToolButton()
        x.setFocusPolicy(no_focus)
        x.setText("x")
        x.setStyleSheet("QToolButton{color:%s;border:none;font-weight:bold;padding:0 3px;}" % theme["muted"])
        x.clicked.connect(self._close)
        self.lay.addWidget(x)
        self.show()

    def _pick(self, key, opt_name, idx, choice):
        self.state.settings_values.setdefault(key, {})[opt_name] = idx
        _toast("%s -> %s: %s" % (ACTION_MAP[key]["label"], opt_name, choice))
        self.show_for(key)

    def _close(self):
        self.current_key = None
        self.hide()
        self.closed.emit()


# ---------------------------------------------------------------------------
# Fuzzy Search Palette (All 58 Tools)
# ---------------------------------------------------------------------------
class FuzzySearchDialog(QtWidgets.QDialog):
    def __init__(self, state, parent=None):
        super(FuzzySearchDialog, self).__init__(parent)
        self.state = state
        theme = THEMES[state.theme_name]
        self.setWindowTitle("Quick Search — All 58 Tools")
        self.resize(360, 420)
        self.setStyleSheet(
            "QDialog{background:%s;color:%s;border:1px solid %s;}"
            "QLineEdit{background:%s;color:%s;border:1px solid %s;border-radius:5px;padding:6px;}"
            "QListWidget{background:%s;color:%s;border:1px solid %s;border-radius:5px;}"
            % (theme["panel"], theme["text"], theme["border"],
               theme["bg"], theme["text"], theme["active"],
               theme["card"], theme["text"], theme["border"])
        )
        lay = QtWidgets.QVBoxLayout(self)
        self.inp = QtWidgets.QLineEdit()
        self.inp.setPlaceholderText("Type tool name, badge, or category (e.g. mirror, ik, step, eul)...")
        self.inp.textChanged.connect(self._refill)
        lay.addWidget(self.inp)

        self.lst = QtWidgets.QListWidget()
        self.lst.itemClicked.connect(self._run_item)
        lay.addWidget(self.lst)
        self._refill("")

    def _refill(self, query):
        q = (query or "").strip().lower()
        self.lst.clear()
        for k, lbl, cat, kind, glyph, _s, hk in ACTIONS:
            hay = "%s %s %s %s" % (k, lbl, cat, glyph)
            if not q or all(tok in hay.lower() for tok in q.split()):
                txt = "%s   [%s]" % (lbl, cat.upper())
                if hk:
                    txt += "  (%s)" % hk
                item = QtWidgets.QListWidgetItem(txt)
                item.setData(QtCore.Qt.ItemDataRole.UserRole if IS_QT6 else QtCore.Qt.UserRole, k)
                self.lst.addItem(item)

    def _run_item(self, item):
        k = item.data(QtCore.Qt.ItemDataRole.UserRole if IS_QT6 else QtCore.Qt.UserRole)
        _toast("Search Trigger: %s (dummy)" % ACTION_MAP[k]["label"], THEMES[self.state.theme_name]["active"])
        self.accept()


# ---------------------------------------------------------------------------
# Edit Profile Dialog
# ---------------------------------------------------------------------------
class EditProfileDialog(QtWidgets.QDialog):
    def __init__(self, state, parent=None):
        super(EditProfileDialog, self).__init__(parent)
        self.state = state
        theme = THEMES[state.theme_name]
        self.setWindowTitle("Edit Profile: %s" % state.active_profile()["name"])
        self.resize(440, 520)
        self.setStyleSheet(
            "QDialog{background:%s;color:%s;} QCheckBox{color:%s;spacing:5px;padding:2px;}"
            "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:5px;padding:5px 10px;}"
            % (theme["panel"], theme["text"], theme["text"], theme["btn"], theme["text"], theme["border"])
        )
        lay = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Tools in '%s':" % state.active_profile()["name"]))
        new_btn = QtWidgets.QPushButton("+ New Profile")
        new_btn.clicked.connect(self._new_profile)
        top.addWidget(new_btn)
        lay.addLayout(top)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(inner)
        cur_keys = set(state.active_profile()["keys"])
        for i, a in enumerate(ACTIONS):
            cb = QtWidgets.QCheckBox("%s [%s]" % (a[1], a[4] if a[3] == "text" else a[2]))
            cb.setChecked(a[0] in cur_keys)
            cb.toggled.connect(lambda on, k=a[0]: state.toggle_tool_in_active(k, on))
            grid.addWidget(cb, i // 2, i % 2)
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        done = QtWidgets.QPushButton("Done")
        done.clicked.connect(self.accept)
        lay.addWidget(done)

    def _new_profile(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name.strip():
            self.state.add_profile(name.strip())
            self.accept()


# ---------------------------------------------------------------------------
# Floating Bar v3 (Proportional 24-52px Scaling + Full-Info ~74px Column Mode)
# ---------------------------------------------------------------------------
class FloatingBar(QtWidgets.QFrame):
    openPieRequested = QtCore.Signal()
    openDockRequested = QtCore.Signal()
    openSearchRequested = QtCore.Signal()
    hotkeyChanged = QtCore.Signal(str)

    def __init__(self, state, parent=None):
        super(FloatingBar, self).__init__(parent or _maya_main_window())
        self.state = state
        self._drag_offset = None
        self._effective_px = state.target_icon_size

        flags = QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint if IS_QT6 else (QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setWindowFlags(flags)
        keep_mac = getattr(QtCore.Qt.WidgetAttribute if IS_QT6 else QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
        if keep_mac is not None:
            self.setAttribute(keep_mac, True)
        self.setObjectName("gusAnimtool58TestBar")

        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(5, 4, 5, 4)
        self.root.setSpacing(4)

        self.chrome_box = QtWidgets.QWidget()
        self.tools_box = QtWidgets.QWidget()
        self.settings_strip = SettingsMicroStrip(state, self)
        self.settings_strip.closed.connect(self._fit_window)

        self.root.addWidget(self.chrome_box)
        self.root.addWidget(self.tools_box)
        self.root.addWidget(self.settings_strip)

        state.changed.connect(self.rebuild)
        self.rebuild()

    def wheelEvent(self, event):
        mods = event.modifiers()
        ctrl = QtCore.Qt.KeyboardModifier.ControlModifier if IS_QT6 else QtCore.Qt.ControlModifier
        if mods & ctrl:
            step = 2 if event.angleDelta().y() > 0 else -2
            self.state.set_icon_size(self.state.target_icon_size + step)
            event.accept()
            return
        super(FloatingBar, self).wheelEvent(event)

    def mousePressEvent(self, event):
        left = QtCore.Qt.MouseButton.LeftButton if IS_QT6 else QtCore.Qt.LeftButton
        if event.button() == left:
            self._drag_offset = _evt_global_pos(event) - self.frameGeometry().topLeft()
            event.accept()
            return
        super(FloatingBar, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            self.move(_evt_global_pos(event) - self._drag_offset)
            event.accept()
            return
        super(FloatingBar, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super(FloatingBar, self).mouseReleaseEvent(event)

    def _cell_w(self, px):
        # Zero dead space when Lbl=OFF; uniform 2-line width when Lbl=ON
        return max(px + 6, 52) if self.state.show_labels else (px + 4)

    def _compute_auto_fit(self, keys, mode):
        scr = _screen_geometry(self)
        max_w = int(scr.width() * 0.92)
        max_h = int(scr.height() * 0.85)
        n = len(keys)
        has_tween = ("tween_prev" in keys and "tween_next" in keys)
        target = self.state.target_icon_size
        lbl_h = 24 if self.state.show_labels else 0

        if mode == "col":
            for px in range(target, 21, -2):
                cell_h = px + 3 + lbl_h
                tween_h = 132 if has_tween else 0
                if 168 + n * (cell_h + 2) + tween_h <= max_h:
                    return px, self._cell_w(px), 1, (px < target)
            return 22, self._cell_w(22), 1, True

        if mode == "row":
            for px in range(target, 21, -2):
                cw = self._cell_w(px)
                tween_w = max(108, int(round(px * 4.1))) if has_tween else 0
                if 20 + n * (cw + 2) + tween_w <= max_w:
                    return px, cw, max(1, n), (px < target)
            return 22, self._cell_w(22), max(1, n), True

        if mode == "2r":
            cols = max(1, int(math.ceil(n / 2.0)))
            for px in range(target, 21, -2):
                cw = self._cell_w(px)
                tween_w = max(108, int(round(px * 4.1))) if has_tween else 0
                if 20 + cols * (cw + 2) + tween_w <= max_w:
                    return px, cw, cols, (px < target)
            return 22, self._cell_w(22), cols, True

        ideal_cols = 12 if n > 24 else (6 if n > 8 else max(4, n))
        for px in range(target, 21, -2):
            cw = self._cell_w(px)
            cols = min(ideal_cols, max(3, (max_w - 20) // (cw + 2)))
            rows = int(math.ceil((n + (2 if has_tween else 0)) / float(cols)))
            if 74 + rows * (px + 3 + lbl_h + 2) <= max_h:
                return px, cw, cols, (px < target)
        return 22, self._cell_w(22), ideal_cols, True

    def rebuild(self):
        theme = THEMES[self.state.theme_name]
        prof = self.state.active_profile()
        prof_col = self.state.profile_color(prof)
        mode = self.state.layout_mode
        keys = prof["keys"]
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus

        self.setStyleSheet(
            "QFrame#gusAnimtool58TestBar{background:%s;border:1px solid %s;border-top:3px solid %s;border-radius:8px;}"
            % (theme["panel"], theme["border"], prof_col)
        )

        px, cell_w, cols, shrunk = self._compute_auto_fit(keys, mode)
        self._effective_px = px

        self._clear_widget(self.chrome_box)
        if mode == "col":
            # Full-Information ~74px Column Chrome (Zero Color-Only Cues!)
            cl = QtWidgets.QVBoxLayout(self.chrome_box)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)

            top_r = QtWidgets.QHBoxLayout()
            top_r.setSpacing(2)
            grip = QtWidgets.QLabel("::")
            grip.setStyleSheet("color:%s;font-weight:bold;font-size:10px;" % theme["muted"])
            sz_lbl = QtWidgets.QLabel("%dpx%s" % (px, "*" if shrunk else ""))
            sz_lbl.setStyleSheet("color:%s;font-size:9px;" % (theme["active"] if shrunk else theme["muted"]))
            menu_btn = QtWidgets.QPushButton("=")
            menu_btn.setFocusPolicy(no_focus)
            menu_btn.setFixedSize(18, 16)
            menu_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-weight:bold;font-size:9px;}"
                % (theme["btn"], theme["text"], theme["border"])
            )
            menu_btn.clicked.connect(self._show_menu)
            top_r.addWidget(grip)
            top_r.addStretch(1)
            top_r.addWidget(sz_lbl)
            top_r.addWidget(menu_btn)
            cl.addLayout(top_r)

            # 1-Click Orientation Row (Row | Col | Grd)
            m_row = QtWidgets.QHBoxLayout()
            m_row.setSpacing(2)
            for mk, ml in (("row", "Row"), ("col", "Col"), ("grid", "Grd")):
                b = QtWidgets.QPushButton(ml)
                b.setFocusPolicy(no_focus)
                on = (mode == mk)
                b.setFixedHeight(17)
                b.setStyleSheet(
                    "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-size:8px;font-weight:bold;padding:0;}"
                    % (theme["active"] if on else theme["bg"], "#111" if on else theme["muted"],
                       theme["active"] if on else theme["border"])
                )
                b.clicked.connect(lambda _c=False, m=mk: self.state.set_layout_mode(m))
                m_row.addWidget(b)
            cl.addLayout(m_row)

            # 1-Click Lbl | Pie Row
            a_row = QtWidgets.QHBoxLayout()
            a_row.setSpacing(2)
            lb = QtWidgets.QPushButton("Lbl")
            lb.setFocusPolicy(no_focus)
            lb.setFixedHeight(17)
            lb.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-size:8px;font-weight:bold;padding:0;}"
                % (theme["active"] if self.state.show_labels else theme["bg"],
                   "#111" if self.state.show_labels else theme["muted"],
                   theme["active"] if self.state.show_labels else theme["border"])
            )
            lb.clicked.connect(lambda: self.state.set_labels(not self.state.show_labels))
            pb = QtWidgets.QPushButton("Pie")
            pb.setFocusPolicy(no_focus)
            pb.setFixedHeight(17)
            pb.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:3px;font-size:8px;font-weight:bold;padding:0;}"
                % (theme["bg"], theme["muted"], theme["border"])
            )
            pb.clicked.connect(self.openPieRequested.emit)
            a_row.addWidget(lb)
            a_row.addWidget(pb)
            cl.addLayout(a_row)

            # Named Profile Pills with Tool Counts & 3px Left Accent
            for idx, p in enumerate(self.state.profiles):
                pc = self.state.profile_color(p)
                is_on = (idx == self.state.active_profile_idx)
                short_txt = p["short"].replace(" 58", "")
                btn = QtWidgets.QPushButton("%s  %d" % (short_txt, len(p["keys"])))
                btn.setFocusPolicy(no_focus)
                btn.setFixedHeight(18)
                btn.setToolTip("Profile %d: %s (%d tools)" % (idx + 1, p["name"], len(p["keys"])))
                btn.setStyleSheet(
                    "QPushButton{background:%s;color:%s;border:1px solid %s;border-left:3px solid %s;"
                    "border-radius:3px;padding:0 4px;font-size:9px;font-weight:bold;text-align:left;}"
                    "QPushButton:hover{background:%s;}"
                    % (theme["card"] if is_on else theme["bg"], theme["text"] if is_on else theme["muted"],
                       theme["border"] if is_on else theme["border_subtle"], pc, theme["btn"])
                )
                btn.clicked.connect(lambda _c=False, i=idx: self.state.set_profile(i))
                cl.addWidget(btn)
        else:
            cl = QtWidgets.QHBoxLayout(self.chrome_box)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)

            grip = QtWidgets.QLabel("::")
            grip.setStyleSheet("color:%s;font-weight:bold;padding:0 2px;font-size:10px;" % theme["muted"])
            cl.addWidget(grip)

            for idx, p in enumerate(self.state.profiles):
                pc = self.state.profile_color(p)
                is_on = (idx == self.state.active_profile_idx)
                tb = QtWidgets.QPushButton(p["short"])
                tb.setFocusPolicy(no_focus)
                tb.setToolTip("Profile %d: %s" % (idx + 1, p["name"]))
                tb.setStyleSheet(
                    "QPushButton{background:%s;color:%s;border:1px solid %s;border-bottom:2px solid %s;"
                    "border-radius:4px;padding:2px 6px;font-size:10px;font-weight:%s;}"
                    "QPushButton:hover{background:%s;}"
                    % (theme["card"] if is_on else theme["bg"], theme["text"] if is_on else theme["muted"],
                       theme["border"] if is_on else "transparent", pc if is_on else "transparent",
                       "bold" if is_on else "normal", theme["btn"])
                )
                tb.clicked.connect(lambda _c=False, i=idx: self.state.set_profile(i))
                cl.addWidget(tb)

            cl.addStretch(1)

            for m_key, m_lbl in (("row", "Row"), ("2r", "2R"), ("col", "Col"), ("grid", "Grid")):
                mb = QtWidgets.QPushButton(m_lbl)
                mb.setFocusPolicy(no_focus)
                on = (mode == m_key)
                mb.setStyleSheet(
                    "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:2px 5px;font-size:10px;font-weight:%s;}"
                    % (theme["active"] if on else theme["bg"], "#111" if on else theme["muted"],
                       theme["active"] if on else theme["border"], "bold" if on else "normal")
                )
                mb.clicked.connect(lambda _c=False, mk=m_key: self.state.set_layout_mode(mk))
                cl.addWidget(mb)

            lbl_btn = QtWidgets.QPushButton("Lbl")
            lbl_btn.setFocusPolicy(no_focus)
            on = self.state.show_labels
            lbl_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:2px 5px;font-size:10px;font-weight:%s;}"
                % (theme["active"] if on else theme["bg"], "#111" if on else theme["muted"],
                   theme["active"] if on else theme["border"], "bold" if on else "normal")
            )
            lbl_btn.clicked.connect(lambda: self.state.set_labels(not self.state.show_labels))
            cl.addWidget(lbl_btn)

            orient = QtCore.Qt.Orientation.Horizontal if IS_QT6 else QtCore.Qt.Horizontal
            sld = QtWidgets.QSlider(orient)
            sld.setFocusPolicy(no_focus)
            sld.setRange(24, 52)
            sld.setValue(self.state.target_icon_size)
            sld.setFixedWidth(64)
            sld.setToolTip("Icon size (24-52px) or Ctrl + Scroll Wheel over bar")
            sld.valueChanged.connect(self.state.set_icon_size)
            cl.addWidget(sld)

            sz_lbl = QtWidgets.QLabel("%dpx%s" % (px, "*" if shrunk else ""))
            sz_lbl.setStyleSheet("color:%s;font-size:10px;padding-right:2px;" % (theme["active"] if shrunk else theme["muted"]))
            cl.addWidget(sz_lbl)

            opt_btn = QtWidgets.QPushButton("=")
            opt_btn.setFocusPolicy(no_focus)
            opt_btn.setFixedWidth(22)
            opt_btn.setToolTip("Pie Hotkey, Dock, Search, Edit Profile & Theme")
            opt_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:2px 4px;font-size:10px;font-weight:bold;}"
                % (theme["btn"], theme["text"], theme["border"])
            )
            opt_btn.clicked.connect(self._show_menu)
            cl.addWidget(opt_btn)

            close_btn = QtWidgets.QToolButton()
            close_btn.setFocusPolicy(no_focus)
            close_btn.setText("x")
            close_btn.setStyleSheet("QToolButton{color:%s;border:none;font-weight:bold;padding:0 2px;}" % theme["muted"])
            close_btn.clicked.connect(self.hide)
            cl.addWidget(close_btn)

        # --- Rebuild Tool Tiles (Tight 2px Rhythm) ---
        self._clear_widget(self.tools_box)
        has_tween = ("tween_prev" in keys and "tween_next" in keys)

        if mode == "col":
            tl = QtWidgets.QVBoxLayout(self.tools_box)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)
            align_h = QtCore.Qt.AlignmentFlag.AlignHCenter if IS_QT6 else QtCore.Qt.AlignHCenter
            for k in keys:
                tile = ToolTile(k, px, self.state.show_labels, cell_w, self.state.theme_name)
                tile.leftClicked.connect(self._on_tool_click)
                tile.rightClicked.connect(self._on_tool_rmb)
                tl.addWidget(tile, 0, align_h)
                if has_tween and k == "tween_prev":
                    tl.addWidget(InlineTweener(self.state, icon_px=px, vertical=True, theme_name=self.state.theme_name), 0, align_h)
        elif mode == "row":
            tl = QtWidgets.QHBoxLayout(self.tools_box)
            tl.setContentsMargins(0, 0, 0, 0)
            tl.setSpacing(2)
            for k in keys:
                tile = ToolTile(k, px, self.state.show_labels, cell_w, self.state.theme_name)
                tile.leftClicked.connect(self._on_tool_click)
                tile.rightClicked.connect(self._on_tool_rmb)
                tl.addWidget(tile)
                if has_tween and k == "tween_prev":
                    tl.addWidget(InlineTweener(self.state, icon_px=px, vertical=False, theme_name=self.state.theme_name))
        else:
            gl = QtWidgets.QGridLayout(self.tools_box)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setHorizontalSpacing(2)
            gl.setVerticalSpacing(2)
            r, c = 0, 0
            for k in keys:
                tile = ToolTile(k, px, self.state.show_labels, cell_w, self.state.theme_name)
                tile.leftClicked.connect(self._on_tool_click)
                tile.rightClicked.connect(self._on_tool_rmb)
                gl.addWidget(tile, r, c)
                c += 1
                if c >= cols:
                    c = 0; r += 1
                if has_tween and k == "tween_prev":
                    span = min(3, cols)
                    if c + span > cols:
                        c = 0; r += 1
                    gl.addWidget(InlineTweener(self.state, icon_px=px, vertical=False, theme_name=self.state.theme_name), r, c, 1, span)
                    c += span
                    if c >= cols:
                        c = 0; r += 1

        self._fit_window()

    def _fit_window(self):
        self.layout().activate()
        self.adjustSize()
        self.resize(self.sizeHint())

    def _clear_widget(self, w):
        old = w.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QtWidgets.QWidget().setLayout(old)

    def _on_tool_click(self, key):
        act = ACTION_MAP[key]
        _toast("Bar Click: %s (dummy)" % act["label"], THEMES[self.state.theme_name]["cat"].get(act["cat"], "#3898c8"))

    def _on_tool_rmb(self, key):
        if self.settings_strip.isVisible() and self.settings_strip.current_key == key:
            self.settings_strip._close()
        else:
            self.settings_strip.show_for(key)
            self._fit_window()

    def _open_edit(self):
        dlg = EditProfileDialog(self.state, self)
        dlg.exec() if IS_QT6 else dlg.exec_()

    def _show_menu(self):
        menu = QtWidgets.QMenu(self)
        for m_key, m_lbl in (("row", "Layout: Row"), ("2r", "Layout: 2-Row"), ("col", "Layout: Column"), ("grid", "Layout: Grid")):
            a = menu.addAction(m_lbl)
            a.triggered.connect(lambda _c=False, mk=m_key: self.state.set_layout_mode(mk))
        menu.addSeparator()
        a_lbl = menu.addAction("Labels: %s" % ("ON" if self.state.show_labels else "OFF"))
        a_lbl.triggered.connect(lambda: self.state.set_labels(not self.state.show_labels))
        a_cb = menu.addAction("Okabe-Ito Color-Blind: %s" % ("ON" if self.state.theme_name == "okabe" else "OFF"))
        a_cb.triggered.connect(lambda: self.state.set_theme("default" if self.state.theme_name == "okabe" else "okabe"))
        menu.addSeparator()
        a_pie = menu.addAction("Open Pie Menu")
        a_pie.triggered.connect(self.openPieRequested.emit)
        hk_menu = menu.addMenu("Pie Trigger Key (%s)" % self.state.pie_hotkey)
        for hk_id, hk_lbl in (("grave", "` (Backtick — under Esc)"), ("F1", "F1 (Single Key)"), ("\\", "\\ (Backslash)")):
            ha = hk_menu.addAction(hk_lbl)
            ha.triggered.connect(lambda _c=False, h=hk_id: self.hotkeyChanged.emit(h))
        menu.addSeparator()
        a_dock = menu.addAction("Open Narrow Dock")
        a_dock.triggered.connect(self.openDockRequested.emit)
        a_srch = menu.addAction("Search All 58 Tools")
        a_srch.triggered.connect(self.openSearchRequested.emit)
        a_edit = menu.addAction("Edit Profile / Add Profile...")
        a_edit.triggered.connect(self._open_edit)
        menu.addSeparator()
        a_close = menu.addAction("Hide Floating Bar")
        a_close.triggered.connect(self.hide)
        menu.exec(QtGui.QCursor.pos()) if IS_QT6 else menu.exec_(QtGui.QCursor.pos())


# ---------------------------------------------------------------------------
# Hotbox-Style Radial Pie Menu (Backdrop Painted Directly in paintEvent!)
# ---------------------------------------------------------------------------
class RadialPieMenu(QtWidgets.QWidget):
    def __init__(self, state, parent=None):
        super(RadialPieMenu, self).__init__(parent or _maya_main_window())
        self.state = state
        self.pinned_for_settings = False

        flags = QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint if IS_QT6 else (QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setWindowFlags(flags)
        trans = QtCore.Qt.WidgetAttribute.WA_TranslucentBackground if IS_QT6 else QtCore.Qt.WA_TranslucentBackground
        self.setAttribute(trans, True)

        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(10, 10, 10, 10)
        self.root.setSpacing(6)

        self.top_zone = QtWidgets.QFrame()
        self.ring_host = QtWidgets.QWidget()
        self.ring_host.setFixedSize(360, 320)
        self.settings_strip = SettingsMicroStrip(state, self)
        self.overflow_zone = QtWidgets.QFrame()

        align_h = QtCore.Qt.AlignmentFlag.AlignHCenter if IS_QT6 else QtCore.Qt.AlignHCenter
        self.root.addWidget(self.top_zone, 0, align_h)
        self.root.addWidget(self.ring_host, 0, align_h)
        self.root.addWidget(self.settings_strip)
        self.root.addWidget(self.overflow_zone, 0, align_h)

        state.changed.connect(self._on_state_change)

    def paintEvent(self, _event):
        """Paints the dark circular Hotbox ring directly on the popup so Maya composites it cleanly."""
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing if IS_QT6 else QtGui.QPainter.Antialiasing)
        r = self.ring_host.geometry()
        cx = r.center().x()
        cy = r.center().y()
        accent = QtGui.QColor(self.state.profile_color())

        # Outer dark translucent circular backdrop
        outer = QtCore.QRectF(cx - 160, cy - 146, 320, 292)
        p.setPen(QtGui.QPen(QtGui.QColor("#454f60"), 1.6))
        p.setBrush(QtGui.QColor(22, 25, 30, 232))
        p.drawEllipse(outer)

        # Inner dashed active-profile ring
        inner = QtCore.QRectF(cx - 82, cy - 72, 164, 144)
        p.setPen(QtGui.QPen(accent, 1.4, QtCore.Qt.PenStyle.DashLine if IS_QT6 else QtCore.Qt.DashLine))
        p.setBrush(QtGui.QColor(34, 38, 45, 220))
        p.drawEllipse(inner)
        p.end()

    def open_at_cursor(self):
        self.pinned_for_settings = False
        self.settings_strip.hide()
        self.rebuild()
        self.adjustSize()
        pos = QtGui.QCursor.pos()
        scr = _screen_geometry(self)
        ring_center_y = self.top_zone.sizeHint().height() + 16 + 160
        x = max(scr.left() + 8, min(pos.x() - self.width() // 2, scr.right() - self.width() - 8))
        y = max(scr.top() + 8, min(pos.y() - ring_center_y, scr.bottom() - self.height() - 8))
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.update()

    def _on_state_change(self):
        if self.isVisible():
            self.rebuild()
            self.adjustSize()
            self.update()

    def keyPressEvent(self, event):
        esc = QtCore.Qt.Key.Key_Escape if IS_QT6 else QtCore.Qt.Key_Escape
        if event.key() == esc:
            self.close()
            return
        if event.text() in ("1", "2", "3", "4", "5"):
            idx = int(event.text()) - 1
            if idx < len(self.state.profiles):
                self.state.set_profile(idx)
                return
        super(RadialPieMenu, self).keyPressEvent(event)

    def _clear_children(self, w):
        old = w.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QtWidgets.QWidget().setLayout(old)
        for child in w.findChildren(QtWidgets.QWidget, options=(
            QtCore.Qt.FindChildOption.FindDirectChildrenOnly if IS_QT6 else QtCore.Qt.FindDirectChildrenOnly
        )):
            child.deleteLater()

    def rebuild(self):
        theme = THEMES[self.state.theme_name]
        prof = self.state.active_profile()
        prof_col = self.state.profile_color(prof)
        keys = prof["keys"]

        # 1. Top 1-5 Profile Tabs
        self._clear_children(self.top_zone)
        self.top_zone.setStyleSheet(
            "QFrame{background:rgba(22,25,30,240);border:1px solid %s;border-radius:8px;}" % theme["border"]
        )
        tl = QtWidgets.QHBoxLayout(self.top_zone)
        tl.setContentsMargins(6, 4, 6, 4)
        tl.setSpacing(4)
        for idx, p in enumerate(self.state.profiles):
            pc = self.state.profile_color(p)
            on = (idx == self.state.active_profile_idx)
            b = QtWidgets.QPushButton("%d · %s" % (idx + 1, p["short"]))
            b.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:5px;padding:3px 8px;font-size:10px;font-weight:bold;}"
                % (pc if on else theme["btn"], "#111" if on else theme["text"], pc if on else theme["border"])
            )
            b.clicked.connect(lambda _c=False, i=idx: self.state.set_profile(i))
            tl.addWidget(b)

        # 2. 8-Compass Ring + Dark Label Pills
        self._clear_children(self.ring_host)
        cx, cy = 180, 160
        rx, ry = 122, 108

        center_lbl = QtWidgets.QLabel("%s\nRMB = Settings" % prof["name"], self.ring_host)
        center_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter if IS_QT6 else QtCore.Qt.AlignCenter)
        center_lbl.setGeometry(cx - 56, cy - 22, 112, 44)
        center_lbl.setStyleSheet(
            "background:rgba(22,25,30,240);color:%s;border:1px solid %s;border-radius:22px;font-size:9px;font-weight:bold;"
            % (theme["text"], prof_col)
        )
        center_lbl.show()

        ring_keys = keys[:8]
        for i, k in enumerate(ring_keys):
            angle = -math.pi / 2.0 + i * (2.0 * math.pi / max(1, len(ring_keys)))
            tx = int(cx + math.cos(angle) * rx - 34)
            ty = int(cy + math.sin(angle) * ry - 32)
            tile = ToolTile(k, 36, True, 68, self.state.theme_name, label_pill=True, parent=self.ring_host)
            tile.move(tx, ty)
            tile.leftClicked.connect(self._fire_and_close)
            tile.rightClicked.connect(self._open_pie_settings)
            tile.show()

        # 3. Bottom Overflow Strip
        self._clear_children(self.overflow_zone)
        extra = keys[8:20]
        if extra:
            self.overflow_zone.setStyleSheet(
                "QFrame{background:rgba(22,25,30,240);border:1px solid %s;border-radius:8px;}" % theme["border"]
            )
            ol = QtWidgets.QHBoxLayout(self.overflow_zone)
            ol.setContentsMargins(6, 4, 6, 4)
            ol.setSpacing(3)
            for k in extra:
                tile = ToolTile(k, 28, True, 56, self.state.theme_name, label_pill=True)
                tile.leftClicked.connect(self._fire_and_close)
                tile.rightClicked.connect(self._open_pie_settings)
                ol.addWidget(tile)
            if len(keys) > 20:
                more = QtWidgets.QLabel("+%d more in Bar" % (len(keys) - 20))
                more.setStyleSheet("color:%s;font-size:10px;padding:0 5px;" % theme["muted"])
                ol.addWidget(more)
            self.overflow_zone.show()
        else:
            self.overflow_zone.hide()

    def _fire_and_close(self, key):
        act = ACTION_MAP[key]
        _toast("Pie Trigger: %s (dummy)" % act["label"], THEMES[self.state.theme_name]["cat"].get(act["cat"], "#3898c8"))
        self.close()

    def _open_pie_settings(self, key):
        self.pinned_for_settings = True
        self.settings_strip.show_for(key)
        self.adjustSize()
        self.update()


# ---------------------------------------------------------------------------
# High-Contrast 242px Narrow Dock (ALL 58 Tools + Scroll + Auto Micro-Rail)
# ---------------------------------------------------------------------------
class AnimtoolDockWidget(QtWidgets.QWidget):
    openSearchRequested = QtCore.Signal()

    def __init__(self, state, parent=None):
        super(AnimtoolDockWidget, self).__init__(parent)
        self.state = state
        self._is_rail = False
        self._closed_cats = {"timing", "curves", "view", "open"}

        self.root = QtWidgets.QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        self.header_box = QtWidgets.QWidget()
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame if IS_QT6 else QtWidgets.QFrame.NoFrame)
        self.scroll_inner = QtWidgets.QWidget()
        self.scroll.setWidget(self.scroll_inner)

        self.status_bar = QtWidgets.QLabel(" ● L_hand_ik · f14 · IK                     58 tools")
        self.status_bar.setFixedHeight(22)

        self.root.addWidget(self.header_box)
        self.root.addWidget(self.scroll, 1)
        self.root.addWidget(self.status_bar)

        state.changed.connect(self.rebuild)
        self.rebuild()

    def resizeEvent(self, event):
        super(AnimtoolDockWidget, self).resizeEvent(event)
        want_rail = self.width() < 135
        if want_rail != self._is_rail:
            self._is_rail = want_rail
            self.rebuild()

    def _clear(self, w):
        old = w.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QtWidgets.QWidget().setLayout(old)

    def _toggle_cat(self, cat_key):
        if cat_key in self._closed_cats:
            self._closed_cats.remove(cat_key)
        else:
            self._closed_cats.add(cat_key)
        self.rebuild()

    def rebuild(self):
        self._clear(self.header_box)
        self._clear(self.scroll_inner)
        theme = THEMES[self.state.theme_name]
        no_focus = QtCore.Qt.FocusPolicy.NoFocus if IS_QT6 else QtCore.Qt.NoFocus

        self.setStyleSheet(
            "QWidget{background:%s;color:%s;}"
            "QScrollBar:vertical{background:%s;width:6px;margin:0;}"
            "QScrollBar::handle:vertical{background:%s;border-radius:3px;min-height:20px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            % (theme["bg"], theme["text"], theme["bg"], theme["border"])
        )
        self.status_bar.setStyleSheet(
            "background:#14171c;color:%s;font-size:10px;padding:0 6px;border-top:1px solid %s;"
            % (theme["muted"], theme["border_subtle"])
        )

        body_lay = QtWidgets.QVBoxLayout(self.scroll_inner)
        body_lay.setContentsMargins(5, 5, 5, 5)
        body_lay.setSpacing(6)

        if self._is_rail:
            self.header_box.hide()
            self.status_bar.hide()
            lbl = QtWidgets.QLabel("RAIL")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter if IS_QT6 else QtCore.Qt.AlignCenter)
            lbl.setStyleSheet("color:%s;font-size:9px;font-weight:bold;" % theme["active"])
            body_lay.addWidget(lbl)
            for k in self.state.active_profile()["keys"][:8]:
                t = ToolTile(k, 32, False, 48, self.state.theme_name)
                t.leftClicked.connect(lambda key=k: _toast("Micro-Rail: %s" % ACTION_MAP[key]["label"]))
                body_lay.addWidget(t, 0, QtCore.Qt.AlignmentFlag.AlignHCenter if IS_QT6 else QtCore.Qt.AlignHCenter)
            body_lay.addStretch(1)
            return

        self.header_box.show()
        self.status_bar.show()
        self.header_box.setStyleSheet(
            "background:%s;border-bottom:1px solid %s;" % (theme["panel"], theme["border_subtle"])
        )

        # Fixed Top Header (Profile Pills + ? + CB + Pick & View 6-Icon Strip)
        h_lay = QtWidgets.QVBoxLayout(self.header_box)
        h_lay.setContentsMargins(6, 5, 6, 5)
        h_lay.setSpacing(4)

        hdr = QtWidgets.QHBoxLayout()
        hdr.setSpacing(3)
        for idx, p in enumerate(self.state.profiles[:3]):
            pc = self.state.profile_color(p)
            on = (idx == self.state.active_profile_idx)
            b = QtWidgets.QPushButton(p["short"])
            b.setFocusPolicy(no_focus)
            b.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:3px 5px;font-size:10px;font-weight:bold;}"
                % (pc if on else theme["btn"], "#111" if on else theme["text"], pc if on else theme["border"])
            )
            b.clicked.connect(lambda _c=False, i=idx: self.state.set_profile(i))
            hdr.addWidget(b)

        srch_btn = QtWidgets.QPushButton("?")
        srch_btn.setFocusPolicy(no_focus)
        srch_btn.setFixedWidth(24)
        srch_btn.setToolTip("Search All 58 Tools")
        srch_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:3px 4px;font-size:10px;font-weight:bold;}"
            % (theme["btn"], theme["text"], theme["border"])
        )
        srch_btn.clicked.connect(self.openSearchRequested.emit)
        hdr.addWidget(srch_btn)

        cb_on = (self.state.theme_name == "okabe")
        cb_btn = QtWidgets.QPushButton("CB")
        cb_btn.setFocusPolicy(no_focus)
        cb_btn.setFixedWidth(26)
        cb_btn.setToolTip("Toggle Okabe-Ito Color-Blind Safe Palette")
        cb_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;padding:3px 4px;font-size:10px;font-weight:bold;}"
            % (theme["active"] if cb_on else theme["btn"], "#111" if cb_on else theme["muted"], theme["border"])
        )
        cb_btn.clicked.connect(lambda: self.state.set_theme("default" if cb_on else "okabe"))
        hdr.addWidget(cb_btn)
        h_lay.addLayout(hdr)

        pv_row = QtWidgets.QHBoxLayout()
        pv_row.setSpacing(2)
        for k in ("arcs", "hide_ctrls", "isolate", "hider", "ghosts", "playblast"):
            t = ToolTile(k, 28, False, 32, self.state.theme_name)
            t.leftClicked.connect(lambda key=k: _toast("Pick & View: %s" % ACTION_MAP[key]["label"]))
            pv_row.addWidget(t)
        h_lay.addLayout(pv_row)

        # Scrollable Body: 1. Calm 3x2 Pinned Grid
        pin_keys = self.state.active_profile()["keys"][:6]
        pin_grid = QtWidgets.QGridLayout()
        pin_grid.setSpacing(3)
        for i, k in enumerate(pin_keys):
            act = ACTION_MAP[k]
            acc = theme["cat"].get(act["cat"], theme["active"])
            pb = QtWidgets.QPushButton(act["glyph"] if act["kind"] == "text" else act["label"].split()[0])
            pb.setFocusPolicy(no_focus)
            pb.setToolTip(act["label"])
            pb.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;border-top:2px solid %s;"
                "border-radius:4px;padding:4px 3px;font-size:10px;font-weight:bold;}"
                "QPushButton:hover{background:%s;}"
                % (theme["btn"], theme["text"], theme["border"], acc, theme["btn_hover"])
            )
            pb.clicked.connect(lambda _c=False, m=act["label"], a=acc: _toast("Pinned: %s" % m, a))
            pin_grid.addWidget(pb, i // 3, i % 3)
        body_lay.addLayout(pin_grid)

        # 2. Full-Width Inline Tweener
        body_lay.addWidget(InlineTweener(self.state, vertical=False, full_width=True, theme_name=self.state.theme_name))

        # 3. ALL 58 Tools Dynamically Generated Across 8 Collapsible High-Contrast Drawers
        for cat, title in DOCK_CATEGORIES:
            items = [a for a in ACTIONS if a[2] == cat]
            accent = theme["cat"][cat]
            tint_bg = _blend_hex(accent, theme["card"], 0.12)
            is_open = (cat not in self._closed_cats)

            box = QtWidgets.QFrame()
            box.setStyleSheet(
                "QFrame{background:%s;border:1px solid %s;border-left:3px solid %s;border-radius:6px;}"
                % (theme["card"], theme["border"], accent)
            )
            bl = QtWidgets.QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)

            hdr_btn = QtWidgets.QPushButton("%s (%d)   %s" % (title, len(items), "v" if is_open else ">"))
            hdr_btn.setFocusPolicy(no_focus)
            hdr_btn.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:none;font-size:10px;font-weight:bold;"
                "text-align:left;padding:5px 7px;}"
                % (tint_bg, accent)
            )
            hdr_btn.clicked.connect(lambda _c=False, ck=cat: self._toggle_cat(ck))
            bl.addWidget(hdr_btn)

            if is_open:
                inner_w = QtWidgets.QWidget()
                inner_w.setStyleSheet("background:transparent;border:none;")
                il = QtWidgets.QVBoxLayout(inner_w)
                il.setContentsMargins(5, 4, 5, 5)
                il.setSpacing(3)
                for a in items:
                    k, lbl = a[0], a[1]
                    sub_lbl = SPLIT_CAPS.get(k)
                    r = QtWidgets.QHBoxLayout()
                    r.setSpacing(2)
                    b1 = QtWidgets.QPushButton(lbl)
                    b1.setFocusPolicy(no_focus)
                    b1.setStyleSheet(
                        "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;"
                        "padding:4px 6px;font-size:11px;text-align:left;}"
                        "QPushButton:hover{background:%s;border-color:%s;}"
                        % (theme["btn"], theme["text"], theme["border"], theme["btn_hover"], accent)
                    )
                    b1.clicked.connect(lambda _c=False, m=lbl, acc=accent: _toast("Dock 1-Click: %s" % m, acc))
                    r.addWidget(b1, 3)
                    if sub_lbl:
                        b2 = QtWidgets.QPushButton(sub_lbl)
                        b2.setFocusPolicy(no_focus)
                        b2.setStyleSheet(
                            "QPushButton{background:%s;color:%s;border:1px solid %s;border-radius:4px;"
                            "padding:4px 4px;font-size:9px;font-weight:bold;}"
                            "QPushButton:hover{background:%s;color:#111;border-color:%s;}"
                            % (theme["bg"], theme["muted"], theme["border"], accent, accent)
                        )
                        b2.clicked.connect(lambda _c=False, m=lbl, s=sub_lbl, acc=accent: _toast("Dock Split: %s (%s)" % (m, s), acc))
                        r.addWidget(b2, 1)
                    il.addLayout(r)
                bl.addWidget(inner_w)

            body_lay.addWidget(box)

        body_lay.addStretch(1)


# ---------------------------------------------------------------------------
# Single-Row Maya Shelf ("Gus_Animtool_58") — ALL 58 Real Rendered PNG Icons
# ---------------------------------------------------------------------------
SHELF_NAME = "Gus_Animtool_58"


def _export_shelf_icons(theme_name="default"):
    out_dir = os.path.join(tempfile.gettempdir(), "gus_animtool_58_icons")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    paths = {}
    for a in ACTIONS:
        key = a[0]
        fp = os.path.join(out_dir, "%s_%s.png" % (key, theme_name))
        pm = render_tile_pixmap(key, 64, theme_name=theme_name, bake_card_bg=True)
        pm.save(fp, "PNG")
        paths[key] = fp
    return paths


def build_test_shelf(theme_name="default"):
    if not IN_MAYA or not mel:
        return
    try:
        icon_paths = _export_shelf_icons(theme_name)
        if cmds.shelfLayout(SHELF_NAME, exists=True):
            for child in cmds.shelfLayout(SHELF_NAME, query=True, childArray=True) or []:
                try:
                    cmds.deleteUI(child)
                except Exception:
                    pass
        else:
            mel.eval('addNewShelfTab "%s"' % SHELF_NAME)

        last_cat = None
        for a in ACTIONS:
            key, lbl, cat, _kind, _glyph, _has_set, hk = a
            if last_cat is not None and last_cat != cat:
                cmds.separator(parent=SHELF_NAME, style="shelf", horizontal=False, width=10, height=34)
            last_cat = cat
            ann = "%s%s (UI Test Dummy)" % (lbl, (" (%s)" % hk) if hk else "")
            cmds.shelfButton(
                parent=SHELF_NAME,
                label=lbl,
                annotation=ann,
                image1=icon_paths[key],
                width=34,
                height=34,
                style="iconOnly",
                command="import maya.cmds as c; c.inViewMessage(amg='Shelf Dummy: %s', pos='botCenter', fade=True)" % lbl,
                sourceType="python",
            )
    except Exception as exc:
        print("[Gus Animtool 5.8 UI Test v3] Shelf note: %s" % exc)


# ---------------------------------------------------------------------------
# Native Maya Hold-and-Release Hotkey (` autoSave=False, Safe Cleanup)
# ---------------------------------------------------------------------------
_HK_PRESS_CMD = "gusAnimtool58PiePressCmd"
_HK_RELEASE_CMD = "gusAnimtool58PieReleaseCmd"
_HK_PRESS_NC = "gusAnimtool58PiePressNC"
_HK_RELEASE_NC = "gusAnimtool58PieReleaseNC"
_REG_KEY = "_gus_animtool_58_ui_test_v3_hooks"


def _bind_native_hotkey(key_str="grave"):
    if not IN_MAYA:
        return
    hook_mod = types.ModuleType(_REG_KEY)
    hook_mod.press = _on_native_pie_press
    hook_mod.release = _on_native_pie_release
    sys.modules[_REG_KEY] = hook_mod

    try:
        for rtc in (_HK_PRESS_CMD, _HK_RELEASE_CMD):
            if cmds.runTimeCommand(rtc, exists=True):
                cmds.runTimeCommand(rtc, edit=True, delete=True)

        cmds.runTimeCommand(
            _HK_PRESS_CMD,
            annotation="Gus Animtool 5.8 Pie Press",
            category="User",
            command="import sys; m = sys.modules.get(%r); m and m.press()" % _REG_KEY,
            commandLanguage="python",
        )
        cmds.runTimeCommand(
            _HK_RELEASE_CMD,
            annotation="Gus Animtool 5.8 Pie Release",
            category="User",
            command="import sys; m = sys.modules.get(%r); m and m.release()" % _REG_KEY,
            commandLanguage="python",
        )
        p_nc = cmds.nameCommand(_HK_PRESS_NC, annotation="Pie Press", command=_HK_PRESS_CMD)
        r_nc = cmds.nameCommand(_HK_RELEASE_NC, annotation="Pie Release", command=_HK_RELEASE_CMD)
        cmds.hotkey(keyShortcut=key_str, name=p_nc, releaseName=r_nc, autoSave=False)
        _RUNTIME["bound_key"] = key_str
    except Exception as exc:
        print("[Gus Animtool 5.8 UI Test v3] Native hotkey note: %s" % exc)


def _unbind_native_hotkey(key_str=None):
    if not IN_MAYA:
        return
    key_str = key_str or _RUNTIME.get("bound_key", "grave")
    try:
        cmds.hotkey(keyShortcut=key_str, name="none", releaseName="none", autoSave=False)
    except Exception:
        pass
    for rtc in (_HK_PRESS_CMD, _HK_RELEASE_CMD):
        try:
            if cmds.runTimeCommand(rtc, exists=True):
                cmds.runTimeCommand(rtc, edit=True, delete=True)
        except Exception:
            pass


def _on_native_pie_press():
    pie = _RUNTIME.get("pie")
    if pie is not None and not pie.isVisible():
        pie.open_at_cursor()


def _on_native_pie_release():
    pie = _RUNTIME.get("pie")
    if pie is not None and pie.isVisible() and not pie.pinned_for_settings:
        under = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
        w = under
        while w is not None and w is not pie:
            if isinstance(w, ToolTile):
                pie._fire_and_close(w.action_key)
                return
            w = w.parentWidget()
        pie.close()


# ---------------------------------------------------------------------------
# Launcher & Maya Drag-and-Drop Entry Point
# ---------------------------------------------------------------------------
_RUNTIME = {}
DOCK_NAME = "gusAnimtool58TestDockControl"


def show_dock():
    state = _RUNTIME.get("state")
    if state is None:
        return
    if IN_MAYA:
        if cmds.workspaceControl(DOCK_NAME, exists=True):
            cmds.deleteUI(DOCK_NAME)
        cmds.workspaceControl(
            DOCK_NAME,
            label="Gus Animtool 5.8 (Test v3)",
            dockToMainWindow=("right", True),
            initialWidth=242,
            minimumWidth=72,
            retain=False,
        )
        ctrl_ptr = omui.MQtUtil.findControl(DOCK_NAME)
        if ctrl_ptr:
            parent_w = wrapInstance(int(ctrl_ptr), QtWidgets.QWidget)
            dock_w = AnimtoolDockWidget(state, parent_w)
            dock_w.openSearchRequested.connect(_open_search)
            parent_w.layout().addWidget(dock_w)
            _RUNTIME["dock"] = dock_w
            return dock_w
    dock_w = AnimtoolDockWidget(state)
    dock_w.openSearchRequested.connect(_open_search)
    dock_w.resize(242, 680)
    dock_w.show()
    _RUNTIME["dock"] = dock_w
    return dock_w


def _open_search():
    state = _RUNTIME.get("state")
    if state:
        dlg = FuzzySearchDialog(state, _RUNTIME.get("dock") or _maya_main_window())
        dlg.exec() if IS_QT6 else dlg.exec_()


def _rebind_hotkey(new_key):
    state = _RUNTIME.get("state")
    if not state:
        return
    _unbind_native_hotkey()
    state.pie_hotkey = new_key
    _bind_native_hotkey(new_key)
    _toast("Pie trigger key bound to: %s (autoSave=False)" % new_key)
    state.changed.emit()


def cleanup():
    _unbind_native_hotkey()
    for k in ("bar", "pie"):
        w = _RUNTIME.pop(k, None)
        if w:
            try:
                w.close()
                w.deleteLater()
            except Exception:
                pass
    if IN_MAYA and cmds.workspaceControl(DOCK_NAME, exists=True):
        try:
            cmds.deleteUI(DOCK_NAME)
        except Exception:
            pass


def show_all():
    cleanup()
    state = MockState()
    _RUNTIME["state"] = state

    bar = FloatingBar(state)
    pie = RadialPieMenu(state)

    bar.openPieRequested.connect(pie.open_at_cursor)
    bar.openDockRequested.connect(show_dock)
    bar.openSearchRequested.connect(_open_search)
    bar.hotkeyChanged.connect(_rebind_hotkey)

    _RUNTIME["bar"] = bar
    _RUNTIME["pie"] = pie

    _bind_native_hotkey("grave")
    build_test_shelf(state.theme_name)

    scr = _screen_geometry(bar)
    bar.move(scr.left() + 140, scr.top() + 120)
    bar.show()
    show_dock()
    _toast("UI Test v3 Ready! All 58 shelf icons + dock tools loaded · Hold ` for Pie · Ctrl+Scroll bar to resize")


def onMayaDroppedPythonFile(*_args):
    show_all()


if __name__ == "__main__":
    if IN_MAYA:
        show_all()
    else:
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        show_all()
        app.exec() if IS_QT6 else app.exec_()