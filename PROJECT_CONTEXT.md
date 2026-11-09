# Gus_Rigtool - project context (backup for a new chat)

This file was written on 2026-11-09 at the end of a long working chat. Give it to a new chat, together with
`CLAUDE.md` and `Gus_Rigtool_install.zip`, to continue the work. It covers what the project is, how we work,
what was built in this chat, the Hare rig's state, and what's open.

---

## 1. The project

- **Gus_Rigtool** is a rigging toolkit for Maya 2024+ (Python). It's built by Gus with Claude, release by release.
  It went from **1.0.0 to 5.6.27, about 147 releases**, all listed in `gus_rigtool/CHANGELOG.txt`.
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
   he can run that changes nothing (undo off, everything put back), and ask him to paste the result.

## 3. The Hare rig (current state)

- **Scene:** `/Volumes/T7/The Tree That Bloomed in Winter/TTTBMW_Hare_Rigging/scenes/Hare_Rigging_v197_NewSkinWeigh.ma`
  (v195 and v196 came before it). macOS, Maya 2024.
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

### Last Check this scene (5.6.27, v196): what was still open

1. Collar and Cape_Ribbon "right side doesn't mirror". Fixed by marking them **Not symmetric** (not done yet).
2. L/R_Pupil_ctrl aren't at zero and are driven by a constraint, and so is Tongue_end_IK_ctrl. The fix: move the
   offset and the constraint onto their offset groups.
3. Six hidden old controls (above). Delete them or drop their control role.
4. Model file clean-up in `Geo_Hare_08_MovedTail.mb`:
   - non-deformer history on 12 meshes (Hare_Body included);
   - duplicate names (Belt, Gums_UP, Hare_Body, Teeth_Up);
   - Redshift unknown nodes;
   - 21 `Eye_geo:` leftover namespaces;
   - 20 unused Orig shapes.
5. Joint up-axis flips and twists, and sleeve joints that aren't exact mirrors. These are low priority.
6. **Not published yet**, so the mirror table shows 0 of 366. Save, Publish, then Deliver.

### Fixed by 5.6.27 Repair (confirmed in the v196 report)
- The belt losing form at x2: Delta Mush displacement is now tied to globalScale, and the scale check passes.
- The hidden `...ShapeDeformed` meshes in the middle of the skin → Head_squash chains were removed.
- Head_squash "Missing componentTags" warnings (450 per session): gone.
- The picker check now finds the rig's picker.

### Speed measurements (dragging COG, Maya 2024 on his Mac)

| Measured | Result |
|---|---|
| Normal | 45–48 ms per step (about 22 fps) |
| GPU override off | 43 ms: **faster than on**, so no skin is on the graphics card |
| Delta Mush, jiggle/wave expressions, squash or follicles off | no real gain (1–2% each) |
| All skins off | about 20 ms |
| Meshes not drawn | 17 ms |
| Each skin off on its own | about 4 ms saved even for tiny skins: a fixed overhead, likely GPU override |
| Real costs above that overhead | Hood ~6 ms (skinCluster18, 677 vertices, 94 joints), Hare_Body ~3.5 ms (skinCluster10, 7,300 vertices, 172 joints), Pants ~3 ms (skinCluster23, 754 vertices, 181 joints), Shirt ~2.5 ms (skinCluster17, 1,031 vertices, 105 joints) |

- **pairBlend1 and pairBlend2 are NOT stray keys.** They blend two space constraints on
  `L/R_humerus_FK_space_grp` (rotate), weight 1. That's normal; the checker message is wrong about them.

## 4. What this chat built (5.6.23 to 5.6.27)

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

## 5. Open items: the proposed 5.6.28 (waiting for Gus's OK)

1. **Speed section:** per-skin timing with the ~4 ms per-skin overhead taken out, and a note when GPU override is
   slower than off for this rig.
2. **pairBlend message:** a pairBlend fed only by constraints is a space blend and shouldn't be flagged. Only real
   keys plus a constraint should warn.
3. **Clothes: full / hidden** switch on the visibility control for Hood, Shirt and Pants. Hiding them while
   blocking should save most of the ~15 ms.
4. **Clothes skins clean-up, through safe mode:** remove zero-weight joints (Hood and Pants have 4 each) and
   report how many joints each vertex really uses.
5. Ideas raised but not planned:
   - a one-click "move the constraint and offset onto the offset group" for the pupils and tongue;
   - an in-Maya check section for 5.6.27 in `maya_check.py`.

Questions that were waiting for Gus:
1. For item 3: hide the clothes, or show a lighter stand-in?
2. Make 5.6.28 with all four items, or leave the rig as it is (it already runs at about 22 fps)?

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
- **Prefix matching:** `run_tests.py <name>` matches as a prefix, and `--update` with a short name can update more
  tests than you meant.
