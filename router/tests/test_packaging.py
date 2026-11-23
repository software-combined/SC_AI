import re
import shutil
import subprocess
import sys
import tarfile
import json
import tempfile
import unittest
from pathlib import Path

from tests.loading import load

# Only the members `packaging/release.py` cannot discover by globbing need an
# explicit contract: modules under ai_router/, tools/ and docs/ travel
# automatically, so a new module cannot be forgotten here.
EXPLICIT_FILES = (
    'LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md', 'README.md',
    'packaging/VERSION', 'packaging/install.py', 'packaging/bundle.py',
    'packaging/updater.py', 'packaging/router_launch.py',
    'packaging/service.py', 'packaging/feed.py', 'packaging/runtime.lock',
    'packaging/platforms/windows_tasks.py',
    'packaging/client_executable.py', 'packaging/setup_completion.py',
    'packaging/assets/router-icon.png',
    'packaging/assets/signin.html',
    'packaging/assets/inter-400.woff2', 'packaging/assets/inter-OFL.txt',
    'packaging/assets/space-grotesk-400.woff2', 'packaging/assets/space-grotesk-OFL.txt',
    'packaging/install.sh', 'packaging/install.ps1',
)


def _release_module():
    return load('packaging/release.py', 'router_release')

class PackagingTests(unittest.TestCase):
    def test_apache_only_licence_gate(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md',
                    'pyproject.toml', 'README.md',
                    '.codex-plugin/plugin.json', '.claude-plugin/plugin.json',
                    'packaging/release.py'):
            text = _release_module().source_file(root, rel).read_text().lower()
            for token in ('polyform', 'licenseref-polyform',
                          'commercial_license', 'unlicensed'):
                self.assertNotIn(token, text, rel)
        self.assertFalse((root / 'COMMERCIAL_LICENSE.md').exists())

    def test_wrappers_call_install_py(self):
        root = Path(__file__).resolve().parents[1] / 'packaging'
        sh, ps1 = (root / 'install.sh').read_text(), (root / 'install.ps1').read_text()
        self.assertIn('install.py', sh)
        self.assertIn('install.py', ps1)

    def test_installer_refuses_an_interpreter_older_than_the_runtime(self):
        installer = Path(__file__).resolve().parents[1] / 'packaging' / 'install.py'
        code = 'import runpy, sys; sys.version_info = (3, 13); runpy.run_path(sys.argv[1], run_name="__main__")'
        result = subprocess.run([sys.executable, '-c', code, str(installer), '--help'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertIn('needs Python 3.14', result.stderr)

    def test_file_list_covers_the_runtime_import_closure(self):
        # A fresh copy-install following the bundle inventory must start: every
        # module and data file ships, and the explicit contract below still
        # names the members globbing cannot discover.
        root = Path(__file__).resolve().parents[1]
        bundled = set(_release_module().bundle_files(root))
        for path in sorted((root / 'ai_router').rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            self.assertIn(path.relative_to(root).as_posix(), bundled,
                          'runtime module missing from the bundle')
        for dep in ('ai_router/models.json',
                    'ai_router/routed_base_instructions.txt',
                    'ai_router/subscription_base_instructions.txt'):
            self.assertIn(dep, bundled, dep)
        for tool in ('tools/disable.py', 'tools/provision_key.py'):
            self.assertIn(tool, bundled, tool)
        for name in EXPLICIT_FILES:
            self.assertIn(name, bundled, name)

    def test_packaging_modules_are_all_bundled(self):
        # Every packaging module an installed release can load must be in the
        # release inventory; release.py is the publish-time tool and is the
        # one deliberate exclusion.
        root = Path(__file__).resolve().parents[1]
        bundled = set(_release_module().bundle_files(root))
        for path in sorted((root / 'packaging').rglob('*.py')):
            if '__pycache__' in path.parts:
                continue
            rel = path.relative_to(root).as_posix()
            if rel == 'packaging/release.py':
                continue
            self.assertIn(rel, bundled, 'packaging module missing from the release inventory')

    def test_linked_setup_installs_its_own_build(self):
        # --url-base keeps the built feed pointing at the local tarball.
        root = Path(__file__).resolve().parents[1]
        self.assertIn('(docs/setup.md)', (root.parent / 'README.md').read_text())
        blocks = re.findall(r'```(?:sh|powershell)\n(.*?)```',
                            (root.parent / 'docs' / 'setup.md').read_text(), re.S)
        release_blocks = [block for block in blocks if 'packaging/release.py' in block]
        self.assertEqual(len(release_blocks), 2)
        posix, windows = release_blocks
        self.assertIn('(Path.cwd() / "dist").as_uri()', posix)
        self.assertIn('--url-base "$ROUTER_DIST_URL"', posix)
        self.assertIn('--feed "$ROUTER_DIST_URL/latest.json"', posix)
        self.assertIn('([uri]$RouterDist).AbsoluteUri', windows)
        self.assertIn('--url-base $RouterDistUrl', windows)
        self.assertIn('--feed "$RouterDistUrl/latest.json"', windows)
        with tempfile.TemporaryDirectory(prefix='router source é %25 ') as temporary:
            out = Path(temporary) / 'dist'
            _release_module().main(['--out', str(out), '--url-base', out.as_uri()])
            latest = json.loads((out / 'latest.json').read_text())
            self.assertEqual(latest['url'], (out / Path.from_uri(latest['url']).name).as_uri())
            self.assertTrue(Path.from_uri(latest['url']).is_file())

    def test_release_bundle_contains_deploy_list(self):
        root = Path(__file__).resolve().parents[1]
        release_mod = load(root / 'packaging' / 'release.py', 'router_release')
        out = root / 'dist-test-packaging'
        self.addCleanup(shutil.rmtree, str(out), True)
        release_mod.main(['--out', str(out)])
        tarball = next(out.glob('*.tar.gz'))
        with tarfile.open(tarball, mode='r') as tar:
            names = set(tar.getnames())
        # Single inventory (Plan 123): the tarball must match release.py's
        # bundle_files() exactly, neither missing a member nor shipping an
        # extra. EXPLICIT_FILES below stays an explicit list so a member
        # dropped from the inventory still fails this gate.
        self.assertEqual(names, set(release_mod.bundle_files(root)) | {'MANIFEST.json'})
        for name in EXPLICIT_FILES:
            self.assertIn(name, names, name)

    def test_activation_receipt_has_a_single_writer(self):
        # Plan 095: activation.json is written in exactly one module
        # (codex_config.py, through the shared atomic writer). A second
        # writer literal fails this closed so receipt schema changes
        # cannot silently drift across adapters again.
        root = Path(__file__).resolve().parents[1] / 'packaging'
        writers = sorted(path.relative_to(root).as_posix()
                         for path in root.rglob('*.py')
                         if '__pycache__' not in path.parts
                         and 'activation.json' in path.read_text())
        self.assertEqual(writers, ['codex_config.py'])

    def test_version_is_semver(self):
        version = (Path(__file__).resolve().parents[1] / 'packaging' / 'VERSION').read_text().strip()
        self.assertRegex(version, r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')

    def test_build_composes_full_version_and_manifest(self):
        root = Path(__file__).resolve().parents[1]
        base = (root / 'packaging' / 'VERSION').read_text().strip()
        tag = f'v{base}'
        release_mod = _release_module()
        out = root / 'dist-test-build'
        self.addCleanup(shutil.rmtree, str(out), True)
        release_mod.main(['--out', str(out), '--build', '57',
                          '--sha', 'abc123', '--channel', 'beta'])
        tarball = next(out.glob('*.tar.gz'))
        self.assertEqual(tarball.name, f'ai-router-{base}.57.tar.gz')
        with tarfile.open(tarball, mode='r') as tar:
            manifest = json.loads(tar.extractfile('MANIFEST.json').read())
        self.assertEqual(manifest['version'], f'{base}.57')
        self.assertEqual(manifest['git_sha'], 'abc123')
        self.assertEqual(manifest['channel'], 'beta')
        with tarfile.open(tarball, mode='r') as tar:
            marker = tar.extractfile('packaging/VERSION').read().decode()
            self.assertEqual(marker, f'{base}.57\n')
        latest = json.loads((out / 'latest.json').read_text())
        self.assertTrue(
            latest['url'].endswith(f'/{tag}-beta/ai-router-{base}.57.tar.gz'),
            latest['url'])

    def test_default_channel_builds_stable_url(self):
        root = Path(__file__).resolve().parents[1]
        base = (root / 'packaging' / 'VERSION').read_text().strip()
        tag = f'v{base}'
        release_mod = _release_module()
        out = root / 'dist-test-stable'
        self.addCleanup(shutil.rmtree, str(out), True)
        release_mod.main(['--out', str(out)])
        latest = json.loads((out / 'latest.json').read_text())
        self.assertTrue(
            latest['url'].endswith(f'/{tag}/ai-router-{base}.0.tar.gz'),
            latest['url'])

if __name__ == '__main__':
    unittest.main()
