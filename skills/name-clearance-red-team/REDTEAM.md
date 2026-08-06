# Red Team (Phase 9, mandatory)

The adversarial pass. By this point in the flow, the research clusters have already produced a set of findings — the red team's job is to argue *against* the emerging conclusion, not to summarize it. Run at the strongest reasoning/effort setting this environment offers, if it offers a choice (SKILL.md "Capability tier"). Write `redteam.json`.

## Why this is a separate, mandatory step

The research clusters are largely fact-gathering: did a search return a hit, yes or no. The red team is the step that asks the harder question a fact-gathering pass tends to under-ask: *if I were trying to argue this name is risky (or that a clean-looking finding isn't actually clean), what would I say?* Skipping it produces exactly the failure mode this skill exists to prevent — a report that reads clean because nothing adversarial was ever attempted against it.

## What to do

1. **Attack every low/clean finding.** For each finding the research clusters scored GREEN/YELLOW, or for the absence of findings in a given cluster, construct the strongest plausible argument that it's actually riskier than scored — reversed goods/services proximity (does a "SaaS platform" and "consulting services" registration in a related Nice class actually compete more than the raw text suggests?), family-of-marks arguments (does the conflicting owner hold a portfolio of similar marks, making this an even stronger prior right than a single registration implies?), territorial spillover (does a mark registered only in one target territory have reputation/well-known-mark protection reaching further than its registration?), bad-faith framing (would a court read the coined name as an intentional echo of an existing brand?).

2. **Attack the absence of a finding.** For every cluster that produced zero findings, ask explicitly: was the search actually broad enough, or does the clean result just reflect a narrow query? Missing coverage (a `manual_only` source that ended up `blocked` rather than user-verified) is exactly where a real conflict hides behind an apparently clean report — flag it here even though `RISK-MODEL.md`'s gates already catch it independently.

3. **Write a rebuttal for every attack.** Each entry in `redteam.json`'s `attacks` array needs a `vector` (short label), `severity` (0–4, same scale as a finding's `severity`), `argument` (the adversarial case, written as if arguing against using this name), and `rebuttal` (the honest counter — why the attack does or doesn't actually change the finding's band). A rebuttal that just restates the original finding without engaging the attack is not a real rebuttal — the `red_team_completed` gate checks presence, not quality, so this is on you, not the gate.

4. **Reopen anything you can't rebut.** If an attack's argument is genuinely stronger than the rebuttal, don't paper over it — add it to `missed_vectors` (`vector`, `severity`, and `resolution` once addressed) and go back to research if it points at a concrete lookup that wasn't done. `missed_vectors` entries with `resolution: null` keep `red_team_completed` false — an unresolved doubt is not allowed to disappear silently between the red team and the final report.

## `redteam.json` shape

```json
{
  "attacks": [
    {"vector": "family_of_marks", "severity": 2, "argument": "...", "rebuttal": "..."}
  ],
  "missed_vectors": [
    {"vector": "narrow_wipo_query", "severity": 3, "resolution": "re-ran WIPO GBD with broader Nice class filter, see findings/intl-wipo.json"}
  ]
}
```

## What the red team is not

It does not re-run any lookups itself (that's the research clusters' job, possibly reopened per point 4 above) and it does not produce a verdict (`RISK-MODEL.md`/`risk_model.py` is the only source of a verdict string). Its output feeds the synthesis pass (SKILL.md step 10) and is rendered as its own report section (REPORTING.md) — it is not folded silently into the findings list.
