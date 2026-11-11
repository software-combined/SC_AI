"""One OpenRouter choice and recovery of the connection used before a limit."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests._platform import unix_only
from tests import test_codex_desktop_switch as switch_fixtures
from tests import test_codex_switch_offer as offer_fixtures
from tests.test_native_setup import module

switcher = switch_fixtures.switcher
offers, T0, HOUR = offer_fixtures.offers, offer_fixtures.T0, offer_fixtures.HOUR


class OneChoiceMenuTests(unittest.TestCase):
    def test_both_openrouter_variants_share_one_checked_choice(self):
        control, model = module('desktop_control'), module('desktop_model')
        installer = mock.Mock()
        installer._diag._status_document.return_value = {'clients': {'codex': {}}}
        config = mock.Mock(SWITCHED='switched', SWITCHED_SIGNED_IN='switched_signed_in',
                           OPENROUTER='openrouter',
                           ROUTED_VARIANTS=('switched', 'switched_signed_in', 'openrouter'))
        config._codex.codex_attachment.return_value = {'openai_mode': 'subscription'}
        modules = dict(install=installer, codex_switch_config=config,
                       update_status=module('update_status'),
                       desktop_startup=SimpleNamespace(enabled=lambda _home: False))
        for variant, status in (('switched', 'ChatGPT sign-in not used'),
                                ('switched_signed_in', 'ChatGPT sign-in required'),
                                ('openrouter', 'ChatGPT sign-in required')):
            with self.subTest(variant=variant):
                config.current.return_value = variant
                with mock.patch.object(control, 'load', side_effect=modules.__getitem__):
                    client = control.snapshot(Path('/unused'))['clients'][0]
                self.assertEqual(client['selected'], 'openrouter')
                self.assertEqual(client['sign_in_status'], status)
                self.assertEqual([c['label'] for c in client['choices']],
                                 ['ChatGPT + OpenRouter', 'OpenRouter'])
                rows = model.menu({'clients': [client]})['menu']
                section = next(r for r in rows if r['label'].startswith('Codex'))
                choices = [r for r in section['children'] if r['action'] == 'codex.openrouter']
                self.assertEqual(len(choices), 1)
                self.assertTrue(choices[0]['checked'])
                self.assertEqual(section['label'], 'Codex — OpenRouter (%s)' % status)
                self.assertIn('codex.openrouter', dict(model.chooser(rows)[1]))

    def test_no_subscription_selected_choice_is_not_a_change_action(self):
        model = module('desktop_model')
        client = dict(id='codex', label='Codex', selected='openrouter',
                      sign_in_status='ChatGPT sign-in not used', choices=[
                          dict(id='subscription', label='ChatGPT + OpenRouter', enabled=False),
                          dict(id='openrouter', label='OpenRouter', reselect=False)])
        rows = model.menu({'clients': [client]})['menu']
        section = next(r for r in rows if r['label'].startswith('Codex'))
        self.assertFalse(next(c for c in section['children'] if c['action'] == 'codex.openrouter')['enabled'])
        self.assertNotIn('codex.openrouter', dict(model.chooser(rows)[1]))


@unix_only
class OneChoiceSwitchTests(unittest.TestCase):
    def setUp(self):
        self.case = switch_fixtures.SwitchFlowTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def choose(self, app, target='openrouter_toggle', prove=None):
        return switcher.switch(self.case.home, target=target, platform_ops=app,
                               ready=lambda _home: True, prove=prove or self.case.prove())

    def test_offer_never_starts_interrupted_mac_recovery(self):
        marker = self.case.home / switcher.MARKER
        marker.write_text('{}')
        app = self.case.fake()
        entry = switcher._receipts.codex_attachment(self.case.home)
        with mock.patch.object(switcher._offer, 'due', return_value=('switch', {'seen_at': 'episode'})):
            self.assertIs(switcher.switch(self.case.home, target='switched', offer_kind='switch',
                offer_seen='episode', expected=entry, platform_ops=app,
                ready=lambda _home: True, prove=self.case.prove()), False)
        self.assertEqual(app.calls, [])
        self.assertTrue(marker.exists())

    def test_episode_can_be_extended_while_recovery_is_being_checked(self):
        switcher._blocks.switch(self.case.home, 'switched')
        app = self.case.fake()
        entry = switcher._receipts.codex_attachment(self.case.home)
        with mock.patch.object(switcher._offer, 'due', side_effect=[('back', {'seen_at': 'episode'}), None]), \
                mock.patch.object(switcher, '_recover'):
            result = switcher.switch(self.case.home, target='switched_back', offer_kind='back',
                                     offer_seen='episode', expected=entry, platform_ops=app,
                                     ready=lambda _home: True, prove=self.case.prove())
        self.assertIs(result, False)
        self.assertEqual(app.calls, [])

    def test_reselect_uses_opposite_mode_without_an_episode(self):
        app = self.case.fake()
        self.assertEqual(self.choose(app), 'openrouter')
        self.assertEqual(self.choose(app), 'switched')
        self.assertIn('projects', app.calls[-3][1].lower())
        self.assertEqual(self.choose(app), 'openrouter')
        self.assertIn('send', app.calls[-3][1].lower())
        self.assertNotIn('model_provider = "scg_router"', self.case.config.read_text())
        self.assertIn('model_catalog_json =', self.case.config.read_text())
        calls = len(app.calls)
        self.assertEqual((self.choose(app, target='openrouter'), len(app.calls)),
                         ('openrouter', calls))

    def test_recorded_limit_selects_signed_out_and_cancel_changes_nothing(self):
        with mock.patch.object(switcher._offer, 'fallback_needed', return_value=True):
            app = self.case.fake(confirm=False)
            before = self.case.config.read_bytes(), (self.case.home / 'activation.json').read_bytes()
            self.assertIsNone(self.choose(app))
            self.assertEqual((self.case.config.read_bytes(), (self.case.home / 'activation.json').read_bytes()), before)
            self.assertNotIn('stop', [call[0] for call in app.calls])
            self.assertEqual(self.choose(self.case.fake()), 'switched')

    def test_unavailable_chatgpt_login_can_offer_the_signed_out_fallback(self):
        app = self.case.fake()
        def prove(_root, target):
            return target == 'switched'
        result = self.choose(app, prove=prove)
        self.assertEqual(result, 'switched')
        self.assertEqual([c[0] for c in app.calls].count('confirm'), 3)
        self.assertIn('without ChatGPT sign-in', app.calls[-3][1])

    def test_failed_signin_fallback_can_be_declined_without_changes(self):
        app = self.case.fake()
        app.confirm = mock.Mock(side_effect=[True, False])
        before = self.case.config.read_bytes()
        self.assertIsNone(self.choose(app, prove=lambda _root, target: target == 'switched'))
        self.assertEqual(app.confirm.call_count, 2)
        self.assertEqual(self.case.config.read_bytes(), before)
        self.assertEqual(switcher._blocks.current(self.case.home), 'default')

    def test_fallback_after_failed_signin_requires_an_explicit_menu_choice(self):
        app = self.case.fake()
        with self.assertRaises(switcher.SwitchError):
            self.choose(app, target='switched_signed_in', prove=lambda _root, target: target == 'switched')
        self.assertEqual([c[0] for c in app.calls].count('confirm'), 1)

    def test_reselect_signed_out_warns_even_with_active_limit(self):
        switcher._blocks.switch(self.case.home, 'switched')
        before = self.case.config.read_bytes(), (self.case.home / 'activation.json').read_bytes()
        app = self.case.fake(confirm=False)
        with mock.patch.object(switcher._offer, 'fallback_needed', return_value=True):
            self.assertIsNone(self.choose(app))
        self.assertIn('Send may still be blocked', app.calls[0][1])
        self.assertEqual((self.case.config.read_bytes(), (self.case.home / 'activation.json').read_bytes()), before)

    def test_a_proven_fallback_remembers_the_previous_connection(self):
        for before, expected in (('switched_signed_in', 'switched_signed_in'),
                                 ('openrouter', 'openrouter'),
                                 ('switched_back', 'switched_back')):
            with self.subTest(before=before):
                switcher._blocks.switch(self.case.home, before)
                self.assertEqual(self.choose(self.case.fake(), target='switched'), 'switched')
                entry = switcher._receipts.codex_attachment(self.case.home)
                self.assertEqual(entry.get('fallback_return'), expected)
                self.assertEqual(switcher._blocks.return_target(entry), expected)
        switcher._blocks.switch(self.case.home, 'switched_signed_in')
        self.assertEqual(self.choose(self.case.fake()), 'switched')
        self.assertEqual(self.choose(self.case.fake()), 'switched_signed_in')

    def test_offer_refuses_a_profile_changed_since_the_notice(self):
        expected = switcher._receipts.codex_attachment(self.case.home)
        switcher._blocks.switch(self.case.home, 'switched_signed_in')
        app = self.case.fake()
        with self.assertRaisesRegex(switcher.SwitchError, 'Nothing was changed'):
            switcher.switch(self.case.home, target='switched', expected=expected,
                            platform_ops=app, ready=lambda _home: True, prove=self.case.prove())
        self.assertEqual(app.calls, [])

    def test_pending_fallback_recovery_keeps_or_restores_return_connection(self):
        blocks = switcher._blocks
        for proves in (False, True):
            with self.subTest(proves=proves):
                blocks.switch(self.case.home, 'switched_signed_in')
                before = blocks.rollback_entry(switcher._receipts.codex_attachment(self.case.home))
                blocks.switch(self.case.home, 'switched')
                switcher._atomic.replace_json(self.case.home / switcher.MARKER,
                                              {'to': 'switched', 'entry': before})
                switcher._recover(self.case.home, lambda _root, _target: proves, str(self.case.app))
                entry = switcher._receipts.codex_attachment(self.case.home)
                self.assertEqual(entry['variant'], 'switched' if proves else 'switched_signed_in')
                self.assertEqual(entry.get('fallback_return'), 'switched_signed_in' if proves else None)
                self.assertFalse((self.case.home / switcher.MARKER).exists())


class OneChoiceOfferTests(unittest.TestCase):
    def setUp(self):
        self.case = offer_fixtures._Home()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.home, self.spawned = self.case.home, self.case.spawned
        self.attach, self.record = self.case.attach, self.case.record
        self.run_pass, self.offered = self.case.run_pass, self.case.offered
        self.write_episode = self.case.write_episode

    def test_return_offer_uses_recorded_destination(self):
        self.record()
        for saved, expected in ((None, 'switched_back'), ('switched_signed_in', 'switched_signed_in'),
                                ('openrouter', 'openrouter'),
                                ('switched_back', 'switched_back'), ('invalid', 'switched_back')):
            with self.subTest(saved=saved):
                self.attach(variant='switched')
                path = offers._codex.receipt_path_for(self.home)
                receipt = json.loads(path.read_text())
                if saved is not None:
                    receipt['clients']['codex']['fallback_return'] = saved
                path.write_text(json.dumps(receipt))
                entry = offers._codex.codex_attachment(self.home)
                self.assertEqual(offers._switch.return_target(entry), expected)
                control = module('desktop_control')
                dialog, owner = mock.Mock(), mock.Mock()
                dialog.confirm_result.return_value = False
                modules = {'service': module('service'), 'codex_switch_offer': offers, 'codex_desktop_switch': owner}
                with mock.patch.object(control.sys, 'platform', 'darwin'), \
                        mock.patch.object(offers.time, 'time', return_value=T0 + HOUR), \
                        mock.patch.object(control, 'load', side_effect=modules.__getitem__):
                    self.assertEqual(control._limit_offer(self.home, dialog), {'outcome': 'cancelled'})
                message = dialog.confirm_result.call_args.args[0]
                self.assertIn('OpenRouter models with ChatGPT sign-in'
                              if expected in ('switched_signed_in', 'openrouter')
                              else 'back from OpenRouter models', message)
                (self.home / offers.OFFERS_FILE).unlink()

    def test_reset_offer_does_not_assume_all_limits_have_reset(self):
        self.attach(variant='switched')
        self.record()
        self.assertEqual(offers.due(self.home, now=T0 + HOUR)[0], offers.BACK)
        self.assertIn('may still', offers.MESSAGES[offers.BACK].lower())

    def test_unavailable_or_refused_desktop_dialog_does_not_switch(self):
        control = module('desktop_control')
        self.attach(variant='switched')
        self.record()
        dialog, owner, service = mock.Mock(), mock.Mock(), module('service')
        for answer in (None, False):
            with self.subTest(answer=answer), \
                    mock.patch.object(control.sys, 'platform', 'linux'), \
                    mock.patch.object(offers.time, 'time', return_value=T0 + HOUR), \
                    mock.patch.object(control, 'load', side_effect={
                        'service': service, 'codex_switch_offer': offers,
                        'codex_desktop_switch': owner}.__getitem__):
                dialog.confirm_result.return_value = answer
                self.assertEqual(control._limit_offer(self.home, dialog), {'outcome': 'cancelled'})
                owner.switch.assert_not_called()
                if answer is None:
                    self.assertEqual(self.offered()['offered'], [])

    def test_desktop_offer_never_starts_a_stale_switch(self):
        control = module('desktop_control')
        self.attach(variant='switched')
        self.record()
        dialog, owner, service = mock.Mock(), mock.Mock(), module('service')
        def change_profile(*_args, **_kwargs):
            self.attach(variant='switched_signed_in')
            return True
        dialog.confirm_result.side_effect = change_profile
        modules = {'service': service, 'codex_switch_offer': offers, 'codex_desktop_switch': owner}
        with mock.patch.object(control.sys, 'platform', 'linux'), \
                mock.patch.object(offers.time, 'time', return_value=T0 + HOUR), \
                mock.patch.object(control, 'load', side_effect=modules.__getitem__):
            self.assertEqual(control._limit_offer(self.home, dialog), {'outcome': 'cancelled'})
        owner.switch.assert_not_called()

    def test_changed_return_target_stays_available_after_stale_offer(self):
        self.attach(variant='switched')
        self.record()
        control = module('desktop_control')
        dialog, owner = mock.Mock(), mock.Mock()
        def change_return(*_args, **_kwargs):
            path = offers._codex.receipt_path_for(self.home)
            receipt = json.loads(path.read_text())
            receipt['clients']['codex']['fallback_return'] = 'switched_signed_in'
            path.write_text(json.dumps(receipt))
            return True
        dialog.confirm_result.side_effect = change_return
        modules = {'service': module('service'), 'codex_switch_offer': offers, 'codex_desktop_switch': owner}
        with mock.patch.object(control.sys, 'platform', 'darwin'), \
                mock.patch.object(offers.time, 'time', return_value=T0 + HOUR), \
                mock.patch.object(control, 'load', side_effect=modules.__getitem__):
            self.assertEqual(control._limit_offer(self.home, dialog), {'outcome': 'cancelled'})
        owner.switch.assert_not_called()
        self.assertEqual(offers.due(self.home, now=T0 + HOUR)[0], offers.BACK)
    def test_missing_or_damaged_control_worker_does_not_record_an_offer(self):
        self.attach(variant='switched')
        self.record()
        self.assertIsNone(offers.offer(self.home, now=T0 + HOUR, platform_name='linux'))
        self.assertEqual(self.spawned, [])
        self.assertIsNone(self.offered())
    def test_retained_control_worker_is_spawned_on_all_platforms(self):
        self.attach(variant='switched')
        self.record()
        (self.home / 'control-version').write_text('1.3.47.1\n')
        worker = self.home / 'control/1.3.47.1/packaging/codex_switch_offer.py'
        worker.parent.mkdir(parents=True)
        worker.touch()
        for platform in ('darwin', 'win32', 'linux'):
            with self.subTest(platform=platform):
                self.assertIsNone(offers.offer(self.home, now=T0 + HOUR, platform_name=platform))
                self.assertEqual(self.spawned[-1][1:], [str(worker), '--home', str(self.home), '--desktop-offer'])
        self.assertIsNone(self.offered())
