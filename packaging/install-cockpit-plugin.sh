#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SOURCE="$REPO_ROOT/cockpit/codepc-link"
DESTINATION="${DESTDIR:-}/usr/share/cockpit/codepc-link"

if [ ! -d "$SOURCE" ]; then
    echo "Cockpit source package not found: $SOURCE" >&2
    exit 1
fi

install -d -m 0755 "$DESTINATION"
install -m 0644 "$SOURCE/manifest.json" "$DESTINATION/manifest.json"
install -m 0644 "$SOURCE/index.html" "$DESTINATION/index.html"
install -m 0644 "$SOURCE/app.js" "$DESTINATION/app.js"
install -m 0644 "$SOURCE/styles.css" "$DESTINATION/styles.css"

echo "Installed CodePC Link Cockpit package in $DESTINATION"
echo "Reload Cockpit in the browser. The CodePC Link item should appear in the menu."
