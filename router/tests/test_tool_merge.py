"""Plan 129: the shared tool-definition merge rule and its two consumers.

The rule is pinned directly and then differentially against prepare_tools and
discovered, so a change at one call site cannot silently diverge from the other.
"""
from copy import deepcopy
import json
import unittest

from ai_router import outbound, registry
from ai_router.discovered import _dedup
from ai_router.tool_adapter import ToolEvents
from ai_router.tool_merge import (complete_parameters, key_of, merge_tool_defs,
                                  missing_schema)
from tests.tool_stages import prepare_tools


def _stub(name, namespace=None):
    row = {'type': 'function', 'name': name}
    if namespace is not None:
        row['namespace'] = namespace
    return row


def _full(name, namespace=None, description='full'):
    row = {'type': 'function', 'name': name, 'description': description,
           'parameters': {'type': 'object'}}
    if namespace is not None:
        row['namespace'] = namespace
    return row


class ToolMergeRuleTests(unittest.TestCase):
    def test_unnamed_builtin_types_survive_beside_a_same_named_function(self):
        tools = [{'type': 'web_search'},
                 {'type': 'tool_search', 'parameters': {'type': 'object'}},
                 _full('web_search')]
        payload = {'model': 'google/gemini-4-carbon', 'tools': tools, 'input': [
            {'type': 'additional_tools', 'role': 'developer', 'tools': deepcopy(tools)}]}
        projected = prepare_tools(payload)[0]
        self.assertEqual([(tool['type'], tool.get('name')) for tool in projected['tools']],
                         [('web_search', None), ('function', 'codex_client_tool_search'),
                          ('function', 'web_search')])

    def test_current_and_saved_declarations_have_one_wire_tool_and_replay(self):
        current = {'type': 'namespace', 'name': 'probe',
                   'tools': [_full('lookup', description='current')]}
        older = deepcopy(current)
        older['tools'][0]['description'] = 'saved'
        payload = {'tools': [current], 'input': [
            {'type': 'additional_tools', 'role': 'developer', 'tools': [older]},
            {'role': 'user', 'content': 'Run the synthetic lookup.'}]}
        original = deepcopy(payload)
        for slug in ('google/gemini-4-carbon', 'meta/muse-ember'):
            with self.subTest(model=slug):
                body, names = outbound.project_external(
                    payload, '/responses', slug, registry.by_slug(slug))
                self.assertEqual(len(body['tools']), 1)
                self.assertFalse(any(item.get('type') == 'additional_tools'
                                     for item in body['input']))
                tool = body['tools'][0]
                self.assertEqual(tool['name'], 'probe__lookup')
                self.assertEqual(tool['description'], 'probe.lookup: current')
                call = ToolEvents(names).item({'type': 'function_call',
                    'name': tool['name'], 'call_id': 'synthetic_call', 'arguments': '{}'})
                self.assertEqual((call['namespace'], call['name']), ('probe', 'lookup'))
                replay = deepcopy(payload)
                replay['input'].extend([call, {'type': 'function_call_output',
                    'call_id': call['call_id'], 'output': 'SYNTHETIC_RESULT'}])
                body, _ = outbound.project_external(
                    replay, '/responses', slug, registry.by_slug(slug))
                wire_call = next(item for item in body['input']
                                 if item.get('type') == 'function_call')
                self.assertEqual(wire_call['name'], 'probe__lookup')
                self.assertEqual(json.loads(wire_call['arguments']), {})
                self.assertEqual(len(body['tools']), 1)
        self.assertEqual(payload, original)

    def test_duplicate_declarations_complete_stubs_without_merging_sibling_tools(self):
        payload = {'model': 'z-ai/glm-5.3', 'tools': [
            _stub('lookup'),
            {'type': 'namespace', 'name': 'probe', 'tools': [_stub('lookup')]},
            {'type': 'namespace', 'name': 'other', 'tools': [_full('lookup')]}],
            'input': [{'type': 'additional_tools', 'role': 'developer', 'tools': [
                _full('lookup'),
                {'type': 'namespace', 'name': 'probe', 'tools': [_full('lookup')]}]}]}
        original = deepcopy(payload)
        projected = prepare_tools(payload)[0]
        self.assertEqual([tool['name'] for tool in projected['tools']],
                         ['lookup', 'probe__lookup', 'other__lookup'])
        self.assertTrue(all(tool['parameters'] == {'type': 'object'}
                            for tool in projected['tools']))
        self.assertEqual(payload, original)

    def test_flat_rows_keep_first_occurrence_order_and_first_full_definition(self):
        merged = merge_tool_defs([_stub('lookup'), _full('other', description='first'),
                                  _full('lookup')])
        self.assertEqual([tool['name'] for tool in merged], ['lookup', 'other'])
        # A later full row replaces the earlier schema-less stub.
        self.assertEqual(merged[0]['description'], 'full')
        self.assertEqual(merged[0]['parameters'], {'type': 'object'})
        self.assertEqual(merged[1]['description'], 'first')

    def test_namespace_wrappers_merge_by_inner_tools(self):
        first = {'type': 'namespace', 'name': 'collab',
                 'tools': [_stub('spawn_agent')]}
        second = {'type': 'namespace', 'name': 'collab',
                  'tools': [_full('send_message')]}
        merged = merge_tool_defs([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['name'], 'collab')
        self.assertEqual([tool['name'] for tool in merged[0]['tools']],
                         ['spawn_agent', 'send_message'])
        self.assertEqual([tool['namespace'] for tool in merged[0]['tools']],
                         ['collab', 'collab'])

    def test_wrapper_and_flat_row_of_the_same_tool_both_survive(self):
        wrapper = {'type': 'namespace', 'name': 'collab',
                   'tools': [_full('spawn_agent')]}
        merged = merge_tool_defs([wrapper, _full('spawn_agent')])
        self.assertEqual(len(merged), 2)

    def test_non_dict_rows_are_ignored(self):
        self.assertEqual(merge_tool_defs(['not-a-tool', None, 7]), [])

    def test_key_of_uses_the_effective_namespace(self):
        self.assertEqual(key_of(_stub('x'), 'collab'), ('collab', 'x'))
        self.assertEqual(key_of(_stub('x')), (None, 'x'))
        # The row's own namespace field is the caller's business, not the
        # leaf's: prepare_tools keys flat rows without it, exactly as before.
        self.assertEqual(key_of(_stub('x', 'collab')), (None, 'x'))
        self.assertEqual(key_of(_stub('x', 'collab'), 'collab'), ('collab', 'x'))

    def test_prepare_tools_keeps_the_flat_key_for_a_namespaced_released_row(self):
        # Regression guard for the pre-image keying: a flat declared row and a
        # flat released row carrying its own namespace field merged into one
        # completed row; they must not become two rows.
        payload = {'model': 'z-ai/glm-5.3', 'input': [
            {'type': 'tool_search_output', 'call_id': 's', 'tools': [
                {'type': 'function', 'name': 'echo', 'namespace': 'a',
                 'parameters': {'type': 'object'}}]}],
            'tools': [{'type': 'function', 'name': 'echo', 'description': 'declared'}]}
        payload = prepare_tools(payload)[0]
        self.assertEqual(len(payload['tools']), 1)
        self.assertEqual(payload['tools'][0]['description'], 'declared')
        self.assertEqual(payload['tools'][0]['parameters'], {'type': 'object'})

    def test_complete_parameters_borrows_only_the_schema(self):
        declared = {'type': 'function', 'name': 'lookup', 'description': 'declared'}
        discovered = _full('lookup')
        self.assertTrue(missing_schema(declared, discovered))
        self.assertTrue(complete_parameters(declared, discovered))
        self.assertEqual(declared['description'], 'declared')
        self.assertEqual(declared['parameters'], {'type': 'object'})
        self.assertFalse(complete_parameters(declared, _full('lookup', description='other')))

    def test_dedup_alias_is_the_leaf(self):
        self.assertIs(_dedup, merge_tool_defs)

    def test_prepare_tools_borrows_the_declared_wins_rule(self):
        payload = {'model': 'z-ai/glm-5.3', 'input': [
            {'type': 'tool_search_output', 'call_id': 's', 'tools': [_full('lookup')]}],
            'tools': [{'type': 'function', 'name': 'lookup', 'description': 'declared'}]}
        payload = prepare_tools(payload)[0]
        self.assertEqual(len(payload['tools']), 1)
        self.assertEqual(payload['tools'][0]['description'], 'declared')
        self.assertEqual(payload['tools'][0]['parameters'], {'type': 'object'})


if __name__ == '__main__':
    unittest.main()
