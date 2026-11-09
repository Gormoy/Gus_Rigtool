"""
Build tab, step 2: the settings form of the module(s) picked in the list.

Every field is made by one small widget function that returns a reader; the form is
{settings path: reader}, so reading it back is one loop. Apply saves the settings and updates
the guides - it never builds (Build picked does).
"""

import maya.cmds as cmds

from gus_rigtool.builder import guides, modules
from gus_rigtool.core import ui, utils

AXES = ["X", "-X", "Y", "-Y", "Z", "-Z"]
_form = {}          # prefix -> {settings path: reader()}
_shown = {}         # prefix -> the module groups the form was made for


def _tab():
    from gus_rigtool.tools import build_tab
    return build_tab


def _N(name):
    return _tab().N(name)


_into = {"layout": None}     # the group (frame) fields go into while the form is made


def _parent():
    return _into["layout"] or _N("Form")


def _group(label, collapse=False, help_text=""):
    """A folding group of fields (a frame straight in the form: never inside another frame)."""
    _into["layout"] = None
    frame = cmds.frameLayout(label=label, collapsable=True, collapse=collapse, marginWidth=4, marginHeight=3,
                             parent=_N("Form"), annotation=help_text)
    _into["layout"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=3, parent=frame)
    return frame


def _end_group():
    _into["layout"] = None


# ---------------------------------------------------------------------------
# widgets: each makes its controls and returns a function that reads the value
# (reader.control is the main control, e.g. for scripts and tests)
# ---------------------------------------------------------------------------

def _reader(fn, control):
    fn.control = control
    return fn


def _cc():
    """changeCommand for every field: greys out what doesn't apply, the status light says when
    something isn't applied."""
    tab = _tab()

    def changed(*_):
        update_enables()
        ui.refresh_light(tab.N("Light"))
    return tab._w(changed)


_needs = {}          # prefix -> [(field path, depends on path, test)]


def _ok(test, value):
    if test == ">0":
        return bool(value) and int(value) > 0
    if isinstance(test, (list, tuple)):
        return value in test
    return bool(value) == bool(test)


def update_enables():
    """Fields that don't apply with the current choices are greyed out (never hidden)."""
    tab = _tab()
    form = _form.get(tab._P["p"], {})
    for path, dep, test in _needs.get(tab._P["p"], []):
        if path not in form or dep not in form:
            continue
        try:
            on = _ok(test, form[dep]())
            cmds.control(form[path].control, edit=True, enable=on)
        except (RuntimeError, ValueError, TypeError, AttributeError):
            pass


def _row(label):
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(150, 190), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2)], parent=_parent())
    cmds.text(label=label)


def _text(label, value, annotation=""):
    _row(label)
    c = cmds.textField(text=str(value), annotation=annotation, changeCommand=_cc())
    cmds.setParent("..")
    return _reader(lambda: cmds.textField(c, query=True, text=True).strip(), c)


def _spaces(label, value):
    """Extra spaces 'label = node, ...' with a button that adds the selected node under a name you type."""
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(150, 150, 40), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)], parent=_parent())
    cmds.text(label=label)
    c = cmds.textField(text=str(value or ""), changeCommand=_cc(),
                       annotation="e.g. chest = Spine_chest_ctrl, head = Head_ctrl. Any node in the scene.")
    tab = _tab()

    def add(*_):
        sel = cmds.ls(selection=True) or []
        if not sel:
            raise RuntimeError("select the node the control should follow, then +.")
        if cmds.promptDialog(title="New space", message="Name of this space (e.g. chest):",
                             button=["Add", "Cancel"], defaultButton="Add", cancelButton="Cancel",
                             dismissString="Cancel") != "Add":
            return
        name = (cmds.promptDialog(query=True, text=True) or "").strip().replace(",", "").replace("=", "")
        if not name:
            return
        items = [x.strip() for x in cmds.textField(c, query=True, text=True).split(",") if x.strip()]
        items = [x for x in items if x.split("=")[0].strip() != name] + ["%s = %s" % (name, sel[0])]
        cmds.textField(c, edit=True, text=", ".join(items))
        update_enables()
        ui.refresh_light(tab.N("Light"))
    cmds.button(label="+ sel", command=tab._w(tab._guard(add)),
                annotation="Add the selected node as a space (you name it).")
    cmds.setParent("..")
    return _reader(lambda: cmds.textField(c, query=True, text=True).strip(), c)


def _names_list(label, value):
    _row(label)
    c = cmds.textField(text=", ".join(str(v) for v in value),
                       annotation="Comma separated, top to bottom. Add or remove names to change the number "
                                  "of joints.")
    cmds.setParent("..")

    def read():
        out = [v.strip() for v in cmds.textField(c, query=True, text=True).split(",") if v.strip()]
        if not out:
            raise ValueError("'%s' needs at least one name." % label)
        return out
    return _reader(read, c)


def _int(label, value, minimum=1, top=40):
    """A whole number picked from a list (nothing to type, so it can't be left unsaved)."""
    value = int(value or 0)
    top = max(top, value)
    _row(label)
    menu = cmds.optionMenu(changeCommand=_cc())
    for i in range(minimum, top + 1):
        cmds.menuItem(label=str(i))
    cmds.optionMenu(menu, edit=True, select=min(top, max(minimum, value)) - minimum + 1)
    cmds.setParent("..")
    return _reader(lambda: cmds.optionMenu(menu, query=True, select=True) - 1 + minimum, menu)


def _count(label, value, top=12):
    """A small number picked from a list (0 to top): taken the moment it is picked, nothing to type."""
    _row(label)
    menu = cmds.optionMenu(changeCommand=_cc())
    for i in range(top + 1):
        cmds.menuItem(label=str(i))
    cmds.optionMenu(menu, edit=True, select=min(top, max(0, int(value or 0))) + 1)
    cmds.setParent("..")
    return _reader(lambda: cmds.optionMenu(menu, query=True, select=True) - 1, menu)


def _float(label, value, minimum=0.001, precision=2):
    _row(label)
    c = cmds.floatField(value=float(value), precision=precision, minValue=minimum, maxValue=1000000.0, step=0.01, changeCommand=_cc())
    cmds.setParent("..")
    return _reader(lambda: cmds.floatField(c, query=True, value=True), c)


def _bool(label, value):
    c = cmds.checkBox(label=label, value=bool(value), parent=_parent(), changeCommand=_cc())
    return _reader(lambda: cmds.checkBox(c, query=True, value=True), c)


def _choice(label, value, choices, annotation=""):
    _row(label)
    menu = cmds.optionMenu(annotation=annotation, changeCommand=_cc())
    for c in choices:
        cmds.menuItem(label=c)
    cmds.optionMenu(menu, edit=True, select=choices.index(value) + 1 if value in choices else 1)
    cmds.setParent("..")
    return _reader(lambda: choices[cmds.optionMenu(menu, query=True, select=True) - 1], menu)


def _vec(label, value):
    c = cmds.floatFieldGrp(label=label, numberOfFields=3, value1=value[0], value2=value[1], value3=value[2],
                           columnWidth4=(150, 55, 55, 55), parent=_parent())
    return _reader(lambda: cmds.floatFieldGrp(c, query=True, value=True)[:3], c)


ANGLES = [0, 45, 90, 135, 180, -135, -90, -45]


def _control(kind, entry, shapes):
    """Shape, size, and how the shape is turned (X / Y / Z, in the control's axes)."""
    shape, size = entry[0], entry[1]
    rot = list(entry[2]) if len(entry) > 2 and entry[2] else [0, 0, 0]
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(100, 150, 70), parent=_parent(),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label=kind)
    menu = cmds.optionMenu(changeCommand=_cc())
    for c in shapes:
        cmds.menuItem(label=c)
    cmds.optionMenu(menu, edit=True, select=shapes.index(shape) + 1 if shape in shapes else 1)
    f = cmds.floatField(value=float(size), precision=3, minValue=0.001, maxValue=1000000.0, step=0.01, changeCommand=_cc())
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(100, 70, 70, 70), parent=_parent(),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.text(label="turn X Y Z", font="smallPlainLabelFont")
    turns = []
    for v in rot:
        t = cmds.optionMenu(changeCommand=_cc(), annotation="Turn the shape (degrees) around the control's axis.")
        for a in ANGLES:
            cmds.menuItem(label=str(a))
        v = int(round(float(v)))
        cmds.optionMenu(t, edit=True, select=ANGLES.index(v) + 1 if v in ANGLES else 1)
        turns.append(t)
    cmds.setParent("..")

    def read():
        out = [shapes[cmds.optionMenu(menu, query=True, select=True) - 1], cmds.floatField(f, query=True, value=True)]
        r = [ANGLES[cmds.optionMenu(t, query=True, select=True) - 1] for t in turns]
        return out + [r] if any(r) else out
    return _reader(read, menu)


def _joints(label, value, group, mod, s, key):
    """Joint numbers ('all', 'auto', '1, 4, 8', '1-5') + Spread N + From selected guides."""
    from gus_rigtool.builder import chain
    tab = _tab()
    cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, parent=_parent(), columnWidth4=(150, 110, 55, 80),
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2), (4, "both", 2)])
    cmds.text(label=label)
    field = cmds.textField(text=str(value), annotation="'all', 'auto', or joint numbers: 1, 4, 8 or 1-5.")

    def do_spread(*_):
        res = cmds.promptDialog(title="Spread controls", message="How many controls?", text="3",
                                button=["OK", "Cancel"], defaultButton="OK", cancelButton="Cancel",
                                dismissString="Cancel")
        if res != "OK":
            return
        try:
            n = int(cmds.promptDialog(query=True, text=True))
        except (TypeError, ValueError):
            raise ValueError("type a whole number.")
        span = int(s["names"]["count"]) if key == "fk_joints" else mod.total(s)   # FK: not the end joint
        cmds.textField(field, edit=True, text=chain.spread(n, span))

    def from_guides(*_):
        nums = []
        for n in cmds.ls(selection=True, long=True) or []:
            role = guides._get(n, "gusRole") if n.startswith(group + "|") else ""
            if role.startswith("j") and role[1:].isdigit():
                nums.append(int(role[1:]))
        if not nums:
            raise RuntimeError("select some of this chain's guides in the viewport first.")
        cmds.textField(field, edit=True, text=chain.format_joints(sorted(set(nums))))

    cmds.button(label="Spread", command=tab._w(tab._guard(do_spread)), annotation="N controls spread evenly.")
    cmds.button(label="From guides", command=tab._w(tab._guard(from_guides)),
                annotation="The joint numbers of the guides selected in the viewport.")
    cmds.setParent("..")
    return _reader(lambda: cmds.textField(field, query=True, text=True).strip(), field)


def _option(label, kind, value, choices, ctx=None):
    """An option field of any kind ('joints' is a plain text field when ctx is None: several modules)."""
    if kind == "bool":
        return _bool(label, value)
    if kind == "int":
        return _int(label, value)
    if kind == "count":                                 # a small number that can be 0 (e.g. number of toes)
        return _count(label, value)
    if kind == "choice":
        return _choice(label, value, choices)
    if kind == "joints" and ctx:
        return _joints(label, value, *ctx)
    if kind == "spaces":
        return _spaces(label, value)
    return _text(label, value)


def _heading(text):
    cmds.text(label=text, align="left", parent=_parent(), font="smallBoldLabelFont")


# ---------------------------------------------------------------------------
# the form
# ---------------------------------------------------------------------------

def clear():
    col = _parent()
    if cmds.columnLayout(col, exists=True):
        for kid in cmds.columnLayout(col, query=True, childArray=True) or []:
            try:
                cmds.deleteUI(kid)
            except RuntimeError:
                pass
    _form[_tab()._P["p"]] = {}
    _shown[_tab()._P["p"]] = []
    _needs[_tab()._P["p"]] = []
    _into["layout"] = None


def fill():
    if not cmds.columnLayout(_parent(), exists=True):
        return
    clear()
    tab = _tab()
    from gus_rigtool.builder import existing
    every = tab._picked_all()
    if len(every) == 1 and existing.is_adopted(every[0]):
        _fill_adopted(every[0])
        return
    picked = tab._picked()
    if not picked:
        cmds.text(label="Pick a module in the list above to see its settings here.", parent=_parent(), align="left")
        return
    _shown[tab._P["p"]] = list(picked)
    if len(picked) > 1:
        _fill_common(picked)
        return
    g = picked[0]
    form = _form[tab._P["p"]]
    info = guides.read(g)
    mod = modules.MODULES[info["type"]]
    s = mod.complete(dict(info["settings"]))
    built = "built" if (cmds.objExists(g) and _built(info)) else "at its guides"
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, parent=_N("Form"),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.text(label="%s  -  %s %s  (%s)" % (mod.LABEL, info["side"], info["name"], built), font="boldLabelFont",
              align="left")
    desc = getattr(mod, "DESCRIPTION", "") or mod.LABEL
    cmds.button(label="?", width=24, height=20, annotation=desc,
                command=lambda *_: cmds.confirmDialog(title=mod.LABEL, message=desc, button=["OK"]))
    cmds.setParent("..")
    cmds.text(label="Change, then Apply (updates the guides). Build picked puts it on the rig.", align="left",
              font="smallPlainLabelFont", parent=_N("Form"))
    _apply_row(tab)

    # options, in groups
    labels = dict(mod.OPTION_LABELS)
    groups = list(getattr(mod, "OPTION_GROUPS", []))
    grouped = set(k for _g, keys in groups for k in keys)
    rest = [k for k in labels if k not in grouped]
    if rest:
        groups.append(("Options", rest))
    for title, keys in groups:
        keys = [k for k in keys if k in labels]
        if not keys:
            continue
        _group(title)
        for key in keys:
            label, kind, choices = labels[key]
            form["options." + key] = _option(label, kind, s["options"].get(key), choices, (g, mod, s, key))
        if hasattr(mod, "total") and "fk_joints" in keys:
            cmds.text(label="Joints are numbered 1 to %d (top to tip). 'all' = every joint, 'auto' = first, "
                            "middle, last. Ranges: 1-4, 7." % mod.total(s),
                      align="left", wordWrap=True, height=30, font="smallPlainLabelFont", parent=_parent())
        _end_group()

    _group("Names", collapse=True, help_text="Names of the joints and controls. Comma separated lists: add or "
           "remove names to change how many joints.")
    for key, value in s["names"].items():
        label = key.replace("_", " ")
        if isinstance(value, list):
            form["names." + key] = _names_list(label, value)
        elif isinstance(value, int):
            form["names." + key] = _int(label, value)
        else:
            form["names." + key] = _text(label, value)
    form["attach"] = _text("attach to", s.get("attach", ""),
                           "module:part it hangs from, e.g. spine:shoulder. Empty = under the root.")
    _end_group()

    _group("Joint orientation", collapse=True)
    o = s["orient"]
    for key, label, choices in (("aim", "aim axis (down the chain)", AXES), ("up", "up axis", AXES),
                                ("up_mode", "up from", ["plane", "world"])):
        form["orient." + key] = _choice(label, o[key], choices,
                                        "plane: the chain's bend (limbs). world: the direction below.")
    form["orient.world_up"] = _vec("world up", o["world_up"])
    form["orient.behavior_right"] = _bool("Right side: behavior (same rotate values = mirrored motion)",
                                          o.get("behavior_right", True))
    _end_group()

    _group("Controls (shape, size x height)", collapse=True)
    from gus_rigtool.core import ribbon
    shapes = [x for x in ribbon.SHAPES() if x != ribbon.JOINT_ONLY]
    for kind, entry in s["controls"].items():
        form["controls." + kind] = _control(kind, entry, shapes)
    form["guide_size"] = _float("guide size", s.get("guide_size", 1.0), 0.05)
    _end_group()

    _apply_row(tab)
    cmds.button(label="Use these as my defaults for new %s modules" % mod.LABEL.lower(), parent=_N("Form"),
                command=tab._w(tab._guard(save_type_defaults)))
    _needs[tab._P["p"]] = [(path, dep, test) for path, (dep, test) in getattr(mod, "OPTION_NEEDS", {}).items()]
    update_enables()


def _apply_row(tab):
    """Apply + Reset (at the top and the bottom of the settings, so they're always near)."""
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(230, 110), adjustableColumn=1, parent=_N("Form"),
                   columnAttach=[(1, "both", 2), (2, "both", 2)])
    cmds.button(label="Apply (update guides)", height=30, command=tab._w(tab._guard(apply)),
                backgroundColor=ui.MAIN_BG,
                annotation="Save these settings and re-make the guides (new names / joint counts); guides that "
                           "still exist keep their place. Nothing is built: Build picked does that.")
    cmds.button(label="Reset", command=tab._w(tab._guard(reset)), annotation="Back to the default settings.")
    cmds.setParent("..")


def _fill_adopted(group):
    """An adopted part: what the tool knows about it, and Forget."""
    from gus_rigtool.builder import existing
    tab = _tab()
    info = existing.read_adopted(group)
    s = info["settings"]
    cmds.text(label="Adopted part  -  %s %s" % (info["side"], info["name"]), font="boldLabelFont", align="left",
              parent=_N("Form"))
    cmds.text(label="Kept as you made it: the tool can't rebuild it, but IK/FK match, Publish, mirror pose and "
                    "Gus Animtool work on it. Builder modules can hang from it (attach '%s:<joint>')." % info["name"],
              align="left", wordWrap=True, parent=_N("Form"))
    cmds.scrollField(editable=False, height=110, wordWrap=True, parent=_N("Form"),
                     text="Controls (%d): %s\n\nIK/FK limbs: %s\n\nSpaces it offers: %s" % (
                         len(s.get("controls", [])), ", ".join(s.get("controls", [])),
                         ", ".join(s.get("limbs", [])) or "none",
                         ", ".join("%s = %s" % kv for kv in sorted((s.get("spaces") or {}).items())) or "none"))
    cmds.button(label="Forget this adopted part", parent=_N("Form"),
                command=tab._w(tab._guard(lambda *_: (existing.forget_adopted(group), tab.refresh_list()))),
                annotation="The tool forgets it; nothing in the rig changes.")


def _built(info):
    from gus_rigtool.builder import build as bld
    return bld.is_module_built(info)


def _set(settings, path, value):
    parts = path.split(".")
    if len(parts) == 1:
        settings[parts[0]] = value
    else:
        settings.setdefault(parts[0], {})[parts[1]] = value


def read():
    """(group, info, module, settings) from the form, checked."""
    tab = _tab()
    g = tab._current()
    if not g:
        raise RuntimeError("pick a module in the list (Modules in the scene).")
    info = guides.read(g)
    mod = modules.MODULES[info["type"]]
    s = mod.complete(dict(info["settings"]))
    for path, reader in _form.get(tab._P["p"], {}).items():
        _set(s, path, reader())
    o = s["orient"]
    if o["aim"].lstrip("-") == o["up"].lstrip("-"):
        raise ValueError("the aim axis and the up axis must be different.")
    s = mod.complete(s)                                 # name lists follow their counts
    if hasattr(mod, "fk_indices"):                    # chain: check the joint numbers now
        mod.fk_indices(s)
        if mod.has_ik(s):
            mod.ik_indices(s)
    return g, info, mod, s


def _get(settings, path):
    parts = path.split(".")
    v = settings
    for p in parts:
        v = v.get(p) if isinstance(v, dict) else None
    return v


def _same(a, b):
    try:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            return abs(float(a) - float(b)) < 1e-6
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    except (TypeError, ValueError):
        pass
    return a == b


def _label_of(path):
    return path.split(".")[-1].replace("_", " ")


def pending():
    """[(module id, field, saved value, value in the form)] not applied yet ([] if none / no form)."""
    tab = _tab()
    form = _form.get(tab._P["p"], {})
    if not form:
        return []
    try:
        picked = tab._picked()
    except RuntimeError:
        return []
    if sorted(picked) != sorted(_shown.get(tab._P["p"], [])):
        return []                                        # the form shows other modules: nothing to compare
    out = []
    for g in picked:
        info = guides.read(g)
        mod = modules.MODULES.get(info["type"])
        if not mod:
            continue
        saved = mod.complete(dict(info["settings"]))
        for path, reader in form.items():
            if len(picked) > 1 and not path.startswith("options."):
                continue
            try:
                new = reader()
            except (RuntimeError, ValueError):
                continue
            old = _get(saved, path)
            if old is not None and not _same(old, new):
                out.append((info["id"], _label_of(path), old, new))
    return out


def describe(changes, limit=6):
    lines = ["%s: %s  %s -> %s" % (mid, field, old, new) for mid, field, old, new in changes[:limit]]
    if len(changes) > limit:
        lines.append("... and %d more" % (len(changes) - limit))
    return "\n".join(lines)


def _saved_message(ids, changes=None):
    if changes is not None:
        seen = []
        for _m, field, old, new in changes:
            text = "%s %s -> %s" % (field, old, new)
            if text not in seen:
                seen.append(text)
        what = "; ".join(seen[:4]) + (" ..." if len(seen) > 4 else "") if seen else "nothing changed"
        utils.info("Build", "%s: %s. Build picked to see it on the rig." % (", ".join(ids), what))
        return
    from gus_rigtool.builder import build as bld
    if bld.is_built():
        utils.info("Build", "settings saved, guides updated (%s). Build picked to see them on the rig."
                   % ", ".join(ids))
    else:
        utils.info("Build", "settings saved, guides updated (%s)." % ", ".join(ids))


def apply(*_):
    """Save the settings and update the guides. Never builds."""
    changes = pending()
    g, info, mod, s = read()
    tab = _tab()
    with utils.undo_chunk("gusrigModuleSettings"):
        guides.save_settings(g, s)
        new = guides.update(g, mod, s, tab._height())
    tab.refresh_list(new)
    _saved_message([info["id"]], changes)


def reset(*_):
    tab = _tab()
    g = tab._current()
    if not g:
        return
    info = guides.read(g)
    mod = modules.MODULES[info["type"]]
    st = mod.default_settings(info["side"])
    if "name" in st["names"] and not st["names"]["name"]:
        st["names"]["name"] = info["name"]                 # a chain keeps its name
    with utils.undo_chunk("gusrigModuleReset"):
        new = guides.update(g, mod, st, tab._height())
    tab.refresh_list(new)


def save_type_defaults(*_):
    _g, info, _mod, s = read()
    utils.save_setting("build_module_" + info["type"], s)
    utils.info("Build", "new %s modules will start with these settings." % info["type"])


# ---------------------------------------------------------------------------
# several modules picked: their common options
# ---------------------------------------------------------------------------

def _common_options(infos):
    """Options every picked module has (same label and kind): {key: (label, kind, choices)}."""
    common = None
    for info in infos:
        labels = dict(modules.MODULES[info["type"]].OPTION_LABELS)
        common = labels if common is None else {k: v for k, v in common.items() if labels.get(k) == v}
    return common or {}


def _fill_common(picked):
    tab = _tab()
    infos = [guides.read(g) for g in picked]
    form = _form[tab._P["p"]]
    cmds.text(label="%d modules picked: %s" % (len(infos), ", ".join(i["id"] for i in infos)),
              font="boldLabelFont", align="left", parent=_parent(), wordWrap=True)
    common = _common_options(infos)
    if not common:
        cmds.text(label="These modules have no options in common. Pick modules of the same kind "
                        "(e.g. arms and legs).", parent=_parent(), align="left", wordWrap=True)
        return
    _heading("Options they all have (shown: the first module's values)")
    first = modules.MODULES[infos[0]["type"]].complete(dict(infos[0]["settings"]))["options"]
    for key, (label, kind, choices) in common.items():
        form["options." + key] = _option(label, kind, first.get(key), choices)
    cmds.button(label="Apply to all %d modules" % len(infos), parent=_parent(), backgroundColor=ui.MAIN_BG,
                command=tab._w(tab._guard(apply_common)),
                annotation="Only these options change; each module keeps its own names, orientation and controls. "
                           "Nothing is built: Build picked does that.")


def apply_common(*_):
    tab = _tab()
    changes = pending()
    picked = tab._picked()
    values = {path.split(".", 1)[1]: reader() for path, reader in _form.get(tab._P["p"], {}).items()
              if path.startswith("options.")}
    ids, new_groups = [], []
    with utils.undo_chunk("gusrigCommonOptions"):
        for g in picked:
            info = guides.read(g)
            mod = modules.MODULES[info["type"]]
            st = mod.complete(dict(info["settings"]))
            st["options"].update(values)
            guides.save_settings(g, st)
            new_groups.append(guides.update(g, mod, st, tab._height()))
            ids.append(info["id"])
    tab.refresh_list(new_groups)
    _saved_message(ids, changes)
