"""
Recording a page (5.7): a tool's own build() runs, its UI calls (cmds.button, cmds.frameLayout, ui.section...)
are written down as a tree instead of being made in Maya - render.py then draws that tree in the new look.
Every other Maya call runs as usual. While it records, the tool's selection callbacks (ui.on_selection /
ui.status_light) are kept, so the new window can call them.
"""

import maya.cmds as _mc

from gus_rigtool.newui import proxy

LAYOUTS = {"columnLayout", "rowLayout", "rowColumnLayout", "frameLayout", "formLayout", "scrollLayout",
           "tabLayout", "paneLayout", "gridLayout", "flowLayout"}
MENUS = {"optionMenu", "popupMenu", "optionMenuGrp"}


class Node(object):
    def __init__(self, kind, name, kw, parent):
        self.kind, self.name, self.kw, self.parent = kind, name, dict(kw), parent
        self.children = []
        self.items = []                     # a menu's items: dicts (label, command...)

    def label(self):
        return self.kw.get("label") or self.kw.get("l") or ""

    def __repr__(self):
        return "<%s %s %r>" % (self.kind, self.name, self.label())


class Recorder(object):
    def __init__(self, stem=""):
        self.stem = stem                    # 5.7.3: in unnamed controls' names - unique per page and per refill
        self.root = Node("columnLayout", "__page__", {"adjustableColumn": True}, None)
        self.nodes = {"__page__": self.root}
        self.current = self.root
        self.menu = None                    # the menu new menuItems go into
        self.count = 0
        self.selection = []                 # [(anchor, fn)] - ui.on_selection / ui.status_light updates
        self.lights = []                    # anchors of status lights
        self.deferred = []
        self.jobs = []
        self.live = False                   # 5.7.3: refilling part of a page that is shown - names the recorder
        #                                     doesn't know are the shown page's fields (proxy.REGISTRY)

    # ---------------------------------------------------------------- names
    def _name(self, kind, args, k):
        if args and isinstance(args[0], str) and args[0]:
            return proxy.short(args[0])
        self.count += 1
        return "%s__%s%d" % (kind, self.stem, self.count)

    def find(self, name):
        return self.nodes.get(proxy.short(name)) if isinstance(name, str) else None

    # ---------------------------------------------------------------- one call
    def _shown(self, kind, args, k):
        """While refilling: the shown page's field this call is about (one this recording didn't make)."""
        if not self.live or not args or not isinstance(args[0], str) or self.find(args[0]) is not None:
            return None
        if not (k.get("query") or k.get("q") or k.get("edit") or k.get("e") or k.get("exists") or k.get("ex")) \
                and kind not in ("deleteUI", "objectTypeUI"):
            return None
        return proxy.REGISTRY.get(proxy.short(args[0]))

    def call(self, kind, args, k):
        f = self._shown(kind, args, k)
        if f is not None:
            if kind == "deleteUI":
                return f.delete()
            if kind == "objectTypeUI":
                return f.kind
            return f.cmd(kind, args, k)
        if kind == "setParent":
            return self._set_parent(args, k)
        if kind == "deleteUI":
            for a in (args[0] if args and isinstance(args[0], (list, tuple)) else args):
                self._delete(a)
            return None
        if kind == "objectTypeUI":
            n = self.find(args[0]) if args else None
            if n is None:
                raise RuntimeError("Object not found: %s" % (args[0] if args else ""))
            return n.kind
        if kind in ("control", "layout"):
            n = self.find(args[0]) if args else None
            if k.get("exists") or k.get("ex"):
                return n is not None
            if n is None:
                raise RuntimeError("Object not found: %s" % (args[0] if args else ""))
            return self._query(n, k) if (k.get("query") or k.get("q")) else self._edit(n, k)
        if kind == "menuItem":
            return self._menu_item(args, k)
        n = self.find(args[0]) if args else None
        if k.get("exists") or k.get("ex"):
            return n is not None
        if k.get("query") or k.get("q"):
            if n is None:
                raise RuntimeError("Object not found: %s" % (args[0] if args else ""))
            return self._query(n, k)
        if k.get("edit") or k.get("e"):
            if n is None:
                raise RuntimeError("Object not found: %s" % (args[0] if args else ""))
            return self._edit(n, k)
        return self._create(kind, args, k)

    def _create(self, kind, args, k):
        name = self._name(kind, args, k)
        parent = self.find(k.get("parent") or k.get("p")) or self.current
        if kind == "popupMenu":
            parent = self.find(k.get("parent") or k.get("p")) or (parent.children[-1] if parent.children else parent)
        n = Node(kind, name, k, parent)
        self.nodes[name] = n
        if kind == "popupMenu":
            parent.kw.setdefault("_popups", []).append(n)
        else:
            parent.children.append(n)
        if kind in LAYOUTS:
            self.current = n
        if kind in MENUS:
            self.menu = n
        return name

    def _menu_item(self, args, k):
        if k.get("query") or k.get("edit") or k.get("exists"):
            return None
        menu = self.find(k.get("parent") or k.get("p")) or self.menu
        if menu is None:
            return None
        self.count += 1
        item = dict(k)
        item["_name"] = "%s__item%d" % (menu.name, self.count)
        menu.items.append(item)
        return item["_name"]

    def _set_parent(self, args, k):
        if k.get("query") or k.get("q"):
            return self.current.name
        if k.get("menu") or k.get("m"):
            m = self.find(args[0]) if args else None
            if m is not None:
                self.menu = m
            return self.menu.name if self.menu else None
        if not args:
            return self.current.name
        target = args[0]
        if target == "..":
            if self.current.parent is not None:
                self.current = self.current.parent
        else:
            n = self.find(target)
            if n is not None:
                self.current = n
        return self.current.name

    def _delete(self, name):
        n = self.find(name)
        if n is None:
            for m in self.nodes.values():
                m.items = [i for i in m.items if i.get("_name") != proxy.short(name)]
            return
        if n.parent is not None and n in n.parent.children:
            n.parent.children.remove(n)
        self.nodes.pop(n.name, None)

    def _query(self, n, k):
        for key in k:
            if key in ("query", "q"):
                continue
            if key in ("childArray", "ca"):
                return [c.name for c in n.children] or None
            if key in ("fullPathName", "fpn"):
                path, p = [n.name], n.parent
                while p is not None:
                    path.insert(0, p.name)
                    p = p.parent
                return "|".join(path)
            if key == "numberOfItems":
                return len(n.items)
            if key == "itemListLong":
                return [i["_name"] for i in n.items] or None
            if key == "itemListShort":
                return [i.get("label") for i in n.items] or None
            if key == "select" and n.kind in MENUS:
                return n.kw.get("select", 1)
            if key == "value" and n.kind in MENUS:
                i = n.kw.get("select", 1)
                return n.items[i - 1].get("label") if 0 < i <= len(n.items) else None
            if key == "selectTabIndex":
                return n.kw.get("selectTabIndex", 1)
            if key in ("width", "w", "height", "h"):
                return n.kw.get(key) or 100
            if key in ("value", "v") and n.kind in ("floatFieldGrp", "intFieldGrp"):     # 5.7.7: Mirror's centre
                cnt = int(n.kw.get("numberOfFields") or n.kw.get("nf") or 0) or max(
                    [i for i in (1, 2, 3, 4) if ("value%d" % i) in n.kw] or [1])
                return [n.kw.get("value%d" % i, 0) for i in range(1, cnt + 1)]
            if key in ("value1", "value2", "value3", "value4") and n.kind in ("floatFieldGrp", "intFieldGrp"):
                return n.kw.get(key, 0)
            if key in ("rgbValue", "rgb"):                     # 5.7.3: a colour picker's colour (Ribbon reads it)
                return list(n.kw.get("rgbValue") or n.kw.get("rgb") or (1.0, 1.0, 1.0))
            if key in ("allItems", "ai"):
                return list(n.kw.get("_items", [])) or None
            if key in ("selectIndexedItem", "sii", "selectItem", "si"):
                return None
            return n.kw.get(key)
        return None

    def _edit(self, n, k):
        for key, v in k.items():
            if key in ("edit", "e"):
                continue
            if n.kind in MENUS and key == "value":
                labels = [i.get("label") for i in n.items]
                if v in labels:
                    n.kw["select"] = labels.index(v) + 1
                continue
            if key in ("append", "a"):
                n.kw.setdefault("_items", []).extend(v if isinstance(v, (list, tuple)) else [v])
                continue
            if key in ("removeAll", "ra"):
                n.kw["_items"] = []
                continue
            n.kw[key] = v
        return n.name


class recording(object):
    """with recording() as rec: build(prefix) - the page written down in rec.root."""

    def __init__(self, rec=None):
        self.given = rec

    def __enter__(self):
        from gus_rigtool.core import ui
        self.rec = self.given or Recorder()
        self.saved = {}
        for kind in proxy.UI_KINDS:              # pages that use maya.cmds itself (and core/ui) are recorded too
            fn = getattr(_mc, kind, None)
            if fn is not None:
                self.saved[kind] = fn
                setattr(_mc, kind, (lambda kind: lambda *a, **k: self.rec.call(kind, a, k))(kind))
        for kind in ("scriptJob", "evalDeferred"):
            self.saved[kind] = getattr(_mc, kind, None)
        _mc.scriptJob = lambda *a, **k: self.rec.jobs.append(k) or len(self.rec.jobs)
        _mc.evalDeferred = lambda fn=None, *a, **k: self.rec.deferred.append(fn) if callable(fn) else None
        self.ui_saved = (ui.on_selection, ui.status_light)
        rec = self.rec

        def on_selection(anchor, fn):
            rec.selection.append((anchor, fn))
            return fn

        def status_light(name, compute, bind_fn):
            ctrl = _mc.text(name, label="", align="left", wordWrap=True, _light=True)

            def update(*_):
                try:
                    level, text = compute()
                except Exception as e:
                    level, text = "warn", "(%s)" % e
                proxy.cmds.text(name, edit=True, label="  " + text, _level=level)
            bound = bind_fn(update)
            ui._lights[name] = bound
            rec.selection.append((name, bound))
            rec.lights.append(name)
            return ctrl
        ui.on_selection, ui.status_light = on_selection, status_light
        proxy._REC["on"] = self.rec
        return self.rec

    def __exit__(self, *exc):
        from gus_rigtool.core import ui
        proxy._REC["on"] = None
        for kind, fn in self.saved.items():
            if fn is None:
                try:
                    delattr(_mc, kind)
                except AttributeError:
                    pass
            else:
                setattr(_mc, kind, fn)
        ui.on_selection, ui.status_light = self.ui_saved
        return False


def record(build, prefix):
    """The tree build(prefix) makes (and the recorder, for its selection callbacks)."""
    with recording(Recorder(prefix)) as rec:
        build(prefix)
    return rec
