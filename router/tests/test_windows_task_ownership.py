"""Owned task contracts and a real, disposable Windows Task Scheduler proof."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_windows_backend import _backend, _install, _query, _state_file, _verbs, backend, service
from tests.test_windows_task_state import _CurrentInstallerFixture
from tests.windows_native_fixture import FIXTURE_LIFETIME, NativeChild, cleanup, task_diagnostics, write_launcher


class OwnershipTests(unittest.TestCase):
    def test_foreign_or_inaccessible_tasks_refuse_install_and_uninstall(self):
        for kind in ('foreign', 'denied'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                state = {'query': {'kind': kind}}
                calls = []
                obj = _backend(state, calls)
                with self.assertRaises(backend._tasks.OwnershipError):
                    _install(obj, Path(tmp))
                with self.assertRaises(backend._tasks.OwnershipError):
                    obj.uninstall(Path(tmp))
                self.assertFalse({'stop', 'delete', 'disable'} & set(_verbs(calls)))


class ExplicitStopTests(_CurrentInstallerFixture, unittest.TestCase):
    def test_pending_updaters_preserve_stop_until_explicit_restart_and_health(self):
        for pending in (backend.UPDATE_TASK, backend.EXPRESS_TASK):
            for stuck in (False, True):
                with self.subTest(pending=pending, stuck=stuck), tempfile.TemporaryDirectory() as tmp:
                    home, calls = self._home(tmp), []
                    tasks = {'query': _query(4), 'stuck': stuck,
                             backend.UPDATE_TASK: _query(1), backend.EXPRESS_TASK: _query(1)}
                    tasks[pending]['pending'] = True
                    obj = _backend(tasks, calls)
                    clock = SimpleNamespace(monotonic=iter((0, 11)).__next__)
                    with mock.patch.object(backend, 'time', clock):
                        if stuck:
                            with self.assertRaisesRegex(SystemExit, 'did not exit'):
                                obj.stop(home)
                        else:
                            obj.stop(home)
                    self.assertFalse(tasks['query']['enabled'])
                    self.assertFalse(tasks['query']['pending'])
                    self.assertEqual(bool(tasks['query']['instances']), stuck)
                    before = {name: dict(tasks[name]) for name in ('query', backend.UPDATE_TASK, backend.EXPRESS_TASK)}
                    calls.clear()
                    self.assertEqual(self._run(home, tasks, calls)[0], 0)
                    self.assertTrue(all(call['operation'] == 'query' for call in calls))
                    self.assertEqual({name: tasks[name] for name in before}, before)
                    self.assertTrue(tasks[pending]['pending'])
                    tasks['stuck'] = False
                    with mock.patch.object(service, 'health', return_value={'version': '1.0.0'}), \
                            mock.patch.object(backend, '_post_shutdown',
                                              side_effect=lambda _: tasks['query'].update(instances=[])):
                        _backend(tasks, []).restart(home)
                    self.assertTrue(tasks['query']['enabled'])
                    self.assertTrue(tasks[pending]['pending'])
                    self.assertEqual(self._run(home, tasks, [])[0], 0)
                    self.assertTrue(tasks[pending]['enabled'])
                    self.assertFalse(tasks[pending]['pending'])
                    other = backend.EXPRESS_TASK if pending == backend.UPDATE_TASK else backend.UPDATE_TASK
                    self.assertFalse(tasks[other]['enabled'])


@unittest.skipUnless(sys.platform == 'win32', 'requires the real Windows Task Scheduler')
class NativeTaskTests(unittest.TestCase):
    @contextmanager
    def scheduler(self):
        obj = backend.Backend(service, subprocess.run)
        sid = obj._identity()
        base = 'SCG-CI-' + uuid.uuid4().hex
        name = base + '-' + sid
        with tempfile.TemporaryDirectory(prefix='router é & [] $ ') as tmp:
            home = Path(tmp)
            _state_file(home)
            children = []
            gate, heartbeat = write_launcher(home, 'router_launch.py', FIXTURE_LIFETIME)
            service.install_task_launcher(home, Path(__file__).resolve().parents[1])
            arguments = backend._arguments(home, 'router_launch.py', backend.ROUTER_LOG)
            xml = backend.render_router_xml(sys.executable, home, sid).replace(
                '<Settings>', '<Settings><Hidden>true</Hidden>')
            # Lifecycle steps start tasks explicitly; automatic recovery would race stopped-state checks.
            xml, replaced = re.subn(r'<Triggers>.*?</Triggers>', '<Triggers/>', xml, flags=re.S)
            self.assertEqual(replaced, 1)
            def call(operation='query', **changes):
                return backend._tasks.invoke(obj._call, changes.get('sid', sid), name,
                    changes.get('arguments', arguments), operation, changes.get('xml', xml),
                    executable=changes.get('executable'))
            self.obj, self.home, self.base, self.sid, self.name = obj, home, base, sid, name
            self.call, self.arguments, self.xml = call, arguments, xml
            self.gate, self.heartbeat, self.children = gate, heartbeat, children
            try:
                yield
            finally:
                gate.unlink(missing_ok=True)
                cleanup(obj._call, [name], children)

    def wait_running(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = self.call()
            if result and result['instances'] and self.heartbeat.exists():
                return result
            time.sleep(0.2)
        self.fail('disposable task did not start: ' + json.dumps(task_diagnostics(
            self.obj._call, self.name, self.heartbeat, self.home / 'logs' / backend.ROUTER_LOG)))

    def test_registration_restore_and_foreign_identity(self):
        with self.scheduler():
            call = self.call
            self.assertIsNone(call())
            self.assertEqual(call('register')['state'], 1)
            self.assertEqual(call('register')['state'], 1)
            status = call()
            self.assertFalse(status['enabled'])
            self.assertTrue(status['pending'])  # Read back from a fresh PowerShell process.
            saved = call('snapshot')
            self.assertEqual(saved['executable'], backend._pythonw(sys.executable))
            call('rebind', executable=sys.executable)
            status = call()
            self.assertEqual(status['executable'], sys.executable)
            self.assertFalse(status['enabled'])
            self.assertTrue(status['pending'])
            call('restore', xml=saved['xml'])
            restored = call('snapshot')
            self.assertEqual(restored['executable'], saved['executable'])
            self.assertEqual(restored['xml'], saved['xml'])
            for changes in ({'sid': 'S-1-5-18'}, {'arguments': self.arguments + ' foreign'}):
                for operation in ('register', 'rebind', 'restore', 'snapshot', 'handover',
                                  'run', 'complete', 'enable', 'disable', 'stop', 'delete'):
                    with self.assertRaises(backend._tasks.OwnershipError):
                        call(operation, **changes)
            self.assertEqual(call('snapshot')['xml'], saved['xml'])

    def test_restart_and_pending_state(self):
        with self.scheduler():
            call, obj, home = self.call, self.obj, self.home
            call('register')
            self.assertIn(call('enable')['state'], (2, 3, 4))
            status = call()
            self.assertTrue(status['enabled'])
            self.assertFalse(status['pending'])
            call('run')
            original = self.wait_running()['instances']
            call('register')
            self.assertTrue(set(original) & set(call()['instances']))
            with mock.patch.object(backend, 'ROUTER_TASK', self.base), \
                    mock.patch.object(backend, '_post_shutdown', return_value=False), \
                    mock.patch.object(backend, 'DRAIN_TIMEOUT_S', 0):
                call('stop')
                self.assertTrue(obj._wait_stopped(self.base, 10, home))
                self.assertEqual(call()['state'], 3)
                call('disable')
                self.assertEqual(call('register')['state'], 1)
                self.assertFalse(call()['pending'])
                call('run')
                original = self.wait_running()['instances']
                # Only health is simulated; marker and instance transitions use the real API.
                with mock.patch.object(service, 'wait_version', return_value=False):
                    with self.assertRaisesRegex(SystemExit, '0.0.0'):
                        obj.restart(home)
                self.assertTrue(call()['pending'])
                self.assertTrue(call('run')['pending'])  # Run cannot acknowledge health.
                with mock.patch.object(service, 'wait_version', return_value=True):
                    obj.restart(home)
                self.assertFalse(call()['pending'])
            self.assertTrue(set(original).isdisjoint(self.wait_running()['instances']))
            call('handover')
            status = call()
            self.assertTrue(status['pending'])
            self.assertFalse(status['enabled'])
            self.assertTrue(status['instances'])
            call('disable')  # An explicit stop cancels pending recovery.
            self.assertFalse(call()['pending'])
            call('run')

    def test_deleted_task_keeps_child_and_missing_metadata_cannot_prove_exit(self):
        with self.scheduler():
            call = self.call
            call('register')
            call('disable')
            call('run')
            self.wait_running()
            child = NativeChild.capture(self.heartbeat)
            self.children.append(child)
            child.assert_alive('before-delete')
            call('delete')
            child.assert_alive('before-metadata-check')
            with mock.patch.object(backend, 'ROUTER_TASK', self.base):
                with self.assertRaisesRegex(SystemExit, 'exit is unverified|cannot verify Windows task') as refused:
                    self.obj._wait_stopped(self.base, 0, self.home)
            reason = 'missing' if 'disappeared' in str(refused.exception) else 'unverified'
            print('Windows fixture metadata refusal: ' + reason, flush=True)
            child.assert_alive('after-metadata-refusal')
            self.gate.unlink()
            self.assertTrue(child.wait_exit(15), 'the deleted task child did not exit')
            print('Windows fixture deleted child: exited=True', flush=True)
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    self.assertIsNone(call())
                    break
                except SystemExit:
                    pass
                time.sleep(0.2)
            self.assertIsNone(call())

    def test_matching_arguments_do_not_own_a_foreign_executable(self):
        with self.scheduler():
            self.call('register')
            foreign = self.xml.replace(backend._pythonw(sys.executable), os.environ['COMSPEC'])
            replace = r'''
$ErrorActionPreference = 'Stop'
$r = [Console]::In.ReadToEnd() | ConvertFrom-Json
$s = New-Object -ComObject Schedule.Service; $s.Connect()
$d = $s.NewTask(0); $d.XmlText = $r.xml; $d.Settings.Enabled = $false
$null = $s.GetFolder('\').RegisterTaskDefinition($r.name, $d, 4, $r.sid, $null, 3, $null)
'''
            backend._shell.run_json(replace, dict(name=self.name, sid=self.sid, xml=foreign),
                                    self.obj._call, timeout=60, check=True)
            for operation in ('query', 'register', 'handover', 'run', 'complete', 'stop', 'delete'):
                with self.assertRaises(backend._tasks.OwnershipError):
                    self.call(operation)
