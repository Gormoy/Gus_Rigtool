"""
A joint (or locator, or empty group) at the centre of the selection (4.1.1) - from any mix of vertices, edges,
faces, CVs and objects. No cluster: the centre is worked out directly.

    from gus_rigtool.core import centre_point as CP
    CP.make(kind="joint", per="piece")          # one joint per separate piece of the selected components

per  : 'all' (one for everything), 'object' (one per mesh / object), 'piece' (one per connected piece of the
       selected components: select both eyes' vertices -> two joints)
centre: 'average' of the points, or 'box' (bounding-box centre)
orient: 'world', or 'components' (a face's normal / an edge's direction, like the Pivots tool)
chain : the new joints parented one under the next, in selection order, X aimed down the chain
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

KINDS = ("joint", "locator", "group")
PER = ("all", "object", "piece")
SUFFIX = {"joint": "_jnt", "locator": "_loc", "group": "_grp"}


# ---------------------------------------------------------------------------
# reading the selection
# ---------------------------------------------------------------------------

def _owner(comp):
    """The transform a component belongs to."""
    node = comp.split(".")[0]
    long_ = cmds.ls(node, long=True) or [node]
    n = long_[0]
    if cmds.objectType(n, isAType="shape"):
        n = (cmds.listRelatives(n, parent=True, fullPath=True) or [n])[0]
    return n


def _points(comps):
    """World points of components (vertices / CVs as they are; edges and faces through their vertices)."""
    verts = []
    for c in comps:
        if ".e[" in c or ".f[" in c:
            verts += cmds.ls(cmds.polyListComponentConversion(c, toVertex=True), flatten=True) or []
        else:
            verts += cmds.ls(c, flatten=True) or [c]
    seen, out = set(), []
    for v in verts:
        if v in seen:
            continue
        seen.add(v)
        p = cmds.xform(v, query=True, worldSpace=True, translation=True)
        out.append((v, p[:3]))
    return out


def centre(points, how="average"):
    if not points:
        raise RuntimeError("nothing to find the centre of.")
    if how == "box":
        return [(min(p[i] for p in points) + max(p[i] for p in points)) / 2.0 for i in range(3)]
    return [sum(p[i] for p in points) / float(len(points)) for i in range(3)]


def islands(items, neighbours):
    """Split items into connected pieces. neighbours(item) -> the items next to it. Keeps first-seen order."""
    wanted = list(dict.fromkeys(items))
    left = set(wanted)
    out = []
    for start in wanted:
        if start not in left:
            continue
        piece, todo = [], [start]
        left.discard(start)
        while todo:
            it = todo.pop()
            piece.append(it)
            for nb in neighbours(it):
                if nb in left:
                    left.discard(nb)
                    todo.append(nb)
        out.append(sorted(piece, key=wanted.index))
    return out


def _vertex_neighbours(vertex):
    """Vertices sharing an edge with this one (meshes); CVs: the next ones along the row."""
    if ".vtx[" in vertex:
        edges = cmds.polyListComponentConversion(vertex, toEdge=True) or []
        got = cmds.ls(cmds.polyListComponentConversion(edges, toVertex=True), flatten=True) or []
        return [g for g in got if g != vertex]
    return []


def groups_from_selection(sel=None, per="all"):
    """[(label, [component or object names], [points])] in selection order."""
    sel = sel if sel is not None else (cmds.ls(orderedSelection=True, long=True) or
                                       cmds.ls(selection=True, long=True) or [])
    comps = [s for s in sel if "." in s]
    objs = []
    for s in sel:
        if "." in s:
            continue
        if cmds.objectType(s, isAType="shape"):
            s = (cmds.listRelatives(s, parent=True, fullPath=True) or [s])[0]
        if s not in objs:
            objs.append(s)
    groups = []
    if comps:
        pts = _points(comps)
        if per == "all":
            groups.append((_owner(comps[0]), comps, [p for _v, p in pts]))
        elif per == "object":
            by = {}
            for v, p in pts:
                by.setdefault(_owner(v), []).append((v, p))
            for owner, items in by.items():
                groups.append((owner, [v for v, _p in items], [p for _v, p in items]))
        else:
            where = dict(pts)
            edges = [e for c in comps if ".e[" in c for e in (cmds.ls(c, flatten=True) or [c])]
            if edges:                           # edges: pieces joined only through the selected edges (loops)
                links = {}
                for e in edges:
                    vs = cmds.ls(cmds.polyListComponentConversion(e, toVertex=True), flatten=True) or []
                    for v in vs:
                        links.setdefault(v, set()).update(x for x in vs if x != v)
                neighbours = lambda v: links.get(v, ())       # noqa: E731
            else:
                neighbours = _vertex_neighbours
            for piece in islands([v for v, _p in pts], neighbours):
                groups.append((_owner(piece[0]), piece, [where[v] for v in piece]))
    if objs:
        pos = [(o, cmds.xform(o, query=True, worldSpace=True, rotatePivot=True)) for o in objs]
        if per == "all" and groups:                 # objects and components: one centre for everything
            label, items, pts = groups[0]
            groups[0] = (label, items + objs, pts + [p for _o, p in pos])
        elif per == "all":
            groups.append((objs[0], objs, [p for _o, p in pos]))
        else:
            groups += [(o, [o], [p]) for o, p in pos]
    return groups


# ---------------------------------------------------------------------------
# naming
# ---------------------------------------------------------------------------

def _side_prefix(name, x, tol):
    from gus_rigtool.core import joint_labels
    if joint_labels.split_side(name)[0] in ("L", "R"):
        return name
    if x > tol:
        return "L_" + name
    if x < -tol:
        return "R_" + name
    return name


def names_for(groups, kind, name="", tol=1e-3):
    """A name for each group: yours (numbered if several), else the owner's name; L_ / R_ from the position
    when the name has no side."""
    out = []
    many = len(groups) > 1
    for i, (label, _items, pts) in enumerate(groups):
        c = centre(pts)
        if name.strip():
            base = name.strip()
            for sfx in SUFFIX.values():
                if base.endswith(sfx):
                    base = base[:-len(sfx)]
            base = base + ("_%02d" % (i + 1) if many else "")
        else:
            base = naming.strip_type_suffix(naming.short_name(label).split(":")[-1])
            if many and any(naming.short_name(g[0]) == naming.short_name(label) for j, g in enumerate(groups)
                            if j != i):
                base += "_%02d" % (i + 1)
        out.append(_side_prefix(base, c[0], tol) + SUFFIX[kind])
    return out


# ---------------------------------------------------------------------------
# making
# ---------------------------------------------------------------------------

def _size(pts):
    if len(pts) < 2:
        return 0.0
    return math.sqrt(sum((max(p[i] for p in pts) - min(p[i] for p in pts)) ** 2 for i in range(3)))


def make(kind="joint", per="all", how="average", orient="world", chain=False, parent=None, name="",
         sel=None):
    """Make the nodes; returns their long names (in selection order)."""
    from gus_rigtool.core import pivots
    if kind not in KINDS:
        raise ValueError(kind)
    groups = groups_from_selection(sel, per)
    if not groups:
        raise RuntimeError("select vertices, edges, faces, CVs or objects first.")
    allpts = [p for g in groups for p in g[2]]
    tol = max(_size(allpts) * 0.001, 1e-4)
    names = names_for(groups, kind, name, tol)
    made = []
    with utils.undo_chunk("gusrigCentrePoint"):
        for (label, items, pts), nm in zip(groups, names):
            pos = centre(pts, how)
            rot = None
            if orient == "components":
                comps = [x for x in items if "." in x]
                if comps:
                    try:
                        rot = pivots.euler_xyz(pivots.component_frame(comps)[1])
                    except RuntimeError:
                        rot = None
            cmds.select(clear=True)
            if kind == "joint":
                node = cmds.joint(name=naming.unique(nm), position=pos)
                size = _size(pts)
                if size > 0:
                    cmds.setAttr(node + ".radius", max(0.05, size * 0.15))
            elif kind == "locator":
                node = cmds.spaceLocator(name=naming.unique(nm))[0]
                cmds.xform(node, worldSpace=True, translation=pos)
            else:
                node = cmds.createNode("transform", name=naming.unique(nm))
                cmds.xform(node, worldSpace=True, translation=pos)
            node = cmds.ls(node, long=True)[0]
            if rot is not None and not chain:
                cmds.xform(node, worldSpace=True, rotation=rot)
                if kind == "joint":
                    cmds.makeIdentity(node, apply=True, rotate=True)          # into Joint Orient
            made.append(utils.uuid(node))
        if chain and len(made) > 1:
            for i in range(1, len(made)):
                cmds.parent(utils.path(made[i]), utils.path(made[i - 1]))
            if kind == "joint":
                cmds.joint(utils.path(made[0]), edit=True, orientJoint="xyz", secondaryAxisOrient="yup",
                           children=True, zeroScaleOrient=True)
                last = utils.path(made[-1])
                for a in ("jointOrientX", "jointOrientY", "jointOrientZ"):
                    cmds.setAttr(last + "." + a, 0)
        if parent:
            for x in ([made[0]] if chain else made):
                cmds.parent(utils.path(x), parent)
        out = [utils.path(x) for x in made]
        cmds.select(out, replace=True)
    try:
        cmds.selectMode(object=True)
    except (RuntimeError, TypeError):
        pass
    return out
