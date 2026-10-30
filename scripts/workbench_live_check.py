"""REMED-04 live check against a real Docker engine: stage, run, export.

Hostile outputs (a link, a hard link, a FIFO, a file past the size limit,
more files than the count limit, 9 MB on stdout) and one benign run, through
the real helpers. Not run by the test suite; it needs a running Docker engine
and an image with sh and python, pinned by digest.

Usage: python scripts/workbench_live_check.py <scratch-vault-dir> <image@sha256:...>
"""
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

from resource_librarian import workbench
from resource_librarian.vault import Vault
from resource_librarian.workbench import Engagement

root, image = Path(sys.argv[1]), sys.argv[2]
vault = Vault(root)
src = Path(tempfile.mkdtemp())
(src / "hello.py").write_text("print('hi')\n", encoding="utf-8")
archive = Path(tempfile.mkdtemp()) / "a.tar.gz"


def fresh(*_):
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(src, arcname="repo-abc")
    return archive, "hash"


workbench._download_archive = fresh
workbench._repository = lambda *_: {"repo_key": "example/test", "surveyed_tree": "abc"}
results = {}

HOSTILE = ("cd /workspace/output && echo kept > keep.txt && ln -s /etc/passwd link "
           "&& ln keep.txt hard && mkfifo fifo && mkdir -p deep/er && echo n > deep/er/n.txt "
           "&& head -c 3000000 /dev/zero > big.bin && for i in $(seq 1 30); do echo $i > f$i.txt; done "
           "&& head -c 9000000 /dev/zero | tr '\\0' x")

for case, limits in (("hostile_size", dict(MAX_OUTPUT_BYTES=1_000_000)),
                     ("hostile_count", dict(MAX_OUTPUT_FILES=10)),
                     ("hostile_types_only", dict())):
    for key, value in limits.items():
        setattr(workbench, key, value)
    engagement = Engagement(id=f"eng-live-{case[-5:]}", source="s", pinned_revision="abc")
    out = workbench._docker_execute(vault, engagement, ["sh", "-c", HOSTILE], image, workbench._run)
    results[case] = {"exit": out["exit_code"], "stderr": out["stderr"][-300:],
                     "stdout_held": len(out["stdout"]), "output_bytes": out.get("output_bytes"),
                     "export": out["export"],
                     "files": sorted(a["path"].split("/output/", 1)[-1] for a in out["artifacts"])}
    workbench.MAX_OUTPUT_BYTES, workbench.MAX_OUTPUT_FILES = 100 * 1024 * 1024, 1000
    for kind in ("source", "output"):
        workbench._run(["docker", "volume", "rm", "-f", workbench._volume_name(engagement, kind)], 60)

engagement = Engagement(id="eng-live-benign", source="s", pinned_revision="abc")
out = workbench._docker_execute(vault, engagement, ["sh", "-c",
                                "python source/hello.py > output/result.txt && cat output/result.txt"],
                                image, workbench._run)
results["benign"] = {"exit": out["exit_code"], "stdout": out["stdout"], "stderr": out["stderr"][-300:],
                     "export": out["export"], "artifacts": out["artifacts"]}
for kind in ("source", "output"):
    workbench._run(["docker", "volume", "rm", "-f", workbench._volume_name(engagement, kind)], 60)
print(json.dumps(results, indent=1))
