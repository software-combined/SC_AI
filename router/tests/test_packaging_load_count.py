"""Loading the installer may not execute router module files more often.

`packaging/` has no module system: about fifty uncached path loaders each
execute their target again, so one `install.py` load runs the same files many
times (`ai_router/atomic_write.py` 45 times when this ceiling was recorded).
A new uncached loader multiplies that cost and splits module state between
copies. The ceiling may only fall; the cached-loader batch drives it to one
execution per file and then tightens the assertion.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests._platform import unix_only

ROOT = Path(__file__).resolve().parents[1]

# Measured on macOS: 240 executions of 51 files.
LOAD_CEILING = 240

# Same loader call as tests/install_fixtures.py, in a fresh isolated process
# so the audit hook sees every module execution and leaves no hook behind.
PROBE = r'''
import collections, importlib.util, json, sys
from pathlib import Path
root = Path(sys.argv[1])
counts = collections.Counter()


def hook(event, args):
    code = args[0] if event == 'exec' else None
    if getattr(code, 'co_name', None) != '<module>':
        return
    rel = Path(code.co_filename).resolve()
    if rel.is_relative_to(root) and rel.relative_to(root).parts[0] in ('packaging', 'ai_router'):
        counts[rel.relative_to(root).as_posix()] += 1


sys.addaudithook(hook)
spec = importlib.util.spec_from_file_location('router_install', root / 'packaging' / 'install.py')
spec.loader.exec_module(importlib.util.module_from_spec(spec))
print(json.dumps(counts))
'''


def load_counts():
    result = subprocess.run([sys.executable, '-I', '-c', PROBE, str(ROOT)],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout.splitlines()[-1])


# ponytail: unmeasured on Windows, where import-time branches may load other
# files; add a win32 ceiling when a Windows run records one.
@unix_only
class PackagingLoadCountTests(unittest.TestCase):
    def test_installer_load_executions_stay_under_the_ceiling(self):
        counts = load_counts()
        total = sum(counts.values())
        repeated = sorted((n, rel) for rel, n in counts.items() if n > 1)[-5:]
        self.assertLessEqual(total, LOAD_CEILING,
                             f'{total} module executions; most repeated: {repeated}')


if __name__ == '__main__':
    unittest.main()
