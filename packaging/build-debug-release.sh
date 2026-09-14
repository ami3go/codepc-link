#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
RELEASE_NAME=${RELEASE_NAME:-0.1.0-debug.1}
DEBIAN_VERSION=${DEBIAN_VERSION:-0.1.0~debug1}
OUTPUT_DIR=${OUTPUT_DIR:-"$REPO_ROOT/dist/$RELEASE_NAME"}
GRADLE_BIN=${GRADLE_BIN:-gradle}

install -d -m 0755 "$OUTPUT_DIR"
"$GRADLE_BIN" -p "$REPO_ROOT/android" :app:assembleDebug
install -m 0644 \
    "$REPO_ROOT/android/app/build/outputs/apk/debug/app-debug.apk" \
    "$OUTPUT_DIR/codepc-link-android-$RELEASE_NAME.apk"
"$SCRIPT_DIR/build-deb.sh" "$DEBIAN_VERSION" "$OUTPUT_DIR"

cd "$OUTPUT_DIR"
sha256sum ./*.apk ./*.deb >SHA256SUMS
chmod 0644 SHA256SUMS
printf 'Release artifacts:\n'
printf '  %s\n' "$OUTPUT_DIR"/*
