# 5.4.0: Deliver puts the model inside the delivered rig - the referenced model imported, its namespace merged
# away, the duplicate names that leaves renamed - in a copy, and your scene opened again
import sys
exec(open("fakemaya.py").read())
from unittest import mock
from gus_rigtool.builder import deliver
ok = []
def check(label, cond):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label)

calls = []
REFS = ["H:/model/Geo_Hare_08_MovedTail.mb"]
NS = ["Geo_Hare_07"]
def file_(*a, **k):
    if k.get("query") and k.get("reference"):
        return list(REFS)
    if k.get("importReference"):
        calls.append(("import", a[0])); REFS.remove(a[0])
    elif k.get("removeReference"):
        calls.append(("remove", a[0])); REFS.remove(a[0])
def namespace(**k):
    calls.append(("merge", k["removeNamespace"])); NS.remove(k["removeNamespace"])
from gus_rigtool.tools import checker
with mock.patch.object(cmds, "file", side_effect=file_, create=True), \
        mock.patch.object(cmds, "referenceQuery", side_effect=lambda r, **k: True, create=True), \
        mock.patch.object(cmds, "namespaceInfo", side_effect=lambda *a, **k: list(NS) + ["UI", "shared"],
                          create=True), \
        mock.patch.object(cmds, "namespace", side_effect=namespace, create=True), \
        mock.patch.object(checker, "find_dup_names", lambda scope: ["|a|Belt", "|a|Belt|Belt"]), \
        mock.patch.object(checker, "fix_dup_names", lambda nodes, ask=True: 1 if not ask else 0):
    lines = deliver.model_inside()
print(calls)
print(lines)
check("the model imported (no reference left)", ("import", "H:/model/Geo_Hare_08_MovedTail.mb") in calls and
      not REFS)
check("its namespace merged away; Maya's UI / shared left", ("merge", "Geo_Hare_07") in calls and
      not [c for c in calls if c[0] == "merge" and c[1] in ("UI", "shared")])
check("the duplicate names it leaves renamed, without asking", any("renamed" in l for l in lines))

# deliver refuses to open a copy while your scene has unsaved changes (nothing lost)
with mock.patch.object(deliver.publish, "rig_group", lambda: "|rig"), \
        mock.patch.object(cmds, "file", side_effect=lambda *a, **k: (["x.mb"] if k.get("reference") else
                                                                       ("H:/work.ma" if k.get("sceneName") else
                                                                        True if k.get("modified") else None)),
                          create=True):
    try:
        deliver.deliver("/tmp/x", "hare")
        refused = ""
    except RuntimeError as e:
        refused = str(e)
check("unsaved changes: refused, asks to save first", "save it first" in refused)
print("%d/%d passed" % (sum(ok), len(ok)))
sys.exit(0 if all(ok) else 1)
