"""Each baseline entry is a ceiling: shrinking passes, growth fails.

Plan 166 on top of landed Plan 156 item 4: the tool already rejects missing
files, unknown areas and entries back under the soft cap. The recorded count
is a growth ceiling, not an exact claim about the current size. The source
ratchets (multi-statement lines, long lines, packaging platform comparisons)
follow the same rule per file, and a file without an entry must count zero.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'check_source_limits.py'
OVER = 251  # ai_router soft cap (250) + 1


def build(root, files, baseline, ratchets=None):
    """Files map to a line count of `x = 1` or to their exact text."""
    for rel, lines in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(lines if isinstance(lines, str) else 'x = 1\n' * lines)
    config = root / 'config'
    config.mkdir(parents=True, exist_ok=True)
    (config / 'source-limits-baseline.json').write_text(json.dumps(baseline))
    if ratchets is not None:
        (config / 'source-ratchets-baseline.json').write_text(json.dumps(ratchets))


def run_tool(root):
    return subprocess.run([sys.executable, str(TOOL), '--root', str(root)],
                          capture_output=True, text=True)


# Each case is one source shape a later refactor batch must not add more of.
MULTI = 'a = 1; b = 2\n'
LONG = 'x = ' + repr('y' * 120) + '\n'
PLATFORM = 'import sys\nWIN = sys.platform == "win32"\n'
DISPATCH = 'def pick(delivery):\n    return delivery.get("platform") == "win32"\n'
LOWERED = 'import platform\nWIN = platform.system().lower() == "windows"\n'
PACKED = 'x = dict(\n    a=1); y = 2\n'
BLOCKS = 'def f(x):\n    match x:\n        case 1:\n            return 2\n    return 3\n'


class SourceLimitsBaselineTests(unittest.TestCase):
    def fixture(self, files, baseline, ratchets=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        build(root, files, baseline, ratchets)
        return run_tool(root)

    def test_exact_exemption_passes(self):
        result = self.fixture({'ai_router/x.py': OVER}, {'ai_router/x.py': OVER})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('failures=0', result.stdout)

    def test_a_new_overrun_fails(self):
        result = self.fixture({'ai_router/x.py': OVER}, {})
        self.assertEqual(result.returncode, 1)
        self.assertIn('not in baseline', result.stdout)

    def test_a_baseline_for_a_missing_file_fails(self):
        result = self.fixture({'ai_router/x.py': 10}, {'ai_router/gone.py': 300})
        self.assertEqual(result.returncode, 1)
        self.assertIn('BASELINE ai_router/gone.py: no such file', result.stdout)

    def test_a_shrunken_file_passes_against_its_ceiling(self):
        result = self.fixture({'ai_router/x.py': OVER}, {'ai_router/x.py': OVER + 9})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('failures=0', result.stdout)

    def test_growth_past_the_ceiling_fails(self):
        result = self.fixture({'ai_router/x.py': OVER + 10}, {'ai_router/x.py': OVER + 9})
        self.assertEqual(result.returncode, 1)
        self.assertIn('baseline ceiling %d' % (OVER + 9), result.stdout)

    def test_a_baseline_below_the_soft_cap_fails(self):
        result = self.fixture({'ai_router/x.py': 10}, {'ai_router/x.py': 10})
        self.assertEqual(result.returncode, 1)
        self.assertIn('no longer over the soft cap', result.stdout)

    def test_an_unknown_baseline_area_fails(self):
        result = self.fixture({'config/x.py': 10}, {'config/x.py': 999})
        self.assertEqual(result.returncode, 1)
        self.assertIn('unknown area', result.stdout)

    def test_a_non_integer_ceiling_fails(self):
        for bad in (OVER + 0.5, '260', True):
            with self.subTest(bad=bad):
                result = self.fixture({'ai_router/x.py': OVER}, {'ai_router/x.py': bad})
                self.assertEqual(result.returncode, 1, bad)
                self.assertIn('ceiling is not an integer', result.stdout)

    def test_the_live_baseline_passes_the_tool(self):
        result = run_tool(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('failures=0', result.stdout)

    def test_utf8_sources_ignore_the_host_locale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(root, {'ai_router/x.py': OVER}, {'ai_router/x.py': OVER})
            (root / 'ai_router/x.py').write_text('# \u201cUTF-8\u201d\n' * OVER, encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-X', 'utf8=0', str(TOOL), '--root', str(root)],
                env={**os.environ, 'LC_ALL': 'C', 'PYTHONCOERCECLOCALE': '0'},
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('checked=1 failures=0', result.stdout)

    def test_the_hard_cap_fails_even_with_an_exact_baseline(self):
        result = self.fixture({'ai_router/x.py': 401}, {'ai_router/x.py': 401})
        self.assertEqual(result.returncode, 1)
        self.assertIn('HARD ai_router/x.py: 401 lines', result.stdout)

    def assert_fails(self, result, text):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(text, result.stdout)

    def test_a_new_file_must_count_zero(self):
        cases = (('multi_statement', 'tests/x.py', MULTI), ('long_lines', 'tools/x.py', LONG),
                 ('platform_literals', 'packaging/x.py', PLATFORM),
                 ('platform_literals', 'packaging/native/x.py', DISPATCH),
                 ('platform_literals', 'packaging/y.py', LOWERED), ('multi_statement', 'tests/y.py', PACKED))
        for name, rel, text in cases:
            with self.subTest(name=name, rel=rel):
                result = self.fixture({rel: text}, {})
                self.assert_fails(result, f'RATCHET {name} {rel}: 1 (baseline 0)')

    def test_growth_past_a_ratchet_entry_fails(self):
        result = self.fixture({'ai_router/x.py': MULTI * 3}, {}, {'multi_statement': {'ai_router/x.py': 2}})
        self.assert_fails(result, 'RATCHET multi_statement ai_router/x.py: 3 (baseline 2)')

    def test_a_shrunken_count_fails_until_the_entry_is_lowered(self):
        result = self.fixture({'tools/x.py': LONG}, {}, {'long_lines': {'tools/x.py': 4}})
        self.assert_fails(result, 'TIGHTEN long_lines tools/x.py: 1 (baseline 4); lower the entry')

    def test_block_statements_are_not_packed_lines(self):
        result = self.fixture({'ai_router/x.py': BLOCKS}, {})
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_the_platform_backend_and_launchers_are_exempt(self):
        files = {'packaging/platforms/darwin.py': PLATFORM, 'packaging/task_launch.py': PLATFORM,
                 'ai_router/x.py': PLATFORM}
        result = self.fixture(files, {})
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_ratchet_entry_for_an_unchecked_file_fails(self):
        result = self.fixture({'ai_router/x.py': 1}, {},
                              {'platform_literals': {'ai_router/x.py': 1, 'packaging/gone.py': 2}})
        self.assert_fails(result, 'BASELINE platform_literals ai_router/x.py: not a checked file')
        self.assertIn('BASELINE platform_literals packaging/gone.py: not a checked file', result.stdout)

    def test_a_non_integer_ratchet_entry_fails(self):
        result = self.fixture({'tests/x.py': 1}, {}, {'long_lines': {'tests/x.py': '3'}})
        self.assert_fails(result, 'BASELINE long_lines tests/x.py: ceiling is not an integer')


if __name__ == '__main__':
    unittest.main()
