# Gates — Project Detection, Format/Analyze, Commit

Orchestrator-only. Resolves which shell commands to run for `format`, `analyze`, `test`; defines the pre-reviewer gate; defines the commit gate. Sub-agents read the resolved commands from `<feature>/.ratchet-up/config-resolved.md`, never from this file.

---

## 1. Project Type Detection

Run once at the start of every `/ratchet-up` invocation. First hit wins.

**1.1 Per-feature override** — `<feature_path>/.ratchet-up/config.yaml`. Keys: `format`, `analyze`, `test`, and the optional `visual`. Each is a shell command line, or the literal `skip` to disable. `visual` also accepts `auto` (the default when the key is absent).

```yaml
format: "dart format ."
analyze: "flutter analyze --fatal-infos --fatal-warnings"
test: "flutter test"
visual: "auto"   # auto = best-effort cheap capture; a command = sanctioned capture; skip = no screenshots
```

`visual` is the reviewer's cost knob for the conditional Visual Verification step (`visual-review.md`). It only ever matters when the diff touched a UI surface (§2.5); for backend-only diffs it is irrelevant. `auto` lets the reviewer probe for an already-running app / golden tests / an installed headless-browser CLI and skip if none is cheap; a command pins one sanctioned capture path; `skip` disables visual capture entirely.

**1.2 Repo `CLAUDE.md`** — grep for a "Commands" / "Quality gates" / "Quality gates before commit" section, extract the format / analyze / test lines verbatim. Examples that should be copied as-is: `flutter analyze --fatal-infos`, `npm run typecheck`, `pnpm test`, `cargo clippy --all-targets -- -D warnings`, `go vet ./...`.

**1.3 Auto-detect** — check marker files at repo root:

| Marker | format | analyze | test |
|---|---|---|---|
| `pubspec.yaml` | `dart format .` | `flutter analyze --fatal-infos --fatal-warnings` | `flutter test` |
| `package.json` | `npx prettier --write .` (skip if not a dep) | `npm run typecheck` (skip if absent) | `npm test --silent` |
| `pyproject.toml` | `ruff format .` (skip if missing) | `ruff check .` | `pytest -q` |
| `Cargo.toml` | `cargo fmt --all` | `cargo clippy --all-targets -- -D warnings` | `cargo test` |
| `go.mod` | `gofmt -w .` | `go vet ./...` | `go test ./...` |

If detection fails entirely, log a one-liner to `run-log.md`, set all three to `skip`, and warn in the final summary — the reviewer must verify behaviour by code inspection alone (degraded mode).

**1.4 Persist** — write the resolved commands to `<feature>/.ratchet-up/config-resolved.md`:

```md
# Resolved Gate Commands

format: dart format .
analyze: flutter analyze --fatal-infos --fatal-warnings
test: flutter test
visual: auto
```

Worker and reviewer load this file via Read; the orchestrator passes its full content as `{{GATE_COMMANDS}}`.

---

## 1.5 Resolving the `visual` command (discovery + heavy detection)

Run once, only when `visual` is `auto` or absent (an explicit command or `skip` is used verbatim). The point: real frontend projects usually *have* a screenshot path — it is just not a running session or golden test. Discover it so the batched visual pass (`algorithm.md` §15.4) can use it, instead of silently skipping.

**Discovery — first hit wins:**

1. `CLAUDE.md` — a "Visual" / "Screenshots" / "Visual QA" command line (same extraction as the Commands section in §1.2).
2. `package.json` `scripts` — a key matching `visual*`, `screenshot*`, `*visual-qa*`, `storybook:*test*`, or `chromatic`.
3. A repo script — `tool/visual_qa.dart`, `scripts/visual-qa*`, `bin/screenshots*`, a `Makefile` target named `visual`/`screenshots`, or an `integration_test/` screenshot driver.
4. Nothing found → keep `visual: auto` (reviewer falls back to its own cheap probe and otherwise skips).

**Heavy detection.** Tag a discovered (or explicit) command `[heavy]` when it boots a simulator/emulator or does a full build — heuristics: the command or the script it calls mentions `simulator`, `emulator`, `flutter run`, `flutter drive`, `integration_test`, `xcrun simctl`, `adb`, `playwright` with a full app build, or a `build` step. A fast headless screenshot (`shot-scraper`, a golden run, a pre-built-dist screenshot) is **not** heavy.

**Persist** the result into `config-resolved.md` (see §1.4):

- `visual: <command> [heavy]` — discovered/explicit heavy path → the per-issue reviewer defers it; the §15.4 batched pass runs it once.
- `visual: <command>` — discovered/explicit cheap path → the per-issue reviewer may run it.
- `visual: auto` — nothing discovered → reviewer best-effort cheap probe, else skip.
- `visual: skip` — opted out.

---

## 2. Quick-Path Heuristic (skip format/analyze for doc-only issues)

After a worker returns `DONE:` and **before** running the format/analyze gate, classify the diff:

```bash
git diff --name-only HEAD
```

**Doc-only path** — every changed file matches **all** of:

- ends in `.md`, `.txt`, `.rst`, `.adoc`, `.mdx`, `CHANGELOG*`, `LICENSE*`, `NOTICE*`, or sits under `docs/`, `notes/`, `<feature_path>/`, `<feature_path>/.ratchet-up/`
- not under `lib/`, `src/`, `test/`, `tests/`, `app/`, `pkg/`, `cmd/`, or any source-code directory the project uses

If doc-only:

- Skip `format` and `analyze` — they don't apply.
- Still run `test` if it's not `skip` and the project convention covers prose tests (rare; usually skip).
- Log `gate quick-path (doc-only)` to `run-log.md`.
- Hand straight to the reviewer.

**Mixed diff** (code + docs) or **code-only** → full gate per §3 below.

The reviewer always knows the gate mode via the line in `run-log.md` and can re-run any check itself.

---

## 2.5 UI-surface detection (cheap hint for the reviewer's visual step)

After classifying the gate mode and **before** spawning the reviewer (§9), classify the same `git diff --name-only HEAD` output a second way: does it touch a **UI surface**? This is a millisecond glob check — no app launch, no extra agent.

A changed file is a UI surface when it matches the project's frontend conventions, e.g.:

- **Flutter:** `.dart` under `lib/` whose path or name signals UI — `**/widgets/**`, `**/screens/**`, `**/pages/**`, `**/views/**`, `**/components/**`, `*_screen.dart`, `*_page.dart`, `*_view.dart`, `*_widget.dart` — plus theme/token files (`**/theme/**`, `**/design*/**`).
- **Web:** `.html`, `.css`, `.scss`, `.vue`, `.svelte`, `.astro`, and `.tsx`/`.jsx` under a UI directory (`**/components/**`, `**/pages/**`, `**/routes/**`, `**/views/**`).

Produce the `{{UI_DIFF}}` value the orchestrator passes to the reviewer:

- **No UI surface touched** → `{{UI_DIFF}}` = `none`. The reviewer skips visual verification at zero cost.
- **One or more touched** → `{{UI_DIFF}}` = the matching paths (one per line). The reviewer loads `visual-review.md`.

When unsure whether a path is a UI surface, **err toward `none`** — a missed visual check is cheaper than burning capture infrastructure on a false positive. The reviewer's protocol degrades safely either way (it skips when no cheap capture path exists).

---

## 3. Format / Analyze Gate (between worker and reviewer)

Run the commands recorded in `config-resolved.md`, in this order:

1. `format` — run with **write** permission. Formatting changes are allowed and may be staged. If `format` is `skip`, log `format skipped`.
2. `analyze` — run as-is. **Do not** auto-fix lint/analyze issues — that is the worker's job. If `analyze` is `skip`, log `analyze skipped`.

Tests are **not** part of this gate — workers already ran them under TDD. The pre-reviewer gate exists solely to catch obvious style/type breakage before burning a reviewer spawn.

**Outcomes:**

- All gate commands succeeded (or were skipped) → log `gate ok` and proceed to reviewer dispatch.
- Any non-skip gate failed → write the **full raw output** to `<feature>/.ratchet-up/test-notes.md`, return one-liner `gate failed: <count> issues` to the loop. The issue goes back to `ready-for-agent` (rework counted in §14); reviewer is **not** spawned.

If gates are skipped in degraded mode (§1), log `gate skipped` and note it in the final summary so the user knows quality wasn't auto-checked.

---

## 4. Commit Gate (after reviewer APPROVED only)

Commit only after the reviewer returns `APPROVED:` and the issue file has `Status: done`.

**Pre-checks:**

```bash
git status --short
git diff --name-only
```

If there are no code changes (e.g. a documentation-only issue resolved by an evidence block alone), log `no changes` to `run-log.md`, do **not** create an empty commit, keep the issue `done`.

**If changes exist**, follow [Conventional Commits](https://www.conventionalcommits.org):

| Type | When |
|---|---|
| `feat` | New user-visible capability |
| `fix` | Bug fix |
| `refactor` | Behavior-preserving change |
| `test` | Test-only change |
| `docs` | Documentation only |
| `chore` | Tooling, config, build |

Derive scope from the affected module/feature. Subject imperative, lowercase, no trailing period, ≤72 chars. Reference the issue filename in the body.

Stage **only** the files the worker enumerated in the Evidence block's `changed_files:` list — never `git add -A`, which would sweep in out-of-scope edits the worker shouldn't have made (the reviewer flags scope drift, but only *after* the commit; staging narrowly prevents it up front).

```bash
git add <each path from the Evidence block's changed_files>
git commit -m "$(cat <<'EOF'
<type>(<scope>): <short imperative description>

Issue: <issue_filename>
EOF
)"
```

**Hard rules:**

- Stay on the active branch. **Never** push, tag, or merge to another branch.
- **Never** use `--no-verify`, `--no-gpg-sign`, or any hook-bypass flag. If a hook fails, log the failure and continue with the next issue — a human will sort it out.

**After APPROVED (commit successful OR no-changes):** delete the rework feedback file if it exists.

```bash
rm -f "$feature_path/.ratchet-up/rework/$issue_basename.md"
```
