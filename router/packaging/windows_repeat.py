"""Read-only readiness check invoked by the exact Windows installer."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_payload import load, read_json


def ready(home, resources, version):
    service = load('service')
    state = service._state.read_strict(service._state.path(home))
    port, token = state.get('port'), state.get('token')
    if (type(port) is not int or not 0 < port <= 65535
            or not isinstance(token, str) or not re.fullmatch('[A-Za-z0-9_-]+', token)):
        return False
    native = load('native_resources')
    if (service.current_version(home) != version or native.current(home) != resources
            or not native.ready(home) or not load('native_readiness').choices_applied(home)):
        return False
    diagnostics = load('diagnostics')
    if diagnostics._provider_defs().unhandled(home, state, diagnostics._key_private):
        return False
    source = resources / 'router'
    manifest = read_json(source / 'MANIFEST.json')
    bundle = load('bundle')
    for parent in ('releases', 'control'):
        installed = home / parent / version
        if read_json(installed / 'MANIFEST.json') != manifest:
            return False
        bundle.check_identity(version, manifest, installed)
        bundle.check_manifest(installed, manifest)
    if not native._backend().runtime_matches(str(resources / 'runtime/python/pythonw.exe'), home):
        return False
    response = service.health(state, timeout=3)
    return bool(response and response.get('version') == version)


if __name__ == '__main__':
    try:
        result = ready(Path(sys.argv[1]), Path(__file__).resolve().parents[2], sys.argv[2])
    except (Exception, SystemExit):
        result = False
    raise SystemExit(0 if result else 1)
