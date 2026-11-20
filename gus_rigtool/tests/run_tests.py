"""
Gus_Rigtool tests - they run OUTSIDE Maya, with a small fake of maya.cmds (fakemaya.py).

    cd gus_rigtool/tests
    python run_tests.py                      # every test, 4 at a time; compares the output with expected/<test>.txt
    python run_tests.py chain biped          # only these tests (exact names: file name without test_ and .py)
    python run_tests.py fix56*               # a name ending in * is a prefix: fix561, fix5617, fix5618...
    python run_tests.py -j 1                 # one at a time (-j N: N at a time)
    python run_tests.py --update 5629 publish    # accept these tests' current output (shows each diff first);
                                             # refused without names, so a regression can't slip in with the rest

Needs Python 3 and numpy. The fake records constraints and connections but doesn't solve them,
so these tests check what is made, named, connected and kept - not how the rig moves in Maya.
"""

import difflib
import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(os.path.dirname(HERE))


def _version():
    try:
        with open(os.path.join(os.path.dirname(HERE), "__init__.py")) as f:
            m = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
        return m.group(1) if m else None
    except (IOError, OSError):
        return None


VERSION = _version()


def normalize(text):
    if VERSION:                                                       # 5.6.46: a version bump changes no output
        text = re.sub(r"(?<![\d.])" + re.escape(VERSION) + r"(?![\d.])", "<this version>", text)
    text = re.sub(r"0x[0-9a-fA-F]+", "0x?", text)                    # object addresses
    text = re.sub(r"/tmp[^\s'\"]*", "<tmp>", text)                    # temporary folders
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def run(path):
    env = dict(os.environ, GUS_RIGTOOL_PARENT=PARENT, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, os.path.basename(path)], cwd=HERE, env=env, capture_output=True,
                       text=True, timeout=900)
    return p.returncode, normalize(p.stdout + p.stderr)


def select(tests, words):
    """5.6.29: exact names (test_<name>.py), or a prefix when the name ends in * (5.6.28 matched any part of the
    name: 'publish' also ran hand_publish501). Returns (tests, names that matched nothing)."""
    out, unknown = [], []
    for w in words:
        if w.endswith("*"):
            got = [t for t in tests if os.path.basename(t)[5:-3].startswith(w[:-1])]
        else:
            got = [t for t in tests if os.path.basename(t)[5:-3] == w]
        if not got:
            unknown.append(w)
        out += [t for t in got if t not in out]
    return out, unknown


def check_one(t, update):
    name = os.path.basename(t)[5:-3]
    start = time.time()
    code, out = run(t)
    exp_path = os.path.join(HERE, "expected", name + ".txt")
    old = None
    if os.path.exists(exp_path):
        with open(exp_path) as f:
            old = normalize(f.read())
    if update:
        diff = "" if old is None else "\n".join(difflib.unified_diff(
            old.splitlines(), out.splitlines(), "expected/%s.txt" % name, "now", lineterm="", n=1))
        with open(exp_path, "w") as f:
            f.write(out + "\n")
        status = "updated" if old != out else "same"
        return name, status, time.time() - start, out, diff
    if code != 0 or "Traceback" in out:
        status = "ERROR"
    elif old is None:
        status = "no expected output (run with --update %s)" % name
    else:
        status = "ok" if old == out else "CHANGED"
    return name, status, time.time() - start, out, ""


def tool_files():
    """5.6.46: the tool's own files (not the tests, not compiled ones) and when each last changed - a test that
    writes over them (5.6.46: the Animtool update test once did) is caught."""
    tool = os.path.dirname(HERE)
    out = {}
    for root, dirs, files in os.walk(tool):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".ruff_cache")]
        for f in files:
            path = os.path.join(root, f)
            try:
                st = os.stat(path)
                out[os.path.relpath(path, tool)] = (st.st_mtime, st.st_size)
            except OSError:
                pass
    return out


def main(args):
    update = "--update" in args
    jobs = 4
    words = []
    it = iter(args)
    for a in it:
        if a == "-j":
            jobs = max(1, int(next(it, "4")))
        elif a.startswith("-j") and a[2:].isdigit():
            jobs = max(1, int(a[2:]))
        elif not a.startswith("--"):
            words.append(a)
    tests = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    if words:
        tests, unknown = select(tests, words)
        if unknown:
            print("no test called: %s (names are exact; end with * for a prefix)" % ", ".join(unknown))
            return 1
    elif update:
        print("--update needs the test names (what you checked): python run_tests.py --update name1 name2")
        return 1
    failed = []
    before = tool_files()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for name, status, took, out, diff in pool.map(lambda t: check_one(t, update), tests):
            if status in ("ERROR", "CHANGED"):
                failed.append(name)
                os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
                with open(os.path.join(HERE, "out", name + ".txt"), "w") as f:
                    f.write(out + "\n")
            print("%-14s %-8s %5.1fs" % (name, status, took))
            if diff:
                print(diff)
    after = tool_files()
    touched = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if touched:
        print("\nA TEST CHANGED THE TOOL'S OWN FILES (put them back from git): %s%s" % (
            ", ".join(touched[:10]), " ..." if len(touched) > 10 else ""))
        failed.append("(tool files)")
    if failed:
        print("\n%d test(s) to look at: %s (their output is in tests/out/)" % (len(failed), ", ".join(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
