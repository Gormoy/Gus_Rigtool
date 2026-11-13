"""
Check this scene: reads the open file (your character) and writes a diagnosis - problems first, then what's in
the scene (each ribbon, follow, skin, stuck control...). It only reads: nothing in the scene changes.

    import gus_rigtool.scene_check as sc; sc.run()

Send the report (Copy report) to get what's wrong fixed. Each part is checked on its own: if one crashes, the
report says which, and the others still run.
"""

import os

import maya.cmds as cmds

from gus_rigtool.core import nodes as _nodes

from gus_rigtool.core.report import FAIL, INFO, NOTE, OK, WARN, Report

MAX_NAMES = 8


def _short(n):
    return (n or "").split("|")[-1]


def _names(nodes, n=MAX_NAMES):
    nodes = [_short(x) for x in nodes]
    return ", ".join(nodes[:n]) + (" ... (+%d)" % (len(nodes) - n) if len(nodes) > n else "")


_wm = _nodes.world_matrix


def mirror_tol():
    """The skin mirror tolerance (Settings > Skin, 5.3.4): pairs closer than this mirror fine."""
    try:
        from gus_rigtool.core import utils
        from gus_rigtool.tools import skin_tool
        return float(utils.tool_settings(skin_tool.SETTINGS_KEY, skin_tool.DEFAULTS).get("mirror_tol", 0.01))
    except Exception:
        return 0.01


def _height():
    """Rough size of the character (for tolerances)."""
    meshes = cmds.ls(type="mesh", noIntermediate=True, long=True) or []
    ys = []
    for m in meshes[:200]:
        try:
            bb = cmds.exactWorldBoundingBox(m)
            ys += [bb[1], bb[4]]
        except (RuntimeError, ValueError):
            pass
    if not ys:
        js = cmds.ls(type="joint", long=True) or []
        ys = [cmds.xform(j, query=True, worldSpace=True, translation=True)[1] for j in js[:500]] or [0.0, 1.0]
    return max(max(ys) - min(ys), 1e-3)


# ---------------------------------------------------------------------------
# parts
# ---------------------------------------------------------------------------

def check_scene(rep):
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import guides
    from gus_rigtool.tools import checker
    rep.start("Scene")
    path = cmds.file(query=True, sceneName=True) or "(not saved)"
    rep.add(INFO, "file", "%s%s" % (path, "  (unsaved changes)" if cmds.file(query=True, modified=True) else ""))
    unit = cmds.currentUnit(query=True, linear=True)
    rep.add(INFO, "units / up / fps", "%s, %s up, %s" % (unit, cmds.upAxis(query=True, axis=True),
                                                       cmds.currentUnit(query=True, time=True)))
    if unit != "cm":
        rep.add(NOTE, "scene units are %s" % unit, "Gus_Rigtool sizes assume cm (controls may look too big / small)")
    _auto_key(rep)
    _default_material(rep)
    joints = cmds.ls(type="joint") or []
    trs = cmds.ls(type="transform", long=True) or []
    ctrls = [t for t in trs if checker.is_control(t)]
    rep.add(INFO, "counts", "%d joints, %d controls, %d meshes, %d skins, %d blendShapes, %d constraints" % (
        len(joints), len(ctrls), len(cmds.ls(type="mesh", noIntermediate=True) or []),
        len(cmds.ls(type="skinCluster") or []), len(cmds.ls(type="blendShape") or []),
        len(cmds.ls(type="constraint") or [])))
    try:
        from gus_rigtool.builder import publish
        published = publish.is_published()
    except Exception:
        published = None
    rep.add(INFO, "rig", "built: %s, published: %s, guide modules: %d" % (
        "yes" if bld.is_built() else "no", {True: "yes", False: "no"}.get(published, "?"),
        len(guides.module_groups())))
    plugins = cmds.unknownPlugin(query=True, list=True) or []
    if plugins:
        rep.add(WARN, "plugins the file asks for that aren't loaded", ", ".join(plugins))
    refs = cmds.file(query=True, reference=True) or []
    if refs:
        rep.add(INFO, "references", _names([os.path.basename(r) for r in refs]))
    rep.add(OK, "scene read")


def check_guides(rep):
    from gus_rigtool.builder import guides
    rep.start("Guides")
    groups = guides.module_groups()
    if not groups:
        rep.add(INFO, "no guide modules", "(a rig made elsewhere, or published without guides)")
        return
    bad = []
    for g in groups:
        info = guides.read(g)
        pos = guides.positions(g)
        zero = [r for r, p in pos.items() if guides._at_origin(p)]
        if pos and len(zero) * 2 >= len(pos) and len(pos) > 2:
            bad.append("%s (%d of %d at 0,0,0)" % (info["id"], len(zero), len(pos)))
    if bad:
        rep.add(WARN, "guides sitting at the origin", "%s - Build tab > Guides: 'Guides from the rig' puts them "
                "back on the joints" % "; ".join(bad[:6]))
    else:
        rep.add(OK, "%d guide module(s) where they should be" % len(groups))


def check_checker(rep):
    from gus_rigtool.tools import checker
    rep.start("Checker (every rig check, the whole scene)")
    results = checker.run_checks(dict(checker.DEFAULTS), [])
    labels = {c[0]: (c[1], c[2]) for c in checker.CHECKS}
    for cid, (sev, nodes) in results.items():
        area, label = labels.get(cid, ("", cid))
        name = "%s: %s" % (area, label)
        if sev == "PASS":
            rep.add(OK, name)
        elif sev == "ERROR":
            rep.add(FAIL, name + " (the check crashed)", str(nodes))
        else:
            n = nodes if isinstance(nodes, list) else []
            status = {"FAIL": FAIL, "WARN": WARN}.get(sev, INFO)
            if cid in ("dup_names", "dup_names_ref"):          # 5.3.3: where each copy is - the short name can't
                shown = "; ".join(n[:MAX_NAMES]) + (" ... (+%d)" % (len(n) - MAX_NAMES) if len(n) > MAX_NAMES
                                                    else "")
                rep.add(status, "%s (%d)" % (name, len(n)), shown + (" - Checker > Duplicate names > Fix renames "
                                                                     "the extra copies" if cid == "dup_names"
                                                                     else ""))
            elif cid == "mesh_history":                        # 5.6.31: what it is, and where to clean it
                rows = []
                for m in n[:MAX_NAMES]:
                    hist, ref = checker.history_detail(m)
                    rows.append("%s: %s - %s" % (_short(m), ", ".join(hist[:3]) + (" ..." if len(hist) > 3 else ""),
                                                 "in the model file" if ref else "in this file"))
                rep.add(status, "%s (%d)" % (name, len(n)), "; ".join(rows) + " - careful: history that places a "
                        "mesh (a mirror, a move) moves it when it's deleted; the Checker's fix puts back any that "
                        "move")
            else:
                rep.add(status, "%s (%d)" % (name, len(n)), _names(n))


def _mirror_rows(m, ax=0):
    """The axes of a true mirror of matrix m across the axis (rows 0-2)."""
    from gus_rigtool.core import mirror_engine
    return mirror_engine.mirror_list(list(m), "true", ax)[:12]


def check_ribbons(rep):
    from gus_rigtool.core import ribbon
    rep.start("Ribbons")
    builds = ribbon._find_builds()
    if not builds:
        rep.add(INFO, "no ribbon builds")
        return
    try:                                                    # 5.6.9
        dead = ribbon.dead_twins()
    except Exception:
        dead = []
    if dead:
        in_skin = set(j for j, _s in ribbon.dead_twin_skins(dead))
        rep.add(WARN if in_skin else NOTE, "bind joints that follow nothing, on a working joint's spot (%d)" % len(dead),
                "%s - the ribbon's loop folds onto itself (closed lips: upper and lower lip on the same line); one of "
                "each pair got the control%s" % (_names([j for j, _t in dead]), (". %d are still in a skin: Repair "
                                                                                "takes them out" % len(in_skin))
                                                  if in_skin else ""))
    for key, build in builds.items():
        name = _short(key)
        st = ribbon._build_settings(build) or {}
        offs = ribbon._build_offsets(build)
        ctrls = {i: ribbon._control_under(o) for i, o in offs.items()}
        modes = {}
        missing = []
        for i, c in ctrls.items():
            if not c:
                continue
            j, mode = ribbon.bind_of(c)
            modes.setdefault(mode, []).append(c)
            if not j:
                missing.append(c)
        looped = False
        try:
            looped = ribbon.is_looped(key) if cmds.objExists(key) else False
        except Exception:
            pass
        skins = []
        if cmds.objExists(key):
            hist = cmds.listHistory(key, pruneDagObjects=True) or []
            skins = [h for h in hist if cmds.nodeType(h) == "skinCluster"]
        fols = [n for n in build["nodes"] if n.endswith("_follicles_grp") and cmds.objExists(n)]
        nfol = len(cmds.listRelatives(fols[0], children=True) or []) if fols else 0
        facts = ["%d follicles" % nfol, "%d controls" % len([c for c in ctrls.values() if c]),
                 "loop" if looped else "open", "skinned" if skins else "NOT skinned",
                 "pivot on the shape" if st.get("pivot_on_shape") else "pivot on the joint",
                 "joints: " + ", ".join("%s %d" % (m, len(v)) for m, v in sorted(modes.items()))]
        if st.get("pivot_scale"):
            facts.append("scale controls on")
        if any(cmds.objExists(n + ".rrbMirrorOf") for n in build["nodes"]):
            facts.append("mirrored build")
        try:
            loose = ribbon._loose_binds([c for c in ctrls.values() if c])
        except Exception:
            loose = []
        if loose:
            rep.add(NOTE, "%s: %d joint(s) hang under their controls (not constrained)" % (name, len(loose)),
                    "on a mirrored (-1 scale) control Maya adds a 'transform1' each time one is touched, and the "
                    "two sides aren't made alike - Ribbon tab > 'Switch to constraints' (or Repair)")
        try:                                            # 5.6.27: a ribbon whose base isn't meant to mirror
            asym = ribbon.is_asymmetric(key)
        except Exception:
            asym = False
        if asym:
            facts.append("marked not symmetric (no mirror checks)")
        # right side mirrored? (a loop round both sides)
        if looped and not asym and len([c for c in ctrls.values() if c]) > 2:
            pos = {i: cmds.xform(o, query=True, worldSpace=True, translation=True) for i, o in offs.items()}
            span = max(max(p[0] for p in pos.values()) - min(p[0] for p in pos.values()), 1e-6)
            tol = span * 0.01
            lefts = [i for i, p in pos.items() if p[0] > tol]
            rights = [i for i, p in pos.items() if p[0] < -tol]
            off = 0
            for r in rights:
                q = pos[r]
                if not lefts:
                    break
                left = min(lefts, key=lambda i: sum((a - b) ** 2 for a, b in zip(pos[i], (-q[0], q[1], q[2]))))
                want = _mirror_rows(_wm(offs[left]))
                have = _wm(offs[r])[:12]
                if max(abs(a - b) for a, b in zip(want, have)) > 1e-2:
                    off += 1
            if rights and off:
                rep.add(WARN, "%s: %d right-side control(s) don't mirror their left twin" % (name, off),
                        "the same values move the sides differently - Ribbon tab > 'Make the right side mirror "
                        "the left'; if its base isn't meant to be symmetric (a collar): Ribbon tab > 'Not "
                        "symmetric' and the warning goes")
            elif rights:
                facts.append("right side mirrors the left")
        if looped and not asym:
            try:
                sym = ribbon.symmetry_report(key)
                off = sym["controls"] + sym["follicles"]
            except Exception:
                off = []
            tol = mirror_tol()
            if off and max(x[2] for x in off) < tol:            # 5.3.4: closer than skin mirroring needs
                facts.append("left / right within %.4f (skin mirror tolerance %g)" % (max(x[2] for x in off), tol))
            elif off:
                worst = max(off, key=lambda x: x[2])
                rep.add(NOTE, "%s: %d left / right pair(s) not exactly symmetric (up to %.4f, %s)" % (
                    name, len(off), worst[2], _short(worst[1])),
                    "skin mirroring by distance (tolerance %g) can miss them - Ribbon tab > 'Make symmetric' (or "
                    "Repair)" % tol)
        rep.add(INFO, name, ", ".join(facts))
        try:
            along_v = cmds.objExists(key) and ribbon.runs_along_v(key)
        except Exception:
            along_v = False
        if along_v:
            rep.add(WARN, "%s: the ribbon runs along V, so its joints bunch across the width" % name,
                    "the controls barely spread - Checker > Repair 'Rebuild along the length' (weights kept)")
        if missing:
            rep.add(WARN, "%s: controls with no bind joint" % name, _names(missing))
        if modes.get("copy"):
            rep.add(WARN, "%s: joints copy their controls (direct connections)" % name,
                    "%d joint(s) - Ribbon tab > 'Switch to constraints' (nothing moves, weights kept)"
                    % len(modes["copy"]))
        if modes.get("copy + scale"):
            rep.add(NOTE if not st.get("pivot_scale") else INFO,
                    "%s: joints copy their controls, scale too (direct connections)" % name,
                    "%d joint(s) - wanted only for 'Scale controls too'; else Ribbon tab > 'Switch to constraints'"
                    % len(modes["copy + scale"]))
        if not skins and st.get("make_skin", True):
            rep.add(WARN, "%s: the ribbon isn't skinned to its joints" % name, "it won't move with the controls")
        binds = [n for n in build["nodes"] if n.endswith("_bind_grp") and cmds.objExists(n)]
        if binds and (modes.get("copy") or modes.get("copy + scale")) and \
                not cmds.listRelatives(binds[0], type="parentConstraint"):
            rep.add(WARN, "%s: its bind joints' group doesn't follow the controls' group" % name,
                    "moving / parenting the controls leaves the joints behind")
    rep.add(OK, "%d ribbon build(s) read" % len(builds))


def check_follows(rep):
    from gus_rigtool.core import follow, utils
    rep.start("Follows")
    groups = utils.nodes_with_attr(follow.META, "transform")
    if not groups:
        rep.add(INFO, "no follows")
        return
    for g in groups:
        m = follow._meta(g)
        if not m:
            rep.add(WARN, "%s: unreadable follow record" % _short(g))
            continue
        ctrl = m["ctrl"]
        if not ctrl:
            rep.add(WARN, "%s: its control is gone (was %s)" % (_short(g), m["stored_ctrl"] or "?"),
                    "Remove follow on that group, or delete the group")
            ctrl = _short(g)
        elif ctrl != m["stored_ctrl"]:
            ctrl = "%s (renamed from %s)" % (ctrl, m["stored_ctrl"]) if m["stored_ctrl"] else ctrl
        try:
            w = cmds.getAttr(m["weight"])
            weight = "%.2f" % w
        except (RuntimeError, ValueError):
            weight = "MISSING"
            rep.add(FAIL, "%s: its weight %s is gone" % (ctrl, m["weight"]), "Remove follow and add it again")
        src = m["source"]
        for node, what in ((m["driver"], "driver"), (src, "rotation from")):
            if node and not cmds.objExists(node):
                rep.add(FAIL, "%s: its %s %s is gone" % (ctrl, what, node), "Remove follow and add it again")
        gone = [n for n in m["nodes"] if not cmds.objExists(n)]
        if gone:
            rep.add(FAIL, "%s: follow nodes missing" % ctrl, _names(gone))
        piv = m.get("pivot", "driver")
        if piv not in ("driver", "control"):
            piv = "picked (%s)" % piv
        rep.add(INFO, ctrl, "<- %s%s x %s, %s, pivot %s, axes %s, %s" % (
            m["driver"], (" (rotation of %s)" % src) if src != m["driver"] else "", weight, "+".join(m["channels"]),
            piv, m.get("axes", "driver"), follow.describe(m["ctrl"]) if m["ctrl"] and cmds.objExists(m["ctrl"])
            else "?"))
        # extra: the follow group should be at rest when its driver is
        fol = g
        drv = src if cmds.objExists(src) else m["driver"]
        if cmds.objExists(drv) and cmds.objExists(fol):
            at_rest = all(abs(v) < 1e-4 for a in ("translate", "rotate") for v in cmds.getAttr(drv + "." + a)[0])
            moved = any(abs(v) > 1e-4 for a in ("translate", "rotate") for v in cmds.getAttr(fol + "." + a)[0])
            if at_rest and moved:
                rep.add(WARN, "%s: its follow group is turned while %s is at rest" % (ctrl, _short(drv)),
                        "something else drives it (a key or another connection)")
    rep.add(OK, "%d follow(s) read" % len(groups))


def check_labels(rep):
    from gus_rigtool.core import joint_labels
    rep.start("Joint labels (skin mirroring, ngSkinTools)")
    joints = joint_labels.skin_joints(mesh_only=True)
    if not joints:
        rep.add(INFO, "no joints skinning a mesh")
        return
    tol = _height() * 0.002
    unlabelled, wrong_side = [], []
    for j in joints:
        x = cmds.xform(j, query=True, worldSpace=True, translation=True)[0]
        try:
            side = cmds.getAttr(j + ".side")
            typ = cmds.getAttr(j + ".type")
            other = cmds.getAttr(j + ".otherType") or ""
        except (RuntimeError, ValueError):
            continue
        if typ == 0 or (typ == 18 and not other):
            unlabelled.append(j)
            continue                    # not labelled: its side isn't a label yet (listed above, not twice)
        if side == 0 and abs(x) > tol * 5:
            wrong_side.append("%s (centre, but at x %.2f)" % (_short(j), x))
        elif side == 1 and x < -tol:
            wrong_side.append("%s (left, but at x %.2f)" % (_short(j), x))
        elif side == 2 and x > tol:
            wrong_side.append("%s (right, but at x %.2f)" % (_short(j), x))
    if unlabelled:
        rep.add(WARN, "skinned joints with no label (%d)" % len(unlabelled),
                "%s - Skin tab > Label joints" % _names(unlabelled))
    if wrong_side:
        rep.add(WARN, "joints labelled on the wrong side (%d)" % len(wrong_side),
                "%s - Skin tab > Label joints" % "; ".join(wrong_side[:MAX_NAMES]))
    try:
        lonely = joint_labels.not_mirrored(joints)
    except Exception:
        lonely = []
    no_twin, twice = [], []
    for a, b, _d in lonely:
        if b:
            continue
        n = joint_labels.twin_count(a)
        if n > 1:
            twice.append("%d joints named %s" % (n, _short(joint_labels.twin_name(a))))
        else:
            no_twin.append(a)
    off = ["%s / %s (%.3f)" % (_short(a), _short(b), d) for a, b, d in lonely if b]
    if no_twin:
        rep.add(WARN, "left joints with no right twin (%d)" % len(no_twin),
                "%s - Skin tab > 'Add missing twins'" % _names(no_twin))
    if twice:
        rep.add(WARN, "twin names used by more than one joint (%d)" % len(twice),
                "%s - rename the extra one, so the left joint finds its twin" % "; ".join(twice[:MAX_NAMES]))
    if off:
        rep.add(NOTE, "twins that aren't mirror images (%d)" % len(off), "; ".join(off[:MAX_NAMES]))
    rep.add(OK, "%d joint(s) skinning a mesh read" % len(joints))


class MissingMesh(ValueError):
    """5.6.36: the skin's mesh isn't there as a mesh (the Hare on the Mac: the model file's path was the Windows
    drive, so the reference didn't load)."""


def _skin_weights(skin):
    """(vertex count, [sum of weights per vertex], [total weight per influence]) by the API."""
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    sel = om.MSelectionList()
    sel.add(skin)
    fn = oma.MFnSkinCluster(sel.getDependNode(0))
    geo = fn.getOutputGeometry()
    if not geo:
        return 0, [], []
    path = om.MDagPath.getAPathTo(geo[0])
    if not path.hasFn(om.MFn.kMesh):        # 5.6.36: not a mesh (its reference didn't load: a stand-in node)
        raise MissingMesh(path.partialPathName())
    cfn = om.MFnSingleIndexedComponent()
    comp = cfn.create(om.MFn.kMeshVertComponent)
    cfn.setCompleteData(om.MFnMesh(path).numVertices)
    weights, count = fn.getWeights(path, comp)
    w = list(weights)
    n = len(w) // count if count else 0
    sums = [sum(w[v * count:(v + 1) * count]) for v in range(n)]
    per = [sum(w[i::count]) for i in range(count)]
    return n, sums, per


def check_skin(rep):
    rep.start("Skin")
    skins = cmds.ls(type="skinCluster") or []
    if not skins:
        rep.add(INFO, "no skins")
        return
    from gus_rigtool.core import skin_tools as _st
    for skin in skins:
        try:
            tw = _st.twice(skin)
        except Exception:
            tw = {}
        if tw:                                                # 5.3.3
            rep.add(FAIL, "%s: joints plugged in twice (%d)" % (skin, len(tw)),
                    "%s - Maya's Paint Skin Weights ('already exists in the treeview') and ngSkinTools (hangs) "
                    "break; Repair merges each joint's two slots (the weights kept)" % _names(list(tw)))
        try:
            sn = _st.same_names(skin)
        except Exception:
            sn = {}
        if sn:                                                # 5.3.4
            rep.add(FAIL, "%s: different joints with the same name (%d)" % (skin, len(sn)),
                    "%s - Maya's Paint Skin Weights and ngSkinTools list joints by name and break; Checker > "
                    "Duplicate names > Fix renames the extra copies" % "; ".join(
                        "%s: %s" % (n, ", ".join(js)) for n, js in list(sn.items())[:MAX_NAMES]))
        geo = cmds.skinCluster(skin, query=True, geometry=True) or []
        infl = cmds.skinCluster(skin, query=True, influence=True) or []
        mx = cmds.getAttr(skin + ".maxInfluences")
        norm = cmds.getAttr(skin + ".normalizeWeights")
        facts = "%s, %d influences, max %d%s, normalize %s" % (
            _names(geo, 2), len(infl), mx, " (kept)" if cmds.getAttr(skin + ".maintainMaxInfluences") else "",
            {0: "off", 1: "interactive", 2: "post"}.get(norm, norm))
        try:
            got = _skin_weights(skin) if geo and cmds.nodeType(geo[0]) == "mesh" else None
        except MissingMesh as e:                    # 5.6.36: its model file didn't load - the others still read
            got = None
            facts += ", its mesh isn't loaded (%s) - weights not read" % e
        if got:
            n, sums, per = got
            bad = [i for i, s in enumerate(sums) if abs(s - 1.0) > 1e-3]
            unused = [infl[i] for i, t in enumerate(per) if t < 1e-6 and i < len(infl)]
            facts += ", %d vertices" % n
            if bad and norm == 2:
                facts += ", %d vertices not adding up to 1 (fine: Post normalises them when it deforms)" % len(bad)
            elif bad:
                rep.add(WARN, "%s: %d vertices whose weights don't add up to 1" % (skin, len(bad)),
                        "e.g. vtx %s - they shrink / grow when posed (Skin page > Cloth > Repair weights)" %
                        ", ".join(str(i) for i in bad[:6]))
            if unused:
                facts += ", %d joints with no weight" % len(unused)
        if norm == 0:
            rep.add(NOTE, "%s: normalize weights is off" % skin, "painting can leave weights that don't add up to 1")
        rep.add(INFO, skin, facts)
    rep.add(OK, "%d skin(s) read" % len(skins))


def check_stuck(rep):
    from gus_rigtool.core import sticky
    rep.start("Stick to skin")
    stuck = cmds.ls("*." + sticky.META, objectsOnly=True, long=True, recursive=True) or []
    if not stuck:
        rep.add(INFO, "no stuck controls")
        return
    for c in stuck:
        data = sticky.read(c) or {}
        mesh = data.get("mesh")
        if mesh and cmds.objExists(mesh):
            rep.add(INFO, _short(c), sticky.diagnose(c, mesh))
        else:
            rep.add(WARN, "%s: stuck to a mesh that's gone (%s)" % (_short(c), mesh), "Unstick, then Stick again")
    rep.add(OK, "%d stuck control(s) read" % len(stuck))


def check_fixes(rep):
    from gus_rigtool.core import shape_fixes
    rep.start("Fixes (corrective shapes)")
    meshes = []
    for bs in cmds.ls(type="blendShape") or []:
        if cmds.attributeQuery("gusFixes", node=bs, exists=True):
            for g in cmds.blendShape(bs, query=True, geometry=True) or []:
                p = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
                if p not in meshes:
                    meshes.append(p)
    if not meshes:
        rep.add(INFO, "no fixes")
        return
    for mesh in meshes:
        for name, joint, cone, w in shape_fixes.listing(mesh):
            if not cmds.objExists(joint):
                rep.add(FAIL, "%s: its joint %s is gone" % (name, joint), "delete the fix and sculpt it again")
            rep.add(INFO, name, "on %s, joint %s, %.0f deg cone, weight now %.2f" % (_short(mesh), _short(joint),
                                                                                   cone or 0, w))
    rep.add(OK, "fixes read on %d mesh(es)" % len(meshes))


def check_face(rep):
    rep.start("Face kit")
    grp = cmds.ls("face_kit_grp", long=True) or []
    if not grp:
        rep.add(INFO, "no face kit in this scene")
        return
    blink = [p.split(".")[0] for p in (cmds.ls("*.Blink", long=True, recursive=True) or [])]
    for c in blink:
        driven = cmds.listConnections(c + ".Blink", source=False, destination=True) or []
        if not driven:
            rep.add(WARN, "%s: Blink drives nothing" % _short(c), "make the eyelids (Face tab > Eyelids) again")
        else:
            rep.add(INFO, "%s: Blink" % _short(c), "drives %d node(s)" % len(driven))
    if not cmds.listRelatives(grp[0], type="parentConstraint"):
        rep.add(NOTE, "face_kit_grp doesn't follow the head", "make the eyes with the head picked, or constrain it")
    rep.add(OK, "face kit read")


def check_correctives(rep):
    from gus_rigtool.core import joint_labels
    rep.start("Corrective joints")
    cors = cmds.ls("*_cor*", type="joint", long=True, recursive=True) or []
    if not cors:
        rep.add(INFO, "no corrective joints")
        return
    skinned = set(joint_labels.skin_joints())
    loose = [c for c in cors if c not in skinned]
    if loose:
        rep.add(NOTE, "corrective joints not in any skin (%d)" % len(loose),
                "%s - add them to the skin and paint some weight round the bend" % _names(loose))
    rep.add(OK, "%d corrective joint(s)" % len(cors))


def check_connections(rep):
    rep.start("Connections")
    try:
        from gus_rigtool.builder import chain
        old = chain.old_jiggles()
    except Exception:
        old = []
    if old:
        rep.add(WARN, "jiggle expressions that break undo (%d)" % len(old),
                "%s - they write with setAttr on every evaluation, so Ctrl+Z can't get past them (and painting / "
                "ngSkinTools can hang). Repair rewrites them (5.0.10)" % _names(old))
    try:
        outdated, every = chain.outdated_jiggles(), chain.jiggles()
    except Exception:
        outdated, every = [], []
    if outdated:
        rep.add(WARN, "older jiggle expressions (%d)" % len(outdated),
                "%s - they don't react to moving sideways / forward (the world control, the COG) and have no limit "
                "towards the body. Repair remakes them with the same settings (5.3.2)" % _names(outdated))
    try:
        always, stopped = chain.always_evaluating(), chain.paused()
    except Exception:
        always, stopped = [], []
    if always:
        rep.add(WARN, "jiggle / wave expressions that always evaluate (%d)" % len(always),
                "%s - they rewrite their groups on every evaluation, so a skin on those joints never settles "
                "(ngSkinTools can hang). Repair turns it off (5.3.3)" % _names(always))
    if stopped:
        rep.add(NOTE, "jiggle / wave paused (%d)" % len(stopped),
                "%s - Skin page > Jiggle and wave > Back on, before animating or delivering" % _names(stopped))
    if every:
        try:
            speed = cmds.playbackOptions(query=True, playbackSpeed=True)
        except (RuntimeError, TypeError, AttributeError):
            speed = 0
        if speed:
            rep.add(WARN, "jiggle: playback isn't 'every frame'",
                    "the jiggle steps only from one frame to the next: when playback skips frames it rests "
                    "(Preferences > Time Slider > Playback speed: Play every frame)")
        try:
            cached = cmds.evaluator(name="cache", query=True, enable=True)
        except (RuntimeError, TypeError, AttributeError):
            cached = False
        if cached:
            rep.add(WARN, "jiggle: Cached Playback is on",
                    "the cache works frames out in the background, not one after another - the jiggle rests. Turn "
                    "Cached Playback off (its icon at the right of the time slider) to see it")
    try:
        from gus_rigtool.core import networks
        from gus_rigtool.tools import checker as _chk
        ctrls = [n for n in _chk.transforms(None) if _chk.is_control(n)]
        moved = [r for r in networks.at_rest(ctrls) if r[2] is not None]
    except Exception:
        moved = []
    if moved:
        rep.add(NOTE, "moved with every control at rest (%d)" % len(moved),
                "; ".join("%s = %s from %s" % (_short(p), networks._fmt(v), who) for p, v, _r, who in moved[:6]) +
                " - an offset left in a network (Nodes > At rest?)")
    try:
        from gus_rigtool.core import networks
        found = networks.loops()
    except Exception:
        found = []
    if found:
        rep.add(NOTE, "possible loops: nodes feeding each other in a circle (%d)" % len(found),
                "; ".join(" -> ".join(_short(n) for n in grp[:5]) for grp in found[:3]) +
                " - cut one connection in each (Nodes > Find loops)")
    empty = []
    idle = []
    for con in cmds.ls(type="constraint", long=True) or []:
        kind = cmds.nodeType(con)
        fn = getattr(cmds, kind, None)
        if fn is None or kind in ("pointOnPolyConstraint",):
            continue
        try:
            targets = fn(con, query=True, targetList=True) or []
        except (RuntimeError, TypeError, ValueError):
            continue
        if not targets:
            empty.append(con)
    try:
        from gus_rigtool.core import repair as _repair
        idle = _repair.idle_constraints()
    except Exception:
        idle = []
    if empty:
        rep.add(FAIL, "constraints with no target (%d)" % len(empty), "%s - delete them" % _names(empty))
    if idle:
        rep.add(NOTE, "constraints that drive nothing (%d)" % len(idle), "%s - Repair deletes them" % _names(idle))
    sdk = []
    for crv in (cmds.ls(type=("animCurveUL", "animCurveUA", "animCurveUU", "animCurveUT")) or []):
        if not cmds.listConnections(crv + ".input", source=True, destination=False):
            sdk.append(crv)
    if sdk:
        rep.add(WARN, "set driven keys with no driver (%d)" % len(sdk), "%s - their driver was deleted" % _names(sdk))
    dead = []
    for kind in ("multiplyDivide", "remapValue", "plusMinusAverage", "condition", "blendColors", "reverse",
                 "decomposeMatrix", "multMatrix", "blendMatrix", "pickMatrix"):
        for n in cmds.ls(type=kind) or []:
            if not cmds.listConnections(n, source=False, destination=True):
                dead.append(n)
    if dead:
        rep.add(INFO, "utility nodes with no output (%d)" % len(dead), _names(dead))
    pb = cmds.ls(type="pairBlend") or []
    if pb:                                             # 5.6.28: only real keys count (a space blend is normal)
        try:
            from gus_rigtool.core import repair
            keyed = [p for p, _c, _k in repair.stray_keys()]
        except Exception:
            keyed = list(pb)
        if keyed:
            rep.add(INFO, "keys + constraints on the same channels (pairBlend) (%d)" % len(keyed), _names(keyed))
        blends = [p for p in pb if p not in keyed]
        if blends:
            rep.add(INFO, "constraints blended by a pairBlend (%d) - normal (a space switch)" % len(blends),
                    _names(blends))
    rep.add(OK, "connections read")


def picker_saved(ns, A=None):
    """5.6.27: (picker, where) - the picker saved IN the rig (gusPicker, what animators get), else your own on
    this computer, else the old profile copy; (None, '') when there is none."""
    try:
        from gus_animtool import pickmodel as PM
        rig = PM.rig_picker(ns)
        if rig:
            return rig, "in the rig - animators get it"
        own = PM.own_picker(ns)
        if own:
            return own, "on this computer only - Picker > Save in the rig to give it to animators"
    except Exception:
        pass
    try:
        pk = (A.profile(ns) or {}).get("picker") if A else None
    except Exception:
        pk = None
    return (pk, "old profile copy") if pk else (None, "")


def check_picker(rep):
    rep.start("Picker (Gus Animtool)")
    try:
        from gus_rigtool.maya_check import _animtool
        _animtool()
        from gus_animtool import anim as A
    except Exception as e:
        rep.add(INFO, "Gus Animtool not found", str(e))
        return
    chars = A.characters()
    if not chars:
        rep.add(INFO, "no characters found (no controls)")
        return
    for ns in chars:
        pk, where = picker_saved(ns, A)
        name = ns or "(no namespace)"
        if pk:
            pages = pk.get("pages") or []
            rep.add(INFO, "%s: saved picker (%s)" % (name, where), ", ".join(
                "%s (%d)" % (p.get("name"), len(p.get("items") or [])) for p in pages))
        else:
            rep.add(INFO, "%s: no saved picker" % name, "the picker makes one automatically when opened")
        try:                                                 # 5.6.23: what it lacks / what looks odd
            from gus_animtool import pickmodel as PM
            got = PM.load(ns, make=False)
            if got:
                r = PM.report(got, ns)
                for key, label in (("missing", "controls with no button (Missing in the picker adds them)"),
                                   ("unsure", "curves not found as controls, no button (Missing > Also curves...)"),
                                   ("excluded", "taken out on purpose"),
                                   ("pinned", "pinned buttons (stay still when you zoom: Unpin all)"),
                                   ("duplicates", "buttons twice on a page (Clean up)"),
                                   ("gone", "buttons for controls that are gone (Clean up)")):
                    if r.get(key):
                        rep.add(INFO, "%s: %d %s" % (name, len(r[key]), label), _names(r[key]))
        except Exception as e:
            rep.add(INFO, "%s: picker report skipped" % name, str(e))
    rep.add(OK, "%d character(s)" % len(chars))


def check_world_turn(rep):
    """5.1.1: turn the world control 90 degrees: what doesn't come along exactly (a double transform, a node left
    behind), then put it back."""
    from gus_rigtool.core import world_turn
    rep.start("World turn (double transforms)")
    r = world_turn.run()
    if not r["world"]:
        rep.add(INFO, "no controls to turn")
        return
    if not r["axis"]:
        rep.add(INFO, "%s can't be turned (its rotation is locked or driven)" % _short(r["world"]))
        return
    top = lambda n: (cmds.ls(n, long=True) or [n])[0].split("|")[1] if "|" in (cmds.ls(n, long=True) or [n])[0] \
        else n
    try:
        rig_top = top(r["world"])
        outside = [n for n, _t, _m, what in r["off"] if "stays behind" in what and top(n) != rig_top]
    except (RuntimeError, ValueError, IndexError):
        outside = []
    if outside:                                         # 5.3.3: not part of the rig at all - easy to miss
        rep.add(NOTE, "outside the rig (%d)" % len(outside),
                "%s - they aren't under %s's hierarchy (an old skeleton, loose joints?): if nothing uses them "
                "delete them, else put them under the rig. To select them: cmds.select(%r)"
                % (_names(outside), rig_top, [_short(x) for x in outside[:MAX_NAMES]]))
    if r["off"]:
        rep.add(WARN, "don't turn with %s (%d)" % (_short(r["world"]), len(r["off"])),
                "; ".join("%s %s" % (_short(n), what) for n, _t, _m, what in r["off"][:MAX_NAMES]) +
                " - something gives them the world's turn twice, or they don't hang under it")
    if r["spring"]:
        rep.add(NOTE, "spring IK handles (%d)" % len(r["spring"]),
                "%s - the spring solver can double the turn when the whole rig turns; Rotate-Plane doesn't"
                % _names(r["spring"]))
    rep.add(OK, "turned %s %.0f degrees on %s and back: %s" % (
        _short(r["world"]), r["angle"], r["axis"], "everything came along" if not r["off"] else
        "%d didn't" % len(r["off"])))


def check_scale(rep):
    """5.6.0: scale the rig x2 (its global scale), list what doesn't grow with it, put it back."""
    from gus_rigtool.core import scale_check as SC
    rep.start("Scale (the rig x2)")
    r = SC.run()
    if not r["control"]:
        rep.add(INFO, "no controls")
        return
    if not r["plug"]:
        rep.add(INFO, "%s can't be scaled (no globalScale, scale locked / driven)" % _short(r["control"]))
        return
    for kind, label, advice in (
            ("stays", "don't scale (stay where they are)", "they aren't under the scaled controls, or a group "
             "above them doesn't pass the scale on (follicles / ribbons): Repair"),
            ("size", "go to the right place but keep their size", "the skin around them doesn't grow - the mesh "
             "loses its form there (joints held by a parent constraint, controls on follicles): Repair"),
            ("shape", "end up somewhere else", "they stretch instead of growing (a stretch that measures its length "
             "without the global scale: Repair), or something drives them in world units")):
        got = [n for n, k, _t in r["off"] if k == kind]
        if got:                                         # 5.6.1: by part of the rig, not one name after another
            rep.add(WARN, "%s (%d)" % (label, len(got)), "%s - %s" % (_by_part(got), advice))
    twice = [m for m, k, _t in r["meshes"] if k == "twice"]
    if twice:
        rep.add(WARN, "skinned meshes that scale twice (%d)" % len(twice), "%s - Repair stops them inheriting the "
                "groups above" % _names(twice))
    other = [(m, t) for m, k, t in r["meshes"] if k == "mesh"]
    if other:
        rep.add(WARN, "skinned meshes that don't grow evenly (%d)" % len(other),
                "; ".join("%s %s" % (_short(m), t) for m, t in other[:MAX_NAMES]))
    bad = len(r["off"]) + len(r["meshes"])
    rep.add(OK, "scaled %s x%g and back: %s" % (r["plug"].split("|")[-1], SC.FACTOR,
                                               "everything grew with it" if not bad else "%d didn't" % bad))


def check_limits(rep):
    """5.3.5: controls with transform limits, and limits on one side only (the twin has none)."""
    from gus_rigtool.core import limits
    from gus_rigtool.core import mirror_setup as MS
    from gus_rigtool.tools import checker
    ctrls = [c for c in checker.transforms(None) if checker.is_control(c)]
    have = [(c, limits.limited(c)) for c in ctrls]
    have = [(c, l) for c, l in have if l]
    if not have:
        return
    rep.start("Limits")
    one_side = []
    for c, lims in have[:40]:
        rep.add(INFO, _short(c), limits.describe(c).split(": ", 1)[1])
        t = MS.twin(c)
        if t and cmds.objExists(t) and set(limits.limited(t)) != set(lims):
            one_side.append(c)
    if one_side:
        rep.add(NOTE, "limits not on both sides (%d)" % len(one_side),
                "%s - their twin has other channels limited: Controls > Attributes > Limits > Mirror" %
                _names(one_side))


def check_views(rep):
    """5.4.2: viewports that hide curves (controls invisible there)."""
    from gus_rigtool.core import repair
    views = repair.curveless_views()
    if views:
        rep.start("Viewports")
        rep.add(WARN, "curves hidden in %s" % ", ".join(views),
                "controls and new curves don't show there (Show > NURBS Curves is off) - Repair turns it back on")


def _by_part(nodes, n=8):
    """'L_Sleeve 14, Mouth 16, Cape 9 ...' - how many in each part of the rig, biggest first."""
    from gus_rigtool.core import network_tools
    count = {}
    for x in nodes:
        p = network_tools._part(x)
        count[p] = count.get(p, 0) + 1
    rows = sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join("%s %d" % kv for kv in rows[:n]) + (" ... (+%d parts)" % (len(rows) - n) if len(rows) > n else "")


HEAVY_PART = 60            # nodes in one part of the rig before it's listed as heavy


def check_networks(rep):
    """5.5.0: the heaviest parts of the rig (where to look when it plays slowly), unit conversions back to back."""
    from gus_rigtool.core import network_tools
    rows = [r for r in network_tools.heaviest(5) if r[1] >= HEAVY_PART]
    pairs = network_tools.double_conversions()
    if not rows and not pairs:
        return
    rep.start("Networks")
    for part, n, kinds in rows:
        rep.add(INFO, "%s: %d node(s)" % (part, n), ", ".join("%s %d" % (k, v) for k, v in
                                                          sorted(kinds.items(), key=lambda x: -x[1])[:4]))
    if pairs:
        rep.add(NOTE, "unit conversions back to back (%d)" % len(pairs),
                "%s - they cancel out; Repair (or Nodes > Clean up) connects the source straight" %
                _names([a for a, _b, _s, _d in pairs]))


def check_ng_data(rep):
    """5.3.3: ngSkinTools data from skins that no longer exist."""
    from gus_rigtool.core import repair
    try:
        orphans = repair.ng_orphans()
    except Exception:
        orphans = []
    if orphans:
        rep.start("ngSkinTools data")
        rep.add(NOTE, "ngSkinTools data from skins that no longer exist (%d)" % len(orphans),
                "%s - leftovers ngSkinTools still reads; Repair deletes them" % _names(orphans))


def _auto_key(rep):
    """5.6.7: Auto Key on - it left keys on the rig while testing."""
    try:
        if cmds.autoKeyframe(query=True, state=True):
            rep.add(NOTE, "Auto Key is on", "every control you move while testing gets a key - turn it off while "
                    "rigging (the key icon at the bottom right)")
    except (RuntimeError, AttributeError):
        pass


def _default_material(rep):
    """5.6.7: Maya's default material changing (keys / connections, transmission): the meshes on it fade in the
    viewport (the Hare's bandages)."""
    try:
        mats = cmds.listConnections("initialShadingGroup.surfaceShader", source=True, destination=False) or []
    except (RuntimeError, ValueError):
        return
    for m in mats:
        keyed = cmds.listConnections(m, source=True, destination=False, type="animCurve") or []
        driven = [x for x in cmds.listConnections(m, source=True, destination=False) or [] if x not in keyed]
        trans = 0.0
        if cmds.attributeQuery("transmission", node=m, exists=True):
            trans = cmds.getAttr(m + ".transmission")
        if keyed or driven or trans > 0:
            meshes = [x for x in cmds.sets("initialShadingGroup", query=True) or []]
            rep.add(WARN, "Maya's default material (%s) changes" % m,
                    "%s%s%s - the meshes on it (%s) fade in the viewport. Give them a material of their own "
                    "(Checker > Meshes on Maya's default material > Fix)" % (
                        "keyed; " if keyed else "", ("driven by %s; " % _names(driven)) if driven else "",
                        ("transmission %.2f" % trans) if trans > 0 else "", _names(meshes)))


def check_spaces(rep):
    """5.6.7: every space switch - each space at rest (no jump), then at the rig's scale x2."""
    from gus_rigtool.core import space_check
    r = space_check.run()
    if not r["switches"]:
        return
    rep.start("Spaces")
    if r["jumps"]:
        rep.add(WARN, "spaces that jump at rest (%d)" % len(r["jumps"]),
                "; ".join("%s %s (%.2f)" % (_short(c), lb, d) for c, lb, d in r["jumps"][:MAX_NAMES]) +
                " - the control moves when this space is chosen (the rig at rest): its target moved after the "
                "switch was made, or the switch was made with the rig posed")
    if r["scale"]:
        rep.add(WARN, "spaces that drift at scale x2 (%d)" % len(r["scale"]),
                "; ".join("%s %s (%.2f)" % (_short(c), lb, d) for c, lb, d in r["scale"][:MAX_NAMES]) +
                " - this space doesn't scale with the rig (a constraint reading the wrong scale: Repair)")
    rep.add(OK, "%d space switch(es): each space chosen%s" % (
        r["switches"], " and scaled x2" if r["plug"] else ""),
        "no jumps, nothing drifts" if not (r["jumps"] or r["scale"]) else "")


def check_turns(rep):
    """5.6.7: the head turned 30 degrees: what turns about twice as much (a double rotation - the Hare's eyeballs
    turned 72 when the head turned 30)."""
    from gus_rigtool.core import space_check
    r = space_check.turn_test()
    if not r["control"] or not r["axis"]:
        return
    rep.start("Head turn (double rotations)")
    if r["twice"]:
        rep.add(WARN, "turn about twice as much as %s (%d)" % (_short(r["control"]), len(r["twice"])),
                "; ".join("%s %.0f" % (_short(n), d) for n, d in r["twice"][:MAX_NAMES]) +
                " degrees for 30 - something gives them the head's turn twice (a control's rotation connected "
                "straight into a joint under the head: use an orient constraint)")
    else:
        rep.add(OK, "turned %s 30 degrees on %s and back: nothing turned twice" % (_short(r["control"]), r["axis"]))


def check_squash(rep):
    """5.6.11: the head squash comes after the skin on every mesh (else the face squashes, then gets skinned)."""
    from gus_rigtool.core import head_squash as HS
    if not HS.find():
        return
    rep.start("Head squash")
    data = HS.read()
    meshes = [m for m in data.get("meshes", []) if cmds.objExists(m)]
    unclear = [m for m in meshes if len(cmds.ls(m) or []) > 1]          # 5.6.17: a squash made before 5.6.17 kept
    wrong = [m for m in meshes if m not in unclear and not HS.after_skin(m)]   # short names (two Hare_Body...)
    if unclear:
        rep.add(INFO, "%d mesh name(s) are on more than one object - not checked" % len(unclear),
                "%s - Remove the head squash and Make it again (5.6.17 keeps full paths)" % _names(unclear))
    copies = sum(len(HS.mesh_copies(m)) for m in meshes if m not in unclear)
    if copies:
        rep.add(WARN, "%d extra copy(ies) of the head meshes pass the mesh along" % copies,
                "Face kit > Head squash > Clean mesh copies (pick the meshes) - they slow the rig")
    if wrong:
        rep.add(WARN, "the squash comes before the skin on %d mesh(es)" % len(wrong), "%s - right-click the mesh > "
                "Inputs > All Inputs, drag Head_squash below the skin (or Remove and Make again)" % _names(wrong))
    else:
        rep.add(OK, "the squash comes after the skin on %d mesh(es); %d face control curve(s) ride it" % (
            len(data.get("meshes", [])), data.get("curves", 0)))


def check_face_layers(rep):
    """5.6.20: the layers group controls and expressions put above controls - one that lost its sum nodes (5.6.19
    could leave that) refuses new poses; one nothing feeds any more is clutter."""
    from gus_rigtool.core import group_ctrls as GC
    lays = cmds.ls("*." + GC.LAYER, objectsOnly=True, long=True) or []
    if not lays:
        return
    rep.start("Face layers (group controls, expressions)")
    broken = [x for x in lays if not all(GC._sum_of(x, a) for a in ("translate", "rotate"))]
    empty = [x for x in lays if x not in broken and not any(
        cmds.listConnections(GC._sum_of(x, a) + ".input3D", source=True, destination=False)
        for a in ("translate", "rotate"))]
    if broken:
        rep.add(WARN, "%d layer(s) lost their sum nodes" % len(broken),
                "%s - Face kit > Expressions > Refresh repairs them" % _names(broken))
    if empty:
        rep.add(INFO, "%d layer(s) nothing feeds any more" % len(empty),
                "%s - Refresh takes them away" % _names(empty))
    if not broken:
        rep.add(OK, "%d layer(s), every one whole" % len(lays))


def check_cloth(rep):
    """5.3.0: a range of motion left keyed (Skin page > Cloth)."""
    from gus_rigtool.core import cloth
    if not cmds.objExists(cloth.ROM_NODE):
        return
    rep.start("Cloth")
    rep.add(WARN, "a range of motion is still keyed",
            "Skin page > Cloth > Remove it, before animating or delivering (it puts every channel back)")


def check_speed(rep):
    """5.6.27: how fast the rig moves (the COG / World dragged), what keeps the skins off the graphics card, and
    deformers that print a warning on every update. Fixes: Repair (safe mode)."""
    from gus_rigtool.core import rigspeed as speed
    rep.start("Speed")
    if cmds.about(batch=True):                  # 5.6.36: mayapy - nothing is drawn, the times would read 0 ms
        rep.add(INFO, "speed skipped", "Maya runs without a window here (the real-Maya tests): nothing is drawn")
        return
    gpu = speed.gpu_on()
    try:
        t = speed.time_drag()
        if t:
            t0 = speed.time_drag(list(t), skins_off=True)
            parts = []
            for c, ms in t.items():
                bit = "%s %.0f ms (%.0f fps)" % (_short(c), ms, 1000.0 / max(ms, 1e-3))
                if t0.get(c) is not None:
                    bit += ", skins %.0f ms of it" % max(ms - t0[c], 0.0)
                parts.append(bit)
            slow = max(t.values()) > 42.0                      # under ~24 fps while dragging
            rep.add(NOTE if slow else INFO, "dragging moves at %s" % "; ".join(parts),
                    "GPU override %s" % {True: "on", False: "off (Preferences > Animation)", None: "?"}[gpu])
        for c, why in sorted(speed.SKIPPED.items()):                # 5.6.29: said, not left out
            rep.add(INFO, "couldn't time %s" % _short(c), why)
        if t:
            _speed_more(rep, speed, t)
    except Exception as e:
        rep.add(INFO, "timing skipped", str(e))
    tags = speed.tag_problems()
    if tags:                                           # 5.6.28: not a repair - make the deformer again
        rep.add(WARN, "deformers asking for a component tag the mesh doesn't have (%d)" % len(tags),
                "%s - Maya prints a warning on every update (slow). Fix: %s" %
                (", ".join("%s[%d] wants %s" % (d, i, "/".join(m)) for d, i, _e, m in tags[:4]),
                 speed.tag_advice(tags[0][0])))
    br = speed.chain_breaks()
    if br:
        rep.add(WARN, "hidden meshes in the middle of deformer chains (%d)" % len(br),
                "%s - the skin under them can't run on the graphics card; Repair connects the deformers straight "
                "(safe mode checks nothing moves)" % _names([m for _u, _d, m in br]))
    plug, dms = speed.unscaled_delta_mush()
    if dms:
        rep.add(WARN, "Delta Mush not tied to the rig's scale (%d)" % len(dms),
                "%s - the mesh loses its form when the rig is scaled; Repair ties displacement to %s" %
                (_names(dms), plug.split("|")[-1]))
    why = speed.gpu_reasons()
    if why:
        big = {m: w for m, w in why.items() if not any("vertices (Maya keeps" in x for x in w)}
        for m, w in sorted(big.items())[:MAX_NAMES]:
            rep.add(INFO, "%s stays on the CPU" % _short(m), "; ".join(w))
        small = len(why) - len(big)
        if small:
            rep.add(INFO, "%d small mesh(es) stay on the CPU by design" % small,
                    "under %d vertices Maya doesn't send a mesh to the graphics card" % speed.GPU_MIN_VERTICES)
    rep.add(OK, "speed read")


def _speed_more(rep, speed, t):
    """5.6.29: one control (the COG when there is one) dragged with the clothes hidden, GPU override off, and each
    heavy skin off - what each costs on this computer."""
    c = next((x for x in t if "cog" in _short(x).lower()), sorted(t)[0])
    try:
        x = speed.extra_timings(c)
    except Exception as e:
        rep.add(INFO, "more timing skipped", str(e))
        return
    for why in x["skipped"]:
        rep.add(INFO, "couldn't time %s" % _short(c), why)
    base = x["base"]
    if base is None:
        return
    if x["clothes"] is not None:
        rep.add(INFO, "with the clothes hidden (Visibility_ctrl.Clothes): %s %.0f ms (%.0f fps), %.0f ms saved" % (
            _short(c), x["clothes"], 1000.0 / max(x["clothes"], 1e-3), max(base - x["clothes"], 0.0)),
            "animators hide them while blocking, show them to check the silhouette")
    else:
        from gus_rigtool.core import clothes_switch as CS
        if CS.suggest():
            rep.add(INFO, "no Clothes switch yet", "Build > Visibility switches > Clothes: full / hidden - hides %s "
                    "and switches their skins off while blocking" % ", ".join(_short(m) for m in CS.suggest()[:4]))
    if x.get("pieces"):                                    # 5.6.30: each piece hidden on its own
        rep.add(INFO, "each clothes piece hidden on its own (%s)" % _short(c), "; ".join(
            "%s saves %.0f ms" % (part, ms) for part, ms in sorted(x["pieces"], key=lambda r: -r[1])))
    if x["gpu_off"] is not None:
        faster = x["gpu_off"] < base * 0.95
        rep.add(NOTE if faster else INFO, "GPU override %s for this rig: on %.0f ms, off %.0f ms" % (
            "is SLOWER than off" if faster else "helps or is the same", base, x["gpu_off"]),
            "Preferences > Animation > GPU Override: off on this computer" if faster else "")
    if x["skins"]:
        rep.add(INFO, "what each heavy skin costs (%s, each switched off on its own)" % _short(c), "; ".join(
            "%s %.1f ms (%.1f above the ~%.1f ms every skin costs) - %d vertices, %d joints" % (
                mesh, gain, real, x["overhead"], v, n) for _s, mesh, v, n, gain, real in x["skins"]))


def check_ready(rep):
    """5.6.27: Ready for animators - what would bite them, in one list."""
    rep.start("Ready for animators")
    bad = 0
    try:
        from gus_rigtool.core import repair
        keys = repair.stray_keys()
    except Exception as e:                             # 5.6.29: said, not taken as "no keys"
        keys = []
        rep.add(INFO, "couldn't look for keys on constrained channels", str(e))
    if keys:
        bad += 1
        rep.add(WARN, "keys left in the rig on constrained channels (%d)" % len(keys),
                "%s - the controls blend between the key and the constraint; Repair deletes the keys" %
                _names(sorted(set(c for _p, cs, _k in keys for c in cs)) or [p for p, _c, _k in keys]))
    try:
        from gus_rigtool.maya_check import _animtool
        _animtool()
        from gus_animtool import anim as A
        for ns in A.characters():
            pk, where = picker_saved(ns, A)
            name = ns or "(no namespace)"
            if not pk or not where.startswith("in the rig"):
                bad += 1
                rep.add(WARN, "%s: the picker isn't saved in the rig" % name,
                        "animators get an automatic one - Picker > Save in the rig")
            ctrls = A.character_controls(ns)
            learned = [c for c in ctrls if A.stored_rest(c) is not None]
            if ctrls and len(learned) < len(ctrls):
                bad += 1
                rep.add(NOTE, "%s: mirror table learned on %d of %d controls" % (name, len(learned), len(ctrls)),
                        "Publish learns it (or Animtool > Mirror > Learn mirror): mirror then ignores how the arms "
                        "are posed")
    except Exception as e:
        rep.add(INFO, "Gus Animtool not found", str(e))
    try:
        if cmds.file(query=True, modified=True):
            bad += 1
            rep.add(NOTE, "the scene has unsaved changes", "save before you Publish / Deliver")
        if cmds.autoKeyframe(query=True, state=True):
            bad += 1
            rep.add(NOTE, "Auto Key is on", "turn it off before you Publish")
    except Exception:
        pass
    rep.add(OK if not bad else INFO, "ready for animators" if not bad else
            "%d thing(s) above, plus the Controls warnings in Checker (not at zero, constraints, hidden)" % bad)


PARTS = [("scene", check_scene), ("guides", check_guides), ("checker", check_checker), ("ribbons", check_ribbons),
         ("follows", check_follows), ("labels", check_labels), ("skin", check_skin), ("stuck", check_stuck),
         ("fixes", check_fixes), ("face", check_face), ("correctives", check_correctives),
         ("connections", check_connections), ("world", check_world_turn), ("scale", check_scale),
         ("spaces", check_spaces), ("turns", check_turns), ("squash", check_squash), ("face_layers", check_face_layers),
         ("cloth", check_cloth),
         ("ngskintools", check_ng_data), ("limits", check_limits),
         ("views", check_views), ("networks", check_networks),
         ("picker", check_picker), ("speed", check_speed), ("ready", check_ready)]


def report():
    """Run every part; returns the Report."""
    rep = Report("Check this scene")
    sel = cmds.ls(selection=True, long=True) or []
    try:
        for name, fn in PARTS:
            rep.start(name.title())                     # a crash before the part names its section lands here
            rep.guard(name, fn, rep)
    finally:
        try:
            cmds.select(sel, replace=True) if sel else cmds.select(clear=True)
        except (RuntimeError, ValueError):
            pass
    try:                                                    # 5.3.4: warnings you marked as intended pass
        from gus_rigtool.core import accept
        if accept.apply(rep):
            rep.start("Accepted")
            rep.add(INFO, "%d warning(s) accepted as intended" % len(accept.load()),
                    "Check this scene window > Accept warnings... to review or take them back")
    except Exception:
        pass
    return rep


# 5.6.30: where each problem is fixed - (words in the problem, button label, tool key, section)
GO_THERE = [
    (r"don't mirror their left twin|not exactly symmetric", "Ribbon > Not symmetric / Make symmetric", "ribbon",
     "Build and mirror"),
    (r"controls not at zero|driven by a constraint", "Behaviour > Rest here (keep the pose, zero)", "behaviour",
     "Rest here"),
    (r"hidden by a group above", "Behaviour > Not a control", "behaviour", "Not a control"),
    (r"mirror table learned", "Build > Publish", "build", "Publish (clean rig for animators)"),
    (r"keys left in the rig|hidden meshes in the middle|delta mush not tied|carry no weight", "Checker > Repair",
     "checker", "Repair"),
    (r"jiggle", "Skin > Jiggle and wave", "skin", "Jiggle and wave"),
    (r"dragging moves at|no clothes switch", "Build > Visibility switches (Clothes)", "build", "Visibility switches"),
]


def go_targets(rep):
    """5.6.30: [(problem, label, tool, section)] - each warning / note that has a place to fix it, once per place."""
    import re as _re
    out, seen = [], set()
    for _sec, status, name, detail in rep.rows:
        if status not in (WARN, NOTE) and "no clothes switch" not in name:
            continue
        for rx, label, tool, section in GO_THERE:
            if _re.search(rx, name.lower()) and (tool, section, name) not in seen:
                seen.add((tool, section, name))
                out.append((name, label, tool, section))
                break
    return out


def go_window(rep):
    """A small window: each problem and a Go button to the tab and section that fixes it."""
    from gus_rigtool.core import ui
    win = "gusRigGoThereWin"
    targets = go_targets(rep)
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title="Gus_Rigtool - go there", widthHeight=(560, 60 + 26 * max(len(targets), 1)))
    cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
    if not targets:
        cmds.text(label="  Nothing in this report has a tab to go to.", align="left")
    for name, label, tool, section in targets:
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 4), (2, "both", 2)])
        cmds.text(label=name[:70], align="left", annotation=name)
        cmds.button(label="Go: " + label, width=250, command=lambda *_, t=tool, sc=section: ui.go_to_tool(t, sc))
        cmds.setParent("..")
    cmds.showWindow(win)
    return win


def accept_window(rep=None):
    """Tick the warnings / notes that are intended; Accept: they pass from now on (until something new shows up on
    the same line). Forget: every accepted one warns again."""
    from gus_rigtool.core import accept
    rep = rep or report()
    rows = accept.problems(rep)
    win = "gusRigAcceptWin"
    if cmds.window(win, exists=True):
        cmds.deleteUI(win)
    cmds.window(win, title="Gus_Rigtool - accept warnings", widthHeight=(620, 460))
    form = cmds.formLayout()
    info = cmds.text(label="Tick what is intended (a choice, not a mistake). It passes from now on - until something "
                     "new shows up on the same line.", align="left", wordWrap=True, height=34)
    scroll = cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
    boxes = []
    for sec, name, detail in rows:
        b = cmds.checkBox(label="%s: %s" % (sec, name), value=False, annotation=detail[:400])
        boxes.append((b, (sec, name, detail)))
    if not rows:
        cmds.text(label="Nothing to accept: no warnings or notes.", align="left")
    cmds.setParent(form)

    def do_accept(*_):
        picked = [r for b, r in boxes if cmds.checkBox(b, query=True, value=True)]
        accept.accept(picked)
        cmds.deleteUI(win)
        run()

    def do_forget(*_):
        accept.forget()
        cmds.deleteUI(win)
        run()
    ok = cmds.button(label="Accept ticked", height=28, command=do_accept)
    no = cmds.button(label="Forget all accepted (%d)" % len(accept.load()), height=28, command=do_forget)
    cmds.formLayout(form, edit=True,
                    attachForm=[(info, "top", 6), (info, "left", 6), (info, "right", 6), (scroll, "left", 6),
                                (scroll, "right", 6), (ok, "left", 6), (ok, "bottom", 6), (no, "right", 6),
                                (no, "bottom", 6)],
                    attachControl=[(scroll, "top", 4, info), (scroll, "bottom", 6, ok)],
                    attachPosition=[(ok, "right", 3, 50), (no, "left", 3, 50)])
    cmds.showWindow(win)


def run_later():
    """5.6.34: what the Check this scene buttons call - the check starts once the click is over. Run inside the
    click (it moves the rig, refreshes the view for the speed timing, opens windows), it crashed Maya on the Hare
    every time; the same run from the Script Editor never did."""
    def go():
        try:
            run()
        except Exception as e:
            from gus_rigtool.core import ui
            ui.report_error(e, "scene_check")
    cmds.evalDeferred(go, lowestPriority=True)


def run(show=True):
    """Check the open scene (reads only); shows the report and saves it. Returns the text."""
    rep = report()
    text = rep.text()
    path = os.path.join(cmds.internalVar(userTmpDir=True), "gus_scene_check.txt")
    try:
        with open(path, "w") as f:
            f.write(text)
    except (IOError, OSError):
        path = None
    print(text)
    if show:
        try:
            from gus_rigtool.core import ui
            ui.report_window("Gus_Rigtool - Check this scene", text + ("\nSaved: %s" % path if path else ""),
                             extra=[("Go there...", lambda *_: go_window(rep)),       # 5.6.30
                                    ("Accept warnings...", lambda *_: accept_window(rep))])
        except Exception:
            pass
    return text
