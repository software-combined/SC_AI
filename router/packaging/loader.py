"""One cached file loader for installer modules. Runs on Python 3.9+.

A third-party distribution owns the import name `packaging`, so these modules
load sibling files by path. `load` executes each file once per process and
returns the same module for the same resolved path, so every caller shares its
classes, globals and test seams. Importers put this directory on `sys.path`
and import this module by name, which keeps one loader per process.
Tests that need fresh modules call `reset`.
"""
import importlib.util
import threading
from pathlib import Path

_modules = {}
_lock = threading.RLock()


def load(path, name=None):
    """Return the one module for `path`, executing the file on first use.

    The resolved path is the key; the first caller's spelling stays `__file__`.
    """
    key = Path(path).resolve()
    with _lock:
        module = _modules.get(key)
        if module is None:
            spec = importlib.util.spec_from_file_location(name or 'router_' + key.stem, path)
            module = importlib.util.module_from_spec(spec)
            _modules[key] = module
            try:
                spec.loader.exec_module(module)
            except BaseException:
                _modules.pop(key, None)
                raise
        return module


def reset():
    """Forget every module; the next load of a file executes it again."""
    with _lock:
        _modules.clear()
