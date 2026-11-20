# Maya facts

How Maya really behaves where Gus_Rigtool and Gus Animtool depend on it. Each line was learned the hard way (the
tool assumed something else). `maya_facts.py` checks them again in every real-Maya run (case m, and Test this
release); when an answer here changes, the fake Maya (`tests/fakemaya.py`) is changed to match.

Before building a feature that depends on how Maya behaves: add the question to `maya_facts.py` first and get
Gus's answer, then build.

| Fact | What Maya does | Found | Version |
|---|---|---|---|
| `multiplyDivide` dividing by a small number | warns "divide by zero" at 0.00001 and below, quiet from 0.00002 (Gus's Mac, Maya 2024); the attach's 0.001 is quiet | Gus's log; facts 5.6.46 | 5.6.43 / 5.6.46 |
| `clamp` floor 0.001 | stored as a float: 0.0010000000474974513 | real-Maya case j | 5.6.43 |
| `cmds.ls([])` (an empty list, no flags) | lists NOTHING (Gus's Mac, 5.6.46 facts) - the 'lists everything' line here before was WRONG; with flags (type=...): facts 5.6.47 | facts 5.6.46 | 5.6.46 |
| follower's own `parentInverseMatrix` in its own driving setup | a cycle: "Cycle on ...outputMatrix", the follower lags / stutters - use the parent's `worldInverseMatrix` | Gus's log, attach | 5.6.41 |
| Time Slider bookmarks | a plugin: `timeSliderBookmark` must be loaded first; without a window (mayapy) `createBookmark` fails ("$gPlayBackSlider is an undeclared variable"); with the window they're made | attach, case i; facts 5.6.46 | 5.6.41 / 5.6.46 |
| undo without a window (mayapy) | undo is ON (both with and without a window) | facts 5.6.46 | 5.6.46 |
| moving keys (`keyframe -edit -relative -timeChange`) | moving a key onto another one: allowed with both the default option and 'over' (they end up 0.0000002 apart); a curve with lockNode: moves. So 'Cannot move keys' (Gus's shot) is something else: facts 5.6.47 try a locked channel, an animation layer, a range with no keys | Gus, inbetween; facts 5.6.46 | 5.6.44 / 5.6.46 |
| a keyed control attached (Animtool Attach) | its own keys keep working on top of the attach (by design, Gus: keep it) | case i | 5.6.44 |
| Qt windows parented to Maya on the Mac | go behind Maya when Maya is clicked - use `Qt.Tool` (+ `WA_MacAlwaysShowToolWindow`) | Gus, Mac | 5.6.42 |
| editable motion trail (`snapshot -motionTrail`) | shows translate keys only; a control with no translate keys (moved by an attach) shows the trail but can't be edited | Gus, arcs | 5.6.41 |
| `controller -query -parent` | answers the parent's tag node name, as a string (e.g. 'nurbsCircle1_tag') | facts 5.6.46 | 5.6.46 |
| arc styling after Make weighted | each setAttr on the trail was its own undo step: the first Ctrl+Z undid a style change, not the weighting - styling is out of undo since 5.6.47 | case h; Gus's Test this release | 5.6.47 |
| a shape (control curve data) | a LIST of curves, each {degree, form, points, knots}; one curve on its own fails in Maya ('string indices must be integers') - the fake used to accept anything | Test this release (pick-walk) | 5.6.47 |
| matrix / pin nodes in Maya 2024 | blendMatrix, multMatrix, pickMatrix, aimMatrix, uvPin, proximityPin | facts 5.6.46 | 5.6.46 |
| a key's two handles on a motion trail | joined ('unified') by default: moving one turns the other; the motion trail has no break button (Autodesk help: Graph Editor > Tangents > Break Tangents) - Arcs > Break the handles since 5.6.47 (`keyTangent -lock false`) | Gus, arcs | 5.6.47 |
