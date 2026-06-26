#!/usr/bin/env python3
"""LLM-input preparation (slice 03) — H1 input + the token-gated S1
representation + Modus-A flagging. Pure + deterministic.

Split of responsibility (documented under the slice-03 LLM mechanism):

* The agent performs **H1** (Metadata-Condenser, Haiku): it reads the raw
  per-app metadata prepared by :func:`prepare_h1_input` and emits one
  *condensed profile* per app — a 1-sentence positioning + top-5 keywords
  + a tag. The raw ``description`` is allowed to reach H1 (it needs it to
  write the positioning sentence).
* Python prepares the **S1 representation** that the later LLM stages
  read, via :func:`build_llm_input`. It is built from the H1 *outputs*
  (condensed profiles) + the score table + Reddit summaries — and contains
  **no raw description** (AC1). That representation is what the token gate
  measures.

Modus A (PRD): when ``own_app_id`` is present the own app is flagged as
``is_own_app`` and carried as just another reference entry — no separate
code path (AC7). Modus B = the same path with no own-app entry.

Condensed-profile schema (H1 output, one per app)::

    {"app_id", "title", "positioning", "top_keywords": [<=5], "tag"}

The S1 representation schema (what the gate measures + S1/S2 read)::

    {
      "own_app_id": <str|None>,
      "meta": {"app_name", "category", "seed_keywords"},
      "condensed_profiles": [ <condensed profile>, ... ],  # strength-ordered
      "score_table": [ <scored keyword>, ... ],            # capped top-N
      "reddit_summaries": [ {subreddit, title, score}, ... ],
    }
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Caps that bound the representation before the gate even measures it.
_SCORE_TABLE_CAP = 50  # top-50 keywords by opportunity (PRD: top 50-80 in report)
_REDDIT_CAP = 10       # top-10 Reddit summaries feed S1's qualitative read

# Fields H1 is allowed to see (the raw metadata it condenses).
_H1_INPUT_FIELDS = (
    "app_id", "title", "subtitle", "description",
    "keyword_hints", "category", "developer",
    "rating_avg", "rating_count", "price_model",
)


def prepare_h1_input(
    competitors: List[Dict], *, own_app_id: Optional[str] = None
) -> List[Dict]:
    """Build the clean per-app raw-metadata artefact the H1 subagent reads.

    One record per competitor, carrying only the fields H1 needs to write a
    positioning sentence + pick top-5 keywords. The own app (Modus A) is
    flagged ``is_own_app=True`` when its id matches ``own_app_id`` — it is
    just another entry in the same list (no separate path).

    Slice 04: Play competitors carry their text under ``short_description`` /
    ``full_description`` (no Apple ``subtitle``/``description``). The resolver
    falls back to those Play slots so H1 sees Play's rich text and can write a
    meaningful positioning sentence for the Play vertical too — same I/O
    schema, no LLM-mechanism change.
    """
    own = (own_app_id or "").strip()
    out: List[Dict] = []
    for c in competitors:
        app_id = str(c.get("id") or "")
        record = {field: _resolve_h1_field(c, field) for field in _H1_INPUT_FIELDS}
        record["app_id"] = app_id
        record["is_own_app"] = bool(own and app_id and app_id == own)
        out.append(record)
    return out


def _resolve_h1_field(competitor: Dict, field: str):
    """Source an H1 field from the competitor record, with Play fallbacks.

    ``description`` falls back to Play's ``full_description`` and ``subtitle``
    to Play's ``short_description`` when the Apple-named field is empty, so a
    unified Apple+Play corpus reads coherently without platform branching.
    """
    if field == "app_id":
        return str(competitor.get("id") or "")
    value = competitor.get(field, "")
    if value:
        return value
    if field == "description":
        return competitor.get("full_description") or ""
    if field == "subtitle":
        return competitor.get("short_description") or ""
    return ""


def build_llm_input(
    condensed_profiles: List[Dict],
    keywords: List[Dict],
    reddit_threads: List[Dict],
    *,
    config: Dict,
) -> Dict:
    """Assemble the token-gated S1 representation from H1 outputs + artefacts.

    No raw ``description`` is carried — only condensed profiles (positioning
    + top_keywords + tag) + the score table + Reddit summaries. The own app
    is flagged ``is_own_app`` on its condensed profile (Modus A). Score
    table + Reddit are pre-capped so the representation is bounded before
    the gate measures it; the caller is expected to pass
    ``condensed_profiles`` in strength order (the gate trims the tail).
    """
    own_app_id = (config.get("own_app_id") or "").strip() or None
    own_ids = {own_app_id} if own_app_id else set()

    flagged_profiles: List[Dict] = []
    for p in condensed_profiles:
        profile = dict(p)
        app_id = str(profile.get("app_id") or "")
        profile["is_own_app"] = bool(app_id and app_id in own_ids)
        flagged_profiles.append(profile)

    score_table = [
        {
            "term": k.get("term"),
            "competition": k.get("competition", 0),
            "relevance": k.get("relevance", 0),
            "opportunity": k.get("opportunity", 0),
            "split": k.get("split", ""),
            "is_gap": bool(k.get("is_gap")),
            "suggest": bool(k.get("suggest")),
        }
        for k in (keywords or [])[:_SCORE_TABLE_CAP]
    ]

    reddit_summaries = [
        {
            "subreddit": t.get("subreddit") or "",
            "title": t.get("title") or "",
            "score": t.get("score") or 0,
        }
        for t in (reddit_threads or [])[:_REDDIT_CAP]
    ]

    return {
        "own_app_id": own_app_id,
        "meta": {
            "app_name": config.get("app_name", ""),
            "category": config.get("category", "other"),
            "seed_keywords": list(config.get("seed_keywords") or []),
        },
        "condensed_profiles": flagged_profiles,
        "score_table": score_table,
        "reddit_summaries": reddit_summaries,
    }


def own_app_is_referenced(rep: Dict) -> bool:
    """True when the representation carries the own app as a reference (Modus A).

    Deterministic Modus-A flag (AC7): the self-audit is present iff the own
    app actually made it into the condensed profiles. No own_app_id -> False.
    """
    own = (rep.get("own_app_id") or "").strip()
    if not own:
        return False
    return any(
        str(p.get("app_id") or "") == own for p in rep.get("condensed_profiles", [])
    )
