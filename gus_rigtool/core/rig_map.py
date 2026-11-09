"""
Rig map (5.5.0): everything the rig does, in one tree - the controls by part with what each has (follows, space
switch, limits, body stop, what drives it), the drivers (controls that move other things through driven keys /
utility nodes), the jiggles and waves. Clicking an item selects its node.

    from gus_rigtool.core import rig_map
    rig_map.entries()       # [(id, parent id, label, node or None)]
    rig_map.text()          # the same as an indented text
    rig_map.show()          # the window
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, network_tools

WIN = "gusRigRigMapWin"


def _short(n):
    return naming.short_name(n)


def _drivers():
    """{driver node: set(driven nodes)} through driven-key curves and utility nodes (one hop through each curve's
    network, end to end)."""
    out = {}
    seen = set()
    for crv in cmds.ls(type=list(network_tools.CURVES)) or []:
        if crv in seen:
            continue
        net = network_tools.network([crv])
        seen.update(_short(x) for x in net["nodes"])
        for d in net["drivers"]:
            if cmds.nodeType(d) == "time":
                continue
            out.setdefault(d, set()).update(x for x in net["driven"] if x != d)
    return out


def _control_notes(c, follows, driven_by):
    from gus_rigtool.core import limits, spaces
    notes = []
    for ctrl, driver, _w, channels, _src in follows:
        if ctrl == c or _short(ctrl) == _short(c):
            notes.append(("follows %s (%s)" % (_short(driver) if driver else "?", channels), driver))
    try:
        sp = spaces.read(c)
    except Exception:
        sp = None
    if sp:
        labels = [t[0] if isinstance(t, (list, tuple)) and t else str(t) for t in sp.get("targets", [])]
        notes.append(("space switch: %s" % (", ".join(labels) or sp.get("attr", "space")), None))
    try:
        lims = limits.limited(c)
    except Exception:
        lims = {}
    if lims:
        fmt = lambda v: "-" if v is None else "%g" % v
        notes.append(("limits: " + ", ".join("%s %s..%s" % (ch, fmt(lo), fmt(hi))
                                             for ch, (lo, hi) in sorted(lims.items())), None))
    if cmds.attributeQuery("gusBodyStop", node=c, exists=True):
        notes.append(("stops at the body", None))
    for d in sorted(driven_by.get(c, set()) | _above(c, driven_by), key=_short):
        notes.append(("driven by %s" % _short(d), d))
    return notes


def _above(c, driven_by, levels=4):
    """Drivers of the groups above a control (its _sdk / offset groups), up to the next control."""
    from gus_rigtool.tools import checker
    out = set()
    p = c
    for _i in range(levels):
        p = (cmds.listRelatives(p, parent=True, fullPath=True) or [None])[0]
        if not p or checker.is_control(p):
            break
        out |= driven_by.get(p, set())
    return out


def entries():
    """[(id, parent id or '', label, node or None)] in display order."""
    from gus_rigtool.builder import chain
    from gus_rigtool.core import follow, on_top
    rows = []
    ctrls = on_top.controls()
    try:
        follows = follow.all_follows()
    except Exception:
        follows = []
    drivers = _drivers()
    driven_by = {}
    for d, targets in drivers.items():
        for t in targets:
            driven_by.setdefault(t, set()).add(d)
    parts = {}
    for c in ctrls:
        parts.setdefault(network_tools._part(c), []).append(c)
    rows.append(("controls", "", "Controls (%d)" % len(ctrls), None))
    for p in sorted(parts):
        pid = "part:" + p
        rows.append((pid, "controls", "%s (%d)" % (p, len(parts[p])), None))
        for c in sorted(parts[p], key=_short):
            cid = "ctrl:" + c
            notes = _control_notes(c, follows, driven_by)
            rows.append((cid, pid, _short(c) + ("  *" if notes else ""), c))
            for i, (label, node) in enumerate(notes):
                rows.append(("%s#%d" % (cid, i), cid, label, node))
    rows.append(("drivers", "", "Drivers (%d)" % len(drivers), None))
    for d in sorted(drivers, key=_short):
        did = "drv:" + d
        rows.append((did, "drivers", "%s -> %d node(s)" % (_short(d), len(drivers[d])), d))
        for i, t in enumerate(sorted(drivers[d], key=_short)):
            rows.append(("%s#%d" % (did, i), did, _short(t), t))
    try:
        motion = chain.motion_exprs()
    except Exception:
        motion = []
    rows.append(("motion", "", "Jiggles and waves (%d)" % len(motion), None))
    for e in motion:
        rows.append(("expr:" + e, "motion", _short(e), e))
    return rows


def text():
    rows = entries()
    depth = {"": -1}
    out = []
    for i, parent, label, _node in rows:
        depth[i] = depth.get(parent, -1) + 1
        out.append("  " * depth[i] + label)
    return "\n".join(out)


def _select(item, *_):
    node = _NODES.get(item)
    if node and cmds.objExists(node):
        cmds.select(node, replace=True)


_NODES = {}


def show(*_):
    """The window: a tree; click selects. Falls back to a text report when the tree can't be made."""
    from gus_rigtool.core import ui
    rows = entries()
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    _NODES.clear()
    try:
        cmds.window(WIN, title="Gus_Rigtool - rig map", widthHeight=(460, 560))
        form = cmds.formLayout()
        tree = cmds.treeView(numberOfButtons=0, abr=False, selectCommand=lambda item, on: _select(item) or True)
        refresh = cmds.button(label="Refresh", height=26, command=show)
        as_text = cmds.button(label="As text", height=26,
                              command=lambda *_: ui.report_window("Gus_Rigtool - rig map", text()))
        cmds.formLayout(form, edit=True,
                        attachForm=[(tree, "top", 4), (tree, "left", 4), (tree, "right", 4), (refresh, "left", 4),
                                    (refresh, "bottom", 4), (as_text, "right", 4), (as_text, "bottom", 4)],
                        attachControl=[(tree, "bottom", 4, refresh)],
                        attachPosition=[(refresh, "right", 2, 50), (as_text, "left", 2, 50)])
        for i, parent, label, node in rows:
            cmds.treeView(tree, edit=True, addItem=(i, parent))
            cmds.treeView(tree, edit=True, displayLabel=(i, label))
            if node:
                _NODES[i] = node
        for i, _p, _l, _n in rows:
            if i.startswith(("part:", "ctrl:", "drv:")):
                cmds.treeView(tree, edit=True, expandItem=(i, False))
        cmds.showWindow(WIN)
    except (RuntimeError, TypeError):
        if cmds.window(WIN, exists=True):
            cmds.deleteUI(WIN)
        return ui.report_window("Gus_Rigtool - rig map", text())
    return WIN
