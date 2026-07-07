#!/usr/bin/env python3
"""
Builds the three audit catalogs (ASVS, MASVS, BSI IT-Grundschutz) from the
official, machine-readable upstream sources. Stdlib-only (json, re, urllib -
xml is deliberately NOT used for BSI, see the reasoning below).

Usage: python3 build_catalog.py [--out <catalog-dir>]

Resolves the latest known version dynamically instead of hardcoding it:
  - ASVS: GitHub Releases API, highest vX.Y.Z_release tag.
  - MASVS: master branch (the standard has no versioned releases in the
    same sense; the version number is read from GitHub releases too, see
    resolve_masvs_version).
  - BSI: probes XML_Kompendium_<year>.xml descending from the current year,
    takes the first edition that actually exists (currently 2023, since the
    classic Basis/Standard/Hoch model would only be superseded by a new
    edition; Grundschutz++ (2026, OSCAL) follows a different model that is
    not Basis/Standard-based and is deliberately NOT used here, because the
    user's requirement is explicitly "Schutzbedarf normal = Basis+Standard").
"""
import argparse
import datetime
import json
import re
import sys
import urllib.request
import urllib.error

UA = {"User-Agent": "owasp-bsi-audit-skill/1.0 (+catalog-build)"}


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url, timeout=30):
    return json.loads(fetch(url, timeout=timeout))


# --------------------------------------------------------------------------
# ASVS
# --------------------------------------------------------------------------

def pick_latest_semver_tag(releases, tag_re):
    """Pure: given a list of GitHub release dicts and a compiled regex with
    three numeric capture groups, return (version_tuple, tag_name) for the
    highest version, or None if nothing matches. Kept separate from the
    network fetch so the selection logic itself is unit-testable."""
    best = None
    for r in releases:
        tag = r.get("tag_name", "")
        m = tag_re.match(tag)
        if not m:
            continue
        version = tuple(int(x) for x in m.groups())
        if best is None or version > best[0]:
            best = (version, tag)
    return best


ASVS_RELEASE_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)_release$")


def resolve_asvs_release():
    releases = fetch_json("https://api.github.com/repos/OWASP/ASVS/releases")
    best = pick_latest_semver_tag(releases, ASVS_RELEASE_TAG_RE)
    if not best:
        raise RuntimeError("No ASVS release tag found matching the expected v*_release format")
    version, tag = best
    version_str = ".".join(str(x) for x in version)
    major_minor = f"{version[0]}.{version[1]}"
    return version_str, tag, major_minor


def parse_asvs_requirements(payload):
    """Pure: turn the raw ASVS flat.json payload into our grouped catalog
    shape, keeping only L1+L2 (Schutzbedarf normal)."""
    items = payload["requirements"] if isinstance(payload, dict) else payload

    groups = {}
    for item in items:
        level = f"L{item['L']}"
        if level not in ("L1", "L2"):
            continue  # Schutzbedarf normal -> only L1+L2
        chapter_id = item["chapter_id"]
        g = groups.setdefault(chapter_id, {
            "group_id": f"asvs-{chapter_id.lower()}",
            "chapter_id": chapter_id,
            "chapter_name": item["chapter_name"],
            "requirements": [],
        })
        g["requirements"].append({
            "req_id": item["req_id"],
            "section_id": item["section_id"],
            "section_name": item["section_name"],
            "level": level,
            "description": item["req_description"],
        })
    return sorted(groups.values(), key=lambda g: g["chapter_id"])


def build_asvs():
    version_str, tag, major_minor = resolve_asvs_release()
    url = (
        f"https://raw.githubusercontent.com/OWASP/ASVS/{tag}/{major_minor}/docs_en/"
        f"OWASP_Application_Security_Verification_Standard_{version_str}_en.flat.json"
    )
    payload = fetch_json(url)
    groups = parse_asvs_requirements(payload)

    catalog = {
        "standard": "asvs",
        "version": version_str,
        "source_url": url,
        "level_note": "Nur L1+L2 enthalten (Schutzbedarf normal). L3 (hoher Schutzbedarf) bewusst ausgelassen.",
        "groups": groups,
    }
    total = sum(len(g["requirements"]) for g in catalog["groups"])
    return catalog, version_str, url, total


# --------------------------------------------------------------------------
# MASVS
# --------------------------------------------------------------------------

MASVS_GROUP_TITLES_FALLBACK = {
    "MASVS-STORAGE": "Storage",
    "MASVS-CRYPTO": "Cryptography",
    "MASVS-AUTH": "Authentication and Authorization",
    "MASVS-NETWORK": "Network Communication",
    "MASVS-PLATFORM": "Platform Interaction",
    "MASVS-CODE": "Code Quality",
    "MASVS-RESILIENCE": "Resilience Against Reverse Engineering and Tampering",
    "MASVS-PRIVACY": "Privacy",
}


MASVS_RELEASE_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

MASVS_CONTROL_RE = re.compile(
    r"- id:\s*(MASVS-[A-Z]+-\d+)\s*\n"
    r"\s*statement:\s*(.+?)\s*\n"
    r"\s*description:",
    re.DOTALL,
)


def resolve_masvs_version():
    # OWASP_MASVS.yaml only carries the placeholder "vx.x.x" in its metadata
    # block - the authoritative version number therefore comes from GitHub
    # releases (same approach as ASVS), while control content still comes
    # from the maintained YAML on master.
    releases = fetch_json("https://api.github.com/repos/OWASP/masvs/releases")
    best = pick_latest_semver_tag(releases, MASVS_RELEASE_TAG_RE)
    if not best:
        return "unknown"
    return ".".join(str(x) for x in best[0])


def parse_masvs_yaml(raw):
    """Pure: extract MASVS controls from the upstream YAML without a full
    YAML parser (stdlib-only) - control IDs already encode their own group
    (MASVS-<GROUP>-<N>), so a targeted regex scan is enough; no need to
    reconstruct the YAML's group nesting."""
    groups = {}
    for m in MASVS_CONTROL_RE.finditer(raw):
        control_id, statement = m.group(1), m.group(2).strip()
        statement = re.sub(r"\s+", " ", statement)  # collapse YAML line-folding
        group_code = "-".join(control_id.split("-")[:2])  # e.g. MASVS-STORAGE
        g = groups.setdefault(group_code, {
            "group_id": f"masvs-{group_code.split('-')[1].lower()}",
            "masvs_group": group_code,
            "title": MASVS_GROUP_TITLES_FALLBACK.get(group_code, group_code),
            "controls": [],
        })
        g["controls"].append({"id": control_id, "statement": statement})
    return sorted(groups.values(), key=lambda g: g["masvs_group"])


def build_masvs():
    url = "https://raw.githubusercontent.com/OWASP/masvs/master/OWASP_MASVS.yaml"
    raw = fetch(url).decode("utf-8")
    version_str = resolve_masvs_version()
    groups = parse_masvs_yaml(raw)

    catalog = {
        "standard": "masvs",
        "version": version_str,
        "source_url": url,
        "level_note": "MASVS 2.x kennt keine L1/L2-Stufung mehr; alle Controls gelten als anwendbar, gefiltert nach erkannter Zielplattform (Flutter/React Native).",
        "groups": groups,
    }
    total = sum(len(g["controls"]) for g in catalog["groups"])
    return catalog, version_str, url, total


# --------------------------------------------------------------------------
# BSI IT-Grundschutz
# --------------------------------------------------------------------------

TARGET_BAUSTEINE = {
    "CON.8": ("Software-Entwicklung",
              "Prozess und Praktiken der Eigenentwicklung von Software: Vorgehensmodell, "
              "sichere Entwicklungsumgebung, Versionsverwaltung, Software-Tests, Umgang mit "
              "externen Komponenten/Bibliotheken."),
    "CON.10": ("Entwicklung von Webanwendungen",
               "Sicherheitsanforderungen an selbst entwickelte Webanwendungen: Authentisierung, "
               "Zugriffskontrolle, Session-Management, Eingabevalidierung, Schutz vor SQL-Injection "
               "und CSRF, sichere HTTP-Konfiguration."),
    "APP.3.1": ("Webanwendungen und Webservices",
                "Betrieb und Konfiguration von Webanwendungen/-services: Authentisierung, "
                "kontrolliertes Einbinden von Dateien/Inhalten, Absicherung von Schnittstellen."),
    "APP.3.2": ("Webserver",
                "Absicherung des Webservers selbst, soweit per Anwendungs-/Config-Ebene "
                "kontrollierbar: sichere Konfiguration, Schutz der Webserver-Dateien, "
                "Protokollierung, Datei-Uploads/-Downloads."),
    "APP.4.3": ("Relationale Datenbanksysteme",
                "Absicherung des Datenbankmanagementsystems (hier: MySQL/MariaDB): "
                "Sicherheitsrichtlinie, Basishärtung, kontrolliertes Anlegen neuer Datenbanken, "
                "Zugriffsrechte."),
    "APP.1.4": ("Mobile Anwendungen (Apps)",
                "Sicherheitsanforderungen an selbst entwickelte mobile Apps (Flutter/React Native): "
                "Minimierung und Kontrolle von App-Berechtigungen, sichere Speicherung lokaler "
                "App-Daten, Verhinderung von Datenabfluss, sichere Deinstallation."),
}

LEVEL_MAP = {"B": "Basis", "S": "Standard", "H": "Hoch"}

# Heuristic checkType classification (deterministic, keyword-based). Order =
# priority: manual/hosting first, then process, then config, everything else
# counts as code-checkable. Deliberately conservative (stdlib-only,
# traceable) - when in doubt the skill still surfaces the control in the
# audit run and the assessor subagent decides case by case.
MANUAL_KEYWORDS = [
    "serverraum", "rechenzentrum", "klimatisi", "stromversorgung",
    "verkabelung", "baulich", "zutritt", "brandschutz", "usv ",
]
PROCESS_KEYWORDS = [
    "richtlinie", "schulung", "sensibilisierung", "awareness", "konzept",
    "zuständig", "verantwortlich", "audits für", "regelmäßig überprüft",
    "dokumentation", "meldewege", "vorgehensmodell",
]
CONFIG_KEYWORDS = [
    "konfigur", "härtung", "deaktiviert werden", "protokollierung",
    "passwortrichtlinie", "firewall", "verschlüsselung der verbindung",
    "tls", "verzeichnisauflistung", "verzeichnislisting",
]


def classify_check_type(text):
    lower = text.lower()
    if any(k in lower for k in MANUAL_KEYWORDS):
        return "manual"
    if any(k in lower for k in PROCESS_KEYWORDS):
        return "process"
    if any(k in lower for k in CONFIG_KEYWORDS):
        return "config"
    return "code"


def resolve_bsi_edition():
    # The BSI blob server rejects HEAD requests with a 400 (application
    # firewall) - so probe with GET instead; a 404 comes back as a small
    # error page, not an unnecessarily expensive download of the full ~3MB file.
    this_year = datetime.date.today().year
    for year in range(this_year, 2022, -1):
        url = (
            "https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/"
            f"IT-GS-Kompendium/XML_Kompendium_{year}.xml?__blob=publicationFile"
        )
        try:
            content = fetch(url)
            return year, url, content
        except urllib.error.HTTPError:
            continue
    raise RuntimeError("No BSI Kompendium XML edition found for 2023..present")


BSI_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def bsi_title_pattern():
    baustein_pattern = "|".join(re.escape(b) for b in sorted(TARGET_BAUSTEINE, key=len, reverse=True))
    # Requirement title shape, e.g.: CON.8.A1 Definition ... (S) [Zentrale Verwaltung]
    return re.compile(
        rf"<title>((?:{baustein_pattern}))\.A(\d+)\s+(.*?)\s*\(([BSH])\)(?:\s*\[[^\]]*\])?</title>"
    )


def parse_bsi_xml(raw):
    """Pure: turn the raw DocBook XML text into our grouped Bausteine dict.
    Kept separate from the network fetch so parsing can be unit-tested
    against a small synthetic XML snippet instead of the full ~3MB document."""
    title_re = bsi_title_pattern()
    matches = list(title_re.finditer(raw))
    bausteine = {code: {"baustein_id": code, "title": title, "description": description, "requirements": []}
                 for code, (title, description) in TARGET_BAUSTEINE.items()}

    for idx, m in enumerate(matches):
        baustein_id, num, title, level_code = m.groups()
        if title.strip().upper() == "ENTFALLEN":
            continue  # requirement number withdrawn by the BSI
        level = LEVEL_MAP[level_code]
        if level == "Hoch":
            continue  # Schutzbedarf normal = only Basis+Standard

        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else min(start + 4000, len(raw))
        body_raw = raw[start:end]
        # Roughly bound the body to the same section closing tag
        body_raw = body_raw.split("</section>")[0]
        body_text = BSI_TAG_STRIP_RE.sub(" ", body_raw)
        body_text = re.sub(r"\s+", " ", body_text).strip()

        req_id = f"{baustein_id}.A{num}"
        bausteine[baustein_id]["requirements"].append({
            "req_id": req_id,
            "title": title.strip(),
            "level": level,
            "check_type": classify_check_type(title + " " + body_text),
            "description": body_text,
        })
    return bausteine


def build_bsi():
    edition, url, content = resolve_bsi_edition()
    raw = content.decode("utf-8", errors="replace")
    bausteine = parse_bsi_xml(raw)

    catalog = {
        "standard": "bsi",
        "edition": str(edition),
        "source_url": url,
        "schutzbedarf": "normal (Basis + Standard-Anforderungen); Anforderungen bei erhöhtem Schutzbedarf ausgeschlossen",
        "scope_note": (
            "Nur code-/config-technisch kontrollierbare Bausteine. Reine "
            "Hosting-/Infrastruktur-Anforderungen innerhalb dieser Bausteine "
            "sind über check_type=manual markiert, nicht entfernt."
        ),
        "bausteine": [b for b in bausteine.values() if b["requirements"]],
    }
    total = sum(len(b["requirements"]) for b in catalog["bausteine"])
    return catalog, str(edition), url, total


# --------------------------------------------------------------------------
# SSDF (NIST SP 800-218) - curated subset
# --------------------------------------------------------------------------

# We deliberately do not ingest all 65 SSDF practices. Most either duplicate
# BSI CON.8 (threat modeling PW.1.1, trusted components PW.4.x - see CON.8.A6/
# A20/A21), duplicate the separate full-quality-scan skill's job (static
# analysis PW.7.x, dependency-vulnerability monitoring RV.1.1), duplicate this
# skill's own fix-plan mechanism (risk/remediation planning RV.2.x, RV.3.x),
# or describe organization-level process (formal roles, independent reviewers)
# that does not fit a solo developer - see CLAUDE.md's ISMS/OPS exclusion
# reasoning. Only these five leaf practices survive: concrete, code-/config-
# checkable, and not covered anywhere else in this skill or its siblings.
SSDF_SELECTED_IDS = {
    "PW.6.1": "Compiler-/Build-Tool-Sicherheit",
    "PW.6.2": "Compiler-/Build-Tool-Sicherheit",
    "PW.9.1": "Sichere Standardkonfiguration",
    "PW.9.2": "Sichere Standardkonfiguration",
    "RV.1.3": "Schwachstellen-Offenlegung",
}


def parse_ssdf_payload(payload):
    """Pure: filter the full CycloneDX SSDF payload down to SSDF_SELECTED_IDS
    and group by parent practice, keeping the requirement text verbatim from
    the fetched document (only the *selection* of IDs is curated, not the text)."""
    standard = payload["definitions"]["standards"][0]
    groups = {}
    for req in standard.get("requirements", []):
        ident = req.get("identifier", "")
        if ident not in SSDF_SELECTED_IDS:
            continue
        group_id = ident.rsplit(".", 1)[0]  # e.g. "PW.6.1" -> "PW.6"
        g = groups.setdefault(group_id, {
            "group_id": f"ssdf-{group_id.lower()}",
            "practice_group": group_id,
            "title": SSDF_SELECTED_IDS[ident],
            "requirements": [],
        })
        g["requirements"].append({"req_id": ident, "description": req.get("text", "").strip()})
    return standard.get("version", "unknown"), sorted(groups.values(), key=lambda g: g["practice_group"])


def build_ssdf():
    url = ("https://raw.githubusercontent.com/CycloneDX/official-3rd-party-standards/main/"
           "standards/NIST/SSDF/nist_secure-software-development-framework_1.1.cdx.json")
    payload = fetch_json(url)
    version_str, groups = parse_ssdf_payload(payload)

    catalog = {
        "standard": "ssdf",
        "version": version_str,
        "source_url": url,
        "scope_note": (
            "Kuratierte Teilmenge von 65 SSDF-Praktiken (siehe SSDF_SELECTED_IDS in "
            "build_catalog.py): nur Praktiken, die (a) nicht bereits über BSI CON.8/CON.10 "
            "oder das full-quality-scan-Skill abgedeckt sind, (b) code-/config-technisch "
            "prüfbar sind und (c) auch für Einzelentwickler ohne formale Organisationsprozesse "
            "sinnvoll sind."
        ),
        "groups": groups,
    }
    total = sum(len(g["requirements"]) for g in catalog["groups"])
    return catalog, version_str, url, total


# --------------------------------------------------------------------------
# SLSA (Supply-chain Levels for Software Artifacts) - curated subset
# --------------------------------------------------------------------------

SLSA_RELEASE_BRANCH_RE = re.compile(r"^releases/v(\d+)\.(\d+)$")


def resolve_slsa_release():
    branches = fetch_json("https://api.github.com/repos/slsa-framework/slsa/branches?per_page=100")
    best = None
    for b in branches:
        m = SLSA_RELEASE_BRANCH_RE.match(b.get("name", ""))
        if not m:
            continue
        version = tuple(int(x) for x in m.groups())
        if best is None or version > best[0]:
            best = (version, b["name"])
    if not best:
        raise RuntimeError("No SLSA releases/vX.Y branch found")
    version, branch = best
    return ".".join(str(x) for x in version), branch


# Hand-distilled from the official Build track requirements (source_url
# below, read in full during catalog design): only the two Producer-facing,
# solo-dev-actionable checks survive - "does a hosted CI pipeline build/
# release the artifact" (Build L1 platform choice + L2 hosted) and "is build
# provenance generated and distributed" (L1 exists + L2 authentic). The
# remaining L3 isolation/hermeticity guarantees are properties of the CI
# *platform* itself (e.g. inherent to GitHub-hosted runners), not something a
# solo developer configures in their own repo, so they are not modeled as a
# separate finding here. The Source track (SLSA Level 4 requires two-party
# review) is out of scope entirely - not achievable for a solo developer.
SLSA_BUILD_REQUIREMENTS = [
    {
        "req_id": "SLSA-BUILD-1",
        "title": "Build auf gehosteter CI-Plattform statt manuell",
        "description": (
            "Build Level 1 verlangt die Wahl eines geeigneten Build-Prozesses; Build Level 2 "
            "verlangt zusätzlich, dass dieser auf einer gehosteten Plattform läuft (z.B. GitHub "
            "Actions), nicht auf einem einzelnen Arbeitsplatzrechner."
        ),
    },
    {
        "req_id": "SLSA-BUILD-2",
        "title": "Build-Provenienz wird erzeugt und verteilt",
        "description": (
            "Der Build-Prozess MUSS eine Provenienz erzeugen, die das Artefakt eindeutig via "
            "kryptographischem Hash identifiziert und beschreibt, wie es gebaut wurde (Build "
            "Level 1); ab Level 2 MUSS diese Provenienz durch die Build-Plattform signiert "
            "(authentisch) sein. Die Provenienz MUSS an Konsumierende verteilt werden."
        ),
    },
]


def build_slsa():
    version_str, branch = resolve_slsa_release()
    url = f"https://raw.githubusercontent.com/slsa-framework/slsa/{branch}/spec/build-requirements.md"
    fetch(url)  # confirms the branch/URL still resolves; recorded in SOURCES.md for provenance

    catalog = {
        "standard": "slsa",
        "version": version_str,
        "source_url": url,
        "scope_note": (
            "Kuratierte Teilmenge des SLSA-Build-Tracks: nur die zwei Producer-seitigen, "
            "solo-dev-tauglichen Prüfpunkte (gehostete CI statt manueller Build, "
            "Build-Provenienz). Source-Track (Level 4 verlangt Zwei-Personen-Review) und "
            "Build-L3-Isolationsgarantien der CI-Plattform selbst sind ausgeklammert."
        ),
        "groups": [{
            "group_id": "slsa-build",
            "practice_group": "BUILD",
            "title": "Build-Integrität",
            "requirements": SLSA_BUILD_REQUIREMENTS,
        }],
    }
    total = len(SLSA_BUILD_REQUIREMENTS)
    return catalog, version_str, url, total


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="Zielverzeichnis für catalog/*.json (default: ../catalog neben diesem Script)")
    args = ap.parse_args()

    import pathlib
    out_dir = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).resolve().parent.parent / "catalog"
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.date.today().isoformat()
    sources_lines = [
        "# Katalog-Quellen (Provenienz)\n",
        f"Zuletzt gebaut/abgerufen: **{today}**\n",
        "\n| Standard | Version/Edition | Quelle | Requirements |\n|---|---|---|---|\n",
    ]

    print("Baue ASVS-Katalog ...", file=sys.stderr)
    asvs_catalog, asvs_version, asvs_url, asvs_total = build_asvs()
    (out_dir / "asvs-5.0-web.json").write_text(json.dumps(asvs_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sources_lines.append(f"| ASVS | {asvs_version} | {asvs_url} | {asvs_total} (L1+L2) |\n")
    print(f"  -> {asvs_total} Requirements (L1+L2)", file=sys.stderr)

    print("Baue MASVS-Katalog ...", file=sys.stderr)
    masvs_catalog, masvs_version, masvs_url, masvs_total = build_masvs()
    (out_dir / "masvs-2.1-mobile.json").write_text(json.dumps(masvs_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sources_lines.append(f"| MASVS | {masvs_version} | {masvs_url} | {masvs_total} |\n")
    print(f"  -> {masvs_total} Controls", file=sys.stderr)

    print("Baue BSI-Katalog ...", file=sys.stderr)
    bsi_catalog, bsi_edition, bsi_url, bsi_total = build_bsi()
    (out_dir / "bsi-grundschutz-normal.json").write_text(json.dumps(bsi_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sources_lines.append(f"| BSI IT-Grundschutz | Edition {bsi_edition} | {bsi_url} | {bsi_total} (Basis+Standard) |\n")
    print(f"  -> {bsi_total} Anforderungen (Basis+Standard) über {len(bsi_catalog['bausteine'])} Bausteine", file=sys.stderr)

    print("Baue SSDF-Katalog ...", file=sys.stderr)
    ssdf_catalog, ssdf_version, ssdf_url, ssdf_total = build_ssdf()
    (out_dir / "ssdf-1.1-curated.json").write_text(json.dumps(ssdf_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sources_lines.append(f"| NIST SSDF | {ssdf_version} | {ssdf_url} | {ssdf_total} (kuratierte Teilmenge) |\n")
    print(f"  -> {ssdf_total} Praktiken (kuratierte Teilmenge)", file=sys.stderr)

    print("Baue SLSA-Katalog ...", file=sys.stderr)
    slsa_catalog, slsa_version, slsa_url, slsa_total = build_slsa()
    (out_dir / "slsa-build-curated.json").write_text(json.dumps(slsa_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    sources_lines.append(f"| SLSA | {slsa_version} | {slsa_url} | {slsa_total} (kuratierte Teilmenge, Build-Track) |\n")
    print(f"  -> {slsa_total} Anforderungen (kuratierte Teilmenge, Build-Track)", file=sys.stderr)

    sources_lines.append(
        "\nMethodik-Referenz (nicht maschinenlesbar, Vorgehensmodell): "
        "[BSI-Standard 200-2](https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/BSI_Standards/standard_200_2.pdf) "
        "— siehe `../BSI-METHODIK.md`.\n\n"
        "Lizenzhinweise: OWASP-Standards stehen unter CC BY-SA 4.0; BSI-Inhalte "
        "unterliegen den Nutzungsbedingungen des BSI (Quellenangabe bei Weiterverwendung).\n\n"
        "checkType-Klassifikation der BSI-Anforderungen (code/config/process/manual) "
        "ist eine deterministische Keyword-Heuristik in `build_catalog.py` "
        "(`classify_check_type`) — bei Unsicherheit entscheidet der Prüfer-Subagent "
        "im jeweiligen Audit-Lauf im Einzelfall neu.\n"
    )
    (out_dir / "SOURCES.md").write_text("".join(sources_lines), encoding="utf-8")

    print(f"\nFertig. Kataloge liegen in: {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
