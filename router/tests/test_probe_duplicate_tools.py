"""Paid-probe bounds and the synthetic declaration/replay comparison."""
import unittest
from unittest import mock

from tools import probe_duplicate_tools as probe


class DuplicateToolProbeTests(unittest.TestCase):
    def test_offline_and_invalid_budget_never_resolve_credentials(self):
        with mock.patch.object(probe, 'live_target') as target:
            result = probe.probe('meta/muse-ember', 'low')
            self.assertEqual(result['calls'], 0)
            self.assertTrue(result['unique_tools'])
            for budget in (0, 2, 4):
                with self.assertRaises(ValueError):
                    probe.probe('meta/muse-ember', 'low', live=True, max_calls=budget)
            target.assert_not_called()

    def test_legacy_rejection_fixed_tool_and_replay_use_three_bounded_calls(self):
        replies = [(400, {'error': {'message': 'Invalid tools'}}), (200, {
            'model': 'meta/muse-ember', 'output': [{'type': 'function_call',
                'name': 'probe__lookup', 'call_id': 'synthetic_call',
                'arguments': '{"code":"probe"}'}]}), (200, {
            'model': 'meta/muse-ember', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': probe.MARKER}]}]})]
        with (mock.patch.object(probe, 'live_target', return_value=('synthetic', {})),
              mock.patch.object(probe, 'send', side_effect=replies) as send):
            result = probe.probe('meta/muse-ember', 'low', live=True, max_calls=3)
        self.assertTrue(result['pass'])
        self.assertEqual(result['calls'], 3)
        before, fixed, replay = [call.args[2] for call in send.call_args_list]
        self.assertEqual(len(before['tools']), 2)
        self.assertEqual(before['input'][0]['type'], 'additional_tools')
        for body in (fixed, replay):
            self.assertEqual(len(body['tools']), 1)
            self.assertFalse(any(item.get('type') == 'additional_tools' for item in body['input']))
            self.assertEqual(body['max_output_tokens'], 2048)
        self.assertEqual(replay['input'][-1]['output'], probe.MARKER)

    def test_rejected_fixed_request_stops_without_a_replay(self):
        with (mock.patch.object(probe, 'live_target', return_value=('synthetic', {})),
              mock.patch.object(probe, 'send', return_value=(400, {})) as send):
            result = probe.probe('meta/muse-ember', 'low', live=True, max_calls=3)
        self.assertFalse(result['pass'])
        self.assertEqual(send.call_count, 2)
