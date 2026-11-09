# 5.3.2: the jiggle reacts to the chain's parent moving in any direction (the world control sliding sideways moved
# nothing before) and turning, and stays within jiggle_limit_body towards the body. The MEL expression is turned
# into C and run frame by frame (when a C compiler is there) - the same maths Maya runs.
import os
import re
import shutil
import subprocess
import sys
import tempfile
exec(open("fakemaya.py").read())
from gus_rigtool.builder import chain
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

# a chain along +X, 10 long, turning about Y (side) and Z (up); the body towards +Y
T = [10.0, 0.0, 0.0]
K = {"side": [0.0, 0.0, -0.1], "up": [0.0, 0.1, 0.0]}     # +Y turn takes the tip to -Z, +Z turn to +Y
text = chain.jiggle_text("Cape", "S", ["G1", "G2", "G3"], "DM", "Y", "Z", "t", K, T, {"side": 0, "up": 1})
check("marked as the 5.3.2 jiggle (Repair knows which are older)", chain.JIGGLE_VERSION in text)
check("reads the movement and the turn of what it hangs from", "DM.outputTranslateX" in text and
      "DM.outputRotateZ" in text and "deg_to_rad" in text)
check("no setAttr / getAttr / xform: undo stays clean", not re.search(r"setAttr|getAttr|xform", text))
check("towards the body (up +): at most jiggle_limit_body for the whole chain (a third per group)",
      "if ($nn > S.jiggle_limit_body / 3)" in text and "if ($nn < -S.jiggle_limit_out)" in text)
check("the side axis: jiggle_limit_out both ways", "if ($nn > S.jiggle_limit_out)" in text)
check("a header Repair can read back", "// groups: G1 G2 G3 | side Y | up Z | settings S | body side 0 up 1" in text)

cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
if not cc:
    print("SKIP no C compiler: the frame-by-frame run is skipped")
else:
    body = []
    for line in text.splitlines():
        if line.startswith("//") or line.startswith("global float"):
            continue
        line = re.sub(r"size\(\$\w+\)", "GSIZE", line).replace("float $q[];", "float $q[9];")
        line = re.sub(r"\babs\(", "fabs(", line)
        line = re.sub(r"\b([A-Za-z_]\w*)\.(\w+)", r"\1__\2", line).replace("$", "")
        body.append(line)
    body = "\n".join(body)
    names = sorted(set(re.findall(r"\b[A-Za-z_]\w*__\w+\b", body)))
    gname = re.search(r"\b(gusJiggle_\w+)\[", body).group(1)
    src = ["#include <math.h>", "#include <stdio.h>", "#define deg_to_rad(x) ((x) * M_PI / 180.0)",
           "#define float double", "static double %s[400]; static int GSIZE = 0; static double frame;" % gname]
    src += ["static double %s = 0;" % n for n in names]
    src += ["static void step(void) {", body, "GSIZE = 400; }",
            "int main(void) { double v[7];",
            "  S__jiggle = 1; S__jiggle_stiffness = 0.15; S__jiggle_damping = 0.2; S__jiggle_bounce = 1;",
            "  S__jiggle_limit_body = 10; S__jiggle_limit_out = 90;",
            "  while (scanf(\"%lf %lf %lf %lf %lf %lf %lf\", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6]) == 7) {",
            "    frame = v[0]; DM__outputTranslateX = v[1]; DM__outputTranslateY = v[2]; DM__outputTranslateZ = v[3];",
            "    DM__outputRotateX = v[4]; DM__outputRotateY = v[5]; DM__outputRotateZ = v[6]; step();",
            "    printf(\"%g %g %g %g\\n\", G3__rotateY, G3__rotateZ, G1__rotateY, G1__rotateZ); }",
            "  return 0; }"]
    d = tempfile.mkdtemp()
    open(os.path.join(d, "j.c"), "w").write("\n".join(src))
    r = subprocess.run([cc, "-O0", "-o", os.path.join(d, "j"), os.path.join(d, "j.c"), "-lm"],
                       capture_output=True, text=True)
    check("the expression compiles as C (its statements are well formed)", r.returncode == 0)
    if r.returncode:
        print(r.stderr[:1500])

    def run(frames):
        inp = "\n".join(" ".join("%g" % x for x in f) for f in frames)
        p = subprocess.run([os.path.join(d, "j")], input=inp, capture_output=True, text=True)
        return [[float(x) for x in ln.split()] for ln in p.stdout.split("\n") if ln.strip()]

    if r.returncode == 0:
        # slides +Z (sideways for this chain) from frame 3, stops at frame 8
        still = [[f, 0, 0, 0, 0, 0, 0] for f in (1, 2)]
        z, zs = 0.0, []
        for f in range(3, 30):
            z += 2.0 if f < 8 else 0.0
            zs.append([f, 0, 0, z, 0, 0, 0])
        out = run(still + zs)
        tipY = [o[0] for o in out]
        print("slide +Z, tip rotateY:", ["%.2f" % x for x in tipY[:12]])
        check("standing still: nothing", all(abs(x) < 1e-9 for x in tipY[:2]))
        check("starts sliding +Z: the tip lags (-Z, so rotateY +)", tipY[3] > 0.1)
        check("stops: it swings past (the other way) and settles", min(tipY[8:]) < -0.1 and abs(tipY[-1]) < abs(
            max(tipY, key=abs)))
        # moves up (+Y, towards the body) fast: the tip lags down (away) freely; down fast: towards the body, limited
        ys, y = [], 0.0
        for f in range(3, 20):
            y -= 6.0 if f < 6 else 0.0
            ys.append([f, 0, y, 0, 0, 0, 0])
        out = run(still + ys)
        print("drop -Y, tip rotateZ:", ["%.2f" % o[1] for o in out[:12]])
        check("drops: the tip flies up towards the body, but no further than the limit (10 for the chain)",
              max(o[1] for o in out) > 0.1 and max(o[1] for o in out) <= 10.0 / 3 + 1e-6)
        # turns about Y: the tip lags behind the turn
        rs = [[f, 0, 0, 0, 0, 5.0 * (f - 2), 0] for f in range(3, 10)]
        out = run(still + rs)
        print("turn +Y, tip rotateY:", ["%.2f" % o[0] for o in out[:9]])
        check("turns +Y: the tip lags (rotateY -)", out[3][0] < -0.1)
        # a jump in time: back to rest
        out = run(still + zs[:6] + [[50, 0, 0, z, 0, 0, 0]])
        check("a jump in time: back to rest", abs(out[-1][0]) < 1e-9 and abs(out[-1][1]) < 1e-9)
        # playing from a moving frame: no kick on the first frame
        out = run([[f, 0, 0, 2.0 * f, 0, 0, 0] for f in range(10, 16)])
        check("starting on a moving shot: no kick (steady speed swings nothing)", all(abs(o[0]) < 1e-9 for o in out))
    shutil.rmtree(d, ignore_errors=True)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
