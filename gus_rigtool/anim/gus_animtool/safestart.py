"""
Safe start (5.7.11, Gus: "make sure everything won't crash as soon as we update it").

Opening a window writes a small note to disk first ("opening, step: ...") and clears it when the window is open.
If Maya dies while opening, the note is still there next time: you're asked whether to open the safe way (only
the window - no bar, no Time Slider menu, no crash backup, no shelf update), and told the step it died in.
Every step is also written to a log (the last few opens), so a crash can be traced without guessing.

A Python error is not a crash: the note is cleared then too (try / finally). Only Maya dying leaves it.

This file imports nothing from gus_animtool, so Gus_Rigtool loads it from its own copy of the Animtool
(gus_rigtool.core.safe_start) and an animator's copy has it too.

    from gus_animtool import safestart
    op = safestart.Opening("animtool", "Gus Animtool")
    safe = op.begin()                 # True: open the safe way (Maya died while opening last time, you chose so)
    try:
        op.step("the window"); ...
    finally:
        op.end()
"""

import os
import tempfile
import time

KEEP_OPENS = 5                       # opens kept in the log
NAMES = ("animtool", "animtool_restore", "rigtool", "rigtool_restore")


def folder():
    """Where the notes and logs go: Maya's prefs folder (gus_safe_start), else the temp folder."""
    base = None
    try:
        import maya.cmds as cmds
        base = cmds.internalVar(userPrefDir=True)
    except Exception:
        base = None
    path = os.path.join(base or tempfile.gettempdir(), "gus_safe_start")
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError:
        path = tempfile.gettempdir()
    return path


def note_path(name):
    return os.path.join(folder(), "%s_opening.txt" % name)


def log_path(name):
    return os.path.join(folder(), "%s_open_log.txt" % name)


def _write(path, text, mode="w"):
    """Written and flushed to the disk at once (a crash right after can't lose it)."""
    try:
        with open(path, mode) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return True
    except (IOError, OSError):
        return False


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except (IOError, OSError):
        return None


def died_last_time(name):
    """The step Maya died in while opening this last time (from the note left behind), or None."""
    text = _read(note_path(name))
    if text is None:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-1].split("  ", 1)[-1] if lines else "the start"


def forget(name):
    try:
        os.remove(note_path(name))
    except OSError:
        pass


def _trim_log(name):
    """Room for one more open: the log keeps the last KEEP_OPENS (called just before a new one is added)."""
    text = _read(log_path(name))
    if not text:
        return
    opens = text.split("=== ")
    if len(opens) - 1 >= KEEP_OPENS:
        _write(log_path(name), "=== " + "=== ".join(opens[-(KEEP_OPENS - 1):]))


def ask(title, step, log=""):
    """Maya died while opening last time: open the safe way? True = safe. (No window: safe.)"""
    try:
        import maya.cmds as cmds
        got = cmds.confirmDialog(
            title=title, message="Maya closed while %s was opening last time (at: %s).\n\nOpen the safe way? Only "
            "the window opens - no bar, no Time Slider menu, no crash backup, no shelf update.\nIf it opens fine, "
            "next time opens as usual.\n\nThe log of the last opens:\n%s" % (title, step, log),
            button=["Safe way", "As usual"], defaultButton="Safe way", cancelButton="Safe way",
            dismissString="Safe way")
        return got != "As usual"
    except Exception:
        return True


class Opening(object):
    """One open of a window: the note on disk while it opens, each step in the log."""

    def __init__(self, name, title, asks=True):
        self.name, self.title, self.asks = name, title, asks
        self.safe = False
        self.last = None             # the step Maya died in last time, or None
        self.done = False

    def begin(self, version=""):
        self.last = died_last_time(self.name)
        if self.last is not None:
            self.safe = ask(self.title, self.last, log_path(self.name)) if self.asks else True
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        _trim_log(self.name)
        _write(log_path(self.name), "=== %s  %s %s%s\n" % (stamp, self.title, version, (
            "  (Maya closed while opening last time, at: %s - %s)" % (self.last, "the safe way" if self.safe
                                                                     else "as usual")) if self.last else ""), "a")
        _write(note_path(self.name), "%s  start\n" % stamp)
        return self.safe

    def step(self, what):
        stamp = time.strftime("%H:%M:%S")
        _write(note_path(self.name), "%s  %s\n" % (stamp, what), "a")
        _write(log_path(self.name), "  %s  %s\n" % (stamp, what), "a")

    def problem(self, what, error):
        """A step that raised (Python, not a crash): logged; the open goes on."""
        _write(log_path(self.name), "  !! %s: %s\n" % (what, error), "a")

    def run(self, what, fn, *args):
        """One step: logged, and an error in it never stops the open. Returns fn's result (None on an error)."""
        self.step(what)
        try:
            return fn(*args)
        except Exception as e:
            self.problem(what, e)
            return None

    def end(self):
        if self.done:
            return
        self.done = True
        _write(log_path(self.name), "  %s  open%s\n" % (time.strftime("%H:%M:%S"), " (the safe way)" if self.safe
                                                         else ""), "a")
        forget(self.name)


def last_log(name, opens=2):
    """The last opens' log, as text (for 'Copy last problem')."""
    text = _read(log_path(name)) or ""
    parts = text.split("=== ")
    return ("=== " + "=== ".join(parts[-opens:])).strip() if len(parts) > 1 else ""


def restore_call(name, module, func, *args):
    """A window Maya reopens at start-up (its uiScript): module.func(*args), guarded. If Maya died while doing
    this last time, it's skipped this time (open the window again yourself) - Maya can't die on it every start."""
    import importlib
    op = Opening(name + "_restore", "%s (reopened by Maya)" % name, asks=False)
    if op.begin():
        op.end()
        return None
    try:
        op.step("%s.%s" % (module, func))
        return getattr(importlib.import_module(module), func)(*args)
    finally:
        op.end()


def all_logs(opens=2):
    """[(name, its last opens)] - every opening log there is."""
    out = []
    try:
        files = sorted(os.listdir(folder()))
    except OSError:
        return out
    for f in files:
        if f.endswith("_open_log.txt"):
            name = f[:-len("_open_log.txt")]
            log = last_log(name, opens)
            if log:
                out.append((name, log))
    return out
