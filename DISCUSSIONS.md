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
- 5.7.2: preview of the Skin area + the Settings button + favourites editing, then the plan, then build.
- Push 5.7.1 to main (needs his explicit "push 5.7.1").
- Still unknown: 'Cannot move keys' in his shot (the tool names refused curves; Copy the last problem).

## Ideas parked (not now)

- Edit FK arc (bake to IK, edit, bake back) - "not a priority".
- Pictures in every page (lock grid, 'in front' drawing) - page by page as areas are redone.
