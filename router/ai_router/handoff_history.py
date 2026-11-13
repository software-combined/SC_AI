"""Handoff history vocabulary, parsing and native readable-name projection."""
import json
import re

NATIVE_NAMESPACE = 'collaboration'
PLAINTEXT_NAMESPACE = 'collaboration_plaintext'
HANDOFF_TOOLS = frozenset(('spawn_agent', 'send_message', 'followup_task'))
# Backend handoff ciphertext: matched all 568 saved encrypted messages (Sep 2026).
CIPHERTEXT = re.compile(r'gAAAA[A-Za-z0-9_-]{40,}={0,2}')


def arguments(item):
    """Parse function-call arguments leniently; {} when absent or malformed."""
    raw = item.get('arguments')
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def spawn_model(spawns, target):
    """Resolve a child path to one spawn model; ambiguous targets return None."""
    if not isinstance(target, str) or not target:
        return None
    if target in spawns:
        return spawns[target]
    suffix = target.rsplit('/', 1)[-1]
    matches = [model for task, model in spawns.items() if suffix == task]
    if len(matches) != 1:
        return None
    return matches[0]


def spawn_models(items):
    """Map canonical or already-projected spawn history to requested models."""
    models = {}
    if not isinstance(items, list):
        return models
    for item in items:
        if (not isinstance(item, dict) or item.get('type') != 'function_call'
                or item.get('namespace') not in (NATIVE_NAMESPACE, PLAINTEXT_NAMESPACE)
                or item.get('name') != 'spawn_agent'):
            continue
        args = arguments(item)
        task, model = args.get('task_name'), args.get('model')
        if isinstance(task, str) and task and isinstance(model, str) and model:
            models[task] = model
    return models


def message_shape(item):
    """'absent', 'readable', 'ciphertext' or 'other'; a classification, never content."""
    message = arguments(item).get('message')  # Unparseable arguments fail in Codex first.
    if message is None:
        return 'absent'
    if not isinstance(message, str):
        return 'other'
    return 'ciphertext' if CIPHERTEXT.fullmatch(message) else 'readable'


def project_readable_calls(payload, names):
    """Match model-visible history to offered aliases, never rewrite saved calls.

    Only an explicit plaintext marker and readable message qualify. Arguments,
    identifiers, markers and outputs remain exactly as the client supplied them.
    """
    items = payload.get('input')
    if not names or not isinstance(items, list):
        return payload
    projected = []
    for item in items:
        if (isinstance(item, dict) and item.get('type') == 'function_call'
                and item.get('namespace') == NATIVE_NAMESPACE and item.get('name') in names
                and item.get('encrypted_function_args') == [] and message_shape(item) == 'readable'):
            item = {**item, 'namespace': PLAINTEXT_NAMESPACE}
        projected.append(item)
    return payload if all(new is old for new, old in zip(projected, items)) else {**payload, 'input': projected}
