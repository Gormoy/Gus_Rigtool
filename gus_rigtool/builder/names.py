"""
Names of everything the builder makes, from a pattern you can change.

Pattern tokens:
    {side}  the side token from your naming pairs (L_ / R_), or the centre token
    {part}  the part name: humerus, index_01... plus a variant (_FK, _IK...) when there is one
    {type}  the type suffix: _jnt, _ctrl, _grp...

Default: "{side}{part}{type}"  ->  L_humerus_jnt, L_humerus_FK_ctrl, spine_jnt
"""

from gus_rigtool.core import sides, utils

SETTINGS_KEY = "build_names"

DEFAULTS = {
    "pattern": "{side}{part}{type}",
    "centre": "",                      # side token for centre parts (e.g. "C_")
    "suffixes": {
        "jnt": "_jnt",                 # bind joints
        "ctrl": "_ctrl",
        "offset": "_offset",
        "grp": "_grp",
        "gde": "_gde",                 # guides
        "loc": "_loc",
        "ik": "_ikHandle",
        "crv": "_crv",
        "srf": "_srf",
        "fol": "_fol",
    },
    "variants": {
        "fk": "_FK",
        "ik": "_IK",
        "pv": "_PV",
        "settings": "_settings",
        "space": "_space",
        "drv": "_drv",
        "twist": "_twist",
        "bend": "_bend",
        "tweak": "_tweak",
        "hock": "_hock",
        "result": "_result",
    },
}


def settings():
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)
    for key in ("suffixes", "variants"):
        merged = dict(DEFAULTS[key])
        merged.update(s.get(key) or {})
        s[key] = merged
    return s


def side_token(side, s=None):
    s = s or settings()
    if side == "C":
        return s.get("centre", "")
    left, right = sides.default_pairs()[0]
    return left if side == "L" else right


def make(side, part, kind="jnt", variant=None, s=None):
    """Name of a node: make('L', 'humerus', 'ctrl', 'fk') -> 'L_humerus_FK_ctrl'."""
    s = s or settings()
    part = part + (s["variants"].get(variant, variant or "") if variant else "")
    suffix = s["suffixes"].get(kind, "_" + kind if kind else "")
    try:
        name = s["pattern"].format(side=side_token(side, s), part=part, type=suffix)
    except (KeyError, IndexError, ValueError):
        name = DEFAULTS["pattern"].format(side=side_token(side, s), part=part, type=suffix)
    return name.replace("__", "_")


def check_pattern(pattern):
    """'' if the pattern is fine, else what's wrong with it."""
    if "{part}" not in pattern:
        return "the pattern needs {part}"
    try:
        pattern.format(side="L_", part="x", type="_jnt")
    except (KeyError, IndexError, ValueError) as e:
        return "unknown token in the pattern (%s); use {side}, {part}, {type}" % e
    return ""
