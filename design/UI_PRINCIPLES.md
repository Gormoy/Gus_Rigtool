# What makes a tool window easy to use - the rules, and what they mean for Gus_Rigtool

Gathered 2026-11-21 for the 5.7.7 look (Gus: "find the design references ... rules, what makes a great UI/UX,
and what the design means"). Each rule: what it says, why, and what we do with it. Sources at the end.

## 1. Show less at first (progressive disclosure)
**Rule.** Show only what most people need for the job; put the advanced or rarely used options one click away.
NN/g: it improves 3 of the 5 parts of usability - learning it, speed, and fewer mistakes. The print dialog is
the classic example (Print button first, the settings behind "Show details").
**Why.** Every extra item on screen competes with the ones that matter (Nielsen heuristic 8, *aesthetic and
minimalist design*).
**For us.** Each section shows its job first: the field you fill, the quick buttons, the main button. The
choices you rarely change (Place, Where, Name, Mode...) fold into one line, **Options ▸**, that says what's set
("Match & zero · Above the object · Add suffix · Each") - so you still see it without reading every row.
Closed sections are one line: their title. Nothing is removed; everything is one click away.

## 2. Fewer choices at once = faster decisions (Hick's law)
**Rule.** The time to decide grows with the number and complexity of choices.
**For us.** One main action per section, the biggest and coloured. Secondary buttons quieter. Long pages split
into short pages (Pivots: Move / Remember & reset).

## 3. Make the important thing big and close (Fitts's law)
**Rule.** The time to hit a target depends on its size and distance.
**For us.** The main button is full width and taller; it sits right under the options it uses. Small things
(?, pin) stay small and at the edge.

## 4. Things close together belong together (Gestalt: proximity, common region, similarity)
**Rule.** Nearby things read as a group - proximity is the strongest grouping cue, stronger than colour or shape.
Things inside a shared border read as one group; things that look alike are taken as alike.
**For us.** Space does the grouping, not boxes: small gaps inside a section, a bigger gap and a thin line between
sections (Mix C). Every choice looks the same everywhere (round radio buttons), every main button looks the same.

## 5. One clear order to read (visual hierarchy)
**Rule.** Hierarchy comes from size, weight, colour, spacing and position; a page needs small, medium and large
things. Test: blur your eyes - the most important thing should still stand out. Use a few hand-picked text sizes
(2-3 per part) and spacing from a fixed scale (4 / 8 / 12 / 16 / 24 px).
**For us.** Three text sizes: section title 15-16 bold, labels and controls 13, notes 12 dim. Spacing on a 4 px
scale. The order on every section: title -> what it does (one line) -> what you fill -> the main button.

## 6. Recognise, don't remember (Nielsen heuristic 6)
**Rule.** Keep options and their state visible so people don't have to remember them between places.
**For us.** The Options line shows the current choices even when folded; the light at the top says what's
selected and what to do; the step badges (tick / dot) say what's done.

## 7. Speak the user's words; be consistent (Nielsen heuristics 2 and 4; Blender's guidelines)
**Rule.** Use words and concepts the user knows, not internal jargon; the same thing looks and works the same
everywhere. Blender's interface guidelines: group related properties under headings (the heading names them, so
labels can be short), one single-column layout everywhere, every editor follows the same patterns.
**For us.** Plain names (Connections, Driven keys); labels in one column on the left, controls on the right, on
every page; the same section look in every area.

## 8. Show what's going on (Nielsen heuristic 1) and let people back out (heuristic 3)
**For us.** The light at the top of each tool; the Selected box; one undo per action; the old window always one
click away in Settings > Window (Gus: "great to always have an option to go back").

## 9. Colour on dark: calm surfaces, few accents, enough contrast (Material dark theme, WCAG)
**Rule.** Dark grey, not black, as the base; lighter surfaces for things that sit "higher"; accents used sparingly
and a little desaturated (saturated colours "vibrate" on dark grey). Contrast: text at least 4.5 : 1 against its
background (large text 3 : 1); borders, focus rings and other controls at least 3 : 1.
**For us.** The new window's palette stays (panel #33373d, fields #202326, text #e9ebee); each area keeps its
colour, used only for the main button, the selected tab, the numbers and the sidebar mark. Grey text for notes
stays above 4.5 : 1 (#a2a7ae on #33373d). Red only for delete / remove.

## 10. Clarity and deference (Apple's interface guidelines)
**Rule.** The interface supports the work and never competes with it: legible text at every size, precise icons,
subtle decoration.
**For us.** No emoji (Gus); line icons; no decoration that doesn't say something.

## How this changes the look (Mix C2)
| Before (Mix C) | After (C2) |
| --- | --- |
| every option of a section on show | the job first; the rest under **Options ▸** with a one-line summary |
| closed sections show a description line | closed sections: just the title (one line) |
| grey / blue look | the new window's colours: each area's colour on its numbers, tab and main button |
| sections the same weight | title 16 bold, a gap and a thin line between sections |

## Sources
- Nielsen Norman Group - 10 usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
- NN/g - Progressive disclosure: https://www.nngroup.com/alertbox/progressive-disclosure.html
- Interaction Design Foundation - Progressive disclosure: https://ixdf.org/encyclopedia/progressive_disclosure.html
- Laws of UX (Hick, Fitts, cognitive load, proximity): https://lawsofux.com/
- UK Department for Education - Laws of UX in practice:
  https://accessibility.education.gov.uk/profession-guidance/interaction-design/laws-of-ux
- NN/g - Principles of visual design: https://www.nngroup.com/articles/principles-visual-design/
- NN/g - Gestalt: proximity https://www.nngroup.com/articles/gestalt-proximity/ ,
  similarity https://nngroup.com/articles/gestalt-similarity , common region
  https://www.nngroup.com/videos/common-region-gestalt/
- Blender Human Interface Guidelines - layouts:
  https://developer.blender.org/docs/features/interface/human_interface_guidelines/layouts/ ; properties editor
  single-column design: https://projects.blender.org/blender/blender/issues/54951
- Material Design - dark theme: https://m2.material.io/design/color/dark-theme
- W3C - WCAG contrast (minimum): https://w3.org/WAI/WCAG22/Understanding/contrast-minimum.html ;
  WebAIM contrast: https://webaim.org/articles/contrast/
- Apple Human Interface Guidelines - design principles:
  https://developer.apple.com/design/human-interface-guidelines/design-principles
