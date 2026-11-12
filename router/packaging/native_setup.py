"""Graphical setup and maintenance, running entirely on the bundled Python."""
import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_payload import install_arguments, load, metadata, read_json, record_channel, retained, succeeded as _succeeded
import client_executable

ACTIONS = (('resume', 'Update or repair'), ('status', 'Check setup'),
           ('add', 'Connect another assistant'), ('key', 'Set up model access'),
           ('remove', 'Remove router'))
ASSISTANT_DOWNLOADS = {'codex': 'https://chatgpt.com/download/',
                       'claude': 'https://claude.com/download'}


def environment(resources):
    """Find the packaged wrapper; it scopes GTK dependencies to its child."""
    env = dict(os.environ)
    gui = Path(resources) / 'gui'
    if gui.is_dir():
        env['PATH'] = str(gui / 'bin') + os.pathsep + env.get('PATH', '')
    return env


def run_installer(resources, home, flags=(), run=subprocess.run):
    state = read_json(Path(home) / 'mixed-router-state.json')
    key, repair, package = (flag in flags for flag in ('--setup', '--repair', '--install-package'))
    args = install_arguments(resources, home, state, key=key, repair=repair, package=package)
    # Explicit clients replace selection; mode-only completion follows receipts.
    if '--clients' in flags or '--openai-mode' in flags or '--claude-mode' in flags:
        if '--choose-clients' in args:
            args.remove('--choose-clients')
        if '--clients' in args:
            index = args.index('--clients')
            del args[index:index + 2]
    args += [flag for flag in flags if flag not in ('--setup', '--repair', '--install-package')]
    if not key and not repair and not package:
        attached = load('codex_config').read_receipt(home).get('clients', {})
        if '--desktop' not in args and 'claude-desktop' in attached:
            args.append('--desktop')
    env = environment(resources)
    env.update(ROUTER_NO_KEY_WINDOW='1', ROUTER_NO_CLIENT_CHOOSER='1', ROUTER_NO_NOTICE='1')
    env['SCG_NATIVE_RESOURCES'] = str(resources)
    return load('install_delivery').run_logged(home, 'setup',
        'key' if key else 'repair' if repair else 'install',
        lambda: run(args, capture_output=True, text=True, timeout=900, env=env))


def status(resources, home, run=subprocess.run):
    python = Path(resources) / 'runtime' / metadata(resources)['runtime_exec']
    source = load('native_controller').launcher_source(home, Path(resources) / 'router')
    result = run([str(python), str(source / 'packaging/install.py'),
                  '--status', '--json', '--home', str(home)], capture_output=True,
                 text=True, timeout=30, env=environment(resources))
    if result.returncode:
        raise ValueError('The router status could not be checked.')
    facts = json.loads(result.stdout)
    progress = read_json(Path(home) / 'setup-progress.json')
    facts['onboarding'] = load('native_readiness').check(home, source, facts, progress, run)
    facts['downloads'] = {'access_ready': True, 'public': True}
    return facts


def _select(dialog):
    picked = dialog.dialog.ask()
    if picked is None or picked is dialog.dialog.CANCELLED:
        return None
    clients, desktop = dialog.dialog.plan(*picked)
    flags = ['--clients', clients]
    if desktop:
        flags.append('--desktop')
    return flags


def _missing_assistant(flags, dialog, run=None):
    skills = load('agent_skills')
    selected = flags[flags.index('--clients') + 1]
    clients = ['codex', 'claude'] if selected == 'both' else [selected]
    if '--desktop' in flags and 'claude' not in clients:
        clients.append('claude')
    for client in clients:
        if client == 'none':
            continue
        while True:
            try:
                executable = client_executable.resolve(client, path=skills.client_path(), run=run)
                reason = None
            except client_executable.DiscoveryError as error:
                executable, reason = None, error.reason
            if executable or reason is None:
                break
            label = 'Codex' if client == 'codex' else 'Claude Code'
            detail = ('%s was found, but its included setup tool could not be verified.' % label
                      if reason == 'bundled_cli_invalid' else
                      'Windows could not confirm which %s installation to use.' % label)
            if dialog.confirm_result(
                    '%s\n\n'
                    'Try again, or cancel and contact Software Combined IT. '
                    'Your assistant can stay open.' % detail,
                    labels=('Try again', 'Cancel')) is not True:
                return True
        if executable:
            continue
        label = 'Codex' if client == 'codex' else 'Claude Code'
        if client == 'claude' and '--desktop' in flags:
            label = 'Claude Code setup tools from Claude desktop’s Install page'
        if dialog.confirm('%s was not found.\n\n'
                          'Continue opens its download page. Run SCG Router again after installation.' % label):
            webbrowser.open(ASSISTANT_DOWNLOADS[client])
        return True
    return False


def _complete_choices(resources, home):
    flags = load('client_choice').mode_flags(read_json(Path(home) / 'mixed-router-state.json'),
        load('codex_config').read_receipt(home).get('clients', {}))
    if flags and not _succeeded(run_installer(resources, home, flags)):
        raise ValueError('Your key is kept. Choose Check setup in SCG Router to apply your choices.')
    if read_json(Path(home) / 'mixed-router-state.json').get('setup'):
        raise ValueError('Model access is unfinished. Keep your saved key and contact Software Combined IT.')
    return 0


def _key(resources, home, replace=False, run=subprocess.run):
    """Return the key window's outcome: 0 saved/usable, 1 reported failure, 2 cancel."""
    state = read_json(Path(home) / 'mixed-router-state.json')
    if not replace:
        diagnostics = load('diagnostics')
        if not diagnostics._provider_defs().unhandled(Path(home), state, diagnostics._key_private):
            return _complete_choices(resources, home)
    if replace:
        with load('native_dialog').Progress('Opening key setup. This can take a few minutes.\n\n'
                'Cancel closes setup after the current step finishes.', home=home) as progress:
            result = run_installer(resources, home, ['--setup'])
        if progress.cancelled:
            return 2
        if not _succeeded(result):
            raise ValueError('The key window could not be prepared. Try setup again.')
        state = read_json(Path(home) / 'mixed-router-state.json')
    setup = state.get('setup', {})
    if not setup.get('nonce') or setup.get('expires', 0) <= time.time():
        return _complete_choices(resources, home)
    python = Path(resources) / 'runtime' / metadata(resources)['runtime_exec']
    url = 'http://127.0.0.1:%s/%s/setup/%s' % (state['port'], state['token'], setup['nonce'])
    release = Path(home) / 'releases' / (Path(home) / 'current').read_text().strip()
    try:
        attached = load('codex_config').read_receipt(home).get('clients', {})
    except (OSError, ValueError):  # An unreadable receipt must not block replacing the key.
        attached = {}
    clients = state.get('clients', 'codex')
    if clients == 'none' and 'claude-desktop' in attached:
        clients = 'claude'  # Claude desktop alone still needs the Claude subscription answer.
    result = run([str(python), '-m', 'ai_router.key_prompt', '--stdin',
                  '--clients', clients], input=url + '\n',
                 capture_output=True, text=True, timeout=900, cwd=release,
                 env=dict(environment(resources), ROUTER_HOME=str(home)))
    if result.returncode in (1, 2):
        return result.returncode
    if result.returncode != 0:
        raise ValueError('The key window could not finish. Open SCG Router to try again.')
    return _complete_choices(resources, home)


def _claude_on_openrouter(home, dialog):
    """Switch Claude asks before restarting; an existing OpenRouter connection is unchanged."""
    owner = load('claude_desktop_switch')
    try:
        if owner.switch(home, target='3p') == '3p':
            return True
        dialog.message('Claude stays on your Claude subscription. To use OpenRouter models, '
                       'choose Claude, then OpenRouter, in the SCG Router menu.')
    except Exception as exc:
        dialog.message(str(exc) if isinstance(exc, owner.SwitchError)
                       else 'Claude could not be switched safely. Try again.')
    return False


def _check(resources, home, dialog):
    facts = status(resources, home)
    if not facts.get('serving'):
        dialog.message('SCG Router needs repair. Open it again and choose Update or repair.', home=home)
        return
    update = facts.get('update', {})
    if update.get('retry_pending'):
        dialog.message('SCG Router is running. The last update check could not finish. '
                       'Updates will retry automatically.', home=home)
        return
    if update.get('required_action'):
        dialog.message('SCG Router is running, but updates need attention.\n\n'
            'Running version: %s\nLatest known for this channel: %s\nLast successful check: %s\n\n'
            'Choose Update or repair to continue.' % (facts.get('running_version') or 'Unknown',
            update.get('latest_known_version') or 'Unknown',
            load('update_status').display_time(update.get('last_successful_check_at'))), home=home)
        return
    if facts.get('service_key_usable') is False:
        if dialog.confirm_result('Model access needs setup.\n\n'
                'Sign in with your work account or enter your own key in the secure window.',
                home, labels=('Set up access', 'Cancel')) is True:
            _key(resources, home, replace=True)
        return
    if not facts['onboarding'].get('choices_applied', True):
        _complete_choices(resources, home)
        facts = status(resources, home)
    pending = facts['onboarding']['clients']
    if facts['onboarding'].get('ready'):
        dialog.message('Ready. Your assistants are connected and updates are automatic.', home=home)
        return
    if dialog.confirm_result('SCG Router is running. Setup is not finished.\n\n'
            'Finish setup now? You may need to restart your assistants and send a test message.',
            home, labels=('Finish setup', 'Cancel')) is not True:
        return
    if 'claude-desktop' in pending and _missing_assistant(
            ['--clients', 'none', '--desktop'], dialog):
        return
    if not pending or any(not row['plugins_available'] for row in pending.values()):
        dialog.message('Your assistant tools still need setup. Open SCG Router and choose Update or repair.', home=home)
        return
    progress = read_json(Path(home) / 'setup-progress.json')
    for client, checks in pending.items():
        if checks['fresh_session_confirmed'] and checks['reply_seen']:
            continue
        label = {'codex': 'Codex', 'claude': 'Claude Code',
                 'claude-desktop': 'Claude desktop'}[client]
        if client == 'claude-desktop' and not _claude_on_openrouter(home, dialog):
            return
        if not dialog.confirm(
                'To finish setup for %s:\n\n%s'
                'Choose an OpenRouter model and send a greeting. Use an enabled SC tool, '
                'such as SC documentation.\n\n'
                'Choose Continue only after you receive a reply and the SC tool works.'
                % (label, 'Choose Code and start a new task. ' if client == 'claude-desktop'
                   else 'Quit and reopen it, then start a new chat. '), home=home):
            return
        if not load('native_readiness').successful_reply(home, progress['started'], client):
            dialog.message('A successful reply has not reached SCG Router yet. '
                           'Check your selected model, then open SCG Router and choose Check setup.', home=home)
            return
        confirmed = progress.setdefault('confirmed_clients', [])
        if client not in confirmed:
            confirmed.append(client)
        load('atomic_write').replace_json(Path(home) / 'setup-progress.json', progress)
    facts = status(resources, home)
    dialog.message('Ready. Your assistants are connected and updates are automatic.'
                   if facts['onboarding']['ready'] else
                   'Setup is saved. Open SCG Router and choose Check setup to finish.', home=home)


def _remove(resources, home, dialog, doc):
    try:  # Before anything closes: removal refuses while Codex is switched.
        load('codex_switch_config').refuse_switched(home)
    except SystemExit as exc:
        dialog.message(str(exc))
        return 0
    if not dialog.confirm('Remove SCG Router and restore your assistant settings? '
                          'Your key and saved settings will stay on this computer.'):
        return 0
    clients = load('codex_config').read_receipt(home).get('clients', {})
    if not load('repair_ui').close_assistants(home, removing=True):
        return 0
    python = resources / 'runtime' / doc['runtime_exec']
    source = load('native_controller').launcher_source(home, resources / 'router')
    with dialog.Progress('Removing SCG Router. If an update is running, removal waits for it '
                         'to finish. A message appears when removal is done.', button='OK'):
        result = subprocess.run([str(python), str(source / 'packaging/install.py'), '--home', str(home),
                                 '--uninstall'], capture_output=True, text=True, timeout=600,
                                env=environment(resources))
    if 'deferred:' in (result.stdout or ''):
        dialog.message('SCG Router is still updating, so nothing was removed. '
                       'Try again in a few minutes.')
        return 1
    if not _succeeded(result):
        dialog.message('SCG Router could not be removed safely. Contact Software Combined IT.')
        return result.returncode or 1
    reopen = [label for name, label in (('codex', 'Codex'), ('claude', 'Claude Code')) if name in clients]
    finish = ' Quit and reopen %s to finish.' % ' and '.join(reopen) if reopen else ''
    dialog.message('SCG Router was removed.%s\n\nYour model key and settings stay in %s, so setting '
                   'up SCG Router again keeps them. Delete that folder to remove them.' % (finish, home))
    return 0


def onboard(resources, home, action=None):
    dialog = load('native_dialog')
    existing = (home / 'current').exists() or (home / 'current').is_symlink()
    action = action or (dialog.choose('What would you like to do?', ACTIONS) if existing else 'resume')
    if action is None:
        return 0
    if action == 'signin':
        dialog.message('SCG Router downloads are public. No download sign-in is needed.')
        return 0
    if action == 'status':
        _check(resources, home, dialog)
        return 0
    if action == 'key':
        return 1 if _key(resources, home, replace=True) == 1 else 0
    doc = metadata(resources)
    if action == 'remove':
        return _remove(resources, home, dialog, doc)
    package_install = action == 'install'
    if package_install and read_json(home / 'mixed-router-state.json'):
        flags = ['--install-package']
    elif not existing or action == 'add':
        flags = _select(dialog)
    else:
        flags = ['--repair']
    if flags is None or ('--clients' in flags and _missing_assistant(flags, dialog)):
        return 0
    restart = load('setup_restart')
    codex_config_before = restart.target(home) if sys.platform == 'win32' else None
    codex_was_running = False
    selected_clients = flags[flags.index('--clients') + 1] if '--clients' in flags else None
    includes_codex = selected_clients in ('codex', 'both')
    if selected_clients is None:
        try:
            attached = load('codex_config').read_receipt(home).get('clients', {})
            saved = read_json(home / 'mixed-router-state.json')
            clients = saved.get('clients')
            if clients not in ('codex', 'claude', 'both', 'none'):
                clients = 'none' if saved.get('client') == 'none' else 'codex'
            includes_codex = 'codex' in attached if attached else clients in ('codex', 'both')
        except (OSError, ValueError):
            includes_codex = False
    if sys.platform == 'win32' and includes_codex:
        try:
            codex_was_running = load('claude_desktop_platform').is_running(
                'win32', app=load('codex_desktop_switch').CODEX)
        except (OSError, subprocess.SubprocessError):
            pass
    with dialog.Progress(home=home) as progress:
        permanent = retained(resources, home)
        python = permanent / 'runtime' / doc['runtime_exec']
        if sys.platform != 'win32':
            load('native_shortcuts').install(home, permanent, python)
        result = run_installer(permanent, home, flags)
    if not _succeeded(result):
        dialog.message('Setup could not finish. '
                       'Open SCG Router to try again, or contact Software Combined IT.')
        return 1
    record_channel(permanent, home, existing=existing, package=package_install)
    try:
        permanent = load('native_resources').current(home)
        doc = metadata(permanent)
    except (OSError, ValueError, KeyError):
        pass
    source = permanent / 'router'
    if sys.platform != 'win32':
        load('native_controller').install(home, source)
    python = permanent / 'runtime' / doc['runtime_exec']
    if sys.platform != 'win32':
        load('native_shortcuts').install(home, permanent, python)
        load('native_resources').confirm_controls(home, permanent)
    load('desktop_menu').start(home, permanent)
    atomic = load('atomic_write')
    if not package_install or read_json(home / 'setup-progress.json').get('version') != doc['version']:
        atomic.replace_json(home / 'setup-progress.json',
                            {'version': doc['version'], 'started': time.time(), 'confirmed_clients': []})
    if progress.cancelled:
        return 0
    key_result = _key(permanent, home)
    if key_result in (1, 2):
        return 1 if key_result == 1 else 0
    if restart.offer(home, codex_config_before, codex_was_running):
        return 0
    _check(permanent, home, dialog)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--home', type=Path, default=Path.home() / '.codex/mixed-model-router')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--action', choices=['install', *[key for key, _ in ACTIONS]])
    args = parser.parse_args(argv)
    resources = args.resources.resolve()
    try:
        if args.home.expanduser().is_symlink():
            raise ValueError('The setup folder is not safe to use.')
        args.home = args.home.expanduser().resolve()
        metadata(resources)
        os.environ.update(environment(resources))
        if args.status:
            print(json.dumps(status(resources, args.home)))
            return 0
        return onboard(resources, args.home, args.action)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        if args.status:
            return 1
        load('native_dialog').message('Setup needs attention. Open SCG Router to try again, '
                                      'or contact Software Combined IT.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
