# Discussions with Gus - decisions, preferences, open plans

Kept up to date during every conversation (CLAUDE.md rule 14) so nothing we talk about is lost when Claude's
context resets - not only the releases. Newest at the top of each section. PROJECT_CONTEXT.md has the history of
the code; this file has what Gus said, decided and wants next.

## Gus's preferences (how he likes to work)

- Plain words, short numbered lists, numbered questions; be honest about flaws and what is untested.
- Previews (mock-ups) before building anything visual; he decides from pictures.
- No emoji in the tools' UI (they don't look professional) - line icons are good (lamp, pin, brush OK).
- "We are not building new tools" - improve what exists: clearer, more useful, everything together.
- Every update must keep all the good parts and options of the older version ("an update, not a loss").
- Wants the commands to paste at the end of every release message (CLAUDE.md 6b).
- Uses the Rigtool's Update button more than the zip + drag, likes having both.
- Works on macOS, Maya 2024 (PySide2). Real-Maya tests + Test this release are run by him and pasted back.

## Decisions (newest first)

- 2026-11-21: Gus on 0.2.1: notes stick to their frame now; Enter / Esc / double-click for curves work; the
  eraser "just deletes everything instead of acting like an eraser" -> 0.2.2: the eraser cuts only the part it
  rubs over (a touched curve / circle / arrow becomes plain lines), Size = eraser size, saved notes too (one
  save per mouse event, .bak keeps the file from before the drag). His video test2.mov = a playblast with the
  notes in it (playblasts OK). "In general it's looking good" - asked when SyncSketch comes in. Found
  (SyncSketch's own Python library README; their site wasn't reachable from here): API access needs an
  ENTERPRISE account; the drawing (stroke) format isn't documented publicly. Plan sent: he checks his account
  has an API key (Settings > Developer Options), runs a small script on his Mac that saves one review's notes to
  a JSON file (his key never in chat), then I build the import. Waiting for his answers.

- 2026-11-21: Gus tried 0.2.0: "it works", curves and notes work. Problems: notes "not sticking to the frame,
  going for the whole duration"; the eraser didn't work well; curves need Enter to stop. 0.2.1 (fixes to what he
  tested, done straight away given "I don't feel we are going forward"): the unsaved drawing shows only on its
  frame, hold defaults to 1 frame (like SyncSketch), eraser drags (the whole path) and also erases saved notes'
  strokes on that frame, Enter ends a curve / saves, Esc drops the curve / drawing, double-click ends a curve.
  "RESTART MAYA" was a false alarm: since 0.1.2 the plugin is a shell, any shell >= 0.1.2 is fine (installer and
  self test say so now); the plugin's code is dropped from memory by file, not name. Asked: was it the unsaved
  drawing or a saved note that showed on every frame?

- 2026-11-21: Gus: "I prefer to go ahead and have a real try it out tool first. If we go step by step I don't
  feel we are going forward" -> for Review Notes, skip the separate try-it (rule 12) and ship a working tool;
  bigger steps. Built 0.2.0: draw on the view with a Maya drawing tool (draggerContext: Alt still moves the camera;
  the mouse read from the view's widget in its own pixels), Pen / Curve (Illustrator-style) / Arrow / Circle /
  Eraser, colours, size; the drawing shows live (the node draws it); the Review window: write, type, hold, Save
  note, Clear, the notes list (Go to, Status, Delete, filters, Nearby, Only open); 3 hotkey commands. Chose a Maya
  tool over a see-through Qt layer (on the Mac it can show as a black box). Tests: 30 without Maya + the window
  built with real Qt off-screen (picture design/review_notes/window_0.2.0.png). Not run in Maya yet.

- 2026-11-21: Review Notes 0.1.4 self test ALL OK after a restart (plugin 0.1.4, save callbacks, a real save
  has no node and no 'requires'). Step 1 done. Not answered yet: test.ma reopened clean? (he made test2.ma).
  Next: step 2 plan sent (try-it first, rule 12), waiting for OK.

- 2026-11-21: 0.1.3 installed (not restarted yet). His log answered "why won't the plugin update": the installer
  DID unload it (undo cleared, no error) but Maya loaded the old code again from Python's memory (module
  reviewNotesNode still in sys.modules) -> still 0.1.1. 0.1.4: the installer / load_plugin drop that module
  first. The real-save check was skipped (test.ma was open, not an empty scene). His log also had Gus_Rigtool
  5.7.8.1 'Test this release' output (1 FAIL: Animtool shelf buttons; QLabel deleted errors) - not Review
  Notes, belongs to the other Rigtool session; told him, not touched here.

- 2026-11-21: Gus "the plan is ok, build 0.1.3". Built: REVIEW_NOTES taken out before every save / export and put
  back after with its settings (as Animtool arcs); making / removing it never goes in the undo queue (likely why
  the plugin wouldn't unload); the installer says RESTART MAYA when the plugin running isn't the tool's version;
  self test: plugin version must match, save callbacks on, a real save with the node there. 23 tests pass;
  waiting for his install (restart once: 0.1.1's plugin is still the one running) + self test.

- 2026-11-21: 0.1.2 self test: 1 FAIL - a real save STILL writes 'requires reviewNotesNode' even with
  writeRequires False (so that flag doesn't stop it while the node exists). Also "plugin loads - version 0.1.1":
  the installer didn't manage to unload the old plugin (lines not pasted yet). Gus didn't know about question 2
  (re-save test.ma) - moot, the line comes back on every save. Plan sent, waiting for OK: take REVIEW_NOTES out
  before every save and put it back after (like Animtool arcs since 5.6.40), self test checks; find why the
  plugin didn't unload.

- 2026-11-21: After a Maya restart 0.1.1 DRAWS (Gus's screenshot: arc, arrow, label sized right). Gus: "yes to
  option 1 and 2" -> 0.1.2: the plugin is a thin shell (drawing in reviewNotes/nodedraw.py, looked up on every
  refresh, so updates work without a restart) and the installer clears undo to unload the plugin. Found from his
  log: test.ma got `requires "reviewNotesNode.py"` on a normal save (the self test had only exported), so opening
  it errors - 0.1.2 tells Maya not to write it, and the self test does a real save. test.ma keeps that line
  until he opens and saves it again with 0.1.2 (rule 9: I don't edit his .ma).

- 2026-11-21: Found why 0.1.0 drew nothing (Gus's diagnostic paste: "maya.api.OpenMaya has no attribute
  'MFileIO'"): the plugin asked the NEW API for the open scene's file; MFileIO is only in the old API
  (maya.OpenMaya). Every refresh failed before drawing. The tests missed it because their stand-in for Maya
  wrongly had MFileIO - removed, and a test now checks it isn't there. 0.1.1 sent (old API, cmds as a fallback).

- 2026-11-21: Review Notes 0.1.0 self test: all ok (plugin, one node, Show menu entry, node NOT saved and no
  'requires' line, review file round trip, camera). BUT the sample note did NOT show in persp1 (frames 0-5) -
  the try-it's notes did. Cause unknown: sent a diagnostic paste (same steps as the drawing, printed) + Show Gate
  on; waiting for its lines. Facts added to MAYA_FACTS.md.

- 2026-11-21: Review Notes 0.1.0 in Gus's Maya: installed, Review button works, "save the scene first" message
  shown on an unsaved scene, rn.sample() wrote test.review.json next to test.ma (n_0001 on persp1, frames 0-5).
  The self test didn't run: my message had a full stop after the command and he pasted it (syntax error) - the
  commands in messages go in code blocks from now on. Waiting: self test lines + screenshot of the note.
  Idea for later (not done, rule 1): rn.sample() prints the whole note as a Result line - could return nothing.

- 2026-11-21: Gus: try-it all good ("everything showed here as well": top camera, onion skin, playblast, label);
  "the plan is ok, go ahead and build step 1"; push of the review-notes-tool branch OK ("3 - yes").
  Step 1 built (Review Notes 0.1.0, scripts/review_notes/): installer + Review shelf button, the REVIEW_NOTES
  node (Attribute Editor settings, Show menu > Review notes), the review file (store.py), rn.sample() to add a
  test note, selftest.py. 19 tests outside Maya pass; nothing of step 1 has run in Maya yet. Waiting: his
  install + self test lines + a screenshot after rn.sample().

- 2026-11-21: Review Notes try-it RESULT (Gus's screenshot, persp, Maya 2024 Mac): the drawing works - arc made
  with the curve tool, arrow, label, the next note faint orange. The gate maths sits exactly on Maya's gate
  (overscan 1.0 and 1.3; facts added to MAYA_FACTS.md). Problem: the label box was cut short on his Retina screen
  (sizes are in screen pixels, 2 per point) - fixed in the try-it (scaled by the pixel ratio). He said he couldn't
  find the things to check in Maya - answered with menu paths. Still to see: the top camera, onion skin ON,
  playblast, the fixed label.

- 2026-11-21: NEW standalone tool asked by Gus: **Review Notes** (like SyncSketch, inside Maya): draw + write notes
  on a camera and frames, see them later in Maya / in playblasts, status open / in progress / done. A separate
  tool next to the onion skin (his choice: "I want it to be a separate tool"), branch `review-notes-tool`, folder
  `scripts/review_notes/` (not inside Animtool). He liked the mock-up (artifact "Maya Review Notes") and asked for
  a **bezier pen like Illustrator** (click = corner, click-drag = smooth, drag points / handles after, Alt breaks
  a handle) - added to the mock-up and the file format (anchors [point, in, out]).
  Agreed from the senior-animator review: one node draws all notes (not one per note); keep a small picture of
  the frame with each note (retimes); SyncSketch import before our own playblast player; notes pinned to a
  control in 3D = later. File: `<shot>.review.json` next to the scene, `_v###` dropped so notes follow versions,
  reload-before-save for teams.
  Rule 12: try-it sent first - `design/review_notes/tryit_review_draw.py` (a test plugin: 3 notes + a green box
  on where it thinks the resolution gate is) and `expected_*.png` (what it should look like, from the same
  drawing code). Waiting: his screenshots + Script Editor lines, and OK on the step 1 plan.

- 2026-11-21: Gus "yes to all": 576 + all_pages outputs accepted, 5.7.6 pushed to main, Toolbox preview next (the
  last area; then the old window can go).

- 2026-11-20: 5.7.6 results all clean: Real Maya 112 ok; Test this release 42 ok, 0 FAIL (the new window 25 ok
  incl. Check & publish + Publish gone from Build; his shelf is back - he remade it). Waiting: OK on the 576 /
  all_pages outputs, the 5.7.6 push, and Toolbox preview next.

- 2026-11-20: Check & publish plan: "1 move (Publish to Check & publish) 2 yes". 5.7.6 built and sent; waiting for
  his results and OK to push. Next after it: Toolbox (preview first), then the old window can go.

- 2026-11-20: Check & publish preview sent (design/screens576: Checker 69 controls, Organize 37 - both short, fine
  in the new look). Found: Publish (Publish / Unpublish / Deliver) lives in Build > Rig builder, not in Check &
  publish. Asked: move it there (my pick) or leave it; plan 5.7.6 waiting for his OK.

- 2026-11-20: Gus "yes to all": 570/571/575 outputs accepted, 5.7.5 pushed to main, Check & publish preview next.

- 2026-11-20: 5.7.5 results: Real Maya 112 ok; Test this release 39 ok - the new window 23 ok incl. Connect (nothing
  cut off on 6 pages, two rows, Connections tab fix); 1 FAIL again = his Gus_Animtool shelf is still empty (Make the
  shelf not run yet). Waiting: OK on 570/571/575 outputs and the 5.7.5 push.

- 2026-11-20: Connect plan: "1 yes 2 its ok (Nodes: See & trace / Make a driver / Find & clean) 3 keep plain"
  (Constraints and Driven keys without steps). 5.7.5 built and sent; waiting for his results and OK to push.

- 2026-11-20: Gus: "ok lets go for the connect". Preview sent (design/screens575: now_* = today's 4 tools in the
  new look, idea_* = Nodes in 3 pages). Found: the Connections tool's key 'connect' = the area's key (its tab goes
  to the area). 5.7.5 plan sent; waiting for his OK.

- 2026-11-20: Gus "yes to all": test outputs 570/571/573/574 accepted; 5.7.3.1 + 5.7.4 pushed to main; "two
  curves" as built is what he wanted (ends meet = one loop, side by side = loft between). Next: Connect, Check,
  Toolbox areas in the new look (preview first), then 5.8 Animtool.

- 2026-11-20: 5.7.4 results: Real Maya 112 ok - case p (face from two curves) 8 ok, curve facts as expected (loft
  uses world positions, reverseCurve flips the start, periodic curve form 2). Test this release: 36 ok, 1 FAIL -
  the Gus_Animtool shelf is there but has none of its buttons (no Animtool code changed since 5.7.2.1, which
  passed): his shelf was emptied - fix: Animtool window > Settings > Make the shelf. Still waiting: his OK on the
  test outputs (570/571/573/574), the push (5.7.3.1 + 5.7.4), and whether "two curves" works the way he wants.

- 2026-11-20: 5.7.3.1 results clean (Real 104 ok; Test this release 35 ok - module check skipped, no guides in his
  test scene). Gus: "still not working" = 1a, Face and Ribbon aren't the approved steps -> 5.7.4 built (the
  approved plan). "Two curves" read both ways: ends meet (lid/lip lines) = one loop, side by side = loft between.
  He is "just testing new scenes" (answer to the guides question). 5.7.3.1 and 5.7.4 not pushed yet - waiting.

- 2026-11-20: 5.7.3 results: Real Maya 104 ok; Test this release 2 FAIL (Build cut off at 326 px - closed cards'
  peek never shrank; the module check took "(no modules yet)" for a module). Fixed in 5.7.3.1. Gus: "the face and
  ribbon build aren't with the updates I approved" - they are 5.7.4 (the split he OKed); my 5.7.3 message didn't
  say so. LESSON: always say in the release message what is NOT in it yet. Next: 5.7.4 Face/Ribbon steps.

- 2026-11-20: Gus: "yes to all" - split into 5.7.3 (Build area in the new look: colour pickers, no cut
  drop-downs, inner sections, live refill of the module settings, two rows of tabs for Build and Skin) and 5.7.4
  (Face and Ribbon as steps + two curves, plus a real-Maya case for lofting from two curves). 5.7.3 built and sent
  for his tests; waiting for his results and his OK to push (push 5.7.3 to main only after he says so).

- 2026-11-20: Face + Ribbon previews approved. Two curves is the default (remembered) for eyelids, strips - and
  (read as yes) mouth and brows too; edges stay as the other way. Full 5.7.3 plan to send before building.

- 2026-11-20: Face: Gus prefers the step page but clearer - eyelids and facial strips are best made from TWO
  CURVES (select two curves, the ribbon lofted between). Face kit today only takes edges (it makes the two sides
  itself); two curves = a new way in, the edge way stays. Ribbon as steps too (Gus: yes). Previews sent
  (face_ribbon_mock.py: eyelids/strips "Make it from: Two curves | edges", selection check; Ribbon Surface ->
  Joints -> Controls -> Create with a progress strip). Waiting for his OK.

- 2026-11-20: 5.7.3 plan OK (colour pickers, no cut drop-downs, inner sections, parts that rebuild, Build area two
  rows of tabs). Skin gets the two rows too, later. Gus on Face: "just a button is not intuitive... isn't it
  repetitive?" - splitting Face into 7 one-button pages is bad. Proposed instead (mock face_mock.py): ONE page
  'Build the face' = face map (made / ready / on / not yet) + steps that say what to select and check the
  selection + options with their part; then 'Ribbons & groups' and 'Squash & expressions'. Waiting for his OK.

- 2026-11-20: 5.7.2 + 5.7.2.1 pushed to main (Gus: "yes to all"); he wants the 5.7.3 Build preview + plan.

- 2026-11-20: 5.7.2's Test this release crashed in my check (Settings looked for in the Toolbox) - fix release
  5.7.2.1 approved; Build in the new look stays 5.7.3.

- 2026-11-20: 5.7.2 test outputs accepted; next is 5.7.3 Build in the new look (Build, Face, Ribbon, Joints) -
  preview first (Gus: "yes").

- 2026-11-20: 5.7.2 plan approved (Settings ⚙ button; favourites profiles + editing on the row and the bar; Skin
  in the new look, 7 sub-pages Bind / Copy & mirror / Save / load / Clean / Weights / Cloth & jiggle / Fixes -
  Fixes stays a Skin sub-page "as in the picture"). 5.7.1 pushed to main (Gus: "push it").

- 2026-11-20: Animtool pitch answers: style A Studio is the default (B / C not asked for - keep as options to
  show again later); bar variants 1 row with labels, 2 compact row, 3 grid AND 4 the pie on a hotkey - in the pie
  each tool's NAME UNDER its icon; the bar needs a profile with ALL the tools too. Release order 5.8.0-5.8.5 OK.
  He wants MORE design options and tool improvements before it's built - maybe in a separate chat just for
  design. Now: finish the 5.7 releases (5.7.2 Settings button + favourites editing + Skin, then the rest).

- 2026-11-20: Gus: "We are not building new tools, just improving what we have." Wants the Animtool presented as
  a studio pitch (clearer, immersive, ideas from other departments and tools, honest about flaws, style variants).

- 2026-11-20: The Animtool redesign (5.8) - sidebar order Pick & see, Pose, Keys & timing, Spaces & props,
  Limbs; Settings its own button. Bar profiles save the bar's shape (row / column / grid, size) per profile.
  The Rigtool favourites use the same editing and profiles as the Animtool bar (one design for both).
- 2026-11-20: 5.7.2 = Settings its own button (⚙ at the bottom of the sidebar) + favourites editing
  (✎ edit, drag to reorder, × remove, + grouped ticks, profiles) + the Skin area in the new look.
  Then Build, Connect, Check, Toolbox (then the old window can go); then the Animtool (5.8).
- 2026-11-20: 5.7.1 approved for main after his tests passed (Real Maya 104 ok, Test this release 29 ok).
  The push was blocked by the session's safety check twice; Gus to say "push 5.7.1" explicitly.
- 2026-11-20: Favourites: a row at the top of the window (the old My tools list) AND a floating bar.
- 2026-11-20: Pop out kept (one panel per page, several side by side). 5.7.0 kept off main (double window).
- 2026-11-20: The new window is the default from 5.7.0; the old one stays under Toolbox > Settings > Window
  until every area is redone.
- 2026-11-20: Look "version 2": a colour per area (Build orange, Skin pink, Controls green, Connect purple,
  Check yellow, Toolbox blue), X/Y/Z red/green/blue, selection chips, shapes as pictures, drawings for hard
  fields, closed cards say what's inside. Big pages split into sub-pages, the last one remembered. No
  duplicates: everything in one place (Publish only in Check & publish, Side colours only in Settings).
- 2026-11-20: 5.7 scope ideas: 1 settings under the module tile, 2 the next step (lamp), 3 pin a card - YES;
  4 Maya's Skin Tools link - later (Maya 2024 doesn't have them); 5 one look everywhere - 5.8.
- 2026-11-19/20: Shape ideas: fit to the body (hugs), lie on the skin, shape from edges (5.6.48); one click on
  a shape makes the controls; Make on a selected control adds a new control (any rig, referenced / locked).

## Open plans / waiting on Gus

- The Animtool design, more options (Gus wants more variants of the design and of the tools before building) -
  possibly in a separate design chat. Pitch slides and sources: design/mockups/ (pitch.py, anim_mock.py, v2*.py).
- Next: Toolbox preview (pictures first); then the old window can go; then 5.8.
- Next: 5.7.4 Face and Ribbon as steps + two curves (plan approved); then Connect, Check, Toolbox areas; then 5.8
  Animtool.
- Still unknown: 'Cannot move keys' in his shot (the tool names refused curves; Copy the last problem).

## Ideas parked (not now)

- Edit FK arc (bake to IK, edit, bake back) - "not a priority".
- Pictures in every page (lock grid, 'in front' drawing) - page by page as areas are redone.
