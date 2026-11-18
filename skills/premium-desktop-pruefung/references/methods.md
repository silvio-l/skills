# UI/UX examination methods

Use `criteria.json` as the criterion register. Its summaries are original operational guidance, not replacements for linked standards. Load only the methods and criteria needed for an assigned unit. Simplicity and successful work take precedence over decoration. Aesthetic preference is not a normative defect. This skill audits and prepares issues in the repository's designated ledger; it does not implement corrections.

## Scope and unit construction

Before judging quality, identify audience, actual core tasks, supported environments and first useful result. Trace repository manifests, release targets, routes, windows, menus, tray surfaces, dialogs, generated screens, translations, feature flags, roles, persisted preferences, shared components, dependencies and content supplied remotely. Reconcile source discoveries with documentation and a runtime tour. Unavailable generated or remote content is an explicit gap. A filename scan is only a discovery aid.

Create stable semantic unit identifiers from surface/task, criterion, state and relevant variant, not line numbers. Keep relationships to parent surfaces, shared implementations and transition endpoints. Record direct entry, deep links, back/forward, reopen, refresh/restart and alternate command routes. For each task enumerate initial, empty, loading, populated, selection, validation, error, permission denied, offline, stale, cancellation, success and recovery states where meaningful. Distinguish new, existing and upgraded profiles. Every claimed inapplicability requires a product fact and bounded scope.

Record supported OS/browser, window size, zoom/scaling, theme, locale/direction, input method, assistive technology, role/flags and realistic data volumes. Split variants whenever they can fail independently. An equivalence group requires evidence of the same relevant implementation AND behavior plus explicit boundary checks; shared CSS alone is insufficient. Pairwise sampling can find defects but cannot silently mark untested combinations passed. Unbounded data spaces require documented equivalence partitions and boundary values, never a claim that every possible input ran.

The 12 dimensions are: 01 layout/order; 02 hierarchy/orientation; 03 typography/readability; 04 color/visual expression; 05 information architecture/navigation; 06 language/mental models; 07 interactions/tasks; 08 states/errors; 09 component consistency; 10 adaptation; 11 accessibility; 12 overall perceived quality. Evaluate every dimension's applicability for each surface and flow. All 55 WCAG 2.2 A/AA criteria must receive applicability decisions; absence of media can justify media exclusions, default screen-reader scope does not exclude accessibility criteria wholesale. Record supported assistive technology from existing sources without running or installing a screen reader.

## Evidence contract and safe execution

Every result identifies repository revision and dirty state, build, environment, dataset/profile, preconditions, exact ordered actions, expected and observed result, criterion, primary artifact and countercheck. Preserve line references with revision and artifact hashes. Screenshots require actual size, viewport/window geometry, theme and state. A screenshot proves appearance, not persistence, keyboard order or successful screen-reader operation. Tests require command, tool/version, exit status and relevant output; a planned test is not evidence.

Read launch scripts and hooks before running repository code. Choose proportionate execution controls under agents.md and platform-compatibility.md: an identified reviewed product may run on the current host with disposable profiles, synthetic data, isolated test accounts and explicit network destinations; do not execute unknown install hooks or download competitor executables merely for an audit. Preserve the target checkout; keep generated audit output and temporary profiles outside it. Browser actions can change remote state: restrict them to authorized test systems. Enforce wall time, process termination and available memory/CPU/network controls using the actual environment. A timeout is not a security sandbox. If a runner fails, assess the current host and available local/authorized remote alternatives before declaring that method blocked. Required containment for unknown code must actually work; ordinary reviewed product testing does not require a named testlab. Continue other executable methods and safe source analysis. Do not substitute source inspection for missing runtime evidence. Never send application secrets or customer data into evidence or external services.

## M1 — Trace the implementation contract

1. Follow a surface from entry declaration to renderer, shared component, state/store, request and persistence; include alternative target implementations.
2. Compare documented behavior with event handlers, permission checks, configuration defaults, translations and error branches.
3. For each state transition, identify input, guard, output and retained user work. Search callers of shared components and duplicate local implementations.
4. Record exact source locations and unresolved runtime hypotheses; inspect at least one alternative caller as a counterexample.

Deliver a source-to-unit map and transition list. A provable unreachable branch or contradictory stored key can support a source fact; it does not establish visual quality. Typical faults: divergent settings stores, unreachable error recovery, missing feature-flag route. Recommend a concrete shared cause investigation in the issue, not an unapproved patch.

## M2 — Task-based cognitive walkthrough

1. Express a realistic goal using the target audience's vocabulary and state their prior knowledge. Establish success before opening the application.
2. At each step record whether the goal suggests the next action, whether the control can be found, whether its label predicts its effect and whether feedback makes progress visible.
3. Traverse the normal path and a plausible wrong turn; recover without private implementation knowledge. Repeat the first task without onboarding hints.
4. Count only observed steps, backtracks, hidden prerequisites and remembered facts. Compare with an available alternative task path; do not equate fewer clicks with less cognitive work.

Keep action log and annotated screens. Report jargon, ambiguous icons, scattered prerequisites and unnecessary decisions as reasoned heuristic concerns tied to specific users. A developer or AI walkthrough is not empirical proof of intuitiveness. Optimize labels, grouping and progressive disclosure while retaining discoverability.

## M3 — Inspect the rendered composition

1. Capture the real first-use, core-work and settings surfaces at actual supported usage size, not marketing mockups.
2. Identify primary working object, essential context and next meaningful action. Trace headings, aligned edges, proximity groups and data comparisons.
3. Compare equivalent objects across at least two contexts and relevant themes. Inspect long names, varied numeric widths, empty and selected states.
4. Trace suspected inconsistent roles to design tokens/components, then look for a justified semantic or platform difference.

Deliver matched captures and the specific task consequence. Check unnecessary cards, competing accents, weak hierarchy, clipped metadata, misleading colors and inconsistent states. Recommend changes to information priority or shared semantics. Do not require a sidebar, right panel, pastel palette, rounded corners or a fashionable framework. Dense professional tools and full-surface editors can be appropriate. No universal spacing, font-size or density score is invented.

## M4 — Exercise state and interaction chains

1. Execute normal, cancel, repeat and error/retry paths with controlled data. Include keyboard and pointer routes to the same outcome.
2. Simulate supported latency/offline/denied permissions in the isolated environment. Check feedback, retained input, focus, selection and duplicated actions.
3. Trigger rapid selection changes and out-of-order responses when possible; navigate away and return during ongoing work.
4. Compare final persisted result with the displayed result, then restart or reopen. Run an unaffected sibling operation as negative control.

Preserve chronological actions, state captures and relevant trace. Faults include stale detail, duplicate submissions, lost input and false success. Recommend explicit state ownership, recoverable feedback and safe retries. A noncancelable atomic operation is permissible when justified; do not demand fabricated progress percentages for unknown work.

## M5 — Adaptation and volume sweep

1. Derive tested bounds from supported targets and product tasks. Test typical and smallest supported windows, boundary points where navigation/panels wrap, and larger windows.
2. Exercise browser text resize to 200% and reflow at 320 CSS pixels wide (or 256 high for horizontal writing flow as applicable); inspect WCAG definitions and legitimate two-dimensional content exceptions. For native software, document WCAG2ICT interpretation and test OS scaling/text preferences.
3. Repeat critical states with long localized strings, RTL where supported, realistic large datasets, themes, high contrast and reduced motion.
4. Resize during selection/editing and reopen with changed display geometry. Confirm collapsed content remains accessible and focus stays useful.

Contrast across states (rendered pages): evaluate `scripts/contrast_sweep.js` in the page (Playwright `page.evaluate`, or any tool that evaluates a page expression) per state and theme, save its JSON and run `probe.py sweep FILE`. Trap: an ancestor's `opacity` fades the whole subtree, background *and* text. Folding opacity into the text color only, against an unfaded background, misstates faded and disabled controls; the sweep composites both through the full ancestor chain. It flags background images/gradients, filters, blend modes and text shadows as `uncertain` and disabled controls as `exempt-candidate` (inactive components are exempt from 1.4.3; verify they are truly inactive). Overlapping non-ancestor layers still need a pixel check on a screenshot.

Record geometry, scale, data volume and paired state evidence. A supported-platform minimum does not cancel a relevant WCAG reflow obligation. Exceptions apply to the necessary two-dimensional region, not all surrounding controls. Diagnose clipping, horizontal scrolling of ordinary text, offscreen restored windows and task-blocking performance with environment-specific measurements; do not invent a universal latency budget.

## M6 — Accessibility, beyond an automated scan

1. Evaluate every applicable A/AA criterion in `criteria.json` against its full official definition, exceptions and dependencies. Native adaptations use WCAG2ICT and platform guidance; record the interpretation separately.
2. On each distinct interactive state, use available automated rules and preserve tool version, rule configuration, excluded nodes, violations and incomplete/manual-check results. Inspect each result in context.
3. Starting without a pointer, complete tasks using Tab/Shift+Tab and the widget's expected keys. Record order, focus visibility, traps, modal entry/exit, sticky-overlay obstruction and shortcuts inside text fields.
4. Inspect accessible names, roles, values, relationships and live updates using the browser or OS accessibility tree. Screen-reader execution is an optional extension, enabled only by an explicit user request (see below).
5. Measure text and meaningful nontext contrast for actual composited foreground/background across states. Use WCAG's luminance algorithm and exact thresholds: ordinary text 4.5:1; qualifying large text 3:1; relevant nontext 3:1. Do not round 4.499 upward or substitute APCA for WCAG AA. Check exemptions against the standard.
6. Measure pointer targets and spacing using the exact 2.5.8 alternatives/exceptions; 24 CSS pixels is not a universal mandate for all visible elements. Check dragging alternatives, authentication assistance, redundant entry, captions/media alternatives and time limits where applicable.
7. Countercheck automatic findings against native semantics, hidden/disabled state and applicable exceptions. Also inspect a state the scanner never visited.

Screen-reader extension: do not run, install, configure or delegate a screen reader by default, including during counterchecks or retests. Record `screen-reader execution: not requested; outside scope` in `profile.scope` and the report, backed by the audit request and this default. For `UX-11-assistive-task`, record an evidenced, independently reviewed `excluded` disposition with this scope reason; never call it passed or technically inapplicable. Do not create jobs, repeated opt-in questions or product-defect issues solely for the omitted extension. For other criteria, perform the applicable non-screen-reader methods; where these cannot establish the criterion, retain a blocked/uncertain result with its evidence limit rather than claiming a pass. No blanket WCAG conformance claim follows from this scoped audit. If explicitly requested, run core tasks and error/recovery with the supported reader, record output and version, and keep unavailable requested checks blocked.

A clean axe run, valid ARIA or passing contrast alone never proves WCAG conformity. Web conformity also requires complete pages/processes, accessibility-supported technology and non-interference; a repository report is not a certification. WCAG2ICT is informative, so do not claim native software formally conforms to a separate WCAG2ICT standard.

## M7 — Empirical evidence, when available

Define audience, task, context, success and protocol before collecting data. Observe consenting representative users without leading instructions; record completion, errors, recovery, time where relevant and participant feedback. For workload, a properly administered instrument such as NASA-TLX can supplement task outcomes. Distinguish raw and weighted procedures. Preserve privacy and note sample limitations, prior experience and facilitator effects. Compare conditions only when protocol supports the comparison. Never manufacture participants, satisfaction scores, cognition measurements or statistical significance. If no user study exists, label perceived simplicity, premium appeal and mental-model fit as hypotheses supported by a walkthrough, not observed audience perception.

## M8 — Independent challenge

A fresh reviewer first reconstructs candidate surfaces and paths from primary source, manifests and runtime entry points without reading the examiner's conclusion. Then reconcile inventories, inspect excluded variants and trace every claimed confirmed finding to raw artifacts. Attempt the strongest alternative explanation: intended product behavior, different scope, native semantics, stale build, test contamination or an allowed exception. Reproduce the original and a falsifying counterexample. Check apparently clean high-risk paths as well as findings. Record confirmed, refuted and unresolved outcomes with reasons. Challenge insufficient depth and missing states as explicit follow-up jobs. If a separate agent is unavailable, use a separate evidence-first pass and disclose that it is not independent personnel validation.

## M9 — Desktop, first use and settings

Apply the DES, ON and SET criteria when their product features exist. Operate native menus, shortcuts, window controls, applicable file dialogs, clipboard and context commands on the actual target OS. Compare pointer and keyboard paths, especially with text focus. Reopen after monitor/scaling changes and verify retained list filters, scroll, selection and focus after dialogs.

For onboarding, use a fresh disposable profile; follow permissions, skip optional steps, interrupt each distinct exit state, then achieve a real reusable result. Compare subsequent and upgraded profiles. Check that setup preferences can be changed later and affect the actual task through the same stored value.

For settings, enumerate every option and classify persistent preference, session decision, command or OS responsibility. Test realistic lookup questions, category paths and search synonyms when search exists. Check precise result focus and return position, appropriate control semantics, scope/overrides, save failures, restart effects, unavailable resource fallback and isolated reset. Use synthetic work to prove preference reset does not delete unrelated content. Immediate application suits independent reversible values; coherent transactional groups may legitimately require Apply/Cancel. Additional search/navigation layers require a real volume or task justification.

## Findings and issue handoff

Separate observed deviation, user consequence, proposed cause and recommendation. Use an ordinal priority based on blocked task/access, exposure, frequency, recovery and loss potential; explain the judgment without a weighted quality score. A shared cause may consolidate issues only while preserving every affected unit/variant. Keep refuted suspicions and their counterevidence in the audit record.

Use the repository's configured ledger/forge and its issue conventions. Prepare reproducible steps, revision/environment, criterion, evidence references, impact, concrete recommendation and acceptance/retest steps. Search existing ledger entries for duplicates and link instead of multiplying them. Missing ledger access is an explicit handoff limitation, not successful issue publication. Do not alter target source or implement the recommendation. When a separately supplied corrected build is audited, repeat the original reproduction, its countercheck and relevant sibling/variant regressions; runtime and visual evidence must refer to that build.
