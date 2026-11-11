"""Update and mode-change coverage for remembered Codex connections."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests._platform import unix_only
from tests import test_codex_desktop_switch as fixtures
from tests import test_windows_switch_transaction as windows_fixtures
from tests import test_codex_switch_offer as offer_fixtures
from tests.test_install_config import _install
from tests.test_native_setup import module

switcher = fixtures.switcher

class PlatformSwitchTests(unittest.TestCase):
    def setUp(self):
        self.case = offer_fixtures._Home()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.attach(variant='switched')
        self.case.record()
        self.offers, self.control = offer_fixtures.offers, module('desktop_control')
        self.dialog, self.owner = mock.Mock(), mock.Mock()
        self.modules = {'service': module('service'), 'codex_switch_offer': self.offers,
                        'codex_desktop_switch': self.owner}
        self.dialog.confirm_result.return_value = True
        self.owner.SwitchError = switcher.SwitchError

    def offer(self, platform='linux', **kwargs):
        with mock.patch.object(self.control.sys, 'platform', platform), \
                mock.patch.object(self.offers.time, 'time', return_value=offer_fixtures.T0 + offer_fixtures.HOUR), \
                mock.patch.object(self.control, 'load', side_effect=self.modules.__getitem__):
            result = self.control._limit_offer(self.case.home, self.dialog, **kwargs)
            due = self.offers.due(self.case.home, now=offer_fixtures.T0 + offer_fixtures.HOUR)
        return result, due

    def test_mac_offer_can_run_while_an_update_check_is_active(self):
        self.owner.switch.return_value = 'switched_back'
        with self.modules['service'].install_lock(self.case.home, 'update.lock') as held:
            self.assertTrue(held)
            result, _ = self.offer(platform='darwin')
        self.assertEqual(result, {'outcome': 'done'})
        self.dialog.confirm_result.assert_called_once()
        self.owner.switch.assert_called_once()

    def test_old_offer_cannot_overwrite_a_new_episode(self):
        def switch(*_args, **_kwargs):
            self.case.record(now=offer_fixtures.T0 + 2 * offer_fixtures.HOUR,
                             resets=offer_fixtures.T0 + 3 * offer_fixtures.HOUR)
            self.offers._remember(self.case.home, self.offers.episode(self.case.home)['seen_at'], ['switch'])
            return 'switched_back'
        self.owner.switch.side_effect = switch
        self.assertEqual(self.offer()[0], {'outcome': 'done'})
        self.assertEqual(self.case.offered()['seen_at'], self.offers.episode(self.case.home)['seen_at'])
        self.assertEqual(self.case.offered()['offered'], ['switch'])

    def test_update_lock_is_available_while_offer_dialog_waits(self):
        def dismiss(*_args, **_kwargs):
            with self.modules['service'].install_lock(self.case.home, 'update.lock') as held:
                self.assertTrue(held)
            return False
        self.dialog.confirm_result.side_effect = dismiss
        self.assertEqual(self.offer()[0], {'outcome': 'cancelled'})

    def test_unwritable_offer_receipt_never_shows_a_dialog(self):
        with mock.patch.object(self.offers, '_claim', side_effect=OSError('read-only home')):
            self.assertEqual(self.offer()[0], {'outcome': 'cancelled'})
        self.dialog.confirm_result.assert_not_called()
        self.owner.switch.assert_not_called()

    def test_fast_acceptance_reaches_the_final_confirmation(self):
        self.owner.switch.return_value = 'switched_back'
        result, due = self.offer(platform='darwin')
        self.assertEqual((result, due), ({'outcome': 'done'}, None))
        self.dialog.confirm_result.assert_called_once()
        self.owner.switch.assert_called_once()

    def test_unshown_dialog_rolls_back_its_prepared_offer(self):
        self.dialog.confirm_result.return_value = None
        result, due = self.offer(platform='darwin')
        self.assertEqual((result, due[0]), ({'outcome': 'cancelled'}, self.offers.BACK))
        self.assertEqual(self.case.offered()['offered'], [])

    def test_unreadable_receipt_after_unshown_dialog_keeps_offer_pending(self):
        receipt = self.offers._codex.receipt_path_for(self.case.home)
        original = receipt.read_bytes()
        def fail(*_args, **_kwargs):
            receipt.write_text('{')
            return None
        self.dialog.confirm_result.side_effect = fail
        try:
            with mock.patch.object(self.control.sys, 'platform', 'darwin'), \
                    mock.patch.object(self.offers.time, 'time', return_value=offer_fixtures.T0 + offer_fixtures.HOUR), \
                    mock.patch.object(self.control, 'load', side_effect=self.modules.__getitem__):
                self.assertEqual(self.control._limit_offer(self.case.home, self.dialog), {'outcome': 'cancelled'})
        finally:
            receipt.write_bytes(original)
        self.assertEqual(self.offers.due(self.case.home, now=offer_fixtures.T0 + offer_fixtures.HOUR)[0],
                         self.offers.BACK)

    def test_interrupted_claim_is_recovered_before_a_new_dialog(self):
        self.offers._claim(self.case.home, self.offers.episode(self.case.home)['seen_at'], [], self.offers.BACK)
        self.dialog.confirm_result.return_value = None
        result, due = self.offer(platform='darwin')
        self.assertEqual((result, due[0]), ({'outcome': 'cancelled'}, self.offers.BACK))
        self.dialog.confirm_result.assert_called_once()

    def test_claimed_offer_is_pending_after_worker_interruption(self):
        self.dialog.confirm_result.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.offer(platform='darwin')
        self.assertEqual(self.offers.due(self.case.home, now=offer_fixtures.T0 + offer_fixtures.HOUR)[0],
                         self.offers.BACK)
        self.dialog.confirm_result.side_effect = None
        self.dialog.confirm_result.return_value = None
        self.assertEqual(self.offer(platform='darwin')[0], {'outcome': 'cancelled'})
        self.assertEqual(self.case.offered()['offered'], [])

    def test_another_worker_cannot_repeat_offer_during_final_confirmation(self):
        def confirm(*_args, **_kwargs):
            self.owner.switch.return_value = 'switched_back'
            self.owner.switch.side_effect = None
            self.assertEqual(self.control._limit_offer(self.case.home, self.dialog), {'outcome': 'cancelled'})
            return 'switched_back'
        self.owner.switch.side_effect = confirm
        self.assertEqual(self.offer()[0], {'outcome': 'done'})
        self.dialog.confirm_result.assert_called_once()
        self.owner.switch.assert_called_once()

    def test_unpresented_final_confirmation_keeps_offer_pending(self):
        self.owner.switch.return_value = False
        result, due = self.offer()
        self.assertEqual((result, due[0]), ({'outcome': 'cancelled'}, self.offers.BACK))

    @unix_only
    def test_missing_actual_final_dialog_keeps_offer_pending_without_stopping(self):
        case = fixtures.SwitchFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        with mock.patch.object(switcher._offer, 'due', return_value=('switch', {'seen_at': 'episode'})), \
                mock.patch.object(switcher._platform, 'app_identity', return_value={'root': str(case.app)}), \
                mock.patch.object(switcher._platform, 'request_stop') as stop, \
                mock.patch.object(switcher._dialog, 'confirm_result', return_value=None) as confirm:
            result = switcher.switch(case.home, target='switched', offer_kind='switch',
                                     offer_seen='episode', expected=switcher._receipts.codex_attachment(case.home),
                                     ready=lambda _home: True, prove=case.prove())
        self.assertIs(result, False)
        confirm.assert_called_once()
        stop.assert_not_called()
        self.assertEqual(switcher._blocks.current(case.home), 'default')

    @unix_only
    def test_offer_is_bound_to_the_episode_that_was_presented(self):
        case = fixtures.SwitchFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        app = case.fake()
        expected = switcher._receipts.codex_attachment(case.home)
        with mock.patch.object(switcher._offer, 'due', return_value=('switch', {'seen_at': 'new'})):
            result = switcher.switch(case.home, target='switched', offer_kind='switch', offer_seen='old',
                                     expected=expected, platform_ops=app,
                                     ready=lambda _home: True, prove=case.prove())
        self.assertIs(result, False)
        self.assertEqual(app.calls, [])

    def test_offer_cancel_at_final_confirmation_is_recorded(self):
        self.owner.switch.return_value = None
        self.assertEqual(self.offer(), ({'outcome': 'cancelled'}, None))

    def test_failed_offer_switch_is_reported_and_offer_remains_pending(self):
        self.owner.switch.side_effect = switcher.SwitchError(switcher.UNFINISHED)
        result, due = self.offer()
        self.assertEqual((result, due[0]), ({'outcome': 'failed'}, self.offers.BACK))
        self.dialog.message.assert_called_once_with(switcher.UNFINISHED)

    @unix_only
    def test_expired_offer_does_not_stop_codex_after_confirmation(self):
        case = fixtures.SwitchFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        app = case.fake()
        expected = switcher._receipts.codex_attachment(case.home)
        with mock.patch.object(switcher._offer, 'due', side_effect=[
                ('switch', {'seen_at': 'episode'}), ('switch', {'seen_at': 'episode'}), None]):
            result = switcher.switch(case.home, target='switched', offer_kind='switch',
                                     offer_seen='episode',
                                     expected=expected, platform_ops=app,
                                     ready=lambda _home: True, prove=case.prove())
        self.assertIs(result, False)
        self.assertEqual([call[0] for call in app.calls], ['confirm'])
        self.assertEqual(switcher._blocks.current(case.home), 'default')

    def test_windows_offer_uses_the_verified_dialog(self):
        windows = mock.Mock()
        windows.show.return_value = False
        self.modules['windows_dialog'] = windows
        self.assertEqual(self.offer(platform='win32')[0], {'outcome': 'cancelled'})
        self.assertEqual(windows.show.call_args.kwargs['labels'], ('Open Switch Codex', 'Later'))
        self.dialog.confirm_result.assert_not_called()
        self.owner.switch.assert_not_called()

    def test_windows_stale_offer_never_starts_pending_recovery(self):
        case = windows_fixtures.WindowsSwitchTransactionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.pending()
        with mock.patch.object(switcher._offer, 'due', return_value=None):
            result = case.switch(target='switched_back', offer_kind='back', offer_seen='stale',
                                 expected=switcher._receipts.codex_attachment(case.home))
        self.assertIs(result, False)
        case.confirm.assert_not_called()
        self.assertEqual(case.api.closed, [])
        self.assertTrue((case.home / switcher.MARKER).exists())

    def test_windows_current_offer_leaves_pending_recovery_for_manual_action(self):
        case = windows_fixtures.WindowsSwitchTransactionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.pending()
        with mock.patch.object(switcher._offer, 'due', return_value=('back', {'seen_at': 'episode'})):
            result = case.switch(target='switched_back', offer_kind='back', offer_seen='episode',
                                 expected=switcher._receipts.codex_attachment(case.home))
        self.assertIs(result, False)
        case.confirm.assert_not_called()
        self.assertEqual(case.api.closed, [])
        self.assertTrue((case.home / switcher.MARKER).exists())

    def test_windows_reselect_reaches_confirmation_for_both_openrouter_modes(self):
        case = windows_fixtures.WindowsSwitchTransactionTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.assertEqual(case.switch(target='openrouter_toggle'), 'openrouter')
        self.assertEqual(case.switch(target='openrouter_toggle'), 'switched')
        self.assertEqual(case.switch(target='openrouter_toggle'), 'openrouter')
        self.assertEqual((case.confirm.call_count, case.proofs[-1][1]), (3, 'openrouter'))

    @unix_only
    def test_linux_reselect_reaches_confirmation_for_both_openrouter_modes(self):
        case = fixtures.SwitchFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        app = case.fake()
        with mock.patch.object(switcher.sys, 'platform', 'linux'):
            for target in ('openrouter', 'switched', 'openrouter'):
                self.assertEqual(switcher.switch(case.home, target='openrouter_toggle', platform_ops=app,
                                                 ready=lambda _home: True, prove=case.prove()), target)
        self.assertEqual([call[0] for call in app.calls].count('confirm'), 3)

    @unix_only
    def test_offer_rechecks_episode_after_acquiring_installation_lock(self):
        case = fixtures.SwitchFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        switcher._blocks.switch(case.home, 'switched')
        before = case.config.read_bytes(), (case.home / 'activation.json').read_bytes()
        app = case.fake()
        with mock.patch.object(switcher._offer, 'due', return_value=None):
            result = switcher.switch(case.home, target='switched_signed_in', offer_kind='back',
                                     offer_seen='episode',
                                     expected=switcher._receipts.codex_attachment(case.home),
                                     platform_ops=app, ready=lambda _home: True, prove=case.prove())
        self.assertIs(result, False)
        self.assertEqual((app.calls, case.config.read_bytes(), (case.home / 'activation.json').read_bytes()), ([], *before))


@unix_only
class OneChoiceUpdateTests(unittest.TestCase):
    def test_update_preserves_prior_connection_without_switching_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve() / 'home'
            config, _, _, _ = _install(self, temporary, home, '1.0.0')
            blocks = switcher._blocks
            blocks.switch(home, 'openrouter')
            blocks.switch(home, 'switched')
            before = config.read_bytes()
            _install(self, temporary, home, '1.0.1')
            entry = blocks._codex.codex_attachment(home)
            self.assertEqual(entry['variant'], 'switched')
            self.assertEqual(entry['fallback_return'], 'openrouter')
            self.assertEqual(config.read_bytes(), before)

    def test_explicit_mode_change_clears_old_return_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / 'home'
            _install(self, temporary, home, '1.0.0')
            blocks = switcher._blocks
            blocks.switch(home, 'openrouter')
            blocks.switch(home, 'switched')
            _install(self, temporary, home, '1.0.1', '--clients', 'codex', '--openai-mode', 'none')
            self.assertNotIn('fallback_return', blocks._codex.codex_attachment(home))
