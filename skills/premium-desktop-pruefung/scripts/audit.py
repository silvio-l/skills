#!/usr/bin/env python3
"""Portable UI/UX ledger. Python >=3.10, standard library; never executes target code."""
import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('files', 'objects', 'units', 'evidence', 'findings', 'jobs', 'reviews', 'gaps', 'profile',
          'applicability', 'equivalences')
RULE_TABLES = ('applicability', 'equivalences')  # optional in older ledgers; bound to the inventory digest
TRANSITIONS = {'pending': {'running', 'excluded', 'blocked'},
               'running': {'pass', 'fail', 'blocked', 'excluded'},
               'pass': {'running'}, 'fail': {'running'},
               'blocked': {'pending', 'running', 'excluded'}, 'excluded': {'running'}}


def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON key: ' + key)
        out[key] = value
    return out


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def load(run):
    """Read the ledger; ledgers written before the rule tables existed gain empty ones."""
    data = read(Path(run) / 'audit.json')
    for table in TABLES:
        data.setdefault(table, {})
    return data


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, data, compact=False):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.ux-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            if compact:  # the ledger is machine state; indentation multiplies its size
                json.dump(data, stream, ensure_ascii=False, separators=(',', ':'))
            else:
                json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def schema_check(value, schema, at='$'):
    """Evaluate the exact JSON Schema subset used by the bundled schema, fail closed."""
    allowed = {'$schema', '$id', 'title', 'type', 'enum', 'minLength', 'minimum',
               'properties', 'required', 'additionalProperties', 'items', 'uniqueItems'}
    if set(schema) - allowed:
        raise ValueError('unsupported schema keyword at ' + at)
    types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool}
    typ = schema.get('type')
    if typ and (not isinstance(value, types[typ]) or (typ == 'integer' and isinstance(value, bool))):
        raise ValueError(at + ': expected ' + typ)
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(at + ': invalid enum')
    if isinstance(value, str) and len(value.strip()) < schema.get('minLength', 0):
        raise ValueError(at + ': empty text')
    if typ == 'integer' and value < schema.get('minimum', value):
        raise ValueError(at + ': below minimum')
    if typ == 'object':
        if set(schema.get('required', [])) - set(value):
            raise ValueError(at + ': missing required fields')
        props = schema.get('properties', {})
        for key, item in value.items():
            sub = props.get(key, schema.get('additionalProperties', {}))
            if sub is False:
                raise ValueError(at + ': unknown key ' + key)
            if isinstance(sub, dict):
                schema_check(item, sub, at + '.' + key)
    if typ == 'array':
        if schema.get('uniqueItems') and len({digest(x) for x in value}) != len(value):
            raise ValueError(at + ': duplicate item')
        for i, item in enumerate(value):
            schema_check(item, schema.get('items', {}), at + '[' + str(i) + ']')


def catalog():
    data = read(ROOT / 'references/criteria.json')
    rows = data if isinstance(data, list) else data['criteria']
    ids = [x['id'] for x in rows]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('empty or duplicate criterion IDs')
    return {x['id']: x for x in rows}


def uid(obj, variant, criterion):
    return 'U-' + digest([obj, variant, criterion])[:20]


def blank_unit(obj, variant, criterion):
    return dict(object=obj, variant=variant, criterion=criterion, status='pending', actor='',
                method='', expected='', actual='', steps=[], evidence=[], limitations=[], reason='')


def context_digest(data):
    """Bind obstacle observations to the evidenced capabilities and scope."""
    return digest({k: data['profile'].get(k) for k in ('runtime', 'platforms', 'scope')})


def blocker_state(data, row):
    if row['status'] != 'blocked':
        return None
    if not row.get('blocker'):
        return 'unsubstantiated'
    if row['blocker']['context_digest'] != context_digest(data):
        return 'stale'
    return 'documented'


def inventory_digest(data):
    # Rule tables join the digest only when used, so digests of older ledgers stay stable.
    keys = ('revision', 'catalog_hash', 'files', 'objects', 'profile', 'scan_complete', 'scan_limits', 'scan_exclusions')
    return digest({k: data[k] for k in keys + RULE_TABLES if k in data and (k not in RULE_TABLES or data[k])})


def rule_matches(rule, criterion, rules):
    return criterion in rule['criteria'] or rules.get(criterion, {}).get('dimension') in rule['dimensions']


def coverage(data, rules):
    """Map unit IDs that the matrix omits to the rule that covers them.

    Applicability rules declare object/criterion combinations not applicable; equivalence rules
    let one representative variant stand for others. Both need evidence and fall under the
    inventory review, so a covered unit is a reviewable claim, not a silent omission."""
    covered = {}
    for key, rule in sorted(data['applicability'].items()):
        for obj, row in data['objects'].items():
            if (rule['kinds'] and row['kind'] not in rule['kinds']) or (rule['objects'] and obj not in rule['objects']):
                continue
            for criterion in rules:
                if rule_matches(rule, criterion, rules):
                    for variant in row['variants']:
                        covered.setdefault(uid(obj, variant, criterion), ('not-applicable', key, None))
    for key, rule in sorted(data['equivalences'].items()):
        row = data['objects'].get(rule['object'])
        if not row:
            continue
        for criterion in rules:
            if rule['criteria'] or rule['dimensions']:
                if not rule_matches(rule, criterion, rules):
                    continue
            representative = uid(rule['object'], rule['representative'], criterion)
            if representative in covered:
                continue
            for variant in rule['variants']:
                covered.setdefault(uid(rule['object'], variant, criterion), ('equivalent', key, representative))
    return covered


_COVERAGE = {}


def cached_coverage(data):
    """Coverage depends only on objects and rules; avoid recomputing it per pruned unit."""
    rules = catalog()
    key = digest([sorted(rules), {k: r.get('dimension') for k, r in rules.items()},
                  {t: data.get(t, {}) for t in ('objects',) + RULE_TABLES}])
    if key not in _COVERAGE:
        _COVERAGE.clear()
        _COVERAGE[key] = coverage(data, rules)
    return _COVERAGE[key]


def rule_errors(data, rules):
    errors = []
    kinds = set(read(ROOT / 'schemas/run.schema.json')['properties']['objects']['additionalProperties']['properties']['kind']['enum'])
    dimensions = {r.get('dimension') for r in rules.values()}
    for table in RULE_TABLES:
        for key, rule in data[table].items():
            if not rule['criteria'] and not rule['dimensions'] and table == 'applicability':
                errors.append(key + ': applicability rule needs criteria or dimensions')
            if set(rule['criteria']) - set(rules):
                errors.append(key + ': unknown criterion in rule')
            if set(rule['dimensions']) - dimensions:
                errors.append(key + ': unknown dimension in rule')
            if not rule['evidence']:
                errors.append(key + ': rule needs primary evidence')
            if table == 'applicability':
                if set(rule['kinds']) - kinds:
                    errors.append(key + ': unknown object kind in rule')
                if set(rule['objects']) - set(data['objects']):
                    errors.append(key + ': unknown object in rule')
    members = {}
    for key, rule in data['equivalences'].items():
        row = data['objects'].get(rule['object'])
        if not row:
            errors.append(key + ': unknown object'); continue
        if not rule['variants'] or rule['representative'] in rule['variants']:
            errors.append(key + ': equivalence needs member variants other than the representative')
        if not ({rule['representative']} | set(rule['variants'])) <= set(row['variants']):
            errors.append(key + ': equivalence names a variant the object does not have')
        for variant in rule['variants']:
            if (rule['object'], variant) in members:
                errors.append(key + ': variant ' + variant + ' already belongs to ' + members[(rule['object'], variant)])
            members[(rule['object'], variant)] = key
    for key, rule in data['equivalences'].items():
        if (rule['object'], rule['representative']) in members:
            errors.append(key + ': representative is itself a member of another equivalence')
    return errors


def review_digest(data, scope, target):
    if scope == 'inventory':
        return inventory_digest(data)
    if scope == 'final':
        return digest({k: v for k, v in data.items() if k not in ('reviews', 'history', 'sequence')})
    table = {'unit': 'units', 'finding': 'findings'}[scope]
    row = dict(data[table][target])
    if scope == 'finding':
        row.pop('status')  # validation precedes promotion, without changing reviewed content
    return digest(row)


def checked_exclusions(exclusions):
    if not isinstance(exclusions, dict):
        raise ValueError('scan exclusions must be a path-to-reason object')
    for path, reason in exclusions.items():
        if (not isinstance(path, str) or not path or path.startswith('/') or
                any(part in ('', '.', '..') for part in path.split('/')) or '\\' in path or
                not isinstance(reason, str) or not reason.strip()):
            raise ValueError('scan exclusion requires a relative canonical path and reason')
    return exclusions


def scan(repo, max_files=50000, max_bytes=16 * 1024 * 1024, exclusions=None, checkpoint=None):
    # Explicit sibling loading also supports importlib-based test/adapter callers.
    import importlib.util
    spec = importlib.util.spec_from_file_location('premium_source_scan', ROOT / 'scripts/source_scan.py')
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    return scanner.scan_tree(repo, max_files, max_bytes,
                             checked_exclusions(exclusions or {}), checkpoint)


def initialize(run, repo, revision, exclusions=None):
    run, repo = Path(run).resolve(), Path(repo).resolve()
    if run == repo or repo in run.parents:
        raise ValueError('audit workspace must be outside target repository')
    if not repo.is_dir():
        raise ValueError('repository directory missing')
    run.mkdir(parents=True, exist_ok=True)
    if (run / 'audit.json').exists():
        raise ValueError('run already exists; resume it')
    exclusions = checked_exclusions(exclusions or {})
    files, limits = scan(repo, exclusions=exclusions, checkpoint=run / 'scan-state.json')
    data = dict(version=1, run_id=str(uuid.uuid4()), repository=str(repo), revision=revision,
                catalog_hash=digest(catalog()), sequence=0, scan_complete=not limits,
                scan_limits=limits, **{t: {} for t in TABLES}, history=[])
    if exclusions:
        data['scan_exclusions'] = exclusions
        data['scan_complete'] = False
    data['files'] = files
    (run / 'evidence').mkdir(exist_ok=True)
    (run / 'parts').mkdir(exist_ok=True)
    atomic(run / 'audit.json', data)
    return data


def validate(data, run, complete=False, check_source=None):
    schema = read(ROOT / 'schemas/run.schema.json')
    schema_check(data, schema)
    checked_exclusions(data.get('scan_exclusions', {}))
    errors = []
    def need(ok, message):
        if not ok:
            errors.append(message)
    rules = catalog()
    need(data['catalog_hash'] == digest(rules), 'catalog changed; start a new run')
    for key in TABLES:
        need(all(x.strip() for x in data[key]), 'empty ID in ' + key)
    # Replay journal independently, including transitions, so edits cannot hide invalid history.
    replay = {t: {} for t in TABLES}
    for key, row in data['files'].items():
        link_limit = next((limit for limit in data['scan_limits']
                           if limit.startswith('unresolved symlink: ' + key + ': ')), '')
        blocked = row['sha256'] == 'unread' or bool(link_limit)
        replay['files'][key] = dict(sha256=row['sha256'], decision='blocked' if blocked else 'pending',
                                   reason=link_limit or (row['reason'] if blocked else ''), objects=[])
    replay['history'] = []
    for event in data['history']:
        t, key = event['table'], event['id']
        if t not in TABLES:
            errors.append('unknown history table'); continue
        old = replay[t].get(key)
        need(old == event['before'], 'history before mismatch: ' + key)
        try:
            if event['after'] is not None:
                schema_check(event['after'], schema['properties'][t]['additionalProperties'])
            put(replay, event['actor'], t, key, copy.deepcopy(event['after']))
        except (ValueError, KeyError, TypeError) as exc:
            errors.append('invalid history operation: ' + key + ': ' + str(exc))
    need({t:replay[t] for t in TABLES} == {t:data[t] for t in TABLES}, 'ledger differs from journal')
    for name in ('objects', 'units', 'findings', 'reviews', 'gaps', 'profile'):
        for key, row in data[name].items():
            for eid in row.get('evidence', []):
                need(eid in data['evidence'], key + ': unknown evidence ' + eid)
    for key, row in data['evidence'].items():
        path = (Path(run) / row['file']).resolve()
        safe = Path(run).resolve() in path.parents and not (Path(run) / row['file']).is_symlink()
        need(safe and path.is_file(), key + ': missing/unsafe evidence')
        if safe and path.is_file():
            need(filehash(path) == row['sha256'], key + ': evidence changed')
    for key, row in data['files'].items():
        need(set(row['objects']) <= set(data['objects']), key + ': unknown object mapping')
        for obj in row['objects']:
            if obj in data['objects']:
                need(key in data['objects'][obj]['sources'], key + ': mapping not reciprocal')
        need(not row['objects'] or row['decision'] == 'mapped', key + ': object mapping requires mapped decision')
        if row['decision'] == 'mapped':
            need(bool(row['objects']), key + ': mapped without objects')
        if row['decision'] in ('blocked', 'excluded'):
            need(bool(row['reason'].strip()), key + ': missing exclusion/limitation reason')
        if complete:
            need(row['decision'] in ('mapped', 'excluded'), key + ': unclassified file')
    for key, row in data['objects'].items():
        need(bool(row['sources']) and set(row['sources']) <= set(data['files']), key + ': missing source mapping')
        need(bool(row['variants']), key + ': no variants')
        need(set(row['relations']) <= set(data['objects']), key + ': unknown relation')
        for path in row['sources']:
            if path in data['files']:
                need(key in data['files'][path]['objects'], key + ': mapping not reciprocal')
                need(data['files'][path]['decision'] == 'mapped', key + ': source is not mapped')
    errors.extend(rule_errors(data, rules))
    covered = coverage(data, rules)
    expected = {uid(o, v, c) for o, row in data['objects'].items() for v in row['variants'] for c in rules} - set(covered)
    if complete:
        need(expected <= set(data['units']), 'criterion/variant matrix incomplete; run plan')
    for key, row in data['units'].items():
        need(row['object'] in data['objects'], key + ': unknown object')
        need(row['criterion'] in rules, key + ': unknown criterion')
        need(key == uid(row['object'], row['variant'], row['criterion']), key + ': unstable ID')
        if row['object'] in data['objects']:
            need(row['variant'] in data['objects'][row['object']]['variants'], key + ': stale variant')
        if row['status'] in ('pass', 'fail'):
            need(all(row[x] for x in ('actor', 'method', 'expected', 'actual', 'steps', 'evidence')), key + ': unsupported result')
        if row['status'] in ('excluded', 'blocked'):
            need(bool(row['reason']) and bool(row['evidence']), key + ': unsupported exclusion/block')
        if row['status'] == 'blocked':
            need(bool(row['limitations']), key + ': missing next step/limitation')
            if complete:
                need(blocker_state(data, row) == 'documented', key + ': blocker missing or stale; reassess available execution paths')
        if complete:
            need(row['status'] in ('pass', 'fail', 'excluded'), key + ': unfinished unit')
            if row['status'] in ('pass', 'fail', 'excluded'):
                need(accepted(data, 'unit', key, row['actor']), key + ': independent unit review missing/stale')
            if row['status'] == 'fail':
                need(any(key in f['units'] and f['status'] == 'confirmed' for f in data['findings'].values()), key + ': failure has no confirmed finding')
    assigned = set()
    for key, job in data['jobs'].items():
        # Closed jobs may name units that a later applicability/equivalence rule pruned.
        known = set(data['units']) | (set(covered) if job['status'] != 'active' else set())
        need(bool(job['units']) and set(job['units']) <= known, key + ': invalid job units')
        if job['status'] == 'active':
            need(not assigned.intersection(job['units']), key + ': overlapping active jobs')
            assigned.update(job['units'])
        if complete:
            need(job['status'] != 'active', key + ': unfinished job')
    for key, row in data['findings'].items():
        need(bool(row['units']) and set(row['units']) <= set(data['units']), key + ': missing units')
        need(bool(row['evidence']) and bool(row['steps']), key + ': finding lacks primary evidence/reproduction')
        if row['status'] in ('confirmed', 'refuted'):
            need(accepted(data, 'finding', key, row['actor']), key + ': finding lacks independent validation')
        if row['status'] == 'confirmed':
            need(all(data['units'].get(u, {}).get('status') == 'fail' for u in row['units']), key + ': confirmed finding contradicts unit status')
        if complete:
            need(row['status'] != 'suspected', key + ': unresolved suspicion')
    for key, row in data['reviews'].items():
        need(bool(row['evidence']), key + ': review has no primary evidence')
        if row['scope'] in ('unit', 'finding'):
            target_table = {'unit':'units','finding':'findings'}[row['scope']]
            need(row['target'] in data[target_table], key + ': review target missing')
        if complete and row['verdict'] in ('reject', 'gap'):
            need(review_resolved(data, key), key + ': review gap not resolved')
    for key, row in data['gaps'].items():
        need(set(row['units']) <= set(data['units']), key + ': unknown gap units')
        if row['status'] == 'resolved':
            need(bool(row['evidence']) and bool(row['resolution']), key + ': gap resolution unsupported')
        if complete:
            need(row['status'] == 'resolved', key + ': open gap')
    if (complete if check_source is None else check_source):
        current, limits = scan(Path(data['repository']), exclusions=data.get('scan_exclusions', {}))
        need(not limits and {k:v['sha256'] for k,v in current.items()} == {k:v['sha256'] for k,v in data['files'].items()}, 'source baseline changed or unreadable; new run required')
    if complete:
        need(bool(data['objects']) and bool(data['units']), 'empty inventory')
        need(data['scan_complete'] and not data['scan_limits'] and not data.get('scan_exclusions'), 'source scan incomplete (including explicitly omitted paths)')
        for key in ('audience', 'tasks', 'platforms', 'states', 'entrypoints', 'runtime', 'scope', 'coordinator', 'tracker'):
            need(key in data['profile'] and bool(data['profile'][key]['evidence']), 'missing evidenced profile: ' + key)
        coordinator = data['profile'].get('coordinator', {}).get('value', '')
        need(accepted(data, 'inventory', 'all', coordinator), 'independent inventory review missing/stale')
        need(accepted(data, 'final', 'all', coordinator), 'independent final review missing/stale')
    return errors


def review_resolved(data, review_id):
    # IDs must be referenced as whole tokens: resolving R10 cannot resolve R1.
    reference = r'(?<![A-Za-z0-9_.-])' + re.escape(review_id) + r'(?![A-Za-z0-9_.-])'
    return any(g['status'] == 'resolved' and re.search(reference, g['description'])
               and g['evidence'] and g['resolution'].strip() for g in data['gaps'].values())


def publication_blockers(data, finding_id):
    """Unresolved objections that stop a finding from becoming an issue.

    An inventory review with verdict `gap` says coverage is incomplete; it does not contradict
    a finding that was confirmed on its own evidence, so it is a coverage notice instead
    (see coverage_notices). An inventory `reject` disputes the inventory itself and blocks."""
    units = set(data['findings'][finding_id]['units'])
    return [key for key, review in data['reviews'].items()
            if review['verdict'] in ('reject', 'gap')
            and not (review['scope'] == 'inventory' and review['verdict'] == 'gap')
            and (review['scope'] in ('inventory', 'final')
                 or (review['scope'] == 'finding' and review['target'] == finding_id)
                 or (review['scope'] == 'unit' and review['target'] in units))
            and not review_resolved(data, key)]


def coverage_notices(data):
    return [key for key, review in data['reviews'].items()
            if review['scope'] == 'inventory' and review['verdict'] == 'gap' and not review_resolved(data, key)]


def accepted(data, scope, target, author):
    try:
        wanted = review_digest(data, scope, target)
    except KeyError:
        return False
    return any(r['scope'] == scope and r['target'] == target and r['digest'] == wanted
               and r['actor'] != author and r['mode'] == 'independent' and r['verdict'] == 'accept'
               and r['evidence'] and r['countercheck']
               and (scope not in ('unit', 'finding') or r['outcome'] == data[{'unit':'units','finding':'findings'}[scope]][target]['status'])
               for r in data['reviews'].values())


def put(data, actor, table, key, row):
    if table not in TABLES:
        raise ValueError('unknown table')
    old = data[table].get(key)
    if old == row:
        return
    if row is None:
        # Only plan prunes, and only untouched units that a rule now covers.
        if table != 'units' or old is None or old['status'] != 'pending' or old['actor']:
            raise ValueError(key + ': only untouched pending units may be removed')
        if key not in cached_coverage(data):
            raise ValueError(key + ': unit is not covered by an applicability or equivalence rule')
        if any(j['status'] == 'active' and key in j['units'] for j in data['jobs'].values()):
            raise ValueError(key + ': unit is claimed by an active job')
        del data[table][key]
        data['history'].append(dict(actor=actor, table=table, id=key, before=copy.deepcopy(old), after=None))
        return
    if table in RULE_TABLES and row['actor'] != actor:
        raise ValueError('rule actor mismatch')
    if table == 'files' and (old is None or row['sha256'] != old['sha256']):
        raise ValueError('source manifest is immutable; new baseline requires a new run')
    if table == 'evidence' and old is not None:
        raise ValueError('evidence is immutable; use a new ID')
    if table == 'reviews' and old is not None:
        raise ValueError('reviews are immutable; use a new ID')
    if table == 'units':
        if old is None:
            if row != blank_unit(row['object'], row['variant'], row['criterion']):
                raise ValueError('units must start pending')
        else:
            if old['status'] in ('pass', 'fail', 'excluded') and row['status'] != 'running':
                raise ValueError('reopen terminal unit before changing its result')
            if any(old[x] != row[x] for x in ('object', 'variant', 'criterion')):
                raise ValueError('unit identity is immutable')
            if old['status'] != row['status'] and row['status'] not in TRANSITIONS[old['status']]:
                raise ValueError('invalid status transition')
            jobs = [(k, j) for k, j in data['jobs'].items() if j['status'] == 'active' and key in j['units']]
            if len(jobs) != 1 or jobs[0][1]['owner'] != actor or row['actor'] != actor:
                found = ', '.join(k + ' (owner ' + j['owner'] + ')' for k, j in jobs) or 'none'
                raise ValueError(key + ': unit update requires an exclusive active job owned by actor ' + repr(actor)
                                 + '; active jobs covering it: ' + found + '; unit actor: ' + repr(row['actor'])
                                 + '. Claim the job as this actor first (earlier operation or fragment), '
                                 'set the unit actor to the same ID, and close the job only after the result.')
    if table == 'jobs' and old and old['status'] == 'active' and old['owner'] != actor:
        raise ValueError('only job owner may release job; recover explicitly with original actor identity')
    if table == 'jobs' and row['owner'] != actor:
        raise ValueError('job owner must match actor')
    if table == 'reviews' and row['actor'] != actor:
        raise ValueError('review actor mismatch')
    if table == 'findings' and row['actor'] != actor:
        raise ValueError('finding actor mismatch')
    data[table][key] = row
    data['history'].append(dict(actor=actor, table=table, id=key, before=copy.deepcopy(old), after=copy.deepcopy(row)))


def apply(run, fragment):
    run = Path(run)
    lock = run / '.write-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('writer locked; inspect active coordinator before removing stale .write-lock')
    try:
        data = load(run)
        if not isinstance(fragment, dict) or set(fragment) != {'base_sequence', 'actor', 'operations'}:
            raise ValueError('malformed fragment: expected base_sequence, actor, operations; review maps need wrapping')
        if type(fragment['base_sequence']) is not int or not isinstance(fragment['operations'], list):
            raise ValueError('malformed fragment: base_sequence must be integer and operations an array')
        if fragment['base_sequence'] != data['sequence']:
            raise ValueError('stale fragment: expected sequence ' + str(data['sequence']) + '; inspect changes before rebasing')
        if not isinstance(fragment['actor'], str) or not fragment['actor'].strip():
            raise ValueError('actor required')
        for op in fragment['operations']:
            if not isinstance(op, dict) or set(op) != {'table', 'id', 'value'}:
                raise ValueError('malformed operation')
            if op['table'] == 'units' and isinstance(op['value'], dict) and op['value'].get('status') == 'blocked':
                row = op['value']
                if not row.get('blocker') or blocker_state(data, row) != 'documented':
                    raise ValueError('blocked requires a current structured blocker; unattempted work stays pending')
                if not row.get('steps') or not row.get('actual') or not row.get('evidence'):
                    raise ValueError('blocked requires attempted steps, observed obstacle and primary evidence')
            put(data, fragment['actor'], op['table'], op['id'], op['value'])
        data['sequence'] += 1
        errors = validate(data, run)
        if errors:
            raise ValueError('\n'.join(errors))
        atomic(run / 'audit.json', data, compact=True)
        return data
    finally:
        lock.rmdir()


def plan(run, actor):
    """Add missing matrix units and prune untouched pending units that a rule now covers."""
    data = load(run)
    rules = catalog()
    covered = coverage(data, rules)
    claimed = {u for j in data['jobs'].values() if j['status'] == 'active' for u in j['units']}
    ops = []
    for obj, row in data['objects'].items():
        for variant in row['variants']:
            for criterion in rules:
                key = uid(obj, variant, criterion)
                if key not in data['units'] and key not in covered:
                    ops.append(dict(table='units', id=key, value=blank_unit(obj, variant, criterion)))
    for key, row in data['units'].items():
        if key in covered and key not in claimed and row['status'] == 'pending' and not row['actor']:
            ops.append(dict(table='units', id=key, value=None))
    return apply(run, dict(base_sequence=data['sequence'], actor=actor, operations=ops))


def patch_row(run, actor, table, key, set_fields=None, add_fields=None, write_fragment=False):
    """Change selected fields of the current row; list fields in add_fields are unioned in order.

    Builds the operation from the current ledger state, so concurrent fields are kept."""
    data = load(run)
    if table not in TABLES:
        raise ValueError('unknown table')
    if key not in data[table]:
        raise ValueError(key + ': no current row in ' + table + '; create it with a full fragment')
    row = copy.deepcopy(data[table][key])
    for name, value in (set_fields or {}).items():
        if name not in row and table != 'units':
            raise ValueError('unknown field for patch: ' + name)
        row[name] = value
    for name, values in (add_fields or {}).items():
        if not isinstance(row.get(name), list) or not isinstance(values, list):
            raise ValueError('--add needs a list field and a JSON array: ' + name)
        row[name] = row[name] + [v for v in values if v not in row[name]]
    fragment = dict(base_sequence=data['sequence'], actor=actor, operations=[dict(table=table, id=key, value=row)])
    if not write_fragment:
        return apply(run, fragment)
    path = Path(run) / 'parts' / ('patch-' + str(data['sequence']) + '-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(fragment, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return path


def evidence(run, actor, key, source, kind, locator, environment):
    run, source = Path(run), Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError('evidence source must be a regular file, not a symlink')
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('evidence exceeds 32 MiB')
    if (run / 'evidence').resolve().parent != run.resolve():
        raise ValueError('unsafe evidence directory')
    content = source.read_bytes()
    if not content or len(content) > 32 * 1024 * 1024:
        raise ValueError('evidence must be nonempty and at most 32 MiB; split large traces')
    h = hashlib.sha256(content).hexdigest()
    relative = 'evidence/' + h
    dest = run / relative
    if dest.is_symlink():
        raise ValueError('unsafe evidence destination')
    if dest.exists() and filehash(dest) != h:
        raise ValueError('artifact collision')
    if not dest.exists():
        with dest.open('xb') as out:
            out.write(content)
    data = load(run)
    row = dict(file=relative, sha256=h, kind=kind, locator=locator, environment=environment, captured_by=actor)
    return apply(run, dict(base_sequence=data['sequence'], actor=actor,
                          operations=[dict(table='evidence', id=key, value=row)]))


def results(data, run):
    integrity_errors = validate(data, run, False, check_source=True)
    errors = list(dict.fromkeys(integrity_errors + validate(data, run, True, check_source=False)))
    findings = []
    for key, f in data['findings'].items():
        findings.append(dict(id=key, **{k:v for k,v in f.items() if k not in ('actor','units')},
                             criterion=','.join(sorted({data['units'][u]['criterion'] for u in f['units']})),
                             publication_blockers=publication_blockers(data, key),
                             independent_confirmation=accepted(data, 'finding', key, f['actor']),
                             independent_validated=not integrity_errors and not publication_blockers(data, key)
                             and accepted(data, 'finding', key, f['actor'])))
    rules = catalog()
    covered = coverage(data, rules)
    return dict(run_id=data['run_id'], repository=data['profile'].get('tracker',{}).get('value',data['repository']),
                target_path=data['repository'], revision=data['revision'],
                scan_exclusions=data.get('scan_exclusions', {}),
                integrity_valid=not integrity_errors, integrity_errors=integrity_errors,
                coverage_notices=coverage_notices(data),
                covered_units={kind: sum(c[0] == kind for c in covered.values()) for kind in ('not-applicable', 'equivalent')},
                applicability=data['applicability'], equivalences=data['equivalences'],
                status='FORMALLY_COMPLETE' if not errors else 'INCOMPLETE',
                disclaimer='Formal consistency is not proof of semantic completeness or WCAG conformance.',
                errors=errors, counts={s:sum(u['status']==s for u in data['units'].values()) for s in TRANSITIONS},
                findings=findings, units=data['units'], gaps=data['gaps'], reviews=data['reviews'],
                evidence=data['evidence'], profile=data['profile'], work=next_work(data),
                snapshot=review_digest(data,'final','all'))


ISSUE_EXPORT_KEYS = ('run_id', 'repository', 'revision', 'status', 'integrity_valid', 'integrity_errors',
                     'coverage_notices', 'findings')


def issue_export(result):
    """Small export for issues.py: a full result.json of a large audit exceeds its input bound."""
    return {k: result[k] for k in ISSUE_EXPORT_KEYS}


def report(result):
    lines = ['# UI/UX audit', '', result['status'], '', result['disclaimer'], '',
             'Baseline: ' + result['revision'], '', 'Coverage: ' + json.dumps(result['counts']), '',
             '## Limitations and unfinished work', '']
    if result.get('work'):
        work = result['work']
        lines += ['Recorded work is not total product coverage. Pending means unexamined, not technically blocked.', '',
                  'Blocker evidence: ' + json.dumps(work['blockers']), '',
                  'Next actions: ' + '; '.join(work['actions']), '']
    lines += ['- ' + x.replace('\n',' ') for x in result['errors']] or ['None recorded.']
    if result.get('coverage_notices'):
        lines += ['', 'Open inventory coverage gaps (confirmed findings still publish): '
                  + ', '.join(result['coverage_notices'])]
    if result.get('applicability') or result.get('equivalences'):
        lines += ['', '## Matrix rules (reviewed with the inventory)', '',
                  'Covered units: ' + json.dumps(result['covered_units']), '']
        for key, rule in result['applicability'].items():
            scope = ', '.join(rule['kinds'] + rule['objects']) or 'all objects'
            lines.append('- ' + key + ' (not applicable): ' + scope + ' × ' + ', '.join(rule['criteria'] + ['dimension ' + d for d in rule['dimensions']])
                         + ' — ' + rule['reason'].replace('\n', ' '))
        for key, rule in result['equivalences'].items():
            lines.append('- ' + key + ' (equivalent): ' + rule['object'] + ' ' + ', '.join(rule['variants']) + ' → ' + rule['representative']
                         + ' — ' + rule['reason'].replace('\n', ' '))
    if result.get('scan_exclusions'):
        lines += ['', '## Explicitly omitted source paths (unexamined)', '']
        lines += ['- ' + path.replace('\n', ' ') + ': ' + reason.replace('\n', ' ') for path, reason in result['scan_exclusions'].items()]
    lines += ['', '## Findings', '']
    for f in result['findings']:
        lines += ['### ' + f['id'] + ': ' + f['title'], '', f['status'] + ' / ' + f['priority'], '',
                  'Impact: ' + f['impact'], '', 'Expected: ' + f['expected'], '', 'Observed: ' + f['actual'], '',
                  'Reproduce: ' + ' → '.join(f['steps']), '', 'Recommendation: ' + f['recommendation'], '',
                  'Evidence: ' + ', '.join(f['evidence']), '']
    lines += ['## Quality checklist', '', '| Unit | Criterion | Variant | Status | Evidence | Limitation |',
              '| --- | --- | --- | --- | --- | --- |']
    for key, u in result['units'].items():
        cells=[key,u['criterion'],u['variant'],u['status'],', '.join(u['evidence']),u['reason'] or '; '.join(u['limitations'])]
        lines.append('| ' + ' | '.join(x.replace('|','\\|').replace('\n',' ') for x in cells) + ' |')
    return '\n'.join(lines) + '\n'


def compact(result):
    groups = {}
    for message in result['errors']:
        prefix, sep, detail = message.partition(': ')
        cause = detail if sep and (prefix in result['units'] or prefix in result['reviews'] or prefix in result['gaps']) else message
        group = groups.setdefault(cause, {'count': 0, 'examples': []})
        group['count'] += 1
        if len(group['examples']) < 3:
            group['examples'].append(message)
    return dict(status=result['status'], counts=result['counts'], error_count=len(result['errors']),
                error_groups=groups, scan_exclusions=result['scan_exclusions'])


def resume(data, obj=None, status=None, limit=20):
    if limit < 1 or limit > 100:
        raise ValueError('resume limit must be between 1 and 100')
    if obj is not None and obj not in data['objects']:
        raise ValueError('unknown object: ' + obj)
    rows = [(k, u) for k, u in data['units'].items()
            if (obj is None or u['object'] == obj) and
            (u['status'] == status if status else u['status'] in ('pending', 'running', 'blocked'))]
    return dict(sequence=data['sequence'], matching=len(rows), remaining=max(0, len(rows)-limit),
                units=[dict(id=k, **u) for k, u in rows[:limit]],
                jobs={k: v for k, v in data['jobs'].items() if any(u in {key for key, _ in rows[:limit]} for u in v['units'])})


def next_work(data, limit=12):
    """Read-only queue: bounded packages, every object/variant represented before overflow."""
    if not 1 <= limit <= 100:
        raise ValueError('next limit must be between 1 and 100')
    blockers = {state: 0 for state in ('documented', 'stale', 'unsubstantiated')}
    packages = {}
    review_units = []
    for key, row in data['units'].items():
        state = blocker_state(data, row)
        if state:
            blockers[state] += 1
        if row['status'] in ('pass', 'fail', 'excluded'):
            if not accepted(data, 'unit', key, row['actor']):
                review_units.append(key)
            continue
        action = 'reassess-blocker' if state in ('stale', 'unsubstantiated') else 'retry-when-ready' if state else 'execute'
        group = (row['object'], row['variant'], action)
        packages.setdefault(group, []).append(key)
    actions = []
    unclassified = sum(f['decision'] not in ('mapped', 'excluded') for f in data['files'].values())
    if not data['scan_complete'] or data['scan_limits'] or data.get('scan_exclusions'):
        actions.append('Finish source discovery; omitted paths are still in scope')
    if unclassified or not data['objects']:
        actions.append('Reconcile source, product tasks, runtime surfaces and platform/state inventory')
    if blockers['stale'] or blockers['unsubstantiated']:
        actions.append('Reassess obsolete/unsupported blockers against current host and alternative paths')
    if any(k[2] == 'execute' for k in packages):
        actions.append('Continue pending/running tests; a report or successful setup is not a stop condition')
    if blockers['documented']:
        actions.append('Check documented retry conditions; continue all unaffected methods')
    if review_units:
        actions.append('Dispatch fresh evidence-first review of terminal units')
    coordinator = data['profile'].get('coordinator', {}).get('value', '')
    if not accepted(data, 'inventory', 'all', coordinator):
        actions.append('Obtain current independent semantic inventory review')
    if any(f['status'] == 'suspected' for f in data['findings'].values()):
        actions.append('Countercheck unresolved findings with original and falsifying paths')
    if not accepted(data, 'final', 'all', coordinator):
        actions.append('Resolve remaining gaps, then obtain final independent review')
    actions.append('Prepare eligible issue drafts; inspect outbox and verify publication receipts separately')
    order = {'execute': 0, 'reassess-blocker': 1, 'retry-when-ready': 2}
    ordered = sorted(packages, key=lambda k: (order[k[2]], k[0], k[1]))
    return dict(sequence=data['sequence'], context_digest=context_digest(data), blockers=blockers,
                unclassified_files=unclassified, actions=actions,
                package_count=len(packages), packages=[dict(object=k[0], variant=k[1], action=k[2],
                units=packages[k][:limit], remaining=max(0, len(packages[k])-limit)) for k in ordered],
                review_units=review_units[:limit], review_remaining=max(0, len(review_units)-limit),
                active_jobs={k:v for k,v in data['jobs'].items() if v['status']=='active'})


def wrap_reviews(run, draft, actor):
    """Preserve reviewer digests; never restamp stale content or overwrite draft files."""
    data = load(run)
    if not isinstance(draft, dict) or set(draft) != {'reviews'} or not isinstance(draft['reviews'], dict) or not draft['reviews']:
        raise ValueError('review draft requires a nonempty reviews map')
    schema = read(ROOT / 'schemas/run.schema.json')['properties']['reviews']['additionalProperties']
    operations = []
    for key, row in draft['reviews'].items():
        schema_check(row, schema)
        if row['actor'] != actor:
            raise ValueError('review actor mismatch: ' + key)
        if row['digest'] != review_digest(data, row['scope'], row['target']):
            raise ValueError('stale review digest: ' + key + '; reviewer must inspect current primary evidence')
        operations.append(dict(table='reviews', id=key, value=row))
    fragment = dict(base_sequence=data['sequence'], actor=actor, operations=operations)
    path = Path(run) / 'parts' / ('reviews-' + str(data['sequence']) + '-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(fragment, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('run'); init.add_argument('repository'); init.add_argument('--revision', required=True); init.add_argument('--exclusions', help='JSON path-to-reason map; run remains incomplete')
    app = sub.add_parser('apply'); app.add_argument('run'); app.add_argument('fragment')
    pl = sub.add_parser('plan'); pl.add_argument('run'); pl.add_argument('--actor', required=True)
    pa = sub.add_parser('patch', help='change fields of one current row without rewriting it by hand')
    pa.add_argument('run'); pa.add_argument('--actor', required=True); pa.add_argument('--table', required=True, choices=TABLES)
    pa.add_argument('--id', required=True)
    pa.add_argument('--set', dest='set_fields', help='JSON object; replaces these fields')
    pa.add_argument('--add', dest='add_fields', help='JSON object of arrays; unions them into list fields')
    pa.add_argument('--append-variant', help='objects only: add one variant, then run plan')
    pa.add_argument('--fragment', action='store_true', help='write the fragment to parts/ instead of applying it')
    ev = sub.add_parser('evidence'); ev.add_argument('run'); ev.add_argument('source'); ev.add_argument('--id', required=True); ev.add_argument('--actor', required=True)
    ev.add_argument('--kind', required=True); ev.add_argument('--locator', required=True); ev.add_argument('--environment', required=True)
    wrap = sub.add_parser('wrap-reviews'); wrap.add_argument('run'); wrap.add_argument('draft'); wrap.add_argument('--actor', required=True)
    res = sub.add_parser('resume'); res.add_argument('run'); res.add_argument('--object'); res.add_argument('--status', choices=list(TRANSITIONS)); res.add_argument('--limit', type=int, default=20)
    nxt = sub.add_parser('next'); nxt.add_argument('run'); nxt.add_argument('--limit', type=int, default=12)
    for command in ('check', 'report', 'digest', 'drift'):
        cmd = sub.add_parser(command); cmd.add_argument('run')
        if command == 'digest':
            cmd.add_argument('--scope', choices=['inventory','final','unit','finding'], default='final')
            cmd.add_argument('--target', default='all')
        if command in ('check', 'report'):
            cmd.add_argument('--verbose', action='store_true')
    args = p.parse_args()
    try:
        if args.command == 'init': initialize(args.run, args.repository, args.revision, read(args.exclusions) if args.exclusions else None)
        elif args.command == 'apply': apply(args.run, read(args.fragment))
        elif args.command == 'wrap-reviews': print(wrap_reviews(args.run, read(args.draft), args.actor))
        elif args.command == 'plan': plan(args.run, args.actor)
        elif args.command == 'patch':
            add = json.loads(args.add_fields) if args.add_fields else {}
            if args.append_variant:
                if args.table != 'objects':
                    raise ValueError('--append-variant applies to objects only')
                add.setdefault('variants', []).append(args.append_variant)
            change = json.loads(args.set_fields) if args.set_fields else {}
            if not isinstance(change, dict) or not isinstance(add, dict) or not (change or add):
                raise ValueError('patch needs --set, --add or --append-variant with a JSON object')
            out = patch_row(args.run, args.actor, args.table, args.id, change, add, args.fragment)
            if args.fragment: print(out)
        elif args.command == 'evidence': evidence(args.run,args.actor,args.id,args.source,args.kind,args.locator,args.environment)
        else:
            data = load(args.run)
            if args.command == 'next':
                print(json.dumps(next_work(data, args.limit), ensure_ascii=False, indent=2)); return 0
            if args.command == 'digest':
                if args.scope in ('inventory', 'final') and args.target != 'all':
                    raise ValueError('inventory/final target must be all')
                print(review_digest(data,args.scope,args.target)); return 0
            if args.command == 'resume':
                print(json.dumps(resume(data,args.object,args.status,args.limit), ensure_ascii=False, indent=2)); return 0
            if args.command == 'drift':
                files, limits = scan(Path(data['repository']), exclusions=data.get('scan_exclusions', {}))
                changed = sorted(k for k in set(files)|set(data['files']) if files.get(k,{}).get('sha256') != data['files'].get(k,{}).get('sha256'))
                print(json.dumps(dict(changed=changed, limits=limits))); return int(bool(changed or limits))
            result = results(data, args.run)
            if args.command == 'report':
                atomic(Path(args.run) / 'result.json', result)
                atomic(Path(args.run) / 'issue-export.json', issue_export(result))
                (Path(args.run) / 'report.md').write_text(report(result), encoding='utf-8')
            atomic(Path(args.run) / 'validation.json', dict(status=result['status'], counts=result['counts'], errors=result['errors']))
            output = dict(status=result['status'], counts=result['counts'], errors=result['errors']) if args.verbose else compact(result)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return int(bool(result['errors']))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('audit: ' + str(exc), file=sys.stderr); return 2

if __name__ == '__main__':
    sys.exit(main())
