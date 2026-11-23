"""The Factory evaluation script counts run behaviour and never prints content."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from tests.loading import load

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT.parent / 'plugins/agents/scg-agent-factory/skills/ai-agent-factory-method/scripts/factory_eval.py'
factory_eval = load(SCRIPT, 'factory_eval')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def event(kind, **payload):
    return {'timestamp': NOW, 'type': kind, 'payload': payload}


def call(name, arguments='{}'):
    return event('response_item', type='function_call', name=name, arguments=arguments)


class FactoryEvalTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.home / 'sessions/2026/11/23').mkdir(parents=True)
        names = [{'id': 'pm', 'thread_name': 'Atlas: Project manager'},
                 {'id': 'qa', 'thread_name': 'Atlas: QA'},
                 {'id': 'lane', 'thread_name': 'Atlas: correctness lane'},
                 {'id': 'other', 'thread_name': 'Plain chat'}]
        (self.home / 'session_index.jsonl').write_text('\n'.join(json.dumps(n) for n in names))
        secret = 'PRIVATE-MESSAGE-TEXT'
        self.write('pm', None, [
            event('turn_context', effort='max'),
            event('response_item', type='message', role='user', content=[{'type': 'input_text', 'text': secret}]),
            event('response_item', type='message', role='user',
                  content=[{'type': 'input_text', 'text': '# AGENTS.md rules'}]),
            call('spawn_agent'), call('wait_agent'), call('wait_agent'), call('sleep'),
            event('event_msg', type='token_count', info={'last_token_usage': {
                'input_tokens': 1000, 'cached_input_tokens': 900, 'output_tokens': 50}}),
        ])
        self.write('lane', 'pm', [event('turn_context', effort='high'),
                                  event('event_msg', type='token_count', info={'last_token_usage': {
                                      'input_tokens': 200, 'cached_input_tokens': 0, 'output_tokens': 10}})])
        self.write('qa', None, [event('turn_context', effort='high'), call('request_user_input'),
                                call('exec_command', '{"cmd":"cat x/ai-agent-factory-method/SKILL.md"}')])
        self.write('other', None, [event('turn_context', effort='high'), call('exec_command')])
        self.secret = secret

    def write(self, thread, parent, events):
        meta = {'timestamp': NOW, 'type': 'session_meta', 'payload': {'id': thread, 'parent_thread_id': parent}}
        path = self.home / f'sessions/2026/11/23/rollout-{thread}.jsonl'
        lines = [json.dumps(e) for e in [meta, *events]] + ['null', '[1, 2]', '{"type": "turn_context"}']
        path.write_text('\n'.join(lines))

    def test_counts_factory_chats_and_flags_patterns(self):
        chats = {c['role']: c for c in factory_eval.collect(self.home, 7)}
        self.assertEqual(set(chats), {'Project manager', 'QA'})
        pm, qa = chats['Project manager'], chats['QA']
        self.assertEqual((pm['human_messages'], pm['tool_calls'], pm['spawned'], pm['children']), (1, 4, 1, 1))
        self.assertEqual(pm['waiting_share'], 0.75)
        self.assertEqual(pm['review_lane_share'], 1.0)
        self.assertEqual(pm['fresh_tokens'], 150 + 210)
        self.assertEqual(factory_eval.signals(pm), ['mostly waiting', 'mostly max effort', 'skill not read'])
        self.assertEqual(qa['skill_reads'], 1)
        self.assertEqual(factory_eval.signals(qa), ['owner asked human'])

    def test_skill_reads_count_every_delivery_path_and_older_reads_clear_the_flag(self):
        old = '2026-01-01T00:00:00.000Z'
        injected = event('response_item', type='message', role='developer',
                         content=[{'type': 'input_text', 'text': '# AI Agent Factory Method\nrules'}])
        self.write('pm', None, [
            {'timestamp': old, 'type': 'response_item', 'payload': {
                'type': 'custom_tool_call', 'name': 'js', 'input': 'read x/ai-agent-factory-method/SKILL.md'}},
            event('turn_context', effort='high'), injected])
        pm = next(c for c in factory_eval.collect(self.home, 7) if c['role'] == 'Project manager')
        self.assertEqual((pm['skill_reads'], pm['skill_read_on_record']), (1, True))
        self.write('pm', None, [{'timestamp': old, 'type': 'response_item', 'payload': {
            'type': 'custom_tool_call', 'name': 'js', 'input': 'read x/ai-agent-factory-method/SKILL.md'}},
            event('turn_context', effort='high')])
        pm = next(c for c in factory_eval.collect(self.home, 7) if c['role'] == 'Project manager')
        self.assertEqual(pm['skill_reads'], 0)
        self.assertNotIn('skill not read', factory_eval.signals(pm))

    def test_output_never_contains_message_content(self):
        for args in ([], ['--json']):
            out = io.StringIO()
            with redirect_stdout(out):
                factory_eval.main(['--codex-home', str(self.home), '--project', 'atlas', *args])
            self.assertIn('Project manager', out.getvalue())
            self.assertNotIn(self.secret, out.getvalue())


if __name__ == '__main__':
    unittest.main()
