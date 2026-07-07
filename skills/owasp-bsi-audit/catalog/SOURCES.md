# Katalog-Quellen (Provenienz)
Zuletzt gebaut/abgerufen: **2026-07-07**

| Standard | Version/Edition | Quelle | Requirements |
|---|---|---|---|
| ASVS | 5.0.0 | https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0_release/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json | 253 (L1+L2) |
| MASVS | 2.1.0 | https://raw.githubusercontent.com/OWASP/masvs/master/OWASP_MASVS.yaml | 24 |
| BSI IT-Grundschutz | Edition 2023 | https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/IT-GS-Kompendium/XML_Kompendium_2023.xml?__blob=publicationFile | 69 (Basis+Standard) |
| NIST SSDF | 1.1 | https://raw.githubusercontent.com/CycloneDX/official-3rd-party-standards/main/standards/NIST/SSDF/nist_secure-software-development-framework_1.1.cdx.json | 5 (kuratierte Teilmenge) |
| SLSA | 1.2 | https://raw.githubusercontent.com/slsa-framework/slsa/releases/v1.2/spec/build-requirements.md | 2 (kuratierte Teilmenge, Build-Track) |

Methodik-Referenz (nicht maschinenlesbar, Vorgehensmodell): [BSI-Standard 200-2](https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Grundschutz/BSI_Standards/standard_200_2.pdf) — siehe `../BSI-METHODIK.md`.

Lizenzhinweise: OWASP-Standards stehen unter CC BY-SA 4.0; BSI-Inhalte unterliegen den Nutzungsbedingungen des BSI (Quellenangabe bei Weiterverwendung).

checkType-Klassifikation der BSI-Anforderungen (code/config/process/manual) ist eine deterministische Keyword-Heuristik in `build_catalog.py` (`classify_check_type`) — bei Unsicherheit entscheidet der Prüfer-Subagent im jeweiligen Audit-Lauf im Einzelfall neu.
