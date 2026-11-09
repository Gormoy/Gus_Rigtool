"""Every Gus_Rigtool tool: key, tab label, module, one-line description."""

TOOLS = [
    ("home", "Home", "gus_rigtool.tools.home", "Where you are in the rig, and the next step."),
    ("shapes", "Shapes", "gus_rigtool.tools.shape_library", "Create, replace and edit control shapes."),
    ("mirror", "Mirror", "gus_rigtool.tools.mirror_tool", "Shapes, controls, joints and geometry, L <-> R."),
    ("joints", "Joints", "gus_rigtool.tools.joint_chain", "Evenly spaced joint chains on curves, edges or objects."),
    ("ribbon", "Ribbon", "gus_rigtool.tools.ribbon_tool", "Ribbon rigs on NURBS surfaces: build, rebuild, mirror."),
    ("skin", "Skin", "gus_rigtool.tools.skin_tool", "Bind, copy, clean, mirror and save skin weights."),
    ("fixes", "Fixes", "gus_rigtool.tools.fixes_tool", "Corrective shapes: sculpt a fix in a bent pose, it turns on "
     "by itself."),
    ("makectrl", "Make controls", "gus_rigtool.tools.make_controls_tool", "A control on each selected joint or "
     "object: shape, offset groups, constraint, FK chains."),
    ("stick", "Stick to skin", "gus_rigtool.tools.stick_tab", "Controls that ride on the skin (lips, cheeks, "
     "brows...), with a 'stick' slider."),
    ("follow", "Follow", "gus_rigtool.tools.follow_tab", "Controls follow part of a driver (lips follow the jaw...)."),
    ("build", "Build", "gus_rigtool.tools.build_tab", "A full body rig from guides: modules, naming, IK/FK."),
    ("face", "Face", "gus_rigtool.tools.face_kit_tool", "The face on the mesh: eyelids, mouth, brows and strips "
     "on ribbons, eyes with Blink."),
    ("select", "Select", "gus_rigtool.tools.selector", "Select joints, controls, groups... inside groups."),
    ("groups", "Groups", "gus_rigtool.tools.group_maker", "Offset / zero groups named after the selection."),
    ("pivots", "Pivots", "gus_rigtool.tools.pivot_matcher", "Put many pivots on the same spot."),
    ("sdk", "SDK", "gus_rigtool.tools.sdk_tool", "Mirror or copy set driven keys."),
    ("attrs", "Attributes", "gus_rigtool.tools.attr_tool", "Order, add, rename, delete, copy attributes."),
    ("behaviour", "Behaviour", "gus_rigtool.tools.behaviour_tool", "How controls behave: limits, in front of the "
     "mesh, stop at the body."),
    ("channels", "Channels", "gus_rigtool.tools.channels_tool", "Lock, hide, keyable - many controls at once."),
    ("spaces", "Spaces", "gus_rigtool.tools.space_tool", "A space switch on any control, no jump."),
    ("connect", "Connect", "gus_rigtool.tools.connect_tool", "Connect attributes: by name, in order, x factor."),
    ("nodes", "Nodes", "gus_rigtool.tools.nodes_tool", "Utility node networks: name, trace, Node Editor, save / load setups, rig map."),
    ("constrain", "Constraints", "gus_rigtool.tools.constraint_tool", "Make, swap, remove, check constraints."),
    ("rename", "Rename", "gus_rigtool.tools.rename_tool", "Rename many: numbers, search, sides, your naming."),
    ("organize", "Organize", "gus_rigtool.tools.organize_tool", "Tidy the Outliner: analyze, plan, organize, restore."),
    ("checker", "Checker", "gus_rigtool.tools.checker", "Finds common rig problems and fixes the safe ones."),
    ("settings", "Settings", "gus_rigtool.tools.settings_tab", "Every option of every tool, and your defaults."),
]


# the main window's categories: (key, label, tool keys)
CATEGORIES = [                                  # in the order you rig: Home, then the workflow, then the toolbox
    ("home", "Home", ["home"]),                 # 5.4.0: one home per job (where everything went: Home > Map)
    ("build", "Build", ["build", "face", "ribbon", "joints"]),
    ("skin", "Skin", ["skin", "fixes"]),
    ("controls", "Controls", ["makectrl", "shapes", "behaviour", "attrs", "channels", "spaces", "follow", "stick"]),
    ("links", "Connect", ["constrain", "connect", "nodes", "sdk"]),
    ("finish", "Check", ["checker", "organize"]),
    ("toolbox", "Toolbox", ["select", "groups", "mirror", "rename", "pivots", "settings"]),
]

MY_TOOLS = ["select", "groups", "shapes", "ribbon", "checker", "mirror", "constrain"]   # 5.4.0: your most used


STAGES = [
    ("guides", "Guides", "Add a template (Biped, Quadruped...) or modules, place the LEFT side, Mirror guides.",
     "build", "Start: template or add a module"),
    ("build", "Build", "Build the rig from the guides (rebuild any part later: Back to guides, adjust, Build picked).",
     "build", "Build"),
    ("skin", "Skin", "Bind the model to the rig's joints, paint / mirror the weights.", "skin", "Bind"),
    ("controls", "Controls", "Make it nice to animate: shapes and colours, follows, space switches, attributes, "
     "connections.", "shapes", "Shapes"),
    ("finish", "Check & publish", "Run the Checker, fix what it finds, then Publish a clean rig for animators.",
     "checker", "Check"),
]

# Which workflow step each tool belongs to (the 'where am I' line); the others are the toolbox: any time.
TOOL_STAGE = {"build": (1, 2), "face": 2, "ribbon": 2, "skin": 3, "fixes": 3, "shapes": 4, "makectrl": 4, "follow": 4, "stick": 4, "spaces": 4, "attrs": 4, "behaviour": 4, "channels": 4, "sdk": 4,
              "connect": 4, "constrain": 4, "checker": 5, "organize": 5}

# Simple view: these sections of each tool start folded, marked '(advanced)'. Full view: as you left them.
ADVANCED = {
    "build": ["Scan a part", "Keep it as it is", "Rebuild it with the builder", "Replace the old part", "Backup",
              "IK / FK switch", "Animator tools"],
    "skin": ["Copy skin", "Clean", "Save / load weights", "Vertex weights"],
    "shapes": ["Edit shapes"],
    "follow": ["Weights", "Follows in the scene"],
    "spaces": ["This control's switch"],
    "attrs": ["Order", "Copy to other controls"],
    "channels": ["Default set", "Copy / check"],
    "sdk": ["Copy (Copy mode)", "Flip"],
    "connect": ["Break / check"],
    "constrain": ["Swap target", "Check / remove"],
    "checker": ["Checks to run", "Batch"],
    "organize": ["Rules", "Extras"],
    "mirror": ["More options", "Side colours"],
    "select": ["Options"],
    "joints": ["Orientation", "IK spline"],
    "ribbon": ["Follicles"],
    "settings": ["Defaults", "Self-test", "Shelf shortcuts", "Side colours"],
}


def category_of(key):
    for cat, label, keys in CATEGORIES:
        if key in keys:
            return cat, label
    return None, None


# panels that open on their own but aren't tabs (Pop out buttons): key, label, module, subtitle, build function
PANELS = [
    ("build_rig", "Build rig", "gus_rigtool.tools.build_tab", "Build, rebuild, publish - with its own module list.",
     "build_rig_panel"),
]


def get(key):
    for item in PANELS:
        if item[0] == key:
            return item[:4]
    for item in TOOLS:
        if item[0] == key:
            return item
    raise KeyError(key)


def module(key):
    import importlib
    return importlib.import_module(get(key)[2])


def builder(key):
    """The function that fills a tool's page (build, or a panel's own one)."""
    for item in PANELS:
        if item[0] == key:
            return getattr(module(key), item[4])
    return module(key).build
