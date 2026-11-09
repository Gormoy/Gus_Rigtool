# simple UI controls for the fake maya: remember values, answer queries
UI = {}
_order = []
_menu_owner = [None]
_count = [0]
_cur = [None]                     # the current parent layout (like Maya's setParent)
LAYOUTS = {"columnLayout", "rowLayout", "frameLayout", "rowColumnLayout", "gridLayout", "formLayout",
           "scrollLayout", "tabLayout", "flowLayout"}
NOT_CHILDREN = {"menuItem", "popupMenu", "workspaceControl"}
def _make(kind):
    def f(*args, **k):
        name = args[0] if args else None
        if k.get("exists"):
            return name in UI
        if k.get("query"):
            c = UI.get(name, {})
            for key in k:
                if key in ("query",):
                    continue
                if key == "select" and c.get("kind") == "optionMenu":
                    return c.get("select", 1)
                if c.get("kind") == "optionMenu" and key == "numberOfItems":
                    return len(c.get("items", []))
                if c.get("kind") == "optionMenu" and key == "itemListLong":
                    ids = c.get("ids") or list(range(len(c.get("items", []))))
                    return ["%s|%s" % (name, i) for i in ids] or None
                if c.get("kind") == "optionMenu" and key == "itemListShort":
                    return list(c.get("items", [])) or None
                if c.get("kind") == "optionMenu" and key == "value":
                    items = c.get("items", [])
                    return items[c.get("select", 1) - 1] if 0 < c.get("select", 1) <= len(items) else None
                if key == "childArray":
                    return [n for n, v in UI.items() if v.get("parent") == name] or None
                if key == "value" and kind == "floatFieldGrp":
                    return [c.get("value1", 0), c.get("value2", 0), c.get("value3", 0)]
                if key == "rgbValue":
                    return c.get("rgbValue", [1.0, 1.0, 1.0])
                if key == "selectIndexedItem":
                    return c.get("selectIndexedItem")
                return c.get(key)
            return None
        if k.get("edit"):
            c = UI.setdefault(name, {})
            if c.get("kind") == "optionMenu" and "select" in k:          # like Maya
                if not 1 <= int(k["select"]) <= len(c.get("items", [])):
                    raise RuntimeError("Value is out of range: %s" % k["select"])
            if c.get("kind") == "optionMenu" and "value" in k:
                if k["value"] not in c.get("items", []):
                    raise RuntimeError("Value is out of range: %s" % k["value"])
                k = dict(k, select=c["items"].index(k["value"]) + 1)
            c.update({a: b for a, b in k.items() if a != "edit"})
            return name
        if kind == "menuItem":
            owner = k.get("parent") if k.get("parent") in UI else _menu_owner[0]
            if owner:
                _count[0] += 1
                UI[owner].setdefault("items", []).append(k.get("label"))
                UI[owner].setdefault("ids", []).append(_count[0])
            return None
        if name and "|" in name:                                   # like Maya: a new control's name has no '|'
            raise RuntimeError("Invalid name: '%s'" % name)
        _count[0] += 1
        name = name or "%s%d" % (kind, _count[0])
        parent = k.get("parent") or (None if kind in NOT_CHILDREN else _cur[0])
        p = UI.get(parent) or {}
        if kind not in NOT_CHILDREN and p.get("kind") == "rowLayout":   # like Maya: a row has N slots
            used = sum(1 for v in UI.values() if v.get("parent") == parent)
            if used >= int(p.get("numberOfColumns") or 1):
                raise RuntimeError("Too many children in layout: %s" % parent)
        UI[name] = dict(k, kind=kind, parent=parent)
        if kind in LAYOUTS:
            _cur[0] = name
        if kind == "optionMenu":
            _menu_owner[0] = name
            UI[name]["select"] = 1
        return name
    return f
for kind in ("textField", "intField", "floatField", "checkBox", "optionMenu", "floatFieldGrp", "textFieldGrp",
             "textScrollList", "columnLayout", "rowLayout", "text", "button", "menuItem", "frameLayout", "scrollField",
             "rowColumnLayout", "separator", "floatSliderGrp", "radioButtonGrp", "iconTextButton", "gridLayout",
             "formLayout", "scrollLayout", "colorSliderGrp", "intFieldGrp", "optionMenuGrp", "layout", "control",
             "workspaceControl", "symbolButton", "popupMenu", "intSliderGrp", "tabLayout", "flowLayout", "intSlider",
             "image", "shelfLayout", "shelfButton"):
    setattr(cmds, kind, _make(kind))
def _set_parent(*a, **k):
    if k.get("query"):
        return _cur[0] or "section_col"
    if k.get("menu") or not a:
        return None
    target = a[0]
    if target == "..":
        _cur[0] = (UI.get(_cur[0]) or {}).get("parent")
    else:
        target = target.split("|")[-1] if target else target
        _cur[0] = target if target in UI else _cur[0]
    return _cur[0]
cmds.setParent = _set_parent
def _delete_ui(name, **k):
    for n in (name if isinstance(name, (list, tuple)) else [name]):
        if isinstance(n, str) and "|" in n and n.rsplit("|", 1)[0] in UI and \
                UI[n.rsplit("|", 1)[0]].get("kind") == "optionMenu":
            menu = UI[n.rsplit("|", 1)[0]]                     # a menu item: "menu|index"
            menu.setdefault("_gone", set()).add(int(n.rsplit("|", 1)[1]))
            continue
        UI.pop(n, None)
    for menu in UI.values():                                   # drop the deleted items (by their id)
        gone = menu.pop("_gone", None)
        if gone:
            ids = menu.get("ids") or list(range(len(menu.get("items", []))))
            keep = [(i, x) for i, x in zip(ids, menu.get("items", [])) if i not in gone]
            menu["ids"], menu["items"] = [i for i, _x in keep], [x for _i, x in keep]
            menu["select"] = 1
cmds.deleteUI = _delete_ui
cmds.fileDialog2 = lambda **k: None
