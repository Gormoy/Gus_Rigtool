"""
Which side a node is on, and who its twin is, even when the name has no L_ / R_.

Side:  from the name first; if the name has no side token, from the world position
       (+X = Left, -X = Right, within the tolerance of the centre = Centre).
Twin:  mirrored pairs are linked with a hidden message attribute (rtMirrorTwin), so the
       twin is found again even after renaming. Names are the fallback.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

TWIN_ATTR = "rtMirrorTwin"


# ---------------------------------------------------------------------------
# settings shared with the Mirror tab
# ---------------------------------------------------------------------------

def mirror_settings():
    return utils.tool_settings("mirror", {})


def default_pairs():
    s = mirror_settings()
    pairs = [(s.get("search") or "L_", s.get("replace") or "R_")]
    if s.get("search2") and s.get("replace2"):
        pairs.append((s["search2"], s["replace2"]))
    return pairs


def tolerance():
    return float(mirror_settings().get("tolerance", 0.01))


# ---------------------------------------------------------------------------
# side
# ---------------------------------------------------------------------------

def has_side(node, pairs):
    return naming.mirror_name(node, pairs) is not None


def shape_center(node):
    """World centre of a node's own shapes (CVs / vertices), or None if it has none."""
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    if not shapes:
        return None
    try:
        bb = cmds.exactWorldBoundingBox(shapes)
    except RuntimeError:
        return None
    return [(bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0]


def side_from_position(node, axis=0, center=(0.0, 0.0, 0.0), tol=None):
    """
    Side from the pivot. When the pivot is in the middle (e.g. a frozen control whose
    pivot stayed at the origin), the centre of its shape decides instead.
    """
    tol = tolerance() if tol is None else tol

    def classify(p):
        d = p[axis] - center[axis]
        return "L" if d > tol else ("R" if d < -tol else "C")

    side = classify(cmds.xform(node, query=True, worldSpace=True, rotatePivot=True))
    if side == "C":
        sc = shape_center(node)
        if sc is not None:
            side = classify(sc)
    return side


def side_of_node(node, pairs=None, axis=0, center=(0.0, 0.0, 0.0), tol=None):
    """'L', 'R' or 'C': from the name, else from the position."""
    pairs = pairs or default_pairs()
    if has_side(node, pairs):
        return naming.side_of(node, pairs)
    return side_from_position(node, axis, center, tol)


def add_side(name, side, pair):
    """
    Put a side token into a name that has none, following the token's shape:
    'L_' -> prefix (L_arm_ctrl), '_L' -> suffix (arm_ctrl_L), anything else -> prefix.
    """
    ns, base = naming.split_namespace(name)
    token = pair[0] if side == "L" else pair[1]
    if not token:
        return ns + base
    if token.startswith("_") and not token.endswith("_"):
        return ns + base + token
    if "_" not in token and base:                    # word token: Left + arm -> LeftArm
        return ns + token + base[0].upper() + base[1:]
    return ns + token + base


# ---------------------------------------------------------------------------
# twin link
# ---------------------------------------------------------------------------

def get_twin(node):
    if not cmds.attributeQuery(TWIN_ATTR, node=node, exists=True):
        return None
    found = cmds.listConnections(node + "." + TWIN_ATTR, source=True, destination=False) or []
    if not found:
        return None
    return cmds.ls(found[0], long=True)[0]


def name_twin(node, pairs=None):
    """The node with the mirrored name (L_ <-> R_), if exactly one exists."""
    name = naming.mirror_name(node, pairs or default_pairs())
    if not name:
        return None
    found = cmds.ls(name, long=True) or []
    return found[0] if len(found) == 1 else None


def link_by_position(nodes, candidates, axis=0, center=(0.0, 0.0, 0.0)):
    """5.0.6: link each node with no twin to the candidate at its mirrored position (the Hare's mouth loop:
    L_Mouth_fol_02_ctrl <-> Mouth_fol_26_ctrl). Controls are compared where their pivots are (at rest).
    Returns [(node, twin)] linked."""
    def pos(n):
        return cmds.xform(n, query=True, worldSpace=True, rotatePivot=True)
    cand = {}
    for c in candidates:
        if checked_twin(c)[0]:
            continue
        try:
            cand[c] = pos(c)
        except (RuntimeError, ValueError):
            pass
    ys = [p[1] for p in cand.values()] or [0.0]
    tol = max(0.01, (max(ys) - min(ys)) * 0.002)
    cand = dict((c, p) for c, p in cand.items() if abs(p[axis] - center[axis]) > tol)
    gaps = []
    for c in cand:
        d = [max(abs(x - y) for x, y in zip(cand[c], cand[k])) for k in cand if k != c]
        if d:
            gaps.append(min(d))
    pair_tol = max(tol, (sorted(gaps)[len(gaps) // 2] if gaps else 0.0) * 0.25)
    done = []
    used = set()
    for n in nodes:
        if n not in cand or n in used:
            continue
        p = list(cand[n])
        p[axis] = 2 * center[axis] - p[axis]
        best, dist = None, None
        for k in cand:
            if k == n or k in used:
                continue
            d = max(abs(x - y) for x, y in zip(p, cand[k]))
            if dist is None or d < dist:
                best, dist = k, d
        if best is not None and dist <= pair_tol:
            link(n, best)
            used.update((n, best))
            done.append((n, best))
    return done


def checked_twin(node, pairs=None):
    """(twin, note). The twin link, unless the node with the mirrored name exists and is another node:
    then the name wins (a link can be left wrong, e.g. a group added after mirroring) and note says so."""
    linked = get_twin(node)
    by_name = name_twin(node, pairs)
    if linked and by_name and by_name != linked:
        return by_name, "by name: link pointed to %s" % naming.short_name(linked)
    return linked or by_name, None


def bad_links(nodes=None, pairs=None):
    """[(node, linked, by_name)] whose twin link disagrees with the mirrored name. by_name None: the
    mirrored name doesn't exist (rename the other side, or link it by hand)."""
    if nodes is None:
        nodes = cmds.ls("*." + TWIN_ATTR, recursive=True, objectsOnly=True, long=True) or []
    out = []
    for n in nodes:
        linked = get_twin(n)
        if not linked:
            continue
        name = naming.mirror_name(n, pairs or default_pairs())
        if name is None:                                  # centre / no side in the name: nothing to compare
            continue
        if naming.short_name(linked) != naming.short_name(name):
            out.append((n, linked, name_twin(n, pairs)))
    return out


def _unlink_all(node):
    if cmds.objExists(node) and cmds.attributeQuery(TWIN_ATTR, node=node, exists=True):
        for src in cmds.listConnections(node + "." + TWIN_ATTR, source=True, destination=False, plugs=True) or []:
            try:
                cmds.disconnectAttr(src, node + "." + TWIN_ATTR)
            except RuntimeError:
                pass


def fix_links(nodes=None, pairs=None):
    """Relink every node whose link disagrees with its mirrored name (when that node exists); the old
    partner's link back to it goes too. Returns (fixed [(node, new twin)], left [(node, linked, wanted)])."""
    fixed = []
    for n, _linked, by_name in bad_links(nodes, pairs):
        if not by_name or not cmds.objExists(n):
            continue
        if get_twin(n) == by_name and get_twin(by_name) == n:
            continue                                     # already fixed from the other side
        for x in (n, by_name):
            old = get_twin(x)
            _unlink_all(x)
            if old and get_twin(old) == x:
                _unlink_all(old)                         # the old partner pointed back: free it too
        link(n, by_name)
        fixed.append((n, by_name))
    left = [(n, linked, naming.mirror_name(n, pairs or default_pairs()))
            for n, linked, by_name in bad_links(nodes, pairs)]
    return fixed, left


def link(a, b):
    """Link two nodes as mirror twins (both directions)."""
    for x, y in ((a, b), (b, a)):
        if not cmds.attributeQuery(TWIN_ATTR, node=y, exists=True):
            cmds.addAttr(y, longName=TWIN_ATTR, attributeType="message", hidden=True)
        try:
            cmds.connectAttr(x + ".message", y + "." + TWIN_ATTR, force=True)
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# plan: what a node becomes on the other side
# ---------------------------------------------------------------------------

def plan(node, pairs, axis=0, center=(0.0, 0.0, 0.0), rename_source=True, side=None):
    """
    {'side', 'rename_to', 'target_name', 'existing'} for node, or None for a centre node.
      rename_to   : new name for the source (only when its name had no side), else None
      target_name : name of the other-side node
      existing    : long name of the other-side node if it exists, else None
    side forces a side for nodes whose name and position say nothing (e.g. offset groups).
    """
    twin, note = checked_twin(node, pairs)
    if twin and (note or get_twin(node)):
        s = side_of_node(node, pairs, axis, center)
        rename_to = None
        if rename_source and not has_side(node, pairs) and s in ("L", "R"):
            rename_to = add_side(naming.short_name(node), s, pairs[0])
        return {"side": s, "rename_to": rename_to,
                "target_name": naming.short_name(twin), "existing": twin, "note": note}

    name = naming.mirror_name(node, pairs)
    if name is not None:
        found = cmds.ls(name, long=True) or []
        return {"side": naming.side_of(node, pairs), "rename_to": None,
                "target_name": name, "existing": found[0] if len(found) == 1 else None,
                "ambiguous": len(found) > 1}

    s = side or side_from_position(node, axis, center)
    if s not in ("L", "R"):
        return None
    short = naming.short_name(node)
    other = "R" if s == "L" else "L"
    rename_to = add_side(short, s, pairs[0]) if rename_source else None
    target = add_side(short, other, pairs[0])
    found = cmds.ls(target, long=True) or []
    return {"side": s, "rename_to": rename_to, "target_name": target,
            "existing": found[0] if len(found) == 1 else None, "ambiguous": len(found) > 1}


def apply_rename(node, new_name):
    """Rename node (keeps working by UUID). Returns the node's long name."""
    nid = utils.uuid(node)
    try:
        cmds.rename(node, new_name)
    except RuntimeError as e:
        utils.warn("Mirror", "could not rename '%s' (%s)." % (naming.short_name(node), e))
    return utils.path(nid)
