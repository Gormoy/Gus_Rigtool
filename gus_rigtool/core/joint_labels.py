"""
Joint labels and left / right symmetry - so skin mirroring (ngSkinTools, Maya's Mirror Skin Weights) pairs every
left joint with its right twin.

  label(joints)      : Maya's joint labels - Side (Left / Right / Center) and Other Type = the name without its
                       side ('L_eye' and 'R_eye' both get 'eye'). In ngSkinTools: Mirror > Influences mapping >
                       use joint labels; in Maya's Mirror Skin Weights: Influence association 'Label'.
  not_mirrored()     : left / right joint pairs (by name) that aren't mirror images in position - the reason a
                       mirror matched 'by distance' sends weights to the wrong joint.
"""

import maya.cmds as cmds

from gus_rigtool.core import utils
from gus_rigtool.core import nodes as _nodes

SIDES = {"C": 0, "L": 1, "R": 2}
PREFIXES = [("L_", "R_"), ("l_", "r_"), ("Lf_", "Rt_"), ("Left_", "Right_"), ("left_", "right_")]
SUFFIXES = [("_L", "_R"), ("_l", "_r"), ("_Lf", "_Rt"), ("_left", "_right"), ("_Left", "_Right")]


def _bare(n):
    return n.split("|")[-1].split(":")[-1]


def _pairs():
    """The built-in side tokens plus the ones in your settings (Mirror: search / replace)."""
    pre, suf = list(PREFIXES), list(SUFFIXES)
    try:
        from gus_rigtool.core import sides
        for a, b in sides.default_pairs():
            if a and b and a.endswith("_") and (a, b) not in pre:
                pre.insert(0, (a, b))
            elif a and b and a.startswith("_") and (a, b) not in suf:
                suf.insert(0, (a, b))
    except Exception:
        pass
    return pre, suf


def split_side(name):
    """'L_eye' -> ('L', 'eye'); 'Head' -> ('C', 'Head')."""
    base = _bare(name)
    PREFIXES, SUFFIXES = _pairs()
    for l_tok, r_tok in PREFIXES:
        for side, tok in (("L", l_tok), ("R", r_tok)):
            if base.startswith(tok) and len(base) > len(tok):
                return side, base[len(tok):]
    for l_tok, r_tok in SUFFIXES:
        for side, tok in (("L", l_tok), ("R", r_tok)):
            if base.endswith(tok) and len(base) > len(tok):
                return side, base[:-len(tok)]
    return "C", base


def twin_name(name):
    """The other side's name ('L_eye' -> 'R_eye'), or None for a centre joint."""
    base = _bare(name)
    ns = name.split("|")[-1][:-len(base)]
    PREFIXES, SUFFIXES = _pairs()
    for l_tok, r_tok in PREFIXES:
        for a, b in ((l_tok, r_tok), (r_tok, l_tok)):
            if base.startswith(a) and len(base) > len(a):
                return ns + b + base[len(a):]
    for l_tok, r_tok in SUFFIXES:
        for a, b in ((l_tok, r_tok), (r_tok, l_tok)):
            if base.endswith(a) and len(base) > len(a):
                return ns + base[:-len(a)] + b
    return None


def _label_name(base):
    """The label text: the name without side and without the joint suffix ('eye_jnt' -> 'eye')."""
    for sx in ("_jnt", "_JNT", "_joint", "_Jnt", "_bind", "_BND"):
        if base.endswith(sx) and len(base) > len(sx):
            return base[:-len(sx)]
    return base


_pos = _nodes.world_pos


def label(joints, report=None):
    """Side + Other Type labels on the joints. Returns how many were labelled.
    By name: 'L_eye' / 'R_eye' -> Left / Right, both 'eye'. Joints with no side in their name (one ribbon across the
    mouth: Mouth_fol_07 at +X, Mouth_fol_15 at -X) pair by position: mirrored twins get the same label, the ones
    on the centre line are Center. report: a list that gets (joint, why) for joints left without a twin."""
    joints = utils.ls(joints, type="joint", long=True) or []
    pos = dict((j, _pos(j)) for j in joints)
    ys = [p[1] for p in pos.values()] or [0.0]
    tol = max(0.01, (max(ys) - min(ys)) * 0.005)               # 0.5% of the height
    named_l = [pos[j][0] for j in joints if split_side(j)[0] == "L"]
    left_sign = 1.0 if not named_l or sum(named_l) >= 0 else -1.0  # which side of X is 'left' in this rig
    n = 0

    def put(j, side, text):
        try:
            cmds.setAttr(j + ".side", SIDES[side])
            cmds.setAttr(j + ".type", 18)                        # Other: the name below is the label
            cmds.setAttr(j + ".otherType", text, type="string")
            return 1
        except RuntimeError:
            return 0

    by_name = set(_bare(j) for j in joints)
    loose = []
    for j in joints:
        side, base = split_side(j)
        if side == "C":
            loose.append(j)
            continue
        n += put(j, side, _label_name(base))
        if report is not None and _bare(twin_name(j) or "") not in by_name:
            report.append((j, "no %s twin by name" % ("right" if side == "L" else "left")))
    # no side in the name: by position, within the same name pattern (_jnt with _jnt, _bind with _bind)
    import re
    centre_tol = tol
    groups = {}
    for j in loose:
        groups.setdefault(re.sub(r"\d+", "#", _bare(j)), []).append(j)
    for _pattern, members in groups.items():
        centre = [j for j in members if abs(pos[j][0]) <= centre_tol]
        lefts = [j for j in members if j not in centre and pos[j][0] * left_sign > 0]
        rights = [j for j in members if j not in centre and j not in lefts]
        for j in centre:
            n += put(j, "C", _bare(j))
        # how far apart neighbours are: a twin a quarter of that off is still the twin
        gaps = []
        for j in members:
            d = [sum((a - b) ** 2 for a, b in zip(pos[j], pos[k])) ** 0.5 for k in members if k != j]
            if d:
                gaps.append(min(d))
        spacing = sorted(gaps)[len(gaps) // 2] if gaps else 0.0
        pair_tol = max(tol, spacing * 0.25)
        free = list(rights)
        for j in sorted(lefts, key=lambda x: _bare(x)):
            a = pos[j]
            best, dist = None, None
            for r in free:
                b = pos[r]
                d = max(abs(a[0] + b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
                if dist is None or d < dist:
                    best, dist = r, d
            text = _bare(j)                  # the full name: _jnt and _bind twins never share a label
            n += put(j, "L", text)
            if best is not None and dist <= pair_tol:
                free.remove(best)
                n += put(best, "R", text)
            elif report is not None:
                report.append((j, "no mirrored joint on the other side (by position)"))
        for r in free:
            n += put(r, "R", _bare(r))
            if report is not None:
                report.append((r, "no mirrored joint on the other side (by position)"))
    return n


def skin_joints(mesh_only=False):
    """Every joint any skin in the scene uses. mesh_only (5.0.5): only skins on meshes - not the joints that drive a
    ribbon surface (those never get mirrored skin weights)."""
    out = []
    for skin in cmds.ls(type="skinCluster") or []:
        if mesh_only:
            geo = cmds.skinCluster(skin, query=True, geometry=True) or []
            if not geo or cmds.nodeType(geo[0]) != "mesh":
                continue
        for j in utils.ls(cmds.skinCluster(skin, query=True, influence=True) or [], type="joint", long=True) or []:
            if j not in out:
                out.append(j)
    return out


def rig_joints():
    """The rig's bind joints (skeleton_grp) and every joint a skin uses."""
    from gus_rigtool.core.skin_tools import rig_joints as bind
    out = list(bind())
    out += [j for j in skin_joints() if j not in out]
    return out


def not_mirrored(joints=None, tol=None, axis=0):
    """[(left joint, right joint, how far off)] for twin pairs whose positions don't mirror across the axis
    (X by default), and [(left joint, None, None)] for a side joint with no twin by name."""
    joints = utils.ls(joints if joints is not None else rig_joints(), type="joint", long=True) or []
    if tol is None:
        ys = [cmds.xform(j, query=True, worldSpace=True, translation=True)[1] for j in joints] or [0.0]
        tol = max(0.001, (max(ys) - min(ys)) * 0.001)
    out, seen = [], set()
    for j in joints:
        side, _base = split_side(j)
        if side != "L" or j in seen:
            continue
        other = twin_name(j)
        found = cmds.ls(other, type="joint", long=True) or [] if other else []
        if len(found) != 1:
            out.append((j, None, None))
            continue
        r = found[0]
        seen.update((j, r))
        a = cmds.xform(j, query=True, worldSpace=True, translation=True)
        b = cmds.xform(r, query=True, worldSpace=True, translation=True)
        b = list(b)
        b[axis] = -b[axis]
        off = max(abs(x - y) for x, y in zip(a, b))
        if off > tol:
            out.append((j, r, off))
    return out


def twin_count(joint):
    """How many joints carry this joint's twin name (5.0.5): 0 = no twin, over 1 = the name is used twice."""
    other = twin_name(joint)
    return len(cmds.ls(other, type="joint", long=True) or []) if other else 0


def add_twins(joints=None):
    """For each left / right joint with no twin by name (L_Humerus_Cor but no R_Humerus_Cor): its mirror image
    is made (across X, mirrored behaviour), under the twin of its parent, added to the same skins with weight 0,
    and labelled. Returns the new joints."""
    joints = utils.ls(joints if joints is not None else rig_joints(), type="joint", long=True)
    made = []
    for j in joints:
        side, _base = split_side(j)
        other = twin_name(j)
        if side == "C" or not other or cmds.ls(other):
            continue
        parent = (cmds.listRelatives(j, parent=True, fullPath=True) or [None])[0]
        twin_parent = parent
        if parent:
            pn = twin_name(parent)
            found = cmds.ls(pn, long=True) if pn else []
            if found:
                twin_parent = found[0]
        tmp = cmds.duplicate(j, parentOnly=True, name=_bare(j) + "_gusTmp")[0]
        try:
            got = cmds.mirrorJoint(tmp, mirrorYZ=True, mirrorBehavior=True) or []
        finally:
            if cmds.objExists(tmp):
                cmds.delete(tmp)
        if not got:
            continue
        new = cmds.ls(got[0], long=True)[0]
        new = cmds.rename(new, _bare(other))
        new = cmds.ls(new, long=True)[0]
        if twin_parent and (cmds.listRelatives(new, parent=True, fullPath=True) or [None])[0] != twin_parent:
            new = cmds.ls(cmds.parent(new, twin_parent)[0], long=True)[0]
        for skin in set(cmds.listConnections(j + ".worldMatrix", type="skinCluster") or []):
            try:
                cmds.skinCluster(skin, edit=True, addInfluence=new, weight=0.0, lockWeights=False)
            except RuntimeError:
                pass
        label([j, new])
        made.append(new)
    return made
