"""First-run key window flow (Plan 139); the loopback page is the fallback.

The installer spawns this module with the setup URL and the running router
calls `open_window` from a worker thread. Either way the popup asks how to
connect (work account or own key), collects the key through
`ai_router.key_dialog` when needed, submits it to the single-use nonce route
and shows a native confirmation. Subscription modes come from the installer's
defaults or saved choices, never from this window.
The key never enters argv, the environment, a file or a log: it travels from
the dialog tool's stdout pipe straight into the POST body. A host with no
dialog tool falls back to the loopback page, which stays the only HTML
surface.

Run manually: `python -m ai_router.key_prompt <setup-url>`
or pipe the URL on stdin with `--stdin` so it never appears in `ps`.
"""
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from . import key_dialog, key_store, provider_defs, setup_page, work_account


def submit(url, fields, opener=None):
    """POST the popup's choices; (status, payload) with the route's JSON."""
    if opener is None:
        opener = urllib.request.urlopen
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(),
        headers={'Accept': 'application/json',
                 'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with opener(request, timeout=30) as response:
            return _payload(response.status, response.read())
    except urllib.error.HTTPError as exc:
        return _payload(exc.code, exc.read())


def _payload(status, body):
    """The route's JSON, or a shaped failure for anything else it returns."""
    try:
        payload = json.loads(body or b'{}')
    except ValueError:
        payload = {}
    if not isinstance(payload, dict) or 'ok' not in payload:
        return status, {'ok': False, 'error': 'setup failed (%s)' % status}
    return status, payload


def _confirm_text(payload, *, managed=False):
    if managed:
        return 'You are signed in. Your work key is saved on this computer.'
    return ('Your key is saved on this computer.\n\nKey: %s\nCredit left: %s'
            % (payload.get('label', 'your key'),
               setup_page.remaining(payload.get('limit'), payload.get('usage'))))


def _open_page(url, opener=None, label=provider_defs.label_for(provider_defs.DEFAULT_EXTERNAL)):
    """Loopback-page fallback; the URL is printed only on a TTY."""
    try:
        opened = (opener or webbrowser.open)(url) is not False
    except OSError:
        opened = False
    if sys.stdout.isatty():
        print('open %s to connect your %s key' % (url, label))
    return opened


def run_window(url, tool_path=None, platform_name=None, which=None, run=None,
               opener=None, post=None, provider_id=None,
               label=provider_defs.label_for(provider_defs.DEFAULT_EXTERNAL), work=False,
               confirm=True):
    """Prompt, submit, confirm. 0 stored, 2 cancelled, 3 no GUI, 1 refused."""
    if not _local_setup_url(url):
        return 1
    if platform_name is None:
        platform_name = sys.platform
    if tool_path is None:
        tool_path = key_dialog.tool(platform_name=platform_name, which=which)
    if tool_path is None:
        _open_page(url, opener, label)
        return 3
    managed = work and (provider_id or provider_defs.DEFAULT_EXTERNAL) == provider_defs.OPENROUTER.id
    while True:
        try:
            collected = work_account.MANUAL
            if managed:
                collected = work_account.collect(tool_path, platform_name, run)
                if collected is work_account.CANCELLED:
                    return 2
            if collected is work_account.MANUAL:
                managed = False
                collected = key_dialog.collect(tool_path, platform_name=platform_name,
                                               run=run, provider_id=provider_id)
        except work_account.SignInFailed as exc:
            key_dialog.message(tool_path, str(exc), platform_name=platform_name, run=run)
            return 1
        except subprocess.TimeoutExpired:
            # The dialog runner has already closed the window. Treat inactivity as Cancel.
            return 2
        except (OSError, subprocess.SubprocessError):
            _open_page(url, opener, label)
            return 3
        if collected is None:
            return 2
        if not collected['key']:
            key_dialog.message(tool_path, f'Paste an {label} key before saving.',
                               platform_name=platform_name, run=run)
            continue
        try:
            status, payload = submit(url, collected, opener=post)
        except (OSError, ValueError):
            key_dialog.message(tool_path,
                               'Could not reach the router; re-run the installer.',
                               platform_name=platform_name, run=run)
            return 1
        if payload.get('ok'):
            if confirm:
                key_dialog.message(tool_path, _confirm_text(payload, managed=managed),
                                   platform_name=platform_name, run=run)
            return 0
        error = payload.get('error') or 'setup failed (%s)' % status
        if status == 409:
            error = 'A key is already saved on this computer. Open SCG Router and choose Check setup.'
        key_dialog.message(tool_path, error,
                           platform_name=platform_name, run=run)
        if managed or payload.get('key_saved') or status in (404, 409):
            return 1


def open_window(url, thread=False, which=None, opener=None, platform_name=None,
                run=None, post=None, provider_id=None):
    """Open the popup (or the page); True when a window was started.

    `thread=True` is the router path: the popup must not hold the request
    thread, and it submits back to the same server. `opener` belongs to the
    browser fallback only; `post` is the HTTP seam, so a caller can never
    wire `webbrowser.open` into the key POST.
    """
    label = provider_defs.label_for(provider_id or provider_defs.DEFAULT_EXTERNAL)
    if platform_name is None:
        platform_name = sys.platform
    if key_dialog.tool(platform_name=platform_name, which=which) is None:
        return _open_page(url, opener, label)
    if not thread:
        return run_window(url, platform_name=platform_name, which=which, run=run,
                          opener=opener, post=post,
                          provider_id=provider_id, label=label, work=True) == 0
    threading.Thread(target=run_window, args=(url,),
                     kwargs=dict(platform_name=platform_name, which=which,
                                 run=run, opener=opener, post=post,
                                 provider_id=provider_id, label=label, work=True),
                     daemon=True).start()
    return True


def _parse(argv):
    """The setup URL, or None; a trailing `--clients <set>` is ignored.

    Installers and setup apps still pass `--clients`, so
    it stays accepted although the window asks nothing per client.
    """
    args = list(argv)
    if len(args) >= 2 and args[-2] == '--clients':
        args = args[:-2]
    if args == ['--stdin']:
        # The installer pipes the URL here so the token never appears in `ps`.
        args = [sys.stdin.readline().strip()]
    if len(args) != 1 or not _local_setup_url(args[0]):
        return None
    return args[0]


def _local_setup_url(url):
    """A work key may be submitted only to the Router's local setup route."""
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                and parsed.username is None and parsed.password is None
                and parsed.port is not None and 0 < parsed.port <= 65535
                and not parsed.query and not parsed.fragment
                and parsed.path.startswith('/'))
    except (ValueError, TypeError, AttributeError):
        return False


def main(argv=None):
    """CLI entry point: `python -m ai_router.key_prompt <setup-url>`."""
    url = _parse(sys.argv[1:] if argv is None else argv)
    if url is None:
        print('usage: python -m ai_router.key_prompt (<loopback setup URL> | --stdin)',
              file=sys.stderr)
        return 1
    # Native setup shows its own closing notice, so it skips this confirmation.
    result = run_window(url, work=True, confirm=os.environ.get('ROUTER_NO_KEY_CONFIRM') != '1')
    if result == 2 and os.environ.get('ROUTER_CANCEL_REPLACEMENT') == '1':
        try:
            submit(url, {'cancel': '1'}, opener=key_store._open_without_redirects)
        except (OSError, ValueError):
            pass  # An unavailable check leaves setup pending without changing the key.
    return result


if __name__ == '__main__':
    sys.exit(main())
