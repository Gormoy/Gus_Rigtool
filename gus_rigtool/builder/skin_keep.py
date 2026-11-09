"""
Keep the skin when the rig's joints are deleted (Back to guides, Rebuild selected):
the weights of every mesh skinned to those joints are saved to files (Maya's deformerWeights,
by vertex index), the meshes are unbound, and after the next Build each mesh is skinned again to
the joints with the same names and its weights are put back.

Files: <Gus_Rigtool data>/skin_backup/<scene name>/<mesh>.xml
The list of saved meshes lives on guides_grp (attribute gusSkinBackup), so it travels with the scene.
"""

import json
import os
import re

import maya.cmds as cmds

import gus_rigtool
from gus_rigtool.builder import guides
from gus_rigtool.core import naming, utils

TOOL = "Build"
ATTR = "gusSkinBackup"
BOUND = "__bound__"                 # manifest key: skins kept bound (in-place mode)
CHECK = "__check__"                 # manifest key: each skin's joints before the rebuild (checked after)
SPECIAL = (BOUND, CHECK)
HOLDERS = "gus_skinHolders_grp"


def _dir():
    scene = cmds.file(query=True, sceneName=True, shortName=True) or "untitled"
    scene = re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.splitext(scene)[0]) or "untitled"
    path = os.path.join(gus_rigtool.ROOT, "data", "skin_backup", scene)
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def _manifest():
    top = guides.top_group(create=False)
    if not top or not cmds.attributeQuery(ATTR, node=top, exists=True):
        return {}
    try:
        return json.loads(cmds.getAttr(top + "." + ATTR) or "{}")
    except ValueError:
        return {}


def _write_manifest(data):
    top = guides.top_group(create=True)
    if not cmds.attributeQuery(ATTR, node=top, exists=True):
        cmds.addAttr(top, longName=ATTR, dataType="string")
    cmds.setAttr(top + "." + ATTR, json.dumps(data), type="string")


def skins_on(joints):
    """Skin clusters that use any of these joints."""
    out = []
    for j in joints:
        if not cmds.objExists(j):
            continue
        for s in cmds.listConnections(j + ".worldMatrix", type="skinCluster", source=False,
                                      destination=True) or []:
            if s not in out:
                out.append(s)
    return out


def _mesh_of(skin):
    geo = cmds.skinCluster(skin, query=True, geometry=True) or []
    if not geo:
        return None
    node = geo[0]
    if cmds.nodeType(node) != "transform":
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
    return cmds.ls(node, long=True)[0]


def _holders_grp():
    found = cmds.ls(HOLDERS, long=True) or []
    if found:
        return found[0]
    g = cmds.createNode("transform", name=HOLDERS)
    cmds.setAttr(g + ".visibility", 0)
    return cmds.ls(g, long=True)[0]


def save_bound(joints):
    """Keep the skins bound: each of these joints' slots in a skin is held by a hidden locator at the joint's
    place (the mesh doesn't move), and the joint's name is written down. After the build the new joint with
    that name takes the slot back, with its new bind position. Returns the skins kept."""
    data = _manifest()
    bound = data.get(BOUND, {})
    longs = set(utils.ls(joints, long=True) or [])
    kept = []
    for skin in skins_on(joints):
        pairs = cmds.listConnections(skin + ".matrix", source=True, destination=False, plugs=True,
                                     connections=True) or []
        slots = bound.get(skin, {})
        for dst, src in zip(pairs[0::2], pairs[1::2]):
            j = (cmds.ls(src.split(".")[0], long=True) or [None])[0]
            if j not in longs or "[" not in dst:
                continue
            index = dst[dst.rindex("[") + 1:dst.rindex("]")]
            holder = cmds.createNode("transform", name=naming.short_name(j) + "_skinHolder", parent=_holders_grp())
            cmds.xform(holder, worldSpace=True, matrix=cmds.getAttr(j + ".worldMatrix[0]"))
            cmds.connectAttr(holder + ".worldMatrix[0]", "%s.matrix[%s]" % (skin, index), force=True)
            for p in cmds.listConnections(j + ".lockInfluenceWeights", source=False, destination=True, plugs=True) \
                    or [] if cmds.attributeQuery("lockInfluenceWeights", node=j, exists=True) else []:
                if p.split(".")[0] == skin.split("|")[-1]:
                    cmds.disconnectAttr(j + ".lockInfluenceWeights", p)
            slots[index] = {"joint": naming.short_name(j), "holder": naming.short_name(holder)}
        if slots:
            bound[skin] = slots
            kept.append(skin)
    if kept:
        data[BOUND] = bound
        _write_manifest(data)
    return kept


def restore_bound():
    """The new joints take their slots back (bind position = where they are now). Returns (slots, notes)."""
    data = _manifest()
    bound = data.get(BOUND, {})
    done, notes, left = 0, [], {}
    for skin, slots in bound.items():
        if not cmds.objExists(skin):
            notes.append("%s: the skin is gone" % skin)
            continue
        for index, slot in slots.items():
            found = cmds.ls(slot["joint"], long=True, type="joint") or []
            if len(found) != 1:
                notes.append("%s: no single joint '%s' - its weights stay on %s (Skin 6 > Move weights)"
                             % (skin, slot["joint"], slot["holder"]))
                left.setdefault(skin, {})[index] = slot
                continue
            j = found[0]
            cmds.connectAttr(j + ".worldMatrix[0]", "%s.matrix[%s]" % (skin, index), force=True)
            inv = _inverse(cmds.getAttr(j + ".worldMatrix[0]"))
            cmds.setAttr("%s.bindPreMatrix[%s]" % (skin, index), inv, type="matrix")
            if cmds.attributeQuery("lockInfluenceWeights", node=j, exists=True):
                try:
                    cmds.connectAttr(j + ".lockInfluenceWeights", "%s.lockWeights[%s]" % (skin, index), force=True)
                except RuntimeError:
                    pass
            h = cmds.ls(slot["holder"], long=True) or []
            if h:
                cmds.delete(h)
            done += 1
    if left:
        data[BOUND] = left
    else:
        data.pop(BOUND, None)
        g = cmds.ls(HOLDERS, long=True) or []
        if g and not cmds.listRelatives(g[0], children=True):
            cmds.delete(g)
    _write_manifest(data)
    return done, notes


def _inverse(m):
    from gus_rigtool.core import mirror_engine as me
    return me.inverse(list(m))


def _remember_joints(skins):
    """Write down each skin's joints (by mesh), to check nothing was lost after the Build."""
    data = _manifest()
    check = data.get(CHECK, {})
    for skin in skins:
        mesh = _mesh_of(skin)
        if mesh:
            names = [naming.short_name(i) for i in cmds.skinCluster(skin, query=True, influence=True) or []]
            old = check.get(naming.short_name(mesh), [])
            check[naming.short_name(mesh)] = sorted(set(old) | set(names))
    data[CHECK] = check
    _write_manifest(data)


def check_joints():
    """After the Build: joints a mesh was skinned to that it isn't any more. Returns notes (and forgets)."""
    data = _manifest()
    check = data.pop(CHECK, {})
    notes = []
    for short, names in sorted(check.items()):
        found = cmds.ls(short, long=True) or []
        if len(found) != 1:
            continue
        skins = [k for k in cmds.ls(type="skinCluster") or [] if _mesh_of(k) == found[0]]
        if not skins:
            notes.append("%s: not skinned any more after the Build (it had %d joints)" % (short, len(names)))
            continue
        now = set(naming.short_name(i) for i in cmds.skinCluster(skins[0], query=True, influence=True) or [])
        lost = [n for n in names if n not in now and n + "_skinHolder" not in now]     # held ones: said already
        if lost:
            notes.append("%s: lost %d joint(s) from its skin: %s%s" % (short, len(lost), ", ".join(lost[:6]),
                                                                       "..." if len(lost) > 6 else ""))
    _write_manifest(data)
    return notes


def save(joints, bound=False):
    """Save and unbind every mesh skinned to these joints (bound: keep them bound, see save_bound).
    Returns the meshes / skins saved."""
    _remember_joints(skins_on(joints))
    if bound:
        return save_bound(joints)
    skins = skins_on(joints)
    if not skins:
        return []
    data = _manifest()
    folder = _dir()
    saved = []
    for skin in skins:
        mesh = _mesh_of(skin)
        if not mesh:
            continue
        short = naming.short_name(mesh)
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", short) + ".xml"
        cmds.deformerWeights(filename, export=True, deformer=skin, path=folder)
        data[short] = {
            "file": filename, "folder": folder, "skin": skin,
            "influences": [naming.short_name(i) for i in cmds.skinCluster(skin, query=True, influence=True) or []],
            "max_influences": cmds.skinCluster(skin, query=True, maximumInfluences=True),
            "method": cmds.skinCluster(skin, query=True, skinMethod=True),
        }
        cmds.skinCluster(skin, edit=True, unbind=True)
        saved.append(short)
    if saved:
        _write_manifest(data)
    return saved


def pending():
    data = _manifest()
    return sorted(k for k in data if k not in SPECIAL or (k == BOUND and data[BOUND]))


def restore():
    """Skin the saved meshes again and put their weights back. Returns (restored, notes)."""
    restored, notes = [], []
    if _manifest().get(BOUND):
        n, bnotes = restore_bound()
        notes += bnotes
        if n:
            restored.append("%d joint slot(s) kept bound" % n)
    data = _manifest()
    for short, entry in list(data.items()):
        if short in SPECIAL:
            continue
        found = cmds.ls(short, long=True) or []
        if len(found) != 1:
            notes.append("%s: mesh not found" % short)
            continue
        mesh = found[0]
        if utils.ls(cmds.listHistory(mesh, pruneDagObjects=True) or [], type="skinCluster"):
            notes.append("%s: already skinned, left as it is" % short)
            del data[short]
            continue
        joints = [j for j in entry["influences"] if len(cmds.ls(j) or []) == 1]
        missing = [j for j in entry["influences"] if j not in joints]
        if not joints:
            notes.append("%s: none of its joints exist any more" % short)
            continue
        skin = cmds.skinCluster(joints, mesh, toSelectedBones=True,
                                maximumInfluences=entry.get("max_influences", 4),
                                skinMethod=entry.get("method", 0),
                                name=entry.get("skin") or short + "_skinCluster")[0]
        cmds.deformerWeights(entry["file"], im=True, deformer=skin, method="index",
                             path=entry.get("folder") or _dir())
        try:
            cmds.skinCluster(skin, edit=True, forceNormalizeWeights=True)
        except RuntimeError:
            pass
        if missing:
            notes.append("%s: %d joint(s) no longer exist, their weights went to the others (%s)"
                         % (short, len(missing), ", ".join(missing[:4])))
        restored.append(short)
        del data[short]
    _write_manifest(data)
    notes += check_joints()
    return restored, notes


def report(restored, notes):
    if restored:
        utils.info(TOOL, "skin put back on %d mesh(es): %s" % (len(restored), ", ".join(restored[:5])))
    for n in notes:
        utils.warn(TOOL, n)
