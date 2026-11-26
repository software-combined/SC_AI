"""CI scope stays one owner: the installer path list and the native test list.

Plan 156: an installer-changing PR pays for macOS and Windows checks; a
router-only PR keeps the single Ubuntu check. tools/ci_scope.py is the only
place either list lives, so this test pins its contract, including that every
singleton installer test file reaches the native jobs.
"""
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from tests.loading import load

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'ci_scope.py'


def scope_module():
    return load(TOOL, 'router_ci_scope')


def run_scope(*args, stdin=''):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          input=stdin, capture_output=True, text=True)


class InstallerScopeTests(unittest.TestCase):
    def scope(self, *paths):
        result = run_scope('--installer', stdin='\n'.join(paths))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_installer_paths_select_the_native_checks(self):
        for path in ('packaging/install.py', 'packaging/platforms/windows.py',
                     '.github/actions/setup/action.yml',
                     '.github/workflows/check.yml',
                     '.github/workflows/release.yml',
                     'tests/test_install_config.py', 'tests/test_windows_acl.py',
                     'tests/test_client_choice.py',
                     'tests/_platform.py',
                     'tests/windows_native_fixture.py',
                     'ai_router/key_dialog.py', 'ai_router/key_prompt.py',
                     'ai_router/winacl.py', 'tools/disable.py'):
            with self.subTest(path=path):
                self.assertEqual(self.scope(path), 'installer=true')

    def test_router_only_paths_keep_the_ubuntu_check(self):
        for path in ('ai_router/router.py', 'ai_router/catalogue.py',
                     'tests/test_ingress_guards.py', 'tests/test_handler.py',
                     'docs/release/compatibility.md', 'README.md'):
            with self.subTest(path=path):
                self.assertEqual(self.scope(path), 'installer=false')

    def test_an_empty_diff_is_not_installer(self):
        self.assertEqual(self.scope(), 'installer=false')

    def test_one_matching_path_selects_the_scope(self):
        self.assertEqual(
            self.scope('README.md', 'packaging/service.py', 'docs/release/compatibility.md'),
            'installer=true')

    def test_every_singleton_installer_test_file_runs_on_the_native_jobs(self):
        module = scope_module()
        listed = set(module.INSTALLER_TESTS)
        for path in module.INSTALLER_PATHS:
            if path.startswith('tests/test_') and path.endswith('.py'):
                with self.subTest(path=path):
                    self.assertIn(path[:-3].replace('/', '.'), listed)

    def test_native_list_names_real_test_modules(self):
        result = run_scope('--installer-tests')
        self.assertEqual(result.returncode, 0, result.stderr)
        modules = result.stdout.split()
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module):
                self.assertTrue((ROOT / (module.replace('.', '/') + '.py')).is_file())

    def test_windows_leaves_out_only_the_macos_only_suites(self):
        # Legacy Mac fixtures stay scoped; shared attachment contracts run on Windows.
        module = scope_module()
        macos_only = module.MACOS_ONLY_TESTS
        self.assertLessEqual(macos_only, set(module.INSTALLER_TESTS))
        self.assertEqual(module.installer_tests(windows=False), list(module.INSTALLER_TESTS))
        self.assertEqual(module.installer_tests(windows=True),
                         [name for name in module.INSTALLER_TESTS if name not in macos_only])
        self.assertIn('tests.test_claude_desktop_platform', module.installer_tests(windows=True))
        self.assertIn('tests.test_client_choice', module.installer_tests(windows=True))
        self.assertIn('tests.test_windows_client_discovery', module.installer_tests(windows=True))
        for name in ('model_access_flow', 'codex_subscription_defaults', 'setup_completion'):
            self.assertIn('tests.test_' + name, module.installer_tests(windows=True))

    def test_arm64_shards_execute_each_windows_test_occurrence(self):
        module = scope_module()

        def inventory(suite):
            for test in suite:
                if isinstance(test, unittest.TestSuite):
                    yield from inventory(test)
                else:
                    yield test.id()

        def selected(shard):
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromNames(module.installer_tests(windows=True, shard=shard))
            self.assertFalse(loader.errors, loader.errors)
            self.assertGreater(suite.countTestCases(), 0)
            return Counter(inventory(suite))

        parallel = sum((selected(shard) for shard in ('general', *module.ARM_INSTALLER_SHARDS)),
                       Counter())
        self.assertEqual(parallel, selected('all'))
        with self.assertRaisesRegex(ValueError, 'unknown installer shard'):
            module.installer_tests(windows=True, shard='misspelled')


if __name__ == '__main__':
    unittest.main()
