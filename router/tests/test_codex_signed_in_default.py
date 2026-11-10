"""1.3.45 sign-in default: a signed-out OpenRouter install migrates on update.

The signed-in OpenRouter variant already shipped in 1.3.41, but updates
preserved the signed-out `switched` variant, so existing installs stayed
signed out and lost sidebar projects on restart. The updater now migrates
`switched` to `switched_signed_in`, except during an active usage limit.
An unreadable episode file stays signed out (fail closed).
"""
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from tests._platform import unix_only
from tests.test_codex_switch_config import switch, _entry
from tests.test_install_config import _install


def _signed_out(test, tmp):
    home = Path(tmp) / 'home'
    config, _, _, _ = _install(test, tmp, home, '1.0.0')
    switch.switch(home, 'switched')
    assert not tomllib.loads(config.read_text())[
        'model_providers']['scg_router']['requires_openai_auth']
    return home, config


def _assert_variant(test, entry_home, config, variant, signed_in):
    test.assertEqual(_entry(entry_home)['variant'], variant)
    doc = tomllib.loads(config.read_text())
    test.assertEqual(
        doc['model_providers']['scg_router']['requires_openai_auth'], signed_in)


@unix_only
class SignedInDefaultTests(unittest.TestCase):
    def test_update_migrates_signed_out_switched_to_signed_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched_signed_in', True)
            self.assertEqual(tomllib.loads(config.read_text())['model'],
                             'deepseek/deepseek-v4.1-flash-1017')

    def test_update_migrates_with_no_episode_record(self):
        # No recorded limit: migrate now; Switch Codex can still fall back.
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            self.assertFalse((home / 'codex-usage-limit.json').exists())
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched_signed_in', True)

    def test_update_keeps_signed_out_during_active_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            # A real active episode: the updater reads this file.
            (home / 'codex-usage-limit.json').write_text(json.dumps(
                {"seen_at": "2000-01-01T00:00:00+00:00",
                 "resets_at": "2100-01-01T00:00:00+00:00"}))
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched', False)

    def test_update_migrates_when_episode_expired(self):
        # A valid record whose limit already ended migrates.
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            (home / 'codex-usage-limit.json').write_text(json.dumps(
                {"seen_at": "2000-01-01T00:00:00+00:00",
                 "resets_at": "2000-01-01T05:00:00+00:00"}))
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched_signed_in', True)

    def test_update_stays_signed_out_on_dangling_link(self):
        # A dangling symlink is an entry that cannot be read: stay signed out.
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            (home / 'codex-usage-limit.json').symlink_to('/does/not/exist')
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched', False)

    def test_update_stays_signed_out_on_impossible_reset(self):
        # A reset earlier than the observation is corrupt: stay signed out.
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            (home / 'codex-usage-limit.json').write_text(json.dumps(
                {"seen_at": "2100-01-01T00:00:00+00:00",
                 "resets_at": "2000-01-01T00:00:00+00:00"}))
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched', False)

    def test_update_stays_signed_out_when_episode_unreadable(self):
        # Fail closed: an unreadable episode file must not migrate.
        with tempfile.TemporaryDirectory() as tmp:
            home, config = _signed_out(self, tmp)
            (home / 'codex-usage-limit.json').write_text('not json')
            _install(self, tmp, home, '1.0.1')
            _assert_variant(self, home, config, 'switched', False)


if __name__ == '__main__':
    unittest.main()
