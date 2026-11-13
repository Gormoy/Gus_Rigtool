# slider_range.py (5.6.32) - where "Step must be less than range" comes from.
# Maya prints that warning when it draws a slider whose min and max are the same, or closer together than the
# step: usually an attribute on a node (Attribute Editor, Channel Box sliders, a tool tab showing it).
# Paste into the Script Editor (Python tab) and run. Nothing in the scene changes.
import maya.cmds as cmds

NUMERIC = ("double", "float", "long", "short", "byte", "doubleLinear", "doubleAngle")
found = []
for n in cmds.ls(long=True) or []:
    for a in cmds.listAttr(n, userDefined=True) or []:
        try:
            if cmds.getAttr("%s.%s" % (n, a), type=True) not in NUMERIC:
                continue
            for lo_f, hi_f, lo_q, hi_q, kind in (("minExists", "maxExists", "minimum", "maximum", "min/max"),
                                                  ("softMinExists", "softMaxExists", "softMin", "softMax", "soft")):
                if cmds.attributeQuery(a, node=n, **{lo_f: True}) and cmds.attributeQuery(a, node=n, **{hi_f: True}):
                    lo = cmds.attributeQuery(a, node=n, **{lo_q: True})[0]
                    hi = cmds.attributeQuery(a, node=n, **{hi_q: True})[0]
                    if hi - lo <= 0.1:
                        found.append((n.split("|")[-1], a, kind, lo, hi))
        except (RuntimeError, ValueError, TypeError):
            pass
print("\n--- attributes with a range too small for a slider (min..max) ---")
for node, a, kind, lo, hi in found:
    print("  %s.%s  %s %g .. %g" % (node, a, kind, lo, hi))
print("  %d found." % len(found))
print("If none: turn on Script Editor > History > Echo All Commands, open the window or tab that warns, and copy "
      "the few lines just above the warning to Claude.")
