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

- 2026-11-21: Gus on the Toolbox preview: plan OK, but "I really didn't like the way the tools look - I want it
  easier to see and retaining at least a bit of the older version so I can understand what's going on"; asked for
  2 new versions (his reference picture didn't arrive - asked him to resend). Q2 (split Pivots): "I let you
  decide". Q3: KEEP the old window reachable (Settings > Window) - "great to always have an option to go back".
  Sent design/screens577/style_*: Version 1 "Classic, clearer" (Maya section bars, label column, round radio
  buttons, blue main button) and Version 2 "New, easier to read" (cards + one-line 'what it does', label column,
  choices with a dot, quieter buttons). Script: design/mockups/toolbox_styles.py (draws a tool's real page).
  Waiting: which version, and for the whole window or the Toolbox only.

- 2026-11-21: Toolbox preview sent (design/screens577: Select 57, Groups 30, Mirror 124, Rename 25, Pivots 44
  controls). Found: Mirror stops while drawn (the recorder doesn't answer a 3-number box), its light shows an error;
  Groups 7 px too wide. Plan 5.7.7 + question: what happens to the old window after this (keep it in Settings /
  remove it) - waiting.

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
