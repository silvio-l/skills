#!/usr/bin/env python3
"""Helper for the instructions-optimizer skill.

This script only handles the mechanical parts: finding candidate instruction
files, estimating their token count, and rendering the savings report. It
never writes to an instruction file. Deciding what is general knowledge vs.
project-specific delta — and writing the compressed content — is the calling
agent's job (see SKILL.md); that judgment can't be done by regex.
"""

import argparse
import json
import os
import sys
from pathlib import Path

EXCLUDED_DIR_NAMES = {
    '.git', 'node_modules', 'dist', 'build', '.next', '__pycache__',
    'venv', '.venv', 'target', '.turbo',
}

# Exact filenames matched case-insensitively. Deliberately excludes
# .claude.json/.claude.yaml/.claude.yml: those are Claude Code's live
# state/config files, not instruction prose, and must never be rewritten here.
INSTRUCTION_FILENAMES = {
    'claude.md',
    'context.md',
    '.cursorrules',
    'copilot-instructions.md',
}
INSTRUCTION_SUFFIXES = ('.instructions.md', '.rules')


class TokenEstimator:
    """~4 chars ≈ 1 token. A rough estimate for a savings percentage, not exact billing."""

    @staticmethod
    def estimate(text: str) -> int:
        return len(text) // 4


def _is_instruction_file(name: str) -> bool:
    lower = name.lower()
    return lower in INSTRUCTION_FILENAMES or lower.endswith(INSTRUCTION_SUFFIXES)


def _flat_candidate_dirs(root: Path):
    """Well-known locations, checked non-recursively only."""
    yield root
    yield root / '.github'
    yield root / '.claude'
    yield root / '.instructions'
    yield Path.home() / '.claude'
    yield Path.home() / '.github'


def _recursive_candidate_dirs(root: Path):
    """Project-local locations only — never the home directory — where
    *.rules / *.instructions.md files may live nested."""
    yield root
    yield root / '.github'
    yield root / '.claude'
    yield root / '.instructions'


def _walk_pruned(top: Path):
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for name in filenames:
            yield Path(dirpath) / name


def discover(root: Path) -> list[Path]:
    """Finds instruction files, deduped by inode so a case-insensitive
    filesystem (default on macOS/Windows) never returns the same physical
    file twice under two different-cased names."""
    found_by_inode = {}

    def add(candidate: Path) -> None:
        if not candidate.is_file():
            return
        st = candidate.stat()
        found_by_inode[(st.st_dev, st.st_ino)] = candidate

    for search_dir in _flat_candidate_dirs(root):
        if not search_dir.is_dir() or search_dir.name in EXCLUDED_DIR_NAMES:
            continue
        for entry in search_dir.iterdir():
            if entry.is_file() and _is_instruction_file(entry.name):
                add(entry)

    for search_dir in _recursive_candidate_dirs(root):
        if not search_dir.is_dir() or search_dir.name in EXCLUDED_DIR_NAMES:
            continue
        for candidate in _walk_pruned(search_dir):
            if _is_instruction_file(candidate.name):
                add(candidate)

    return sorted(found_by_inode.values(), key=str)


def cmd_discover(args) -> None:
    root = Path(args.path).resolve() if args.path else Path.cwd()
    files = discover(root)
    result = []
    for f in files:
        text = f.read_text(encoding='utf-8', errors='replace')
        result.append({'path': str(f), 'tokens': TokenEstimator.estimate(text)})
    json.dump(result, sys.stdout, indent=2)
    print()


def cmd_count(args) -> None:
    text = Path(args.file).read_text(encoding='utf-8', errors='replace')
    print(TokenEstimator.estimate(text))


def cmd_report(args) -> None:
    with open(args.manifest, encoding='utf-8') as f:
        rows = json.load(f)

    lines = ["# Instructions Optimization Report", ""]
    lines.append("| File | Path | Original (tokens) | Compressed (tokens) | Savings | Status |")
    lines.append("|------|------|-------------------|----------------------|---------|--------|")

    total_original = 0
    total_compressed = 0
    compressed_count = 0
    unchanged_count = 0

    for row in rows:
        path = Path(row['path'])
        original = int(row['original_tokens'])
        compressed = int(row['optimized_tokens'])
        savings = original - compressed
        savings_pct = (savings / original * 100) if original > 0 else 0.0

        if compressed < original:
            status = "Compressed"
            compressed_count += 1
        else:
            status = "Unchanged (already optimal)"
            unchanged_count += 1

        total_original += original
        total_compressed += compressed

        lines.append(
            f"| {path.name} | `{path}` | {original} | {compressed} | "
            f"{savings} ({savings_pct:.1f}%) | {status} |"
        )

    total_savings = total_original - total_compressed
    total_savings_pct = (total_savings / total_original * 100) if total_original > 0 else 0.0

    lines += [
        "",
        f"**Total savings:** {total_savings} tokens ({total_savings_pct:.1f}%)",
        f"**Files compressed:** {compressed_count}",
        f"**Files unchanged (already optimal):** {unchanged_count}",
    ]

    report_path = Path(args.out)
    report_path.write_text("\n".join(lines) + "\n", encoding='utf-8')
    print(f"Report written to: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    p_discover = sub.add_parser('discover', help='Find candidate instruction files and their token counts')
    p_discover.add_argument('--path', help='Project root to search from (default: cwd)')
    p_discover.set_defaults(func=cmd_discover)

    p_count = sub.add_parser('count', help='Estimate token count of a single file')
    p_count.add_argument('file')
    p_count.set_defaults(func=cmd_count)

    p_report = sub.add_parser('report', help='Render the compression report from a JSON manifest')
    p_report.add_argument('manifest', help='JSON file: [{"path", "original_tokens", "optimized_tokens"}, ...]')
    p_report.add_argument('--out', default='prompt-compression-report.md')
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
