"""Windows runtime architecture and private native helper extraction."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_native_setup import payload

_ROOT = Path(__file__).resolve().parents[1]


class WindowsArmRuntimeTests(unittest.TestCase):
    def test_windows_target_uses_interpreter_architecture_under_emulation(self):
        with mock.patch.object(payload.platform, 'system', return_value='Windows'):
            for machine, expected in (('win-amd64', 'windows/x86_64'),
                                      ('win-arm64', 'windows/arm64')):
                with self.subTest(machine=machine), \
                        mock.patch.object(payload.sysconfig, 'get_platform', return_value=machine), \
                        mock.patch.object(payload.platform, 'machine', return_value='ARM64'):
                    self.assertEqual(payload.target(), expected)

    def test_arm_helper_uses_verified_owner_only_extraction_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            backend = mock.Mock()
            platforms = mock.Mock()
            platforms.select.return_value = backend
            service = mock.Mock()
            with mock.patch.object(payload, 'target', return_value='windows/arm64'), \
                    mock.patch.object(payload, 'metadata', return_value={
                    'target': 'windows/arm64', 'menu_sha256': 'a' * 64}), \
                    mock.patch.object(payload, 'load', return_value=service), \
                    mock.patch.object(payload.loader, 'load', return_value=platforms):
                env = payload.windows_helper_env(home, home / 'resources')
            directory = home / 'dotnet-bundle'
            self.assertEqual(env['DOTNET_BUNDLE_EXTRACT_BASE_DIR'], str(directory.resolve()))
            self.assertEqual(backend.protect_secret.call_args_list,
                             [mock.call(home), mock.call(directory)])
            self.assertNotEqual(os.environ.get('DOTNET_BUNDLE_EXTRACT_BASE_DIR'), str(directory))

    def test_arm_helper_requires_verified_digest(self):
        with mock.patch.object(payload, 'target', return_value='windows/arm64'), \
                mock.patch.object(payload, 'metadata', return_value={'target': 'windows/arm64'}):
            with self.assertRaisesRegex(OSError, 'unavailable'):
                payload.windows_helper_env(Path('home'), Path('resources'))

    def test_arm_acl_failure_is_a_safe_os_error(self):
        backend = mock.Mock()
        backend.protect_secret.side_effect = SystemExit('private details')
        platforms = mock.Mock()
        platforms.select.return_value = backend
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(payload, 'load'), \
                mock.patch.object(payload.loader, 'load', return_value=platforms):
            with self.assertRaisesRegex(OSError, '^The menu is unavailable'):
                payload.windows_helper_env(Path(temporary), Path(temporary) / 'resources',
                    {'target': 'windows/arm64', 'menu_sha256': 'a' * 64})

    def test_arm_helper_rejects_junction_before_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with mock.patch.object(payload.Path, 'is_junction', return_value=True), \
                    mock.patch.object(payload, 'load') as load:
                with self.assertRaisesRegex(OSError, 'unavailable'):
                    payload.windows_helper_env(home, home / 'resources',
                        {'target': 'windows/arm64', 'menu_sha256': 'a' * 64})
            load.assert_not_called()


class WindowsBootstrapArchitectureTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('pwsh') or shutil.which('powershell'), 'needs PowerShell')
    def test_target_selection_for_native_os_architecture(self):
        script = (_ROOT / 'packaging/bootstrap.ps1').read_text()
        selection = script[script.index('$cpu = switch'):script.index('$rt = (Get-Content')]
        shell = shutil.which('pwsh') or shutil.which('powershell')
        for architecture, target in (('arm64', 'windows/arm64'), ('x64', 'windows/x86_64')):
            with self.subTest(architecture=architecture):
                command = "$architecture = '%s'\n%s\nWrite-Output $target" % (architecture, selection)
                result = subprocess.run([shell, '-NoProfile', '-Command', command],
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout.strip(), target)
