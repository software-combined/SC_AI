"""Setup ends with one notice; a re-run that changes nothing stays quiet."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_router import key_prompt
from tests.test_native_setup import module, resources


class NativeFinishTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = resources(self.root / 'download')
        self.home = self.root / 'home'
        self.home.mkdir()

    def onboard(self, clients, stdout, platform='darwin', serving=True):
        setup = module('native_setup')
        dialog = mock.MagicMock()
        dialog.Progress.return_value.__enter__.return_value.cancelled = False
        dialog.message.return_value = True
        owners = {name: mock.Mock() for name in ('desktop_menu', 'native_resources', 'atomic_write',
                                                'native_controller', 'native_shortcuts', 'notice')}
        owners['native_resources'].current.return_value = self.source
        owners['native_dialog'] = dialog
        owners['codex_config'] = SimpleNamespace(read_receipt=lambda home: {'clients': clients})
        original = setup.load
        with mock.patch.object(setup, 'load', side_effect=lambda name: owners.get(name) or original(name)), \
                mock.patch.object(setup, 'sys', SimpleNamespace(platform=platform)), \
                mock.patch.object(setup, 'retained', return_value=self.source), \
                mock.patch.object(setup, 'run_installer',
                                  return_value=SimpleNamespace(returncode=0, stdout=stdout)), \
                mock.patch.object(setup, '_select', return_value=['--clients', 'codex']) as select, \
                mock.patch.object(setup, '_missing_assistant', return_value=False), \
                mock.patch.object(setup, 'record_channel') as channel, \
                mock.patch.object(setup, 'status', return_value={'serving': serving}), \
                mock.patch.object(setup, '_key', return_value=0) as key:
            self.assertEqual(setup.onboard(self.source, self.home, 'install'), 0)
        key.assert_called_once_with(self.source, self.home, confirm=False)
        dialog.choose.assert_not_called()
        dialog.confirm.assert_not_called()
        dialog.confirm_result.assert_not_called()
        return dialog, owners['notice'], select, channel

    def test_fresh_install_shows_one_client_aware_notice_after_the_access_step(self):
        cases = (({'codex': {}}, 'SCG Router is ready. Quit and reopen Codex to use it.'),
                 ({'claude': {}}, 'SCG Router is ready. Restart Claude Code to use it.'),
                 ({'codex': {}, 'claude': {}}, 'SCG Router is ready for Codex and Claude Code. '
                  'Quit and reopen Codex. Restart Claude Code.'),
                 ({'codex': {}, 'claude': {}, 'claude-desktop': {}},
                  'SCG Router is ready for Codex, Claude Code and Claude desktop. Quit and reopen Codex. '
                  'Restart Claude Code. Quit and reopen Claude. To use OpenRouter models in Claude, '
                  'choose Claude, then OpenRouter, in the SCG Router menu.'),
                 ({}, 'No assistant was found. Install Codex or Claude, then open SCG Router again.'))
        for platform in ('darwin', 'win32'):
            for clients, expected in cases:
                with self.subTest(platform=platform, clients=sorted(clients)):
                    dialog, notice, select, channel = self.onboard(
                        clients, 'router 1.2.0; health ok\n', platform)
                    select.assert_called_once()
                    channel.assert_called_once()
                    dialog.message.assert_called_once_with(expected, home=self.home)
                    notice.suppress_closed_client_restart.assert_called_once_with(self.home)

    def test_a_router_that_is_not_serving_gets_the_repair_notice_instead(self):
        repair = 'SCG Router needs repair. Open the SCG Router menu and choose Update or repair.'
        dialog, notice, _, _ = self.onboard({'codex': {}}, 'installed 1.0.1; health verified\n', serving=False)
        dialog.message.assert_called_once_with(repair, home=self.home)
        notice.suppress_closed_client_restart.assert_not_called()
        (self.home / 'current').write_text('1.2.0\n')
        (self.home / 'mixed-router-state.json').write_text(json.dumps({'clients': 'codex'}))
        dialog, _, _, _ = self.onboard({'codex': {}}, 'up to date 1.2.0\n', serving=False)
        dialog.message.assert_called_once_with(repair, home=self.home)

    def test_rerun_when_already_set_up_shows_only_up_to_date(self):
        (self.home / 'current').write_text('1.2.0\n')
        (self.home / 'mixed-router-state.json').write_text(json.dumps({'clients': 'codex'}))
        dialog, notice, select, channel = self.onboard({'codex': {}}, 'up to date 1.2.0\n')
        select.assert_not_called()
        dialog.dialog.ask.assert_not_called()
        channel.assert_not_called()  # An older package must not fail or adopt its channel.
        dialog.message.assert_called_once_with('SCG Router is up to date.', home=self.home)
        notice.suppress_closed_client_restart.assert_not_called()

    def test_finish_wording_never_claims_a_checked_reply_or_misnames_clients(self):
        owner = module('setup_completion')
        claude = owner.finish_message({'claude': {}})
        self.assertNotIn('Codex', claude)
        desktop = owner.finish_message({'claude-desktop': {}})
        self.assertIn('Quit and reopen Claude', desktop)
        self.assertIn('choose Claude, then OpenRouter', desktop)
        for clients in ({'codex': {}}, {'claude': {}}, {'claude-desktop': {}}):
            self.assertNotIn('repl', owner.finish_message(clients).lower())


class KeyConfirmationTests(unittest.TestCase):
    def test_setup_key_window_skips_its_own_confirmation(self):
        setup = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            source, home = resources(Path(temporary) / 'download'), Path(temporary) / 'home'
            home.mkdir()
            (home / 'current').write_text('1.2.0\n')
            (home / 'mixed-router-state.json').write_text(json.dumps(dict(
                clients='codex', port=1, token='synthetic', setup=dict(nonce='test', expires=2000))))
            for confirm in (True, False):
                run = mock.Mock(return_value=SimpleNamespace(returncode=2))
                with mock.patch.object(setup.time, 'time', return_value=1000):
                    self.assertEqual(setup._key(source, home, run=run, confirm=confirm), 2)
                env = run.call_args.kwargs['env']
                self.assertEqual(env.get('ROUTER_NO_KEY_CONFIRM'), None if confirm else '1')

    def test_window_without_confirmation_saves_quietly(self):
        url = 'http://127.0.0.1:1/t/setup/n'
        with mock.patch.object(key_prompt.key_dialog, 'collect', return_value={'key': 'synthetic'}), \
                mock.patch.object(key_prompt, 'submit', return_value=(200, {'ok': True})), \
                mock.patch.object(key_prompt.key_dialog, 'message') as message:
            self.assertEqual(key_prompt.run_window(url, tool_path='/dialog', platform_name='darwin',
                                                   confirm=False), 0)
            message.assert_not_called()
            self.assertEqual(key_prompt.run_window(url, tool_path='/dialog', platform_name='darwin'), 0)
            message.assert_called_once()
        for value, confirm in (('1', False), ('', True)):
            with mock.patch.dict(os.environ, {'ROUTER_NO_KEY_CONFIRM': value}), \
                    mock.patch.object(key_prompt, 'run_window', return_value=0) as window:
                self.assertEqual(key_prompt.main([url]), 0)
            self.assertEqual(window.call_args.kwargs['confirm'], confirm)


class RepairCloseTests(unittest.TestCase):
    def owner(self, clients, mode='3p'):
        owner, dialog, platform, switch = module('repair_ui'), mock.Mock(), mock.Mock(), mock.Mock()
        receipts = SimpleNamespace(read_receipt=lambda home: {'clients': clients})
        dialog.confirm_result.return_value = False
        switch.SwitchError = type('SwitchError', (Exception,), {})
        switch.attached_profile.return_value = (None, {'deploymentMode': mode})
        owner._load = lambda name: {'codex_config': receipts, 'native_dialog': dialog,
                                    'claude_desktop_platform': platform,
                                    'claude_desktop_switch': switch}[name]
        return owner, dialog, platform

    def test_repair_that_rewrites_nothing_does_not_ask_to_close_assistants(self):
        for clients in ({'codex': {}, 'claude': {}}, {'codex': {}, 'claude-desktop': {}}):
            owner, dialog, platform = self.owner(clients, mode='1p')
            self.assertTrue(owner.close_assistants(Path('/synthetic/home'), owned=True))
            dialog.confirm_result.assert_not_called()
            platform.request_stop.assert_not_called()

    def test_claude_desktop_on_openrouter_still_closes_before_its_entry_changes(self):
        owner, dialog, platform = self.owner({'codex': {}, 'claude-desktop': {}})
        self.assertFalse(owner.close_assistants(Path('/synthetic/home'), owned=True))
        question = dialog.confirm_result.call_args.args[0]
        self.assertIn('Claude desktop', question)
        self.assertNotIn('Codex', question)
        platform.request_stop.assert_not_called()

    def test_repair_passes_attachment_ownership_to_the_close_question(self):
        delivery, repair = module('install_delivery'), mock.Mock()
        original = delivery._load

        def load_with_repair_ui(name):
            return repair if name == 'repair_ui' else original(name)
        for status, owned in (('ready', True), ('failed', False), ('unknown', False)):
            with mock.patch.object(delivery, 'assistant_status', return_value=status), \
                    mock.patch.object(delivery, '_load', side_effect=load_with_repair_ui):
                delivery.close_assistants(Path('/synthetic/home'))
            repair.close_assistants.assert_called_with(Path('/synthetic/home'), owned=owned)


if __name__ == '__main__':
    unittest.main()
