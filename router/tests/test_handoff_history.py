"""Native replay uses the offered readable name without changing saved calls."""
from copy import deepcopy
from compression import zstd
import json
import unittest

from ai_router import agent_handoffs as handoffs, errors
from ai_router.providers import SubscriptionProvider
from tests.test_agent_handoffs import CIPHERTEXT, KEY, NO_KEY, handoff_call, native_tools


def recorded_call(**changes):
    return handoff_call(encrypted_function_args=[], **changes)


class HandoffHistoryTests(unittest.TestCase):
    def test_calls_match_classic_lite_and_discovered_declarations(self):
        for location in ('classic', 'lite', 'discovered'):
            with self.subTest(location=location):
                calls = [recorded_call(name=name, id=f'fc_{name}', call_id=f'call_{name}')
                         for name in sorted(handoffs.HANDOFF_TOOLS)]
                outputs = [{'type': 'function_call_output', 'call_id': call['call_id'],
                            'output': '{"status":"accepted"}'} for call in calls]
                payload = {'input': [item for pair in zip(calls, outputs) for item in pair]}
                tools = native_tools(*sorted(handoffs.HANDOFF_TOOLS))
                if location == 'classic':
                    payload['tools'] = tools
                else:
                    declaration = ({'type': 'additional_tools', 'role': 'developer', 'id': 'at_old'}
                                   if location == 'lite' else
                                   {'type': 'tool_search_output', 'call_id': 'search'})
                    payload['input'].insert(0, {**declaration, 'tools': tools})
                before = deepcopy(payload)
                prepared, names = handoffs.native_handoffs(payload, True, catalogue={})
                self.assertEqual(names, handoffs.HANDOFF_TOOLS)
                history = prepared['input'][-6:]
                for call, output, projected, result in zip(calls, outputs, history[::2], history[1::2]):
                    self.assertEqual(projected, {**call, 'namespace': 'collaboration_plaintext'})
                    self.assertIs(projected['arguments'], call['arguments'])
                    self.assertIs(result, output)
                    self.assertEqual(handoffs.mark_readable(projected, names), call)
                self.assertEqual(payload, before)
                self.assertIs(handoffs.native_handoffs(prepared, True, catalogue={})[0], prepared)

    def test_only_explicit_readable_declared_calls_are_projected(self):
        valid = recorded_call()
        excluded = [
            handoff_call(),
            handoff_call(encrypted_function_args=['message']),
            handoff_call(encrypted_function_args=None),
            recorded_call(arguments=json.dumps({'message': CIPHERTEXT})),
            recorded_call(arguments='{malformed'),
            recorded_call(arguments='[]'),
            recorded_call(arguments='{}'),
            recorded_call(arguments={'message': {'text': 'synthetic'}}),
            recorded_call(name='spawn_agent'),
            recorded_call(name='wait_agent'),
            recorded_call(namespace='other'),
            recorded_call(type='custom_tool_call'),
            'not-a-call',
        ]
        payload = {'tools': native_tools('send_message'), 'input': [valid, *excluded]}
        prepared, _ = handoffs.native_handoffs(payload, True, catalogue={})
        self.assertEqual(prepared['input'][0]['namespace'], 'collaboration_plaintext')
        for old, new in zip(excluded, prepared['input'][1:]):
            self.assertIs(new, old)

    def test_absent_or_opaque_declarations_preserve_call_history(self):
        opaque = native_tools('send_message')
        opaque[0]['tools'][0]['parameters']['properties']['message']['type'] = ['string', 'null']
        for tools in ([], opaque):
            with self.subTest(tools=tools):
                call = recorded_call()
                payload = {'tools': tools, 'input': [call]}
                prepared, names = handoffs.native_handoffs(payload, True, catalogue={})
                self.assertFalse(names)
                self.assertIs(prepared['input'][0], call)

    def test_non_list_input_is_unchanged(self):
        for items in (None, 'synthetic'):
            prepared, _ = handoffs.native_handoffs(
                {'tools': native_tools('send_message'), 'input': items}, True, catalogue={})
            self.assertIs(prepared['input'], items)

    def test_projected_spawn_keeps_the_followup_guard_across_repeated_preparation(self):
        spawn = recorded_call(name='spawn_agent', arguments={
            'task_name': 'synthetic', 'model': 'openai/gpt-6.1-sol', 'message': 'Read only.'})
        payload = {'tools': native_tools('spawn_agent', 'followup_task'), 'input': [spawn]}
        for _ in range(2):
            payload, names = handoffs.native_handoffs(payload, True)
            self.assertEqual(names.spawn_models, {'synthetic': 'openai/gpt-6.1-sol'})
            with self.assertRaises(errors.ResponseRejected) as caught:
                handoffs.validate_handoff(handoff_call(name='followup_task', arguments={
                    'target': '/root/synthetic', 'message': CIPHERTEXT}), names)
            self.assertEqual(caught.exception.detail, 'HANDOFF_REQUIRES_PLAINTEXT')

    def test_provider_reencodes_only_the_readable_responses_route(self):
        call = recorded_call()
        payload = {'model': 'gpt-6-astra', 'tools': native_tools('send_message'), 'input': [
            call, {'type': 'function_call_output', 'call_id': call['call_id'], 'output': 'accepted'}]}
        before = deepcopy(payload)
        raw = zstd.compress(json.dumps(payload).encode())
        provider = SubscriptionProvider()
        for path, keys in (('/responses', KEY), ('/responses', NO_KEY), ('/responses/compact', KEY)):
            with self.subTest(path=path, readable=keys is KEY):
                prepared = provider.prepare('gpt-6-astra', path, payload, raw,
                    {'Content-Encoding': 'zstd'}, keys)
                if path == '/responses' and keys is KEY:
                    decoded = json.loads(prepared.body)
                    self.assertEqual(decoded['input'][0], {**call, 'namespace': 'collaboration_plaintext'})
                    self.assertNotIn('Content-Encoding', prepared.headers)
                else:
                    self.assertIs(prepared.body, raw)
                self.assertEqual(payload, before)


if __name__ == '__main__':
    unittest.main()
