"""
Quick shortcuts for the Gus_Rigtool shelf: the small things a rigger does all day.

Left-click a shelf button runs the usual version; right-click it for the variants.
Every action is one undo, and works on the selection.

    import gus_rigtool.core.quick as q; q.freeze()
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, ui, utils

TOOL = "Quick"
SETTINGS_KEY = "quick"
_M = "import gus_rigtool.core.quick as q; q."

# key, shelf label, tooltip, left-click call, [(right-click label, call)]
BUTTONS = [
    ("freeze", "Freeze", "Freeze transformations (translate, rotate, scale). Joints: rotation goes "
     "into the joint orient. Right-click: only translate / rotate / scale.",
     "freeze()", [("Freeze translate", "freeze(rotate=False, scale=False)"),
                  ("Freeze rotate", "freeze(translate=False, scale=False)"),
                  ("Freeze scale", "freeze(translate=False, rotate=False)")]),
    ("pivot", "Center pivot", "Center the pivot. Right-click: pivot to the world origin, or to the bottom.",
     "center_pivot()", [("Pivot to world origin", "center_pivot('origin')"),
                        ("Pivot to bottom", "center_pivot('bottom')")]),
    ("history", "Delete history", "Delete history. Default: the safe one (non-deformer history, keeps "
     "skin clusters and blendshapes). Right-click: delete all history.",
     "delete_history()", [("Delete non-deformer history (safe)", "delete_history('safe')"),
                          ("Delete ALL history", "delete_history('all')")]),
    ("reset", "Reset", "Translate and rotate to 0, scale to 1. Locked or connected channels are "
     "skipped. Right-click: custom attributes too.",
     "reset()", [("Reset transforms", "reset()"),
                 ("Reset transforms + custom attributes", "reset(custom=True)")]),
    ("snap", "Snap", "Snap the selected objects to the last selected one (position + rotation). "
     "Last selection can be vertices / edges / faces (position only). Right-click: position or rotation only.",
     "snap()", [("Snap position + rotation", "snap('both')"),
                ("Snap position", "snap('position')"),
                ("Snap rotation", "snap('rotation')")]),
    ("point", "Loc at sel", "A locator (or joint) at the centre of the selection: objects, vertices, "
     "edges or faces. Right-click: joint, or one per object.",
     "point_at_selection()", [("Locator at centre", "point_at_selection('locator')"),
                              ("Joint at centre", "point_at_selection('joint')"),
                              ("One locator per object", "point_at_selection('locator', each=True)"),
                              ("One joint per object", "point_at_selection('joint', each=True)")]),
    ("lock", "Lock/Hide", "Lock and hide scale and visibility on the selected controls. "
     "Right-click: unlock and show everything.",
     "lock_hide()", [("Lock + hide scale and visibility", "lock_hide()"),
                     ("Lock + hide scale only", "lock_hide(('sx', 'sy', 'sz'))"),
                     ("Unlock + show everything", "unlock_all()")]),
    ("axes", "Joint axes", "Show / hide the local rotation axes of the selected joints and the joints "
     "below them (all joints if nothing is selected). Right-click: all joints.",
     "joint_axes()", [("All joints: show axes", "joint_axes('all', True)"),
                      ("All joints: hide axes", "joint_axes('all', False)")]),
    ("jsize", "Joint size", "How big joints are drawn in the scene (a slider). Right-click: quick sizes.",
     "joint_size()", [("Joint size 0.25", "joint_size(0.25)"), ("Joint size 0.5", "joint_size(0.5)"),
                      ("Joint size 1", "joint_size(1.0)"), ("Joint size 2", "joint_size(2.0)")]),
    ("pose", "Mirror pose", "Mirror the selected controls' pose onto their twins (both sides selected: "
     "left -> right). Right-click: flip, L -> R, R -> L, reset both sides.",
     "mirror_pose()", [("Mirror pose", "mirror_pose()"),
                       ("Flip pose (swap sides)", "flip_pose()"),
                       ("Pose L -> R", "mirror_pose('L>R')"),
                       ("Pose R -> L", "mirror_pose('R>L')"),
                       ("Reset both sides", "reset_pose()"),
                       ("Live follow L -> R", "follow_on('L>R')"),
                       ("Live follow R -> L", "follow_on('R>L')"),
                       ("Live follow off (selection)", "follow_off('selection')"),
                       ("Live follow off (whole scene)", "follow_off('all')")]),
    ("twin", "Select twin", "Select the other side of the selection. Right-click: both sides.",
     "select_twins()", [("Select the other side", "select_twins('other')"),
                        ("Select both sides", "select_twins('both')")]),
    ("ikfk", "IK/FK", "Builder rigs: switch the selected limb between IK and FK, matching the pose (no jump). "
     "Right-click: to FK, to IK.",
     "ikfk_switch()", [("Switch to FK (match)", "ikfk_switch('fk')"),
                       ("Switch to IK (match)", "ikfk_switch('ik')")]),
    ("alone", "Move alone", "Move / rotate one object without its children following (Maya's Preserve "
     "Children), like D on a joint. Click again to turn it off. Right-click: on, off.",
     "move_alone()", [("Move alone: on", "move_alone(True)"), ("Move alone: off", "move_alone(False)")]),
    ("offset", "Offset grp", "Offset group(s) on the selection, with the options of the Groups tool. "
     "Right-click: open the Groups tool.",
     "offset_group()", [("Open the Groups tool", "open_groups()")]),
]

DEFAULTS = {
    "hidden": [],                          # shortcuts left off the shelf (new ones always show)
    "history_default": "safe",             # left-click of Delete history: 'safe' or 'all'
    "snap_default": "both",                # left-click of Snap: 'both', 'position', 'rotation'
    "point_default": "locator",            # left-click of Loc at sel: 'locator' or 'joint'
}
CHOICES = {
    "history_default": [("safe", "Safe (non-deformer)"), ("all", "All history")],
    "snap_default": [("both", "Position + rotation"), ("position", "Position"), ("rotation", "Rotation")],
    "point_default": [("locator", "Locator"), ("joint", "Joint")],
}


def settings():
    return utils.tool_settings(SETTINGS_KEY, DEFAULTS)


def shelf_buttons():
    """[(key, label, tooltip, command, [(menu label, command)])] of the shortcuts to show."""
    hidden = settings().get("hidden", [])
    return [(k, label, tip, _M + call, [(m, _M + c) for m, c in menu])
            for k, label, tip, call, menu in BUTTONS if k not in hidden]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _action(name):
    """One undo per action; problems become a warning / error report, never a silent failure."""
    def wrap(fn):
        def run(*args, **kwargs):
            try:
                with utils.undo_chunk("gusrig_" + name):
                    return fn(*args, **kwargs)
            except RuntimeError as e:
                utils.warn(TOOL, str(e).strip())
            except Exception as e:
                ui.report_error(e, "quick_" + name)
        run.__name__ = fn.__name__
        run.__doc__ = fn.__doc__
        return run
    return wrap


def _objects(need=1):
    objs = utils.selected_transforms(ordered=True)
    if len(objs) < need:
        raise RuntimeError("select %s first." % ("an object" if need == 1 else "%d or more objects" % need))
    return objs


def _components():
    """Selected vertices / edges / faces / CVs (flattened as vertices or CVs)."""
    comps = cmds.filterExpand(selectionMask=(28, 31, 32, 34), expand=False) or []
    if not comps:
        return []
    verts = cmds.polyListComponentConversion(comps, toVertex=True) or []
    cvs = [c for c in comps if ".cv[" in c]
    return cmds.ls(verts + cvs, flatten=True) or []


def _centre(points):
    n = float(len(points))
    return [sum(p[i] for p in points) / n for i in range(3)]


def _pos(node):
    return cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)


_settable = utils.settable


def _done(what, count, skipped=None):
    msg = "%s %d object(s)." % (what, count)
    if skipped:
        msg += " Skipped %d: %s" % (len(skipped), ", ".join(naming.short_name(s) for s in skipped[:5]))
        msg += "..." if len(skipped) > 5 else ""
        utils.warn(TOOL, msg)
    else:
        utils.info(TOOL, msg)


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------

@_action("freeze")
def freeze(translate=True, rotate=True, scale=True):
    """Freeze transformations. On joints Maya moves the rotation into the joint orient."""
    done, skipped = 0, []
    for obj in _objects():
        try:
            cmds.makeIdentity(obj, apply=True, translate=translate, rotate=rotate, scale=scale,
                              normal=0, preserveNormals=True)
            done += 1
        except RuntimeError:
            skipped.append(obj)            # locked / connected channels, skinned mesh...
    parts = [n for n, on in (("translate", translate), ("rotate", rotate), ("scale", scale)) if on]
    _done("froze %s on" % "/".join(parts), done, skipped)


@_action("pivot")
def center_pivot(where="center"):
    """Pivot to the centre of the object, the world origin, or the bottom centre."""
    objs = _objects()
    for obj in objs:
        if where == "origin":
            cmds.xform(obj, worldSpace=True, pivots=(0, 0, 0))
        elif where == "bottom":
            bb = cmds.exactWorldBoundingBox(obj)
            cmds.xform(obj, worldSpace=True, pivots=((bb[0] + bb[3]) / 2.0, bb[1], (bb[2] + bb[5]) / 2.0))
        else:
            cmds.xform(obj, centerPivots=True)
    _done({"origin": "pivot to world origin on", "bottom": "pivot to bottom on"}.get(where, "centered the pivot of"),
          len(objs))


def _deformers(obj):
    hist = cmds.listHistory(obj, pruneDagObjects=True) or []
    return utils.ls(hist, type="geometryFilter") or []


@_action("history")
def delete_history(mode=None):
    """'safe': non-deformer history (keeps skin clusters, blendshapes...). 'all': everything."""
    mode = mode or settings().get("history_default", "safe")
    objs = _objects()
    if mode == "all":
        deformed = [o for o in objs if _deformers(o)]
        if deformed:
            answer = cmds.confirmDialog(
                title="Delete ALL history",
                message="%d of the selected objects have a skin cluster or other deformers "
                        "(e.g. %s).\nDeleting all history removes them.\n\nTip: the safe version keeps them."
                        % (len(deformed), naming.short_name(deformed[0])),
                button=["Delete all", "Safe instead", "Cancel"], defaultButton="Cancel",
                cancelButton="Cancel", dismissString="Cancel")
            if answer == "Cancel":
                return
            if answer == "Safe instead":
                mode = "safe"
    if mode == "all":
        cmds.delete(objs, constructionHistory=True)
        _done("deleted all history on", len(objs))
        return
    done, skipped = 0, []
    for obj in objs:
        try:
            cmds.bakePartialHistory(obj, prePostDeformers=True)
            done += 1
        except RuntimeError:
            try:
                if not _deformers(obj):
                    cmds.delete(obj, constructionHistory=True)
                    done += 1
                    continue
            except RuntimeError:
                pass
            skipped.append(obj)
    _done("deleted non-deformer history on", done, skipped)


@_action("reset")
def reset(custom=False):
    """Translate / rotate to 0, scale to 1 (custom keyable attributes to their default)."""
    objs = _objects()
    guides_ = [o for o in objs if cmds.attributeQuery("gusRole", node=o, exists=True)]
    objs = [o for o in objs if o not in guides_]                  # guides keep their place
    if guides_ and not objs:
        raise RuntimeError("those are guides - Reset leaves guides where you placed them.")
    changed = 0
    for obj in objs:
        for attr, value in (("t", 0.0), ("r", 0.0), ("s", 1.0)):
            for axis in "xyz":
                plug = "%s.%s%s" % (obj, attr, axis)
                if _settable(plug):
                    cmds.setAttr(plug, value)
        if custom:
            for attr in cmds.listAttr(obj, keyable=True, userDefined=True) or []:
                plug = "%s.%s" % (obj, attr)
                try:
                    default = cmds.attributeQuery(attr, node=obj, listDefault=True)
                except RuntimeError:
                    continue
                if default and _settable(plug):
                    try:
                        cmds.setAttr(plug, default[0])
                    except RuntimeError:
                        pass
        changed += 1
    _done("reset", changed)


@_action("snap")
def snap(mode=None):
    """Snap the selected objects onto the last selected one (or the centre of selected components)."""
    mode = mode or settings().get("snap_default", "both")
    comps = _components()
    if comps:
        objs = [o for o in utils.selected_transforms(ordered=True)
                if not any(c.split(".")[0].split("|")[-1] == naming.short_name(o) for c in comps)]
        if not objs:
            raise RuntimeError("select the object(s) to move, then the vertices / edges / faces to snap to.")
        target = _centre([cmds.xform(c, query=True, worldSpace=True, translation=True) for c in comps])
        for obj in objs:
            piv = _pos(obj)                                          # the pivot lands on the point
            cmds.move(target[0] - piv[0], target[1] - piv[1], target[2] - piv[2], obj,
                      relative=True, worldSpace=True)
        _done("snapped to the centre of the components:", len(objs))
        return
    objs = _objects(need=2)
    target, movers = objs[-1], objs[:-1]
    for obj in movers:
        cmds.matchTransform(obj, target, position=mode in ("both", "position"),
                            rotation=mode in ("both", "rotation"))
    _done("snapped (%s) to %s:" % ({"both": "position + rotation"}.get(mode, mode), naming.short_name(target)),
          len(movers))


@_action("point")
def point_at_selection(kind=None, each=False):
    """A locator or joint at the centre of the selection (objects and / or components) - the Joints tab's
    'At the centre of the selection' with its default options."""
    from gus_rigtool.core import centre_point
    kind = kind or settings().get("point_default", "locator")
    made = centre_point.make(kind=kind, per="object" if each else "all")
    utils.info(TOOL, "made %d %s(s): %s" % (len(made), kind, ", ".join(naming.short_name(m) for m in made[:5])))


@_action("lock")
def lock_hide(attrs=("sx", "sy", "sz", "v")):
    objs = _objects()
    for obj in objs:
        for attr in attrs:
            plug = "%s.%s" % (obj, attr)
            if cmds.objExists(plug):
                cmds.setAttr(plug, lock=True, keyable=False, channelBox=False)
    _done("locked and hid %s on" % ", ".join(attrs), len(objs))


@_action("unlock")
def unlock_all():
    objs = _objects()
    for obj in objs:
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"):
            plug = "%s.%s" % (obj, attr)
            if cmds.objExists(plug):
                cmds.setAttr(plug, lock=False)
                cmds.setAttr(plug, keyable=True)
    _done("unlocked and showed the transform channels on", len(objs))


@_action("axes")
def joint_axes(scope="selection", state=None):
    """Toggle (or set) the local rotation axes of joints."""
    joints = []
    if scope == "selection":
        for obj in cmds.ls(selection=True, long=True, type="joint") or []:
            joints.append(obj)
            joints += cmds.listRelatives(obj, allDescendents=True, type="joint", fullPath=True) or []
        sel = cmds.ls(selection=True)
        if not joints and sel:
            for obj in utils.selected_transforms():        # e.g. a group with joints inside
                joints += cmds.listRelatives(obj, allDescendents=True, type="joint", fullPath=True) or []
        if not joints and not sel:
            joints = cmds.ls(type="joint", long=True) or []
    else:
        joints = cmds.ls(type="joint", long=True) or []
    joints = list(dict.fromkeys(joints))
    if not joints:
        raise RuntimeError("no joints found %s." % ("in the scene" if scope == "all" else "in the selection"))
    if state is None:
        state = not cmds.getAttr(joints[0] + ".displayLocalAxis")
    for j in joints:
        try:
            cmds.setAttr(j + ".displayLocalAxis", bool(state))
        except RuntimeError:
            pass
    utils.info(TOOL, "%s the axes of %d joint(s)." % ("showing" if state else "hid", len(joints)))


SIZE_WIN = "gusrig_joint_size_win"


def joint_size(value=None):
    """Set the joint display size, or open a small slider window."""
    if value is not None:
        cmds.jointDisplayScale(float(value))
        utils.info(TOOL, "joint size %g." % value)
        return
    if cmds.window(SIZE_WIN, exists=True):
        cmds.deleteUI(SIZE_WIN)
    cmds.window(SIZE_WIN, title="Joint size", widthHeight=(330, 40), sizeable=True, toolbox=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    current = cmds.jointDisplayScale(query=True)
    cmds.floatSliderGrp(label="Joint size", field=True, value=current, minValue=0.05, maxValue=5.0,
                        fieldMaxValue=100.0, precision=2, step=0.05, columnWidth3=(60, 50, 200),
                        dragCommand=lambda v: cmds.jointDisplayScale(float(v)),
                        changeCommand=lambda v: cmds.jointDisplayScale(float(v)))
    cmds.showWindow(SIZE_WIN)


@_action("pose")
def mirror_pose(direction="auto"):
    from gus_rigtool.core import mirror_engine
    mirror_engine.mirror_pose(direction)


@_action("flip")
def flip_pose():
    from gus_rigtool.core import mirror_engine
    mirror_engine.flip_pose()


@_action("reset_pose")
def reset_pose():
    from gus_rigtool.core import mirror_engine
    mirror_engine.reset_pose()


@_action("follow")
def follow_on(direction="L>R"):
    from gus_rigtool.core import mirror_engine
    mirror_engine.follow_on(direction)


@_action("unfollow")
def follow_off(scope="selection"):
    from gus_rigtool.core import mirror_engine
    mirror_engine.follow_off(scope)


@_action("twin")
def select_twins(mode="other"):
    from gus_rigtool.core import mirror_engine
    mirror_engine.select_twins(mode)


@_action("ikfk")
def ikfk_switch(to="toggle"):
    from gus_rigtool.builder import limb
    limb.match_selected(to)


def is_move_alone():
    try:
        return bool(cmds.manipMoveContext("Move", query=True, preserveChildPosition=True))
    except (RuntimeError, TypeError):
        return False


def move_alone(state=None, quiet=False):
    """Move / Rotate tools: children stay where they are (True) or follow (False). None = toggle."""
    if state is None:
        state = not is_move_alone()
    for ctx, fn in (("Move", cmds.manipMoveContext), ("Rotate", cmds.manipRotateContext)):
        try:
            fn(ctx, edit=True, preserveChildPosition=bool(state))
        except (RuntimeError, TypeError):
            pass
    if not quiet:
        utils.info(TOOL, "move alone %s: %s" % ("ON" if state else "off", "children stay where they are"
                                                if state else "children follow again"))
    return state


@_action("offset")
def offset_group():
    """Offset group(s) on the selection with the Groups tool's saved options."""
    from gus_rigtool.tools import group_maker as gm
    gm.apply(utils.tool_settings(gm.SETTINGS_KEY, gm.DEFAULTS))


def open_groups():
    ui.open_panel("groups")
