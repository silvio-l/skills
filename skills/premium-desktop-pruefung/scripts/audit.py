#!/usr/bin/env python3
"""Portable UI/UX ledger. Python >=3.10, standard library; never executes target code."""
import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('files', 'objects', 'units', 'evidence', 'findings', 'jobs', 'reviews', 'gaps', 'profile',
          'applicability', 'equivalences')
RULE_TABLES = ('applicability', 'equivalences')  # optional in older ledgers; bound to the inventory digest
LAZY_TABLES = ('units', 'files', 'evidence', 'reviews')  # may reach 10^5 rows; apply reads them row by row
REF_SEP = '\x1f'
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


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def row_ref(table, row):
    """Indexed lookup key: the units of an object, the reviews of one target."""
    if row is None:
        return None
    if table == 'units':
        return row['object']
    if table == 'reviews':
        return row['scope'] + REF_SEP + row['target']
    return None


LEDGER_SQL = '''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE rows(tbl TEXT NOT NULL, id TEXT NOT NULL, ref TEXT, body TEXT NOT NULL, UNIQUE(tbl, id));
CREATE INDEX rows_ref ON rows(tbl, ref);
CREATE TABLE history(seq INTEGER PRIMARY KEY, event TEXT NOT NULL);
CREATE TABLE marks(sequence INTEGER PRIMARY KEY, history_start INTEGER NOT NULL);
'''
# marks: the journal position where each sequence's events start, so a stale fragment can be
# rebased when no row it writes changed since its base. Ledgers created before it gain the
# table on their next write; sequences without a mark cannot be rebased.
MARKS_SQL = 'CREATE TABLE IF NOT EXISTS marks(sequence INTEGER PRIMARY KEY, history_start INTEGER NOT NULL)'



def connect(run, readonly=False):
    path = (Path(run) / 'audit.db').resolve()
    if readonly:
        con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None)
    else:
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute('PRAGMA synchronous=FULL')
        con.execute(MARKS_SQL)
    return con


def create_ledger(run, data):
    """Write a complete ledger atomically (init, migration): build beside it, then rename."""
    run = Path(run)
    tmp = run / ('.ux-' + uuid.uuid4().hex + '.db')
    try:
        con = sqlite3.connect(str(tmp), isolation_level=None)
        try:
            con.executescript(LEDGER_SQL)
            con.execute('BEGIN')
            con.executemany('INSERT INTO meta VALUES (?, ?)',
                            [(k, canonical(v)) for k, v in data.items() if k not in TABLES and k != 'history'])
            con.executemany('INSERT INTO rows(tbl, id, ref, body) VALUES (?, ?, ?, ?)',
                            [(t, k, row_ref(t, v), canonical(v)) for t in TABLES for k, v in data[t].items()])
            con.executemany('INSERT INTO history(event) VALUES (?)', [(canonical(e),) for e in data['history']])
            con.execute('COMMIT')
        finally:
            con.close()
        with tmp.open('rb+') as stream:
            os.fsync(stream.fileno())
        os.replace(tmp, run / 'audit.db')
    finally:
        if tmp.exists():
            tmp.unlink()


def load(run):
    """Read the whole ledger into memory (check, report, queue, review digests).

    Runs created before the SQLite ledger still read from audit.json until their next write
    migrates them; they also gain the rule tables, which older ledgers lack."""
    run = Path(run)
    if not (run / 'audit.db').exists():
        data = read(run / 'audit.json')
        for table in TABLES:
            data.setdefault(table, {})
        return data
    con = connect(run, readonly=True)
    try:
        data = {k: json.loads(v) for k, v in con.execute('SELECT key, value FROM meta')}
        for table in TABLES:
            data[table] = {}
        for table, key, body in con.execute('SELECT tbl, id, body FROM rows ORDER BY rowid'):
            data[table][key] = json.loads(body)
        data['history'] = [json.loads(e) for (e,) in con.execute('SELECT event FROM history ORDER BY seq')]
    finally:
        con.close()
    return data


class LazyTable:
    """A large table read on demand during apply; changes stay in memory until commit.

    Full iteration is refused on purpose: a code path that needs every row belongs to
    load()/validate(), and a silent full scan here would bring back the slow apply."""

    def __init__(self, con, name):
        self.con, self.name, self.cache, self.written = con, name, {}, set()

    def _fetch(self, keys):
        keys = [k for k in dict.fromkeys(keys) if k not in self.cache]
        for start in range(0, len(keys), 500):
            part = keys[start:start + 500]
            found = dict(self.con.execute('SELECT id, body FROM rows WHERE tbl = ? AND id IN (%s)'
                                          % ','.join('?' * len(part)), (self.name, *part)))
            for key in part:
                self.cache[key] = json.loads(found[key]) if key in found else None

    def get(self, key, default=None):
        self._fetch([key])
        value = self.cache[key]
        return default if value is None else value

    def __getitem__(self, key):
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __contains__(self, key):
        return self.get(key) is not None

    def __setitem__(self, key, value):
        self.cache[key] = value
        self.written.add(key)

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.cache[key] = None
        self.written.add(key)

    def present(self, keys):
        keys = list(keys)
        self._fetch(keys)
        return {k for k in keys if self.cache[k] is not None}

    def by_ref(self, ref):
        rows = {}
        for key, body in self.con.execute('SELECT id, body FROM rows WHERE tbl = ? AND ref = ? ORDER BY rowid',
                                          (self.name, ref)):
            if key not in self.written:
                rows[key] = self.cache.setdefault(key, json.loads(body))
        for key in self.written:
            if self.cache[key] is not None and row_ref(self.name, self.cache[key]) == ref:
                rows[key] = self.cache[key]
        return list(rows.items())

    def _refuse(self, *args):
        raise TypeError('full scan of lazy table ' + self.name + ' during apply; use load()')

    __iter__ = __len__ = keys = values = items = _refuse


def open_view(run):
    """Small tables in memory, large ones lazy, history = only the events of this write."""
    con = connect(run)
    data = {k: json.loads(v) for k, v in con.execute('SELECT key, value FROM meta')}
    for table in TABLES:
        data[table] = LazyTable(con, table) if table in LAZY_TABLES else {}
    marks = ','.join('?' * len(LAZY_TABLES))
    for table, key, body in con.execute('SELECT tbl, id, body FROM rows WHERE tbl NOT IN (%s) ORDER BY rowid'
                                        % marks, LAZY_TABLES):
        data[table][key] = json.loads(body)
    data['history'] = []
    return con, data


def commit(con, data, base_sequence):
    """One SQLite transaction: final row states, appended journal events, new sequence."""
    con.execute('BEGIN IMMEDIATE')
    try:
        (stored,) = con.execute("SELECT value FROM meta WHERE key = 'sequence'").fetchone()
        if json.loads(stored) != base_sequence:
            raise ValueError('ledger changed during apply; retry with the current sequence')
        final = {}
        for event in data['history']:
            final[(event['table'], event['id'])] = event['after']
        for (table, key), row in final.items():
            if row is None:
                con.execute('DELETE FROM rows WHERE tbl = ? AND id = ?', (table, key))
            else:
                con.execute('INSERT INTO rows(tbl, id, ref, body) VALUES (?, ?, ?, ?) ON CONFLICT(tbl, id) '
                            'DO UPDATE SET ref = excluded.ref, body = excluded.body',
                            (table, key, row_ref(table, row), canonical(row)))
        mark(con, data['sequence'])
        con.executemany('INSERT INTO history(event) VALUES (?)', [(canonical(e),) for e in data['history']])
        con.execute("UPDATE meta SET value = ? WHERE key = 'sequence'", (canonical(data['sequence']),))
        con.execute('COMMIT')
    except BaseException:
        con.execute('ROLLBACK')
        raise


def mark(con, sequence):
    (start,) = con.execute('SELECT COALESCE(MAX(seq), 0) FROM history').fetchone()
    con.execute('INSERT OR REPLACE INTO marks(sequence, history_start) VALUES (?, ?)', (sequence, start))


def rebase_conflicts(con, base, rows):
    """Rows of a fragment written by others since base; None if the journal cannot tell."""
    found = con.execute('SELECT history_start FROM marks WHERE sequence = ?', (base + 1,)).fetchone()
    if found is None:
        return None
    changed = set()
    for (event,) in con.execute('SELECT event FROM history WHERE seq > ?', found):
        event = json.loads(event)
        changed.add((event['table'], event['id']))
    return sorted(changed & rows)


@contextmanager
def write_lock(run):
    lock = Path(run) / '.write-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('writer locked; inspect active coordinator before removing stale .write-lock')
    try:
        yield
    finally:
        lock.rmdir()


def migrate(run):
    """Convert a JSON ledger (audit.json) into audit.db once; the JSON stays as audit.json.migrated."""
    run = Path(run)
    if (run / 'audit.db').exists() or not (run / 'audit.json').exists():
        return False
    data = load(run)
    errors = validate(data, run)
    if errors:
        raise ValueError('cannot migrate an invalid ledger:\n' + '\n'.join(errors))
    create_ledger(run, data)
    os.replace(run / 'audit.json', run / 'audit.json.migrated')
    return True


def ensure_ledger(run):
    run = Path(run)
    if not (run / 'audit.db').exists():
        if not (run / 'audit.json').exists():
            raise ValueError('no ledger in ' + str(run) + '; run init first')
        with write_lock(run):
            migrate(run)


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
            # json.dumps uses the C encoder; json.dump streams through the slow Python one
            stream.write(canonical(data) if compact else json.dumps(data, indent=2, ensure_ascii=False))
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
        raise ValueError(at + ': invalid enum ' + json.dumps(value) + '; allowed: ' + ', '.join(map(str, schema['enum'])))
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
    keys = ('revision', 'catalog_hash', 'files', 'objects', 'profile', 'scan_complete', 'scan_limits', 'scan_exclusions',
            'scan_policy', 'scan_ignored', 'scan_includes', 'scan_policy_adopted')
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
            variants = [v for v in row['variants'] if not rule.get('variants') or v in rule['variants']]
            for criterion in rules:
                if rule_matches(rule, criterion, rules):
                    for variant in variants:
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
                known = {v for o in data['objects'].values() for v in o['variants']}
                if set(rule.get('variants', [])) - known:
                    errors.append(key + ': unknown variant in rule')
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
    return row_digest(scope, data[table][target])


def row_digest(scope, row):
    row = dict(row)
    if scope == 'finding':
        # Validation precedes promotion without changing the reviewed content. duplicate_of stays
        # in the digest: an independent review with outcome duplicate vouches for that primary.
        row.pop('status')
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


def scan_policy(data):
    """None for runs created before the relevance policy, so their baseline stays comparable."""
    return dict(includes=data.get('scan_includes', [])) if data.get('scan_policy') else None


def rescan(data):
    found = scan(Path(data['repository']), exclusions=data.get('scan_exclusions', {}), policy=scan_policy(data))
    return found[0], found[1]


def under_any(path, directories):
    return any(path == d or path.startswith(d + '/') for d in directories)


def baseline_files(data):
    """The ledger rows a rescan must reproduce. Rows under scan_ignored exist only in runs that
    adopted the policy after init; they stay in the journal but are no longer compared."""
    ignored = data.get('scan_ignored', {})
    if not ignored:
        return data['files']
    return {k: v for k, v in data['files'].items() if not under_any(k, ignored)}


def adopt_scan_policy(run, includes=()):
    """Switch a run created before the relevance policy to it, without rewriting its journal.

    Allowed only when every row in the newly skipped directories is an excluded file and the
    policy scan reproduces the remaining baseline exactly. The inventory digest changes, so the
    inventory review must be repeated; an outstanding fragment that writes a changed row is refused as stale."""
    run = Path(run)
    with write_lock(run):
        ensure_ledger(run)
        data = load(run)
        if data.get('scan_policy'):
            raise ValueError('run already uses the scan relevance policy')
        includes = sorted(checked_exclusions({p: 'include' for p in includes}))
        files, limits, ignored = scan(Path(data['repository']), exclusions=data.get('scan_exclusions', {}),
                                      policy=dict(includes=includes))
        if limits or data['scan_limits']:
            raise ValueError('scan limits present; adoption needs a limit-free baseline')
        dropped = {k: v for k, v in data['files'].items() if under_any(k, ignored)}
        kept_mapped = sorted({d for k, v in dropped.items() if v['decision'] != 'excluded'
                              for d in ignored if under_any(k, [d])})
        if kept_mapped:
            raise ValueError('skipped directories hold mapped or unclassified files; rerun with --include for: '
                             + ', '.join(kept_mapped))
        kept = {k: v['sha256'] for k, v in data['files'].items() if k not in dropped}
        current = {k: v['sha256'] for k, v in files.items()}
        if current != kept:
            diff = sorted(k for k in set(current) | set(kept) if current.get(k) != kept.get(k))
            raise ValueError('source differs from the baseline outside the skipped directories (' + str(len(diff))
                             + ' paths, e.g. ' + ', '.join(diff[:5]) + '); new run required')
        meta = dict(scan_policy=1, scan_ignored=ignored, sequence=data['sequence'] + 1,
                    scan_policy_adopted=dict(at_sequence=data['sequence'], rows_no_longer_compared=len(dropped)))
        if includes:
            meta['scan_includes'] = includes
        con = connect(run)
        try:
            con.execute('BEGIN IMMEDIATE')
            try:
                (stored,) = con.execute("SELECT value FROM meta WHERE key = 'sequence'").fetchone()
                if json.loads(stored) != data['sequence']:
                    raise ValueError('ledger changed during adoption; retry')
                con.executemany('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                                [(k, canonical(v)) for k, v in meta.items()])
                mark(con, meta['sequence'])
                con.execute('COMMIT')
            except BaseException:
                con.execute('ROLLBACK')
                raise
        finally:
            con.close()
        return dict(sequence=meta['sequence'], rows_no_longer_compared=len(dropped), not_inventoried=ignored,
                    next='repeat the inventory review: its digest now binds the scan policy')


def scan(repo, max_files=50000, max_bytes=16 * 1024 * 1024, exclusions=None, checkpoint=None, policy=None):
    # Explicit sibling loading also supports importlib-based test/adapter callers.
    import importlib.util
    spec = importlib.util.spec_from_file_location('premium_source_scan', ROOT / 'scripts/source_scan.py')
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    return scanner.scan_tree(repo, max_files, max_bytes,
                             checked_exclusions(exclusions or {}), checkpoint, policy=policy)


def initialize(run, repo, revision, exclusions=None, includes=None, scan_all=False):
    run, repo = Path(run).resolve(), Path(repo).resolve()
    if run == repo or repo in run.parents:
        raise ValueError('audit workspace must be outside target repository')
    if not repo.is_dir():
        raise ValueError('repository directory missing')
    run.mkdir(parents=True, exist_ok=True)
    if (run / 'audit.json').exists() or (run / 'audit.db').exists():
        raise ValueError('run already exists; resume it')
    exclusions = checked_exclusions(exclusions or {})
    includes = sorted(checked_exclusions({p: 'include' for p in includes or []}))
    if scan_all:
        files, limits = scan(repo, exclusions=exclusions, checkpoint=run / 'scan-state.json')
    else:
        files, limits, ignored = scan(repo, exclusions=exclusions, checkpoint=run / 'scan-state.json',
                                      policy=dict(includes=includes))
    data = dict(version=1, run_id=str(uuid.uuid4()), repository=str(repo), revision=revision,
                catalog_hash=digest(catalog()), sequence=0, scan_complete=not limits,
                scan_limits=limits, **{t: {} for t in TABLES}, history=[])
    if not scan_all:
        # Not product source: listed for the inventory review, not an incomplete scan.
        data.update(scan_policy=1, scan_ignored=ignored)
        if includes:
            data['scan_includes'] = includes
    if exclusions:
        data['scan_exclusions'] = exclusions
        data['scan_complete'] = False
    data['files'] = files
    (run / 'evidence').mkdir(exist_ok=True)
    (run / 'parts').mkdir(exist_ok=True)
    create_ledger(run, data)
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
            for eid in evidence_refs(row):
                need(eid in data['evidence'], key + ': unknown evidence ' + eid)
    for key, row in data['evidence'].items():
        errors.extend(evidence_errors(run, key, row))
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
    index = review_index(data)
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
            need(bool(row['reason']) and bool(row['evidence']), key + ': unsupported exclusion/block (needs reason and evidence)')
        if row['status'] == 'blocked':
            need(bool(row['limitations']), key + ': missing next step/limitation (blocked needs limitations: what stays untested)')
            if complete:
                need(blocker_state(data, row) == 'documented', key + ': blocker missing or stale; reassess available execution paths')
        if complete:
            need(row['status'] in ('pass', 'fail', 'excluded'), key + ': unfinished unit')
            if row['status'] in ('pass', 'fail', 'excluded'):
                need(accepted(data, 'unit', key, row['actor'], index), key + ': independent unit review missing/stale')
            if row['status'] == 'fail':
                need(covering_finding(data, key), key + ': failure has no confirmed finding (list the unit in a finding\'s units)')
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
        errors.extend(finding_errors(data, key, row, index))
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
        current, limits = rescan(data)
        base = baseline_files(data)
        changed = sorted(k for k in set(current) | set(base) if current.get(k, {}).get('sha256') != base.get(k, {}).get('sha256'))
        need(not limits and not changed, 'source baseline changed or unreadable; new run required'
             + ((' (changed: ' + ', '.join(changed[:5]) + (', ...' if len(changed) > 5 else '') + ')') if changed else '')
             + ((' (unreadable: ' + ', '.join(sorted(limits)[:5]) + ')') if limits else ''))
    if complete:
        need(bool(data['objects']) and bool(data['units']), 'empty inventory')
        need(data['scan_complete'] and not data['scan_limits'] and not data.get('scan_exclusions'), 'source scan incomplete (including explicitly omitted paths)')
        for key in ('audience', 'tasks', 'platforms', 'states', 'entrypoints', 'runtime', 'scope', 'coordinator', 'tracker'):
            need(key in data['profile'] and bool(data['profile'][key]['evidence']), 'missing evidenced profile: ' + key)
        coordinator = data['profile'].get('coordinator', {}).get('value', '')
        need(accepted(data, 'inventory', 'all', coordinator), 'independent inventory review missing/stale')
        need(accepted(data, 'final', 'all', coordinator), 'independent final review missing/stale')
    return errors


def validate_changes(data, run, events):
    """The checks of validate() for one write, limited to the rows it touched and their dependents.

    Same rules as validate(complete=False) for those rows; it assumes the stored ledger was
    valid. Untouched evidence files and the journal replay are verified by check and report,
    which always run the full validate()."""
    schema = read(ROOT / 'schemas/run.schema.json')
    errors = []
    def need(ok, message):
        if not ok:
            errors.append(message)
    rules = catalog()
    need(data['catalog_hash'] == digest(rules), 'catalog changed; start a new run')
    touched = {t: {} for t in TABLES}
    for event in events:
        touched[event['table']].setdefault(event['id'], event['before'])
    current = {t: {k: data[t].get(k) for k in keys} for t, keys in touched.items()}
    for table, rows in current.items():
        for key, row in rows.items():
            need(key.strip(), 'empty ID in ' + table)
            if row is not None:
                schema_check(row, schema['properties'][table]['additionalProperties'], '$.' + table + '.' + key)
    deleted_units = {k for k, row in current['units'].items() if row is None}
    for name in ('objects', 'units', 'findings', 'reviews', 'gaps', 'profile'):
        rows = [(k, r) for k, r in current[name].items() if r is not None]
        known = data['evidence'].present({e for _, r in rows for e in evidence_refs(r)})
        for key, row in rows:
            for eid in evidence_refs(row):
                need(eid in known, key + ': unknown evidence ' + eid)
    for key, row in current['evidence'].items():
        errors.extend(evidence_errors(run, key, row))
    # Files and objects reference each other; recheck both sides of every changed mapping.
    file_keys, object_keys = set(touched['files']), set(touched['objects'])
    for key, before in touched['objects'].items():
        file_keys.update((before or {}).get('sources', []), data['objects'][key]['sources'])
    for key, before in touched['files'].items():
        object_keys.update((before or {}).get('objects', []), data['files'][key]['objects'])
    data['files'].present(file_keys | {p for o in object_keys if o in data['objects'] for p in data['objects'][o]['sources']})
    for key in sorted(file_keys):
        row = data['files'].get(key)
        if row is None:
            continue
        need(set(row['objects']) <= set(data['objects']), key + ': unknown object mapping')
        for obj in row['objects']:
            if obj in data['objects']:
                need(key in data['objects'][obj]['sources'], key + ': mapping not reciprocal')
        need(not row['objects'] or row['decision'] == 'mapped', key + ': object mapping requires mapped decision')
        if row['decision'] == 'mapped':
            need(bool(row['objects']), key + ': mapped without objects')
        if row['decision'] in ('blocked', 'excluded'):
            need(bool(row['reason'].strip()), key + ': missing exclusion/limitation reason')
    for key in sorted(object_keys):
        row = data['objects'].get(key)
        if row is None:
            continue
        need(bool(row['sources']) and all(p in data['files'] for p in row['sources']), key + ': missing source mapping')
        need(bool(row['variants']), key + ': no variants')
        need(set(row['relations']) <= set(data['objects']), key + ': unknown relation')
        for path in row['sources']:
            if path in data['files']:
                need(key in data['files'][path]['objects'], key + ': mapping not reciprocal')
                need(data['files'][path]['decision'] == 'mapped', key + ': source is not mapped')
    rules_changed = any(touched[t] for t in RULE_TABLES + ('objects',))
    if rules_changed:
        errors.extend(rule_errors(data, rules))
    units = {k: r for k, r in current['units'].items() if r is not None}
    for obj in touched['objects']:
        units.update(data['units'].by_ref(obj))  # a removed variant makes the object's units stale
    for key, row in units.items():
        need(row['object'] in data['objects'], key + ': unknown object')
        need(row['criterion'] in rules, key + ': unknown criterion')
        need(key == uid(row['object'], row['variant'], row['criterion']), key + ': unstable ID')
        if row['object'] in data['objects']:
            need(row['variant'] in data['objects'][row['object']]['variants'], key + ': stale variant')
        if row['status'] in ('pass', 'fail'):
            need(all(row[x] for x in ('actor', 'method', 'expected', 'actual', 'steps', 'evidence')), key + ': unsupported result')
        if row['status'] in ('excluded', 'blocked'):
            need(bool(row['reason']) and bool(row['evidence']), key + ': unsupported exclusion/block (needs reason and evidence)')
        if row['status'] == 'blocked':
            need(bool(row['limitations']), key + ': missing next step/limitation (blocked needs limitations: what stays untested)')
    jobs = set(data['jobs']) if deleted_units or rules_changed else set(touched['jobs'])
    existing = data['units'].present({u for k in jobs for u in data['jobs'][k]['units']})
    covered = None
    assigned = set()
    for key, job in data['jobs'].items():
        if job['status'] == 'active':
            need(not assigned.intersection(job['units']), key + ': overlapping active jobs')
            assigned.update(job['units'])
        if key in jobs:
            missing = set(job['units']) - existing
            if missing and job['status'] != 'active':  # closed jobs may name units a rule pruned
                covered = set(coverage(data, rules)) if covered is None else covered
                missing -= covered
            need(bool(job['units']) and not missing, key + ': invalid job units')
    changed_units = set(touched['units'])
    findings = {k for k, f in data['findings'].items() if k in touched['findings']
                or changed_units.intersection(f['units']) or f.get('duplicate_of') in touched['findings']}
    for key in sorted(findings):
        row = data['findings'][key]
        errors.extend(finding_errors(data, key, row, units_present=data['units'].present(row['units'])))
    reviews = {k: r for k, r in current['reviews'].items() if r is not None}
    for unit in deleted_units:
        reviews.update(data['reviews'].by_ref('unit' + REF_SEP + unit))
    for key, row in reviews.items():
        need(bool(row['evidence']), key + ': review has no primary evidence')
        if row['scope'] in ('unit', 'finding'):
            target_table = {'unit': 'units', 'finding': 'findings'}[row['scope']]
            need(row['target'] in data[target_table], key + ': review target missing')
    gaps = set(data['gaps']) if deleted_units else set(touched['gaps'])
    for key in sorted(gaps):
        row = data['gaps'][key]
        need(data['units'].present(row['units']) == set(row['units']), key + ': unknown gap units')
        if row['status'] == 'resolved':
            need(bool(row['evidence']) and bool(row['resolution']), key + ': gap resolution unsupported')
    return errors


def finding_errors(data, key, row, index=None, units_present=None):
    """Checks of one finding, shared by validate() and validate_changes()."""
    errors = []
    present = set(data['units']) if units_present is None else units_present
    if row['status'] == 'confirmed' or row['status'] == 'duplicate':
        if not row['units']:
            errors.append(key + ': missing units (a confirmed or duplicate finding needs its failing units)')
    if not set(row['units']) <= present:
        errors.append(key + ': missing units')
    if not row['evidence'] or not row['steps']:
        errors.append(key + ': finding lacks primary evidence/reproduction')
    if row['status'] in ('confirmed', 'refuted', 'duplicate') and not accepted(data, 'finding', key, row['actor'], index):
        stale = any(r['verdict'] == 'accept' and r['mode'] == 'independent' and r['actor'] != row['actor']
                    for r in reviews_for(data, 'finding', key, index))
        errors.append(key + (': finding changed after its independent review; apply the reviewer\'s corrections '
                             '(apply-corrections) or set status suspected and obtain a new review' if stale
                             else ': finding lacks independent validation'))
    if row['status'] == 'confirmed':
        if not all(data['units'].get(u, {}).get('status') == 'fail' for u in row['units']):
            errors.append(key + ': confirmed finding contradicts unit status')
    if row['status'] == 'duplicate' and 'duplicate_of' not in row:
        errors.append(key + ': status duplicate needs duplicate_of')
    if 'duplicate_of' in row and row['status'] not in ('suspected', 'duplicate'):
        errors.append(key + ': duplicate_of belongs to a proposed (suspected) or reviewed duplicate')
    if 'duplicate_of' in row:
        primary = data['findings'].get(row['duplicate_of'])
        if primary is None or row['duplicate_of'] == key:
            errors.append(key + ': duplicate_of names no other finding')
        elif primary['status'] == 'duplicate':
            errors.append(key + ': duplicate_of must name a primary finding, not another duplicate')
    if 'tracking' in row and not row['tracking']['evidence']:
        errors.append(key + ': tracking claim needs primary evidence')
    return errors


def evidence_refs(row):
    """Evidence IDs a row relies on, including those of a tracking claim."""
    return list(row.get('evidence', [])) + list((row.get('tracking') or {}).get('evidence', []))


def covering_finding(data, unit):
    """A fail unit is covered by a confirmed finding, or by a reviewed duplicate of a confirmed one."""
    for f in data['findings'].values():
        if unit in f['units']:
            if f['status'] == 'confirmed':
                return True
            if f['status'] == 'duplicate' and data['findings'].get(f.get('duplicate_of'), {}).get('status') == 'confirmed':
                return True
    return False


def evidence_errors(run, key, row):
    errors = []
    path = (Path(run) / row['file']).resolve()
    safe = Path(run).resolve() in path.parents and not (Path(run) / row['file']).is_symlink()
    if not (safe and path.is_file()):
        return [key + ': missing/unsafe evidence']
    if filehash(path) != row['sha256']:
        errors.append(key + ': evidence changed')
    elif 'members' in row:
        try:
            listed = json.loads(path.read_text(encoding='utf-8')).get('manifest')
        except (ValueError, UnicodeDecodeError, AttributeError):
            listed = None
        if listed != row['members']:
            errors.append(key + ': members differ from the stored manifest')
    for name, sha in row.get('members', {}).items():
        member = (Path(run) / 'evidence' / sha)
        if member.is_symlink() or not member.is_file() or filehash(member) != sha:
            errors.append(key + ': manifest member missing or changed: ' + name)
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


def review_index(data):
    """Reviews grouped by target, so per-unit acceptance checks stay linear in large ledgers."""
    index = {}
    for row in data['reviews'].values():
        index.setdefault(row['scope'] + REF_SEP + row['target'], []).append(row)
    return index


def reviews_for(data, scope, target, index=None):
    if index is not None:
        return index.get(scope + REF_SEP + target, [])
    if isinstance(data['reviews'], LazyTable):
        return [row for _, row in data['reviews'].by_ref(scope + REF_SEP + target)]
    return [r for r in data['reviews'].values() if r['scope'] == scope and r['target'] == target]


def accepted(data, scope, target, author, index=None):
    try:
        wanted = review_digest(data, scope, target)
    except KeyError:
        return False
    return any(r['scope'] == scope and r['target'] == target and r['digest'] == wanted
               and r['actor'] != author and r['mode'] == 'independent' and r['verdict'] == 'accept'
               and r['evidence'] and r['countercheck']
               and (scope not in ('unit', 'finding') or r['outcome'] == data[{'unit':'units','finding':'findings'}[scope]][target]['status'])
               for r in reviews_for(data, scope, target, index))


def put(data, actor, table, key, row):
    if table not in TABLES:
        raise ValueError('unknown table')
    old = data[table].get(key)
    if row is None and old is None:
        raise ValueError(key + ': no ' + table + ' row to remove')
    if old == row:
        return
    if row is None and table in RULE_TABLES:
        # Retiring a rule is journaled and changes the inventory digest, so it is reviewed.
        if old['actor'] != actor:
            raise ValueError(key + ': only the rule author ' + repr(old['actor']) + ' may retire it')
        del data[table][key]
        data['history'].append(dict(actor=actor, table=table, id=key, before=copy.deepcopy(old), after=None))
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
    # A reviewer correction is looked up only when a write would otherwise be refused, so the
    # journal replay does not scan reviews for every ordinary write.
    correction = lambda: old is not None and correcting_review(data, table, key, old, row) is not None
    if table == 'units':
        if old is None:
            if row != blank_unit(row['object'], row['variant'], row['criterion']):
                raise ValueError('units must start pending')
        elif not (old['status'] in ('pass', 'fail', 'excluded') and old['status'] == row['status'] and correction()):
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
    if table == 'findings':
        if old is not None and row['actor'] != old['actor']:
            raise ValueError(key + ': finding author is immutable')
        if row['actor'] != actor and not bookkeeping_only(old, row) and not correction():
            raise ValueError(key + ': finding actor mismatch; only its author ' + repr(row['actor']) + ' may change the content. '
                             'Others may add units, mark it duplicate, or apply reviewer corrections (apply-corrections)')
    data[table][key] = row
    data['history'].append(dict(actor=actor, table=table, id=key, before=copy.deepcopy(old), after=copy.deepcopy(row)))


# Corrections sharpen text. What decides coverage, identity or publication stays with the author:
# units, evidence, root cause and tracking change the finding itself and need its author and a review.
CORRECTION_LOCKED = ('status', 'actor', 'object', 'variant', 'criterion', 'duplicate_of',
                     'units', 'evidence', 'root_cause', 'tracking', 'blocker')


def correcting_review(data, table, key, old, row):
    """An accepting independent review whose corrections turn old into exactly row.

    The reviewer authored the corrected content and reviewed it in advance (digest of the
    corrected row), so applying it needs no further review round; who applies it is irrelevant."""
    scope = 'unit' if table == 'units' else 'finding'
    if scope == 'unit' and (old['status'] not in ('pass', 'fail', 'excluded') or row['status'] != old['status']):
        return None  # running work belongs to the job owner; only a finished result is corrected
    base = row_digest(scope, old)
    for review in reviews_for(data, scope, key):
        fix = review.get('corrections')
        if (fix and review.get('base_digest') == base and review['verdict'] == 'accept'
                and review['mode'] == 'independent' and review['actor'] != old['actor']
                and (scope != 'unit' or review['outcome'] == old['status'])
                and not set(fix) & set(CORRECTION_LOCKED) and set(fix) <= set(old)
                and {**old, **fix} == row and row_digest(scope, row) == review['digest']):
            return review
    return None


def bookkeeping_only(old, row):
    """Changes anyone may make to another author's finding: link more units, propose or mark a duplicate.

    Units and duplicate_of are reviewed content: a finding that gains units, or a duplicate pointed
    at another primary, needs a new independent review before it is confirmed or duplicate again
    (finding_errors enforces that), so these writes cannot launder an unreviewed claim."""
    if old is None:
        return False
    rest = lambda r: {k: v for k, v in r.items() if k not in ('units', 'status', 'duplicate_of')}
    if rest(old) != rest(row) or not set(old['units']) <= set(row['units']):
        return False
    grew = set(row['units']) > set(old['units'])
    return row['status'] == old['status'] or row['status'] == 'duplicate' \
        or (old['status'] == 'duplicate' and row['status'] == 'suspected') \
        or (grew and old['status'] == 'confirmed' and row['status'] == 'suspected')


def normalize_blocked(data, row):
    """Accept the shapes workers naturally send; the stored row stays schema-exact."""
    blocker = row.get('blocker')
    if isinstance(blocker, dict):
        blocker = dict(blocker)
        if isinstance(blocker.get('alternatives'), list):
            blocker['alternatives'] = '; '.join(str(x) for x in blocker['alternatives'] if str(x).strip())
        blocker.setdefault('context_digest', context_digest(data))
        row = {**row, 'blocker': blocker}
        if not row.get('actual') and blocker.get('obstacle'):
            row['actual'] = blocker['obstacle']
    return row


def check_fragment(data, fragment):
    if not isinstance(fragment, dict) or set(fragment) != {'base_sequence', 'actor', 'operations'}:
        raise ValueError('malformed fragment: expected base_sequence, actor, operations; review maps need wrapping')
    if type(fragment['base_sequence']) is not int or not isinstance(fragment['operations'], list):
        raise ValueError('malformed fragment: base_sequence must be integer and operations an array')
    if fragment['base_sequence'] != data['sequence']:
        raise ValueError('stale fragment: expected sequence ' + str(data['sequence']) + '; inspect changes before rebasing')
    if not isinstance(fragment['actor'], str) or not fragment['actor'].strip():
        raise ValueError('actor required')


def apply_operations(data, fragment):
    for op in fragment['operations']:
        if not isinstance(op, dict) or set(op) != {'table', 'id', 'value'}:
            raise ValueError('malformed operation')
        if op['table'] == 'files' and isinstance(op['value'], dict) and 'sha256' not in op['value'] \
                and data['files'].get(op['id']) is not None:
            # The manifest hash is immutable, so a mapping need not copy it from the files row.
            op['value'] = {**op['value'], 'sha256': data['files'][op['id']]['sha256']}
        if op['table'] == 'units' and isinstance(op['value'], dict) and op['value'].get('status') == 'blocked':
            row = op['value'] = normalize_blocked(data, op['value'])
            if not row.get('blocker') or blocker_state(data, row) != 'documented':
                raise ValueError(op['id'] + ': blocked requires a current structured blocker (attempt, obstacle, alternatives, '
                                 'next_action, retry_when); unattempted work stays pending')
            missing = [f for f in ('steps', 'actual', 'evidence') if not row.get(f)]
            if missing:
                raise ValueError(op['id'] + ': blocked requires attempted steps, observed obstacle and primary evidence; missing: '
                                 + ', '.join(missing))
        put(data, fragment['actor'], op['table'], op['id'], op['value'])
    data['sequence'] += 1


def apply(run, fragment, info=None):
    """Apply one fragment as a single transaction; returns the new sequence.

    Only the touched rows are read and checked, so a write stays fast in a ledger with
    10^5 units. A fragment based on an older sequence is rebased when none of the rows it
    writes changed since then (parallel workers on disjoint units); the result is validated
    against the current ledger like any write. AUDIT_VERIFY_APPLY=1 additionally runs the
    full validate() on the result and fails if the two disagree (used by the tests)."""
    run = Path(run)
    ensure_ledger(run)
    with write_lock(run):
        con, data = open_view(run)
        try:
            base = data['sequence']
            if isinstance(fragment, dict) and type(fragment.get('base_sequence')) is int and fragment['base_sequence'] < base \
                    and isinstance(fragment.get('operations'), list):
                rows = {(op.get('table'), op.get('id')) for op in fragment['operations'] if isinstance(op, dict)}
                conflicts = rebase_conflicts(con, fragment['base_sequence'], rows)
                if conflicts is None:
                    raise ValueError('stale fragment: expected sequence ' + str(base) + '; the journal has no rebase marks '
                                     'before sequence ' + str(fragment['base_sequence'] + 1) + ', rebuild it on the current state')
                if conflicts:
                    raise ValueError('stale fragment: rows changed since sequence ' + str(fragment['base_sequence']) + ': '
                                     + ', '.join(t + '/' + k for t, k in conflicts[:10]) + '; rebuild these operations')
                implicit = [op.get('id') for op in fragment['operations'] if isinstance(op, dict) and op.get('table') == 'units'
                            and isinstance(op.get('value'), dict) and op['value'].get('status') == 'blocked'
                            and not (isinstance(op['value'].get('blocker'), dict) and 'context_digest' in op['value']['blocker'])]
                if implicit and rebase_conflicts(con, fragment['base_sequence'], {('profile', k) for k in ('runtime', 'platforms', 'scope')}):
                    raise ValueError('stale fragment: runtime, platforms or scope changed since sequence ' + str(fragment['base_sequence'])
                                     + '; re-check the blocker of ' + ', '.join(map(str, implicit[:5])) + ' against the current context')
                if info is not None:
                    info['rebased_from'] = fragment['base_sequence']
                fragment = {**fragment, 'base_sequence': base}
            check_fragment(data, fragment)
            apply_operations(data, fragment)
            errors = validate_changes(data, run, data['history'])
            if os.environ.get('AUDIT_VERIFY_APPLY') == '1':
                full = load(run)
                apply_operations(full, fragment)
                full_errors = validate(full, run)
                if bool(full_errors) != bool(errors):
                    raise AssertionError('incremental and full validation disagree: '
                                         + repr(errors) + ' vs ' + repr(full_errors))
            if errors:
                raise ValueError('\n'.join(errors))
            commit(con, data, base)
            return data['sequence']
        finally:
            con.close()


def current_row(run, table, key):
    """One row and the ledger sequence, without loading the ledger."""
    ensure_ledger(run)
    con, data = open_view(run)
    try:
        return data['sequence'], copy.deepcopy(data[table].get(key))
    finally:
        con.close()


def plan(run, actor):
    """Add missing matrix units and prune untouched pending units that a rule now covers."""
    ensure_ledger(run)
    con, data = open_view(run)
    try:
        units = {key: json.loads(body) for key, body in con.execute(
            "SELECT id, body FROM rows WHERE tbl = 'units' ORDER BY rowid")}
    finally:
        con.close()
    rules = catalog()
    covered = coverage(data, rules)
    claimed = {u for j in data['jobs'].values() if j['status'] == 'active' for u in j['units']}
    ops = []
    for obj, row in data['objects'].items():
        for variant in row['variants']:
            for criterion in rules:
                key = uid(obj, variant, criterion)
                if key not in units and key not in covered:
                    ops.append(dict(table='units', id=key, value=blank_unit(obj, variant, criterion)))
    created = len(ops)
    for key, row in units.items():
        if key in covered and key not in claimed and row['status'] == 'pending' and not row['actor']:
            ops.append(dict(table='units', id=key, value=None))
    sequence = apply(run, dict(base_sequence=data['sequence'], actor=actor, operations=ops))
    pruned = len(ops) - created
    return dict(sequence=sequence, created=created, pruned=pruned, covered_by_rule=len(covered),
                units=len(units) + created - pruned)


def patch_row(run, actor, table, key, set_fields=None, add_fields=None, write_fragment=False):
    """Change selected fields of the current row; list fields in add_fields are unioned in order.

    Builds the operation from the current ledger state, so concurrent fields are kept."""
    if table not in TABLES:
        raise ValueError('unknown table')
    sequence, row = current_row(run, table, key)
    if row is None:
        raise ValueError(key + ': no current row in ' + table + '; create it with a full fragment')
    optional = dict(units={'blocker'}, findings={'duplicate_of', 'tracking'}, reviews={'corrections', 'base_digest'},
                    applicability={'variants'}).get(table, set())
    for name, value in (set_fields or {}).items():
        if name not in row and name not in optional and table != 'units':
            raise ValueError('unknown field for patch: ' + name)
        if value is None and name in optional:
            row.pop(name, None)
            continue
        row[name] = value
    for name, values in (add_fields or {}).items():
        if not isinstance(row.get(name), list) or not isinstance(values, list):
            raise ValueError('--add needs a list field and a JSON array: ' + name)
        row[name] = row[name] + [v for v in values if v not in row[name]]
    fragment = dict(base_sequence=sequence, actor=actor, operations=[dict(table=table, id=key, value=row)])
    if not write_fragment:
        return apply(run, fragment)
    path = Path(run) / 'parts' / ('patch-' + str(sequence) + '-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(fragment, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return path


MAX_EVIDENCE = 32 * 1024 * 1024
MAX_MEMBERS = 10000


def _store_blob(run, content, label):
    if not content or len(content) > MAX_EVIDENCE:
        raise ValueError(label + ': evidence must be nonempty and at most 32 MiB; split large traces')
    h = hashlib.sha256(content).hexdigest()
    dest = run / 'evidence' / h
    if dest.is_symlink():
        raise ValueError('unsafe evidence destination')
    if dest.exists() and filehash(dest) != h:
        raise ValueError('artifact collision')
    if not dest.exists():
        with dest.open('xb') as out:
            out.write(content)
    return h


def store_evidence(run, actor, source, kind, locator, environment):
    """Copy a file, or every file of a directory plus a hash manifest, into evidence/.

    Returns the evidence row; files are content-addressed, so storing twice is harmless."""
    run, source = Path(run), Path(source)
    if (run / 'evidence').resolve().parent != run.resolve():
        raise ValueError('unsafe evidence directory')
    if source.is_symlink():
        raise ValueError(str(source) + ': evidence source is a symlink; pass the real file or directory')
    if source.is_dir():
        paths = {}
        for path in sorted(source.rglob('*')):  # check the whole tree before storing anything
            name = path.relative_to(source).as_posix()
            if path.is_symlink():
                raise ValueError(str(source) + ': directory evidence contains a symlink: ' + name)
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(str(source) + ': directory evidence contains a non-regular file: ' + name)
            if len(paths) >= MAX_MEMBERS:
                raise ValueError(str(source) + ': more than ' + str(MAX_MEMBERS) + ' files; split the directory')
            paths[name] = path
        members = {name: _store_blob(run, path.read_bytes(), name) for name, path in paths.items()}
        if not members:
            raise ValueError(str(source) + ': evidence directory is empty')
        manifest = (json.dumps(dict(manifest=members), sort_keys=True, ensure_ascii=False, indent=1) + '\n').encode()
        h = _store_blob(run, manifest, str(source))
        return dict(file='evidence/' + h, sha256=h, kind=kind, locator=locator, environment=environment,
                    captured_by=actor, members=members)
    if not source.is_file():
        raise ValueError(str(source) + ': evidence source missing or not a regular file or directory')
    if source.stat().st_size > MAX_EVIDENCE:
        raise ValueError(str(source) + ': evidence exceeds 32 MiB')
    h = _store_blob(run, source.read_bytes(), str(source))
    return dict(file='evidence/' + h, sha256=h, kind=kind, locator=locator, environment=environment, captured_by=actor)


def evidence(run, actor, key, source, kind, locator, environment):
    row = store_evidence(run, actor, source, kind, locator, environment)
    sequence, _ = current_row(run, 'evidence', key)
    return apply(run, dict(base_sequence=sequence, actor=actor,
                          operations=[dict(table='evidence', id=key, value=row)]))


EVIDENCE_ITEM = ('id', 'source', 'kind', 'locator', 'environment')


def evidence_operations(run, actor, items, base):
    if not isinstance(items, list) or not items:
        raise ValueError('evidence batch must be a nonempty array')
    ops, seen = [], set()
    for i, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != set(EVIDENCE_ITEM) or not all(isinstance(item[k], str) and item[k].strip() for k in EVIDENCE_ITEM):
            raise ValueError('evidence item ' + str(i) + ' needs exactly: ' + ', '.join(EVIDENCE_ITEM))
        if item['id'] in seen:
            raise ValueError('duplicate evidence ID in batch: ' + item['id'])
        seen.add(item['id'])
        source = Path(item['source']) if Path(item['source']).is_absolute() else Path(base) / item['source']
        ops.append(dict(table='evidence', id=item['id'],
                        value=store_evidence(run, actor, source, item['kind'], item['locator'], item['environment'])))
    return ops


def evidence_batch(run, actor, batch_path):
    """Register many artifacts in one write; relative sources resolve against the batch file."""
    batch_path = Path(batch_path)
    ops = evidence_operations(run, actor, read(batch_path), batch_path.parent)
    sequence, _ = current_row(run, 'evidence', ops[0]['id'])
    return apply(run, dict(base_sequence=sequence, actor=actor, operations=ops))


INGEST_KEYS = {'job', 'evidence', 'units', 'findings', 'close'}
UNIT_RESULT = ('method', 'expected', 'actual', 'steps', 'evidence', 'limitations', 'reason')


def ingest(run, actor, result_path):
    """Import one worker result in a single write: evidence, unit results, findings, job close.

    Format (see references/fragments.md): {"job": ID, "evidence": [batch items], "units":
    {unit: {"status", "method", ... , "blocker"?, "finding"?}}, "findings": {id: row}, "close": bool}.
    A unit's "finding" adds the unit to that finding (new or existing)."""
    run, result_path = Path(run), Path(result_path)
    result = read(result_path)
    if not isinstance(result, dict) or not set(result) <= INGEST_KEYS or 'job' not in result:
        raise ValueError('worker result needs "job" and only: ' + ', '.join(sorted(INGEST_KEYS)))
    ensure_ledger(run)
    con, data = open_view(run)
    try:
        sequence = data['sequence']
        job = data['jobs'].get(result['job'])
        if not job or job['status'] != 'active' or job['owner'] != actor:
            raise ValueError(result['job'] + ': ingest needs an active job owned by ' + repr(actor))
        ops = evidence_operations(run, actor, result['evidence'], result_path.parent) if result.get('evidence') else []
        links = {}
        for key, given in (result.get('units') or {}).items():
            if key not in job['units']:
                raise ValueError(key + ': not in job ' + result['job'] + '; rework units must be claimed in the job')
            current = data['units'].get(key)
            if current is None:
                raise ValueError(key + ': unknown unit')
            extra = set(given) - set(UNIT_RESULT) - {'status', 'blocker', 'finding'}
            if extra or given.get('status') not in ('pass', 'fail', 'blocked', 'excluded'):
                raise ValueError(key + ': unit result needs a terminal status and only: status, blocker, finding, ' + ', '.join(UNIT_RESULT))
            row = {**blank_unit(current['object'], current['variant'], current['criterion']), 'actor': actor, 'status': 'running'}
            if current['status'] != 'running':
                ops.append(dict(table='units', id=key, value=row))
            final = {**row, **{k: given[k] for k in UNIT_RESULT if k in given}, 'status': given['status']}
            if 'blocker' in given:
                final['blocker'] = given['blocker']
            ops.append(dict(table='units', id=key, value=final))
            if given.get('finding'):
                links.setdefault(given['finding'], []).append(key)
        new = result.get('findings') or {}
        for key, row in new.items():
            row = {'actor': actor, 'units': [], **row}
            row['units'] = list(dict.fromkeys(row['units'] + links.pop(key, [])))
            ops.append(dict(table='findings', id=key, value=row))
        for key, units in links.items():
            existing = data['findings'].get(key)
            if existing is None:
                raise ValueError(key + ': unit names a finding that neither exists nor is in this result')
            grown = {**existing, 'units': list(dict.fromkeys(existing['units'] + units))}
            if existing['status'] in ('confirmed', 'duplicate') and grown['units'] != existing['units']:
                grown['status'] = 'suspected'  # new units change the reviewed content
            ops.append(dict(table='findings', id=key, value=grown))
        if result.get('close'):
            ops.append(dict(table='jobs', id=result['job'], value={**job, 'status': 'done'}))
    finally:
        con.close()
    info = {}
    sequence = apply(run, dict(base_sequence=sequence, actor=actor, operations=ops), info)
    touched = sorted({op['id'] for op in ops if op['table'] == 'findings'})
    return dict(sequence=sequence, operations=len(ops), findings=touched, **info,
                note='findings that gained units need a new finding review' if links or touched else '')


def apply_corrections(run, actor, review_ids=None):
    """Apply the machine-readable corrections of accepting reviews ("corrections": {field: value}).

    Only corrections whose base_digest matches the current target apply; the reviewer already
    accepted the corrected content (its digest), so no further review round is needed."""
    data = load(run)
    ops, skipped = [], {}
    wanted = set(review_ids) if review_ids else None
    for key, review in data['reviews'].items():
        if not review.get('corrections') or (wanted is not None and key not in wanted):
            continue
        table = {'unit': 'units', 'finding': 'findings'}.get(review['scope'])
        target = data[table].get(review['target']) if table else None
        if target is None:
            skipped[key] = 'corrections apply to unit or finding reviews with an existing target'
            continue
        if review_digest(data, review['scope'], review['target']) == review['digest']:
            continue  # already applied
        if review.get('base_digest') != row_digest(review['scope'], target):
            skipped[key] = 'target changed since the review (base_digest differs); obtain a new review'
            continue
        fixed = {**target, **review['corrections']}
        if not correcting_review({**data, 'reviews': {key: review}}, table, review['target'], target, fixed):
            skipped[key] = ('corrections invalid: only existing text fields (never ' + ', '.join(CORRECTION_LOCKED)
                            + '), an independent accept, a digest of the corrected row, and for a unit a finished '
                            'result whose status equals the review outcome')
            continue
        ops.append(dict(table=table, id=review['target'], value=fixed))
        data[table][review['target']] = fixed
    if wanted is not None and wanted - set(data['reviews']):
        raise ValueError('unknown review: ' + ', '.join(sorted(wanted - set(data['reviews']))))
    sequence = apply(run, dict(base_sequence=data['sequence'], actor=actor, operations=ops)) if ops else data['sequence']
    return dict(sequence=sequence, applied=[op['id'] for op in ops], skipped=skipped)


def resolve_answered(run, actor):
    """Resolve review objections that a later independent accept on the current content answered."""
    data = load(run)
    index = review_index(data)
    order = list(data['reviews'])
    ops = []
    for key, review in data['reviews'].items():
        if review['verdict'] not in ('reject', 'gap') or review_resolved(data, key):
            continue
        scope, target = review['scope'], review['target']
        if scope in ('unit', 'finding'):
            table = {'unit': 'units', 'finding': 'findings'}[scope]
            if target not in data[table]:
                continue
            author = data[table][target]['actor']
        else:
            author = data['profile'].get('coordinator', {}).get('value', '')
        if not accepted(data, scope, target, author, index):
            continue
        wanted = review_digest(data, scope, target)
        later = [r for r in order[order.index(key) + 1:]
                 if data['reviews'][r]['scope'] == scope and data['reviews'][r]['target'] == target
                 and data['reviews'][r]['verdict'] == 'accept' and data['reviews'][r]['digest'] == wanted
                 and data['reviews'][r]['actor'] != author and data['reviews'][r]['mode'] == 'independent']
        if not later:
            continue
        answer = data['reviews'][later[0]]
        units = [target] if scope == 'unit' else data['findings'][target]['units'] if scope == 'finding' else []
        gap = 'G-answered-' + key
        if gap in data['gaps']:
            continue
        ops.append(dict(table='gaps', id=gap, value=dict(
            description='Review ' + key + ' answered: ' + scope + ' ' + target + ' was reworked and independently accepted by '
                        + later[0] + ' on its current content.',
            status='resolved', units=units, evidence=answer['evidence'], resolution='answered by ' + later[0])))
    sequence = apply(run, dict(base_sequence=data['sequence'], actor=actor, operations=ops)) if ops else data['sequence']
    return dict(sequence=sequence, resolved=[op['id'] for op in ops])


def classify(run, actor, prefix, exclude=None, obj=None):
    """Exclude or map every file under one directory prefix in a single write."""
    if bool(exclude) == bool(obj):
        raise ValueError('classify needs exactly one of --exclude REASON or --map OBJECT')
    checked_exclusions({prefix: 'prefix'})
    ensure_ledger(run)
    con, data = open_view(run)
    try:
        # substr, not LIKE: LIKE ignores ASCII case and would take Docs/ for docs/.
        files = {k: json.loads(b) for k, b in con.execute(
            "SELECT id, body FROM rows WHERE tbl = 'files' AND (id = ? OR substr(id, 1, ?) = ?) ORDER BY id",
            (prefix, len(prefix) + 1, prefix + '/'))}
        if not files:
            raise ValueError('no inventoried file under ' + prefix)
        ops = []
        if exclude:
            mapped = sorted(k for k, f in files.items() if f['decision'] == 'mapped')
            if mapped:
                raise ValueError('files under ' + prefix + ' are mapped to objects (e.g. ' + ', '.join(mapped[:3]) + '); unmap them first')
            for key, row in files.items():
                if row['decision'] != 'blocked':
                    ops.append(dict(table='files', id=key, value={**row, 'decision': 'excluded', 'reason': exclude}))
        else:
            target = data['objects'].get(obj)
            if target is None:
                raise ValueError('unknown object: ' + obj)
            for key, row in files.items():
                if row['decision'] == 'blocked':
                    continue
                ops.append(dict(table='files', id=key, value={**row, 'decision': 'mapped', 'reason': '',
                                                              'objects': list(dict.fromkeys(row['objects'] + [obj]))}))
            ops.append(dict(table='objects', id=obj, value={**target, 'sources': list(dict.fromkeys(
                target['sources'] + [op['id'] for op in ops]))}))
        sequence = data['sequence']
    finally:
        con.close()
    return dict(sequence=apply(run, dict(base_sequence=sequence, actor=actor, operations=ops)), files=len(files),
                changed=sum(op['table'] == 'files' for op in ops))


SIZE_OR_MODE = re.compile(r'(compact|narrow|wide|mobile|tablet|desktop|small|large|\d{3,4}x\d{3,4}|dark|light|'
                          r'high-contrast|rtl|ltr|zoom|landscape|portrait)', re.I)


def inventory_export(data):
    """Compact inventory for reviewers: objects and rules without the file manifest."""
    rules = catalog()
    covered = coverage(data, rules)
    per_rule = {}
    for kind, rule, _ in covered.values():
        per_rule[rule] = per_rule.get(rule, 0) + 1
    dimensions = {}
    for cid, row in rules.items():
        dimensions.setdefault(row.get('dimension', ''), []).append(cid)
    objects = {}
    for key, row in data['objects'].items():
        variants = {}
        for variant in row['variants']:
            gaps = {d: sum(uid(key, variant, c) in covered for c in ids) for d, ids in dimensions.items()}
            variants[variant] = {d: str(len(ids) - gaps[d]) + '/' + str(len(ids)) for d, ids in dimensions.items()}
        objects[key] = dict(label=row['label'], kind=row['kind'], sources=len(row['sources']),
                            relations=row['relations'], criteria_planned_per_dimension=variants)
    warnings = []
    for key, rule in data['equivalences'].items():
        tokens = {v: {t.lower() for t in SIZE_OR_MODE.findall(v)} for v in [rule['representative']] + rule['variants']}
        if len({frozenset(t) for t in tokens.values()}) > 1:
            warnings.append(key + ': equivalence spans variants that differ in size, layout or mode tokens ('
                            + ', '.join(sorted(tokens)) + '); confirm structure, navigation and setting criteria really match')
    decisions = {}
    for row in data['files'].values():
        decisions[row['decision']] = decisions.get(row['decision'], 0) + 1
    return dict(revision=data['revision'], objects=objects,
                applicability={k: {**{f: r[f] for f in ('kinds', 'objects', 'criteria', 'dimensions', 'reason', 'evidence')},
                                   'variants': r.get('variants', []), 'covered_units': per_rule.get(k, 0)}
                               for k, r in data['applicability'].items()},
                equivalences={k: {**{f: r[f] for f in ('object', 'representative', 'variants', 'criteria', 'dimensions', 'reason', 'evidence')},
                                  'covered_units': per_rule.get(k, 0)} for k, r in data['equivalences'].items()},
                file_decisions=decisions, not_inventoried=data.get('scan_ignored', {}),
                scan_exclusions=data.get('scan_exclusions', {}), warnings=warnings,
                inventory_digest=inventory_digest(data))


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
                scan_exclusions=data.get('scan_exclusions', {}), scan_ignored=data.get('scan_ignored', {}),
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
    if result.get('scan_ignored'):
        lines += ['', '## Not inventoried: nested checkouts, Git-ignored and dependency directories', '',
                  'Not product source by the scan policy; the inventory review can dispute any entry (rerun init with --include).', '']
        lines += ['- ' + path.replace('\n', ' ') + ': ' + reason for path, reason in result['scan_ignored'].items()]
    if result.get('scan_exclusions'):
        lines += ['', '## Explicitly omitted source paths (unexamined)', '']
        lines += ['- ' + path.replace('\n', ' ') + ': ' + reason.replace('\n', ' ') for path, reason in result['scan_exclusions'].items()]
    foreign = {k: g for k, g in result['gaps'].items() if g.get('category') == 'foreign-change'}
    if foreign:
        lines += ['', '## Foreign changes on the test host', '',
                  'Activity outside the audit (other sessions, provisioning, updates) during the run; affected units are listed.', '']
        lines += ['- ' + k + ' (' + g['status'] + '): ' + g['description'].replace('\n', ' ')
                  + (' — units: ' + ', '.join(g['units']) if g['units'] else '') for k, g in foreign.items()]
    lines += ['', '## Findings', '']
    for f in result['findings']:
        state = f['status'] + (' of ' + f['duplicate_of'] if f.get('duplicate_of') else '')
        if f.get('tracking'):
            state += ' / tracked (' + f['tracking']['kind'] + '): ' + f['tracking']['reference']
        lines += ['### ' + f['id'] + ': ' + f['title'], '', state + ' / ' + f['priority'], '',
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
                error_groups=groups, scan_exclusions=result['scan_exclusions'],
                not_inventoried=len(result.get('scan_ignored', {})))


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


def next_work(data, limit=12, first=()):
    """Read-only queue: bounded packages, every object/variant represented before overflow.

    first: objects to schedule ahead of the rest (risk order), in the given order."""
    unknown = set(first) - set(data['objects'])
    if unknown:
        raise ValueError('unknown object for --first: ' + ', '.join(sorted(unknown)))
    if not 1 <= limit <= 100:
        raise ValueError('next limit must be between 1 and 100')
    blockers = {state: 0 for state in ('documented', 'stale', 'unsubstantiated')}
    index = review_index(data)
    packages = {}
    review_units = []
    for key, row in data['units'].items():
        state = blocker_state(data, row)
        if state:
            blockers[state] += 1
        if row['status'] in ('pass', 'fail', 'excluded'):
            if not accepted(data, 'unit', key, row['actor'], index):
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
    rank = {obj: i for i, obj in enumerate(first)}
    ordered = sorted(packages, key=lambda k: (order[k[2]], rank.get(k[0], len(rank)), k[0], k[1]))
    return dict(sequence=data['sequence'], context_digest=context_digest(data), blockers=blockers,
                unclassified_files=unclassified, actions=actions,
                package_count=len(packages), packages=[dict(object=k[0], variant=k[1], action=k[2],
                units=packages[k][:limit], criteria={u: data['units'][u]['criterion'] for u in packages[k][:limit]},
                remaining=max(0, len(packages[k])-limit)) for k in ordered],
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
        if row.get('corrections') is not None and row['scope'] in ('unit', 'finding'):
            # A correcting review reviews the corrected row; its base_digest binds the row as read.
            current = data[{'unit': 'units', 'finding': 'findings'}[row['scope']]].get(row['target'])
            if current is None:
                raise ValueError('review target missing: ' + key)
            if row.get('base_digest') != row_digest(row['scope'], current):
                raise ValueError('stale base_digest: ' + key + '; the target changed since the review, inspect it again')
            if row['digest'] != row_digest(row['scope'], {**current, **row['corrections']}):
                raise ValueError('digest of ' + key + ' is not the digest of the corrected row; use digest --corrections')
        elif row['digest'] != review_digest(data, row['scope'], row['target']):
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
    init.add_argument('--include', action='append', default=[], help='scan this directory although the policy skips it (repeatable)')
    init.add_argument('--scan-all', action='store_true', help='no relevance policy: also scan dependency, Git-ignored and nested-checkout directories')
    app = sub.add_parser('apply'); app.add_argument('run'); app.add_argument('fragment')
    ad = sub.add_parser('adopt-scan-policy', help='switch a run created before the relevance policy to it; requires a new inventory review')
    ad.add_argument('run'); ad.add_argument('--include', action='append', default=[], help='keep scanning this skipped directory (repeatable)')
    mig = sub.add_parser('migrate', help='convert a JSON ledger (audit.json) to audit.db; apply does this on its first write'); mig.add_argument('run')
    pl = sub.add_parser('plan'); pl.add_argument('run'); pl.add_argument('--actor', required=True)
    pa = sub.add_parser('patch', help='change fields of one current row without rewriting it by hand')
    pa.add_argument('run'); pa.add_argument('--actor', required=True); pa.add_argument('--table', required=True, choices=TABLES)
    pa.add_argument('--id', required=True)
    pa.add_argument('--set', dest='set_fields', help='JSON object; replaces these fields')
    pa.add_argument('--add', dest='add_fields', help='JSON object of arrays; unions them into list fields')
    pa.add_argument('--append-variant', help='objects only: add one variant, then run plan')
    pa.add_argument('--fragment', action='store_true', help='write the fragment to parts/ instead of applying it')
    ev = sub.add_parser('evidence'); ev.add_argument('run'); ev.add_argument('source'); ev.add_argument('--id'); ev.add_argument('--actor', required=True)
    ev.add_argument('--kind'); ev.add_argument('--locator'); ev.add_argument('--environment')
    wrap = sub.add_parser('wrap-reviews'); wrap.add_argument('run'); wrap.add_argument('draft'); wrap.add_argument('--actor', required=True)
    res = sub.add_parser('resume'); res.add_argument('run'); res.add_argument('--object'); res.add_argument('--status', choices=list(TRANSITIONS)); res.add_argument('--limit', type=int, default=20)
    nxt = sub.add_parser('next'); nxt.add_argument('run'); nxt.add_argument('--limit', type=int, default=12)
    nxt.add_argument('--first', action='append', default=[], help='schedule this object first (repeatable, risk order)')
    ev.add_argument('--batch', action='store_true', help='SOURCE is a JSON array of {id, source, kind, locator, environment}; one write')
    ing = sub.add_parser('ingest', help='import one worker result (evidence, units, findings, job close) in one write')
    ing.add_argument('run'); ing.add_argument('result'); ing.add_argument('--actor', required=True)
    co = sub.add_parser('apply-corrections', help="apply accepting reviews' machine-readable corrections")
    co.add_argument('run'); co.add_argument('--actor', required=True); co.add_argument('--review', action='append', default=[])
    ra = sub.add_parser('resolve-answered', help='resolve rejects/gaps answered by a later independent accept on current content')
    ra.add_argument('run'); ra.add_argument('--actor', required=True)
    cl = sub.add_parser('classify', help='exclude or map every inventoried file under a directory in one write')
    cl.add_argument('run'); cl.add_argument('--actor', required=True); cl.add_argument('--prefix', required=True)
    group = cl.add_mutually_exclusive_group(required=True)
    group.add_argument('--exclude', metavar='REASON'); group.add_argument('--map', metavar='OBJECT')
    inv = sub.add_parser('inventory', help='compact inventory (objects, rules, coverage, warnings) for reviewers'); inv.add_argument('run')
    for command in ('check', 'report', 'digest', 'drift'):
        cmd = sub.add_parser(command); cmd.add_argument('run')
        if command == 'digest':
            cmd.add_argument('--scope', choices=['inventory','final','unit','finding'], default='final')
            cmd.add_argument('--target', default='all')
            cmd.add_argument('--targets', help='comma-separated targets; prints a JSON map target -> digest')
            cmd.add_argument('--targets-file', help='file with one target per line (or a JSON array); prints a JSON map')
            cmd.add_argument('--corrections', help='JSON {field: value}; prints base_digest and the digest of the corrected row')
        if command in ('check', 'report'):
            cmd.add_argument('--verbose', action='store_true')
    args = p.parse_args()
    try:
        if args.command == 'init':
            data = initialize(args.run, args.repository, args.revision, read(args.exclusions) if args.exclusions else None,
                              args.include, args.scan_all)
            print(json.dumps(dict(files=len(data['files']), limits=len(data['scan_limits']),
                                  not_inventoried=data.get('scan_ignored', {})), ensure_ascii=False, indent=2))
        elif args.command == 'apply':
            info = {}
            print(json.dumps(dict(sequence=apply(args.run, read(args.fragment), info), **info)))
        elif args.command == 'adopt-scan-policy':
            print(json.dumps(adopt_scan_policy(args.run, args.include), ensure_ascii=False, indent=2))
        elif args.command == 'migrate':
            with write_lock(args.run):
                print('migrated' if migrate(args.run) else 'nothing to migrate')
        elif args.command == 'wrap-reviews': print(wrap_reviews(args.run, read(args.draft), args.actor))
        elif args.command == 'plan': print(json.dumps(plan(args.run, args.actor)))
        elif args.command == 'ingest': print(json.dumps(ingest(args.run, args.actor, args.result), ensure_ascii=False, indent=2))
        elif args.command == 'apply-corrections':
            print(json.dumps(apply_corrections(args.run, args.actor, args.review), ensure_ascii=False, indent=2))
        elif args.command == 'resolve-answered': print(json.dumps(resolve_answered(args.run, args.actor), ensure_ascii=False, indent=2))
        elif args.command == 'classify':
            print(json.dumps(classify(args.run, args.actor, args.prefix.rstrip('/'), args.exclude, args.map)))
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
            print(out if args.fragment else json.dumps(dict(sequence=out)))
        elif args.command == 'evidence' and not args.batch and not (args.id and args.kind and args.locator and args.environment):
            raise ValueError('evidence needs --id, --kind, --locator and --environment (or --batch)')
        elif args.command == 'evidence' and args.batch:
            print(json.dumps(dict(sequence=evidence_batch(args.run, args.actor, args.source))))
        elif args.command == 'evidence':
            print(json.dumps(dict(sequence=evidence(args.run,args.actor,args.id,args.source,args.kind,args.locator,args.environment))))
        else:
            data = load(args.run)
            if args.command == 'next':
                print(json.dumps(next_work(data, args.limit, args.first), ensure_ascii=False, indent=2)); return 0
            if args.command == 'inventory':
                print(json.dumps(inventory_export(data), ensure_ascii=False, indent=2)); return 0
            if args.command == 'digest' and args.corrections:
                if args.scope not in ('unit', 'finding'):
                    raise ValueError('--corrections applies to unit and finding scopes')
                row = data['units' if args.scope == 'unit' else 'findings'].get(args.target)
                fix = json.loads(args.corrections)
                if row is None or not isinstance(fix, dict) or not fix:
                    raise ValueError('--corrections needs an existing --target and a nonempty JSON object')
                if set(fix) & set(CORRECTION_LOCKED) or not set(fix) <= set(row):
                    raise ValueError('corrections may change existing content fields only, not ' + ', '.join(CORRECTION_LOCKED))
                print(json.dumps(dict(base_digest=row_digest(args.scope, row), digest=row_digest(args.scope, {**row, **fix})), indent=2))
                return 0
            if args.command == 'digest' and (args.targets or args.targets_file):
                if args.scope not in ('unit', 'finding'):
                    raise ValueError('--targets applies to unit and finding scopes')
                if args.targets_file:
                    text = Path(args.targets_file).read_text(encoding='utf-8')
                    targets = json.loads(text) if text.lstrip().startswith('[') else text.split()
                else:
                    targets = [t for t in args.targets.split(',') if t]
                table = 'units' if args.scope == 'unit' else 'findings'
                missing = [t for t in targets if t not in data[table]]
                if missing:
                    raise ValueError('unknown ' + args.scope + ': ' + ', '.join(missing[:10]))
                print(json.dumps({t: review_digest(data, args.scope, t) for t in targets}, indent=2)); return 0
            if args.command == 'digest':
                if args.scope in ('inventory', 'final') and args.target != 'all':
                    raise ValueError('inventory/final target must be all')
                print(review_digest(data,args.scope,args.target)); return 0
            if args.command == 'resume':
                print(json.dumps(resume(data,args.object,args.status,args.limit), ensure_ascii=False, indent=2)); return 0
            if args.command == 'drift':
                files, limits = rescan(data)
                base = baseline_files(data)
                changed = sorted(k for k in set(files)|set(base) if files.get(k,{}).get('sha256') != base.get(k,{}).get('sha256'))
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
