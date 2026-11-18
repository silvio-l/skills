"""Resumable, complete source inventory; checkpoint limits never trim scope."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time


def _write(path, state):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.scan-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _signature(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def _source_path(repo, rel):
    path = repo / rel
    if rel != '.' and path.parent.resolve() != path.parent:
        raise ValueError('source ancestor changed to a symlink: ' + rel)
    return path


def _children(repo, rel, exclusions):
    directory = _source_path(repo, rel)
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            child = (Path(rel) / entry.name).as_posix()
            # Git metadata is the only implicit omission, also for worktree .git files.
            if entry.name == '.git' or child in exclusions:
                continue
            names.append(entry.name)
    return sorted(names)


def _membership(names):
    return hashlib.sha256(json.dumps(names, ensure_ascii=False).encode()).hexdigest()


def _reconcile(repo, state):
    for rel, expected in state['directories'].items():
        try:
            if (repo / rel).is_symlink() or _membership(_children(repo, rel, state['exclusions'])) != expected:
                return False
        except (OSError, ValueError):
            return False
    for rel, expected in state['signatures'].items():
        try:
            if _signature(_source_path(repo, rel)) != expected:
                return False
        except (OSError, ValueError):
            return False
    return True


def _link_target(repo, rel, state):
    """Resolve using inventory and link text only; never traverse an external path."""
    remaining = rel.split('/')
    resolved, seen = [], set()
    while remaining:
        part = remaining.pop(0)
        if part in ('', '.'):
            continue
        if part == '..':
            if not resolved:
                raise ValueError('external target')
            resolved.pop()
            continue
        candidate = '/'.join(resolved + [part])
        if candidate in state['links']:
            if candidate in seen:
                raise ValueError('cyclic target')
            seen.add(candidate)
            target = state['links'][candidate]
            if os.path.isabs(target):
                # Reject external absolute paths before any filesystem access.
                try:
                    target = str(Path(target).relative_to(repo))
                except ValueError:
                    raise ValueError('external target') from None
                resolved = []
            remaining = target.split('/') + remaining
        else:
            if candidate not in state['directories'] and candidate not in state['files']:
                raise ValueError('missing or excluded target')
            if remaining and candidate not in state['directories']:
                raise ValueError('non-directory target ancestor')
            resolved.append(part)
    return '/'.join(resolved) or '.'


def _finish_links(repo, state):
    targets, failures = {}, {}
    for rel in state['links']:
        try:
            targets[rel] = _link_target(repo, rel, state)
        except ValueError as exc:
            failures[rel] = str(exc)
    # Directory aliases depend on every inventoried descendant being readable.
    # Iterate to propagate failures through other directory aliases, including root.
    changed = True
    while changed:
        changed = False
        for rel, target in targets.items():
            if rel in failures:
                continue
            under = lambda name: target == '.' or name == target or name.startswith(target + '/')
            if target in state['directories']:
                invalid = (any(under(name) for name in state['exclusions'])
                           or any(under(name) for name in failures)
                           or any(under(name) and row['decision'] == 'blocked'
                                  for name, row in state['files'].items() if name not in state['links']))
            else:
                invalid = state['files'][target]['decision'] == 'blocked'
            if invalid:
                failures[rel] = 'target contains excluded or unresolved source'
                changed = True
    for rel, reason in failures.items():
        reason = 'unresolved symlink: ' + rel + ': ' + reason
        state['files'][rel].update(decision='blocked', reason=reason)
        if reason not in state['limits']:
            state['limits'].append(reason)


def scan_tree(repo, max_files=50000, max_bytes=16 * 1024 * 1024,
              exclusions=None, checkpoint=None, batch_seconds=60):
    """Scan all entries. max_files/time are checkpoint intervals, not global caps.

    max_bytes bounds a read chunk (at most 1 MiB), never the file size. A changed
    tree fails closed; use a stable source copy for coherent multi-batch scans.
    """
    if max_files < 1 or max_bytes < 1 or batch_seconds <= 0:
        raise ValueError('scan batch controls must be positive')
    repo = Path(repo).resolve()
    exclusions = exclusions or {}
    checkpoint = Path(checkpoint).resolve() if checkpoint else None
    if checkpoint and (checkpoint == repo or repo in checkpoint.parents):
        raise ValueError('scan checkpoint must be outside source repository')
    if checkpoint and checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding='utf-8'))
        if (state.get('version') != 2 or state.get('repository') != str(repo)
                or state.get('exclusions') != exclusions):
            raise ValueError('scan checkpoint belongs to another source/scope')
        paths = list(state['pending']) + list(state['files']) + list(state['directories']) + list(state['signatures']) + list(state['links'])
        if any(not isinstance(rel, str) or (rel != '.' and (Path(rel).is_absolute() or '\\' in rel or any(part in ('', '.', '..') for part in rel.split('/')))) for rel in paths):
            raise ValueError('unsafe path in scan checkpoint')
        if not _reconcile(repo, state):
            checkpoint.unlink()
            raise ValueError('source changed since scan checkpoint; rerun init on a stable baseline')
    else:
        state = dict(version=2, repository=str(repo), exclusions=exclusions,
                     pending=['.'], files={}, limits=[], directories={}, signatures={}, links={})
    started, count = time.monotonic(), 0
    while state['pending']:
        # Keep the current path queued until its observation is fully recorded.
        rel = state['pending'][-1]
        path = _source_path(repo, rel)
        children = []
        try:
            before = _signature(path)
            if stat.S_ISDIR(before[2]):
                names = _children(repo, rel, exclusions)
                state['directories'][rel] = _membership(names)
                children = [(Path(rel) / name).as_posix() for name in reversed(names)]
            elif stat.S_ISREG(before[2]):
                checksum = hashlib.sha256()
                # O_NOFOLLOW avoids following a file changed to a symlink since lstat.
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
                with os.fdopen(fd, 'rb') as stream:
                    opened = os.fstat(stream.fileno())
                    if not stat.S_ISREG(opened.st_mode) or [opened.st_dev, opened.st_ino] != before[:2]:
                        raise ValueError('source changed while opening: ' + rel)
                    heartbeat = time.monotonic()
                    for chunk in iter(lambda: stream.read(min(max_bytes, 1024 * 1024)), b''):
                        checksum.update(chunk)
                        if time.monotonic() - heartbeat >= 60:
                            print('audit scan: hashing ' + rel + '; continuing', file=sys.stderr)
                            heartbeat = time.monotonic()
                if _signature(path) != before:
                    raise ValueError('source changed while hashing: ' + rel)
                state['files'][rel] = dict(sha256=checksum.hexdigest(), decision='pending', reason='', objects=[])
                state['signatures'][rel] = before
            elif stat.S_ISLNK(before[2]):
                target = os.readlink(path)
                if _signature(path) != before:
                    raise ValueError('source changed while reading symlink: ' + rel)
                state['links'][rel] = target
                digest = hashlib.sha256(b'symlink\0' + os.fsencode(target)).hexdigest()
                state['files'][rel] = dict(sha256=digest, decision='pending', reason='', objects=[])
                state['signatures'][rel] = before
            else:
                reason = 'non-regular source: ' + rel
                state['limits'].append(reason)
                state['files'][rel] = dict(sha256='unread', decision='blocked', reason=reason, objects=[])
                state['signatures'][rel] = before
        except OSError as exc:
            reason = 'source read/traversal failed: ' + rel + ': ' + type(exc).__name__
            state['limits'].append(reason)
            state['files'][rel] = dict(sha256='unread', decision='blocked', reason=reason, objects=[])
        state['pending'].pop()
        state['pending'].extend(children)
        count += 1
        if count >= max_files or time.monotonic() - started >= batch_seconds:
            if checkpoint:
                _write(checkpoint, state)
            print('audit scan: ' + str(len(state['files'])) + ' files inventoried; '
                  + str(len(state['pending'])) + ' queued paths; continuing', file=sys.stderr)
            started, count = time.monotonic(), 0
    _finish_links(repo, state)
    if not _reconcile(repo, state):
        if checkpoint and checkpoint.exists():
            checkpoint.unlink()
        raise ValueError('source changed during inventory; rerun on a stable baseline')
    if checkpoint:
        _write(checkpoint, state)
    return state['files'], state['limits']
