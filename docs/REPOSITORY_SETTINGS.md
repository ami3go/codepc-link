# Recommended Repository Settings

Repository automation and files are committed in-repo. A few GitHub settings are repository-level controls and should be reviewed in the GitHub UI.

## General

Recommended:

- Repository visibility: **Public**
- Default branch: `main`
- Enable Issues
- Enable Releases
- Enable GitHub Actions
- Prefer squash merges for focused feature/fix PRs
- Automatically delete merged branches if desired

## Branch protection / ruleset

Once the bootstrap is stable, protect `main` with a ruleset that requires:

- pull request before merge for non-maintainer changes
- passing `CI` checks
- branch up to date before merge when practical
- no force pushes
- no branch deletion

Do not make the initial ruleset so strict that release automation cannot function.

## GitHub Pages

The repository contains `.github/workflows/pages.yml`, which deploys the `site/` directory using GitHub Actions and attempts Pages enablement automatically.

Expected production URL:

```text
https://ami3go.github.io/codepc-link/
```

If the first Pages run reports that Pages is not enabled, open **Settings → Pages** once and set the source/build mode to **GitHub Actions**, then rerun the workflow.

## Security

Recommended:

- Enable private vulnerability reporting / Security Advisories
- Enable Dependabot alerts
- Enable dependency graph
- Enable secret scanning if available for the repository/account
- Keep Actions permissions at the minimum needed by each workflow

## Topics / description

Suggested description:

> BLE discovery, network-status and recovery companion for headless Linux mini-PC systems with Cockpit.

Suggested topics:

```text
bluetooth
ble
cockpit
linux
headless
networking
systemd
networkmanager
web-bluetooth
pwa
```
