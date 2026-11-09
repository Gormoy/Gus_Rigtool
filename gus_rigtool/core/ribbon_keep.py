"""
Keep the character's skin when a ribbon's bind joints are rebuilt (4.3.0): Rebuild (e.g. with more or fewer
controls), Replace the surface, Face kit re-runs.

    saved = park(key)       # before the build goes: the bind joints' weights on OTHER skins are saved and parked
                            # on a holder joint (so nothing is renormalised), then the bind joints leave those skins
    ...rebuild...
    restore(saved, key)     # after: each old joint's weights go to the new joint with its name, else the nearest
                            # new bind joint; the holder goes. Other influences are never touched.

The ribbon's own skin is made again by the build; only meshes skinned to the ribbon's joints are kept here.
"""

import maya.cmds as cmds

from gus_rigtool.core import naming

HOLDER = "gusRibbonKeep_holder"


def _api():
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    return om, oma


def bind_joints(key):
    """The bind joints of a build: every influence of the ribbon's own skin (else the joints its controls drive)."""
    from gus_rigtool.core import ribbon
    builds = ribbon._find_builds()
    if key not in builds:
        return []
    out = []
    for skin in builds[key]["skins"]:
        if cmds.objExists(skin):
            for j in cmds.skinCluster(skin, query=True, influence=True) or []:
                j = (cmds.ls(j, long=True) or [j])[0]
                if j not in out:
                    out.append(j)
    if not out:
        for off in ribbon._build_offsets(builds[key]).values():
            c = ribbon._control_under(off)
            j = ribbon.bind_of(c)[0] if c else None
            if j and j not in out:
                out.append(j)
    return out


def other_skins(joints, exclude=()):
    out = []
    for j in joints:
        for s in cmds.listConnections(j + ".worldMatrix", type="skinCluster", source=False, destination=True) or []:
            if s not in out and s not in exclude:
                out.append(s)
    return out


def _skin_fn(skin):
    om, oma = _api()
    sel = om.MSelectionList()
    sel.add(skin)
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    path = om.MDagPath.getAPathTo(fn.getOutputGeometry()[0])
    cfn = om.MFnSingleIndexedComponent()
    comp = cfn.create(om.MFn.kMeshVertComponent)
    cfn.setCompleteData(om.MFnMesh(path).numVertices)
    return fn, path, comp


def _influences(fn):
    """{short name: index in influenceObjects}."""
    return {naming.short_name(p.fullPathName()): i for i, p in enumerate(fn.influenceObjects())}


def _set(fn, path, comp, values):
    """values: {influence index: [weight per vertex]}."""
    om, _oma = _api()
    order = sorted(values)
    if not order:
        return
    idx = om.MIntArray()
    for i in order:
        idx.append(i)
    vals = om.MDoubleArray()
    n = len(values[order[0]])
    for v in range(n):
        for i in order:
            vals.append(values[i][v])
    fn.setWeights(path, comp, idx, vals, False)


def _holder():
    if cmds.objExists(HOLDER):
        return cmds.ls(HOLDER, long=True)[0]
    cmds.select(clear=True)
    j = cmds.joint(name=HOLDER)
    cmds.setAttr(j + ".visibility", 0)
    return cmds.ls(j, long=True)[0]


def park(key):
    """Save the bind joints' weights on other meshes, park them on a holder joint, and take the bind joints out
    of those skins. Returns what restore() needs ({} when there's nothing to keep)."""
    from gus_rigtool.core import ribbon
    builds = ribbon._find_builds()
    own = builds[key]["skins"] if key in builds else []
    joints = bind_joints(key)
    names = {naming.short_name(j) for j in joints}
    saved = {"joints": {naming.short_name(j): cmds.xform(j, query=True, worldSpace=True, translation=True)
                        for j in joints}, "skins": {}}
    for skin in other_skins(joints, own):
        geo = cmds.skinCluster(skin, query=True, geometry=True) or []
        if not geo or cmds.nodeType(geo[0]) != "mesh":
            continue
        fn, path, comp = _skin_fn(skin)
        inf = _influences(fn)
        per = {nm: list(fn.getWeights(path, comp, i)) for nm, i in inf.items() if nm in names}
        if not per:
            continue
        saved["skins"][skin] = per
        holder = _holder()
        if naming.short_name(holder) not in inf:
            cmds.skinCluster(skin, edit=True, addInfluence=holder, lockWeights=True, weight=0.0)
            cmds.setAttr(holder + ".liw", False)
        fn, path, comp = _skin_fn(skin)
        inf = _influences(fn)
        n = len(next(iter(per.values())))
        total = [sum(per[nm][v] for nm in per) for v in range(n)]
        values = {inf[nm]: [0.0] * n for nm in per}
        values[inf[naming.short_name(holder)]] = total
        _set(fn, path, comp, values)
        for nm in per:
            j = [x for x in joints if naming.short_name(x) == nm][0]
            cmds.skinCluster(skin, edit=True, removeInfluence=j)
    return saved if saved["skins"] else {}


def mapping(old, new):
    """{old joint: new joint}: the same name when it still exists, else the nearest. old / new: {name: pos}."""
    out = {}
    for name, p in old.items():
        if name in new:
            out[name] = name
        elif new:
            out[name] = min(new, key=lambda n: sum((a - b) ** 2 for a, b in zip(new[n], p)))
    return out


def merge(weights, mapping_):
    """{new joint: [weights]} - the old joints' weights added up into the joints they map to."""
    out = {}
    for old, ws in weights.items():
        new = mapping_.get(old)
        if not new:
            continue
        out[new] = [a + b for a, b in zip(out[new], ws)] if new in out else list(ws)
    return out


def restore(saved, key):
    """The parked weights go onto the new bind joints; the holder leaves the skins. Returns the skins done."""
    if not saved or not saved.get("skins"):
        return 0
    joints = bind_joints(key)
    new = {naming.short_name(j): cmds.xform(j, query=True, worldSpace=True, translation=True) for j in joints}
    long_of = {naming.short_name(j): j for j in joints}
    mp = mapping(saved["joints"], new)
    done = 0
    holder = cmds.ls(HOLDER, long=True)
    for skin, per in saved["skins"].items():
        if not cmds.objExists(skin):
            continue
        target = merge(per, mp)
        have = {naming.short_name(x) for x in cmds.skinCluster(skin, query=True, influence=True) or []}
        for name in target:
            if name not in have:
                cmds.skinCluster(skin, edit=True, addInfluence=long_of[name], lockWeights=True, weight=0.0)
                cmds.setAttr(long_of[name] + ".liw", False)
        fn, path, comp = _skin_fn(skin)
        inf = _influences(fn)
        n = len(next(iter(target.values()))) if target else 0
        values = {inf[nm]: ws for nm, ws in target.items() if nm in inf}
        if holder and HOLDER in inf:
            values[inf[HOLDER]] = [0.0] * n
        _set(fn, path, comp, values)
        if holder and HOLDER in inf:
            cmds.skinCluster(skin, edit=True, removeInfluence=holder[0])
        done += 1
    if holder and not cmds.listConnections(holder[0] + ".worldMatrix", type="skinCluster"):
        cmds.delete(holder[0])
    return done
