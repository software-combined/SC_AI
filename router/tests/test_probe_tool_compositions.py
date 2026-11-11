"""Keep the separately invoked live reproduction bounded and offline in CI."""
import json
import unittest
from unittest.mock import patch

from tools import probe_tool_compositions as probe

MODEL = 'anthropic/claude-haiku-5.5'


class CompositionProbeTests(unittest.TestCase):
    def test_offline_and_invalid_live_budget_never_resolve_credentials(self):
        with patch.object(probe, 'live_target') as target:
            self.assertTrue(probe.probe(MODEL, 'low')['adapted'])
            with self.assertRaisesRegex(ValueError, 'max-calls'):
                probe.probe(MODEL, 'low', live=True, max_calls=2)
            target.assert_not_called()

    def test_live_contract_requires_rejection_exact_arguments_and_final_marker(self):
        error = {'error': {'message': 'Provider returned error', 'metadata': {'raw':
            json.dumps({'message': 'input_schema does not support anyOf at the top level'})}}}
        call = {'model': 'https://example.invalid/private?token=synthetic',
            'output': [{'type': 'function_call', 'name': 'probe__run',
            'call_id': 'call_synthetic',
            'arguments': json.dumps({'arguments_json': json.dumps({'code': 'probe'})})}]}
        final = {'model': MODEL, 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': probe.MARKER}]}]}
        with patch.object(probe, 'live_target', return_value=('https://example.invalid', {})), \
                patch.object(probe, 'send', side_effect=[(400, error), (200, call), (200, final)]) as send:
            result = probe.probe(MODEL, 'low', live=True, max_calls=3)
        self.assertTrue(result['pass'])
        self.assertIsNone(result['served_model'])
        self.assertEqual(result['calls'], 3)
        bodies = [args.args[2] for args in send.call_args_list]
        self.assertTrue(all(body['max_output_tokens'] == 2048 for body in bodies))
        self.assertIn('anyOf', bodies[0]['tools'][0]['parameters'])
        self.assertNotIn('anyOf', bodies[1]['tools'][0]['parameters'])
        replay = next(item for item in bodies[2]['input'] if item.get('type') == 'function_call')
        self.assertEqual(json.loads(json.loads(replay['arguments'])['arguments_json']), {'code': 'probe'})

    def test_failed_adapted_request_does_not_buy_another_attempt(self):
        with patch.object(probe, 'live_target', return_value=('https://example.invalid', {})), \
                patch.object(probe, 'send', return_value=(400, {})) as send:
            result = probe.probe(MODEL, 'low', live=True, max_calls=3)
        self.assertFalse(result['pass'])
        self.assertEqual(send.call_count, 2)
