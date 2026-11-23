"""Loading the installer executes each router module file once.

`packaging/` has no module system, so its modules load siblings by path
through the one cached loader in `packaging/loader.py`. A second execution of
a file means an uncached loader: its copy has separate classes and globals,
so exception checks and test seams on one copy miss the other.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from tests._platform import unix_only

ROOT = Path(__file__).resolve().parents[1]

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
# files; drop unix_only when a Windows run passes.
@unix_only
class PackagingLoadCountTests(unittest.TestCase):
    def test_installer_load_executes_each_file_once(self):
        counts = load_counts()
        self.assertIn('packaging/loader.py', counts)
        self.assertEqual({rel: n for rel, n in counts.items() if n > 1}, {})


if __name__ == '__main__':
    unittest.main()
