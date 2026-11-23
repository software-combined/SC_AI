"""The one loader tests use for file-based modules (packaging, tools, plugins).

`packaging/` and the plugin scripts are not importable packages, so tests load
them by path. Each call executes the file again and returns a new module, so a
test may patch its own copy without reaching another test's. Packaging modules
share their siblings through `packaging/loader.py`; each call resets that cache
first, so the new module's siblings are new copies too.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path, name=None):
    """Execute `path` (absolute, or relative to router/) as a new module."""
    path = ROOT / path
    if 'loader' in sys.modules:
        sys.modules['loader'].reset()
    spec = importlib.util.spec_from_file_location(name or 'router_test_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
