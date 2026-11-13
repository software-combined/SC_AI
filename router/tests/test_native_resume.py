"""Saved access resumes after transient setup expiry without changing user choices."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_setup import module


class NativeResumeTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.native = module('native_setup')
        self.readiness = module('native_readiness')
        self.state = dict(clients='codex', openai_mode='subscription',
                          claude_mode='subscription',
                          setup=dict(nonce='synthetic', expires=0))
        self.save_state()
        (self.home / 'activation.json').write_text(json.dumps({'version': 2, 'clients': {
            'codex': {'openai_mode': 'subscription'}}}))
        (self.home / 'openrouter.key').write_text('synthetic-key')
        (self.home / 'openrouter.key').chmod(0o600)
        (self.home / 'config.toml').write_text('model = "owner-choice"\n')
        (self.home / 'plugins.json').write_text('{"enabled":false}')
        (self.home / 'setup-progress.json').write_text('{"started":1}')

    def save_state(self):
        (self.home / 'mixed-router-state.json').write_text(json.dumps(self.state))

    def snapshot(self):
        return {path.name: path.read_bytes() for path in self.home.iterdir()}

    def facts(self, *, ready=False, reply=True, confirmed=False, retry_pending=False):
        return dict(serving=True, service_key_usable=True,
            update=dict(retry_pending=retry_pending, required_action=None), onboarding=dict(
            ready=ready, choices_applied=self.readiness.choices_applied(self.home),
            clients={'codex': dict(plugins_available=True, reply_seen=reply,
                                   fresh_session_confirmed=confirmed)}))

    def test_expired_nonce_only_saved_key_resumes_without_mutation_or_installer(self):
        before = self.snapshot()
        with mock.patch.object(self.native, 'run_installer') as installer:
            window = mock.Mock()
            self.assertEqual(self.native._key(self.home, self.home, run=window), 0)
        installer.assert_not_called()
        window.assert_not_called()
        self.assertTrue(self.readiness.choices_applied(self.home))
        self.assertEqual(self.snapshot(), before)

    def test_live_session_and_unmatched_choices_stay_pending(self):
        self.state['setup']['expires'] = time.time() + 3600
        self.save_state()
        with mock.patch.object(self.native, 'run_installer') as installer:
            self.assertFalse(self.readiness.choices_applied(self.home))
            with self.assertRaises(ValueError):
                self.native._complete_choices(self.home, self.home)
        installer.assert_not_called()
        self.state.update(openai_mode='none', setup=dict(nonce='synthetic', expires=0))
        self.save_state()
        self.assertFalse(self.readiness.choices_applied(self.home))
        with mock.patch.object(self.native, 'run_installer',
                               return_value=SimpleNamespace(returncode=1)) as installer:
            with self.assertRaises(ValueError):
                self.native._complete_choices(self.home, self.home)
        installer.assert_called_once_with(self.home, self.home, ['--openai-mode', 'none'])

    def test_expired_session_without_usable_access_stays_pending(self):
        for key in ('', None):
            with self.subTest(key=key):
                path = self.home / 'openrouter.key'
                if key is None:
                    path.unlink()
                else:
                    path.write_text(key)
                before = self.snapshot()
                with mock.patch.object(self.native, 'run_installer') as installer:
                    window = mock.Mock()
                    with self.assertRaises(ValueError):
                        self.native._key(self.home, self.home, run=window)
                installer.assert_not_called()
                window.assert_not_called()
                self.assertEqual(self.snapshot(), before)

    def test_confirmation_and_ready_copy_name_the_actual_assistants(self):
        owner = self.native._completion
        for client, label in (('codex', 'Codex'), ('claude', 'Claude Code')):
            dialog = mock.Mock()
            dialog.confirm_result.return_value = True
            self.assertTrue(owner.confirm_client(self.home, dialog, client, True))
            prompt = dialog.confirm_result.call_args.args[0]
            self.assertIn('Keep %s open' % label, prompt)
            if client == 'claude':
                self.assertNotIn('Codex', prompt)
            self.assertIn(label + ' is connected', owner.ready_message({client: {}}, True))
        self.assertIn('Codex and Claude Code are connected',
                      owner.ready_message({'codex': {}, 'claude': {}}, True))

    def test_check_saved_key_has_one_safe_confirmation_and_keeps_current_chat(self):
        self._confirm_saved_key(False)

    def test_pending_background_check_does_not_block_saved_key_confirmation(self):
        self._confirm_saved_key(True)

    def _confirm_saved_key(self, retry_pending):
        dialog = mock.Mock()
        dialog.confirm_result.return_value = True
        before = self.snapshot()
        observed = [self.facts(retry_pending=retry_pending),
                    self.facts(ready=True, confirmed=True, retry_pending=retry_pending)]
        real_load = self.native.load
        with mock.patch.object(self.native, 'status', side_effect=observed), \
                mock.patch.object(self.native, 'load', side_effect=lambda name:
                    self.readiness if name == 'native_readiness' else real_load(name)), \
                mock.patch.object(self.readiness, 'successful_reply', return_value=True) as reply, \
                mock.patch.object(self.native, 'run_installer') as installer:
            self.native._check(self.home, self.home, dialog)
        installer.assert_not_called()
        dialog.confirm_result.assert_called_once()
        prompt = dialog.confirm_result.call_args.args[0]
        self.assertIn('Keep Codex open and keep your current model', prompt)
        self.assertIn('enabled SC tool', prompt)
        self.assertNotIn('OpenRouter', prompt)
        self.assertNotIn('reopen', prompt)
        self.assertEqual(dialog.confirm_result.call_args.kwargs['labels'], ('Confirm', 'Later'))
        dialog.confirm.assert_not_called()
        reply.assert_called_once_with(self.home, 1, 'codex')
        expected = 'Ready. Codex is connected. You can keep working in this chat.'
        if retry_pending:
            expected += ' An update check is pending. Updates will retry automatically.'
        self.assertEqual(dialog.message.call_args.args[0], expected)
        after = self.snapshot()
        progress = json.loads(after.pop('setup-progress.json'))
        before.pop('setup-progress.json')
        self.assertEqual(after, before)
        self.assertEqual(progress, dict(started=1, confirmed_clients=['codex']))

    def test_confirmed_saved_access_shows_ready_without_repeating_work(self):
        dialog = mock.Mock()
        before = self.snapshot()
        with mock.patch.object(self.native, 'status',
                               return_value=self.facts(ready=True, confirmed=True)), \
                mock.patch.object(self.native, 'run_installer') as installer:
            self.native._check(self.home, self.home, dialog)
        installer.assert_not_called()
        dialog.confirm_result.assert_not_called()
        dialog.confirm.assert_not_called()
        dialog.message.assert_called_once_with(
            'Ready. Codex is connected. You can keep working in this chat.', home=self.home)
        self.assertEqual(self.snapshot(), before)

    def test_later_or_missing_reply_cannot_mark_ready(self):
        for answer, seen in ((False, True), (None, True), (True, False)):
            with self.subTest(answer=answer, reply=seen):
                dialog = mock.Mock()
                dialog.confirm_result.return_value = answer
                before = self.snapshot()
                real_load = self.native.load
                with mock.patch.object(self.native, 'status', return_value=self.facts(reply=seen)), \
                        mock.patch.object(self.native, 'load', side_effect=lambda name:
                            self.readiness if name == 'native_readiness' else real_load(name)), \
                        mock.patch.object(self.readiness, 'successful_reply', return_value=seen):
                    self.native._check(self.home, self.home, dialog)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(any('Ready.' in call.args[0] for call in dialog.message.call_args_list))

    def test_known_resume_failure_uses_native_home_and_safe_fixed_message(self):
        self.state['openai_mode'] = 'none'
        self.save_state()
        dialog = mock.Mock()
        real_load = self.native.load
        with mock.patch.object(self.native, 'metadata'), \
                mock.patch.object(self.native, 'load', side_effect=lambda name:
                    dialog if name == 'native_dialog' else real_load(name)), \
                mock.patch.object(self.native, 'onboard', side_effect=lambda *args:
                    self.native._complete_choices(self.home, self.home)), \
                mock.patch.object(self.native, 'run_installer',
                                  return_value=SimpleNamespace(returncode=1)):
            self.assertEqual(self.native.main(['--resources', str(self.home),
                                               '--home', str(self.home), '--action', 'status']), 1)
        dialog.message.assert_called_once_with(
            'Your saved key is kept, but setup could not finish. Try Check setup again. '
            'If it still fails, contact Software Combined IT.', home=self.home.resolve())


if __name__ == '__main__':
    unittest.main()
