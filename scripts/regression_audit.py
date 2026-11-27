"""A before/after regression audit of the Librarian (implementation plan §2; Owner, 27 November 2026).

The build is a hardening pass over a mature system: nothing it does may lose a capability, a setting,
a workflow, an adapter or a level of detail. This compares two checkouts and lists every difference,
so each is either intended (and named in the commit) or restored.

    git worktree add --detach G:/Librarian-work/audit-base <base-ref>
    git worktree add --detach G:/Librarian-work/audit-head <head-ref>
    python -I scripts/regression_audit.py inventory G:/Librarian-work/audit-base base.json
    python -I scripts/regression_audit.py inventory G:/Librarian-work/audit-head head.json
    python -I scripts/regression_audit.py compare base.json head.json
    python scripts/regression_audit.py deletions <base-ref> <head-ref>

`inventory` imports the checkout's own `src` (run it with `-I`, so an installed copy is not used).
It records, without calling a model or opening a vault:
- every registered tool: tier, effect, flags, phases, parameters and their defaults, returns;
- the refusal rules; the standard workflows, pipelines and macros, as text;
- per module: public functions and classes with their parameters, and module-level constants;
- API route strings in app.py; the model task names the code uses;
- the batch's stages, recipes, dependencies, model stages and tools; roles and default profiles.

`compare` lists what was removed or changed between two inventories (additions are only counted).
`deletions` lists, from git, deleted test files and test functions, removed or changed assertions,
added skips, and every line removed from the docs.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path


def inventory(checkout: Path, out_path: Path) -> None:
    root = checkout.resolve()
    sys.path.insert(0, str(root / "src"))
    import resource_librarian
    if Path(resource_librarian.__file__).resolve().parents[1] != (root / "src"):
        raise SystemExit(f"imported {resource_librarian.__file__}, not {root}; run with python -I")
    import resource_librarian.tools  # noqa: F401
    from resource_librarian.registry import REGISTRY
    out: dict = {"checkout": str(root)}

    tools = {}
    for name in REGISTRY.names():
        s = REGISTRY.get(name)
        try:
            params = {p: (repr(v.default) if v.default is not inspect._empty else "<required>")
                      for p, v in inspect.signature(s.fn).parameters.items() if p != "ctx"}
        except (TypeError, ValueError):
            params = {}
        row = {"tier": s.tier, "effect": s.effect}
        for key in ("scope", "open_world", "orchestrates", "post_write", "sessionless", "idempotent"):
            row[key] = getattr(s, key, None)
        row["phases"] = sorted(getattr(s, "phases", ()) or ())
        row["returns"] = sorted(getattr(s, "returns", ()) or ())
        row["params"] = params
        tools[name] = row
    out["tools"] = tools

    out["rules"] = sorted(set(re.findall(r'Rule\("([A-Z_0-9]+)"',
                                         (root / "src/resource_librarian/rules.py").read_text(encoding="utf-8"))))
    out["standard"] = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
                       for p in sorted((root / "src/resource_librarian/standard").rglob("*"))
                       if p.is_file() and p.suffix in (".yaml", ".yml", ".json", ".md")}

    modules = {}
    for path in sorted((root / "src/resource_librarian").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        defs, consts = {}, {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = node.args
                defs[node.name] = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
            elif isinstance(node, ast.ClassDef):
                defs["class " + node.name] = {
                    item.name: [x.arg for x in item.args.posonlyargs + item.args.args + item.args.kwonlyargs]
                    for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))}
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if isinstance(t, ast.Name) and t.id.strip("_").isupper():
                        consts[t.id] = ast.unparse(node.value)[:4000]
        modules[path.relative_to(root).as_posix()] = {"defs": defs, "consts": consts}
    out["modules"] = modules

    app_src = (root / "src/resource_librarian/app.py").read_text(encoding="utf-8")
    out["routes"] = sorted(set(re.findall(r'["\'](/api/[A-Za-z0-9_/\-{}]+)["\']', app_src)))
    tasks: set[str] = set()
    for path in (root / "src/resource_librarian").rglob("*.py"):
        tasks |= set(re.findall(r'task\s*=\s*["\']([a-z_]+)["\']', path.read_text(encoding="utf-8")))
    out["task_names"] = sorted(tasks)

    # Values computed at import time (a constant that became a function call is compared by value).
    from resource_librarian import agent_runtime, batch, role_routes
    runtime = {"MODEL_STAGES": sorted(batch.MODEL_STAGES), "STAGE_TOOLS": sorted(batch.STAGE_TOOLS),
               "STAGE_RECIPES": dict(sorted(batch.STAGE_RECIPES.items())),
               "STAGES": [s[0] for s in getattr(batch, "STAGES", [])],
               "ROLES": list(role_routes.ROLES), "CHAT_ROLES": list(role_routes.CHAT_ROLES),
               "DEFAULT_PROFILES": {k: repr(v) for k, v in sorted(agent_runtime.DEFAULT_PROFILES.items())}}
    contract = getattr(batch, "CONTRACT", None)
    runtime["DEPENDENCIES"] = ({k: sorted(v) for k, v in sorted(contract.dependencies().items())}
                               if contract is not None else "(hard-coded in batch._run)")
    out["runtime"] = runtime
    out_path.write_text(json.dumps(out, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(f"{root}: {len(tools)} tools, {len(modules)} modules, {len(out['routes'])} routes, "
          f"{len(out['rules'])} rules -> {out_path}")


def compare(base_path: Path, head_path: Path) -> int:
    b = json.loads(base_path.read_text(encoding="utf-8"))
    h = json.loads(head_path.read_text(encoding="utf-8"))
    found: list[str] = []

    def note(line: str) -> None:
        found.append(line)
        print(line)

    for n in sorted(set(b["tools"]) - set(h["tools"])):
        note(f"TOOL REMOVED: {n}")
    for n in sorted(set(b["tools"]) & set(h["tools"])):
        bt, ht = b["tools"][n], h["tools"][n]
        for key in bt:
            if key == "params":
                gone = sorted(set(bt["params"]) - set(ht["params"]))
                new_required = sorted(p for p, v in ht["params"].items()
                                      if v == "<required>" and p not in bt["params"])
                defaults = [f"{p}: {bt['params'][p]} -> {ht['params'][p]}"
                            for p in sorted(set(bt["params"]) & set(ht["params"]))
                            if bt["params"][p] != ht["params"][p]]
                if gone or new_required or defaults:
                    note(f"TOOL PARAMS {n}: removed={gone} new_required={new_required} defaults={defaults}")
            elif key == "returns":
                lost = sorted(set(bt[key]) - set(ht.get(key, [])))
                if lost:
                    note(f"TOOL RETURNS {n}: no longer returns {lost}")
            elif bt[key] != ht.get(key):
                note(f"TOOL {key.upper()} {n}: {bt[key]} -> {ht.get(key)}")
    for kind in ("rules", "routes", "task_names"):
        for x in sorted(set(b[kind]) - set(h[kind])):
            note(f"{kind.upper()} REMOVED: {x}")
    for f in sorted(set(b["standard"]) - set(h["standard"])):
        note(f"STANDARD REMOVED: {f}")
    for f in sorted(set(b["standard"]) & set(h["standard"])):
        if b["standard"][f] != h["standard"][f]:
            note(f"STANDARD CHANGED: {f}")
    for m in sorted(set(b["modules"]) - set(h["modules"])):
        note(f"MODULE REMOVED: {m}")
    for m in sorted(set(b["modules"]) & set(h["modules"])):
        bd, hd = b["modules"][m]["defs"], h["modules"][m]["defs"]
        for name, args in sorted(bd.items()):
            if name not in hd:
                note(f"REMOVED {m}: {name}")
            elif name.startswith("class "):
                for meth, margs in args.items():
                    if meth not in hd[name]:
                        note(f"REMOVED {m}: {name}.{meth}")
                    elif [a for a in margs if a not in hd[name][meth]]:
                        note(f"SIGNATURE {m}: {name}.{meth} lost {[a for a in margs if a not in hd[name][meth]]}")
            elif [a for a in args if a not in hd[name]]:
                note(f"SIGNATURE {m}: {name} lost {[a for a in args if a not in hd[name]]}")
        bc, hc = b["modules"][m]["consts"], h["modules"][m]["consts"]
        for c in sorted(bc):
            if c not in hc:
                note(f"CONSTANT REMOVED {m}: {c}")
            elif bc[c] != hc[c]:
                note(f"CONSTANT CHANGED {m}: {c} (compare by value under RUNTIME if computed)")
    for key, value in b.get("runtime", {}).items():
        now = h.get("runtime", {}).get(key)
        if isinstance(value, dict) and isinstance(now, dict):
            for k in value:
                if k not in now:
                    note(f"RUNTIME {key}: {k} removed")
                elif value[k] != now[k]:
                    note(f"RUNTIME {key}: {k} changed: {value[k]} -> {now[k]}")
        elif isinstance(value, list) and isinstance(now, list):
            lost = [x for x in value if x not in now]
            if lost:
                note(f"RUNTIME {key}: lost {lost}")
            elif [x for x in now if x in value] != value:
                note(f"RUNTIME {key}: order changed")
        elif value != now:
            note(f"RUNTIME {key}: {value} -> {now}")
    added = len(set(h["tools"]) - set(b["tools"]))
    print(f"\n{len(found)} difference(s) to account for; {added} tool(s) added")
    return 1 if found else 0


def deletions(base: str, head: str) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=True).stdout
    print("== deleted test files")
    print(git("diff", "--diff-filter=D", "--name-only", base, head, "--", "tests"))
    current = ""
    print("== removed test functions, removed or changed assertions, added skips")
    for line in git("diff", "-U0", base, head, "--", "tests").splitlines():
        if line.startswith("+++ "):
            current = line[6:]
        elif re.match(r"^-(async )?def test_", line) or (line.startswith("-") and not line.startswith("---")
                                                         and re.search(r"assert|pytest\.raises", line)):
            print(f"{current}: {line[:240]}")
        elif line.startswith("+") and re.search(r"pytest\.mark\.(skip|xfail)|pytest\.skip\(", line):
            print(f"{current}: {line[:240]}")
    print("== lines removed from docs")
    for line in git("diff", "-U0", base, head, "--", "docs", ":!docs/tool-access-declarations.json").splitlines():
        if line.startswith("--- "):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{current}: {line[:300]}")


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    if command == "inventory" and len(args) == 2:
        inventory(Path(args[0]), Path(args[1]))
    elif command == "compare" and len(args) == 2:
        raise SystemExit(compare(Path(args[0]), Path(args[1])))
    elif command == "deletions" and len(args) == 2:
        deletions(*args)
    else:
        raise SystemExit(__doc__)
