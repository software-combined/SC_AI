"""Path scope for the expensive CI checks (Plan 156).

Usage:
  git diff --name-only BASE HEAD | python tools/ci_scope.py --installer
  python tools/ci_scope.py --installer-tests [SHARD]

`--installer` prints `installer=true|false`, whether a pull request can reach
the installer, its platform backends or its tests. Only then do the macOS and
Windows runners run. `--installer-tests` prints the module list those runners
execute, so the workflows and this file have one owner instead of two copies.

Every file the installer loads or runs outside `packaging/` is listed too, so a
change to `ai_router/winacl.py` or `tools/disable.py` cannot skip the native
checks.
"""
import os
import sys

INSTALLER_PATHS = (
    'packaging/',
    '.github/actions/setup/',
    '.github/workflows/check.yml',
    '.github/workflows/release.yml',
    'tests/_platform.py',
    'tests/fakes.py',
    'tests/harness.py',
    'tests/install_fixtures.py',
    'tests/loading.py',
    'tests/windows_native_fixture.py',
    'tests/test_windows_migration_native.py',
    'tests/windows_shutdown_fixture.py',
    'tests/test_bootstrap.py',
    'tests/test_bootstrap_interpreter.py',
    'tests/test_claude_attachment_path.py',
    'tests/test_ci_scope.py',
    'tests/test_client_dialog.py',
    'tests/test_client_choice.py',
    'tests/test_codex_owned.py',
    'tests/test_codex_lossless.py',
    'tests/test_codex_one_choice.py',
    'tests/test_codex_one_choice_update.py',
    'tests/test_attachment_classification.py',
    'tests/test_attachment_recovery.py',
    'tests/test_attachment_notices.py',
    'tests/test_winsecurity.py',
    'tests/test_owned_json.py',
    'tests/test_removal_recovery.py',
    'tests/test_native_setup.py',
    'tests/test_native_readiness.py',
    'tests/test_native_access.py',
    'tests/test_model_access_flow.py',
    'tests/test_codex_subscription_defaults.py',
    'tests/test_setup_completion.py',
    'tests/test_private_updates.py',
    'tests/test_linux_dialog_delivery.py',
    'tests/claude_profile_sync_fixtures.py',
    'tests/test_claude_desktop_policy.py',
    'tests/test_claude_desktop_config.py',
    'tests/test_claude_desktop_setup.py',
    'tests/test_claude_desktop_switch.py',
    'tests/test_claude_profile_launch.py',
    'tests/test_popup_style.py',
    'tests/test_claude_desktop_platform.py',
    'tests/test_claude_profile_hook.py',
    'tests/test_claude_profile_identity.py',
    'tests/test_claude_account_recovery.py',
    'tests/test_claude_profile_rotation.py',
    'tests/test_claude_rotation_lifecycle.py',
    'tests/test_claude_account_switch.py',
    'tests/test_claude_account_reopen.py',
    'tests/test_claude_first_gateway.py',
    'tests/test_claude_rotation_app_guard.py',
    'tests/test_claude_retention_acl.py',
    'tests/test_claude_current_account_history.py',
    'tests/test_claude_removal_guards.py',
    'tests/test_claude_profile_records.py',
    'tests/test_claude_profile_publish.py',
    'tests/test_claude_profile_recovery.py',
    'tests/test_claude_profile_ledger.py',
    'tests/test_claude_profile_sync_deletions.py',
    'tests/test_claude_profile_history.py',
    'tests/test_claude_profile_bundle.py',
    'tests/test_claude_profile_sync.py',
    'tests/test_claude_profile_sync_safety.py',
    'tests/test_claude_profile_native_layout.py',
    'tests/test_claude_profile_transcript_capture.py',
    'tests/test_claude_profile_account_scope.py',
    'tests/test_claude_profile_binding.py',
    'tests/test_claude_profile_rules.py',
    'tests/test_claude_profile_faithful_copy.py',
    'tests/test_claude_profile_org_scope.py',
    'tests/test_claude_switch_recovery.py',
    'tests/test_claude_profile_workspace_names.py',
    'tests/test_claude_profile_repair_resume.py',
    'tests/test_claude_desktop_upgrade_paths.py',
    'tests/test_install',
    'tests/test_interpreter_resolution.py',
    'tests/test_key_prompt.py',
    'tests/test_launchd',
    'tests/test_local_services.py',
    'tests/test_maintenance_recovery.py',
    'tests/test_notice',
    'tests/test_packaging.py',
    'tests/test_platform_dispatch_order.py',
    'tests/test_systemd',
    'tests/test_update_announce.py',
    'tests/test_update_channel.py',
    'tests/test_update_status.py',
    'tests/test_update_retry.py',
    'tests/test_update_warning.py',
    'tests/test_update_cache_recovery.py',
    'tests/test_public_repair.py',
    'tests/test_router_scheduler_native.py',
    'tests/test_router_warning_native.py',
    'tests/test_windows_',
    'ai_router/key_dialog.py',
    'ai_router/key_prompt.py',
    # Router files the installer loads or runs.
    'ai_router/atomic_write.py',
    'ai_router/dialog_tool.py',
    'ai_router/provider_defs.py',
    'ai_router/retired_slugs.py',
    'ai_router/state.py',
    'ai_router/subscription_roster.py',
    'ai_router/clients/roster.py',
    'ai_router/winacl.py',
    'ai_router/winsecurity.py',
    'tools/classify_attachments.py',
    'tools/disable.py',
    'tools/global_instructions.py',
    'tools/ci_scope.py',
    'tools/verify_runtime_pins.py',
    'tools/run_windows_standard.ps1',
    'tools/windows_standard.py',
)

TASK_OWNERSHIP = 'tests.test_windows_task_ownership'
TASK_MIGRATION = 'tests.test_windows_migration_native'

INSTALLER_TESTS = (
    'tests.test_update_status',
    'tests.test_update_retry',
    'tests.test_update_warning',
    'tests.test_update_cache_recovery',
    'tests.test_public_repair',
    'tests.test_router_scheduler_native',
    'tests.test_router_warning_native',
    'tests.test_codex_owned',
    'tests.test_codex_lossless',
    'tests.test_codex_one_choice',
    'tests.test_codex_one_choice_update',
    'tests.test_attachment_classification',
    'tests.test_attachment_recovery',
    'tests.test_attachment_notices',
    'tests.test_winsecurity',
    'tests.test_owned_json',
    'tests.test_removal_recovery',
    'tests.test_install',
    'tests.test_install_catalogue',
    'tests.test_install_config',
    'tests.test_install_owner_keys',
    'tests.test_install_key_window',
    'tests.test_install_lifecycle',
    'tests.test_install_state',
    'tests.test_install_client_retention',
    'tests.test_bootstrap',
    'tests.test_bootstrap_interpreter',
    'tests.test_claude_attachment_path',
    'tests.test_ci_scope',
    'tests.test_client_dialog',
    'tests.test_client_choice',
    'tests.test_setup_completion',
    'tests.test_native_setup',
    'tests.test_native_readiness',
    'tests.test_native_access',
    'tests.test_model_access_flow',
    'tests.test_codex_subscription_defaults',
    'tests.test_native_resources',
    'tests.test_native_resources_publish',
    'tests.test_desktop_delivery',
    'tests.test_desktop_controls',
    'tests.test_desktop_recovery',
    'tests.test_windows_lifecycle',
    'tests.test_installation_evidence',
    'tests.test_menu_installation_evidence',
    'tests.test_desktop_targets',
    'tests.test_desktop_management',
    'tests.test_desktop_platform_contracts',
    'tests.test_desktop_profile_transition',
    'tests.test_native_menu_build',
    'tests.test_private_updates',
    'tests.test_linux_dialog_delivery',
    'tests.test_claude_desktop_policy',
    'tests.test_claude_desktop_config',
    'tests.test_claude_desktop_setup',
    'tests.test_claude_desktop_switch',
    'tests.test_claude_profile_launch',
    'tests.test_popup_style',
    'tests.test_claude_desktop_platform',
    'tests.test_claude_account_recovery',
    'tests.test_claude_profile_rotation',
    'tests.test_claude_rotation_lifecycle',
    'tests.test_claude_account_switch',
    'tests.test_claude_account_reopen',
    'tests.test_claude_first_gateway',
    'tests.test_claude_rotation_app_guard',
    'tests.test_claude_retention_acl',
    'tests.test_claude_current_account_history',
    'tests.test_claude_removal_guards',
    'tests.test_windows_native',
    'tests.test_windows_codex',
    'tests.test_windows_dialog',
    'tests.test_windows_shell',
    'tests.test_windows_switch_transaction',
    'tests.test_windows_native_lifecycle',
    'tests.test_windows_process_generation',
    'tests.test_windows_shutdown_race',
    'tests.test_windows_update_policy',
    'tests.test_windows_process_snapshot',
    'tests.test_windows_switch_contention',
    'tests.test_windows_cli_resolution',
    'tests.test_windows_client_discovery',
    'tests.test_claude_profile_hook',
    'tests.test_claude_profile_identity',
    'tests.test_claude_profile_records',
    'tests.test_claude_profile_publish',
    'tests.test_claude_profile_recovery',
    'tests.test_claude_profile_ledger',
    'tests.test_claude_profile_sync_deletions',
    'tests.test_claude_profile_history',
    'tests.test_claude_profile_bundle',
    'tests.test_claude_profile_sync',
    'tests.test_claude_profile_sync_safety',
    'tests.test_claude_profile_native_layout',
    'tests.test_claude_profile_transcript_capture',
    'tests.test_claude_profile_account_scope',
    'tests.test_claude_profile_binding',
    'tests.test_claude_profile_rules',
    'tests.test_claude_profile_faithful_copy',
    'tests.test_claude_profile_org_scope',
    'tests.test_claude_switch_recovery',
    'tests.test_claude_profile_workspace_names',
    'tests.test_claude_profile_repair_resume',
    'tests.test_claude_desktop_upgrade_paths',
    'tests.test_interpreter_resolution',
    'tests.test_key_prompt',
    'tests.test_launchd',
    'tests.test_launchd_guard',
    'tests.test_local_services',
    'tests.test_maintenance_recovery',
    'tests.test_notice',
    'tests.test_notice_delivery',
    'tests.test_packaging',
    'tests.test_platform_dispatch_order',
    'tests.test_systemd',
    'tests.test_systemd_recovery',
    'tests.test_systemd_runtime',
    'tests.test_update_announce',
    'tests.test_update_channel',
    'tests.test_windows_acl',
    'tests.test_windows_acl_native',
    'tests.test_windows_permission_recovery',
    'tests.test_windows_desktop_regressions',
    'tests.test_windows_agent_skills',
    'tests.test_windows_backend',
    'tests.test_windows_runtime_rebind',
    'tests.test_windows_native_fixture',
    TASK_OWNERSHIP,
    TASK_MIGRATION,
    'tests.test_windows_task_diagnostics',
    'tests.test_windows_task_cohort',
    'tests.test_windows_installation',
    'tests.test_windows_shortcut_recovery',
    'tests.test_windows_task_state',
    'tests.test_windows_task_migration',
    'tests.test_windows_portability',
)


# Legacy fixtures encode Mac app paths and POSIX permissions. Keep them on the
# Mac job; desktop_profile_transition and desktop_platform_contracts exercise
# the shared transition, saved-work recovery and shutdown on native runners.
MACOS_ONLY_TESTS = frozenset((
    'tests.test_claude_desktop_switch',
    'tests.test_claude_profile_account_scope',
    'tests.test_claude_profile_bundle',
    'tests.test_claude_profile_faithful_copy',
    'tests.test_claude_profile_history',
    'tests.test_claude_profile_launch',
    'tests.test_claude_profile_ledger',
    'tests.test_claude_profile_native_layout',
    'tests.test_claude_profile_org_scope',
    'tests.test_claude_profile_publish',
    'tests.test_claude_profile_recovery',
    'tests.test_claude_profile_repair_resume',
    'tests.test_claude_profile_rules',
    'tests.test_claude_profile_sync',
    'tests.test_claude_profile_sync_deletions',
    'tests.test_claude_profile_sync_safety',
    'tests.test_claude_profile_transcript_capture',
    'tests.test_claude_profile_workspace_names',
))


ARM_INSTALLER_SHARDS = {
    'ownership': (
        TASK_OWNERSHIP + '.NativeTaskTests.test_registration_restore_and_foreign_identity',
        TASK_OWNERSHIP + '.NativeTaskTests.test_matching_arguments_do_not_own_a_foreign_executable',
        TASK_OWNERSHIP + '.NativeTaskTests.test_deleted_task_keeps_child_and_missing_metadata_cannot_prove_exit',
    ),
    'lifecycle': (TASK_OWNERSHIP + '.NativeTaskTests.test_restart_and_pending_state',),
    'migration': (TASK_MIGRATION + '.NativeMigrationTests.test_migration_recovers_after_the_disabled_parent_exits',),
    'retry': (
        TASK_MIGRATION + '.NativeMigrationTests.test_failed_registration_preserves_running_tasks_and_allows_retry',
    ),
}


def installer_tests(windows=os.name == 'nt', shard='all'):
    modules = [name for name in INSTALLER_TESTS if not (windows and name in MACOS_ONLY_TESTS)]
    if shard == 'all':
        return modules
    if not windows:
        raise ValueError('installer shards require Windows')
    if shard == 'general':
        return [name for name in modules if name not in (TASK_OWNERSHIP, TASK_MIGRATION)] + [
            TASK_OWNERSHIP + '.OwnershipTests', TASK_OWNERSHIP + '.ExplicitStopTests',
        ]
    if shard not in ARM_INSTALLER_SHARDS:
        raise ValueError('unknown installer shard: ' + shard)
    return list(ARM_INSTALLER_SHARDS[shard])


def installer_scope(paths):
    """True when any changed path can affect the installer or its tests."""
    return any(path.removeprefix('router/').startswith(INSTALLER_PATHS) for path in paths)


def main(argv):
    if argv[:1] == ['--installer-tests'] and len(argv) <= 2:
        try:
            names = installer_tests(shard=argv[1] if len(argv) == 2 else 'all')
        except ValueError as error:
            print(error, file=sys.stderr)
            return 2
        print(' '.join(names))
        return 0
    if '--installer' in argv:
        paths = [line.strip() for line in sys.stdin if line.strip()]
        print('installer=%s' % ('true' if installer_scope(paths) else 'false'))
        return 0
    sys.stderr.write(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
