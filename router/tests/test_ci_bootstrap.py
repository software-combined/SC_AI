"""A pull request into main selects native acceptance from its actual diff."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_ci_pipeline import CHECK
from tests.test_workflows import run_block

COMPONENT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash') and shutil.which('git'),
                     'runs the real Ubuntu workflow shell and Git')
class CleanHistoryScopeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.component = self.root / 'router'
        for name in ('tools', 'packaging', 'ai_router'):
            (self.component / name).mkdir(parents=True)
        shutil.copyfile(COMPONENT / 'tools/ci_scope.py', self.component / 'tools/ci_scope.py')
        (self.component / 'packaging/install.py').write_text('# Synthetic installer fixture.\n')
        self.env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                    'GITHUB_OUTPUT': str(self.root / 'scope.out')}
        self.git('init', '-q')
        self.git('config', 'user.name', 'Example')
        self.git('config', 'user.email', 'test@example.invalid')
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, env=self.env,
                                       text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def scope(self, base):
        if base:
            self.git('update-ref', 'refs/remotes/origin/main', base)
        block = run_block('Installer scope', CHECK.read_text())
        result = subprocess.run(['bash', '-e', '-c', block], cwd=self.component,
                                env=dict(self.env, VERIFICATION_BASE='origin/main'),
                                capture_output=True, text=True)
        output = Path(self.env['GITHUB_OUTPUT'])
        return result, output.read_text() if output.exists() else ''

    def test_installer_change_selects_native_checks(self):
        (self.component / 'packaging/install.py').write_text('# Synthetic installer change.\n')
        self.commit()
        result, output = self.scope(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'installer=true\n')

    def test_runtime_only_change_keeps_the_actual_diff_scope(self):
        (self.component / 'ai_router/router.py').write_text('# Synthetic runtime-only change.\n')
        self.commit()
        result, output = self.scope(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, 'installer=false\n')

    def test_missing_base_branch_remains_a_failure(self):
        result, _ = self.scope(None)
        self.assertNotEqual(result.returncode, 0)
