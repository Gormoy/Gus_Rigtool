"""
Repair (4.3.0): the problems Check this scene finds that can be fixed safely, as a list to tick and apply in one undo.

    from gus_rigtool.core import repair
    items = repair.find()                       # [Item(id, label, detail, count)]
    repair.apply([i.id for i in items])         # -> [(label, result or error)]

Every fix keeps the scene where it is (nothing moves, weights stay or are only normalised).
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, safe, utils


class Item(object):
    def __init__(self, id_, label, detail, count, fix):
        self.id, self.label, self.detail, self.count, self.fix = id_, label, detail, count, fix

    def __repr__(self):
        return "<repair %s: %s (%d)>" % (self.id, self.label, self.count)


# 5.6.1: fixes that are meant to change the mesh at rest (the others are undone if they do)
MOVES = ("ribbon_along_v", "skin_normalize", "ribbon_symmetric", "skin_limits")
# 5.6.27: fixes meant to change how the rig scales (safe mode doesn't hold them to the x2 look)
SCALE_FIXES = ("deltamush_scale",)


def safe_states(id_):
    """The states safe mode compares for a repair: none for the fixes meant to move the mesh, no x2 look for
    the scale fixes, else rest + x2 + a few frames of real animation."""
    if id_ in MOVES:
        return ()
    if id_ in SCALE_FIXES or id_.startswith("scale_"):
        return ("rest", "anim")
    return safe.STATES


def ng_skins():
    """Skins with ngSkinTools layers (their weights come from the layers: ngSkinTools writes them over any change
    made to the skin)."""
    out = set()
    for n in cmds.ls(type="ngst2SkinLayerData") or []:
        for s in cmds.listConnections(n, type="skinCluster") or []:
            out.add(s)
    for s in cmds.ls(type="skinCluster") or []:
        if any(cmds.nodeType(x).startswith("ngst") for x in set(cmds.listConnections(s) or [])):
            out.add(s)
    return out


def _skin_of_mesh(m):
    for h in cmds.listHistory(m, pruneDagObjects=True) or []:
        if cmds.nodeType(h) == "skinCluster":
            return h
    return None


def rest_points():
    """{mesh shape: [x, y, z, ...]} of every skinned mesh as it deforms now (5.6.1: Repair's safety net)."""
    try:
        import maya.api.OpenMaya as om
    except ImportError:
        return {}
    out = {}
    for skin in cmds.ls(type="skinCluster") or []:
        for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
            try:
                if cmds.nodeType(g) != "mesh":
                    continue
                sel = om.MSelectionList()
                sel.add(g)
                pts = om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kWorld)
                out[g] = [c for p in pts for c in (p.x, p.y, p.z)]
            except Exception:
                continue
    return out


def moved(before, after, tol=1e-3):
    """[(mesh, vertices moved, most)] between two rest_points()."""
    out = []
    for g, a in before.items():
        b = after.get(g)
        if b is None or len(b) != len(a):
            continue
        n, most = 0, 0.0
        for i in range(0, len(a), 3):
            d = ((a[i] - b[i]) ** 2 + (a[i + 1] - b[i + 1]) ** 2 + (a[i + 2] - b[i + 2]) ** 2) ** 0.5
            if d > tol:
                n += 1
                most = max(most, d)
        if n:
            out.append((g, n, most))
    return out


def _names(nodes, n=6):
    nodes = [naming.short_name(x) for x in nodes]
    return ", ".join(nodes[:n]) + (" ..." if len(nodes) > n else "")


# ---------------------------------------------------------------------------
# finders - each returns an Item or None
# ---------------------------------------------------------------------------

def _ribbons_copying():
    from gus_rigtool.core import ribbon
    keys = []
    for key, build in ribbon._find_builds().items():
        st = ribbon._build_settings(build) or {}
        if st.get("pivot_scale"):
            continue
        for off in ribbon._build_offsets(build).values():
            c = ribbon._control_under(off)
            if c and ribbon.bind_of(c)[1] == "copy":
                keys.append(key)
                break
    if not keys:
        return None

    def fix():
        return sum(ribbon.to_constraints(k) for k in keys)
    return Item("ribbon_constraints", "Ribbons whose joints copy their controls -> Switch to constraints",
                _names(keys), len(keys), fix)


def _along_v():
    from gus_rigtool.core import ribbon
    keys = []
    for key in ribbon._find_builds():
        try:
            if cmds.objExists(key) and ribbon.runs_along_v(key):
                keys.append(key)
        except Exception:
            continue
    if not keys:
        return None

    def fix():
        from gus_rigtool.core import face_kit
        builds = ribbon._find_builds()
        done, seen = 0, set()
        for key in keys:
            if not cmds.objExists(key) or key not in builds:
                continue
            first = face_kit.first_side(key)
            if first:                                 # a Face kit part: made again from its edges
                if first not in seen:
                    seen.add(first)
                    face_kit.redo(first)
                    done += 1
                continue
            mirror_of = ribbon._mirror_of(key, builds)
            if mirror_of and mirror_of in keys:       # rebuilt with its first side
                continue
            ribbon.rebuild(ribbon._build_settings(builds[key]) or {}, surface=key, update_mirror=True)
            builds = ribbon._find_builds()
            done += 1
        return done
    return Item("ribbon_along_v", "Ribbons that run along V (joints bunched across the width) -> Rebuild along "
                "the length (weights kept)", _names(keys), len(keys), fix)


def _loops_not_mirrored():
    from gus_rigtool.core import mirror_engine, ribbon
    keys = []
    for key, build in ribbon._find_builds().items():
        try:
            if not ribbon.is_looped(key) or ribbon.is_asymmetric(key):
                continue
        except Exception:
            continue
        offs = ribbon._build_offsets(build)
        pos = {i: cmds.xform(o, query=True, worldSpace=True, translation=True) for i, o in offs.items()}
        if len(pos) < 3:
            continue
        span = max(max(p[0] for p in pos.values()) - min(p[0] for p in pos.values()), 1e-6)
        lefts = [i for i, p in pos.items() if p[0] > span * 0.01]
        rights = [i for i, p in pos.items() if p[0] < -span * 0.01]
        for r in rights:
            q = pos[r]
            if not lefts:
                break
            left = min(lefts, key=lambda i: sum((a - b) ** 2 for a, b in zip(pos[i], (-q[0], q[1], q[2]))))
            want = mirror_engine.mirror_list(cmds.xform(offs[left], query=True, worldSpace=True, matrix=True),
                                             "true", 0)[:12]
            have = cmds.xform(offs[r], query=True, worldSpace=True, matrix=True)[:12]
            if max(abs(a - b) for a, b in zip(want, have)) > 1e-2:
                keys.append(key)
                break
    if not keys:
        return None

    def fix():
        return sum(ribbon.mirror_sides(k) for k in keys)
    return Item("mirror_sides", "Loop ribbons whose right side doesn't mirror the left -> Make the right side mirror "
                "the left", _names(keys), len(keys), fix)


def _labels():
    from gus_rigtool.core import joint_labels
    joints = joint_labels.skin_joints()
    bad = []
    for j in joints:
        try:
            if cmds.getAttr(j + ".type") == 0 or (cmds.getAttr(j + ".type") == 18 and
                                                   not cmds.getAttr(j + ".otherType")):
                bad.append(j)
        except (RuntimeError, ValueError):
            continue
    if not bad:
        return None

    def fix():
        return joint_labels.label(joint_labels.skin_joints())
    return Item("labels", "Skinned joints with no label -> Label joints", _names(bad), len(bad), fix)


def _twins():
    from gus_rigtool.core import joint_labels
    try:
        lonely = [a for a, b, _d in joint_labels.not_mirrored(joint_labels.skin_joints()) if not b]
    except Exception:
        lonely = []
    if not lonely:
        return None

    def fix():
        return len(joint_labels.add_twins(lonely))
    return Item("twins", "Left joints with no right twin -> Add missing twins (weight 0)", _names(lonely),
                len(lonely), fix)


def _empty_constraints():
    empty = []
    for con in cmds.ls(type="constraint", long=True) or []:
        fn = getattr(cmds, cmds.nodeType(con), None)
        if fn is None:
            continue
        try:
            if not (fn(con, query=True, targetList=True) or []):
                empty.append(con)
        except (RuntimeError, TypeError, ValueError):
            continue
    if not empty:
        return None

    def fix():
        gone = [c for c in empty if cmds.objExists(c)]
        if gone:
            cmds.delete(gone)
        return len(gone)
    return Item("empty_constraints", "Constraints with no target -> delete them", _names(empty), len(empty), fix)


def _guides_zeroed():
    from gus_rigtool.builder import build as bld
    from gus_rigtool.builder import guides
    if not bld.is_built():
        return None
    bad = []
    for g in guides.module_groups():
        pos = guides.positions(g)
        zero = [r for r, p in pos.items() if guides._at_origin(p)]
        if pos and len(pos) > 2 and len(zero) * 2 >= len(pos):
            bad.append(guides.read(g)["id"])
    if not bad:
        return None

    def fix():
        moved, _missing = bld.guides_from_rig()
        return moved
    return Item("guides", "Guides sitting at the origin -> Guides from the rig", ", ".join(bad[:6]), len(bad), fix)


def _skin_sums():
    from gus_rigtool import scene_check
    bad = []
    ng = ng_skins()
    for skin in cmds.ls(type="skinCluster") or []:
        if skin in ng:                                     # 5.6.1: ngSkinTools writes these from its layers
            continue
        geo = cmds.skinCluster(skin, query=True, geometry=True) or []
        if not geo or cmds.nodeType(geo[0]) != "mesh":
            continue
        if cmds.getAttr(skin + ".normalizeWeights") == 2:
            continue                    # Post: Maya normalises at deform time, the stored sums don't matter
        try:
            _n, sums, _per = scene_check._skin_weights(skin)
        except Exception:
            continue
        if any(abs(s - 1.0) > 1e-3 for s in sums):
            bad.append(skin)
    if not bad:
        return None

    def fix():
        done = 0
        for skin in bad:
            geo = cmds.skinCluster(skin, query=True, geometry=True) or []
            for g in geo:
                t = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
                cmds.skinPercent(skin, t + ".vtx[*]", normalize=True)
                done += 1
        return done
    return Item("skin_normalize", "Skins with weights that don't add up to 1 -> normalise them", _names(bad),
                len(bad), fix)


DEAD_TYPES = ("multiplyDivide", "remapValue", "plusMinusAverage", "condition", "blendColors", "reverse",
              "decomposeMatrix", "multMatrix", "blendMatrix", "pickMatrix", "multDoubleLinear", "addDoubleLinear")


def _ribbons_not_symmetric():
    from gus_rigtool.core import ribbon
    found = []
    for key in ribbon._find_builds():
        try:
            if not ribbon.is_looped(key) or ribbon.is_asymmetric(key):
                continue
            r = ribbon.symmetry_report(key)
        except Exception:
            continue
        off = r["controls"] + r["follicles"]
        try:
            from gus_rigtool import scene_check
            tol = scene_check.mirror_tol()
        except Exception:
            tol = 0.0
        if off and max(x[2] for x in off) >= tol:          # 5.3.4: within the skin mirror tolerance: fine
            found.append(r)
    if not found:
        return None

    def fix():
        done = 0
        for r in found:
            done += len(ribbon.make_symmetric(report=ribbon.symmetry_report(r["key"])))
        return done
    n = sum(len(r["controls"]) + len(r["follicles"]) for r in found)
    return Item("ribbon_symmetric", "Ribbon pairs not exactly symmetric -> move the other side onto its twin's "
                "mirror", _names([r["key"] for r in found]), n, fix)


def _ribbon_child_binds():
    from gus_rigtool.core import ribbon
    keys = []
    for key, build in ribbon._find_builds().items():
        try:
            ctrls = [c for c in (ribbon._control_under(o) for o in ribbon._build_offsets(build).values()) if c]
            if ribbon._loose_binds(ctrls):
                keys.append(key)
        except Exception:
            continue
    if not keys:
        return None

    def fix():
        done = 0
        for k in keys:
            done += ribbon.to_constraints(k)
        return done
    return Item("ribbon_child_binds", "Ribbon joints hanging under their (mirrored) controls -> constraints",
                _names(keys), len(keys), fix)


def _old_jiggles():
    from gus_rigtool.builder import chain
    old = chain.old_jiggles()
    if not old:
        return None

    def fix():
        done = 0
        for e in old:
            if cmds.objExists(e):
                chain.remake_jiggle(e)
                done += 1
        return done
    return Item("old_jiggle", "Jiggle expressions that break undo (setAttr) -> rewrite them (5.0.10)", _names(old),
                len(old), fix)


def _outdated_jiggles():
    from gus_rigtool.builder import chain
    old = chain.outdated_jiggles()
    if not old:
        return None

    def fix():
        done = 0
        for e in old:
            if cmds.objExists(e):
                chain.remake_jiggle(e)
                done += 1
        return done
    return Item("outdated_jiggle", "Older jiggles (no reaction to moving, no body limit) -> remake them (5.3.2)",
                _names(old), len(old), fix)


def _always_evaluating():
    """5.3.3: jiggle / wave expressions with 'always evaluate' -> off (they kept the skin re-evaluating)."""
    from gus_rigtool.builder import chain
    exprs = chain.always_evaluating()
    if not exprs:
        return None
    return Item("always_evaluate", "Jiggle / wave expressions that always evaluate -> only when time or their "
                "inputs change (5.3.3)", _names(exprs), len(exprs), lambda: chain.stop_always_evaluating())


def ng_orphans():
    """ngSkinTools data nodes whose skin is gone."""
    out = []
    for n in cmds.ls(type="ngst2SkinLayerData") or []:
        try:
            if not cmds.listConnections(n + ".sc", source=True, destination=False):
                out.append(n)
        except (RuntimeError, ValueError):
            continue
    return out


def _ng_orphans():
    """5.3.3: ngSkinTools data left from skins that no longer exist -> delete it."""
    nodes = ng_orphans()
    if not nodes:
        return None

    def fix():
        left = [n for n in nodes if cmds.objExists(n)]
        if left:
            cmds.delete(left)
        return len(left)
    return Item("ng_orphans", "ngSkinTools data from skins that no longer exist -> delete it", _names(nodes),
                len(nodes), fix)


def _twice():
    """5.3.3: a joint plugged into a skin more than once -> merge the slots."""
    from gus_rigtool.core import skin_tools
    bad = {}
    for sk in cmds.ls(type="skinCluster") or []:
        try:
            t = skin_tools.twice(sk)
        except Exception:
            continue
        if t:
            bad[sk] = t
    if not bad:
        return None

    def fix():
        lines = []
        for sk in bad:
            if cmds.objExists(sk):
                n, posed = skin_tools.merge_twice(sk)
                lines.append(n)
                if posed:
                    utils.warn("Repair", "%s: %s were bound twice in different poses - check the mesh at rest" %
                               (sk, ", ".join(naming.short_name(j) for j in posed)))
        return sum(lines)
    joints = [j for t in bad.values() for j in t]
    return Item("skin_twice", "Joints plugged into a skin twice (painting / ngSkinTools break) -> merge them",
                "%s in %s" % (_names(joints), ", ".join(bad)), len(joints), fix)


def idle_constraints():
    """Constraints that have targets but drive nothing."""
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
        if targets:
            outs = [o for o in cmds.listConnections(con, source=False, destination=True) or []
                    if o != naming.short_name(con) and cmds.ls(o, long=True) != [con]]
            if not outs:
                idle.append(con)
    return idle


def _idle_constraints():
    """5.3.4: constraints with targets that drive nothing -> delete them."""
    idle = idle_constraints()
    if not idle:
        return None

    def fix():
        left = [c for c in idle if cmds.objExists(c)]
        if left:
            cmds.delete(left)
        return len(left)
    return Item("idle_constraints", "Constraints that drive nothing -> delete them", _names(idle), len(idle), fix)


def _plugins():
    """5.3.4: plugins the file asks for that aren't loaded -> load the ones Maya has; a request no node uses is
    taken out of the file."""
    try:
        wanted = cmds.unknownPlugin(query=True, list=True) or []
    except (RuntimeError, AttributeError):
        return None
    if not wanted:
        return None

    def fix():
        done = []
        for p in wanted:
            try:
                cmds.loadPlugin(p, quiet=True)
                done.append(p)
                continue
            except RuntimeError:
                pass
            try:
                cmds.unknownPlugin(p, remove=True)
                done.append(p)
            except RuntimeError:
                pass
        return ", ".join(done) or "none could be loaded"
    return Item("plugins", "Plugins the file asks for -> load them (or drop an unused request)", ", ".join(wanted),
                len(wanted), fix)


def _playback():
    """5.3.4: a scene with a jiggle, playback not 'every frame' -> every frame."""
    from gus_rigtool.builder import chain
    try:
        if not chain.jiggles() or not cmds.playbackOptions(query=True, playbackSpeed=True):
            return None
    except (RuntimeError, AttributeError, TypeError):
        return None

    def fix():
        cmds.playbackOptions(playbackSpeed=0, maxPlaybackSpeed=1)
        return "every frame (up to real time)"
    return Item("playback", "Playback isn't 'every frame' (the jiggle rests) -> every frame", "", 1, fix)


def unused_joint_roots():
    """5.3.4: hand-made joint hierarchies outside skeleton_grp that skin nothing and drive / are driven by
    nothing (only their own parent-child links and old bind poses) - the Hare's joint1-5 and its old L_Clavicule
    arm. Returns their top joints."""
    from gus_rigtool.tools import checker
    skel = checker._group("skeleton")
    made = checker._tool_made_joints()
    roots = []
    for j in cmds.ls(type="joint", long=True) or []:
        par = cmds.listRelatives(j, parent=True, fullPath=True) or []
        if par and cmds.nodeType(par[0]) == "joint":
            continue
        if (skel and j.startswith(skel + "|")) or j in made:
            continue
        chain = [j] + (cmds.listRelatives(j, allDescendents=True, type="joint", fullPath=True) or [])
        if any(x in made for x in chain):
            continue
        used = False
        for x in chain:
            for p in cmds.listConnections(x, source=False, destination=True, plugs=True) or []:
                if cmds.nodeType(p.split(".")[0]) not in ("joint", "dagPose"):
                    used = True
                    break
            if used:
                break
            for p in cmds.listConnections(x, source=True, destination=False, plugs=True) or []:
                if cmds.nodeType(p.split(".")[0]) not in ("joint",):
                    used = True
                    break
            if used:
                break
        if not used:
            roots.append(j)
    return roots


def _unused_joints():
    roots = unused_joint_roots()
    if not roots:
        return None

    def fix():
        left = [r for r in roots if cmds.objExists(r)]
        if left:
            cmds.delete(left)
        return len(left)
    return Item("unused_joints", "Loose joints that skin and drive nothing (outside the skeleton) -> delete them",
                _names(roots), len(roots), fix)


def curveless_views():
    """5.4.2: viewports with curves switched off (Show > NURBS Curves) - controls and new curves don't show there
    (the Hare's modelPanel4: Edge to curve looked empty)."""
    out = []
    try:
        for p in cmds.getPanel(type="modelPanel") or []:
            if not cmds.modelEditor(p, query=True, nurbsCurves=True):
                out.append(p)
    except (RuntimeError, AttributeError, TypeError):
        pass
    return out


def _curveless_views():
    views = curveless_views()
    if not views:
        return None

    def fix():
        for p in views:
            cmds.modelEditor(p, edit=True, nurbsCurves=True)
        return len(views)
    return Item("curve_views", "Viewports with curves hidden (controls invisible there) -> show curves",
                ", ".join(views), len(views), fix)


def _util_names():
    """5.3.3: utility nodes still called by their type + number (unitConversion253...) -> named from their
    connections, as Nodes > Name utility nodes does."""
    from gus_rigtool.core import networks
    try:
        plan = networks.plan()
    except Exception:
        return None
    if not plan:
        return None

    def fix():
        return len(networks.rename(networks.plan()))
    return Item("util_names", "Utility nodes with default names -> name them from their connections",
                _names([old for old, _new in plan]), len(plan), fix)


def _skin_limits():
    """5.3.3: skins with vertices over their joints-per-vertex limit -> cut to the limit, every vertex to 1."""
    from gus_rigtool.tools import checker
    try:
        verts = checker.find_skin_influences(None)
    except Exception:
        return None
    meshes = []
    ng = ng_skins()
    for v in verts:
        m = v.split(".")[0]
        if m not in meshes and _skin_of_mesh(m) not in ng:   # 5.6.1: ngSkinTools decides those weights
            meshes.append(m)
    if not meshes:
        return None

    def fix():
        from gus_rigtool.core import cloth
        done = 0
        for m in meshes:
            if cmds.objExists(m):
                cloth.repair(m)
                done += 1
        return done
    return Item("skin_limits", "Skins over their joints-per-vertex limit -> cut to the limit (every vertex to 1)",
                "%s (%d vertices)" % (_names(meshes), len(verts)), len(meshes), fix)


def _dead_twins():
    """5.6.9: ribbon bind joints that follow nothing, on a working twin's spot, still in a skin (no weight)."""
    from gus_rigtool.core import ribbon
    items = ribbon.dead_twin_skins()
    if not items:
        return []
    joints = sorted(set(j for j, _s in items))
    return [Item("ribbon_dead_twins", "Ribbon bind joints that follow nothing, on a working joint's spot, still in a "
                 "skin (a loop folding onto itself - closed lips): out of the skins (no weight - nothing moves)",
                 _names(joints), len(joints), lambda: ribbon.fix_dead_twins())]


def _scale_causes():
    """5.6.0: what keeps the rig from scaling evenly (Check this scene > Scale) - one item per cause."""
    from gus_rigtool.core import scale_check as SC
    ctrl, plug = SC.scale_control()
    if not ctrl or not plug:
        return []
    out = []
    f = SC.follicles(ctrl)
    if f:
        out.append(Item("scale_follicles", "Follicles (ribbons) that don't scale with the rig -> take the global "
                        "scale", _names(f), len(f), lambda: SC.fix_follicles(SC.follicles(ctrl), plug)))
    j = SC.joints(ctrl)
    if j:
        out.append(Item("scale_joints", "Skin joints held by a constraint that don't scale -> they take the "
                        "global scale", _names([x for x, _d in j]), len(j),
                        lambda: SC.fix_joints(SC.joints(ctrl), plug)))
    m = SC.meshes_twice(ctrl)
    if m:
        out.append(Item("scale_meshes", "Skinned meshes that scale twice -> stop inheriting the groups above",
                        _names(m), len(m), lambda: SC.fix_meshes(SC.meshes_twice(ctrl))))
    r = SC.world_measures(plug)
    if r:
        out.append(Item("scale_rest", "IK stretch / pin / soft IK lengths measured without the scale -> with it",
                        _names([n for _k, n in r]), len(r), lambda: SC.fix_world_measures(SC.world_measures(plug),
                                                                                           plug)))
    gr = SC.control_groups(ctrl)
    if gr:
        out.append(Item("scale_groups", "Control groups cut off from the scale (a group that doesn't pass it on) -> "
                        "their own scale x the global scale", _names(gr), len(gr),
                        lambda: [SC.give_scale(x, plug) for x in SC.control_groups(ctrl)]))
    ts = SC.target_scales()
    if ts:
        out.append(Item("scale_targets", "Constraint targets reading another node's scale (the global scale counted "
                        "twice: hands / head off at x2) -> their own target's scale", _names([p for p, _r in ts]),
                        len(ts), lambda: SC.fix_target_scales(SC.target_scales())))
    lg = SC.limb_groups(ctrl)
    if lg:
        out.append(Item("scale_limbs", "Groups that follow a control with a parent constraint but not its scale "
                        "(limbs stretch at x2) -> a scale constraint too", _names([g for g, _t in lg]), len(lg),
                        lambda: SC.fix_limb_groups(SC.limb_groups(ctrl))))
    return out


def _double_conversions():
    """5.5.0: two unit conversions back to back that cancel out -> the source connected straight."""
    from gus_rigtool.core import network_tools
    pairs = network_tools.double_conversions()
    if not pairs:
        return None

    def fix():
        return network_tools.fold_conversions()
    return Item("double_conversions", "Unit conversions back to back that cancel out -> connect straight",
                _names([a for a, _b, _s, _d in pairs]), len(pairs), fix)


def _dead_nodes():
    dead = []
    for kind in DEAD_TYPES:
        for n in cmds.ls(type=kind) or []:
            if not cmds.listConnections(n, source=False, destination=True) and \
                    not cmds.lockNode(n, query=True, lock=True)[0]:
                dead.append(n)
    if not dead:
        return None

    def fix():
        gone = [n for n in dead if cmds.objExists(n)]
        if gone:
            cmds.delete(gone)
        return len(gone)
    return Item("dead_nodes", "Utility nodes with no output -> delete them", _names(dead), len(dead), fix)


def _speed_chain():
    """5.6.27: a hidden mesh between two deformers keeps the chain off the graphics card."""
    from gus_rigtool.core import rigspeed as speed
    items = speed.chain_breaks()
    if not items:
        return None
    return Item("speed_chain", "Hidden meshes in the middle of deformer chains (the skin can't run on the graphics "
                "card) -> connect the deformers straight", _names([m for _u, _d, m in items]), len(items),
                lambda: speed.fix_chain_breaks())


def _speed_tags():
    """5.6.27: a deformer asking for a component tag the mesh doesn't have (a warning on every update)."""
    from gus_rigtool.core import rigspeed as speed
    items = speed.tag_problems()
    if not items:
        return None
    return Item("speed_tags", "Deformers asking for a component tag the mesh doesn't have (a warning on every "
                "update) -> the whole mesh", _names(sorted(set("%s[%d]" % (d, i) for d, i, _e, _m in items))),
                len(items), lambda: speed.fix_tags())


def _delta_mush_scale():
    """5.6.27: Delta Mush whose detail doesn't grow with the rig (the belt loses its form at x2)."""
    from gus_rigtool.core import rigspeed as speed
    plug, nodes = speed.unscaled_delta_mush()
    if not nodes:
        return None
    return Item("deltamush_scale", "Delta Mush not tied to the rig's scale (the mesh loses its form when scaled) -> "
                "displacement follows the global scale (nothing changes at scale 1)", _names(nodes), len(nodes),
                lambda: speed.fix_delta_mush(*speed.unscaled_delta_mush()))


def stray_keys():
    """[(pairBlend, [controls], [anim curves])]: keys left in the rig on channels a constraint drives."""
    out = []
    for pb in cmds.ls(type="pairBlend") or []:
        curves = []
        for a in ("inTranslate1", "inRotate1", "inTranslateX1", "inTranslateY1", "inTranslateZ1",
                  "inRotateX1", "inRotateY1", "inRotateZ1"):
            try:
                curves += cmds.listConnections(pb + "." + a, source=True, destination=False, type="animCurve") or []
            except (RuntimeError, ValueError):
                pass
        ctrls = sorted(set(cmds.listConnections(pb, source=False, destination=True, type="transform") or []))
        if curves:
            out.append((pb, ctrls, sorted(set(curves))))
    return out


def fix_stray_keys(items=None):
    """Delete those keys and give the constraint the whole say (blend weight 1)."""
    items = stray_keys() if items is None else items
    done = 0
    for pb, ctrls, curves in items:
        w = cmds.listConnections(pb + ".weight", source=True, destination=False, plugs=True) or []
        for plug in w:
            node = plug.split(".")[0]
            if cmds.nodeType(node).startswith("animCurve"):
                cmds.delete(node)
            else:
                for crv in cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []:
                    cmds.delete(crv)
                try:
                    cmds.setAttr(plug, 1)
                except RuntimeError:
                    pass
        gone = [c for c in curves if cmds.objExists(c)]
        if gone:
            cmds.delete(gone)
        done += 1
    return done


def _stray_keys():
    items = stray_keys()
    if not items:
        return None
    ctrls = sorted(set(c for _p, cs, _c in items for c in cs))
    return Item("stray_keys", "Keys left in the rig on channels a constraint drives (pairBlend) -> delete them",
                _names(ctrls or [p for p, _c, _k in items]), len(items), lambda: fix_stray_keys())


FINDERS = [_along_v, _ribbons_copying, _loops_not_mirrored, _labels, _twins, _empty_constraints, _guides_zeroed,
           _skin_sums, _ribbons_not_symmetric, _ribbon_child_binds, _old_jiggles, _outdated_jiggles, _always_evaluating, _ng_orphans, _twice, _idle_constraints, _plugins, _playback,
           _unused_joints, _curveless_views, _util_names, _skin_limits, _double_conversions, _scale_causes, _dead_twins, _dead_nodes,
           _speed_chain, _speed_tags, _delta_mush_scale, _stray_keys]


def find():
    """Every repair this scene needs (a finder that can't run here is skipped)."""
    out = []
    for f in FINDERS:
        try:
            got = f()
        except Exception:
            got = None
        if isinstance(got, list):                         # 5.6.0: a finder can give several items
            out.extend(got)
        elif got:
            out.append(got)
    return out


def apply(ids, items=None):
    """Run the picked repairs, each its own undo step (a failed one is undone at once: nothing half-done);
    returns [(label, result or 'failed: ...')]."""
    items = items if items is not None else find()
    out = []
    for it in items:                                          # 5.3.4: each repair its own undo step
        if it.id not in ids:
            continue
        ok = False
        states = safe_states(it.id)                        # 5.6.27: rest, x2 and real animation
        frames = safe.anim_frames() if "anim" in states else []
        before = safe.snapshot(states, frames) if states else {}
        cmds.undoInfo(openChunk=True, chunkName="gusrigRepair_" + it.id)
        try:
            got = it.fix()
            ok = True
            bad = safe.compare(before, safe.snapshot(states, frames)) if before else []
            if bad:                                        # a fix may never change what the animators see
                ok = False
                got = "undone - safe mode: it moved %s" % safe.describe(bad)
        except Exception as e:
            got = "failed (nothing of it left changed): %s" % str(e).strip().splitlines()[0]
        finally:
            cmds.undoInfo(closeChunk=True)
        if not ok:                                         # 5.3.4: a failed fix leaves nothing half-done
            try:
                # only our own step (a fix that failed before changing anything left no step of its own)
                if cmds.undoInfo(query=True, state=True) and \
                        "gusrigRepair_" + it.id in (cmds.undoInfo(query=True, undoName=True) or ""):
                    cmds.undo()
            except RuntimeError:
                pass
        out.append((it.label, got))
    return out
