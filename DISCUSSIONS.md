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

- 2026-11-21: Gus: 5.7.7 plan (C6 look behind Settings > Window > Look, default Today; + Toolbox) - YES. Step pages:
  ALL steps open (not only the current one). Asked "is there anything apart from the visual we needed to do?" -
  listed the open non-visual items (below in Open plans).

- 2026-11-21: Gus: "C5 is the best, the right direction; I like the way the Face is today - keep good parts like
  these; I want things clearer visually"; the fine borders / quick-button edge / status line STAY; yes to a build
  plan; "give more examples of C5 keeping what is good visually". Sent C6 (design/screens577/c6_*): C5 + today's
  good parts - the face map, the Ribbon steps strip, each step's state as a coloured tag on its title line
  (✓ Made / ● Ready / To do) with its message as one line under it (instead of a big light box), the badge's
  tick / dot, and the choices that say how a step works (Make it from, Mode, Style) never folded. Pages: Face,
  Ribbon, Skin > Bind, Behaviour, Driven keys, Checker, Groups. Plus a step-page idea: only the step you're on is
  open (c6_face_steps, c6_ribbon_make_steps), compare_face_c6 (Today | C5 | C6). Build plan 5.7.7 sent; waiting.

- 2026-11-21: Gus on C4: "still not liking it - it seems better but loses the look we were working on; bring back
  more of what we discussed and the images, with what is now + the updates we were planning + the new one; make a
  new version first". Sent C5 (design/screens577/c5_*): today's 5.7 look as the base (cards with a colour edge,
  number badges, filled main button with a darker bottom edge, tinted area header, tab with a colour top, sub-page
  pills) + our plan (C3b: names in a short left column, one left edge, joined choices, Options folded with what's
  set, presets folded, step lights folded) + a few Gemini bits (fine borders, quick buttons with a thin colour
  edge, status line at the bottom). Comparison sheets: compare_groups.png, compare_face.png (Today | C3b | C4 |
  C5). Waiting for his opinion.

- 2026-11-21: Gus: (1) yes, one look for both tools - but first show how the Rigtool looks with the Gemini bits;
  (2) Rigtool first; the new look applied to the Rigtool's tools for now so he can see it in Maya and compare;
  (3) the three files are all for now; (4) the Rigtool can take the HTML's style, but he wants to look at
  everything first and see how I interpret it. Sent C4 (design/screens577/c4_*): C3b's layout in the Gemini style
  (slate #16191e/#22262d/#242933/#343c4a, #454f60 borders, sections as drawers with a 3px area-colour rail and a
  12%-tinted header 'N NAME', tabs as pills, buttons with a coloured bottom edge, a status line at the bottom,
  step lights folded). Plan 5.7.7 = the new look as a switch (Settings > Window > Look) + Toolbox; waiting.

- 2026-11-21: Gus picked C3b (names on the left, short, left-aligned) for the Rigtool look; "yes" the joined choice
  buttons read better than round radio buttons; FOLD the step lights too (the number badge says ready / done).
  He then sent his 5.8 Animtool work made with Gemini (kept in design/references/): a style guide
  (gus_animtool_5_8_style_guide.md), a Maya test script with dummy actions (gus_animtool_5_8_ui_test_v3.py) and
  an HTML workspace (gus_animtool_5_8_workspace_v3_1_1.html + workspace_v3_1_1.png). Gus: "the html is how it
  should look more visually". Its 58 tools = today's 56 Animtool actions + 2 window openers (attach_window,
  arcs_panel). I asked: one palette for both tools? Rigtool look first (5.7.7) then 5.8? and the Maya facts the
  pie hotkey needs. Waiting.

- 2026-11-21: Gus on C2: "keep more of this idea, but some tools are not centred or pushed to the right; I want to see
  it pushed more to the new style, just to have a look". Sent C3a (new-style cards, each field's name ABOVE it -
  one left edge, full-width controls) and C3b (same cards, names on the LEFT in a short left-aligned column);
  both: joined choice buttons (the new window's), quick buttons as chips, 'Options (n)' as a small rounded button
  with the summary, the area colour on numbers / tab / main button. Pictures design/screens577/c3a_*, c3b_*
  (+ c3a_groups_open: Options opened). Waiting for his pick.

- 2026-11-21: Gus: "I liked C better, but it's still too much information at first look, and I want more of the
  colours and looks of the new version"; "I need them more organized - find the design references (rules, what
  makes a great UI/UX) and bring a based reference, understanding what the design means"; "yes, I need to see
  more (pages)". Did: design/UI_PRINCIPLES.md (10 rules with sources: progressive disclosure, Hick, Fitts,
  Gestalt proximity, hierarchy, recognition over recall, Nielsen heuristics, Blender HIG, Material dark theme,
  WCAG contrast, Apple HIG) + version C2 (Mix C + the new window's colours, each area's colour on numbers / tab /
  main button; the job first and the rarely changed choices folded in one 'Options >' line that says what's set;
  presets folded into one button; closed sections one line; a step with a light shows no second description).
  Pictures design/screens577/c2_*: Groups, Mirror, Pivots > Move, Face > Build the face, Skin > Bind, Controls >
  Behaviour. Waiting for his opinion / references.

- 2026-11-21: Gus: "1 (classic) is still easier to read, but the design of 2 is good - give me more options combining
  the two"; "we can think of the whole window, but I need to see how it would look overall in more versions - I'll
  send more references"; he sent NO picture ("take a look at this" = his words before - my misread). Sent 3 mixes
  (design/screens577 window_groups_mix*, style_*_mix*): all keep Version 1's controls (label column, round radio
  buttons, square check boxes, solid grey buttons, blue main button) + Version 2's one-line description:
  A = in cards; B = Maya-like section bars with a colour edge + number; C = no boxes, a thin line between
  sections. Waiting for his pick and his references before building anything.

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
- 2026-11-21: Gus asked to arrange each tab's sections himself ("like in the edit shape I want to put the size and
  turn in front of the swap shape ... organize the way I want each tab"); plan approved: "this is exactly what I
  want" - drag a title, right-click Move up / down / to top / Reset order, remembered per tab and page, both looks.
- 2026-11-21: 5.7.7 results: Real Maya 112 ok; Test this release 47 ok, 1 FAIL (new look cut off at 326 px:
  Settings, Make a ribbon's drop-down, Rename's tick box). Gus: "the result seems great overall ... feeling better";
  wants: text never cut ("they should always stay"), a sidebar button to hide the first column, better spacing in
  titles (Toolbox icon touches its name), and "apply to the rest after you see the results". His Groups shot:
  "Match _zero" (& eaten), "Above the objec" (choice button squeezed), something peeking at the right edge.
  5.7.8 plan sent with questions: push 5.7.7 now?; "the rest" = default new look / Settings / Animtool?; hide the
  sidebar fully or keep icons?; what's at the right edge? - waiting. 5.7.7 not pushed yet.
- 2026-11-21: Gus: 1 wait for the rest of testing (no push); 5.8 is only for the Animtool; "the rest" = the
  Toolbox improvements on every tab ("the other tabs aren't moving like in Controls or the Toolbox"); hidden
  sidebar = thin strip; the right-edge question was the cut text. Splitting one-section pages: "ok"; Settings in
  the new look: "yes". He couldn't move "Move the shape" above "Swap the shape" and asked for an edit button
  for Move up / down. 5.7.8 plan sent: Arrange button per page, Swap section keeps its own items, order on
  every tab, Settings new look, text never cut, sidebar strip, title spacing - waiting for his OK.
- 2026-11-21: Gus: "1 yes / 2 yes" (build 5.7.8; Arrange closes the sections while arranging). Section splits
  (pictures in design/screens578): "ok, you can put it together". 5.7.8 built - waiting for his Maya tests and
  OK to push (5.7.7 and 5.7.8 both unpushed; he said wait for the rest of testing).
- 2026-11-21: 5.7.8 results: Real Maya 112 ok; Test this release 63 ok, 1 FAIL (5.7.7's check compared Reset
  with his own saved Edit shape order - the checks wipe his order). Gus: "it is taking too long in test" (255 s
  vs 66 s): the new check presses Reset order on ~80 pages and Reset redraws the page. 5.7.8.1 plan sent:
  instant Reset (remember the first order), checks keep his order, a lighter check - waiting for his OK.
- 2026-11-21: Gus: "1 yes / 2 yes / 3 yes" - 5.7.8.1 approved; dragging a section by its title works in his Maya;
  Arrange is how he wanted it. 5.7.8.1 built - waiting for his tests and OK to push (5.7.7, 5.7.8, 5.7.8.1).
- 2026-11-21: 5.7.8.1 results: Real Maya 112 ok; Test this release 59 ok, 1 FAIL (the Gus_Animtool shelf: every
  button missing - "Make the shelf" fixes it; nothing in 5.7.x touched the shelf). "the test was faster" (96 s,
  was 255 s). Gus: "you can go ahead and push it" - 5.7.7, 5.7.8, 5.7.8.1 pushed, main = 5.7.8.1.
- 2026-11-21: Gus: "I think we can start to take out the 5.7 version, the only thing to maintain is the old look
  before that, the one using maya" - next: plan to remove the new window's "Today's look (5.7)" so the new window
  has one look (C6), and keep the old Maya window (5.6) as the way back. Plan to be shown first.
- 2026-11-21: Gus: "1 yes, maintain like we have now, but call it legacy look; 2 removing it" (today's look out;
  the 5.6 window = "Legacy look"). Shelf: he didn't remove it ("strange") - the shelf tab is probably empty to a
  script until opened (Maya fact to ask). Shelf: "everything" (every tool), icons OK, but the bar must follow
  profiles + favourites with right-click to a tool's settings; Home redone in 5.7.9; "bring me the list" (lighter
  tools); shelf keeps Build and Publish (Build rig out). He asked if I understood his Gemini bar (profiles pills,
  Row/2R/Col/Grid, size slider + Ctrl+wheel, labels, right-click settings strip, auto-shrink, NoFocus) - answered;
  updated 5.7.9 plan + lighter list sent, waiting for his OK.
- 2026-11-21: Gus: "1 yes (plan); 2 rigtool with mockup layout (Rigtool colours, his mock-up's layout); 4 options
  fold (right-click strip = a tool's main options)". Lighter items not picked: going with my recommendation (1, 2, 4;
  the Checker rewrite in its own release). Bar + Home built and shown as pictures (design/screens579). Gus on the
  column: "too much space on the right, it should be even and proportional" - fixed (one width, tiles centred).
- 2026-11-21: Gus: column "too wide" -> 64 px (short controls: initials, R 2 C G, Aa, pencil); Home "yes"; names
  under tiles on two lines "yes"; beside a column: "B" (names above the boxes, narrow); "be sure that the row
  stays tight like other designs and don't let a lot of negative space" -> a row keeps only grip, profile, ▾, =
  when its controls are wider than its tiles; = opens the bar's settings under it.
- 2026-11-21: Gus: tight row "yes"; Publish in its own file "we can do it in the next" (with the Checker rewrite).
  5.7.9 built - waiting for his Maya tests and OK to push.
- 2026-11-22: 5.7.9 results: Real Maya 112 ok; Test this release 57 ok, 0 FAIL (102 s). Maya fact: shelf tabs
  Gus_Rigtool 43/43, Gus_Animtool 57/57 - full before opening (the lazy-tab guess was wrong; 5.7.8.1's shelf FAIL
  still unknown). Gus: the bar's options strip stacks ("doesn't close when I open another or when I right-click
  again") - my bug (old title / size rows not cleared); the row "doesn't show the settings like you showed me";
  the shelf "looks the same, do I have to restart Maya?". 5.7.9.1 plan sent - waiting.
- 2026-11-22: Gus: "1 yes / 2 always show the settings on top" (a row always shows Row / 2R / Col / Grid, names,
  size - short forms when short; never hidden). 5.7.9.1 built - waiting for his tests and OK to push.
- 2026-11-22: 5.7.9.1 results: Real Maya 112 ok; Test this release 57 ok, 0 FAIL (101 s). Gus: "yes to all" -
  the strip opens one tool at a time and closes on a second right-click; the shelf shows the new icons; push OK.
  5.7.9 and 5.7.9.1 pushed, main = 5.7.9.1.
- 2026-11-22: 5.7.10 plan OK ("1 yes"); Checker checks: "keep them as they are unless you think there is something
  good to add that will help you find more problems". Publish moved to tools/publish_tab.py (done). Finding: the
  Checker is ALREADY one table (CHECKS) - my lighter list was wrong; proposed instead: its checks in their own file
  (Publish, Check this scene, self-tests stop loading the page), Face's step lights read the selection once, and
  4 candidate checks for Gus to pick - waiting.
- 2026-11-22: Gus: "1 yes / 2 all of them" (the 4 new checks). 5.7.10 built: checks in core/rig_checks.py (16 parts
  load only them), Face reads once, 4 new checks - waiting for his tests and OK to push.
- Next (5.7.10): Publish in its own file; the Checker as one table; read Mirror / Ribbon / Face for a second
  "lighter" list. Then the Animtool (5.8) plan.
- After the Rigtool is "completely working and polished": plan the Animtool (5.8) from what we discussed + his
  Gemini UI/UX ideas, combined. Then 5.8 Animtool from Gus's
  references (design/references) - check its right-click options against the real tools (no new tools) and the
  pie hotkey (a Maya fact first).
- Not checked in Maya yet: Build > Settings of the picked module (needs a scene with guides); Check & publish rows
  (Run checks / Find repairs / Analyze the Outliner).
- Hare open items (PROJECT_CONTEXT section 3): pupils / tongue Keep the pose; L_IK_Elbow / Wrist 'Not a control';
  the model file clean-up; low-priority joint flips; the before-delivering checklist.
- Still unknown: 'Cannot move keys' in his shot (the tool names refused curves; Copy the last problem).

## Ideas parked (not now)

- Edit FK arc (bake to IK, edit, bake back) - "not a priority".
- Pictures in every page (lock grid, 'in front' drawing) - page by page as areas are redone.
