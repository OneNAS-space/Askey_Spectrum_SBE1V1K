# Security Policy

## Scope

This repository automates syncing OpenWrt `main` and applying a small set of
custom patches (see `patch_specs.py`) for a personal build target
(qualcommbe/ipq95xx, Askey SBE1V1K). It has no independent release versions —
the `Askey_Spectrum_SBE1V1K` branch is force-pushed on a rolling schedule and
only ever reflects the latest sync.

- **Vulnerabilities in upstream OpenWrt, the Linux kernel, or backports code**
  synced by this repo are not this repo's to fix. Please report those
  directly to the OpenWrt security team
  (https://openwrt.org/security or security@openwrt.org) or the relevant
  upstream project instead.
- **Issues in the custom patches maintained here** (in `patch_specs.py` or
  `.github/workflows/`) — for example, a patch that introduces a logic bug,
  a bad default, or a CI workflow permission that's broader than it needs to
  be — are in scope and should be reported here.

## Reporting a Vulnerability

Please do not open a public GitHub issue for a suspected security problem.
Use GitHub's private vulnerability reporting instead: go to the repository's
**Security** tab → **Report a vulnerability**. (This requires enabling
private vulnerability reporting once under **Settings → Security** if it
isn't already on.)

This is a personally maintained repository, not a funded project with an SLA
— I'll acknowledge reports as soon as I can and aim to have a fix (or a
revert of the offending patch) pushed within a few days, but there's no
formal response-time guarantee.
