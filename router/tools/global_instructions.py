"""Legacy global-instructions shim: the router writes no global instructions.

Setup, updates and uninstall never touch global instructions.
These names survive so old releases and tests importing this module keep
working: prepare reports nothing to do, write changes nothing, restore is
a no-op, and BLOCK stays for receipt-compat reads only.
"""
from pathlib import Path

BEGIN = '<!-- BEGIN ai-router subagent rules -->'
END = '<!-- END ai-router subagent rules -->'
# Kept so old receipts referencing a block still resolve; new installs
# never insert it.
BLOCK = ''


def prepare(codex_home, previous=None):
    """Nothing to install; the path stays only for legacy receipt-compat reads.

    Frozen shim: the override rule here must not evolve.
    """
    override = Path(codex_home) / 'AGENTS.override.md'
    path = (override if override.exists() and override.read_text().strip()
            else Path(codex_home) / 'AGENTS.md').resolve()
    before = path.read_text() if path.exists() else ''
    return path, before, before, {'path': str(path), 'block': ''}


def write(path, before, after):
    """No-op: the installer leaves global instructions unchanged."""
    return None


def restore(receipt):
    """No-op: uninstall leaves the owner's global instructions alone."""
    return None
