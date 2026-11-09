"""
Setups library (5.5.0): a node network (utility nodes, set driven key curves with their keys and tangents,
blendWeighted) saved to a file and made again on another character - its connections to the controls / joints
outside it found by name, with a find / replace (Hare -> Fox) or a namespace.

    from gus_rigtool.core import setups
    setups.save(["L_Brow_02_ctrl"], "brow_raise")          # the network around the selection
    setups.names()                                          # ['brow_raise', ...]
    setups.load("brow_raise", find="Hare", replace="Fox")   # {'made': [...], 'connected': n, 'missing': [...]}

The file is JSON in the setups folder (Settings: 'setups_folder', else <Maya app dir>/gus_rigtool/setups).
"""

import json
import os
import re

import maya.cmds as cmds

from gus_rigtool.core import naming, network_tools, utils

VERSION = 1
SKIP_ATTRS = ("message", "caching", "frozen", "isHistoricallyInteresting", "nodeState", "binMembership",
              "output", "outputX", "outputY", "outputZ", "outValue", "outColor", "outColorR", "outColorG",
              "outColorB", "outputR", "outputG", "outputB", "outFloat", "outBool", "distance", "output1D",
              "output2D", "output3D", "output2Dx", "output2Dy", "output3Dx", "output3Dy", "output3Dz")


def _short(n):
    return naming.short_name(n)


def folder():
    f = utils.load_setting("setups_folder", "")
    if not f:
        try:
            base = cmds.internalVar(userAppDir=True)
        except (AttributeError, RuntimeError):
            base = os.path.expanduser("~")
        f = os.path.join(base, "gus_rigtool", "setups")
    return f


def _path(name, where=None):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip()) or "setup"
    return os.path.join(where or folder(), safe + ".json")


def names(where=None):
    where = where or folder()
    if not os.path.isdir(where):
        return []
    return sorted(f[:-5] for f in os.listdir(where) if f.endswith(".json"))


# ---- reading a network ----------------------------------------------------------------------------------------

def _values(n, connected):
    """{attr: value} for the node's own settable numbers / bools / strings (not the connected ones)."""
    out = {}
    for a in cmds.listAttr(n, settable=True, scalar=True) or []:
        if a in SKIP_ATTRS or a in connected or "." in a:
            continue
        try:
            v = cmds.getAttr("%s.%s" % (n, a))
        except (RuntimeError, ValueError, TypeError):
            continue
        if isinstance(v, bool) or isinstance(v, (int, float)) or isinstance(v, str):
            out[a] = v
    return out


def _keys(curve):
    """[[input, value, in type, out type, in angle, out angle, in weight, out weight]] of a driven-key curve."""
    ins = cmds.keyframe(curve, query=True, floatChange=True) or []
    vals = cmds.keyframe(curve, query=True, valueChange=True) or []
    out = []
    for i, (f, v) in enumerate(zip(ins, vals)):
        def tq(**k):
            try:
                got = cmds.keyTangent(curve, query=True, index=(i, i), **k)
                return got[0] if got else None
            except (RuntimeError, TypeError):
                return None
        out.append([f, v, tq(inTangentType=True), tq(outTangentType=True), tq(inAngle=True), tq(outAngle=True),
                    tq(inWeight=True), tq(outWeight=True)])
    return out


def read(nodes):
    """The network around the nodes as a plain dict (what save() writes)."""
    net = network_tools.network(nodes)
    inside = net["nodes"]
    if not inside:
        raise RuntimeError("no utility nodes / driven keys around %s." % ", ".join(_short(n) for n in nodes))
    short = dict((n, _short(n)) for n in inside)
    data = {"version": VERSION, "nodes": {}, "connections": [], "outside": []}
    outside = set()
    for n in inside:
        incoming = cmds.listConnections(n, source=True, destination=False, plugs=True, connections=True) or []
        connected = set(incoming[i].split(".", 1)[1].split("[")[0] for i in range(0, len(incoming), 2))
        entry = {"type": cmds.nodeType(n), "attrs": _values(n, connected)}
        if entry["type"] in network_tools.CURVES:
            entry["keys"] = _keys(n)
        data["nodes"][short[n]] = entry
        for i in range(0, len(incoming) - 1, 2):
            dst, src = incoming[i], incoming[i + 1]
            snode = src.split(".", 1)[0]
            if snode.split("|")[-1] in ("time1",) or src.endswith(".message"):
                continue
            sl = (cmds.ls(snode, long=True) or [snode])[0]
            sname = short.get(sl) or _short(snode)
            if sl not in short:
                outside.add(sname)
            data["connections"].append([sname + "." + src.split(".", 1)[1], short[n] + "." + dst.split(".", 1)[1]])
    for n in inside:                                       # what the network drives outside it
        got = cmds.listConnections(n, source=False, destination=True, plugs=True, connections=True) or []
        for i in range(0, len(got) - 1, 2):
            src, dst = got[i], got[i + 1]
            dnode = dst.split(".", 1)[0]
            dl = (cmds.ls(dnode, long=True) or [dnode])[0]
            if dl in short or any(k in dnode for k in ("defaultRenderUtilityList", "NodeEditor", "nodeGraph")):
                continue
            dname = _short(dnode)
            outside.add(dname)
            data["connections"].append([short[n] + "." + src.split(".", 1)[1], dname + "." + dst.split(".", 1)[1]])
    data["outside"] = sorted(outside)
    return data


def save(nodes, name, where=None):
    """Write the network around the nodes. Returns (path, node count, outside names)."""
    data = read(nodes)
    data["name"] = name
    p = _path(name, where)
    if not os.path.isdir(os.path.dirname(p)):
        os.makedirs(os.path.dirname(p))
    with open(p, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    return p, len(data["nodes"]), data["outside"]


# ---- making it again ------------------------------------------------------------------------------------------

def _mapper(find="", replace="", namespace=""):
    def m(name):
        if find:
            name = name.replace(find, replace)
        if namespace:
            name = namespace.rstrip(":") + ":" + name
        return name
    return m


def preview(name, find="", replace="", namespace="", where=None):
    """[(saved outside name, name in this scene, found?)] - check before loading."""
    with open(_path(name, where)) as f:
        data = json.load(f)
    m = _mapper(find, replace, namespace)
    return [(o, m(o), bool(cmds.ls(m(o)))) for o in data["outside"]]


def load(name, find="", replace="", namespace="", where=None, data=None):
    """Make the saved network: new nodes renamed with find / replace (a namespace goes only on the outside names -
    the new nodes are made in the scene's root), keys and tangents set, connected to the outside nodes that exist.
    One undo. Returns {'made': [names], 'connected': n, 'missing': [outside names not found], 'failed': [plugs]}."""
    if data is None:
        with open(_path(name, where)) as f:
            data = json.load(f)
    rename = _mapper(find, replace)
    outer = _mapper(find, replace, namespace)
    made, missing, failed = {}, [], []
    connected = 0
    with utils.undo_chunk("gusrigLoadSetup"):
        for old, entry in sorted(data["nodes"].items()):
            new = cmds.createNode(entry["type"], name=rename(old), skipSelect=True)
            made[old] = new
            for a, v in sorted(entry.get("attrs", {}).items()):
                try:
                    if isinstance(v, str):
                        cmds.setAttr("%s.%s" % (new, a), v, type="string")
                    else:
                        cmds.setAttr("%s.%s" % (new, a), v)
                except (RuntimeError, ValueError, TypeError):
                    pass
            for i, key in enumerate(entry.get("keys", [])):
                f, v, itt, ott, ia, oa, iw, ow = (list(key) + [None] * 8)[:8]
                cmds.setKeyframe(new, float=f, value=v)
                tan = {}
                if ia is not None:
                    tan.update(inAngle=ia, outAngle=oa if oa is not None else ia)
                if iw is not None:
                    tan.update(inWeight=iw, outWeight=ow if ow is not None else iw)
                if itt:
                    tan["inTangentType"] = itt
                if ott:
                    tan["outTangentType"] = ott
                if tan:
                    try:
                        cmds.keyTangent(new, edit=True, index=(i, i), **tan)
                    except (RuntimeError, TypeError):
                        pass

        def plug(p):
            node, attr = p.split(".", 1)
            if node in made:
                return "%s.%s" % (made[node], attr)
            there = outer(node)
            if not cmds.ls(there):
                if node not in missing:
                    missing.append(node)
                return None
            return "%s.%s" % (there, attr)

        for src, dst in data["connections"]:
            a, b = plug(src), plug(dst)
            if not a or not b:
                continue
            try:
                cmds.connectAttr(a, b, force=True)
                connected += 1
            except RuntimeError:
                failed.append("%s -> %s" % (a, b))
    return {"made": [made[k] for k in sorted(made)], "connected": connected,
            "missing": [outer(m) for m in missing], "failed": failed}


def delete(name, where=None):
    p = _path(name, where)
    if os.path.exists(p):
        os.remove(p)
