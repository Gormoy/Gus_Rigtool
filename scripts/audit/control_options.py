"""
Which control options each tool offers (5.6.29) - a table read from the code, to see when one tool has an option
another lacks (the Ribbon's "distance in front", the Builder's shape turns...).

    python3 scripts/audit/control_options.py              (from the repository's root; no Maya needed)

It looks for each option's words in the code of every tool that makes controls (the tab and the module behind it).
That is a rough look: "x" means the words are there, so the tool very likely has the option - check by hand before
relying on one cell. Add a tool or an option to TOOLS / OPTIONS below.
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "gus_rigtool")

TOOLS = [                                    # (name, files that make its controls)
    ("Shapes", ["tools/shape_library.py"]),
    ("Make controls", ["core/make_controls.py", "tools/make_controls_tool.py"]),
    ("Ribbon", ["core/ribbon.py", "tools/ribbon_tool.py"]),
    ("Builder", ["builder/controls.py", "tools/build_form.py"]),
    ("Joints IK spline", ["core/ik_spline.py"]),
    ("World levels", ["core/world_levels.py"]),
]

OPTIONS = [                                  # (option, regular expression looked for)
    ("shape picked", r"ctrl_shape|shape_name|\bshape\s*=|SHAPES\(\)"),
    ("size", r"\bsize\b|ctrl_radius|\bradius\b"),
    ("facing axis", r"face_axis|facing|\bface\s*="),
    ("shape turned (any angle)", r"turn X Y Z|euler_matrix\(\s*\[float"),
    ("distance in front", r"ctrl_distance"),
    ("pivot on the shape", r"pivot_on_shape"),
    ("colour picked", r"rgb_style|colorSliderGrp"),
    ("colour by side", r"side_colou?rs?\b|apply_side_color|use_side_colors"),
    ("line width", r"line_width|lineWidth"),
    ("group stack", r"\bstack\b"),
    ("drives the joint", r"\bdrive\b|DRIVE"),
    ("lock / hide channels", r"lock_hide|\block\s*="),
    ("tagged as controller", r"cmds\.controller\("),
]


def read(files):
    text = ""
    for f in files:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            with open(p) as fh:
                text += fh.read()
    return text


def table():
    texts = [(name, read(files)) for name, files in TOOLS]
    head = "| Option | " + " | ".join(n for n, _t in texts) + " |"
    lines = [head, "|" + "---|" * (len(texts) + 1)]
    gaps = []
    for opt, rx in OPTIONS:
        row = []
        for name, text in texts:
            has = bool(re.search(rx, text))
            row.append("x" if has else "")
        lines.append("| %s | %s |" % (opt, " | ".join(row)))
        have = [n for (n, _t), c in zip(texts, row) if c]
        if 0 < len(have) < len(texts):
            gaps.append("%s: only in %s" % (opt, ", ".join(have)))
    return lines, gaps


def main():
    lines, gaps = table()
    print("\n".join(lines))
    print("\nOptions some tools have and others don't:")
    for g in gaps:
        print("  - " + g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
