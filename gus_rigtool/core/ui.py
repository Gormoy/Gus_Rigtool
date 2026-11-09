"""
Shared look and dockable panels for every Gus_Rigtool tool.

Each tool module has:
    LABEL, build(prefix)  - content, built into the current layout
    show()                - opens the tool as its own dockable panel

Control names inside a tool start with an instance prefix, so the same tool can be
open in the main window and in its own panel at the same time. Callbacks are wrapped
with bind(): they always talk to the instance that was clicked, and any error is caught,
shown on the status line and kept for "Copy error report".
"""

import json
import os
import platform
import traceback

import maya.cmds as cmds

# colours
HEADER_BG = (0.17, 0.23, 0.29)
MAIN_BG = (0.26, 0.42, 0.56)          # the main action of a step
SECOND_BG = (0.35, 0.35, 0.35)        # other buttons (Maya's default grey)
DANGER_BG = (0.54, 0.23, 0.23)        # deletes something
DANGER_WORDS = ("delete", "remove", "back to guides", "clear", "unlink", "forget")
STATUS_BG = {
    "info": (0.24, 0.24, 0.24),
    "ok": (0.20, 0.36, 0.22),
    "warn": (0.52, 0.36, 0.10),
}
LIGHT_BG = {"ok": (0.20, 0.36, 0.22), "warn": (0.52, 0.36, 0.10), "idle": (0.26, 0.26, 0.26)}

MAIN_KEY = "main"
SPEED_LIMIT = 3000          # live counts / previews skip themselves above this many nodes

_status_controls = []
_lights = {}
_error_buttons = []
_last_error = {"text": ""}


# ---------------------------------------------------------------------------
# instances + error capture
# ---------------------------------------------------------------------------

def bind(state, fn):
    """Wrap a callback: right control prefix, and errors reported instead of lost."""
    prefix = state["p"]

    def run(*args):
        old = state["p"]
        state["p"] = prefix
        try:
            with _Fit():                       # 5.3.3: what a callback adds to its page fits the window too
                return fn(*args)
        except Exception as e:
            report_error(e, prefix)
        finally:
            state["p"] = old
            refit_visible()                    # 5.6.4: what the click added (the Checker's list...) isn't cut off
    return run


def tool_helpers(prefix, tool, dialog=True):
    """The helpers every tool page uses: (state, N, w, guard).
    N(name): control name with this page's prefix. w(fn): callback with the right prefix and errors reported.
    guard(fn): expected problems (RuntimeError / ValueError) go to the status line, and to a window if dialog."""
    state = {"p": prefix}

    def N(name):
        return state["p"] + name

    def w(fn):
        return bind(state, fn)

    def guard(fn):
        def run(*a):
            try:
                return fn(*a)
            except (RuntimeError, ValueError) as e:
                from gus_rigtool.core import utils
                utils.warn(tool, str(e).strip())
                if dialog:
                    try:
                        cmds.confirmDialog(title="Gus_Rigtool - " + tool, message=str(e).strip(), button=["OK"])
                    except RuntimeError:
                        pass
        return run
    return state, N, w, guard


def report_window(title, text, win="gusRigReportWin", extra=None):
    """A window with a read-only report and a Copy button (extra: [(label, command)] more buttons beside it)."""
    from gus_rigtool.core import utils
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title=title, widthHeight=(560, 460))
    form = cmds.formLayout()
    field = cmds.scrollField(editable=False, wordWrap=False, text=text, font="fixedWidthFont")
    copy = cmds.button(label="Copy report", height=28,
                       command=lambda *_: utils.copy_to_clipboard(text) and utils.info("Report", "copied."))
    buttons = [copy] + [cmds.button(label=lab, height=28, command=cmd) for lab, cmd in (extra or [])]
    n = len(buttons)
    att = [(field, "top", 4), (field, "left", 4), (field, "right", 4)]
    pos = []
    for i, b in enumerate(buttons):
        att.append((b, "bottom", 4))
        if i == 0:
            att.append((b, "left", 4))
        else:
            pos.append((b, "left", 2, int(100 * i / n)))
        if i == n - 1:
            att.append((b, "right", 4))
        else:
            pos.append((b, "right", 2, int(100 * (i + 1) / n)))
    cmds.formLayout(form, edit=True, attachForm=att, attachControl=[(field, "bottom", 4, copy)])
    if pos:
        cmds.formLayout(form, edit=True, attachPosition=pos)
    cmds.showWindow(win)
    return win


def report_error(error, where=""):
    import gus_rigtool
    tb = traceback.format_exc()
    _last_error["text"] = (
        "Gus_Rigtool %s error report\n"
        "Tool: %s\nMaya: %s   OS: %s   Python: %s\n\n%s" % (
            gus_rigtool.__version__, where.strip("_") or "-", cmds.about(version=True),
            platform.platform(), platform.python_version(), tb))
    print(_last_error["text"])
    status("Error: %s  -  click 'Copy error report' and paste it to get it fixed." % error, "warn")
    for b in list(_error_buttons):
        try:
            if cmds.button(b, exists=True):
                cmds.button(b, edit=True, manage=True)
        except RuntimeError:
            pass


def copy_error(*_):
    from gus_rigtool.core import utils
    if not _last_error["text"]:
        return
    if utils.copy_to_clipboard(_last_error["text"]):
        status("Error report copied to the clipboard.", "info")
    else:
        status("Error report printed in the Script Editor.", "info")


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

def header(title, subtitle="", pop_key=None, extra_button=None):
    col = cmds.columnLayout(adjustableColumn=True, backgroundColor=HEADER_BG)
    extras = extra_button if isinstance(extra_button, list) else [extra_button]
    buttons = [b for b in extras + [("Pop out", lambda *_: open_panel(pop_key),
                                     "Open this tool in its own dockable panel.") if pop_key else None] if b]
    if buttons:
        cmds.rowLayout(numberOfColumns=1 + len(buttons), adjustableColumn=1, backgroundColor=HEADER_BG)
    cmds.text(label="  " + title, font="boldLabelFont", align="left", height=24, backgroundColor=HEADER_BG, width=1)
    for label, command, annotation in buttons:
        cmds.button(label=label, width=86, height=20, annotation=annotation, command=command)
    if buttons:
        cmds.setParent("..")
    if subtitle:
        cmds.text(label="  " + subtitle, align="left", backgroundColor=HEADER_BG, width=1, wordWrap=True,
                  height=max(18, note_height(subtitle) - 4))      # 5.4.0: wraps, never widens the page
    cmds.setParent("..")
    return col


_view = {"tool": None}


def view_mode():
    """'simple' (advanced sections folded) or 'full'. New users start simple; an existing install stays full."""
    from gus_rigtool.core import utils
    mode = utils.load_setting("viewMode", None)
    if mode in ("simple", "full"):
        return mode
    old_user = utils.load_setting("panelWidths", None) is not None or utils.load_setting("mainCategory", None) \
        is not None
    mode = "full" if old_user else "simple"
    utils.save_setting("viewMode", mode)
    return mode


def set_view_mode(mode):
    from gus_rigtool.core import utils
    utils.save_setting("viewMode", mode)
    cmds.evalDeferred(rebuild_open)


def _is_advanced(label):
    from gus_rigtool import registry
    tool = _view.get("tool")
    if not tool or view_mode() != "simple":
        return False
    return any(label.startswith(a) or a in label for a in registry.ADVANCED.get(tool, []))


def section(label, collapse=False, help_text=None, step=None):
    """Collapsible section, optionally numbered, with a '?' help button. Close with end_section().
    In Simple view the tool's advanced sections (registry.ADVANCED) start folded, marked '(advanced)'."""
    title = "%d.  %s" % (step, label) if step else label
    if _is_advanced(label):
        collapse = True
        title += "   (advanced)"
    frame = cmds.frameLayout(label=title, collapsable=True, collapse=collapse, marginWidth=6, marginHeight=4,
                             annotation=help_text or "")
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    if help_text:
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
        cmds.text(label="")
        cmds.button(label="?", width=22, height=18, annotation=help_text,
                    command=lambda *_: cmds.confirmDialog(title=label, message=help_text, button=["OK"]))
        cmds.setParent("..")
    return frame


def more_options(collapse=True):
    """The standard 'More options' section (close with end_section())."""
    return section("More options", collapse=collapse,
                   help_text="Options you rarely need to change. Your choices are remembered.")


def end_section():
    cmds.setParent("..")
    cmds.setParent("..")


NOTE_CHARS = 52          # about what a narrow panel fits on one line
NOTE_LINE = 15           # px per line


def note_height(text):
    """The height a note needs in a narrow panel. Fixed up front: a wrapping text that grows AFTER its section
    was sized pushes the section's last buttons out of sight (Maya doesn't grow the section again)."""
    import textwrap
    lines = sum(max(1, len(textwrap.wrap(part, NOTE_CHARS))) for part in str(text).split("\n"))
    return lines * NOTE_LINE + 4


def note(text):
    return cmds.text(label=text, align="left", wordWrap=True, height=note_height(text))


def main_button(label, command, annotation=""):
    return cmds.button(label=label, height=34, backgroundColor=MAIN_BG, command=command, annotation=annotation)


def row(count, width=80):
    """Row of equal columns. Close it with cmds.setParent('..')."""
    return cmds.rowLayout(numberOfColumns=count,
                          columnWidth=[(i + 1, width) for i in range(count)],
                          columnAttach=[(i + 1, "both", 2) for i in range(count)])


# ---------------------------------------------------------------------------
# status light (what the tool will act on, updated with the selection)
# ---------------------------------------------------------------------------

def status_light(name, compute, bind_fn):
    """
    A light under the tool header. compute() -> (level 'ok'|'warn'|'idle', text).
    It updates on every selection change while the control exists.
    """
    ctrl = cmds.text(name, label="", align="left", height=34, wordWrap=True, enableBackground=True, width=1,
                     backgroundColor=LIGHT_BG["idle"])          # 5.3.3: two lines, wraps (no wider page; always open)

    def update(*_):
        if not cmds.text(name, exists=True):
            return
        try:
            level, text = compute()
        except Exception as e:
            level, text = "warn", "(%s)" % e
        cmds.text(name, edit=True, label="  " + text, backgroundColor=LIGHT_BG.get(level, LIGHT_BG["idle"]))
    bound = bind_fn(update)
    _lights[name] = bound
    on_selection(name, bound)
    bound()
    return ctrl


# ---------------------------------------------------------------------------
# selection callbacks only for what can be seen (the main window builds every tool: with all of them updating
# on each click, Maya slows down)
# ---------------------------------------------------------------------------

_pending = {}       # control -> its update, skipped while its tab was hidden


def shown(anchor):
    """True when the control's tabs are the ones showing and its panel is open."""
    try:
        path = cmds.control(anchor, query=True, fullPathName=True)
    except RuntimeError:
        return False
    parts = path.split("|")
    for i in range(len(parts) - 1):
        here = "|".join(parts[:i + 1])
        try:
            kind = cmds.objectTypeUI(here)
        except RuntimeError:
            continue
        if kind == "tabLayout":
            picked = cmds.tabLayout(here, query=True, selectTab=True) or ""
            if picked and picked.split("|")[-1] != parts[i + 1]:
                return False
        elif kind == "workspaceControl":
            try:
                if not cmds.workspaceControl(here, query=True, visible=True):
                    return False
            except RuntimeError:
                pass
    return True


def on_selection(anchor, fn):
    """fn on every selection change while anchor exists - right away when it can be seen, else when its tab
    is shown again (flush_shown)."""
    def run(*_):
        if not cmds.control(anchor, exists=True):
            _pending.pop(anchor, None)
            return
        if shown(anchor):
            _pending.pop(anchor, None)
            fn()
        else:
            _pending[anchor] = fn
    cmds.scriptJob(event=["SelectionChanged", run], parent=anchor)
    return run


def flush_shown(*_):
    """Run the updates that were skipped while their tab was hidden, for the ones showing now."""
    for anchor, fn in list(_pending.items()):
        try:
            if not cmds.control(anchor, exists=True):
                _pending.pop(anchor, None)
            elif shown(anchor):
                _pending.pop(anchor, None)
                fn()
        except Exception:
            _pending.pop(anchor, None)


def refresh_light(name):
    """Update a status light now (e.g. after an option changed)."""
    fn = _lights.get(name)
    if fn:
        fn()


def selection_summary(nodes, what="object"):
    """'3 controls selected' style text."""
    n = len(nodes)
    if not n:
        return "nothing selected"
    if n == 1:
        return "%s selected" % nodes[0].split("|")[-1]
    return "%d %ss selected" % (n, what)


def too_many(count):
    return count > SPEED_LIMIT


# ---------------------------------------------------------------------------
# presets (per tool, stored in data/presets.json)
# ---------------------------------------------------------------------------

def _presets_file():
    import gus_rigtool
    return os.path.join(gus_rigtool.DATA_DIR, "presets.json")


def load_presets():
    try:
        with open(_presets_file(), "r") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_presets(data):
    import gus_rigtool
    if not os.path.isdir(gus_rigtool.DATA_DIR):
        os.makedirs(gus_rigtool.DATA_DIR)
    with open(_presets_file(), "w") as f:
        json.dump(data, f, indent=1)


def presets_row(settings_key, save_now, bind_fn):
    """Preset dropdown + Save / Load / Delete for a tool. save_now() writes the UI to settings."""
    from gus_rigtool.core import utils
    menu_holder = {}

    def fill(select=None):
        menu = menu_holder["menu"]
        for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
            cmds.deleteUI(item)
        names = sorted(load_presets().get(settings_key, {}))
        cmds.menuItem(label="(presets)", parent=menu)
        for n in names:
            cmds.menuItem(label=n, parent=menu)
        if select in names:
            cmds.optionMenu(menu, edit=True, value=select)

    def current():
        v = cmds.optionMenu(menu_holder["menu"], query=True, value=True)
        return None if v == "(presets)" else v

    def save(*_):
        result = cmds.promptDialog(title="Save preset", message="Preset name:", text=current() or "",
                                   button=["Save", "Cancel"], defaultButton="Save", cancelButton="Cancel",
                                   dismissString="Cancel")
        if result != "Save":
            return
        name = cmds.promptDialog(query=True, text=True).strip()
        if not name:
            return
        save_now()
        data = load_presets()
        data.setdefault(settings_key, {})[name] = utils.load_setting(settings_key, {})
        save_presets(data)
        fill(name)
        utils.info("Presets", "saved '%s'." % name)

    def load(*_):
        name = current()
        if not name:
            utils.warn("Presets", "pick a preset in the list first.")
            return
        utils.save_setting(settings_key, load_presets().get(settings_key, {}).get(name, {}))
        cmds.evalDeferred(rebuild_open)
        utils.info("Presets", "loaded '%s'." % name)

    def delete(*_):
        name = current()
        if not name:
            return
        data = load_presets()
        data.get(settings_key, {}).pop(name, None)
        save_presets(data)
        fill()
        utils.info("Presets", "deleted '%s'." % name)

    cmds.rowLayout(numberOfColumns=4, adjustableColumn=1,
                   columnAttach=[(1, "both", 2), (2, "both", 1), (3, "both", 1), (4, "both", 1)])
    menu_holder["menu"] = cmds.optionMenu(annotation="Your saved settings for this tool.")
    cmds.button(label="Save", width=48, command=bind_fn(save), annotation="Save the current options as a preset.")
    cmds.button(label="Load", width=48, command=bind_fn(load), annotation="Load the preset picked in the list.")
    cmds.button(label="Delete", width=52, command=bind_fn(delete))
    cmds.setParent("..")
    fill()


# ---------------------------------------------------------------------------
# status line
# ---------------------------------------------------------------------------

def status_line():
    """Bottom bar: messages, plus a 'Copy error report' button that appears after an error."""
    form = cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 2)])
    ctrl = cmds.text(label="  Ready.", align="left", height=24, enableBackground=True, width=1,
                     backgroundColor=STATUS_BG["info"])
    btn = cmds.button(label="Copy error report", height=22, manage=bool(_last_error["text"]),
                      command=copy_error)
    cmds.setParent("..")
    _status_controls.append(ctrl)
    _error_buttons.append(btn)
    return form


def status(message, level="info"):
    """Show a message on every open Gus_Rigtool status line."""
    alive = []
    for ctrl in _status_controls:
        try:
            if cmds.text(ctrl, exists=True):
                cmds.text(ctrl, edit=True, label="  " + message,
                          backgroundColor=STATUS_BG.get(level, STATUS_BG["info"]))
                alive.append(ctrl)
        except RuntimeError:
            pass
    _status_controls[:] = alive


# ---------------------------------------------------------------------------
# what's new
# ---------------------------------------------------------------------------

def whats_new(*_):
    """The short summary (WHATSNEW.txt), else the changelog, in a window you can scroll and copy from."""
    import gus_rigtool
    text = None
    for name in ("WHATSNEW.txt", "CHANGELOG.txt"):
        try:
            with open(os.path.join(gus_rigtool.ROOT, name), "r") as f:
                text = f.read()
            break
        except (IOError, OSError):
            continue
    report_window("Gus_Rigtool %s - What's new" % gus_rigtool.__version__, text or "No changelog found.")


# ---------------------------------------------------------------------------
# dockable panels
# ---------------------------------------------------------------------------

def panel_name(key):
    return "gusrig_%s_panel" % key


def _label(key):
    if key == MAIN_KEY:
        return "Gus_Rigtool"
    from gus_rigtool import registry
    return "Gus_Rigtool: " + registry.get(key)[1]


def _form_name(key):
    return panel_name(key) + "_form"


def _remember_width(key):
    from gus_rigtool.core import utils

    def run(*_):
        try:
            w = cmds.workspaceControl(panel_name(key), query=True, width=True)
            if w and w > 200:
                widths = utils.load_setting("panelWidths", {})
                widths[key] = int(w)
                utils.save_setting("panelWidths", widths)
        except RuntimeError:
            pass
    return run


def open_panel(key, width=None):
    """Open (or reopen) a tool - or the main window, key 'main' - as a dockable panel."""
    from gus_rigtool.core import utils
    name = panel_name(key)
    if cmds.workspaceControl(name, exists=True):
        cmds.deleteUI(name)
    try:                                        # forget any old saved state (old build script)
        if cmds.workspaceControlState(name, exists=True):
            cmds.workspaceControlState(name, remove=True)
    except (RuntimeError, AttributeError, TypeError):
        pass
    width = width or utils.load_setting("panelWidths", {}).get(key, 430)
    # Python, because the panel is created from Python: Maya runs it to build the panel,
    # and again when it restores a docked panel at startup.
    script = "import gus_rigtool.core.ui as _gui; _gui.fill_panel(%r)" % key
    cmds.workspaceControl(name, label=_label(key), floating=True, retain=False,
                          initialWidth=width, minimumWidth=280, uiScript=script,
                          closeCommand=_remember_width(key))
    if not cmds.formLayout(_form_name(key), exists=True):
        fill_panel(key)                         # build now if Maya did not run the script
    return name


def _attach(form, top, body, bar):
    cmds.formLayout(form, edit=True,
                    attachForm=[(top, "top", 0), (top, "left", 0), (top, "right", 0),
                                (body, "left", 0), (body, "right", 0),
                                (bar, "left", 0), (bar, "right", 0), (bar, "bottom", 0)],
                    attachControl=[(body, "top", 2, top), (body, "bottom", 2, bar)])


def _guide(*_):
    from gus_rigtool.tools import guide
    guide.show()


def _update(*_):
    from gus_rigtool.core import updater
    try:
        updater.install_dialog()
    except Exception as e:
        report_error(e, "update")


def fill_panel(key):
    """Build a panel's content (also called by Maya when it restores a docked panel)."""
    import gus_rigtool
    from gus_rigtool import registry
    if cmds.formLayout(_form_name(key), exists=True):
        return                                  # already built
    cmds.setParent(panel_name(key))
    form = cmds.formLayout(_form_name(key))
    if key == MAIN_KEY:
        top = cmds.columnLayout(adjustableColumn=True, backgroundColor=HEADER_BG, rowSpacing=3)
        simple = view_mode() == "simple"
        header("Gus_Rigtool %s" % gus_rigtool.__version__, "Home shows where you are and the next step. Every "
               "action is one undo.",
               extra_button=[("Guide", _guide, "A step-by-step guide to rigging with Gus_Rigtool."),
                             ("Full view" if simple else "Simple view",
                              lambda *_: set_view_mode("full" if simple else "simple"),
                              "Simple: advanced sections folded away. Full: everything as you left it."),
                             ("What's new", whats_new, "What changed in this version."),
                             ("Update...", _update, "Install a newer Gus_Rigtool zip (it restarts by itself).")])
        search_row()
        my_tools_row()
        cmds.setParent(form)
        body = cmds.tabLayout(_cat_tabs(), innerMarginWidth=2, innerMarginHeight=2)
        cats = []
        for cat, cat_label, keys in registry.CATEGORIES:
            cmds.setParent(body)
            inner = cmds.tabLayout(_tool_tabs(cat), innerMarginWidth=2, innerMarginHeight=2)
            children = []
            for tkey in keys:
                _k, label, _mod, subtitle = registry.get(tkey)
                cmds.setParent(inner)
                child = cmds.scrollLayout(childResizable=True)
                col = cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
                header(label, subtitle, pop_key=tkey if tkey != "home" else None)
                where_line(tkey)
                _lazy[tkey] = (cmds.layout(col, query=True, fullPathName=True), "m_%s_" % tkey)   # built when shown
                _page_cols[tkey] = (cmds.layout(child, query=True, fullPathName=True), _lazy[tkey][0])
                children.append((child, label))
            cmds.tabLayout(inner, edit=True, tabLabel=children)
            _remember_tab(inner, "mainTab2_" + cat)
            cats.append((inner, cat_label))
        cmds.tabLayout(body, edit=True, tabLabel=cats)
        _remember_tab(body, "mainCategory2")
        build_visible_page()
        _index_state["stale"] = True
        _build_rest_later()
    else:
        _key, label, _mod, subtitle = registry.get(key)
        top = header(label, subtitle)
        body = cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        where_line(key)
        _build_tool(key, "p_%s_" % key)
    cmds.setParent(form)
    bar = status_line()
    _attach(form, top, body, bar)


def where_line(key):
    """'Step 3 of 5 - before: ... next: ...' under a tool's title, with buttons to the steps around it."""
    from gus_rigtool import registry
    stage = registry.TOOL_STAGE.get(key)
    stages = registry.STAGES
    if key == "home":
        return None
    row_ = cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, backgroundColor=(0.21, 0.24, 0.27),
                          columnAttach=[(1, "both", 4), (2, "both", 2), (3, "both", 2)])
    first, last = stage if isinstance(stage, tuple) else (stage, stage)
    if stage and first != last:
        text = "  Steps %d-%d of %d: %s - place the guides, then build the rig." % (
            first, last, len(stages), " and ".join(s[1] for s in stages[first - 1:last]))
    elif stage:
        text = "  Step %d of %d: %s - %s" % (first, len(stages), stages[first - 1][1], stages[first - 1][2])
    else:
        text = "  Toolbox: a helper you can use at any step."
    cmds.text(label=text, align="left", font="smallPlainLabelFont", backgroundColor=(0.21, 0.24, 0.27),
              annotation=text.strip(), width=1)          # 5.4.0: this line made every workflow page ~650 px wide
    if not stage:
        cmds.button(label="Home", height=18, annotation="The Home page: every step and what's next.",
                    command=lambda *_: go_to_tool("home"))
        cmds.button(label="Next step  >", height=18, annotation="The next step for this scene (Home knows it).",
                    command=_next_step)
        cmds.setParent("..")
        return row_
    prev_ = stages[first - 2] if first > 1 else None
    next_ = stages[last] if last < len(stages) else None
    for st, arrow in ((prev_, "<  %s"), (next_, "%s  >")):
        if st:
            cmds.button(label=arrow % st[1], height=18, annotation="Go to step: %s - %s" % (st[1], st[2]),
                        command=lambda *_, s=st: go_to_tool(s[3], s[4]))
        else:
            cmds.button(label="Home", height=18, annotation="The Home page: every step and what's next.",
                        command=lambda *_: go_to_tool("home"))
    cmds.setParent("..")
    return row_


def _next_step(*_):
    """Open the step this scene needs next (Home when it's all done)."""
    from gus_rigtool import registry
    from gus_rigtool.tools import home
    nxt = home.state()[1]
    for key, _t, _d, tool, sec in registry.STAGES:
        if key == nxt:
            return go_to_tool(tool, sec)
    return go_to_tool("home")


def go_to_tool(key, section_label=None):
    """Show a tool in the main window (opening it if needed), with one of its sections open."""
    from gus_rigtool import registry
    if not cmds.formLayout(_form_name(MAIN_KEY), exists=True):
        open_panel(MAIN_KEY)
    cat, _label = registry.category_of(key)
    if not cat or not cmds.tabLayout(_cat_tabs(), exists=True):
        return False
    cats = [c for c, _l, _k in registry.CATEGORIES]
    cmds.tabLayout(_cat_tabs(), edit=True, selectTabIndex=cats.index(cat) + 1)
    keys = dict((c, k) for c, _l, k in registry.CATEGORIES)[cat]
    inner = _tool_tabs(cat)
    if cmds.tabLayout(inner, exists=True):
        cmds.tabLayout(inner, edit=True, selectTabIndex=keys.index(key) + 1)
    build_page(key)
    if section_label:
        if not _index or _index_state["stale"]:
            index_search()
        path = find_section(key, section_label)
        if path:
            go_to(path)
    try:
        cmds.workspaceControl(panel_name(MAIN_KEY), edit=True, restore=True)
    except RuntimeError:
        pass
    flush_shown()
    return True


def _plain_title(label):
    """'2.  Bind   (advanced)' -> 'Bind'."""
    import re
    return re.sub(r"^\d+\.?\s+", "", label.replace("(advanced)", "")).strip()


def find_section(key, section_label):
    """UI path of a tool's section in the main window: same title first, then one starting with it."""
    from gus_rigtool import registry
    tool_label = registry.get(key)[1]
    frames = []
    for _hay, label, where, path in _index:
        if (" > %s" % tool_label) not in where:
            continue
        try:
            if cmds.objectTypeUI(path) == "frameLayout":
                frames.append((_plain_title(label), path))
        except RuntimeError:
            continue
    for title, path in frames:
        if title == section_label:
            return path
    for title, path in frames:
        if title.startswith(section_label):
            return path
    return None


# ---------------------------------------------------------------------------
# main window pages: built when first shown (5.0.0 - opening built all 26 pages and took ~5 s)
# ---------------------------------------------------------------------------

_lazy = {}           # tool key -> (its page's column layout, prefix) while not built yet
_page_cols = {}      # tool key -> (its scrollLayout, its column) in the main window (5.4.0: width check)


def page_widths():
    """[(tool key, page width, visible width)] for every page of the main window, each shown in turn (Maya check:
    a page wider than the window gets a horizontal scroll bar and cut-off buttons)."""
    out = []
    for key, (scroll, col) in list(_page_cols.items()):
        try:
            go_to_tool(key)
            cmds.refresh(force=True)
            out.append((key, cmds.layout(col, query=True, width=True),
                        cmds.scrollLayout(scroll, query=True, scrollAreaWidth=True)))
        except Exception:
            continue
    return out
_index_state = {"stale": True}


def page_built(key):
    return key not in _lazy


def build_page(key):
    """Build a main-window page now if it's still waiting. True when it was built now."""
    got = _lazy.pop(key, None)
    if not got:
        return False
    col, prefix = got
    if not cmds.layout(col, exists=True):
        return False
    before = len(_children(col))
    hidden = visible_tool() != key
    here = cmds.setParent(query=True)
    try:
        cmds.setParent(col)
        _build_tool(key, prefix)
    finally:
        try:
            cmds.setParent(here)
        except RuntimeError:
            pass
    if hidden:                                           # 5.6.1: built again when it's first shown
        _built_hidden[key] = (col, prefix, before)
    _index_state["stale"] = True
    return True


def visible_tool():
    """The tool key of the page shown in the main window, or None."""
    from gus_rigtool import registry
    try:
        ci = cmds.tabLayout(_cat_tabs(), query=True, selectTabIndex=True)
        cat, _l, keys = registry.CATEGORIES[ci - 1]
        ti = cmds.tabLayout(_tool_tabs(cat), query=True, selectTabIndex=True)
        return keys[ti - 1]
    except (RuntimeError, TypeError, IndexError, ValueError):
        return None


_built_hidden = {}   # 5.6.1: tool key -> (column, prefix, children before) for pages built while their tab was hidden


def build_visible_page(*_):
    key = visible_tool()
    if not key:
        return False
    built = build_page(key)
    if key in _built_hidden:
        rebuild_page(key)
    return built


def rebuild_page(key):
    """5.6.1: a page built while its tab was hidden (in the background, or for the search) is built again the first
    time it's shown - Maya sizes a page it can't see wrong, and cut off what didn't fit (Make controls,
    Constraints > 3, Connect > 3). Built while visible, it's sized like any page built in front of you."""
    got = _built_hidden.pop(key, None)
    if not got:
        return False
    col, prefix, before = got
    if not cmds.layout(col, exists=True):
        return False
    for kid in _children(col)[before:]:
        try:
            cmds.deleteUI(kid)
        except RuntimeError:
            pass
    here = cmds.setParent(query=True)
    try:
        cmds.setParent(col)
        _build_tool(key, prefix)
    finally:
        try:
            cmds.setParent(here)
        except RuntimeError:
            pass
    _index_state["stale"] = True
    return True


def build_all_pages():
    """Every page still waiting, now (search, checks)."""
    n = 0
    for key in list(_lazy):
        n += bool(build_page(key))
    return n


def _build_rest_later():
    """The other pages, one at a time while Maya is idle (the window is usable meanwhile)."""
    def one():
        if not _lazy:
            return
        try:
            build_page(next(iter(_lazy)))
        except Exception as e:
            report_error(e, "page")
        if _lazy:
            cmds.evalDeferred(one, lowestPriority=True)
    try:
        cmds.evalDeferred(one, lowestPriority=True)
    except (RuntimeError, TypeError):
        pass


FIT_KINDS = ("text", "button", "checkBox")


def _in_adjustable_column(par=None):
    """In a page's column (a Gus_Rigtool panel - not a dialog window that sizes itself from its contents)."""
    try:
        par = par or cmds.setParent(query=True)
        if not ("gusrig_" in str(par) and "_panel" in str(par)) and _view.get("tool") is None:
            return False
        if cmds.objectTypeUI(par) != "columnLayout":
            return False
        return bool(cmds.columnLayout(par, query=True, adjustableColumn=True))
    except Exception:
        return False


def wrap(text, lines=2):
    """A label broken into lines of a narrow panel's width (for a text whose label changes later)."""
    import textwrap
    out = []
    for part in str(text).split("\n"):
        out += textwrap.wrap(part, NOTE_CHARS) or [""]
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][:NOTE_CHARS - 3] + "..."
    return "\n".join(out)


LABEL_CHARS = 52         # a button / check box label longer than this is shortened (the full text in its tooltip)


def _fitting(fn, kind):
    """A text / button / check box made in a page's column never makes the page wider than a narrow window.
    5.4.1: no more width=1 - Maya stretches a 1-pixel control to the column only in a section that is open when
    the page is built; in one folded at first and opened later the buttons stayed 1 pixel wide (invisible - the
    Ribbon page's 'Check / fix curves', 'Follicles'...). Now: a long one-line text is broken into lines (its height
    fixed up front), a too-long button / check box label is shortened with its full text in the tooltip."""
    import textwrap

    def make(*a, **k):
        if kind == "text" and a and (k.get("edit") or k.get("e")) and ("label" in k or "l" in k):
            return fn(*a, **_fit_edit(fn, a[0], k))           # 5.4.2: a text whose label changes later
        if a and any(k.get(f) for f in ("query", "q", "edit", "e", "exists", "ex")):
            return fn(*a, **k)
        if "width" in k or "w" in k or not _in_adjustable_column(k.get("parent") or k.get("p")):
            return fn(*a, **k)
        k = dict(k)
        lkey = "label" if "label" in k else ("l" if "l" in k else None)
        label = str(k.get(lkey, "") or "") if lkey else ""
        if kind == "text":
            if not (k.get("wordWrap") or k.get("ww")) and "height" not in k and "h" not in k \
                    and len(label) > NOTE_CHARS:
                lines = []
                for part in label.split("\n"):
                    lines += textwrap.wrap(part, NOTE_CHARS) or [""]
                k[lkey] = "\n".join(lines)
                k["height"] = len(lines) * NOTE_LINE + 4
                k.setdefault("annotation", label)
        elif len(label) > LABEL_CHARS:
            k[lkey] = label[:LABEL_CHARS - 1].rstrip() + "..."
            if not (k.get("annotation") or k.get("ann")):
                k["annotation"] = label
        return fn(*a, **k)
    make._gus_fit = True
    return make


_relayout_busy = [False]


FRAME_TITLE = 20         # a section's title bar (px) - what Maya reports for a folded section
PAGE_PAD = 12


def _kind(c):
    try:
        return cmds.objectTypeUI(c)
    except RuntimeError:
        return ""


def _q(fn, c, **k):
    try:
        return fn(c, query=True, **k)
    except (RuntimeError, TypeError, ValueError):
        return None


def natural_height(c, fixes):
    """5.6.2: how tall a layout really needs to be, from its contents (Maya's own measure goes stale: Make
    controls' page stayed 213 px with 260 px in it - the rest was cut off). Columns found too short or too tall are
    added to fixes as (column, height)."""
    kind = _kind(c)
    if not kind:
        return 0
    lay = cmds.layout(c, exists=True)
    if not (_q(cmds.layout if lay else cmds.control, c, manage=True)):
        return 0
    if kind == "frameLayout":
        if _q(cmds.frameLayout, c, collapse=True):
            return _q(cmds.frameLayout, c, height=True) or FRAME_TITLE
        kids = _children(c)
        inner = natural_height(kids[0], fixes) if kids else 0
        margin = _q(cmds.frameLayout, c, marginHeight=True) or 0
        return FRAME_TITLE + 2 * margin + inner + 4
    if kind == "columnLayout":
        kids = [natural_height(k, fixes) for k in _children(c)]
        kids = [h for h in kids if h]
        spacing = _q(cmds.columnLayout, c, rowSpacing=True) or 0
        need = sum(kids) + spacing * max(0, len(kids) - 1)
        have = _q(cmds.columnLayout, c, height=True) or 0
        if need and abs(have - need) > 2:
            fixes.append((c, need))
        return need
    h = _q(cmds.layout if lay else cmds.control, c, height=True)
    return h or 0


def fit_page(page):
    """Every column on the page (and the page itself) set to what its contents need. Returns how many changed."""
    if not cmds.layout(page, exists=True):
        return 0
    fixes = []
    need = natural_height(page, fixes)
    n = 0
    for col, h in fixes:
        try:
            cmds.columnLayout(col, edit=True, height=h + (PAGE_PAD if col == page else 0))
            n += 1
        except RuntimeError:
            continue
    if need and not any(col == page for col, _h in fixes):
        try:
            cmds.columnLayout(page, edit=True, height=need + PAGE_PAD)
        except RuntimeError:
            pass
    return n


def _page_of(ctrl):
    """The page (the column right under the scrollLayout) a control is on, or None."""
    try:
        path = cmds.control(ctrl, query=True, fullPathName=True) if cmds.control(ctrl, exists=True) else \
            cmds.layout(ctrl, query=True, fullPathName=True)
    except RuntimeError:
        return None
    parts = path.split("|")
    for i in range(len(parts) - 1, 0, -1):
        if _kind("|".join(parts[:i])) == "scrollLayout":
            return "|".join(parts[:i + 1])
    return None


_refit_queued = [False]


def refit_visible():
    """5.6.4: after any button / field of a page: the page shown in the main window fitted to its contents again
    (deferred, once however many callbacks ran - the Checker's results came in after the click and were cut off)."""
    if _refit_queued[0] or _view.get("tool"):
        return

    def go():
        _refit_queued[0] = False
        try:
            key = visible_tool()
            got = _page_cols.get(key) if key else None
            if got and cmds.layout(got[1], exists=True):
                fit_page(got[1])
        except Exception:
            pass
    try:
        cmds.evalDeferred(go)
        _refit_queued[0] = True
    except (RuntimeError, AttributeError):
        pass


def relayout(ctrl):
    """5.6.2: the page around ctrl sized to its contents by the tool itself (after a section opens / closes, or a
    page is built) - deferred, so Maya has finished the click first. (5.4.2-5.6.1 asked Maya to measure again by
    closing / opening sections and hiding the page: it didn't hold - pages and sections stayed cut off.)"""
    if _relayout_busy[0]:
        return

    def go():
        _relayout_busy[0] = True
        try:
            page = _page_of(ctrl)
            if page:
                fit_page(page)
        except Exception:
            pass
        finally:
            _relayout_busy[0] = False
    try:
        cmds.evalDeferred(go)
    except (RuntimeError, AttributeError):
        pass


def _framing(fn):
    """A section (frameLayout) made in a page re-measures the page when it opens or closes (5.4.2)."""
    def make(*a, **k):
        if a and any(k.get(f) for f in ("query", "q", "edit", "e", "exists", "ex")):
            return fn(*a, **k)
        frame = fn(*a, **k)
        if k.get("collapsable") or k.get("cll"):
            try:
                extra_e, extra_c = k.get("expandCommand") or k.get("ec"), k.get("collapseCommand") or k.get("cc")

                def on_open(*x):
                    if extra_e:
                        extra_e(*x) if callable(extra_e) else None
                    relayout(frame)

                def on_close(*x):
                    if extra_c:
                        extra_c(*x) if callable(extra_c) else None
                    relayout(frame)
                fn(frame, edit=True, expandCommand=on_open, collapseCommand=on_close)
            except (RuntimeError, TypeError):
                pass
        return frame
    make._gus_fit = True
    return make


def _fit_edit(fn, ctrl, k):
    """A new label on an existing page text: broken into the lines its height has room for (the rest '...', the
    whole text in the tooltip) - so a long info line can't widen the page after a click. Texts that wrap
    themselves, or are given a fixed width, are left alone."""
    k = dict(k)
    lkey = "label" if "label" in k else "l"
    label = str(k[lkey] or "")
    try:
        if len(label) <= NOTE_CHARS + 2 or fn(ctrl, query=True, wordWrap=True):
            return k
        h = fn(ctrl, query=True, height=True) or 0
    except (RuntimeError, TypeError):
        return k
    lines = max(1, int((h - 2) // NOTE_LINE)) if h else 1
    k[lkey] = wrap(label, lines)
    if lines > 1 and h < lines * NOTE_LINE:
        k["height"] = h
    if not (k.get("annotation") or k.get("ann")):
        k["annotation"] = label
    return k


class _Fit(object):
    """While a page is built, its texts / buttons / check boxes fit the window (see _fitting), and its sections
    re-measure the page when they open / close (see _framing)."""
    def __enter__(self):
        self.saved = {}
        for kind in FIT_KINDS + ("frameLayout",):
            fn = getattr(cmds, kind, None)
            if fn is not None and not getattr(fn, "_gus_fit", False):
                self.saved[kind] = fn
                setattr(cmds, kind, _framing(fn) if kind == "frameLayout" else _fitting(fn, kind))
        return self

    def __exit__(self, *exc):
        for kind, fn in self.saved.items():
            setattr(cmds, kind, fn)
        return False


def _build_tool(key, prefix):
    """Build one tool; if it fails, show the error in its place instead of breaking the window."""
    from gus_rigtool import registry
    start = cmds.setParent(query=True)
    _view["tool"] = key
    try:
        with _Fit():
            registry.builder(key)(prefix)
        relayout(start)                                # 5.4.2: measured again once Maya has drawn it
    except Exception as e:
        report_error(e, prefix)
        try:                                   # back to the tool's own page: a broken layout can't stop the window
            cmds.setParent(start)
            cmds.text(label="  This tool could not open: %s" % e, align="left", wordWrap=True)
        except Exception:
            pass
    _view["tool"] = None
    try:
        colour_buttons(start)
    except RuntimeError:
        pass


def _children(layout):
    """Full UI paths of a layout's children."""
    try:
        full = cmds.layout(layout, query=True, fullPathName=True) or layout
        return [full + "|" + k for k in (cmds.layout(layout, query=True, childArray=True) or [])]
    except RuntimeError:
        return []


def walk(layout):
    """Every control under a layout (full UI paths), depth first."""
    out = []
    for kid in _children(layout):
        out.append(kid)
        if cmds.layout(kid, exists=True):
            out += walk(kid)
    return out


def colour_buttons(layout):
    """Buttons that delete something are red, everywhere (unless they have a colour already)."""
    for c in walk(layout):
        if cmds.objectTypeUI(c) != "button":
            continue
        label = (cmds.button(c, query=True, label=True) or "").lower()
        if any(w in label for w in DANGER_WORDS):
            cmds.button(c, edit=True, backgroundColor=DANGER_BG)


# ---------------------------------------------------------------------------
# main window: categories, remembered tabs, search
# ---------------------------------------------------------------------------

def _cat_tabs():
    return "gusrig_main_categories"


def _tool_tabs(cat):
    return "gusrig_main_tools_" + cat


def _remember_tab(tabs, key):
    from gus_rigtool.core import utils
    index = utils.load_setting(key, 1)
    count = cmds.tabLayout(tabs, query=True, numberOfChildren=True)
    if isinstance(index, int) and isinstance(count, int) and 1 <= index <= count:
        cmds.tabLayout(tabs, edit=True, selectTabIndex=index)

    def remember(*_):
        try:
            utils.save_setting(key, cmds.tabLayout(tabs, query=True, selectTabIndex=True))
        except RuntimeError:
            pass
        build_visible_page()
        flush_shown()
    cmds.tabLayout(tabs, edit=True, changeCommand=remember)


_index = []          # [(searchable text, shown label, where, UI path)]
_SEARCH_KINDS = {"button": "button", "checkBox": "checkBox", "frameLayout": "frameLayout",
                 "radioButtonGrp": "radioButtonGrp", "optionMenu": None, "text": "text"}


def _ui_label(c, kind):
    try:
        if kind == "frameLayout":
            return cmds.frameLayout(c, query=True, label=True)
        if kind == "radioButtonGrp":
            return cmds.radioButtonGrp(c, query=True, label=True)
        if kind == "text":
            return cmds.text(c, query=True, label=True)
        return getattr(cmds, kind)(c, query=True, label=True)
    except (RuntimeError, TypeError):
        return ""


def _annotation(c):
    try:
        return cmds.control(c, query=True, annotation=True) or ""
    except RuntimeError:
        return ""


def index_search():
    """Remember every button, option and section of the main window, for the search box."""
    from gus_rigtool import registry
    build_all_pages()
    _index_state["stale"] = False
    del _index[:]
    for cat, cat_label, keys in registry.CATEGORIES:
        inner = _tool_tabs(cat)
        if not cmds.tabLayout(inner, exists=True):
            continue
        for kid, tkey in zip(_children(inner), keys):
            tool_label = registry.get(tkey)[1]
            _index.append((tool_label.lower() + " " + registry.get(tkey)[3].lower(), tool_label,
                           "%s > %s" % (cat_label, tool_label), kid))
            section = ""
            for c in walk(kid):
                kind = cmds.objectTypeUI(c)
                if kind not in _SEARCH_KINDS:
                    continue
                label = (_ui_label(c, kind) or "").strip()
                if kind == "frameLayout":
                    section = label
                if not label or len(label) > 120 or (kind == "text" and len(label) < 4):
                    continue
                where = "%s > %s%s" % (cat_label, tool_label, (" > " + section) if section and section != label else "")
                _index.append(((label + " " + _annotation(c)).lower(), label, where, c))


def search(text):
    """[(label, where, UI path)] best matches first."""
    words = [w for w in text.lower().split() if w]
    if not words:
        return []
    if _index_state["stale"] or not _index:          # pages built since (or not yet): read them again
        index_search()
    scored = []
    for hay, label, where, path in _index:
        if all(w in hay for w in words):
            score = (0 if label.lower().startswith(words[0]) else 1, len(label))
            scored.append((score, label, where, path))
    scored.sort()
    seen, out = set(), []
    for _s, label, where, path in scored:
        if (label, where) not in seen:
            seen.add((label, where))
            out.append((label, where, path))
    return out[:40]


def go_to(path):
    """Show a control of the main window: its category, tool and sub-tabs, open sections."""
    parts = path.split("|")
    for i in range(len(parts) - 1):
        here = "|".join(parts[:i + 1])
        try:
            kind = cmds.objectTypeUI(here)
        except RuntimeError:
            continue
        if kind == "tabLayout":
            kids = cmds.tabLayout(here, query=True, childArray=True) or []
            if parts[i + 1] in kids:
                cmds.tabLayout(here, edit=True, selectTabIndex=kids.index(parts[i + 1]) + 1)
        elif kind == "frameLayout":
            cmds.frameLayout(here, edit=True, collapse=False)
    try:
        if cmds.objectTypeUI(path) == "frameLayout":
            cmds.frameLayout(path, edit=True, collapse=False)
    except RuntimeError:
        pass


SEARCH_WIN = "gusrig_search_window"


def run_search(*_):
    text = cmds.textField("gusrig_search_field", query=True, text=True) if \
        cmds.textField("gusrig_search_field", exists=True) else ""
    index_search()                       # fresh: the settings form changes with the picked module
    hits = search(text)
    if not hits:
        status("Nothing found for '%s'." % text, "warn")
        return
    if len(hits) == 1:
        go_to(hits[0][2])
        status("Showing: %s  (%s)" % (hits[0][0], hits[0][1]), "info")
        return
    if cmds.window(SEARCH_WIN, exists=True):
        cmds.deleteUI(SEARCH_WIN)
    win = cmds.window(SEARCH_WIN, title="Gus_Rigtool - search: %s" % text, widthHeight=(520, 320))
    cmds.formLayout("gusrig_search_form")
    lst = cmds.textScrollList("gusrig_search_list", font="fixedWidthFont",
                              append=["%-32s %s" % (label[:32], where) for label, where, _p in hits])

    def pick(*_):
        i = (cmds.textScrollList(lst, query=True, selectIndexedItem=True) or [0])[0]
        if 1 <= i <= len(hits):
            go_to(hits[i - 1][2])
            status("Showing: %s  (%s)" % (hits[i - 1][0], hits[i - 1][1]), "info")
    cmds.textScrollList(lst, edit=True, selectCommand=pick, doubleClickCommand=pick)
    cmds.formLayout("gusrig_search_form", edit=True,
                    attachForm=[(lst, s, 4) for s in ("top", "left", "right", "bottom")])
    cmds.showWindow(win)


def my_tools():
    """5.4.0: the tools pinned under the search box (Settings > My tools, or its + button)."""
    from gus_rigtool import registry
    from gus_rigtool.core import utils
    keys = utils.load_setting("myTools", None) or list(registry.MY_TOOLS)
    out = []
    for k in keys:
        try:
            registry.get(k)
            out.append(k)
        except Exception:
            pass
    return out


def my_tools_row():
    """Your most used tools, one click away on every tab, then Map (where everything is) and + (choose them)."""
    from gus_rigtool import registry
    cmds.flowLayout("gusrig_mytools", wrap=True, columnSpacing=2, backgroundColor=HEADER_BG, height=48,
                    width=1)
    for k in my_tools():
        label = registry.get(k)[1]
        cmds.button(label=label, height=21, width=len(label) * 7 + 14, annotation="Open %s." % label,
                    command=lambda *_, t=k: go_to_tool(t))
    cmds.button(label="Map", height=21, width=40, backgroundColor=(0.33, 0.45, 0.55),
                annotation="Where everything is: every tab and page.", command=lambda *_: show_map())
    cmds.button(label="+", height=21, width=24, annotation="Choose the tools pinned here.",
                command=lambda *_: edit_my_tools())
    cmds.setParent("..")


def edit_my_tools():
    from gus_rigtool import registry
    from gus_rigtool.core import utils
    win = "gusRigMyToolsWin"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title="Gus_Rigtool - My tools", widthHeight=(300, 460))
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2, columnAttach=("both", 8))
    cmds.text(label="Pinned under the search box, on every tab:", align="left")
    mine = set(my_tools())
    boxes = []
    for k, label, _m, desc in registry.TOOLS:
        if k == "home":
            continue
        boxes.append((k, cmds.checkBox(label=label, value=k in mine, annotation=desc)))

    def save(*_):
        utils.save_setting("myTools", [k for k, b in boxes if cmds.checkBox(b, query=True, value=True)])
        cmds.deleteUI(win)
        cmds.evalDeferred(rebuild_open)

    def reset(*_):
        utils.save_setting("myTools", list(registry.MY_TOOLS))
        cmds.deleteUI(win)
        cmds.evalDeferred(rebuild_open)
    cmds.button(label="Save", height=28, command=save)
    cmds.button(label="Back to the defaults", command=reset)
    cmds.showWindow(win)


MOVED_540 = [
    ("Limits", "Controls > Attributes", "Controls > Behaviour"),
    ("In front of the mesh", "Controls > Make controls", "Controls > Behaviour"),
    ("Stop at the body", "Controls > Make controls", "Controls > Behaviour"),
    ("Joints (chains on curves / edges)", "Toolbox", "Build > Joints"),
    ("SDK (mirror / copy driven keys)", "Controls", "Connect > SDK"),
    ("Checker, Check this scene, Repair, Organize", "Finish tab", "Check tab (renamed)"),
]


def map_text():
    """Every tab and its pages, with what each is for, and what moved in 5.4.0."""
    from gus_rigtool import registry
    lines = ["WHERE EVERYTHING IS (Gus_Rigtool tabs > pages)", ""]
    for _cat, label, keys in registry.CATEGORIES:
        lines.append(label.upper())
        for k in keys:
            _k, name, _m, desc = registry.get(k)
            lines.append("  %-15s %s" % (name, desc))
        lines.append("")
    lines.append("MOVED IN 5.4.0")
    for what, old, new in MOVED_540:
        lines.append("  %-44s %s  ->  %s" % (what, old, new))
    lines += ["", "Under the search box: My tools (your most used - + to choose them).",
              "Search: type what you want to do (limit, mirror weights, jiggle...) and press Enter: every page, "
              "section, button and option that matches.",
              "Home > For what you have selected: the likely next things for your selection."]
    return "\n".join(lines)


def show_map():
    return report_window("Gus_Rigtool - map", map_text(), win="gusRigMapWin")


def search_row():
    """The search box of the main window."""
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, backgroundColor=HEADER_BG,
                   columnAttach=[(1, "both", 4), (2, "both", 4)])
    cmds.textField("gusrig_search_field", placeholderText="What do you want to do? (mirror weights, space switch, "
                   "rename...)",
                   enterCommand=lambda *_: run_search(), alwaysInvokeEnterCommandOnReturn=True,
                   annotation="Type a word and press Enter: every tool, option and button that matches.")
    cmds.button(label="Find", width=60, command=lambda *_: run_search())
    cmds.setParent("..")


def rebuild_open():
    """Rebuild every open Gus_Rigtool panel (after settings change). Run deferred."""
    from gus_rigtool import registry
    for key in [MAIN_KEY] + [t[0] for t in registry.TOOLS] + [p[0] for p in getattr(registry, "PANELS", [])]:
        name = panel_name(key)
        if not cmds.workspaceControl(name, exists=True):
            continue
        if cmds.formLayout(_form_name(key), exists=True):
            cmds.deleteUI(_form_name(key))
        fill_panel(key)


def close_all():
    from gus_rigtool import registry
    for key in [MAIN_KEY] + [t[0] for t in registry.TOOLS] + [p[0] for p in getattr(registry, "PANELS", [])]:
        name = panel_name(key)
        if cmds.workspaceControl(name, exists=True):
            cmds.deleteUI(name)
