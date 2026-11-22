"""Installer code starts PowerShell one way and quotes every value one way."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.loading import load

QUOTES = ('\u0027', '\u2018', '\u2019', '\u201a', '\u201b')
SHELL = shutil.which('pwsh') or shutil.which('powershell')


class WindowsShellTests(unittest.TestCase):
    def setUp(self):
        self.shell = load('packaging/windows_shell.py')
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / 'Windows'
        self.enterContext(mock.patch.dict(os.environ, {'SystemRoot': str(self.root)}))
        self.exe = str(self.root / 'System32/WindowsPowerShell/v1.0/powershell.exe')

    def test_every_single_quote_variant_is_doubled(self):
        for mark in QUOTES:
            with self.subTest(mark=hex(ord(mark))):
                self.assertEqual(self.shell.ps_quote('a' + mark + 'b'), "'a" + mark * 2 + "b'")
        self.assertEqual(self.shell.ps_quote(Path('plain')), "'plain'")

    def test_runner_uses_the_system_path_standard_flags_and_no_window(self):
        run = mock.Mock(return_value='done')
        with mock.patch.object(subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True):
            self.assertEqual(self.shell.run_script('Get-Date', run, timeout=7), 'done')
        self.assertEqual(run.call_args.args[0], [
            self.exe, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', 'Get-Date'])
        self.assertEqual(run.call_args.kwargs, {'timeout': 7, 'creationflags': 0x08000000})
        self.shell.run_script('Get-Date', run, creationflags=1)
        self.assertEqual(run.call_args.kwargs['creationflags'], 1)
        self.assertEqual(self.shell.argv('x', 'C:/found/powershell.exe')[0], 'C:/found/powershell.exe')

    def test_json_request_travels_as_ascii_on_stdin(self):
        run = mock.Mock()
        self.shell.run_json('$r=[Console]::In.ReadToEnd()', {'path': 'C:/O\u2019Brien \u00e9'}, run)
        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs['input'].isascii())
        self.assertEqual(json.loads(kwargs['input']), {'path': 'C:/O\u2019Brien \u00e9'})
        self.assertEqual((kwargs['encoding'], kwargs['text'], kwargs['capture_output']),
                         ('utf-8', True, True))
        self.assertNotIn('Brien', run.call_args.args[0][-1])

    def test_missing_or_relative_system_root_never_searches_path(self):
        run = mock.Mock(side_effect=AssertionError('unsafe executable lookup'))
        for root in ('', 'relative-windows'):
            with self.subTest(root=root), mock.patch.dict(os.environ, {'SystemRoot': root}), \
                    self.assertRaises(FileNotFoundError):
                self.shell.run_script('Get-Date', run)
        run.assert_not_called()

    def test_shortcut_script_keeps_a_typographic_quote_path_inside_one_literal(self):
        startup = load('packaging/desktop_startup.py')
        target = Path('C:/Users/O\u2019Brien \u2018x\u2019/Startup/SCG Router.lnk')
        run = mock.Mock(return_value=SimpleNamespace(returncode=0))
        with mock.patch.object(startup, 'windows_target', return_value=target), \
                mock.patch.object(Path, 'mkdir'):
            startup._windows(Path('C:/Router'), 'C:/Python/pythonw.exe', False, None, run)
        script = run.call_args.args[0][-1]
        self.assertIn('-LiteralPath ' + self.shell.ps_quote(target), script)
        self.assertNotIn('O\u2019Brien \u2018x\u2019', script)

    @unittest.skipUnless(SHELL, 'requires PowerShell to parse the quoted literal')
    def test_quoted_typographic_path_survives_powershell(self):
        value = 'C:\\O\u2019Brien\\\u2018a\u2019 \u201ab\u201b \'c\' $env:X `n'
        script = ('[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);'
                  '[Console]::Out.Write(%s)' % self.shell.ps_quote(value))
        result = subprocess.run([SHELL, '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode('utf-8'), value)


class LinuxRestartNoticeTests(unittest.TestCase):
    def setUp(self):
        self.notice = load('packaging/notice.py')
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def retained(self):
        folder = self.home / 'setup/1.2.3-0123456789abcdef'
        wrapper = folder / 'gui/bin/zenity'
        wrapper.parent.mkdir(parents=True)
        wrapper.write_text('#!/bin/sh\nexit 0\n')
        wrapper.chmod(0o755)
        (self.home / 'setup-current').write_text(folder.name + '\n')
        return str(wrapper)

    def test_restart_notice_uses_the_retained_dialog_tool(self):
        wrapper = self.retained()
        cmd = self.notice.dialog_command('1.0.0', 'linux', which=lambda _name: None,
                                         icon='', home=self.home)
        self.assertEqual(cmd[0], wrapper)
        with_app = self.notice.dialog_command(
            '1.0.0', 'linux', which=lambda name: '/usr/bin/' + name, icon='', home=self.home)
        self.assertEqual(with_app[:2], ['sh', '-c'])
        self.assertEqual(with_app[4], wrapper)

    def test_pending_notice_passes_its_home_to_the_dialog_choice(self):
        (self.home / self.notice.NOTICE_FILE).write_text(json.dumps(
            {'version': '1.0.0', 'names': ['Model'], 'clients': 'codex'}))
        command = mock.Mock(return_value=None)
        with mock.patch.object(self.notice, 'dialog_command', command), \
                mock.patch.object(self.notice.sys, 'platform', 'linux'), \
                mock.patch.dict(os.environ, {'ROUTER_NO_NOTICE': ''}):
            self.assertFalse(self.notice.show_pending(self.home))
        self.assertEqual(command.call_args.kwargs['home'], self.home)


if __name__ == '__main__':
    unittest.main()
