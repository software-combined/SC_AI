"""The post-install restart offer reuses one recorded Windows notice."""
import contextlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_setup import module, resources


class SetupRestartTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.owner = module('setup_restart')
        self.notice = mock.Mock()
        self.notice.record_client_change.return_value = True
        self.notice.current_restart.return_value = False
        self.notice_windows = mock.Mock()
        self.notice_windows.show.return_value = True
        self.platform = mock.Mock()
        self.platform.is_running.return_value = True
        self.app = object()
        self.codex = mock.Mock(CODEX=self.app)
        self.service = mock.Mock()
        self.service.current_version.return_value = '1.3.35'
        self.service.install_lock.return_value = contextlib.nullcontext(True)
        real = self.owner.load
        owners = dict(notice=self.notice, notice_windows=self.notice_windows,
                      claude_desktop_platform=self.platform, codex_desktop_switch=self.codex,
                      service=self.service)
        self.enterContext(mock.patch.object(self.owner, 'load',
                            side_effect=lambda name: owners.get(name) or real(name)))
        self.enterContext(mock.patch.object(self.owner, 'target', return_value='changed'))
        self.enterContext(mock.patch.object(self.owner.sys, 'platform', 'win32'))

    def test_malformed_receipt_can_be_repaired(self):
        owner = module('setup_restart')
        receipt = mock.Mock()
        with mock.patch.object(owner, 'load', return_value=receipt):
            for clients in ([], {'codex': []}, {'codex': None}):
                with self.subTest(clients=clients):
                    receipt.read_receipt.return_value = {'clients': clients}
                    self.assertIsNone(owner.target(self.home))

    def test_changed_target_records_one_event_and_uses_existing_dialog_owner(self):
        self.assertTrue(self.owner.offer(self.home, 'before', True))
        self.assertFalse(self.owner.offer(self.home, 'changed', True))
        self.notice.record_client_change.assert_called_once()
        args = self.notice.record_client_change.call_args.args
        self.assertEqual(args[:2], (self.home, '1.3.35'))
        self.assertEqual(args[2], '1.3.35')
        self.notice_windows.show.assert_called_once_with(self.home, setup_completion=True)

    def test_closed_or_unidentified_client_does_not_queue_a_restart(self):
        self.assertFalse(self.owner.offer(self.home, 'before', False))
        self.notice.suppress_closed_client_restart.assert_called_once_with(self.home)
        self.notice_windows.show.assert_not_called()
        self.notice.reset_mock()
        self.notice_windows.reset_mock()
        self.platform.is_running.return_value = False
        self.assertFalse(self.owner.offer(self.home, 'before', True))
        self.notice.suppress_closed_client_restart.assert_called_once_with(self.home)
        self.notice_windows.show.assert_not_called()

    def _shared_notice_helpers(self):
        notice = module('notice')
        old, current = module('notice_windows'), module('notice_windows')
        self.notice.record_client_change.side_effect = notice.record_client_change
        self.notice.current_restart.side_effect = notice.current_restart
        self.notice_windows.show.side_effect = current.show
        self.service.install_lock.side_effect = module('service').install_lock
        dialog, text = mock.Mock(), module('notice_text')
        dialog.show.return_value = False
        self.enterContext(mock.patch.object(text, 'pending_names', return_value=[]))
        self.enterContext(mock.patch.object(text, 'acknowledge'))
        owners = dict(service=self.service, windows_dialog=dialog, notice_text=text,
                      claude_desktop_platform=self.platform)
        for helper in (old, current):
            original = helper.load
            self.enterContext(mock.patch.object(helper, 'load', side_effect=lambda name, load=original:
                              owners.get(name) or load(name)))
        notice.record(self.home, '1.3.34', '1.3.35', 'codex', names=['Example: Model 1'])
        notice.record_attachment(self.home, '1.3.35', 'synthetic-attachment')
        return old, current, dialog

    def test_first_later_survives_model_attachment_and_completion_helper_handoff(self):
        old, current, dialog = self._shared_notice_helpers()
        self.assertTrue(old.show(self.home))
        path = self.home / 'update-notice.json'
        first_later = path.read_bytes()
        self.assertEqual(json.loads(first_later)['restart_result'], 'later')
        notice = module('notice')
        self.assertFalse(notice.record(self.home, '1.3.34', '1.3.35', 'codex', names=['Example: Model 1']))
        self.assertFalse(notice.record_attachment(self.home, '1.3.35', 'synthetic-attachment'))
        self.assertTrue(self.owner.offer(self.home, 'before', True))
        self.assertTrue(self.owner.offer(self.home, 'before', True))
        self.assertEqual(dialog.show.call_count, 1)
        self.assertEqual(path.read_bytes(), first_later)
        self.assertTrue(self.owner.offer(self.home, 'changed', True))
        self.assertFalse(current.offer(self.home, spawn=mock.Mock()))
        self.platform.request_stop.assert_not_called()
        self.platform.open_app.assert_not_called()
        # A genuinely newer installed generation gets one useful optional offer.
        self.service.current_version.return_value = '1.3.36'
        self.assertTrue(self.owner.offer(self.home, 'before', True))
        self.assertTrue(self.owner.offer(self.home, 'before', True))
        self.assertEqual(dialog.show.call_count, 2)
        self.assertIn("We couldn't confirm Codex loaded the changes", dialog.show.call_args.args[0])
        self.assertEqual(dialog.show.call_args.kwargs['labels'], ('Restart Codex', 'Later'))
        self.assertEqual(json.loads(path.read_text())['restart_result'], 'later')

    def test_active_earlier_offer_keeps_its_record_and_first_later(self):
        old, current, dialog = self._shared_notice_helpers()
        path = self.home / 'update-notice.json'
        pending = path.read_bytes()
        def later(*args, **kwargs):
            self.assertTrue(self.owner.offer(self.home, 'changed', True))
            self.assertEqual(path.read_bytes(), pending)
            return False
        dialog.show.side_effect = later
        self.assertTrue(old.show(self.home))
        self.assertEqual(dialog.show.call_count, 1)
        self.assertEqual(json.loads(path.read_text())['restart_result'], 'later')
        self.assertTrue(self.owner.offer(self.home, 'changed', True))
        self.assertEqual(dialog.show.call_count, 1)
        self.platform.request_stop.assert_not_called()
        self.platform.open_app.assert_not_called()

    def test_unchanged_target_joins_current_notice_before_automatic_confirmation(self):
        old, current, restart_dialog = self._shared_notice_helpers()
        setup = module('native_setup')
        source = resources(self.home / 'resources', version='1.3.35', channel='beta')
        (self.home / 'releases/1.3.35').mkdir(parents=True)
        (self.home / 'current').write_text('1.3.35')
        (self.home / 'mixed-router-state.json').write_text('{"clients":"codex"}')
        dialog = mock.MagicMock()
        dialog.Progress.return_value.__enter__.return_value.cancelled = False
        owners = {name: mock.Mock() for name in ('desktop_menu', 'native_resources', 'atomic_write')}
        owners.update(native_dialog=dialog, setup_restart=self.owner,
                      claude_desktop_platform=self.platform, codex_desktop_switch=self.codex,
                      codex_config=mock.Mock(read_receipt=lambda _: {'clients': {'codex': {}}}))
        owners['native_resources'].current.return_value = source
        with mock.patch.object(setup, 'load', side_effect=owners.__getitem__), \
                mock.patch.object(setup, 'retained', return_value=source), \
                mock.patch.object(setup, 'run_installer', return_value=SimpleNamespace(returncode=0)), \
                mock.patch.object(setup, '_key', return_value=0), \
                mock.patch.object(setup, '_check') as check:
            self.assertEqual(setup.onboard(source, self.home, 'install'), 0)
            check.assert_not_called()
            self.assertEqual(restart_dialog.show.call_count, 1)
            later = (self.home / 'update-notice.json').read_bytes()
            self.assertEqual(json.loads(later)['restart_result'], 'later')
            self.assertTrue(self.owner.offer(self.home, 'changed', True))
            self.assertEqual((self.home / 'update-notice.json').read_bytes(), later)
            self.assertEqual(restart_dialog.show.call_count, 1)
            self.assertFalse(current.offer(self.home, spawn=mock.Mock()))
            # Explicit Check setup remains available; its reply/tool gates own readiness.
            self.assertEqual(setup.onboard(source, self.home, 'status'), 0)
            check.assert_called_once_with(source, self.home, dialog)
        self.platform.request_stop.assert_not_called()
        self.platform.open_app.assert_not_called()

    def test_unchanged_target_does_not_join_other_versions_or_claude_only_notices(self):
        self._shared_notice_helpers()
        path = self.home / 'update-notice.json'
        for changes in (dict(version='1.3.34'), dict(clients='claude')):
            doc = dict(version='1.3.35', clients='codex', attachment='synthetic')
            doc.update(changes)
            path.write_text(json.dumps(doc))
            self.assertFalse(self.owner.offer(self.home, 'changed', True))
        self.notice_windows.show.assert_not_called()

    def test_unavailable_or_timed_out_completion_is_handled_and_stays_pending(self):
        record = module('notice').record_client_change
        self.notice.record_client_change.side_effect = record
        for outcome in (False, None, OSError('unavailable'), subprocess.TimeoutExpired('dialog', 120)):
            with self.subTest(outcome=type(outcome).__name__):
                self.notice_windows.show.side_effect = outcome if isinstance(outcome, Exception) else None
                self.notice_windows.show.return_value = outcome
                self.assertTrue(self.owner.offer(self.home, 'before', True))
                pending = json.loads((self.home / 'update-notice.json').read_text())
                self.assertTrue(pending['client_change'])
                self.assertTrue(pending['completion_selected'])
                self.assertNotIn('shown', pending)
                self.assertNotIn('restart_result', pending)
                spawn = mock.Mock()
                windows = module('notice_windows')
                self.assertFalse(windows.offer(self.home, spawn))
                spawn.assert_not_called()
                self.assertIsNotNone(windows.pending(self.home, setup_completion=True)[2])
        self.assertEqual(self.notice_windows.show.call_count, 4)
        self.assertFalse(self.owner.offer(self.home, 'changed', True))
        self.assertEqual(self.notice_windows.show.call_count, 4)
        module('notice').record_attachment(self.home, '1.3.35', 'c' * 32)
        self.assertIsNotNone(windows.pending(self.home)[2])

    def test_completed_onboarding_does_not_fall_back_after_missing_or_timed_out_offer(self):
        setup = module('native_setup')
        windows = module('notice_windows')
        self.notice.record_client_change.side_effect = module('notice').record_client_change
        self.service.install_lock.return_value = contextlib.nullcontext(True)
        restart_dialog = mock.Mock()
        text = module('notice_text')
        text.pending_names = mock.Mock(return_value=[])
        window_owners = dict(service=self.service, windows_dialog=restart_dialog,
                             claude_desktop_platform=self.platform, notice_text=text)
        window_load, restart_load = windows.load, self.owner.load
        source = resources(self.home / 'resources')
        home = self.home / 'installed'
        home.mkdir()
        (home / 'current').write_text('1.2.0')
        dialog = mock.MagicMock()
        dialog.Progress.return_value.__enter__.return_value.cancelled = False
        owners = {name: mock.Mock() for name in ('desktop_menu', 'native_resources', 'atomic_write')}
        owners.update(native_dialog=dialog, setup_restart=self.owner,
                      claude_desktop_platform=self.platform, codex_desktop_switch=self.codex)
        owners['native_resources'].current.return_value = source
        owners['codex_config'] = mock.Mock(read_receipt=lambda _: {'clients': {'codex': {}}})
        for outcome in (False, subprocess.TimeoutExpired('dialog', 120)):
            with self.subTest(outcome=type(outcome).__name__):
                self.owner.target.side_effect = ['before', 'changed']
                self.platform.is_running.side_effect = [True, True, False] if outcome is False else None
                restart_dialog.show.side_effect = outcome if isinstance(outcome, Exception) else None
                with mock.patch.object(setup, 'load', side_effect=lambda name: owners[name]), \
                        mock.patch.object(self.owner, 'load', side_effect=lambda name:
                                          windows if name == 'notice_windows' else restart_load(name)), \
                        mock.patch.object(windows, 'load', side_effect=lambda name:
                                          window_owners.get(name) or window_load(name)), \
                        mock.patch.object(setup, 'retained', return_value=source), \
                        mock.patch.object(setup, 'run_installer', return_value=SimpleNamespace(returncode=0)), \
                        mock.patch.object(setup, '_key', return_value=0), \
                        mock.patch.object(setup, '_check') as check:
                    self.assertEqual(setup.onboard(source, home, 'resume'), 0)
                    calls = restart_dialog.show.call_count
                    spawn = mock.Mock()
                    self.assertFalse(windows.offer(home, spawn))
                    self.assertFalse(windows.show(home))
                    spawn.assert_not_called()
                    self.assertEqual(restart_dialog.show.call_count, calls)
                check.assert_not_called()
                dialog.message.assert_not_called()


if __name__ == '__main__':
    unittest.main()
