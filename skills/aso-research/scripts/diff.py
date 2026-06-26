#!/usr/bin/env python3
"""Cross-run diff for aso-research (slice 06 ``--compare-last``).

Diffs the current run's **machine-readable** artefacts against the most
recent PRIOR run of the same app in the same output dir and produces a
deterministic deltas section (US10): which competitors entered/left, which
keywords rose/fell (and are brand-new or gone), and where the listing
recommendation changed per store/slot. With no prior run it reports
``"no prior run to diff"`` instead of erroring.

The diff is keyed on the stable artefacts the deterministic spine writes
(``keywords.json`` / ``competition.json`` and the agent-produced
``llm/s2-listing*.json``) — never on free text — so it is reproducible:
the same two run dirs always yield the same diff (US18).

"Most recent prior run" = the chronologically greatest run-id strictly
less than the current one **with the same app slug** (run-ids are
``YYYYMMDD-HHMMSS-<app-slug>``). A diff across two different apps is
meaningless (US10 is about re-running the *same* app after some weeks);
a different-app prior run is therefore treated as "no prior run".
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# "YYYYMMDD-HHMMSS-" is the fixed 16-char timestamp prefix of a run-id;
# everything after it is the app-slug.
_RUN_ID_PREFIX_LEN = len("YYYYMMDD-HHMMSS-")

# Caps so the rendered section stays readable; the structured diff keeps
# the full lists.
_LISTING_DISPLAY_CAP = 15
_KEYWORD_DISPLAY_CAP = 20


def _slug_of(run_id: str) -> str:
    if len(run_id) <= _RUN_ID_PREFIX_LEN:
        return ""
    return run_id[_RUN_ID_PREFIX_LEN:]


def is_run_id(name: str) -> bool:
    """True for ``YYYYMMDD-HHMMSS-<slug>`` directory names."""
    parts = name.split("-", 2)
    if len(parts) != 3:
        return False
    date, clock, slug = parts
    return (
        len(date) == 8
        and date.isdigit()
        and len(clock) == 6
        and clock.isdigit()
        and bool(slug)
    )


def find_prior_run(output_root: str, current_run_id: str) -> Optional[str]:
    """Most recent prior run-id of the same app in ``output_root``, or None.

    Chronological ordering falls out of the run-id's leading timestamp
    (a lexicographic string compare agrees with chronological order for
    same-timestamp-format ids). Only prior, same-slug, run-id-shaped
    directories qualify; the current run and any non-run directory are
    ignored. Returns ``None`` when nothing qualifies (-> "no prior run").
    """
    if not os.path.isdir(output_root):
        return None
    slug = _slug_of(current_run_id)
    candidates: List[str] = []
    for name in os.listdir(output_root):
        path = os.path.join(output_root, name)
        if not os.path.isdir(path):
            continue
        if name == current_run_id:
            continue
        if not is_run_id(name):
            continue
        if name >= current_run_id:
            continue  # only strictly-prior runs
        if slug and _slug_of(name) != slug:
            continue  # same app only (US10)
        candidates.append(name)
    return max(candidates) if candidates else None


def _load_json(path: str) -> Any:
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _comp_key(c: Dict) -> tuple:
    return (str(c.get("id", "")), str(c.get("platform", "apple")))


def _kw_key(k: Dict) -> tuple:
    return (str(k.get("term", "")), str(k.get("platform", "apple")))


def compute_diff(current_dir: str, prior_dir: str) -> Dict[str, Any]:
    """Compute the structured deltas between two run directories.

    All deltas are deterministic: sets are materialised into sorted lists
    and deltas are ordered by magnitude then key, so identical inputs
    always produce an identical result.
    """
    # --- competitors entered / left (by store id + platform) ---
    cur_comp = _load_json(os.path.join(current_dir, "competition.json")) or []
    pri_comp = _load_json(os.path.join(prior_dir, "competition.json")) or []
    cur_ids = {_comp_key(c) for c in cur_comp}
    pri_ids = {_comp_key(c) for c in pri_comp}
    entered = sorted(cur_ids - pri_ids)
    left = sorted(pri_ids - cur_ids)

    # --- keyword rise / fall / new / gone (by opportunity delta) ---
    cur_kw = _load_json(os.path.join(current_dir, "keywords.json")) or []
    pri_kw = _load_json(os.path.join(prior_dir, "keywords.json")) or []
    cur_opp = {_kw_key(k): int(k.get("opportunity", 0)) for k in cur_kw}
    pri_opp = {_kw_key(k): int(k.get("opportunity", 0)) for k in pri_kw}

    risen: List[tuple] = []
    fallen: List[tuple] = []
    new_kw: List[tuple] = []
    gone_kw: List[tuple] = []
    for key in set(cur_opp) | set(pri_opp):
        cur_v = cur_opp.get(key)
        pri_v = pri_opp.get(key)
        if cur_v is not None and pri_v is not None:
            delta = cur_v - pri_v
            if delta > 0:
                risen.append((key, delta))
            elif delta < 0:
                fallen.append((key, delta))
        elif cur_v is not None:
            new_kw.append(key)
        else:
            gone_kw.append(key)
    risen.sort(key=lambda x: (-x[1], x[0]))
    fallen.sort(key=lambda x: (x[1], x[0]))

    # --- listing-recommendation changes (per store/slot recommended text) ---
    listing_changes: List[Dict[str, str]] = []
    for store, fname in (
        ("apple", "llm/s2-listing.json"),
        ("play", "llm/s2-listing-play.json"),
    ):
        cur_s2 = _load_json(os.path.join(current_dir, fname))
        pri_s2 = _load_json(os.path.join(prior_dir, fname))
        if not cur_s2 or not pri_s2:
            continue
        pri_slots = {
            (s.get("slot")): ((s.get("recommended") or {}).get("text", ""))
            for s in pri_s2.get("slots", [])
        }
        for s in cur_s2.get("slots", []):
            slot = s.get("slot")
            cur_text = (s.get("recommended") or {}).get("text", "")
            pri_text = pri_slots.get(slot, "")
            if cur_text != pri_text:
                listing_changes.append(
                    {
                        "store": store,
                        "slot": str(slot),
                        "before": pri_text,
                        "after": cur_text,
                    }
                )
    listing_changes.sort(key=lambda c: (c["store"], c["slot"]))

    return {
        "competitors_entered": [{"id": k[0], "platform": k[1]} for k in entered],
        "competitors_left": [{"id": k[0], "platform": k[1]} for k in left],
        "keywords_risen": [
            {"term": k[0], "platform": k[1], "delta": d} for k, d in risen
        ],
        "keywords_fallen": [
            {"term": k[0], "platform": k[1], "delta": d} for k, d in fallen
        ],
        "keywords_new": [{"term": k[0], "platform": k[1]} for k in sorted(new_kw)],
        "keywords_gone": [{"term": k[0], "platform": k[1]} for k in sorted(gone_kw)],
        "listing_changes": listing_changes,
    }


def _kv_list(items: List[Dict], *fields: str) -> str:
    rendered = []
    for it in items:
        rendered.append(", ".join(f"{f}={it.get(f)}" for f in fields))
    return "; ".join(rendered)


def build_diff_section(diff: Dict[str, Any], *, prior_run_id: str) -> str:
    """Render the structured diff as a Markdown section (deterministic)."""
    lines: List[str] = []
    lines.append("## Diff vs last run")
    lines.append("")
    lines.append(f"_Compared against prior run `{prior_run_id}` (same app)._")
    lines.append("")

    entered = diff["competitors_entered"]
    left = diff["competitors_left"]
    lines.append(
        f"- **Competitors entered** ({len(entered)}): "
        + (_kv_list(entered[:_LISTING_DISPLAY_CAP], "id", "platform") or "—")
    )
    lines.append(
        f"- **Competitors left** ({len(left)}): "
        + (_kv_list(left[:_LISTING_DISPLAY_CAP], "id", "platform") or "—")
    )

    risen = diff["keywords_risen"]
    fallen = diff["keywords_fallen"]
    new_kw = diff["keywords_new"]
    gone_kw = diff["keywords_gone"]
    lines.append(
        f"- **Keywords risen** ({len(risen)}, top "
        f"{min(len(risen), _KEYWORD_DISPLAY_CAP)} by opportunity delta): "
        + (_kv_list(risen[:_KEYWORD_DISPLAY_CAP], "term", "platform", "delta") or "—")
    )
    lines.append(
        f"- **Keywords fallen** ({len(fallen)}, top "
        f"{min(len(fallen), _KEYWORD_DISPLAY_CAP)} by opportunity delta): "
        + (_kv_list(fallen[:_KEYWORD_DISPLAY_CAP], "term", "platform", "delta") or "—")
    )
    lines.append(
        f"- **Keywords new** ({len(new_kw)}): "
        + (_kv_list(new_kw[:_KEYWORD_DISPLAY_CAP], "term", "platform") or "—")
    )
    lines.append(
        f"- **Keywords gone** ({len(gone_kw)}): "
        + (_kv_list(gone_kw[:_KEYWORD_DISPLAY_CAP], "term", "platform") or "—")
    )

    changes = diff["listing_changes"]
    lines.append(
        f"- **Listing-recommendation changes** ({len(changes)}):"
    )
    if changes:
        for c in changes[:_LISTING_DISPLAY_CAP]:
            lines.append(
                f"  - `{c['store']}` / `{c['slot']}`: "
                f"`{c['before']}` -> `{c['after']}`"
            )
    else:
        lines.append("  - _No recommended-slot text changed._")
    lines.append("")
    return "\n".join(lines) + "\n"


def compare_last(current_dir: str, output_root: str, current_run_id: str) -> str:
    """Full ``--compare-last`` entry point -> Markdown deltas section.

    Returns the "no prior run to diff" notice when there is no prior run
    of the same app in ``output_root``; otherwise the deterministic deltas
    section comparing the current run against that prior run.
    """
    prior = find_prior_run(output_root, current_run_id)
    if prior is None:
        return (
            "_No prior run to diff — this is the first run of this app in "
            "this output dir._\n"
        )
    prior_dir = os.path.join(output_root, prior)
    diff = compute_diff(current_dir, prior_dir)
    return build_diff_section(diff, prior_run_id=prior)
