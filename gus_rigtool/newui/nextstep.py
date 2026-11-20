"""
The next step (5.7): what to do with this selection, in plain words - it only suggests; its button takes you to
the page (it never does anything by itself).
"""

KINDS = ("joint", "control", "mesh", "other")


def suggest(kinds, here, edges=0):
    """kinds: the selection's kinds (['joint', 'joint', 'mesh'...]); here: the page shown (tool key, page index).
    Returns (text, where, button, (tool key, page index)) or None."""
    n = {k: kinds.count(k) for k in KINDS}
    tool, sub = here
    if edges:
        target = ("controls_tab", 2)
        return ("%d edge(s) selected: a control in the shape of this loop" % edges,
                "Edit shape > On the body > Shape from edges", "Go to Edit shape" if here != target else "Show me",
                target)
    if n["mesh"] and n["joint"] and not n["control"]:
        return ("<b>%s</b> and <b>%d joints</b> selected: bind the skin" % ("a mesh" if n["mesh"] == 1 else
                                                                         "%d meshes" % n["mesh"], n["joint"]),
                "Skin > Bind - one click takes you there", "Go to Skin > Bind", ("skin", None))
    if n["control"] and n["mesh"] == 1 and not n["joint"]:
        target = ("controls_tab", 2)
        return ("controls, then the mesh: wrap the shapes around the body",
                "Edit shape > On the body > Fit to the body", "Show me" if here == target else "Go to Edit shape",
                target)
    if n["joint"] and not n["control"] and not n["mesh"]:
        target = ("controls_tab", 1)
        what = "a chain of %d joints: an FK chain of controls" % n["joint"] if n["joint"] > 1 else \
            "a joint: a control on it"
        return (what, "you're on the right page - the big button does it" if here == target else
                "Controls > Make", "Show me" if here == target else "Go to Make", target)
    if n["control"] and not n["joint"] and not n["mesh"] and tool == "controls_tab" and sub == 1:
        target = ("controls_tab", 2)
        return ("controls selected: change their shape, colour, size",
                "Make puts a NEW control on each one; Edit shape changes them", "Go to Edit shape", target)
    return None
