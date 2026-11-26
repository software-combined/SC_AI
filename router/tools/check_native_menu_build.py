"""Compile this runner's native menu and check its native desktop protocol."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging/native'))
import native_menu_build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        resources = Path(temporary)
        (resources / 'installer.json').write_text(json.dumps(dict(target=args.target)))
        helper = native_menu_build.build(resources, args.target)
        print('Native helper compiled: ' + helper.name)
        if args.target.startswith('linux/'):
            subprocess.run(['dbus-run-session', '--', 'cargo', '+1.90.0', 'test', '--locked',
                '--manifest-path', str(native_menu_build.HERE / 'linux/Cargo.toml'),
                '--target-dir', str(resources / 'tests'), '--', '--ignored'], check=True)
        if args.target == 'windows/arm64':
            env = dict(os.environ, SCG_TEST_NATIVE_MENU_HELPER=str(helper))
            subprocess.run([sys.executable, '-m', 'unittest',
                'tests.test_windows_native_lifecycle.WindowsNativeLifecycleTests.'
                'test_compiled_progress_protocol_closes_when_its_parent_pipe_closes'],
                cwd=Path(__file__).resolve().parents[1], env=env, check=True)


if __name__ == '__main__':
    main()
