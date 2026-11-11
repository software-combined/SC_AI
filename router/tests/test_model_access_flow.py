"""Menu access and work provisioning respect local facts and saved-key authority."""
import json
import contextlib
import io
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_router import key_store, work_account
from tests.test_native_setup import module, resources
from tests.test_work_account import issued


class ModelAccessTests(unittest.TestCase):
    def test_native_normalisation_preserves_the_unsafe_home_link_refusal(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, target, link = resources(root / 'Resources'), root / 'target', root / 'linked'
            target.mkdir()
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest('This host cannot create a directory link.')
            dialog = mock.Mock()
            with mock.patch.object(native, 'load', return_value=dialog), \
                    mock.patch.object(native, 'onboard', return_value=0) as action:
                self.assertEqual(native.main(['--resources', str(source), '--home', str(link)]), 1)
            action.assert_not_called()
            self.assertEqual(list(target.iterdir()), [])

    def test_unreadable_key_reports_attention_without_provisioning_or_network(self):
        control, diagnostics = module('desktop_control'), module('diagnostics')
        installer = mock.Mock()
        installer._diag._status_document.side_effect = diagnostics._status_document
        modules = dict(install=installer, update_status=module('update_status'),
                       desktop_startup=SimpleNamespace(enabled=lambda _: False))
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            key = home / 'openrouter.key'
            key.write_text('synthetic-incumbent')
            original = Path.read_text
            def read(path, *args, **kwargs):
                if path == key:
                    raise PermissionError('synthetic')
                return original(path, *args, **kwargs)
            with mock.patch.object(Path, 'read_text', read), \
                    mock.patch.object(control, 'load', side_effect=modules.__getitem__), \
                    mock.patch.object(diagnostics, '_key_private', return_value=False):
                self.assertEqual(control.snapshot(home)['key_status'], 'attention')
            self.assertEqual(key.read_text(), 'synthetic-incumbent')

    def test_relative_installer_home_is_checked_from_the_child_working_directory(self):
        installer = module('install')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = root / 'selected'
            release = home / 'releases/1.2.0'
            release.mkdir(parents=True)
            (home / 'current').write_text('1.2.0')
            key = home / 'openrouter.key'
            key.write_text('synthetic-incumbent')
            launch = mock.Mock(return_value=mock.Mock())
            with contextlib.chdir(root), mock.patch.object(installer.subprocess, 'Popen', launch):
                installer._open_key_window('synthetic-python', Path('selected'),
                                           'http://127.0.0.1:1/t/setup/n', 'codex')
                child_cwd = Path(launch.call_args.kwargs['cwd']).resolve()
                child_env = launch.call_args.kwargs['env']
            authorize = mock.Mock(return_value={'access_token': 'synthetic'})
            post = mock.Mock(return_value=issued())
            with contextlib.chdir(child_cwd), mock.patch.dict(os.environ, child_env, clear=True), \
                    mock.patch.object(key_store, 'check_key', return_value=('key', None, None)):
                with self.assertRaises(work_account.SignInFailed):
                    work_account.provision(authorize=authorize, post=post)
            authorize.assert_not_called()
            post.assert_not_called()
            self.assertEqual(key.read_text(), 'synthetic-incumbent')

    def test_native_entry_point_normalises_the_home_before_any_action(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, home = resources(root / 'Resources'), root / 'selected'
            with contextlib.chdir(root), mock.patch.object(native, 'onboard', return_value=0) as action:
                self.assertEqual(native.main(['--resources', str(source), '--home', 'selected',
                                              '--action', 'key']), 0)
            action.assert_called_once_with(source, home, 'key')

    def test_installer_prompt_checks_its_selected_home_in_both_mismatch_directions(self):
        installer = module('install')
        for selected_has_key in (False, True):
            with self.subTest(selected_has_key=selected_has_key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                selected, inherited = root / 'selected', root / 'inherited'
                selected.mkdir()
                inherited.mkdir()
                incumbent = (selected if selected_has_key else inherited) / 'openrouter.key'
                incumbent.write_text('synthetic-incumbent')
                launch = mock.Mock(return_value=mock.Mock())
                with mock.patch.dict(os.environ, {'ROUTER_HOME': str(inherited)}), \
                        mock.patch.object(installer.subprocess, 'Popen', launch):
                    installer._open_key_window('synthetic-python', selected,
                                               'http://127.0.0.1:1/t/setup/n', 'codex')
                    child_env = launch.call_args.kwargs.get('env', dict(os.environ))
                authorize = mock.Mock(return_value={'access_token': 'synthetic'})
                post = mock.Mock(return_value=issued())
                with mock.patch.dict(os.environ, child_env, clear=True), \
                        mock.patch.object(key_store, 'check_key', return_value=('key', None, None)):
                    if selected_has_key:
                        with self.assertRaises(work_account.SignInFailed):
                            work_account.provision(authorize=authorize, post=post)
                        authorize.assert_not_called()
                        post.assert_not_called()
                    else:
                        self.assertEqual(work_account.provision(authorize=authorize, post=post),
                                         issued()['data']['key'])
                        authorize.assert_called_once()
                        post.assert_called_once()
                self.assertEqual(incumbent.read_text(), 'synthetic-incumbent')

    def test_menu_reads_service_access_without_using_a_shell_key_or_contacting_provider(self):
        control, diagnostics = module('desktop_control'), module('diagnostics')
        installer = mock.Mock()
        installer._diag._status_document.side_effect = diagnostics._status_document
        modules = dict(install=installer, update_status=module('update_status'),
                       desktop_startup=SimpleNamespace(enabled=lambda _: False))
        for stored, expected in ((None, 'needed'), ('', 'needed'), ('synthetic-saved', 'saved')):
            with self.subTest(stored=stored), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                if stored is not None:
                    path = home / 'openrouter.key'
                    path.write_text(stored)
                with mock.patch.dict(os.environ, {'OPENROUTER_API_KEY': 'synthetic-shell'}, clear=True), \
                        mock.patch.object(control, 'load', side_effect=modules.__getitem__), \
                        mock.patch.object(diagnostics, '_key_private', return_value=True), \
                        mock.patch.object(key_store, 'check_key') as check:
                    facts = control.snapshot(home)
                self.assertEqual(facts['key_status'], expected)
                self.assertNotIn('synthetic', json.dumps(facts))
                check.assert_not_called()

    def test_work_account_action_shows_connecting_and_ignores_duplicate_clicks(self):
        menu = module('desktop_menu')
        release = threading.Event()
        calls, documents = [], []
        class Input(io.StringIO):
            def write(self, text):
                documents.append(json.loads(text))
                return len(text)
            def close(self):
                release.set()
                super().close()
        shell = SimpleNamespace(stdin=Input(), stdout=io.StringIO(), poll=lambda: None,
                                wait=lambda **kwargs: 0)
        def events(stream, queue):
            for event in ({'action': 'setup.key'}, {'action': 'setup.key'}, {'closed': True}):
                queue.put(event)
        def control(home, resources, action=None):
            if action:
                calls.append(action)
                release.wait(2)
                return dict(outcome='done')
            return dict(status='Key needed', key_status='needed', clients=[])
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / 'control').mkdir()
            (home / 'control' / ('scg-router-menu.exe' if os.name == 'nt' else 'scg-router-menu')).touch()
            (home / 'installer.json').write_text('{"version":"1.3.51"}')
            with mock.patch.object(menu, '_events', side_effect=events), \
                    mock.patch.object(menu, '_control', side_effect=control), \
                    mock.patch.object(menu.subprocess, 'Popen', return_value=shell):
                self.assertEqual(menu.run_menu(home, home), 74)
        self.assertEqual(calls, ['setup.key'])
        self.assertTrue(any(doc['status'] == 'Connecting…' for doc in documents))

    def test_menu_exposes_missing_access_and_retains_dead_key_recovery(self):
        model = module('desktop_model')
        for key_status in ('needed', 'saved', 'attention', 'unknown'):
            with self.subTest(key_status=key_status):
                facts = dict(status='Running', key_status=key_status, clients=[])
                rows = model.menu(facts)['menu']
                access = [row for row in rows if row['action'] == 'setup.key']
                if key_status in ('needed', 'attention'):
                    self.assertEqual(len(access), 1)
                    self.assertIn('work account' if key_status == 'needed' else 'attention',
                                  access[0]['label'])
                elif key_status == 'saved':
                    saved = next(row for row in rows if row['label'] == 'OpenRouter key: Saved')
                    self.assertFalse(saved['enabled'])
                    self.assertIsNone(saved['action'])
                manage = next(row for row in rows if row['label'] == 'Manage Router')
                self.assertIn('setup.key', [row['action'] for row in manage['children']])
                if key_status == 'needed':
                    self.assertEqual(dict(model.chooser(rows)[1])['setup.key'], access[0]['label'])
                else:
                    self.assertIn('Replace model key…', [row['label'] for row in manage['children']])
                self.assertEqual(model.chooser(model.menu(facts, busy='Connecting…')['menu'])[1], [])
                self.assertNotIn('email', json.dumps(rows))

    def test_saved_key_prevents_oauth_and_issuance_unless_definitively_dead(self):
        for result in ('live', 'unknown', 429, 401, 403):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                key_path = home / 'openrouter.key'
                key_path.write_text('synthetic-incumbent')
                authorize = mock.Mock(return_value={'access_token': 'synthetic-access'})
                post = mock.Mock(return_value=issued())
                outcome = ('label', None, None) if result == 'live' else (
                    OSError('private-path') if result == 'unknown' else
                    key_store.KeyRejected('rejected', status=result))
                with mock.patch.dict(os.environ, {'ROUTER_HOME': str(home)}), \
                        mock.patch.object(key_store, 'check_key',
                            **({'return_value': outcome} if result == 'live' else {'side_effect': outcome})):
                    if result in (401, 403):
                        self.assertEqual(work_account.provision(authorize=authorize, post=post),
                                         issued()['data']['key'])
                        authorize.assert_called_once()
                        post.assert_called_once()
                    else:
                        with self.assertRaises(work_account.SignInFailed) as raised:
                            work_account.provision(authorize=authorize, post=post)
                        self.assertIn('already saved', str(raised.exception))
                        self.assertNotIn('still works', str(raised.exception))
                        self.assertNotIn('private', str(raised.exception))
                        authorize.assert_not_called()
                        post.assert_not_called()
                self.assertEqual(key_path.read_text(), 'synthetic-incumbent')

    def test_missing_and_empty_keys_can_provision_without_checking_a_provider_key(self):
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                if empty:
                    (home / 'openrouter.key').write_bytes(b'')
                with mock.patch.dict(os.environ, {'ROUTER_HOME': str(home)}), \
                        mock.patch.object(key_store, 'check_key') as check:
                    result = work_account.provision(
                        authorize=lambda _: {'access_token': 'synthetic'},
                        post=lambda *args: issued())
                self.assertEqual(result, issued()['data']['key'])
                check.assert_not_called()

    def test_unreadable_saved_key_blocks_before_browser_or_issuance(self):
        authorize, post = mock.Mock(), mock.Mock()
        with mock.patch.object(Path, 'read_bytes', side_effect=PermissionError('private-path')):
            with self.assertRaises(work_account.SignInFailed) as raised:
                work_account.provision(authorize=authorize, post=post)
        self.assertNotIn('private-path', str(raised.exception))
        authorize.assert_not_called()
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
