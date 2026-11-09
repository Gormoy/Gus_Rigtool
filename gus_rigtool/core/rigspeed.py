"""
Speed (5.6.27): what makes the rig slow to move, and the fixes that don't change how it looks.

    from gus_rigtool.core import rigspeed
    rigspeed.time_drag()            # {control: ms per step} - the COG / World dragged a few steps
    rigspeed.chain_breaks()         # a hidden mesh in the middle of a deformer chain (keeps it off the graphics card)
    rigspeed.tag_problems()         # deformer inputs naming a component tag the mesh doesn't have (a warning per update)
    rigspeed.unscaled_delta_mush()  # Delta Mush that doesn't scale its detail with the rig
    rigspeed.gpu_reasons()          # {mesh: [why it can't go to the graphics card]}

Every fix here runs through Repair, so safe mode undoes it if anything the animators see moves.
"""

import maya.cmds as cmds

STEPS = 12
GPU_MIN_VERTICES = 2000       # Maya's GPU override leaves smaller meshes on the CPU (its default)


def _short(n):
    return n.split("|")[-1]


# ---------------------------------------------------------------------------
# timing
# ---------------------------------------------------------------------------

def drag_controls():
    """The controls an animator drags that move everything: COG and World / Global (found by name or tag)."""
    out = []
    try:
        from gus_rigtool.core import world_levels
        lv = world_levels.levels()
        for k in ("world", "global"):
            if lv.get(k):
                out.append(lv[k])
    except Exception:
        pass
    for pat in ("*COG*_ctrl", "*cog*_ctrl", "*COG*_CTRL", "World_ctrl", "*:World_ctrl"):
        for n in cmds.ls(pat, type="transform", long=True) or []:
            if n not in out and cmds.listRelatives(n, shapes=True, type="nurbsCurve"):
                out.append(n)
    return out[:3]


def _step_time(plug, steps):
    import time
    v0 = cmds.getAttr(plug)
    cmds.refresh(force=True)
    t = time.time()
    for i in range(steps):
        cmds.setAttr(plug, v0 + (i + 1) * 0.5)
        cmds.refresh(force=True)
    dt = (time.time() - t) / float(steps)
    cmds.setAttr(plug, v0)
    cmds.refresh(force=True)
    return dt * 1000.0


def time_drag(controls=None, steps=STEPS, skins_off=False):
    """{control: ms per step} dragging translateX (everything put back, no undo steps). skins_off: the same
    with every skin switched off for the test (what the skinning costs)."""
    from gus_rigtool.core import safe
    controls = controls if controls is not None else drag_controls()

    def go():
        back = []
        if skins_off:
            for s in cmds.ls(type="skinCluster") or []:
                try:
                    back.append((s, cmds.getAttr(s + ".nodeState")))
                    cmds.setAttr(s + ".nodeState", 1)
                except Exception:
                    pass
        out = {}
        try:
            for c in controls:
                plug = c + ".translateX"
                try:
                    if cmds.getAttr(plug, settable=True):
                        out[c] = _step_time(plug, steps)
                except Exception:
                    pass
        finally:
            for s, v in back:
                try:
                    cmds.setAttr(s + ".nodeState", v)
                except Exception:
                    pass
        return out
    return safe._no_undo(go)


# ---------------------------------------------------------------------------
# deformer chains
# ---------------------------------------------------------------------------

def _deformers():
    return cmds.ls(type="geometryFilter") or []


def _indices(dfm):
    try:
        return cmds.getAttr(dfm + ".input", multiIndices=True) or []
    except Exception:
        return []


def _source(plug):
    got = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
    return got[0] if got else None


def chain_breaks():
    """[(upstream deformer plug, deformer input plug, hidden mesh)]: a hidden (intermediate) mesh between two
    deformers that feeds only the next one - Maya then can't run the chain on the graphics card. Connecting the
    two deformers straight gives the same result."""
    out = []
    for dfm in _deformers():
        for i in _indices(dfm):
            dst = "%s.input[%d].inputGeometry" % (dfm, i)
            src = _source(dst)
            if not src:
                continue
            mesh = src.split(".")[0]
            try:
                if cmds.nodeType(mesh) != "mesh" or not cmds.getAttr(mesh + ".intermediateObject"):
                    continue
            except Exception:
                continue
            up = _source(mesh + ".inMesh")
            if not up or not cmds.objectType(up.split(".")[0], isAType="geometryFilter"):
                continue
            outs = cmds.listConnections(mesh, source=False, destination=True, plugs=True, connections=True) or []
            other = False
            for k in range(0, len(outs), 2):
                mine, theirs = outs[k], outs[k + 1]
                attr = mine.split(".", 1)[1]
                if not (attr.startswith("worldMesh") or attr.startswith("outMesh")):
                    continue
                if theirs.split(".")[0] != dfm:
                    other = True
                    break
            if not other:
                out.append((up, dst, mesh))
    return out


def fix_chain_breaks(items=None):
    """Connect each pair of deformers straight and delete the hidden mesh between them. Returns how many."""
    items = chain_breaks() if items is None else items
    done = 0
    for up, dst, mesh in items:
        cmds.connectAttr(up, dst, force=True)
        if cmds.objExists(mesh):
            try:
                cmds.delete(mesh)
            except RuntimeError:
                pass
        done += 1
    return done


def _tags_on(plug):
    """The component tag names on the geometry coming into plug, or None when Maya can't say."""
    try:
        got = cmds.geometryAttrInfo(plug, componentTagNames=True)
        return set(got or [])
    except Exception:
        return None


def _expr_names(expr):
    import re
    return [t for t in re.split(r"[\s,+\-*&|()!]+", expr or "") if t]


def tag_problems():
    """[(deformer, index, expression, missing tags)]: a deformer input asks for component tags the mesh doesn't
    have - Maya prints a warning on every update (the Head_squash flood) and slows down."""
    out = []
    for dfm in _deformers():
        for i in _indices(dfm):
            plug = "%s.input[%d].componentTagExpression" % (dfm, i)
            try:
                expr = cmds.getAttr(plug)
            except Exception:
                continue
            if not expr or expr.strip() == "*":
                continue
            have = _tags_on("%s.input[%d].inputGeometry" % (dfm, i))
            if have is None:
                continue
            missing = [t for t in _expr_names(expr) if t not in have]
            if missing:
                out.append((dfm, i, expr, missing))
    return out


def fix_tags(items=None):
    """Inputs whose tag is missing take the whole mesh (an empty expression - what the deformer's weights then
    limit). Returns how many."""
    items = tag_problems() if items is None else items
    for dfm, i, _e, _m in items:
        cmds.setAttr("%s.input[%d].componentTagExpression" % (dfm, i), "", type="string")
    return len(items)


# ---------------------------------------------------------------------------
# delta mush and scale
# ---------------------------------------------------------------------------

def unscaled_delta_mush():
    """(plug, [delta mush]) - Delta Mush nodes whose displacement isn't tied to the rig's scale: their detail
    stays the same size when the rig grows, so the mesh loses its form at x2 (the belt)."""
    from gus_rigtool.core import safe
    plug = safe.scale_plug()
    if not plug:
        return None, []
    out = []
    for dm in cmds.ls(type="deltaMush") or []:
        if not cmds.listConnections(dm + ".displacement", source=True, destination=False):
            out.append(dm)
    return plug, out


def fix_delta_mush(plug=None, nodes=None):
    """Tie each Delta Mush's displacement to the global scale (x its own value when that isn't 1): at scale 1
    nothing changes. Returns how many."""
    if plug is None or nodes is None:
        plug, nodes = unscaled_delta_mush()
    done = 0
    for dm in nodes or []:
        v = cmds.getAttr(dm + ".displacement")
        if abs(v - 1.0) < 1e-6:
            cmds.connectAttr(plug, dm + ".displacement", force=True)
        else:
            md = cmds.createNode("multDoubleLinear", name=_short(dm) + "_scale_mdl", skipSelect=True)
            cmds.setAttr(md + ".input2", v)
            cmds.connectAttr(plug, md + ".input1")
            cmds.connectAttr(md + ".output", dm + ".displacement", force=True)
        done += 1
    return done


# ---------------------------------------------------------------------------
# graphics card
# ---------------------------------------------------------------------------

NON_DEFORMERS_OK = ("groupParts", "groupId", "tweak", "objectSet", "dagPose", "shadingEngine", "nodeGraphEditorInfo")


def gpu_on():
    try:
        return bool(cmds.evaluator(name="deformer", query=True, enable=True))
    except Exception:
        return None


def geo_chain(mesh, limit=60):
    """The nodes the mesh's geometry flows through, nearest first (deformers, hidden meshes, poly modifiers)."""
    import re
    out = []
    plug = _source(mesh + ".inMesh")
    while plug and len(out) < limit:
        node, attr = plug.split(".", 1)
        if node in out:
            break
        out.append(node)
        if cmds.objectType(node, isAType="geometryFilter"):
            m = re.search(r"\[(\d+)\]", attr)
            plug = _source("%s.input[%s].inputGeometry" % (node, m.group(1) if m else 0))
        elif cmds.nodeType(node) == "mesh":
            plug = _source(node + ".inMesh")
        else:
            nxt = None
            for a in ("inputPolymesh", "inMesh", "inputGeometry"):
                if cmds.attributeQuery(a, node=node, exists=True):
                    nxt = _source(node + "." + a)
                    if nxt:
                        break
            plug = nxt
    return out


def gpu_reasons():
    """{visible deformed mesh: [reasons it stays on the CPU]} (only meshes with at least one reason)."""
    tags = set(d for d, _i, _e, _m in tag_problems())
    out = {}
    for m in cmds.ls(type="mesh", noIntermediate=True, long=True) or []:
        chain = geo_chain(m)
        dfms = [h for h in chain if cmds.objectType(h, isAType="geometryFilter")]
        if not dfms:
            continue
        why = []
        try:
            n = cmds.polyEvaluate(m, vertex=True)
            if isinstance(n, int) and n < GPU_MIN_VERTICES:
                why.append("%d vertices (Maya keeps meshes under %d on the CPU)" % (n, GPU_MIN_VERTICES))
        except Exception:
            pass
        last = max(chain.index(d) for d in dfms)
        hidden = [h for h in chain[:last] if cmds.nodeType(h) == "mesh"]
        if hidden:
            why.append("a hidden mesh in the middle of the deformer chain (%s)" % _short(hidden[0]))
        for d in dfms:
            if d in tags:
                why.append("%s asks for a component tag the mesh doesn't have" % _short(d))
        other = sorted(set(cmds.nodeType(h) for h in chain if cmds.nodeType(h) != "mesh" and
                           not cmds.objectType(h, isAType="geometryFilter") and
                           cmds.nodeType(h) not in NON_DEFORMERS_OK))
        if other:
            why.append("non-deformer history: %s (clean it in the model file)" % ", ".join(other[:4]))
        if why:
            out[m] = why
    return out
