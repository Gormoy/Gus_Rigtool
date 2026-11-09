"""
SDK: mirror or copy set driven keys.

    import gus_rigtool.main as gr; gr.show_tool("sdk")

Select the driver (e.g. L_hand_ctrl). Its driven keys are listed.
  Mirror : the other-side driver drives the other-side driven nodes (found by twin link,
           name, then position - like the Mirror tab).
  Copy   : another driver attribute (indexCurl -> middleCurl) drives other nodes, found by a
           search / replace on the driven names (index -> middle), with a value multiplier.
Curves are duplicated, so keys, tangents, weights and infinity are identical. Flipped
channels get their values negated - 5.6.18: Auto works that out per driven node from how its parent is turned
against its twin's (a ribbon mirrored with Z flipped needs tz, rx, ry; an orientation mirror tx, ry, rz; a
behaviour mirror none), the ticked channels only where it can't. Several drivers on one channel are combined with a
blendWeighted node, like Maya does. "Replace existing" swaps an older copy instead of
stacking a new one.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, sides, ui, utils

TOOL = "SDK"
SETTINGS_KEY = "sdk"
UCURVES = ("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT")
CHANNELS = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ",
            "scaleX", "scaleY", "scaleZ"]
SHORT = {"translateX": "tx", "translateY": "ty", "translateZ": "tz", "rotateX": "rx", "rotateY": "ry",
         "rotateZ": "rz", "scaleX": "sx", "scaleY": "sy", "scaleZ": "sz"}
PRESETS = {
    "Behavior": [],
    "Orientation": ["translateX", "rotateY", "rotateZ"],
}
SUFFIX_PRESETS = ("_sdk", "_driven", "_auto")
MODES = ["Mirror", "Copy"]

DEFAULTS = {
    "mode": 1,
    "suffix": "",
    "flip": [],
    "flip_other": False,
    "auto": True,
    "replace": True,
    "new_attr": "",
    "new_driver": "",
    "search": "",
    "replace_with": "",
    "multiplier": 1.0,
}

_P, N, _w, _guard = ui.tool_helpers("p_sdk_", TOOL)
_state = {}                 # prefix -> {"rows": [...], "attrs": [...]}
_notes = {}                 # other-side node -> why it was picked by name (its twin link was wrong)


# ===========================================================================
# finding driven keys
# ===========================================================================

def _node(plug):
    return plug.split(".", 1)[0]


def _attr(plug):
    return plug.split(".", 1)[1]


def _final_plugs(plug):
    """Where an output ends up: through unit conversions and blendWeighted nodes.
    Returns [(final plug, blendWeighted or None)]."""
    out = []
    for dst in cmds.listConnections(plug, source=False, destination=True, plugs=True,
                                    skipConversionNodes=True) or []:
        if cmds.nodeType(_node(dst)) == "blendWeighted":
            bw = _node(dst)
            for final in cmds.listConnections(bw + ".output", source=False, destination=True, plugs=True,
                                              skipConversionNodes=True) or []:
                out.append((final, bw))
        else:
            out.append((dst, None))
    return out


def find_sdks(driver, attr=None):
    """
    Driven keys of a driver: [{'attr', 'curve', 'plug', 'blend'}]
      attr  : driver attribute (e.g. indexCurl)
      curve : the animCurveU* node
      plug  : the final driven plug (node.attribute)
      blend : the blendWeighted node in between, or None
    """
    pairs = cmds.listConnections(driver, source=False, destination=True, plugs=True, connections=True,
                                 skipConversionNodes=True) or []
    out = []
    for src, dst in zip(pairs[0::2], pairs[1::2]):
        curve = _node(dst)
        if cmds.nodeType(curve) not in UCURVES:
            continue
        a = _attr(src)
        if attr and a != attr:
            continue
        for final, blend in _final_plugs(curve + ".output"):
            out.append({"attr": a, "curve": curve, "plug": final, "blend": blend})
    return out


def driver_attrs(driver):
    return sorted({r["attr"] for r in find_sdks(driver)})


# ===========================================================================
# planning
# ===========================================================================

def _twin(node):
    pl = sides.plan(cmds.ls(node, long=True)[0], sides.default_pairs(), 0, (0.0, 0.0, 0.0),
                    rename_source=False)
    if not pl:
        return None, "centre"
    if not pl["existing"]:
        return None, "no '%s'" % pl["target_name"]
    if pl.get("note"):
        _notes[pl["existing"]] = pl["note"]
    return pl["existing"], None


def _frame(node):
    """The world axes a node's channels move in: its parent's (rows x, y, z), unit length."""
    import math
    p = cmds.listRelatives(node, parent=True, fullPath=True)
    m = cmds.xform(p[0], query=True, worldSpace=True, matrix=True) if p else \
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    out = []
    for i in range(3):
        v = m[i * 4:i * 4 + 3]
        n = math.sqrt(sum(c * c for c in v)) or 1.0
        out.append([c / n for c in v])
    return out


def mirror_flips(node, twin, tol=0.05):
    """5.6.18: how twin's parent is turned against node's, mirrored across X - per axis +1 (that axis the
    mirror of node's), -1 (the opposite way) or None (not a clean mirror: can't tell)."""
    a, b = _frame(node), _frame(twin)
    out = []
    for u, w in zip(a, b):
        m = [-u[0], u[1], u[2]]
        if sum((x - y) ** 2 for x, y in zip(w, m)) ** 0.5 < tol:
            out.append(1)
        elif sum((x + y) ** 2 for x, y in zip(w, m)) ** 0.5 < tol:
            out.append(-1)
        else:
            out.append(None)
    return out


def channel_sign(flips, attr):
    """The sign a mirrored channel's value takes: translate follows its axis; rotate about an axis takes the
    product of the other two (Z flipped: rx, ry flip, rz keeps; behaviour - all three flipped: rotations
    keep); scale and anything else keep theirs. None: can't tell."""
    if attr[:-1] not in ("translate", "rotate") or attr[-1] not in "XYZ":
        return 1
    i = "XYZ".index(attr[-1])
    if attr.startswith("translate"):
        return flips[i]
    a, b = [flips[k] for k in range(3) if k != i]
    return None if None in (a, b) else a * b


def _copy_name(node, search, replace):
    ns, short = naming.split_namespace(node)
    if not search:
        return None
    return ns + short.replace(search, replace) if search in short else None


def plan(o, driver):
    """Rows: {'src', 'driver', 'driver_attr', 'plug', 'flip', 'mult', 'skip'}."""
    sel_attr = None if o.get("attr_filter") in (None, "", "All") else o["attr_filter"]
    rows = []
    records = find_sdks(driver, sel_attr)
    suffix = o["suffix"].strip()
    for rec in records:
        driven = _node(rec["plug"])
        if suffix and not naming.split_namespace(driven)[1].endswith(suffix):
            continue
        row = {"src": rec, "skip": None, "mult": 1.0}
        attr = _attr(rec["plug"])
        if o["mode"] == 1:                                         # mirror
            tdriver, why = _twin(driver)
            tdriven, why2 = _twin(driven)
            row["driver"], row["driver_attr"] = tdriver, rec["attr"]
            row["skip"] = ("driver: " + why) if not tdriver else (("driven: " + why2) if not tdriven else None)
            row["plug"] = "%s.%s" % (tdriven, attr) if tdriven else None
            row["notes"] = [_notes[x] for x in (tdriver, tdriven) if x in _notes]
        else:                                                      # copy
            tdriver = driver
            if o["new_driver"]:
                found = cmds.ls(o["new_driver"], long=True)
                tdriver = found[0] if len(found) == 1 else None
            new_attr = o["new_attr"] or rec["attr"]
            name = _copy_name(driven, o["search"], o["replace_with"]) if o["search"] else driven
            found = cmds.ls(name, long=True) if name else []
            row["driver"], row["driver_attr"] = tdriver, new_attr
            row["plug"] = "%s.%s" % (found[0], attr) if len(found) == 1 else None
            row["mult"] = float(o["multiplier"])
            if not tdriver:
                row["skip"] = "driver '%s' not found" % o["new_driver"]
            elif not row["plug"]:
                row["skip"] = "no '%s'" % (name or driven)
            elif row["plug"] == rec["plug"] and new_attr == rec["attr"] and tdriver == driver:
                row["skip"] = "same as the source (set a new attribute or a search / replace)"
        row["flip"] = attr in o["flip"] if attr in CHANNELS else bool(o["flip_other"])
        row["dflip"] = False
        if o["mode"] == 1 and o.get("auto", True) and not row["skip"]:
            sign = channel_sign(mirror_flips(driven, _node(row["plug"])), attr) if attr in CHANNELS else None
            if sign is None and attr in CHANNELS:
                row["notes"] = row.get("notes", []) + ["check: not a clean mirror - your ticks used"]
            elif sign is not None:
                row["flip"] = sign < 0
                row["auto"] = True
            dsign = channel_sign(mirror_flips(driver, tdriver), rec["attr"]) if rec["attr"] in CHANNELS else 1
            row["dflip"] = dsign == -1
        if row["plug"] and not cmds.objExists(row["plug"]):
            row["skip"] = "'%s' has no attribute '%s'" % (naming.short_name(_node(row["plug"])), attr)
        rows.append(row)
    return rows


def row_text(row):
    src = row["src"]
    left = "%s -> %s (%d keys)" % (src["attr"], naming.short_name(src["plug"]),
                                   cmds.keyframe(src["curve"], query=True, keyframeCount=True) or 0)
    if row["skip"]:
        return "SKIP  %s   [%s]" % (left, row["skip"])
    right = "%s.%s -> %s" % (naming.short_name(row["driver"]), row["driver_attr"], naming.short_name(row["plug"]))
    tags = []
    if row.get("auto"):
        tags.append("auto: " + ("flip" if row["flip"] else "keep"))
    elif row["flip"]:
        tags.append("flip")
    if row.get("dflip"):
        tags.append("driver flipped")
    if abs(row["mult"] - 1.0) > 1e-6:
        tags.append("x%g" % row["mult"])
    tags += row.get("notes") or []
    return "%s   =>   %s%s" % (left, right, ("   [" + ", ".join(tags) + "]") if tags else "")


# ===========================================================================
# applying
# ===========================================================================

def _ensure_driver_attr(src_driver, src_attr, driver, attr):
    if cmds.attributeQuery(attr, node=driver, exists=True):
        return
    kw = {"longName": attr, "attributeType": "double", "keyable": True}
    if cmds.attributeQuery(src_attr, node=src_driver, exists=True):
        if cmds.attributeQuery(src_attr, node=src_driver, minExists=True):
            kw["minValue"] = cmds.attributeQuery(src_attr, node=src_driver, minimum=True)[0]
        if cmds.attributeQuery(src_attr, node=src_driver, maxExists=True):
            kw["maxValue"] = cmds.attributeQuery(src_attr, node=src_driver, maximum=True)[0]
        default = cmds.attributeQuery(src_attr, node=src_driver, listDefault=True)
        if default:
            kw["defaultValue"] = default[0]
    cmds.addAttr(driver, **kw)


def _remove_old(driver, attr, plug):
    """Driven keys from driver.attr already landing on plug (to replace them)."""
    target = cmds.ls(_node(plug), long=True)[0] + "." + _attr(plug)
    for rec in find_sdks(driver, attr):
        if cmds.ls(_node(rec["plug"]), long=True)[0] + "." + _attr(rec["plug"]) == target:
            if cmds.objExists(rec["curve"]):
                cmds.delete(rec["curve"])


def _connect_output(curve, plug):
    """Connect a driven-key curve to plug, combining with existing driven keys."""
    incoming = cmds.listConnections(plug, source=True, destination=False, plugs=True,
                                    skipConversionNodes=True) or []
    if not incoming:
        cmds.connectAttr(curve + ".output", plug, force=True)
        return
    src_node = _node(incoming[0])
    kind = cmds.nodeType(src_node)
    if kind == "blendWeighted":
        index = cmds.getAttr(src_node + ".input", size=True)
        cmds.connectAttr(curve + ".output", "%s.input[%d]" % (src_node, index))
    elif kind in UCURVES:
        bw = cmds.createNode("blendWeighted", name=naming.unique(_node(plug).split("|")[-1] + "_blendWeighted"))
        cmds.connectAttr(incoming[0], bw + ".input[0]")
        cmds.connectAttr(curve + ".output", bw + ".input[1]")
        cmds.connectAttr(bw + ".output", plug, force=True)
    else:
        raise RuntimeError("'%s' is driven by something else (%s)" % (plug.split("|")[-1], kind))


def apply_row(row, src_driver):
    src = row["src"]
    driver, attr, plug = row["driver"], row["driver_attr"], row["plug"]
    _ensure_driver_attr(src_driver, src["attr"], driver, attr)
    if row.get("replace"):
        _remove_old(driver, attr, plug)
    name = naming.unique("%s_%s" % (_node(plug).split("|")[-1].split(":")[-1], _attr(plug)))
    curve = cmds.duplicate(src["curve"], name=name)[0]
    scale = row["mult"] * (-1.0 if row["flip"] else 1.0)
    if abs(scale - 1.0) > 1e-9:
        cmds.scaleKey(curve, valueScale=scale, valuePivot=0.0)
    if row.get("dflip"):                                    # 5.6.18: the twin driver moves the other way
        cmds.scaleKey(curve, floatScale=-1.0, floatPivot=0.0)
    cmds.connectAttr("%s.%s" % (driver, attr), curve + ".input", force=True)
    _connect_output(curve, plug)
    return curve


# ===========================================================================
# window
# ===========================================================================

def _driver():
    sel = [s for s in (cmds.ls(selection=True, long=True) or []) if "." not in s]
    return sel[0] if sel else None


def _ui():
    flip = [c for c in CHANNELS if cmds.checkBox(N("Flip_" + c), query=True, value=True)]
    menu = N("AttrFilter")
    return {
        "mode": cmds.radioButtonGrp(N("Mode"), query=True, select=True),
        "attr_filter": cmds.optionMenu(menu, query=True, value=True) if
        cmds.optionMenu(menu, query=True, numberOfItems=True) else "All",
        "suffix": cmds.textField(N("Suffix"), query=True, text=True),
        "flip": flip,
        "flip_other": cmds.checkBox(N("FlipOther"), query=True, value=True),
        "auto": cmds.checkBox(N("Auto"), query=True, value=True),
        "replace": cmds.checkBox(N("Replace"), query=True, value=True),
        "new_attr": cmds.textField(N("NewAttr"), query=True, text=True).strip(),
        "new_driver": cmds.textField(N("NewDriver"), query=True, text=True).strip(),
        "search": cmds.textField(N("Search"), query=True, text=True),
        "replace_with": cmds.textField(N("ReplaceWith"), query=True, text=True),
        "multiplier": cmds.floatField(N("Mult"), query=True, value=True),
    }


def _save(*_):
    try:
        s = _ui()
        s.pop("attr_filter", None)
        utils.save_setting(SETTINGS_KEY, s)
    except RuntimeError:
        pass


def _refresh_attrs(driver):
    """Fill the attribute dropdown with the driver's SDK attributes (keeps the choice)."""
    menu = N("AttrFilter")
    current = cmds.optionMenu(menu, query=True, value=True) if \
        cmds.optionMenu(menu, query=True, numberOfItems=True) else "All"
    attrs = driver_attrs(driver) if driver else []
    if _state.get(_P["p"], {}).get("attrs") == attrs and cmds.optionMenu(menu, query=True, numberOfItems=True):
        return
    for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    cmds.menuItem(label="All", parent=menu)
    for a in attrs:
        cmds.menuItem(label=a, parent=menu)
    if current in attrs:
        cmds.optionMenu(menu, edit=True, value=current)
    _state.setdefault(_P["p"], {})["attrs"] = attrs


def preview(*_):
    if not cmds.textScrollList(N("Rows"), exists=True):
        return
    driver = _driver()
    try:
        _refresh_attrs(driver)
        o = _ui()
        mode = o["mode"]
        cmds.rowLayout(N("CopyRow1"), edit=True, enable=mode == 2)
        cmds.rowLayout(N("CopyRow2"), edit=True, enable=mode == 2)
        cmds.rowLayout(N("CopyRow3"), edit=True, enable=mode == 2)
    except RuntimeError:
        return
    cmds.textScrollList(N("Rows"), edit=True, removeAll=True)
    if not driver:
        _state.setdefault(_P["p"], {})["rows"] = []
        cmds.textScrollList(N("Rows"), edit=True, append=["Select the driver (e.g. L_hand_ctrl)."])
        return
    rows = plan(o, driver)
    _state.setdefault(_P["p"], {})["rows"] = rows
    _state[_P["p"]]["driver"] = driver
    if not rows:
        what = " ending in '%s'" % o["suffix"] if o["suffix"].strip() else ""
        cmds.textScrollList(N("Rows"), edit=True,
                            append=["'%s' drives no set driven keys%s." % (naming.short_name(driver), what)])
        return
    cmds.textScrollList(N("Rows"), edit=True, append=[row_text(r) for r in rows])
    for i, r in enumerate(rows):
        if not r["skip"]:
            cmds.textScrollList(N("Rows"), edit=True, selectIndexedItem=i + 1)


def _light():
    d = _driver()
    if not d:
        return "warn", "Select the driver (e.g. L_hand_ctrl)."
    n = len(find_sdks(d))
    if not n:
        return "warn", "%s drives no set driven keys." % naming.short_name(d)
    return "ok", "Driver %s: %d driven key(s). Pick rows below, then Apply." % (naming.short_name(d), n)


def _on_change(*_):
    _save()
    preview()


def run(*_):
    _save()
    st = _state.get(_P["p"], {})
    if not st.get("rows") or st.get("driver") != _driver():
        preview()                                  # list out of date: rebuild it first
        st = _state.get(_P["p"], {})
    rows, driver = st.get("rows") or [], st.get("driver")
    picked = cmds.textScrollList(N("Rows"), query=True, selectIndexedItem=True) or []
    todo = [rows[i - 1] for i in picked if i - 1 < len(rows) and not rows[i - 1]["skip"]]
    if not todo:
        utils.warn(TOOL, "nothing to do: select the driver, and keep at least one row selected (not SKIP).")
        return
    replace = cmds.checkBox(N("Replace"), query=True, value=True)
    done, failed = 0, []
    with utils.undo_chunk("gusrigSDK"):
        for row in todo:
            row["replace"] = replace
            try:
                apply_row(row, driver)
                done += 1
            except RuntimeError as e:
                failed.append("%s (%s)" % (naming.short_name(row["plug"]), e))
    mode = "mirrored" if cmds.radioButtonGrp(N("Mode"), query=True, select=True) == 1 else "copied"
    if failed:
        utils.warn(TOOL, "%s %d driven key(s); failed %d: %s" % (mode, done, len(failed), "; ".join(failed[:3])))
    else:
        utils.info(TOOL, "%s %d driven key(s)." % (mode, done))
    st["rows"] = []                                # rebuilt on the next selection change


def delete_rows(*_):
    """Delete the driven keys of the picked rows (the selected driver's own keys) - e.g. ones mirrored onto
    the wrong node. Empty blendWeighted nodes left behind go too."""
    st = _state.get(_P["p"], {})
    if not st.get("rows") or st.get("driver") != _driver():
        preview()
        st = _state.get(_P["p"], {})
    rows = st.get("rows") or []
    picked = cmds.textScrollList(N("Rows"), query=True, selectIndexedItem=True) or []
    curves = []
    for i in picked:
        if i - 1 < len(rows) and rows[i - 1]["src"]["curve"] not in curves:
            curves.append(rows[i - 1]["src"]["curve"])
    if not curves:
        raise RuntimeError("select the driver, then pick the rows whose driven keys you want to delete.")
    driver = naming.short_name(st["driver"])
    if cmds.confirmDialog(title="Delete driven keys", button=["Delete", "Cancel"], defaultButton="Cancel",
                          cancelButton="Cancel", dismissString="Cancel",
                          message="Delete %d driven key curve(s) of %s?\n(One undo.)" % (len(curves), driver)) \
            != "Delete":
        return
    with utils.undo_chunk("gusrigSDKDelete"):
        blends = set()
        for c in curves:
            if cmds.objExists(c):
                for dst in cmds.listConnections(c + ".output", source=False, destination=True,
                                                skipConversionNodes=True) or []:
                    if cmds.nodeType(dst) == "blendWeighted":
                        blends.add(dst)
                cmds.delete(c)
        for bw in blends:
            if cmds.objExists(bw) and not cmds.listConnections(bw + ".input", source=True, destination=False):
                cmds.delete(bw)
    utils.info(TOOL, "deleted %d driven key curve(s) of %s." % (len(curves), driver))
    st["rows"] = []
    preview()


def _preset(name, *_):
    for c in CHANNELS:
        cmds.checkBox(N("Flip_" + c), edit=True, value=c in PRESETS[name])
    _on_change()


def _suffix(value, *_):
    cmds.textField(N("Suffix"), edit=True, text=value)
    _on_change()


def _get_driver(*_):
    d = _driver()
    if d:
        cmds.textField(N("NewDriver"), edit=True, text=naming.short_name(d))
        _on_change()


def build(prefix="p_sdk_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Driver", step=1, help_text="Select the driver (e.g. L_hand_ctrl). Its set driven keys are "
               "listed at the bottom. Driver attribute and Driven suffix narrow the list down.")
    cmds.radioButtonGrp(N("Mode"), label="Mode", numberOfRadioButtons=2, labelArray2=MODES, select=s["mode"],
                        columnWidth3=(90, 80, 80), changeCommand=_w(_on_change),
                        annotation="Mirror: to the other side. Copy: to another attribute / other nodes.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(90, 200), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Driver attribute")
    cmds.optionMenu(N("AttrFilter"), changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=5, columnWidth5=(90, 90, 55, 55, 55), adjustableColumn=2,
                   columnAttach=[(i, "both", 2) for i in range(1, 6)])
    cmds.text(label="Driven suffix", align="right")
    cmds.textField(N("Suffix"), text=s["suffix"], changeCommand=_w(_on_change),
                   annotation="Only driven nodes ending with this (e.g. _sdk). Empty = everything.")
    for p in SUFFIX_PRESETS:
        cmds.button(label=p, command=_w(lambda *_, v=p: _suffix(v)))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Copy (Copy mode)", step=2, help_text="Copy mode: the new attribute (e.g. middleCurl) drives "
               "nodes found by search / replace on the driven names (index -> middle), times the multiplier. "
               "Mirror mode ignores this section.")
    cmds.rowLayout(N("CopyRow1"), numberOfColumns=4, columnWidth4=(90, 120, 70, 60), adjustableColumn=2,
                   columnAttach=[(i, "both", 2) for i in range(1, 5)])
    cmds.text(label="New attribute", align="right")
    cmds.textField(N("NewAttr"), text=s["new_attr"], changeCommand=_w(_on_change),
                   annotation="e.g. middleCurl. Empty = the same attribute. Created if missing.")
    cmds.text(label="Multiplier", align="right")
    cmds.floatField(N("Mult"), value=float(s["multiplier"]), precision=3, changeCommand=_w(_on_change))
    cmds.setParent("..")
    cmds.rowLayout(N("CopyRow2"), numberOfColumns=4, columnWidth4=(90, 100, 60, 100), adjustableColumn=2,
                   columnAttach=[(i, "both", 2) for i in range(1, 5)])
    cmds.text(label="Driven: search", align="right")
    cmds.textField(N("Search"), text=s["search"], changeCommand=_w(_on_change), annotation="e.g. index")
    cmds.text(label="replace", align="right")
    cmds.textField(N("ReplaceWith"), text=s["replace_with"], changeCommand=_w(_on_change),
                   annotation="e.g. middle")
    cmds.setParent("..")
    cmds.rowLayout(N("CopyRow3"), numberOfColumns=3, columnWidth3=(90, 160, 50), adjustableColumn=2,
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Other driver")
    cmds.textField(N("NewDriver"), text=s["new_driver"], changeCommand=_w(_on_change),
                   annotation="Empty = the same driver.")
    cmds.button(label="Get", command=_w(_get_driver))
    cmds.setParent("..")
    ui.end_section()

    ui.section("Flip (negate the driven values)", step=3, help_text="Auto (Mirror mode): each driven node's "
               "flips come from how its parent is turned against its twin's - the rows show 'auto: flip / keep'; "
               "'check' where it isn't a clean mirror (then the ticks below are used). Without Auto: tick them - "
               "behavior-mirrored joints usually need none; orientation-mirrored ones tx, ry, rz. Replace existing "
               "swaps the old copy.")
    cmds.checkBox(N("Auto"), label="Auto (from how each side is turned)", value=s.get("auto", True),
                  changeCommand=_w(_on_change),
                  annotation="Works out which channels flip per driven node (e.g. tz rx ry for a ribbon mirrored "
                             "with Z flipped). Your ticks are used only where it can't tell.")
    cmds.gridLayout(numberOfColumns=3, cellWidthHeight=(110, 20))
    for c in CHANNELS:
        cmds.checkBox(N("Flip_" + c), label=c, value=c in s["flip"], changeCommand=_w(_on_change))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Preset: Behavior (none)", command=_w(lambda *_: _preset("Behavior")))
    cmds.button(label="Preset: Orientation (tx ry rz)", command=_w(lambda *_: _preset("Orientation")))
    cmds.setParent("..")
    cmds.checkBox(N("FlipOther"), label="Flip other attributes too (custom, blendShape...)",
                  value=s["flip_other"], changeCommand=_w(_on_change))
    cmds.checkBox(N("Replace"), label="Replace existing copies (don't stack)", value=s["replace"],
                  changeCommand=_w(_on_change))
    ui.end_section()

    ui.section("Driven keys (selected rows are applied)", step=4, help_text="Every row that is not SKIP starts "
               "selected. Ctrl / Cmd-click a row to leave it out, then Apply.")
    cmds.textScrollList(N("Rows"), allowMultiSelection=True, height=150,
                        annotation="Ctrl / Cmd-click to leave rows out.")
    ui.main_button("Apply", _w(run), "Mirror or copy the selected rows. One undo.")
    cmds.button(label="Delete picked driven keys", command=_w(_guard(delete_rows)),
                annotation="The selected driver's driven keys in the picked rows are deleted (e.g. keys mirrored "
                           "onto the wrong node). Asks first; one undo.")
    ui.end_section()

    ui.section("Nodes <-> driven key", step=5, help_text="Select the driven node (e.g. L_Brow_02_sdk) and type "
               "(or pick) its channel. Nodes -> driven key: the clamp / multiply chain driving it becomes a set "
               "driven key giving the same result (keys at the corners, linear) - shape it in the Graph Editor. "
               "Driven key -> nodes: a straight key curve, or straight on one side and flat on the other, becomes "
               "clamp + multiply nodes (a curved one is left, with the reason). Other side too: the R_ twin as well. "
               "Shows what it will do first; one undo.")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth=[(1, 60), (3, 90)],
                   columnAttach=[(1, "right", 4), (2, "both", 2), (3, "both", 2)])
    cmds.text(label="Channel")
    cmds.textField(N("ConvAttr"), placeholderText="rotateX")
    cmds.button(label="< Channel Box", command=_w(_guard(_conv_from_box)))
    cmds.setParent("..")
    cmds.checkBox(N("ConvTwin"), label="Other side too (the R_ twin)", value=True)
    ui.row(2, 170)
    cmds.button(label="Nodes -> driven key", command=_w(_guard(lambda *_: convert("sdk"))))
    cmds.button(label="Driven key -> nodes", command=_w(_guard(lambda *_: convert("nodes"))))
    cmds.setParent("..")
    ui.end_section()

    ui.on_selection(N("Rows"), _w(preview))
    preview()


def _conv_from_box(*_):
    from gus_rigtool.core import connector
    got = connector.channel_box_attrs()
    if not got:
        raise RuntimeError("pick a channel in the Channel Box first.")
    cmds.textField(N("ConvAttr"), edit=True, text=got[0])


def convert(direction):
    """5.2.1: the selected node's channel: its node chain -> a set driven key, or the other way."""
    from gus_rigtool.core import sdk_convert as SC
    sel = cmds.ls(selection=True, long=True) or []
    attr = (cmds.textField(N("ConvAttr"), query=True, text=True) or "").strip()
    if not sel or not attr:
        raise RuntimeError("select the driven node (e.g. L_Brow_02_sdk) and type its channel (rotateX).")
    plugs = ["%s.%s" % (n, attr) for n in sel]
    if cmds.checkBox(N("ConvTwin"), query=True, value=True):
        plugs += [t for t in (SC.twin_plug(p) for p in plugs) if t and t not in plugs]
    rows, ok = [], []
    for p in plugs:
        try:
            if direction == "sdk":
                drv, nodes, keys, pre, post = SC.plan_sdk(p)
                rows.append("%s: %d node(s) -> %d key(s) on %s" % (SC._short(p), len(nodes), len(keys),
                                                                  SC._short(drv)))
            else:
                _c, drv, lo, hi, slope, off = SC.plan_nodes(p)
                rows.append("%s: key -> clamp %s..%s, x %g%s" % (SC._short(p), "-" if lo is None else lo,
                                                                "+" if hi is None else hi, slope,
                                                                (" + %g" % off) if abs(off) > 1e-9 else ""))
            ok.append(p)
        except RuntimeError as e:
            rows.append("skip: %s" % e)
    if not ok:
        raise RuntimeError("\n".join(rows))
    if cmds.confirmDialog(title="Gus_Rigtool - %s" % ("nodes -> driven key" if direction == "sdk" else
                                                      "driven key -> nodes"),
                          button=["Do it", "Cancel"], defaultButton="Do it", cancelButton="Cancel",
                          dismissString="Cancel", message="\n".join(rows) + "\n\nOne undo.") != "Do it":
        return
    done = []
    with utils.undo_chunk("gusrigSdkConvert"):
        for p in ok:
            done.append(SC.to_sdk(p) if direction == "sdk" else SC.to_nodes(p))
    utils.info(TOOL, "; ".join(done))


def show():
    ui.open_panel("sdk")


SCHEMA = [
    ("mode", "Mode", "choice", MODES),
    ("suffix", "Driven suffix filter", "text", None),
    ("flip_other", "Flip other attributes", "bool", None),
    ("auto", "Auto flips", "bool", None),
    ("replace", "Replace existing copies", "bool", None),
    ("multiplier", "Copy: multiplier", "float", None),
]
