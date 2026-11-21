# Maya facts

How Maya really behaves where Gus_Rigtool and Gus Animtool depend on it. Each line was learned the hard way (the
tool assumed something else). `maya_facts.py` checks them again in every real-Maya run (case m, and Test this
release); when an answer here changes, the fake Maya (`tests/fakemaya.py`) is changed to match.

Before building a feature that depends on how Maya behaves: add the question to `maya_facts.py` first and get
Gus's answer, then build.

| Fact | What Maya does | Found | Version |
|---|---|---|---|
| `pluginInfo -edit -writeRequires false` | does NOT stop the `requires` line while a node of the plugin is in the scene (even a do-not-write one). What works: delete the node in a kBeforeSave / kBeforeExport callback and make it again in kAfterSave (Review Notes 0.1.3+): a real save then has no node and no requires | Review Notes self test 0.1.2 FAIL, 0.1.4 all ok | 2026-11-21 |
| Updating a Python plugin (.py) while Maya runs | `unloadPlugin` works (once its node is out of the undo queue: `flushUndo`), but `loadPlugin` then runs the OLD code if the plugin's module is still in `sys.modules` - pop it first | Review Notes 0.1.3 (stayed 0.1.1), 0.1.4 ok | 2026-11-21 |
| `MFileIO` (the open scene's file) | only in the OLD Python API (`maya.OpenMaya.MFileIO.currentFile()`); `maya.api.OpenMaya` has no MFileIO in Maya 2024 (AttributeError) | Review Notes 0.1.0 drew nothing; Gus's paste | 2026-11-21 |
| A plugin locator marked do-not-write (`MFnDependencyNode.setDoNotWrite(True)` on shape in postConstructor + on the transform) | the node is NOT written. BUT a normal SAVE still wrote `requires "reviewNotesNode.py"` (an EXPORT did not - the 0.1.0 self test only exported), so opening the scene said "Plug-in reviewNotesNode.py was not found on MAYA_PLUG_IN_PATH". 0.1.2 sets `pluginInfo -edit -writeRequires false`; its self test does a real save | Review Notes self test 0.1.0 + Gus's test.ma | 2026-11-21 |
| `cmds.pluginDisplayFilter(name, register=True, classification='drawdb/geometry/...')` | adds a Show menu entry; it's ON in every model panel by default | Review Notes self test 0.1.0 | 2026-11-21 |
| Where the resolution gate is in a view (Review Notes) | `MFnCamera.getViewingFrustum(viewW/viewH, True, False, True)` vs `getRenderingFrustum(deviceAspectRatio)`: their ratio puts the gate exactly on Maya's own gate, at overscan 1.0 and 1.3 (Gus's Mac, persp, 960x540) | Review Notes try-it, Gus's screenshot | try-it 2026-11-21 |
| View sizes in a draw override on a Mac Retina screen | `frameContext.getViewportDimensions()` and 2D drawing are in SCREEN pixels (2 per point: a 1634-point view reports 3268); text sizes must be scaled by the pixel ratio | Review Notes try-it (label box cut short) | try-it 2026-11-21 |
| `multiplyDivide` dividing by a small number | warns "divide by zero" at 0.00001 and below, quiet from 0.00002 (Gus's Mac, Maya 2024); the attach's 0.001 is quiet | Gus's log; facts 5.6.46 | 5.6.43 / 5.6.46 |
| `clamp` floor 0.001 | stored as a float: 0.0010000000474974513 | real-Maya case j | 5.6.43 |
| `cmds.ls([])` (an empty list) | lists NOTHING, with or without flags (type='mesh', long, dag, objectsOnly), and `listRelatives([])` too (Gus's Mac) - the 'lists everything' line here before was WRONG; the fake Maya matches since 5.6.48 | facts 5.6.46 / 5.6.47 | 5.6.46 / 5.6.48 |
| follower's own `parentInverseMatrix` in its own driving setup | a cycle: "Cycle on ...outputMatrix", the follower lags / stutters - use the parent's `worldInverseMatrix` | Gus's log, attach | 5.6.41 |
| Time Slider bookmarks | a plugin: `timeSliderBookmark` must be loaded first; without a window (mayapy) `createBookmark` fails ("$gPlayBackSlider is an undeclared variable"); with the window they're made | attach, case i; facts 5.6.46 | 5.6.41 / 5.6.46 |
| undo without a window (mayapy) | undo is ON (both with and without a window) | facts 5.6.46 | 5.6.46 |
| moving keys (`keyframe -edit -relative -timeChange`) | moving a key onto another one: allowed with both the default option and 'over' (they end up 0.0000002 apart); a curve with lockNode: moves. A locked channel, a curve in an animation layer, a range with no keys: all move (no error). So 'Cannot move keys' (Gus's shot) is still unknown - the tool now names the curves it refuses, and Copy the last problem captures it | Gus, inbetween; facts 5.6.46 / 5.6.47 | 5.6.44 / 5.6.47 |
| a keyed control attached (Animtool Attach) | its own keys keep working on top of the attach (by design, Gus: keep it) | case i | 5.6.44 |
| Qt windows parented to Maya on the Mac | go behind Maya when Maya is clicked - use `Qt.Tool` (+ `WA_MacAlwaysShowToolWindow`) | Gus, Mac | 5.6.42 |
| editable motion trail (`snapshot -motionTrail`) | shows translate keys only; a control with no translate keys (moved by an attach) shows the trail but can't be edited | Gus, arcs | 5.6.41 |
| `controller -query -parent` | answers the parent's tag node name, as a string (e.g. 'nurbsCircle1_tag') | facts 5.6.46 | 5.6.46 |
| arc styling after Make weighted | each setAttr on the trail was its own undo step: the first Ctrl+Z undid a style change, not the weighting - styling is out of undo since 5.6.47 | case h; Gus's Test this release | 5.6.47 |
| a shape (control curve data) | a LIST of curves, each {degree, form, points, knots}; one curve on its own fails in Maya ('string indices must be integers') - the fake used to accept anything | Test this release (pick-walk) | 5.6.47 |
| matrix / pin nodes in Maya 2024 | blendMatrix, multMatrix, pickMatrix, aimMatrix, uvPin, proximityPin | facts 5.6.46 | 5.6.46 |
| a key's two handles on a motion trail | joined ('unified') by default: moving one turns the other; the motion trail has no break button (Autodesk help: Graph Editor > Tangents > Break Tangents) - Arcs > Break the handles since 5.6.47 (`keyTangent -lock false`) | Gus, arcs | 5.6.47 |
| the nearest point on a mesh, a ray onto a mesh (`MFnMesh.getClosestPointAndNormal`, `closestIntersection`) | both work (a radius 2 sphere: the nearest point from x=5 is [2,0,0], normal [1,0,0]; a ray from the centre along +Z hits [0,0,2]) - Fit to the body / Lie on the skin use them | facts 5.6.47 | 5.6.47 / 5.6.48 |
| changing a referenced or locked control's shape | its curve can't be deleted (so the old 'new curve, delete the old' failed on other rigs); since 5.6.48 it's rebuilt in place with `curve -replace`: it works on a plain curve, one with history, a locked one (lockNode) and one from a referenced file; a LOCKED curve can't be deleted ('Cannot delete locked node'), the referenced one could here | Gus, other rigs; facts 5.6.48 | 5.6.48 |
| `evalDeferred` inside a running script | waits in Maya's idle queue: `maya.utils.processIdleEvents()` doesn't run it, `flushIdleQueue` does - the 5.6.47 click-away check failed for that; the tool worked (5.6.48 check passes) | Test this release | 5.6.48 |
| Qt widgets inside a workspaceControl; today's cmds pages moved into a Qt widget (the 5.7 window) | ASK: Test this release 5.7.0 checks it (opens, docks, an old page inside) | 5.7.0 | 5.7.0 |
