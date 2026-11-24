"""The repeat gate uses verified local code, read-only readiness, and a bounded health check."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests.test_native_setup import module


ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.4.1.1'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


class RepeatReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.resources = self.root / 'Resources'
        self.home = self.root / 'home'
        self.repeat = module('windows_repeat')
        self.manifest = {'version': VERSION, 'files': {'packaging/VERSION': hashlib.sha256(
            VERSION.encode()).hexdigest()}}
        for root in (self.resources / 'router', self.home / 'releases' / VERSION, self.home / 'control' / VERSION):
            (root / 'packaging').mkdir(parents=True)
            (root / 'packaging/VERSION').write_text(VERSION)
            (root / 'MANIFEST.json').write_text(json.dumps(self.manifest))
        self.state = {'port': 45678, 'token': 'synthetic-loopback-token'}
        self.health = mock.Mock(return_value={'status': 'ok', 'version': VERSION})
        service = SimpleNamespace(_state=SimpleNamespace(path=lambda home: home / 'state.json',
            read_strict=lambda _: self.state), health=self.health, current_version=lambda _: VERSION)
        self.tasks = mock.Mock(return_value=True)
        self.controls = mock.Mock(return_value=True)
        self.choices = mock.Mock(return_value=True)
        self.keys = mock.Mock(return_value=[])
        native = SimpleNamespace(ready=self.controls, current=lambda _: self.resources,
                                 _backend=lambda: SimpleNamespace(runtime_matches=self.tasks))
        diagnostics = SimpleNamespace(_provider_defs=lambda: SimpleNamespace(unhandled=self.keys),
                                      _key_private=lambda _: True)
        modules = {'service': service, 'native_resources': native, 'bundle': module('bundle'),
                   'native_readiness': SimpleNamespace(choices_applied=self.choices),
                   'diagnostics': diagnostics}
        patch = mock.patch.object(self.repeat, 'load', side_effect=modules.__getitem__)
        patch.start()
        self.addCleanup(patch.stop)

    def test_exact_live_ready_cohort_passes(self):
        self.assertTrue(self.repeat.ready(self.home, self.resources, VERSION))
        self.tasks.assert_called_once_with(str(self.resources / 'runtime/python/pythonw.exe'), self.home)
        self.health.assert_called_once_with(self.state, timeout=3)

    def test_unknown_or_inconsistent_state_never_passes(self):
        for gate in (self.controls, self.choices, self.tasks):
            with self.subTest(gate=gate):
                gate.return_value = False
                self.assertFalse(self.repeat.ready(self.home, self.resources, VERSION))
                gate.return_value = True
        self.state['port'] = 'unknown'
        self.assertFalse(self.repeat.ready(self.home, self.resources, VERSION))
        self.health.assert_not_called()

    def test_stopped_or_different_release_never_passes(self):
        for reply in (None, {'status': 'ok', 'version': '1.4.1.2'}):
            self.health.return_value = reply
            self.assertFalse(self.repeat.ready(self.home, self.resources, VERSION))

    def test_missing_or_unusable_key_leaves_normal_setup_available(self):
        self.keys.return_value = ['synthetic provider']
        self.assertFalse(self.repeat.ready(self.home, self.resources, VERSION))
        self.keys.side_effect = SystemExit('synthetic permissions failure')
        with self.assertRaises(SystemExit):
            self.repeat.ready(self.home, self.resources, VERSION)
        self.health.assert_not_called()

    def test_corrupt_same_version_controller_fails_before_health(self):
        (self.home / 'control' / VERSION / 'packaging/VERSION').write_text('x' * len(VERSION))
        with self.assertRaises(SystemExit):
            self.repeat.ready(self.home, self.resources, VERSION)
        self.health.assert_not_called()


@unittest.skipUnless(os.name == 'nt' and CSC.is_file(), 'requires the Windows .NET Framework compiler')
class NativeRepeatProbeTests(unittest.TestCase):
    def test_compiled_probe_never_launches_unknown_or_changed_runtime(self):
        with tempfile.TemporaryDirectory(prefix='native repeat with spaces ') as temporary:
            self.run_probe_cases(Path(temporary))

    def run_probe_cases(self, root):
        _, exe = self.compile(root, 'check', '''
class Check {
    static int Main(string[] args) {
        try { return WindowsRepeat.Ready(args[0], args[1]) ? 0 : 1; }
        catch (System.Exception) { return 1; }
    }
}
''', ROOT / 'packaging/native/menu/windows_repeat.cs')
        profile = root / 'synthetic user'
        home = profile / '.codex/mixed-model-router'
        name = VERSION + '-' + 'a' * 16
        resources = home / 'setup' / name
        runtime = resources / 'runtime/python'
        runtime.mkdir(parents=True)
        (home / 'current').write_text(VERSION)
        (home / 'setup-current').write_text(name)
        (home / 'install.lock').touch()
        with (home / 'install.lock').open('rb') as lock:
            self.assertEqual(lock.read(), b'')
        _, interpreter = self.compile(runtime, 'python', '''
class Fixture {
    static int Main(string[] args) {
        System.IO.File.WriteAllText(System.Environment.GetEnvironmentVariable("SCG_TEST_REPEAT_PROBE"), "called");
        return args.Length == 8 && args[0] == "-I" && args[1] == "-S" && args[2] == "-B"
            && args[3] == "-X" && args[4].StartsWith("pycache_prefix=") ? 0 : 1;
    }
}
''')
        (runtime / 'python.cs').unlink()
        probe = resources / 'router/packaging/windows_repeat.py'
        probe.parent.mkdir(parents=True)
        probe.write_text('fixture')
        inventory = root / 'repeat-files.txt'
        inventory.write_text(f'{VERSION}\n' + 'a' * 64 + '\n' + ''.join(
            f'{hashlib.sha256(file.read_bytes()).hexdigest()}\t{file.relative_to(resources).as_posix()}\n'
            for file in (interpreter, probe)))
        marker = root / 'probe-called'

        def run():
            marker.unlink(missing_ok=True)
            env = dict(os.environ, SCG_TEST_REPEAT_PROBE=str(marker))
            return subprocess.run([exe, inventory, profile], env=env, timeout=20).returncode

        cache = probe.parent / '__pycache__'
        cache.mkdir()
        (cache / 'generated.pyc').write_bytes(b'untrusted cache')
        self.assertEqual(run(), 0)
        self.assertTrue(marker.is_file())
        (home / 'current').write_text('1.4.1.2')
        self.assertEqual(run(), 1)
        self.assertFalse(marker.exists())
        (home / 'current').write_text(VERSION)
        extra = probe.with_name('sitecustomize.py')
        extra.write_text('unexpected executable source')
        self.assertEqual(run(), 1)
        self.assertFalse(marker.exists())
        extra.unlink()
        probe.write_text('changed')
        self.assertEqual(run(), 1)
        self.assertFalse(marker.exists())
        probe.write_text('fixture')
        from msvcrt import LK_NBLCK, locking
        with (home / 'install.lock').open('r+b') as guard:
            locking(guard.fileno(), LK_NBLCK, 1)
            self.assertEqual(run(), 1)
            self.assertFalse(marker.exists())
        interpreter.unlink()
        self.assertEqual(run(), 1)
        self.assertFalse(marker.exists())

    @staticmethod
    def compile(directory, name, content, *files):
        source = directory / (name + '.cs')
        exe = directory / (name + '.exe')
        source.write_text(content)
        subprocess.run([CSC, '/nologo', '/platform:x64', '/out:' + str(exe), source, *files],
                       check=True, capture_output=True, text=True, timeout=30)
        return source, exe
