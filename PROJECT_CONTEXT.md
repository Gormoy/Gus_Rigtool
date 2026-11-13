# Gus_Rigtool - project context (backup for a new chat)

Written on 2026-11-09 at the end of a long working chat; updated on 2026-11-13 after the first Claude Code
session (5.6.28 - 5.6.31). The code is in the GitHub repo `Gormoy/gus_rigtool` (one branch per release:
`import-5.6.27`, `release-5.6.28` ... `release-5.6.31`; `main` holds only the licence so far). It covers what the
project is, how we work, what was built, the Hare rig's state, and what's open.

---

## 1. The project

- **Gus_Rigtool** is a rigging toolkit for Maya 2024+ (Python). It's built by Gus with Claude, release by release.
  It went from **1.0.0 to 5.6.31, about 151 releases**, all listed in `gus_rigtool/CHANGELOG.txt`.
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

### Last Check this scene (5.6.30, v199, Windows): what's still open

1. **Collar and Cape_Ribbon** "right side doesn't mirror": mark them **Ribbon tab > Not symmetric** (not done yet).
2. **L / R_Pupil_ctrl** (aim constraint on the control) and **Tongue_end_IK_ctrl**: 5.6.31's **Behaviour > Rest here >
   Keep the pose, zero** moves aim constraints too - run it on them.
3. **L_IK_Elbow_ctrl / L_IK_Wrist_ctrl**: the left side's old controls, still hidden by hand - **Behaviour > Not a
   control** (the right side, Neck_ctrl and Head_ctrl are marked).
4. **Non-deformer history** on Bandage_L / R, Bandages_Arms and both eyes. **Don't delete the eyes' history**: Gus
   tried and the left eye jumped to the other side (it's probably the mirror that made it). 5.6.31's report names
   the nodes; the Checker's fix now puts back any mesh that moves. The bandages: clean in the model file.
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

## 4. What was built (5.6.23 to 5.6.31)

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

### 5.6.28 - 5.6.31 (Claude Code, 2026-11-10 to 13)
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

## 5. Open items and the roadmap

Next for the Hare: the list in section 3. The review (5.6.28) and the roadmap agreed with Gus:
1. **Stage 1 (during the film)**: real-Maya tests with `mayapy` on Maya 2024 (Windows and Mac): build, skin,
   IK/FK jump, mirror pose, Publish / Unpublish.
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
