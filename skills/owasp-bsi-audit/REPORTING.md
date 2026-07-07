# Report and Fix-Plan Layout

Reference for `scripts/render_report.py` and for anyone touching up the output by hand. Goal: the report reads like the result of a real Grundschutz-Check — the process (BSI-METHODIK.md) must be traceable, not just the result.

**Note on languages:** this document (and the rest of the skill's own documentation) is English per repo convention. The actual generated `report.md`/`report.html`/`fix-plan.md` content described below is deliberately **German** — see the language note in `SKILL.md`.

## `report.md` — section order

1. **Title + metadata** — audited repo, date, catalog versions (from `catalog/SOURCES.md`), Schutzbedarf level (normal).
2. **Glossary** — abbreviations/terms actually used in this report (OWASP, ASVS, MASVS, BSI, SSDF, SLSA, Baustein, Basis/Standard, L1/L2, etc.), filtered to the standards present so it doesn't bloat when e.g. no mobile targets exist. See `GLOSSARY`/`glossary_entries()` in `render_report.py`.
3. **Executive Summary** — totals per standard (ASVS/MASVS/BSI/SSDF/SLSA), status distribution, top-5 critical open findings.
4. **Vorgehen (Methodik)** — short paragraph referencing BSI-Standard 200-2 and naming the four phases traversed (Strukturanalyse, Schutzbedarfsfeststellung, Modellierung, Grundschutz-Check). No filler — a reference is enough, detail lives in the following tables.
5. **Strukturanalyse** — table of all Zielobjekte (`profile.json`/`methodik.json`): ID, title, type, language/framework.
6. **Schutzbedarfsfeststellung** — table per Zielobjekt: C/I/A assessment, level (normal/hoch flag), justification. On a "hoch" flag: explicit reference to BSI-Standard 200-3.
7. **Modellierung** — table Zielobjekt ↔ mapped Bausteine/standards, justification.
8. **Angewendete Bausteine & Standards** ("applied Bausteine & standards") — one short table per standard actually present (BSI/ASVS/MASVS/SSDF/SLSA), listing only the groups that appear in the findings, with a one-line description of what each covers — context the reader needs before the detail tables.
9. **Abgrenzung** ("scope & exclusions") — explicit statement of what this audit deliberately does NOT cover: static-only (no pentest/dynamic testing), hosting/infrastructure layer, BSI-200-3 risk analysis, Hoch/L3-level requirements, any catalog groups that exist but weren't run this pass (computed by diffing the full catalog against what's present in the findings — see `compute_scope()`), and standards not applied at all (e.g. MASVS/SLSA when no mobile targets/CI pipeline were found).
10. **Grundschutz-Check (BSI, Soll-Ist)** — one table per Baustein, split into **Basis-Anforderungen** then **Standard-Anforderungen** subsections (Basis always first), each sorted by requirement number in natural order (A1 before A12, not lexicographic). Columns: requirement ID, title, Umsetzungsstatus, justification (if set), evidence, remediation.
11. **OWASP ASVS** — one table per chapter, split into L1 then L2 subsections (mirroring the BSI Basis/Standard split), naturally sorted within each.
12. **OWASP MASVS** (only if mobile Zielobjekte exist) — flat per group (no level split, MASVS 2.x has none), naturally sorted.
13. **NIST SSDF** (only if applicable) — flat per practice group (PW.6, PW.9, RV.1), naturally sorted.
14. **SLSA** (only if applicable) — flat, single Build group, naturally sorted.
15. **Manuelle Prüfung nötig** ("needs manual review") — all findings with `status: manual` (without `out_of_scope_reason`), listing what a human still needs to check.
16. **Nicht in unserer Hand** ("not ours to control", hosting/infrastructure) — all findings with `out_of_scope_reason` set.
17. **Risikoanalyse-Vermerk** — per Zielobjekt from section 6, the matching note ("not required, Schutzbedarf normal" or a 200-3 recommendation).
18. **Übersicht offener Punkte** ("overview of open items") — a flat table of every open finding (status nein/teilweise/fail/partial) across all standards, sorted by severity, each row with a copy-to-clipboard button that copies a ready-to-paste AI-agent fix prompt (see below) plus one combined button that copies all open findings as a single prompt.
19. **Abschluss** — pointer to `fix-plan.md` and a recommendation to re-audit after remediation.

## `fix-plan.md` — layout

A prioritized task list, grouped by urgency:

1. **Sofort** (immediate) — Basis-level deficits (`nein`/`teilweise`), or OWASP/SSDF/SLSA `fail`/`partial` at severity critical/high
2. **Kurzfristig** (near-term) — Standard-level deficits, medium severity
3. **Mittelfristig** (mid-term) — low/info severity, doc/process gaps

Per task: control ID, title, affected Zielobjekt, file reference (from evidence), concrete remediation, optionally responsible/deadline. No prose — a checklist, directly actionable.

## `report.html`

Same content as `report.md`, rendered as a dedicated self-contained HTML document directly from the same aggregated data (not a Markdown→HTML conversion) — this is what lets status/severity render as colored badges. Inline CSS, no external requests, light/dark theme aware (`prefers-color-scheme` + `data-theme` overrides). Only produced when `--html` is passed. See `build_html()` in `render_report.py`; the badge color scheme, stat cards, and copy-to-clipboard fix-prompt JS all live there.
