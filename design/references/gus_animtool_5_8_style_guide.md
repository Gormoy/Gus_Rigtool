# Gus Animtool 5.8 — UI/UX & Qt Engineering Style Guide (Claude Code Spec)

This document is the single source of truth for building **Gus Animtool 5.8** in **Maya 2024 (PySide2 / Qt 5.15)** with full forward compatibility for **Maya 2025–2027 (PySide6 / Qt 6)**.

---

## 1. Core Design Principles (Non-Negotiable)

1. **1-Click Instant Triggers:** Every tool fires immediately on left-click inside a single Maya undo chunk (`cmds.undoInfo(openChunk=True)`). No multi-step confirmation buttons.
2. **Viewport-Safe Focus (`NoFocus`):** Every tool button on the Floating Bar, Narrow Dock, and Micro-Rail MUST set `Qt.FocusPolicy.NoFocus` so clicking a tool never steals `Spacebar` (Hotbox), `S` (Key), or navigation hotkeys from Maya's Viewport 2.0. Keyboard focus is reserved exclusively for the **Fuzzy Search Palette** (`Ctrl+K`) and text inputs.
3. **Zero Color-Only Cues:** Category colors are always paired with a **geometric shape + number** in dock headers (`● 1 POSE`, `■ 2 KEYS`, `◆ 3 LIMBS`, `▢ 4 SPACES`, etc.) and **named text pills** in Column mode (`BLK`, `POL`, `SPC`, `RIG`, `ALL`). Never use unlabeled colored dots.
4. **Surface-Step Depth Over Shadows:** Qt Style Sheets (QSS) do not support CSS `box-shadow` reliably inside Maya docks. Establish visual hierarchy strictly through our four dark slate steps (`#16191e` → `#22262d` → `#242933` → `#343c4a`) and crisp 1px borders (`#454f60`).
5. **Single Source of Truth (`ActionSpec`):** All 58 tools are defined once. The Maya Shelf, Floating Bar, Narrow Dock, Micro-Rail, Radial Pie Menu, and Fuzzy Search Palette all generate from that single registry.

---

## 2. Color Palette & QSS Design Tokens

### Surface & Text Tokens (Balanced Dark Mode, ≥ 7:1 Contrast)

| Role | Hex | Usage |
| :--- | :---: | :--- |
| **Sunken Background** | `#16191e` | Dock root background, slider tracks, secondary split caps, micro-strip background |
| **Panel Surface** | `#22262d` | Floating Bar body, Dock fixed header, dialogs |
| **Card / Section Surface** | `#242933` | Collapsible category drawers, active profile tab |
| **Button Default** | `#343c4a` | Tool tiles, primary dock buttons |
| **Button Hover** | `#404a5b` | Hover state for tiles and buttons |
| **Primary Border** | `#454f60` | Card outlines, button borders, pie backdrop rim |
| **Subtle Divider** | `#333a47` | Internal hairlines and header separators |
| **Primary Text** | `#f1f5f9` | Button labels, badge text, active titles |
| **Muted Text** | `#9aa5b5` | Inactive tabs, secondary captions, telemetry |
| **Primary Active Accent** | `#3898c8` | Active toggles, focus highlights (`#56b4e9` in Okabe-Ito mode) |

### Category Accents (Default Balanced vs. Okabe-Ito Color-Blind Safe)

| Category Key | Dock Header Badge | Default Hex | Okabe-Ito Safe Hex |
| :--- | :--- | :---: | :---: |
| `pose` | `● 1 POSE` | `#d66b8c` | `#cc79a7` |
| `keys` | `■ 2 KEYS & TANGENTS` | `#d9a13b` | `#e69f00` |
| `limbs` | `◆ 3 LIMBS` | `#3ea87c` | `#009e73` |
| `space` | `▢ 4 SPACES & PROPS` | `#907ad6` | `#f0e442` |
| `timing` | `▲ 5 TIMING & CYCLES` | `#38b2ac` | `#0072b2` |
| `curves` | `〰 6 GRAPH CURVES` | `#e07a3c` | `#d55e00` |
| `view` | `◉ 7 PICK & VIEW` | `#cf6ba9` | `#cc79a7` |
| `open` | `⊞ 8 LAUNCHERS` | `#4fb3d9` | `#56b4e9` |

* **Category Header Tint:** Blend the category hex at **12% alpha** over `#242933` for collapsible drawer headers, paired with a **3px solid left rail** on the drawer frame.

---

## 3. The 58-Tool Hybrid Icon System

Following NN/G's 2-second recognition rule, the 58 tools are split into **29 Schematic Graphic Icons** (universal physical/spatial shapes) and **29 Bold Typographic Badges** (abstract animation/rigging operations). Every tile has:
* A **3px bottom category accent bar** (`height = max(2, round(w * 0.09))`).
* A **5px white bottom-right triangle** above the accent bar whenever the tool has right-click settings (`has_settings = True`).

| Category | Graphic Icons (29) | Typographic Badges (29) |
| :--- | :--- | :--- |
| **Launchers (5)** | `picker`, `poses`, `clips`, `bar` | `main` (**`GA`**) |
| **Pose (6)** | `tween_prev`, `tween_next`, `mirror`, `flip`, `reset` | `twin` (**`TWIN`**) |
| **Keys & Tangents (9)** | `key`, `nudge_left`, `nudge_right`, `tan_auto`, `tan_spline`, `tan_linear`, `tan_flat`, `tan_step` | `blocking` (**`BLK`**) |
| **Timing & Cycles (16)** | `copy_keys`, `paste_keys` | `inbetween_add` (**`+INB`**), `inbetween_remove` (**`-INB`**), `offset_minus` (**`OFF-`**), `offset_plus` (**`OFF+`**), `offset_back` (**`ORIG`**), `mirror_cycle` (**`MCYC`**), `cycle_continue` (**`CYC+`**), `cycle_place` (**`INPL`**), `cycle_forward` (**`FWD`**), `bake_keys` (**`BAKE`**), `reduce_keys` (**`RED`**), `stretch` (**`STR`**), `reverse` (**`REV`**), `time_scale` (**`x1.2`**) |
| **Graph Curves (7)** | `pull`, `push`, `smooth`, `noise` | `negate` (**`NEG`**), `redundant` (**`CLN`**), `euler` (**`EUL`**) |
| **Limbs (2)** | — | `ikfk` (**`IK/FK`**), `overlap` (**`OVL`**) |
| **Spaces & Props (6)** | `temp_world`, `temp_pivot`, `attach`, `release` | `bake_back` (**`BK<-`**), `attach_window` (**`ATT=`**) |
| **Pick & View (7)** | `arcs`, `hide_ctrls`, `isolate`, `ghosts`, `playblast` | `arcs_panel` (**`ARC=`**), `hider` (**`PART`**) |

### 75/25 Split-Button Secondary Caps (Narrow Dock)
`mirror` (`R->L`), `reset` (`All`), `key` (`All`), `blocking` (`Spline`), `inbetween_add` (`-Inb`), `offset_plus` (`Casc`), `bake_keys` (`1/2/4`), `reduce_keys` (`Tol`), `ikfk` (`Rng`), `overlap` (`Cyc`), `attach` (`Win`), `release` (`Bake`), `arcs` (`Panel`), `playblast` (`50%`).

---

## 4. The Four Synchronized UI Surfaces

### A. Single-Row Maya Shelf (`Gus_Animtool_58`)
* **Layout:** Strictly **one straight horizontal row** (never a grid).
* **Icons:** Render/export all 58 tiles at `64×64` PNG with the `#343c4a` rounded-square background, `#454f60` border, and 3px category bar baked in.
* **Separators:** Insert vertical shelf separators (`cmds.separator(style="shelf", horizontal=False)`) between each of the 8 categories.

### B. Proportional Floating Bar
* **Profiles:** 5 default profiles (`BLK`, `POL`, `SPC`, `RIG`, `ALL 58`) + user-customizable profiles stored in JSON.
* **Persistent Layout Mode:** Selecting `Row`, `2R`, `Col`, or `Grid` persists when switching profiles. Exception: selecting `ALL 58` from `Row` or `Col` defaults to `Grid`.
* **Zero Scrolling & Auto-Shrink:** Before laying out tiles, calculate whether the bar fits within `92%` screen width / `85%` screen height. If it overflows, step `icon_px` down by `2px` (to a minimum of `22px`) and display `*` next to the pixel readout. Restore the user's `target_icon_size` when switching back to a smaller profile.
* **Proportional Scaling (`24px – 52px`):**
  * Controlled via inline slider OR **`Ctrl + Mouse Wheel`** over the bar.
  * `Lbl OFF`: `cell_w = icon_px + 4` with `2px` spacing (zero dead space).
  * `Lbl ON`: `cell_w = max(icon_px + 6, 52)` with uniform 2-line labels so icons stay aligned.
  * **Inline Tweener** (rendered between `tween_prev` and `tween_next`): scales proportionally (`width = max(108, icon_px * 4.1)`, `height = max(30, icon_px + 4)`). At `icon_px <= 28`, hide the 7-tick sub-row to keep the track clean.
* **Full-Information Column Mode (`~74px` wide):**
  * Top chrome: `::` drag grip, pixel readout, `=` menu button.
  * 1-click `Row | Col | Grd` row and `Lbl | Pie` row.
  * Named profile pills (`BLK 11`, `POL 12`, `SPC 8`, `RIG 10`, `ALL 58`) with 3px colored left bars.
  * Full vertical Tweener (`64×128px`) keeping `%` readout, `100%/150%` overshoot toggle, and 7 clickable ticks (`+75` to `-75`) beside the vertical slider.
* **Right-Click Tool Settings Micro-Strip:** Right-clicking any tile unfolds a slim attached strip directly under the bar showing that tool's options (`Step`, `Scope`, `Mode`, etc.) without opening a modal dialog.

### C. Hotbox-Style Radial Pie Menu
* **Trigger:** Native Maya press-and-release single-key hotkey bound via `cmds.runTimeCommand` + `cmds.nameCommand` + `cmds.hotkey(keyShortcut="grave", ..., autoSave=False)` (default `` ` `` Backtick; user-switchable to `F1` or `\`).
* **Backdrop:** Paint the outer dark translucent circle (`rgba(22, 25, 30, 232)`, `#454f60` border) and inner dashed active-profile circle **directly inside `RadialPieMenu.paintEvent`** (not a child widget) so Maya composites it cleanly over Viewport 2.0.
* **3 Zones:**
  1. **Top:** 1–5 Profile switcher strip (also responds to keyboard keys `1`–`5` while open).
  2. **Center:** 8-compass radial ring (`N` through `NW`) with `36px` tiles and solid dark pills behind every label. Releasing the hotkey over a tile triggers it; right-clicking pins the pie open and loads that tool's settings into the bottom strip.
  3. **Bottom:** Overflow strip (for profiles with >8 tools) + attached RMB Tool Settings micro-strip.

### D. High-Contrast 242px Narrow Dock + Auto Micro-Rail
* **Docking:** Wrapped in Maya `cmds.workspaceControl(..., dockToMainWindow=("right", True), initialWidth=242, minimumWidth=72)` with a `uiScript` restore hook.
* **Fixed Header:** Profile pills (`BLK | POL | SPC`) + `?` Fuzzy Search button + `CB` Okabe-Ito toggle + 6-icon **Pick & View** compact strip (`arcs`, `hide_ctrls`, `isolate`, `hider`, `ghosts`, `playblast`).
* **Scrollable Body (`QScrollArea`):** Calm 3×2 Pinned Quick-Launch Grid (2px top category accent) → Full-width Tick-Detent Tweener → All **58 tools** across 8 collapsible drawers with 12%-tinted headers and 75/25 split buttons.
* **Fixed Footer (`22px`):** Live selection/frame/mode telemetry (`● L_hand_ik · f14 · IK | 58 tools`).
* **Auto Micro-Rail (`width < 135px`):** In `resizeEvent`, automatically hides the header, drawers, and footer and displays a single vertical column of the active profile's top 8 pinned tiles.

---

## 5. Maya & Qt Engineering Rules (For Claude Code)

1. **Cross-Version Qt (`Qt.py` 2.0.x):**
   * Use fully qualified enums (`Qt.AlignmentFlag.AlignCenter`, `Qt.FocusPolicy.NoFocus`, `Qt.WindowType.Tool`).
   * Import `QAction` and `QShortcut` from `QtGui`.
   * Use `QtCompat` (or `position()` / `globalPosition()` fallback) for mouse/wheel event coordinates.
   * Use `.exec()` in PySide6 / `.exec_()` in PySide2 (or `QtCompat.QApplication.exec_()`).
2. **Pure `core/` vs. `ui/` Split:**
   * Nothing inside `core/` may import `Qt`, `PySide2`, or `PySide6`.
   * Keep `gus_animtool/actions.py` as pure data (`ActionSpec` frozen dataclass + `run(key)` with `cmds.undoInfo(openChunk=True)` error-safe wrapper).
3. **Selection Performance:**
   * Replace direct `scriptJob(e=["SelectionChanged", ...])` calls with `om.MEventMessage.addEventCallback("SelectionChanged", ...)` feeding an **80ms single-shot `QTimer`**.
   * Bail out immediately if `cmds.play(q=True, state=True)` is `True`.
4. **JSON Profile Storage Schema:**
   ```json
   {
     "active_profile": "blocking",
     "layout_mode": "row",
     "show_labels": false,
     "target_icon_size": 34,
     "color_blind_safe": false,
     "pie_hotkey": "grave",
     "profiles": {
       "blocking": ["key", "mirror", "tween_prev", "tween_next", "inbetween_add", "inbetween_remove", "tan_step", "ikfk", "flip", "attach", "reset"]
     }
   }
   ```
5. **Reference Implementation:** Use **`gus_animtool_58_ui_test_v3.py`** as the visual and behavioral reference for widget spacing, `paintEvent` pie backdrop rendering, auto-shrink layout math, and shelf PNG export.