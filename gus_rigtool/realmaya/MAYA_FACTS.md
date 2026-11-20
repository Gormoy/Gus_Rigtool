# Maya facts

How Maya really behaves where Gus_Rigtool and Gus Animtool depend on it. Each line was learned the hard way (the
tool assumed something else). `maya_facts.py` checks them again in every real-Maya run (case m, and Test this
release); when an answer here changes, the fake Maya (`tests/fakemaya.py`) is changed to match.

Before building a feature that depends on how Maya behaves: add the question to `maya_facts.py` first and get
Gus's answer, then build.

| Fact | What Maya does | Found | Version |
|---|---|---|---|
| `multiplyDivide` dividing by a small number | warns "divide by zero" (every evaluation) below about 0.00001 - a floor of 0.000001 counts as zero; 0.001 is quiet | Gus's log, attach | 5.6.43 |
| `clamp` floor 0.001 | stored as a float: 0.0010000000474974513 | real-Maya case j | 5.6.43 |
| `cmds.ls([])` (an empty list) | lists EVERYTHING in the scene, not nothing - guard empty lists | onion skin | onion Nov 19 |
| follower's own `parentInverseMatrix` in its own driving setup | a cycle: "Cycle on ...outputMatrix", the follower lags / stutters - use the parent's `worldInverseMatrix` | Gus's log, attach | 5.6.41 |
| Time Slider bookmarks | a plugin: `timeSliderBookmark` must be loaded first; without a window (mayapy) none are made | attach, case i | 5.6.41 / 5.6.44 |
| undo without a window (mayapy) | to be confirmed by case m (case h's Ctrl+Z check came back 'not undone') | case h | 5.6.44 |
| moving keys (`keyframe -edit -relative -timeChange`) | can fail with "Cannot move keys" and stop all the curves in the call; which curve and why: case m | Gus, inbetween | 5.6.44 |
| a keyed control attached (Animtool Attach) | its own keys keep working on top of the attach (by design, Gus: keep it) | case i | 5.6.44 |
| Qt windows parented to Maya on the Mac | go behind Maya when Maya is clicked - use `Qt.Tool` (+ `WA_MacAlwaysShowToolWindow`) | Gus, Mac | 5.6.42 |
| editable motion trail (`snapshot -motionTrail`) | shows translate keys only; a control with no translate keys (moved by an attach) shows the trail but can't be edited | Gus, arcs | 5.6.41 |
