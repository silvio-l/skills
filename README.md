# Skills

My personal Claude Code skills. Engineering process, context hygiene, and AI-agent maintenance — distilled into composable skills, straight from my `.claude` directory.

## Quickstart

```bash
npx skills@latest add silvio-l/skills
```

Pick the skills you want and the agents you want to install to. The installer is the generic [`skills` CLI by Vercel Labs](https://github.com/vercel-labs/skills) — the same one Matt Pocock uses.

## Updating

After new versions land upstream, refresh your local copy:

```bash
npx skills@latest update                 # interactive: picks scope, lists changes
npx skills@latest update -g              # all global skills, no prompts
npx skills@latest update -g ratchet-up   # one specific skill
```

The CLI tracks where each installed skill came from and pulls only what changed — across this repo, Matt's, and any others you have installed.

## Prerequisites: install Matt Pocock's skills first

These skills are built on top of the conventions, vocabulary, and issue formats produced by [`mattpocock/skills`](https://github.com/mattpocock/skills). **Install Matt's skills first** — several of mine consume what his produce.

```bash
npx skills@latest add mattpocock/skills
# then, inside an agent session:
/setup-matt-pocock-skills
```

Which of mine depends on which of Matt's:

| My skill | Depends on Matt's |
|---|---|
| `ratchet-up` | `/to-issues`, `/triage`, and the issue-tracker config from `/setup-matt-pocock-skills` |
| `domain-glossary` | `/grill-me` (mandatory in the interview loop); extends the `CONTEXT.md` philosophy from `/grill-with-docs` |
| `full-quality-scan` | parallel-subagent dispatch pattern shared with Matt's process-oriented skills |
| `context-optimization-audit` | audits the loaded surface, including Matt's installed skills |

If you only want one of these, skip the dependencies you do not exercise.

## The skills

### `apple-notes`

**The Problem.** Non-technical collaborators write bug reports, ideas, and feedback wherever it is comfortable — for me, that is Apple Notes. The agent cannot reach into Notes; the human cannot reach into the issue tracker. The result is a swamp of half-captured intent that never makes it into a session.

**The Fix.** A single dispatcher (`scripts/apple-notes`) wraps AppleScript to read, search, write, and image-extract from Notes on macOS. Subfolders of one configured "company folder" map to projects (auto-resolved from the current git repo). Each project enforces a four-folder layout — `inbox` / `ready` / `done` / `docs` — with title prefixes (`BUG:` `FEAT:` `IDEA:` `FB:` `TECH:`) so the partner drops things in `inbox`, the agent triages from there, and nothing has to leave Notes until it is ready to become a real issue. Note titles are just the first body line, which Apple Notes truncates with an ellipsis — so when a collaborator dumps everything into the first line, the dispatcher still resolves the note from the truncated title, a prefix, or its stable `id` (exposed in `notes --json`).

### `aso-research`

**The Problem.** ASO tools (AppTweak, Sensor Tower) sell competitor intelligence and keyword difficulty behind a recurring SaaS subscription, lock the "real" data in proprietary panels you cannot reproduce locally, and hand out generic advice disconnected from your own app's competitive reality. You want to know how rivals position themselves and which keywords they fight for *before* you write your store listing — without a subscription or a cloud dependency.

**The Fix.** A local, deterministic, macOS-only research pipeline (`/aso-research`) that turns a structured app-idea input into an evidence-based ASO report. Deterministic Python stages (run via `uv`) collect public competitor intelligence and compress it; the LLM only interprets the compressed, token-budget-gated result — it never does the data collection. Official public APIs first (iTunes Search, Apple RSS, Reddit `.json`), Playwright only where the API genuinely has nothing, a shared HTTP cache (`~/.cache/aso-research/`, 24h TTL) for resumability, and transparent proxy scores that are honest about being *signals, not real search volume*. Keyword extraction (YAKE + TF-IDF) and the full 8-section report land in later slices; the skeleton slice already proves the Apple-only iTunes→artefact loop end to end.

### `context-optimization-audit`

**The Problem.** Claude Code loads everything in sight — skills, MCP servers, plugins, project instructions. Over time the context turns into a buffet. You lose tokens, signal-to-noise drops, and the model gets distracted.

**The Fix.** Audit every loaded surface — skills, agents, slash commands, MCP/plugin config, project files — and propose what to cut, merge, condense, disable, or move. Nothing is changed without your approval; the skill produces a plan first.

### `domain-glossary`

**The Problem.** Devs and domain experts speak different languages. So do agents and the projects they wake up in. You burn tokens explaining the same nouns every session.

**The Fix.** Build a `CONTEXT.md` collaboratively. The glossary is the artifact; the real work is getting the language right. Lifts Matt's "shared language" idea from `/grill-with-docs` and turns it into an explicit, repeatable authoring loop.

### `full-quality-scan`

**The Problem.** "Run all the linters" is fine until a scanner returns 200 findings and the agent tries to fix them inside a single context. Halfway through, you run out of room and lose the rest.

**The Fix.** A threshold: ≤10 findings → fix directly. >10 → produce a plan first, then dispatch parallel subagents per finding cluster. Each subagent works in isolation; the orchestrator never holds the full pile in one head.

### `openai-image`

**The Problem.** Generating an image from a prompt always means re-deriving the same boilerplate: which OpenAI model supports transparency, how the key is loaded, how to retry a flaky 429, how to decode the base64 to a file. Every project reinvents it, and the API key ends up copy-pasted into yet another script that risks getting committed.

**The Fix.** One self-contained Node script. It picks the model automatically — `--transparent` ⇒ `gpt-image-1` (the only one with an alpha channel), everything else ⇒ the higher-quality `gpt-image-2` — resolves the API key from its own gitignored `.env` (or the shell env), retries transient 429/5xx/network errors with exponential backoff, and writes PNG(s) to disk. No project dependencies; usable from any directory. `--dry-run` validates the resolved config for free before spending a credit.

### `ratchet-up`

**The Problem.** An agentic loop that grinds through issues sounds great until you realize each iteration drags the whole feature's state back into the orchestrator's context. Six issues in, you are hallucinating dependencies that do not exist.

**The Fix.** A context-safe ratchet — discover ready issues, respect `blocked-by`, dispatch isolated workers and read-only reviewers, gate on format/analyze, persist rework feedback to disk. The orchestrator stays small; the work moves forward one click at a time, never backward. For frontend diffs it also verifies the rendered UI against the plan's visual expectations in three cost tiers: screenshot-free code-level checks (incl. sibling-component comparison) per issue, cheap capture (running app, goldens, installed browser) per issue, and a heavy capture path (simulator boot or a discovered visual-QA command) batched into one pass at feature-end — so backend work pays nothing and no simulator boots more than once.

### `humanize-text`

**The Problem.** AI-generated text in German and English bleeds through the same hollow openers, inflation particles, and filler verbs — „Zudem", „Darüber hinaus", „Es ist wichtig zu beachten", "delve", "leverage", "seamlessly" — regardless of topic. But the academic-slop lexicon misses modern *marketing* copy entirely: punchy landing pages pass a naive scan with 50/50 while reading like a generated press release, because their tells are **structural** — the "Kein X. Kein Y. Nur Z." staccato, the "— groß, klar, motivierend" adjective burst, the em-dash flood — not vocabulary.

**The Fix.** A bilingual (DE/EN), offline, deterministic slop pipeline with three modes. `--mode scan` matches every file against curated tier-1 DE/EN lexica (word-boundary, case-insensitive, with opt-in `inflect` stemming for German declension) plus language-neutral structure tells: **anaphora** (repeated sentence openers) and the **clause-final adjective tricolon** are high-confidence tier-2 detectors that always surface, while **em-dash over-use** is scored by *density* (a single dash is free; a peppered text is dragged down) — a 2026 rework driven by Wikipedia's "Signs of AI writing", Pangram, and German sources. It auto-detects language, handles `.md`, `.html`, `.astro`, and `.ts` filetypes with appropriate strip strategies, and returns sorted findings with replacement suggestions. `--mode score` runs the five-dimension scorer (directness, rhythm, trust, authenticity, density; 50 pts max) over *prose only* — UI labels are excluded so a slop-dense paragraph is not diluted by nav strings, and rhythm is held neutral for fragment `.ts` dictionaries — and exits 1 below threshold (default 37/50), wiring into `ratchet-up` gates in one line. `--mode rewrite` is an agent-side protocol: the script findings drive a targeted LLM rewrite pass that protects proper nouns (loam, whispaste, hellerio) and technical terms, invents nothing, and waits for explicit user confirmation before changing any file.

### `seo-audit`

**The Problem.** SEO audits collapse into three failure modes: paid tools you do not want to depend on (Ahrefs, Semrush, Screaming Frog Pro), one-off shell hacks that nobody re-runs because they are not reproducible, and brand-voice drift — plus increasingly a GEO/AEO blind spot: your site is technically correct but AI search engines cannot cite you because there is no About page, no citable prose, no structured FAQ, and no JSON-LD markup telling them what your entity even is.

**The Fix.** A local-first, free-tier-only audit skill that runs the same eight-phase pipeline every time: inventory → brand scan (anti-vocabulary from `CONTEXT.md`) → GEO/AEO scan (entity page, citable prose, FAQ structures, heading hierarchy, `llms.txt`) → JSON-LD schema audit (presence, required fields, deprecated types, sameAs consistency) → external probes (Lighthouse, pa11y, GSC, W3C, Observatory, PageSpeed) → synthesis (per-dimension `/100` headline score via versioned `DIMENSION_WEIGHTS_V1`) → report. Findings are split into *Strategisch* (content decisions you must make) and *Technisch* (copy-paste fixes), with ready-to-use JSON-LD and `llms.txt` snippets in the report. An optional `--brief <path>` provides brand context for the recommendation section without affecting scores. Optional `--push` (IndexNow, Bing, `llms.txt` generation) is confirmation-gated per operation.

### `to-roadmap`

**The Problem.** A raw idea document or rough PRD is too big to feed straight into `/to-prd` — the agent either drowns in scope or quietly skips half the features. And once a roadmap exists, mid-flight changes (new sprint, split, drop, reorder) tend to fragment it instead of staying coherent. There is no upstream layer that owns the roadmap as a living artifact.

**The Fix.** Three operations on `.scratch/roadmap.md`: `create` decomposes the idea document into ~100k-token sprints with stable Sprint-IDs, dependencies, MVP cut, and later-release ordering; `update` patches the roadmap surgically from a free-text instruction with a diff-plan-then-confirm flow; `status` flips a sprint through `todo → in-progress → done`, called manually or automatically by `ratchet-up` at the start and end of a loop. One sprint at a time later becomes one PRD via `/to-prd`.

### `ship-to-appstore`

**The Problem.** Publishing a Flutter app to the Apple App Store is a long, error-prone path with many interdependent steps — bundle ID, certificates, provisioning, versioning, archive, upload, TestFlight, store metadata, privacy labels, age rating, export compliance, in-app-purchase submission state, review submission. Apple changes requirements continuously (minimum Xcode/SDK versions, screenshot sizes, privacy rules), so even a correct guide from six months ago can be wrong today. The solo-dev gets lost in Apple's documentation, misses mandatory steps, and never knows exactly where in the process they stand.

**The Fix.** An interactive, step-by-step guided release skill — grill-me style for release steps, not a wall of text. Phase 0 runs a deterministic introspection script that reads `pubspec.yaml` and the iOS project to extract a structured situation report (bundle ID, marketing version, build number, Team ID, signing style, icon-set completeness, launch assets, analytics/ATT SDKs, account-deletion flow, **In-App Purchase usage**) and aborts cleanly on non-Flutter repos. Phase 1 web-searches for current Apple requirements before suggesting any step — nothing from training memory. Phase 2 discovers ASC credentials from the repo/environment and queries the live app record via a **bundled read-only `asc-status` script** that hits the modern `reviewSubmissions` resource and **both** IAP namespaces (non-consumables *and* subscriptions — a single-namespace query silently misses subscriptions) with per-product App Review screenshot presence. Phase 3 presents one release step at a time, waits for "done" or "stuck here", and only advances when the user confirms — with a hard pre-submit gate that every IAP product must be `READY_TO_SUBMIT` (screenshot + metadata complete) and attached to the version, or the build is not submitted (else the Guideline 2.1(b) App-Completeness reject lands). A final **LLM/vision pre-submit gate suite** proactively catches the whole class of reject reasons no API field exposes — one gate per high-frequency Apple guideline, each scoped by Phase 0 facts so it runs only when relevant: price references in visual metadata (2.3.7 — "kostenlos/free" counts), store/review-note claims the code doesn't implement (2.3), privacy nutrition label vs the data the code actually collects (5.1.2), Info.plist purpose strings present/specific/unused (5.1.1/5.1.5), Sign in with Apple when a third-party login exists (5.1.1iv), subscription paywall disclosures + Terms/Privacy links (3.1.2), external-purchase steering for digital goods (3.1.1), Privacy/Support URL liveness (via WebFetch), demo credentials in review notes (2.1), account-deletion depth (5.1.1v), UGC safety controls (1.2), and placeholder/incompleteness (2.1). All hard-won ASC endpoint knowledge — the v1/v2 screenshot false-negative, the deprecated submit endpoint, what the API genuinely can't see (Resolution Center text, privacy label, Paid Apps Agreement, version→IAP attachment) — lives in a dedicated API reference. Beyond guiding the deliberate release, the skill doubles as the place to **cleanly manage ASC API access**: a Step 0 pre-flight gate catches the build-aborting failures (iOS platform not installed, `Podfile.lock` drift) up front; the upload path is the robust `xcodebuild -exportArchive` flow with the silent `manageAppVersionAndBuildNumber` footgun called out; and a second bundled **`asc-submit`** script performs the few high-error-rate ASC *writes* — App Review screenshot upload (for both IAP namespaces), review-note correction, re-submit-after-reject, and publishing an approved version — **dry-run by default**, mutating only with an explicit `--yes` after the user confirms.

### `ship-to-playstore`

**The Problem.** Shipping a Flutter app to Google Play is an ad-hoc, memory-dependent sequence of error-prone steps — keystore signing, service-account JSON setup, AAB build, Play Developer API edits/tracks/releases, Data Safety, target-API-level compliance, Play Billing, content rating. Google changes requirements continuously (target SDK, screenshot specs, policy rules), so even a recent guide can already be wrong. The solo-dev misses mandatory steps, cargo-cults config from Stack Overflow, and never knows exactly where in the process they stand.

**The Fix.** The Android companion to `ship-to-appstore` — the same proven orchestration shape with every store-specific action swapped for its Play Console equivalent. Phase 0 runs a deterministic introspection script that reads `pubspec.yaml`, `build.gradle`, and the Android project to produce a JSON situation report (applicationId, version code/name, keystore facts, Play services, permissions, Play Billing, Data Safety hints, Gradle toolchain). Phase 1 web-searches for current Play requirements before suggesting any step — nothing from training memory. Phase 2 discovers service-account credentials from the repo/environment and queries live Play Console state via a **bundled read-only `play-status` script** (tracks, active releases, IAP catalog, signing enrolment) using RS256-signed OAuth2 JWT — no browser required. Phase 3 guides the full release loop one step at a time — AAB build, signing, upload, track assignment with staged rollout, and commit — using a **bundled `play-submit` script** that is **dry-run by default** and mutates only with an explicit `--yes`. A **pre-submit gate suite** proactively catches the Play Policy reject reasons that are judgements over text, images, and code (Data Safety mismatches, permission over-declaration, subscription disclosure gaps, UGC safety controls, store listing claims) and are invisible to any API query.

### `flutter-design-language`

**The Problem.** A Figma→Flutter pipeline is only as good as the design it carries. Pointed at no deliberate design language, it produces cleanly-packaged slop: the inherited Tailwind `#4F46E5` indigo, default Roboto/Inter, a uniform 16px radius on everything, a centred hero + one purple CTA. The tooling is fine; the taste is missing — and once the tokens exist, the slop is baked in.

**The Fix.** A mandatory Phase-0 gate, before a single Figma variable or `ThemeData` is written. It forces a conscious design plan — a named 4–6 colour palette with rationale, a Display/Body/Utility type pairing off the default-font blocklist, a layout concept, and one *signature* element — then critiques every part of it against a verified AI-slop checklist ("would I land here on any similar brief? → it's a default, not a choice"). Only a plan that passes gets frozen into `design/design-language.md` + a role-named three-tier `design/tokens.json` (light **and** dark). The upstream stage that feeds `figma-to-flutter`.

### `figma-to-flutter`

**The Problem.** "Turn this Figma frame into Flutter" tempts an agent into autonomous codegen: raw `Color(0x…)` literals and magic numbers copied from the design, data-fetching and state stuffed into the widget, component instances guessed at, and the whole thing merged unseen. Figma Code Connect cannot even target Flutter, so the guessing is unbounded.

**The Fix.** An assisted, one-frame-per-run translator with hard rails. It parses the design URL, pulls both `get_design_context` and a `get_screenshot` benchmark, resolves Figma variable *names* (never raw hex/px) onto the project's theme tokens, and writes a single presentation-only `StatelessWidget` that takes its data through the constructor — no Supabase, no `http`, no navigation. A golden test (light + dark) plus `dart analyze`/`flutter test` gate the output, vision-blind details (1px borders, shadow spread) are flagged for review, and nothing is wired into the app until a human OKs it at the explicit review gate. Consumes the tokens produced by `flutter-design-language`.

### `screenshot-review`

**The Problem.** "Review the screens" tempts an agent into two failure modes at
once: it praises politely instead of finding problems — or it turns
"uncompromising" and then hallucinates falsely-precise findings ("set the headline
to 28 px") from a screenshot that carries no px at all. On top of that it does not
know the audience, so every audience-fit verdict is guessed, and once the folder
holds more than a handful of images, each screen drags the whole pile into one
context and the reviewer loses the thread halfway through.

**The Fix.** A standalone audit over a screenshot folder with the discipline of
`ratchet-up`: Phase 0 pulls the app context (audience, purpose, platform, design
system, declared tokens) from `CLAUDE.md`, `design/design-language.md`,
`pubspec.yaml`, and `README`, marks gaps as `UNKNOWN`, and clarifies them in a
feedback loop before a single screen is reviewed. Phase 1 dispatches one read-only
Sonnet subagent per screenshot that audits against a 13-point rubric, writes its
report straight to disk, and returns only a compact score line to the orchestrator —
no full text in active context. The tone stays uncompromising (full severity, "always
dig deeper"), but every finding is anchored in a visible pixel: phrased relatively
instead of falsely-precise, vision-limited calls (1px border, shadow, contrast)
honestly flagged as "low" confidence. Phase 2 aggregates the per-screen reports into
an overall report, including the app-wide consistency patterns that only become
visible in the aggregate. The report format is deliberately machine-parseable (stable
finding IDs, severity enum, imperative recommendations, prioritised worklist) so a
downstream agent — e.g. `/ratchet-up` — can work the findings off without follow-up
questions.

### `owasp-bsi-audit`

**The Problem.** "Audit this against OWASP and BSI IT-Grundschutz" is a task with
no shape until someone decides which of the hundred-plus BSI Bausteine even apply,
what "Schutzbedarf normal" means in practice, and how a solo developer's app
compares to the enterprise-with-an-ops-department the standard assumes. Do it by
hand and you either drown the agent's context in every requirement at once, or
skip the parts of the methodology (Strukturanalyse, Schutzbedarfsfeststellung,
Modellierung) that make a Grundschutz-Check traceable instead of a vibe-check.

**The Fix.** An orchestrator that runs the actual BSI-Standard-200-2 process —
structure analysis, protection-need assessment, Baustein/standard modeling
confirmed with the user before dispatch, then the Grundschutz-Check itself — while
keeping the main context free: one Sonnet subagent per confirmed control group
(a BSI Baustein, an ASVS chapter, a MASVS category, ...) reads its own controls
and the code, judges like a human auditor (not keyword matching), and writes its
findings straight to disk with the mandatory BSI vocabulary (ja/teilweise/nein/
entbehrlich, justified) or the OWASP one (pass/fail/partial/n_a). The catalogs
themselves are machine-fetched from the official upstream sources (ASVS 5.0,
MASVS 2.1, the BSI Kompendium XML, curated NIST SSDF and SLSA subsets) rather than
hand-copied, and re-resolve to whatever the latest version is on each refresh. The
BSI Baustein selection is deliberately narrow — most of the Kompendium's ~111
Bausteine are organizational-governance or physical-infrastructure practices that
don't translate to "check this in the code" for an individual developer; only the
ones describing an actual software artifact survive. The rendered report makes
the methodology itself visible (which Bausteine were applied and what they cover,
what was explicitly out of scope, the full Soll-Ist comparison sorted Basis-before-
Standard in natural requirement order) and ships as a self-contained, badge-
colored HTML report with a one-click "copy an AI-agent fix prompt" button per
finding (or all of them at once) alongside the Markdown report and a prioritized
fix-plan.

### `mail-deliverability-audit`

**The Problem.** A mail domain that "looks configured" — an MX record and maybe an
SPF string copy-pasted from a forum post years ago — still lands in spam, because
deliverability is a checklist of interacting, easy-to-get-subtly-wrong pieces: one
SPF record too many (permerror), a `+all` that lets anyone spoof the domain, DKIM
enabled but never checked, DMARC missing the `rua=` that would show spoofing
attempts, a TLS certificate that silently doesn't match the hostname a client
actually connects to. Since Gmail and Yahoo started enforcing SPF+DKIM+DMARC for
real in 2024, "it sends without erroring" is no longer evidence it's healthy.

**The Fix.** A read-only DNS/SMTP/TLS auditor (`dig` + Python's stdlib `smtplib`/
`ssl`, no paid APIs) that checks MX, SPF (RFC 7208 syntax + the ≤10-lookup limit,
counted recursively through `include:` chains), DKIM, DMARC (RFC 7489), reverse-DNS
(forward-confirmed PTR), STARTTLS/submission-TLS certificate-hostname matching,
a Spamhaus ZEN blocklist check, and the state-of-the-art bonus trio MTA-STS/
TLS-RPT/BIMI — against a single scored report with copy-paste DNS fix snippets for
every gap. Network checks degrade to `n_a` (not a false `fail`) when a local
network blocks outbound port 25, and the TLS checks never send `AUTH`, so a run
cannot trip a provider's brute-force lockout. When the resolved MX matches Netcup's
shared-webhosting pattern, an extra section diffs the live SPF/DKIM records
against Netcup's fixed known-good values and flags the classic Netcup footgun —
pointing a mail client at the customer domain instead of the canonical
`mx<hex>.netcup.net` wildcard-cert hostname — automatically via a TLS handshake.

### `motion-and-ui-design`

**The Problem.** AI-driven design tools (Claude Design and others) move fast — the UI, model lineup, and available templates shift every few weeks — but the durable workflow underneath (design-system-first, then prototype/slides/document/wireframe/animation) barely changes at all. Without that captured somewhere, every session re-derives the same lessons from scratch: skip the design system and every artifact looks generic, describe an animation vaguely and it comes back subtly wrong, port a web layout straight into an app shell and it feels foreign even though it's technically on-brand.

**The Fix.** A design hub that captures the durable workflow, not the volatile UI. `studio-workflow.md` walks the five studio artifact types (prototype, slides, document, wireframe, animation) with the design-system-first discipline threaded through all of them; `motion-graphics.md` distills four practical motion-graphics methods (template copy, start/end screenshots, transcript-driven, animate-any-UI) plus the precision lesson that makes vague animation prompts land right, with an agent-buildable variant for when the target is a code artifact instead of a studio export; `modern-design.md` filters current web-design trend noise for what's actually evidenced to hold up in production (bento grids, token-based design systems, restrained glassmorphism) versus what looks good in a showcase and breaks on real devices (heavy blur, unscoped kinetic typography), plus a concrete web→app adaptation table. A routing table sends anything already owned by another skill — Flutter tokens, Figma discipline, data viz, image generation, deployment — to that skill instead of duplicating it.

## Credit

These skills exist because [Matt Pocock](https://github.com/mattpocock) made his own [`mattpocock/skills`](https://github.com/mattpocock/skills) public and showed what a working skill ecosystem looks like. The structural choices here — directory layout, frontmatter conventions, the `npx skills@latest add` install path, the failure-mode/fix narrative pattern in this README — are his. If you find any of this useful, point upstream first.

## License

[MIT](./LICENSE).
