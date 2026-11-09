"""
Pure maths for joint chains (no Maya): spacing and orientation frames.

Vectors are [x, y, z] lists. A frame is three axis vectors [X, Y, Z] (rows of a Maya
rotation matrix: row 0 = the joint's X axis in world space, and so on).
"""

import math

AXES = {"+X": (0, 1.0), "-X": (0, -1.0), "+Y": (1, 1.0), "-Y": (1, -1.0), "+Z": (2, 1.0), "-Z": (2, -1.0)}
WORLD = {"X": [1.0, 0.0, 0.0], "Y": [0.0, 1.0, 0.0], "Z": [0.0, 0.0, 1.0]}


# ---------------------------------------------------------------------------
# vectors
# ---------------------------------------------------------------------------

def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    l = length(a)
    return [a[0] / l, a[1] / l, a[2] / l] if l > 1e-12 else [0.0, 0.0, 0.0]


def rotate_towards(v, a, b):
    """Rotate v by the smallest rotation that turns unit vector a into unit vector b."""
    axis = cross(a, b)
    s = length(axis)
    c = max(-1.0, min(1.0, dot(a, b)))
    if s < 1e-9:
        if c > 0:
            return list(v)
        # opposite directions: turn 180 degrees around any axis perpendicular to a
        p = cross(a, [1.0, 0.0, 0.0])
        if length(p) < 1e-6:
            p = cross(a, [0.0, 1.0, 0.0])
        axis, s, c = norm(p), 0.0, -1.0
    else:
        axis = mul(axis, 1.0 / s)
    # Rodrigues
    return add(add(mul(v, c), mul(cross(axis, v), s)), mul(axis, dot(axis, v) * (1.0 - c)))


# ---------------------------------------------------------------------------
# spacing
# ---------------------------------------------------------------------------

def lengths_for(total, mode, count, spacing, trim_start, trim_end, closed):
    """
    Distances along the curve for each joint.
    mode 'count'  : count joints, evenly between the trimmed ends
    mode 'spacing': one joint every `spacing` units from the trimmed start (+ the end)
    trim_* are fractions 0..1 of the length. On a closed curve the last joint is not
    put on top of the first.
    """
    start = total * trim_start
    end = total * (1.0 - trim_end)
    span = max(0.0, end - start)
    if mode == "spacing":
        spacing = max(spacing, 1e-6)
        n = int(math.floor(span / spacing + 1e-9)) + 1
        out = [start + i * spacing for i in range(n)]
        if not closed and span - out[-1] + start > spacing * 0.25:
            out.append(end)                        # finish on the end
        return out
    count = max(1, int(count))
    if count == 1:
        return [start + span / 2.0]
    if closed and trim_start == 0 and trim_end == 0:
        return [start + span * i / float(count) for i in range(count)]
    return [start + span * i / float(count - 1) for i in range(count)]


# ---------------------------------------------------------------------------
# orientation
# ---------------------------------------------------------------------------

def aims(points, closed=False, last="parent"):
    """Aim direction of each joint (towards the next one)."""
    out = []
    n = len(points)
    for i in range(n):
        if i < n - 1:
            out.append(norm(sub(points[i + 1], points[i])))
        elif closed and n > 1:
            out.append(norm(sub(points[0], points[i])))
        elif n > 1:
            out.append(list(out[-1]) if last == "parent" else None)
        else:
            out.append([1.0, 0.0, 0.0])
    return out


def _perpendicular(ref, aim, fallback):
    u = sub(ref, mul(aim, dot(ref, aim)))
    if length(u) < 1e-6:
        u = sub(fallback, mul(aim, dot(fallback, aim)))
    return norm(u)


def up_vectors(points, aim_list, mode, ref, object_point=None, normals=None):
    """
    Up direction of each joint (already perpendicular to its aim).
    mode 'noflip' : start from ref, then carried smoothly along the chain (no flips)
         'world'  : ref at every joint
         'object' : towards object_point
         'normal' : the curve normals given in `normals` (falls back to no flip)
    """
    fallback = [0.0, 0.0, 1.0] if abs(dot(norm(ref), [0.0, 1.0, 0.0])) > 0.9 else [0.0, 1.0, 0.0]
    ups = []
    for i, (p, a) in enumerate(zip(points, aim_list)):
        if a is None:
            ups.append(None)
            continue
        if mode == "world":
            ups.append(_perpendicular(ref, a, fallback))
        elif mode == "object" and object_point is not None:
            ups.append(_perpendicular(sub(object_point, p), a, fallback))
        elif mode == "normal" and normals and length(normals[i]) > 1e-6:
            ups.append(_perpendicular(normals[i], a, fallback))
        else:                                      # no flip (parallel transport)
            if not ups or ups[-1] is None:
                ups.append(_perpendicular(ref, a, fallback))
            else:
                prev_aim = aim_list[i - 1]
                carried = rotate_towards(ups[-1], prev_aim, a)
                ups.append(_perpendicular(carried, a, fallback))
    return ups


def frame(aim, up, aim_axis="+X", up_axis="+Y"):
    """Three world axis vectors [X, Y, Z] for a joint, right-handed."""
    ai, asign = AXES[aim_axis]
    ui, usign = AXES[up_axis]
    if ai == ui:
        raise ValueError("The aim and up axes must be different.")
    axes = [None, None, None]
    axes[ai] = mul(norm(aim), asign)
    axes[ui] = mul(norm(sub(up, mul(norm(aim), dot(up, norm(aim))))), usign)
    k = 3 - ai - ui
    if (ai, ui) in ((0, 1), (1, 2), (2, 0)):
        axes[k] = cross(axes[ai], axes[ui])
    else:
        axes[k] = cross(axes[ui], axes[ai])
    return axes


def frames(points, closed=False, aim_axis="+X", up_axis="+Y", up_mode="noflip", ref=None,
           object_point=None, normals=None, last="parent"):
    """Frame of every joint. The last joint copies its parent ('parent') or is world ('world')."""
    ref = ref or [0.0, 1.0, 0.0]
    a = aims(points, closed, last)
    u = up_vectors(points, a, up_mode, ref, object_point, normals)
    out = []
    for i in range(len(points)):
        if a[i] is None:                           # last joint, world orientation
            out.append([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        else:
            out.append(frame(a[i], u[i], aim_axis, up_axis))
    return out


def matrix(frame_axes, point):
    """16 values (Maya row order) from a frame and a position."""
    x, y, z = frame_axes
    return [x[0], x[1], x[2], 0.0, y[0], y[1], y[2], 0.0, z[0], z[1], z[2], 0.0,
            point[0], point[1], point[2], 1.0]
