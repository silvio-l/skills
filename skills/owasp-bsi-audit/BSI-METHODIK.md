# BSI-Standard 200-2 — Process Model for the Grundschutz-Check

Reference: [BSI-Standard 200-2 "IT-Grundschutz-Methodik"](https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/BSI_Standards/standard_200_2.pdf). This skill maps the standard's operative phases 1–4 onto a single app/backend instead of an entire organization — the Informationsverbund is the audited application. Phases 5–7 (risk analysis per 200-3, implementation, maintenance) are organizational and out of this skill's scope; the report only notes them.

## Phase 1 — Strukturanalyse (structure analysis)

Goal: which **Zielobjekte** (target objects) belong to the Informationsverbund? The recon subagent captures them explicitly (not just files, but named objects):

- Applications/services (e.g. "REST API backend", "admin panel")
- Data stores (e.g. "MySQL database, user data")
- Client applications (Flutter app, React frontend)
- Communication paths (e.g. "TLS connection app↔API")
- Config/operations objects controllable via code/config (php.ini, .htaccess, webserver vhost config if present in the repo)

Each Zielobjekt gets a short ID (`Z1`, `Z2`, …) and a title. Result lives in `audit/methodik.json` under `strukturanalyse`.

## Phase 2 — Schutzbedarfsfeststellung (protection-need assessment)

Goal: for each Zielobjekt, assess the Schutzbedarf (protection need) across **confidentiality, integrity, availability**. This skill's default is **normal** (the user's requirement for the whole audit). The orchestrator still documents a short justification per Zielobjekt for why "normal" is appropriate — and flags outliers:

- Does the object hold payment data, health data, plaintext auth secrets, or similar? → note "tendentially **hoch**" (high), referencing BSI-Standard 200-3 (risk analysis), which this skill does **not** perform but recommends.
- Otherwise: "normal" with a one-sentence justification (e.g. "standard user data, no special protection need beyond the baseline").

Result in `audit/methodik.json` under `schutzbedarf` (per Zielobjekt: `vertraulichkeit`, `integritaet`, `verfuegbarkeit`, `einschaetzung`, `begruendung`).

## Phase 3 — Modellierung (modeling)

Goal: map each Zielobjekt to the matching Bausteine/standards. Since the catalogs are already pre-filtered to code-/config-relevant Bausteine (see `catalog/SOURCES.md`), modeling reduces to a short mapping table:

| Zielobjekt type | Mapped Bausteine/standards |
|---|---|
| Backend application/API | CON.8, CON.10, APP.3.1, SSDF (curated), SLSA Build (curated) |
| Webserver config (in the repo, e.g. .htaccess) | APP.3.2 (only the configurable parts) |
| Relational database (MySQL) | APP.4.3 |
| Mobile app (Flutter/React Native) | APP.1.4, ASVS chapters + MASVS |

This proposed mapping is **not** applied automatically — the orchestrator presents it to the user and asks which Bausteine/groups to actually run (see SKILL.md step 5, "Baustein/standard selection"). This mirrors how a real Grundschutz-Check's Modellierung is human-reviewed, not a fixed formula. Result in `audit/methodik.json` under `modellierung` (list of `{zielobjekt_id, bausteine[], begruendung}`), reflecting only the confirmed selection.

### Why most of the BSI Kompendium is out of scope

The full BSI Kompendium has ~111 Bausteine across 10 layers (ISMS, ORP, CON, OPS, DER, APP, SYS, NET, IND, INF). Only a small subset survived review as genuinely code-/config-checkable and appropriate for a solo developer or small team without a dedicated ops/security department:

- **ISMS/ORP/OPS/DER layers** (security management, organization, personnel, operations, detection/response) are almost entirely organizational-governance practices — formal roles, documented processes, procurement policies, incident-response teams — that don't translate to "check this in the code" and don't fit an individual developer. Excluded wholesale.
- **NET/INF layers** (network, physical/building) are pure infrastructure, already out of scope per the "Nicht in unserer Hand" boundary.
- **SYS layer** (servers, clients, devices) is mostly hosting/device-management, likewise out of scope for shared/managed hosting.
- Within **APP/CON**, several Bausteine were considered and rejected after reading their actual requirement text (not just the title) — e.g. APP.6 "Allgemeine Software" turned out to be enterprise software-procurement governance (roles like "Beschaffungsstelle"), and CON.6 "Löschen und Vernichten" turned out to be almost entirely about physical media destruction, not application-level data deletion. Only Bausteine describing an actual software artifact (a web app, a database, a mobile app, the dev process itself) survive: CON.8, CON.10, APP.3.1, APP.3.2, APP.4.3, APP.1.4.

## Phase 4 — IT-Grundschutz-Check

The actual Soll-Ist (should-vs-is) comparison: for each requirement of a mapped Baustein, the **Umsetzungsstatus** (implementation status) is determined. This is the core work of the fan-out subagents (see ORCHESTRATION.md). Mandatory vocabulary (see `finding.schema.json`):

| Status | Meaning | Justification required |
|---|---|---|
| `ja` (yes) | fully implemented | no |
| `teilweise` (partial) | partially/incompletely implemented | yes (what's missing) |
| `nein` (no) | not implemented | yes (why, risk) |
| `entbehrlich` (not applicable) | requirement doesn't apply / deliberately not implemented | **yes, mandatory** |

Rule from 200-2 that every assessor subagent follows:
- **Basis requirements** (MUSS/must) should generally be fully implemented (`ja`). An `entbehrlich` at Basis level is the exception and needs a genuinely solid justification (e.g. "requirement concerns the physical server room — outside our area of responsibility, see hosting section").
- **Standard requirements** (SOLLTE/should) should be implemented; `nein` or `teilweise` is permitted but requires a visible remediation plan in the fix-plan rather than a bare note.
- The assessment is a **professional judgment**, not a grep hit: the subagent reads the relevant code/config, forms a picture of the actual behavior (e.g. "is input really validated here before the query runs?"), and justifies its status with concrete evidence — exactly as a human auditor would through interview and document review.

## Phase 5 (referenced, not executed) — Risk analysis per 200-3

Only relevant if Phase 2 flagged a Zielobjekt as "tendentially hoch". The report then notes: "For Zielobjekt Zx, a supplementary risk analysis per BSI-Standard 200-3 is recommended given protection need > normal — out of scope for this automated check." For all objects at Schutzbedarf normal, the note reads "risk analysis not required (Schutzbedarf normal)".

## Phases 6–7 — Remediation planning/implementation/maintenance

Remediation planning is delivered by the skill as `fix-plan.md` (prioritized, Basis deficits first). Implementation and maintenance (recertification, ongoing operations) are organizational follow-up steps outside the skill — the report closes by recommending a re-audit once remediations are implemented.
