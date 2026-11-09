# a tiny numpy stand-in for the bits of maya.api.OpenMaya the Maya check uses (row-vector matrices, like Maya)
import math
import numpy as np


class MMatrix(object):
    def __init__(self, m=None):
        self.a = np.eye(4) if m is None else (m.a.copy() if isinstance(m, MMatrix) else np.array(m, float).reshape(4, 4))

    def __mul__(self, o):
        return MMatrix(self.a @ o.a)

    def inverse(self):
        return MMatrix(np.linalg.inv(self.a))

    def getElement(self, r, c):
        return float(self.a[r, c])


class MVector(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __sub__(self, o):
        return MVector(self.x - o.x, self.y - o.y, self.z - o.z)

    def __add__(self, o):
        return MVector(self.x + o.x, self.y + o.y, self.z + o.z)

    def length(self):
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)


class MEulerRotation(object):
    def __init__(self, x, y, z):
        self.r = (x, y, z)

    def asMatrix(self):
        x, y, z = self.r
        cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
        rx = np.array([[1, 0, 0], [0, cx, sx], [0, -sx, cx]])
        ry = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
        rz = np.array([[cz, sz, 0], [-sz, cz, 0], [0, 0, 1]])
        m = np.eye(4)
        m[:3, :3] = rx @ ry @ rz
        return MMatrix(m)


class _Q(object):
    def __init__(self, x, y, z, w):
        self.x, self.y, self.z, self.w = x, y, z, w


class MTransformationMatrix(object):
    def __init__(self, m):
        self.m = m.a[:3, :3]

    def rotation(self, asQuaternion=False):
        r = self.m / np.linalg.norm(self.m, axis=1)[:, None]
        if np.linalg.det(r) < 0:
            r = -r
        t = np.trace(r)
        w = math.sqrt(max(0.0, 1 + t)) / 2
        x = math.copysign(math.sqrt(max(0.0, 1 + r[0, 0] - r[1, 1] - r[2, 2])) / 2, r[1, 2] - r[2, 1])
        y = math.copysign(math.sqrt(max(0.0, 1 - r[0, 0] + r[1, 1] - r[2, 2])) / 2, r[2, 0] - r[0, 2])
        z = math.copysign(math.sqrt(max(0.0, 1 - r[0, 0] - r[1, 1] + r[2, 2])) / 2, r[0, 1] - r[1, 0])
        return _Q(x, y, z, w)
