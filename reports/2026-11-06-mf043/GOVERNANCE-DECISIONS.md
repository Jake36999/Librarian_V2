# MF-043f: operating governance, decisions for the owner (2026-11-06)

MF-043's parent condition ends with "ownership/support/license decision". These
decisions are the owner's. Nothing here is decided, and no file below has been added
to the repository. Each section gives what was measured, the options and what each
commits you to.

## What is true today (measured 2026-11-06)

- `Jake36999/Librarian_V2` is **public** (`gh repo view`: `visibility: PUBLIC`).
- It has **no licence**: `licenseInfo: null`, and no `LICENSE` file. Under default
  copyright, others may read the code but have no grant to use, copy, modify or
  redistribute it.
- It has no `SECURITY.md`, `CODEOWNERS` or support statement.
- Branch protection on `master` was not checked. Setting it is a repository setting,
  which only you can change.

## 1. Licence

| Option | What it permits | Consequence here |
|---|---|---|
| Keep no licence | Reading only | Fine for a personal tool. Nobody else may legally use or package a release |
| MIT or BSD-2-Clause | Anything, with attribution | Simplest; anyone may ship a closed fork |
| Apache-2.0 | As MIT, plus an explicit patent grant and notice rules | Common for tooling; a `NOTICE` file is expected |
| GPL-3.0 or AGPL-3.0 | Copyleft: derived works stay open; AGPL also covers network use | Limits commercial reuse; the bundled dependencies' licences must be compatible |
| Source-available (e.g. PolyForm Noncommercial) | Your terms | Not open source; some platforms treat it differently |

**Check before choosing.** The runtime dependencies are PyYAML (MIT) and keyring
(MIT). The SBOM (`scripts/make_sbom.py`) does not yet record licences. Adding them is
a small follow-up once the choice is made.

## 2. Ownership (`CODEOWNERS`)

- **Option A:** one owner (`* @Jake36999`), with reviews required on protected
  branches. Codex and Claude commits then need your review before they reach
  `master`. Today both agents push to `master` directly.
- **Option B:** no `CODEOWNERS`. Keep the current practice: the agents push, and
  the owner reviews after the fact.

## 3. Support and security reporting

- **`SECURITY.md`:** says where to report a vulnerability, for example GitHub's
  private vulnerability reporting, which you can turn on in repository settings.
  It also says which versions get fixes (for example, only the latest `2.x`).
- **Support statement:** for example "personal project, best effort, no SLA", or a
  named channel. Without one, issues are the only route.

## 4. Repository settings that back the CI rules (owner-only)

- Require the `Core CI` checks on `master` before merging, if work moves to pull
  requests.
- Restrict who may run `Release bundle` by keeping the `stable-release`
  environment's required reviewers.
- Set the default workflow token permission to read-only. The workflows now ask
  for `contents: read` themselves, so this changes nothing in them; it only
  protects any future workflow that forgets to.

## Not claimed

Choosing these does not make the project certified or compliant with anything.
MF-043's own condition says so: "No certification claim from checklist."
