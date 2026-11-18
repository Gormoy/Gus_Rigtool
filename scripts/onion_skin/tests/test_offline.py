"""Onion Skin - tests without Maya (a tiny fake maya.cmds). Run: python3 test_offline.py"""
import os
import sys
import types

ok = []


def check(label, cond):
    ok.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + label)


# ---- a tiny fake Maya: two characters, A (namespace) and B (top group), keys on their controls
class FakeCmds(object):
    def __init__(self):
        self.time = 12.0
        self.nodes = {}                 # long name -> type
        self.curves = {}                # curve -> (driven long name, [key times])
        self.undo = True
        self.opts = {}
        self.made = []
        self.deleted = []
        self.selection = []
        for n, t in (("|A:RIG", "transform"), ("|A:RIG|A:ctrl", "transform"), ("|A:RIG|A:body", "transform"),
                     ("|A:RIG|A:body|A:bodyShape", "mesh"), ("|B_RIG", "transform"), ("|B_RIG|B_ctrl", "transform"),
                     ("|B_RIG|B_geo", "transform"), ("|B_RIG|B_geo|B_geoShape", "mesh"),
                     ("|B_RIG|B_geo|B_geoShapeOrig", "mesh")):
            self.nodes[n] = t
        self.hidden = set()
        self.intermediate = {"|B_RIG|B_geo|B_geoShapeOrig"}
        self.curves = {"curveA": ("|A:RIG|A:ctrl", [1.0, 10.0, 20.0]), "curveB": ("|B_RIG|B_ctrl", [5.0, 15.0]),
                       "curveBlend": ("pairBlend1", [30.0])}

    def _find(self, n):
        if n in self.nodes:
            return n
        hits = [k for k in self.nodes if k.split("|")[-1] == n.split("|")[-1]]
        return hits[0] if len(hits) == 1 else None

    def ls(self, *a, **k):
        if k.get("selection"):
            return list(self.selection)
        if k.get("type"):
            t = k["type"]
            if t == ["animCurveTL", "animCurveTA", "animCurveTU"]:
                return list(self.curves)
            if t == "mesh":
                pat = a[0] if a else "*"
                ns = pat.split(":")[0] + ":" if ":" in pat else ""
                return [n for n, ty in self.nodes.items() if ty == "mesh" and ns in n]
            return []
        if a and isinstance(a[0], list):
            out = []
            for n in a[0]:
                f = self._find(n)
                if not f:
                    continue
                if k.get("noIntermediate") and f in self.intermediate:
                    continue
                if k.get("visible") and any(f == h or f.startswith(h + "|") for h in self.hidden):
                    continue
                out.append(f)
            return out
        if a:
            f = self._find(a[0])
            return [f] if f else []
        return []

    def nodeType(self, n):
        return self.nodes.get(self._find(n) or n, "transform")

    def objectType(self, n, isAType=None):
        return self.nodes.get(n) in ("transform", "mesh")

    def listRelatives(self, n, **k):
        n = self._find(n) or n
        if k.get("parent"):
            return ["|".join(n.split("|")[:-1])]
        if k.get("shapes"):
            return [c for c, t in self.nodes.items() if t == "mesh" and c.rsplit("|", 1)[0] == n] or None
        if k.get("allDescendents"):
            return [c for c, t in self.nodes.items() if t == "mesh" and c.startswith(n + "|")] or None
        return None

    def listConnections(self, plug, **k):
        node = plug.split(".")[0]
        if node in self.curves:
            return [self.curves[node][0]]
        if node == "pairBlend1":
            return ["|A:RIG|A:ctrl"]
        return []

    def keyframe(self, curve, **k):
        return list(self.curves[curve][1])

    def currentTime(self, *a, **k):
        if k.get("query"):
            return self.time
        self.time = a[0]

    def undoInfo(self, **k):
        if k.get("query"):
            return self.undo
        self.undo = k.get("stateWithoutFlush", self.undo)

    def optionVar(self, **k):
        if "exists" in k:
            return k["exists"] in self.opts
        if "query" in k:
            return self.opts[k["query"]]
        for f in ("intValue", "floatValue", "stringValue"):
            if f in k:
                self.opts[k[f][0]] = k[f][1]

    def objExists(self, n):
        return n in self.nodes or n in self.made

    def createNode(self, t, name=None, parent=None, **k):
        full = (parent and "|" + parent.strip("|") + "|" or "|") + name
        self.nodes[full] = t
        self.made.append(full)
        return name

    def createDisplayLayer(self, **k):
        self.nodes[k["name"]] = "displayLayer"

    def editDisplayLayerMembers(self, *a, **k):
        return []

    def setAttr(self, *a, **k):
        pass

    def addAttr(self, *a, **k):
        pass

    def attributeQuery(self, *a, **k):
        return False

    def shadingNode(self, t, name=None, **k):
        self.nodes[name] = t

    def sets(self, *a, **k):
        if k.get("name"):
            self.nodes[k["name"]] = "shadingEngine"
            return k["name"]

    def connectAttr(self, *a, **k):
        pass

    def snapshot(self, m, startTime=None, **k):
        g = "%s_ghost_%g" % (m.split("|")[-1], startTime)
        self.nodes["|" + g] = "transform"
        self.nodes["snap_" + g] = "snapshot"
        self.made.append("|" + g)
        return ["|" + g, "snap_" + g]

    def parent(self, child, grp):
        new = grp + "|" + child.split("|")[-1]
        self.nodes[new] = self.nodes.pop(child)
        return [new]

    def delete(self, nodes):
        for n in (nodes if isinstance(nodes, list) else [nodes]):
            self.deleted.append(n)
            for k in [k for k in self.nodes if k == n or k.startswith(n + "|")]:
                self.nodes.pop(k, None)


fake = FakeCmds()
maya = types.ModuleType("maya")
maya.cmds = fake
sys.modules["maya"] = maya
sys.modules["maya.cmds"] = fake
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from onion_skin import core  # noqa: E402

# ---- which frames
check("keys: the key before and after (12 between 10 and 20)", core.frames_needed(12, 1, 1, "keys", keys=[1, 10, 20])
      == [(10, "past", 1), (20, "next", 1)])
check("keys: 2 past, 1 next - the nearest first", core.frames_needed(12, 2, 1, "keys", keys=[1, 10, 20]) ==
      [(10, "past", 1), (1, "past", 2), (20, "next", 1)])
check("keys: on a key, that key isn't a ghost", core.frames_needed(10, 1, 1, "keys", keys=[1, 10, 20]) ==
      [(1, "past", 1), (20, "next", 1)])
check("keys: past the last key, no next ghost", core.frames_needed(25, 1, 1, "keys", keys=[1, 10, 20]) ==
      [(20, "past", 1)])
check("every N frames: 2 past, 1 next, step 3", core.frames_needed(12, 2, 1, "frames", step=3) ==
      [(9, "past", 1), (6, "past", 2), (15, "next", 1)])
check("0 past / 0 next: no ghosts", core.frames_needed(12, 0, 0, "keys", keys=[1, 10, 20]) == [])
check("plan: ghosts still wanted are kept, only the new ones made",
      core.plan([("A", 10.0), ("A", 20.0)], [("A", 10.0), ("A", 1.0)]) == ([("A", 20.0)], [("A", 1.0)]))

# ---- what to ghost
check("a referenced character is its namespace, one without is its top group",
      core.scope_of("|A:RIG|A:ctrl") == ("ns", "A") and core.scope_of("|B_RIG|B_ctrl") == ("root", "|B_RIG"))
check("a control stands for its character's visible meshes (not the hidden Orig shape)",
      core.meshes_of("|A:RIG|A:ctrl") == ["|A:RIG|A:body"] and core.meshes_of("|B_RIG|B_ctrl") == ["|B_RIG|B_geo"])
check("a mesh stands for itself", core.meshes_of("|B_RIG|B_geo") == ["|B_RIG|B_geo"])
check("each character's own keys - and keys through a blend node count",
      core.key_times(["|A:RIG|A:ctrl"]) == [1.0, 10.0, 20.0, 30.0] and core.key_times(["|B_RIG|B_ctrl"]) == [5.0, 15.0])

# ---- the whole update, two characters
core.add_targets(["|A:RIG|A:ctrl", "|B_RIG|B_ctrl"])
got = core.update(now=12.0)
check("two characters: each at its own keys (A 10 / 20, B 5 / 15)",
      got["frames"] == {"A": [10.0, 20.0], "B_RIG": [5.0, 15.0]} and got["made"] == 4)
check("the undo queue is left as it was", fake.undo is True)
got = core.update(now=14.0)
check("moving between the same keys: nothing made again", got["made"] == 0 and got["removed"] == 0)
got = core.update(now=16.0)
check("past B's last key: the 5 ghost goes, the 15 one is kept (recoloured as past), nothing rebuilt",
      got["frames"]["B_RIG"] == [15.0] and got["removed"] == 1 and got["made"] == 0)
fake.hidden.add("|B_RIG|B_geo")
got = core.update(now=16.0)
check("a hidden mesh isn't ghosted (it says so)", "B_RIG: no visible meshes" in got["notes"])
fake.hidden.clear()
core.clear(keep_targets=False)
check("Clear list: no ghost and no list left", core.TARGETS == [] and core.built_frames() == [])

# ---- empty list: the selection goes in
fake.selection = ["|B_RIG|B_ctrl"]
got = core.update(now=12.0)
check("empty list + Update: the selection is used and kept in the list (Live follows it)",
      core.TARGETS == ["|B_RIG|B_ctrl"] and got["frames"] == {"B_RIG": [5.0, 15.0]})
core.clear(keep_targets=False)
fake.selection = []
try:
    core.update(now=12.0)
    said = ""
except RuntimeError as e:
    said = str(e)
check("nothing in the list or selected: it says what to do", "Add selected" in said)

print("%d/%d passed" % (sum(ok), len(ok)))
