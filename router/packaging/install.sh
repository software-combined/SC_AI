#!/bin/sh
# Thin wrapper: the installer lives in install.py (Plan 041) and needs Python 3.14.
set -eu
PYTHON=python3.14
# install.py refuses an older python3 with a clear message.
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3
exec "$PYTHON" "$(dirname "$0")/install.py" "$@"
