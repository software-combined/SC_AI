"""Offer Switch Codex when the ChatGPT allowance runs out, and the way back.

Codex desktop 26.917.51856 and later disables Send for every model once the
ChatGPT allowance runs out. The router records each such episode in
`codex-usage-limit.json` (docs/runtime-files.md). Every updater pass, the
minute Express job included, reads it here and offers each of these at most
once per episode:

- the signed-out Switch Codex fallback, while the episode lasts and Codex is
  not already signed out, when the episode came from a build from
  `AFFECTED_FROM` up to `FIXED_IN` and the installed app is not yet at `FIXED_IN`;
- the way back, while Codex is signed out, once the episode has ended or the
  installed ChatGPT app is at or above `FIXED_IN`.

The dialog is only the offer: the switch owner still asks before it changes
anything. It applies only to Codex installs in subscription mode. A detached
worker from the retained controller shows it on every platform. Missing
dialogs leave the offer pending.

Python 3.9-safe, stdlib only and side-effect free on import (apart from `sys.path`): the updater loads it by
path, and Switch Codex's installer reuses `APP`.
"""
import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402

APP = Path.home() / 'Applications' / 'Switch Codex.app'
CHATGPT_APP = Path('/Applications/ChatGPT.app')
AFFECTED_FROM = '26.917.51856'
# The first ChatGPT app (Codex) build that keeps Send working once the
# allowance runs out; None until OpenAI ships the fix.
FIXED_IN = None
# The router's file and its rule for an episode with no named reset
# (ai_router/usage_episodes.NAME and WINDOW_S; a test pins both).
EPISODE_FILE = 'codex-usage-limit.json'
WINDOW_S = 5 * 60 * 60
OFFERS_FILE = 'codex-switch-offers.json'
SWITCH, BACK = 'switch', 'back'
MESSAGES = {
    SWITCH: ('Your ChatGPT subscription has reached its usage limit, so the '
             'ChatGPT app (Codex) cannot send messages. Switch it to OpenRouter '
             'models until the limit resets?'),
    BACK: ('The ChatGPT app (Codex) may be able to use your ChatGPT subscription again. '
           'Switch it back from OpenRouter models? Send may still be blocked.'),
}
BACK_OPENROUTER = ('The ChatGPT app (Codex) may be able to use your ChatGPT subscription again. '
                   'Return to OpenRouter models with ChatGPT sign-in? Send may still be blocked.')
_VERSION = re.compile(r'\d{1,9}(?:\.\d{1,9}){0,5}')


def _load(name, filename):
    return loader.load(filename, name)


_HERE = Path(__file__).resolve().parent
_notice = _load('router_offer_notice', _HERE / 'notice.py')
_codex = _load('router_offer_codex_config', _HERE / 'codex_config.py')
_switch = _load('router_offer_switch_config', _HERE / 'codex_switch_config.py')
_atomic = _load('router_offer_atomic_write', _HERE / 'atomic_write.py')


def _version(text):
    """A dotted version as a tuple of ints, or None."""
    if not isinstance(text, str) or not _VERSION.fullmatch(text):
        return None
    return tuple(int(part) for part in text.split('.'))


def _seconds(text):
    """Unix seconds of an ISO-8601 time that names its UTC offset, else None."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return moment.timestamp() if moment.tzinfo is not None else None


def episode(home):
    """The router's last episode with its `end`, or None when missing or corrupt.

    The fields and checks of `ai_router/usage_episodes.current`; the episode
    ends at `resets_at`, or `WINDOW_S` after `seen_at` when none was named.
    """
    try:
        doc = json.loads((Path(home) / EPISODE_FILE).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    seen, resets, version = (doc.get(key) for key in ('seen_at', 'resets_at', 'client_version'))
    start = _seconds(seen)
    parsed = _version(version)
    if start is None or (version is not None and parsed is None):
        return None
    end = start + WINDOW_S if resets is None else _seconds(resets)
    if end is None:
        return None
    return {'seen_at': seen, 'end': end, 'version': parsed}


def fallback_needed(home, now=None):
    """True when this episode needs the signed-out route on the installed app."""
    current = episode(home)
    if current is None:
        return False
    return _episode_active(current, now)


def _episode_active(current, now=None):
    now = time.time() if now is None else now
    fixed = _version(FIXED_IN)
    return now < current['end'] and (fixed is None or (installed() or ()) < fixed)


def installed():
    """The installed ChatGPT app's version as a tuple, or None."""
    try:
        info = plistlib.loads((CHATGPT_APP / 'Contents' / 'Info.plist').read_bytes())
    except (OSError, ValueError):
        return None
    return _version(info.get('CFBundleShortVersionString')) if isinstance(info, dict) else None


def _offered(home, seen_at):
    """The offers already made for the episode that started at `seen_at`."""
    try:
        doc = json.loads((Path(home) / OFFERS_FILE).read_text())
    except (OSError, ValueError):
        return []
    if (not isinstance(doc, dict) or doc.get('seen_at') != seen_at
            or not isinstance(doc.get('offered'), list)):
        return []
    return [kind for kind in doc['offered'] if kind in (SWITCH, BACK)]


def due(home, now=None, platform_name=None, *, include_offered=False):
    """(kind, episode) for the offer this pass should make, else None."""
    platform_name = platform_name or sys.platform
    if (platform_name not in ('darwin', 'win32', 'linux')
            or (platform_name == 'darwin' and not APP.exists())):
        return None
    entry = _codex.codex_attachment(home)
    current = episode(home)
    if not entry.get('inserted_block') or entry.get('openai_mode') == 'none' or current is None:
        return None
    fixed = _version(FIXED_IN)
    if _switch.recorded(entry) != _switch.SWITCHED:
        version = current['version']
        affected = (version is not None and version >= _version(AFFECTED_FROM)
                    and (fixed is None or version < fixed))
        kind = SWITCH if affected and _episode_active(current, now) else None
    else:
        kind = BACK if not _episode_active(current, now) else None
    if kind is None or (not include_offered and kind in _offered(home, current['seen_at'])):
        return None
    return kind, current


def _remember(home, seen_at, offered):
    _atomic.replace_json(Path(home) / OFFERS_FILE, {'seen_at': seen_at, 'offered': offered})


def _claim(home, seen_at, offered, kind):
    """Reserve a writable record without marking the dialog presented."""
    _atomic.replace_json(Path(home) / OFFERS_FILE,
                         {'seen_at': seen_at, 'offered': offered, 'claim': kind})


def _finish_claim(home, seen_at, offered):
    """Clear only this episode's claim; preserve any newer record."""
    current = episode(home)
    if current is not None and current['seen_at'] != seen_at:
        return
    try:
        doc = json.loads((Path(home) / OFFERS_FILE).read_text())
    except (OSError, ValueError):
        return
    if isinstance(doc, dict) and doc.get('seen_at') == seen_at and doc.get('claim') in (SWITCH, BACK):
        _remember(home, seen_at, offered)


def _recover_claim(home):
    """The caller holds the offer lock, so no previous worker is still active."""
    try:
        doc = json.loads((Path(home) / OFFERS_FILE).read_text())
    except (OSError, ValueError):
        return
    if (isinstance(doc, dict) and isinstance(doc.get('seen_at'), str)
            and isinstance(doc.get('offered'), list) and doc.get('claim') in (SWITCH, BACK)):
        _remember(home, doc['seen_at'], _offered(home, doc['seen_at']))


def _offer_desktop(home):
    """Start a retained, detached worker; a launch is not presentation."""
    try:
        version = (Path(home) / 'control-version').read_text().strip()
        if not _load('router_offer_update_status', _HERE / 'update_status.py').version(version):
            return None
        helper = Path(home) / 'control' / version / 'packaging' / Path(__file__).name
        if not helper.is_file():
            return None
    except OSError:
        return
    command = [sys.executable, str(helper), '--home', str(home), '--desktop-offer']
    try:
        _notice._spawn(command)
    except (OSError, ValueError):
        return


def offer(home, now=None, platform_name=None):
    """Start the worker when an offer is due; never claim presentation."""
    try:
        if os.environ.get('ROUTER_NO_NOTICE') == '1':
            return None
        found = due(home, now, platform_name)
        if found is None:
            return None
        return _offer_desktop(home)
    except (Exception, SystemExit):  # an unknown receipt variant raises SystemExit
        return None


def _owner(name):
    """A sibling owner, loaded only when an offer is shown."""
    return _load('router_offer_' + name, _HERE / (name + '.py'))


def offer_and_switch(home, dialog, platform_name=None):
    """Show a due offer, then ask through the switch owner before any restart."""
    platform_name = platform_name or sys.platform
    # Hold only the offer lock while waiting for the person. Updates must not wait.
    with _owner('service').install_lock(home, '.codex-switch-offer.lock') as held:
        if not held:
            return dict(outcome='cancelled')
        try:
            _recover_claim(home)
        except (OSError, ValueError):
            return dict(outcome='cancelled')
        found = due(home)
        if found is None:
            return dict(outcome='cancelled')
        kind, current = found
        seen_at = current['seen_at']
        entry = _codex.codex_attachment(home)
        destination = _switch.SWITCHED if kind == SWITCH else _switch.return_target(entry)
        before = _offered(home, seen_at)
        try:
            _claim(home, seen_at, before, kind)
        except (OSError, ValueError):
            return dict(outcome='cancelled')
        message = (BACK_OPENROUTER if kind == BACK
                   and destination in (_switch.SWITCHED_SIGNED_IN, _switch.OPENROUTER)
                   else MESSAGES[kind])
        if platform_name == 'win32':
            try:
                answer = _owner('windows_dialog').show(message, home, True,
                                                      labels=('Open Switch Codex', 'Later'))
            except (OSError, ValueError, subprocess.SubprocessError):
                answer = None
        else:
            answer = dialog.confirm_result(message, home, labels=('Open Switch Codex', 'Later'))
        try:
            found = due(home, include_offered=True)
            unchanged = _codex.codex_attachment(home) == entry
        except (OSError, ValueError, SystemExit):
            found = None
        # A dialog that was not shown, or an offer that went stale meanwhile, stays pending.
        if found is None or found[0] != kind or found[1]['seen_at'] != seen_at or not unchanged or answer is None:
            _finish_claim(home, seen_at, before)
            return dict(outcome='cancelled')
        if not answer:
            _finish_claim(home, seen_at, before + [kind])
            return dict(outcome='cancelled')
        owner = _owner('codex_desktop_switch')
        failed = False
        try:
            result = owner.switch(home, target=destination, expected=entry, offer_kind=kind, offer_seen=seen_at)
        except (Exception, SystemExit) as exc:
            result, failed = False, True
            safe = str(exc) if isinstance(exc, owner.SwitchError) else 'SCG Router could not finish. Try again.'
            try:
                dialog.message(safe)
            except (Exception, SystemExit):
                pass
        try:
            _finish_claim(home, seen_at, before if result is False else before + [kind])
        except (OSError, ValueError):
            pass
        return dict(outcome=('failed' if failed else 'cancelled')
                    if result is None or result is False else 'done')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--desktop-offer', action='store_true', required=True)
    args = parser.parse_args()
    try:
        offer_and_switch(args.home, _load('router_offer_dialog', _HERE / 'native_dialog.py'))
    except (Exception, SystemExit):
        pass  # The next updater pass can retry a dialog that was not shown.
