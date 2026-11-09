# Attributes tool: move in the list, reorder with the delete / undo trick (values, keys, connections kept),
# undo off refused, add / rename / edit / copy / delete, and the page (list follows the selection)
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
from unittest import mock
cmds.scriptJob = mock.MagicMock(return_value=1)
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
_last = []
def _delete_attr(plug, **k):
    n, a = _split(plug)
    kept = [c for c in S.conns if (c[2] is n and c[3] == a) or (c[0] is n and c[1] == a)]
    S.conns[:] = [c for c in S.conns if c not in kept]
    _last.append((n, a, n.user.pop(a), getattr(n, "types", {}).get(a), kept, a in n.locks))
cmds.deleteAttr = _delete_attr
calls = {"undo": 0}
def _undo():
    calls["undo"] += 1
    n, a, v, t, kept, lk = _last.pop()
    n.user[a] = v                                    # back at the END, like Maya
    S.conns.extend(kept)
cmds.undo = _undo
state = {"on": True}
cmds.undoInfo = lambda **k: state["on"] if k.get("query") else None
def _rename_attr(plug, new):
    n, a = _split(plug)
    n.user = {(new if k == a else k): v for k, v in n.user.items()}
cmds.renameAttr = _rename_attr
_aq = cmds.attributeQuery
def attributeQuery(attr, node=None, **k):
    if k.get("listParent") or k.get("minExists") or k.get("maxExists"):
        return None
    if k.get("niceName"):
        return getattr(_n(node), "nice", {}).get(attr, attr)
    return _aq(attr, node=node, **k)
cmds.attributeQuery = attributeQuery
_add = cmds.addAttr
def addAttr(*a, **k):
    if k.get("edit"):
        print("  edit", a[0], sorted(x for x in k if x != "edit"))
        return
    _add(*a, **k)
    if k.get("niceName"):
        n = _n(a[0]); n.nice = getattr(n, "nice", {}); n.nice[k["longName"]] = k["niceName"]
cmds.addAttr = addAttr
from gus_rigtool.core import attrs
from gus_rigtool.builder import controls

a = cmds.createNode("transform", name="L_hand_ctrl")
for x in ("curl", "spread", "fist"):
    controls.add_float(a, x)
controls.separator(a, "Fingers")
controls.add_float(a, "thumb")
key = cmds.createNode("animCurveTU", name="curl_key"); cmds.connectAttr(key + ".output", a + ".curl")
drv = cmds.createNode("transform", name="driven"); cmds.connectAttr(a + ".spread", drv + ".tx")
cmds.setAttr(a + ".fist", 0.7)
print("attrs:", attrs.user_attrs(a))
print("labels:", [attrs.label(a, x) for x in attrs.user_attrs(a)])
order = attrs.user_attrs(a)
print("move thumb top:", attrs.move(order, ["thumb"], "top"))
print("move curl+spread down:", attrs.move(order, ["curl", "spread"], "down"))
print("move separator up:", attrs.move(order, ["_Fingers"], "up"))
print("move fist bottom:", attrs.move(order, ["fist"], "bottom"))
wanted = ["_Fingers", "thumb", "curl", "spread", "fist"]
print("to move:", attrs.to_move(order, wanted))
print("only the tail moves:", attrs.to_move(order, ["curl", "spread", "fist", "thumb", "_Fingers"]))
state["on"] = False
try:
    attrs.apply_order(a, wanted); print("undo off: NOT refused")
except RuntimeError as e:
    print("undo off refused:", str(e)[:40], "| attrs untouched:", attrs.user_attrs(a) == order)
state["on"] = True
n = attrs.apply_order(a, wanted)
print("moved", n, "->", attrs.user_attrs(a), "| undo calls:", calls["undo"])
print("kept: fist", cmds.getAttr(a + ".fist"), "| key", cmds.listConnections(a + ".curl", source=True, destination=False),
      "| drives", cmds.listConnections(a + ".spread", source=False, destination=True, plugs=True),
      "| separator locked", "_Fingers" in _n(a).locks)
print("same again changes nothing:", attrs.apply_order(a, wanted))

# add / rename / edit / copy / delete
print("add int:", attrs.add(a, "count", "int", "0", "10", "3"), _n(a).types["count"])
print("add enum:", attrs.add(a, "mode", "enum", enum="off, on"), _n(a).enums["mode"])
print("add separator:", attrs.add(a, "Extra Stuff", "separator"), attrs.is_separator(a, "_Extra_Stuff"))
for bad in (("9x", "float"), ("count", "int"), ("e", "enum")):
    try:
        attrs.add(a, bad[0], bad[1]); print("NOT refused", bad)
    except (ValueError, RuntimeError) as e:
        print("refused:", e)
attrs.rename(a, "count", "amount"); print("renamed:", "amount" in attrs.user_attrs(a), "count" in attrs.user_attrs(a))
print("edit:", attrs.edit(a, "amount", "1", "", "2"))
b = cmds.createNode("transform", name="R_hand_ctrl")
added, updated = attrs.copy(a, b, ["_Fingers", "curl", "fist", "mode"], connections=True)
print("copied:", added, updated, "| b:", attrs.user_attrs(b), "| curl keyed on b:",
      cmds.listConnections(b + ".curl", source=True, destination=False), "| fist", cmds.getAttr(b + ".fist"))
attrs.delete(a, "_Extra_Stuff"); print("deleted separator:", "_Extra_Stuff" in attrs.user_attrs(a))

# the page
from gus_rigtool.tools import attr_tool as at
from gus_rigtool.core import ui
_cur[0] = None; cmds.columnLayout("root"); ui._build_tool("attrs", "p_attrs_"); at._P["p"] = "p_attrs_"
c = cmds.createNode("transform", name="C_spine_ctrl")
for x in ("aa", "bb", "cc"):
    controls.add_float(c, x)
d = cmds.createNode("transform", name="C_neck_ctrl")
for x in ("cc", "bb", "aa", "zz"):
    controls.add_float(d, x)
cmds.select([c, d]); at.reload()
print("list:", UI["p_attrs_List"].get("append"), "| light:", at._light()[1])
cmds.textScrollList("p_attrs_List", edit=True, selectIndexedItem=[3]); UI["p_attrs_List"]["selectIndexedItem"] = [3]
at._move("top")
print("pending:", at._st()["order"], "| note:", UI["p_attrs_ListNote"]["label"])
at.apply_order()
print("spine:", attrs.user_attrs(c), "| neck:", attrs.user_attrs(d))
at.back_order()
print("back:", attrs.user_attrs(c), attrs.user_attrs(d))
