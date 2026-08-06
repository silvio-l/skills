#!/usr/bin/env python3
"""
Diagnostic CLI: loads a run's working directory, derives all 13 gates via
risk_model.derive_gates(), and prints a readable gate table. Writes nothing.
Exit 0 if every gate is true, 1 if any gate is false — meant to be run
mid-flow (e.g. before Checkpoint C, or before rendering) to check whether
the run can already produce a real verdict or is still headed for
RESULT INCOMPLETE.

Usage: python3 check_gates.py <workdir>
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import risk_model  # noqa: E402
from render_report import load_workdir  # noqa: E402


def render_table(gates):
    lines = []
    width = max(len(name) for name in gates)
    for name, g in gates.items():
        status = "true " if g["value"] else "false"
        lines.append(f"{name.ljust(width)}  {status}  {g['reason']}")
    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_gates.py <workdir>", file=sys.stderr)
        return 2

    workdir = pathlib.Path(sys.argv[1])
    if not workdir.exists():
        print(f"error: workdir does not exist: {workdir}", file=sys.stderr)
        return 2

    profile, variants, digital, searchlog_rows, findings, redteam = load_workdir(workdir)
    gates = risk_model.derive_gates(profile, variants, searchlog_rows, findings, redteam)

    print(f"Gate status for {workdir}\n")
    print(render_table(gates))

    open_gates = [name for name, g in gates.items() if not g["value"]]
    print()
    if open_gates:
        print(f"{len(open_gates)}/{len(gates)} gate(s) open — this run would render RESULT INCOMPLETE.")
        return 1
    print(f"All {len(gates)} gates satisfied — this run can render a real verdict.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
