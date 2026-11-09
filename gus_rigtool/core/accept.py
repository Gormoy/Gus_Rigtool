"""
Accepted warnings (5.3.4): a warning in Check this scene that's a choice, not a mistake (duplicate names inside the
model file, a hand-made joint's twist, a control kept offset on purpose), marked as intended. Kept in the scene on
a 'gusAccepted' node. It passes ('ok  ... (accepted)') only while it lists exactly what you accepted: anything new
on that line and it warns again.

    from gus_rigtool.core import accept
    accept.accept([(section, name, detail), ...])
    accept.forget()                      # everything back to warning
"""

import json
import re

import maya.cmds as cmds

NODE = "gusAccepted"
ATTR = "gusAcceptedData"
ACCEPTABLE = ("warn", "note")


def key(section, name):
    """The row without its count ('Controls: Controls not at zero (1)' -> '...not at zero')."""
    return "%s|%s" % (section, re.sub(r"\s*\(\d+\)\s*$", "", name).strip())


def load():
    if not cmds.objExists(NODE) or not cmds.attributeQuery(ATTR, node=NODE, exists=True):
        return {}
    try:
        return json.loads(cmds.getAttr(NODE + "." + ATTR) or "{}")
    except (ValueError, TypeError):
        return {}


def _save(data):
    if not cmds.objExists(NODE):
        cmds.createNode("network", name=NODE, skipSelect=True)
    if not cmds.attributeQuery(ATTR, node=NODE, exists=True):
        cmds.addAttr(NODE, longName=ATTR, dataType="string")
    cmds.setAttr(NODE + "." + ATTR, json.dumps(data, sort_keys=True), type="string")


def accept(rows):
    """rows: [(section, name, detail)]. Returns how many are accepted now."""
    data = load()
    for section, name, detail in rows:
        data[key(section, name)] = detail
    _save(data)
    return len(rows)


def forget(keys=None):
    data = load()
    for k in (list(data) if keys is None else keys):
        data.pop(k, None)
    if data or cmds.objExists(NODE):
        if not data and cmds.objExists(NODE):
            cmds.delete(NODE)
        else:
            _save(data)


def apply(rep):
    """In a finished report: rows accepted with the same detail become ok '(accepted)'; one with something new
    stays a warning and says so. Returns how many passed as accepted."""
    data = load()
    if not data:
        return 0
    n = 0
    rows = []
    for section, status, name, detail in rep.rows:
        k = key(section, name)
        if status in ACCEPTABLE and k in data:
            if data[k] == detail:
                status, name = "ok", name + "  (accepted)"
                n += 1
            else:
                detail = detail + "  [changed since you accepted it]"
        rows.append((section, status, name, detail))
    rep.rows = rows
    return n


def problems(rep):
    """The rows that can be accepted: [(section, name, detail)]."""
    return [(sec, name, detail) for sec, status, name, detail in rep.rows if status in ACCEPTABLE]
