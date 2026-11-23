"""Every backend answers the repair hooks, and shared modules ask the host backend."""
import contextlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.loading import load
from tests import test_native_resources as resource_fixtures


def _platforms():
    return load('packaging/platforms/__init__.py', 'router_platforms_under_test')


HOME, LATEST, FEED = Path('home'), dict(version='1.0.1'), 'file:///latest.json'
SERVICE = SimpleNamespace(run=mock.Mock())
# Each Windows hook, the windows_installation body it must reach, and whether that body gets the backend.
WINDOWS = (
    ('recover_interrupted', (HOME,), 'restore', True),
    ('reconcile_after_update', (HOME, SERVICE), 'reconcile', True),
    ('prepare_maintenance', (HOME, HOME, LATEST, dict(feed=FEED)), 'prepare', False),
    ('installation_ready', (HOME,), 'ready', False),
    ('repair_controls', (HOME, LATEST, FEED, None), 'controls', True),
)
DEFAULTS = dict(recover_interrupted='inactive', reconcile_after_update='inactive', recover_pending=None,
                prepare_maintenance=None, finish_maintenance=None, verified_after_timeout=False,
                controls_ready=True, installation_ready=True, repair_controls=None)
ARGS = dict(recover_interrupted=(HOME,), reconcile_after_update=(HOME, SERVICE),
            recover_pending=('python', HOME, HOME, '1.0.0'), prepare_maintenance=(HOME, HOME, LATEST, {}),
            finish_maintenance=(HOME, None, None), verified_after_timeout=(HOME, LATEST, SERVICE),
            controls_ready=(HOME,), installation_ready=(HOME,), repair_controls=(HOME, LATEST, FEED, None))


class RepairHookTests(unittest.TestCase):
    def test_every_backend_answers_every_repair_hook(self):
        platforms = _platforms()
        hooks = {name for name in vars(platforms.NoRepair) if not name.startswith('_')}
        self.assertEqual(hooks, set(DEFAULTS))
        for name in ('darwin', 'linux'):
            backend = platforms.select(name, SERVICE, SERVICE.run)
            for hook in hooks:
                self.assertEqual(getattr(type(backend), hook).__qualname__, 'NoRepair.' + hook)
                self.assertEqual(getattr(backend, hook)(*ARGS[hook]), DEFAULTS[hook])
        windows = type(platforms.select('win32', SERVICE, SERVICE.run))
        for hook in hooks:
            self.assertNotEqual(getattr(windows, hook).__qualname__, 'NoRepair.' + hook)

    def test_unsupported_host_keeps_the_no_op_hooks(self):
        platforms = _platforms()
        with mock.patch.object(platforms.sys, 'platform', 'freebsd14'):
            backend = platforms.host(SERVICE)
        for hook, default in DEFAULTS.items():
            self.assertEqual(getattr(backend, hook)(*ARGS[hook]), default)

    def test_windows_hooks_run_the_installation_bodies(self):
        platforms = _platforms()
        backend = platforms.select('win32', SERVICE, SERVICE.run)
        owner = platforms._windows_mod()._installation
        for hook, args, body, passes_backend in WINDOWS:
            with self.subTest(hook=hook), mock.patch.object(owner, 'pending', return_value=True), \
                    mock.patch.object(owner, body, return_value=dict(source=HOME)) as called:
                getattr(backend, hook)(*args)
                called.assert_called_once()
                self.assertEqual(backend in called.call_args.args, passes_backend)
        native = SimpleNamespace(ready=mock.Mock(return_value=False), deliver=mock.Mock(return_value=False))
        reconcile = SimpleNamespace(verified_timeout=mock.Mock(return_value=True))
        modules = dict(native_resources=native, update_reconcile=reconcile)
        with mock.patch.object(owner, 'load', side_effect=modules.__getitem__):
            self.assertFalse(backend.controls_ready(HOME))
            self.assertFalse(backend.finish_maintenance(HOME, dict(latest=LATEST, feed=FEED), None))
            self.assertTrue(backend.finish_maintenance(HOME, None, None))
            self.assertTrue(backend.verified_after_timeout(HOME, LATEST, SERVICE))
        native.ready.assert_called_once_with(HOME)
        native.deliver.assert_called_once_with(HOME, LATEST, FEED, None)
        reconcile.verified_timeout.assert_called_once_with(HOME, LATEST, SERVICE)

    def test_shared_modules_ask_the_host_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            owner, home, latest, data = resource_fixtures.NativeResourcesTests().fixture(Path(temporary))
            original, feed = owner.load, 'https://dist.softwarecombined.com/stable/latest.json'
            def install(home, permanent, python):
                (home / 'setup-current').write_text(permanent.name)
            with mock.patch.object(owner, 'load', side_effect=lambda name:
                    SimpleNamespace(install=install) if name == 'native_shortcuts' else original(name)):
                self.assertTrue(owner.deliver(home, latest, feed, lambda _: data))
            self.assertTrue(owner.ready(home))
            backend, fetch = mock.Mock(), mock.Mock()
            backend.installation_ready.return_value = False
            backend.repair_controls.return_value = True
            with mock.patch.object(owner, '_backend', return_value=backend):
                self.assertFalse(owner.ready(home))
                self.assertTrue(owner.reconcile(home, latest, feed, fetch))
            backend.installation_ready.assert_called_once_with(home)
            backend.repair_controls.assert_called_once_with(home, latest, feed, fetch)
            fetch.assert_not_called()  # The backend's repair replaced the shared delivery.
            maintenance = load('packaging/update_reconcile.py')
            backend.reconcile_after_update.return_value = 'deferred'
            service = SimpleNamespace(load=lambda *_: SimpleNamespace(host=lambda _: backend))
            self.assertEqual(maintenance.run(home, service)['installation'], 'deferred')
            backend.reconcile_after_update.assert_called_once_with(home, service)
            runtime = load('packaging/runtime_rebind.py')
            with mock.patch.object(runtime.load('service'), 'load',
                                   return_value=SimpleNamespace(host=lambda _: SimpleNamespace())), \
                    mock.patch.object(runtime, 'load', wraps=runtime.load) as loaded:
                self.assertEqual(runtime.reconcile(home), 'inactive')
            self.assertEqual([call.args for call in loaded.call_args_list], [('service',), ('update_status',)])

    def test_post_update_repair_keeps_one_fixed_step_order(self):
        maintenance, calls = load('packaging/update_reconcile.py'), []

        def step(name, preflight, applied):
            def run(*_, apply=True):
                calls.append((name, apply))
                return applied if apply else preflight
            return run
        backend = SimpleNamespace(reconcile_after_update=step('installation', 'inactive', 'inactive'))
        modules = dict(
            codex_recovery=SimpleNamespace(reconcile=step('attachment', 'repairable', 'repaired'),
                                           offer=lambda *_: calls.append(('offer', True))),
            runtime_rebind=SimpleNamespace(reconcile=step('runtime', 'repairable', 'ready')),
            install_delivery=SimpleNamespace(assistant_status=lambda *_: calls.append(('assistants', True)) or 'ready'))
        state = SimpleNamespace(read=lambda _: dict(clients='codex'), path=lambda home: home,
                                saved_clients=lambda doc: doc['clients'], update=mock.Mock())
        service = SimpleNamespace(load=lambda *_: SimpleNamespace(host=lambda _: backend), _state=state,
                                  _atomic_write=None, install_lock=lambda _: contextlib.nullcontext(True))
        original = maintenance.load
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(maintenance, 'load', side_effect=lambda name: modules.get(name) or original(name)):
            outcomes = maintenance.run(Path(temporary), service)
        self.assertEqual(outcomes, dict(installation='inactive', attachment='repaired', runtime='ready'))
        # Unlocked preflight in step order, then the locked changes, then the notice.
        self.assertEqual(calls, [('installation', True), ('attachment', False), ('runtime', False),
                                 ('attachment', True), ('assistants', True), ('runtime', True), ('offer', True)])
        state.update.assert_called_once()


if __name__ == '__main__':
    unittest.main()
