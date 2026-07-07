# Motion Graphics

Four practical methods for producing on-brand motion graphics without design or animation skills, plus the agent-buildable equivalent for when the target is a code artifact rather than a studio export.

In the studio, select the **animation** template before using any of these — the exact button location has moved a few times as the studio UI has changed, so find it wherever it currently sits rather than relying on a fixed screenshot.

## Method 1: template copy (easiest)

Find an existing motion graphic you like on a code-sharing showcase site and copy its source. Paste that code into the prompt box with a simple instruction: *"Use this template, but [describe the specific changes]."* Because the template already fully specifies the visual design, this needs no back-and-forth — one prompt, done in a couple of minutes. Templates can also be combined: copy two different templates, hand both over, and ask for them sequenced into one animation (e.g. a title screen followed by a progress bar).

## Method 2: start/end screenshots

For a motion graphic you've only ever seen, not found as a template: screenshot the first frame, the last frame, and one or two mid-animation frames if there's a significant transition worth pinning down. Attach all of them, select the animation template, and describe:
1. What's being recreated (start frame, end frame, attached).
2. The animation itself, step by step.
3. Any content changes (your own text/labels instead of the original's).

**The prompt-precision lesson (the single most important detail here):** vague adjectives don't reliably describe motion. "Smooth" was interpreted correctly as *not jerky* but not as *continuous* — the animation was smooth yet still stepped. The fix was to specify the actual physical behavior wanted: *"steadily increase the entire time, so it reaches full when the animation ends"*. When an edit doesn't land, the fix is almost always to describe the underlying behavior more precisely, not to repeat the same adjective louder.

Other useful precision tools:
- **Time-targeting** — reference specific points, e.g. *"around the 5-second mark, the storyboards overlap the text — move them"*.
- **Selective reveal** — e.g. blur specific text until a defined moment, so a viewer can't read ahead.
- **Markup mode** — select one element directly (e.g. spacing between a dash and a number) and describe just that fix, rather than a full-animation prompt.

## Method 3: transcript-driven (talking-head videos)

For a video or presentation, get a timestamped transcript (SRT-style; any transcription tool works) and paste it in alongside a prompt asking for chapter/section motion graphics synced to it. Attach a brand reference (even just a screenshot of the relevant product UI) so the output stays on-brand. Expect one or two follow-up prompts referencing specific timestamps to fix small misalignments — this rarely lands perfectly from a transcript alone, since there's no template to anchor it.

## Method 4: animate any UI (web element capture)

To turn a real website or app UI into a motion graphic (e.g. "someone using this product"): take a screenshot of the UI, then use a bookmarklet-based element-capture tool to grab the actual code of the target element from the live page (drag the tool to the bookmarks bar, click it on the target page, select the element — its code is captured for you to copy). Paste both the screenshot and the captured code into the studio prompt, select the animation template, and describe the sequence step by step (e.g. "zoom into the prompt box → type X → zoom out → new content appears").

## Agent-buildable variant

All four methods above work identically when *you* (Claude Code) are the one building the output, rather than sending the user to the studio — the only difference is the deliverable becomes a self-contained HTML/CSS/JS artifact (inline styles/scripts, CSP-safe, theme-aware) built with the `Artifact` tool instead of a studio export:

- **Template copy** → adapt the copied markup/CSS/JS directly in the artifact file.
- **Start/end screenshots** → describe the same start/end states and precise motion behavior in the build, using CSS transitions/animations or a small JS timeline.
- **Transcript-driven** → generate section markers from the transcript directly into the animation's timing.
- **Animate-any-UI** → recreate the captured element's markup/styling, then layer the interaction sequence on top.

The same prompt-precision lesson applies to self-authored animations: describe the actual easing/duration/continuity wanted, not just an adjective. For animated *data* visualization specifically (charts, stat tiles, sparklines), use the `dataviz` skill instead of hand-rolling it here — it owns color, form, and motion conventions for that domain.

## Export workarounds

The studio has no direct "export as video file" option. Two working approaches:
1. **Project archive → Claude Desktop co-work.** Export → Project Archive → download the ZIP. Open the Claude Desktop app, enable co-work, point it at a save location, attach the ZIP, and ask it to export as MP4. Works, but is slow.
2. **Screen recording (the pragmatic default).** Just play the animation in the studio and record the screen (e.g. QuickTime on macOS). Faster, and the output is indistinguishable from a "real" export.
