"""
The Guide: how to rig with Gus_Rigtool, one page per step, with 'Take me there' buttons that open the right tool
and section in the main window. 'Save as web page' writes the same guide as one .html file to share.

    import gus_rigtool.tools.guide as g; g.show()
"""

import base64
import os

import maya.cmds as cmds

from gus_rigtool import registry
from gus_rigtool.core import ui

WIN = "gusRigGuideWin"
BODY = "gusRigGuideBody"
_page = {"i": 0}

# (key, title, intro, [(what to do, tool, section or None)], tip)
PAGES = [
    ("start", "Start here",
     "Gus_Rigtool follows the way you rig: five steps, left to right. The main window's tabs are in that order.",
     [("Home: every step, which ones this scene has done, and the next one.", "home", None),
      ("Build, Skin, Controls, Connect, Finish: the workflow tabs.", "build", None),
      ("Toolbox: helpers for any step (select, groups, pivots, rename, mirror, joints, ribbons, settings).",
       "select", None)],
     "Lost? Type in the search box at the top (e.g. 'mirror weights') and pick a result. Under every tool's "
     "title, a line says which step it is, with buttons to the steps before and after. Simple view folds the "
     "advanced sections away; Full view shows everything."),
    ("guides", "1. Guides",
     "Guides are the locators you place on the model. The rig is built from them.",
     [("Add a template (Biped, Quadruped, an animal) or single modules.", "build", "Start: template or add a module"),
      ("Pick a module in the list to change its settings (IK/FK, twist joints, fingers...).", "build",
       "Settings of the picked module"),
      ("Place the LEFT side guides on the model, then Mirror guides.", "build", "Guides")],
     "Only place one side: Mirror guides copies it to the right."),
    ("build", "2. Build",
     "Build makes the joints, controls and rig nodes from the guides, in one undo.",
     [("Build: every module that isn't built yet.", "build", "Build"),
      ("Something wrong? Back to guides, adjust, Build picked: only that part is rebuilt.", "build", "Build"),
      ("Keep the skin and your shapes when rebuilding (on by default).", "build", "Keep when rebuilding"),
      ("The face on the mesh: eyes, eyelids (Blink), mouth, brows and strips on ribbons from its edges.", "face",
       "Eyes"),
      ("Change a face part later: Redo this part (it remembers its edges; the skin is kept).", "face",
       "Face ribbons"),
      ("Ribbons for anything, not only the face: build, rebuild with more or fewer controls (the skin is kept), "
       "mirror, switch how the joints follow.", "ribbon", "Builds in the scene")],
     "Skin to the joints in skeleton_grp. Rebuilding keeps the weights."),
    ("skin", "3. Skin",
     "Bind the model to the rig's joints, then paint and mirror the weights.",
     [("Bind: select the meshes (and joints, or none for every rig joint).", "skin", "Bind"),
      ("Mirror weights left to right (joints are labelled so each side finds its twin).", "skin", "Mirror weights"),
      ("Save the weights to a file before big changes.", "skin", "Save / load weights"),
      ("A bend still looks wrong? Sculpt a fix in that pose: it turns on by itself as the joint bends.", "fixes",
       "Sculpt a fix")],
     "ngSkinTools users: the joints are labelled for you - mirror by label."),
    ("controls", "4. Controls",
     "Make the rig nice to animate. Any order, any time after the build.",
     [("Your own joints (props, extra bones)? Make controls puts a control on each, FK chains included.",
       "makectrl", "Controls on the selection"),
      ("Control shapes: replace, scale, colour.", "shapes", "Shapes"),
      ("Follows: lips follow the jaw, and so on.", "follow", "Add follow"),
      ("Stick to skin: controls that ride on the skin (cheeks, lip corners...).", "stick", "Stick to skin"),
      ("Space switches: a hand follows the world, the chest, the head... with no jump.", "spaces", "Make"),
      ("Attributes: add, order, rename on the controls.", "attrs", "Add / edit"),
      ("Lock and hide what animators shouldn't touch.", "channels", "Channels")],
     "Connect and Constraints (the Connect tab) are here too, when you need them."),
    ("finish", "5. Check & publish",
     "Find problems before the animators do, then hand over a clean rig.",
     [("Run the Checker: it finds common problems and fixes the safe ones.", "checker", "Check"),
      ("Tidy the Outliner (optional).", "organize", "Analyze"),
      ("Publish: a clean rig for animators (guides out, everything locked).", "build",
       "Publish (clean rig for animators)"),
      ("Deliver to animators: the rig, their tools and a README in one folder (same section).", "build",
       "Publish (clean rig for animators)"),
      ("Something odd on your character? 'Check this scene' (Checker) writes a diagnosis to send.", "checker",
       "Check"),
      ("Repair: what the checks found that can be fixed safely, ticked and fixed in one undo.", "checker",
       "Repair"),
      ("Feels slow? The speed report times the tools on your character, slowest first.", "settings",
       "Self-test (check the rig builder in this Maya)")],
     "Many files? Checker > Batch runs the checks and publishes several files in one go."),
    ("toolbox", "Toolbox",
     "Helpers you'll use at every step. They're in the Toolbox tab; each one is one undo.",
     [("Pivots: the bottom of the box, from a face or vertices, along a chain; remember one and mirror it.",
       "pivots", "Move pivots to"),
      ("Groups: an offset / sdk group above (or around) anything, where you want it; remove groups.", "groups",
       "Groups"),
      ("Select: by type, inside groups, the twins, the skin joints, the controls of a ribbon; quick sets.",
       "select", "Related to the selection"),
      ("Mirror: controls, poses, and the links between them (follows, spaces, attributes, pivots).", "mirror",
       "Links, attributes and pivots"),
      ("Joints: a joint at the centre of a selection (per object, per piece...), chains, orient.", "joints", None)],
     "Search finds any of these by what you want to do, e.g. 'pivot', 'twin', 'centre'."),
    ("anim", "6. For the animators",
     "Gus Animtool (in the delivery) gives animators a picker, a pose library, IK/FK switching, mirror, tween "
     "and more - on any rig, even hand-made ones: it finds the controls by itself.",
     [("Make the picker yours: in the rig's own file, open the picker, Edit, Save - it's kept IN the rig, so "
       "every animator gets it. Publish and deliver as usual.", "build", "Publish (clean rig for animators)"),
      ("Animators can edit and Save their own picker (it stays on their computer), Export / Import it to take "
       "it home, or go back to the rig's.", "build", "Publish (clean rig for animators)"),
      ("Check the rig the way animators use it: the speed report and the Maya check.", "settings",
       "Self-test (check the rig builder in this Maya)")],
     "Re-deliver after a Gus_Rigtool update so the animators get the newest tools (their window title shows "
     "the version)."),
]


def _icon(name):
    import gus_rigtool
    path = os.path.join(gus_rigtool.ROOT, "icons", name)
    return path.replace("\\", "/") if os.path.isfile(path) else None


def _go(tool, section):
    ui.go_to_tool(tool, section)


def _fill():
    """Draw the current page."""
    for kid in cmds.columnLayout(BODY, query=True, childArray=True) or []:
        try:
            cmds.deleteUI(kid)
        except RuntimeError:
            pass
    cmds.setParent(BODY)
    i = _page["i"]
    key, title, intro, steps, tip = PAGES[i]
    cmds.text(label="  %s" % title, align="left", font="boldLabelFont", height=26)
    pic = _icon("guide_%s.png" % key)
    if pic:
        cmds.image(image=pic, height=70)
    cmds.text(label=intro, align="left", wordWrap=True)
    cmds.separator(height=8, style="in")
    for n, (text, tool, section) in enumerate(steps):
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 4), (2, "both", 2)])
        cmds.text(label="%d.  %s" % (n + 1, text), align="left", wordWrap=True)
        where = registry.get(tool)[1] + (" > " + section if section else "")
        cmds.button(label="Take me there", width=100, annotation="Open " + where,
                    command=lambda *_, t=tool, s=section: _go(t, s))
        cmds.setParent("..")
    cmds.separator(height=8, style="in")
    cmds.text(label="Tip: " + tip, align="left", wordWrap=True, font="obliqueLabelFont")
    cmds.text(label="Page %d of %d" % (i + 1, len(PAGES)), align="right", font="smallPlainLabelFont")


def page(i):
    _page["i"] = max(0, min(len(PAGES) - 1, i))
    if cmds.columnLayout(BODY, exists=True):
        _fill()
        cmds.button(WIN + "Back", edit=True, enable=_page["i"] > 0)
        cmds.button(WIN + "Next", edit=True, enable=_page["i"] < len(PAGES) - 1)


def show(start=0):
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    cmds.window(WIN, title="Gus_Rigtool - Guide", widthHeight=(560, 520))
    form = cmds.formLayout()
    scroll = cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(BODY, adjustableColumn=True, rowSpacing=6)
    cmds.setParent(form)
    bar = cmds.rowLayout(numberOfColumns=5, adjustableColumn=3,
                         columnAttach=[(c, "both", 2) for c in range(1, 6)])
    cmds.button(WIN + "Back", label="<  Back", width=80, command=lambda *_: page(_page["i"] - 1))
    cmds.button(WIN + "Next", label="Next  >", width=80, command=lambda *_: page(_page["i"] + 1))
    cmds.optionMenu(WIN + "Jump", changeCommand=lambda v: page([p[1] for p in PAGES].index(v)))
    for p in PAGES:
        cmds.menuItem(label=p[1])
    cmds.button(label="Save as web page", width=110, command=lambda *_: save_dialog(),
                annotation="The whole guide as one .html file, to share with your team.")
    cmds.button(label="Close", width=60, command=lambda *_: cmds.deleteUI(WIN))
    cmds.setParent(form)
    cmds.formLayout(form, edit=True,
                    attachForm=[(scroll, "top", 4), (scroll, "left", 4), (scroll, "right", 4),
                                (bar, "left", 4), (bar, "right", 4), (bar, "bottom", 4)],
                    attachControl=[(scroll, "bottom", 4, bar)])
    cmds.showWindow(WIN)
    page(start)
    try:
        cmds.optionMenu(WIN + "Jump", edit=True, select=_page["i"] + 1)
    except RuntimeError:
        pass
    return WIN


# ---------------------------------------------------------------------------
# web page
# ---------------------------------------------------------------------------

def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _img_tag(name):
    path = _icon(name)
    if not path:
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return '<img src="data:image/png;base64,%s" alt="">' % data


def html():
    """The guide as one self-contained web page (pictures inside)."""
    import gus_rigtool
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width, initial-scale=1'>",
             "<title>Gus_Rigtool Guide</title><style>",
             ":root{--bg:#fafafa;--fg:#222;--card:#fff;--line:#ddd;--accent:#42789f;--muted:#666}",
             "@media (prefers-color-scheme: dark){:root{--bg:#2b2b2b;--fg:#eee;--card:#353535;--line:#4a4a4a;"
             "--muted:#aaa}}",
             "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px}",
             "main{max-width:760px;margin:auto}section{background:var(--card);border:1px solid var(--line);",
             "border-radius:8px;padding:16px 20px;margin:16px 0}h1{margin:.2em 0}h2{color:var(--accent);margin-top:0}",
             "img{max-width:100%;border-radius:6px}.where{color:var(--muted);font-size:13px}",
             ".tip{font-style:italic;color:var(--muted)}nav a{margin-right:12px;color:var(--accent)}",
             "</style></head><body><main>",
             "<h1>Gus_Rigtool %s - Guide</h1>" % _esc(gus_rigtool.__version__),
             "<p>Open the main window: <code>import gus_rigtool.main as gr; gr.show()</code>. "
             "In Maya, the Guide button (top of the window) has the same pages with 'Take me there' buttons.</p>",
             "<nav>" + "".join("<a href='#%s'>%s</a>" % (k, _esc(t)) for k, t, _i, _s, _tip in PAGES) + "</nav>"]
    for key, title, intro, steps, tip in PAGES:
        parts.append("<section id='%s'><h2>%s</h2>%s<p>%s</p><ol>" % (key, _esc(title),
                                                                       _img_tag("guide_%s.png" % key), _esc(intro)))
        for text, tool, section in steps:
            cat = registry.category_of(tool)[1] or ""
            names = []
            for x in (cat, registry.get(tool)[1], section):
                if x and (not names or names[-1] != x):
                    names.append(x)
            where = " > ".join(names)
            parts.append("<li>%s<br><span class='where'>%s</span></li>" % (_esc(text), _esc(where)))
        parts.append("</ol><p class='tip'>Tip: %s</p></section>" % _esc(tip))
    parts.append("</main></body></html>")
    return "\n".join(parts)


def export_html(path):
    with open(path, "w") as f:
        f.write(html())
    return path


def save_dialog():
    got = cmds.fileDialog2(fileMode=0, caption="Save the guide as a web page",
                           fileFilter="Web page (*.html)", startingDirectory=os.path.expanduser("~"))
    if not got:
        return None
    path = got[0] if got[0].lower().endswith(".html") else got[0] + ".html"
    export_html(path)
    from gus_rigtool.core import utils
    utils.info("Guide", "Saved: %s - open it in a browser or send it to your team." % path)
    return path
