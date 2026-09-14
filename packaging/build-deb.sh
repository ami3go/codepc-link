#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VERSION=${1:-0.1.0~debug1}
OUTPUT_DIR=${2:-"$REPO_ROOT/dist"}

case "$VERSION" in
    ""|*[!0-9A-Za-z.+:~-]*)
        echo "Invalid Debian version: $VERSION" >&2
        exit 2
        ;;
esac

STAGING_DIR=$(mktemp -d)
trap 'rm -rf "$STAGING_DIR"' EXIT HUP INT TERM

install -d -m 0755 \
    "$STAGING_DIR/DEBIAN" \
    "$STAGING_DIR/usr/bin" \
    "$STAGING_DIR/usr/lib/python3/dist-packages/codepc_link" \
    "$STAGING_DIR/usr/share/cockpit/codepc-link" \
    "$STAGING_DIR/usr/share/doc/codepc-link" \
    "$STAGING_DIR/lib/systemd/system" \
    "$OUTPUT_DIR"

install -m 0755 \
    "$SCRIPT_DIR/debian/postinst" \
    "$SCRIPT_DIR/debian/prerm" \
    "$SCRIPT_DIR/debian/postrm" \
    "$STAGING_DIR/DEBIAN/"
install -m 0644 "$SCRIPT_DIR/debian/copyright" \
    "$STAGING_DIR/usr/share/doc/codepc-link/copyright"

install -m 0755 \
    "$SCRIPT_DIR/bin/codepc-link" \
    "$SCRIPT_DIR/bin/codepc-link-bt" \
    "$STAGING_DIR/usr/bin/"
find "$REPO_ROOT/src/codepc_link" -maxdepth 1 -type f -name '*.py' \
    -exec install -m 0644 {} "$STAGING_DIR/usr/lib/python3/dist-packages/codepc_link/" \;
install -m 0644 "$REPO_ROOT/cockpit/codepc-link/"* \
    "$STAGING_DIR/usr/share/cockpit/codepc-link/"
install -m 0644 "$SCRIPT_DIR/systemd/codepc-link-rfcomm.service" \
    "$STAGING_DIR/lib/systemd/system/codepc-link-rfcomm.service"
install -m 0644 \
    "$REPO_ROOT/README.md" \
    "$REPO_ROOT/docs/ANDROID_RFCOMM.md" \
    "$REPO_ROOT/docs/ANDROID_RFCOMM_PAIRING.md" \
    "$STAGING_DIR/usr/share/doc/codepc-link/"

# mktemp intentionally creates a private root and install creates intermediate
# directories using the caller's umask. Normalize all packaged directories so
# installing the archive cannot tighten / or leave group-writable system paths.
find "$STAGING_DIR" -type d -exec chmod 0755 {} +
INSTALLED_SIZE=$(du -sk "$STAGING_DIR/usr" "$STAGING_DIR/lib" | awk '{ total += $1 } END { print total }')
sed \
    -e "s/@VERSION@/$VERSION/g" \
    -e "s/@INSTALLED_SIZE@/$INSTALLED_SIZE/g" \
    "$SCRIPT_DIR/debian/control.in" >"$STAGING_DIR/DEBIAN/control"

PACKAGE_FILE_VERSION=$(printf '%s' "$VERSION" | tr '~' '.')
PACKAGE_PATH="$OUTPUT_DIR/codepc-link_${PACKAGE_FILE_VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$STAGING_DIR" "$PACKAGE_PATH"
echo "$PACKAGE_PATH"
