"""The setup route writes no starter instructions and keeps saved modes."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_router import setup
from tests.test_setup import NOW, _key_ok, _state
from tests.setup_fixtures import offline_availability


class SetupWithoutStarterTests(unittest.TestCase):
    setUp = offline_availability

    def _home(self, **saved):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        state = _state(home, **saved)
        (home / 'mixed-router-state.json').write_text(json.dumps(state))
        return home, state

    def _saved(self, home):
        return json.loads((home / 'mixed-router-state.json').read_text())

    def test_an_older_callers_starter_field_writes_no_instructions(self):
        home, state = self._home()
        user = home / 'user'
        with mock.patch.object(Path, 'home', return_value=user):
            status, payload = setup.handle_setup_json(
                state, home, 'n' * 16, b'key=sk-test&profile=dev', _urlopen=_key_ok(), _now=NOW)
        self.assertEqual((status, payload['ok']), (200, True))
        self.assertNotIn('starter', payload)
        self.assertFalse((user / '.codex').exists(), 'no starter AGENTS.md')
        self.assertNotIn('agents_profile', self._saved(home))

    def test_a_key_only_post_keeps_the_saved_modes(self):
        home, state = self._home(openai_mode='none', claude_mode='none', anthropic_mode='none')
        status, payload = setup.handle_setup_json(
            state, home, 'n' * 16, b'key=sk-test', _urlopen=_key_ok(), _now=NOW)
        self.assertEqual((status, payload['ok']), (200, True))
        saved = self._saved(home)
        for name in ('openai_mode', 'claude_mode', 'anthropic_mode'):
            self.assertEqual(saved[name], 'none', name)

    def test_close_failure_still_reports_500(self):
        home, state = self._home()
        with mock.patch.object(setup, '_finish_setup', return_value=False):
            status, payload = setup.handle_setup_json(
                state, home, 'n' * 16, b'key=sk-test', _urlopen=_key_ok(), _now=NOW)
        self.assertEqual(status, 500)
        self.assertFalse(payload['ok'])
        self.assertTrue(payload['key_saved'])
        self.assertIn('Check setup', payload['error'])


if __name__ == '__main__':
    unittest.main()
