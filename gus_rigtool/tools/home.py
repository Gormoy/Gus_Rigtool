"""
Home: the rigging workflow at a glance - five steps, which are done in this scene, and the next one.

    Guides -> Build -> Skin -> Controls -> Check & publish

Each step: what you do, a 'Go' button that opens the right tool and section, and a light: done / next / to do.
The toolbox (select, groups, pivots, rename, mirror, joints, ribbons...) is for any step.
"""

import maya.cmds as cmds

from gus_rigtool import registry
from gus_rigtool.core import ui

TOOL = "Home"
_P, N, _w, _guard = ui.tool_helpers("p_home_", TOOL)

COLORS = {"done": (0.22, 0.42, 0.25), "next": (0.26, 0.42, 0.56), "todo": (0.27, 0.27, 0.27),
          "any": (0.30, 0.30, 0.30)}


# ---------------------------------------------------------------------------
# where is this scene?
# ---------------------------------------------------------------------------

def _guides_done():
    from gus_rigtool.builder import guides
    try:
        return bool(guides.module_groups())
    except Exception:
        return False


def _built():
    from gus_rigtool.builder import build as bld
    try:
        return any(bld.is_module_built(i) for i in bld._infos())
    except Exception:
        return False


def _skinned():
    from gus_rigtool.builder import skin_keep
    from gus_rigtool.core.skin_tools import rig_joints
    try:
        joints = rig_joints()
        return bool(joints and skin_keep.skins_on(joints))
    except Exception:
        return False


def _published():
    from gus_rigtool.builder import publish
    try:
        return bool(publish.is_published())
    except Exception:
        return False


def state():
    """{stage key: 'done' | 'next' | 'todo' | 'any'} for this scene, and the next stage key."""
    done = {"guides": _guides_done(), "build": _built(), "skin": _skinned(), "finish": _published()}
    out, nxt = {}, None
    for key, _t, _d, _tool, _sec in registry.STAGES:
        if key == "controls":                       # any time after the build: can't be 'finished'
            out[key] = "any" if done["build"] else "todo"
            continue
        if done.get(key):
            out[key] = "done"
        elif nxt is None:
            out[key] = "next"
            nxt = key
        else:
            out[key] = "todo"
    return out, nxt


def advice(nxt):
    """One sentence: what to do now."""
    return {None: "The rig is published - animators can use it. Change something? Unpublish happens by itself "
                  "when you edit; Publish again when done.",
            "guides": "Start here: add a template (Biped, Quadruped, an animal) or modules, then place the guides.",
            "build": "Guides are in. Place the LEFT side, Mirror guides, then Build.",
            "skin": "The rig is built. Next: bind your model to the rig's joints (Skin > Bind).",
            "finish": "Built and skinned. Polish the controls if you like, then run the Checker and Publish."}.get(
        nxt, "")


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def refresh(*_):
    if not cmds.columnLayout(N("Steps"), exists=True):
        return
    st, nxt = state()
    cmds.text(N("Advice"), edit=True, label="  " + advice(nxt))
    for i, (key, title, desc, tool, sec) in enumerate(registry.STAGES):
        s = st[key]
        mark = {"done": "Done", "next": "NEXT", "todo": "", "any": "Any time"}[s]
        cmds.text(N("Mark%d" % i), edit=True, label=mark, backgroundColor=COLORS[s])
        cmds.button(N("Go%d" % i), edit=True, backgroundColor=COLORS["next"] if s == "next" else COLORS["todo"],
                    label="Go  >" if s != "next" else "Start  >")


def suggest(sel=None):
    """5.4.0: (what you have selected, [(button label, tool, section)]) - the 3-6 things you'd likely do next."""
    sel = cmds.ls(selection=True, long=True) if sel is None else sel
    if not sel:
        return "Nothing selected", [("Select joints / controls / groups...", "select", None),
                                     ("Build the rig", "build", None), ("Check the scene", "checker", None)]
    comps = [x for x in sel if "." in x]
    if comps:
        if any(".e[" in x for x in comps):
            return "Edges", [("Ribbon on these edges (face strip)", "face", None),
                             ("Cloth: ribbon on a garment's edges", "skin", "Cloth"),
                             ("Joints along these edges", "joints", None)]
        return "Vertices", [("Vertex weights (copy / paste / hammer)", "skin", "Vertex weights"),
                            ("A sculpt fix", "fixes", None), ("Stick a control to the skin here", "stick", None)]
    kinds = set()
    for n in sel:
        t = cmds.nodeType(n)
        if t == "joint":
            kinds.add("joint")
            continue
        shapes = cmds.listRelatives(n, shapes=True, fullPath=True) or []
        st = set(cmds.nodeType(x) for x in shapes)
        if "nurbsCurve" in st:
            kinds.add("control")
        elif "mesh" in st:
            from gus_rigtool.core.skin_mirror import skin_of
            kinds.add("skinned mesh" if skin_of(n) else "mesh")
        elif "nurbsSurface" in st:
            kinds.add("surface")
        else:
            kinds.add("group")
    out = []
    if "control" in kinds:
        out += [("Shape / colour", "shapes", None), ("Limits, in front, stop at the body", "behaviour", None),
                ("Attributes", "attrs", None), ("Space switch / follow", "spaces", None),
                ("Mirror to the other side", "mirror", None)]
    if "joint" in kinds:
        out += [("Controls on these joints", "makectrl", None), ("Add them to a skin", "skin", None),
                ("Constrain", "constrain", None), ("Mirror joints", "mirror", None)]
    if "skinned mesh" in kinds:
        out += [("Skin: add joints, copy, mirror weights", "skin", None), ("Cloth / repair weights", "skin", "Cloth"),
                ("A corrective fix", "fixes", None)]
    if "mesh" in kinds:
        out += [("Bind skin", "skin", None), ("Face kit on this head", "face", None)]
    if "surface" in kinds:
        out += [("Ribbon on this surface", "ribbon", None)]
    if "group" in kinds:
        out += [("Offset groups / pivots", "groups", None), ("Constrain", "constrain", None)]
    seen, uniq = set(), []
    for o in out:
        if (o[1], o[2]) not in seen:
            seen.add((o[1], o[2]))
            uniq.append(o)
    return ", ".join(sorted(kinds)).capitalize(), uniq[:6]


def refresh_suggest(*_):
    col = N("Suggest")
    if not cmds.columnLayout(col, exists=True):
        return
    for c in cmds.columnLayout(col, query=True, childArray=True) or []:
        cmds.deleteUI(c)
    what, items = suggest()
    cmds.setParent(col)
    cmds.text(label="  Selected: %s" % what, align="left", font="boldLabelFont", width=1)
    for label, tool, sec in items:
        cmds.button(label="%s  >" % label, height=22, width=1,
                    annotation="Open %s." % registry.get(tool)[1],
                    command=lambda *_, t=tool, s=sec: ui.go_to_tool(t, s))


def build(prefix="p_home_"):
    _P["p"] = prefix
    cmds.text(N("Advice"), label="", align="left", wordWrap=True, height=34, font="boldLabelFont")
    cmds.columnLayout(N("Steps"), adjustableColumn=True, rowSpacing=3)
    for i, (key, title, desc, tool, sec) in enumerate(registry.STAGES):
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=3, columnWidth4=(34, 70, 220, 70),
                       columnAttach=[(1, "both", 2), (2, "both", 2), (3, "both", 4), (4, "both", 2)], height=46)
        cmds.image(image=ui_icon(tool), width=32, height=32)
        cmds.text(N("Mark%d" % i), label="", align="center", height=40, font="boldLabelFont")
        cmds.text(label="%d. %s\n%s" % (i + 1, title, desc), align="left", wordWrap=True,
                  annotation=desc)
        cmds.button(N("Go%d" % i), label="Go  >", height=34,
                    annotation="Open %s > %s." % (registry.get(tool)[1], sec),
                    command=lambda *_, t=tool, s=sec: ui.go_to_tool(t, s))
        cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=8, style="in")
    ui.section("For what you have selected", help_text="The likely next things for your selection - a mesh, joints, "
               "controls, a surface, edges or vertices. It follows the selection.")
    cmds.columnLayout(N("Suggest"), adjustableColumn=True, rowSpacing=2)
    cmds.setParent("..")
    ui.end_section()
    cmds.text(label="  Toolbox (any step): Select, Groups, Mirror, Rename, Pivots, Settings. Where is everything: "
              "the Map button under the search box.", align="left", wordWrap=True)
    ui.row(3, 113)
    cmds.button(label="Refresh", command=_w(refresh), annotation="Look at the scene again.")
    cmds.button(label="Open the Guide", command=_w(lambda *_: __import__("gus_rigtool.tools.guide",
                                                                         fromlist=["x"]).show()),
                annotation="Step-by-step pages with 'Take me there' buttons.")
    cmds.button(label="Toolbox  >", command=_w(lambda *_: ui.go_to_tool("select")),
                annotation="The helpers for any step.")
    cmds.setParent("..")
    try:
        cmds.scriptJob(event=["SceneOpened", _w(refresh)], parent=N("Steps"))
        cmds.scriptJob(event=["NewSceneOpened", _w(refresh)], parent=N("Steps"))
    except (RuntimeError, TypeError):
        pass
    refresh()
    ui.on_selection(N("Suggest"), _w(refresh_suggest))
    refresh_suggest()


def say_next(tool, done_text):
    """'<done_text> Next: Skin > Bind.' on the status line, and the Home page updated."""
    from gus_rigtool.core import utils
    try:
        _st, nxt = state()
    except Exception:
        nxt = "?"
    if nxt == "?":
        hint = ""
    elif nxt is None:
        hint = " The rig is published."
    else:
        st = [x for x in registry.STAGES if x[0] == nxt][0]
        hint = " Next: %s > %s (Home shows every step)." % (registry.get(st[3])[1], st[4])
    utils.info(tool, done_text + hint)
    try:
        refresh()
    except Exception:
        pass
    return hint


def ui_icon(tool):
    import os
    import gus_rigtool
    path = os.path.join(gus_rigtool.ROOT, "icons", "gr_%s.png" % tool)
    return path.replace("\\", "/") if os.path.isfile(path) else "pythonFamily.png"


def show():
    ui.go_to_tool("home")
