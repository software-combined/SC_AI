"""Bounded synthetic reproduction and tool round trip for composed schema roots.

Offline by default. --live --max-calls 3 permits one baseline rejection and
two adapted requests for one explicitly selected OpenRouter model. Each call
caps output at 2048 tokens and input at 32 KiB. There are no retries. The
existing credential resolver supplies headers; output contains only status,
identity, safe error classification and argument/marker equality checks.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_router import provider_defs, registry, request_evidence, upstream
from ai_router.outbound import project_external
from ai_router.tool_adapter import ToolEvents
from tools.probe_wire_shapes import live_target, send

MARKER = 'SCHEMA_ROUND_TRIP_719'
MAX_OUTPUT = 2048


def payload_for(model, effort):
    return {'model': model, 'max_output_tokens': MAX_OUTPUT, 'stream': False,
        'reasoning': {'effort': effort}, 'tool_choice': 'auto',
        'input': [{'role': 'user', 'content':
            'Call probe.run once with code equal to "probe". Then reply with its result exactly.'}],
        'tools': [{'type': 'namespace', 'name': 'probe', 'tools': [
            {'type': 'function', 'name': 'run', 'description': 'Returns a synthetic marker.',
             'parameters': {'type': 'object', 'anyOf': [
                {'type': 'object', 'properties': {'code': {'type': 'string'}},
                 'required': ['code'], 'additionalProperties': False},
                {'type': 'object', 'properties': {'completion_summary': {'type': 'string'}},
                 'required': ['completion_summary'], 'additionalProperties': False}]}}]}]}


def probe(model, effort, *, live=False, max_calls=0):
    row = registry.by_slug(model)
    if row is None or row.provider != provider_defs.OPENROUTER.id or effort not in row.reasoning:
        raise ValueError('select an OpenRouter registry model and a supported effort')
    if live and not 3 <= max_calls <= 6:
        raise ValueError('--live requires --max-calls between 3 and 6')
    payload = payload_for(model, effort)
    fixed, names = project_external(payload, '/responses', model, row)
    if not live:
        return {'model': model, 'effort': effort, 'calls': 0,
                'adapted': 'anyOf' not in fixed['tools'][0]['parameters']}
    url, headers = live_target()
    calls = 0

    def request(body):
        nonlocal calls
        if (calls >= max_calls or len(json.dumps(body).encode()) > 32768
                or not 0 < body['max_output_tokens'] <= MAX_OUTPUT):
            raise ValueError('probe call or token budget exceeded')
        calls += 1
        status, reply = send(url, headers, body)
        return status, reply or {}

    # Keep every field identical except the tool's parameter envelope.
    original = deepcopy(fixed)
    original['tools'][0]['parameters'] = payload['tools'][0]['tools'][0]['parameters']
    original['tools'][0].pop('strict', None)
    original['tools'][0]['description'] = 'probe.run: Returns a synthetic marker.'
    before_status, before = request(original)
    after_status, after = request(fixed)
    result = {'model': model, 'effort': effort, 'before_status': before_status,
              'before_reason': upstream.rejection_reason(json.dumps(before)),
              'after_status': after_status, 'served_model': request_evidence.identifier(after.get('model')),
              'arguments_match': False, 'marker_match': False}
    if after_status == 200:
        output = after.get('output', [])
        tool_calls = [item for item in output if item.get('type') == 'function_call']
        if len(tool_calls) == 1:
            native = ToolEvents(names).item(deepcopy(tool_calls[0]))
            result['arguments_match'] = (native.get('namespace') == 'probe'
                and native.get('name') == 'run'
                and json.loads(native['arguments']) == {'code': 'probe'})
            if result['arguments_match']:
                replay = deepcopy(payload)
                replay['input'].extend([native, {'type': 'function_call_output',
                    'call_id': native['call_id'], 'output': MARKER}])
                followup, _ = project_external(replay, '/responses', model, row)
                final_status, final = request(followup)
                result['final_status'] = final_status
                result['marker_match'] = final_status == 200 and any(
                    block.get('text', '').strip() == MARKER
                    for item in final.get('output', []) if item.get('type') == 'message'
                    for block in item.get('content', []))
    result['calls'] = calls
    result['pass'] = (before_status == 400 and result['before_reason'] == 'the tool schema was rejected'
                      and result['arguments_match'] and result['marker_match'])
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
