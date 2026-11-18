"""Resumable, complete source inventory; checkpoint limits never trim scope."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
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


# Directory names that only ever hold installed dependencies or tool caches. Ambiguous names
# such as build/, dist/ or target/ are skipped only when Git ignores them (see git_ignored_dirs).
GENERATED_DIRS = frozenset({
    'node_modules', 'bower_components', 'jspm_packages', '__pycache__', '.pytest_cache', '.mypy_cache',
    '.ruff_cache', '.tox', '.nox', '.venv', '.next', '.nuxt', '.svelte-kit', '.turbo', '.parcel-cache',
    '.gradle', '.dart_tool', 'DerivedData', 'Pods'})
NESTED_CHECKOUT = 'separate Git checkout or worktree (own baseline)'
GIT_IGNORED = 'ignored by Git (.gitignore or exclude rules)'
GENERATED = 'dependency or tool cache directory'


def git_ignored_dirs(repo):
    """Directories Git itself ignores; read-only, with fsmonitor hooks disabled. [] without Git."""
    git = shutil.which('git')
    if not git or not (Path(repo) / '.git').exists():
        return []
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'}
    try:
        done = subprocess.run([git, '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false', 'ls-files', '-z',
                               '--others', '--ignored', '--exclude-standard', '--directory'],
                              cwd=repo, capture_output=True, timeout=300, env=env)
    except (OSError, subprocess.SubprocessError):
        return []
    if done.returncode:
        return []
    return sorted(p[:-1] for p in done.stdout.decode('utf-8', 'surrogateescape').split('\0') if p.endswith('/'))


def _skip_reason(entry, child, policy):
    if policy is None or child in policy['includes'] or not entry.is_dir(follow_symlinks=False):
        return None
    if os.path.lexists(os.path.join(entry.path, '.git')):
        return NESTED_CHECKOUT
    if child in policy['git_ignored']:
        return GIT_IGNORED
    if entry.name in GENERATED_DIRS:
        return GENERATED
    return None


def _children(repo, rel, exclusions, policy=None, ignored=None):
    directory = _source_path(repo, rel)
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            child = (Path(rel) / entry.name).as_posix()
            # Git metadata is always omitted, also for worktree .git files.
            if entry.name == '.git' or child in exclusions:
                continue
            reason = _skip_reason(entry, child, policy)
            if reason:
                if ignored is not None:
                    ignored[child] = reason
                continue
            names.append(entry.name)
    return sorted(names)


def _membership(names):
    return hashlib.sha256(json.dumps(names, ensure_ascii=False).encode()).hexdigest()


def _reconcile(repo, state):
    for rel, expected in state['directories'].items():
        try:
            if (repo / rel).is_symlink() or _membership(_children(repo, rel, state['exclusions'], state.get('policy'))) != expected:
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
              exclusions=None, checkpoint=None, batch_seconds=60, policy=None):
    """Scan all entries. max_files/time are checkpoint intervals, not global caps.

    max_bytes bounds a read chunk (at most 1 MiB), never the file size. A changed
    tree fails closed; use a stable source copy for coherent multi-batch scans.

    policy=None scans everything (runs created before the relevance policy). With a policy
    {'includes': [...]}, directories that are nested checkouts, ignored by Git or dependency/
    tool caches are not traversed; they are returned as a third value, path -> reason.
    Paths in includes are scanned regardless.
    """
    if max_files < 1 or max_bytes < 1 or batch_seconds <= 0:
        raise ValueError('scan batch controls must be positive')
    repo = Path(repo).resolve()
    exclusions = exclusions or {}
    if policy is not None:
        policy = dict(includes=sorted(policy.get('includes', [])), git_ignored=git_ignored_dirs(repo))
    checkpoint = Path(checkpoint).resolve() if checkpoint else None
    if checkpoint and (checkpoint == repo or repo in checkpoint.parents):
        raise ValueError('scan checkpoint must be outside source repository')
    if checkpoint and checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding='utf-8'))
        if (state.get('version') != 2 or state.get('repository') != str(repo)
                or state.get('exclusions') != exclusions or state.get('policy') != policy):
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
        if policy is not None:
            state.update(policy=policy, ignored={})
    started, count = time.monotonic(), 0
    while state['pending']:
        # Keep the current path queued until its observation is fully recorded.
        rel = state['pending'][-1]
        path = _source_path(repo, rel)
        children = []
        try:
            before = _signature(path)
            if stat.S_ISDIR(before[2]):
                names = _children(repo, rel, exclusions, policy, state.get('ignored'))
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
    if policy is None:
        return state['files'], state['limits']
    return state['files'], state['limits'], dict(sorted(state['ignored'].items()))
