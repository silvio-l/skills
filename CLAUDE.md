# CLAUDE.md — Maintenance Guide for AI Agents

This repo is the source of truth for my personal Claude Code skills. It is maintained by AI agents (mostly Claude Code itself) — that is who this guide is for.

## Skill scope: global vs project-local

Default every skill to **project-local**: global status is earned only by being useful *regardless of which repo (or none) is open* (an OS-level utility, generic writing/ideation, a meta-routing skill) — anything tied to a project type (a game engine, an app's icon/marketing/SEO pipeline) stays project-local so it doesn't tax every session's context on every machine. Keep this list current, and mirror it in `README.md`'s per-skill tags:

- **global:** `apple-notes`, `brainstorming`, `deep-monograph`, `escalate`, `fetch-open-chat-tab`, `fetch-shared-chat`, `gh-full-fix`, `instructions-optimizer`, `name-clearance-red-team`, `omada-admin`, `owasp-bsi-audit` (the last is an explicit standing exception, see the global `~/.claude/CLAUDE.md`)
- **project-local:** everything else in `skills/`

**Global provisioning is `update`-only, never `add -g`.** `add -g` installs a skill onto every future session's ambient context, so it is never part of an automated or standing-authorized sequence — always a deliberate, individual decision, and only for a skill on the global list above. To use a project-local skill in a project that needs it, install it there (no `-g`) from *outside* this repo's working directory:

```bash
cd <target-project-root>   # never inside this skills/ repo — see the cwd warning below
npx skills@latest add silvio-l/skills -s <skill-name> -y
```

## Workflow

```
edit here → commit on dev → push dev → merge dev into main (ff-only) → push main → npx skills@latest update -g -y
```

**The skills CLI sources global skills from the `main` branch on GitHub (`origin/main`).** A skill edit is therefore not "live" globally until it is committed on `dev`, merged to `main`, and **both branches are pushed** — only then does `update -g` pick it up. Skipping the merge/push is the #1 reason a freshly-edited skill does not refresh: `update` pulls a stale `main`, so you either see no change or fall back to a local-path `add`. **Every** skill change goes through the full `dev` → `main` roundtrip below, no exceptions.

The roundtrip's final step, `npx skills@latest update -g -y`, only refreshes skills **already tracked** in the global lock (`~/.agents/.skill-lock.json`) — it never installs a skill that isn't already there. That is exactly the intended effect: editing a project-local skill in this repo and running the roundtrip updates it for any project that has separately opted in via `add -s <skill-name>` (no `-g`), without ever pushing it onto every machine-wide session.

1. Edit skill files in this working copy (`~/Documents/Projekte/skills/`).
2. **Work on `dev`, never commit directly on `main`** (solo-dev branch guard — see the global `~/.claude/CLAUDE.md`; a `pre-commit` hook blocks commits on `main`/`master` once `dev` exists). Before any commit, confirm `HEAD` is on `dev`; if a `dev` branch does not yet exist, create it from `main` (`git switch -c dev`).
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/) — `feat(skill-name): …`, `fix(skill-name): …`, `docs: …`, `chore: …`. No `Co-Authored-By` trailer (enforced by `commit-msg`).
4. **Publish both branches, in this order:**
   - `git push origin dev` — publish the work.
   - `git switch main && git merge --ff-only dev && git push origin main && git switch dev` — fast-forward `main` to match `dev` and publish it. `--ff-only` creates no merge commit; this ff-merge of `dev` into `main` is the only merge this repo ever does.
5. **Then** refresh with **`update`**, never `add`, and never before step 4 (otherwise `update` pulls a stale `main` and the edit silently does not land):
   - `npx skills@latest update -g -y` — refresh every **global**-scope skill already tracked (see "Skill scope" above; installs nothing new).
   - Edited a **project-local** skill? It refreshes the same way but scoped per project: run `update <skill-name> -y` (no `-g`) from that project's root — one call per project that installed it.

   **`add` is only for a first-time install, never a refresh**, and its scope (`-g` or not) follows "Skill scope" above, which also has the exact command and the `cwd` danger (running `add` from inside this repo clobbers `skills/<skill-name>/` with a symlink; always `cd` outside the repo first).

**Never edit `~/.claude/skills/<skill-name>/` directly.** Those paths are CLI-managed symlinks into `~/.agents/skills/<skill-name>/`. Any edit there is overwritten on the next install.

**Standing authorization for this exact roundtrip.** The operator has pre-authorized the literal sequence above as the default close-out of any skill edit in this repo — run it without pausing to ask each time, per the global `~/.claude/CLAUDE.md` note that durable CLAUDE.md instructions are a valid advance-authorization mechanism. It does **not** extend to anything else the global rules still gate on confirmation (force-push, `git reset --hard`, history rewrites) or to `add -g`, which stays a separate, explicit, per-skill decision (see "Skill scope" above) even for a global-listed skill.

## Repo layout

`README.md`/`CLAUDE.md`/`CONTEXT.md`/`LICENSE` at the root; each skill lives in `skills/<name>/` (`SKILL.md` plus whatever supporting files it needs — `REFERENCE.md`, `scripts/`, extra phase docs) and is bundled wholesale by the `skills` CLI, so nothing besides the skill's own files belongs in that directory.

`tests/<skill-name>/` sits **outside** `skills/` on purpose — shipping tests to every installer would bloat the bundle. Tests stay in the repo for AI-agent maintenance but never travel with the install.

## Adding a new skill

1. `mkdir skills/<new-name>`.
2. Create `skills/<new-name>/SKILL.md` with YAML frontmatter:

   ```yaml
   ---
   name: <new-name>           # lowercase, hyphens; MUST match the directory name
   description: <English prose, ≤ 250 chars HARD CAP; end with trigger phrases (may be German) — see "Authoring language" and CONTEXT.md "Trigger pattern">
   ---

   # <Human Title>

   …
   ```

3. Add supporting files as needed (`REFERENCE.md`, `scripts/`, additional phase `.md` files). Everything in the skill's directory is bundled as-is by the `skills` CLI.
4. **Decide global vs project-local and add the name to the matching list** in "Skill scope" above (default: project-local). Mirror the same scope tag in the new `README.md` entry (next step).
5. **Update `README.md`** — add a `### <skill-name>` block in the "The skills" section using the same *Problem/Fix* shape as the existing entries, tagged with its scope. The README is the public surface; a skill that is not in it is invisible to anyone browsing the repo.
6. Commit, push, roundtrip. If the new skill is project-local, it is *not* installed anywhere by the roundtrip — install it into the specific project(s) that need it via the `add -s <skill-name>` command in "Skill scope" above.

## Frontmatter rules (enforced by the `skills` CLI)

- `name` — required. Lowercase, hyphens only. MUST match the directory name.
- `description` — required, one paragraph, **≤ 250 characters (hard cap)**. It *is* the auto-invoke router, so it must carry the core trigger phrases and nothing more — but not so short the model can't tell when to load the skill; aim for ~200–250 chars. Count before committing (`python3 -c 'print(len(open("…").read()))'` on the extracted value).
- `metadata.*` — optional. Used for extra hints.
- `disable-model-invocation: true` — **the default for every new skill**, not an afterthought: it drops the `description` from the model's ambient context entirely, so a skill that carries it costs zero tokens on sessions that never use it. Leave it unset only when the answer to *"would the model ever usefully load this without the user typing the slash command?"* is genuinely yes — auto-discovery via natural-language triggers is then the whole point, and that's carve-out #1 in "Authoring language" below. When in doubt, set it; a missed auto-trigger is recoverable (the user just types the slash command), a silently bloated context on every unrelated session is not.

Frontmatter is currently checked by hand. If the skill count grows, add a small lint script and a CI job.

## Harness hygiene (context discipline)

Every model-invoked skill pre-loads its `description` into the system prompt at startup ([Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)); a large always-on skill set is real context cost and degrades routing ("context rot"). Two ongoing practices keep the harness lean:

1. **Invocation-type discipline** — classify every new skill as a *procedure* (user-invoked, `disable-model-invocation: true` — the default) or an *ability* (model-invoked, description stays in context — only when auto-discovery is genuinely the point). See the `disable-model-invocation` rule above.
2. **Scope discipline** — global vs project-local, per "Skill scope" above. This is the bigger lever: a project-local skill installed globally by mistake costs its full description on *every* session forever, not just this repo's.
3. **Periodic blank-slate audit** — periodically review the loaded skill/agent/MCP surface **in a fresh session** (not at the tail of a long one — a polluted context mismeasures the baseline) to catch description leak, redundant globally-installed skill clusters (including duplicates from other install paths, e.g. a skill loaded both via the `skills` CLI and via a Claude Code plugin under a prefixed name), and stale lock entries pointing at skills deleted upstream.

## Authoring language (HARD RULE)

**Skill documentation is written in English.** This is non-negotiable and applies to every new skill and every edit: `SKILL.md` (including the `description` prose), every supporting/phase/reference `.md` file, code comments inside scripts, and the skill's `README.md` block. The repo's baseline is English (this file, `README.md`); a German skill body is a defect to fix, not a style choice. Rationale: a skill must be readable by any agent or maintainer that picks it up, and mixed-language bodies fracture that.

The user prompts in German and the *running* agent still talks to the user in German (per the global `~/.claude/CLAUDE.md` language rule) — that is conversation, not skill source, and is unaffected by this rule.

Three deliberate carve-outs stay non-English (everything else is English):

1. **Trigger phrases in the `description`.** German trigger phrases may — and should — be kept alongside the English ones, because the `description` is the auto-invoke router and the user phrases requests in German (e.g. `'Notiz anlegen'`, `'BSI-Audit durchführen'`). The descriptive prose around them is still English.
2. **Functional language data.** Content that *is* the skill's payload rather than its documentation stays in its native language. These are data, not prose.
3. **Deliberate German artifact/output mandates.** Where German is the skill's stated intent for what it *produces*, the mandate stays (phrased in English). Example: `deep-monograph` mandates that the produced monograph defaults to German because the process it implements was authored for a German-speaking home-user audience — the instruction is English, the mandated artifact language is German on purpose (overridable if the user explicitly asks for another language).

When in doubt, ask: is this string *documentation* (→ English) or *payload/trigger/output* (→ may stay German)?

## Tooling and testing

There is no CI and no global test runner. Verification is still the roundtrip: push, install, confirm the skill is discoverable in a fresh agent session.

**Tests are welcome where a script can fail silently** — i.e. where a bug produces plausible-but-wrong output that the roundtrip cannot see. Today this applies to:

- `skills/apple-notes/scripts/_helper.py` — regex-driven HTML stripping and base64 extraction. A missed edge case produces text the agent will happily use without noticing the loss. Tests live at `tests/apple-notes/test_helper.py`.
- `skills/owasp-bsi-audit/scripts/build_catalog.py` and `render_report.py` — the catalog parser's regex/XML parsing and the renderer's sorting/grouping/scope-diffing logic can each produce a plausible-but-wrong result (a mis-parsed control, a mis-sorted finding) that only shows up as a subtly wrong report a human has to notice by eye. Tests live at `tests/owasp-bsi-audit/test_build_catalog.py` and `test_render_report.py`.
- `skills/name-clearance-red-team/scripts/*.py` — the risk model, digital-availability classifiers, name-variant generator, and report renderer all produce exactly this failure mode (a blocked lookup misread as "no hits", a wrong verdict, a missed variant) rather than an obvious crash. Tests live at `tests/name-clearance-red-team/test_*.py`.

### Conventions

- Plain `unittest` (stdlib). No framework, no requirements file, no fixtures dir. A test file should be runnable with `python3 tests/<skill-name>/test_*.py` from the repo root.
- Tests set `sys.dont_write_bytecode = True` and pass `PYTHONDONTWRITEBYTECODE=1` to any subprocesses, so they leave no `__pycache__` inside `skills/`. `.gitignore` covers it as a second line of defense.
- Run them locally before pushing if you touched the underlying script. There is no CI to catch a red test.

## Agent skills

### Issue tracker

Issues and specs live as local markdown files under `.scratch/` (gitignored — local to this machine, not committed). See `docs/agents/issue-tracker.md`.

### Triage labels

Standard five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line per issue file — no external label system to map against. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Vocabulary

See [`CONTEXT.md`](./CONTEXT.md). Read it before introducing new terms.
