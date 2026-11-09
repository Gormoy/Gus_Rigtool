"""
Vectors and joint orientation, in plain Python (matrices are 16-number lists in Maya's layout,
rows = X, Y, Z axes, then the position).
"""

import math

from gus_rigtool.core import mirror_engine as me

AXIS_VECTORS = {"X": (1, 0, 0), "-X": (-1, 0, 0), "Y": (0, 1, 0), "-Y": (0, -1, 0),
                "Z": (0, 0, 1), "-Z": (0, 0, -1)}


def sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def scale(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-9 else [0.0, 0.0, 0.0]


def lerp(a, b, t):
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]


def distance(a, b):
    return length(sub(a, b))


def plane_normal(points):
    """Normal of the plane through a bent chain (the biggest bend wins), or None if straight."""
    best, normal = 0.0, None
    for i in range(1, len(points) - 1):
        n = cross(sub(points[i], points[i - 1]), sub(points[i + 1], points[i]))
        if length(n) > best:
            best, normal = length(n), n
    if normal is None or best < 1e-6 * max(1e-6, distance(points[0], points[-1])) ** 2:
        return None
    return norm(normal)


def axes_matrix(aim_axis, aim_vec, up_axis, up_vec, pos):
    """Rotation whose aim_axis row points along aim_vec and up_axis row towards up_vec (det +1)."""
    a_name, u_name = aim_axis.lstrip("-"), up_axis.lstrip("-")
    if a_name == u_name:
        raise ValueError("the aim axis and the up axis must be different")
    a_sign = -1.0 if aim_axis.startswith("-") else 1.0
    u_sign = -1.0 if up_axis.startswith("-") else 1.0
    ai, ui = "XYZ".index(a_name), "XYZ".index(u_name)
    aim = norm(aim_vec)
    up = norm(sub(up_vec, scale(aim, dot(up_vec, aim))))           # up, made square to the aim
    if length(up) < 1e-6:
        # up is along the aim: pick any square direction
        up = norm(cross(aim, [0, 0, 1] if abs(aim[2]) < 0.9 else [1, 0, 0]))
    rows = [None, None, None]
    rows[ai] = scale(aim, a_sign)
    rows[ui] = scale(up, u_sign)
    k = 3 - ai - ui
    rows[k] = cross(rows[(k + 1) % 3], rows[(k + 2) % 3])          # right-handed
    m = list(me.IDENTITY)
    for r in range(3):
        m[r * 4:r * 4 + 3] = rows[r]
    m[12:15] = list(pos)
    return m


def steady_up(points, world_up):
    """world_up, unless the chain runs (nearly) along it - e.g. a neck going straight up with 'up = world Y':
    the up direction would be undefined and the joints twist. Then the world axis most square to the chain
    is used instead, the same for every joint of the chain (no flips)."""
    if len(points) < 2:
        return list(world_up)
    along = sub(points[-1], points[0])
    if length(along) < 1e-9:
        return list(world_up)
    along = norm(along)
    up = norm(world_up)
    if abs(dot(along, up)) < 0.85:
        return list(world_up)
    for a in ([0, 0, 1], [0, 1, 0], [1, 0, 0]):              # forward first, then up, then sideways
        if abs(dot(a, up)) < 0.5 and abs(dot(a, along)) < 0.5:
            return a
    return min(([0, 0, 1], [0, 1, 0], [1, 0, 0]), key=lambda a: abs(dot(a, along)))


def chain_matrices(points, aim="X", up="Y", up_mode="plane", world_up=(0, 1, 0), up_vectors=None):
    """
    World matrices of joints at points: each aims at the next one; the last copies its parent.
    up_mode 'plane': up = the chain's bend plane normal (falls back to world_up when straight);
            'world': up = world_up.
    up_vectors: an up direction per joint (overrides).
    """
    n = len(points)
    if n == 0:
        return []
    normal = plane_normal(points) if up_mode == "plane" else None
    world_up = steady_up(points, world_up)
    out = []
    for i in range(n):
        if i < n - 1:
            aim_vec = sub(points[i + 1], points[i])
        else:
            aim_vec = sub(points[i], points[i - 1]) if n > 1 else [1, 0, 0]
        if up_vectors:
            up_vec = up_vectors[min(i, len(up_vectors) - 1)]
        elif normal is not None:
            up_vec = normal
        else:
            up_vec = list(world_up)
        if length(aim_vec) < 1e-9:
            m = list(out[-1]) if out else list(me.IDENTITY)
            m[12:15] = list(points[i])
        else:
            m = axes_matrix(aim, aim_vec, up, up_vec, points[i])
        if i == n - 1 and n > 1:
            m = list(out[-1])                                        # last joint: parent's axes
            m[12:15] = list(points[i])
        out.append(m)
    return out


def mirrored_chain_matrices(points, behavior=True, **kwargs):
    """Right side: reflect the points to the left, orient them like a left chain, then mirror back
    (behavior: same rotate values = mirrored motion), so both sides follow the same rules."""
    if not behavior:
        return chain_matrices(points, **kwargs)
    left = [[-p[0], p[1], p[2]] for p in points]
    kw = dict(kwargs)
    if kw.get("world_up"):
        w = list(kw["world_up"])
        kw["world_up"] = [-w[0], w[1], w[2]]
    if kw.get("up_vectors"):
        kw["up_vectors"] = [[-v[0], v[1], v[2]] for v in kw["up_vectors"]]
    return [me.mirror_list(m, "behavior", 0) for m in chain_matrices(left, **kw)]


def translate_matrix(pos):
    m = list(me.IDENTITY)
    m[12:15] = list(pos)
    return m


def position(m):
    return list(m[12:15])


def axis_of(m, axis):
    """World direction of a matrix axis ('X', '-Y'...)."""
    sign = -1.0 if axis.startswith("-") else 1.0
    i = "XYZ".index(axis.lstrip("-"))
    return scale(norm(m[i * 4:i * 4 + 3]), sign)


def pole_position(a, b, c, distance_factor=1.0):
    """Pole vector spot for a chain a-b-c: out from the bend at b, in the chain's plane."""
    ac = sub(c, a)
    t = dot(sub(b, a), ac) / max(dot(ac, ac), 1e-9)
    on_line = add(a, scale(ac, t))
    out = sub(b, on_line)
    if length(out) < 1e-6 * max(length(ac), 1e-6):
        out = cross(ac, [0, 1, 0]) if abs(norm(ac)[1]) < 0.9 else cross(ac, [1, 0, 0])
    dist = (distance(a, b) + distance(b, c)) * 0.5 * distance_factor
    return add(b, scale(norm(out), dist))


def rotation_between(a, b):
    """Row-vector rotation matrix (16 values) turning direction a onto direction b."""
    import math
    a, b = norm(a), norm(b)
    axis = cross(a, b)
    sn = length(axis)
    c = max(-1.0, min(1.0, dot(a, b)))
    m = list(me.IDENTITY)
    if sn < 1e-9:
        if c > 0:
            return m
        perp = norm(cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]))      # 180 degrees
        x, y, z = perp
        rot = [[2 * x * x - 1, 2 * x * y, 2 * x * z], [2 * x * y, 2 * y * y - 1, 2 * y * z],
               [2 * x * z, 2 * y * z, 2 * z * z - 1]]
    else:
        x, y, z = [v / sn for v in axis]
        ang = math.atan2(sn, c)
        cs, si, t = math.cos(ang), math.sin(ang), 1 - math.cos(ang)
        col = [[t * x * x + cs, t * x * y - si * z, t * x * z + si * y],
               [t * x * y + si * z, t * y * y + cs, t * y * z - si * x],
               [t * x * z - si * y, t * y * z + si * x, t * z * z + cs]]
        rot = [[col[k][r] for k in range(3)] for r in range(3)]
    for r in range(3):
        m[r * 4:r * 4 + 3] = rot[r]
    return m


def det3(m):
    """Determinant of the 3x3 part of a 4x4 matrix (negative: a -1 scale / reflection)."""
    a = [m[0:3], m[4:7], m[8:11]]
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
            a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
