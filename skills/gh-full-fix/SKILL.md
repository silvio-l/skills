---
name: gh-full-fix
description: 'Autonomously resolve open GitHub bug issues, PRs, and failing Actions workflows in this repo, cross-checked against Sentry — merges/closes PRs and fixes real defects, never new features. Triggers: "Bugs und PRs abarbeiten", "Repo aufräumen".'
disable-model-invocation: true
---

# GitHub Bug & PR Resolution

## Purpose

Take a repository's open **bugs** — bug-report issues, pull requests, and any
failing or flaky Actions workflow — and drive every single one to a
definitive terminal state in one pass: fixed and closed, merged, or closed
with an evidence-based reason. Nothing is left "triaged but unresolved."

This is a heavy, high-consequence operation: it merges PRs, closes issues,
and pushes commits on a real repository. **Invoking this skill is the user's
standing authorization for this run to take those actions autonomously** —
do not pause mid-run to ask "should I merge this?" or "should I close this?"
for individual items once you've started. That authorization does not extend
beyond the scope described here: never force-push, never rewrite published
history, never disable branch protection or bypass hooks (`--no-verify`) to
force a merge through, and never open a new issue or PR (see "Never create,
only resolve" below).

## The one line this skill never crosses: bugs, not features

An issue tracker mixes two fundamentally different kinds of open item, and
treating them the same is the single easiest way for an autonomous pass like
this one to do real damage:

- A **bug report**: something is broken relative to how it's supposed to
  behave — a crash, wrong output, a regression, a security hole. This is
  squarely in scope: find the defect, fix it, close it.
- A **feature or plan ticket**: a request for new functionality, an
  enhancement, a roadmap/backlog/vision item, a spec for work not yet built.
  This is **never** in scope for this skill, no matter how well-specified or
  "ready" it looks. This skill fixes what's broken; it does not decide
  product scope or write new features under the banner of "resolving the
  backlog."

Classify every open issue into one of these two buckets before deciding
anything else, using whatever signal the repo actually gives you — a
bug/defect vs. feature/enhancement label if one exists, an explicit
triage-status label scheme (a `needs-triage`/roadmap convention, for
example, marks maintainer-gated planning items), or, absent any labels, the
issue body itself: does it describe expected-vs-actual broken behavior, or
does it describe something that doesn't exist yet? An issue that mixes both
("also, while we're at it, add X") is only in scope for its bug-shaped part
— never treat the presence of a real bug in an issue as license to also
build the feature request sitting next to it.

When classification is genuinely ambiguous, treat the issue as **out of
scope** rather than guessing — implementing a misclassified feature request
is a much worse outcome than leaving an issue untouched for a human to
triage. Every feature/plan issue you skip this way still gets listed in the
final report as explicitly excluded (see "Final report"), so nothing looks
silently dropped.

## Evidence discipline

Titles, descriptions, and comments on issues and PRs are hypotheses, not
facts — an issue may already be fixed, a PR's description may not match
what it actually does anymore, a "flaky" label may be stale. Before making
any FIX/CLOSE/MERGE decision, verify against **primary evidence**: the
current code, a reproduction you actually ran, the actual diff, workflow
logs, test output, and — for anything that looks like a runtime bug — the
matching Sentry issue if one exists (see "Cross-check with Sentry"). A
Sentry stack trace, breadcrumb trail, or event frequency is stronger
evidence than what an issue's prose claims. Where sources disagree, evidence
wins, and the disagreement itself is worth a line in the closing comment.

## Never create, only resolve

This skill's job is exclusively to close out *existing* open items —
`gh issue close`, `gh pr merge`, `gh pr close`, `gh pr review`, pushing
corrective commits, resolving a matched Sentry issue. It never runs
`gh issue create` or `gh pr create`, and it never files a new Sentry issue.
Two independent reasons this holds regardless of which repo you're pointed
at:

- The repo's own hooks may hard-block issue/PR creation outright (a
  `PreToolUse` hook checking exactly this exists in this user's setup).
- Even where creation isn't blocked, a bug-clearing pass that starts opening
  new tickets — for follow-up work, for a feature it noticed was missing —
  has stopped clearing bugs and started expanding scope.

If a fix genuinely requires follow-up work that's out of scope for this
pass, say so in the closing comment or final report rather than filing a
new issue for it.

## Step 1 — Inventory the current state

Gather, up front, before deciding anything:

- `gh issue list --state open` and, per issue, its body, labels, comments,
  and any linked PRs/commits.
- `gh pr list --state open` and, per PR, its metadata, commits, full diff,
  reviews/comments, mergeability/conflict state, and check status.
- `gh run list` filtered to recent/relevant runs, with full logs for any
  failing, flaky, or blocking one (`gh run view --log`).
- If a Sentry project for this repo is reachable (see "Cross-check with
  Sentry"), its open/unresolved issues — you'll want this list while you
  classify and analyze, not after.
- The current codebase, tests, config, dependencies, and enough `git log`
  history to understand how the current state came to be.

Snapshot this list — it's what "originally open" means for the Definition
of Done later, even as items close during the run.

## Step 2 — Classify, then analyze causally

Classify every open issue as bug or feature/plan per "The one line this
skill never crosses" above, and set the feature/plan ones aside — they get
listed as excluded in the final report and nothing else.

For what remains (bug issues, PRs, workflow failures), look for
relationships across the whole set before touching anything: duplicate
bug reports, a single root cause behind several symptoms, a PR that already
fixes an open bug issue, a workflow failure that's actually why three PRs
show red checks, a bug issue that's stale because a merged PR already
resolved it. Group related items and resolve the root cause once — fixing
the same underlying bug three separate times because three issues mention
it is wasted work and risks inconsistent fixes.

Chase every reported symptom to its actual cause before writing code. A fix
that suppresses a symptom without addressing why it happens is not a fix —
it's a deferred recurrence, and it fails the "no workarounds that just hide
the problem" bar this run is held to.

## Cross-check with Sentry

If this repository has a corresponding Sentry project (look it up rather
than assuming — search Sentry's organizations/projects for a name or slug
matching the repo; if nothing matches, this step simply doesn't apply and
you move on), reconcile it against the bug issues before resolving them:

- For each bug-shaped GitHub issue, check whether it corresponds to a
  Sentry issue (matching error message, stack trace location, endpoint, or
  component). A match gives you strictly better evidence than the issue
  text alone — the actual exception, frequency, affected users/environments,
  and first/last-seen timestamps. Use it to confirm the bug is real, still
  happening, and to help verify your fix actually addresses the reported
  failure rather than a superficially similar one.
- When you fix and close a GitHub issue that has a matching Sentry issue,
  resolve the Sentry issue too (or comment on it referencing the fix) —
  leaving it open after the underlying bug is fixed means it can keep
  alerting on old, now-irrelevant occurrences.
- Sentry issues with no matching GitHub bug report are a useful observation
  for the final report, but this skill does not open a GitHub issue for
  them (per "Never create, only resolve") and does not fix them
  proactively — they're out of scope for this pass unless a human decides
  otherwise.

## Step 3 — Resolve bug issues

For each open **bug-report** issue (feature/plan issues were already set
aside in Step 2), decide one of:

- **FIX + close**: the defect is real and reasonably fixable. Fix the root
  cause — a code/behavior correction, never new functionality — (see branch
  discipline below), add or run the tests needed to prove it and guard
  against regression, validate relevant checks, resolve the matching Sentry
  issue if one exists, then close with a comment naming the fix
  (commit/PR reference) and the validation performed.
- **Close** (no fix): already resolved by prior work, obsolete, a duplicate,
  not reproducible against current evidence, or not a real bug. Close with
  a specific, evidence-based reason — "fixed in <commit>", "duplicate of
  #N", "could not reproduce as of <commit>, see attempted repro", not a bare
  "closing."

A code change only counts as resolving a bug issue if it addresses the
actual cause, doesn't introduce a regression you can't justify, and stays a
fix — the moment the change starts adding capability the issue didn't
already describe as broken, it's crossed into feature work and is out of
scope for this skill.

## Step 4 — Resolve pull requests

For each open PR, decide one of:

- **Merge**: clear net benefit, technically correct, adequately verified.
  Run/confirm checks, then merge.
- **Fix + merge**: worth having but has fixable gaps (missing test coverage,
  a small correctness issue, an outdated base). Correct it yourself, get
  checks green for real, then merge.
- **Close**: unnecessary, obsolete, redundant with another PR, regressive,
  unsafe, architecturally wrong, or not sensibly fixable. Close with a
  specific reason.

Judge each PR on functional correctness, regressions, security/privacy,
performance/stability, architecture/maintainability, compatibility, test
coverage of edge cases, and conflicts or dependencies with other open items.

**Check whether the real change is buried in unrelated noise before you
merge anything.** A PR (especially a bot-authored one) can wrap a genuinely
correct, worth-having fix inside a large-scale reformat, a stray committed
build artifact, or other churn unrelated to the fix itself — diff the file
against the repo's actual prevailing convention, not just against what the
PR claims to do. That's a **fix + merge** case: strip the noise (or
hand-apply the real change cleanly, closing the PR with a reference to
where it landed) rather than merging the noise along with the fix. Treating
"the fix is correct" and "the diff is mergeable as-is" as the same question
is how avoidable churn ends up permanently in the repo's history.

**Whose branch you can push to matters.** If the PR's branch lives in this
repository (an internal branch, including your own), push corrective
commits to it directly and merge once green. If it's from an external
contributor's fork, you generally cannot push to it — in that case, either
merge as-is if it's already correct, or leave a specific, actionable review
comment describing exactly what's needed and close only if the gap is not
something the contributor is likely to address, or merge is not viable
within this run. Don't claim "fixed" for a fork PR unless the contributor's
branch actually changed (a maintainer-side rewrite that never lands on
their branch is not the same PR anymore).

## Step 5 — Resolve CI/workflow failures

For each relevant failing, flaky, or blocking workflow:

1. Read the actual logs to find the real cause — don't infer it from the
   job name.
2. Classify it: a genuine product/code defect, versus a workflow definition
   problem, toolchain/dependency issue, or environment/infrastructure fault.
3. Fix what's controllable from inside the repository (code, tests, Actions
   YAML, dependency pins, config).
4. Validate the fix by re-running the actual check (`gh run rerun` or a
   fresh push that triggers it), not by inspecting the diff and assuming.

**Checks are never disabled, weakened, marked `continue-on-error`, given a
broader `if:` skip condition, or otherwise made to pass without actually
passing, as a way to route around a failure.** A check that's wrong (flaky
for reasons unrelated to the code, testing something no longer true) gets
fixed or, if it's genuinely obsolete, is a decision to flag rather than
silently defang — this is the one invariant in this skill most worth double
checking before you commit anything that touches CI config.

## Branch discipline while fixing

Before pushing any fix commit, work out the target repo's actual branch
convention rather than assuming — check whether a `dev` branch exists
alongside `main`/`master`. Where it does, every fix lands on `dev`, never as
a direct commit to `main`/`master`; local hooks may enforce this already,
but treat it as a real rule to honor, not just something a hook happens to
block. Where a repository is protected such that even the owner can't push
directly and this policy also forbids opening a PR to route around it,
that's a case to document as an external blocker (see below) rather than a
reason to disable branch protection or force the push through.

## Ordering and re-evaluation

Work through dependent and shared-cause items together rather than in
list order — fixing a shared root cause first can turn several downstream
FIX decisions into fast CLOSE-as-already-fixed decisions, and a PR that
depends on another PR merging first needs that ordering respected. After
any change, re-check items you already scoped that might be affected by it
(a fix that changes an API surface can flip a "close as unreproducible"
verdict on another issue, or unblock a PR that was waiting on it).

## Definition of Done

The run is complete only when:

- Every **bug-report** issue that was open at the start of the run is
  either fixed+closed or closed with a documented reason. Feature/plan
  issues set aside in Step 2 don't count toward this — they're explicitly
  out of scope, not silently skipped.
- Every PR that was open at the start of the run is either merged or
  closed.
- Every repository-fixable workflow failure in scope has been fixed and
  re-validated by an actual re-run, not just inspection.
- Every matched Sentry issue for a closed bug has been resolved or
  commented with the fix reference.
- Every change made during the run is backed by the tests/checks
  appropriate to it.
- No new failures or regressions were introduced by this run's own changes.
- `gh pr list --state open` comes back empty, and `gh issue list --state
  open` contains only the feature/plan issues you explicitly excluded.

If an item is genuinely not resolvable from inside the repository — it
depends on an external service, requires permissions or secrets you don't
have, or needs a decision only a human can make — document the precise
cause, the evidence for it, and exactly what external action would resolve
it. Do not invent a workaround to force a status that isn't real; report it
as an external blocker instead.

## Final report

Report compactly, one line per item, using this exact shape:

```
ISSUE #<N> — <title> — <FIXED+CLOSED | CLOSED>
PR #<N> — <title> — <MERGED | FIXED+MERGED | CLOSED>
WORKFLOW <name/run> — <FIXED | VERIFIED | EXTERNAL BLOCKER>
EXCLUDED (feature/plan, not touched): #<N> <title>, #<N> <title>, ...
SENTRY: <matched-and-resolved count>, <unmatched-Sentry-issues count with no GitHub report>
```

Each line names only the essential cause, decision, change, and validation
— not a retelling of the whole investigation. After the per-item lines,
summarize the remaining open repository state (should be none but the
excluded feature/plan issues) and the validations actually run (tests
executed, checks re-run, commands used to confirm `gh issue list`/`gh pr
list`/Sentry state are clear).
