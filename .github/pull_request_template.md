## Summary

Describe the change and why it is needed.

## Scope

- [ ] Focused change; unrelated work is excluded
- [ ] Protocol/schema compatibility considered
- [ ] Security/privacy impact considered

## Validation

- [ ] `ruff check src tests`
- [ ] `pytest`
- [ ] Documentation updated where needed

## BLE / networking checklist (when applicable)

- [ ] Wi-Fi + Ethernet multi-homing considered
- [ ] Link/IP/default-route/Internet states remain distinct
- [ ] No secrets or credentials are exposed in status/logs
- [ ] No privileged BLE write path was added without the security foundation
