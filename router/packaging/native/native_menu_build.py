"""Compile the thin menu shell on its native release runner."""
import os
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'menu'


def build(resources, target, run=subprocess.run):
    resources = Path(resources)
    cpu = {'aarch64': 'arm64', 'amd64': 'x86_64'}.get(platform.machine().lower(), platform.machine().lower())
    system = {'darwin': 'darwin', 'win32': 'windows', 'linux': 'linux'}.get(sys.platform)
    if system == 'windows':
        cpu = {'win-amd64': 'x86_64', 'win-arm64': 'arm64'}.get(sysconfig.get_platform(), '')
    if target != str(system) + '/' + cpu:
        raise ValueError('Menu helper requires its matching native build runner')
    directory = resources / 'control'
    directory.mkdir(exist_ok=True)
    binary = directory / ('scg-router-menu.exe' if target.startswith('windows/') else 'scg-router-menu')
    if target.startswith('darwin/'):
        run(['xcrun', 'swiftc', '-O', str(HERE / 'mac.swift'), '-o', str(binary)], check=True)
    elif target == 'windows/x86_64':
        compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/out:' + str(binary),
             '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', '/r:System.Web.Extensions.dll',
             str(HERE / 'windows.cs'), str(HERE / 'windows_repeat.cs')], check=True)
    elif target == 'windows/arm64':
        with tempfile.TemporaryDirectory(prefix='scg-menu-build-') as temporary:
            run(['dotnet', 'publish', str(HERE / 'windows-arm64.csproj'), '-c', 'Release',
                 '-o', temporary, '--artifacts-path', str(Path(temporary) / 'artifacts'),
                 '-p:RestorePackagesPath=' + str(Path(temporary) / 'packages')], check=True)
            shutil.copyfile(Path(temporary) / 'scg-router-menu.exe', binary)
            notices = directory / 'dotnet-notices'
            notices.mkdir()
            packages = Path(temporary) / 'packages'
            for package, names in (('microsoft.netcore.app.runtime.win-arm64',
                                    ('LICENSE.TXT', 'THIRD-PARTY-NOTICES.TXT')),
                                   ('microsoft.windowsdesktop.app.runtime.win-arm64', ('LICENSE',))):
                versions = list((packages / package).iterdir())
                if len(versions) != 1:
                    raise ValueError('Unable to locate .NET runtime notices')
                for name in names:
                    shutil.copyfile(versions[0] / name, notices / (package + '-' + name))
    elif target.startswith('linux/'):
        with tempfile.TemporaryDirectory(prefix='scg-menu-build-') as temporary:
            run(['cargo', '+1.90.0', 'build', '--release', '--locked', '--manifest-path',
                 str(HERE / 'linux/Cargo.toml'), '--target-dir', temporary], check=True)
            shutil.copyfile(Path(temporary) / 'release/scg-router-menu', binary)
            binary.chmod(0o755)
        # A release receipt retains the actual native dependency closure.
        result = run(['ldd', str(binary)], capture_output=True, text=True, check=True)
        if 'not found' in result.stdout:
            raise ValueError('The Linux menu helper has unresolved dependencies')
        (directory / 'linux-dependencies.txt').write_text(result.stdout)
    else:
        raise ValueError('Menu helper requires its native build runner')
    if not binary.is_file():
        raise ValueError('Native menu compiler produced no helper')
    if target.startswith('windows/'):
        data = binary.read_bytes()
        offset = int.from_bytes(data[60:64], 'little')
        machine = {'x86_64': 0x8664, 'arm64': 0xaa64}[target.split('/')[1]]
        if data[:2] != b'MZ' or data[offset:offset + 4] != b'PE\0\0' or (
                int.from_bytes(data[offset + 4:offset + 6], 'little') != machine):
            raise ValueError('Native menu helper architecture does not match target')
    shutil.copyfile(HERE / 'linux/NOTICES.txt', directory / 'THIRD_PARTY_NOTICES.txt')
    shutil.copytree(HERE / 'linux/rust', directory / 'rust-notices')
    path = resources / 'installer.json'
    doc = json.loads(path.read_text())
    doc['menu_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    path.write_text(json.dumps(doc, indent=2) + '\n')
    return binary
