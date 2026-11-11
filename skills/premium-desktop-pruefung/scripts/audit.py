#!/usr/bin/env python3
"""Ledger tool for a Premium Desktop audit run.

Commands:
  init RUN            create RUN/audit.json (never overwrites an existing ledger)
  merge RUN PART...   merge worker fragments into RUN/audit.json (coordinator only)
  check RUN           validate the ledger; exit 0 complete, 1 open/violations, 2 broken
  report RUN          print a Markdown report (also on exit 1)
  digest RUN          print the snapshot hash for final.snapshot
  capacity            suggest how many subagents may run in parallel right now

Python 3.8+, standard library only. Only the coordinator writes audit.json.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "references" / "methoden.md"
RULE = r"[A-Z][A-Z0-9]{0,11}-[0-9]{2,3}"
TABLES = {"objects": "O", "evidence": "E", "units": "U", "candidates": "C", "findings": "F"}
VIEWS = ("product", "code", "runtime", "platform")
KINDS = ("source", "runtime", "image", "trace", "diff", "test", "document")
LIVE = {"runtime", "image", "trace"}
PRODUCT_FIELDS = ("audience", "type", "core_task", "first_value", "platforms", "scope", "coordinator")
MERGEABLE = set(TABLES) | {"views", "waves", "product", "final"}
HARD_CAP = 3  # never more parallel subagents than this, whatever the machine says


def catalog():
    keys = re.findall(r"^\|\s*(" + RULE + r")\s*\|", CATALOG.read_text(encoding="utf-8"), re.M)
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("rule catalog empty or contains a duplicate rule ID")
    return keys


def unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError(f"duplicate JSON key: {k}")
        result[k] = v
    return result


def read_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: JSON object expected")
    return data


def load(folder):
    return read_json(folder / "audit.json")


def write_ledger(folder, data):
    """Atomic write so a crash mid-merge never leaves a half-written ledger."""
    fd, tmp = tempfile.mkstemp(dir=str(folder), prefix=".audit.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2, ensure_ascii=False)
            out.write("\n")
        os.replace(tmp, folder / "audit.json")
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def digest(data, folder):
    snapshot = dict(data)
    final = data.get("final") if isinstance(data.get("final"), dict) else {}
    snapshot["final"] = {k: v for k, v in final.items() if k != "snapshot"}
    hashes = {}
    root = folder.resolve()
    for eid, item in (data.get("evidence") or {}).items():
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            continue
        path = (root / item["file"]).resolve()
        if root in path.parents and path.is_file():
            with path.open("rb") as stream:
                h = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
                hashes[eid] = h.hexdigest()
    snapshot = {"ledger": snapshot, "artifacts": hashes, "catalog": CATALOG.read_text(encoding="utf-8")}
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def init(folder, rules):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "parts").mkdir(exist_ok=True)
    (folder / "evidence").mkdir(exist_ok=True)
    target = folder / "audit.json"
    if target.exists():
        print(f"{target} already exists, left untouched")
        return
    data = {"version": 1, "product": {k: "" for k in PRODUCT_FIELDS},
            "views": {k: {"account": "", "evidence": []} for k in VIEWS},
            **{k: {} for k in TABLES}, "waves": [], "final": {}}
    write_ledger(folder, data)
    print(f"{target} · {len(rules)} catalog rules")


def merge(folder, parts):
    """Merge worker fragments. Table rows are inserted or replaced by ID, waves are appended,
    views/product fields are overwritten field by field, final is replaced."""
    data = load(folder)
    log = []
    for part in parts:
        frag = read_json(part)
        unknown = set(frag) - MERGEABLE
        if unknown:
            raise ValueError(f"{part}: unknown top-level keys {sorted(unknown)}")
        for name, prefix in TABLES.items():
            rows = frag.get(name, {})
            if not isinstance(rows, dict):
                raise ValueError(f"{part}: {name} must be an object")
            for key, row in rows.items():
                if not re.fullmatch(prefix + r"-[a-zA-Z0-9][a-zA-Z0-9._-]*", key):
                    raise ValueError(f"{part}: invalid ID {key} for {name}")
                if not isinstance(row, dict):
                    raise ValueError(f"{part}: {key} must be an object")
                log.append(("replaced" if key in data[name] else "added", key))
                data[name][key] = row
        for view, row in (frag.get("views") or {}).items():
            if view not in VIEWS or not isinstance(row, dict):
                raise ValueError(f"{part}: invalid view {view}")
            data["views"][view].update(row)
            log.append(("updated", "views." + view))
        for field, value in (frag.get("product") or {}).items():
            if field not in PRODUCT_FIELDS:
                raise ValueError(f"{part}: unknown product field {field}")
            data["product"][field] = value
            log.append(("updated", "product." + field))
        waves = frag.get("waves", [])
        if not isinstance(waves, list):
            raise ValueError(f"{part}: waves must be a list")
        for wave in waves:
            data["waves"].append(wave)
            log.append(("appended", f"wave {len(data['waves'])}"))
        if "final" in frag:
            data["final"] = frag["final"]
            log.append(("replaced", "final"))
    write_ledger(folder, data)
    for action, key in log:
        print(f"{action}: {key}")
    if any(a == "replaced" for a, _ in log):
        print("note: replaced rows overwrite earlier results; make sure that was intended")


def capacity(cap):
    """Suggest a parallel subagent count from the 1-minute load per core.
    Subagents themselves are light; builds, test runs and app instances they start are not."""
    cpus = os.cpu_count() or 1
    try:
        load1 = os.getloadavg()[0]
    except (AttributeError, OSError):
        load1 = 0.0
    per_core = load1 / cpus
    slots = 3 if per_core < 0.5 else 2 if per_core < 0.8 else 1
    slots = max(1, min(slots, cap, HARD_CAP))
    print(f"slots={slots} load1={load1:.1f} cpus={cpus} load_per_core={per_core:.2f}")
    return slots


def check(data, folder, rules):
    issues = []

    def require(test, msg):
        if not test:
            issues.append(msg)

    def record(value, loc):
        if isinstance(value, dict):
            return value
        issues.append(f"{loc}: object expected")
        return {}

    def strings(row, fields, loc):
        for field in fields.split():
            require(filled(row.get(field)), f"{loc}.{field}: text missing")

    def ids(row, key, allowed, loc, empty=False):
        arr = row.get(key)
        if not isinstance(arr, list) or any(not filled(x) for x in arr):
            issues.append(f"{loc}.{key}: list of IDs expected")
            return set()
        values = set(arr)
        require(len(arr) == len(values), f"{loc}.{key}: duplicate IDs")
        require(empty or values, f"{loc}.{key}: empty")
        require(values <= set(allowed), f"{loc}.{key}: unknown {sorted(values - set(allowed))}")
        return values & set(allowed)

    require(type(data.get("version")) is int and data["version"] == 1, "version must be 1")
    product = record(data.get("product"), "product")
    strings(product, " ".join(PRODUCT_FIELDS), "product")
    tables = {}
    for name, prefix in TABLES.items():
        rows = record(data.get(name), name)
        tables[name] = {k: record(v, k) for k, v in rows.items()}
        for key in rows:
            require(re.fullmatch(prefix + r"-[a-zA-Z0-9][a-zA-Z0-9._-]*", key), f"{key}: invalid ID for {name}")
    objects, evidence, units, candidates, findings = (tables[k] for k in TABLES)
    require(objects and units, "inventory or audit units missing")
    valid_artifacts = set()
    for key, row in evidence.items():
        strings(row, "kind file observation context", key)
        require(row.get("kind") in KINDS, f"{key}: unknown evidence kind")
        if filled(row.get("file")):
            rel = Path(row["file"])
            path = (folder / rel).resolve()
            if not rel.is_absolute() and folder.resolve() in path.parents and path.is_file() and path.stat().st_size:
                valid_artifacts.add(key)
            else:
                issues.append(f"{key}: relative non-empty evidence file missing or outside the run")

    def proof(row, loc, kinds=None, field="evidence"):
        values = ids(row, field, evidence, loc)
        if kinds:
            require(any(e in valid_artifacts and evidence[e].get("kind") in kinds for e in values),
                    f"{loc}.{field}: evidence of kind {sorted(kinds)} missing")
        return values

    views = record(data.get("views"), "views")
    for name in VIEWS:
        row = record(views.get(name), "views." + name)
        strings(row, "account", "views." + name)
        proof(row, "views." + name, LIVE if name == "runtime" else None)
    required_pairs = set()
    required_variants = set()
    for key, row in objects.items():
        strings(row, "description variants", key)
        proof(row, key)
        ids(row, "links", objects, key, empty=True)
        mapped = ids(row, "rules", rules, key)
        required_pairs.update((key, r) for r in mapped)
        plan = record(row.get("plan"), key + ".plan")
        require(set(plan) == mapped, f"{key}: variant plan must hold exactly the mapped rules")
        for r, variants in plan.items():
            if not isinstance(variants, list) or not variants or any(not filled(v) for v in variants):
                issues.append(f"{key}.{r}: concrete target variants missing")
                continue
            require(len(variants) == len(set(variants)), f"{key}.{r}: duplicate target variant")
            required_variants.update((key, r, v) for v in variants)
    require(set(rules) <= {r for _, r in required_pairs},
            f"rules without inventory mapping: {sorted(set(rules) - {r for _, r in required_pairs})}")
    observed = set()
    if not any(row.get("status") in ("pass", "candidate") for row in units.values()):
        issues.append("all audit units open or excluded")
    for key, row in units.items():
        strings(row, "task owner variant expected status observation", key)
        obj, rule = row.get("object"), row.get("rule")
        require(filled(obj) and filled(rule) and (obj, rule) in required_pairs, f"{key}: object/rule mapping missing")
        triple = (obj, rule, row.get("variant"))
        require(triple in required_variants, f"{key}: variant outside the target plan")
        observed.add(triple)
        proof(row, key, LIVE if row.get("status") in ("pass", "candidate") and row.get("mode") == "runtime" else None)
        require(row.get("mode") in ("runtime", "inspection"), f"{key}: invalid mode")
        state = row.get("status")
        require(state in ("pass", "candidate", "excluded"), f"{key}: open ({state})")
        if state in ("pass", "candidate", "excluded"):
            strings(row, "countercheck", key)
        if state == "excluded":
            strings(row, "rationale", key)
        if row.get("mode") == "inspection":
            strings(row, "inspection_reason", key)
        if state not in ("pass", "candidate", "excluded"):
            strings(row, "missing next", key)
        order = row.get("wave")
        require(type(order) is int and order >= 1, f"{key}: invalid wave")
    require(required_variants <= observed, f"missing variant units: {sorted(required_variants - observed)}")
    require(any(r.get("mode") == "runtime" and r.get("status") in ("pass", "candidate") for r in units.values()),
            "no completed runtime test")
    wave_rows = data.get("waves")
    if not isinstance(wave_rows, list):
        issues.append("waves: list expected")
        wave_rows = []
    require(wave_rows, "audit waves missing")
    actors = {r.get("owner") for r in units.values() if filled(r.get("owner"))}
    if filled(product.get("coordinator")):
        actors.add(product["coordinator"])
    critics = set()
    reviewed = set()
    for number, raw in enumerate(wave_rows, 1):
        key = f"wave {number}"
        row = record(raw, key)
        strings(row, "critic critique", key)
        critic = row.get("critic")
        require(critic not in actors and critic not in critics, f"{key}: fresh critic missing")
        critics.add(critic)
        covered = ids(row, "units", units, key)
        for uid in covered:
            last = units[uid].get("wave")
            require(type(last) is int and last >= number, f"{uid}: wrong last wave")
        reviewed |= {(uid, number) for uid in covered}
        proof(row, key)
        for uid in ids(row, "gaps", units, key, empty=True):
            later = units[uid].get("wave")
            require(type(later) is int and later > number, f"{key}: gap {uid} without a later audit")
    for uid, row in units.items():
        require((uid, row.get("wave")) in reviewed, f"{uid}: critique of its last wave missing")

    claimed_units = set()
    assigned = set()
    causes = set()
    for cid, row in candidates.items():
        strings(row, "symptom", cid)
        proof(row, cid)
        for uid in ids(row, "units", units, cid):
            require(units[uid].get("status") == "candidate", f"{cid}: {uid} has no candidate status")
            claimed_units.add(uid)
    for uid, row in units.items():
        require(row.get("status") != "candidate" or uid in claimed_units, f"{uid}: candidate record missing")
    fixers = {r.get("implementer") for r in findings.values() if filled(r.get("implementer"))}
    verifiers = set()
    for fid, row in findings.items():
        strings(row, "cause verifier alternative decision reasoning", fid)
        group = ids(row, "candidates", candidates, fid)
        require(not (assigned & group), f"{fid}: candidate assigned more than once")
        assigned |= group
        cause = str(row.get("cause", "")).strip().casefold()
        require(cause not in causes, f"{fid}: merge findings with the same cause")
        causes.add(cause)
        verifier = row.get("verifier")
        require(verifier not in actors | critics | fixers, f"{fid}: verification not independent")
        verifiers.add(verifier)
        verification = proof(row, fid)
        originals = set()
        for cid in group:
            originals |= ids(candidates[cid], "evidence", evidence, cid)
        require(originals <= verification, f"{fid}: original evidence missing from verification")
        decision = row.get("decision")
        if decision == "open":
            strings(row, "missing next", fid)
        require(decision in ("confirmed", "refuted"), f"{fid}: decision open ({decision})")
        if decision != "confirmed":
            continue
        strings(row, "change implementer retester retest_result", fid)
        require(row.get("retest_status") == "pass", f"{fid}: retest not passed")
        require(row.get("retester") not in actors | critics | fixers, f"{fid}: retest not independent")
        before = proof(row, fid, LIVE, "before")
        patch = proof(row, fid, {"diff"}, "patch")
        after = proof(row, fid, LIVE, "after")
        strings(row, "adjacent_result", fid)
        adjacent = proof(row, fid, LIVE | {"test"}, "adjacent")
        require(bool(adjacent - before - after - patch), f"{fid}: separate evidence for the adjacent path missing")
        require(row.get("adjacent_status") == "pass", f"{fid}: adjacent test not passed")
        before_files = {Path(folder, evidence[e]["file"]).resolve() for e in before & valid_artifacts}
        after_files = {Path(folder, evidence[e]["file"]).resolve() for e in after & valid_artifacts}
        require(not (before_files & after_files), f"{fid}: before and after use the same file")
        require(bool(after - before - patch), f"{fid}: separate post-change evidence missing")
    require(set(candidates) == assigned, f"unassigned candidates: {sorted(set(candidates) - assigned)}")
    final = record(data.get("final"), "final")
    strings(final, "critic critique", "final")
    retesters = {r.get("retester") for r in findings.values() if filled(r.get("retester"))}
    require(final.get("critic") not in actors | critics | fixers | verifiers | retesters, "final critic not fresh")
    require(final.get("gaps") == [], "final review: gaps open or not assessed")
    proof(final, "final")
    require(final.get("snapshot") == digest(data, folder), "final critique missing or data changed since")
    return issues


def brief(data, issues):
    print("# Premium Desktop Audit\n")
    print("**" + ("INCOMPLETE" if issues else "COMPLETE") + "**\n")
    product = data.get("product", {})
    if isinstance(product, dict):
        for k in ("audience", "type", "core_task", "scope", "platforms"):
            print(f"- {k}: {product.get(k, '')}")
    for table, fields in (("units", ("task", "status", "observation", "rationale", "evidence", "missing", "next")),
                          ("findings", ("cause", "decision", "reasoning", "change", "patch", "retest_status",
                                        "after", "adjacent_result", "adjacent", "missing", "next")),
                          ("candidates", ("symptom", "units", "evidence"))):
        print(f"\n## {table}\n")
        rows = data.get(table)
        if isinstance(rows, dict):
            for k, row in rows.items():
                if isinstance(row, dict):
                    print(f"- **{k}** " + " · ".join(f"{f}: {row[f]}" for f in fields if row.get(f)))
    print("\n## Evidence register\n")
    for k, row in (data.get("evidence") or {}).items():
        if isinstance(row, dict):
            print(f"- {k}: {row.get('file')} · {row.get('context')} · {row.get('observation')}")
    if issues:
        print("\n## Open checks and ledger errors\n")
        for msg in issues:
            print(f"- {msg}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check", "report", "digest"):
        sub.add_parser(name).add_argument("folder", type=Path)
    m = sub.add_parser("merge")
    m.add_argument("folder", type=Path)
    m.add_argument("parts", type=Path, nargs="+")
    c = sub.add_parser("capacity")
    c.add_argument("--max", type=int, default=HARD_CAP, help=f"upper bound (never above {HARD_CAP})")
    args = parser.parse_args(argv)
    try:
        if args.command == "capacity":
            capacity(args.max)
            return 0
        rules = catalog()
        if args.command == "init":
            init(args.folder, rules)
            return 0
        if args.command == "merge":
            merge(args.folder, args.parts)
            return 0
        data = load(args.folder)
        if args.command == "digest":
            print(digest(data, args.folder))
            return 0
        issues = check(data, args.folder, rules)
        if args.command == "report":
            brief(data, issues)
        else:
            print("\n".join(issues) if issues else "COMPLETE")
        return int(bool(issues))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        print(f"INCOMPLETE · ledger unreadable/invalid: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
