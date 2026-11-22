"""
Checker: looks for common rig problems and fixes the safe ones.

    import gus_rigtool.main as gr; gr.show_tool("checker")

Scope: the selected hierarchies, or the whole scene when nothing is selected.
Each check shows FAIL / WARN / INFO / PASS with a count. "Select" selects the problems,
"Fix" appears only when the fix is safe (it never moves skinned geometry or changes how
things deform). Every fix is one undo.
"""

from gus_rigtool.core.rig_checks import *  # noqa: F401,F403 - the checks (5.7.10: their own file)
from gus_rigtool.core.rig_checks import _roots
# (after the checks: the page's own cmds, not theirs)
from gus_rigtool.newui import proxy
from gus_rigtool.newui.proxy import cmds   # noqa: F811 - maya.cmds; the new window's fields by name (5.7.6)

from gus_rigtool.core import ui, utils

TOOL = "Checker"
SETTINGS_KEY = "checker"
SEVERITY_BG = {
    "FAIL": (0.55, 0.16, 0.16),
    "WARN": (0.55, 0.38, 0.10),
    "INFO": (0.22, 0.32, 0.45),
    "PASS": (0.20, 0.36, 0.22),
    "ERROR": (0.40, 0.40, 0.40),
}

_P, N, _w, _guard = ui.tool_helpers("p_checker_", TOOL)
_results = {}            # prefix -> {check id: [nodes]}


# ===========================================================================
# window
# ===========================================================================

def _ui():
    o = {"influence_limit": cmds.intField(N("Limit"), query=True, value=True),
         "twist_limit": cmds.intField(N("TwistLimit"), query=True, value=True)}
    for c in CHECKS:
        o["on_" + c[0]] = cmds.checkBox(N("On_" + c[0]), query=True, value=True)
    return o


def _light():
    roots = _roots()
    if roots:
        return "ok", "Scope: %s. Run checks." % ui.selection_summary(roots, "hierarchie")
    return "ok", "Scope: the whole scene (nothing selected). Run checks."


def _save(*_):
    try:
        utils.save_setting(SETTINGS_KEY, _ui())
    except RuntimeError:
        pass


def run(*_):
    o = _ui()
    _save()
    roots = _roots()
    results = run_checks(o, roots)
    _results[_P["p"]] = results
    _show(results)
    fails = sum(1 for s, _n in results.values() if s == "FAIL")
    warns = sum(1 for s, _n in results.values() if s == "WARN")
    where = "%d selected hierarchies" % len(roots) if roots else "the whole scene"
    level = "warn" if fails or warns else "ok"
    utils.info(TOOL, "%d checks on %s: %d fail, %d warning." % (len(results), where, fails, warns), level)


_repairs = {}


def find_repairs(*_):
    from gus_rigtool.core import repair
    items = repair.find()
    _repairs[_P["p"]] = items
    col = N("Repairs")

    def fill():
        for child in cmds.columnLayout(col, query=True, childArray=True) or []:
            cmds.deleteUI(child)
        cmds.setParent(col)
        if not items and not repair.ERRORS:
            cmds.text(label="Nothing to repair.", align="left")
        for what, why in repair.ERRORS:              # 5.6.29: a check that couldn't run says so
            cmds.text(label="  couldn't check: %s - %s" % (what, why), align="left", font="smallPlainLabelFont")
        for it in items:
            cmds.checkBox(N("Rep_" + it.id), label="%s  (%d)" % (it.label, it.count), value=True,
                          annotation=it.detail)
            cmds.text(label="      " + it.detail, align="left", font="smallPlainLabelFont")
        cmds.setParent("..")
    proxy.refill(col, fill)                          # 5.7.6: in the new window, drawn on its page
    utils.info(TOOL, "%d repair(s) found%s." % (len(items), "; %d check(s) couldn't run - listed" % len(
        repair.ERRORS) if repair.ERRORS else ""), "warn" if items or repair.ERRORS else "ok")


def apply_repairs(*_):
    from gus_rigtool.core import repair
    items = _repairs.get(_P["p"]) or []
    ids = [it.id for it in items if cmds.checkBox(N("Rep_" + it.id), exists=True)
           and cmds.checkBox(N("Rep_" + it.id), query=True, value=True)]
    if not ids:
        raise RuntimeError("press Find repairs, then tick what to repair.")
    out = repair.apply(ids, items)
    lines = ["%s: %s" % (label, res) for label, res in out]
    ui.report_window("Gus_Rigtool - repairs", "\n".join(lines) + "\n\nEach repair is its own undo step (Ctrl+Z, "
                     "newest first); one that failed was undone at once.")
    find_repairs()


def _show(results):
    """The checks' results, row by row (5.7.6: in the new window, drawn on its page)."""
    return proxy.refill(N("Results"), lambda: _show_now(results))


def _show_now(results):
    col = N("Results")
    for child in cmds.columnLayout(col, query=True, childArray=True) or []:
        cmds.deleteUI(child)
    cmds.setParent(col)
    if not results:
        cmds.text(label="No checks are on.", align="left")
        return
    for cid, area, label, _sev, _find, fix, _on in CHECKS:
        if cid not in results:
            continue
        sev, nodes = results[cid]
        count = len(nodes) if isinstance(nodes, list) else 0
        cmds.rowLayout(numberOfColumns=6, columnWidth6=(48, 170, 34, 55, 45, 22), adjustableColumn=2,
                       columnAttach=[(1, "both", 1), (2, "both", 4), (3, "both", 1), (4, "both", 1),
                                     (5, "both", 1), (6, "both", 1)])
        cmds.text(label=sev, backgroundColor=SEVERITY_BG[sev], enableBackground=True, height=22)
        cmds.text(label=label if sev != "ERROR" else "%s (error: %s)" % (label, nodes), align="left",
                  annotation=area)
        cmds.text(label=str(count) if sev != "ERROR" else "-")
        cmds.button(label="Select", enable=count > 0, command=_w(lambda *_, c=cid: select_check(c)))
        cmds.button(label="Fix", enable=bool(fix) and count > 0,
                    command=_w(lambda *_, c=cid: fix_check(c)),
                    annotation="Safe fix, one undo." if fix else "No safe automatic fix.")
        cmds.button(label="?", annotation=HELP.get(cid, ""),
                    command=lambda *_, t=label, h=HELP.get(cid, ""): cmds.confirmDialog(title=t, message=h,
                                                                                        button=["OK"]))
        cmds.setParent("..")


def _current(cid):
    sev, nodes = _results.get(_P["p"], {}).get(cid, ("PASS", []))
    if not isinstance(nodes, list):
        return []
    return [n for n in nodes if cmds.objExists(n)]


def select_check(cid):
    nodes = _current(cid)
    if nodes:
        cmds.select(nodes, replace=True)
        utils.info(TOOL, "selected %d." % len(nodes), "info")


def _fix_one(cid):
    entry = [c for c in CHECKS if c[0] == cid][0]
    fix, nodes = entry[5], _current(cid)
    if not fix or not nodes:
        return 0
    return fix(nodes)


def fix_check(cid):
    with utils.undo_chunk("gusrigCheckerFix"):
        done = _fix_one(cid)
    label = [c[2] for c in CHECKS if c[0] == cid][0]
    utils.info(TOOL, "%s: fixed %d. Running the checks again..." % (label, done))
    cmds.evalDeferred(_w(run))                 # after this click: the list is rebuilt


NOT_IN_FIX_ALL = ("naming_side", "dup_names")       # 5.0.11: renaming isn't 'safe' (follows, mirroring, scripts by name)


def fix_all(*_):
    total = 0
    with utils.undo_chunk("gusrigCheckerFixAll"):
        for c in CHECKS:
            if c[5] and c[0] not in NOT_IN_FIX_ALL and _current(c[0]):
                try:
                    total += _fix_one(c[0])
                except Exception as e:
                    utils.warn(TOOL, "%s: %s" % (c[2], e))
    utils.info(TOOL, "fixed %d item(s) with the safe fixes. Running the checks again..." % total)
    cmds.evalDeferred(_w(run))


def copy_report(*_):
    results = _results.get(_P["p"])
    if not results:
        utils.warn(TOOL, "run the checks first.")
        return
    text = report_text(results)
    try:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        QtWidgets.QApplication.clipboard().setText(text)
        utils.info(TOOL, "report copied to the clipboard.", "info")
    except Exception:
        print(text)
        utils.info(TOOL, "report printed in the Script Editor.", "info")


def tag_controls(*_):
    """5.6.45: Tag all controls (the button - never automatic)."""
    from gus_rigtool.core import control_maker
    sel = cmds.ls(selection=True, long=True) or []
    nodes = [n for n in transforms(sel or None) if is_control(n)]
    tagged, linked = control_maker.tag_all(nodes)
    utils.info(TOOL, "%d control(s) tagged as Maya controllers (%d were already), %d linked to the control above."
               % (tagged, len(nodes) - tagged, linked))
    return tagged, linked


def build(prefix="p_checker_"):
    _P["p"] = prefix
    s = utils.tool_settings(SETTINGS_KEY, DEFAULTS)

    ui.status_light(N("Light"), _light, _w)
    ui.presets_row(SETTINGS_KEY, _save, _w)
    ui.section("Check", help_text="Run checks on the selected hierarchies, or the whole scene when nothing "
               "is selected. Select shows the problems; Fix appears only for safe fixes (never moves skinned "
               "geometry). The ? on each row explains why it matters.")
    ui.main_button("Run checks", _w(run))
    cmds.columnLayout(N("Results"), adjustableColumn=True, rowSpacing=2)
    cmds.text(label="Not run yet.", align="left")
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Fix all safe", command=_w(fix_all),
                annotation="Runs every safe fix (one undo), then checks again.")
    cmds.button(label="Copy report", command=_w(copy_report))
    cmds.setParent("..")
    cmds.button(label="Check this scene: full diagnosis (ribbons, follows, labels, skin...)", height=26,
                command=_w(lambda *_: __import__("gus_rigtool.scene_check", fromlist=["x"]).run_later()),
                annotation="Reads the whole scene and writes a report to send: problems first, then each ribbon, "
                           "follow, skin, stuck control... Nothing changes.")
    cmds.button(label="Tag all controls as Maya controllers", height=26, command=_w(_guard(tag_controls)),
                annotation="For rigs made before 5.6.45: every control (the selected hierarchies, or the whole "
                           "scene) tagged as a Maya controller and linked to the control above it - pick-walk and "
                           "the animators' tools find them. 'Not a control' curves are left out. One undo.")
    ui.end_section()

    ui.section("Repair", help_text="Finds what Check this scene can fix safely: ribbons whose joints copy their "
               "controls, loops whose right side doesn't mirror, unlabelled joints, missing twins, constraints with "
               "no target, guides at the origin, skins whose weights don't add up to 1, dead utility nodes. Tick, "
               "then Apply: one undo. Nothing moves.")
    ui.main_button("Find repairs", _w(_guard(find_repairs)), "Looks through the whole scene.")
    cmds.columnLayout(N("Repairs"), adjustableColumn=True, rowSpacing=2)
    cmds.text(label="Not looked yet.", align="left")
    cmds.setParent("..")
    cmds.button(label="Apply the ticked repairs", height=26, command=_w(_guard(apply_repairs)))
    ui.end_section()

    ui.section("Checks to run", collapse=True, help_text="Turn checks on or off, and set the skin influence "
               "limit. Save your own sets with the presets at the top.")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 80))
    cmds.text(label="Skin influence limit per vertex", align="right")
    cmds.intField(N("Limit"), value=int(s["influence_limit"]), minValue=1, maxValue=16,
                  changeCommand=_w(_save))
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(200, 80))
    cmds.text(label="Joint twist limit (degrees)", align="right")
    cmds.intField(N("TwistLimit"), value=int(s.get("twist_limit", 30)), minValue=1, maxValue=179,
                  changeCommand=_w(_save))
    cmds.setParent("..")
    area = None
    for cid, a, label, sev, _find, fix, _on in CHECKS:
        if a != area:
            cmds.text(label=a, font="boldLabelFont", align="left")
            area = a
        cmds.checkBox(N("On_" + cid), label="%s  (%s%s)" % (label, sev.lower(), ", fix" if fix else ""),
                      value=bool(s["on_" + cid]), changeCommand=_w(_save))
    ui.end_section()
    ui.section("Batch: several files", help_text="Check many scene files in one go with these settings - one "
               "report for all. Optionally publish each file with no FAIL, saved next to it as <name>_publish "
               "(your files are untouched).")
    cmds.button(label="Batch Checker / Publish...", height=26,
                command=lambda *_: __import__("gus_rigtool.tools.batch", fromlist=["x"]).show())
    ui.end_section()


def show():
    ui.open_panel("checker")


SCHEMA = [("influence_limit", "Skin influence limit", "float", None)] + \
    [("on_" + c[0], "Check: " + c[2], "bool", None) for c in CHECKS]
