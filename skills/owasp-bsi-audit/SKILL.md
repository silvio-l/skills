---
name: owasp-bsi-audit
description: "Runs an OWASP ASVS/MASVS + BSI IT-Grundschutz security compliance audit (plus curated NIST SSDF/SLSA subsets) via orchestrated subagents, producing report.md/report.html and a fix plan. Usage: /owasp-bsi-audit <target-path>"
disable-model-invocation: true
metadata:
  argument-hint: "<target-path>"
---

# OWASP + BSI IT-Grundschutz Audit

Audits like a human auditor would — only automated and more thorough: every control assessed individually, every verdict justified. The main context stays free because the actual assessment work goes to subagents that write their results to disk (see [ORCHESTRATION.md](ORCHESTRATION.md)). The BSI portion follows [BSI-Standard 200-2](BSI-METHODIK.md) — Schutzbedarf is fixed at **normal** (Basis + Standard requirements) per this skill's design.

**Report language note:** the generated `report.md`/`report.html`/`fix-plan.md` are deliberately written in **German** — BSI IT-Grundschutz is a German standard with German normative vocabulary (MUSS/SOLLTE, Basis-/Standard-Anforderungen, Umsetzungsstatus ja/teilweise/nein/entbehrlich), and the audience for a Grundschutz-Check is German-speaking. This skill's own documentation (this file and its siblings) is English per repo convention; only the report *output* is German by design.

## Flow

1. **Check catalog freshness.** Read `catalog/SOURCES.md`. Older than 90 days or a file is missing → run `python3 scripts/build_catalog.py` (fetches the latest ASVS/MASVS/BSI/SSDF/SLSA editions, see below). Briefly tell the user if a refresh ran.
2. **Confirm the target directory.** If the user didn't name a path, ask or infer it from context. Create `<repo>/.audit-tmp/`.
3. **Structure analysis.** One `Agent` call, `model: haiku`, following the prompt skeleton in ORCHESTRATION.md step 1. Result: `.audit-tmp/profile.json`.
4. **Schutzbedarf + modeling.** Directly in the main thread (small enough), following BSI-METHODIK.md Phase 2+3; write `.audit-tmp/methodik.json`. Derive the list of candidate control groups from it.
5. **Baustein/standard selection (confirm with the user).** Present the candidate list from step 4 — grouped by standard (BSI Bausteine, ASVS chapters, MASVS groups if mobile targets were found, SSDF/SLSA groups if applicable) — and ask the user which ones to actually run this audit against, via `AskUserQuestion` (multiSelect). Default selection = everything the modeling step proposed, but the user must confirm or adjust before dispatch; never silently run the full catalog without this checkpoint. This mirrors BSI-200-2's real-world practice of a human-reviewed Modellierung. Record the confirmed selection in `methodik.json` (`modellierung[].bausteine` reflects only the confirmed set).
6. **Fan-out / Grundschutz-Check.** One `Agent` call per confirmed group, `model: sonnet`, following ORCHESTRATION.md step 3, in batches of 3–5 in parallel. Each writes `.audit-tmp/findings/<group-id>.json` and returns only a one-line summary.
7. **Render.** `python3 scripts/render_report.py .audit-tmp/ --html` (always pass `--html` unless the user explicitly wants Markdown only). Produces `report.md`, `report.html`, `fix-plan.md` — layout in [REPORTING.md](REPORTING.md).
8. **Wrap-up.** Short summary (totals per standard, top findings) plus the three file paths, to the user. Don't paste the full findings into the chat — the files are the source of truth.

A run is done when: every confirmed control group has written a `findings/<group-id>.json`, `render_report.py` completed without error, and all three methodology-report sections (Strukturanalyse, Schutzbedarf, Grundschutz-Check) are non-empty.

## Catalog scope

- **ASVS 5.0** (L1+L2 = normal) — web backends, APIs.
- **MASVS 2.1** — only when structure analysis finds Flutter/React Native targets.
- **BSI Bausteine** (Basis+Standard) — only the code-/config-checkable ones: CON.8, CON.10, APP.3.1, APP.3.2 (config-checkable parts), APP.4.3 (MySQL), APP.1.4 (mobile apps — only when mobile targets exist). Pure hosting/infrastructure requirements are tracked via `out_of_scope_reason`, not dropped — details in [BSI-METHODIK.md](BSI-METHODIK.md). Most of the BSI Kompendium's ~111 Bausteine (ISMS, ORP, OPS, NET, INF, IND layers) are organizational-governance or physical-infrastructure and were deliberately excluded — they don't fit a code audit for a solo developer or small team without a dedicated ops/security department.
- **NIST SSDF** (curated, 5 of 65 practices) — only practices that are (a) not already covered by BSI CON.8/CON.10 or ASVS, (b) not the job of the separate `full-quality-scan` skill (static analysis, dependency scanning), and (c) code-/config-checkable without a formal organizational process. See `SSDF_SELECTED_IDS` in `build_catalog.py`.
- **SLSA** (curated, Build track only, 2 requirements) — supply-chain build integrity: hosted CI vs. manual builds, build provenance. The Source track is excluded (SLSA Level 4 requires two-party review, not achievable for a solo developer).

## Important rules

- Every `Agent` call sets `model:` explicitly (`haiku` for recon, `sonnet` for assessment) — never inherit the default.
- BSI findings **always** use the vocabulary `ja/teilweise/nein/entbehrlich`, with a mandatory justification for `entbehrlich` and for `nein`/`teilweise` at Standard level (Basis requirements should be `ja`). OWASP/SSDF/SLSA findings use `pass/fail/partial/n_a`. Schema: [`schema/finding.schema.json`](schema/finding.schema.json).
- Read config values for real where possible (php.ini, security headers, .htaccess, TLS) — don't just assert them.
- `.audit-tmp/` does not belong in the audited repo — don't commit it, just point the user to it at the end.
