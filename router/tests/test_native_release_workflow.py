"""Public native downloads use stable; unaccepted platforms remain private."""
import unittest
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

from tests.test_native_beta_assets import NATIVE_NAMES, beta_artifacts, publish
from tests.test_workflows import run_block

WORKFLOW = Path(__file__).resolve().parents[2] / '.github/workflows/release.yml'


class NativeReleaseWorkflowTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'release publication runs on Ubuntu')
    def test_publish_rerun_keeps_existing_release_and_assets(self):
        step = WORKFLOW.read_text().split('      - name: Create release\n', 1)[1]
        script = textwrap.dedent(step.split('        run: |\n', 1)[1])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'dist').mkdir()
            (root / 'dist/release-latest.json').write_text('{}')
            (root / 'dist/example.tar.gz').write_bytes(b'fixture')
            gh = root / 'gh'
            gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SCG_TEST_CALLS"\n'
                          'if [ "$2" = view ]; then exit "$SCG_TEST_VIEW"; fi\n')
            gh.chmod(0o755)
            calls = root / 'calls'
            for exists in (True, False):
                with self.subTest(existing_release=exists):
                    calls.write_text('')
                    result = subprocess.run(['bash', '-c', script], cwd=root, capture_output=True,
                        env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                             'SCG_TEST_CALLS': str(calls), 'SCG_TEST_VIEW': '0' if exists else '1',
                             'CHANNEL': 'stable', 'GITHUB_REF_NAME': 'v1.2.11'})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    actions = calls.read_text().splitlines()
                    self.assertEqual(any(line.startswith('release create ') for line in actions), not exists)
                    self.assertFalse(any('upload' in line or 'delete' in line for line in actions))

    @unittest.skipIf(os.name == 'nt', 'release publication runs on Ubuntu')
    def test_beta_creates_exact_assets_and_existing_releases_require_matching_bodies(self):
        script = (run_block('Publish to the update feed', WORKFLOW.read_text()) + '\n'
                  + run_block('Create release', WORKFLOW.read_text()))
        for case in ('new', 'exact', 'missing', 'different', 'unreadable'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args, public, _ = beta_artifacts(root)
                with mock.patch.object(publish.verify, 'FEED_PUBLIC_KEY', public):
                    publish.stage_beta(args)
                shutil.copyfile(args.dist / 'latest.json', args.dist / 'release-latest.json')
                (args.dist / 'feed-latest.json.sig').write_bytes(b'synthetic feed signature')
                required = {p.name: p for p in args.stage_beta.iterdir()}
                required.update({'ai-router-1.2.3.4.tar.gz': args.dist / 'ai-router-1.2.3.4.tar.gz',
                    'latest-beta.json': args.dist / 'release-latest.json',
                    'feed-latest.json.sig': args.dist / 'feed-latest.json.sig'})
                remote = root / 'remote'
                remote.mkdir()
                for name, path in required.items():
                    if case == 'missing' and name == NATIVE_NAMES['windows/x86_64']:
                        continue
                    (remote / name).write_bytes(b'wrong' if case == 'different'
                        and name == NATIVE_NAMES['windows/x86_64'] else path.read_bytes())
                gh = root / 'gh'
                gh.write_text(f'#!{sys.executable}\n' + textwrap.dedent('''\
                    import json,os,shutil,sys
                    from pathlib import Path
                    args=sys.argv[1:]
                    if args[0]=='api':
                        if args[1].endswith('/releases'):
                            if os.environ['SCG_TEST_CASE']=='unreadable': raise SystemExit(1)
                            if os.environ['SCG_TEST_CASE']!='new': print(os.environ['GITHUB_REF_NAME'])
                        else: print(os.environ['GITHUB_SHA'])
                        raise SystemExit(0)
                    with open(os.environ['SCG_TEST_CALLS'],'a') as out:
                        out.write(json.dumps(args)+'\\n')
                    if args[:2]==['release','view']:
                        raise SystemExit(int(os.environ['SCG_TEST_VIEW']))
                    if args[:2]==['release','download']:
                        output=Path(args[args.index('--dir')+1])
                        for index, value in enumerate(args):
                            if value=='--pattern':
                                source=Path(os.environ['SCG_TEST_REMOTE'])/args[index+1]
                                if source.is_file(): shutil.copyfile(source,output/source.name)
                    '''))
                gh.chmod(0o755)
                calls = root / 'calls'
                stubs = '''
                    aws() { printf 'synthetic-seed\\n'; }
                    python() {
                      case "$*" in
                        *publish_feed.py*)
                          case "$*" in *--prepare-only*) return 0;; esac
                          touch published;;
                      esac
                    }
                '''
                result = subprocess.run(['bash', '-e', '-c', textwrap.dedent(stubs) + script], cwd=root, capture_output=True,
                    env={**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                         'SCG_TEST_CALLS': str(calls), 'SCG_TEST_REMOTE': str(remote),
                         'SCG_TEST_CASE': case,
                         'SCG_TEST_VIEW': '1' if case == 'new' else '0',
                         'CHANNEL': 'beta', 'GITHUB_REF_NAME': 'v1.2.3-beta',
                         'GITHUB_SHA': 'a' * 40, 'GITHUB_REPOSITORY': 'example/router',
                         'NATIVE_INSTALLERS_ACCEPTED': 'true'})
                self.assertEqual(result.returncode == 0, case in ('new', 'exact'), result.stderr)
                self.assertEqual((root / 'published').exists(), case in ('new', 'exact'))
                commands = ([json.loads(line) for line in calls.read_text().splitlines()]
                            if calls.exists() else [])
                creates = [command for command in commands if command[:2] == ['release', 'create']]
                self.assertEqual(len(creates), int(case == 'new'))
                self.assertFalse(any('upload' in command or 'delete' in command for command in commands))
                if creates:
                    self.assertIn('--verify-tag', creates[0])
                    self.assertIn('--prerelease', creates[0])
                    self.assertEqual({Path(value).name for value in creates[0]
                        if (root / value).is_file()}, set(required))
                elif case != 'unreadable':
                    download = next(command for command in commands
                                    if command[:2] == ['release', 'download'])
                    self.assertEqual({download[i+1] for i, value in enumerate(download)
                                      if value == '--pattern'}, set(required))

    @unittest.skipIf(os.name == 'nt', 'release publication runs on Ubuntu')
    def test_beta_requires_all_platforms_and_staging_success_before_feed_publication(self):
        script = run_block('Publish to the update feed', WORKFLOW.read_text())
        for channel, accepted, staged, allowed in (
                ('beta', 'true', '1', True), ('beta', 'false', '1', False),
                ('beta', 'true', '0', False), ('stable', 'false', '1', True)):
            with self.subTest(channel=channel, accepted=accepted, staged=staged), \
                    tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stubs = '''
                    gh() {
                      if [ "$1" = api ]; then
                        case "$2" in */releases) return 0;; esac
                        printf '%s\\n' "$GITHUB_SHA"
                      else return 1; fi
                    }
                    aws() { printf '%s' "$SEED_FILE" > seed-path; printf 'synthetic-seed\\n'; }
                    python() {
                      printf '%s\\n' "$*" >> python-calls
                      case "$*" in
                        *--stage-beta*) return "$SCG_TEST_STAGED";;
                        *--prepare-only*) mkdir -p dist; touch dist/release-latest.json;;
                        *publish_feed.py*) touch published;;
                      esac
                    }
                '''
                # Exit0 means successful staging; the label keeps cases easy to read.
                result = subprocess.run(['bash', '-e', '-c', textwrap.dedent(stubs) + script],
                    cwd=root, capture_output=True, env={**os.environ, 'CHANNEL': channel,
                        'NATIVE_INSTALLERS_ACCEPTED': accepted,
                        'NATIVE_INSTALLERS_MACOS_ARM64_ONLY': 'true',
                        'SCG_TEST_STAGED': '0' if staged == '1' else '1',
                        'GITHUB_SHA': 'a' * 40, 'GITHUB_REPOSITORY': 'example/router',
                        'GITHUB_REF_NAME': 'v1.2.3-beta'})
                self.assertEqual(result.returncode == 0, allowed, result.stderr)
                self.assertEqual((root / 'published').exists(), allowed)
                self.assertFalse(Path((root / 'seed-path').read_text()).exists())
                commands = ((root / 'python-calls').read_text().splitlines()
                            if (root / 'python-calls').exists() else [])
                stage_commands = [command for command in commands if '--stage-beta' in command]
                self.assertEqual(len(stage_commands), int(channel == 'beta' and accepted == 'true'))
                if stage_commands and allowed:
                    self.assertIn('--stage-beta', commands[0])
                    self.assertIn('publish_feed.py', commands[1])

    def test_windows_checks_release_subset_and_native_acl_in_separate_powershell_steps(self):
        release = WORKFLOW.read_text()
        command = release.split('      - name: Native packaging contracts\n', 1)[1]
        command = command.split('        run: ', 1)[1].splitlines()[0]
        check = WORKFLOW.with_name('check.yml').read_text()
        windows = check.split('  installer-windows:\n', 1)[1].split('  installer-python39:\n', 1)[0]
        steps = {block.splitlines()[0]: block.rstrip().splitlines()[1:]
                 for block in windows.split('      - name: ')[1:]}
        for name, run in (
                ('Native packaging contracts (PowerShell)', command),
                ('Native ACL contract (PowerShell)', 'python -m unittest tests.test_windows_acl_native')):
            with self.subTest(step=name):
                self.assertEqual(steps.get(name), ['        shell: pwsh', '        run: ' + run])

    def test_native_builds_stay_out_of_public_actions_artifacts(self):
        text = WORKFLOW.read_text()
        native = text.split('  native:', 1)[1].split('  publish:', 1)[0]
        self.assertNotIn('actions/upload-artifact', native)
        self.assertIn('/native-builds/', native)
        self.assertIn('role-session-name: router-native-build', native)

    def test_native_pilot_does_not_suppress_normal_update_publication(self):
        text = WORKFLOW.read_text()
        self.assertNotIn('PILOT_ONLY', text)
        publish = text.split('      - name: Publish to the update feed', 1)[1]
        self.assertIn('python tools/publish_feed.py', publish)
        self.assertNotIn('--download-config', publish)
        release = text.split('      - name: Create release', 1)[1]
        self.assertIn('dist/*.tar.gz', release)
        self.assertIn('--prerelease', release)

    def test_native_downloads_require_stable_and_a_platform_publication_gate(self):
        text = WORKFLOW.read_text()
        self.assertIn('if [ "$CHANNEL" = stable ] && {', text)
        self.assertIn('NATIVE_INSTALLERS_MACOS_ARM64_ONLY', text)
        self.assertIn('NATIVE_OPTIONS=(--macos-arm64-only)', text)
        self.assertNotIn('NATIVE_INSTALLERS_PILOT', text)


if __name__ == '__main__':
    unittest.main()
