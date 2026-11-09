"""
Gus_Rigtool tests - they run OUTSIDE Maya, with a small fake of maya.cmds (fakemaya.py).

    cd gus_rigtool/tests
    python run_tests.py            # every test; compares the output with expected/<test>.txt
    python run_tests.py chain      # only the tests whose name has 'chain'
    python run_tests.py --update   # accept the current output as the new expected one

Needs Python 3 and numpy. The fake records constraints and connections but doesn't solve them,
so these tests check what is made, named, connected and kept - not how the rig moves in Maya.
"""

import glob
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(os.path.dirname(HERE))


def normalize(text):
    text = re.sub(r"0x[0-9a-fA-F]+", "0x?", text)                    # object addresses
    text = re.sub(r"/tmp[^\s'\"]*", "<tmp>", text)                    # temporary folders
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def run(path):
    env = dict(os.environ, GUS_RIGTOOL_PARENT=PARENT, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, os.path.basename(path)], cwd=HERE, env=env, capture_output=True,
                       text=True, timeout=900)
    return p.returncode, normalize(p.stdout + p.stderr)


def main(args):
    update = "--update" in args
    words = [a for a in args if not a.startswith("--")]
    tests = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    tests = [t for t in tests if not words or any(w in os.path.basename(t) for w in words)]
    failed = []
    for t in tests:
        name = os.path.basename(t)[5:-3]
        start = time.time()
        code, out = run(t)
        exp_path = os.path.join(HERE, "expected", name + ".txt")
        if update:
            with open(exp_path, "w") as f:
                f.write(out + "\n")
            status = "updated"
        elif code != 0 or "Traceback" in out:
            status = "ERROR"
        elif not os.path.exists(exp_path):
            status = "no expected output (run with --update)"
        else:
            with open(exp_path) as f:
                status = "ok" if normalize(f.read()) == out else "CHANGED"
        if status in ("ERROR", "CHANGED"):
            failed.append(name)
            os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
            with open(os.path.join(HERE, "out", name + ".txt"), "w") as f:
                f.write(out + "\n")
        print("%-14s %-8s %5.1fs" % (name, status, time.time() - start))
    if failed:
        print("\n%d test(s) to look at: %s (their output is in tests/out/)" % (len(failed), ", ".join(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
