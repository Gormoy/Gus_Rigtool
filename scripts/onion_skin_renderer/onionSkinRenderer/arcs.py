"""
(noPyMEL copy) Arcs: a line through where a point is on each frame, some frames back and forward, like tracking
an arc on the drawing in 2D. The point is a vertex of the mesh (nose tip, ear tip: what you see, with the head,
the squash and the skin all in it) or an object (a control, a joint: its pivot).

The positions are recorded while the time visits the frames (the controller does that when you stop on a frame,
never during playback) and kept until the animation changes. The onion skin's overlay pass draws them on top of
everything, in the onion viewport only - nothing is added to the scene.
"""

import maya.cmds as cmds

MAX_POINTS = 12


class Arcs(object):
    def __init__(self):
        self.points = []          # [(node long name, vertex id or None for an object's pivot)]
        self.cache = {}           # frame -> [(x, y, z) or None, one per point]
        self.stale = False        # the animation changed: everything is recorded again on the next stop
        self.keys = set()         # key times of the points' characters (bigger dots)
        self.before = 24
        self.after = 24
        self.dotEvery = 1         # a dot every N frames (the line always goes through every frame)
        self.show = True
        self.hidden = set()       # points whose line isn't drawn (still recorded - turning one back on is instant)
        self.onDirty = None       # the controller's "record again soon" (set by the window)

    # -- the points
    def setPoints(self, points):
        self.points = list(points)[:MAX_POINTS]
        self.cache = {}
        self.stale = False
        self.hidden = set(p for p in self.hidden if p in self.points)

    def removePoint(self, point):
        """Forget one point; the others keep what they recorded."""
        if point not in self.points:
            return
        i = self.points.index(point)
        self.points.pop(i)
        self.hidden.discard(point)
        for f, pos in list(self.cache.items()):
            self.cache[f] = pos[:i] + pos[i + 1:]

    def setVisible(self, point, visible):
        if visible:
            self.hidden.discard(point)
        elif point in self.points:
            self.hidden.add(point)

    def clear(self):
        self.setPoints([])

    def label(self, point):
        node, vid = point
        short = node.split("|")[-1]
        return short if vid is None else "%s  vtx %d" % (short, vid)

    # -- which frames
    def window(self, now):
        """The frames the line covers around now (whole frames, inside the scene's animation range)."""
        now = int(round(now))
        frames = range(now - int(self.before), now + int(self.after) + 1)
        lo, hi = _scene_range()
        return [float(f) for f in frames if (lo is None or f >= lo) and (hi is None or f <= hi)]

    def toRecord(self, now):
        if not self.points or not self.show:
            return []
        if self.stale:
            return self.window(now)
        return [f for f in self.window(now) if f not in self.cache]

    def animationChanged(self, *_):
        """A key or a curve changed: the line is recorded again (the old one stays until then - no flicker)."""
        if self.points and self.cache:
            self.stale = True
            if self.onDirty:
                try:
                    self.onDirty()
                except Exception:
                    pass

    def record(self, frame):
        """Store where each point is now (the time is at this frame)."""
        if self.points:
            self.cache[float(frame)] = [_position(p) for p in self.points]

    def finish(self, recorded):
        """After a full new recording, the frames that weren't recorded again are old: drop them."""
        if self.stale:
            keep = set(float(f) for f in recorded)
            self.cache = dict((f, v) for f, v in self.cache.items() if f in keep)
            self.stale = False

    # -- what to draw
    def lines(self, now):
        """For each point: [(frame, (x, y, z))] in frame order, the frames of the window that are known."""
        out = []
        win = self.window(now)
        for i in range(len(self.points)):
            line = []
            if self.points[i] in self.hidden:
                out.append(line)
                continue
            for f in win:
                pos = self.cache.get(f)
                if pos and i < len(pos) and pos[i] is not None:
                    line.append((f, pos[i]))
            out.append(line)
        return out

    def isDot(self, frame, now):
        if frame in self.keys:
            return True
        step = max(1, int(self.dotEvery))
        return int(round(frame - now)) % step == 0


def _scene_range():
    try:
        return (cmds.playbackOptions(query=True, animationStartTime=True),
                cmds.playbackOptions(query=True, animationEndTime=True))
    except Exception:
        return (None, None)


def _position(point):
    node, vid = point
    try:
        if vid is None:
            p = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
        else:
            p = cmds.pointPosition("%s.vtx[%d]" % (node, vid), world=True)
        return (p[0], p[1], p[2])
    except Exception:
        return None


def from_selection():
    """The selected vertices (faces / edges count as their vertices) and objects, as arc points."""
    points = []
    sel = cmds.ls(selection=True, long=True) or []
    comps = [s for s in sel if "." in s]
    objs = [s for s in sel if "." not in s]
    if comps:
        conv = cmds.polyListComponentConversion(comps, toVertex=True) or []
        verts = cmds.ls(conv, flatten=True, long=True) or [] if conv else []      # ls([]) = everything
        for v in verts:
            node, _dot, rest = v.partition(".vtx[")
            if not rest:
                continue
            if cmds.nodeType(node) == "mesh":
                node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
            points.append((node, int(rest.rstrip("]"))))
    for o in objs:
        if cmds.objectType(o, isAType="transform"):
            points.append((o, None))
    out = []
    for p in points:
        if p not in out:
            out.append(p)
    return out


# -- drawing (the onion skin's overlay pass calls this with Maya's 2D draw manager)
def draw(arcs, drawManager, frameContext, now, pastTint, futureTint):
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaRender as omr
    lines = arcs.lines(now)
    if not any(lines):
        return
    mtx = frameContext.getMatrix(omr.MFrameContext.kViewProjMtx)
    ox, oy, w, h = frameContext.getViewportDimensions()

    def screen(p):
        c = om.MPoint(p[0], p[1], p[2], 1.0) * mtx
        if c.w <= 1e-6:
            return None
        return om.MPoint(ox + (c.x / c.w + 1.0) * 0.5 * w, oy + (c.y / c.w + 1.0) * 0.5 * h)

    span = float(max(arcs.before, arcs.after, 1))

    def colour(f, extra=1.0):
        if abs(f - now) < 0.5:
            r, g, b = 255, 255, 255
        else:
            r, g, b = pastTint if f < now else futureTint
        a = max(0.25, 1.0 - 0.7 * abs(f - now) / span) * extra
        return om.MColor((r / 255.0, g / 255.0, b / 255.0, a))

    drawManager.beginDrawable()
    drawManager.setLineWidth(2.0)
    for line in lines:
        pts = [(f, screen(p)) for f, p in line]
        for (f0, a), (f1, b) in zip(pts, pts[1:]):
            if a is None or b is None or f1 - f0 > 1.5:      # a frame missing: no line across the gap
                continue
            drawManager.setColor(colour(f1 if f1 > now else f0, 0.9))
            drawManager.line2d(a, b)
        for f, s in pts:
            if s is None or not arcs.isDot(f, now):
                continue
            current = abs(f - now) < 0.5
            drawManager.setColor(colour(f))
            drawManager.circle2d(s, 5.0 if current else (4.0 if f in arcs.keys else 2.5), True)
    drawManager.endDrawable()
