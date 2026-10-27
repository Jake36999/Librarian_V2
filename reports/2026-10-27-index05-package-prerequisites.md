# INDEX-05 packaged-adapter prerequisites

Date: 2026-10-27
Implementation: `bcf687a`
Status: partial; packaged-adapter prerequisites hardened, INDEX-05/G1 open

## Delivered boundary

This packet removes three avoidable sources of ambiguity before real packaged
adapter acceptance:

- setup selects only CPython 3.11--3.13, refuses an unsupported existing
  virtual environment, and does not silently substitute another interpreter
  when the operator explicitly requests one;
- release construction validates Core `2.1.0.dev0` and the corresponding
  adapter `2.1.0-dev` across Python metadata, Obsidian source/built/npm
  metadata and the Cowork plugin manifest before building; and
- Host discovery publishes its process-start identity, while Obsidian validates
  the exact PID, process start, vault and loopback endpoint through the
  authoritative installed Core CLI before returning the discovery token.

The Obsidian graceful-stop wait is also aligned with the Host's 25-second
window. Its checked-in bundle was regenerated from the reviewed source; the
CSS output now matches the current shared UI stylesheet rather than the older
stale bundle.

## Verification

Focused Python verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_setup_python.py tests/test_release_versions.py tests/test_obsidian_adapter_contract.py tests/test_host_lifecycle.py tests/test_process_identity.py tests/test_doctor.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **41 passed in 12.41s**.

Obsidian source and generated-bundle verification:

```powershell
Push-Location obsidian
npm.cmd run build
npm.cmd run check
Pop-Location
```

Both commands passed. The build ran TypeScript checking and regenerated
`dist/main.js` and `dist/styles.css`; the standalone type check then passed.

Release metadata and candidate-artifact verification:

```powershell
& .\.venv\Scripts\python.exe scripts/check_release_versions.py --root .
& .\scripts\build-release.ps1 -OutDir tmp\release-prereq-check-host-20261027 -SkipTests -SkipUi
```

The direct check reported **Core 2.1.0.dev0, adapters 2.1.0-dev**. A fresh
release-candidate build on the normal host with CPython 3.11 passed that same
gate, resolved the isolated build environment, built the wheel and visibly
packaged `standard/model_expectations/core.json` and
`service_expectations/core.json`. `-SkipTests` and `-SkipUi` were deliberate:
the focused tests and Obsidian build/check had already run separately, and this
command was used to prove the hardened candidate construction path.

The first candidate invocation in the Codex sandbox reached the new metadata
gate, then failed because sandbox DNS could not reach PyPI for isolated
setuptools resolution. The identical construction step succeeded on the
normal host; the sandbox attempt is recorded as an environment limitation, not
a product failure or acceptance result. Candidate output under `tmp/` is local,
generated and untracked.

Frozen-source full default-suite verification against `bcf687a`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,453 passed, 2 skipped, 3 deselected in 1,025.42s (17m05s)**.

## Limits and remaining boundary

The successful candidate build proves version coherence and wheel contents,
not installed runtime behavior. It did not install the wheel into a clean
environment or start packaged Browser, Cowork or Obsidian clients. The host
does not provide the Obsidian executable/SecretStorage environment required
for real Obsidian acceptance, and only CPython 3.11 was available; Python
3.12/3.13 matrix evidence remains outstanding. No signed stable bundle was
created.

INDEX-05/G1 therefore remains open for simultaneous packaged Browser/Cowork
runtime evidence, externally provided real-Obsidian evidence, Python 3.12/3.13
clean-wheel smoke, clean packaged-install acceptance, unsupported long-lived
external handles, large attachments and encoder writer occupancy.
