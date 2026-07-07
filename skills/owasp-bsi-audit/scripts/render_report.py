#!/usr/bin/env python3
"""
Renders report.md (+ optional report.html) and fix-plan.md from the audit
intermediate results (profile.json, methodik.json, findings/*.json).
Stdlib-only, deterministic - see REPORTING.md for the section layout.

Usage: python3 render_report.py <audit-dir> [--html]
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys

BSI_STATUS_LABEL = {
    "ja": "Ja", "teilweise": "Teilweise", "nein": "Nein",
    "entbehrlich": "Entbehrlich", "manual": "Manuell zu prüfen",
}
OWASP_STATUS_LABEL = {
    "pass": "Pass", "fail": "Fail", "partial": "Partial",
    "n_a": "N/A", "manual": "Manuell zu prüfen",
}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
BSI_STATUS_ORDER = {"nein": 0, "teilweise": 1, "manual": 2, "entbehrlich": 3, "ja": 4}
OWASP_STATUS_ORDER = {"fail": 0, "partial": 1, "manual": 2, "n_a": 3, "pass": 4}
BSI_LEVEL_ORDER = {"Basis": 0, "Standard": 1}
ASVS_LEVEL_ORDER = {"L1": 0, "L2": 1, "L3": 2}

# Glossary entries per standard: only the ones actually present in the
# report get rendered (see glossary_entries()), so the section doesn't
# bloat when e.g. no MASVS/SSDF/SLSA was applied.
GLOSSARY = {
    "always": [
        ("OWASP", "Open Web Application Security Project — gemeinnützige Organisation, "
                   "die Standards und Werkzeuge für Anwendungssicherheit veröffentlicht."),
        ("BSI", "Bundesamt für Sicherheit in der Informationstechnik — die deutsche Bundesbehörde, "
                "die den IT-Grundschutz herausgibt."),
        ("IT-Grundschutz", "Die BSI-Methodik zur Informationssicherheit: Bausteine mit konkreten "
                           "Anforderungen, gestuft nach Basis/Standard/erhöhtem Schutzbedarf."),
        ("Baustein", "Ein Themenblock im BSI-Kompendium (z.B. CON.10 „Entwicklung von "
                     "Webanwendungen“), der mehrere konkrete Anforderungen bündelt."),
        ("Basis-Anforderung", "BSI-Anforderungsebene: MUSS grundsätzlich vollständig umgesetzt sein."),
        ("Standard-Anforderung", "BSI-Anforderungsebene: SOLLTE umgesetzt sein; Abweichungen sind mit "
                                 "Begründung/Planung zulässig."),
        ("Schutzbedarf", "Wie hoch die Anforderungen an Vertraulichkeit/Integrität/Verfügbarkeit "
                         "eines Objekts eingeschätzt werden (normal/hoch/sehr hoch)."),
    ],
    "asvs": [
        ("ASVS", "Application Security Verification Standard (OWASP) — der Anforderungskatalog "
                 "für Web-Backends/APIs, den dieser Audit für den Webanwendungs-Teil nutzt."),
        ("L1/L2/L3", "ASVS-Anforderungsebenen (Level 1 = Basisschutz bis Level 3 = sehr hoher "
                     "Schutzbedarf). Dieser Audit prüft L1+L2 (Schutzbedarf normal)."),
    ],
    "masvs": [
        ("MASVS", "Mobile Application Security Verification Standard (OWASP) — der "
                  "Anforderungskatalog für mobile Apps (Flutter/React Native)."),
    ],
    "ssdf": [
        ("SSDF", "Secure Software Development Framework (NIST SP 800-218) — US-amerikanischer "
                 "Standard für sichere Software-Entwicklungspraktiken; hier nur eine kuratierte "
                 "Teilmenge, die nicht bereits durch BSI/OWASP abgedeckt ist (siehe Abgrenzung)."),
        ("NIST", "National Institute of Standards and Technology — US-Bundesbehörde für Standards, "
                 "u.a. Herausgeberin des SSDF."),
        ("PW / RV", "SSDF-Praktikengruppen: PW = „Produce Well-Secured Software“, RV = „Respond "
                    "to Vulnerabilities“."),
    ],
    "slsa": [
        ("SLSA", "Supply-chain Levels for Software Artifacts — Framework für die Integrität der "
                 "Software-Lieferkette (Build-Provenienz, Manipulationsschutz); hier nur der "
                 "Build-Track, kuratiert auf solo-dev-taugliche Prüfpunkte."),
        ("Provenienz", "Nachweis, wie und wo ein Software-Artefakt gebaut wurde — Grundlage dafür, "
                       "einem Build-Ergebnis zu vertrauen."),
    ],
}


def glossary_entries(present_standards):
    entries = list(GLOSSARY["always"])
    for std in ("asvs", "masvs", "ssdf", "slsa"):
        if std in present_standards:
            entries.extend(GLOSSARY[std])
    return entries


def natural_key(req_id):
    # "CON.10.A3" vs "CON.10.A12", "V7.10.1" vs "V7.3.2": compare digit
    # groups numerically instead of lexicographically, so A3 comes before A12.
    return [int(tok) if tok.isdigit() else tok.lower()
            for tok in re.split(r"(\d+)", req_id or "")]


def load_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_findings(audit_dir):
    findings_dir = audit_dir / "findings"
    findings = []
    for f in sorted(findings_dir.glob("*.json")) if findings_dir.exists() else []:
        data = load_json(f, [])
        for item in data:
            item.setdefault("_group_file", f.name)
            findings.append(item)
    return findings


def bsi_baustein_of(req_id):
    # e.g. "CON.8.A2" -> "CON.8", "APP.3.1.A4" -> "APP.3.1"
    if ".A" in req_id:
        return req_id.rsplit(".A", 1)[0]
    return req_id


def asvs_chapter_of(req_id):
    return req_id.split(".")[0]


def masvs_group_of(ctrl_id):
    parts = ctrl_id.split("-")
    return "-".join(parts[:2])


def ssdf_group_of(req_id):
    # "PW.6.1" -> "PW.6" (parent practice)
    return req_id.rsplit(".", 1)[0]


def slsa_group_of(req_id):
    # "SLSA-BUILD-1" -> "BUILD"
    parts = req_id.split("-")
    return "-".join(parts[1:-1]) or req_id


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        cells = [str(c).replace("\n", " ").replace("|", "\\|") for c in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def evidence_str(ev_list):
    if not ev_list:
        return "–"
    return "; ".join(f"{e.get('source', '?')}: {e.get('detail', '')}" for e in ev_list)


def is_open(f):
    return f.get("status") in ("nein", "teilweise", "fail", "partial")


def catalog_dir():
    return pathlib.Path(__file__).resolve().parent.parent / "catalog"


def load_catalog_summaries():
    # Best-effort: if the catalog is missing (e.g. skill installed
    # elsewhere), the scope/Bausteine section stays empty instead of
    # aborting the render.
    cdir = catalog_dir()
    bsi_meta, asvs_meta, masvs_meta, ssdf_meta, slsa_meta = {}, {}, {}, {}, {}

    bsi_data = load_json(cdir / "bsi-grundschutz-normal.json")
    if bsi_data:
        for b in bsi_data.get("bausteine", []):
            bsi_meta[b["baustein_id"]] = {
                "title": b.get("title", ""),
                "description": b.get("description", ""),
            }

    asvs_data = load_json(cdir / "asvs-5.0-web.json")
    if asvs_data:
        for g in asvs_data.get("groups", []):
            asvs_meta[g["chapter_id"]] = g.get("chapter_name", "")

    masvs_data = load_json(cdir / "masvs-2.1-mobile.json")
    if masvs_data:
        for g in masvs_data.get("groups", []):
            masvs_meta[g["masvs_group"]] = g.get("title", "")

    ssdf_data = load_json(cdir / "ssdf-1.1-curated.json")
    if ssdf_data:
        for g in ssdf_data.get("groups", []):
            ssdf_meta[g["practice_group"]] = g.get("title", "")

    slsa_data = load_json(cdir / "slsa-build-curated.json")
    if slsa_data:
        for g in slsa_data.get("groups", []):
            slsa_meta[g["practice_group"]] = g.get("title", "")

    return {"bsi": bsi_meta, "asvs": asvs_meta, "masvs": masvs_meta, "ssdf": ssdf_meta, "slsa": slsa_meta}


def compute_scope(bsi, asvs, masvs, ssdf, slsa, catalog_meta):
    bsi_covered = sorted({bsi_baustein_of(f.get("id", "")) for f in bsi})
    asvs_covered = sorted({asvs_chapter_of(f.get("id", "")) for f in asvs})
    masvs_covered = sorted({masvs_group_of(f.get("id", "")) for f in masvs})
    ssdf_covered = sorted({ssdf_group_of(f.get("id", "")) for f in ssdf})
    slsa_covered = sorted({slsa_group_of(f.get("id", "")) for f in slsa})

    bsi_meta, asvs_meta = catalog_meta["bsi"], catalog_meta["asvs"]
    masvs_meta, ssdf_meta, slsa_meta = catalog_meta["masvs"], catalog_meta["ssdf"], catalog_meta["slsa"]

    applied_bsi = [(c, bsi_meta.get(c, {}).get("title", ""), bsi_meta.get(c, {}).get("description", ""))
                   for c in bsi_covered]
    applied_asvs = [(c, asvs_meta.get(c, "")) for c in asvs_covered]
    applied_masvs = [(c, masvs_meta.get(c, "")) for c in masvs_covered]
    applied_ssdf = [(c, ssdf_meta.get(c, "")) for c in ssdf_covered]
    applied_slsa = [(c, slsa_meta.get(c, "")) for c in slsa_covered]

    not_covered_bsi = [(c, meta.get("title", "")) for c, meta in bsi_meta.items() if c not in bsi_covered]
    not_covered_asvs = [(c, name) for c, name in asvs_meta.items() if c not in asvs_covered]

    return {
        "applied_bsi": applied_bsi, "applied_asvs": applied_asvs, "applied_masvs": applied_masvs,
        "applied_ssdf": applied_ssdf, "applied_slsa": applied_slsa,
        "not_covered_bsi": sorted(not_covered_bsi), "not_covered_asvs": sorted(not_covered_asvs),
        "masvs_applied_at_all": bool(masvs), "ssdf_applied_at_all": bool(ssdf), "slsa_applied_at_all": bool(slsa),
    }


def build_markdown(audit_dir):
    profile = load_json(audit_dir / "profile.json", {}) or {}
    methodik = load_json(audit_dir / "methodik.json", {}) or {}
    findings = load_findings(audit_dir)

    bsi = [f for f in findings if f.get("standard") == "bsi"]
    asvs = [f for f in findings if f.get("standard") == "asvs"]
    masvs = [f for f in findings if f.get("standard") == "masvs"]
    ssdf = [f for f in findings if f.get("standard") == "ssdf"]
    slsa = [f for f in findings if f.get("standard") == "slsa"]
    all_findings = bsi + asvs + masvs + ssdf + slsa
    present_standards = {f.get("standard") for f in all_findings}

    today = datetime.date.today().isoformat()
    out = []
    out.append("# Security-Compliance-Audit — OWASP + BSI IT-Grundschutz\n")
    out.append(f"**Datum:** {today}  ")
    out.append(f"**Geprüftes Ziel:** {profile.get('target', profile.get('repo_path', 'n/a'))}  ")
    out.append("**Schutzbedarf:** normal (Basis + Standard-Anforderungen)  ")
    out.append("**Vorgehen:** nach BSI-Standard 200-2 (Strukturanalyse, Schutzbedarfsfeststellung, "
                "Modellierung, IT-Grundschutz-Check) sowie OWASP ASVS/MASVS, ergänzt um kuratierte "
                "Teilmengen von NIST SSDF und SLSA (siehe Abgrenzung).\n")

    # --- glossary ---
    out.append("## Glossar — Abkürzungen und Begriffe\n")
    rows = [[f"**{term}**", expl] for term, expl in glossary_entries(present_standards)]
    out.append(md_table(["Begriff", "Bedeutung"], rows) + "\n")

    # --- executive summary ---
    out.append("## Executive Summary\n")

    def status_counts(items):
        counts = {}
        for it in items:
            counts[it.get("status", "manual")] = counts.get(it.get("status", "manual"), 0) + 1
        return counts

    summary_rows = []
    for items, order, name in [
        (bsi, BSI_STATUS_ORDER, "BSI IT-Grundschutz"),
        (asvs, OWASP_STATUS_ORDER, "OWASP ASVS"),
        (masvs, OWASP_STATUS_ORDER, "OWASP MASVS"),
        (ssdf, OWASP_STATUS_ORDER, "NIST SSDF"),
        (slsa, OWASP_STATUS_ORDER, "SLSA"),
    ]:
        if not items:
            continue
        label_map = BSI_STATUS_LABEL if order is BSI_STATUS_ORDER else OWASP_STATUS_LABEL
        counts = status_counts(items)
        summary_rows.append([name, len(items),
                              ", ".join(f"{label_map.get(k, k)}: {v}" for k, v in
                                        sorted(counts.items(), key=lambda x: order.get(x[0], 9)))])
    out.append(md_table(["Standard", "Anzahl Kontrollen", "Status-Verteilung"], summary_rows) + "\n")

    critical = [f for f in all_findings
                if f.get("severity") in ("critical", "high")
                and f.get("status") in ("nein", "fail", "teilweise", "partial")]
    critical.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity"), 9))
    if critical:
        out.append("**Kritischste offene Findings:**\n")
        for f in critical[:5]:
            out.append(f"- `{f.get('id')}` ({f.get('severity')}): {f.get('title', '')}")
        out.append("")

    # --- Vorgehen (approach) ---
    out.append("## Vorgehen (Methodik)\n")
    out.append(
        "Der BSI-Anteil dieses Audits folgt dem operativen Vorgehensmodell aus "
        "**BSI-Standard 200-2**: Strukturanalyse (Zielobjekte erfassen) → "
        "Schutzbedarfsfeststellung (V/I/V je Zielobjekt) → Modellierung "
        "(Zielobjekt↔Baustein) → IT-Grundschutz-Check (Soll-Ist-Vergleich je "
        "Anforderung, Status ja/teilweise/nein/entbehrlich). Details siehe "
        "`BSI-METHODIK.md` des Skills. Der OWASP-Anteil (ASVS/MASVS) folgt dem "
        "Standard-Vokabular pass/fail/partial/n_a.\n"
    )

    # --- Strukturanalyse (structure analysis) ---
    strukturanalyse = methodik.get("strukturanalyse", [])
    out.append("## Strukturanalyse — Zielobjekte\n")
    if strukturanalyse:
        rows = [[z.get("id", ""), z.get("titel", ""), z.get("typ", ""), z.get("sprache_framework", "")]
                for z in strukturanalyse]
        out.append(md_table(["ID", "Titel", "Typ", "Sprache/Framework"], rows) + "\n")
    else:
        out.append("_Keine Strukturanalyse-Daten vorhanden (methodik.json fehlt oder leer)._\n")

    # --- Schutzbedarfsfeststellung (protection-need assessment) ---
    schutzbedarf = methodik.get("schutzbedarf", [])
    out.append("## Schutzbedarfsfeststellung\n")
    if schutzbedarf:
        rows = [[s.get("zielobjekt_id", ""), s.get("vertraulichkeit", ""), s.get("integritaet", ""),
                 s.get("verfuegbarkeit", ""), s.get("einschaetzung", ""), s.get("begruendung", "")]
                for s in schutzbedarf]
        out.append(md_table(["Zielobjekt", "Vertraulichkeit", "Integrität", "Verfügbarkeit",
                              "Einschätzung", "Begründung"], rows) + "\n")
    else:
        out.append("_Keine Schutzbedarfsfeststellung vorhanden._\n")

    # --- Modellierung (modeling) ---
    modellierung = methodik.get("modellierung", [])
    out.append("## Modellierung\n")
    if modellierung:
        rows = [[m.get("zielobjekt_id", ""), ", ".join(m.get("bausteine", [])), m.get("begruendung", "")]
                for m in modellierung]
        out.append(md_table(["Zielobjekt", "Zugeordnete Bausteine/Standards", "Begründung"], rows) + "\n")
    else:
        out.append("_Keine Modellierung vorhanden._\n")

    # --- applied Bausteine & standards / scope-and-exclusions ---
    catalog_meta = load_catalog_summaries()
    scope = compute_scope(bsi, asvs, masvs, ssdf, slsa, catalog_meta)

    out.append("## Angewendete Bausteine & Standards\n")
    out.append("Kurzbeschreibung dessen, was mit den tatsächlich geprüften Bausteinen/Kapiteln "
                "inhaltlich abgedeckt wird — als Einordnungshilfe, bevor die Detail-Tabellen folgen.\n")
    if scope["applied_bsi"]:
        out.append("**BSI IT-Grundschutz:**\n")
        rows = [[c, t, d] for c, t, d in scope["applied_bsi"]]
        out.append(md_table(["Baustein", "Titel", "Was geprüft wird"], rows) + "\n")
    if scope["applied_asvs"]:
        out.append("**OWASP ASVS:**\n")
        rows = [[c, t] for c, t in scope["applied_asvs"]]
        out.append(md_table(["Kapitel", "Titel"], rows) + "\n")
    if scope["applied_masvs"]:
        out.append("**OWASP MASVS:**\n")
        rows = [[c, t] for c, t in scope["applied_masvs"]]
        out.append(md_table(["Gruppe", "Titel"], rows) + "\n")
    if scope["applied_ssdf"]:
        out.append("**NIST SSDF (kuratierte Teilmenge):**\n")
        rows = [[c, t] for c, t in scope["applied_ssdf"]]
        out.append(md_table(["Praktikengruppe", "Titel"], rows) + "\n")
    if scope["applied_slsa"]:
        out.append("**SLSA (kuratierte Teilmenge, Build-Track):**\n")
        rows = [[c, t] for c, t in scope["applied_slsa"]]
        out.append(md_table(["Gruppe", "Titel"], rows) + "\n")

    out.append("## Abgrenzung — was explizit nicht betrachtet wurde\n")
    out.append(
        "Dieser Audit ist eine **statische Code-/Konfigurationsprüfung** (kein Penetrationstest, "
        "keine dynamische Testausführung, kein Live-Scan der laufenden Anwendung). Explizit "
        "außerhalb des Scopes:\n"
    )
    out.append("- **Hosting-/Infrastruktur-Ebene**: physische Sicherheit, Netzwerk-/Server-Betrieb "
                "außerhalb der Anwendungs-Konfiguration — siehe Abschnitt „Nicht in unserer Hand“.")
    out.append("- **Risikoanalyse nach BSI-Standard 200-3**: nicht durchgeführt (nur bei Schutzbedarf "
                "über normal relevant, siehe „Risikoanalyse-Vermerk“).")
    out.append("- **Anforderungen bei erhöhtem Schutzbedarf** (BSI „Hoch“) sowie **ASVS L3**: nicht "
                "Teil dieses Katalogs (Schutzbedarf normal = Basis + Standard bzw. L1+L2).")
    if scope["not_covered_bsi"]:
        liste = ", ".join(f"{c} ({t})" for c, t in scope["not_covered_bsi"])
        out.append(f"- **BSI-Bausteine im Katalog, aber in diesem Lauf nicht geprüft**: {liste}.")
    elif catalog_meta["bsi"]:
        out.append("- **BSI-Bausteine im Katalog**: alle katalogisierten Bausteine wurden in diesem Lauf geprüft.")
    if scope["not_covered_asvs"]:
        liste = ", ".join(f"{c} ({t})" for c, t in scope["not_covered_asvs"])
        out.append(f"- **ASVS-Kapitel im Katalog, aber in diesem Lauf nicht geprüft**: {liste}.")
    elif catalog_meta["asvs"]:
        out.append("- **ASVS-Kapitel im Katalog**: alle katalogisierten Kapitel wurden in diesem Lauf geprüft.")
    if not scope["masvs_applied_at_all"]:
        out.append("- **OWASP MASVS**: nicht angewendet — keine Flutter/React-Native-Zielobjekte "
                    "in der Strukturanalyse identifiziert.")
    out.append("- **NIST SSDF**: nur eine kuratierte Teilmenge von 5 der 65 offiziellen Praktiken "
                "wird geprüft — alle anderen sind bereits über BSI CON.8/CON.10 abgedeckt, gehören "
                "zum Aufgabenbereich des separaten `full-quality-scan`-Skills, oder sind "
                "Organisationsprozess-Anforderungen, die für Einzelentwickler nicht sinnvoll sind.")
    if not scope["slsa_applied_at_all"]:
        out.append("- **SLSA**: nicht angewendet — keine Findings vorhanden (Build-Track nur relevant, "
                    "wenn Strukturanalyse eine CI/CD-Build-Pipeline identifiziert hat).")
    else:
        out.append("- **SLSA**: nur der Build-Track (kuratiert auf 2 solo-dev-taugliche Prüfpunkte) "
                    "wird geprüft. Der Source-Track ist ausgeklammert (Level 4 verlangt "
                    "Zwei-Personen-Review, nicht erfüllbar für Einzelentwickler).")
    out.append("")

    # --- Grundschutz-Check (BSI) ---
    out.append("## Grundschutz-Check (BSI, Soll-Ist-Vergleich)\n")
    if bsi:
        by_baustein = {}
        for f in bsi:
            b = bsi_baustein_of(f.get("id", ""))
            by_baustein.setdefault(b, []).append(f)
        for baustein_id in sorted(by_baustein):
            out.append(f"### {baustein_id}\n")
            items_by_level = by_baustein[baustein_id]
            for level in ("Basis", "Standard"):
                level_items = sorted(
                    (f for f in items_by_level if f.get("level") == level),
                    key=lambda f: natural_key(f.get("id", "")),
                )
                if not level_items:
                    continue
                out.append(f"#### {level}-Anforderungen\n")
                rows = [[f.get("id"), f.get("title", ""),
                          BSI_STATUS_LABEL.get(f.get("status"), f.get("status")),
                          f.get("begruendung", "") or "–", evidence_str(f.get("evidence")),
                          f.get("remediation", "")]
                         for f in level_items]
                out.append(md_table(["Anforderung", "Titel", "Status", "Begründung", "Evidence", "Remediation"], rows) + "\n")
    else:
        out.append("_Keine BSI-Findings vorhanden (kein zutreffender Baustein oder Audit noch nicht gelaufen)._\n")

    # --- ASVS ---
    out.append("## OWASP ASVS\n")
    if asvs:
        by_chapter = {}
        for f in asvs:
            c = asvs_chapter_of(f.get("id", ""))
            by_chapter.setdefault(c, []).append(f)
        for chapter in sorted(by_chapter):
            out.append(f"### {chapter}\n")
            chapter_items = by_chapter[chapter]
            levels_present = sorted({f.get("level", "") for f in chapter_items},
                                     key=lambda l: ASVS_LEVEL_ORDER.get(l, 9))
            for level in levels_present:
                level_items = sorted(
                    (f for f in chapter_items if f.get("level") == level),
                    key=lambda f: natural_key(f.get("id", "")),
                )
                out.append(f"#### {level}\n")
                rows = [[f.get("id"), f.get("title", ""),
                          OWASP_STATUS_LABEL.get(f.get("status"), f.get("status")),
                          f.get("severity", ""), evidence_str(f.get("evidence")), f.get("remediation", "")]
                         for f in level_items]
                out.append(md_table(["Control", "Titel", "Status", "Severity", "Evidence", "Remediation"], rows) + "\n")
    else:
        out.append("_Keine ASVS-Findings vorhanden._\n")

    # --- MASVS ---
    if masvs:
        out.append("## OWASP MASVS\n")
        by_group = {}
        for f in masvs:
            g = masvs_group_of(f.get("id", ""))
            by_group.setdefault(g, []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            out.append(f"### {group}\n")
            rows = [[f.get("id"), f.get("title", ""), OWASP_STATUS_LABEL.get(f.get("status"), f.get("status")),
                      f.get("severity", ""), evidence_str(f.get("evidence")), f.get("remediation", "")]
                     for f in items]
            out.append(md_table(["Control", "Titel", "Status", "Severity", "Evidence", "Remediation"], rows) + "\n")

    # --- SSDF ---
    if ssdf:
        out.append("## NIST SSDF (kuratierte Teilmenge)\n")
        by_group = {}
        for f in ssdf:
            by_group.setdefault(ssdf_group_of(f.get("id", "")), []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            out.append(f"### {group}\n")
            rows = [[f.get("id"), f.get("title", ""), OWASP_STATUS_LABEL.get(f.get("status"), f.get("status")),
                      f.get("severity", ""), evidence_str(f.get("evidence")), f.get("remediation", "")]
                     for f in items]
            out.append(md_table(["Practice", "Titel", "Status", "Severity", "Evidence", "Remediation"], rows) + "\n")

    # --- SLSA ---
    if slsa:
        out.append("## SLSA (kuratierte Teilmenge, Build-Track)\n")
        by_group = {}
        for f in slsa:
            by_group.setdefault(slsa_group_of(f.get("id", "")), []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            out.append(f"### {group}\n")
            rows = [[f.get("id"), f.get("title", ""), OWASP_STATUS_LABEL.get(f.get("status"), f.get("status")),
                      f.get("severity", ""), evidence_str(f.get("evidence")), f.get("remediation", "")]
                     for f in items]
            out.append(md_table(["Requirement", "Titel", "Status", "Severity", "Evidence", "Remediation"], rows) + "\n")

    # --- manual / out of scope ---
    manual = [f for f in all_findings if f.get("status") == "manual" and not f.get("out_of_scope_reason")]
    hosting = [f for f in all_findings if f.get("out_of_scope_reason")]

    out.append("## Manuelle Prüfung nötig\n")
    if manual:
        rows = [[f.get("id"), f.get("title", ""), f.get("remediation", "")] for f in manual]
        out.append(md_table(["ID", "Titel", "Was noch zu prüfen ist"], rows) + "\n")
    else:
        out.append("_Keine offenen manuellen Prüfpunkte._\n")

    out.append("## Nicht in unserer Hand (Hosting/Infrastruktur)\n")
    if hosting:
        rows = [[f.get("id"), f.get("title", ""), f.get("out_of_scope_reason", "")] for f in hosting]
        out.append(md_table(["ID", "Titel", "Grund"], rows) + "\n")
    else:
        out.append("_Keine Anforderungen als reine Hosting-Ebene markiert._\n")

    # --- Risikoanalyse-Vermerk (risk-analysis note) ---
    out.append("## Risikoanalyse-Vermerk\n")
    if schutzbedarf:
        for s in schutzbedarf:
            if s.get("einschaetzung", "normal") != "normal":
                out.append(f"- **{s.get('zielobjekt_id')}**: Schutzbedarf tendenziell über normal eingeschätzt — "
                            f"ergänzende Risikoanalyse nach BSI-Standard 200-3 empfohlen (außerhalb des Scopes "
                            f"dieses automatisierten Checks).")
            else:
                out.append(f"- **{s.get('zielobjekt_id')}**: Risikoanalyse nicht erforderlich (Schutzbedarf normal).")
    else:
        out.append("_Keine Schutzbedarfsfeststellung vorhanden — kein Vermerk möglich._")
    out.append("")

    # --- open-findings overview ---
    open_findings = sorted((f for f in all_findings if is_open(f)),
                            key=lambda f: SEVERITY_ORDER.get(f.get("severity"), 9))
    out.append("## Übersicht offener Punkte\n")
    if open_findings:
        rows = [[f.get("standard", "").upper(), f.get("id"), f.get("title", ""),
                  BSI_STATUS_LABEL.get(f.get("status"), OWASP_STATUS_LABEL.get(f.get("status"), f.get("status"))),
                  f.get("severity", "")]
                 for f in open_findings]
        out.append(md_table(["Standard", "ID", "Titel", "Status", "Severity"], rows) + "\n")
    else:
        out.append("_Keine offenen Punkte — alle geprüften Anforderungen sind erfüllt oder begründet "
                    "entbehrlich/nicht anwendbar._\n")

    out.append("## Abschluss\n")
    out.append("Priorisierte Maßnahmen siehe `fix-plan.md`. Nach Umsetzung wird ein Re-Audit empfohlen, "
                "um den Soll-Ist-Vergleich erneut zu prüfen.\n")

    return "\n".join(out), {"bsi": bsi, "asvs": asvs, "masvs": masvs, "ssdf": ssdf, "slsa": slsa}


def build_fix_plan(findings_by_standard):
    bsi = findings_by_standard["bsi"]
    other = (findings_by_standard["asvs"] + findings_by_standard["masvs"]
             + findings_by_standard.get("ssdf", []) + findings_by_standard.get("slsa", []))

    sofort, kurzfristig, mittelfristig = [], [], []
    for f in bsi:
        if not is_open(f):
            continue
        target = sofort if f.get("level") == "Basis" else kurzfristig
        target.append(f)
    for f in other:
        if not is_open(f):
            continue
        sev = f.get("severity")
        if sev in ("critical", "high"):
            sofort.append(f)
        elif sev == "medium":
            kurzfristig.append(f)
        else:
            mittelfristig.append(f)

    def task_line(f):
        parts = [f"- [ ] **{f.get('id')}** — {f.get('title', '')}"]
        if f.get("target_object"):
            parts.append(f"(Zielobjekt: {f['target_object']})")
        parts.append(f"\n  - Evidence: {evidence_str(f.get('evidence'))}")
        parts.append(f"\n  - Maßnahme: {f.get('remediation', '')}")
        if f.get("verantwortlich"):
            parts.append(f"\n  - Verantwortlich: {f['verantwortlich']}")
        if f.get("umzusetzen_bis"):
            parts.append(f"\n  - Frist: {f['umzusetzen_bis']}")
        return " ".join(parts)

    out = ["# Fix-Plan\n"]
    for title, items in [
        ("Sofort (Basis-Defizite / kritische OWASP-Findings)", sofort),
        ("Kurzfristig (Standard-Defizite / mittlere Severity)", kurzfristig),
        ("Mittelfristig (geringe Severity, Prozess-/Doku-Lücken)", mittelfristig),
    ]:
        out.append(f"## {title}\n")
        if items:
            for f in sorted(items, key=lambda x: SEVERITY_ORDER.get(x.get("severity"), 5)):
                out.append(task_line(f))
        else:
            out.append("_Keine offenen Punkte in dieser Kategorie._")
        out.append("")
    return "\n".join(out)


SEVERITY_LABEL = {
    "critical": "Critical", "high": "High", "medium": "Medium",
    "low": "Low", "info": "Info",
}


def esc(text):
    return html.escape("" if text is None else str(text))


def rid(req_id):
    """Anforderungs-/Control-ID als Monospace-Chip (semantisch: das *ist* Code)."""
    return f'<code class="rid">{esc(req_id)}</code>'


def status_badge(status, standard):
    label_map = BSI_STATUS_LABEL if standard == "bsi" else OWASP_STATUS_LABEL
    s = status or "manual"
    return f'<span class="badge badge-status-{esc(s)}">{esc(label_map.get(s, s))}</span>'


def severity_badge(severity):
    s = severity or "info"
    return f'<span class="badge badge-sev-{esc(s)}">{esc(SEVERITY_LABEL.get(s, s))}</span>'


def evidence_html(ev_list):
    if not ev_list:
        return '<span class="muted">–</span>'
    parts = []
    for e in ev_list:
        src = esc(e.get("source", "?"))
        detail = esc(e.get("detail", ""))
        parts.append(f'<code class="src">{src}</code> {detail}'.rstrip())
    return "<br>".join(parts)


def table_wrap(headers, rows):
    """rows = Liste von Zellen-HTML-Listen (bereits fertiges, sicheres HTML)."""
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    return ('<div class="table-wrap"><table><thead><tr>' + thead
            + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")


def status_summary(items, order, standard):
    """Distribution meter + count chips for one standard (worst-first)."""
    counts = {}
    for it in items:
        k = it.get("status", "manual")
        counts[k] = counts.get(k, 0) + 1
    total = sum(counts.values()) or 1
    keys = sorted(counts, key=lambda k: order.get(k, 9))
    label_map = BSI_STATUS_LABEL if standard == "bsi" else OWASP_STATUS_LABEL
    segs, chips = [], []
    for k in keys:
        pct = counts[k] / total * 100
        lbl = label_map.get(k, k)
        segs.append(f'<span class="seg seg-status-{esc(k)}" style="width:{pct:.4g}%" '
                    f'title="{esc(lbl)}: {counts[k]}"></span>')
        chips.append(f'<span class="badge badge-status-{esc(k)}">{esc(lbl)}'
                     f'<b>{counts[k]}</b></span>')
    meter = f'<div class="meter" role="img" aria-label="Status-Verteilung">{"".join(segs)}</div>'
    return meter, '<div class="chips">' + "".join(chips) + "</div>"


def build_html(audit_dir):
    profile = load_json(audit_dir / "profile.json", {}) or {}
    methodik = load_json(audit_dir / "methodik.json", {}) or {}
    findings = load_findings(audit_dir)

    bsi = [f for f in findings if f.get("standard") == "bsi"]
    asvs = [f for f in findings if f.get("standard") == "asvs"]
    masvs = [f for f in findings if f.get("standard") == "masvs"]
    ssdf = [f for f in findings if f.get("standard") == "ssdf"]
    slsa = [f for f in findings if f.get("standard") == "slsa"]
    all_findings = bsi + asvs + masvs + ssdf + slsa
    present_standards = {f.get("standard") for f in all_findings}

    today = datetime.date.today().isoformat()
    target = profile.get("target", profile.get("repo_path", "n/a"))
    h = []

    # --- header ---
    h.append('<header class="doc-head">')
    h.append('<p class="eyebrow">Security-Compliance-Audit</p>')
    h.append("<h1>OWASP <span class=\"amp\">+</span> BSI IT-Grundschutz</h1>")
    h.append('<dl class="meta">')
    h.append(f'<div><dt>Datum</dt><dd>{esc(today)}</dd></div>')
    h.append(f'<div><dt>Geprüftes Ziel</dt><dd>{esc(target)}</dd></div>')
    h.append('<div><dt>Schutzbedarf</dt><dd>normal · Basis + Standard</dd></div>')
    h.append('</dl>')
    h.append('<p class="method">Vorgehen nach <strong>BSI-Standard 200-2</strong> '
             '(Strukturanalyse, Schutzbedarfsfeststellung, Modellierung, '
             'IT-Grundschutz-Check) sowie OWASP ASVS/MASVS, ergänzt um kuratierte Teilmengen '
             'von NIST SSDF und SLSA.</p>')
    h.append('</header>')

    # --- glossary ---
    h.append('<section class="sec"><h2 class="sec-title">Glossar <small>Abkürzungen und Begriffe</small></h2>')
    rows = [[f"<strong>{esc(term)}</strong>", esc(expl)] for term, expl in glossary_entries(present_standards)]
    h.append(table_wrap(["Begriff", "Bedeutung"], rows))
    h.append('</section>')

    # --- executive summary: stat cards ---
    h.append('<section class="sec"><h2 class="sec-title">Executive Summary</h2>')
    h.append('<div class="cards">')
    for items, order, name, std in [
        (bsi, BSI_STATUS_ORDER, "BSI IT-Grundschutz", "bsi"),
        (asvs, OWASP_STATUS_ORDER, "OWASP ASVS", "asvs"),
        (masvs, OWASP_STATUS_ORDER, "OWASP MASVS", "masvs"),
        (ssdf, OWASP_STATUS_ORDER, "NIST SSDF", "ssdf"),
        (slsa, OWASP_STATUS_ORDER, "SLSA", "slsa"),
    ]:
        if not items:
            continue
        meter, chips = status_summary(items, order, std)
        h.append('<article class="card">')
        h.append(f'<header class="card-head"><h3>{esc(name)}</h3>'
                 f'<span class="card-total">{len(items)}<small>Kontrollen</small></span></header>')
        h.append(meter)
        h.append(chips)
        h.append('</article>')
    h.append('</div>')

    critical = [f for f in all_findings
                if f.get("severity") in ("critical", "high")
                and f.get("status") in ("nein", "fail", "teilweise", "partial")]
    critical.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity"), 9))
    if critical:
        h.append('<div class="callout callout-alert">')
        h.append('<h3>Kritischste offene Findings</h3><ul class="finding-list">')
        for f in critical[:5]:
            h.append(f'<li>{severity_badge(f.get("severity"))} {rid(f.get("id"))} '
                     f'<span class="finding-title">{esc(f.get("title", ""))}</span></li>')
        h.append('</ul></div>')
    h.append('</section>')

    # --- Vorgehen (approach) ---
    h.append('<section class="sec"><h2 class="sec-title">Vorgehen (Methodik)</h2>')
    h.append('<p>Der BSI-Anteil folgt dem operativen Vorgehensmodell aus '
             '<strong>BSI-Standard 200-2</strong>: Strukturanalyse (Zielobjekte erfassen) → '
             'Schutzbedarfsfeststellung (V/I/V je Zielobjekt) → Modellierung '
             '(Zielobjekt↔Baustein) → IT-Grundschutz-Check (Soll-Ist-Vergleich je Anforderung, '
             'Status ja/teilweise/nein/entbehrlich). Der OWASP-Anteil (ASVS/MASVS) sowie die '
             'kuratierten SSDF-/SLSA-Prüfpunkte folgen dem Standard-Vokabular pass/fail/partial/n_a.</p>')
    h.append('</section>')

    # --- Strukturanalyse (structure analysis) ---
    h.append('<section class="sec"><h2 class="sec-title">Strukturanalyse — Zielobjekte</h2>')
    strukturanalyse = methodik.get("strukturanalyse", [])
    if strukturanalyse:
        rows = [[rid(z.get("id", "")), esc(z.get("titel", "")), esc(z.get("typ", "")),
                 esc(z.get("sprache_framework", ""))] for z in strukturanalyse]
        h.append(table_wrap(["ID", "Titel", "Typ", "Sprache/Framework"], rows))
    else:
        h.append('<p class="empty">Keine Strukturanalyse-Daten vorhanden '
                 '(methodik.json fehlt oder leer).</p>')
    h.append('</section>')

    # --- Schutzbedarfsfeststellung (protection-need assessment) ---
    h.append('<section class="sec"><h2 class="sec-title">Schutzbedarfsfeststellung</h2>')
    schutzbedarf = methodik.get("schutzbedarf", [])
    if schutzbedarf:
        rows = [[rid(s.get("zielobjekt_id", "")), esc(s.get("vertraulichkeit", "")),
                 esc(s.get("integritaet", "")), esc(s.get("verfuegbarkeit", "")),
                 esc(s.get("einschaetzung", "")), esc(s.get("begruendung", ""))]
                for s in schutzbedarf]
        h.append(table_wrap(["Zielobjekt", "Vertraulichkeit", "Integrität", "Verfügbarkeit",
                             "Einschätzung", "Begründung"], rows))
    else:
        h.append('<p class="empty">Keine Schutzbedarfsfeststellung vorhanden.</p>')
    h.append('</section>')

    # --- Modellierung (modeling) ---
    h.append('<section class="sec"><h2 class="sec-title">Modellierung</h2>')
    modellierung = methodik.get("modellierung", [])
    if modellierung:
        rows = [[rid(m.get("zielobjekt_id", "")),
                 ", ".join(esc(b) for b in m.get("bausteine", [])),
                 esc(m.get("begruendung", ""))] for m in modellierung]
        h.append(table_wrap(["Zielobjekt", "Zugeordnete Bausteine/Standards", "Begründung"], rows))
    else:
        h.append('<p class="empty">Keine Modellierung vorhanden.</p>')
    h.append('</section>')

    # --- applied Bausteine & standards / scope-and-exclusions ---
    catalog_meta = load_catalog_summaries()
    scope = compute_scope(bsi, asvs, masvs, ssdf, slsa, catalog_meta)

    h.append('<section class="sec"><h2 class="sec-title">Angewendete Bausteine &amp; Standards</h2>')
    h.append('<p>Kurzbeschreibung dessen, was mit den tatsächlich geprüften Bausteinen/Kapiteln '
             'inhaltlich abgedeckt wird — als Einordnungshilfe, bevor die Detail-Tabellen folgen.</p>')
    if scope["applied_bsi"]:
        h.append('<h3 class="group-title">BSI IT-Grundschutz</h3>')
        rows = [[rid(c), esc(t), esc(d)] for c, t, d in scope["applied_bsi"]]
        h.append(table_wrap(["Baustein", "Titel", "Was geprüft wird"], rows))
    if scope["applied_asvs"]:
        h.append('<h3 class="group-title">OWASP ASVS</h3>')
        rows = [[rid(c), esc(t)] for c, t in scope["applied_asvs"]]
        h.append(table_wrap(["Kapitel", "Titel"], rows))
    if scope["applied_masvs"]:
        h.append('<h3 class="group-title">OWASP MASVS</h3>')
        rows = [[rid(c), esc(t)] for c, t in scope["applied_masvs"]]
        h.append(table_wrap(["Gruppe", "Titel"], rows))
    if scope["applied_ssdf"]:
        h.append('<h3 class="group-title">NIST SSDF (kuratierte Teilmenge)</h3>')
        rows = [[rid(c), esc(t)] for c, t in scope["applied_ssdf"]]
        h.append(table_wrap(["Praktikengruppe", "Titel"], rows))
    if scope["applied_slsa"]:
        h.append('<h3 class="group-title">SLSA (kuratierte Teilmenge, Build-Track)</h3>')
        rows = [[rid(c), esc(t)] for c, t in scope["applied_slsa"]]
        h.append(table_wrap(["Gruppe", "Titel"], rows))
    h.append('</section>')

    h.append('<section class="sec"><h2 class="sec-title">Abgrenzung '
             '<small>was explizit nicht betrachtet wurde</small></h2>')
    h.append('<p>Dieser Audit ist eine <strong>statische Code-/Konfigurationsprüfung</strong> '
             '(kein Penetrationstest, keine dynamische Testausführung, kein Live-Scan der '
             'laufenden Anwendung). Explizit außerhalb des Scopes:</p>')
    h.append('<ul class="notes">')
    h.append('<li><strong>Hosting-/Infrastruktur-Ebene</strong>: physische Sicherheit, '
             'Netzwerk-/Server-Betrieb außerhalb der Anwendungs-Konfiguration — siehe Abschnitt '
             '„Nicht in unserer Hand“.</li>')
    h.append('<li><strong>Risikoanalyse nach BSI-Standard 200-3</strong>: nicht durchgeführt '
             '(nur bei Schutzbedarf über normal relevant, siehe „Risikoanalyse-Vermerk“).</li>')
    h.append('<li><strong>Anforderungen bei erhöhtem Schutzbedarf</strong> (BSI „Hoch“) sowie '
             '<strong>ASVS L3</strong>: nicht Teil dieses Katalogs (Schutzbedarf normal = Basis + '
             'Standard bzw. L1+L2).</li>')
    if scope["not_covered_bsi"]:
        liste = ", ".join(f"{esc(c)} ({esc(t)})" for c, t in scope["not_covered_bsi"])
        h.append(f'<li><strong>BSI-Bausteine im Katalog, aber in diesem Lauf nicht geprüft</strong>: {liste}.</li>')
    elif catalog_meta["bsi"]:
        h.append('<li><strong>BSI-Bausteine im Katalog</strong>: alle katalogisierten Bausteine '
                 'wurden in diesem Lauf geprüft.</li>')
    if scope["not_covered_asvs"]:
        liste = ", ".join(f"{esc(c)} ({esc(t)})" for c, t in scope["not_covered_asvs"])
        h.append(f'<li><strong>ASVS-Kapitel im Katalog, aber in diesem Lauf nicht geprüft</strong>: {liste}.</li>')
    elif catalog_meta["asvs"]:
        h.append('<li><strong>ASVS-Kapitel im Katalog</strong>: alle katalogisierten Kapitel '
                 'wurden in diesem Lauf geprüft.</li>')
    if not scope["masvs_applied_at_all"]:
        h.append('<li><strong>OWASP MASVS</strong>: nicht angewendet — keine Flutter/React-Native-'
                 'Zielobjekte in der Strukturanalyse identifiziert.</li>')
    h.append('<li><strong>NIST SSDF</strong>: nur eine kuratierte Teilmenge von 5 der 65 offiziellen '
             'Praktiken wird geprüft — der Rest ist bereits über BSI CON.8/CON.10 abgedeckt, gehört '
             'zum separaten <code>full-quality-scan</code>-Skill, oder ist eine '
             'Organisationsprozess-Anforderung ohne Passung für Einzelentwickler.</li>')
    if not scope["slsa_applied_at_all"]:
        h.append('<li><strong>SLSA</strong>: nicht angewendet — keine Findings vorhanden.</li>')
    else:
        h.append('<li><strong>SLSA</strong>: nur der Build-Track (kuratiert auf 2 solo-dev-taugliche '
                 'Prüfpunkte) wird geprüft; der Source-Track ist ausgeklammert (Level 4 verlangt '
                 'Zwei-Personen-Review).</li>')
    h.append('</ul></section>')

    # --- Grundschutz-Check (BSI) ---
    h.append('<section class="sec"><h2 class="sec-title">Grundschutz-Check '
             '<small>BSI, Soll-Ist-Vergleich</small></h2>')
    if bsi:
        by_baustein = {}
        for f in bsi:
            by_baustein.setdefault(bsi_baustein_of(f.get("id", "")), []).append(f)
        for baustein_id in sorted(by_baustein):
            h.append(f'<div class="group"><h3 class="group-title">{esc(baustein_id)}</h3>')
            items_by_level = by_baustein[baustein_id]
            for level in ("Basis", "Standard"):
                level_items = sorted(
                    (f for f in items_by_level if f.get("level") == level),
                    key=lambda f: natural_key(f.get("id", "")))
                if not level_items:
                    continue
                h.append(f'<div class="subgroup"><h4 class="subgroup-title">'
                         f'<span class="lvl">{esc(level)}</span> Anforderungen</h4>')
                rows = [[rid(f.get("id")), esc(f.get("title", "")),
                         status_badge(f.get("status"), "bsi"),
                         esc(f.get("begruendung", "")) or '<span class="muted">–</span>',
                         evidence_html(f.get("evidence")), esc(f.get("remediation", ""))]
                        for f in level_items]
                h.append(table_wrap(["Anforderung", "Titel", "Status", "Begründung",
                                     "Evidence", "Remediation"], rows))
                h.append('</div>')
            h.append('</div>')
    else:
        h.append('<p class="empty">Keine BSI-Findings vorhanden '
                 '(kein zutreffender Baustein oder Audit noch nicht gelaufen).</p>')
    h.append('</section>')

    # --- ASVS ---
    h.append('<section class="sec"><h2 class="sec-title">OWASP ASVS</h2>')
    if asvs:
        by_chapter = {}
        for f in asvs:
            by_chapter.setdefault(asvs_chapter_of(f.get("id", "")), []).append(f)
        for chapter in sorted(by_chapter):
            h.append(f'<div class="group"><h3 class="group-title">{esc(chapter)}</h3>')
            chapter_items = by_chapter[chapter]
            levels_present = sorted({f.get("level", "") for f in chapter_items},
                                    key=lambda l: ASVS_LEVEL_ORDER.get(l, 9))
            for level in levels_present:
                level_items = sorted(
                    (f for f in chapter_items if f.get("level") == level),
                    key=lambda f: natural_key(f.get("id", "")))
                h.append(f'<div class="subgroup"><h4 class="subgroup-title">'
                         f'<span class="lvl">{esc(level)}</span></h4>')
                rows = [[rid(f.get("id")), esc(f.get("title", "")),
                         status_badge(f.get("status"), "asvs"),
                         severity_badge(f.get("severity")),
                         evidence_html(f.get("evidence")), esc(f.get("remediation", ""))]
                        for f in level_items]
                h.append(table_wrap(["Control", "Titel", "Status", "Severity",
                                     "Evidence", "Remediation"], rows))
                h.append('</div>')
            h.append('</div>')
    else:
        h.append('<p class="empty">Keine ASVS-Findings vorhanden.</p>')
    h.append('</section>')

    # --- MASVS ---
    if masvs:
        h.append('<section class="sec"><h2 class="sec-title">OWASP MASVS</h2>')
        by_group = {}
        for f in masvs:
            by_group.setdefault(masvs_group_of(f.get("id", "")), []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            h.append(f'<div class="group"><h3 class="group-title">{esc(group)}</h3>')
            rows = [[rid(f.get("id")), esc(f.get("title", "")),
                     status_badge(f.get("status"), "masvs"),
                     severity_badge(f.get("severity")),
                     evidence_html(f.get("evidence")), esc(f.get("remediation", ""))]
                    for f in items]
            h.append(table_wrap(["Control", "Titel", "Status", "Severity",
                                 "Evidence", "Remediation"], rows))
            h.append('</div>')
        h.append('</section>')

    # --- SSDF ---
    if ssdf:
        h.append('<section class="sec"><h2 class="sec-title">NIST SSDF <small>kuratierte Teilmenge</small></h2>')
        by_group = {}
        for f in ssdf:
            by_group.setdefault(ssdf_group_of(f.get("id", "")), []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            h.append(f'<div class="group"><h3 class="group-title">{esc(group)}</h3>')
            rows = [[rid(f.get("id")), esc(f.get("title", "")),
                     status_badge(f.get("status"), "ssdf"),
                     severity_badge(f.get("severity")),
                     evidence_html(f.get("evidence")), esc(f.get("remediation", ""))]
                    for f in items]
            h.append(table_wrap(["Practice", "Titel", "Status", "Severity",
                                 "Evidence", "Remediation"], rows))
            h.append('</div>')
        h.append('</section>')

    # --- SLSA ---
    if slsa:
        h.append('<section class="sec"><h2 class="sec-title">SLSA <small>kuratierte Teilmenge, Build-Track</small></h2>')
        by_group = {}
        for f in slsa:
            by_group.setdefault(slsa_group_of(f.get("id", "")), []).append(f)
        for group in sorted(by_group):
            items = sorted(by_group[group], key=lambda f: natural_key(f.get("id", "")))
            h.append(f'<div class="group"><h3 class="group-title">{esc(group)}</h3>')
            rows = [[rid(f.get("id")), esc(f.get("title", "")),
                     status_badge(f.get("status"), "slsa"),
                     severity_badge(f.get("severity")),
                     evidence_html(f.get("evidence")), esc(f.get("remediation", ""))]
                    for f in items]
            h.append(table_wrap(["Requirement", "Titel", "Status", "Severity",
                                 "Evidence", "Remediation"], rows))
            h.append('</div>')
        h.append('</section>')

    # --- manual / out of scope ---
    manual = [f for f in all_findings
              if f.get("status") == "manual" and not f.get("out_of_scope_reason")]
    hosting = [f for f in all_findings if f.get("out_of_scope_reason")]

    h.append('<section class="sec"><h2 class="sec-title">Manuelle Prüfung nötig</h2>')
    if manual:
        rows = [[rid(f.get("id")), esc(f.get("title", "")), esc(f.get("remediation", ""))]
                for f in manual]
        h.append(table_wrap(["ID", "Titel", "Was noch zu prüfen ist"], rows))
    else:
        h.append('<p class="empty">Keine offenen manuellen Prüfpunkte.</p>')
    h.append('</section>')

    h.append('<section class="sec"><h2 class="sec-title">Nicht in unserer Hand '
             '<small>Hosting/Infrastruktur</small></h2>')
    if hosting:
        rows = [[rid(f.get("id")), esc(f.get("title", "")), esc(f.get("out_of_scope_reason", ""))]
                for f in hosting]
        h.append(table_wrap(["ID", "Titel", "Grund"], rows))
    else:
        h.append('<p class="empty">Keine Anforderungen als reine Hosting-Ebene markiert.</p>')
    h.append('</section>')

    # --- Risikoanalyse-Vermerk (risk-analysis note) ---
    h.append('<section class="sec"><h2 class="sec-title">Risikoanalyse-Vermerk</h2>')
    if schutzbedarf:
        h.append('<ul class="notes">')
        for s in schutzbedarf:
            zid = esc(s.get("zielobjekt_id"))
            if s.get("einschaetzung", "normal") != "normal":
                h.append(f'<li><strong>{zid}</strong>: Schutzbedarf tendenziell über normal '
                         'eingeschätzt — ergänzende Risikoanalyse nach BSI-Standard 200-3 '
                         'empfohlen (außerhalb des Scopes dieses automatisierten Checks).</li>')
            else:
                h.append(f'<li><strong>{zid}</strong>: Risikoanalyse nicht erforderlich '
                         '(Schutzbedarf normal).</li>')
        h.append('</ul>')
    else:
        h.append('<p class="empty">Keine Schutzbedarfsfeststellung vorhanden — '
                 'kein Vermerk möglich.</p>')
    h.append('</section>')

    # --- open-findings overview ---
    open_findings = sorted((f for f in all_findings if is_open(f)),
                           key=lambda f: SEVERITY_ORDER.get(f.get("severity"), 9))
    h.append('<section class="sec"><h2 class="sec-title">Übersicht offener Punkte</h2>')
    if open_findings:
        h.append('<div class="hint-row">')
        h.append('<p class="hint">Die Buttons kopieren einen fertigen KI-Agenten-Prompt in die '
                 'Zwischenablage, der Fundort, Begründung und Maßnahme enthält — direkt einsetzbar, '
                 'um das Finding (oder alle auf einmal) von einem Coding-Agenten beheben zu lassen.</p>')
        h.append('<button class="copy-btn copy-all-btn" type="button">'
                 f'<span class="copy-label">Alle {len(open_findings)} Findings als ein Prompt kopieren</span></button>')
        h.append('</div>')
        rows = [[esc(f.get("standard", "").upper()), rid(f.get("id")), esc(f.get("title", "")),
                 status_badge(f.get("status"), f.get("standard", "")), severity_badge(f.get("severity")),
                 f'<button class="copy-btn" type="button" data-fid="{esc(f.get("id"))}">'
                 f'<span class="copy-label">Fix-Prompt kopieren</span></button>']
                for f in open_findings]
        h.append(table_wrap(["Standard", "ID", "Titel", "Status", "Severity", "Aktion"], rows))
        h.append(f'<script type="application/json" id="findings-data">{json.dumps(open_findings, ensure_ascii=False)}</script>')
        h.append(f'<script>{COPY_PROMPT_JS}</script>')
    else:
        h.append('<p class="empty">Keine offenen Punkte — alle geprüften Anforderungen sind erfüllt '
                 'oder begründet entbehrlich/nicht anwendbar.</p>')
    h.append('</section>')

    h.append('<section class="sec"><h2 class="sec-title">Abschluss</h2>')
    h.append('<p>Priorisierte Maßnahmen siehe <code>fix-plan.md</code>. Nach Umsetzung wird '
             'ein Re-Audit empfohlen, um den Soll-Ist-Vergleich erneut zu prüfen.</p>')
    h.append('</section>')

    return DOC_HEAD + "\n".join(h) + DOC_TAIL


COPY_PROMPT_JS = r"""
(function () {
  var dataEl = document.getElementById('findings-data');
  if (!dataEl) return;
  var findings = JSON.parse(dataEl.textContent);
  var byId = {};
  findings.forEach(function (f) { byId[f.id] = f; });

  var STATUS_LABEL = {
    ja: 'Ja', teilweise: 'Teilweise', nein: 'Nein', entbehrlich: 'Entbehrlich',
    pass: 'Pass', fail: 'Fail', partial: 'Partial', n_a: 'N/A', manual: 'Manuell zu prüfen'
  };

  function evidenceLines(ev) {
    if (!ev || !ev.length) return '- (keine Evidence hinterlegt)';
    return ev.map(function (e) {
      return '- ' + (e.source || '?') + ': ' + (e.detail || '');
    }).join('\n');
  }

  function findingBlock(f) {
    var standard = (f.standard || '').toUpperCase();
    var level = f.level ? ' (' + f.level + ')' : '';
    var status = STATUS_LABEL[f.status] || f.status;
    var lines = [];
    lines.push('Finding: ' + f.id + ' — ' + (f.title || ''));
    lines.push('Standard: ' + standard + level + '   Status: ' + status + '   Severity: ' + (f.severity || ''));
    if (f.target_object) lines.push('Zielobjekt: ' + f.target_object);
    if (f.begruendung) {
      lines.push('');
      lines.push('Warum das relevant ist:');
      lines.push(f.begruendung);
    }
    lines.push('');
    lines.push('Wo zu finden (Evidence):');
    lines.push(evidenceLines(f.evidence));
    lines.push('');
    lines.push('Was zu tun ist:');
    lines.push(f.remediation || '(keine Remediation hinterlegt — Finding und Kontext manuell einschätzen)');
    return lines.join('\n');
  }

  var CLOSING_INSTRUCTIONS = 'Bitte: (1) den betroffenen Code an den genannten Stellen öffnen und den ' +
    'beschriebenen Ist-Zustand verifizieren, (2) die Maßnahme wie oben beschrieben umsetzen, ' +
    '(3) sicherstellen, dass bestehende Funktionalität/Tests dabei nicht brechen, ' +
    '(4) kurz zusammenfassen, was geändert wurde.';

  function buildPrompt(f) {
    return 'Behebe den folgenden Security-Compliance-Finding in diesem Repository.\n\n' +
      findingBlock(f) + '\n\n' + CLOSING_INSTRUCTIONS;
  }

  function buildAllPrompt() {
    var intro = 'Behebe die folgenden ' + findings.length + ' Security-Compliance-Findings in ' +
      'diesem Repository, eines nach dem anderen. Bearbeite sie in der angegebenen Reihenfolge ' +
      '(kritischste zuerst) und committe idealerweise pro Finding separat.';
    var blocks = findings.map(function (f, i) {
      return '--- Finding ' + (i + 1) + '/' + findings.length + ' ---\n' + findingBlock(f);
    });
    return intro + '\n\n' + blocks.join('\n\n') + '\n\n' + CLOSING_INSTRUCTIONS;
  }

  function flashLabel(btn, text, temporaryLabel) {
    var label = btn.querySelector('.copy-label');
    var original = label ? label.textContent : null;
    var reset = function () {
      if (label) label.textContent = original;
      btn.classList.remove('copied');
    };
    if (label) label.textContent = temporaryLabel;
    return reset;
  }

  document.addEventListener('click', function (ev) {
    var allBtn = ev.target.closest('.copy-all-btn');
    var singleBtn = !allBtn && ev.target.closest('.copy-btn');
    var btn = allBtn || singleBtn;
    if (!btn) return;
    var text = allBtn ? buildAllPrompt() : buildPrompt(byId[btn.getAttribute('data-fid')]);
    if (!text) return;
    navigator.clipboard.writeText(text).then(function () {
      var reset = flashLabel(btn, text, 'Kopiert ✓');
      btn.classList.add('copied');
      setTimeout(reset, 1600);
    }, function () {
      var reset = flashLabel(btn, text, 'Kopieren fehlgeschlagen');
      setTimeout(reset, 1600);
    });
  });
})();
"""


DOC_HEAD = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Security-Compliance-Audit-Report</title>
<style>
:root{
  color-scheme: light dark;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
  --bg:#f5f6f8; --surface:#ffffff; --surface-2:#f0f2f5; --surface-3:#e9edf2;
  --ink:#1a1f29; --ink-2:#5b6472; --line:#e2e6ea; --accent:#4f46e5;
  --shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0d1117; --surface:#161b22; --surface-2:#1c232d; --surface-3:#232c38;
    --ink:#e6edf3; --ink-2:#9aa5b1; --line:#2a323d; --accent:#818cf8;
    --shadow: 0 1px 2px rgba(0,0,0,.3);
  }
}
:root[data-theme="dark"]{
  --bg:#0d1117; --surface:#161b22; --surface-2:#1c232d; --surface-3:#232c38;
  --ink:#e6edf3; --ink-2:#9aa5b1; --line:#2a323d; --accent:#818cf8;
  --shadow: 0 1px 2px rgba(0,0,0,.3);
}
:root[data-theme="light"]{
  --bg:#f5f6f8; --surface:#ffffff; --surface-2:#f0f2f5; --surface-3:#e9edf2;
  --ink:#1a1f29; --ink-2:#5b6472; --line:#e2e6ea; --accent:#4f46e5;
  --shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
}

*{box-sizing:border-box;}
html{-webkit-text-size-adjust:100%;}
body{
  font-family:var(--sans); background:var(--bg); color:var(--ink);
  line-height:1.55; margin:0; padding:2.5rem 1.25rem 5rem;
  overflow-x:hidden; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px; margin:0 auto;}
p{margin:.6rem 0;}
strong{font-weight:650;}
a{color:var(--accent);}
small{font-weight:500; color:var(--ink-2);}

/* Monospace IDs / Pfade — die IDs *sind* Code (Console-Charakter) */
code{
  font-family:var(--mono); font-size:.86em;
  background:var(--surface-2); color:var(--ink);
  padding:.08em .38em; border-radius:5px; border:1px solid var(--line);
}
code.rid{font-weight:600; color:var(--accent); white-space:nowrap;
  background:color-mix(in srgb, var(--accent) 10%, var(--surface));
  border-color:color-mix(in srgb, var(--accent) 24%, transparent);}
code.src{font-size:.82em; color:var(--ink-2);}
.muted{color:var(--ink-2);}

/* --- Kopf --- */
.doc-head{
  position:relative; background:var(--surface); border:1px solid var(--line);
  border-radius:16px; padding:1.9rem 1.9rem 1.6rem; margin-bottom:2.2rem;
  box-shadow:var(--shadow); overflow:hidden;
}
.doc-head::before{
  content:""; position:absolute; inset:0 auto 0 0; width:5px;
  background:linear-gradient(180deg, var(--accent), color-mix(in srgb, var(--accent) 40%, transparent));
}
.eyebrow{
  margin:0 0 .35rem; font-size:.74rem; font-weight:700; letter-spacing:.14em;
  text-transform:uppercase; color:var(--accent);
}
h1{
  margin:0 0 1.1rem; font-size:clamp(1.7rem, 4vw, 2.4rem); line-height:1.1;
  font-weight:800; letter-spacing:-.02em;
}
h1 .amp{color:var(--ink-2); font-weight:400;}
.meta{display:flex; flex-wrap:wrap; gap:.4rem 2.4rem; margin:0 0 1.1rem;}
.meta div{margin:0;}
.meta dt{font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-2);}
.meta dd{margin:.1rem 0 0; font-size:1rem; font-weight:600; font-family:var(--mono);}
.method{margin:0; padding-top:1rem; border-top:1px solid var(--line);
  font-size:.92rem; color:var(--ink-2); max-width:70ch;}

/* --- Sektionen --- */
.sec{margin:2.6rem 0;}
.sec-title{
  margin:0 0 1.1rem; font-size:1.35rem; font-weight:750; letter-spacing:-.01em;
  padding-bottom:.5rem; border-bottom:2px solid var(--line);
  display:flex; align-items:baseline; gap:.6rem;
}
.sec-title::before{
  content:""; width:.55rem; height:.55rem; border-radius:2px;
  background:var(--accent); flex:0 0 auto; transform:translateY(-.06em);
}
.sec-title small{font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; font-weight:600;}

/* --- Executive Summary Cards --- */
.cards{display:grid; grid-template-columns:repeat(auto-fit, minmax(260px,1fr)); gap:1rem;}
.card{
  background:var(--surface); border:1px solid var(--line); border-radius:14px;
  padding:1.25rem 1.3rem; box-shadow:var(--shadow);
}
.card-head{display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; margin-bottom:1rem;}
.card-head h3{margin:0; font-size:1.02rem; font-weight:700;}
.card-total{display:flex; flex-direction:column; align-items:flex-end; line-height:1;
  font-size:2rem; font-weight:800; letter-spacing:-.03em;}
.card-total small{font-size:.62rem; font-weight:600; letter-spacing:.06em;
  text-transform:uppercase; margin-top:.2rem;}
.meter{display:flex; height:9px; border-radius:999px; overflow:hidden;
  background:var(--surface-2); margin-bottom:.9rem; box-shadow:inset 0 0 0 1px var(--line);}
.seg{min-width:4px; display:block;}
.chips{display:flex; flex-wrap:wrap; gap:.4rem;}

/* --- Callout kritische Findings --- */
.callout{margin-top:1.4rem; border-radius:14px; padding:1.1rem 1.3rem; border:1px solid;}
.callout-alert{
  background:color-mix(in srgb, #ef4444 8%, var(--surface));
  border-color:color-mix(in srgb, #ef4444 30%, transparent);
}
.callout h3{margin:0 0 .7rem; font-size:.95rem; font-weight:750;
  display:flex; align-items:center; gap:.5rem;}
.callout h3::before{content:"!"; display:inline-flex; align-items:center; justify-content:center;
  width:1.25rem; height:1.25rem; border-radius:50%; font-size:.8rem; font-weight:800;
  color:#fff; background:#ef4444;}
.finding-list{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:.55rem;}
.finding-list li{display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; font-size:.92rem;}
.finding-title{color:var(--ink);}

/* --- Gruppen (H3) / Untergruppen (H4) --- */
.group{
  margin:1.5rem 0; padding:.2rem 0 .2rem 1.1rem;
  border-left:3px solid color-mix(in srgb, var(--accent) 55%, transparent);
}
.group-title{margin:.2rem 0 .8rem; font-size:1.1rem; font-weight:750;
  font-family:var(--mono); letter-spacing:-.01em; color:var(--ink);}
.subgroup{margin:1rem 0 1.2rem;}
.subgroup-title{margin:0 0 .5rem; font-size:.82rem; font-weight:600; color:var(--ink-2);
  display:flex; align-items:center; gap:.5rem;}
.lvl{display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.03em;
  padding:.18em .6em; border-radius:6px; color:var(--ink);
  background:var(--surface-3); border:1px solid var(--line);}

/* --- Tabellen --- */
.table-wrap{overflow-x:auto; border:1px solid var(--line); border-radius:12px;
  background:var(--surface); box-shadow:var(--shadow); -webkit-overflow-scrolling:touch;}
table{border-collapse:collapse; width:100%; font-size:.875rem; min-width:640px;}
thead th{
  position:sticky; top:0; text-align:left; font-weight:650; font-size:.72rem;
  letter-spacing:.05em; text-transform:uppercase; color:var(--ink-2);
  background:var(--surface-2); padding:.6rem .85rem;
  border-bottom:1px solid var(--line); white-space:nowrap;
}
tbody td{padding:.6rem .85rem; vertical-align:top; border-bottom:1px solid var(--line);}
tbody tr:last-child td{border-bottom:none;}
tbody tr:nth-child(even){background:color-mix(in srgb, var(--surface-2) 45%, var(--surface));}
tbody td:nth-child(2){min-width:14ch;}

.empty{color:var(--ink-2); font-style:italic;
  background:var(--surface); border:1px dashed var(--line); border-radius:10px;
  padding:.9rem 1.1rem; margin:0;}
.notes{margin:0; padding-left:1.2rem;}
.notes li{margin:.4rem 0;}
.hint{color:var(--ink-2); font-size:.85rem; margin:0;}
.hint-row{display:flex; align-items:center; justify-content:space-between; gap:1rem;
  flex-wrap:wrap; margin:0 0 .9rem;}
.copy-all-btn{border-color:color-mix(in srgb, var(--accent) 40%, var(--line));
  background:color-mix(in srgb, var(--accent) 10%, var(--surface)); color:var(--accent); flex:0 0 auto;}

/* --- Copy-Fix-Prompt-Button --- */
.copy-btn{
  font-family:var(--sans); font-size:.78rem; font-weight:650; white-space:nowrap;
  padding:.35em .75em; border-radius:8px; border:1px solid var(--line);
  background:var(--surface-2); color:var(--ink); cursor:pointer;
  transition:background-color .15s, border-color .15s;
}
.copy-btn:hover{background:var(--surface-3);}
.copy-btn.copied{border-color:color-mix(in srgb, #15803d 45%, transparent);
  background:color-mix(in srgb, #15803d 14%, var(--surface)); color:#15803d;}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]) .copy-btn.copied{color:#4ade80;}
}
:root[data-theme="dark"] .copy-btn.copied{color:#4ade80;}

/* --- Badges (Status + Severity) --- */
.badge{
  display:inline-flex; align-items:center; gap:.4em; white-space:nowrap;
  font-size:.74rem; font-weight:650; line-height:1.4; letter-spacing:.01em;
  padding:.2em .6em; border-radius:999px; border:1px solid;
  color:var(--c);
  background:color-mix(in srgb, var(--c) 14%, var(--surface));
  border-color:color-mix(in srgb, var(--c) 32%, transparent);
}
.badge b{font-weight:800; font-variant-numeric:tabular-nums;
  padding-left:.15em; color:var(--c);}
.seg{background:var(--c);}

/* Farb-Tokens: Status (BSI + OWASP) */
.badge-status-ja,.seg-status-ja,.badge-status-pass,.seg-status-pass{--c:#15803d;}
.badge-status-teilweise,.seg-status-teilweise,.badge-status-partial,.seg-status-partial{--c:#b45309;}
.badge-status-nein,.seg-status-nein,.badge-status-fail,.seg-status-fail{--c:#c31d1d;}
.badge-status-entbehrlich,.seg-status-entbehrlich,.badge-status-n_a,.seg-status-n_a{--c:#516172;}
.badge-status-manual,.seg-status-manual{--c:#7c3aed;}
/* Severity */
.badge-sev-critical{--c:#a3123f;}
.badge-sev-high{--c:#dc2626;}
.badge-sev-medium{--c:#c2410c;}
.badge-sev-low{--c:#a16207;}
.badge-sev-info{--c:#2563eb;}

@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]) .badge-status-ja,:root:not([data-theme="light"]) .seg-status-ja,
  :root:not([data-theme="light"]) .badge-status-pass,:root:not([data-theme="light"]) .seg-status-pass{--c:#4ade80;}
  :root:not([data-theme="light"]) .badge-status-teilweise,:root:not([data-theme="light"]) .seg-status-teilweise,
  :root:not([data-theme="light"]) .badge-status-partial,:root:not([data-theme="light"]) .seg-status-partial{--c:#fbbf24;}
  :root:not([data-theme="light"]) .badge-status-nein,:root:not([data-theme="light"]) .seg-status-nein,
  :root:not([data-theme="light"]) .badge-status-fail,:root:not([data-theme="light"]) .seg-status-fail{--c:#f87171;}
  :root:not([data-theme="light"]) .badge-status-entbehrlich,:root:not([data-theme="light"]) .seg-status-entbehrlich,
  :root:not([data-theme="light"]) .badge-status-n_a,:root:not([data-theme="light"]) .seg-status-n_a{--c:#94a3b8;}
  :root:not([data-theme="light"]) .badge-status-manual,:root:not([data-theme="light"]) .seg-status-manual{--c:#c4b5fd;}
  :root:not([data-theme="light"]) .badge-sev-critical{--c:#fb7185;}
  :root:not([data-theme="light"]) .badge-sev-high{--c:#f87171;}
  :root:not([data-theme="light"]) .badge-sev-medium{--c:#fb923c;}
  :root:not([data-theme="light"]) .badge-sev-low{--c:#fcd34d;}
  :root:not([data-theme="light"]) .badge-sev-info{--c:#60a5fa;}
}
:root[data-theme="dark"] .badge-status-ja,:root[data-theme="dark"] .seg-status-ja,
:root[data-theme="dark"] .badge-status-pass,:root[data-theme="dark"] .seg-status-pass{--c:#4ade80;}
:root[data-theme="dark"] .badge-status-teilweise,:root[data-theme="dark"] .seg-status-teilweise,
:root[data-theme="dark"] .badge-status-partial,:root[data-theme="dark"] .seg-status-partial{--c:#fbbf24;}
:root[data-theme="dark"] .badge-status-nein,:root[data-theme="dark"] .seg-status-nein,
:root[data-theme="dark"] .badge-status-fail,:root[data-theme="dark"] .seg-status-fail{--c:#f87171;}
:root[data-theme="dark"] .badge-status-entbehrlich,:root[data-theme="dark"] .seg-status-entbehrlich,
:root[data-theme="dark"] .badge-status-n_a,:root[data-theme="dark"] .seg-status-n_a{--c:#94a3b8;}
:root[data-theme="dark"] .badge-status-manual,:root[data-theme="dark"] .seg-status-manual{--c:#c4b5fd;}
:root[data-theme="dark"] .badge-sev-critical{--c:#fb7185;}
:root[data-theme="dark"] .badge-sev-high{--c:#f87171;}
:root[data-theme="dark"] .badge-sev-medium{--c:#fb923c;}
:root[data-theme="dark"] .badge-sev-low{--c:#fcd34d;}
:root[data-theme="dark"] .badge-sev-info{--c:#60a5fa;}

@media (max-width:640px){
  body{padding:1.5rem .85rem 4rem;}
  .doc-head{padding:1.4rem 1.3rem;}
  .meta{gap:.4rem 1.4rem;}
}
</style>
</head>
<body>
<div class="wrap">
"""

DOC_TAIL = """
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audit_dir", help="Pfad zum Audit-Arbeitsverzeichnis (z.B. .audit-tmp/)")
    ap.add_argument("--html", action="store_true", help="Zusätzlich report.html erzeugen")
    args = ap.parse_args()

    audit_dir = pathlib.Path(args.audit_dir)
    if not audit_dir.exists():
        print(f"Audit-Verzeichnis nicht gefunden: {audit_dir}", file=sys.stderr)
        sys.exit(1)

    report_md, findings_by_standard = build_markdown(audit_dir)
    (audit_dir / "report.md").write_text(report_md, encoding="utf-8")

    fix_plan_md = build_fix_plan(findings_by_standard)
    (audit_dir / "fix-plan.md").write_text(fix_plan_md, encoding="utf-8")

    print(f"report.md geschrieben: {audit_dir / 'report.md'}", file=sys.stderr)
    print(f"fix-plan.md geschrieben: {audit_dir / 'fix-plan.md'}", file=sys.stderr)

    if args.html:
        html_out = build_html(audit_dir)
        (audit_dir / "report.html").write_text(html_out, encoding="utf-8")
        print(f"report.html geschrieben: {audit_dir / 'report.html'}", file=sys.stderr)


if __name__ == "__main__":
    main()
