from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import lint_tree, SEVERITY_ORDER

ICON = {"error": "E", "warning": "W", "info": "i"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="skillcheck", description="Lint agent skill folders (SKILL.md).")
    p.add_argument("paths", nargs="*", default=["."], help="skill folders, SKILL.md files or a directory tree")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error",
                   help="lowest severity that causes a non-zero exit (default: error)")
    p.add_argument("--ignore", action="append", default=[], metavar="RULE", help="rule id to skip (repeatable)")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)
    findings = []
    for path in a.paths:
        pp = Path(path)
        if not pp.exists():
            print(f"skillcheck: path not found: {path}", file=sys.stderr)
            return 2
        findings += lint_tree(pp)
    findings = [f for f in findings if f.rule not in a.ignore]
    if a.format == "json":
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        for f in findings:
            loc = f"{f.path}:{f.line}" if f.line else f.path
            print(f"{ICON[f.severity]} {f.rule:<13} {loc}\n    {f.message}")
        counts = {s: sum(f.severity == s for f in findings) for s in SEVERITY_ORDER}
        print(f"\n{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} note(s)")
    if a.fail_on == "never":
        return 0
    limit = SEVERITY_ORDER[a.fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] <= limit for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
