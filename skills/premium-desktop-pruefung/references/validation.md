# Validation record — 2026-11-18

## Executed checks

The replacement was developed in the skills repository and checked with Python 3 standard-library unittest suites. Reproduce from the repository root:

```sh
python3 -I tests/premium-desktop-pruefung/test_depth_audit.py
python3 -I tests/premium-desktop-pruefung/test_issues.py
python3 -I tests/premium-desktop-pruefung/test_probe.py
```

Initial replacement result: **62 tests passed** (30 ledger, 24 tracker, 8 probe/package checks). Later regression results are recorded below. The skill-creator frontmatter validator also passed. Its first isolated Python invocation lacked PyYAML; rerunning with the installed maintainer Python environment succeeded. The shipped tools themselves need no PyYAML.

Tests cover state transitions, full catalogue matrix construction, evidence hashes, invalid references/schema fields, disjoint work ownership, interrupted/stale merges, lock contention, source drift, independent-review freshness, separated fallback rejection, negative review gaps, refuted suspicions, report consistency and issue outbox integration. The all-criteria complete-ledger fixture tests protocol consistency using synthetic observations and reviewer identities; it does not certify actual UI quality or real agent independence.

Tracker tests use controlled HTTP mocks: destination/visibility guards, pagination, deduplication, dry run, errors, uncertain publication outcomes, receipt recovery and redaction. No live issue was published to a Gitea-compatible forge, GitHub or GitLab. Endpoint portability is based on official provider documentation and mocks, not a four-provider deployment test.

The Cloudflare reference's Node suites also ran successfully: 65 tests, no failures or skips, at the commit recorded in reference-analysis.md.

## Real browser fixture

The authored fixture is retained in `tests/premium-desktop-pruefung/preferences.html` in the development repository. Serve that directory only on loopback with `python3 -m http.server 8765 --bind 127.0.0.1 --directory tests/premium-desktop-pruefung`; open `/preferences.html` in an isolated browser. The actual test used an identical copy named index.html in a temporary directory. No product repository or personal browser profile was used.

Executed using `pwc --headless` in Chrome:

- Accessibility snapshot names the icon button **Save preferences**; the suspicion that the icon necessarily lacks an accessible name is refuted. This does not establish sighted-user comprehension.
- Tab, Tab, Enter activates Save; the status becomes **Preferences saved**. This proves immediate feedback only, not storage persistence.
- A further Tab moves to BODY while Advanced remains hidden. Source inspection finds a clickable div with no keyboard handler or tab stop. Mouse activation exposes Advanced. This substantiates a keyboard barrier (WCAG 2.1.1).
- Computed text foreground is rgb(153,153,153), background rgb(255,255,255), font 18px and weight 400. The contrast probe measures 2.849027755287037:1, below 4.5:1 for this normal text (WCAG 1.4.3).
- The only console error was a missing favicon (404), not an application failure. File-URL navigation was initially blocked; the loopback server supplied the supported execution path.

A separate fresh AI agent inspected primary source and the new implementation without receiving the expected fixture verdicts. It exposed an integrity-invalid issue export and incomplete reciprocal file/object mappings. Both were fixed with five regression tests: damaged evidence and changed source baselines block export; a sound finding remains exportable during incomplete coverage; both source mapping directions and mapped-file decisions are enforced. The previously missing validation reference was added. A follow-up independent review exposed publication despite a later contradictory review. Three further regression tests now verify that unresolved negative finding, unit, inventory or final reviews block affected issues; only an explicitly referenced, evidenced resolution clears the blocker. Unrelated incomplete coverage does not prevent publishing a sound finding. Browser actions were performed by the coordinator; that source review is not a second independent browser execution or assistive-technology test.

The real observations were imported into a persistent fixture audit, planned against all 100 criteria, then reconciled with the separate critic’s source report. Result: **2 confirmed findings, 1 refuted suspicion, 98 pending units, INCOMPLETE**. The issue adapter prepared exactly 2 issues offline and skipped the refuted finding. No fake passes or global acceptance were added. Runtime artifacts and the ledger remain in the development session’s temporary audit workspace; the authored HTML and reproduction instructions are retained in the repository.

## Limits and acceptance meaning

Portable skill frontmatter and local CLI help were checked for Codex 0.169.0 and Claude Code 2.1.326. Live Claude skill discovery/model execution, real native desktop execution, screen readers, empirical target-user research and live provider publication were **not tested**. Native execution, live Claude and provider publication remain open validation limits. Screen-reader execution is now an optional extension, outside the standard audit unless explicitly requested; its untested status does not mandate running it during standard audits. A current Codex session actually performed the delegated code/fixture review; actor-label mocks alone do not establish independence.

The tools do not supply an OS sandbox. Runtime audits require controls proportionate to the identified code and action; the current host may run reviewed ordinary product tests with disposable data. Unknown code requires demonstrated containment. Assess available alternatives before documenting a method-specific blocker. Deterministic gates establish ledger consistency, not exhaustive semantic discovery or WCAG conformance. Journals detect inconsistent edits; coordinated malicious rewrites and forged identities are outside their guarantee. Existing version-1 ledgers from the former implementation have a different schema: archive them and start a new run, never silently reinterpret them.

## Definition-of-done reconciliation

| Requested criterion | Evidence / status |
| --- | --- |
| 1. Reference analysis | Complete source inspection, pinned commit and 65 upstream tests |
| 2. Professional basis | Primary standards and research register, explicit applicability limits |
| 3. Installable implementation | Common skill bundle and working Python tools; Codex catalog discovery observed; fresh Claude execution remains open |
| 4. Inventory and depth | Four-view reconciliation, 100-criterion matrix, nine methods; semantic completeness still requires actual review |
| 5. Persistent state | Hashed evidence, journal, jobs, reports; exercised by tests and fixture run |
| 6. Independent and deterministic review | Actual fresh-agent source review plus validators; actor labels alone remain assertions |
| 7. Incomplete-work rejection | Adversarial tests and real 98-pending fixture remains INCOMPLETE |
| 8. Resume and coordination | Ownership, stale transactions, lock and receipt recovery tested locally |
| 9. Consistent output | JSON/Markdown from one snapshot, adapter integration and offline issue preparation exercised |
| 10. Audit/correction separation | Product edits removed from skill; issue-only adapter |
| 11. Platform compatibility | Current documentation and installed CLI checks; Codex catalog discovery observed; live Claude execution remains open |
| 12. End-to-end validation | Synthetic protocol E2E and actual browser-to-outbox path pass; native/AT/live-provider/full-host runs remain open |

The replacement is implemented and locally tested; it is not represented as fully validated across every requested production runtime. Repository merge/export were not performed. Local global installation was subsequently completed as recorded below; a fresh Claude execution remains untested.

## Screen-reader scope update

Screen-reader execution is explicitly opt-in in the entrypoint, M6, catalogue methods and worker/critic/retest contracts. Keyboard, accessibility-tree, contrast and adaptive checks remain in the standard scope. The dedicated assistive-task criterion receives an evidenced scope exclusion when not requested; other criteria retain uncertainty where available evidence is insufficient. All 62 existing tests and the skill-format validator passed after this instruction-only change. No screen reader was launched.


## Global installation and practical-audit feedback

The canonical source is linked from `~/.agents/skills/premium-desktop-pruefung`; `~/.codex/skills/premium-desktop-pruefung` and `~/.claude/skills/premium-desktop-pruefung` resolve to that shared installation. All installed files match the source and the CLI runs outside this repository. Codex exposed the skill in the available-skills catalog. These are live links: source updates propagate without copying; moving/deleting the source checkout breaks them. Alternative Claude account directories/config overrides were not present. No remote computers were installed.

Earlier feedback from a separate real audit led to explicit bounded scans (then always incomplete; superseded by the continuous scanner below), scope-bound drift checks, separate malformed/stale-fragment diagnostics, CLI review digests, collision-resistant review draft wrapping without digest restamping, compact validation output plus full JSON, and filtered resume queues. Independent finding confirmation is now visible separately from publication eligibility; global contradictory reviews remain blockers. HTTP LAN destinations can prepare offline issue drafts without credentials/network; live delivery remains HTTPS-only. That earlier sandbox guidance treated failed macOS probes as unavailable isolation; the host-first revision below supersedes using historical probes as a present global obstacle.

Regression result: **74 tests passed** (38 ledger, 28 tracker, 8 probe/package). Tests use newly authored temporary fixtures/mocks, not the other audit's files. Additional cases cover intentional omissions and remaining incompleteness, untracked source drift, canonical paths/digest binding, malformed versus stale fragments, non-overwriting review drafts, stale digest and actor rejection, 1,300-unit output grouping, bounded resume selection and confirmation/publication separation. No live HTTP transmission, target build, screen reader or remote test lab was executed. Automatic aggregation of child-run coverage is not implemented; manual manifest reconciliation cannot certify omitted paths.

An additional independent source review ran the 65 ledger/adapter tests present at that point and found that human reports omitted explicitly excluded paths. The report now lists paths and reasons, with a dedicated regression test. No completeness or HTTP transport bypass was found in that review.

## Host-first completion revision — 2026-11-18

Primary failure evidence: the local HTML report and ledger of a real desktop-product audit. The report was opened in Chrome via `pwc` and a loopback server after file navigation failed. It describes successful browser setup followed by only limited execution, missing native/lifecycle/accessibility coverage, premature source-scan limits and mostly unattempted work labelled blocked. The report is historical input, not evidence that those missing product tests now passed.

Implemented corrections:

- Host-first capability selection and proportionate controls replace a mandatory lab/containment interpretation for ordinary reviewed product tests. Failed runners are method-specific; available local and authorized remote alternatives must be assessed. Setup success leads immediately into a real core task.
- Continuous, streaming source discovery includes untracked files and durable batch checkpoints. File count/read chunk size do not cap total coverage. Resume reconciles additions/deletions/mutations and rejects changed baselines rather than mixing revisions. Interrupted hashing restarts the current file.
- `next` provides bounded packages across surfaces, pending work, review needs and blocker freshness. Intermediate reports are not completion; source, browser, native, persistence, error recovery and review/delivery retain separate evidence obligations.
- New blocked writes require a concrete attempt, observed obstacle, alternatives, retry action/condition, primary evidence and current runtime/platform/scope digest. Old rows remain readable; unsupported or stale blockers are visible, and blocked work can return to pending while preserving history.
- Insight quality requires a discriminating expected outcome, counterexample/recovery checks, observed-versus-inferred distinctions and independent semantic inventory review. Structural validity cannot establish truthful execution or exhaustive UI discovery.

Read-only analysis of the supplied legacy ledger identifies all **1,382 blocked units as unsubstantiated under the new structured contract**. This is not an assertion that every method is executable; each needs reassessment. The legacy ledger and report were not rewritten and their source completeness claim was not endorsed.

Independent forward test: a fresh agent read the revised workflow and ran the 88 then-current tests. It correctly chose local Mac alternatives after a failed runner, kept browser/native evidence separate and continued after bounded work. An additional 53-file fixture with a seven-path batch size and five-byte read chunks inventoried every file without scan limits. The review exposed internal symlinks as an unnecessary permanent completion obstacle; the subsequent scanner correction and regression tests address that defect. External/unreadable source boundaries remain explicit limits, not silently certified subrun coverage.

No full product audit, native persistence test or live tracker publication was performed as part of this skill revision. No portable instruction can guarantee future agent persistence by itself; the queue, write guards, source checks, regression tests and independent review make failures more visible and harder to misreport.

Final regression result for this revision: **93 tests passed**, including 14 source-discovery tests, plus the skill-format validator. Internal file/directory/root aliases, link retargeting, unresolved external/cyclic/excluded targets, whole-tree batching, interruption/resume, large/untracked files and blocker freshness are exercised. These are local regression fixtures, not a repeated product audit.

The independent follow-up reproduced clean internal-alias initialization, then exposed an unresolved-link journal replay mismatch. Baseline replay now reconstructs blocked link rows from immutable scan limits. An integration regression verifies initialization, evidence import, file disposition changes and runtime-profile writes while the external source limit remains open. All 93 tests passed after this correction.

## Practical-audit feedback revision 2 — 2026-11-18

A real browser and native audit of a desktop product (run r2) hit these limits; each is now addressed:

- `result.json` reached 46 MB and exceeded the issue adapter's 32 MiB input bound. `report` now also writes `issue-export.json` with only run identity, integrity, coverage notices and findings; the adapter's size error names it. Regression test: a synthetic result above 32 MiB is refused, its export (< 100 kB) prepares the issue.
- Confirmed findings blocked by a review were reported as "not independently confirmed". Skip reasons now name the gate and the blocking review ID.
- An inventory review `gap` blocked every finding although the reference allowed coverage gaps to pass. Rule now: inventory `gap` = coverage notice (shown in report and issue body, audit stays INCOMPLETE), inventory `reject` and finding/unit/final objections = blockers.
- The plain-HTTP LAN tracker required a private client outside the adapter. `tracker.json` accepts `"allow_http": "private-lan"` for RFC 1918/loopback/link-local/ULA addresses and `.local` names that resolve privately, without redirects or proxies, and `"credential": "git-credential"` reads the keychain through `git credential fill`. Tests mock DNS and git; no live request.
- `plan` produced 164,000 units and a 380 MB ledger. Evidenced `applicability` and `equivalences` rules, bound to the inventory review, keep covered combinations out of the matrix; `plan` prunes untouched covered units. The ledger is written as compact JSON. A SQLite or sharded ledger was not implemented in this revision (see the next section).
- Hand-written merge scripts replaced partial updates. `audit.py patch` (`--set`, `--add`, `--append-variant`, `--fragment`) builds operations from the current row; the job contract error names the covering jobs and the required order, and the protocol documents claim → running → result → done (one fragment is fine when the job comes first).
- Object kinds gain `dialog`, `menu`, `notification`.
- A hand-made contrast sweep folded ancestor opacity into the text color only. `scripts/contrast_sweep.js` collects raw layers in the page, `probe.py sweep` composites text and background through every ancestor group. Checked in headless Chromium on a fixture: a 40 % panel over black measures 3.66:1 (fail), OKLCH colors normalize, gradients are `uncertain`, disabled controls `exempt-candidate`.
- Native isolation guidance now covers the real home directory and service managers (a sandboxed run had registered a service under a production label), and critic briefs require an own browser session with a network guard.

Regression result: **117 tests passed** (55 ledger, 36 tracker, 12 probe/package, 14 source discovery), with Python 3.15 and the system Python 3.9.

## Scalable ledger — 2026-11-18

Even with matrix rules the single JSON ledger made every write load, revalidate and rewrite everything. Measured on a synthetic ledger with 100 objects × 10 variants × 100 criteria (100,000 units): one `apply` that claims a job took **21 s** (11 s serializing 45 MB through the Python JSON encoder, 8 s replaying the full journal, plus re-hashing every evidence file).

The ledger is now `audit.db` (SQLite from the standard library): rows per table with an index for the units of an object and the reviews of a target, an append-only journal, and the sequence as metadata. `apply` checks only touched and dependent rows and commits one transaction. Same fixture: claim job 0.15 s, unit transitions and patches 0.01–0.02 s, adding an applicability rule 0.01 s, `plan` creating 100,000 units 3.6 s, `plan` pruning 10,000 units 2.0 s, full load 0.55 s, full journal replay 3.8 s, complete validation for the report 4.1 s (per-unit review lookups now use a target index instead of scanning every review).

Guarantees: the full validator and journal replay are unchanged and still run on `check`/`report`. The tests run every `apply` a second time through the full validator (`AUDIT_VERIFY_APPLY=1`) and fail when the two disagree; a deliberately removed dependency check is caught this way. Further tests cover JSON ledger migration, rows that depend on a change (stale variants, unmapped sources, a reopened unit under a confirmed finding, pruning a reviewed unit), a hand-edited database row and a commit against a ledger that moved on. Large tables refuse full iteration during `apply`, so a slow path cannot return unnoticed.

Regression result: **122 tests passed** (60 ledger, 36 tracker, 12 probe/package, 14 source discovery), with Python 3.15 and the system Python 3.9.

## Relevance policy for the source scan — 2026-11-18

Live run on a Tauri/React product: the full traversal inventoried 128,529 files in 34.9 s (ledger 48 MB), about 98 % of them in nested agent worktrees, `target/` and `node_modules/`. With the policy, `init` on the same tree inventoried 1,854 files in 0.3 s (ledger 0.5 MB) and listed ten skipped directories, all Git-ignored. Tests cover nested checkouts (`.git` file or directory), exact-path Git ignores (`target/` skipped, `src/target/` kept), cache names, `--include`, `--scan-all`, checkpoint scope, no drift from changes in skipped trees and unchanged full scope for pre-policy runs.

Adoption for a pre-policy run: a copy of the live gitoodo ledger (5,389 journal steps, 128,529 file rows) could no longer run `drift` or `check`, because other sessions were building in Git-ignored agent worktrees inside the target repository. `adopt-scan-policy` with three includes for mapped generated sources took 0.9 s; afterwards `drift` reported no changes in 0.9 s, the journal replay stayed consistent and the only new check error was the expected stale inventory review.
