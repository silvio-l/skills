# Visual Review — Conditional UI Verification

Loaded by the reviewer **only** when the orchestrator passed a non-empty `{{UI_DIFF}}`. For a backend-only diff this file is never read and costs nothing.

Goal: confirm that a frontend change does not merely compile, but **looks the way the plan said it should** — and, where the plan declared a visual expectation, that it fulfils it precisely, not just approximately.

This protocol runs **inside the existing reviewer spawn** (no extra sub-agent). The reviewer is still read-only with respect to source files — see the carve-out below.

## The three capture tiers (cheapest first — do not skip a cheaper tier)

1. **Code-level (screenshot-free)** — Step 0. Always run. Most "does the headline match its sibling card" questions are answered by *reading* the peer component, with zero capture.
2. **Cheap capture (per-issue, here in this spawn)** — Step 1, cheap branch. An already-running session, golden tests, or an already-installed headless browser. Run it now.
3. **Heavy capture (deferred, NOT here)** — Step 1, heavy branch. A path that boots a simulator/emulator or does a full build, or a discovered project visual-QA command. **Do not run it per-issue** — booting a simulator once per reviewer is wasteful. Record it; the orchestrator runs it **once** in the batched visual pass at feature-end (`algorithm.md` §15.4).

---

## When this runs (the orchestrator already decided)

`{{UI_DIFF}}` lists the UI surfaces the diff touched (see `gates.md` §2.5 for the classification). If it is `none`, you never reached this file. If it is non-empty, walk the protocol below — but be cheap about it.

## Tool carve-out (still read-only on source)

For this protocol only, you may go beyond the read-only command set in `reviewer.md`:

- Use `Bash` to **probe** for an already-running app / dev server and to capture screenshots via a tool the project already provides.
- Use the dart MCP tools (`widget_inspector`, `flutter_driver_command`) against an **already-running** Flutter session.
- Use a repo-local headless-browser CLI (Playwright, Puppeteer, `shot-scraper`) if one is already installed.

Hard limits — these keep the step resource-bounded and keep you a reviewer, not an editor:

- **Never edit source, tests, or config.** Screenshots are inspection, not mutation.
- **Never `git`-mutate** (no add/commit/checkout/stash). Same rule as the rest of the review.
- **Do not build infrastructure speculatively.** Never boot a simulator/emulator, never run a full build, never `flutter run` just to look. Heavy paths are the batched pass's job, not yours (see tier 3 above).
- **Cap the capture.** A handful of screenshots for the changed surface(s) — not a full app crawl.
- **Tear down anything you started.** If you launched a process, stop it before returning.

## Step 0 — Code-level checks (screenshot-free, always, cheapest)

Before any capture, resolve as much as possible by reading code — this is free and often decisive:

- **Sibling / peer component comparison.** Find the nearest already-existing component of the same kind (the other card in the same list, the sibling screen, the row next to the changed one) and diff the changed widget against it: same typography ramp (`titleSmall` / `w700`), same spacing tokens, same alignment, same padding scale. A new card whose headline uses a different text style than its siblings is a **declared-by-precedent** mismatch — the codebase *is* the spec here.
- **Design-token usage.** The changed widget uses the project's tokens (theme text styles, spacing/colour tokens) rather than hardcoded values, per `CLAUDE.md`. Hardcoded sizes/colours where tokens exist is a finding even without a screenshot.
- **Obvious layout smells in code** — a `Column`/`Row` `crossAxisAlignment` that contradicts the declared intent (e.g. `start` where the design wants centred), a fixed height that will clip dynamic text, a missing `Expanded`/`Flexible`.

Many issues (the HellerIO headline-alignment case among them) are fully resolvable here. Record findings now; only proceed to capture for what code reading cannot settle.

## Step 1 — Resolve the capture path (cheap = now, heavy = defer)

Read the resolved `visual:` line from the gate config (`{{GATE_COMMANDS}}` contains it; `gates.md` §1 explains how the orchestrator resolved it). It is one of:

- `visual: skip` → the user opted out of capture. Record `visual-review: skipped (config: skip)` as a SUGGESTION and stop after Step 0. No probing.
- `visual: <command> [heavy]` → a sanctioned or discovered project command. If tagged **heavy** (boots a simulator/emulator or does a full build), **do not run it here** — record `visual-review: deferred to batched pass (<command>)` as a SUGGESTION; the orchestrator will run it once at feature-end. If it is *not* heavy (a fast headless screenshot script), run it now.
- `visual: auto` → no command resolved; best-effort **cheap** probe only, taking the **first** that is already available:

  **Flutter**
  1. A running app/session reachable via the dart MCP → use `flutter_driver_command` to screenshot the changed screen, or `widget_inspector` to read the rendered tree (sizes, colours, text, overflow).
  2. The project has **golden tests** covering the changed widget → run them (read-only, no `--update-goldens`); a golden failure is direct visual evidence.
  3. Neither is cheaply available → **defer to the batched pass** if a heavy path exists, else record `visual-review: skipped (no cheap capture path)` as a SUGGESTION. Never boot a simulator here.

  **Web**
  1. A dev server already running, or a built `dist/`/`build/` present, **and** a headless-browser CLI already installed → screenshot the changed route(s).
  2. Neither → **skip** with a SUGGESTION (`visual-review: skipped (no server/build + no screenshot tool)`).

Inability to capture is **never a BLOCKER** — it is a project-infrastructure gap, not a defect in the diff. Say so in one SUGGESTION line and rely on Step 0 plus the code-level UI inspection you already do.

## Step 2 — Resolve the expectation (what "correct" means)

Compare the captured (or code-read) state against the strongest expectation available, in this order:

1. **Declared visual expectations in the issue** — a `## Visual expectations` / `## Design reference` section, a referenced Figma node-id, or visual bullets in the acceptance criteria. This is the contract.
2. **Peer components already in the codebase** — the sibling card/row/screen of the same kind (Step 0). Established precedent is a binding expectation: a new component must match the visual language its siblings already set.
3. **Referenced design assets** in the feature dir — mockups, a Figma export, design tokens named in the issue.
4. **Project design language** — design tokens / spacing scale / typography in `CLAUDE.md` or a design-language doc; the `flutter-design-language` anti-slop principles if present.

If the issue is a frontend change but declares **no** visual expectation, has **no** comparable sibling, and the project has no design language, limit yourself to objective defects (overflow, clipped text, invisible/contrast-broken elements, obviously broken layout) — everything else is a SUGGESTION.

## Step 3 — Grade against the existing blocker philosophy

The reviewer's rule holds: **style is never a blocker; an unmet declared criterion is.** Apply it to pixels:

**BLOCKER** (visual)
- A **declared** visual expectation (issue / Figma / design tokens) is not met — wrong spacing scale, wrong token colour, component state missing, layout differs from the referenced design.
- A **divergence from an established sibling** of the same kind without a documented reason — the new card's headline style differs from its peers, breaking the codebase's own precedent.
- An **objective rendering defect** regardless of any spec: overflow / clipped or truncated text, element off-screen or zero-size, unreadable contrast, a control that does not render.
- A golden test fails on the changed surface.

**SUGGESTION** (visual)
- Polish with no declared expectation and no sibling precedent ("could breathe more", "this hue feels off") — taste, not contract.
- A nicer-but-equivalent layout, optional animation, micro-alignment within tolerance.
- Capture was skipped or deferred (record which branch of Step 1 applied).

"Perfectly fulfils the principle" only escalates to BLOCKER when the principle was **declared** somewhere the worker was bound by — including the precedent its sibling components set. Absent that, hold it as a SUGGESTION — do not invent a spec to fail the diff against.

## Step 4 — Fold into the single status line

This protocol does not add a new return format. Feed its findings into the reviewer's existing output:

- Visual BLOCKERs go into the `BLOCKERS:` list with a `[screen/route]` locator instead of `path/file:NN` where a file line is meaningless (e.g. `[screen: SavingsGoalCard]`) — but cite `path/file:NN` for code-level Step 0 findings, which do have a line.
- Visual SUGGESTIONs (including every skip and every deferral to the batched pass) go into `SUGGESTIONS:`.
- If a check confirmed the declared expectation, mention it in the `APPROVED:` one-liner (e.g. `APPROVED: … headline style matches sibling breakdown_card`).

Keep it to the one status line plus the two lists — no embedded images, no long prose, no pasted screenshots into the orchestrator.
