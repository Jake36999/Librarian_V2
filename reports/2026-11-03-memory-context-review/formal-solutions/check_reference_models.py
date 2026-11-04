"""Finite research models, NOT Librarian runtime tests or a general proof.

Run with Python 3.11+. No providers, third-party packages or external writes.
The only output is JSON on stdout. Broken variants are negative controls.
"""
from collections import deque
from itertools import product
import json


def explore(initial, successors, invariant):
    queue = deque([(initial, [])])
    seen = {initial}
    edges = 0
    while queue:
        state, trace = queue.popleft()
        if not invariant(state):
            return {"holds": False, "states_seen": len(seen),
                    "transitions": edges, "counterexample": trace,
                    "bad_state": state}
        for action, nxt in successors(state):
            edges += 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, trace + [action]))
    return {"holds": True, "states_seen": len(seen), "transitions": edges}


def worker_model(stale_guard=True, duplicate_guard=True):
    # Revision 0/1; worker capture -1/0/1; at most two deliveries each.
    # Bad acceptance is a sticky flag recording a violation AT MERGE TIME.
    initial = (0, (-1, -1), (0, 0), (0, 0), False)

    def steps(s):
        revision, captures, deliveries, accepted, bad = s
        if revision == 0:
            yield "revise parent to 1", (1, captures, deliveries, accepted, bad)
        for i in range(2):
            if captures[i] == -1:
                cs = list(captures)
                cs[i] = revision
                yield f"dispatch worker {i} at revision {revision}", (
                    revision, tuple(cs), deliveries, accepted, bad)
            elif deliveries[i] < 2:
                ds, ac = list(deliveries), list(accepted)
                ds[i] += 1
                accept = ((not stale_guard or captures[i] == revision)
                          and (not duplicate_guard or accepted[i] == 0))
                if accept:
                    ac[i] += 1
                yield f"deliver worker {i}: {'accept' if accept else 'ignore'}", (
                    revision, captures, tuple(ds), tuple(ac),
                    bad or (accept and captures[i] != revision))

    return explore(initial, steps, lambda s: not s[4] and max(s[3]) <= 1)


def budget_model(atomic=True):
    # Two workers each need two units; total cap three; one attempt each.
    # 0=new, 1=locally prechecked, 2=reserved, 3=settled.
    initial = ((0, 0), 0, 0)

    def steps(s):
        statuses, reserved, spent = s
        for i, status in enumerate(statuses):
            ss = list(statuses)
            if status == 0 and reserved + spent + 2 <= 3:
                ss[i] = 2 if atomic else 1
                yield f"worker {i}: {'atomic reserve' if atomic else 'precheck'}", (
                    tuple(ss), reserved + (2 if atomic else 0), spent)
            elif status == 1:
                ss[i] = 2
                yield f"worker {i}: commit old precheck", (tuple(ss), reserved + 2, spent)
            elif status == 2:
                # Unknown completion holds its reservation (self-loop).
                yield f"worker {i}: completion unknown", s
                ss[i] = 3
                yield f"worker {i}: settle", (tuple(ss), reserved - 2, spent + 2)

    return explore(initial, steps, lambda s: s[1] >= 0 and s[2] >= 0 and s[1] + s[2] <= 3)


def support_model():
    # Explicit finite support function: (a AND b) OR c.
    checks = 0
    flattening_counterexample = None
    for a, b, c in product((False, True), repeat=3):
        expected = (a and b) or c
        groups = ((a, b), (c,))
        calculated = any(all(group) for group in groups)
        assert calculated == expected
        checks += 1
        if flattening_counterexample is None and all((a, b, c)) != expected:
            flattening_counterexample = {"a": a, "b": b, "c": c,
                                        "qualified_support_exists": expected,
                                        "incorrect_flat_AND": all((a, b, c))}
    # Freshness/permission UNKNOWN is not silently mapped to qualified TRUE.
    def conjunction(values):
        return False if False in values else (None if None in values else True)
    def disjunction(values):
        return True if True in values else (None if None in values else False)
    assert disjunction([conjunction([True, None]), False]) is None
    assert disjunction([conjunction([True, None]), True]) is True
    return {"boolean_valuations": checks, "unknown_cases": 2,
            "holds": True, "flattening_counterexample": flattening_counterexample}


def main():
    results = {
        "status": "executed_abstract_finite_models_not_runtime_verification",
        "assumptions": ["atomic transitions", "two workers", "two parent revisions",
                        "at most two result deliveries per worker",
                        "one budgeted attempt per worker", "declared support sets"],
        "worker_guarded": worker_model(),
        "worker_without_revision_guard": worker_model(stale_guard=False),
        "worker_without_duplicate_guard": worker_model(duplicate_guard=False),
        "budget_atomic": budget_model(),
        "budget_check_then_write": budget_model(atomic=False),
        "support_sets": support_model(),
    }
    assert results["worker_guarded"]["holds"]
    assert results["budget_atomic"]["holds"]
    for name in ("worker_without_revision_guard", "worker_without_duplicate_guard", "budget_check_then_write"):
        assert not results[name]["holds"], name
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
