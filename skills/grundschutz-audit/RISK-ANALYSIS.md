# Method: phase 6, risk analysis

This phase follows BSI standard 200-3 and the catalog's RISK.1 requirements (GC.7.2, STM.4). Read `gspp.py show <run>/catalog RISK.1.1` (and the other RISK.1.x) for the exact current wording, and quote it in `04-risk-analysis.md`.

## When

A risk analysis is mandatory for:

1. every asset with protection need `hoch` in any dimension;
2. every asset that the catalog does not adequately model (`assets_without_requirements`, special technology, unusual deployment);
3. every requirement whose status is not effective (`effective = nein`), as the risk of the gap until its measure is done;
4. every `entbehrlich` decision on a MUSS requirement (`risk_ref` in `check.json`);
5. every confirmed technical finding with severity medium or higher.

## Steps

1. **Threat overview.** For each target object, start from the elementary threats in `catalog/basethreats.csv` (G 0.1 to G 0.47). Use those the catalog links to the object's requirements (`threats` in `package.json`) plus any others that apply. Add specific threats from phase 4 (attack classes, confirmed findings). Discard a threat only with a one-line reason.
2. **Assessment.** For each relevant threat, estimate **likelihood** and **impact** on a four-step scale:
   - likelihood: selten, mittel, häufig, sehr häufig;
   - impact: vernachlässigbar, begrenzt, beträchtlich, existenzbedrohend.

   Base impact on the protection needs from phase 2 and likelihood on exposure, attacker effort and existing safeguards (status from phase 5). Give a short reason for each rating.
3. **Risk level.** Combine the two in the 4×4 matrix:

   |                  | vernachl. | begrenzt | beträchtl. | existenzbedr. |
   |------------------|-----------|----------|------------|---------------|
   | sehr häufig      | mittel    | hoch     | sehr hoch  | sehr hoch     |
   | häufig           | mittel    | mittel   | hoch       | sehr hoch     |
   | mittel           | gering    | mittel   | mittel     | hoch          |
   | selten           | gering    | gering   | mittel     | mittel        |

   Do not change the matrix without recording the reason as an assumption.
4. **Treatment.** Choose one per risk:
   - **avoid:** change the process or architecture;
   - **reduce:** apply additional measures, catalog or own;
   - **transfer:** insurance, contract or provider;
   - **accept:** only for `gering`/`mittel` without an existential impact. Acceptance is always a decision *proposed* to management, never made by you.

   Each reducing measure gets an `M-xxx` and joins the plan.
5. **Consolidation.** Check that the additional measures fit together and with the existing ones, and that they are economical. Assess the risk again after treatment, which gives the residual risk.

## Output

`04-risk-analysis.md` contains:

- a short method section with the matrix and scales;
- the **risk register**, one row per risk: `R-xxx`, target object, threat (G 0.x or specific), reason, likelihood, impact, risk, treatment, measures, residual risk, and an acceptance proposal for management;
- the list of residual risks that management must formally accept. This list also goes into `REPORT.md`.
