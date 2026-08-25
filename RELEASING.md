# Releasing CodePC Link

GitHub Releases are tag-driven.

## Versioning

Use semantic version tags:

```text
v0.1.0
v0.2.0
v0.2.1
```

Pre-1.0 releases may change rapidly, but protocol/schema compatibility must still be documented.

## Release procedure

1. Ensure CI is green on `main`.
2. Complete the applicable release checklist in `docs/COMPLICATIONS_CHECKLIST.md`.
3. Update `CHANGELOG.md`.
4. Confirm documentation matches the implementation.
5. Create and push an annotated or lightweight tag matching `v*.*.*`.

Example:

```bash
git checkout main
git pull --ff-only
git tag v0.1.0
git push origin v0.1.0
```

The `Release` GitHub Actions workflow creates the GitHub Release and generated release notes.

## v0.1 release gate

Do not tag v0.1 until BLE hardware compatibility, schema/UUID stability, pairing/privacy policy, payload-size testing, BlueZ recovery, HTTPS PWA behavior, and target-hardware integration tests are complete.

## Release artifacts

Until native packages exist, GitHub automatically provides source archives. Distribution packages can be attached in a later release workflow when packaging is implemented.
