"""
Ribbon surfaces (split out of core/ribbon.py in 4.2.0): edge loops to curves, checking / fixing curves before a
loft, lofting, a plane, swapping U / V, flipping normals. core/ribbon still has every name, so
ribbon.edge_to_curve(...) works as before.
"""

import math

import maya.cmds as cmds



def _rb():
    from gus_rigtool.core import ribbon
    return ribbon


def _say(message):
    from gus_rigtool.core import ribbon
    ribbon._say(message)


def _report(lines):
    from gus_rigtool.core import ribbon
    ribbon._report(lines)


# ----------------------------------------------------------------------------
# surface tools: plane, edge to curve, curve check, loft
# ----------------------------------------------------------------------------

EDGE_FORMS = {'Best guess': 2, 'Open': 0, 'Closed': 1}          # polyToCurve form values
FORM_NAMES = {0: 'open', 1: 'closed', 2: 'periodic'}
START_RULES = ['Maya default', 'Lowest X', 'Highest X', 'Lowest Y', 'Highest Y', 'Lowest Z', 'Highest Z']
DEGREES = {'Linear': 1, 'Cubic': 3}


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _length(a):
    return (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5


def _mean(points):
    n = float(len(points))
    return [sum(p[c] for p in points) / n for c in range(3)]


def _angle_deg(a, b):
    la, lb = _length(a), _length(b)
    if la < 1e-12 or lb < 1e-12:
        return 0.0
    cosv = max(-1.0, min(1.0, _dot(a, b) / (la * lb)))
    return math.degrees(math.acos(cosv))


def _winding(points, centre):
    """Normal of the way a loop of points winds around its centre (its sign gives the direction)."""
    w = [0.0, 0.0, 0.0]
    for k in range(len(points)):
        c = _cross(_sub(points[k], centre), _sub(points[(k + 1) % len(points)], centre))
        w = [w[0] + c[0], w[1] + c[1], w[2] + c[2]]
    return w


def _periodic_edit_points(cvs, degree):
    """
    Edit points (the points the curve passes through at its knots) of a uniform periodic B-spline
    whose distinct CVs are cvs. Edit point j is where the curve would start if its seam were
    moved j steps along. Plain maths, no Maya.
    """
    n = len(cvs)
    ext = [list(c) for c in cvs] + [list(c) for c in cvs[:degree]]
    knots = list(range(len(ext) + degree + 1))
    return [_rb()._bspline_point(degree + j, degree, knots, ext) for j in range(n)]


def _rotate_cvs(cvs, shift):
    """The CV list of the same periodic curve with its seam moved `shift` steps along."""
    shift %= len(cvs)
    return list(cvs[shift:]) + list(cvs[:shift])


def _curve_shape(curve):
    shapes = cmds.listRelatives(curve, shapes=True, noIntermediate=True, type='nurbsCurve', fullPath=True) or []
    if not shapes:
        raise RuntimeError('"%s" is not a NURBS curve.' % curve)
    return shapes[0]


def _curve_info(curve):
    """Facts about a curve, from its CV positions (world space)."""
    shape = _curve_shape(curve)
    form = cmds.getAttr(shape + '.form')               # 0 open, 1 closed, 2 periodic
    degree = cmds.getAttr(shape + '.degree')
    spans = cmds.getAttr(shape + '.spans')
    count = spans if form == 2 else spans + degree
    cvs = [list(cmds.pointPosition('%s.cv[%d]' % (curve, i), world=True)) for i in range(count)]
    return {'curve': curve, 'shape': shape, 'form': form, 'degree': degree, 'spans': spans, 'cvs': cvs}


def _enrich(info):
    """Adds start, end, centre, size, edit points and winding to a curve's info."""
    cvs, form, degree = info['cvs'], info['form'], info['degree']
    if form == 2:
        edits = _periodic_edit_points(cvs, degree)
        start = end = edits[0]
    else:
        edits = None
        start, end = cvs[0], cvs[-1]
    info['edits'] = edits
    info['start'], info['end'] = start, end
    info['centre'] = _mean(cvs)
    lo = [min(p[c] for p in cvs) for c in range(3)]
    hi = [max(p[c] for p in cvs) for c in range(3)]
    info['size'] = _length(_sub(hi, lo)) or 1.0
    info['gap'] = _length(_sub(start, end))
    info['loop'] = form in (1, 2) or info['gap'] <= 0.02 * info['size']
    ring = edits if edits else cvs
    info['winding'] = _winding(ring, info['centre'])
    return info


def _needs_close(info):
    """An open-form curve whose ends meet (or nearly) is a loop that was never closed."""
    return info['form'] == 0 and info['gap'] <= 0.02 * info['size']


def _plan_fixes(infos, tolerance_deg=None):
    """
    For each curve, relative to the one before it: should it be reversed, and (loops) how far
    must its seam move? Pure maths on the enriched infos. Returns one dict per curve with
    reverse, shift, angle (the seam error left over once fixed, in degrees) and notes.
    """
    plans = []
    ref = None                                           # the previous curve as it will be once fixed
    for info in infos:
        plan = {'curve': info['curve'], 'reverse': False, 'shift': 0, 'angle': 0.0, 'notes': [],
                'fixable': True}
        edits = list(info['edits']) if info['edits'] else None
        start, end, winding = info['start'], info['end'], info['winding']

        if ref is not None and info['loop'] and ref['loop']:
            if _dot(winding, ref['winding']) < 0:
                plan['reverse'] = True
                plan['notes'].append('runs the opposite way round')
                winding = [-w for w in winding]
                if edits:
                    edits = [edits[0]] + edits[:0:-1]
            ref_vec = _sub(ref['start'], ref['centre'])
            if edits:
                angles = [_angle_deg(_sub(e, info['centre']), ref_vec) for e in edits]
                best = min(range(len(edits)), key=lambda j: angles[j])
                step = 360.0 / len(edits)
                tol = tolerance_deg if tolerance_deg is not None else max(2.0, step / 2.0 + 0.5)
                if angles[0] > tol and best != 0:
                    plan['shift'] = best
                    plan['notes'].append('start point is %.0f degrees off, moved %d step(s)' % (angles[0], best))
                plan['angle'] = angles[best] if plan['shift'] else angles[0]
                start = edits[plan['shift']]
            else:
                angle = _angle_deg(_sub(start, info['centre']), ref_vec)
                step = 360.0 / max(1, len(info['cvs']))
                tol = tolerance_deg if tolerance_deg is not None else max(2.0, step / 2.0 + 0.5)
                plan['angle'] = angle
                if angle > tol:
                    plan['fixable'] = False
                    plan['notes'].append('start point is %.0f degrees off, but this curve is not periodic '
                                         'so its seam cannot be moved (make it with Form: Best guess)' % angle)
        elif ref is not None and not info['loop'] and not ref['loop']:
            same = _length(_sub(start, ref['start'])) + _length(_sub(end, ref['end']))
            swapped = _length(_sub(start, ref['end'])) + _length(_sub(end, ref['start']))
            if swapped < same:
                plan['reverse'] = True
                plan['notes'].append('runs the opposite way')
                start, end = end, start
        elif ref is not None:
            plan['fixable'] = False
            plan['notes'].append('is %s but the curve before it is %s: a loft needs them to match'
                                 % ('a loop' if info['loop'] else 'open', 'a loop' if ref['loop'] else 'open'))

        ref = {'loop': info['loop'], 'start': start, 'end': end, 'centre': info['centre'], 'winding': winding}
        plans.append(plan)
    return plans


def _shift_seam(curve, shift):
    """Move the seam of a periodic curve `shift` steps along, keeping its shape. Returns the curve."""
    info = _curve_info(curve)
    if info['form'] != 2:
        raise RuntimeError('"%s" is not periodic, so its seam cannot be moved.' % curve)
    d = info['degree']
    cvs = _rotate_cvs(info['cvs'], shift)
    pts = cvs + cvs[:d]                                   # a periodic curve repeats its first CVs
    short = curve.split('|')[-1]
    new = cmds.curve(degree=d, periodic=True, point=[tuple(p) for p in pts],
                     knot=list(range(len(pts) + d - 1)), worldSpace=True)
    cmds.delete(curve)
    return cmds.rename(new, short)


def _reverse_curve(curve):
    res = cmds.reverseCurve(curve, constructionHistory=False, replaceOriginal=True)
    return res[0] if res else curve


def _close_curve(curve):
    res = cmds.closeCurve(curve, constructionHistory=False, replaceOriginal=True)
    return res[0] if res else curve


def _curves_inside(node):
    """Curves inside a group, in Outliner order (top to bottom)."""
    out = []
    for kid in cmds.listRelatives(node, children=True, type='transform', fullPath=True) or []:
        if cmds.listRelatives(kid, shapes=True, noIntermediate=True, type='nurbsCurve'):
            out.append(kid)
        out += _curves_inside(kid)
    return out


def _ordered_curves():
    """Selected NURBS curves, in the order they were selected. A selected group gives the curves
    inside it, top to bottom in the Outliner."""
    sel = cmds.ls(orderedSelection=True, long=True) or cmds.ls(sl=True, long=True) or []
    curves = []
    for node in sel:
        if '.' in node:
            node = node.split('.')[0]                     # a CV / edit point: its curve
            node = cmds.ls(node, long=True)[0] if cmds.ls(node, long=True) else node
        if cmds.nodeType(node) == 'nurbsCurve':
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
        if cmds.listRelatives(node, shapes=True, noIntermediate=True, type='nurbsCurve'):
            found = [node]
        elif cmds.nodeType(node) == 'transform':
            found = _curves_inside(node)
        else:
            found = []
        for c in found:
            if c not in curves:
                curves.append(c)
    return curves


def check_curves(curves=None, fix=False):
    """
    Check curves that will be lofted, in selection order: are the loops closed, do they run the
    same way, and do their start points (seams) line up? With fix=True the curves themselves are
    fixed (a periodic curve's seam can be moved; others can only be reversed or closed).
    Returns (curves, report lines). The curves may be renamed by a fix.
    """
    curves = list(curves) if curves else _ordered_curves()
    if len(curves) < 2:
        raise RuntimeError('Select two or more curves (or a group of them), in the order you want them '
                           'lofted. Found %d.' % len(curves))

    lines = []
    infos = [_enrich(_curve_info(c)) for c in curves]

    # 1. loops that were never closed
    for i, info in enumerate(infos):
        if _needs_close(info):
            msg = '%s is open but its ends meet (gap %.4f): it is a loop that was never closed' % (
                info['curve'].split('|')[-1], info['gap'])
            if fix:
                try:
                    curves[i] = _close_curve(info['curve'])
                    msg += ' -> closed'
                except Exception as e:
                    msg += ' -> could not close it (%s)' % e
            else:
                msg += ' -> press Fix to close it'
            lines.append(msg)
    if fix:
        infos = [_enrich(_curve_info(c)) for c in curves]

    # 2. direction and seams
    if fix:
        # one curve at a time, always against the previous curve as it is NOW: reverse it, read it
        # back, then work out how far its seam must move (reading back avoids guessing how Maya
        # reorders the CVs of a reversed curve)
        ref = infos[0]
        for i in range(1, len(curves)):
            info = infos[i]
            name = info['curve'].split('|')[-1]
            plan = _plan_fixes([ref, info])[1]
            notes = list(plan['notes'])
            if not notes:
                ref = info
                continue
            msg = None
            try:
                c = info['curve']
                if plan['reverse']:
                    c = _reverse_curve(c)
                    info = _enrich(_curve_info(c))
                    plan = _plan_fixes([ref, info])[1]
                if plan['shift']:
                    c = _shift_seam(c, plan['shift'])
                    info = _enrich(_curve_info(c))
                curves[i] = c
                msg = '%s %s -> fixed' % (name, '; '.join(notes))
                if not plan['fixable']:
                    msg = '%s %s' % (name, '; '.join(notes))
            except Exception as e:
                msg = '%s %s -> could not fix it (%s)' % (name, '; '.join(notes), e)
            lines.append(msg)
            ref = info
    else:
        plans = _plan_fixes(infos)
        for i, (info, plan) in enumerate(zip(infos, plans)):
            if i == 0 or not plan['notes']:
                continue
            msg = '%s %s' % (info['curve'].split('|')[-1], '; '.join(plan['notes']))
            if plan['fixable']:
                msg += ' -> press Fix'
            lines.append(msg)

    kinds = set('loop' if i['loop'] else 'open' for i in infos)
    if not lines:
        lines.append('%d curves checked: all %s, same direction, start points line up.'
                     % (len(curves), 'loops' if kinds == {'loop'} else 'open'))
    _report(lines)
    return curves, lines


def make_plane(name='ribbon', length=20.0, width=4.0, spans_u=8, spans_v=1, degree=3, normal='Z'):
    """A flat ribbon. Its length runs along U (as the Rig tab expects) with spans_u spans."""
    if length <= 0 or width <= 0:
        raise RuntimeError('Length and width must be above 0.')
    spans_u, spans_v = max(1, int(spans_u)), max(1, int(spans_v))

    def make(pu, pv):
        return cmds.nurbsPlane(name=name, axis=_rb().AXES[normal], width=length, lengthRatio=width / float(length),
                               patchesU=pu, patchesV=pv, degree=degree, constructionHistory=False)[0]

    plane = make(spans_u, spans_v)
    shape = cmds.listRelatives(plane, shapes=True, noIntermediate=True, type='nurbsSurface', fullPath=True)[0]

    def extent(direction):                               # distance between the two ends of a CV row
        nu = cmds.getAttr(shape + '.spansU') + cmds.getAttr(shape + '.degreeU')
        nv = cmds.getAttr(shape + '.spansV') + cmds.getAttr(shape + '.degreeV')
        a = cmds.pointPosition('%s.cv[0][0]' % plane, world=True)
        b = cmds.pointPosition('%s.cv[%d][0]' % (plane, nu - 1) if direction == 'U'
                               else '%s.cv[0][%d]' % (plane, nv - 1), world=True)
        return _length(_sub(a, b))

    # the documentation does not say whether the width runs along U or V, so measure it
    if abs(length - width) > 1e-6 * max(length, width) and abs(extent('U') - length) > abs(extent('U') - width):
        cmds.delete(plane)
        plane = make(spans_v, spans_u)                   # build it swapped, then swap U and V back
        cmds.reverseSurface(plane, direction=3, constructionHistory=False, replaceOriginal=True)
    cmds.select(plane)
    _say('plane "%s" made (%d spans along its length).' % (plane, spans_u))
    return plane


def edge_to_curve(degree=3, form='Best guess', rebuild_spans=0, start='Maya default', reverse=False,
                  delete_history=True, name='edgeCurve'):
    """Turn the selected polygon edges into a curve."""
    edges = [e for e in (cmds.ls(sl=True, flatten=True) or []) if '.e[' in e]
    if not edges:
        raise RuntimeError('Select the polygon edges first (an edge loop or a connected chain).')

    res = cmds.polyToCurve(form=EDGE_FORMS[form], degree=degree, name=name)
    curve = res[0]
    if delete_history:
        cmds.delete(curve, constructionHistory=True)

    lines = []
    got = cmds.getAttr(_curve_shape(curve) + '.form')
    if (form == 'Open' and got != 0) or (form == 'Closed' and got == 0):
        lines.append('the curve came out %s, not %s: check Modify > Convert > Polygon Edges to Curve' % (
            FORM_NAMES[got], form.lower()))

    if rebuild_spans and rebuild_spans > 0:
        cmds.rebuildCurve(curve, constructionHistory=False, replaceOriginal=True, rebuildType=0,
                          spans=int(rebuild_spans), degree=degree, keepRange=0,
                          endKnots=1 if got == 0 else 0, keepEndPoints=True)
    if reverse:
        curve = _reverse_curve(curve)

    if start != 'Maya default':
        axis = 'XYZ'.index(start[-1])
        want_low = start.startswith('Lowest')
        info = _enrich(_curve_info(curve))
        if info['form'] == 2:
            values = [e[axis] for e in info['edits']]
            best = values.index(min(values) if want_low else max(values))
            if best:
                curve = _shift_seam(curve, best)
        elif info['form'] == 0:
            if (info['start'][axis] > info['end'][axis]) == want_low:
                curve = _reverse_curve(curve)
        else:
            lines.append('the start point of a closed (not periodic) curve cannot be moved')

    cmds.select(curve)
    lines.insert(0, 'curve "%s" made (%s, degree %d).' % (curve, FORM_NAMES[cmds.getAttr(_curve_shape(curve) + '.form')], degree))
    _report(lines)
    return curve


def _runs_along(surface, curve_degree, curve_spans, loft_degree, count, section_spans):
    """'U' or 'V': the direction of a lofted surface that follows the curves. None if unsure."""
    shape = cmds.listRelatives(surface, shapes=True, noIntermediate=True, type='nurbsSurface', fullPath=True)[0]
    du, dv = cmds.getAttr(shape + '.degreeU'), cmds.getAttr(shape + '.degreeV')
    su, sv = cmds.getAttr(shape + '.spansU'), cmds.getAttr(shape + '.spansV')
    if curve_degree != loft_degree:
        if du == curve_degree and dv == loft_degree:
            return 'U'
        if dv == curve_degree and du == loft_degree:
            return 'V'
    across = (count - 1) * section_spans
    if curve_spans != across:
        if su == curve_spans and sv == across:
            return 'U'
        if sv == curve_spans and su == across:
            return 'V'
    return None


def swap_uv(surface=None):
    surface = surface or (cmds.ls(sl=True) or [None])[0]
    if not surface:
        raise RuntimeError('Select a surface first.')
    cmds.reverseSurface(surface, direction=3, constructionHistory=False, replaceOriginal=True)
    cmds.select(surface)


def flip_normals(surface=None):
    """Flip which side is the front without changing the order of the CVs along the length."""
    surface = surface or (cmds.ls(sl=True) or [None])[0]
    if not surface:
        raise RuntimeError('Select a surface first.')
    if not cmds.listRelatives(surface, shapes=True, noIntermediate=True, type='nurbsSurface', fullPath=True):
        raise RuntimeError('%s is not a NURBS surface.' % surface)
    cmds.reverseSurface(surface, direction=1, constructionHistory=False, replaceOriginal=True)
    cmds.select(surface)


def loft_curves(uniform=True, auto_reverse=True, close=False, degree=1, section_spans=1,
                partial_range=False, along_u=True, flip=False, auto_fix=True, name='ribbon'):
    """
    Loft the selected curves (in selection order) into a NURBS ribbon. With auto_fix the curves are
    checked first and fixed on copies, so the originals are never changed. With along_u the result is
    turned so the ribbon runs along U, as the Rig tab needs.
    """
    curves = _ordered_curves()
    if len(curves) < 2:
        raise RuntimeError('Select two or more curves (or a group of them), in the order you want them '
                           'lofted. Found %d.' % len(curves))

    cmds.undoInfo(openChunk=True)
    copies = []
    try:
        use = curves
        lines = []
        if auto_fix:
            copies = cmds.duplicate(curves, returnRootsOnly=True)
            for c in copies:
                if cmds.listRelatives(c, parent=True):
                    cmds.parent(c, world=True)
            use, lines = check_curves(copies, fix=True)
            copies = list(use)

        first = _curve_info(use[0])
        res = cmds.loft(use, name=name, uniform=uniform, autoReverse=auto_reverse, close=close, degree=degree,
                        sectionSpans=section_spans, range=partial_range, polygon=0,
                        constructionHistory=False, reverseSurfaceNormals=False)
        surface = res[0]

        direction = _runs_along(surface, first['degree'], first['spans'], degree, len(use), section_spans)
        if direction == 'V' and along_u:
            swap_uv(surface)
            lines.append('the loft ran along V, so U and V were swapped: the ribbon now runs along U.')
        elif direction is None and along_u:
            lines.append('could not tell which way the ribbon runs. If the Rig tab complains, press Swap U/V.')
        if flip:
            flip_normals(surface)
            lines.append('normals flipped.')
        lines.insert(0, 'lofted %d curves into "%s".' % (len(use), surface))
    finally:
        if copies:
            for c in copies:
                if cmds.objExists(c):
                    cmds.delete(c)
        cmds.undoInfo(closeChunk=True)

    cmds.select(surface)
    _report(lines)
    return surface
