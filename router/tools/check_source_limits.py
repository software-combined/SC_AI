"""Enforce source size limits and per-file source ratchets.

Usage: python3.14 tools/check_source_limits.py [--root REPO]

Each baseline entry is a ceiling for one file over its soft cap (Plan 166):
the file may shrink freely and may not grow past the recorded count. An
entry for a missing file, an unknown area, or a file back under its soft
cap fails the check instead of drifting silently past it (Plan 156).

The ratchet baseline holds per-file counts that may only fall: lines with more
than one statement, lines over 120 characters, and platform comparisons in
packaging outside the platform backend and the self-contained launchers. A
file without an entry must count zero. A count below its entry fails until the
entry is lowered in the same change, so a gain cannot be spent again later.
"""
import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

# packaging/ holds entrypoints (installer, service helpers), so it takes the
# entrypoint budget from docs/RULES.md rather than the module one.
SOFT = {'ai_router': 250, 'tools': 400, 'tests': 300, 'packaging': 400}
HARD = {'ai_router': 400, 'tools': 700, 'tests': 500, 'packaging': 700}
LONG_LINE = 120
STR_METHODS = {'lower', 'upper', 'strip', 'casefold'}
# Platform branching belongs behind packaging/platforms/. The stable launchers
# stay self-contained on purpose: they run before any retained module loads.
PLATFORM_EXEMPT = {f'packaging/{name}_launch.py' for name in (
    'router', 'update', 'task', 'native', 'desktop', 'codex_switch', 'claude_profile')}


def _platform_value(node):
    """sys.platform, os.name, platform.system() or a delivery.get('platform')."""
    if isinstance(node, ast.BoolOp):
        return any(map(_platform_value, node.values))
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (node.value.id, node.attr) in (('sys', 'platform'), ('os', 'name'))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS:
        return _platform_value(node.func.value)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        owner = node.func.value
        if isinstance(owner, ast.Name) and (owner.id, node.func.attr) == ('platform', 'system'):
            return True
        first = node.args[0] if node.args else None
        return node.func.attr == 'get' and isinstance(first, ast.Constant) and first.value == 'platform'
    return False


def _platform_checks(tree):
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            count += any(map(_platform_value, [node.left, *node.comparators]))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            count += node.func.attr == 'startswith' and _platform_value(node.func.value)
    return count


def shape(rel, text):
    """Ratchet name -> count for one source file."""
    tree = ast.parse(text, rel)
    # A block statement (if, def, match ...) holds others; only its first line is its own.
    statements = [node for node in ast.walk(tree) if isinstance(node, ast.stmt)]
    compound = [node for node in statements if hasattr(node, 'body') or hasattr(node, 'cases')]
    simple = [node for node in statements if node not in compound]
    starts = Counter([node.lineno for node in compound]
                     + [line for node in simple for line in {node.lineno, node.end_lineno}])
    counts = {
        'multi_statement': sum(1 for seen in starts.values() if seen > 1),
        'long_lines': sum(1 for line in text.split('\n') if len(line.rstrip('\r')) > LONG_LINE),
    }
    scoped = rel.startswith('packaging/') and not rel.startswith('packaging/platforms/')
    if scoped and rel not in PLATFORM_EXEMPT:
        counts['platform_literals'] = _platform_checks(tree)
    return counts


def ratchet(name, counts, baseline):
    """Failures for one per-file count that may only fall."""
    failures = []
    for rel, count in sorted(counts.items()):
        ceiling = baseline.get(rel, 0)
        if isinstance(ceiling, bool) or not isinstance(ceiling, int):
            failures.append(f'BASELINE {name} {rel}: ceiling is not an integer')
        elif count > ceiling:
            failures.append(f'RATCHET {name} {rel}: {count} (baseline {ceiling})')
        elif count < ceiling:
            failures.append(f'TIGHTEN {name} {rel}: {count} (baseline {ceiling}); lower the entry')
    for rel in sorted(set(baseline) - set(counts)):
        failures.append(f'BASELINE {name} {rel}: not a checked file')
    return failures


def problems(root):
    """(checked, failures) for one repository root."""
    baseline = json.loads((root / 'config' / 'source-limits-baseline.json').read_text(encoding='utf-8'))
    ratchets_path = root / 'config' / 'source-ratchets-baseline.json'
    ratchets = json.loads(ratchets_path.read_text(encoding='utf-8')) if ratchets_path.is_file() else {}
    checked, failures, over_soft = 0, [], set()
    shapes = {'multi_statement': {}, 'long_lines': {}, 'platform_literals': {}}
    for area in SOFT:
        for path in sorted((root / area).rglob('*.py')):
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding='utf-8')
            count = text.count('\n') + (bool(text) and not text.endswith('\n'))
            for name, value in shape(rel, text).items():
                shapes[name][rel] = value
            checked += 1
            if count <= SOFT[area]:
                continue
            over_soft.add(rel)
            recorded = baseline.get(rel)
            if count > HARD[area]:
                failures.append(f'HARD {rel}: {count} lines')
            elif recorded is None:
                failures.append(f'SOFT {rel}: {count} lines (not in baseline)')
            elif isinstance(recorded, bool) or not isinstance(recorded, int):
                failures.append(f'BASELINE {rel}: ceiling is not an integer')
            elif count > recorded:
                failures.append(f'SOFT {rel}: {count} lines (baseline ceiling {recorded})')
    for rel in sorted(set(baseline) - over_soft):
        if not (root / rel).is_file():
            failures.append(f'BASELINE {rel}: no such file')
        elif rel.split('/', 1)[0] not in SOFT:
            failures.append(f'BASELINE {rel}: unknown area')
        else:
            failures.append(f'BASELINE {rel}: no longer over the soft cap')
    for name in sorted(set(shapes) | set(ratchets)):
        failures += ratchet(name, shapes.get(name, {}), ratchets.get(name, {}))
    return checked, failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]),
                        help='repository root to check')
    args = parser.parse_args(argv)
    checked, failures = problems(Path(args.root).resolve())
    for failure in failures:
        print(failure)
    print(f'source-limits: checked={checked} failures={len(failures)}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
