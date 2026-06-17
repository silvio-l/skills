# Visual Review — Conditional UI Verification

Loaded by the reviewer **only** when the orchestrator passed a non-empty `{{UI_DIFF}}`. For a backend-only diff this file is never read and costs nothing.

Goal: confirm that a frontend change does not merely compile, but **looks the way the plan said it should** — and, where the plan declared a visual expectation, that it fulfils it precisely, not just approximately.

This protocol runs **inside the existing reviewer spawn** (no extra sub-agent). The reviewer is still read-only with respect to source files — see the carve-out below.

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
- **Do not build infrastructure speculatively.** Prefer an already-running instance or an existing golden/screenshot test. Only launch an app or dev server yourself if the project provides a documented, cheap run target (see `visual:` config below).
- **Cap the capture.** A handful of screenshots for the changed surface(s) — not a full app crawl.
- **Tear down anything you started.** If you launched a process, stop it before returning.

## Step 1 — Resolve the capture path (cheapest first)

Read the `visual:` line from the resolved gate config (`{{GATE_COMMANDS}}` already contains it):

- `visual: skip` → the user opted out of visual capture. Record `visual-review: skipped (config: skip)` as a SUGGESTION and stop. No probing.
- `visual: <command>` → a project-supplied capture command (e.g. a golden-update-free screenshot script, a `flutter test --update-goldens`-free golden run, a `shot-scraper` invocation). Run it; it is the sanctioned, cost-bounded path.
- absent / `auto` → best-effort probe, in this order, taking the **first** that is cheap:

  **Flutter**
  1. A running app/session reachable via the dart MCP → use `flutter_driver_command` to screenshot the changed screen, or `widget_inspector` to read the rendered tree (sizes, colours, text, overflow).
  2. The project has **golden tests** covering the changed widget → run them (read-only, no `--update-goldens`); a golden failure is direct visual evidence.
  3. Neither, and launching is not cheap → **skip** with a SUGGESTION (`visual-review: skipped (no running session, no goldens)`). Do **not** spin up `flutter run` just to look.

  **Web**
  1. A dev server already running, or a built `dist/`/`build/` present, **and** a headless-browser CLI already installed → screenshot the changed route(s).
  2. Neither → **skip** with a SUGGESTION (`visual-review: skipped (no server/build + no screenshot tool)`).

Inability to capture is **never a BLOCKER** — it is a project-infrastructure gap, not a defect in the diff. Say so in one SUGGESTION line and fall back to the code-level UI inspection you already do.

## Step 2 — Resolve the expectation (what "correct" means)

Compare the captured state against the strongest expectation available, in this order:

1. **Declared visual expectations in the issue** — a `## Visual expectations` / `## Design reference` section, a referenced Figma node-id, or visual bullets in the acceptance criteria. This is the contract.
2. **Referenced design assets** in the feature dir — mockups, a Figma export, design tokens named in the issue.
3. **Project design language** — design tokens / spacing scale / typography in `CLAUDE.md` or a design-language doc; the `flutter-design-language` anti-slop principles if present.

If the issue is a frontend change but declares **no** visual expectation and the project has no design language to check against, limit yourself to objective defects (overflow, clipped text, invisible/contrast-broken elements, obviously broken layout) — everything else is a SUGGESTION.

## Step 3 — Grade against the existing blocker philosophy

The reviewer's rule holds: **style is never a blocker; an unmet declared criterion is.** Apply it to pixels:

**BLOCKER** (visual)
- A **declared** visual expectation (issue / Figma / design tokens) is not met — wrong spacing scale, wrong token colour, component state missing, layout differs from the referenced design.
- An **objective rendering defect** regardless of any spec: overflow / clipped or truncated text, element off-screen or zero-size, unreadable contrast, a control that does not render.
- A golden test fails on the changed surface.

**SUGGESTION** (visual)
- Polish with no declared expectation ("could breathe more", "this hue feels off") — taste, not contract.
- A nicer-but-equivalent layout, optional animation, micro-alignment within tolerance.
- Capture was skipped (record which branch of Step 1 applied).

"Perfectly fulfils the principle" only escalates to BLOCKER when the principle was **declared** somewhere the worker was bound by. Absent that, hold it as a SUGGESTION — do not invent a spec to fail the diff against.

## Step 4 — Fold into the single status line

This protocol does not add a new return format. Feed its findings into the reviewer's existing output:

- Visual BLOCKERs go into the `BLOCKERS:` list with a `[screen/route]` locator instead of `path/file:NN` where a file line is meaningless (e.g. `[screen: SavingsGoalCard]`).
- Visual SUGGESTIONs (including every skip) go into `SUGGESTIONS:`.
- If visual capture confirmed the declared expectation, mention it in the `APPROVED:` one-liner (e.g. `APPROVED: … visual matches declared design tokens`).

Keep it to the one status line plus the two lists — no embedded images, no long prose, no pasted screenshots into the orchestrator.
