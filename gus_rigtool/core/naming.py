"""
Naming convention helpers.

Convention (taken from the Ribbon Rig Builder):
    sides  : prefix  L_ / R_   (also l_ / r_, and suffix _L / _R)
    types  : suffix  _ctrl, _ctrl_offset, _jnt, _bind, _grp ...
"""

import maya.cmds as cmds

CTRL = "_ctrl"
OFFSET = "_ctrl_offset"

# Longest first, so "_ctrl_offset" is stripped before "_offset" or "_ctrl".
TYPE_SUFFIXES = (
    "_ctrl_offset", "_offset", "_zero", "_sdk", "_ctrl", "_jnt", "_bind",
    "_grp", "_geo", "_loc", "_fol", "_crv",
)

_PREFIX_PAIRS = (("L_", "R_"), ("R_", "L_"), ("l_", "r_"), ("r_", "l_"))
_SUFFIX_PAIRS = (("_L", "_R"), ("_R", "_L"), ("_l", "_r"), ("_r", "_l"))
_MIDDLE_PAIRS = (("_L_", "_R_"), ("_R_", "_L_"), ("_l_", "_r_"), ("_r_", "_l_"))


def short_name(node):
    """'|grp|ns:L_arm_ctrl' -> 'ns:L_arm_ctrl'."""
    return node.split("|")[-1]


def split_namespace(name):
    """'ns:L_arm_ctrl' -> ('ns:', 'L_arm_ctrl')."""
    name = short_name(name)
    if ":" in name:
        ns, base = name.rsplit(":", 1)
        return ns + ":", base
    return "", name


# ---------------------------------------------------------------------------
# side swapping with your own search / replace pairs (Mirror tool)
# ---------------------------------------------------------------------------

DEFAULT_PAIRS = [("L_", "R_"), ("l_", "r_"), ("_L", "_R"), ("Left", "Right")]


def _swap_token(base, x, y):
    """Swap one side token in a name, by where it sits. None if it is not there."""
    if x.endswith("_") and not x.startswith("_"):          # prefix token, e.g. L_
        if base.startswith(x):
            return y + base[len(x):]
        if "_" + x in base:                                 # middle: arm_L_ctrl
            return base.replace("_" + x, "_" + y, 1)
        return None
    if x.startswith("_") and not x.endswith("_"):          # suffix token, e.g. _L
        if base.endswith(x):
            return base[:-len(x)] + y
        if x + "_" in base:                                 # middle: arm_L_ctrl
            return base.replace(x + "_", y + "_", 1)
        return None
    if x and x in base:                                     # anything else: Left, lf, _L_
        return base.replace(x, y, 1)
    return None


def mirror_name(node, pairs=None):
    """
    Other-side name of node using (left, right) pairs, in both directions.
    Every pair that matches is applied once. None if no pair matches (a centre name).
    """
    ns, base = split_namespace(node)
    new, changed = base, False
    for a, b in (pairs or DEFAULT_PAIRS):
        if not a or not b:
            continue
        for x, y in ((a, b), (b, a)):
            swapped = _swap_token(new, x, y)
            if swapped is not None:
                new, changed = swapped, True
                break
    return ns + new if changed else None


def side_of(node, pairs=None):
    """'L', 'R' or 'C' from the name."""
    base = split_namespace(node)[1]
    for a, b in (pairs or DEFAULT_PAIRS):
        if not a or not b:
            continue
        if _swap_token(base, a, b) is not None:
            return "L"
        if _swap_token(base, b, a) is not None:
            return "R"
    return "C"


def label_of(node, pairs=None):
    """Name without side and type suffix, for joint labels: 'R_arm_jnt' -> 'arm'."""
    base = split_namespace(strip_type_suffix(node))[1]
    for a, b in (pairs or DEFAULT_PAIRS):
        for tok in (a, b):
            if tok and _swap_token(base, tok, "") is not None:
                base = _swap_token(base, tok, "")
                return base.strip("_") or base
    return base


def strip_type_suffix(name):
    """'L_arm_jnt' -> 'L_arm' (namespace kept)."""
    ns, base = split_namespace(name)
    for suffix in TYPE_SUFFIXES:
        if base.endswith(suffix) and len(base) > len(suffix):
            return ns + base[:-len(suffix)]
    return ns + base


def unique(name):
    """name, or name1, name2 ... if it already exists."""
    if not cmds.objExists(name):
        return name
    i = 1
    while cmds.objExists("%s%d" % (name, i)):
        i += 1
    return "%s%d" % (name, i)


def ctrl_names(base):
    """(control name, offset name) for a base name, both unique."""
    return unique(base + CTRL), unique(base + OFFSET)
