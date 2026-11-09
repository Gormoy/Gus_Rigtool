"""
Reports for the Maya check and Check this scene: problems first, one line per section, everything else at the
bottom. Statuses:
    ok    worked
    FAIL  broken: an error, or a result that is wrong
    warn  works, but something in the scene / rig looks wrong (scene check)
    note  a tool said what it needs - if it isn't a known one, it's listed with the problems
    fine  a known, expected note (e.g. 'select keys in the Graph Editor' when nothing is selected)
    info  facts (what a ribbon / follow is), never a problem
"""

import platform
import time
import traceback

OK, FAIL, WARN, NOTE, FINE, INFO = "ok", "FAIL", "warn", "note", "fine", "info"
PROBLEMS = (FAIL, WARN, NOTE)

# notes we know are fine: a tool asking for something the check doesn't give it on purpose
EXPECTED_NOTES = (
    "skipped:",
    "select keys in the graph editor",
    "no keys at frame",
    "nothing was offset",
    "nothing travels in this cycle",
    "nothing was put in place",
    "already in a temporary space",
    "select something attached",
)


def short(v, n=80):
    s = repr(v)
    return s if len(s) < n else s[:n - 3] + "..."


def tb(lines=6):
    """The last lines of the current traceback (file, line, error)."""
    out = traceback.format_exc().strip().splitlines()
    return "\n".join(out[-lines:])


class Report(object):
    def __init__(self, title):
        self.title = title
        self.rows = []                  # (section, status, name, detail)
        self.sections = []
        self.section = ""
        self.started = time.time()

    def start(self, title):
        """Rows added from now on go under this section (listed once it has a row)."""
        self.section = title

    def add(self, status, name, detail=""):
        detail = str(detail or "")
        if self.section not in self.sections:
            self.sections.append(self.section)
        if status == NOTE and any(p in detail.lower() for p in EXPECTED_NOTES):
            status = FINE
        self.rows.append((self.section, status, name, detail))

    def step(self, name, fn, *args, **kw):
        """Run fn: ok / FAIL (with the error and where) / note (a RuntimeError or ValueError: the tool said what
        it needs). Returns fn's result, or None."""
        t = time.time()
        try:
            got = fn(*args, **kw)
            self.add(OK, name, "%s(%.1fs)" % (("%s  " % short(got)) if got not in (None, True) else "",
                                               time.time() - t))
            return got
        except (RuntimeError, ValueError) as e:
            self.add(NOTE, name, "said: %s" % (str(e).strip().splitlines() or [""])[0][:200])
        except Exception as e:
            self.add(FAIL, name, "%s: %s\n%s" % (type(e).__name__, e, tb()))
        return None

    def expect(self, name, cond, detail="", bad=FAIL):
        """ok when cond, else FAIL (or bad). Returns cond."""
        self.add(OK if cond else bad, name, detail)
        return bool(cond)

    def guard(self, name, fn, *args, **kw):
        """Run a whole check; if it crashes, one FAIL row says which check and where (the others still run)."""
        try:
            return fn(*args, **kw)
        except Exception as e:
            self.add(FAIL, "%s (the check itself crashed)" % name, "%s: %s\n%s" % (type(e).__name__, e, tb()))
            return None

    # ----------------------------------------------------------------- text
    def counts(self, section=None):
        rows = [r for r in self.rows if section is None or r[0] == section]
        return {s: sum(1 for r in rows if r[1] == s) for s in (OK, FAIL, WARN, NOTE, FINE, INFO)}

    def problems(self):
        return [r for r in self.rows if r[1] in PROBLEMS]

    def _line(self, status, name, detail, indent="  "):
        pad = indent + " " * 8
        return "%s%-5s %s%s" % (indent, status, name, ("   " + detail.replace("\n", "\n" + pad)) if detail else "")

    def _tally(self, c):
        parts = []
        for s, word in ((FAIL, "FAIL"), (WARN, "warning"), (NOTE, "note to look at"), (OK, "ok"),
                        (FINE, "expected note"), (INFO, "info")):
            if c[s]:
                parts.append("%d %s%s" % (c[s], word, "s" if c[s] > 1 and s in (WARN, NOTE, FINE) else ""))
        return ", ".join(parts) or "nothing"

    def text(self, header_lines=()):
        import gus_rigtool
        try:
            import maya.cmds as cmds
            maya = cmds.about(version=True)
        except Exception:
            maya = "?"
        c = self.counts()
        out = ["Gus_Rigtool %s - %s" % (gus_rigtool.__version__, self.title),
               "Maya %s   %s   Python %s   %.0fs" % (maya, platform.platform(), platform.python_version(),
                                                     time.time() - self.started)]
        out += list(header_lines)
        out.append("")
        probs = self.problems()
        if not probs:
            out.append("RESULT: no problems. (%s)" % self._tally(c))
        else:
            out.append("RESULT: %s" % self._tally(c))
            out.append("")
            out.append("PROBLEMS (look at these first)")
            sec = None
            for section, status, name, detail in probs:
                if section != sec:
                    out.append("  [%s]" % section)
                    sec = section
                out.append(self._line(status, name, detail, "    "))
        out.append("")
        out.append("SUMMARY")
        for section in self.sections:
            sc = self.counts(section)
            mark = FAIL if sc[FAIL] else (WARN if sc[WARN] or sc[NOTE] else OK)
            out.append("  %-5s %-58s %s" % (mark, section, self._tally(sc)))
        info = [r for r in self.rows if r[1] == INFO]
        if info:
            out.append("")
            out.append("WHAT'S IN THE SCENE")
            sec = None
            for section, status, name, detail in info:
                if section != sec:
                    out.append("  [%s]" % section)
                    sec = section
                out.append("    %s%s" % (name, ("   " + detail.replace("\n", "\n        ")) if detail else ""))
        out.append("")
        out.append("DETAILS (every step)")
        for section in self.sections:
            out.append("  == %s ==" % section)
            for sec, status, name, detail in self.rows:
                if sec == section and status != INFO:
                    out.append(self._line(status, name, detail.splitlines()[0] if detail else "", "    "))
        return "\n".join(out) + "\n"
