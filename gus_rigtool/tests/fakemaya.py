"""A small fake of maya.cmds: a scene graph with transforms / joints, attributes, matrices, connections.
Enough to run the Gus_Rigtool builder end to end without Maya (constraints are recorded, not solved)."""
import sys, types, math, re
from unittest import mock

import os as _os
sys.path.insert(0, _os.environ.get("GUS_RIGTOOL_PARENT") or _os.path.abspath(_os.path.join(_os.getcwd(), "..", "..")))
maya = types.ModuleType("maya"); cmds = types.ModuleType("maya.cmds"); mel = mock.MagicMock()
api = types.ModuleType("maya.api"); om = mock.MagicMock()
maya.cmds = cmds; maya.mel = mel; maya.api = api; api.OpenMaya = om
sys.modules.update({"maya": maya, "maya.cmds": cmds, "maya.mel": mel, "maya.api": api,
                    "maya.api.OpenMaya": om, "maya.api.OpenMayaAnim": mock.MagicMock()})

from gus_rigtool.core import mirror_engine as me   # pure maths, uses cmds lazily

DAG_TYPES = {"transform", "joint", "nurbsCurve", "nurbsSurface", "mesh", "locator", "follicle", "ikHandle",
             "ikEffector", "parentConstraint", "orientConstraint", "pointConstraint", "scaleConstraint",
             "poleVectorConstraint", "aimConstraint"}
SHAPE_TYPES = {"nurbsCurve", "nurbsSurface", "mesh", "locator", "follicle"}
CONSTRAINTS = {"parentConstraint", "orientConstraint", "pointConstraint", "scaleConstraint", "poleVectorConstraint",
               "aimConstraint"}


class Node(object):
    def __init__(self, name, ntype, parent=None):
        self.name, self.type, self.parent, self.children = name, ntype, parent, []
        self.attrs = {"translate": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0],
                      "jointOrient": [0.0, 0.0, 0.0], "rotateOrder": 0, "visibility": True, "radius": 1.0,
                      "inheritsTransform": True, "intermediateObject": False}
        self.locks, self.user = set(), {}
        if parent:
            parent.children.append(self)


class Scene(object):
    def __init__(self):
        self.nodes = []
        self.conns = []          # (src plug, dst plug)
        self.sel = []

    def path(self, n):
        p, x = [], n
        while x:
            p.append(x.name)
            x = x.parent
        return "|" + "|".join(reversed(p)) if n.type in DAG_TYPES else n.name

    def find(self, name):
        if name is None:
            return []
        name = str(name)
        if name.startswith("UUID-"):                          # like Maya's UUIDs: survive renames / reparents
            return [n for n in self.nodes if "UUID-%d" % id(n) == name]
        if name.startswith("|"):
            return [n for n in self.nodes if self.path(n) == name]
        parts = name.split("|")
        out = []
        for n in self.nodes:
            if n.name != parts[-1]:
                continue
            if len(parts) > 1 and not self.path(n).endswith("|" + name):
                continue
            out.append(n)
        return out

    def get(self, name):
        f = self.find(name)
        if not f:
            raise ValueError("No object matches name: %s" % name)
        if len(f) > 1:
            raise ValueError("More than one object matches name: %s" % name)
        return f[0]

    def unique(self, name):
        name = name.replace("#", "1") if "#" in name else name
        if not any(n.name == name for n in self.nodes):
            return name
        base = re.sub(r"\d+$", "", name)
        i = 1
        while any(n.name == "%s%d" % (base, i) for n in self.nodes):
            i += 1
        return "%s%d" % (base, i)

    def create(self, ntype, name=None, parent=None):
        n = Node(self.unique(name or (ntype + "1")), ntype, parent)
        self.nodes.append(n)
        return n

    def remove(self, n):
        for c in list(n.children):
            self.remove(c)
        if n.parent:
            n.parent.children.remove(n)
        if n in self.nodes:
            self.nodes.remove(n)
            self.conns = [c for c in self.conns if c[0] is not n and c[2] is not n]


S = Scene()


# ---------------------------------------------------------------- matrices
def local(n):
    a = n.attrs
    jo = a["jointOrient"] if n.type == "joint" else None
    return me.compose(a["translate"], a["rotate"], a["scale"], a["rotateOrder"], jo)


def world(n):
    m = local(n) if n.type not in SHAPE_TYPES else list(me.IDENTITY)
    p = n.parent
    while p:
        if p.type not in SHAPE_TYPES:
            m = me.mul(m, local(p))
        p = p.parent
    return m


def set_world(n, m):
    pw = world(n.parent) if n.parent else list(me.IDENTITY)
    loc = me.mul(m, me.inverse(pw))
    if n.type == "joint":
        t, r, s = me.decompose(loc, n.attrs["rotateOrder"], n.attrs["jointOrient"])
    else:
        t, r, s = me.decompose(loc, n.attrs["rotateOrder"])
    n.attrs["translate"], n.attrs["rotate"], n.attrs["scale"] = list(t), list(r), list(s)


# ---------------------------------------------------------------- commands
def _n(x):
    return S.get(x)


def createNode(ntype, name=None, parent=None, **k):
    par = _n(parent) if parent else None
    if ntype in SHAPE_TYPES and par is None:
        t = S.create("transform", (name or ntype) .replace("Shape", "") if name else ntype.replace("follicle", "follicle") + "1")
        s = S.create(ntype, (name or ntype + "Shape1"), t)
        return s.name
    return S.create(ntype, name, par).name


def sets(*args, **k):
    """objectSet: members kept on the node (sets can hold sets)."""
    if k.get("query"):
        node = S.find(args[0])[0]
        return [S.path(m) for m in node.members if m in S.nodes]
    if k.get("add"):                                            # sets(x, add=theSet): x into the set
        target = S.find(k["add"])[0]
        for x in (args[0] if args and isinstance(args[0], (list, tuple)) else list(args)):
            target.members += S.find(x)[:1]
        return None
    node = S.create("objectSet", k.get("name") or "set1", None)
    node.members = []
    for x in (args[0] if args and isinstance(args[0], (list, tuple)) else list(args)):
        node.members += S.find(x)[:1]
    return node.name


def ls(*args, **k):
    long = k.get("long")
    if k.get("assemblies"):
        nodes = [n for n in S.nodes if n.parent is None and n.type in DAG_TYPES and n.type not in SHAPE_TYPES]
    elif k.get("selection") or k.get("sl") or k.get("orderedSelection"):
        nodes = [n for n in S.sel if n in S.nodes]
    elif args and not (isinstance(args[0], (list, tuple)) and not args[0]):    # Maya: ls([]) lists EVERY node
        names = args[0] if isinstance(args[0], (list, tuple)) else list(args)
        nodes = []
        for nm in names:
            nm = str(nm)
            if nm.startswith("*.") and k.get("objectsOnly"):          # nodes with this attribute
                attr = nm[2:]
                nodes += [n for n in S.nodes if attr in n.user]
                continue
            if "." in nm:
                if S.find(nm.split(".")[0]):
                    nodes.append(nm)
                continue
            nodes += S.find(nm)
    else:
        nodes = list(S.nodes)
    t = k.get("type")
    if t:
        types_ = t if isinstance(t, (list, tuple)) else [t]
        nodes = [n for n in nodes if not isinstance(n, str) and (n.type in types_ or
                 (("transform" in types_) and n.type in ("joint", "ikHandle")) or
                 ("constraint" in types_ and n.type in CONSTRAINTS) or
                 ("geometryFilter" in types_ and n.type == "skinCluster"))]
    if k.get("uuid"):
        return ["UUID-%d" % id(n) for n in nodes if not isinstance(n, str)]
    return [x if isinstance(x, str) else (S.path(x) if long else x.name) for x in nodes]


def objExists(name):
    name = str(name)
    if "." in name:
        node, attr = name.split(".", 1)
        f = S.find(node)
        return bool(f) and (attr.split("[")[0] in f[0].attrs or attr.split("[")[0] in f[0].user or
                            attr.rstrip("XYZ") in f[0].attrs or attr.startswith(("cv", "worldMatrix", "matrix")) or
                            attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"))
    return bool(S.find(name))


def nodeType(name):
    return _n(name).type


def objectType(name, isAType=None):
    t = _n(name).type
    if isAType == "shape":
        return t in SHAPE_TYPES
    if isAType == "transform":
        return t in ("transform", "joint", "ikHandle") or t in CONSTRAINTS
    if isAType == "constraint":
        return t in CONSTRAINTS
    if isAType == "geometryFilter":
        return t == "skinCluster"
    return t if isAType is None else t == isAType


def listRelatives(name, **k):
    if isinstance(name, (list, tuple)):                       # like Maya: several nodes at once
        out = []
        for x in name:
            for r in listRelatives(x, **k) or []:
                if r not in out:
                    out.append(r)
        return out or None
    n = _n(name)
    full = k.get("fullPath")
    out = []
    if k.get("parent"):
        out = [n.parent] if n.parent else []
    elif k.get("shapes"):
        out = [c for c in n.children if c.type in SHAPE_TYPES]
    elif k.get("allDescendents"):
        def walk(x):
            for c in x.children:
                out.append(c)
                walk(c)
        walk(n)
        out.reverse()
    else:
        out = list(n.children)
    t = k.get("type")
    if t:
        types_ = t if isinstance(t, (list, tuple)) else [t]
        out = [c for c in out if c.type in types_ or ("transform" in types_ and c.type in ("joint", "ikHandle"))
               or ("transform" in types_ and c.type in CONSTRAINTS)            # like Maya: constraints are transforms
               or ("constraint" in types_ and c.type in CONSTRAINTS)]
    if not out:
        return None
    return [S.path(c) if full else c.name for c in out]


def parent(*args, **k):
    args = list(args)
    flat = []
    for a in args:
        flat += a if isinstance(a, (list, tuple)) else [a]
    if k.get("world"):
        kids, par = flat, None
    else:
        kids, par = flat[:-1], _n(flat[-1])
    out = []
    for c in kids:
        n = _n(c)
        w = world(n)
        if n.parent:
            n.parent.children.remove(n)
        n.parent = par
        if par:
            par.children.append(n)
        if not k.get("relative") and n.type not in SHAPE_TYPES:
            set_world(n, w)
        out.append(n.name)
    return out


def rename(old, new):
    n = _n(old)
    n.name = S.unique(new)
    return n.name


def delete(*args, **k):
    for a in args:
        for x in (a if isinstance(a, (list, tuple)) else [a]):
            for n in S.find(x):
                S.remove(n)


def _split(plug):
    node, attr = plug.split(".", 1)
    return _n(node), attr


AXES = "XYZ"


def getAttr(plug, **k):
    n, attr = _split(plug)
    if k.get("settable"):
        return attr not in n.locks and not any(c[2] is n and c[3] == attr for c in S.conns)
    if k.get("lock"):
        return attr in n.locks
    if k.get("keyable") or k.get("channelBox"):
        return attr not in getattr(n, "hidden", set())
    if k.get("type"):
        if attr in getattr(n, "types", {}):
            return n.types[attr]
        v = n.user.get(attr, n.attrs.get(attr))
        return "string" if isinstance(v, str) else "double"
    if attr.startswith("worldMatrix"):
        return world(n)
    if attr == "matrix":
        return local(n)
    if attr.startswith("parentInverseMatrix"):
        return me.inverse(world(n.parent)) if n.parent else list(me.IDENTITY)
    if attr in ("minMaxRangeU", "minMaxRangeV"):
        return [(0.0, 1.0)]
    if attr in ("parameterU", "parameterV"):
        return 0.5
    for base in ("translate", "rotate", "scale", "jointOrient"):
        if attr == base:
            return [tuple(n.attrs[base])]
        if attr.startswith(base) and attr[len(base):] in AXES and len(attr) == len(base) + 1:
            return n.attrs[base][AXES.index(attr[-1])]
    short = {"tx": ("translate", 0), "ty": ("translate", 1), "tz": ("translate", 2), "rx": ("rotate", 0),
             "ry": ("rotate", 1), "rz": ("rotate", 2), "sx": ("scale", 0), "sy": ("scale", 1), "sz": ("scale", 2)}
    if attr in short:
        b, i = short[attr]
        return n.attrs[b][i]
    if attr == "v":
        return n.attrs["visibility"]
    if attr in n.user:
        return n.user[attr]
    return n.attrs.get(attr, 0)


def setAttr(plug, *values, **k):
    n, attr = _split(plug)
    if "lock" in k:
        (n.locks.add if k["lock"] else n.locks.discard)(attr)
    if "keyable" in k:
        n.hidden = getattr(n, "hidden", set())
        (n.hidden.discard if k["keyable"] else n.hidden.add)(attr)
    if not values:
        return
    for base in ("translate", "rotate", "scale", "jointOrient"):
        if attr == base:
            n.attrs[base] = [float(v) for v in values[:3]]
            return
        if attr.startswith(base) and attr[len(base):] in AXES and len(attr) == len(base) + 1:
            n.attrs[base][AXES.index(attr[-1])] = float(values[0])
            return
    short = {"tx": ("translate", 0), "ty": ("translate", 1), "tz": ("translate", 2), "rx": ("rotate", 0),
             "ry": ("rotate", 1), "rz": ("rotate", 2), "sx": ("scale", 0), "sy": ("scale", 1), "sz": ("scale", 2)}
    if attr in short:
        b, i = short[attr]
        n.attrs[b][i] = float(values[0])
        return
    if attr in n.user:
        n.user[attr] = values[0] if len(values) == 1 else list(values)
    else:
        n.attrs[attr] = values[0] if len(values) == 1 else list(values)


def addAttr(node, **k):
    n = _n(node)
    name = k.get("longName") or k.get("ln")
    if name in n.user:
        raise RuntimeError("attribute exists: " + name)
    n.user[name] = "" if k.get("dataType") == "string" else k.get("defaultValue", 0)
    if not hasattr(n, "types"):
        n.types, n.enums = {}, {}
    n.types[name] = k.get("attributeType") or k.get("dataType") or "double"
    if "defaultValue" in k:                         # 5.6.28: listDefault answers it
        if not hasattr(n, "defaults"):
            n.defaults = {}
        n.defaults[name] = k["defaultValue"]
    if k.get("enumName"):
        n.enums[name] = k["enumName"]
    if not hasattr(n, "limits"):                           # 5.6.24: the picker reads ranges
        n.limits = {}
    n.limits[name] = (k.get("minValue"), k.get("maxValue"))


def attributeQuery(attr, node=None, exists=False, **k):
    n = _n(node)
    if exists:
        return attr in n.user or attr in n.attrs or attr in ("translate", "rotate", "jointOrient", "side",
                                                             "displayLocalAxis")
    if k.get("listDefault"):
        return [float(getattr(n, "defaults", {}).get(attr, 0.0))]
    if k.get("listEnum"):
        return [getattr(n, "enums", {}).get(attr, "")]
    lim = getattr(n, "limits", {}).get(attr, (None, None))
    if k.get("attributeType"):
        if attr not in getattr(n, "types", {}):
            raise RuntimeError("no attribute %s" % attr)
        return n.types[attr]
    if k.get("minExists"):
        return lim[0] is not None
    if k.get("maxExists"):
        return lim[1] is not None
    if k.get("minimum"):
        return [lim[0]]
    if k.get("maximum"):
        return [lim[1]]
    return False


def listAttr(node, **k):
    n = _n(node)
    return list(n.user) if k.get("userDefined") else list(n.attrs)


def connectAttr(a, b, force=False, **k):
    sa, sb = _split(a), _split(b)
    if not force and any(d is sb[0] and da == sb[1] for _s, _sa, d, da in S.conns):
        raise RuntimeError("%s is already connected" % b)
    S.conns = [c for c in S.conns if not (c[2] is sb[0] and c[3] == sb[1])]
    S.conns.append((sa[0], sa[1], sb[0], sb[1]))


def disconnectAttr(a, b):
    sa, sb = _split(a), _split(b)
    S.conns = [c for c in S.conns if not (c[0] is sa[0] and c[1] == sa[1] and c[2] is sb[0] and c[3] == sb[1])]


def listConnections(plug, source=True, destination=True, plugs=False, type=None, **k):
    out = []
    if "." in plug:
        node, attr = _split(plug)
    else:
        node, attr = _n(plug), None
    for s_, sa, d, da in S.conns:
        if source and d is node and (attr is None or da == attr or da.startswith(attr)):
            out.append((s_, sa))
        if destination and s_ is node and (attr is None or sa == attr or sa.startswith(attr)):
            out.append((d, da))
    if k.get("skipConversionNodes"):                          # through Maya's unit conversions, like Maya
        through = []
        for o in out:
            if o[0].type == "unitConversion":
                for s2, sa2, d2, da2 in S.conns:
                    if source and d2 is o[0] and da2 == "input":
                        through.append((s2, sa2))
                    if destination and s2 is o[0] and sa2 == "output":
                        through.append((d2, da2))
            else:
                through.append(o)
        out = through
    if type:
        abstract = {"constraint": CONSTRAINTS, "animCurve": ("animCurveUL", "animCurveUA", "animCurveUU",
                                                              "animCurveUT", "animCurveTL", "animCurveTA")}
        kinds = abstract.get(type, (type,))
        out = [o for o in out if o[0].type in kinds]
    if k.get("connections"):
        pairs = []
        for s_, sa, d, da in S.conns:
            if source and d is node and (attr is None or da == attr or da.startswith(attr)) and \
                    any(o[0] is s_ for o in out):
                pairs += [d.name + "." + da, s_.name + "." + sa]
            if destination and s_ is node and (attr is None or sa == attr or sa.startswith(attr)) and \
                    any(o[0] is d for o in out):
                pairs += [s_.name + "." + sa, d.name + "." + da]
        return pairs or None
    return [(o[0].name + "." + o[1]) if plugs else o[0].name for o in out] or None


def xform(name, query=False, worldSpace=False, matrix=None, translation=None, rotation=None,
          rotatePivot=None, scalePivot=None, **k):
    n = _n(name)
    if query:
        if matrix:
            return local(n) if k.get("objectSpace") else world(n)
        if (rotatePivot or scalePivot) and getattr(n, "pivot", None) is not None:
            return list(n.pivot)                                # a pivot moved off the node (world)
        if translation or rotatePivot or scalePivot:
            return world(n)[12:15]
        return None
    if (rotatePivot is not None or scalePivot is not None) and matrix is None and translation is None:
        n.pivot = list(rotatePivot if rotatePivot is not None else scalePivot)   # pivots only: the node stays
        return None
    if matrix is not None:
        set_world(n, list(matrix))
    if rotation is not None:
        w = world(n)
        order = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"].index(k["rotateOrder"]) if k.get("rotateOrder") else 0
        rot = me.euler_matrix(rotation, order)
        rot[12:15] = w[12:15]
        set_world(n, rot)
    if translation is not None:
        w = world(n)
        w[12:15] = list(translation)
        set_world(n, w)


_BAD_FLAGS = {"pointConstraint": ("skipTranslate", "skipRotate", "st", "sr"),
              "orientConstraint": ("skipTranslate", "skipRotate", "st", "sr"),
              "scaleConstraint": ("skipTranslate", "skipRotate", "st", "sr"),
              "parentConstraint": ("skip", "sk")}


def _constraint(ctype, *args, **k):
    for f in _BAD_FLAGS.get(ctype, ()):
        if f in k:
            raise TypeError("Invalid flag '%s'" % f)        # like Maya: each constraint has its own skip flags
    if k.get("query"):
        c = _n(args[0])
        if k.get("targetList"):
            return list(c.attrs.get("targets", []))
        return [t + "W%d" % i for i, t in enumerate(c.attrs.get("targets", []))] if k.get("weightAliasList") else None
    flat = []
    for a in args:
        flat += a if isinstance(a, (list, tuple)) else [a]
    targets, driven = flat[:-1], _n(flat[-1])
    for t in targets:
        _n(t)
    existing = [x for x in driven.children if x.type == ctype]
    if k.get("edit") and k.get("remove") and existing:          # remove targets
        c = existing[0]
        for t in targets:
            tn = _n(t)
            S.conns[:] = [x for x in S.conns if not (x[0] is tn and x[2] is c)]
            c.attrs["targets"] = [n for n in c.attrs["targets"] if n != tn.name]
        return [c.name]
    if existing:                                                # Maya adds targets to the existing one
        c = existing[0]
    else:
        c = S.create(ctype, driven.name + "_" + ctype + "1", driven)
        c.attrs["targets"] = []
        for out_attr, in_attr in (("constraintTranslate", "translate"), ("constraintRotate", "rotate")):
            S.conns.append((c, out_attr, driven, in_attr))
    for t in targets:
        tn = _n(t)
        i = len(c.attrs["targets"])
        c.attrs["targets"].append(tn.name)
        c.user[tn.name + "W%d" % i] = 1.0
        S.conns.append((tn, "parentMatrix[0]", c, "target[%d].targetParentMatrix" % i))
    return [c.name]


for _c in CONSTRAINTS:
    setattr(cmds, _c, (lambda ct: lambda *a, **k: _constraint(ct, *a, **k))(_c))


def ikHandle(startJoint=None, endEffector=None, solver="ikRPsolver", name="ikHandle1", createCurve=False, **k):
    _n(startJoint), _n(endEffector)
    h = S.create("ikHandle", name)
    e = S.create("ikEffector", "effector1", _n(endEffector).parent)
    if createCurve:
        c = S.create("transform", "curve1")
        S.create("nurbsCurve", "curveShape1", c)
        return [h.name, e.name, c.name]
    return [h.name, e.name]


def skinCluster(*args, **k):
    if k.get("query"):
        return []
    return [S.create("skinCluster", k.get("name", "skinCluster1")).name]


def curve(degree=1, point=None, editPoint=None, name=None, **k):
    t = S.create("transform", name or "curve1")
    S.create("nurbsCurve", t.name + "Shape", t)
    return t.name


def loft(*args, **k):
    t = S.create("transform", k.get("name", "loftedSurface1"))
    S.create("nurbsSurface", t.name + "Shape", t)
    return [t.name]


def spaceLocator(name=None, **k):
    t = S.create("transform", name or "locator1")
    S.create("locator", t.name + "Shape", t)
    return [t.name]


def select(*args, **k):
    if k.get("clear") or not args:
        S.sel = []
        return
    flat = []
    for a in args:
        flat += a if isinstance(a, (list, tuple)) else [a]
    S.sel = [_n(x) for x in flat]


for _name, _fn in list(globals().items()):
    if callable(_fn) and not _name.startswith("_") and _name not in ("Node", "Scene", "local", "world",
                                                                      "set_world", "mock", "types"):
        setattr(cmds, _name, _fn)
for _name in ("undoInfo", "move", "warning", "reverseSurface", "rebuildSurface", "optionVar", "evalDeferred",
              "scriptJob", "confirmDialog", "inViewMessage", "refresh", "about"):
    setattr(cmds, _name, mock.MagicMock(return_value=None))
cmds.optionVar = mock.MagicMock(return_value=False)
if not hasattr(cmds, "keyframe"):                      # 5.6.24: the picker's keyed dots (no keys here)
    cmds.keyframe = lambda *a, **k: 0
if not hasattr(cmds, "currentTime"):
    cmds.currentTime = lambda *a, **k: 1.0
cmds.confirmDialog = mock.MagicMock(return_value="Delete rig")

# curves: a control is a transform with a curve shape (no CV maths)
from gus_rigtool.core import curves as _curves


def _ccc(name, data, style=None):
    t = S.create("transform", name)
    S.create("nurbsCurve", t.name + "Shape", t)
    return S.path(t)


_curves.create_curve_control = _ccc
_curves.set_shape = lambda *a, **k: None
from gus_rigtool.core import utils as _utils
_SETTINGS = {}
_utils.load_setting = lambda key, default: _SETTINGS.get(key, default)
_utils.save_setting = lambda key, value: _SETTINGS.__setitem__(key, value)
_utils.info = lambda t, m, level="ok": print("  [info] %s" % m)
_utils.warn = lambda t, m: print("  [warn] %s" % m)
cmds.file = lambda **k: ""
cmds.manipMoveContext = mock.MagicMock(return_value=False)
cmds.manipRotateContext = mock.MagicMock(return_value=False)


def listHistory(*a, **k):
    return []


def reorder(*a, **k):
    return None


def deleteAttr(plug, **k):
    n, attr = _split(plug)
    n.user.pop(attr, None)


cmds.listHistory = listHistory; cmds.reorder = reorder; cmds.deleteAttr = deleteAttr


# references and node locks (4.5.2): fake scenes have no references; locks are remembered per node
_LOCKED = set()
def referenceQuery(node, **k):
    if k.get("isNodeReferenced"):
        return bool(getattr(_n(node), "referenced", False))
    return None
cmds.referenceQuery = referenceQuery
def lockNode(nodes, **k):
    nodes = nodes if isinstance(nodes, (list, tuple)) else [nodes]
    if k.get("query"):
        return [S.path(_n(x)) in _LOCKED for x in nodes]
    for x in nodes:
        (_LOCKED.add if k.get("lock", True) else _LOCKED.discard)(S.path(_n(x)))
cmds.lockNode = lockNode


def duplicate(name, **k):
    """Copy a node and everything under it (5.0.3): same types, attributes and local values."""
    import copy as _copy
    src = _n(name)

    def dup(n, parent):
        c = S.create(n.type, n.name, parent)
        c.attrs = _copy.deepcopy(n.attrs)
        c.user = _copy.deepcopy(n.user)
        for kid in list(n.children):
            dup(kid, c)
        return c
    top = dup(src, src.parent)
    set_world(top, world(src))
    return [top.name]
cmds.duplicate = duplicate


def renameAttr(plug, new):
    """5.6.20: the attribute keeps its value, type and connections under the new name."""
    n, attr = _split(plug)
    if attr in n.user:
        n.user[new] = n.user.pop(attr)
        if hasattr(n, "types") and attr in n.types:
            n.types[new] = n.types.pop(attr)
    S.conns = [(a, (new if a is n and aa == attr else aa), b, (new if b is n and ba == attr else ba))
               for a, aa, b, ba in S.conns]
    return new


cmds.renameAttr = renameAttr


_UTILITY = ("condition", "plusMinusAverage", "reverse", "multiplyDivide", "clamp", "setRange", "blendColors",
            "multDoubleLinear", "addDoubleLinear")
def getClassification(t, **k):
    """5.6.32: Maya's node classification - the utility nodes only."""
    return ["utility/general"] if t in _UTILITY else [""]
cmds.getClassification = getClassification
