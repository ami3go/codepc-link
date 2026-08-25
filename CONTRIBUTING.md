# Contributing to CodePC Link

Thanks for helping improve CodePC Link.

## Before you start

- Use an issue for bugs, feature proposals, protocol changes, and security-sensitive design discussions.
- Keep v0.1 read-only over BLE. Privileged BLE writes are intentionally deferred until the security foundation is complete.
- Avoid duplicating Cockpit features that already exist in Networking, Services, or Logs.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
ruff check src tests
pytest
```

## Pull requests

1. Keep each PR focused.
2. Add or update tests for behavior changes.
3. Update documentation when interfaces, protocol fields, or setup steps change.
4. Do not change committed BLE UUIDs or schema semantics incompatibly after release.
5. Never add secrets, Wi-Fi passwords, tokens, or private host data to tests or logs.

## Commit style

Conventional-style prefixes are encouraged: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`.

## Definition of done

A task is complete only when its implementation, acceptance criteria, tests, and documentation impact are addressed.
