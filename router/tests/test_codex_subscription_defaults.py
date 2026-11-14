"""Fresh subscribers keep native defaults; explicit picks survive every attach."""
import contextlib
import io
import json
import os
import tempfile
import time
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_router import availability, key_store, setup as key_setup
from tests.test_client_choice import _install as current_install
from tests.test_native_setup import module, resources


class SubscriptionDefaultTests(unittest.TestCase):
    def test_late_key_window_choice_reconciles_the_real_codex_attachment(self):
        config, native = module('codex_config'), module('native_setup')
        config._atomic_write = module('atomic_write')
        for mode in ('subscription', 'none'):
            for picked in (None, 'native-choice', 'external/owner-choice'):
                with self.subTest(mode=mode, picked=picked), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    user, home = root / 'fakehome', root / 'router'
                    user.mkdir()
                    home.mkdir()
                    source = resources(root / 'Resources')
                    (home / 'current').write_text('1.0.0')
                    (home / 'releases/1.0.0').mkdir(parents=True)
                    path = user / '.codex/config.toml'
                    path.parent.mkdir()
                    path.write_text('approval_policy = "never"\n' + (
                        'model = "' + picked + '"\nmodel_reasoning_effort = "high"\n' if picked else ''))
                    with mock.patch.object(Path, 'home', return_value=user), \
                            mock.patch.dict(os.environ, {'HOME': str(user), 'ROUTER_HOME': str(home)}), \
                            contextlib.redirect_stdout(io.StringIO()):
                        self.assertFalse((path.parent / 'auth.json').exists())
                        initial_mode = config.default_mode()
                        self.assertEqual(initial_mode, 'subscription')
                        state = dict(port=1, token='synthetic', clients='codex', owner_setting='keep',
                                     setup=dict(nonce='synthetic', expires=time.time() + 3600))
                        (home / 'mixed-router-state.json').write_text(json.dumps(state))
                        (home / 'mixed-models.json').write_text('{"models":[]}')
                        code, _, bundle, _, _ = current_install(root, home, ['--clients', 'codex'])
                        self.assertEqual(code, 0)
                        bundle.assert_not_called()
                        self.assertEqual(config.codex_attachment(home)['openai_mode'], initial_mode)
                        def window(*args, **kwargs):
                            key_store.store_key(home, 'synthetic-saved-key')
                            with mock.patch.object(availability, 'current_key', return_value=None):
                                self.assertTrue(key_setup._finish_setup(state, home, mode=mode))
                            return SimpleNamespace(returncode=0)
                        def installer_process(argv, **kwargs):
                            code, output, bundle, _, _ = current_install(root, home, argv[2:])
                            bundle.assert_not_called()
                            return SimpleNamespace(returncode=code, stdout=output)
                        invoke = native.run_installer
                        with mock.patch.object(native, 'run_installer', side_effect=lambda *args:
                                invoke(*args, run=installer_process)) as reconcile:
                            self.assertEqual(native._key(source, home, run=window), 0)
                        final = tomllib.loads(path.read_text())
                        self.assertEqual(final.get('model'), picked or (
                            config.DEFAULT_MODEL if mode == 'none' else None))
                        self.assertEqual(final.get('model_provider'), 'scg_router' if mode == 'none' else None)
                        self.assertEqual(config.codex_attachment(home)['openai_mode'], mode)
                        self.assertEqual(final['approval_policy'], 'never')
                        self.assertEqual(json.loads((home / 'mixed-router-state.json').read_text())['owner_setting'], 'keep')
                        self.assertEqual(len(reconcile.call_args_list), int(mode == 'none'))

    def test_both_late_choices_use_one_installer_reconciliation(self):
        native = module('native_setup')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source, home = resources(root / 'Resources'), root / 'router'
            home.mkdir()
            (home / 'current').write_text('1.2.0')
            state = dict(port=1, token='synthetic', clients='both',
                         openai_mode='subscription', claude_mode='subscription',
                         setup=dict(nonce='synthetic', expires=time.time() + 3600))
            state_path = home / 'mixed-router-state.json'
            state_path.write_text(json.dumps(state))
            (home / 'activation.json').write_text(json.dumps({'version': 2, 'clients': {
                'codex': {'openai_mode': 'subscription'}, 'claude': {'claude_mode': 'subscription'}}}))
            def window(*args, **kwargs):
                key_store.store_key(home, 'synthetic-saved-key')
                state.update(openai_mode='none', claude_mode='none')
                state.pop('setup')
                state_path.write_text(json.dumps(state))
                return SimpleNamespace(returncode=0)
            with mock.patch.object(native, 'run_installer', return_value=SimpleNamespace(returncode=0)) as reconcile:
                self.assertEqual(native._key(source, home, run=window), 0)
            reconcile.assert_called_once_with(source, home,
                ['--openai-mode', 'none', '--claude-mode', 'none'])

    def test_real_attachment_preserves_native_default_or_explicit_choice(self):
        config, clients = module('codex_config'), module('client_choice')
        config._atomic_write = module('atomic_write')
        for mode in ('subscription', 'none'):
            for picked in (None, 'native-choice', 'external/owner-choice'):
                with self.subTest(mode=mode, picked=picked), tempfile.TemporaryDirectory() as temporary:
                    user = Path(temporary)
                    home = user / 'router'
                    home.mkdir()
                    path = user / '.codex/config.toml'
                    path.parent.mkdir()
                    if picked:
                        path.write_text('model = "' + picked + '"\nmodel_reasoning_effort = "high"\n')
                    with mock.patch.object(Path, 'home', return_value=user), \
                            contextlib.redirect_stdout(io.StringIO()):
                        clients.attach_codex(home, dict(port=1, token='synthetic'), mode, config)
                        first = tomllib.loads(path.read_text())
                        clients.attach_codex(home, dict(port=1, token='synthetic'), mode, config)
                        self.assertEqual(tomllib.loads(path.read_text()), first)
                    expected = picked or (config.DEFAULT_MODEL if mode == 'none' else None)
                    self.assertEqual(first.get('model'), expected)
                    self.assertEqual(first.get('model_reasoning_effort'),
                                     'high' if picked else config.DEFAULT_MODEL_EFFORT if mode == 'none' else None)
                    self.assertEqual(first.get('model_provider'), 'scg_router' if mode == 'none' else None)


if __name__ == '__main__':
    unittest.main()
