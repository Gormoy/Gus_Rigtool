"""
Speed (5.6.27): what makes the rig slow to move, and the fixes that don't change how it looks.

    from gus_rigtool.core import rigspeed
    rigspeed.time_drag()            # {control: ms per step} - the COG / World dragged a few steps
    rigspeed.chain_breaks()         # a hidden mesh in the middle of a deformer chain (keeps it off the graphics card)
    rigspeed.tag_problems()         # deformer inputs naming a component tag the mesh doesn't have (a warning per update;
                                    # 5.6.28: reported only - make the deformer again)
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
    try:
        cmds.refresh(force=True)
        t = time.time()
        for i in range(steps):
            cmds.setAttr(plug, v0 + (i + 1) * 0.5)
            cmds.refresh(force=True)
        dt = (time.time() - t) / float(steps)
    finally:                                        # 5.6.28: always back where it was (there's no undo for it)
        cmds.setAttr(plug, v0)
        try:
            cmds.refresh(force=True)
        except Exception:
            pass
    return dt * 1000.0


def _autokey_off():
    """5.6.28: Auto Key off for the test (dragging by script could key the COG); returns how it was."""
    try:
        was = bool(cmds.autoKeyframe(query=True, state=True))
        if was:
            cmds.autoKeyframe(state=False)
        return was
    except Exception:
        return False


SKIPPED = {}                  # 5.6.29: {control: why it couldn't be timed} - the last time_drag()


def time_drag(controls=None, steps=STEPS, skins_off=False, off=None, hide=None, attrs=None):
    """{control: ms per step} dragging translateX (everything put back, no undo steps). skins_off: the same
    with every skin switched off for the test (what the skinning costs); off: these deformers switched off;
    hide: these meshes hidden; attrs: {plug: value} set for the test (5.6.30: a piece's Clothes switch).
    5.6.29: a control that can't be timed is in SKIPPED with the reason (it was left out without a word)."""
    from gus_rigtool.core import safe
    controls = controls if controls is not None else drag_controls()
    SKIPPED.clear()

    def go():
        back = []
        key_was = _autokey_off()
        every = (cmds.ls(type="skinCluster") or []) if skins_off else []
        temp = [(s + ".nodeState", 1) for s in every + list(off or [])]
        temp += [(m + ".visibility", 0) for m in hide or []] + list((attrs or {}).items())
        for plug, value in temp:
            try:
                if cmds.getAttr(plug, settable=True):
                    back.append((plug, cmds.getAttr(plug)))
                    cmds.setAttr(plug, value)
            except Exception:
                pass
        out = {}
        try:
            for c in controls:
                plug = c + ".translateX"
                try:
                    if cmds.getAttr(plug, settable=True):
                        out[c] = _step_time(plug, steps)
                    else:
                        SKIPPED[c] = "translateX is locked or driven"
                except Exception as e:
                    SKIPPED[c] = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        finally:
            for plug, v in reversed(back):
                try:
                    cmds.setAttr(plug, v)
                except Exception:
                    pass
            if key_was:
                try:
                    cmds.autoKeyframe(state=True)
                except Exception:
                    pass
        return out
    return safe._no_undo(go)


def _skin_size(skin):
    """(vertices, influences) of a skin, (0, 0) when Maya can't say."""
    n = 0
    for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
        try:
            v = cmds.polyEvaluate(g, vertex=True)
            n += v if isinstance(v, int) else 0
        except Exception:
            pass
    return n, len(cmds.skinCluster(skin, query=True, influence=True) or [])


def _mesh_of(skin):
    geos = cmds.skinCluster(skin, query=True, geometry=True) or []
    if not geos:
        return "?"
    t = cmds.listRelatives(geos[0], parent=True) or [geos[0]]
    return t[0].split(":")[-1]


def gpu_set(on):
    """GPU override on / off for this session (Preferences > Animation): True when it could be set."""
    try:
        cmds.evaluator(name="deformer", enable=bool(on))
        return True
    except Exception:
        return False


def extra_timings(control, steps=8, top=6, small=2):
    """5.6.29: one control dragged in more ways (everything put back). Returns {
      'base': ms, 'clothes': ms or None (Visibility_ctrl.Clothes hidden), 'gpu_off': ms or None (GPU override off,
      when it's on), 'overhead': ms every skin costs just for being there (the smallest skins switched off),
      'skins': [(skin, mesh, vertices, influences, ms saved, ms above the overhead)] - the heaviest first,
      'skipped': [why something wasn't timed]}"""
    from gus_rigtool.core import clothes_switch as CS
    out = {"base": None, "clothes": None, "gpu_off": None, "overhead": 0.0, "skins": [], "skipped": [],
           "pieces": []}

    def one(**k):
        t = time_drag([control], steps=steps, **k)
        if control not in t:
            out["skipped"].append(SKIPPED.get(control, "not timed"))
        return t.get(control)

    out["base"] = one()
    if out["base"] is None:
        return out
    try:
        with CS.hidden() as there:
            if there:
                out["clothes"] = one()
    except Exception as e:
        out["skipped"].append("clothes hidden: %s" % e)
    if gpu_on():
        try:
            if gpu_set(False):
                out["gpu_off"] = one()
        finally:
            gpu_set(True)
    out["pieces"] = []                                 # 5.6.30: each clothes piece hidden on its own
    try:
        data = CS.read()
        if data.get("parts"):
            sw = CS._switch_control()
            for part, p in sorted(data["parts"].items()):
                ms = one(attrs={"%s.%s" % (sw, p["attr"]): 1})
                if ms is not None:
                    out["pieces"].append((part, max(0.0, out["base"] - ms)))
        else:
            by = {}
            for m in CS.suggest():
                by.setdefault(CS.part_of(m), []).append(m)
            for part, ms_ in sorted(by.items()):
                _m, _k, dfm = CS.plan(ms_)
                ms = one(hide=ms_, off=dfm)
                if ms is not None:
                    out["pieces"].append((part, max(0.0, out["base"] - ms)))
    except Exception as e:
        out["skipped"].append("clothes pieces: %s" % e)
    sized = []
    for skin in cmds.ls(type="skinCluster") or []:
        try:
            v, n = _skin_size(skin)
        except Exception:
            continue
        sized.append((v * max(n, 1), v, n, skin))
    if not sized:
        return out
    sized.sort()
    tiny = [x[3] for x in sized[:small]]
    heavy = [x for x in reversed(sized) if x[3] not in tiny][:top]
    saved = [out["base"] - (one(off=[s]) or out["base"]) for s in tiny]
    out["overhead"] = max(0.0, sum(saved) / len(saved)) if saved else 0.0
    for _w, v, n, skin in heavy:
        ms = one(off=[skin])
        if ms is None:
            continue
        gain = max(0.0, out["base"] - ms)
        out["skins"].append((skin, _mesh_of(skin), v, n, gain, max(0.0, gain - out["overhead"])))
    return out


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
    return [t for t in re.split(r"[\s,+\-&|()!]+", expr or "") if t]     # 5.6.28: * stays (a wildcard)


def _tag_found(name, have):
    """5.6.28: a name in a tag expression is there when a tag matches it (wildcards: head_* matches head_top)."""
    import fnmatch
    if name in have:
        return True
    return any(ch in name for ch in "*?[") and any(fnmatch.fnmatchcase(t, name) for t in have)


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
            missing = [t for t in _expr_names(expr) if not _tag_found(t, have)]
            if missing:
                out.append((dfm, i, expr, missing))
    return out


def fix_tags(items=None):
    """5.6.28: nothing is changed any more - reported only. 5.6.27 gave such inputs the whole mesh (an empty
    expression), but nothing says which vertices the deformer was meant to move: the Head_squash lattice could
    then reach the neck and shoulders, which safe mode can't see (nothing moves until it squashes). The clean fix
    is to make the deformer again (Face tab > Head squash: Remove, then Make - 5.6.28 needs no tags). Returns 0."""
    return 0


def tag_advice(dfm):
    """What to do about a deformer asking for a missing tag (said in Check this scene)."""
    if "squash" in dfm.lower():
        return "Face tab > Head squash: Remove, then Make (5.6.28 makes it without component tags)"
    return "make the deformer again on the mesh (Repair can't tell which vertices it was meant to move)"


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
