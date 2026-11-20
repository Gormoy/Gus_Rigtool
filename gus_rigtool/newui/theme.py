"""The 5.7 look: a colour per area, Maya's axis colours, the dark palette - one stylesheet built from them."""

BG = "#1d1f22"
WIN = "#2b2e33"
PANEL = "#33373d"
CARD = "#3a3e45"
CARD_CLOSED = "#363a40"
LINE = "#4a4f57"
FIELD = "#202326"
TXT = "#e9ebee"
DIM = "#a2a7ae"
FAINT = "#7d838b"
SIDE = "#26292d"
BTN = "#4a4f57"
DANGER = "#b4544f"
WARN = "#e3bd3c"
OK = "#5fbf4f"

# (key, label, colour, icon, registry categories) - the rig's steps in order, then the toolbox
AREAS = [
    ("home", "Home", "#c9ccd1", "home", ["home"]),
    ("build", "Build", "#e0893a", "build", ["build"]),
    ("skin", "Skin", "#d8638c", "skin", ["skin"]),
    ("controls", "Controls", "#36b38a", "controls", ["controls"]),
    ("connect", "Connect", "#9b74dc", "connect", ["links"]),
    ("check", "Check & publish", "#e3bd3c", "check", ["finish"]),
    ("toolbox", "Toolbox", "#6f93bd", "toolbox", ["toolbox"]),
    ("settings", "Settings", "#8a9098", "gear", []),
]
AXIS = {"X": "#e2504a", "Y": "#5fbf4f", "Z": "#4c8fe0"}
KIND = {"joint": "#f0c85a", "control": "#6fd6b0", "mesh": "#9ec3f0", "other": "#cfd2d6"}
LEVEL = {"ok": "#2f5a35", "warn": "#6b5016", "idle": "#2a2d32", "info": "#2a2d32", "error": "#6b2a28",
         "made": "#2f5a35", "ready": "#5c5418"}             # 5.7.4 steps: done / your selection fits


def area(key):
    for a in AREAS:
        if a[0] == key:
            return a
    return AREAS[0]


def colour(key):
    return area(key)[2]


def mix(hex_a, hex_b, t):
    """hex_a toward hex_b by t (0..1)."""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def axis_of(label):
    """'X' for 'X', '+X', '-X', 'tx', 'rx'... else None."""
    s = str(label).strip().upper().lstrip("+-")
    if s in AXIS:
        return s
    if len(s) == 2 and s[0] in "TRS" and s[1] in AXIS:
        return s[1]
    return None


def stylesheet(accent):
    """The whole window's style, with this area's colour."""
    dark = mix(accent, "#000000", 0.35)
    soft = mix(accent, CARD, 0.75)
    return """
QWidget { color: %(TXT)s; font-size: 13px; }
QWidget#gusFrame, QWidget#gusPage, QScrollArea, QScrollArea > QWidget > QWidget { background: %(PANEL)s; }
QWidget#gusSide { background: %(SIDE)s; }
QLabel { background: transparent; }
QLabel[role="dim"] { color: %(DIM)s; }
QLabel[role="faint"] { color: %(FAINT)s; font-size: 11px; }
QLabel[role="sec"] { color: %(FAINT)s; font-size: 10px; letter-spacing: 1px; }
QFrame#gusCard { background: %(CARD)s; border-radius: 9px; border-left: 3px solid %(accent)s; }
QFrame#gusCard[closed="true"] { background: %(CARD_CLOSED)s; border-left: 3px solid %(LINE)s; }
QFrame#gusCard[inner="true"] { background: rgba(255,255,255,0.04); border-left: 2px solid rgba(255,255,255,0.12);
                               border-radius: 7px; }
QFrame#gusCard[inner="true"] QLabel#gusCardTitle { font-size: 13px; }
QFrame#gusCard[pinned="true"] { border-left: 3px solid #ffcf5c; background: #3d3a30; }
QLabel#gusNum { background: %(accent)s; color: #111; border-radius: 10px; font-weight: bold; font-size: 11px; }
QFrame#gusCard[closed="true"] QLabel#gusNum { background: #5a6069; }
QLabel#gusCardTitle { font-weight: bold; font-size: 14px; }
QLabel#gusTitle { font-weight: bold; font-size: 21px; }
QLabel#gusPeek { color: %(FAINT)s; font-size: 12px; }
QPushButton { background: %(BTN)s; border: none; border-radius: 6px; padding: 5px 11px; }
QPushButton:hover { background: #575d66; }
QPushButton:pressed { background: #3e434a; }
QPushButton:disabled { color: %(FAINT)s; background: #3a3e45; }
QPushButton[role="accent"] { background: %(soft)s; border: 1px solid %(accent)s; }
QPushButton[role="danger"] { background: #5a2f2d; border: 1px solid %(DANGER)s; }
QPushButton[role="big"] { background: %(accent)s; color: #111; font-weight: bold; font-size: 14px;
                          border-radius: 8px; padding: 9px 12px; border-bottom: 3px solid %(dark)s; }
QPushButton[role="big"] QLabel { color: #111; font-weight: bold; font-size: 14px; }
QPushButton[role="big"]:hover { background: %(hover)s; }
QPushButton[role="big"]:disabled { background: #4a4f57; color: %(DIM)s; border-bottom: 3px solid #33373d; }
QPushButton[role="help"], QToolButton[role="help"] { background: transparent; border: 1px solid %(LINE)s;
                          border-radius: 9px; color: %(FAINT)s; padding: 0px; min-width: 18px; max-width: 18px;
                          min-height: 18px; max-height: 18px; font-size: 11px; }
QPushButton[role="seg"] { background: #2e3237; border-radius: 0px; border: 1px solid %(LINE)s; padding: 4px 10px; }
QPushButton[role="seg"]:checked { background: %(accent)s; color: #111; font-weight: bold; }
QPushButton[role="tab"] { background: transparent; color: %(DIM)s; border-radius: 7px; padding: 7px 12px; }
QPushButton[role="tab"]:checked { background: %(PANEL)s; color: white; border-top: 3px solid %(accent)s; }
QPushButton[role="tab2"] { background: transparent; color: %(DIM)s; border-radius: 11px; padding: 4px 11px;
                          font-size: 12px; border: 1px solid transparent; }
QPushButton[role="tab2"]:checked { background: %(soft)s; color: white; border: 1px solid %(accent)s; }
QPushButton[role="tab2"]:hover { color: white; }
QPushButton[role="nav"] { background: transparent; text-align: left; padding: 6px 8px; border-radius: 6px;
                          color: #cfd2d6; border-left: 3px solid transparent; }
QPushButton[role="nav"]:checked { background: rgba(255,255,255,0.07); color: white; font-weight: bold; }
QLineEdit, QComboBox, QPlainTextEdit, QListWidget { background: %(FIELD)s; border: 1px solid %(LINE)s;
                          border-radius: 5px; padding: 3px 6px; selection-background-color: %(accent)s; }
QLineEdit:focus, QComboBox:focus { border: 1px solid %(accent)s; }
QComboBox QAbstractItemView { background: %(FIELD)s; selection-background-color: %(accent)s; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid #8a9098; }
QCheckBox::indicator:checked { background: %(accent)s; border: 1.5px solid %(accent)s; }
QSlider::groove:horizontal { height: 4px; background: %(LINE)s; border-radius: 2px; }
QSlider::handle:horizontal { background: %(accent)s; width: 12px; margin: -5px 0; border-radius: 6px; }
QToolTip { background: #111; color: %(TXT)s; border: 1px solid %(LINE)s; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #4d525b; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
QFrame#gusHead { border-top: 4px solid %(accent)s;
                 background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 %(headtop)s, stop:1 %(PANEL)s); }
QFrame#gusSel { background: #24272b; border-radius: 8px; }
QFrame#gusNext { background: %(nexttop)s; border: 1px dashed %(accent)s; border-radius: 8px; }
QLabel#gusLight { border-radius: 6px; padding: 6px 8px; }
QLabel#gusStatus { background: #24272b; padding: 4px 8px; }
""" % dict(globals(), accent=accent, dark=dark, soft=soft, hover=mix(accent, "#ffffff", 0.12),
           headtop=mix(accent, PANEL, 0.72), nexttop=mix(accent, "#24272b", 0.75))
