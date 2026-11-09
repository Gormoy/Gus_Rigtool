"""
Select: pick every joint, control, group... inside the selected groups.

    import gus_rigtool.main as gr; gr.show_tool("select")

Select one or more groups, then click a type. Filters narrow it down:
  Side  : All / L / R / Centre (from the name, else the position: +X = L)
  Name  : wildcards, comma separated, e.g. *finger*, *_jnt  (no wildcard = "contains")

4.1.0
  More types : follicles, skinned meshes, NURBS surfaces, anything with an attribute (e.g. follow, Blink).
  Filters    : depth (direct children / N levels), same colour as a picked control, Invert.
  Related    : the other-side twins, a mesh's skin joints, the meshes a joint deforms, the joints a control
               drives, a ribbon's controls, parents.
  Quick sets : save the selection under a name (a Maya set in the scene, gusQuickSets) and get it back in
               one click; Recent: the last selections made here.
"""

import fnmatch

import maya.cmds as cmds

from gus_rigtool.core import naming, sides, ui, utils

TOOL = "Select"
SETTINGS_KEY = "select"
CTRL_SUFFIXES = ("_ctrl", "_Ctrl", "_CTL")
SIDE_FILTERS = ["All", "Left", "Right", "Centre"]

DEFAULTS = {
    "add": False,
    "include_top": False,
    "side": 1,
    "name_filter": "",
    "depth": 0,
    "invert": False,
    "attr": "",
}
QS_PARENT = "gusQuickSets"
QS_PREFIX = "gusQS_"
_recent = []                    # [(label, [uuids])], newest first
RECENT_MAX = 10
_colour = {"node": None}

_P, N, _w, _guard = ui.tool_helpers("p_select_", TOOL)


# ---------------------------------------------------------------------------
# type tests
# ---------------------------------------------------------------------------

def _shapes(n):
    return cmds.listRelatives(n, shapes=True, fullPath=True, noIntermediate=True) or []


def _shape_types(n):
    return {cmds.nodeType(s) for s in _shapes(n)}


def _ctrl_named(n):
    return naming.split_namespace(n)[1].endswith(CTRL_SUFFIXES)


def is_joint(n):
    return cmds.nodeType(n) == "joint"


def is_control(n):
    return _ctrl_named(n) or "nurbsCurve" in _shape_types(n)


def is_curve(n):
    return "nurbsCurve" in _shape_types(n) and not _ctrl_named(n)


def is_group(n):
    return cmds.nodeType(n) == "transform" and not _shapes(n) and bool(cmds.listRelatives(n, children=True))


def is_mesh(n):
    return "mesh" in _shape_types(n)


def is_locator(n):
    return "locator" in _shape_types(n)


def is_constraint(n):
    return bool(cmds.objectType(n, isAType="constraint"))


def is_ik(n):
    return cmds.nodeType(n) == "ikHandle"


def is_cluster(n):
    return "clusterHandle" in _shape_types(n)


def is_any(n):
    return True


def is_follicle(n):
    return "follicle" in _shape_types(n)


def is_surface(n):
    return "nurbsSurface" in _shape_types(n)


def is_skinned(n):
    for sh in _shapes(n):
        if cmds.nodeType(sh) in ("mesh", "nurbsSurface", "nurbsCurve"):
            hist = cmds.listHistory(sh, pruneDagObjects=True, interestLevel=1) or []
            if any(cmds.nodeType(h) == "skinCluster" for h in hist):
                return True
    return False


def has_attr(name):
    def test(n):
        return bool(name) and cmds.attributeQuery(name, node=n, exists=True)
    return test


TYPES = [
    ("Joints", is_joint), ("Controls", is_control), ("Curves", is_curve), ("Groups", is_group),
    ("Meshes", is_mesh), ("Skinned", is_skinned), ("Locators", is_locator), ("Constraints", is_constraint),
    ("IK Handles", is_ik), ("Clusters", is_cluster), ("Follicles", is_follicle), ("Surfaces", is_surface),
    ("All", is_any),
]


# ---------------------------------------------------------------------------
# filters
# ---------------------------------------------------------------------------

def _name_ok(node, patterns):
    if not patterns:
        return True
    short = naming.split_namespace(node)[1].lower()
    for p in patterns:
        if fnmatch.fnmatchcase(short, p):
            return True
    return False


def _patterns(text):
    out = []
    for p in text.split(","):
        p = p.strip().lower()
        if not p:
            continue
        if not any(c in p for c in "*?["):
            p = "*%s*" % p
        out.append(p)
    return out


def _side_ok(node, wanted):
    if wanted == 1:
        return True
    return sides.side_of_node(node) == {2: "L", 3: "R", 4: "C"}[wanted]


def colour_of(node):
    """The display colour of a node (its first shape's override, else the transform's): ('rgb', (r, g, b)),
    ('index', n) or None."""
    for n in _shapes(node) + [node]:
        try:
            if not cmds.getAttr(n + ".overrideEnabled"):
                continue
            if cmds.getAttr(n + ".overrideRGBColors"):
                return ("rgb", tuple(round(v, 3) for v in cmds.getAttr(n + ".overrideColorRGB")[0]))
            return ("index", cmds.getAttr(n + ".overrideColor"))
        except (RuntimeError, ValueError):
            continue
    return None


def _depth_ok(node, root, depth):
    if not depth:
        return True
    return node.count("|") - root.count("|") <= depth


def find_inside(roots, test, patterns=(), side=1, depth=0, include_top=False, invert=False, colour=None):
    """Nodes inside the roots that pass test and the filters (invert: those that don't pass test)."""
    nodes = []
    for r in roots:
        if include_top:
            nodes.append((r, r))
        nodes += [(n, r) for n in cmds.listRelatives(r, allDescendents=True, fullPath=True, type="transform") or []]
    seen, out = set(), []
    for n, r in nodes:
        if n in seen:
            continue
        seen.add(n)
        if not (_name_ok(n, patterns) and _side_ok(n, side) and _depth_ok(n, r, depth)):
            continue
        if colour is not None and colour_of(n) != colour:
            continue
        if bool(test(n)) != bool(invert):
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# related
# ---------------------------------------------------------------------------

def twins(nodes):
    """The other-side twin of each node (by name), and the ones with none."""
    from gus_rigtool.core import joint_labels
    out, lonely = [], []
    for n in nodes:
        other = joint_labels.twin_name(naming.short_name(n))
        found = cmds.ls(other, long=True) if other else []
        if found and len(found) == 1:
            out.append(found[0])
        else:
            lonely.append(n)
    return out, lonely


def skin_joints_of(meshes):
    out = []
    for m in meshes:
        for h in cmds.listHistory(m, pruneDagObjects=True) or []:
            if cmds.nodeType(h) == "skinCluster":
                for j in cmds.skinCluster(h, query=True, influence=True) or []:
                    j = cmds.ls(j, long=True)[0]
                    if j not in out:
                        out.append(j)
    return out


def deformed_by(joints):
    out = []
    for j in joints:
        for skin in set(cmds.listConnections(j + ".worldMatrix", type="skinCluster") or []):
            for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
                t = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
                if t not in out:
                    out.append(t)
    return out


def driven_joints(ctrls):
    """Joints each control drives: by constraints, direct connections, or as children."""
    out = []
    for c in ctrls:
        for con in set(cmds.listConnections(c, type="constraint", source=False, destination=True) or []):
            for n in cmds.listRelatives(con, parent=True, fullPath=True) or []:
                if cmds.nodeType(n) == "joint" and n not in out:
                    out.append(n)
        for plug in ("translate", "rotate", "scale"):
            for n in cmds.listConnections("%s.%s" % (c, plug), source=False, destination=True) or []:
                n = cmds.ls(n, long=True)[0]
                if cmds.nodeType(n) == "joint" and n not in out:
                    out.append(n)
        for k in cmds.listRelatives(c, children=True, type="joint", fullPath=True) or []:
            if k not in out:
                out.append(k)
    return out


def ribbon_controls(nodes):
    from gus_rigtool.core import ribbon
    out = []
    builds = ribbon._find_builds()
    keys = []
    for n in nodes:
        cmds.select(n, replace=True)
        k = ribbon._selected_surface()
        if k and k in builds and k not in keys:
            keys.append(k)
    for k in keys:
        for o in ribbon._build_offsets(builds[k]).values():
            c = ribbon._control_under(o)
            if c and c not in out:
                out.append(c)
    return out


RELATED = [
    ("Other-side twins", "twins", "The L_ / R_ twin of each selected node (by name)."),
    ("Skin joints of mesh", "skin", "Every joint the selected meshes are skinned to."),
    ("Meshes it deforms", "deformed", "The meshes the selected joints deform."),
    ("Joints it drives", "driven", "Joints the selected controls drive (constraints, connections, children)."),
    ("Ribbon's controls", "ribbon", "Every control of the ribbon you picked (the ribbon or one of its controls)."),
    ("Parents", "parents", "The parent of each selected node."),
]


def related(kind, nodes):
    if kind == "twins":
        return twins(nodes)
    if kind == "skin":
        return skin_joints_of(nodes), []
    if kind == "deformed":
        return deformed_by([n for n in nodes if cmds.nodeType(n) == "joint"]), []
    if kind == "driven":
        return driven_joints(nodes), []
    if kind == "ribbon":
        return ribbon_controls(nodes), []
    if kind == "parents":
        out = []
        for n in nodes:
            p = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
            if p and p not in out:
                out.append(p)
        return out, []
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# quick sets, recent
# ---------------------------------------------------------------------------

def quick_sets():
    """{name: set node} saved in this scene."""
    out = {}
    for st in cmds.ls(QS_PREFIX + "*", type="objectSet") or []:
        out[st[len(QS_PREFIX):]] = st
    return out


def save_quick_set(name, nodes):
    import re
    name = re.sub(r"[^A-Za-z0-9_]", "_", (name or "").strip())
    if not name:
        raise RuntimeError("give the set a name.")
    if not nodes:
        raise RuntimeError("select what to save first.")
    node = QS_PREFIX + name
    if cmds.objExists(node):
        cmds.delete(node)
    st = cmds.sets(nodes, name=node)
    if not cmds.objExists(QS_PARENT):
        cmds.sets(name=QS_PARENT, empty=True)
    cmds.sets(st, add=QS_PARENT)
    return name


def load_quick_set(name, add=False):
    node = QS_PREFIX + name
    if not cmds.objExists(node):
        raise RuntimeError("no quick set '%s' in this scene." % name)
    members = cmds.sets(node, query=True) or []
    if not members:
        raise RuntimeError("quick set '%s' is empty (its nodes were deleted)." % name)
    cmds.select(members, add=add, replace=not add)
    return members


def delete_quick_set(name):
    node = QS_PREFIX + name
    if cmds.objExists(node):
        cmds.delete(node)


def remember_selection(label, nodes):
    ids = [utils.uuid(n) for n in nodes if cmds.objExists(n)]
    if not ids:
        return
    _recent.insert(0, (label, ids))
    del _recent[RECENT_MAX:]


def recent():
    return list(_recent)


def restore_recent(i, add=False):
    label, ids = _recent[i]
    nodes = [p for p in (utils.path(x) for x in ids) if p]
    if not nodes:
        raise RuntimeError("those nodes are gone.")
    cmds.select(nodes, add=add, replace=not add)
    return nodes


# ---------------------------------------------------------------------------
# action
# ---------------------------------------------------------------------------

def _roots():
    """Selected transforms, top-most only."""
    sel = sorted(set(cmds.ls(selection=True, long=True, type="transform") or []), key=len)
    roots = []
    for n in sel:
        if not any(n.startswith(r + "|") for r in roots):
            roots.append(n)
    return roots


def _ui():
    return {
        "add": cmds.checkBox(N("Add"), query=True, value=True),
        "include_top": cmds.checkBox(N("Top"), query=True, value=True),
        "side": cmds.optionMenu(N("Side"), query=True, select=True),
        "name_filter": cmds.textField(N("Filter"), query=True, text=True),
        "depth": cmds.intField(N("Depth"), query=True, value=True),
        "invert": cmds.checkBox(N("Invert"), query=True, value=True),
        "attr": cmds.textField(N("Attr"), query=True, text=True),
    }


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def _filters(o):
    return dict(patterns=_patterns(o["name_filter"]), side=o["side"], depth=int(o.get("depth") or 0),
                include_top=o["include_top"], invert=bool(o.get("invert")), colour=_colour_filter())


def _colour_filter():
    n = _colour.get("node")
    return colour_of(n) if n and cmds.objExists(n) else None


def select_type(label, test):
    o = _ui()
    _save()
    roots = _roots()
    if not roots:
        utils.warn(TOOL, "select a group first.")
        return
    if label == "With attr":
        if not o["attr"].strip():
            raise RuntimeError("type the attribute name next to 'With attr' (e.g. follow, Blink).")
        test = has_attr(o["attr"].strip())
        label = "nodes with .%s" % o["attr"].strip()
    found = find_inside(roots, test, **_filters(o))
    if not found:
        utils.warn(TOOL, "no %s found with these filters." % label.lower())
        return
    if o["add"]:
        cmds.select(found, add=True)
    else:
        cmds.select(found, replace=True)
    remember_selection(label, cmds.ls(selection=True, long=True) or found)
    _fill_recent()
    filters = []
    if o["side"] != 1:
        filters.append(SIDE_FILTERS[o["side"] - 1].lower())
    if o["name_filter"].strip():
        filters.append("name " + o["name_filter"].strip())
    if o.get("depth"):
        filters.append("depth %d" % o["depth"])
    if o.get("invert"):
        filters.append("inverted")
    if _colour_filter() is not None:
        filters.append("colour of %s" % naming.short_name(_colour["node"]))
    utils.info(TOOL, "%s %d %s%s." % ("added" if o["add"] else "selected", len(found), label.lower(),
                                      (" (" + ", ".join(filters) + ")") if filters else ""))


def select_related(kind, label):
    o = _ui()
    nodes = cmds.ls(selection=True, long=True) or []
    if not nodes:
        raise RuntimeError("select something first (see the button's tip).")
    found, lonely = related(kind, nodes)
    if not found:
        raise RuntimeError("found nothing (%s)." % label.lower())
    cmds.select(found, add=o["add"], replace=not o["add"])
    remember_selection(label, found)
    _fill_recent()
    msg = "%s: %d." % (label, len(found))
    if lonely:
        utils.warn(TOOL, msg + " No twin: " + ", ".join(naming.short_name(n) for n in lonely[:6]))
    else:
        utils.info(TOOL, msg)


def _pick_colour(*_):
    sel = utils.selected_transforms()
    if not sel:
        _colour["node"] = None
        cmds.text(N("ColourLbl"), edit=True, label="any colour")
        return
    if colour_of(sel[0]) is None:
        raise RuntimeError("%s has no colour override." % naming.short_name(sel[0]))
    _colour["node"] = sel[0]
    cmds.text(N("ColourLbl"), edit=True, label="like %s" % naming.short_name(sel[0]))
    _on_change()


def _clear_colour(*_):
    _colour["node"] = None
    cmds.text(N("ColourLbl"), edit=True, label="any colour")
    _on_change()


def _fill_sets():
    if not cmds.textScrollList(N("Sets"), exists=True):
        return
    names = sorted(quick_sets())
    cmds.textScrollList(N("Sets"), edit=True, removeAll=True, append=names or ["(no quick sets)"])


def _save_set(*_):
    nodes = cmds.ls(selection=True, long=True) or []
    name = cmds.textField(N("SetName"), query=True, text=True)
    got = save_quick_set(name, nodes)
    _fill_sets()
    utils.info(TOOL, "quick set '%s': %d node(s)." % (got, len(nodes)))


def _pick_set(*_):
    picked = cmds.textScrollList(N("Sets"), query=True, selectItem=True) or []
    if picked and picked[0] in quick_sets():
        o = _ui()
        members = load_quick_set(picked[0], o["add"])
        remember_selection("set " + picked[0], members)
        _fill_recent()
        cmds.textField(N("SetName"), edit=True, text=picked[0])


def _delete_set(*_):
    picked = cmds.textScrollList(N("Sets"), query=True, selectItem=True) or []
    if not picked or picked[0] not in quick_sets():
        raise RuntimeError("pick a quick set in the list first.")
    delete_quick_set(picked[0])
    _fill_sets()


def _fill_recent():
    if not cmds.optionMenu(N("Recent"), exists=True):
        return
    for item in cmds.optionMenu(N("Recent"), query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    if not _recent:
        cmds.menuItem(label="(nothing yet)", parent=N("Recent"))
    for label, ids in _recent:
        cmds.menuItem(label="%s (%d)" % (label, len(ids)), parent=N("Recent"))


def _restore(*_):
    if not _recent:
        raise RuntimeError("nothing selected with this tool yet.")
    i = cmds.optionMenu(N("Recent"), query=True, select=True) - 1
    restore_recent(max(0, i), _ui()["add"])


def _light():
    """Status light + live counts on the type buttons."""
    roots = _roots()
    if not roots:
        _set_counts(None)
        return "warn", "Select one or more groups to look inside."
    o = _ui()
    nodes = []
    for r in roots:
        if o["include_top"]:
            nodes.append(r)
        nodes += cmds.listRelatives(r, allDescendents=True, fullPath=True, type="transform") or []
    if ui.too_many(len(nodes)):
        _set_counts(None)
        return "ok", "%d group(s), %d objects inside (too many to count live)." % (len(roots), len(nodes))
    f = _filters(o)
    counts = {label: len(find_inside(roots, test, **f)) for label, test in TYPES}
    _set_counts(counts)
    return "ok", "%d group(s) selected. The numbers show what each button will select." % len(roots)


def _set_counts(counts):
    for label, _t in TYPES:
        name = N("Btn_" + label.replace(" ", ""))
        if cmds.button(name, exists=True):
            text = label if counts is None else "%s  (%d)" % (label, counts[label])
            cmds.button(name, edit=True, label=text, enable=counts is None or counts[label] > 0)


def _on_change(*_):
    _save()
    ui.refresh_light(N("Light"))


def clear_filters(*_):
    cmds.optionMenu(N("Side"), edit=True, select=1)
    cmds.textField(N("Filter"), edit=True, text="")
    cmds.intField(N("Depth"), edit=True, value=0)
    cmds.checkBox(N("Invert"), edit=True, value=False)
    _clear_colour()


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def build(prefix="p_select_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Options", step=1, help_text="Add to selection keeps what you had and adds to it, so you can "
               "combine types (e.g. joints, then controls).")
    cmds.checkBox(N("Add"), label="Add to selection", value=s["add"], changeCommand=_w(_on_change))
    cmds.checkBox(N("Top"), label="Include the selected group itself", value=s["include_top"],
                  changeCommand=_w(_on_change))
    ui.end_section()

    ui.section("Filters", step=2, help_text="Side: from the name (L_ / R_...), else the position (+X = Left). "
               "Name: wildcards, comma separated (*finger*, *_jnt); without a wildcard it means 'contains'.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(60, 120))
    cmds.text(label="Side", align="right")
    cmds.optionMenu(N("Side"), changeCommand=_w(_on_change),
                    annotation="From the name (L_ / R_...), else the position: +X = Left.")
    for label in SIDE_FILTERS:
        cmds.menuItem(label=label)
    cmds.setParent("..")
    cmds.optionMenu(N("Side"), edit=True, select=s["side"])
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(60, 200, 60), adjustableColumn=2)
    cmds.text(label="Name", align="right")
    cmds.textField(N("Filter"), text=s["name_filter"], changeCommand=_w(_on_change),
                   annotation="Wildcards, comma separated: *finger*, *_jnt. No wildcard = contains.")
    cmds.button(label="Clear all", command=_w(clear_filters))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 50, 40, 140), adjustableColumn=4)
    cmds.text(label="Depth", align="right")
    cmds.intField(N("Depth"), value=int(s["depth"]), minValue=0, maxValue=1000000, step=1, changeCommand=_w(_on_change),
                  annotation="0 = everything inside; 1 = direct children only; 2 = two levels...")
    cmds.text(label="")
    cmds.checkBox(N("Invert"), label="Invert (what doesn't match)", value=s["invert"],
                  changeCommand=_w(_on_change), annotation="Select what is NOT of the type you click.")
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(60, 130, 50, 50), adjustableColumn=2)
    cmds.text(label="Colour", align="right")
    cmds.text(N("ColourLbl"), label="any colour", align="left")
    cmds.button(label="<", command=_w(_guard(_pick_colour)),
                annotation="Only nodes with the same colour as the selected control.")
    cmds.button(label="Any", command=_w(_clear_colour))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Select inside the selected groups", step=3, help_text="Each button selects that type inside "
               "the selected groups, with the filters above. The numbers update with the selection.")
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(170, 30))
    for label, test in TYPES:
        cmds.button(N("Btn_" + label.replace(" ", "")), label=label,
                    command=_w(lambda *_, l=label, t=test: select_type(l, t)))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(170, 170),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.button(label="With attr:", command=_w(_guard(lambda *_: select_type("With attr", None))),
                annotation="Nodes that have the attribute typed on the right (e.g. follow, Blink, stick).")
    cmds.textField(N("Attr"), text=s["attr"], placeholderText="attribute name", changeCommand=_w(_on_change))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Related to the selection", step=4, help_text="From what is selected: its twins on the other "
               "side, a mesh's skin joints, the meshes a joint deforms, the joints a control drives, every control "
               "of a ribbon, the parents. 'Add to selection' applies here too.")
    cmds.gridLayout(numberOfColumns=2, cellWidthHeight=(170, 28))
    for label, kind, tip in RELATED:
        cmds.button(label=label, annotation=tip,
                    command=_w(_guard(lambda *_, k=kind, l=label: select_related(k, l))))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Quick sets and recent", step=5, help_text="Save the selection under a name (kept in the scene, "
               "in the gusQuickSets set) and click it to select it again. Recent: the last selections made with "
               "this tool.")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(230, 110),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.textField(N("SetName"), placeholderText="name, e.g. lips")
    cmds.button(label="Save selection", command=_w(_guard(_save_set)))
    cmds.setParent("..")
    cmds.textScrollList(N("Sets"), height=80, allowMultiSelection=False, selectCommand=_w(_guard(_pick_set)))
    cmds.button(label="Delete the picked set", command=_w(_guard(_delete_set)))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(230, 110),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.optionMenu(N("Recent"))
    cmds.button(label="Select again", command=_w(_guard(_restore)))
    cmds.setParent("..")
    ui.end_section()
    _fill_sets()
    _fill_recent()
    ui.refresh_light(N("Light"))            # the buttons exist now: fill in the counts


def show():
    ui.open_panel("select")


SCHEMA = [
    ("add", "Add to selection", "bool", None),
    ("include_top", "Include the selected group itself", "bool", None),
    ("side", "Side filter", "choice", SIDE_FILTERS),
    ("name_filter", "Name filter", "text", None),
    ("depth", "Depth (0 = all)", "int", None),
    ("invert", "Invert", "bool", None),
]
