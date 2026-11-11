"""Model access must be ready before setup asks for a routed test message."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_native_setup import module


class NativeAccessTests(unittest.TestCase):
    def test_missing_service_key_opens_secure_setup_only_after_user_choice(self):
        setup = module('native_setup')
        facts = dict(serving=True, service_key_usable=False, key_usable=True,
                     onboarding=dict(ready=False, clients={}))
        for answer in (True, False, None):
            with self.subTest(answer=answer):
                dialog = mock.Mock()
                dialog.confirm_result.return_value = answer
                with mock.patch.object(setup, 'status', return_value=facts), \
                        mock.patch.object(setup, '_key', return_value=2) as key:
                    setup._check(Path('/resources'), Path('/router-home'), dialog)
                if answer is True:
                    key.assert_called_once_with(Path('/resources'), Path('/router-home'), replace=True)
                else:
                    key.assert_not_called()
                self.assertEqual(dialog.confirm_result.call_args.kwargs['labels'],
                                 ('Set up access', 'Cancel'))
                dialog.confirm.assert_not_called()
                dialog.message.assert_not_called()

    def test_status_separates_shell_only_key_from_service_visible_access(self):
        diagnostics = module('diagnostics')
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with mock.patch.dict(os.environ, {'OPENROUTER_API_KEY': 'synthetic'}, clear=True):
                facts = diagnostics._status_document(home)
            self.assertTrue(facts['key_usable'])
            self.assertFalse(facts['service_key_usable'])
            self.assertFalse(facts['service_key_present'])
            self.assertNotIn('synthetic', json.dumps(facts))
            self.assertEqual(list(home.iterdir()), [])

    def test_discovery_reasons_do_not_count_as_readiness_booleans(self):
        readiness = module('native_readiness')
        skills = mock.Mock()
        skills.plugin_sources.return_value = {'scg-review': Path('/plugin')}
        with mock.patch.object(readiness, 'load', return_value=skills), \
                mock.patch.object(readiness, 'choices_applied', return_value=True), \
                mock.patch.object(readiness, 'plugins_available', side_effect=lambda *a, **kw:
                    kw['reasons'].update(codex='found') or True), \
                mock.patch.object(readiness, 'successful_reply', return_value=True):
            for usable in (False, True):
                facts = readiness.check(Path('/home'), Path('/source'),
                    dict(serving=True, service_key_usable=usable, clients={'codex': {}}),
                    dict(confirmed_clients=['codex']))
                self.assertEqual(facts['ready'], usable)
                self.assertEqual(facts['discovery'], {'codex': 'found'})
                self.assertTrue(all(type(value) is bool for value in facts['clients']['codex'].values()))


if __name__ == '__main__':
    unittest.main()
