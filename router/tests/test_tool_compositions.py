"""Regression for Anthropic's rejection of composed tool parameter roots."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from ai_router import model_refresh, outbound, provider_defs, registry, upstream
from ai_router.providers import ExternalResponsesProvider, SubscriptionProvider
from ai_router.tool_adapter import ToolEvents
from tests.test_agent_handoffs import KEY


MODELS = ('anthropic/claude-haiku-5.5', 'anthropic/claude-opus-5.5',
          'anthropic/claude-sonnet-5.5', 'anthropic/claude-fable-5.2')
BRANCHES = [
    {'type': 'object', 'properties': {'code': {'type': 'string'}},
     'required': ['code'], 'additionalProperties': False},
    {'type': 'object', 'properties': {'completion_summary': {'type': 'string'}},
     'required': ['completion_summary'], 'additionalProperties': False}]


def payload_for(composition='anyOf', location='classic'):
    branches = BRANCHES[:1] if composition == 'allOf' else BRANCHES
    tool = {'type': 'function', 'name': 'run', 'description': 'Synthetic tool.',
            'parameters': {'type': 'object', composition: deepcopy(branches)}}
    tools = [{'type': 'namespace', 'name': 'probe', 'tools': [tool]}]
    payload = {'input': [{'role': 'user', 'content': 'Run the synthetic tool.'}]}
    if location == 'classic':
        payload['tools'] = tools
    elif location == 'lite':
        payload['input'].insert(0, {'type': 'additional_tools', 'role': 'developer',
                                    'id': 'at_synthetic', 'tools': tools})
    else:
        payload['tools'] = [{'type': 'tool_search', 'parameters': {'type': 'object'}}]
        payload['input'][:0] = [
            {'type': 'tool_search_call', 'call_id': 's1', 'execution': 'client',
             'arguments': {'query': 'probe run'}},
            {'type': 'tool_search_output', 'call_id': 's1', 'execution': 'client',
             'tools': tools}]
    return payload


def prepare(provider, payload, model):
    return provider.prepare(model, '/responses', payload, json.dumps(payload).encode(), {}, KEY)


class ToolCompositionTests(unittest.TestCase):
    def test_composed_roots_round_trip_across_declaration_locations(self):
        provider = ExternalResponsesProvider(provider_defs.OPENROUTER)
        for model in MODELS:
            for composition in ('anyOf', 'oneOf', 'allOf'):
                for location in ('classic', 'lite', 'discovered'):
                    with self.subTest(model=model, composition=composition, location=location):
                        payload = payload_for(composition, location)
                        original = deepcopy(payload)
                        prepared = prepare(provider, payload, model)
                        body = json.loads(prepared.body)
                        tool = next(t for t in body['tools'] if t['name'] == 'probe__run')
                        self.assertNotIn(composition, tool['parameters'])
                        self.assertEqual(tool['parameters']['properties'],
                                         {'arguments_json': {'type': 'string'}})
                        values = [{'code': 'probe'}]
                        if composition != 'allOf':
                            values.append({'completion_summary': 'done'})
                        for value in values:
                            wire_args = json.dumps({'arguments_json': json.dumps(value)})
                            item = ToolEvents(prepared.tool_names).item({
                                'type': 'function_call', 'name': 'probe__run',
                                'call_id': 'echo1', 'arguments': wire_args})
                            self.assertEqual(json.loads(item['arguments']), value)
                            self.assertEqual((item['namespace'], item['name']), ('probe', 'run'))
                            replay = deepcopy(payload)
                            replay['input'].extend([item, {'type': 'function_call_output',
                                                          'call_id': 'echo1', 'output': 'OK'}])
                            again = json.loads(prepare(provider, replay, model).body)
                            call = next(i for i in again['input'] if i.get('call_id') == 'echo1')
                            self.assertEqual(json.loads(call['arguments']),
                                             {'arguments_json': item['arguments']})
                        self.assertEqual(payload, original)

    def test_plain_objects_and_nested_compositions_keep_native_arguments(self):
        provider = ExternalResponsesProvider(provider_defs.OPENROUTER)
        payload = payload_for()
        schema = {'type': 'object', 'properties': {'choice': {'anyOf': [
            {'type': 'string'}, {'type': 'integer'}]}}}
        payload['tools'][0]['tools'][0]['parameters'] = schema
        for model in MODELS:
            with self.subTest(model=model):
                prepared = prepare(provider, payload, model)
                self.assertEqual(json.loads(prepared.body)['tools'][0]['parameters'], schema)

    def test_other_models_and_subscription_keep_the_existing_contract(self):
        payload = payload_for()
        schema = payload['tools'][0]['tools'][0]['parameters']
        external = ExternalResponsesProvider(provider_defs.OPENROUTER)
        for model in ('z-ai/glm-5.3-flash', 'x-ai/grok-4.7'):
            with self.subTest(model=model):
                self.assertEqual(json.loads(prepare(external, payload, model).body)
                                 ['tools'][0]['parameters'], schema)
        native = prepare(SubscriptionProvider(), payload, 'gpt-6-astra')
        self.assertEqual(json.loads(native.body)['tools'][0]['tools'][0]['parameters'], schema)

    def test_configured_anthropic_responses_rows_apply_composition_profile(self):
        for model in MODELS:
            self.assertEqual(registry.by_slug(model).schema_mode, 'json_text_composition')

    def test_older_model_cache_cannot_remove_the_shipped_schema_adaptation(self):
        for model in MODELS:
            with self.subTest(model=model):
                shipped = registry.by_slug(model)
                stale = replace(shipped, schema_mode='native')
                effective, = model_refresh.overlay((shipped,), (stale,))
                body, _ = outbound.project_external(payload_for(), '/responses', model, effective)
                self.assertNotIn('anyOf', body['tools'][0]['parameters'])
                # A different upstream target must keep its own schema contract.
                moved = replace(stale, upstream_id='synthetic/different-target')
                effective, = model_refresh.overlay((shipped,), (moved,))
                self.assertEqual(effective.schema_mode, 'native')

    def test_nested_provider_errors_identify_schema_rejection_without_raw_prose(self):
        message = ('tools.0.custom.input_schema: input_schema does not support '
                   'oneOf, allOf, or anyOf at the top level; SYNTH_PRIVATE_TEXT')
        for inner in ({'message': message},
                      {'type': 'error', 'error': {'type': 'invalid_request_error',
                                                 'message': message}}):
            with self.subTest(inner=inner):
                body = json.dumps({'error': {'message': 'Provider returned error',
                    'metadata': {'provider_name': 'Synthetic', 'raw': json.dumps(inner)}}})
                status, text, _ = upstream.describe_failure(None,
                    {'status': 400, 'body': body}, {'model': MODELS[0], 'protocol': 'responses'})
                self.assertEqual(status, 400)
                self.assertIn('tool schema was rejected', text)
                self.assertNotIn('SYNTH_PRIVATE_TEXT', text)
                self.assertNotIn('without naming a cause', text)
