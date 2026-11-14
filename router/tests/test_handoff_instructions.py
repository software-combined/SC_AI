"""Native handoff examples must name the tools the same request offers."""
from copy import deepcopy
from compression import zstd
import json
import unittest

from ai_router import agent_handoffs as handoffs
from ai_router.providers import SubscriptionProvider
from tests.test_agent_handoffs import KEY, NO_KEY, native_tools


EXAMPLE = '`to=functions.collaboration.spawn_agent`'
READABLE = '`to=collaboration_plaintext.spawn_agent`'
ROLE = ('<multi_agent_role>Call tools directly using the recipient shown in '
        f'their definitions, such as {EXAMPLE}.</multi_agent_role>')


def instruction(text=ROLE, **changes):
    return {'type': 'message', 'role': 'developer',
            'content': [{'type': 'input_text', 'text': text}], **changes}


class HandoffInstructionTests(unittest.TestCase):
    def test_role_example_matches_classic_lite_and_discovered_spawn(self):
        for location in ('classic', 'lite', 'discovered'):
            with self.subTest(location=location):
                message = instruction()
                payload = {'input': [message]}
                tools = native_tools('spawn_agent', 'wait_agent')
                if location == 'classic':
                    payload['tools'] = tools
                else:
                    declaration = ({'type': 'additional_tools', 'role': 'developer', 'id': 'at_role'}
                                   if location == 'lite' else
                                   {'type': 'tool_search_output', 'call_id': 'search'})
                    payload['input'].insert(0, {**declaration, 'tools': tools})
                original = deepcopy(payload)
                prepared, names = handoffs.native_handoffs(payload, True)
                self.assertIn('spawn_agent', names)
                self.assertEqual(prepared['input'][-1]['content'][0]['text'], ROLE.replace(EXAMPLE, READABLE))
                self.assertEqual(payload, original)
                self.assertIs(handoffs.native_handoffs(prepared, True)[0], prepared)

    def test_only_the_host_role_example_is_projected(self):
        untouched = [
            instruction(role='user'), instruction(role='assistant'),
            instruction(type='function_call_output'),
            instruction('Quoted example: ' + ROLE),
            instruction(ROLE + '\nOther instructions.'),
            instruction(ROLE.replace('multi_agent_role', 'untrusted_text')),
            instruction('Use ' + EXAMPLE),
            instruction(encrypted_content='opaque'),
            instruction(content=[{'type': 'encrypted_content', 'text': ROLE}]),
            instruction(content=ROLE),
            instruction(content=[{'type': 'input_text', 'text': 3}]),
        ]
        plain = '<multi_agent_role>Keep `collaboration.wait_agent` and literal spawn_agent.</multi_agent_role>'
        payload = {'tools': native_tools('spawn_agent', 'wait_agent'),
                   'input': [*untouched, instruction(plain)]}
        prepared, _ = handoffs.native_handoffs(payload, True)
        for before, after in zip(payload['input'], prepared['input']):
            self.assertIs(after, before)

    def test_an_unavailable_or_opaque_spawn_keeps_the_example(self):
        opaque = native_tools('spawn_agent')
        opaque[0]['tools'][0]['parameters']['properties']['message']['type'] = ['string', 'null']
        for tools in ([], native_tools('wait_agent'), opaque):
            with self.subTest(tools=tools):
                message = instruction()
                prepared, _ = handoffs.native_handoffs({'tools': tools, 'input': [message]}, True)
                self.assertIs(prepared['input'][0], message)

    def test_provider_changes_only_the_readable_native_responses_route(self):
        payload = {'model': 'gpt-6.1-terra', 'tools': native_tools('spawn_agent'),
                   'input': [instruction()]}
        original = deepcopy(payload)
        raw = zstd.compress(json.dumps(payload).encode())
        for path, keys in (('/responses', KEY), ('/responses', NO_KEY), ('/responses/compact', KEY)):
            with self.subTest(path=path, readable=keys is KEY):
                prepared = SubscriptionProvider().prepare(payload['model'], path, payload, raw,
                    {'Content-Encoding': 'zstd'}, keys)
                if path == '/responses' and keys is KEY:
                    self.assertEqual(json.loads(prepared.body)['input'][0]['content'][0]['text'],
                                     ROLE.replace(EXAMPLE, READABLE))
                    self.assertNotIn('Content-Encoding', prepared.headers)
                elif path == '/responses':
                    self.assertEqual(json.loads(prepared.body)['input'], payload['input'])
                else:
                    self.assertIs(prepared.body, raw)
                self.assertEqual(payload, original)


if __name__ == '__main__':
    unittest.main()
