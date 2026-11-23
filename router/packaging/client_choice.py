"""Which clients this install serves, and attaching each of them.

Split from the installer entry point, which sits at its recorded line ceiling
(Plan 166). Runs on the installer's Python 3.9: no router imports, and every
collaborator arrives as an argument. A manual run attaches what it finds on
this computer; `client_executable` and `claude_desktop_platform` own how an
assistant is found, `codex_switch_config` which Codex block an attach writes
and `codex_switch_app` whether the Switch Codex app goes with it.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import client_executable  # noqa: E402
import loader  # noqa: E402


def _load(name):
    return loader.load(Path(__file__).resolve().parent / (name + '.py'))


_switch = _load('codex_switch_config')
_app = _load('codex_switch_app')

LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'claude-desktop': 'Claude desktop'}
TERMINAL = {'codex': ('codex',), 'claude': ('claude',), 'both': ('codex', 'claude'), 'none': ()}
_RESTART = {'Codex': 'quit and reopen Codex',
            'Claude Code': 'restart Claude Code',
            'Claude desktop': 'switch Claude to OpenRouter in the SCG Router menu'}
refuse_switched = _switch.refuse_switched


def validate(args):
    """Reject contradictory explicit choices before creating any state."""
    if args.client == 'none' and (args.desktop or args.clients not in (None, 'none')):
        raise SystemExit('--client none conflicts with client attachments')
    if (args.claude_mode is not None and args.anthropic_mode is not None
            and args.claude_mode != args.anthropic_mode):
        raise SystemExit('--claude-mode conflicts with --anthropic-mode')


def require_recovered(home, *, automatic=False):
    if os.path.lexists(Path(home) / '.claude-profile-rotation-pending.json'):
        if automatic:
            print('deferred: recover the saved Claude profile in SCG Router before updating')
            return False
        raise SystemExit('Choose Claude in SCG Router to recover the saved Claude profile before setup or repair.')
    return True


def detect(platform_name=None):
    """The assistants installed on this computer, in attach order."""
    found = []
    for name in ('codex', 'claude'):
        try:
            if client_executable.resolve(name):
                found.append(name)
        except client_executable.DiscoveryError:
            pass  # An install Windows cannot verify is not attached.
    try:
        _load('claude_desktop_platform').app_identity(platform_name or sys.platform)
        found.append('claude-desktop')
    except Exception:  # Detection never stops an install.
        pass
    return tuple(found)


def newly_found(args, home, receipts, automatic):
    """Assistants found on this computer that are not attached yet.

    Only a manual run looks. Client flags, a dry run, a scheduled or Express
    update and a saved `client: none` add nothing. A saved `clients: none` adds
    nothing unless `--connect-found` asks. Mode flags change the attached
    clients only, so they add nothing once any client is attached.
    """
    if automatic or args.dry_run or flagged(args):
        return ()
    path = Path(home) / 'mixed-router-state.json'
    try:
        state = json.loads(path.read_text()) if path.exists() else {}
        saved_none = state.get('client') == 'none' or (
            state.get('clients') == 'none' and not args.connect_found)
        attached = receipts.read_receipt(home).get('clients', {})
    except (OSError, ValueError, AttributeError):
        return ()  # Repair recovers unreadable files first; nothing attaches on top of them.
    mode_only = attached and any((args.openai_mode, args.claude_mode, args.anthropic_mode))
    return () if saved_none or mode_only else tuple(name for name in detect() if name not in attached)


def _choice(names):
    """The saved `clients` value for these terminal clients."""
    return 'both' if len(names) == 2 else names[0] if names else 'none'


def _terminal(home, receipts):
    """The terminal clients the receipts hold, in attach order."""
    attached = receipts.read_receipt(home).get('clients', {})
    return [name for name in ('codex', 'claude') if name in attached]


def saved_clients(home, state, receipts):
    """The saved `clients` choice, else the terminal clients the receipts hold.

    A missing choice is never read as Codex, and reading it saves nothing.
    """
    if state.get('client') == 'none':
        return 'none'
    if isinstance(state.get('clients'), str):
        return state['clients']
    try:
        return _choice(_terminal(home, receipts))
    except (OSError, ValueError, AttributeError):
        return 'none'  # An unreadable receipt names no client.


def save_attached(args, home, state, receipts, write_state):
    """Save the terminal clients the receipts now hold after a run without client flags.

    The restart notice and later scheduled updates read this saved choice, so it
    names exactly what is connected. Finding nothing never saves `none`, and a
    saved `none` changes only on a run that found assistants (`--connect-found`).
    """
    if flagged(args) or (state.get('clients') == 'none' and not getattr(args, 'found', ())):
        return
    try:
        names = _terminal(home, receipts)
    except (OSError, ValueError):
        return  # The service-only repair leaves an unreadable receipt alone.
    if names and state.get('clients') != _choice(names):
        state['clients'] = _choice(names)
        write_state(home, state)


def resolve(args, home, state, receipts, write_state, repair=False):
    """Explicit flags, else attached clients or the saved choice plus newly found ones.

    Saves only the choice from flags, receipts or the saved choice; a newly
    found assistant is saved by `save_attached` once it attaches. A saved
    `none` changes only with `--clients` or `--client`.
    """
    validate(args)
    found = getattr(args, 'found', ())
    try:
        attached = receipts.read_receipt(home).get('clients', {})
    except (OSError, ValueError):
        if not repair or any((args.client, args.clients, args.desktop,
                              args.openai_mode, args.claude_mode, args.anthropic_mode)):
            raise SystemExit('client receipts are unreadable; repair them before continuing')
        # The service-only repair leaves unreadable client settings and receipts alone.
        attached = {}
    explicit = flagged(args)
    if (attached and args.clients is None and args.client is None
            and any((args.openai_mode, args.claude_mode, args.anthropic_mode))):
        explicit = False  # Mode-only completion follows every retained attachment.
    client = (args.client or 'codex') if explicit else state.get('client', 'codex')
    if client not in ('codex', 'none'):
        raise SystemExit('client must be codex or none')
    if explicit:
        clients = args.clients or ('none' if client == 'none' or args.desktop else 'codex')
        # A bare --desktop names no terminal client, so it keeps the saved choice.
        keep = clients if args.clients is not None or args.client is not None else None
    else:
        saved = state.get('clients')
        if attached:
            names = [name for name in ('codex', 'claude') if name in attached]
        else:
            names = list(TERMINAL.get(saved, ()) if isinstance(saved, str) else ())
        # Found assistants are saved only once they attach (`save_attached`).
        # Finding nothing never saves `none`, and a saved `none` stays without client flags.
        keep = _choice(names) if names and saved != 'none' else None
        clients = _choice(names + [name for name in found
                                   if name in ('codex', 'claude') and name not in names])
    if clients not in TERMINAL:
        raise SystemExit('clients must be codex, claude, both, or none')
    claude_mode = args.claude_mode or args.anthropic_mode or state.get(
        'anthropic_mode', state.get('claude_mode', 'subscription'))
    mode = args.openai_mode or state.get('openai_mode') or 'subscription'
    if claude_mode not in ('subscription', 'none') or mode not in ('subscription', 'none'):
        raise SystemExit('openai_mode and claude_mode must be subscription or none')
    updated = dict(state, claude_mode=claude_mode, openai_mode=mode)
    if state.get('client', 'codex') != client:
        updated['client'] = client
    if keep is not None:
        updated['clients'] = keep
    if (args.claude_mode is not None or args.anthropic_mode is not None
            or args.clients in ('claude', 'both') or args.desktop
            or {'claude', 'claude-desktop'} & set(found)):
        updated['anthropic_mode'] = claude_mode
    elif ('anthropic_mode' not in state
          and mode != state.get('openai_mode', 'subscription')
          and any(name in attached for name in ('claude', 'claude-desktop'))):
        # Legacy Claude shares OpenAI's mode until an independent choice is saved.
        claude_mode = state.get('openai_mode', 'subscription')
        updated.update(claude_mode=claude_mode, anthropic_mode=claude_mode)
    if updated != state:
        write_state(home, updated)
        state.update(updated)
    return client, clients, claude_mode, mode


def mode_flags(state, attached):
    """Mode-only completion arguments for attached clients with saved answers."""
    flags = []
    for clients, key in ((('codex',), 'openai_mode'), (('claude', 'claude-desktop'), 'claude_mode')):
        mode = state.get('anthropic_mode', state.get(key)) if key == 'claude_mode' else state.get(key)
        if mode in ('subscription', 'none') and any(
                client in attached and attached[client].get(key, 'subscription') != mode for client in clients):
            flags += ['--' + key.replace('_', '-'), mode]
    return flags


def _connected(names, home, receipts):
    """One client-aware closing line; never names a client that is not served."""
    if not names:
        try:
            attached = receipts.read_receipt(home).get('clients', {})
        except (OSError, ValueError, AttributeError):
            attached = {}
        kept = [label for name, label in LABELS.items() if name in attached]
        return 'no client changes; %s still connected' % ', '.join(kept) if kept else 'no assistant connected'
    return '%s connected; %s to use the router.' % (
        ', '.join(names), ' and '.join(_RESTART[name] for name in names))


def attach_codex(home, state, mode, codex_config, previous=None,
                 static_catalogue=False, python=None):
    """Write the Codex provider block and receipt; returns the config path.

    Shared with the full install path so a current install and a fresh one
    write the same block, the same before-image and the same receipt. The
    block is the variant the receipt records, so an update never switches
    Codex to or from the router's own provider. Given the router's `python`,
    the Switch Codex app is then built, refreshed or removed to match.
    """
    if previous is None:
        previous = codex_config.codex_attachment(home)
    config_path = Path.home() / '.codex' / 'config.toml'
    variant = _switch.recorded(previous)
    if variant != _switch.DEFAULT and previous.get('openai_mode') not in (None, mode):
        variant = _switch.SWITCHED_BACK
    block = _switch.build(home, state, mode, static_catalogue, variant)
    # The installer never writes, rewrites, or re-enforces global instructions.
    rules_receipt = previous.get('global_instructions')
    stamp = time.strftime('%Y%m%d-%H%M%S', time.gmtime()) + '-' + uuid.uuid4().hex[:8]
    (home / f'config-before-{stamp}.toml').write_bytes(
        (config_path.read_text() if config_path.exists() else '').encode())
    try:
        os.chmod(home / f'config-before-{stamp}.toml', 0o600)
    except OSError:
        pass
    block, before, desktop, reviewer = codex_config.attach_config(
        config_path, block, previous, seed_external=mode == 'none' or variant in _switch.ROUTED_VARIANTS,
        python=python)
    after = codex_config._owned.read(config_path)
    codex_config._owned.inspect(after, block, python=python)
    event = previous.get('repair_notice') if after == before else None
    event = event or uuid.uuid4().hex
    fallback_return = previous.get(_switch.FALLBACK_RETURN)
    codex_config.write_receipt(home, config_path, block, rules_receipt, mode, before,
                               desktop=desktop, variant=variant if variant != _switch.DEFAULT else None,
                               reviewer=reviewer, repair_notice=event, fallback_return=fallback_return
                               if variant == _switch.SWITCHED else None)
    entry = codex_config.codex_attachment(home)
    codex_config._owned.inspect(codex_config._owned.read(config_path), block, python=python)
    if entry.get('inserted_block') != block or entry.get('repair_notice') != event:
        raise OSError('attachment readback failed')
    try:
        _load('notice').record_attachment(home, _load('service').current_version(home), event)
    except (Exception, SystemExit):
        pass
    if python:
        _app.sync(home, python)
    return config_path


def attach_each(home, state, mode, names, *, codex, desktop, claude, python, saved=None,
                static_catalogue=False, explicit=False):
    """Attach each client on its own, so one that refuses never stops the others.

    Only a client named by flag or already attached fails the run, once every
    client has been tried. Any other client that refuses (newly found, or only
    saved) is skipped. If a newly found Claude desktop cannot connect, setup
    skips it without a message. Returns the labels of the attached clients.
    """
    try:
        before = codex.read_receipt(home).get('clients', {})
    except (OSError, ValueError):
        before = {}  # The service-only repair leaves an unreadable receipt alone.
    done, errors = [], []
    for name in names:
        try:
            if name == 'codex':
                attach_codex(home, state, mode, codex, static_catalogue=static_catalogue, python=python)
            elif name == 'claude':
                claude(home, state, python=python)
            else:
                desktop.attach(home, state, codex, saved, python=python)
            done.append(LABELS[name])
        except (Exception, SystemExit) as exc:
            if explicit or name in before:
                errors.append(exc)
            elif name != 'claude-desktop':
                print('%s was not connected: %s' % (LABELS[name], exc))
    if errors:
        raise errors[0]
    return done


def flagged(args):
    """True when flags name the clients, so each named client must attach."""
    return args.clients is not None or args.client is not None or bool(args.desktop)


def wanted(args, clients, saved):
    """The clients to attach, in order: terminal clients, then Claude desktop when asked for, saved or found."""
    desktop = args.desktop or saved or 'claude-desktop' in getattr(args, 'found', ())
    return list(TERMINAL[clients]) + ['claude-desktop'] * bool(desktop)


def attach_current(args, home, *, codex, desktop, claude, resolve, ensure_state, python, ready,
                   write_state):
    """Attach the wanted clients without re-extracting the release.

    Additive by design: it attaches and detaches nothing. `--clients none
    --desktop` means the Claude desktop profile alone.
    """
    if args.dry_run:
        print('would connect the selected clients to the installed router')
        return 0
    require_recovered(home)
    state = ensure_state(home)
    previous = state.copy()
    _, clients, _, mode = resolve(args, home, state)
    saved = desktop.saved_profile(home, codex) if args.desktop or getattr(args, 'repair', False) else None
    names = wanted(args, clients, saved)
    if not names:
        ready(home, state, previous, python, only_if_changed=True)
        print(_connected(names, home, codex))
        return 0
    ready(home, state, previous, python)
    connected = attach_each(home, state, mode, names, codex=codex, desktop=desktop, claude=claude,
                            python=python, saved=saved, static_catalogue=args.static_catalogue,
                            explicit=flagged(args))
    save_attached(args, home, state, codex, write_state)
    print(_connected(connected, home, codex))
    return 0
