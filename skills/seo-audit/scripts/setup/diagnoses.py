#!/usr/bin/env python3
"""Curated diagnose strings for verify-mode status codes.

A mapping from (tool, status_code) → human-readable hint. The set is
frozen by `tests/seo-audit/test_setup_verify_diagnoses.py`; extending
it requires editing the test too — keeps the catalogue curated.

Tools covered: indexnow, pagespeed, bing, gsc.
Codes covered: 401, 403, 404, 429 per tool (the documented common cases).
"""

from __future__ import annotations

from typing import Dict, Tuple

from . import urls as URLS


# (tool, status) → diagnose. Keys must lowercase the tool name.
DIAGNOSES: Dict[Tuple[str, int], str] = {
    # -- PageSpeed Insights ---------------------------------------------
    ("pagespeed", 401): (
        "PageSpeed: API-Key fehlt oder ungültig. Neuen Key in der Cloud "
        f"Console erstellen: {URLS.PAGESPEED_API_CONSOLE}"
    ),
    ("pagespeed", 403): (
        "PageSpeed: API-Key existiert, aber die PageSpeed-Insights-API ist "
        f"im Projekt nicht aktiviert. Aktivieren: {URLS.PAGESPEED_API_LIBRARY}"
    ),
    ("pagespeed", 404): (
        "PageSpeed: Endpoint nicht gefunden — vermutlich URL-Drift. "
        f"Doku gegenprüfen: {URLS.PAGESPEED_API_DOCS}"
    ),
    ("pagespeed", 429): (
        "PageSpeed: Tageskontingent erschöpft (25 000 Calls/Tag, 240/100 s/User). "
        f"Bis morgen warten oder rate limit anpassen: {URLS.PAGESPEED_API_DOCS}"
    ),

    # -- Bing Webmaster -------------------------------------------------
    ("bing", 401): (
        "Bing: API-Key abgelehnt. Key in Bing Webmaster Tools unter "
        f"Settings → API Access neu generieren: {URLS.BING_WEBMASTER_HOME}"
    ),
    ("bing", 403): (
        "Bing: Site nicht verifiziert oder API-Zugriff nicht freigeschaltet. "
        f"Verifikation prüfen: {URLS.BING_WEBMASTER_HOME}"
    ),
    ("bing", 404): (
        "Bing: Endpoint oder Site-URL nicht gefunden. "
        f"Doku gegenprüfen: {URLS.BING_WEBMASTER_API_DOCS}"
    ),
    ("bing", 429): (
        "Bing: Daily Quota erschöpft (10/Tag default, 10 000/Tag verifiziert). "
        "Bis UTC-Mitternacht warten oder BING_DAILY_LIMIT setzen."
    ),

    # -- IndexNow -------------------------------------------------------
    ("indexnow", 401): (
        "IndexNow: HEAD auf die Key-Datei abgelehnt. Server liefert kein "
        f"Lesezugriff auf <public>/<key>.txt. Setup-Doku: {URLS.INDEXNOW_DOCS}"
    ),
    ("indexnow", 403): (
        "IndexNow: Key-Datei ist nicht öffentlich lesbar (403 forbidden). "
        "Hosting-Regeln für statische Dateien prüfen."
    ),
    ("indexnow", 404): (
        "IndexNow: Key-Datei nicht gefunden unter https://<host>/<key>.txt. "
        "Datei nach dem nächsten Deploy erreichbar machen."
    ),
    ("indexnow", 429): (
        "IndexNow: Rate-Limit gegen die Key-URL erreicht — Hosting drosselt. "
        f"Spec: {URLS.INDEXNOW_DOCS}"
    ),

    # -- Google Search Console (MCP) ------------------------------------
    ("gsc", 401): (
        "GSC: OAuth-Token abgelaufen. `mcp__gsc__reauthenticate` ausführen "
        f"und neu zustimmen: {URLS.GSC_MCP_REPO}"
    ),
    ("gsc", 403): (
        "GSC: Property nicht verifiziert oder Service-Account hat keinen "
        f"Lesezugriff. In GSC freischalten: {URLS.GSC_HOME}"
    ),
    ("gsc", 404): (
        "GSC: Property nicht gefunden — URL stimmt nicht mit verifizierter "
        f"Property überein. Verifizierte Sites listen: {URLS.GSC_HOME}"
    ),
    ("gsc", 429): (
        "GSC: API-Quote überschritten (1 200/Minute, 30 000/Tag). "
        f"Quotas: {URLS.GSC_API_QUOTAS_DOCS}"
    ),
}


def diagnose(tool: str, status: int) -> str:
    """Return a curated diagnose string, or a generic fallback."""
    key = (tool.lower(), int(status))
    if key in DIAGNOSES:
        return DIAGNOSES[key]
    if status == 0:
        return f"{tool}: Netzwerk-Fehler — kein Server-Response erhalten."
    if 500 <= status < 600:
        return f"{tool}: Server-Fehler {status} — Service-Status prüfen."
    if 200 <= status < 300:
        return f"{tool}: OK ({status})."
    return f"{tool}: Unerwarteter Status {status}."
