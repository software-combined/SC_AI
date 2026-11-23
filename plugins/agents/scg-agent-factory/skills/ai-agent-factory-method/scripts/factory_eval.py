"""Summarise how Factory chats ran, from local Codex run records.

Read-only and standard library only. Prints chat titles and counts, never
message content. It lists top-level chats named `{Project}: {Role}`, the
Factory naming convention; use --project to keep one team.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re

WAIT_TOOLS = {'wait', 'wait_agent', 'sleep', 'list_agents'}
SPAWN_TOOLS = {'spawn_agent', 'multi_agent_v1.spawn_agent'}
ASK_TOOLS = {'request_user_input', 'request_user_input_async'}
HIGH_EFFORTS = {'max', 'xhigh'}
LANE = re.compile(r'simplif|correctness|quality|adversarial|security', re.I)
SKILL_FILE = 'ai-agent-factory-method/SKILL.md'
SKILL_HEADING = '# AI Agent Factory Method'
NAME = re.compile(r'^([^:]{1,60}):\s*(.+)$')


def thread_names(codex_home):
    names = {}
    index = codex_home / 'session_index.jsonl'
    if index.exists():
        for line in index.open(encoding='utf-8', errors='replace'):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and isinstance(row.get('id'), str):
                names[row['id']] = row.get('thread_name') or ''
    return names


def text_of(payload):
    parts = payload.get('content')
    parts = parts if isinstance(parts, list) else []
    return ' '.join(str(part.get('text', '')) for part in parts if isinstance(part, dict))


def read_skill(payload):
    """True when this record item reads or loads the Factory skill."""
    # ponytail: a tool call that only names the skill file, such as a brief, counts as a read;
    # match read commands only when that false negative matters.
    item = payload.get('type')
    if item == 'function_call':
        return SKILL_FILE in str(payload.get('arguments', ''))
    if item == 'custom_tool_call':
        return SKILL_FILE in str(payload.get('input', ''))
    return item == 'message' and SKILL_HEADING in text_of(payload)


def is_human(text):
    head = text.lstrip()[:300]
    return bool(head) and not head.startswith(('<', '# AGENTS.md')) and '<environment_context>' not in head


def scan(path, since):
    """Count one run record's activity from `since` onwards."""
    run = {'id': None, 'parent': None, 'tools': Counter(), 'human': 0, 'fresh_tokens': 0,
           'turns': 0, 'high_effort_turns': 0, 'skill_reads': 0, 'skill_ever': False, 'task': ''}
    with path.open(encoding='utf-8', errors='replace') as lines:
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            kind, payload = event.get('type'), event.get('payload')
            payload = payload if isinstance(payload, dict) else {}
            if kind == 'session_meta':
                run['id'], run['parent'] = payload.get('id'), payload.get('parent_thread_id')
                continue
            read = kind == 'response_item' and read_skill(payload)
            run['skill_ever'] |= read
            if str(event.get('timestamp') or '') < since:
                continue
            run['skill_reads'] += read
            if kind == 'turn_context':
                run['turns'] += 1
                run['high_effort_turns'] += str(payload.get('effort')) in HIGH_EFFORTS
            elif kind == 'event_msg' and payload.get('type') == 'token_count':
                usage = ((payload.get('info') or {}).get('last_token_usage')) or {}
                fresh = usage.get('input_tokens', 0) - usage.get('cached_input_tokens', 0)
                run['fresh_tokens'] += max(0, fresh) + usage.get('output_tokens', 0)
            elif kind == 'response_item':
                item = payload.get('type')
                if item in ('function_call', 'custom_tool_call'):
                    run['tools'][payload.get('name')] += 1
                elif item == 'message' and payload.get('role') == 'user':
                    run['human'] += is_human(text_of(payload))
                elif item == 'agent_message' and not run['task']:
                    run['task'] = text_of(payload)[:300]
    return run


def collect(codex_home, days):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    since = start.strftime('%Y-%m-%dT%H:%M:%S')
    names = thread_names(codex_home)
    runs = [scan(p, since) for p in sorted((codex_home / 'sessions').rglob('*.jsonl'))
            if datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) >= start]
    runs = [r for r in runs if r['id']]
    children = defaultdict(list)
    for run in runs:
        if run['parent']:
            children[run['parent']].append(run)
    chats = []
    for run in runs:
        match = NAME.match(names.get(run['id'], '')) if not run['parent'] else None
        if not match or not (run['turns'] or children[run['id']]):
            continue
        kids = children[run['id']]
        lanes = sum(bool(LANE.search(names.get(k['id'], '') + ' ' + k['task'])) for k in kids)
        tools = run['tools']
        calls = sum(tools.values())
        chats.append({
            'project': match.group(1).strip(), 'role': match.group(2).strip(),
            'human_messages': run['human'], 'tool_calls': calls,
            'waiting_share': round(sum(tools[t] for t in WAIT_TOOLS) / calls, 2) if calls else 0.0,
            'spawned': sum(tools[t] for t in SPAWN_TOOLS), 'children': len(kids),
            'review_lane_share': round(lanes / len(kids), 2) if kids else 0.0,
            'asked_human': sum(tools[t] for t in ASK_TOOLS),
            'high_effort_share': round(run['high_effort_turns'] / run['turns'], 2) if run['turns'] else 0.0,
            'skill_reads': run['skill_reads'], 'skill_read_on_record': run['skill_ever'],
            'fresh_tokens': run['fresh_tokens'] + sum(k['fresh_tokens'] for k in kids),
        })
    return sorted(chats, key=lambda c: (c['project'].lower(), c['role'].lower()))


def signals(chat):
    found = []
    if chat['waiting_share'] > 0.5:
        found.append('mostly waiting')
    if chat['review_lane_share'] > 0.8 and chat['children'] >= 20:
        found.append('review-heavy')
    if chat['asked_human'] and 'project manager' not in chat['role'].lower():
        found.append('owner asked human')
    if chat['high_effort_share'] > 0.5:
        found.append('mostly max effort')
    if 'project manager' in chat['role'].lower() and not chat['skill_read_on_record']:
        found.append('skill not read')
    return found


def report(chats):
    rows = ['| Chat | Human msgs | Tool calls | Waiting | Spawned | Review lanes | Max effort | Skill reads '
            '| Fresh tokens | Watch |',
            '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for c in chats:
        rows.append(f"| {c['project']}: {c['role']} | {c['human_messages']} | {c['tool_calls']} | "
                    f"{c['waiting_share']:.0%} | {c['spawned']} | {c['review_lane_share']:.0%} | "
                    f"{c['high_effort_share']:.0%} | {c['skill_reads']} | {c['fresh_tokens'] / 1e6:.1f}M | "
                    f"{', '.join(signals(c)) or '-'} |")
    return '\n'.join(rows) if chats else 'No Factory chats found in this period.'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=7, help='period to review (default 7)')
    parser.add_argument('--project', help='only this project prefix, for example "Atlas"')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', '~/.codex'))
    parser.add_argument('--json', action='store_true', help='print rows as JSON')
    args = parser.parse_args(argv)
    chats = collect(Path(args.codex_home).expanduser(), args.days)
    if args.project:
        chats = [c for c in chats if c['project'].lower() == args.project.lower()]
    if args.json:
        print(json.dumps([c | {'watch': signals(c)} for c in chats], indent=2))
    else:
        print(report(chats))


if __name__ == '__main__':
    main()
