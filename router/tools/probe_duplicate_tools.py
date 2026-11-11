"""Synthetic duplicate-declaration rejection and tool replay check.

Offline by default. --live --max-calls 3 permits one legacy-declaration baseline,
one deduplicated tool request and one result replay for the selected model.
Each request caps input at 32 KiB and output at 2048 tokens. No retries.
Only safe status, identity and equality checks leave the probe.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_router import outbound, provider_defs, registry, request_evidence, upstream
from ai_router.tool_adapter import ToolEvents
from tools.probe_wire_shapes import live_target, send

MARKER = 'DUPLICATE_TOOL_RESULT_381'


def payload_for(model, effort):
    tool = {'type': 'namespace', 'name': 'probe', 'tools': [
        {'type': 'function', 'name': 'lookup', 'description': 'Returns a synthetic marker.',
         'parameters': {'type': 'object', 'properties': {'code': {'type': 'string'}},
                        'required': ['code'], 'additionalProperties': False}}]}
    return {'model': model, 'max_output_tokens': 2048, 'stream': False,
        'reasoning': {'effort': effort}, 'tools': [tool], 'input': [
            {'type': 'additional_tools', 'role': 'developer', 'tools': [deepcopy(tool)]},
            {'role': 'user', 'content': 'Call probe.lookup with code equal to "probe". '
             'Then reply with its result exactly.'}]}


def probe(model, effort, *, live=False, max_calls=0):
    row = registry.by_slug(model)
    if row is None or row.provider != provider_defs.OPENROUTER.id or effort not in row.reasoning:
        raise ValueError('select an OpenRouter registry model and a supported effort')
    if live and max_calls != 3:
        raise ValueError('--live requires --max-calls 3')
    payload = payload_for(model, effort)
    fixed, names = outbound.project_external(payload, '/responses', model, row)
    unique = len(fixed['tools']) == 1
    if not live:
        return {'model': model, 'effort': effort, 'calls': 0, 'unique_tools': unique}
    if not unique:
        raise ValueError('candidate still exposes duplicate tools')
    url, headers = live_target()
    calls = 0

    def request(body):
        nonlocal calls
        if (calls >= max_calls or len(json.dumps(body).encode()) > 32768
                or not 0 < body['max_output_tokens'] <= 2048):
            raise ValueError('probe call or token budget exceeded')
        calls += 1
        status, reply = send(url, headers, body)
        return status, reply or {}

    duplicate = deepcopy(fixed)
    duplicate['tools'].append(deepcopy(duplicate['tools'][0]))
    duplicate['input'].insert(0, deepcopy(payload['input'][0]))
    before_status, before = request(duplicate)
    after_status, after = request(fixed)
    result = {'model': model, 'effort': effort, 'before_status': before_status,
        'before_reason': upstream.rejection_reason(json.dumps(before)),
        'after_status': after_status,
        'served_model': request_evidence.identifier(after.get('model')),
        'arguments_match': False, 'marker_match': False}
    tool_calls = [item for item in after.get('output', []) if item.get('type') == 'function_call']
    if after_status == 200 and len(tool_calls) == 1:
        native = ToolEvents(names).item(deepcopy(tool_calls[0]))
        result['arguments_match'] = (native.get('namespace') == 'probe'
            and native.get('name') == 'lookup' and json.loads(native['arguments']) == {'code': 'probe'})
        if result['arguments_match']:
            replay = deepcopy(payload)
            replay['input'].extend([native, {'type': 'function_call_output',
                'call_id': native['call_id'], 'output': MARKER}])
            followup, _ = outbound.project_external(replay, '/responses', model, row)
            final_status, final = request(followup)
            result['final_status'] = final_status
            result['final_served_model'] = request_evidence.identifier(final.get('model'))
            result['marker_match'] = final_status == 200 and any(
                block.get('text', '').strip() == MARKER
                for item in final.get('output', []) if item.get('type') == 'message'
                for block in item.get('content', []))
    result['calls'] = calls
    result['pass'] = before_status == 400 and result['arguments_match'] and result['marker_match']
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--effort', default='low')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--max-calls', type=int, default=0)
    args = parser.parse_args(argv)
    result = probe(args.model, args.effort, live=args.live, max_calls=args.max_calls)
    print(json.dumps(result))
    return int(args.live and not result['pass'])


if __name__ == '__main__':
    raise SystemExit(main())
