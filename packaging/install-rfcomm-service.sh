#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE="$SCRIPT_DIR/systemd/codepc-link-rfcomm.service"
DESTINATION="${DESTDIR:-}/etc/systemd/system/codepc-link-rfcomm.service"

install -D -m 0644 "$SOURCE" "$DESTINATION"

if [ -z "${DESTDIR:-}" ]; then
    python3 -m venv /opt/codepc-link/venv
    /opt/codepc-link/venv/bin/python -m pip install --upgrade "$REPO_ROOT"
    install -d -m 0755 /usr/local/bin
    ln -sfn /opt/codepc-link/venv/bin/codepc-link /usr/local/bin/codepc-link
    ln -sfn /opt/codepc-link/venv/bin/codepc-link-bt /usr/local/bin/codepc-link-bt
    systemctl daemon-reload
fi

echo "Installed CodePC Link RFCOMM service in $DESTINATION"
if [ -z "${DESTDIR:-}" ]; then
    echo "Installed the isolated server runtime in /opt/codepc-link/venv"
fi
echo "Use the Cockpit Keep RFCOMM server alive checkbox to enable and start it."
