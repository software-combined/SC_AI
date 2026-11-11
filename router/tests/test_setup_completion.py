"""Late answers use the owning installer without another key or assistant restart."""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_router import availability, key_store, setup as key_setup
from tests.install_fixtures import install_mod
from tests.test_client_choice import _full_install, _home, _install
from tests.test_native_setup import module, resources


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(install_mod, 'platform_backend'))

    def test_popup_wait_is_bounded_and_url_is_only_on_stdin(self):
        owner = module('setup_completion')
        process = mock.Mock()
        process.wait.return_value = 0
        url = 'http://127.0.0.1:1/synthetic/setup/nonce'
        out = io.StringIO()
        with mock.patch.object(owner.subprocess, 'Popen', return_value=process) as launch, \
                contextlib.redirect_stdout(out):
            self.assertEqual(owner.open_window('python', Path('/home'), Path('/release'), url, 'codex'), 0)
        process.wait.assert_called_once_with(timeout=900)
        process.stdin.write.assert_called_once_with((url + '\n').encode())
        process.stdin.close.assert_called_once()
        self.assertNotIn(url, str(launch.call_args))
        self.assertNotIn(url, out.getvalue())
        process.wait.side_effect = subprocess.TimeoutExpired('popup', 900)
        with mock.patch.object(owner.subprocess, 'Popen', return_value=process):
            self.assertIsNone(owner.open_window('python', Path('/home'), Path('/release'), url, 'codex'))
        process.terminate.assert_not_called()

    def test_cancel_unavailable_and_automatic_runs_leave_honest_pending(self):
        owner = module('setup_completion')
        for code in (None, 1, 2, 3):
            with self.subTest(code=code), mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(owner.sys, 'platform', 'darwin'), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                popup, complete = mock.Mock(return_value=code), mock.Mock()
                owner.finish(SimpleNamespace(update=False), '/home', 'python', 'synthetic', 'codex', popup, complete)
                self.assertIn('Setup is pending', out.getvalue())
                popup.assert_called_once()
                complete.assert_not_called()
        for automatic, platform in ((True, 'darwin'), (False, 'linux')):
            with mock.patch.dict(os.environ, {}, clear=True), \
                    mock.patch.object(owner.sys, 'platform', platform), contextlib.redirect_stdout(io.StringIO()):
                popup, complete = mock.Mock(), mock.Mock()
                owner.finish(SimpleNamespace(update=automatic), '/home', 'python', 'synthetic', 'codex', popup, complete)
                popup.assert_not_called()
                complete.assert_not_called()

    def test_readiness_requires_saved_modes_to_match_all_attached_clients(self):
        ready = module('native_readiness')
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            (home / 'mixed-router-state.json').write_text('{"claude_mode":"none"}')
            receipt = home / 'activation.json'
            receipt.write_text(json.dumps({'version': 2, 'clients': {
                'claude-desktop': {'claude_mode': 'subscription'}}}))
            self.assertFalse(ready.choices_applied(home))
            receipt.write_text(json.dumps({'version': 2, 'clients': {
                'claude-desktop': {'claude_mode': 'none'}}}))
            self.assertTrue(ready.choices_applied(home))
            (home / 'mixed-router-state.json').write_text(
                '{"claude_mode":"none","setup":{"nonce":"synthetic","expires":0}}')
            self.assertFalse(ready.choices_applied(home))  # A failed close cannot become Ready after expiry.
            with self.assertRaisesRegex(ValueError, 'contact Software Combined IT'):
                module('native_setup')._complete_choices(home, home)

    def test_completion_refuses_unreadable_state_without_creating_or_repairing_it(self):
        for contents in (None, '{', '[]'):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as temporary:
                home = Path(temporary)
                path = home / 'mixed-router-state.json'
                if contents is not None:
                    path.write_text(contents)
                with mock.patch.object(install_mod, '_attach_current') as attach:
                    with self.assertRaises(install_mod._svc._state.StateUnreadable):
                        install_mod._complete_choices(home, 'python')
                    attach.assert_not_called()
                self.assertEqual(path.read_text() if path.exists() else None, contents)

    def test_claude_only_late_answer_leaves_codex_and_disabled_plugins_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home, path = root / 'router', root / 'fakehome/.codex/config.toml'
            path.parent.mkdir(parents=True)
            path.write_text('model = "owner-choice"\n')
            plugins = root / 'claude/settings.json'
            plugins.parent.mkdir()
            plugins.write_text('{"enabledPlugins":{"scg-review@scg-agent-plugins":false}}')
            def window(*args):
                self.assertEqual(install_mod._codex_config.read_receipt(home)['clients']['claude']['claude_mode'],
                                 'subscription')
                key_store.store_key(home, 'synthetic-key')
                state = json.loads((home / 'mixed-router-state.json').read_text())
                with mock.patch.object(availability, 'current_key', return_value=None):
                    self.assertTrue(key_setup._finish_setup(state, home, claude_mode='none'))
                return 0
            with mock.patch.object(install_mod, '_open_key_window', side_effect=window), \
                    mock.patch.object(install_mod._operator, 'listing', return_value={
                        'data': [{'id': 'synthetic-sonnet', 'anthropic_family_tier': 'sonnet'}]}):
                self.assertEqual(_full_install(self, root, home, '1.0.0', ['--clients', 'claude'],
                    {'ROUTER_NO_KEY_WINDOW': '0'})[0], 0)
            self.assertEqual(install_mod._codex_config.read_receipt(home)['clients']['claude']['claude_mode'], 'none')
            self.assertNotIn('codex', install_mod._codex_config.read_receipt(home)['clients'])
            self.assertEqual(path.read_text(), 'model = "owner-choice"\n')
            self.assertIs(json.loads(plugins.read_text())['enabledPlugins']['scg-review@scg-agent-plugins'], False)

    def test_cli_attaches_before_late_answer_and_preserves_owner_pick(self):
        for picked in (None, 'external/owner-choice'):
            with self.subTest(picked=picked), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                home, path = root / 'router', root / 'fakehome/.codex/config.toml'
                path.parent.mkdir(parents=True)
                original = 'approval_policy = "never"\n'
                if picked:
                    original += 'model = "' + picked + '"\nmodel_reasoning_effort = "high"\n'
                path.write_text(original)
                def window(python, selected, url, clients):
                    self.assertEqual(selected, home)
                    self.assertEqual(install_mod._codex_config.codex_attachment(home)['openai_mode'],
                                     'subscription')
                    key_store.store_key(home, 'synthetic-key')
                    state = json.loads((home / 'mixed-router-state.json').read_text())
                    with mock.patch.object(availability, 'current_key', return_value=None):
                        self.assertTrue(key_setup._finish_setup(state, home, mode='none'))
                    self.assertEqual(state['openai_mode'], 'none')
                    return 0
                with mock.patch.object(install_mod, '_open_key_window', side_effect=window) as popup, \
                        mock.patch.object(install_mod._delivery, 'close_assistants') as close:
                    code, _, _, _ = _full_install(self, root, home, '1.0.0', ['--clients', 'codex'],
                                                  {'ROUTER_NO_KEY_WINDOW': '0'})
                self.assertEqual(code, 0)
                popup.assert_called_once()
                close.assert_not_called()
                self.assertEqual(install_mod._codex_config.codex_attachment(home)['openai_mode'], 'none')
                doc = tomllib.loads(path.read_text())
                self.assertEqual(doc['model'], picked or install_mod._codex_config.DEFAULT_MODEL)
                self.assertEqual(doc['approval_policy'], 'never')
                self.assertIn(original, [p.read_text() for p in home.glob('config-before-*.toml')])
                self.assertNotIn('setup', json.loads((home / 'mixed-router-state.json').read_text()))

    def test_saved_key_native_completion_covers_both_clients_without_window(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, source = root / 'router', resources(root / 'Resources')
            home.mkdir()
            (home / 'openrouter.key').write_text('synthetic-key')
            (home / 'openrouter.key').chmod(0o600)
            (home / 'mixed-router-state.json').write_text(json.dumps(
                dict(openai_mode='none', claude_mode='none')))
            (home / 'activation.json').write_text(json.dumps({'version': 2, 'clients': {
                'codex': {'openai_mode': 'subscription'}, 'claude': {'claude_mode': 'subscription'}}}))
            with mock.patch.object(native, 'run_installer', return_value=SimpleNamespace(returncode=0)) as apply:
                run = mock.Mock()
                self.assertEqual(native._key(source, home, run=run), 0)
            run.assert_not_called()
            apply.assert_called_once_with(source, home,
                ['--openai-mode', 'none', '--claude-mode', 'none'])

    def test_failed_completion_keeps_key_answer_and_retries_only_modes(self):
        self._failed_completion('attach')
        self._failed_completion('health')

    def _failed_completion(self, failure):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = _home(root)
            _install(root, home, ['--clients', 'codex'])
            key_store.store_key(home, 'synthetic-key')
            state = json.loads((home / 'mixed-router-state.json').read_text())
            state['openai_mode'] = 'none'
            (home / 'mixed-router-state.json').write_text(json.dumps(state))
            ready = install_mod._current_ready
            def unhealthy(*args, **kwargs):
                with mock.patch.object(install_mod, 'wait_version', return_value=False):
                    return ready(*args, **kwargs)
            patch = (mock.patch.object(install_mod._client_choice, 'attach_codex', side_effect=OSError('synthetic'))
                     if failure == 'attach' else mock.patch.object(install_mod, '_current_ready', side_effect=unhealthy))
            with patch:
                with self.assertRaises((OSError, SystemExit)):
                    _install(root, home, ['--openai-mode', 'none'])
            self.assertEqual((home / 'openrouter.key').read_text().strip(), 'synthetic-key')
            self.assertEqual(json.loads((home / 'mixed-router-state.json').read_text())['openai_mode'], 'none')
            with mock.patch.object(install_mod, '_open_key_window') as popup, \
                    mock.patch.object(install_mod._delivery, 'close_assistants') as close:
                self.assertEqual(_install(root, home, ['--openai-mode', 'none'])[0], 0)
            popup.assert_not_called()
            close.assert_not_called()
            self.assertEqual(install_mod._codex_config.codex_attachment(home)['openai_mode'], 'none')

    def test_check_setup_applies_runtime_saved_choices_before_ready_or_test_reply(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home, source = _home(root), resources(root / 'Resources')
            _install(root, home, ['--clients', 'codex'])
            key_store.store_key(home, 'synthetic-key')
            state = json.loads((home / 'mixed-router-state.json').read_text())
            with mock.patch.object(availability, 'current_key', return_value=None):
                self.assertTrue(key_setup._finish_setup(state, home, mode='none'))
            def status(*args):
                applied = install_mod._codex_config.codex_attachment(home)['openai_mode'] == 'none'
                return dict(serving=True, service_key_usable=True,
                            onboarding=dict(ready=applied, clients={}, choices_applied=applied))
            def apply(*args):
                return SimpleNamespace(returncode=_install(root, home, args[2])[0])
            dialog = mock.Mock()
            with mock.patch.object(native, 'status', side_effect=status), \
                    mock.patch.object(native, 'run_installer', side_effect=apply) as installer, \
                    mock.patch.object(install_mod, '_open_key_window') as popup:
                native._check(source, home, dialog)
            installer.assert_called_once_with(source, home, ['--openai-mode', 'none'])
            popup.assert_not_called()
            dialog.confirm.assert_not_called()
            self.assertIn('Ready.', dialog.message.call_args.args[0])

    def test_native_completion_follows_all_receipts_after_adding_claude(self):
        self._native_additive(False)
        self._native_additive(True)

    def _native_additive(self, desktop):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home, source = _home(root), resources(root / 'Resources')
            _install(root, home, ['--clients', 'both'])
            _install(root, home, ['--clients', 'claude'] + (['--desktop'] if desktop else []))
            key_store.store_key(home, 'synthetic-key')
            state = json.loads((home / 'mixed-router-state.json').read_text())
            self.assertEqual(state['clients'], 'claude')
            with mock.patch.object(availability, 'current_key', return_value=None):
                self.assertTrue(key_setup._finish_setup(state, home, mode='none'))
            def installer_process(argv, **kwargs):
                code, output, _, _, _ = _install(root, home, argv[2:],
                    {'CLAUDE_USER_DATA_DIR': str(root / 'new-default')} if desktop else None)
                return SimpleNamespace(returncode=code, stdout=output)
            invoke = native.run_installer
            with mock.patch.object(native, 'run_installer', side_effect=lambda *args:
                    invoke(*args, run=installer_process)), mock.patch.object(install_mod, '_open_key_window') as popup:
                self.assertEqual(native._key(source, home), 0)
            popup.assert_not_called()
            attached = install_mod._codex_config.read_receipt(home)['clients']
            self.assertEqual(attached['codex']['openai_mode'], 'none')
            self.assertEqual(attached['claude']['claude_mode'], 'subscription')
            self.assertFalse((root / 'new-default').exists())

    def test_never_switched_variant_survives_none_then_subscription(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            home = _home(root)
            for mode in ('subscription', 'none', 'subscription'):
                self.assertEqual(_install(root, home, ['--clients', 'codex', '--openai-mode', mode])[0], 0)
                entry = install_mod._codex_config.codex_attachment(home)
                self.assertNotIn('variant', entry)
            config = tomllib.loads((root / 'fakehome/.codex/config.toml').read_text())
            self.assertNotIn('model_providers', config)


if __name__ == '__main__':
    unittest.main()
