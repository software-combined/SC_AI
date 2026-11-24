"""Codebase readiness scripts stay read-only, honest about gaps and in step with the framework."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests._platform import symlink_or_skip

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT.parent / 'plugins/development/scg-codebase-readiness'
SKILL = PLUGIN / 'skills/codebase-ai-readiness'
SCRIPTS = PLUGIN / 'scripts'


def git(repo, *args):
    subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
                   check=True, capture_output=True)


def run(script, *args):
    return subprocess.run([sys.executable, '-I', str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, cwd=tempfile.gettempdir())


class CodebaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'repo'
        (self.repo / 'docs').mkdir(parents=True)
        (self.repo / 'my docs').mkdir()
        (self.repo / 'my docs/real.md').write_text('# Real\n')
        (self.repo / 'README.md').write_text('# Readme\n')
        (self.repo / 'docs/a.md').write_text(
            '[ok](../README.md)\n[^1]: A footnote\n[home](/)\n[space](../my%20docs/real.md)\n[case](../readme.md)\n'
            '[ref]: ./missing.md\n```\n[code](./not-real.md)\n```\n'
            '1. Step\n   ```\n   [x](./also-not-real.md)\n   ```\n')
        (self.repo / 'big.ts').write_text('x\n' * 450)
        marker = self.repo / 'FSMONITOR_RAN'
        hook = self.repo / 'fsm.sh'
        hook.write_text(f'#!/bin/sh\ntouch "{marker}"\n')
        hook.chmod(0o755)
        git(self.repo, 'init', '-q', '-b', 'main')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        git(self.repo, 'config', 'user.name', 'Test')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-qm', 'init')
        git(self.repo, 'config', 'core.fsmonitor', str(hook))

    def measure(self):
        done = run('measure.py', self.repo)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_measure_never_runs_repository_code(self):
        self.measure()
        self.assertFalse((self.repo / 'FSMONITOR_RAN').exists())

    def test_never_reads_through_a_folder_link(self):
        outside = self.repo.parent / 'outside'
        outside.mkdir()
        (outside / 'a.md').write_text('[x](./LEAK-MARKER.md)\n')
        (self.repo / 'docs/a.md').unlink()
        (self.repo / 'docs').rmdir()
        symlink_or_skip(outside, self.repo / 'docs', target_is_directory=True)
        self.assertNotIn('LEAK-MARKER', json.dumps(self.measure()))

    @unittest.skipIf(os.name == 'nt', 'Git for Windows refuses these index names')
    def test_windows_style_names_are_never_read(self):
        sha = subprocess.run(['git', '-C', str(self.repo), 'hash-object', '-w', '--stdin'], input=b'x\n',
                             capture_output=True, check=True).stdout.decode().strip()
        for name in ('a\\b.ts', 'C:/x.ts', '\\\\server\\share\\x.ts'):
            git(self.repo, 'update-index', '--add', '--cacheinfo', f'100644,{sha},{name}')
        self.assertEqual(self.measure()['tracked_files'], 5)

    def test_agent_link_text_comes_from_git(self):
        (self.repo / 'AGENTS.md').write_text('# Agents\n')
        symlink_or_skip('AGENTS.md', self.repo / 'CLAUDE.md')
        git(self.repo, 'add', '-A')
        (self.repo / 'CLAUDE.md').unlink()
        symlink_or_skip('LEAK-MARKER', self.repo / 'CLAUDE.md')
        result = json.dumps(self.measure()['agent_files'])
        self.assertIn('"symlink_to": "AGENTS.md"', result)
        self.assertNotIn('LEAK-MARKER', result)

    @unittest.skipIf(os.name == 'nt', 'uses a POSIX shell script as a git wrapper')
    def test_git_never_fetches_from_a_remote(self):
        marker = self.repo.parent / 'FETCH_RAN'
        git(self.repo, 'remote', 'add', 'origin', 'ssh://example.invalid/owner/project.git')
        for key, value in (('core.repositoryformatversion', '1'), ('extensions.partialClone', 'origin'),
                           ('remote.origin.promisor', 'true'), ('protocol.ssh.allow', 'always'),
                           ('core.sshCommand', f'touch "{marker}"; false')):
            git(self.repo, 'config', key, value)
        git(self.repo, 'update-index', '--add', '--info-only', '--cacheinfo', '120000,' + 'ab' * 20 + ',CLAUDE.md')
        self.assertIn({'path': 'CLAUDE.md', 'symlink_to': None}, self.measure()['agent_files'])
        self.assertFalse(marker.exists())
        # Like a git older than 2.44 that ignores GIT_NO_LAZY_FETCH: the protocol block must hold alone.
        shim = self.repo.parent / 'shim'
        shim.mkdir()
        (shim / 'git').write_text(f'#!/bin/sh\nunset GIT_NO_LAZY_FETCH\nexec "{shutil.which("git")}" "$@"\n')
        (shim / 'git').chmod(0o755)
        env = dict(os.environ, PATH=os.pathsep.join([str(shim), os.environ.get('PATH', '')]))
        done = subprocess.run([sys.executable, '-I', str(SCRIPTS / 'measure.py'), str(self.repo)],
                              capture_output=True, text=True, cwd=tempfile.gettempdir(), env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(marker.exists())

    @unittest.skipIf(os.name == 'nt', 'uses a POSIX shell script as the fake git')
    def test_git_is_never_taken_from_the_current_folder(self):
        work, marker = self.repo.parent / 'work', self.repo.parent / 'FAKE_GIT_RAN'
        work.mkdir()
        (work / 'git').write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
        (work / 'git').chmod(0o755)
        env = dict(os.environ, PATH=os.pathsep.join(['.', os.environ.get('PATH', '')]))
        done = subprocess.run([sys.executable, '-I', str(SCRIPTS / 'measure.py'), str(self.repo)],
                              capture_output=True, text=True, cwd=work, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(marker.exists())

    def test_measure_never_runs_repository_filters(self):
        marker = self.repo.parent / 'FILTER_RAN'
        (self.repo / '.gitattributes').write_text('* filter=probe\n')
        git(self.repo, 'config', 'filter.probe.clean', f'sh -c \'touch "{marker}"; cat\'')
        (self.repo / 'README.md').write_text('# Readme changed\n')
        result = self.measure()
        self.assertFalse(marker.exists())
        self.assertIsNone(result['repository']['uncommitted_changes'])

    def test_remote_credentials_and_local_paths_never_reach_output(self):
        git(self.repo, 'remote', 'add', 'origin', 'https://SYNTHETIC-TOKEN@example.invalid/repo.git')
        result = json.dumps(self.measure())
        self.assertNotIn('SYNTHETIC-TOKEN', result)
        git(self.repo, 'remote', 'set-url', 'origin', 'https://example.invalid/owner/project.git')
        self.assertEqual(self.measure()['repository']['name'], 'owner/project')
        for url in ('ssh://git@example.invalid/home/someuser/repos/project.git',
                    'https://example.invalid/owner/project.git?token=SYNTHETIC-TOKEN'):
            git(self.repo, 'remote', 'set-url', 'origin', url)
            self.assertEqual(self.measure()['repository']['name'], 'repo')

    def test_path_unit_is_normalised_and_must_match(self):
        (self.repo / 'src').mkdir()
        (self.repo / 'src/a.ts').write_text('x\n')
        git(self.repo, 'add', 'src/a.ts')
        done = run('measure.py', self.repo, '--path', './src/')
        self.assertEqual(json.loads(done.stdout)['production_source']['files'], 1)
        self.assertEqual(run('measure.py', self.repo, '--path', 'missing').returncode, 2)
        self.assertEqual(run('measure.py', self.repo, '--path', '../outside').returncode, 2)

    def test_unreadable_file_is_reported_not_counted_as_zero(self):
        (self.repo / 'package.json').write_text('{}\n')
        git(self.repo, 'add', 'package.json')
        (self.repo / 'big.ts').unlink()
        (self.repo / 'package.json').unlink()
        result = self.measure()
        source = result['production_source']
        self.assertEqual((source['files'], source['unreadable_files']), (0, 1))
        self.assertEqual((source['average_lines'], source['over_400_percent']), (None, None))
        self.assertEqual((result['signals']['lint'], result['signals']['unreadable_config_files']), (None, 1))

    def test_bare_path_flag_prints_usage(self):
        self.assertEqual(run('measure.py', self.repo, '--path').returncode, 2)
        self.assertEqual(run('measure.py', self.repo, '--path=src').returncode, 2)

    def test_jobs_are_counted_at_any_indent(self):
        (self.repo / '.github/workflows').mkdir(parents=True)
        (self.repo / '.github/workflows/ci.yml').write_text(
            'on: [push]\njobs:\n    lint:\n        runs-on: x\n    test:\n        runs-on: x\n')
        git(self.repo, 'add', '-A')
        self.assertEqual(self.measure()['ci']['github_workflows'][0]['jobs'], 2)

    def test_unreadable_default_branch_is_not_reported_as_clean(self):
        git(self.repo, 'remote', 'add', 'origin', 'https://example.invalid/owner/project.git')
        git(self.repo, 'symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/master')
        self.assertEqual(self.measure()['branches'], {'measured': False, 'reason': 'origin/master could not be read'})

    def test_hygiene_signals_are_measured(self):
        (self.repo / '.github/workflows').mkdir(parents=True)
        (self.repo / '.github/workflows/ci.yml').write_text(
            'on: [pull_request]\npermissions:\n  contents: read\njobs:\n  test:\n    steps:\n'
            '      - uses: actions/checkout@v4\n      - uses: actions/setup-node@' + 'a' * 40 + '\n'
            '      - uses: ./local-action\n      - uses: docker://alpine:3.8\n'
            '      - uses: docker://alpine@sha256:' + 'b' * 64 + '\n')
        for name in ('pnpm-lock.yaml', 'deno.lock', 'ios/Podfile.lock', '.env.example', '.renovaterc.json5',
                     'api/openapi.yaml'):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text('x\n')
        symlink_or_skip('README.md', self.repo / 'linked.md')
        symlink_or_skip('missing.md', self.repo / 'gone.md')
        (self.repo / 'docs/b.md').write_text('[l](../linked.md)\n[g](../gone.md)\n')
        git(self.repo, 'add', '-A')
        result = self.measure()
        flow, found = result['ci']['github_workflows'][0], result['signals']
        self.assertEqual(flow['unpinned_actions'], 2)
        self.assertEqual((found['lockfiles'], found['update_tool'], found['env_example_files'],
                          found['api_schema_files']),
                         (['deno.lock', 'ios/Podfile.lock', 'pnpm-lock.yaml'], '.renovaterc.json5', ['.env.example'],
                          ['api/openapi.yaml']))
        broken = {item['link'] for item in result['documents']['broken_local_links']}
        self.assertNotIn('../linked.md', broken)
        self.assertIn('../gone.md', broken)

    def test_signals_follow_the_unit(self):
        for name, text in (('src/a.ts', 'x\n'), ('docs/CODEOWNERS', '* @owner\n'),
                           ('other/package.json', '{"scripts": {"lint": "eslint ."}}\n'),
                           ('.github/workflows/scan.yml',
                            'on: [push]\njobs:\n  scan:\n    steps:\n      - run: trufflehog git\n')):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text)
        git(self.repo, 'add', '-A')
        found = json.loads(run('measure.py', self.repo, '--path', 'src').stdout)['signals']
        self.assertEqual((found['lint'], found['secret_scan'], found['codeowners']), (False, True, 'docs/CODEOWNERS'))

    def test_links_resolve_like_a_reader_sees_them(self):
        broken = {item['link'] for item in self.measure()['documents']['broken_local_links']}
        self.assertEqual(broken, {'../readme.md', './missing.md'})

    def test_missing_remote_is_not_reported_as_clean_branches(self):
        result = self.measure()
        self.assertEqual(result['branches'], {'measured': False, 'reason': 'no remote'})
        self.assertEqual(result['repository']['name'], 'repo')
        self.assertNotIn(str(self.repo.parent), json.dumps(result))
        self.assertEqual(result['production_source']['over_400'], 1)

    def test_report_matches_framework_and_escapes_text(self):
        framework = json.loads((SKILL / 'references/framework.json').read_text(encoding='utf-8'))
        codes = [item['code'] for dim in framework['dimensions'] for item in dim['items']]
        answers = [{'itemCode': code, 'answer': {'kind': 'scored', 'level': 4}, 'reason': '<b>r</b>',
                    'evidence': 'e'} for code in codes]
        answers[-1]['answer'] = {'kind': 'unanswered'}
        work = self.repo.parent
        results = work / 'results.json'
        check = {'checkedBy': 'subagent', 'held': 20, 'rejected': [],
                 'changed': [{'itemCode': '3.3', 'from': 4, 'to': 3, 'why': '<i>w</i>'}]}
        results.write_text(json.dumps({'repository': 'example/repo', 'commit': 'abc1234',
                                       'assessedAt': '2026-11-23T10:00:00+11:00', 'summary': 's',
                                       'answers': answers, 'verification': check}), encoding='utf-8')
        done = run('build_report.py', results, work / 'report.html')
        self.assertEqual(done.returncode, 0, done.stderr)
        page = (work / 'report.html').read_text(encoding='utf-8')
        self.assertIn('&lt;b&gt;r&lt;/b&gt;', page)
        self.assertIn('Not checked', page)
        self.assertIn('Unit: repository', page)
        self.assertIn('A second agent checked the scores against the evidence: 20 held, 1 changed', page)
        self.assertIn('3.3: level 4 to 3. &lt;i&gt;w&lt;/i&gt;', page)
        results.write_text(json.dumps({'repository': 'x', 'commit': 'a', 'assessedAt': 'b', 'summary': 's',
                                       'answers': answers + answers[:1]}), encoding='utf-8')
        self.assertEqual(run('build_report.py', results, work / 'dup.html').returncode, 1)
        results.write_text(json.dumps({'repository': 'x', 'commit': 'a', 'assessedAt': 'b',
                                       'summary': 's', 'answers': answers[:-1]}), encoding='utf-8')
        self.assertEqual(run('build_report.py', results, work / 'bad.html').returncode, 1)
        answers[0]['answer'] = {'kind': 'not-applicable'}
        results.write_text(json.dumps({'repository': 'x', 'commit': 'a', 'assessedAt': 'b',
                                       'summary': 's', 'answers': answers}), encoding='utf-8')
        self.assertEqual(run('build_report.py', results, work / 'na.html').returncode, 1)

    def test_framework_allows_not_applicable_only_where_intended(self):
        framework = json.loads((SKILL / 'references/framework.json').read_text(encoding='utf-8'))
        allowed = [item['code'] for dim in framework['dimensions'] for item in dim['items'] if item['naAllowed']]
        self.assertEqual(allowed, ['4.4', '5.3', '6.1', '6.2', '7.2'])


if __name__ == '__main__':
    unittest.main()
