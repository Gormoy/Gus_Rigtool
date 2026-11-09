"""
Custom steps: your own Python scripts that run by themselves before or after every Build / Build picked,
so your extra work (set driven keys, constraints, attributes, shapes...) comes back on every rebuild.

    from gus_rigtool.builder import custom_steps
    custom_steps.add("C:/rigs/hare/after_build.py", "post")

The list is saved in the scene (on guides_grp), so it travels with the file. Each script runs with:
    cmds      maya.cmds
    when      'pre' or 'post'
    modules   the module ids being built (e.g. ['L:arm', 'L:fingers'])
    rig       the rig groups {'rig', 'geo', 'skeleton', 'controls', 'nodes'} (post only)
A script that fails is reported and never stops the build.
"""

import json
import os
import traceback

import maya.cmds as cmds

from gus_rigtool.builder import controls, guides
from gus_rigtool.core import utils

TOOL = "Custom steps"
ATTR = "gusCustomSteps"


def steps():
    top = guides.top_group(create=False)
    if not top:
        return []
    try:
        return json.loads(controls.get_string(top, ATTR) or "[]")
    except ValueError:
        return []


def _write(items):
    controls.add_string(guides.top_group(create=True), ATTR, json.dumps(items))


def add(path, when="post"):
    if when not in ("pre", "post"):
        raise ValueError("when: 'pre' or 'post'")
    if not os.path.isfile(path):
        raise RuntimeError("file not found: %s" % path)
    items = steps()
    items.append({"path": path.replace("\\", "/"), "when": when, "on": True})
    _write(items)
    return items


def remove(index):
    items = steps()
    if 0 <= index < len(items):
        items.pop(index)
        _write(items)
    return items


def toggle(index):
    items = steps()
    if 0 <= index < len(items):
        items[index]["on"] = not items[index].get("on", True)
        _write(items)
    return items


def move(index, delta):
    items = steps()
    j = index + delta
    if 0 <= index < len(items) and 0 <= j < len(items):
        items[index], items[j] = items[j], items[index]
        _write(items)
    return items


def label(item):
    return "[%s] %s%s" % (item.get("when", "post"), os.path.basename(item["path"]),
                          "" if item.get("on", True) else "   (off)")


def run_one(item, when, module_ids=None, rig=None):
    """Run one step; returns None when fine, else the error text."""
    path = item["path"]
    if not os.path.isfile(path):
        return "file not found: %s" % path
    env = {"cmds": cmds, "when": when, "modules": list(module_ids or []), "rig": rig or {},
           "__name__": "__gus_custom_step__", "__file__": path}
    try:
        with open(path) as f:
            code = compile(f.read(), path, "exec")
        exec(code, env)
    except Exception:
        return traceback.format_exc()
    return None


def run(when, module_ids=None, rig=None):
    """Run every step that is on, for 'pre' or 'post'. Returns [(step, error)] for the ones that failed."""
    failed = []
    for item in steps():
        if not item.get("on", True) or item.get("when", "post") != when:
            continue
        err = run_one(item, when, module_ids, rig)
        if err:
            failed.append((item, err))
            utils.warn(TOOL, "%s failed (the build goes on): %s" % (os.path.basename(item["path"]),
                                                                    err.strip().splitlines()[-1]))
        else:
            utils.info(TOOL, "ran %s (%s)." % (os.path.basename(item["path"]), when))
    return failed
