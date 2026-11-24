"""Offline contracts for the native setup cancellation operation."""
import json
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest import mock

from ai_router import availability, setup
from tests.test_setup import NOW, _key_ok, _key_rejected, _state
from tests.test_setup_provider import _register_acme


class SetupCancellationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.state = _state(self.home, openai_mode='none')
        self.path = self.home / 'mixed-router-state.json'
        self.path.write_text(json.dumps(self.state))
        self.keyfile = self.home / 'openrouter.key'
        self.keyfile.write_bytes(b'synthetic-saved-key\n')
        lookup = mock.patch.object(availability, 'current_key', return_value='synthetic-saved-key')
        self.lookup = lookup.start()
        self.addCleanup(lookup.stop)

    def cancel(self, opener, form=b'cancel=1'):
        return setup.handle_setup_json(self.state, self.home, 'n' * 16, form,
                                       _urlopen=opener, _now=NOW)

    def test_live_key_closes_only_setup(self):
        opener = mock.Mock(side_effect=_key_ok())
        self.assertEqual(self.cancel(opener), (200, {'ok': True}))
        opener.assert_called_once()
        self.lookup.assert_called_with(self.home, 'openrouter')
        self.assertEqual(json.loads(self.path.read_text()), self.state)
        self.assertNotIn('setup', self.state)
        self.assertEqual(self.state['openai_mode'], 'none')
        self.assertEqual(self.keyfile.read_bytes(), b'synthetic-saved-key\n')
        self.assertEqual(set(self.home.iterdir()), {self.path, self.keyfile})

    def test_rejected_unavailable_and_unreadable_keys_keep_the_link(self):
        before = self.path.read_bytes()
        for opener in (_key_rejected(), mock.Mock(side_effect=OSError()),
                       mock.Mock(side_effect=IncompleteRead(b''))):
            self.assertEqual(self.cancel(opener), (409, {'ok': False}))
            self.assertEqual(self.path.read_bytes(), before)
        self.lookup.return_value = None
        opener = mock.Mock()
        self.assertEqual(self.cancel(opener), (409, {'ok': False}))
        opener.assert_not_called()
        self.assertEqual(json.loads(before), self.state)

    def test_unsupported_endpoint_and_nonexact_form_cannot_cancel(self):
        provider = _register_acme(self)
        self.state['setup']['provider'] = provider.id
        self.path.write_text(json.dumps(self.state))
        opener = mock.Mock()
        self.assertEqual(self.cancel(opener), (409, {'ok': False}))
        self.assertEqual(self.cancel(opener, b'cancel=1&unused=1')[0], 422)
        opener.assert_not_called()
        self.lookup.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text()), self.state)

    def test_newer_saved_nonce_is_preserved_during_liveness_check(self):
        newer = dict(self.state, setup={'nonce': 'newer', 'expires': NOW + 900})

        def open_then_replace(req, timeout):
            self.path.write_text(json.dumps(newer))
            return _key_ok()(req, timeout)

        self.assertEqual(self.cancel(open_then_replace), (409, {'ok': False}))
        self.assertEqual(json.loads(self.path.read_text()), newer)
        self.assertIn('setup', self.state)

    def test_atomic_retry_preserves_a_concurrently_saved_nonce(self):
        newer = dict(self.state, setup={'nonce': 'newer', 'expires': NOW + 900})
        replace = setup.atomic_write.replace_json

        def save_newer_first(path, doc, **options):
            path.write_text(json.dumps(newer))
            return replace(path, doc, **options)

        with mock.patch.object(setup.atomic_write, 'replace_json', side_effect=save_newer_first) as write:
            self.assertEqual(self.cancel(_key_ok()), (409, {'ok': False}))
            write.assert_called_once()
        self.assertEqual(json.loads(self.path.read_text()), newer)
        self.assertIn('setup', self.state)

    def test_key_change_during_liveness_check_keeps_link(self):
        self.lookup.side_effect = ['synthetic-saved-key', 'synthetic-replacement']
        self.assertEqual(self.cancel(_key_ok()), (409, {'ok': False}))
        self.assertEqual(json.loads(self.path.read_text()), self.state)
        self.assertIn('setup', self.state)
