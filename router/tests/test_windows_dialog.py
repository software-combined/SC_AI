"""Switch dialogs use the verified compiled helper and an explicit safe result."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_setup import module, resources, ROOT


class WindowsDialogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve() / 'home'
        self.source = resources(self.home / 'setup/fixture', version='1.3.26')
        self.helper = self.source / 'control/scg-router-menu.exe'
        self.helper.parent.mkdir()
        self.helper.write_bytes(b'MZ helper fixture')
        self.icon = self.source / 'router/packaging/assets/router-icon.png'
        self.icon.parent.mkdir(parents=True)
        self.icon.write_bytes((ROOT / 'packaging/assets/router-icon.png').read_bytes())
        metadata = json.loads((self.source / 'installer.json').read_text())
        metadata.update(target='windows/x86_64', menu_sha256=hashlib.sha256(self.helper.read_bytes()).hexdigest())
        (self.source / 'installer.json').write_text(json.dumps(metadata))
        (self.home / 'setup-current').write_text('fixture')
        self.dialog = module('windows_dialog')

    def test_confirm_and_cancel_are_native_quiet_and_preserve_unicode(self):
        for code, marker, want in ((0, 'accept', True), (1, 'cancel', False)):
            run = mock.Mock(return_value=SimpleNamespace(returncode=code,
                stdout='SCG_ROUTER_DIALOG_RESULT=' + marker + '\n'))
            self.assertIs(self.dialog.show('Switch Codex — café?', self.home, True, run), want)
            self.assertEqual(run.call_args.args[0], [str(self.helper), '--dialog', str(self.icon)])
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)
            self.assertEqual(run.call_args.kwargs['encoding'], 'utf-8')
            request = json.loads(run.call_args.kwargs['input'])
            self.assertEqual(request['labels'], ['Continue', 'Cancel'])
            self.assertEqual(request['text'], 'Switch Codex — café?')

    def test_old_or_failed_helpers_never_imply_consent(self):
        for code, stdout in ((0, ''), (2, ''), (0, 'SCG_ROUTER_DIALOG_RESULT=cancel'),
                             (1, 'SCG_ROUTER_DIALOG_RESULT=accept')):
            run = mock.Mock(return_value=SimpleNamespace(returncode=code, stdout=stdout))
            with self.assertRaises(OSError):
                self.dialog.show('Switch Codex?', self.home, True, run)

    def test_damaged_helper_is_refused_before_execution(self):
        self.helper.write_bytes(b'damaged helper')
        run = mock.Mock()
        with self.assertRaises(ValueError):
            self.dialog.show('Switch Codex?', self.home, True, run)
        run.assert_not_called()

    def test_setup_confirmations_and_ready_use_the_verified_home_helper(self):
        native = module('native_dialog')
        with mock.patch.object(native, 'sys', SimpleNamespace(platform='win32')), \
                mock.patch.object(native.platform, '_windows_dialogs', self.dialog), \
                mock.patch.object(native.dialog, 'tool', return_value=None):
            for code, marker, expected in ((0, 'accept', True), (1, 'cancel', False),
                                            (0, '', None)):
                run = mock.Mock(return_value=SimpleNamespace(returncode=code,
                    stdout='SCG_ROUTER_DIALOG_RESULT=' + marker + '\n'))
                self.assertIs(native.confirm_result('Finish setup?', self.home, run,
                    labels=('Finish setup', 'Cancel')), expected)
                self.assertEqual(run.call_args.args[0][0], str(self.helper))
                self.assertEqual(json.loads(run.call_args.kwargs['input'])['labels'],
                                 ['Finish setup', 'Cancel'])
            with mock.patch.object(native.platform, 'show_message') as show:
                native.message('Ready.', home=self.home)
            show.assert_called_once_with('Ready.', 'win32', home=self.home)

    def test_setup_ready_forwards_its_home_to_the_message(self):
        native = module('native_setup')
        dialog = mock.Mock()
        with mock.patch.object(native, 'status', return_value=dict(serving=True,
                onboarding=dict(ready=True, clients={}))), \
                mock.patch.object(native, 'load', return_value=dialog):
            native._check(self.source, self.home, dialog)
        dialog.message.assert_called_once_with(
            'Ready. Your assistants are connected and updates are automatic.', home=self.home)

    def test_ready_information_timeout_does_not_turn_success_into_an_error_dialog(self):
        setup, native = module('native_setup'), module('native_dialog')
        show_message, load = native.platform.show_message, setup.load
        run = mock.Mock(side_effect=subprocess.TimeoutExpired('synthetic-helper', 120))
        facts = dict(serving=True, service_key_usable=True,
                     onboarding=dict(ready=True, clients={'codex': {}}))
        before = {p.relative_to(self.home): p.read_bytes()
                  for p in self.home.rglob('*') if p.is_file()}
        with mock.patch.object(native, 'sys', SimpleNamespace(platform='win32')), \
                mock.patch.object(native.platform, '_windows_dialogs', self.dialog), \
                mock.patch.object(native.platform, 'show_message', side_effect=lambda text, platform, home=None:
                                  show_message(text, platform, run=run, home=home)), \
                mock.patch.object(setup, 'metadata'), \
                mock.patch.object(setup, 'load', side_effect=lambda name:
                                  native if name == 'native_dialog' else load(name)), \
                mock.patch.object(setup, 'status', return_value=facts), \
                mock.patch.object(setup, 'onboard', side_effect=lambda resources, home, action:
                                  setup._check(resources, home, native) or 0):
            self.assertEqual(setup.main(['--resources', str(self.source),
                                        '--home', str(self.home), '--action', 'install']), 0)
        run.assert_called_once()
        request = json.loads(run.call_args.kwargs['input'])
        self.assertEqual(request['labels'], ['OK'])
        self.assertTrue(request['text'].startswith('Ready.'))
        self.assertEqual(run.call_args.kwargs['timeout'], 120)
        self.assertEqual({p.relative_to(self.home): p.read_bytes()
                          for p in self.home.rglob('*') if p.is_file()}, before)

    def test_information_fallback_keeps_success_and_contains_timeout(self):
        native = module('native_dialog')
        for result in (True, subprocess.TimeoutExpired('synthetic-fallback', 120)):
            with self.subTest(result=type(result).__name__), \
                    mock.patch.object(native.platform, 'show_message',
                                      side_effect=[FileNotFoundError(), result]) as show:
                self.assertIs(native.message('Ready.', home=self.home), result is True)
            self.assertEqual(show.call_args_list, [
                mock.call('Ready.', native.sys.platform, home=self.home),
                mock.call('Ready.', native.sys.platform)])

    def test_confirmation_timeouts_never_grant_consent(self):
        native = module('native_dialog')
        confirm = native.platform.confirm
        run = mock.Mock(side_effect=subprocess.TimeoutExpired('synthetic-helper', 120))
        with mock.patch.object(native, 'sys', SimpleNamespace(platform='win32')), \
                mock.patch.object(native.platform, '_windows_dialogs', self.dialog), \
                mock.patch.object(native.platform, 'confirm', side_effect=lambda text, platform, home=None:
                                  confirm(text, platform, run=run, home=home)):
            with self.assertRaises(subprocess.TimeoutExpired):
                native.confirm('Restart Codex?', home=self.home)
            self.assertIsNone(native.confirm_result('Restart Codex?', self.home, run))
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(json.loads(call.kwargs['input'])['labels'], ['Continue', 'Cancel'])

    def test_first_setup_progress_keeps_the_existing_fallback_without_a_retained_helper(self):
        native = module('native_dialog')
        (self.home / 'setup-current').unlink()
        child = mock.Mock()
        child.poll.return_value = None
        with mock.patch.object(native, 'sys', SimpleNamespace(platform='win32')), \
                mock.patch.object(native.platform, '_windows_dialogs', self.dialog), \
                mock.patch.object(native.subprocess, 'Popen', return_value=child) as popen:
            with native.Progress(home=self.home) as progress:
                self.assertIs(progress.process, child)
        self.assertEqual(popen.call_args.args[0][0], 'powershell')

    def test_waiting_window_uses_the_same_verified_native_helper(self):
        child = mock.Mock()
        with mock.patch.object(self.dialog.subprocess, 'Popen', return_value=child) as popen:
            self.assertIs(self.dialog.progress(self.home, 'Waiting for SCG Router', 'Cancel'), child)
        self.assertEqual(popen.call_args.args[0], [str(self.helper), '--progress', str(self.icon)])
        self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)
        self.assertEqual(json.loads(child.stdin.write.call_args.args[0])['labels'], ['Cancel'])

    def test_blocked_helper_falls_back_to_the_styled_script(self):
        for code, marker, want in ((0, 'accept', True), (1, 'cancel', False)):
            run = mock.Mock(side_effect=[OSError('blocked by endpoint protection'),
                SimpleNamespace(returncode=code, stdout='SCG_ROUTER_DIALOG_RESULT=' + marker)])
            self.assertIs(self.dialog.show('Switch Codex?', self.home, True, run), want)
            self.assertEqual(run.call_args.args[0][0], 'powershell')
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)

    def test_blocked_helper_falls_back_for_the_waiting_window(self):
        responses = [OSError('blocked by endpoint protection'), mock.Mock()]
        with mock.patch.object(self.dialog.subprocess, 'Popen', side_effect=responses) as popen:
            self.dialog.progress(self.home, 'Waiting for SCG Router', 'Cancel')
        self.assertEqual(popen.call_args.args[0][0], 'powershell')
        self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)

    def test_pre_dialog_helpers_use_the_styled_quiet_fallback_for_wait_and_cancel(self):
        for name in ('installer.json', 'payload/latest.json'):
            path = self.source / name
            doc = json.loads(path.read_text())
            doc['version'] = '1.3.16.207'
            path.write_text(json.dumps(doc))
        (self.source / 'router/packaging/VERSION').write_text('1.3.16.207')
        for code, marker, expected in ((0, 'accept', True), (1, 'cancel', False)):
            run = mock.Mock(return_value=SimpleNamespace(returncode=code,
                stdout='SCG_ROUTER_DIALOG_RESULT=' + marker))
            self.assertIs(self.dialog.show('Switch Codex?', self.home, True, run), expected)
            self.assertEqual(run.call_args.args[0][0], 'powershell')
            self.assertEqual(run.call_args.kwargs['creationflags'], 0x08000000)
            script = run.call_args.args[0][-1]
            for required in ("$f.Text='SCG Router'", "$b.Text='Continue'", "$b.DialogResult='OK'",
                             "$c.Text='Cancel'", "$c.DialogResult='Cancel'"):
                self.assertIn(required, script)
        with mock.patch.object(self.dialog.subprocess, 'Popen') as popen:
            self.dialog.progress(self.home, 'Waiting for SCG Router', 'Cancel')
        self.assertEqual(popen.call_args.args[0][0], 'powershell')
        self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000000)


if __name__ == '__main__':
    unittest.main()
