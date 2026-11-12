#!/usr/bin/env python3
"""Deterministic helper for the grundschutz-audit skill (stdlib only).

The BSI Grundschutz++ catalog is CC BY-SA 4.0 and is never bundled: `fetch`
downloads it at run time into the run's cache directory and pins the commit.

Commands
  fetch    <cache> [--ref REF]                    download catalog, ISO mapping, namespaces
  show     <cache> <id>...                        full requirement text, threats, links
  categories <cache>                              target-object category tree
  model    <cache> <model.json> [--out FILE]      requirement package (STM.2.1)
  check    <package.json> <check.json> [--out F]  validate target/actual check (UMS.1.1)
  soa      <cache> <package.json> <effective.json> [--out FILE]  ISO 27001 Annex A SoA

model.json: {"assets": [{"id", "name", "categories": [...], "protection":
  {"confidentiality"|"integrity"|"availability"|"authenticity": "normal"|"hoch"}}],
  "relevance": {"<id or prefix such as GEB / GEB.3>": {"relevant": bool, "reason": str}}}
check.json: {"<id>": {"status": one of STATUSES, "evidence": [...], "measure": "M-..",
  "justification": str, "risk_ref": "R-.."}}

Exit codes: 0 ok, 1 validation findings, 2 usage or input error.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = "BSI-Bund/Stand-der-Technik-Bibliothek"
FILES = {
    "catalog.json": "control_layer/Grundschutz++/Grundschutz++-resolved_catalog.json",
    "iso-mapping.json": "control_layer/Mappings/ISO-27001-zu-GSpp/ISO27001-AnnexA-to-GS++-mapping_collection.json",
    "basethreats.csv": "documentation/namespaces/basethreats.csv",
    "target_object_categories.csv": "documentation/namespaces/target_object_categories.csv",
}
# STM.2.1.1: the ISMS practices belong to every requirement package. RISK carries
# the risk method that GC.7.2 / STM.4.1 require, so it is always included too.
ISMS_PRACTICES = ("GC", "STM", "UMS", "VRB", "PERF", "RISK")
DIMENSIONS = ("confidentiality", "integrity", "availability", "authenticity")
NEEDS = ("normal", "hoch")
STATUSES = ("umgesetzt", "teilweise", "nicht_umgesetzt", "entbehrlich", "nachweis_fehlt")
PARAM_RE = re.compile(r"\{\{\s*insert:\s*param,\s*([^}\s]+)\s*\}\}")


class InputError(Exception):
    pass


def _strict_load(path):
    def no_dupes(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise InputError(f"{path}: duplicate JSON key {key!r}")
            seen[key] = value
        return seen

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=no_dupes)
    except FileNotFoundError:
        raise InputError(f"{path}: not found") from None
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON ({exc})") from None


def _csv_rows(path):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise InputError(f"{path}: not found (run fetch first)") from None
    return list(csv.DictReader(io.StringIO(text)))


def _split(value):
    return [part.strip() for part in value.split(",") if part.strip()]


# ---------------------------------------------------------------- catalog


def parse_catalog(data):
    """Flatten the OSCAL catalog into {id: requirement} including sub-controls."""
    catalog = data.get("catalog")
    if not isinstance(catalog, dict):
        raise InputError("catalog.json: missing 'catalog' object")
    out = {}

    def control(ct, parent):
        props = {p["name"]: p.get("value", "") for p in ct.get("props", [])}
        params = {}
        for prm in ct.get("params", []):
            values = prm.get("values") or []
            params[prm["id"]] = values[0] if values else prm.get("label", prm["id"])
        stmt, guidance, sprops = "", "", {}
        for part in ct.get("parts", []):
            if part.get("name") == "statement":
                stmt = PARAM_RE.sub(lambda m: params.get(m.group(1), m.group(1)), part.get("prose", ""))
                sprops = {p["name"]: p.get("value", "") for p in part.get("props", [])}
            elif part.get("name") == "guidance":
                guidance = part.get("prose", "")
        categories = _split(sprops.get("target_object_categories", ""))
        if not categories and parent is not None:
            categories = list(out[parent]["categories"])  # sub-control inherits
        links = ct.get("links", [])
        rid = ct["id"]
        out[rid] = {
            "id": rid,
            "parent": parent,
            "practice": rid.split(".")[0],
            "title": ct.get("title", ""),
            "sec_level": props.get("sec_level", ""),
            "effort_level": int(props["effort_level"]) if props.get("effort_level", "").isdigit() else None,
            "cia": {d: int(props[d]) for d in DIMENSIONS if props.get(d, "").isdigit()},
            "threats": _split(props.get("threats", "")),
            "tags": _split(props.get("tags", "")),
            "categories": categories,
            "modal_verb": sprops.get("modal_verb", ""),
            "documentation": sprops.get("documentation", ""),
            "statement": stmt,
            "guidance": guidance,
            "requires": [l["href"].lstrip("#") for l in links if l.get("rel") == "required"],
            "related": [l["href"].lstrip("#") for l in links if l.get("rel") == "related"],
        }
        for sub in ct.get("controls", []):
            control(sub, rid)

    def group(g):
        for sub in g.get("groups", []):
            group(sub)
        for ct in g.get("controls", []):
            control(ct, None)

    group(catalog)
    if not out:
        raise InputError("catalog.json: no controls found")
    return out


def catalog_meta(data):
    meta = data.get("catalog", {}).get("metadata", {})
    return {"title": meta.get("title", ""), "last_modified": meta.get("last-modified", ""),
            "version": meta.get("version", "")}


def load_categories(path):
    """Return {name: parent_name_or_None} plus a synonym map to canonical names."""
    rows = _csv_rows(path)
    by_uuid = {r["UUID"]: r["Zielobjekt"].strip() for r in rows if r.get("UUID")}
    parents, synonyms = {}, {}
    for r in rows:
        name = r["Zielobjekt"].strip()
        parents[name] = by_uuid.get((r.get("ChildOfUUID") or "").strip())
        for syn in _split(r.get("Synonyme") or ""):
            synonyms.setdefault(syn.casefold(), name)
        synonyms[name.casefold()] = name
    return parents, synonyms


def ancestors(name, parents):
    """The category itself plus every parent (STM.2.1.4.1), cycle-safe."""
    chain, seen = [], set()
    while name and name not in seen:
        seen.add(name)
        chain.append(name)
        name = parents.get(name)
    return chain


def load_cache(cache):
    cache = Path(cache)
    data = _strict_load(cache / "catalog.json")
    parents, synonyms = load_categories(cache / "target_object_categories.csv")
    return data, parse_catalog(data), parents, synonyms


# ---------------------------------------------------------------- model


def build_package(reqs, parents, synonyms, model):
    """STM.2.1: map assets to categories, inherit, select, deduplicate."""
    errors = []
    assets = model.get("assets")
    if not isinstance(assets, list) or not assets:
        raise InputError("model.json: 'assets' must be a non-empty list")
    relevance = model.get("relevance", {})
    expanded = {}
    for a in assets:
        aid = a.get("id")
        if not aid:
            errors.append("asset without id")
            continue
        if aid in expanded:
            errors.append(f"{aid}: duplicate asset id")
        cats = set()
        for raw in a.get("categories", []):
            canon = synonyms.get(str(raw).casefold())
            if canon is None:
                errors.append(f"{aid}: unknown target-object category {raw!r}")
                continue
            cats.update(ancestors(canon, parents))
        if not a.get("categories"):
            errors.append(f"{aid}: no target-object category")
        prot = a.get("protection", {})
        for d in DIMENSIONS:
            if prot.get(d) not in NEEDS:
                errors.append(f"{aid}: protection.{d} must be one of {NEEDS}")
        expanded[aid] = (cats, prot)
    if errors:
        raise InputError("; ".join(errors))

    def raised_for(req, prot):
        dims = [d for d in DIMENSIONS if req["cia"].get(d, 0) > 0] or list(DIMENSIONS)
        return any(prot.get(d) == "hoch" for d in dims)

    package, undecided = {}, []
    for rid, req in reqs.items():
        if req["practice"] in ISMS_PRACTICES:
            if req["sec_level"] == "erhöht" and not any(
                    raised_for(req, prot) for _, prot in expanded.values()):
                continue
            package[rid] = dict(req, assets=["*"], reason="STM.2.1.1 ISMS practice")
            continue
        if not req["categories"]:
            decision = _decision(relevance, rid)
            if decision is None:
                undecided.append(rid)
            elif decision.get("relevant") is True:
                if not str(decision.get("reason", "")).strip():
                    raise InputError(f"relevance.{rid}: reason required (STM.2.1.5)")
                package[rid] = dict(req, assets=decision.get("assets", ["*"]),
                                    reason="STM.2.1.5 " + decision["reason"].strip())
            continue
        wanted = {synonyms.get(c.casefold(), c) for c in req["categories"]}
        hits = []
        for aid, (cats, prot) in expanded.items():
            if not (wanted & cats):
                continue
            if req["sec_level"] == "erhöht" and not raised_for(req, prot):
                continue
            hits.append(aid)
        if hits:  # STM.2.1.4.2: one entry per requirement, all assets listed
            package[rid] = dict(req, assets=sorted(hits),
                                reason="STM.2.1.4 category " + ", ".join(sorted(wanted)))
    covered = {a for r in package.values() for a in r["assets"]}
    # "*" (ISMS practices) does not count: every asset needs its own requirements.
    uncovered = sorted(a for a in expanded if a not in covered)
    missing_deps = sorted({d for r in package.values() for d in r["requires"]
                           if d not in package})
    return {
        "requirements": [package[k] for k in sorted(package, key=_id_key)],
        "undecided_relevance": sorted(undecided, key=_id_key),
        "assets_without_requirements": uncovered,
        "dependencies_outside_package": missing_deps,
    }


def _decision(relevance, rid):
    """Most specific relevance decision: exact id, then each parent prefix (GEB.3.1 -> GEB.3 -> GEB)."""
    parts = rid.split(".")
    for n in range(len(parts), 0, -1):
        hit = relevance.get(".".join(parts[:n]))
        if hit is not None:
            return hit
    return None


def _id_key(rid):
    head, *rest = rid.split(".")
    return (head, [int(x) if x.isdigit() else 0 for x in rest])


# ---------------------------------------------------------------- check


def check(package, entries):
    """Validate the target/actual check and derive the binary UMS.1.1 status."""
    findings = []
    reqs = {r["id"]: r for r in package.get("requirements", [])}
    for rid in sorted(set(entries) - set(reqs), key=_id_key):
        findings.append(f"{rid}: not in requirement package")
    for rid, req in reqs.items():
        e = entries.get(rid)
        if e is None:
            findings.append(f"{rid}: no status")
            continue
        st = e.get("status")
        if st not in STATUSES:
            findings.append(f"{rid}: status must be one of {STATUSES}")
            continue
        if st == "umgesetzt" and not e.get("evidence"):
            findings.append(f"{rid}: umgesetzt without evidence")
        if st == "entbehrlich":
            if not str(e.get("justification", "")).strip():
                findings.append(f"{rid}: entbehrlich without justification")
            if req.get("modal_verb") == "MUSS" and not e.get("risk_ref"):
                findings.append(f"{rid}: MUSS requirement entbehrlich without risk_ref")
        if st in ("teilweise", "nicht_umgesetzt", "nachweis_fehlt") and not e.get("measure"):
            findings.append(f"{rid}: {st} without measure")
    effective = {}

    def ok(rid, stack=()):
        if rid in effective:
            return effective[rid]
        if rid in stack:
            return False  # cyclic dependency is never satisfied
        st = entries.get(rid, {}).get("status")
        own = st in ("umgesetzt", "entbehrlich")
        deps = reqs.get(rid, {}).get("requires", [])
        result = own and all(ok(d, stack + (rid,)) for d in deps if d in reqs)
        effective[rid] = result
        return result

    for rid in reqs:
        ok(rid)
    blocked = sorted((r for r in reqs if not effective[r]
                      and entries.get(r, {}).get("status") in ("umgesetzt", "entbehrlich")),
                     key=_id_key)
    return findings, {"effective": {r: ("ja" if effective[r] else "nein") for r in sorted(reqs, key=_id_key)},
                      "blocked_by_dependency": blocked}


# ---------------------------------------------------------------- soa


def soa(mapping, package, effective):
    reqs = {r["id"] for r in package.get("requirements", [])}
    eff = effective.get("effective", effective)
    rows = {}
    for coll in mapping.get("mapping-collection", {}).get("mappings", []):
        for m in coll.get("maps", []):
            targets = [t["id-ref"] for t in m.get("targets", [])]
            for src in m.get("sources", []):
                row = rows.setdefault(src["id-ref"], {"control": src["id-ref"], "targets": []})
                row["targets"].extend(t for t in targets if t not in row["targets"])
    out = []
    for key in sorted(rows, key=lambda k: [int(x) if x.isdigit() else x for x in k.split(".")]):
        row = rows[key]
        applicable = [t for t in row["targets"] if t in reqs]
        done = [t for t in applicable if eff.get(t) == "ja"]
        if not applicable:
            state = "not_applicable"
        elif len(done) == len(applicable):
            state = "implemented"
        elif done:
            state = "partially_implemented"
        else:
            state = "not_implemented"
        out.append(dict(row, applicable=applicable, implemented=done, state=state))
    return out


# ---------------------------------------------------------------- fetch


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "grundschutz-audit"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https host
        return resp.read()


def fetch(cache, ref):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    commit = ref
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        try:
            commit = _get(f"https://api.github.com/repos/{REPO}/commits/{ref}").decode()
            commit = json.loads(commit)["sha"]
        except Exception as exc:  # pin failed: keep the ref, say so
            print(f"warning: could not pin {ref} to a commit ({exc})", file=sys.stderr)
    sources = {"repository": f"https://github.com/{REPO}", "ref": ref, "commit": commit,
               "license": "CC BY-SA 4.0 (BSI)", "files": {}}
    for name, rel in FILES.items():
        url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{rel}"
        body = _get(url)
        (cache / name).write_bytes(body)
        sources["files"][name] = {"path": rel, "sha256": hashlib.sha256(body).hexdigest()}
    data = _strict_load(cache / "catalog.json")
    sources["catalog"] = catalog_meta(data)
    sources["catalog"]["requirements"] = len(parse_catalog(data))
    (cache / "sources.json").write_text(json.dumps(sources, indent=1, ensure_ascii=False), encoding="utf-8")
    return sources


# ---------------------------------------------------------------- cli


def _emit(obj, out):
    text = json.dumps(obj, indent=1, ensure_ascii=False)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gspp.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("cache"); p.add_argument("--ref", default="main")
    p = sub.add_parser("show"); p.add_argument("cache"); p.add_argument("ids", nargs="+")
    p = sub.add_parser("categories"); p.add_argument("cache")
    p = sub.add_parser("model"); p.add_argument("cache"); p.add_argument("model"); p.add_argument("--out")
    p = sub.add_parser("check"); p.add_argument("package"); p.add_argument("entries"); p.add_argument("--out")
    p = sub.add_parser("soa"); p.add_argument("cache"); p.add_argument("package")
    p.add_argument("effective"); p.add_argument("--out")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if args.cmd == "fetch":
            s = fetch(args.cache, args.ref)
            print(f"{s['catalog']['title']} {s['catalog']['last_modified']} "
                  f"({s['catalog']['requirements']} requirements) @ {s['commit']}")
            return 0
        if args.cmd == "categories":
            parents, _ = load_categories(Path(args.cache) / "target_object_categories.csv")
            for name in sorted(parents):
                print(" > ".join(reversed(ancestors(name, parents))))
            return 0
        if args.cmd == "show":
            _, reqs, _, _ = load_cache(args.cache)
            threats = {r["ID"]: r["Begriff"] for r in _csv_rows(Path(args.cache) / "basethreats.csv")}
            unknown = [i for i in args.ids if i not in reqs]
            if unknown:
                raise InputError("unknown requirement id(s): " + ", ".join(unknown))
            for rid in args.ids:
                r = dict(reqs[rid], threat_names=[f"{t} {threats.get(t, '?')}" for t in reqs[rid]["threats"]])
                _emit(r, None)
            return 0
        if args.cmd == "model":
            _, reqs, parents, synonyms = load_cache(args.cache)
            pkg = build_package(reqs, parents, synonyms, _strict_load(args.model))
            _emit(pkg, args.out)
            print(f"package: {len(pkg['requirements'])} requirements, "
                  f"{len(pkg['undecided_relevance'])} undecided, "
                  f"{len(pkg['assets_without_requirements'])} assets without requirements",
                  file=sys.stderr)
            return 1 if pkg["undecided_relevance"] or pkg["assets_without_requirements"] else 0
        if args.cmd == "check":
            findings, eff = check(_strict_load(args.package), _strict_load(args.entries))
            _emit(eff, args.out)
            for f in findings:
                print("finding: " + f, file=sys.stderr)
            return 1 if findings else 0
        if args.cmd == "soa":
            rows = soa(_strict_load(Path(args.cache) / "iso-mapping.json"),
                       _strict_load(args.package), _strict_load(args.effective))
            _emit(rows, args.out)
            return 0
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
