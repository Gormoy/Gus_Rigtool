# Gus_Rigtool - project context (backup for a new chat)

Written on 2026-11-09 at the end of a long working chat; updated on 2026-11-13 after the first Claude Code
session (5.6.28 - 5.6.47). The code is in the GitHub repo `Gormoy/gus_rigtool` (one branch per release:
`import-5.6.27`, `release-5.6.28` ... `release-5.6.47`; `main` holds the latest release since 5.6.45). It covers what the
project is, how we work, what was built, the Hare rig's state, and what's open.

---

## 1. The project

- **Gus_Rigtool** is a rigging toolkit for Maya 2024+ (Python). It's built by Gus with Claude, release by release.
  It went from **1.0.0 to 5.6.47, about 167 releases**, all listed in `gus_rigtool/CHANGELOG.txt`.
- **Gus Animtool** (`gus_rigtool/anim/gus_animtool/`) is the animators' side:
  - the picker;
  - the pose library;
  - IK/FK and space switching without jumps;
  - mirror, flip and reset;
  - tween, keys and timing tools, overlap, jiggle bake, temporary spaces, attach props;
  - playblast and crash backup.

  Deliver ships it to the animators with its own installer.
- **Install:** unzip `Gus_Rigtool_install.zip`, then drag `drag_to_maya.mel` into Maya's viewport.
- **Open:** `import gus_rigtool.main as gr; gr.show()`
- The main window follows a rigging workflow: **Home > Build > Skin > Controls > Connect > Finish**, plus a
  Toolbox. The key finishing tools are:
  - **Check this scene** (`scene_check.py`): a report of warnings, notes and info;
  - **Repair** (`core/repair.py`): one-click fixes;
  - **Publish** (`builder/publish.py`): saves the default pose, locks, and learns the mirror table;
  - **Deliver** (`builder/deliver.py`): a folder with the rig, the animator tools, poses, `rig_check.txt` and a
    README.

## 2. How Gus works (keep doing this)

1. Show a **numbered plan before any code change**, and wait for his OK.
2. **Number questions.**
3. Put small choices under **"Decisions I made"** in the CHANGELOG entry.
4. Run the **full test suite once per release**.
5. Every release message ends with three flush-left code blocks: Reset, Version, Bring. The exact text is in
   `CLAUDE.md`.
6. Also tell him to **restart Maya or reset gus_animtool**, because the picker is in Animtool.
7. He likes **big releases**. He often says "everything" or "I'll let you work through the night".
8. Plain words. He judges results in Maya: what moves, what looks wrong.
9. He often sends diagnostic output back. When something is unclear in Maya, write a **small diagnostic script**
   he can run that changes nothing (undo off, everything put back), and ask him to paste the result. Keep them in
   `scripts/diagnostics/` (repo only, not in the zip).
10. **Two lanes for new work** (agreed in 5.6.28): what he needs to finish the Hare goes in when needed, each with an
    impact note first (files, risk, tests, what to check in Maya); "nice to have" waits for the clean-up stages of
    the roadmap. No feature without tests; a real-Maya check for anything that moves the rig.
11. It's a **personal tool**, used in **Maya 2024 until the short is finished**. He works mainly on **Windows**,
    sometimes on his Mac. After a release he usually says to push the branch (only the branch: no merge, no PR).

## 3. The Hare rig (current state)

- **Scene:** `Hare_Rigging_v199_NewSkinWeigh.ma` in `.../TTTBMW_Hare_Rigging/scenes/` (on Windows `H:/Assignments/The
  Tree That Bloomed in Winter/`, on the Mac `/Volumes/T7/...`). Maya 2024.
- **Model:** a reference to `Geo_Hare_08_MovedTail.mb`, namespace **`Geo_Hare_07`**.
- **Scale of the rig:** 995 joints, 367 controls, 24 meshes, 55 skins, 850 constraints, 17 ribbon builds,
  14 guide modules.
- **Top controls:** Global_ctrl (`globalScale`) > World_ctrl > COG_ctrl.
- **Settings controls:**

  | Control | What it holds |
  |---|---|
  | `L_/R_ankle_settings_ctrl` | ikfk, stretch, soft_ik, Pants_Tweaks, Bends |
  | `L_/R_wrist_settings_ctrl` | ikfk, stretch, soft_ik, spread, finger curls, Sleeves, Bend |
  | `Face_settings_ctrl` | visibility of the face groups; tongue ikfk / curl / wave |
  | `Cape_settings_ctrl`, `L_/R_Cape01`, `L_/R_Cape02_settings_ctrl` | ikfk, curl, wave, jiggle, tweaks; Upper_Collar / Bottom_Collar |
  | `L_/R_Ear_settings_ctrl` | ikfk, tweaks |
  | `Head_squash_ctrl` | squash, bulge, bend |
  | `Visibility_ctrl` | Body_Ctrls, Secondary_Ctrls, Joints, Geometry, Geo_Display, Head_Squash |

- **Spaces:**

  | Control | Spaces |
  |---|---|
  | ankle IK | World / COG / Waist |
  | knee PV | Foot / World / COG |
  | humerus FK | Chest / COG / World / clavicle_FK |
  | wrist IK | COG / Chest / root |
  | elbow PV | Chest / World / Hand |

- **Picker:** saved **in the rig** (`gusPicker` attribute), with pages Body (86), Face (92), Hands (16),
  Tweaks (94) and Clothes (109). Six old controls are taken out on purpose: Head_ctrl, Neck_ctrl,
  L/R_IK_Elbow_ctrl, L/R_IK_Wrist_ctrl.
- **Ribbons:**
  - Collar and Cape_Ribbon go around the hood and **aren't symmetric** (the hood's base isn't).
  - Gus doesn't want them mirrored. Mark them with **Ribbon tab > Not symmetric**.
  - The cape controls 04, 07, 10, 19, 22 and 25 have `_sdk` groups that are parent-constrained to the clavicle
    and humerus.

### Last Check this scene (5.6.31, Windows): what's still open

1. **Collar and Cape_Ribbon**: fixed in 5.6.31's report.
2. **L / R_Pupil_ctrl** (aim constraint on the control) and **Tongue_end_IK_ctrl**: 5.6.31's **Behaviour > Rest here >
   Keep the pose, zero** moves aim constraints too - run it on them (select the control curves: Gus selected the
   eye meshes, which zeroes nothing; 5.6.32 says so).
3. **L_IK_Elbow_ctrl / L_IK_Wrist_ctrl**: the left side's old controls, still hidden by hand - **Behaviour > Not a
   control** (the right side, Neck_ctrl and Head_ctrl are marked).
4. **Non-deformer history** on Bandage_L / R, Bandages_Arms and both eyes. **Don't delete the eyes' history**: Gus
   tried and the left eye jumped to the other side (it's probably the mirror that made it). 5.6.31's report names
   the nodes; the Checker's fix now puts back any mesh that moves. The bandages' warning was false: the Clothes
   switch's nodes (5.6.32 leaves them out). The eyes' transformGeometry after the skin must stay.
   Head squash: Gus took it out; Remove stopped half-way on Publish's locks and left Head_squash_off,
   Head_squash_factor_md, L / R_Ear_ctrls_grp_squash_follow (the ears still follow the head) - 5.6.32's Remove
   cleans them. "Step must be less than range" warnings on opening / some tabs: scripts/diagnostics/
   slider_range.py to find the attribute. Picker: Save after Clean up.
5. Model file clean-up in `Geo_Hare_08_MovedTail.mb`: duplicate names (Belt, Gums_UP, Hare_Body, Teeth_Up),
   21 `Eye_geo:` leftover namespaces, 20 unused Orig shapes.
6. Joint up-axis flips (14), Nose and R_Humerus twisted, sleeve joints not exact mirrors - low priority.
7. Before delivering: Auto Key off, playback "every frame" (the jiggles), save, Publish, Deliver.

### Done since 5.6.27 (confirmed in Maya)
- The **head squash was taken out** (to add again later - Make no longer needs component tags, 5.6.28).
- The **mirror table** and the **default pose** are on all 362 controls (Publish).
- **Clothes switch**: Visibility_ctrl.Clothes + Hood_Geo, Shirt_Geo, Pants_Geo, Bandages_Geo (Full / Hidden).
- The **Mouth** is symmetric within the skin-mirror tolerance; the pupil joints' scale is 1.
- pairBlend1 / 2 are reported as normal space blends.
- **Delta Mush**: displacement fed by Global_ctrl.globalScale keeps every mesh's form at x2 (checked with the
  diagnostic: "now" 0.000; unplugged up to 1.88). deltaMush1 (Shirt, Scale XYZ 2 2 4) and deltaMush2
  (Bandages_Arms, 1 0.001 3) have odd Scale XYZ on purpose (Gus fitted them that way).

### Speed (dragging COG, Maya 2024, Windows, 5.6.30)

| Measured | Result |
|---|---|
| Normal | 103-111 ms per step (about 9-10 fps) - this PC; the Mac's 45 ms (22 fps) isn't comparable |
| Clothes hidden (Visibility_ctrl.Clothes) | 60 ms (17 fps), 44 ms saved |
| Each piece hidden | Hood 18 ms, Pants 12, Shirt 9, Bandages 3 |
| Each skin off on its own | Hood 22 ms, Hare_Body 14, Pants 13, Shirt 10; the fixed per-skin cost is ~0 here |
| GPU override off | about the same (104 vs 108 ms) |

## 4. What was built (5.6.23 to 5.6.39)

- **5.6.23:**
  - a more professional picker UI;
  - the visibility switches leave the squash rider copies alone (`core/vis_switch.py` `fix_riders`).
- **5.6.24:**
  - picker text that scales, titles you control, mirror pairs;
  - the page model: normalize, fit to text;
  - rig switch and face slider pages, my sets, styles, shortcuts.
- **5.6.25:** the picker as an organizer, part 1:
  - one text placement for everything, Ctrl+drag to move text;
  - Nuke/Miro-style connectors;
  - layers, sticky notes, toolbar customisation;
  - a mesh silhouette background;
  - a mirror-pairs tolerance for centre controls.
- **5.6.26:** the picker, part 2:
  - limb buttons fixed (text no longer blocks clicks);
  - rename window, shape gallery, Maya colour palette, group by limb;
  - IK/FK fade, badges;
  - 8 handles plus rotate, snapping and equal gaps, Alt+drag duplicate;
  - copy/paste, folding frames, minimap, templates, preview (P);
  - saved versions, pages from another character, find everywhere, undo history;
  - Z / Shift+Z undo and redo, a floatable Item panel.
- **5.6.27:** safe fixes:
  - **Safe mode** (`core/safe.py`): every Repair fix is compared at rest, scaled x2, and on 3 frames of real
    animation. If any deformed vertex or control moved more than 0.001 cm, it's undone and the report lists what
    moved.
  - **Mirror table** (`anim.py`: `learn_rest`, `stored_rest`, `world_rest`): Publish saves each control's rest
    world matrix as `gusRestWorld`, so mirroring ignores how the arms are posed.
  - **Not symmetric** ribbon mark (`rrbNotSymmetric` on the ribbon's controls group): no mirror warnings, the
    mirror tools leave the ribbon alone, and Animtool gives its controls no twin.
  - *Make the right side mirror the left* refuses when an in-between group is held by a constraint.
  - **Speed** (`core/rigspeed.py`; not `core/speed.py`, which is the older tool-timing module):
    - drag timing in the checker;
    - chain breaks (hidden meshes between deformers);
    - missing component tags;
    - Delta Mush tied to the scale;
    - reasons a mesh stays on the CPU.
  - Check this scene: the picker read from the rig (`picker_saved`), and a **Ready for animators** section.
  - Repair: stray keys on pairBlends.
  - Tests: `tests/test_5627.py` passes 41/41. The **full suite was not re-run after the last edits** (the
    `speed.py` → `rigspeed.py` rename and small `safe.py` / `publish.py` changes). The affected tests were run and
    pass.
  - Accident to remember: a new `core/speed.py` overwrote the existing one. It was restored from the 5.6.26 zip,
    and the new code moved to `rigspeed.py`.

### Documents made in this chat (Claude Docs)
- **Hare Rig — Safe Fixes Plan (5.6.27):** https://claude.ai/artifact/2VSSF1vEi8oYebYQvcPK6a
- **Hare Rig — Animator README:** https://claude.ai/artifact/FSKMSGzponeNwGKHHGFXbB
  It lists the rig's controls and attributes, the picker, every Animtool tool, speed tips and rules.

### Diagnostic scripts made in this chat
- `hare_speed_check.py`: times COG/World dragging with each heavy part switched off.
- `hare_skin_cost.py`: times each skin on its own, GPU override on vs off, and inspects the pairBlends.

### 5.6.28 - 5.6.39 (Claude Code, 2026-11-10 to 13)
- **5.6.28** (the 5.6.27 review): Repair no longer empties component tag expressions; Make head squash works
  without tags; the mirror table keeps joints' translate and reads custom attributes at default; Make the right
  side mirror the left also refuses held offsets / pairBlends; safe mode by UUID, unsteady frames skipped, only
  its own undo step; the speed drag always put back with Auto Key off; pairBlend space blends called normal;
  Unpublish clears the mirror table.
- **5.6.29**: the Clothes switch; Speed: clothes hidden / GPU off / each skin; Publish learns the table on every
  Animtool control; Repair takes out joints with no weight; checks that can't run say so; run_tests.py 4 at a
  time with exact names; scripts/audit/control_options.py.
- **5.6.30**: bandages and a switch per piece; Keep the pose moves a control's constraint onto its group; Not a
  control (gusNotControl); Go there... in Check this scene; default pose on every control.
- **5.6.31**: Keep the pose moves aim constraints (the pupils); the Checker's history fix puts back a mesh that
  moves; the history warning names the nodes and where to clean them; Remove head squash leaves no switch node.
- **5.6.32**: the history check leaves out nodes that only drive a setting (the Clothes switch on the bandages);
  Remove head squash unlocks Publish's locks and cleans a squash removed half-way; Keep the pose says when no
  control is selected; scripts/diagnostics/slider_range.py.
- **5.6.33**: the history check reads Maya's whole classification (the bandages for real); Keep the pose zeroes
  locked channels (the pupils' translate Z / rotate, full turns) and relocks them; the Checker's zero fix says what
  it can't change; the "Step must be less than range" fields (Joints Padding / IK count, Face Brow count).
- **5.6.34**: the pupils are left alone (their rotate feeds the eyeballs' orient constraints: zeroing it turned the
  eyes); Keep the pose skips controls whose values drive something and runs in safe mode; the Checker ignores
  locked channels; Check this scene's buttons start it after the click (it crashed Maya from the buttons).
  **Gotcha:** never zero a control whose own channels feed something - check its outgoing connections first.
- **5.6.35**: real-Maya tests (Stage 1): `gus_rigtool/realmaya/` - run_maya_tests.bat / .command run
  run_maya_tests.py in mayapy; maya_cases.py holds the tests (a pupils, b history, c squash leftovers, e biped
  build/publish, d Check this scene, f IK/FK + mirror) and Gus's scene opened, never saved. Results:
  realmaya/maya_test_results.txt.
- **5.6.36**: first real-Maya run (Mac) passed a-e; 5.6.33's change doesn't turn an eye in a clean scene (the
  Hare's eye jump has another cause: the eye dry run on Gus's scene lists what moves). Check this scene no longer
  crashes when the model reference didn't load; Speed skipped with no window; test f fixed; g = builder self-test;
  the scene's references are found inside the local project folder (the Mac had H:/ paths).
- **5.6.37**: test f puts both arms in IK first (the biped starts in FK). Second real-Maya run (Mac): all clean
  but f; the eye dry run moved the eye meshes only 0.009 cm - the Hare's eye jump (5.6.33) is NOT explained by the
  pose going into the group; suspects: the Ctrl+Z after it, or GUI evaluation. Keep the pose skips the pupils now.
- **5.6.38**: test f keys the IK control after moving it (the switch keyed it: an unkeyed move is undone at the
  next update) and checks the arm moved before measuring jumps. **Gotcha for real-Maya tests:** after an Animtool
  switch, a moved control must be keyed, and a "no change" pass is only meaningful if something moved first.
- **5.6.39**: test f reads the mirrored values and keys the right control; new scene check scales each L_ control
  driving a joint's scale with its R_ twin and compares. **The Hare (v202 is the current file - "v210" was misnamed):**
  the left pupil didn't scale - its weights were on 62 stray vertices above the eye. Gus fixed it in the scene with a
  script (selected pupil ring -> L_Pupil_jnt 1, rest -> L_Eyeball_jnt), then did the same on the right so both match.
  The eyes' Orig shapes don't read reliably with xform (vertex matching by shape failed) - use selection-based fixes.

- **5.6.40**: Animtool arcs = Maya's editable motion trail styled like the onion skin's arcs (window of 24 frames,
  past blue / future orange, dots, handles on the selected key), follow selection + pin, rotation-only controls shown
  by the onion skin, trails out of saved files, timing beads via "make weighted" (asks). Real-Maya test h.
- **Onion skin (standalone, branch `onion-skin-tool`, `scripts/onion_skin_renderer/`)**: Gus's first script
  (onionSkinRenderer, MIT) made to run on Maya 2024 without PyMEL, installed by drag_to_maya.mel; ghosts in front
  (Harmony style), per-character pictures and keys, light table (others see-through), arcs on vertices / controls,
  new window (Ghosts / Arcs / Settings) and mini bar. Tested with a fake render API and real Qt offscreen; Gus
  confirmed it works in Maya.
- **5.6.41**: Attach rebuilt (hold channels on the follower, normalised blendMatrix, grips keyed so nothing jumps,
  hand-over, both hands, Attach window, bookmarks plugin loaded, loops refused) after Gus saw the stutter (cycle from
  the follower's own parentInverseMatrix); arcs on any control with free translate. Real-Maya tests h and i.
- **5.6.42**: arcs back to the plain arc (Gus: 5.6.40's look was "too much") + the Arcs panel (per-arc colour /
  hide / remove, range, look, handles, beads, sampling); Attach / Arcs windows are Qt.Tool on the Mac (stay in front).
- **5.6.43**: Attach's divider floor 0.001 (0.000001 is 'zero' to Maya: a divide-by-zero warning every frame where
  nothing held it, and the wrong place there); Repair fixes 5.6.41-42 attaches. The floating Animtool bar
  (`bar.py`: every tool, the Attach window / Arcs panel, row or column, opens with the window). Shelf buttons never
  vanish silently. Face kit tab: deleted ribbons skipped. Real-Maya test j.
- **5.6.44**: the toolbar under the Time Slider off once (the bar replaces it), the bar's buttons chosen. Gus's first
  real-Maya run (5.6.43, Mac, --no-scene): 82 ok; case i's FAIL was the test (a keyed hand: its own keys work on top
  of the attach - now checks the held space); bookmarks / undo need the Maya window (info, not notes). Add / Remove inbetween: one curve at a
  time ("Cannot move keys" on one stopped all), refused curves named; real-Maya case k.
  Next (Gus chose): Stage 2a - one control maker, Shapes + Make controls merged, every control a Maya controller.
- **5.6.45**: core/control_maker.py - every tool makes controls there (new(): curve, groups, place, parent, tag);
  every new control a Maya controller, linked up (pick-walk); Checker > Tag all controls (button only, Gus: never
  on Publish). drag_to_maya.mel updates Gus's own maya/scripts/gus_animtool (it didn't: his Animtool stayed 5.6.42
  through 5.6.43-44 until he ran updater.update_animtool by hand). Next: 5.6.46 one Controls tab (mock-up first).
- **5.6.46** (foundations, Gus: 'all of them'): the installed Animtool redirects to Gus_Rigtool's newer copy
  (gus_animtool/__init__.py, LOCAL_ROOT keeps defaults.json); realmaya/maya_facts.py + MAYA_FACTS.md (case m);
  realmaya/window_checks.py = bar > Test this release; bar > Copy the last problem (anim.LAST_PROBLEM); attach
  bake_all; run_tests normalizes the version; CLAUDE.md rules 11-13. Next: 5.6.47 one Controls tab (mock-up first).
- **5.6.47**: tools/controls_tab.py (Make + Shapes in one tab: shape list left, Make / Edit shape pages;
  registry.ALIASES shapes/makectrl -> controls_tab) and core/shape_edit.py (in front on an axis, stretch, hover
  preview, shape handles Done / Cancel / click away); MC.make front / front_axis / pivot_on_shape. Fixes: arc
  styling out of undo; Arcs break / join handles; shelf rebuilt once per version; a shape is a LIST of curves (the
  fake refuses one on its own); fake ls([]) -> []. Next: shape ideas 3-5 (fit to body, lie on the skin, shape
  from edges) once the mesh facts are back.
- **5.6.48**: shape_edit.fit_to_body / lie_on_skin / from_edges (Edit shape > On the body, Gap %); controls_tab:
  one click on Make makes the controls; Make on a selected control = a NEW control at its place (on_controls, any
  rig); curves.set_shape rebuilds referenced / locked curves in place (curve -replace, facts pending);
  shape_edit.controls allows helper shapes (not geometry); Animtool title fixed in build(); click-away check
  flushes Maya's idle queue (NOTE if still not done). Case o; fact curve_replace. Next: 5.7 UI redesign (Qt) -
  look 'version 2' approved (a colour per area: Build orange, Skin pink, Controls green, Connect purple, Check
  yellow, Toolbox blue; X/Y/Z red/green/blue; selection chips; shapes as pictures; drawings for hard fields),
  same functionality as 5.6.48, sub-pages remembered, an inventory test per area (nothing lost, nothing twice).
- **5.7.0** (Gus: 'make the new one default'): gus_rigtool/newui/ - the Qt window (window.py: Frame, Area,
  OldPage; workspaceControl gusRigtool57Window, uiScript restore()); pages = the tool's build() recorded
  (record.py) and drawn (render.py: Field answers query/edit by name; cards, wrapping rows, QFormLayout label
  above field); proxy.py = the `cmds` of core/ui and the 7 Controls tools (UI names registered by the new window
  go there). Controls area in the new look (controls_tab -> Make / Edit shape sub-pages with ShapeGrid); other
  areas = today's pages embedded (OldPage, in Maya only). main.new_window() / use_window(); Settings > Window.
  core/ui: STATUS_HOOKS, REBUILD_HOOKS, _to_new_window in go_to_tool. Next: 5.7.1 Skin (preview first), then
  Build, Connect, Check, Toolbox (then the old window can go); 5.8 one look for the Animtool / bar / Arcs / Attach.
- **5.7.1**: window filled once (uiScript runs at creation; restore() reuses a Frame already in the host); Pop out
  (PopFrame, Area(only=[tool], prefix="q7p_"), workspaceControl gusRigtool57Pop_<tool>); header buttons (Favourite,
  Pop out, Guide, Simple/Full, What's new, Update), tool description, Copy error report, Simple view while
  recording (ui._view); favourites.py (FavRow under the search, FavBar floating, myTools list, badges = initials
  in the area colour); cut_off also checks button text (_fits). Next: 5.7.2 Skin.
- **5.7.2**: window.SPLITS (a tool page shown as sub-pages by card titles; Skin: 6 + Fixes), Area.default_sub,
  NEW_LOOK skin + settings (settings drawn as today's page, OLD_PAGE), Settings its own area/button; favourites
  profiles (favProfiles: current, mine; builtin = All tools + one per area; My tools mirrors myTools), edit mode
  on the row (× remove, drop to reorder, + Add grouped) and the bar (per-profile shape: favBar.shapes).
  Next: 5.7.3 Build (preview first), then Connect, Check, Toolbox.
- **5.7.3**: NEW_LOOK + build; window.TABBED (a tool's own tabLayout -> sub-pages, Area._tabbed / _show_tab: the
  tab's changeCommand runs, so Build remembers sub_page2); TWO_ROWS (build, skin: Frame.tabs = tools, Frame.tabs2 =
  the tool's sub-pages, role "tab2"); proxy.refill(layout, fill) + render.refill: build_form.fill() in the new
  window records into the shown Form layout (Recorder.live: unknown names go to the shown page's fields) and
  draws it in place; Recorder(stem) - unnamed controls named kind__<stem>N, unique per page / refill;
  colorSliderGrp drawn (swatch + QColorDialog, rgbValue); float/intFieldGrp = render._Numbers (value list,
  value1..4); nested frameLayouts = inner cards (property inner, no number/pin, not in page.cards); combos
  AdjustToContents + window._combo_fits in cut_off. build_tab, build_form, build_existing, face_kit_tool,
  ribbon_tool, joint_chain use the proxy cmds. Next: 5.7.4 Face/Ribbon steps + two curves.
- **5.7.3.1**: widgets.Peek (a closed card's hint gives way: Maya at 326 px cut Rig builder / Ribbon).
- **5.7.4**: face_kit: selected_curves, curve_pair (loop = ends meet / sides; reverse; side L/R/C), strip_from_curves
  (loop -> periodic curve -> _band; sides -> loft of world-parented copies), parts take curves= and remember them
  (redo). face_kit_tool: from_<part> settings, _part_light / part_states, ui.step_status lights (levels made /
  ready). ui.step_light / set_light (both windows). Card.set_state -> tick / dot. window.SPLITS face + ribbon,
  FaceMap card (Build the face), StepStrip (Make a ribbon), Area._update_steps on selection. ribbon_tool:
  _curves_check, step_states, loft panel first, Loft options, More. realmaya case p + fact loft_curves.
- **5.7.5**: NEW_LOOK + connect, TWO_ROWS + connect, SPLITS nodes (3 pages), window.TOOL_LABEL / tool_label
  (Connections, Driven keys - new window only), Frame.go(as_tool=True) for tabs, go_key, next step, Recent (the
  'connect' tool vs area). render._fit_list (lists as tall as their rows). sdk_tool: Copy section managed by mode.
- **5.7.6**: NEW_LOOK + check; registry.PANELS + ("publish", build_tab.build_publish_panel); build_tab._publish_part /
  NP (Publish fields' own prefix, _PUB) / SKIP_PUBLISH (window.MOVED_OUT while recording Build); window.EXTRA_TOOLS
  {"check": ["publish"]} (area_of, search); Area records registry.builder(tool). checker (_show, find_repairs) and
  organize_tool (analyze) fill their rows through proxy.refill.
- **5.7.7**: theme.LOOK / LOOK_KEY "newWindowLook" ("today" default / "new"), load_look, new_look; stylesheet adds
  _new_look (scoped to QWidget#gusPage). render: _labelled (QFormLayout WrapLongRows), _card_new (Options Fold +
  summary, light first, desc), _Combo (current-text width), _short. widgets: Fold, Card.chip / set_desc / moved /
  drag + right-click menu, pin on hover. window: NEW_LOOK + toolbox, SPLITS pivots, Area order (_order_key,
  _apply_order, _place / _move_next_to across layouts, move_card, _visual), state["order"]; _breadcrumb.
  record: floatFieldGrp value lists (Mirror). main.use_look. window_checks.new_look.
- **5.7.8**: widgets.SegButton (bold width, '&&'), widgets.FormLayout (names above when narrow; replaces
  QFormLayout in render), WrapCheckBox plain text + longest-word minimum; Area.arrange / arrange_bar, Card.arr
  (Up / Down / To top), Card.set_title / set_arranging; header "Arrange"; _cards_of skips hidden tab pages
  (Build TABBED), moved -> current sub; _loose_before_cards (Edit shape swap); CARD_SPLITS + _split_cards;
  OLD_PAGE = () (Settings drawn, render.NO_FOLD); Frame.side_hidden / toggle_side; header gap 12.
  window_checks.arrange.
- **5.7.8.1**: Area._orig (each sub-page's first order) -> Reset order without rebuild; window_checks.arrange
  saves / restores state["order"], every page once in Gus's look; new_look's order part removed.
- **Onion skin (Nov 19)**: rigs not referenced (model and rig in different groups) work - meshes through the skin,
  keys from the rig; `cmds.ls([])` lists EVERYTHING in Maya - guard empty lists; the onion icon; Mac tool windows.
- **Later (Gus: "not a priority")**: Edit FK arc - bake the arm to IK over the range (anim.bake exists, every frame),
  edit the hand's trail, bake back to FK. To make it pleasant: bake only on the FK keys' frames, not every frame.

## 5. Open items and the roadmap

Next for the Hare: the list in section 3. The review (5.6.28) and the roadmap agreed with Gus:
1. **Stage 1 (during the film)**: real-Maya tests with `mayapy` on Maya 2024 (Windows and Mac): build, skin,
   IK/FK jump, mirror pose, Publish / Unpublish. **Started in 5.6.35** (gus_rigtool/realmaya/); next: make the
   first run clean, then each release lists the real-Maya tests to run and is done only when they pass.
2. **Stage 2 (quiet weeks)**: one shared control maker in `core/` (every option: distance in front, pivot on
   the shape, shape turns, group stack, line width, tag as controller) used by Shapes, Make controls, Ribbon,
   Builder, IK spline, World levels; merge **Shapes + Make controls** into one Controls tab (today's Make controls
   look as default, a clear Custom panel); every control tagged as a Maya controller; skin mirror in one place;
   one shape mirror; side-colour settings out of the Mirror tab; logic out of tools/ (checker queries, shape
   library, group maker); one updater; split pickerqt.py; IK/FK matching with stretch / soft IK (only used for
   exaggerated poses, so not urgent).
3. **Stage 3 (after the film)**: Maya 2025-2027 (PySide6, Python 3.13 - the fake tests already pass on 3.13;
   Maya 2027's built-in ngSkinTools skinning), merge Checker + Check this scene, a short README, the Hare as a
   demo rig once the short is out.
4. Ideas raised: a Check this scene test that the head squash moves every mesh it should (when it comes back);
   per-skin timing in a separate button if Check this scene gets slow (it takes ~48 s now).

## 6. Useful facts and gotchas

- **Picker storage:** in the rig's `gusPicker` string attribute (`pickmodel.RIG_ATTR`), or per user.
  `PM.where_from(ns)` returns "rig", "yours" or "auto". Picker prefs are per computer (optionVars `picker_*`).
  Backups go to `userAppDir/gus_animtool/picker_history/<rig>/` (the last 30).
- **Picker hit order:** buttons first, then texts (Edit only), then frames. Folded items and items on hidden
  layers are skipped.
- **Ribbons:** `core/ribbon.py`:
  - `_find_builds()` keys builds by surface;
  - `mirror_sides()` flips right-side offsets;
  - `make_symmetric()` moves controls onto the mirror spots (it's in `repair.MOVES`).
- **Repair:**
  - `FINDERS` list → `Item(id, label, names, count, fix)`;
  - `repair.apply()` wraps each fix in safe mode;
  - `repair.MOVES` are fixes meant to move the mesh, so safe mode skips them;
  - `SCALE_FIXES` and ids starting `scale_` skip the x2 look.
- **Scale plug:** `core/scale_check.scale_control()` returns (control, plug), here `Global_ctrl.globalScale`.
- **Heredocs:** writing Python through bash heredocs has caused escaped-backslash bugs (`\\n`). Check regexes
  after writing.
- **Whole-repo lint** gives thousands of false errors (the tests `exec` the fakes). Lint only the changed files.
- **Test names:** since 5.6.29 `run_tests.py` takes exact names (`name*` for a prefix); `--update` needs names
  and prints each diff.
- **The fake Maya** (`tests/fakemaya.py`): `ls` has no wildcards, constraint commands ignore `name=` (they're
  called `<driven>_parentConstraint1`) and connect themselves to the driven node, only `skinCluster` counts as a
  `geometryFilter`, `skinCluster` / `listHistory` queries return nothing (patch them in a test). Since 5.6.28 it
  remembers `defaultValue` for `attributeQuery(listDefault=True)`.
- **Delta Mush** `displacement` has a hard maximum of 1 for `setAttr`, but a connection from globalScale passes 2
  through (and that's what keeps the belt's form).
- **Python's `a or b if c else d`** is `(a or b) if c else d` - it was right; brackets only for clarity.
