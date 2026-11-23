"""Installer-side name for the shared atomic writer (Plan 131).

The leaf lives in ai_router/atomic_write.py so the runtime and the installer
share one contract; this file keeps the Plan 123 file-based load path
(`service.load('router_atomic_write', ...)`) working. Python 3.9-safe.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loader  # noqa: E402
_mod = loader.load(Path(__file__).resolve().parents[1] / 'ai_router' / 'atomic_write.py')

replace_text = _mod.replace_text
replace_bytes = _mod.replace_bytes
replace_json = _mod.replace_json
StaleTmp = _mod.StaleTmp
ConcurrentChange = _mod.ConcurrentChange
check_unchanged = _mod.check_unchanged
remove = _mod.remove
