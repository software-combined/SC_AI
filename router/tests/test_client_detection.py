"""A manual run attaches the assistants it finds; nothing asks which.

Each client attaches on its own, so one that refuses never stops the others.
Scheduled updates, mode-only runs and a saved `none` choice attach nothing new;
Connect another assistant (`--connect-found`) overrides only `clients: none`.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.install_fixtures import install_mod
from tests.loading import load
from tests.test_client_choice import _full_install, _home, _install

choice = install_mod._client_choice
_ROOT = Path(__file__).resolve().parents[1]


def _clients(home):
    return set(install_mod._codex_config.read_receipt(home).get('clients', {}))


class DetectTests(unittest.TestCase):
    def setUp(self):
        # A fresh copy: the installer rig replaces detect() on the shared module.
        self.choice = load(_ROOT / 'packaging/client_choice.py', 'router_detect_probe')

    def test_detect_reports_each_installed_assistant_in_attach_order(self):
        desktop = mock.Mock()
        found = {'codex': '/bin/codex', 'claude': '/bin/claude'}
        with mock.patch.object(self.choice.client_executable, 'resolve', side_effect=found.get), \
                mock.patch.object(self.choice, '_load', return_value=desktop):
            self.assertEqual(self.choice.detect('darwin'), ('codex', 'claude', 'claude-desktop'))
        desktop.app_identity.assert_called_once_with('darwin')

    def test_unverified_or_missing_assistants_are_not_found(self):
        def resolve(name):
            if name == 'codex':
                raise self.choice.client_executable.DiscoveryError('identity_unavailable')
            return None
        desktop = mock.Mock(**{'app_identity.side_effect': OSError('not installed')})
        with mock.patch.object(self.choice.client_executable, 'resolve', side_effect=resolve), \
                mock.patch.object(self.choice, '_load', return_value=desktop):
            self.assertEqual(self.choice.detect('linux'), ())

    def test_only_a_plain_manual_run_looks(self):
        parse = install_mod.build_parser().parse_args
        receipts = mock.Mock(read_receipt=mock.Mock(return_value={'clients': {'codex': {}}}))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(self.choice, 'detect', return_value=('codex', 'claude')) as detect:
            self.assertEqual(self.choice.newly_found(parse([]), tmp, receipts, automatic=False), ('claude',))
            for argv, automatic in (([], True), (['--dry-run'], False), (['--clients', 'codex'], False),
                                    (['--desktop'], False), (['--client', 'none'], False)):
                with self.subTest(argv=argv, automatic=automatic):
                    self.assertEqual(self.choice.newly_found(parse(argv), tmp, receipts, automatic), ())
            detect.assert_called_once()


class DetectAndAttachTests(unittest.TestCase):
    def install(self, tmp, home, found, argv=(), env=None):
        with mock.patch.object(choice, 'detect', return_value=found):
            return _full_install(self, tmp, home, '1.0.0', list(argv), env)

    def test_both_found_attach_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            code, out, fake_home, claude = self.install(tmp, home, ('codex', 'claude'))
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'codex', 'claude'})
            self.assertTrue((fake_home / '.codex/config.toml').exists())
            self.assertTrue((claude / 'settings.json').exists())
            self.assertIn('Codex, Claude Code connected', out)
            self.assertEqual(install_mod.ensure_state(home)['clients'], 'both')

    def test_one_found_attaches_only_that_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            code, out, fake_home, _ = self.install(tmp, home, ('claude',))
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'claude'})
            self.assertFalse((fake_home / '.codex/config.toml').exists())

    def test_none_found_attaches_nothing_and_says_how_to_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            code, out, fake_home, claude = self.install(tmp, home, ())
            self.assertEqual(code, 0)
            self.assertIn('no assistant connected', out)
            self.assertEqual(_clients(home), set())
            self.assertFalse((fake_home / '.codex/config.toml').exists())
            self.assertFalse((claude / 'settings.json').exists())
            self.assertNotIn('clients', install_mod.ensure_state(home))  # No `none` choice is saved.
        notice = install_mod._completion.finish_message({})
        self.assertIn('No assistant was connected', notice)
        self.assertIn('choose Update or repair', notice)
        native = (_ROOT / 'packaging/native_setup.py').read_text()
        self.assertNotIn('webbrowser', native)  # No download page opens.

    def test_one_refusal_does_not_stop_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            with mock.patch.object(install_mod._claude_config, 'attach',
                                   side_effect=SystemExit('Claude settings are managed elsewhere')):
                code, out, fake_home, _ = self.install(tmp, home, ('codex', 'claude'))
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'codex'})
            self.assertTrue((fake_home / '.codex/config.toml').exists())
            self.assertIn('Claude Code was not connected', out)

    def test_an_attached_client_refusal_still_fails_after_the_others_attach(self):
        names, calls = ['codex', 'claude'], []
        codex = mock.Mock(**{'read_receipt.return_value': {'clients': {'codex': {}}}})
        with mock.patch.object(choice, 'attach_codex', side_effect=OSError('attachment readback failed')):
            with self.assertRaisesRegex(OSError, 'readback'):
                choice.attach_each(Path('/home'), {}, 'subscription', names, codex=codex, desktop=mock.Mock(),
                                   claude=lambda *a, **k: calls.append('claude'), python=None)
        self.assertEqual(calls, ['claude'])

    def test_claude_desktop_refusal_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            with mock.patch.object(install_mod._desktop_config, 'attach',
                                   side_effect=SystemExit('Quit Claude before setup')) as attach:
                code, out, fake_home, _ = self.install(tmp, home, ('codex', 'claude-desktop'))
            self.assertEqual(code, 0)
            attach.assert_called_once()
            self.assertEqual(_clients(home), {'codex'})
            self.assertNotIn('Claude desktop', out)
            self.assertNotIn('Quit Claude', out)

    def test_found_claude_desktop_attaches_on_its_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            code, out, _, _ = self.install(tmp, home, ('claude-desktop',))
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'claude-desktop'})
            profile = Path(tmp) / 'Claude-3p'
            entry = install_mod._desktop_config.applied_entry_path(profile)
            self.assertEqual(json.loads(entry.read_text())['inferenceProvider'], 'gateway')
            # Setup never switches Claude: it stays on its own subscription sign-in.
            self.assertIsNone(install_mod._desktop_config.read_desktop_config(profile)[0].get('deploymentMode'))

    def test_saved_none_is_respected(self):
        for saved in ({'clients': 'none'}, {'client': 'none'}):
            with self.subTest(saved=saved), tempfile.TemporaryDirectory() as tmp:
                home = _home(tmp)
                state = install_mod.ensure_state(home)
                install_mod._write_state(home, dict(state, **saved))
                with mock.patch.object(choice, 'detect', return_value=('codex', 'claude')) as detect:
                    code, _, _, fake_home, claude = _install(tmp, home, [])
                self.assertEqual(code, 0)
                detect.assert_not_called()
                self.assertEqual(_clients(home), set())
                self.assertFalse((fake_home / '.codex/config.toml').exists())

    def test_a_damaged_saved_choice_falls_back_to_found_assistants(self):
        args = mock.Mock(client=None, clients=None, desktop=False, openai_mode=None,
                         claude_mode=None, anthropic_mode=None, found=('codex',))
        receipts = mock.Mock(read_receipt=mock.Mock(return_value={}))
        with tempfile.TemporaryDirectory() as tmp:
            resolved = choice.resolve(args, tmp, {'clients': ['codex']}, receipts, lambda home, state: None)
        self.assertEqual(resolved[1], 'codex')

    def test_manual_rerun_attaches_a_newly_installed_assistant(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = _home(tmp)
            _install(tmp, home, ['--clients', 'codex'])
            with mock.patch.object(choice, 'detect', return_value=('codex', 'claude')):
                code, out, _, _, claude = _install(tmp, home, [])
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'codex', 'claude'})
            self.assertTrue((claude / 'settings.json').exists())

    def test_a_found_assistant_that_refused_is_not_saved_for_scheduled_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            with mock.patch.object(choice, 'attach_codex', side_effect=OSError('Codex settings are locked')):
                code, out, fake_home, _ = self.install(tmp, home, ('codex',))
            self.assertEqual(code, 0)
            self.assertIn('Codex was not connected', out)
            self.assertNotIn('clients', install_mod.ensure_state(home))
            # The refusal clears; a scheduled update still never connects a new assistant.
            code, _, _, _ = _full_install(self, tmp, home, '1.0.1', [], {'ROUTER_AUTOMATIC_UPDATE': '1'})
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), set())
            self.assertFalse((fake_home / '.codex/config.toml').exists())

    def test_a_bare_desktop_run_keeps_the_saved_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = str(Path(tmp).resolve())
            home = _home(tmp)
            _install(tmp, home, ['--clients', 'codex'])
            code, _, _, _, _ = _install(tmp, home, ['--desktop'])
            self.assertEqual(code, 0)
            self.assertEqual(install_mod.ensure_state(home)['clients'], 'codex')
            with mock.patch.object(choice, 'detect', return_value=('codex', 'claude')):
                code, out, _, _, claude = _install(tmp, home, [])
            self.assertEqual(code, 0)
            self.assertEqual(_clients(home), {'codex', 'claude', 'claude-desktop'})
            self.assertTrue((claude / 'settings.json').exists())
            self.assertEqual(install_mod.ensure_state(home)['clients'], 'both')

    def test_scheduled_update_attaches_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            self.install(tmp, home, ('codex',))
            with mock.patch.object(choice, 'detect', return_value=('codex', 'claude')) as detect:
                code, _, _, claude = _full_install(self, tmp, home, '1.0.1', [],
                                                   {'ROUTER_AUTOMATIC_UPDATE': '1'})
            self.assertEqual(code, 0)
            detect.assert_not_called()
            self.assertEqual(_clients(home), {'codex'})
            self.assertFalse((claude / 'settings.json').exists())


    def test_a_saved_clients_none_stays_on_plain_manual_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'router'
            self.install(tmp, home, (), ['--clients', 'codex'])
            self.install(tmp, home, (), ['--clients', 'none', '--desktop'])
            self.assertEqual(install_mod.ensure_state(home)['clients'], 'none')
            for version in ('1.0.1', '1.0.2'):
                with mock.patch.object(choice, 'detect', return_value=('codex', 'claude')):
                    code, _, _, _ = _full_install(self, tmp, home, version, [])
                self.assertEqual(code, 0)
                self.assertEqual(_clients(home), {'codex', 'claude-desktop'})
                self.assertEqual(install_mod.ensure_state(home)['clients'], 'none')

    def test_connect_another_assistant_overrides_only_a_saved_clients_none(self):
        for saved, attached in (({'clients': 'none'}, {'claude'}),
                                ({'client': 'none', 'clients': 'none'}, set())):
            with self.subTest(saved=saved), tempfile.TemporaryDirectory() as tmp:
                home = _home(tmp)
                install_mod._write_state(home, dict(install_mod.ensure_state(home), **saved))
                with mock.patch.object(choice, 'detect', return_value=('claude',)):
                    code, _, _, _, claude = _install(tmp, home, ['--connect-found'])
                self.assertEqual(code, 0)
                self.assertEqual(_clients(home), attached)
                self.assertEqual((claude / 'settings.json').exists(), bool(attached))
                self.assertEqual(install_mod.ensure_state(home)['clients'], 'claude' if attached else 'none')

    def test_a_mode_only_run_attaches_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = _home(tmp)
            _install(tmp, home, ['--clients', 'codex'])
            with mock.patch.object(choice, 'detect', return_value=('claude',)) as detect, \
                    mock.patch.object(install_mod, 'platform_backend'):
                code, out, _, _, claude = _install(tmp, home, ['--claude-mode', 'none'])
            self.assertEqual(code, 0)
            detect.assert_not_called()
            self.assertNotIn('Claude Code', out)  # Not even tried.
            self.assertEqual(_clients(home), {'codex'})
            self.assertFalse((claude / 'settings.json').exists())

    def test_clients_none_with_attachments_names_what_stays_connected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = _home(tmp)
            _install(tmp, home, ['--clients', 'codex'])
            code, out, _, _, _ = _install(tmp, home, ['--clients', 'none'])
            self.assertEqual(code, 0)
            self.assertNotIn('no assistant connected', out)
            self.assertIn('no client changes; Codex still connected', out)
            self.assertEqual(_clients(home), {'codex'})


    def test_a_missing_saved_choice_is_not_read_as_codex(self):
        notice, names = install_mod._svc.notice, ['Synthetic: Model One']
        for found in ((), ('claude-desktop',)):
            with self.subTest(found=found), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp) / 'router'
                self.install(tmp, home, found)
                state = install_mod.ensure_state(home)
                self.assertNotIn('clients', state)
                # The scheduled model announcement offers no Codex dialog.
                self.assertFalse(install_mod._updater._codex_attached(home, state))
                # A later release's pending notice names no Codex restart.
                self.assertTrue(notice.record(home, '1.0.0', '1.0.1', names=names))
                clients = json.loads((home / notice.NOTICE_FILE).read_text())['clients']
                command = notice.dialog_command('1.0.1', 'darwin', which=lambda _: '/usr/bin/osascript',
                                                icon='', clients=clients, names=names)
                self.assertNotIn('Codex', ' '.join(command))
                if not found:  # No receipt and no client wanted: nothing to verify.
                    status = install_mod._delivery._load('update_status')
                    self.assertEqual(install_mod._delivery.assistant_status(home, state), status.READY)


if __name__ == '__main__':
    unittest.main()
