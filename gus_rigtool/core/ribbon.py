"""
Ribbon rig logic (ported from Gus's Ribbon Rig Builder, behaviour kept).

Builds follicles, joints, controls, bind joints and a skin cluster on a NURBS ribbon;
mirrors a build to the other side; deletes builds; and the surface tools (plane, edge to
curve, curve check / fix, loft, swap U/V, flip normals).

Everything a build creates is tagged with its ribbon (rrbSurface, rrbSkin, rrbSettings,
rrbIndex - the same tags as the original tool), so builds made with the original script
are still found by Delete / Mirror / Rebuild.

Changes from the original:
  - control shapes come from the Shape Library (old names Circle / Square / ... still work)
  - follicle distribution 'length': evenly spaced by length along the ribbon
  - optional side colours, and Mirror build naming with the Gus_Rigtool name pairs
    (side from the position when the prefix has none) + twin links between L and R
  - messages go to the Gus_Rigtool status line
"""

import json

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import colors, curves, mirror_engine, naming, shape_data, sides, utils

TOOL = "Ribbon"
AXES = {'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}
JOINT_ONLY = 'None (joint only)'      # no curve: the joint itself is the control
OLD_SHAPES = {'Circle': 'circle', 'Square': 'square', 'Diamond': 'diamond', 'Cube': 'cube'}
AUTO_COUNTS = {'span': 'One per span (even)', 'cv': 'One per CV row (original)'}
DISTRIBUTIONS = {'auto': 'Auto (CV rows / even U)', 'length': 'Even by length'}


def shape_names():
    """Library shape names (built-in, then your saved ones), then joint-only."""
    names = [n for _c, items in shape_data.builtin_shapes() for n, _d in items]
    try:
        from gus_rigtool.tools.shape_library import load_custom
        names += sorted(n for n in load_custom() if n not in names)
    except Exception:
        pass
    return names + [JOINT_ONLY]


SHAPES = shape_names
# how a joint-only control reaches the ribbon: label in the window -> value
CONNECT = {'Skin directly': 'skin', 'Constrain a bind joint': 'constrain'}

DEFAULTS = {
    'prefix': '',
    'num_follicles': 0,            # 0 = one follicle per CV row
    'v_pos': 0.5,                  # position across the width
    'make_joints': True,
    'make_ctrls': True,
    'make_skin': True,
    'make_groups': True,
    'ribbon_group': True,          # the whole build (ribbon included) in one <prefix>_ribbon_grp
    'group_parent': '',            # put that group under this node (e.g. controls_grp); empty = the world
    'ctrl_mode': 'every',          # 'every' or 'list'
    'ctrl_every': 2,
    'ctrl_list': '1, 4, 7',        # joint numbers, counting from 1
    'include_ends': False,         # always give the first and last joint a control
    'ctrl_shape': 'Circle',
    'joint_connect': 'skin',       # joint-only controls: 'skin' (control joint skinned) or 'constrain'
    'ctrl_radius': 1.0,
    'ctrl_distance': 3.0,
    'dir_axis': 'Z',
    'face_axis': 'Z',
    'color': [1.0, 1.0, 0.0],
    'lock_hide': True,             # lock and hide scale + visibility on the controls
    'fol_jnt_radius': 0.5,
    'bind_jnt_radius': 1.0,
    'mirror_axis': 'X',            # the mirror plane is perpendicular to this axis, through the origin
    'mirror_prefix': '',           # empty = swap L_ and R_ in the prefix
    'mirror_color': [0.2, 0.5, 1.0],
    'mirror_style': 'true',        # 'true' (reflected, -1 scale, like the original) or 'behavior'
    'rebuild_mirror': True,        # Rebuild on the first side also rebuilds its mirror
    'distribution': 'auto',        # 'auto' (CV rows, or even U with a count) or 'length'
    'auto_count': 'span',          # count 0: 'span' (one per span, even) or 'cv' (one per CV row, original)
    'use_side_colors': False,      # colour controls with the Gus_Rigtool side colours
    'pivot_on_shape': False,       # the control's pivot sits on its shape; the bind joint follows by point + orient constraints
    'pivot_scale': False,          # with pivot_on_shape: the bind joint copies the control directly (translate, rotate, scale)
    'made_by': '',                 # who made the build (e.g. 'Face kit: Mouth_ribbon'), shown in the Ribbon tab
}

# The settings the Face kit builds its ribbons with (sizes are scaled to the strip there). The Ribbon tab's
# 'Face kit setup' button loads the same ones.
FACE_KIT = {
    'ctrl_mode': 'every', 'make_joints': True, 'make_ctrls': True, 'make_skin': True, 'make_groups': True,
    'ribbon_group': True, 'distribution': 'length', 'ctrl_shape': 'circle', 'face_axis': 'Z',
    'use_side_colors': True, 'mirror_style': 'behavior', 'pivot_on_shape': False, 'pivot_scale': False,
}


def builds_list():
    """[(ribbon, settings, number of controls)] for every build in the scene, sorted by name."""
    out = []
    for key, build in _find_builds().items():
        st = _build_settings(build) or {}
        out.append((key, st, len(_build_offsets(build))))
    return sorted(out, key=lambda r: r[0].split('|')[-1])

# the ribbon of the last build made in this session (used when nothing useful is selected)
_last = {'surface': None}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _control_indices(n, mode, every, list_text, include_ends):
    """Zero-based follicle indexes that get a control."""
    if mode == 'list':
        idx = []
        for tok in list_text.replace(';', ',').split(','):
            tok = tok.strip()
            if not tok:
                continue
            try:
                idx.append(int(tok) - 1)             # the window counts from 1
            except ValueError:
                raise ValueError('Control list: "%s" is not a whole number.' % tok)
        idx = [i for i in idx if 0 <= i < n]
    else:
        idx = list(range(0, n, max(1, int(every))))

    if include_ends:
        idx += [0, n - 1]
    return sorted(set(idx))


def _library_shape(name):
    name = OLD_SHAPES.get(name, name)
    for _c, items in shape_data.builtin_shapes():
        for n, data in items:
            if n == name:
                return data
    try:
        from gus_rigtool.tools.shape_library import load_custom
        custom = load_custom()
        if name in custom:
            return custom[name]
    except Exception:
        pass
    raise ValueError('Unknown control shape "%s".' % name)


def _make_control(name, shape, face_axis, radius):
    """Create a control curve (a Shape Library shape) and return its transform."""
    data = shape_data.scale(shape_data.face(_library_shape(shape), face_axis), float(radius))
    node = curves.create_curve_control(name, data, {})
    return naming.short_name(node)


def _bspline_point(u, degree, knots, points):
    """Point on a B-spline curve (de Boor). knots is the full vector: len(points) + degree + 1."""
    n = len(points)
    k = degree
    while k < n - 1 and u >= knots[k + 1]:
        k += 1
    d = [list(points[j + k - degree]) for j in range(degree + 1)]
    for r in range(1, degree + 1):
        for j in range(degree, r - 1, -1):
            i = j + k - degree
            denom = knots[j + 1 + k - r] - knots[i]
            a = 0.0 if denom == 0 else (u - knots[i]) / denom
            d[j] = [(1.0 - a) * d[j - 1][c] + a * d[j][c] for c in range(3)]
    return d[degree]


def _cv_row_params(surf, shape, degU, spans, minU, maxU, n):
    """
    U (0-1) of the first n CV rows: for each row, the point on the ribbon's centre line that is
    closest to the centre of that row. The follicles then sit right on the CV rows, instead of at
    the knot averages, which bunch up at both ends of an open cubic ribbon.
    Plain Python maths on the CV positions and knots, so nothing here can crash Maya.
    """
    n_total = spans + degU
    rng = float(maxU - minU)

    mlist = om.MSelectionList()
    mlist.add(shape)
    knots = list(om.MFnNurbsSurface(mlist.getDagPath(0)).knotsInU())
    greville = [(sum(knots[i:i + degU]) / float(degU) - minU) / rng for i in range(n)]

    full = [knots[0]] + knots + [knots[-1]]          # Maya leaves out the first and last knot
    if len(full) != n_total + degU + 1:
        return greville                               # unusual knot vector: keep the older spacing

    # centre line: the middle of each CV row across the width
    cols = max(1, cmds.getAttr(shape + '.spansV') + cmds.getAttr(shape + '.degreeV'))
    centre = []
    for i in range(n_total):
        pts = [cmds.pointPosition('%s.cv[%d][%d]' % (surf, i, j), local=True) for j in range(cols)]
        centre.append([sum(p[c] for p in pts) / float(cols) for c in range(3)])

    lo, hi = full[degU], full[-degU - 1]
    steps = max(200, 20 * n_total)
    ts = [lo + (hi - lo) * k / float(steps) for k in range(steps + 1)]
    samples = [_bspline_point(t, degU, full, centre) for t in ts]

    def dist2(p, q):
        return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2

    params = []
    for i in range(n):
        q = centre[i]
        best = min(range(len(ts)), key=lambda k: dist2(samples[k], q))
        a, b = ts[max(best - 1, 0)], ts[min(best + 1, steps)]
        for _ in range(40):                           # narrow down between the neighbouring samples
            m1 = a + (b - a) / 3.0
            m2 = b - (b - a) / 3.0
            if dist2(_bspline_point(m1, degU, full, centre), q) < dist2(_bspline_point(m2, degU, full, centre), q):
                b = m2
            else:
                a = m1
        params.append(min(1.0, max(0.0, ((a + b) / 2.0 - minU) / rng)))
    return params


_SIDES = (('L_', 'R_'), ('R_', 'L_'), ('l_', 'r_'), ('r_', 'l_'))


def _swap_side(name):
    """'L_Eyez' -> 'R_Eyez' (and back), with the Gus_Rigtool name pairs. None if no side."""
    return naming.mirror_name(name, sides.default_pairs())


MIRROR_STYLES = {'true': 'True mirror (-1 scale)', 'behavior': 'Behavior (no -1 scale)'}


def _mirror_matrix(m, axis_index, style='true'):
    """
    The twin control's offset matrix. 'true': the reflection itself (negative scale), exactly like
    the original tool. 'behavior': the reflection with all three axes turned round, so there is no
    negative scale (like Maya's joint Behavior mirror): the same rotate values mirror, the same
    translate values go the opposite way. (The shared Gus_Rigtool mirror engine.)
    """
    return mirror_engine.mirror_list(m, style if style in MIRROR_STYLES else 'true', axis_index)


def _mirror_matrices(build, axis_index, style='true'):
    """{follicle index: twin offset matrix} for every control of a build."""
    return {index: _mirror_matrix(cmds.xform(offset, query=True, worldSpace=True, matrix=True),
                                  axis_index, style)
            for index, offset in _build_offsets(build).items()}


def _make_bind(fol, ctrl, fol_matrix, radius, as_child):
    """
    Bind joint of a control. Normally it sits on the ribbon, at the follicle, and a parent
    constraint from the control drives it. On a mirrored build it is a child of the control
    instead (the control's pivot is already on the joint), because a constraint can twist when it
    reads a mirrored control.
    """
    cmds.select(clear=True)
    bind = cmds.joint(name=fol + '_bind')
    cmds.setAttr(bind + '.radius', radius)
    if as_child:
        return cmds.parent(bind, ctrl, relative=True)[0]
    cmds.xform(bind, worldSpace=True, matrix=fol_matrix)
    cmds.parentConstraint(ctrl, bind, maintainOffset=True)
    return bind


def _make_bind_on_shape(fol, ctrl, fol_matrix, radius):
    """
    Bind joint of a control whose pivot sits on its shape: on the ribbon at the follicle, driven by a
    point constraint (follows the control's moves, no swing round the shape's pivot) and an orient
    constraint (turns in place by the control's rotation), both keeping the offset. Works on mirrored
    (-1 scale) controls too: the orient constraint passes the same turn.
    """
    cmds.select(clear=True)
    bind = cmds.joint(name=fol + '_bind')
    cmds.setAttr(bind + '.radius', radius)
    cmds.xform(bind, worldSpace=True, matrix=fol_matrix)
    cmds.setAttr(bind + '.rotateOrder', cmds.getAttr(ctrl + '.rotateOrder'))
    _constrain_bind(ctrl, bind)
    return bind


def _constrain_bind(ctrl, bind):
    cmds.pointConstraint(ctrl, bind, maintainOffset=True, name=bind.split('|')[-1] + '_pointConstraint')
    cmds.orientConstraint(ctrl, bind, maintainOffset=True, name=bind.split('|')[-1] + '_orientConstraint')


def _clean_matrix(m):
    """m with unit scale and no reflection (a joint shouldn't get -1 scale)."""
    rows = []
    for r in range(3):
        v = m[r * 4:r * 4 + 3]
        ln = sum(x * x for x in v) ** 0.5 or 1.0
        rows.append([x / ln for x in v])
    a, b, c = rows
    det = (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
           + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if det < 0:
        rows[0] = [-x for x in rows[0]]
    return rows[0] + [0.0] + rows[1] + [0.0] + rows[2] + [0.0] + list(m[12:15]) + [1.0]


def _loose_binds(ctrls):
    """[(control, bind joint)] for bind joints that are children of their control (mirrored builds before 5.2.1),
    or that ended up outside it (the Hare's R_Sleeve_fol_01_bind under a 'transform1' Maya added) - found by name:
    <name>_ctrl -> <name>_bind, not driven by anything."""
    out = []
    for c in ctrls:
        if _copier(c):
            continue
        kids = [k for k in cmds.listRelatives(c, children=True, type='joint', fullPath=True) or []]
        if kids:
            out.append((c, kids[0]))
            continue
        short = naming.short_name(c)
        if not short.endswith('_ctrl'):
            continue
        found = cmds.ls(short[:-len('_ctrl')] + '_bind', type='joint', long=True) or []
        if len(found) != 1:
            continue
        j = found[0]
        driven = any(cmds.listConnections('%s.%s' % (j, ch), source=True, destination=False)
                     for ch in ('translate', 'rotate', 'tx', 'ty', 'tz', 'rx', 'ry', 'rz'))
        if not driven:
            out.append((c, j))
    return out


def _bind_group(key, build, settings):
    """The build's _bind_grp, made (next to its controls' group) when a mirrored build had none."""
    for n in build['nodes']:
        if n.endswith('_bind_grp') and cmds.objExists(n):
            return n
    prefix = settings.get('prefix') or key.split('|')[-1]
    ctrls_grp = [n for n in build['nodes'] if n.endswith('_ctrls_grp') and cmds.objExists(n)]
    parent = cmds.listRelatives(ctrls_grp[0], parent=True, fullPath=True) if ctrls_grp else None
    grp = cmds.createNode('transform', name=prefix + '_bind_grp', parent=parent[0], skipSelect=True) if parent \
        else cmds.createNode('transform', name=prefix + '_bind_grp', skipSelect=True)
    grp = cmds.ls(grp, long=True)[0]
    skin = sorted(build.get('skins') or [''])[0]
    _tag([grp], key, skin)
    build['nodes'].append(grp)
    return grp


def _drop_empty(node):
    """Delete a plain group left empty (Maya's 'transform1')."""
    if not node or not cmds.objExists(node) or cmds.nodeType(node) != 'transform':
        return
    if cmds.listRelatives(node, children=True) or cmds.listConnections(node, source=True, destination=False):
        return
    import re
    if re.match(r'^transform\d*$', naming.short_name(node)):
        cmds.delete(node)


def to_constraints(surface=None):
    """
    An existing ribbon whose bind joints copy their controls (pivot on the shape) gets constraints instead:
    each joint leaves its copy group, sits on the ribbon where it is now, and is driven by point + orient
    constraints from its control. Follow groups the Follow tool made above the copy groups go too (the
    constraint already carries the joint along). Nothing moves, the skin weights are kept. Builds made with
    'Scale controls too' lose it: joint scale back to 1, the build's setting off. Controls must be at rest.
    Returns how many joints were switched.
    """
    from gus_rigtool.core import follow
    builds = _find_builds()
    key = _resolve(surface) if surface else _pick_build(builds)
    if key not in builds:
        raise RuntimeError('select the ribbon (or one of its controls) first.')
    settings = _build_settings(builds[key]) or {}
    ctrls = [c for c in (_control_under(o) for o in _build_offsets(builds[key]).values()) if c]
    pairs = [(c, _copier(c)) for c in ctrls]
    pairs = [(c, j) for c, j in pairs if j]
    loose = _loose_binds(ctrls)                         # 5.2.1: children of the controls, or left outside
    if not pairs and not loose:
        raise RuntimeError('this ribbon has no joints copying their controls or hanging under them (already '
                           'constraints?).')
    posed = [naming.short_name(c) for c, _j in pairs + loose
             if any(abs(v) > 1e-4 for a in ('translate', 'rotate') for v in cmds.getAttr(c + '.' + a)[0])
             or any(abs(v - 1) > 1e-4 for v in cmds.getAttr(c + '.scale')[0])]
    if posed:
        raise RuntimeError('put the controls at rest first (Reset, scale 1): %s' % ', '.join(posed[:5]))
    done = 0
    cmds.undoInfo(openChunk=True, chunkName='gusrigRibbonToConstraints')
    try:
        for ctrl, joint in pairs:
            jid = utils.uuid(joint)
            wm = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
            for ch in ('translate', 'rotate', 'scale'):
                for a in ('', 'X', 'Y', 'Z'):
                    plug = '%s.%s%s' % (joint, ch, a)
                    for src in cmds.listConnections(plug, source=True, destination=False, plugs=True) or []:
                        cmds.disconnectAttr(src, plug)
            cop_off = cmds.listRelatives(joint, parent=True, fullPath=True)[0]
            home = cop_off
            while home and not home.endswith('_bind_grp'):
                home = (cmds.listRelatives(home, parent=True, fullPath=True) or [None])[0]
            if home:
                cmds.parent(joint, home)
            else:
                cmds.parent(joint, world=True)
            joint = utils.path(jid)
            for a in ('jointOrientX', 'jointOrientY', 'jointOrientZ'):
                cmds.setAttr(joint + '.' + a, 0)
            cmds.setAttr(joint + '.scale', 1, 1, 1)
            cmds.xform(joint, worldSpace=True, matrix=_clean_matrix(wm))
            _constrain_bind(ctrl, joint)
            _rebind(joint)
            # the copy group and anything the Follow tool put above it (up to the bind group) go
            top = cop_off
            while True:
                up = (cmds.listRelatives(top, parent=True, fullPath=True) or [None])[0]
                if not up or up.endswith('_bind_grp') or not (
                        up.endswith('_follow') or up.endswith('_followSpace')):
                    break
                top = up
            follow.forget_space(top)
            if cmds.objExists(top):
                cmds.delete(top)
            if settings.get('pivot_scale') and settings.get('lock_hide', True):
                for a in ('sx', 'sy', 'sz'):                      # the control doesn't scale anything now
                    try:
                        cmds.setAttr('%s.%s' % (ctrl, a), lock=True, keyable=False, channelBox=False)
                    except RuntimeError:
                        pass
            done += 1
        if loose:
            grp = _bind_group(key, builds[key], settings)
            for ctrl, joint in loose:
                jid = utils.uuid(joint)
                wm = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
                was = cmds.listRelatives(joint, parent=True, fullPath=True)
                joint = cmds.parent(joint, grp, relative=True)[0]     # relative: Maya adds no group
                joint = utils.path(jid)
                for a in ('jointOrientX', 'jointOrientY', 'jointOrientZ'):
                    cmds.setAttr(joint + '.' + a, 0)
                cmds.setAttr(joint + '.scale', 1, 1, 1)
                cmds.xform(joint, worldSpace=True, matrix=_clean_matrix(wm))
                for kind in ('parentConstraint', 'pointConstraint', 'orientConstraint'):
                    old = cmds.listRelatives(joint, type=kind, fullPath=True) or []
                    if old:
                        cmds.delete(old)
                _constrain_bind(ctrl, joint)
                _rebind(joint)
                _drop_empty(was[0] if was else None)
                done += 1
            link_bind_group(key)
        if settings.get('pivot_scale'):
            settings['pivot_scale'] = False
            for node in builds[key]['nodes']:
                if cmds.objExists(node + '.rrbSettings') and cmds.getAttr(node + '.rrbSettings'):
                    cmds.setAttr(node + '.rrbSettings', json.dumps(settings), type='string')
    finally:
        cmds.undoInfo(closeChunk=True)
    _say('%d joint(s) now follow their controls by constraints (point + orient), on the ribbon; nothing moved, '
         'skin kept.' % done)
    return done


def _tag(nodes, surface, skin, extra=None):
    """Mark nodes as made by this tool, remembering their ribbon, skin cluster and settings."""
    values = [('rrbSurface', surface), ('rrbSkin', skin or '')] + sorted((extra or {}).items())
    for node in nodes:
        for name, value in values:
            if not cmds.objExists(node + '.' + name):
                cmds.addAttr(node, longName=name, dataType='string')
            cmds.setAttr(node + '.' + name, value, type='string')


def _tag_index(node, index):
    """Remember which follicle (0-based) a control offset group belongs to."""
    if not cmds.objExists(node + '.rrbIndex'):
        cmds.addAttr(node, longName='rrbIndex', attributeType='long')
    cmds.setAttr(node + '.rrbIndex', index)


def _resolve(path):
    """A stored ribbon path (or name), as a full path now (the ribbon may have moved into a group since)."""
    if not path:
        return path
    if cmds.objExists(path):
        found = cmds.ls(path, long=True) or []
        if len(found) == 1:
            return found[0]
        return path
    found = cmds.ls(path.split('|')[-1], long=True) or []
    return found[0] if len(found) == 1 else path


class _Builds(dict):
    """{ribbon full path: build}; looking a ribbon up by its name or an old path works too."""

    def _key(self, k):
        if dict.__contains__(self, k) or not isinstance(k, str):
            return k
        return _resolve(k)

    def __contains__(self, k):
        return dict.__contains__(self, self._key(k))

    def __getitem__(self, k):
        return dict.__getitem__(self, self._key(k))

    def get(self, k, default=None):
        return dict.get(self, self._key(k), default)


def _find_builds():
    """All tagged builds in the scene: {ribbon: {'nodes': [...], 'skins': set()}}."""
    builds = _Builds()
    for node in utils.nodes_with_attr('rrbSurface', 'transform'):
        surface = _resolve(cmds.getAttr(node + '.rrbSurface'))
        skin = cmds.getAttr(node + '.rrbSkin')
        b = builds.setdefault(surface, {'nodes': [], 'skins': set()})
        b['nodes'].append(node)
        if skin:
            b['skins'].add(skin)
    return builds


def _selected_surface():
    """The ribbon the selection points at: a ribbon, or any node inside a build (a control, a group...)."""
    sel = cmds.ls(sl=True, long=True)
    if not sel:
        return None
    node = sel[0]

    probe = node
    for _ in range(100):                          # walk up to the tagged group of the build
        if cmds.objExists(probe + '.rrbSurface'):
            return _resolve(cmds.getAttr(probe + '.rrbSurface'))
        if cmds.objExists(probe + '.rrbGroup'):
            return _resolve(cmds.getAttr(probe + '.rrbGroup'))
        parents = cmds.listRelatives(probe, parent=True, fullPath=True) or []
        if not parents or parents[0] == probe:
            break
        probe = parents[0]

    if cmds.nodeType(node) == 'nurbsSurface':
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    return node


def _pick_build(builds):
    """Which build to act on: the selected one, else the last made, else the only one. Else None."""
    if not builds:
        utils.warn(TOOL, 'no build found in this scene.')
        return None

    key = _selected_surface()
    if key not in builds:
        key = _last['surface'] if _last['surface'] in builds else None
    if key is None and len(builds) == 1:
        key = next(iter(builds))
    if key is None:
        utils.warn(TOOL, 'several builds found. Select the ribbon (or a node of the build) and try again.')
    return key


def _build_settings(build):
    """The settings a build was made with (stored on its nodes), or None for an older build."""
    for node in build['nodes']:
        if cmds.objExists(node + '.rrbSettings'):
            text = cmds.getAttr(node + '.rrbSettings')
            if text:
                stored = json.loads(text)
                stored.setdefault('auto_count', 'cv')     # builds made before 1.2.4 used CV rows
                return stored
    return None


def _build_offsets(build):
    """{follicle index: control offset group} of a build."""
    found = {}
    for top in build['nodes']:
        kids = cmds.listRelatives(top, allDescendents=True, type='transform', fullPath=True) or []
        for node in [top] + kids:
            if cmds.objExists(node + '.rrbIndex'):
                found[int(cmds.getAttr(node + '.rrbIndex'))] = node
    return found


# ----------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------

def surface_and_shape(surface):
    """(transform, nurbsSurface shape) of a ribbon. Raises if it is not a NURBS surface."""
    # full paths: two ribbons can have shapes with the same short name (e.g. a duplicated ribbon)
    if not cmds.objExists(surface):
        raise RuntimeError('"%s" does not exist.' % surface)
    found = cmds.ls(surface, long=True) or [surface]
    if len(found) > 1:
        raise RuntimeError('several objects are called "%s". Rename one, or select the ribbon.' % surface)
    surface = found[0]
    if cmds.nodeType(surface) == 'nurbsSurface':
        return cmds.listRelatives(surface, parent=True, fullPath=True)[0], surface
    shapes = cmds.listRelatives(surface, shapes=True, noIntermediate=True, type='nurbsSurface',
                                fullPath=True) or []
    if not shapes:
        raise RuntimeError('"%s" is not a NURBS surface.' % naming.short_name(surface))
    return surface, shapes[0]


def _even_length_params(shape, n, looped, v_pos):
    """n U values (0-1) evenly spaced by length along the ribbon, at the given width position."""
    sel = om.MSelectionList()
    sel.add(shape)
    fn = om.MFnNurbsSurface(sel.getDagPath(0))
    (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV
    v = v0 + (v1 - v0) * v_pos
    steps = max(400, 40 * n)
    us = [u0 + (u1 - u0) * k / float(steps) for k in range(steps + 1)]
    pts = [fn.getPointAtParam(u, v, om.MSpace.kWorld) for u in us]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + (b - a).length())
    total = lengths[-1] or 1.0
    if n == 1:
        targets = [total / 2.0]
    elif looped:
        targets = [total * i / float(n) for i in range(n)]
    else:
        targets = [total * i / float(n - 1) for i in range(n)]
    out, k = [], 0
    for t in targets:
        while k < steps - 1 and lengths[k + 1] < t:
            k += 1
        seg = lengths[k + 1] - lengths[k]
        f = (t - lengths[k]) / seg if seg > 1e-12 else 0.0
        u = us[k] + (us[k + 1] - us[k]) * min(max(f, 0.0), 1.0)
        out.append(min(1.0, max(0.0, (u - u0) / float(u1 - u0))))
    return out


def _surface_fn(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return om.MFnNurbsSurface(sel.getDagPath(0))


def _seam_closed(shape):
    """An open-form ribbon whose two ends meet (e.g. a loft of loops that came out 'open'):
    the first and last CV rows are on top of each other."""
    try:
        fn = _surface_fn(shape)
        (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV
        far = 0.0
        gaps = []
        for k in range(5):
            v = v0 + (v1 - v0) * k / 4.0
            a = fn.getPointAtParam(u0, v, om.MSpace.kWorld)
            b = fn.getPointAtParam(u1, v, om.MSpace.kWorld)
            m = fn.getPointAtParam((u0 + u1) / 2.0, v, om.MSpace.kWorld)
            gaps.append((b - a).length())
            far = max(far, (m - a).length())
        return max(gaps) <= 1e-4 * max(far, 1e-3)
    except Exception:
        return False


def is_looped(surface):
    """True when the ribbon goes all the way round along its length (closed, periodic, or its
    two ends simply meet). A loop has no ends, so U = 0 and U = 1 are the same line."""
    _surf, shape = surface_and_shape(surface)
    return cmds.getAttr(shape + '.formU') in (1, 2) or _seam_closed(shape)


def _drop_doubles(shape, u_vals, v_pos):
    """Remove follicles that would sit on top of an earlier one (e.g. at the seam of a loop)."""
    try:
        fn = _surface_fn(shape)
        (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV
        v = v0 + (v1 - v0) * v_pos
        pts = [fn.getPointAtParam(u0 + (u1 - u0) * u, v, om.MSpace.kWorld) for u in u_vals]
        size = max([(p - pts[0]).length() for p in pts] + [1e-3])
    except Exception:
        return u_vals
    keep, kept_pts = [], []
    for u, p in zip(u_vals, pts):
        if all((p - q).length() > 1e-4 * size for q in kept_pts):
            keep.append(u)
            kept_pts.append(p)
    return keep


def _span_params(shape, minU, maxU, looped):
    """U (0-1) of every span line (the distinct knots inside the range). The last one is left out
    on a loop, where it is the first one again."""
    try:
        knots = list(_surface_fn(shape).knotsInU())
    except Exception:
        return None
    rng = float(maxU - minU) or 1.0
    out = []
    for k in knots:
        if minU - 1e-9 <= k <= maxU + 1e-9:
            u = (k - minU) / rng
            if not out or u - out[-1] > 1e-6:
                out.append(min(1.0, max(0.0, u)))
    if looped and len(out) > 1 and out[-1] > 1.0 - 1e-6:
        out = out[:-1]
    return out if len(out) >= 2 else None


def follicle_params(surf, shape, s):
    n, u_vals = _follicle_params(surf, shape, s)
    u_vals = _drop_doubles(shape, u_vals, float(s['v_pos']))
    return len(u_vals), u_vals


def _follicle_params(surf, shape, s):
    """(number of follicles, U values 0-1) for the settings s - same rules as the original tool,
    plus 'Even by length'."""
    num_follicles = int(s['num_follicles'])
    degU = cmds.getAttr(shape + '.degreeU')
    minU = cmds.getAttr(shape + '.minValueU')
    maxU = cmds.getAttr(shape + '.maxValueU')
    spans = cmds.getAttr(shape + '.spansU')
    form = cmds.getAttr(shape + '.formU')        # 0 = open, 1 = closed, 2 = periodic
    seam = form == 0 and _seam_closed(shape)     # open form, but its ends meet: a loop too
    looped = form in (1, 2) or seam              # on a loop, U = 0 and U = 1 are the same line

    per_span = s.get('auto_count', 'span') == 'span'
    if num_follicles > 0:
        n = num_follicles
    elif per_span:
        n = spans if looped else spans + 1       # one on every span line (knot)
    elif form == 2:
        n = spans
    else:
        n = spans + degU
        if form == 1 or seam:
            n -= 1                               # the last CV row is the first one again

    if s.get('distribution') == 'length':
        return n, _even_length_params(shape, n, looped, float(s['v_pos']))

    # where each follicle sits along U (original rules)
    if num_follicles > 0:
        if n == 1:
            u_vals = [0.5]
        elif looped:
            u_vals = [i / float(n) for i in range(n)]          # last one stops before the seam
        else:
            u_vals = [i / float(n - 1) for i in range(n)]      # first on one end, last on the other
    elif per_span:
        # one follicle on every span line: where the surface's own knots are
        u_vals = _span_params(shape, minU, maxU, looped) or \
            ([i / float(n) for i in range(n)] if looped else [i / float(n - 1) for i in range(n)])
        n = len(u_vals)
    elif form == 2:
        # periodic: evenly spaced around the loop, one follicle per span
        u_vals = [i / float(n) for i in range(n)]
    else:
        # one follicle per CV row, placed right on the row
        u_vals = _cv_row_params(surf, shape, degU, spans, minU, maxU, n)
    return n, u_vals


def build_rig(settings=None, surface=None, mirror=None, _own_chunk=True, **overrides):
    """
    Build the rig on a NURBS ribbon (the selected one, unless surface is given). Any key of
    DEFAULTS can be passed, either in a dict (settings) or as keyword arguments.
    mirror is used by mirror_build: {'matrices': {follicle index: reflected control matrix},
    'of': left ribbon}. Returns the top-level nodes.
    """
    s = dict(DEFAULTS)
    s.update(settings or {})
    s.update(overrides)

    if surface is None:
        sel = cmds.ls(sl=True)
        if not sel:
            raise RuntimeError('Select the NURBS ribbon first.')
        surface = sel[0]

    surf, shape = surface_and_shape(surface)
    turned = _turn_along_u(surf)              # a lofted strip runs along V: the follicles go along U
    if turned:
        surf, shape = surface_and_shape(surf)

    mirrored = mirror is not None
    prefix = s['prefix'].strip() or naming.short_name(surf)
    color = s['color']
    if s.get('use_side_colors'):
        color = colors.side_colors()[sides.side_of_node(cmds.ls(surf, long=True)[0])]

    n, u_vals = follicle_params(surf, shape, s)

    # which follicles get a control (checked before anything is created)
    ctrl_idx = []
    if s['make_ctrls']:
        ctrl_idx = _control_indices(n, s['ctrl_mode'], s['ctrl_every'], s['ctrl_list'],
                                    s['include_ends'] and not is_looped(surf))   # a loop has no ends
        if not ctrl_idx:
            raise RuntimeError('No joints selected for controls. Check "Controls on".')
        if mirrored:
            missing = [i + 1 for i in ctrl_idx if i not in mirror['matrices']]
            if missing:
                raise RuntimeError('The first side has no control on joint(s) %s, so they cannot be '
                                   'mirrored. Does the ribbon have the same number of CV rows?' % missing)

    if _own_chunk:
        cmds.undoInfo(openChunk=True)
    try:
        # ---------------------------------------------- follicles (+ joints)
        follicles = []
        for i in range(n):
            fol_shape = cmds.createNode('follicle')
            fol = cmds.listRelatives(fol_shape, parent=True)[0]
            fol = cmds.rename(fol, '%s_fol_%02d' % (prefix, i + 1))
            fol_shape = cmds.listRelatives(fol, shapes=True, fullPath=True)[0]

            cmds.connectAttr(shape + '.local', fol_shape + '.inputSurface')
            cmds.connectAttr(shape + '.worldMatrix[0]', fol_shape + '.inputWorldMatrix')
            cmds.connectAttr(fol_shape + '.outTranslate', fol + '.translate')
            cmds.connectAttr(fol_shape + '.outRotate', fol + '.rotate')
            cmds.setAttr(fol_shape + '.parameterU', u_vals[i])
            cmds.setAttr(fol_shape + '.parameterV', s['v_pos'])

            if s['make_joints']:
                cmds.select(clear=True)
                jnt = cmds.joint(name=fol + '_jnt')
                cmds.parent(jnt, fol, relative=True)
                cmds.setAttr(jnt + '.radius', s['fol_jnt_radius'])

            follicles.append(fol)

        # ---------------------------------------------- controls (separate group)
        ctrl_offsets = []
        bind_joints = []
        bind_offsets = []                       # pivot on the shape + scale: the bind joints' own groups
        constrained = []                        # pivot on the shape: bind joints on the ribbon, constrained
        joint_only = s['ctrl_shape'] == JOINT_ONLY
        direct_skin = joint_only and s['joint_connect'] != 'constrain'   # control joint is itself skinned
        if s['make_ctrls']:
            move_vec = [c * s['ctrl_distance'] for c in AXES[s['dir_axis']]]
            if mirrored and mirror.get('style') == 'behavior':
                move_vec = [-c for c in move_vec]       # the axes are turned round: keep the shape in front
            on_shape = bool(s.get('pivot_on_shape')) and not joint_only
            shift = list(mirror_engine.IDENTITY)
            shift[12:15] = move_vec                     # the shape's spot, in the joint's axes
            back = list(mirror_engine.IDENTITY)
            back[12:15] = [-c for c in move_vec]
            for i in ctrl_idx:
                fol = follicles[i]
                fol_matrix = cmds.xform(fol, query=True, worldSpace=True, matrix=True)

                # offset group = the follicle's world position/rotation (same axes, not parented),
                # so the control's pivot sits exactly on the joint. On a mirrored build it is the
                # reflected matrix of the twin control instead, so the two mirror each other.
                # Pivot on the shape: the offset group sits where the shape is, same axes.
                if mirrored:
                    offset_matrix = mirror['matrices'][i]
                elif on_shape:
                    offset_matrix = mirror_engine.mul(shift, fol_matrix)
                else:
                    offset_matrix = fol_matrix
                offset = cmds.group(empty=True, name=fol + '_ctrl_offset')
                cmds.xform(offset, worldSpace=True, matrix=offset_matrix)
                _tag_index(offset, i)

                if joint_only:
                    # no curve: the joint is the control and sits on the ribbon
                    cmds.select(clear=True)
                    ctrl = cmds.joint(name=fol + '_ctrl')
                    ctrl = cmds.parent(ctrl, offset, relative=True)[0]
                    cmds.setAttr(ctrl + '.radius', s['ctrl_radius'])
                    cmds.setAttr(ctrl + '.overrideEnabled', 1)
                    cmds.setAttr(ctrl + '.overrideRGBColors', 1)
                    cmds.setAttr(ctrl + '.overrideColorRGB', color[0], color[1], color[2])
                    if direct_skin:
                        bind = ctrl                          # the ribbon is skinned to the control joint
                    else:
                        # separate bind joint on the ribbon, driven by the control joint
                        bind = _make_bind(fol, ctrl, fol_matrix, s['bind_jnt_radius'], False)
                        if mirrored:                     # 5.2.1: no child of a -1 scaled control
                            cmds.delete(cmds.listRelatives(bind, type='parentConstraint', fullPath=True) or [])
                            _constrain_bind(ctrl, bind)
                            constrained.append(bind)
                else:
                    ctrl = _make_control(fol + '_ctrl', s['ctrl_shape'], s['face_axis'], s['ctrl_radius'])
                    ctrl = cmds.parent(ctrl, offset, relative=True)[0]

                    if not on_shape:
                        # move only the shape out in front; the pivot stays on the joint
                        cmds.move(move_vec[0], move_vec[1], move_vec[2], ctrl + '.cv[*]',
                                  objectSpace=True, relative=True)

                    for sh in cmds.listRelatives(ctrl, shapes=True, fullPath=True) or []:
                        cmds.setAttr(sh + '.overrideEnabled', 1)
                        cmds.setAttr(sh + '.overrideRGBColors', 1)
                        cmds.setAttr(sh + '.overrideColorRGB', color[0], color[1], color[2])

                    if on_shape and s.get('pivot_scale'):
                        # scale too: the bind joint has its own offset group on the joint, with the same
                        # axes as the control's, and copies the control's channels (scale passes through)
                        bind_offset = cmds.group(empty=True, name=fol + '_bind_offset')
                        cmds.xform(bind_offset, worldSpace=True,
                                   matrix=mirror_engine.mul(back, offset_matrix))
                        cmds.select(clear=True)
                        bind = cmds.joint(name=fol + '_bind')
                        bind = cmds.parent(bind, bind_offset, relative=True)[0]
                        cmds.setAttr(bind + '.radius', s['bind_jnt_radius'])
                        cmds.setAttr(bind + '.rotateOrder', cmds.getAttr(ctrl + '.rotateOrder'))
                        for ch in ('translate', 'rotate', 'scale'):
                            cmds.connectAttr(ctrl + '.' + ch, bind + '.' + ch)
                        bind_offsets.append(bind_offset)
                    elif on_shape:
                        # the bind joint sits on the ribbon (at the follicle); point + orient constraints
                        # from the control: it moves with the control and turns in place by the same amount
                        bind = _make_bind_on_shape(fol, ctrl, fol_matrix, s['bind_jnt_radius'])
                        constrained.append(bind)
                    elif mirrored:
                        # 5.2.1: a mirrored build - the bind joint on the ribbon, point + orient constraints
                        # (a child of a -1 scaled control made Maya add 'transform1' groups whenever it was
                        # touched, and the two sides weren't made the same way)
                        bind = _make_bind_on_shape(fol, ctrl, fol_matrix, s['bind_jnt_radius'])
                        constrained.append(bind)
                    else:
                        # bind joint stays on the ribbon (at the follicle), driven by the control
                        bind = _make_bind(fol, ctrl, fol_matrix, s['bind_jnt_radius'], False)

                if s['lock_hide']:
                    scales = on_shape and s.get('pivot_scale')      # 'scale controls too': keep scale free
                    for attr in (('v',) if scales else ('sx', 'sy', 'sz', 'v')):
                        cmds.setAttr('%s.%s' % (ctrl, attr), lock=True, keyable=False, channelBox=False)

                ctrl_offsets.append(offset)
                bind_joints.append(bind)

        # ---------------------------------------------- skin
        skin = None
        if s['make_ctrls'] and s['make_skin'] and bind_joints:
            skin = cmds.skinCluster(bind_joints, surf, toSelectedBones=True,
                                    name=prefix + '_skinCluster')[0]

        # ---------------------------------------------- groups
        # bind joints that are the control joint, or children of the control (mirrored build),
        # already live inside their offset groups
        if bind_offsets or constrained:
            loose_bind = bind_offsets + constrained
        else:
            loose_bind = [] if (direct_skin or mirrored) else bind_joints
        top = []
        if s['make_groups']:
            top.append(cmds.group(follicles, name=prefix + '_follicles_grp'))
            if ctrl_offsets:
                top.append(cmds.group(ctrl_offsets, name=prefix + '_ctrls_grp'))
                if loose_bind:
                    top.append(cmds.group(loose_bind, name=prefix + '_bind_grp'))
        else:
            top = follicles + ctrl_offsets + loose_bind

        top = [cmds.ls(t, long=True)[0] for t in top]
        if s['make_groups'] and len(top) > 2 and top[2].endswith('_bind_grp'):
            # the bind joints' group follows the controls' group (move / parent the controls: joints come along)
            cmds.parentConstraint(top[1], top[2], maintainOffset=True)
            cmds.scaleConstraint(top[1], top[2], maintainOffset=True)
        surf_long = cmds.ls(surf, long=True)[0]
        if s.get('make_groups', True) and s.get('ribbon_group', True):
            ids = [utils.uuid(x) for x in top]
            group_build(surf_long, top, prefix, s.get('group_parent', ''))
            top = [utils.path(i) for i in ids]
            surf_long = _resolve(surf_long)
        extra = {'rrbSettings': json.dumps(dict(s, prefix=prefix))}
        if mirrored:
            extra['rrbMirrorOf'] = mirror['of']
        _tag(top, surf_long, skin, extra)
        _last['surface'] = surf_long

        cmds.select(top[1] if (s['make_groups'] and len(top) > 1) else top[0])
    finally:
        if _own_chunk:
            cmds.undoInfo(closeChunk=True)

    _say('made %d follicles, %d controls on %s%s%s.'
          % (n, len(ctrl_offsets), naming.short_name(surf), ' (mirrored)' if mirrored else '',
             '; it ran along V, so U / V were swapped first' if turned == 'swapped' else ''))
    if turned == 'deformed':
        utils.warn(TOOL, "%s runs along V but has deformers, so it wasn't swapped: the joints bunch across its "
                         "width. Delete its history and rebuild." % naming.short_name(surf))
    if bind_offsets:
        utils.warn(TOOL, "'Scale controls too' was on: the bind joints COPY their controls (direct connections, "
                         "scale included), no constraints. Untick it and rebuild, or use Switch to constraints.")
    return top


def delete_build(key=None):
    """
    Remove a build made by this tool. Which one: key if given; else the build of the selected
    ribbon (or of any selected node of a build); otherwise the last build made in this session;
    otherwise the only build in the scene. The ribbon itself is kept.
    """
    builds = _find_builds()
    if key not in builds:
        key = _pick_build(builds)
    if key is None:
        return

    build = builds[key]
    cmds.undoInfo(openChunk=True)
    try:
        for skin in build['skins']:
            if cmds.objExists(skin):
                cmds.skinCluster(skin, edit=True, unbind=True)   # frees the ribbon before the joints go
        for node in build['nodes']:
            if cmds.objExists(node):
                cmds.delete(node)
    finally:
        cmds.undoInfo(closeChunk=True)

    if _last['surface'] == key:
        _last['surface'] = None
    _say('build on %s deleted.' % key)


delete_last_build = delete_build        # old name, kept so earlier calls still work


def _control_under(node):
    """The control below an offset group: the nearest transform with a curve shape (groups such as
    _driven / _sdk can sit in between)."""
    kids = cmds.listRelatives(node, allDescendents=True, type='transform', fullPath=True) or []
    for k in sorted(kids, key=lambda x: x.count('|')):
        if cmds.listRelatives(k, shapes=True, type='nurbsCurve', fullPath=True):
            return k
    return None


def _groups_between(top, ctrl):
    out, p = [], (cmds.listRelatives(ctrl, parent=True, fullPath=True) or [None])[0]
    while p and p != top and p.startswith(top):
        out.append(p)
        p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
    return out


def group_build(surface, nodes, prefix, parent=''):
    """Put a build (its groups and, when it sits in the world, the ribbon itself) in one
    <prefix>_ribbon_grp. The group doesn't inherit transforms, so moving what it's under never moves the
    ribbon twice. A ribbon already in a ribbon group keeps that group. Returns the group."""
    surf_parent = (cmds.listRelatives(surface, parent=True, fullPath=True) or [None])[0]
    if surf_parent and cmds.objExists(surf_parent + '.rrbGroup'):
        grp = surf_parent                                     # rebuilt on the same ribbon: same group
    else:
        grp = cmds.createNode('transform', name=naming.unique((prefix or naming.short_name(surface)) + '_ribbon_grp'))
        grp = cmds.ls(grp, long=True)[0]
        cmds.addAttr(grp, longName='rrbGroup', dataType='string')
        cmds.setAttr(grp + '.inheritsTransform', 0)
    gid = utils.uuid(grp)
    move = [n for n in nodes if cmds.objExists(n)]
    if not surf_parent:
        move.insert(0, surface)
    for n in move:
        parent_now = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
        if parent_now != utils.path(gid):
            cmds.parent(n, utils.path(gid))
    grp = utils.path(gid)
    if parent and cmds.objExists(parent) and (cmds.listRelatives(grp, parent=True, fullPath=True) or [None])[0] \
            != cmds.ls(parent, long=True)[0]:
        cmds.parent(grp, parent)
        grp = utils.path(gid)
    surf_now = surface if cmds.objExists(surface) else _resolve(surface)
    cmds.setAttr(grp + '.rrbGroup', surf_now, type='string')
    return grp


def organize_builds(parent=''):
    """Every build not in a ribbon group yet gets one (nothing moves in the viewport). Returns the groups."""
    out = []
    for key, build in _find_builds().items():
        settings = _build_settings(build) or {}
        prefix = settings.get('prefix') or naming.short_name(key)
        tops = [n for n in build['nodes'] if cmds.objExists(n)]
        already = [n for n in tops if cmds.objExists(((cmds.listRelatives(n, parent=True, fullPath=True) or
                                                         ['|'])[0]) + '.rrbGroup')]
        if tops and len(already) == len(tops):
            continue
        ids = [utils.uuid(n) for n in tops]
        out.append(group_build(key, tops, prefix, parent))
        for i in ids:                                         # the tags keep pointing at the ribbon
            n = utils.path(i)
            if n and cmds.objExists(n + '.rrbSurface'):
                cmds.setAttr(n + '.rrbSurface', _resolve(key), type='string')
    return out


def _link_builds(left, right, style=None):
    """Twin links between the two ribbons and their controls (by follicle index), with the style."""
    try:
        sides.link(left, right)
        builds = _find_builds()
        lo = _build_offsets(builds.get(left, {'nodes': []}))
        ro = _build_offsets(builds.get(right, {'nodes': []}))
        for i, off in lo.items():
            if i in ro:
                lc, rc = _control_under(off), _control_under(ro[i])
                if lc and rc:
                    mirror_engine.link(lc, rc, style)           # control <-> control, groups or not
                for g in _groups_between(off, lc) if lc else []:
                    twin = sides.name_twin(g)                    # groups in between: by their names
                    if twin:
                        sides.link(g, twin)
    except Exception:
        pass


def _driven_by(ctrl):
    """What the control moves: its child transforms, and the nodes its constraints drive."""
    kids = [k for k in cmds.listRelatives(ctrl, children=True, type='transform', fullPath=True) or []]
    cons = set()
    for c in cmds.listConnections(ctrl, type='constraint', source=False, destination=True) or []:
        cons.add(c)
    driven = []
    for c in cons:
        node = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0]
        if node and node not in driven and node not in kids:
            driven.append((node, c))
    return kids, driven


SKIP_PLUGS = {'parentConstraint': (('skipTranslate', 'constraintTranslate'), ('skipRotate', 'constraintRotate')),
              'pointConstraint': (('skip', 'constraintTranslate'),),
              'orientConstraint': (('skip', 'constraintRotate'),),
              'scaleConstraint': (('skip', 'constraintScale'),)}


def _skip_flags(con, kind):
    """The axes a constraint leaves alone, as the flags its own command takes (only a parent constraint has
    skipTranslate / skipRotate; point, orient and scale constraints take 'skip')."""
    flags = {}
    for flag, plug in SKIP_PLUGS.get(kind, ()):
        flags[flag] = [a for a in 'xyz' if not cmds.listConnections(
            '%s.%s%s' % (con, plug, a.upper()), source=True)] or 'none'
    return flags


def _remake_constraint(con, driven, keep=None):
    """The constraint again with 'maintain offset', same targets and weights (after its target turned)."""
    return _remake_constraints(driven, [con], keep)[0]


def _remake_constraints(driven, cons, keep=None):
    """Every constraint on driven again with 'maintain offset', same targets, weights and skipped axes. keep: the
    world matrix driven had BEFORE its target turned - in Maya the old constraints have already dragged it away,
    so it goes back there first (with all its constraints off), then they're remade: nothing moves."""
    data = []
    for con in cons:
        kind = cmds.nodeType(con)
        fn = getattr(cmds, kind)
        data.append((fn, fn(con, query=True, targetList=True) or [],
                     [cmds.getAttr(con + '.' + a) for a in fn(con, query=True, weightAliasList=True) or []],
                     _skip_flags(con, kind), con.split('|')[-1]))
    cmds.delete(cons)
    if keep is not None:
        cmds.xform(driven, worldSpace=True, matrix=keep)
    made = []
    for fn, targets, weights, flags, name in data:
        con = fn(targets, driven, maintainOffset=True, name=name, **flags)[0]
        for alias, w in zip(fn(con, query=True, weightAliasList=True) or [], weights):
            cmds.setAttr(con + '.' + alias, w)
        made.append(con)
    return made


def _copier(ctrl):
    """The bind joint that copies the control's channels (pivot on the shape), or None."""
    for n in cmds.listConnections(ctrl + '.translate', source=False, destination=True) or []:
        if cmds.nodeType(n) == 'joint':
            return cmds.ls(n, long=True)[0]
    return None


def bind_of(ctrl):
    """(bind joint, how it follows the control): 'constraints' (point + orient), 'parent constraint',
    'copy' / 'copy + scale' (direct connections), 'child' (joint under the control), 'is the joint'
    (a joint control skinned itself), or (None, 'none')."""
    cop = _copier(ctrl)
    if cop:
        scaled = bool(cmds.listConnections(cop + '.scale', source=True, destination=False))
        return cop, ('copy + scale' if scaled else 'copy')
    kids, driven = _driven_by(ctrl)
    kinds = {}
    for node, con in driven:
        if cmds.nodeType(node) == 'joint':
            kinds.setdefault(node, set()).add(cmds.nodeType(con))
    for node, ks in kinds.items():
        if 'parentConstraint' in ks:
            return node, 'parent constraint'
        if ks >= {'pointConstraint', 'orientConstraint'}:
            return node, 'constraints'
        return node, ' + '.join(sorted(ks))
    for k in kids:
        if cmds.nodeType(k) == 'joint':
            return k, 'child'
    if cmds.nodeType(ctrl) == 'joint' and cmds.listConnections(ctrl + '.worldMatrix', type='skinCluster'):
        return ctrl, 'is the joint'
    return None, 'none'


def _rebind(joint):
    """The skins this joint drives take its current place as its rest (nothing moves)."""
    from gus_rigtool.core import shape_fixes
    inv = shape_fixes.inverse(list(cmds.getAttr(joint + '.worldMatrix[0]')))
    for plug in cmds.listConnections(joint + '.worldMatrix', plugs=True, source=False, destination=True) or []:
        node, attr = plug.split('.', 1)
        if cmds.nodeType(node) == 'skinCluster' and attr.startswith('matrix['):
            idx = attr[len('matrix['):-1]
            cmds.setAttr('%s.bindPreMatrix[%s]' % (node, idx), *inv, type='matrix')


def _unlock(node):
    for a in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz'):
        try:
            cmds.setAttr(node + '.' + a, lock=False)
        except RuntimeError:
            pass


def _place_mirrored(node, twin, ax):
    """node gets twin's world matrix reflected (true mirror: X mirrored, Y / Z the same), at its own spot."""
    m = mirror_engine.mirror_list(cmds.xform(twin, query=True, worldSpace=True, matrix=True), 'true', ax)
    m[12:15] = cmds.xform(node, query=True, worldSpace=True, translation=True)
    _unlock(node)
    cmds.xform(node, worldSpace=True, matrix=m)


def link_bind_group(key=None):
    """A build's bind joints' group follows its controls' group (moving / parenting the controls' group moves
    the joints too). Returns True when linked."""
    builds = _find_builds()
    key = key or _pick_build(builds)
    if key not in builds:
        return False
    tops = [n for n in builds[key]['nodes'] if cmds.objExists(n)]
    ctrls = [n for n in tops if n.endswith('_ctrls_grp')]
    binds = [n for n in tops if n.endswith('_bind_grp')]
    if not ctrls or not binds:
        return False
    if cmds.listRelatives(binds[0], type='parentConstraint'):
        return True
    cmds.parentConstraint(ctrls[0], binds[0], maintainOffset=True)
    cmds.scaleConstraint(ctrls[0], binds[0], maintainOffset=True)
    return True


def mirror_sides(surface=None, axis='X', tolerance=None):
    """
    A ribbon that runs round both sides (a mouth loop): each control on the -X side - and the joint that copies
    it - gets the mirror of its +X twin (true mirror: +X goes outward on both sides, Y up and Z forward the
    same), so selecting both and moving them moves them as mirror images. Nothing moves at rest: the controls,
    the joints and the ribbon stay where they are (the ribbon's skin takes the joints' new axes as rest), so
    weights are untouched. Centre controls keep their axes. Returns how many controls were done.
    """
    builds = _find_builds()
    key = _resolve(surface) if surface else _pick_build(builds)
    if key not in builds:
        raise RuntimeError('select the ribbon (or one of its controls) first.')
    if is_asymmetric(key):                              # 5.6.27: marked as not meant to mirror
        raise RuntimeError('%s is marked "not symmetric" - its sides are left as they are (Ribbon tab > '
                           'Not symmetric to take the mark off).' % _label(key))
    ax = 'XYZ'.index(axis)
    offs = _build_offsets(builds[key])
    ctrls = {i: _control_under(o) for i, o in offs.items()}
    pos = {i: cmds.xform(c, query=True, worldSpace=True, translation=True) for i, c in ctrls.items() if c}
    span = max(max(p[k] for p in pos.values()) - min(p[k] for p in pos.values()) for k in range(3)) or 1.0
    tol = tolerance if tolerance is not None else span * 0.01
    lefts = [i for i, p in pos.items() if p[ax] > tol]
    rights = [i for i, p in pos.items() if p[ax] < -tol]
    held_between = [g for r in rights for g in constrained_between(offs[r], ctrls[r])]
    if held_between:                                    # 5.6.27: they'd keep their old turn under a flipped offset
        raise RuntimeError('groups from the offset down to the control are held by a constraint (%s) - flipping '
                           'the offset would leave their controls turned wrong. Nothing changed.'
                           % ', '.join(g.split('|')[-1] for g in held_between[:6]))
    done = 0
    cmds.undoInfo(openChunk=True, chunkName='gusrigRibbonMirrorSides')
    try:
        free = list(lefts)
        for r in sorted(rights, key=lambda i: pos[i][ax]):
            if not free:
                break
            q = list(pos[r])
            q[ax] = -q[ax]
            left = min(free, key=lambda i: sum((a - b) ** 2 for a, b in zip(pos[i], q)))
            free.remove(left)
            off, ctrl = offs[r], ctrls[r]
            kids, driven = _driven_by(ctrl)
            keep = {k: cmds.xform(k, query=True, worldSpace=True, matrix=True) for k in kids}
            held = {}                                           # constrained nodes: where they are now
            for node, con in driven:
                held.setdefault(node, [cmds.xform(node, query=True, worldSpace=True, matrix=True), []])[1].append(con)
            _place_mirrored(off, offs[left], ax)
            for k, wm in keep.items():                          # children stay where they were
                cmds.xform(k, worldSpace=True, matrix=wm)
                if cmds.nodeType(k) == 'joint':
                    _rebind(k)
            for node, (wm, cons) in held.items():               # constrained nodes: back, then remade
                _remake_constraints(node, cons, wm)
            # the joint copying the control (pivot on the shape): its group turns the same way
            cop, twin_cop = _copier(ctrl), _copier(ctrls[left])
            if cop and twin_cop:
                cop_off = cmds.listRelatives(cop, parent=True, fullPath=True)[0]
                twin_off = cmds.listRelatives(twin_cop, parent=True, fullPath=True)[0]
                _place_mirrored(cop_off, twin_off, ax)
                _rebind(cmds.ls(cop.split('|')[-1], long=True)[0])
            done += 1
        link_bind_group(key)
    except Exception:
        cmds.undoInfo(closeChunk=True)
        try:                                                    # nothing left half mirrored - only our own step
            if 'gusrigRibbonMirrorSides' in (cmds.undoInfo(query=True, undoName=True) or ''):
                cmds.undo()
        except RuntimeError:
            pass
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    _say('%d control(s) on the other side mirror their twins (+X out on both sides, Y up, Z forward); '
         'nothing moved.' % done)
    return done


ASYM_ATTR = 'rrbNotSymmetric'


def _label(key):
    return str(key).split('|')[-1]


def _ctrls_grp(build):
    for n in build.get('nodes') or []:
        if n.endswith('_ctrls_grp') and cmds.objExists(n):
            return n
    return None


def is_asymmetric(key):
    """5.6.27: True when the ribbon is marked 'not symmetric' (its base isn't - the hood's collar): no mirror
    warnings, Make the right side mirror the left / Make symmetric leave it alone, mirror pose gives its
    controls no twin."""
    try:
        builds = _find_builds()
        if key not in builds:
            return False
        grp = _ctrls_grp(builds[key])
        return bool(grp and cmds.attributeQuery(ASYM_ATTR, node=grp, exists=True) and
                    cmds.getAttr(grp + '.' + ASYM_ATTR))
    except Exception:
        return False


def set_asymmetric(surface=None, on=True):
    """Mark (on) or unmark the picked ribbon as not symmetric. Nothing in the rig moves. Returns the key."""
    builds = _find_builds()
    key = _resolve(surface) if surface else _pick_build(builds)
    if key not in builds:
        raise RuntimeError('select the ribbon (or one of its controls) first.')
    grp = _ctrls_grp(builds[key])
    if not grp:
        raise RuntimeError('%s has no controls group.' % _label(key))
    if not cmds.attributeQuery(ASYM_ATTR, node=grp, exists=True):
        cmds.addAttr(grp, longName=ASYM_ATTR, attributeType='bool')
    cmds.setAttr(grp + '.' + ASYM_ATTR, bool(on))
    _say('%s %s.' % (_label(key), 'marked not symmetric: no mirror warnings, the sides are left as they are'
                     if on else 'is treated as symmetric again'))
    return key


def asymmetric_controls():
    """Every control on a ribbon marked not symmetric (mirror pose gives them no twin)."""
    out = []
    for key, build in _find_builds().items():
        if is_asymmetric(key):
            for o in _build_offsets(build).values():
                c = _control_under(o)
                if c:
                    out.append(c)
    return out


def _held_by_constraint(node):
    """5.6.28: a constraint drives the node - straight, or through a pairBlend (a keyed channel or a space blend)."""
    if cmds.listConnections(node, type='constraint', source=True, destination=False):
        return True
    for pb in set(cmds.listConnections(node, type='pairBlend', source=True, destination=False) or []):
        if cmds.listConnections(pb, type='constraint', source=True, destination=False):
            return True
    return False


def constrained_between(off, ctrl):
    """Groups between a control's offset and the control that a constraint drives (the cape's _sdk groups).
    5.6.28: the offset itself too (it's the group that gets flipped), and constraints through a pairBlend."""
    out = []
    if not ctrl:
        return out
    p = (cmds.listRelatives(ctrl, parent=True, fullPath=True) or [None])[0]
    off_long = (cmds.ls(off, long=True) or [off])[0]
    while p and p != off_long:
        if _held_by_constraint(p):
            out.append(p)
        p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
    if p == off_long and _held_by_constraint(p):
        out.append(p)
    return out


SYMMETRY_TOL = 1e-4          # closer than this to the mirror spot counts as exact


def _master_sign(nodes, pos, ax):
    """+1 or -1: which side of the axis is the master. The side whose names carry L_ (the Hare's L_ side sits at
    -X), else +X."""
    from gus_rigtool.core import joint_labels
    xs = [pos[n][ax] for n in nodes if joint_labels.split_side(n)[0] == 'L']
    if xs:
        return 1.0 if sum(xs) >= 0 else -1.0
    return 1.0


def _mirror_pairs(pos, sign, ax):
    """[(master, follower, how far the follower is from the master's mirror spot)], nearest first."""
    vals = list(pos.values())
    span = max(max(p[k] for p in vals) - min(p[k] for p in vals) for k in range(3)) or 1.0 if vals else 1.0
    tol = span * 0.01
    masters = [n for n, p in pos.items() if sign * p[ax] > tol]
    followers = [n for n, p in pos.items() if sign * p[ax] < -tol]
    free, out = list(masters), []
    for f in sorted(followers, key=lambda n: -abs(pos[n][ax])):
        if not free:
            break
        q = list(pos[f])
        q[ax] = -q[ax]
        m = min(free, key=lambda n: sum((a - b) ** 2 for a, b in zip(pos[n], q)))
        d = sum((a - b) ** 2 for a, b in zip(pos[m], q)) ** 0.5
        if d > span * 0.25:                                  # nobody near its mirror spot: not a twin
            continue
        free.remove(m)
        out.append((m, f, d))
    return out


def _follicles(build):
    out = []
    for grp in [n for n in build['nodes'] if n.endswith('_follicles_grp') and cmds.objExists(n)]:
        for t in cmds.listRelatives(grp, children=True, fullPath=True, type='transform') or []:
            if cmds.listRelatives(t, shapes=True, type='follicle'):
                out.append(t)
    return out


def _wpos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)


def _closest_uv(shape, point):
    """The follicle parameters (0..1) of the surface spot closest to point."""
    cps = cmds.createNode('closestPointOnSurface')
    try:
        cmds.connectAttr(shape + '.worldSpace[0]', cps + '.inputSurface')
        cmds.setAttr(cps + '.inPosition', *point, type='double3')
        u = cmds.getAttr(cps + '.result.parameterU')
        v = cmds.getAttr(cps + '.result.parameterV')
    finally:
        cmds.delete(cps)
    u0, u1 = cmds.getAttr(shape + '.minMaxRangeU')[0]
    v0, v1 = cmds.getAttr(shape + '.minMaxRangeV')[0]
    return (u - u0) / ((u1 - u0) or 1.0), (v - v0) / ((v1 - v0) or 1.0)


def symmetry_report(surface=None, axis='X'):
    """5.0.7: how far each other-side control / follicle is from the exact mirror of its twin.
    {'key', 'sign', 'controls': [(master offset, follower offset, off)], 'follicles': [...]} - only pairs off
    by more than SYMMETRY_TOL."""
    builds = _find_builds()
    key = _resolve(surface) if surface else _pick_build(builds)
    if key not in builds:
        raise RuntimeError('select the ribbon (or one of its controls) first.')
    ax = 'XYZ'.index(axis)
    offs = _build_offsets(builds[key])
    named = {}
    for o in offs.values():
        c = _control_under(o)
        named[o] = c or o
    opos = dict((o, _wpos(o)) for o in offs.values())
    fols = _follicles(builds[key])
    fpos = dict((f, _wpos(f)) for f in fols)
    sign = _master_sign(list(named.values()) + fols, dict(
        [(named[o], p) for o, p in opos.items()] + list(fpos.items())), ax)
    return {'key': key, 'sign': sign, 'axis': ax,
            'controls': [x for x in _mirror_pairs(opos, sign, ax) if x[2] > SYMMETRY_TOL],
            'follicles': [x for x in _mirror_pairs(fpos, sign, ax) if x[2] > SYMMETRY_TOL]}


def make_symmetric(surface=None, axis='X', report=None):
    """
    5.0.7: the other side lands exactly on the mirror of the master side (the side named L_, else +X):
    - each control's offset group moves to the mirror spot of its twin's (the joint that follows it comes along);
      every skin those joints drive takes their new place as rest, so neither the ribbon nor the mesh moves;
    - each follicle slides on the surface to the spot closest to its twin's mirror spot (its joint comes along,
      the mesh's skin keeps it still).
    Only position; the axes are 'Make the right side mirror the left'. One undo. Returns the lines it did, with
    how far each moved and any follicle that can't reach the exact spot (the surface itself is lopsided there).
    """
    r = report or symmetry_report(surface, axis)
    ax, key = r['axis'], r['key']
    if is_asymmetric(key):                              # 5.6.27
        raise RuntimeError('%s is marked "not symmetric" - nothing moved.' % _label(key))
    shape = surface_and_shape(key)[1]
    lines = []
    cmds.undoInfo(openChunk=True, chunkName='gusrigRibbonSymmetric')
    try:
        for master, off, d in r['controls']:
            ctrl = _control_under(off)
            want = list(_wpos(master))
            want[ax] = -want[ax]
            have = _wpos(off)
            delta = [a - b for a, b in zip(want, have)]
            joints = []
            bind = bind_of(ctrl)[0] if ctrl else None
            if bind and bind not in (cmds.listRelatives(off, allDescendents=True, fullPath=True) or []):
                joints.append(bind)
            cop = _copier(ctrl) if ctrl else None
            _unlock(off)
            cmds.xform(off, worldSpace=True, translation=want)
            if cop:                                         # the copying joint's own group comes along
                cop_off = cmds.listRelatives(cop, parent=True, fullPath=True)[0]
                p = _wpos(cop_off)
                _unlock(cop_off)
                cmds.xform(cop_off, worldSpace=True, translation=[a + b for a, b in zip(p, delta)])
                joints.append(cop)
            joints += [j for j in cmds.listRelatives(off, allDescendents=True, type='joint', fullPath=True) or []]
            for j in joints:
                _rebind(cmds.ls(j, long=True)[0])
            lines.append('control %s: moved %.4f' % (naming.short_name(ctrl or off), d))
        for master, fol, d in r['follicles']:
            want = list(_wpos(master))
            want[ax] = -want[ax]
            fshape = cmds.listRelatives(fol, shapes=True, type='follicle', fullPath=True)[0]
            u, v = _closest_uv(shape, want)
            cmds.setAttr(fshape + '.parameterU', u)
            cmds.setAttr(fshape + '.parameterV', v)
            for j in cmds.listRelatives(fol, allDescendents=True, type='joint', fullPath=True) or []:
                _rebind(j)
            left = sum((a - b) ** 2 for a, b in zip(_wpos(fol), want)) ** 0.5
            lines.append('follicle %s: moved %.4f%s' % (naming.short_name(fol), d, (
                ', still %.4f off (the surface is lopsided there)' % left) if left > SYMMETRY_TOL else ''))
    except Exception:
        cmds.undoInfo(closeChunk=True)
        try:
            cmds.undo()                                     # nothing left half done
        except RuntimeError:
            pass
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    _say('%s: %d control(s) and %d follicle(s) now mirror their twins exactly; the mesh did not move.' % (
        naming.short_name(key), len(r['controls']), len(r['follicles'])))
    return lines


def mirror_build(axis='X', prefix='', color=None, style='true'):
    """
    Mirror a finished build to the other side of the model. Which build: the selected one (select
    its ribbon or any control), else the last one made. The ribbon is duplicated and mirrored
    across the plane perpendicular to the axis (through the world origin), and the same rig is
    built on the copy, as a separate rig that shares nothing with the first. Each new control is
    the reflection of its twin, so the same channel values move the pair in mirrored directions.
    The copy's surface direction is reversed across the width, so it shades the right way round.
    """
    builds = _find_builds()
    key = _pick_build(builds)
    if key is None:
        return
    build = builds[key]

    settings = _build_settings(build)
    if settings is None:
        raise RuntimeError('This build was made before mirroring existed and has no stored '
                           'settings. Delete it and build it again, then mirror it.')
    if not cmds.objExists(key):
        raise RuntimeError('The ribbon "%s" no longer exists.' % key)
    if axis not in AXES:
        raise RuntimeError('Mirror axis must be X, Y or Z.')
    axis_index = 'XYZ'.index(axis)

    # names: swap the side; a name without a side gets the other side from the position
    pairs = sides.default_pairs()
    left_prefix = settings.get('prefix') or key.split('|')[-1]
    short = key.split('|')[-1]
    side = sides.side_from_position(key, axis_index)
    other = 'R' if side == 'L' else 'L'
    new_prefix = prefix.strip() or _swap_side(left_prefix) or \
        (sides.add_side(left_prefix, other, pairs[0]) if side in ('L', 'R') else None)
    if not new_prefix:
        raise RuntimeError('Type a Mirror prefix: "%s" has no side and sits in the middle.' % left_prefix)
    new_name = _swap_side(short) or \
        (sides.add_side(short, other, pairs[0]) if side in ('L', 'R') else new_prefix + '_ribbon')
    if cmds.objExists(new_name):
        raise RuntimeError('"%s" already exists. Rename it, or type another Mirror prefix.' % new_name)

    # the first side's controls, reflected
    if style not in MIRROR_STYLES:
        style = 'true'
    matrices = _mirror_matrices(build, axis_index, style)
    if settings.get('make_ctrls', True) and not matrices:
        raise RuntimeError('No controls were found on this build, so there is nothing to mirror.')

    cmds.undoInfo(openChunk=True)
    try:
        # a copy of the ribbon, with every CV moved to its mirrored position (same CV order, so
        # joint 3 on one side is joint 3 on the other)
        dup = cmds.duplicate(key, name=new_name)[0]
        if cmds.listRelatives(dup, parent=True):
            dup = cmds.parent(dup, world=True)[0]
        for sh in cmds.listRelatives(dup, shapes=True, fullPath=True) or []:   # unique shape name
            cmds.rename(sh, naming.short_name(dup) + 'Shape#')
        cvs = cmds.ls('%s.cv[*][*]' % dup, flatten=True)
        points = [list(cmds.pointPosition(cv, world=True)) for cv in cvs]
        for cv, p in zip(cvs, points):
            p[axis_index] = -p[axis_index]
            cmds.xform(cv, worldSpace=True, translation=p)

        # A mirror image has its front side reversed (the surface would shade black). Reverse
        # the V direction, across the width, to turn it back: that only changes the order of the
        # CVs across the ribbon, so the order along its length (joint 3 = joint 3) is kept.
        cmds.reverseSurface(dup, direction=1, constructionHistory=False, replaceOriginal=True)

        new_settings = dict(settings)
        # reversing V swaps which edge is V = 0, so mirror the position across the width as well
        new_settings['v_pos'] = 1.0 - float(settings.get('v_pos', DEFAULTS['v_pos']))
        new_settings['prefix'] = new_prefix
        if color:
            new_settings['color'] = list(color)
        new_settings['use_side_colors'] = False
        if settings.get('use_side_colors'):
            new_settings['color'] = colors.side_colors()['R' if side != 'R' else 'L']
        new_settings['mirror_axis'] = axis          # remembered, so Rebuild can mirror again
        new_settings['mirror_style'] = style
        top = build_rig(new_settings, surface=dup,
                        mirror={'matrices': matrices, 'of': key, 'style': style},
                        _own_chunk=False)
        _link_builds(key, cmds.ls(dup, long=True)[0], style)
    finally:
        cmds.undoInfo(closeChunk=True)

    _say('%s mirrored to %s (%s).' % (short, new_name, MIRROR_STYLES[style]))
    return top


REPORT = {"ctrl": None}       # the report box of the open Ribbon tab (set by the UI)


def _say(message):
    utils.info(TOOL, message)


def _report(lines):
    """Show lines on the status line and in the Ribbon tab's report box."""
    for line in lines:
        print('Gus_Rigtool Ribbon: ' + line)
    if lines:
        warn = any(("->" in l and "fixed" not in l) or "could not" in l for l in lines)
        (utils.warn if warn else utils.info)(TOOL, lines[0] if len(lines) == 1 else "%s (+%d more, see the report)" % (lines[0], len(lines) - 1))
    try:
        if REPORT["ctrl"] and cmds.scrollField(REPORT["ctrl"], exists=True):
            cmds.scrollField(REPORT["ctrl"], edit=True, text='\n'.join(lines))
    except Exception:
        pass



# ----------------------------------------------------------------------------
# Gus_Rigtool additions: current ribbon, surface check, rebuild
# ----------------------------------------------------------------------------

def current_ribbon():
    """
    The ribbon the buttons act on: the selected ribbon (or a node of its build), else the last
    build. {'surface', 'built', 'follicles', 'controls', 'mirror_of', 'mirrored_to'} or None.
    """
    key = None
    sel = cmds.ls(sl=True, long=True) or []
    if sel:
        key = _selected_surface()
        if key and not cmds.objExists(key):
            key = None
        if key and cmds.nodeType(key) != 'transform':
            key = None
        if key and not (cmds.listRelatives(key, shapes=True, type='nurbsSurface') or []):
            key = None
    builds = _find_builds()
    if key is None:
        key = _last['surface'] if _last['surface'] in builds else None
    if key is None:
        return None
    key = cmds.ls(key, long=True)[0] if cmds.objExists(key) else key
    info = {'surface': key, 'built': key in builds, 'follicles': 0, 'controls': 0,
            'mirror_of': None, 'mirrored_to': None}
    if info['built']:
        b = builds[key]
        for top in b['nodes']:
            kids = cmds.listRelatives(top, allDescendents=True, type='transform', fullPath=True) or []
            for n in [top] + kids:
                short = n.split('|')[-1]
                if '_fol_' in short and cmds.listRelatives(n, shapes=True, type='follicle'):
                    info['follicles'] += 1
            if cmds.objExists(top + '.rrbMirrorOf'):
                info['mirror_of'] = _resolve(cmds.getAttr(top + '.rrbMirrorOf'))
        info['controls'] = len(_build_offsets(b))
        for other, ob in builds.items():
            for top in ob['nodes']:
                if cmds.objExists(top + '.rrbMirrorOf') and _resolve(cmds.getAttr(top + '.rrbMirrorOf')) == key:
                    info['mirrored_to'] = other
    return info


def runs_along_v(surface):
    """True when the ribbon's length runs along V (the builder puts its follicles along U)."""
    surf, shape = surface_and_shape(surface)
    sel = om.MSelectionList()
    sel.add(shape)
    fn = om.MFnNurbsSurface(sel.getDagPath(0))
    (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV

    def length(along_u, fixed, steps=40):
        pts = []
        for k in range(steps + 1):
            t = k / float(steps)
            u, v = (u0 + (u1 - u0) * t, fixed) if along_u else (fixed, v0 + (v1 - v0) * t)
            pts.append(fn.getPointAtParam(u, v, om.MSpace.kWorld))
        return sum((b - a).length() for a, b in zip(pts, pts[1:]))
    return length(False, (u0 + u1) / 2.0) > length(True, (v0 + v1) / 2.0)


def along_u(surface):
    """Make the ribbon run along U (swap U / V when it runs along V). Returns True if it was swapped."""
    if runs_along_v(surface):
        cmds.reverseSurface(surface, direction=3, constructionHistory=False, replaceOriginal=True)
        return True
    return False


def _turn_along_u(surf):
    """Before a build: 'swapped' if the ribbon ran along V and was swapped, 'deformed' if it runs along V but
    has deformers (left as is), else None."""
    try:
        if not runs_along_v(surf):
            return None
    except Exception:
        return None
    hist = cmds.listHistory(surf, pruneDagObjects=True) or []
    if cmds.ls(hist, type='geometryFilter') if hist else []:
        return 'deformed'
    along_u(surf)
    return 'swapped'


def surface_check(surface):
    """
    Facts about a ribbon before building: (level 'ok'|'warn', [lines]).
    Which way it runs (U should run along the length), twists across the width, CV rows.
    """
    surf, shape = surface_and_shape(surface)
    sel = om.MSelectionList()
    sel.add(shape)
    fn = om.MFnNurbsSurface(sel.getDagPath(0))
    (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV
    um, vm = (u0 + u1) / 2.0, (v0 + v1) / 2.0

    def length(along_u, fixed, steps=60):
        pts = []
        for k in range(steps + 1):
            t = k / float(steps)
            u, v = (u0 + (u1 - u0) * t, fixed) if along_u else (fixed, v0 + (v1 - v0) * t)
            pts.append(fn.getPointAtParam(u, v, om.MSpace.kWorld))
        return sum((b - a).length() for a, b in zip(pts, pts[1:]))

    len_u, len_v = length(True, vm), length(False, um)
    rows = cmds.getAttr(shape + '.spansU') + cmds.getAttr(shape + '.degreeU')
    lines, level = [], 'ok'
    if len_u >= len_v:
        lines.append('runs along U (length %.3g, width %.3g), %d CV rows' % (len_u, len_v, rows))
    else:
        level = 'warn'
        lines.append('runs along V (length %.3g along V): press Swap U/V' % len_v)

    flips = 0
    prev = None
    for k in range(41):
        u = u0 + (u1 - u0) * k / 40.0
        across = fn.getPointAtParam(u, v1, om.MSpace.kWorld) - fn.getPointAtParam(u, v0, om.MSpace.kWorld)
        if prev is not None and (across * prev) < 0:
            flips += 1
        prev = across
    if flips:
        level = 'warn'
        lines.append('twisted: the width turns over %d time(s) - check the loft curves (Check / Fix)' % flips)
    else:
        lines.append('no twist')
    nrm = fn.normal(um, vm, om.MSpace.kWorld)
    axis = max(range(3), key=lambda i: abs(nrm[i]))
    lines.append('front side faces about %s%s' % ('+' if nrm[axis] >= 0 else '-', 'XYZ'[axis]))
    return level, lines


MIRROR_KEEPS = ('prefix', 'color', 'use_side_colors', 'v_pos', 'mirror_axis', 'mirror_style')


def _mirror_of(key, builds):
    """The first side a build was mirrored from, or None."""
    for top in builds.get(key, {'nodes': []})['nodes']:
        if cmds.objExists(top + '.rrbMirrorOf'):
            return _resolve(cmds.getAttr(top + '.rrbMirrorOf')) or None
    return None


def _mirrors_of(key, builds):
    """The builds mirrored from this one."""
    return [other for other in builds if other != key and _mirror_of(other, builds) == key]


def _rebuild_mirror(key, first):
    """
    Build a mirrored ribbon again from its first side, keeping it a mirror: the first side's
    settings and controls, reflected; this side keeps its own name, colour, V position, mirror axis
    and style. The mirrored ribbon surface itself is kept. Call inside an undo chunk.
    """
    builds = _find_builds()
    if first not in builds:
        raise RuntimeError('"%s" is a mirror of "%s", which has no build now. Build the first side, '
                           'then Rebuild.' % (naming.short_name(key), naming.short_name(first)))
    first_settings = _build_settings(builds[first])
    own = _build_settings(builds[key]) or {}
    if first_settings is None:
        raise RuntimeError('"%s" has no stored settings (made with an old version). Rebuild it first.'
                           % naming.short_name(first))
    new = dict(first_settings)
    for k in MIRROR_KEEPS:
        if k in own:
            new[k] = own[k]
    if 'v_pos' not in own:
        new['v_pos'] = 1.0 - float(first_settings.get('v_pos', DEFAULTS['v_pos']))
    axis = new.get('mirror_axis') if new.get('mirror_axis') in AXES else 'X'
    style = new.get('mirror_style') if new.get('mirror_style') in MIRROR_STYLES else 'true'
    new['mirror_axis'], new['mirror_style'] = axis, style
    matrices = _mirror_matrices(builds[first], 'XYZ'.index(axis), style)

    from gus_rigtool.core import ribbon_keep
    saved = ribbon_keep.park(key)
    delete_build(key)
    top = build_rig(new, surface=key, mirror={'matrices': matrices, 'of': first, 'style': style},
                    _own_chunk=False)
    _link_builds(first, cmds.ls(key, long=True)[0], style)
    ribbon_keep.restore(saved, cmds.ls(key, long=True)[0])
    return top


def rebuild(settings, surface=None, update_mirror=None):
    """
    Delete the build of the ribbon and build it again with settings. One undo.
    - A mirrored ribbon (made with Mirror build) is built again from its first side, so it stays
      a mirror (settings ignored, it follows the first side).
    - A first side with a mirror also rebuilds the mirror, when update_mirror (default: the
      'rebuild_mirror' setting) is on.
    """
    info = current_ribbon() if surface is None else {'surface': cmds.ls(surface, long=True)[0], 'built': True}
    if not info:
        raise RuntimeError('Select a ribbon (or a node of its build) first.')
    key = info['surface']
    if update_mirror is None:
        update_mirror = (settings or {}).get('rebuild_mirror', DEFAULTS['rebuild_mirror'])

    builds = _find_builds()
    first = _mirror_of(key, builds) if key in builds else None
    if first and not cmds.objExists(first):
        utils.warn(TOOL, 'the first side "%s" is gone, so %s is rebuilt as a normal ribbon.'
                   % (naming.short_name(first), naming.short_name(key)))
        first = None

    done = []
    cmds.undoInfo(openChunk=True)
    try:
        if first:
            top = _rebuild_mirror(key, first)
            done.append('%s rebuilt as the mirror of %s (it follows the first side)'
                        % (naming.short_name(key), naming.short_name(first)))
        else:
            from gus_rigtool.core import ribbon_keep
            twins = _mirrors_of(key, builds) if update_mirror else []
            saved = ribbon_keep.park(key) if key in builds else {}
            if key in builds:
                delete_build(key)
            top = build_rig(settings, surface=key, _own_chunk=False)
            kept = ribbon_keep.restore(saved, cmds.ls(key, long=True)[0])
            done.append('%s rebuilt%s' % (naming.short_name(key),
                                          ' (the skin of %d mesh(es) kept on the new joints)' % kept if kept else ''))
            for twin in twins:
                if cmds.objExists(twin):
                    _rebuild_mirror(twin, key)
                    done.append('its mirror %s too' % naming.short_name(twin))
        _last['surface'] = key
        if top and cmds.objExists(top[-1]):
            cmds.select(top[-1])                  # keeps this ribbon the current one
    finally:
        cmds.undoInfo(closeChunk=True)
    _say(', '.join(done) + '.')
    return top


def rebuild_preview(settings, surface=None):
    """What Rebuild will do: {'ribbon', 'controls_now', 'controls_new', 'follicles_new', 'meshes'} (meshes: the
    other meshes skinned to its joints, whose weights are kept)."""
    from gus_rigtool.core import ribbon_keep
    info = current_ribbon() if surface is None else {'surface': _resolve(surface)}
    if not info:
        raise RuntimeError('Select a ribbon (or a node of its build) first.')
    key = info['surface']
    builds = _find_builds()
    s = dict(DEFAULTS)
    s.update(settings or {})
    surf, shape = surface_and_shape(key)
    n, _u = follicle_params(surf, shape, s)
    new = _control_indices(n, s['ctrl_mode'], s['ctrl_every'], s['ctrl_list'],
                           s['include_ends'] and not is_looped(surf)) if s['make_ctrls'] else []
    now = len(_build_offsets(builds[key])) if key in builds else 0
    meshes = []
    if key in builds:
        joints = ribbon_keep.bind_joints(key)
        for skin in ribbon_keep.other_skins(joints, builds[key]['skins']):
            for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
                meshes.append((cmds.listRelatives(g, parent=True) or [g])[0])
    return {'ribbon': key, 'controls_now': now, 'controls_new': len(new), 'follicles_new': n, 'meshes': meshes}


def replace_surface(old, new_surface, settings=None):
    """Build on a new surface with the old build's settings (or settings), the meshes' weights moved onto the new
    joints (same name, else the nearest); the old build goes and the old surface is hidden and renamed _old.
    Returns the new build's top nodes."""
    builds = _find_builds()
    old = _resolve(old)
    if old not in builds:
        raise RuntimeError('pick a built ribbon to replace.')
    st = settings or _build_settings(builds[old]) or {}
    from gus_rigtool.core import ribbon_keep
    cmds.undoInfo(openChunk=True, chunkName='gusrigRibbonReplace')
    try:
        saved = ribbon_keep.park(old)
        name = naming.short_name(old)
        delete_build(old)
        old_t = cmds.rename(old, naming.unique(name + '_old'))
        cmds.setAttr(old_t + '.visibility', 0)
        new_t = cmds.rename(new_surface, name)
        top = build_rig(st, surface=new_t, _own_chunk=False)
        kept = ribbon_keep.restore(saved, cmds.ls(new_t, long=True)[0])
    finally:
        cmds.undoInfo(closeChunk=True)
    _say('%s rebuilt on the new surface%s; the old one is hidden as %s.' % (
        name, ' (the skin of %d mesh(es) kept)' % kept if kept else '', naming.short_name(old_t)))
    return top


def to_copying(surface=None, scale=False):
    """The reverse of to_constraints: each bind joint gets its own group (on the joint, with the control's axes) in
    _bind_grp and copies its control's channels (translate, rotate; scale too with scale). Nothing moves, the skin
    takes the joints' new axes as rest. Controls must be at rest. Returns how many joints were switched."""
    import json
    builds = _find_builds()
    key = _resolve(surface) if surface else _pick_build(builds)
    if key not in builds:
        raise RuntimeError('select the ribbon (or one of its controls) first.')
    offs = _build_offsets(builds[key])
    pairs = []
    for o in offs.values():
        c = _control_under(o)
        j, mode = bind_of(c) if c else (None, 'none')
        if j and mode == 'constraints':
            pairs.append((c, o, j))
    if not pairs:
        raise RuntimeError('this ribbon has no joints following by constraints (already copying?).')
    posed = [naming.short_name(c) for c, _o, _j in pairs
             if any(abs(v) > 1e-4 for a in ('translate', 'rotate') for v in cmds.getAttr(c + '.' + a)[0])]
    if posed:
        raise RuntimeError('put the controls at rest first (Reset): %s' % ', '.join(posed[:5]))
    bind_grp = [n for n in builds[key]['nodes'] if n.endswith('_bind_grp') and cmds.objExists(n)]
    done = 0
    cmds.undoInfo(openChunk=True, chunkName='gusrigRibbonToCopying')
    try:
        for ctrl, off, joint in pairs:
            jid = utils.uuid(joint)
            pos = cmds.xform(joint, query=True, worldSpace=True, translation=True)
            for con in cmds.listRelatives(joint, type='constraint', fullPath=True) or []:
                cmds.delete(con)
            joint = utils.path(jid)
            m = cmds.xform(off, query=True, worldSpace=True, matrix=True)
            m[12:15] = pos
            grp = cmds.createNode('transform', name=naming.unique(naming.short_name(joint) + '_offset'))
            if bind_grp:
                grp = cmds.parent(grp, bind_grp[0])[0]
            grp = cmds.ls(grp, long=True)[0]
            cmds.xform(grp, worldSpace=True, matrix=m)
            cmds.parent(joint, grp)
            joint = utils.path(jid)
            for a in ('translate', 'rotate', 'jointOrient'):
                try:
                    cmds.setAttr(joint + '.' + a, 0, 0, 0)
                except RuntimeError:
                    pass
            cmds.setAttr(joint + '.scale', 1, 1, 1)
            for ch in ('translate', 'rotate') + (('scale',) if scale else ()):
                cmds.connectAttr(ctrl + '.' + ch, joint + '.' + ch, force=True)
            _rebind(joint)
            done += 1
        st = _build_settings(builds[key]) or {}
        st['pivot_scale'] = bool(scale)
        for node in builds[key]['nodes']:
            if cmds.objExists(node + '.rrbSettings') and cmds.getAttr(node + '.rrbSettings'):
                cmds.setAttr(node + '.rrbSettings', json.dumps(st), type='string')
        link_bind_group(key)
    finally:
        cmds.undoInfo(closeChunk=True)
    _say('%d joint(s) now copy their controls (direct connections%s); nothing moved, skin kept.'
         % (done, ', scale too' if scale else ''))
    return done


def preview_points(surface, s):
    """World positions where the follicles would go, without building anything."""
    surf, shape = surface_and_shape(surface)
    n, u_vals = follicle_params(surf, shape, s)
    sel = om.MSelectionList()
    sel.add(shape)
    fn = om.MFnNurbsSurface(sel.getDagPath(0))
    (u0, u1), (v0, v1) = fn.knotDomainInU, fn.knotDomainInV
    v = v0 + (v1 - v0) * float(s['v_pos'])
    out = []
    for u in u_vals:
        p = fn.getPointAtParam(u0 + (u1 - u0) * u, v, om.MSpace.kWorld)
        out.append([p.x, p.y, p.z])
    return n, out



# ----------------------------------------------------------------------------
# ribbon surfaces live in core/ribbon_surface (4.2.0); every name is still reachable from here
# ----------------------------------------------------------------------------

def _take_surface_names():
    from gus_rigtool.core import ribbon_surface
    g = globals()
    for name, value in vars(ribbon_surface).items():
        if name.startswith("__") or name in ("_say", "_report") or name in g:
            continue
        g[name] = value


_take_surface_names()


# ---- 5.6.9: dead twins ------------------------------------------------------------------------------------------

def _follows_something(j):
    return bool(cmds.listConnections(j, source=True, destination=False, type='constraint') or
                cmds.listConnections(j + '.translate', source=True, destination=False) or
                cmds.listConnections(j + '.rotate', source=True, destination=False))


def dead_twins(tol=None):
    """[(dead bind, working twin)]: ribbon bind joints that follow no control and sit on the spot of one that does -
    a ribbon on an edge loop that folds onto itself (the Hare's mouth: along the line where the closed lips touch,
    the upper and lower lip follicles lie on top of each other; one of each pair got the control). They do nothing,
    but sitting in the ribbon's own skin they make a loop (surface -> follicle -> joint -> surface)."""
    binds = [j for j in cmds.ls(type='joint', long=True) or [] if j.endswith('_bind')]
    if not binds:
        return []
    pos = dict((j, cmds.xform(j, query=True, worldSpace=True, translation=True)) for j in binds)
    if tol is None:
        span = max(max(p[k] for p in pos.values()) - min(p[k] for p in pos.values()) for k in range(3)) or 1.0
        tol = span * 1e-4
    live = [j for j in binds if _follows_something(j)]
    out = []
    for j in binds:
        if j in live:
            continue
        twin = [x for x in live if sum((a - b) ** 2 for a, b in zip(pos[x], pos[j])) <= tol * tol]
        if twin:
            out.append((j, twin[0]))
    return out


def _weight_in(skin, joint):
    total = 0.0
    for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
        t = cmds.nodeType(g)
        comp = g + ('.vtx[*]' if t == 'mesh' else '.cv[*][*]' if t == 'nurbsSurface' else '.cv[*]')
        try:
            v = cmds.skinPercent(skin, comp, transform=joint, query=True) or 0
        except (RuntimeError, ValueError):
            continue
        total += sum(v) if isinstance(v, list) else v
    return total


def dead_twin_skins(pairs=None):
    """[(dead bind, skin)] where a dead twin is an influence with no weight (safe to take out)."""
    out = []
    for j, _twin in (pairs if pairs is not None else dead_twins()):
        for sk in set(cmds.listConnections(j + '.worldMatrix', type='skinCluster') or []):
            if _weight_in(sk, j) < 1e-4:
                out.append((j, sk))
    return out


def fix_dead_twins(items=None):
    """Dead twins out of every skin where they have no weight. The joints stay (the build's record keeps them)."""
    n = 0
    for j, sk in (items if items is not None else dead_twin_skins()):
        cmds.skinCluster(sk, edit=True, removeInfluence=j)
        n += 1
    return n
