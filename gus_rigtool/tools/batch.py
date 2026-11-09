"""
Batch Checker / Publish: run the Checker on several scene files in one go - one report for all of them - and
(optionally) publish each file that has no FAIL, saved next to it as <name>_publish.ma (your files untouched).

    import gus_rigtool.tools.batch as b; b.show()
"""

import os

import maya.cmds as cmds

from gus_rigtool.core import ui, utils

TOOL = "Batch"
WIN = "gusRigBatchWin"
_files = []


def publish_path(path):
    base, ext = os.path.splitext(path)
    return base + "_publish" + (ext if ext in (".ma", ".mb") else ".ma")


def check_file(path, options, publish=False):
    """Open path, run the Checker (whole scene). Returns (summary line, report text, published file or None)."""
    from gus_rigtool.tools import checker
    cmds.file(path, open=True, force=True, prompt=False)
    results = checker.run_checks(options, [])
    fails = sum(1 for s, _n in results.values() if s == "FAIL")
    warns = sum(1 for s, _n in results.values() if s == "WARN")
    errors = sum(1 for s, _n in results.values() if s == "ERROR")
    out = None
    note = ""
    if publish and not fails and not errors:
        from gus_rigtool.builder import publish as pub
        try:
            pub.publish()
            out = publish_path(path)
            cmds.file(rename=out)
            cmds.file(save=True, force=True, type="mayaBinary" if out.endswith(".mb") else "mayaAscii")
            note = " -> published: %s" % os.path.basename(out)
        except Exception as e:                              # one file never stops the batch
            note = " -> not published (%s)" % e
    elif publish:
        note = " -> not published (fix the FAIL / ERROR items first)"
    line = "%-40s %d fail, %d warning%s%s" % (os.path.basename(path), fails, warns,
                                              (", %d error" % errors) if errors else "", note)
    return line, checker.report_text(results), out


def run(paths, publish=False, options=None):
    """Every file in turn. Returns the whole report (text)."""
    from gus_rigtool.tools import checker
    o = dict(checker.DEFAULTS)
    o.update(options or utils.tool_settings(checker.SETTINGS_KEY, checker.DEFAULTS))
    summary, details = [], []
    for p in paths:
        try:
            line, text, _out = check_file(p, o, publish)
        except Exception as e:
            line, text = "%-40s could not open / check: %s" % (os.path.basename(p), e), ""
        summary.append(line)
        details.append("=== %s ===\n%s" % (os.path.basename(p), text))
    return "Batch %s - %d file(s)\n\n%s\n\n%s" % ("check + publish" if publish else "check", len(paths),
                                                 "\n".join(summary), "\n\n".join(details))


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def _refresh():
    cmds.textScrollList(WIN + "List", edit=True, removeAll=True)
    for p in _files:
        cmds.textScrollList(WIN + "List", edit=True, append=p)


def _add_files(*_):
    got = cmds.fileDialog2(fileMode=4, caption="Scenes to check", fileFilter="Maya scenes (*.ma *.mb)") or []
    _files.extend(p for p in got if p not in _files)
    _refresh()


def _add_folder(*_):
    got = cmds.fileDialog2(fileMode=3, caption="A folder of scenes") or []
    if got:
        for f in sorted(os.listdir(got[0])):
            p = os.path.join(got[0], f).replace("\\", "/")
            if f.endswith((".ma", ".mb")) and "_publish." not in f and p not in _files:
                _files.append(p)
    _refresh()


def _remove(*_):
    for p in cmds.textScrollList(WIN + "List", query=True, selectItem=True) or []:
        _files.remove(p)
    _refresh()


def _go(*_):
    if not _files:
        raise RuntimeError("add scene files first.")
    import maya.mel as mel
    if not mel.eval('saveChanges("")'):
        return
    publish = cmds.checkBox(WIN + "Publish", query=True, value=True)
    text = run(list(_files), publish)
    ui.report_window("Gus_Rigtool - batch", text)


def _g(fn):
    """A button: problems become a warning, never a Python error."""
    def run_(*_):
        try:
            return fn()
        except RuntimeError as e:
            utils.warn(TOOL, str(e))
    return run_


def show(*_):
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)
    cmds.window(WIN, title="Gus_Rigtool - Batch Checker / Publish", widthHeight=(520, 380))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4, columnAttach=("both", 6))
    cmds.text(label="Each file is opened, checked with the Checker's settings, and listed in one report.",
              align="left")
    cmds.textScrollList(WIN + "List", height=200, allowMultiSelection=True)
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(160, 160, 160), columnAttach=[(i + 1, "both", 2)
                                                                                 for i in range(3)])
    cmds.button(label="Add files...", command=_g(_add_files))
    cmds.button(label="Add a folder...", command=_g(_add_folder))
    cmds.button(label="Remove picked", command=_g(_remove))
    cmds.setParent("..")
    cmds.checkBox(WIN + "Publish", label="Publish the files with no FAIL (saved as <name>_publish next to them)",
                  value=False)
    cmds.button(label="Run", height=30, backgroundColor=ui.MAIN_BG, command=_g(_go))
    cmds.showWindow(WIN)
    _refresh()
    return WIN
