"""A CycloneDX 1.5 software bill of materials for a Core wheel (MF-043e).

    python scripts/make_sbom.py --wheel release-out/core/<wheel> --out release-out/sbom.cdx.json
        [--lock release-out/requirements.release.lock]
        [--build-lock requirements-build.txt]
        [--npm-lock ui/package-lock.json --npm-lock obsidian/package-lock.json]

What ships and what built it are kept apart:
- **required:** the wheel's own runtime requirements (`Requires-Dist`, extras left
  out).
  - With a hash lock (a stable release's `requirements.release.lock`), every package
    the lock pins is listed with its version and SHA-256 hashes.
  - Without one (a candidate build), each requirement is listed by name with its
    specifier, marked unresolved: nothing is claimed that was not pinned.
- **excluded:** the build environment. These are the hash-locked Python build tools,
  and the npm packages the UI and Obsidian bundles were built with, each with its
  lockfile integrity hash.

The output is deterministic for the same inputs: sorted, with a serial number derived
from the wheel's hash, and a timestamp from SOURCE_DATE_EPOCH when that is set.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import uuid
import zipfile
from email.parser import Parser
from pathlib import Path

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")
HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")
NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(path: Path) -> dict[str, dict]:
    """name -> {version, hashes} from a pip-compile --generate-hashes file."""
    pins: dict[str, dict] = {}
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = PIN.match(line)
        if match:
            current = canonical(match.group(1))
            pins[current] = {"name": match.group(1), "version": match.group(2), "hashes": []}
        if current is not None:
            pins[current]["hashes"].extend(HASH.findall(line))
        if not line.endswith("\\"):
            current = None
    return pins


def wheel_metadata(wheel: Path) -> tuple[str, str, list[tuple[str, str]]]:
    with zipfile.ZipFile(wheel) as bundle:
        meta = next(n for n in bundle.namelist() if n.endswith(".dist-info/METADATA"))
        message = Parser().parsestr(bundle.read(meta).decode("utf-8"))
    requires = []
    for spec in message.get_all("Requires-Dist") or []:
        requirement, _, marker = spec.partition(";")
        if "extra" in marker:
            continue                                    # optional extras do not ship
        match = NAME.match(requirement)
        if match:
            requires.append((match.group(1), match.group(3).strip().strip("()")))
    return message["Name"], message["Version"], requires


def pypi(name: str, version: str, hashes: list[str], scope: str) -> dict:
    ref = f"pkg:pypi/{canonical(name)}@{version}"
    return {"type": "library", "bom-ref": ref, "name": name, "version": version, "purl": ref,
            "scope": scope, "hashes": [{"alg": "SHA-256", "content": h} for h in sorted(set(hashes))]}


def npm(path: Path) -> list[dict]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for key, package in sorted((lock.get("packages") or {}).items()):
        if not key.startswith("node_modules/") or not package.get("version"):
            continue
        name = key.rsplit("node_modules/", 1)[-1]
        ref = f"pkg:npm/{name.replace('@', '%40')}@{package['version']}"
        component = {"type": "library", "bom-ref": ref, "name": name,
                     "version": package["version"], "purl": ref, "scope": "excluded",
                     "properties": [{"name": "librarian:lockfile", "value": path.as_posix()}]}
        integrity = str(package.get("integrity") or "")
        if integrity.startswith("sha512-"):
            component["hashes"] = [{"alg": "SHA-512", "content":
                                    base64.b64decode(integrity[7:]).hex()}]
        out.append(component)
    return out


def build(wheel: Path, lock: Path | None, build_lock: Path | None,
          npm_locks: list[Path]) -> dict:
    name, version, requires = wheel_metadata(wheel)
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    main_ref = f"pkg:pypi/{canonical(name)}@{version}"
    components: dict[str, dict] = {}
    runtime_refs = []
    pins = read_lock(lock) if lock else {}
    if pins:
        for pin in pins.values():
            component = pypi(pin["name"], pin["version"], pin["hashes"], "required")
            components[component["bom-ref"]] = component
        runtime_refs = [f"pkg:pypi/{canonical(n)}@{pins[canonical(n)]['version']}"
                        for n, _ in requires if canonical(n) in pins]
        missing = [n for n, _ in requires if canonical(n) not in pins]
        if missing:
            raise SystemExit(f"the lock does not pin the wheel's requirement(s): {missing}")
    else:
        for req_name, specifier in requires:
            ref = f"pkg:pypi/{canonical(req_name)}"
            components[ref] = {"type": "library", "bom-ref": ref, "name": req_name,
                               "scope": "required", "purl": ref, "properties": [
                                   {"name": "librarian:specifier", "value": specifier or "any"},
                                   {"name": "librarian:resolution", "value": "unresolved: no lock"}]}
            runtime_refs.append(ref)
    for pin in (read_lock(build_lock) if build_lock else {}).values():
        component = pypi(pin["name"], pin["version"], pin["hashes"], "excluded")
        components.setdefault(component["bom-ref"], component)
    for path in npm_locks:
        for component in npm(path):
            components.setdefault(component["bom-ref"], component)
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(epoch) if epoch else None))
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'sha256:' + digest)}",
        "metadata": {"timestamp": stamp,
                     "tools": {"components": [{"type": "application",
                                               "name": "librarian-make-sbom", "version": "1"}]},
                     "component": {"type": "library", "bom-ref": main_ref, "name": name,
                                   "version": version, "purl": main_ref,
                                   "hashes": [{"alg": "SHA-256", "content": digest}],
                                   "properties": [{"name": "librarian:wheel",
                                                   "value": wheel.name}]}},
        "components": [components[ref] for ref in sorted(components)],
        "dependencies": [{"ref": main_ref, "dependsOn": sorted(runtime_refs)}],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--build-lock", type=Path)
    parser.add_argument("--npm-lock", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    bom = build(args.wheel, args.lock, args.build_lock, args.npm_lock)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bom, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(bom['components'])} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
