# CLAUDE.md — Maintenance Guide for AI Agents

This repo is the source of truth for my personal Claude Code skills. It is maintained by AI agents (mostly Claude Code itself) — that is who this guide is for.

## Skill scope: global vs project-local

Most skills in this repo are **project-local by design** — they belong only in the specific project(s) that need them, never on every machine-wide session. Only a skill that is genuinely useful *regardless of what repo you're in* (or with no repo open at all) earns global status. This table is the single source of truth; update it whenever a skill is added, removed, or its scope changes — and mirror the same marker in `README.md`.

| Skill | Scope | Why |
|---|---|---|
| `apple-notes` | global | macOS system utility, not tied to any codebase |
| `brainstorming` | global | generic ideation, works on any topic |
| `deep-monograph` | global | generic long-form writing, not code-tied |
| `escalate` | global | meta-routing skill, useful in every project |
| `fetch-open-chat-tab` | global | generic macOS/Safari utility |
| `fetch-shared-chat` | global | generic URL fetcher |
| `name-clearance-red-team` | global | ad hoc naming/trademark research, not code-tied |
| `owasp-bsi-audit` | global | explicit standing exception, see the global `~/.claude/CLAUDE.md` |
| `app-icon-director` | project-local | only relevant to app projects shipping an icon |
| `blender-scripting` | project-local | only relevant to 3D/game projects |
| `game-asset-director` | project-local | only relevant to game projects |
| `godot-cli` | project-local | only relevant to Godot projects |
| `marketing-video-automation` | project-local | only relevant to app projects producing marketing videos |
| `seo-aso-optimizer` | project-local | only relevant to web/app projects doing SEO/ASO |

**Global provisioning is `update`-only — never `add -g`.** Running `npx skills@latest add silvio-l/skills -g` for a *project-local* skill is exactly how machine-wide skill bloat happens: every future project pays its ambient context cost even when it never uses it. `add -g` is therefore never part of any automated or standing-authorized sequence in this repo — it is a deliberate, individual, human-made decision, and only ever for a skill this table marks **global**.

To use a **project-local** skill in a project that needs it, install it there (never with `-g`), from *outside* this repo's working directory:

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
5. **Then** refresh with **`update`**, never `add`, and never for a skill this repo doesn't already have installed somewhere:
   - `npx skills@latest update -g -y` — refresh every **global**-scope skill already tracked (see the scope table above). Auto-detects the source repo per skill, pulls only what changed, installs nothing new.
   - `npx skills@latest update <skill-name> -g -y` — refresh one global skill, e.g. `update apple-notes -g -y`.
   - A **project-local** skill you edited here refreshes the same way, but scoped to whichever project(s) installed it: run `update <skill-name> -y` (no `-g`) from that project's root.

   Run this only **after step 4** (both branches pushed, `main` current) — otherwise `update` pulls a stale `main` and the edit silently does not land.

   **`add` is only for a first-time install, never a refresh**, and its scope (`-g` or not) follows the scope table — see "Skill scope" above for the exact command and the `cwd` danger (running `add` from inside this repo clobbers `skills/<skill-name>/` with a symlink; always `cd` outside the repo first). The `-g` failure this used to note (`PromptScript: PromptScript does not support global skill installation`) is real but harmless — it only affects the unrelated "PromptScript" agent target; every other agent (including Claude Code) installs fine, verify via `ls ~/.agents/skills/<skill-name>`.

**Never edit `~/.claude/skills/<skill-name>/` directly.** Those paths are CLI-managed symlinks into `~/.agents/skills/<skill-name>/`. Any edit there is overwritten on the next install.

**Standing authorization for this exact roundtrip.** The operator has pre-authorized the literal sequence above (`git push origin dev` → `git switch main && git merge --ff-only dev && git push origin main && git switch dev` → `npx skills@latest update … -g -y`) as the default close-out of any skill edit in this repo — run it without pausing to ask each time. This is a narrow carve-out for this specific sequence in this specific repo, per the global `~/.claude/CLAUDE.md` note that durable CLAUDE.md instructions are a valid advance-authorization mechanism. It does **not** extend to anything else that repo's global rules still gate on confirmation — force-push, `git reset --hard`, history rewrites, or any operation outside this exact roundtrip. It especially does **not** cover `add -g`: installing a skill globally for the first time is always a separate, explicit, individual decision (see "Skill scope" above), never something this close-out performs on its own.

## Repo layout

```
.
├── README.md              ← public-facing overview; lists every skill
├── LICENSE                ← MIT
├── CLAUDE.md              ← this file
├── CONTEXT.md             ← vocabulary for skill authoring
├── .gitignore
├── skills/                ← bundled as-is by the skills CLI
│   ├── apple-notes/
│   │   ├── SKILL.md
│   │   ├── REFERENCE.md
│   │   └── scripts/
│   │       ├── apple-notes        ← dispatcher (AppleScript wrapper)
│   │       └── _helper.py         ← HTML→text + base64 extraction
│   ├── deep-monograph/
│   │   ├── SKILL.md
│   │   ├── clarification.md
│   │   ├── capabilities-and-modes.md
│   │   ├── process.md
│   │   ├── research-and-sources.md
│   │   ├── didactics-and-writing.md
│   │   └── quality-and-output.md
│   └── owasp-bsi-audit/
└── tests/                 ← NOT shipped by the skills CLI
    └── apple-notes/test_helper.py
```

`tests/` lives outside `skills/` on purpose. The `skills` CLI bundles a skill directory wholesale, so anything beside `SKILL.md` (and friends) ends up on every installer's disk. Tests stay in the repo for AI-agent maintenance but never travel with the install.

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
4. **Decide global vs project-local and add a row to the scope table** in "Skill scope" above. Default to project-local — a skill earns global only if it's useful regardless of which repo (or no repo) is open; see that table's existing rows for the bar. Mirror the same scope marker in the new `README.md` entry (next step).
5. **Update `README.md`** — add a `### <skill-name>` block in the "The skills" section using the same *Problem/Fix* shape as the existing entries, tagged with its scope. The README is the public surface; a skill that is not in it is invisible to anyone browsing the repo.
6. Commit, push, roundtrip. If the new skill is project-local, it is *not* installed anywhere by the roundtrip — install it into the specific project(s) that need it via the `add -s <skill-name>` command in "Skill scope" above.

## Frontmatter rules (enforced by the `skills` CLI)

- `name` — required. Lowercase, hyphens only. MUST match the directory name.
- `description` — required. One paragraph, **≤ 250 characters. This is a hard cap — never exceed it.** The description *is* the auto-invoke router: it must carry the core trigger phrases ("Use when …") and nothing more. Push every detail (modes, flags, tool lists, examples) into the body. Don't overcorrect into terseness either — too short and the model can't tell when to load the skill; aim for ~200–250 chars with the essential triggers intact. Count characters before committing (`python3 -c 'print(len(open("…").read()))'` on the extracted value, or just eyeball against an existing in-cap skill).
- `metadata.*` — optional. Used for extra hints.
- `disable-model-invocation: true` — optional. Makes the skill **user-invoked only** (a procedure) and removes its `description` from the model's auto-invoke context entirely, so it costs zero ambient tokens. Set it on skills you always trigger deliberately by slash command and would never want the model to auto-load — e.g. heavyweight, stateful, or argument-driven controllers. **Do NOT set it** on skills whose value is auto-discovery via natural-language triggers — disabling those defeats carve-out #1 in "Authoring language". The test: *would the model ever usefully load this without the user typing the slash command?* If no → disable.

Frontmatter is currently checked by hand. If the skill count grows, add a small lint script and a CI job.

## Harness hygiene (context discipline)

Every model-invoked skill pre-loads its `description` into the system prompt at startup ([Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)); a large always-on skill set is real context cost and degrades routing ("context rot"). Two ongoing practices keep the harness lean:

1. **Invocation-type discipline** — classify every new skill as a *procedure* (user-invoked; prefer `disable-model-invocation: true`) or an *ability* (model-invoked; description stays in context). Default to procedure unless auto-discovery is the point. See the `disable-model-invocation` rule above.
2. **Scope discipline** — global vs project-local, per the "Skill scope" table above. This is the bigger lever: a project-local skill installed globally by mistake costs its full description on *every* session forever, not just this repo's.
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

- Tests live in `tests/<skill-name>/` at the repo root — **outside** `skills/`. The `skills` CLI bundles a skill directory wholesale; shipping tests to every installer would just bloat the bundle.
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
