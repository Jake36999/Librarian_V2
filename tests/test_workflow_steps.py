"""W1 part 3 (owner, 2026-11-20): workflow steps carry depends_on, side_effects,
acceptance_criteria and compensation, after the dual-orchestrator step schema."""
import pytest

from resource_librarian import tools, workflows  # noqa: F401
from resource_librarian.registry import REGISTRY

from test_workflows import person


def save(vault, text):
    out = REGISTRY.call("save_workflow", {"yaml_text": text}, person(vault))
    assert "error" not in out, out
    return out


def run(vault, name, **inputs):
    return REGISTRY.call("run_workflow", {"name": name, "inputs": inputs}, person(vault))


GATED = """
workflow: gated-steps
purpose: a search that must find something, then two steps that depend on it
inputs:
  query: {type: string}
steps:
  - id: found
    action: search
    args: {query: {from: inputs.query}, limit: 3}
    acceptance_criteria:
      - {from: result.results, empty: false}
    on_error: continue
  - id: after
    action: staging_list
    args: {kind: source}
    depends_on: [found]
  - id: anyway
    action: staging_list
    args: {kind: source}
outputs:
  after: {from: steps.after}
  found: {from: steps.found}
"""


def test_a_result_that_misses_its_criteria_fails_and_its_dependants_skip(vault):
    save(vault, GATED)
    out = run(vault, "gated-steps", query="zzqx nothing matches this")
    assert out["status"] == "finished", out
    assert out["outputs"]["found"]["error"] == "not_accepted"
    assert "result.results" in out["outputs"]["found"]["detail"]
    assert out["outputs"]["after"] == {"skipped": True,
                                       "because": "dependency 'found' did not succeed"}
    assert "items" in out["steps"]["anyway"]                    # no depends_on: runs as before


UNDONE = """
workflow: undo-shown
purpose: a finished step declares its undo; a later failure lists it, never runs it
inputs:
  query: {type: string}
steps:
  - id: first
    action: staging_list
    args: {kind: source}
    compensation: {action: staging_list, args: {kind: folder}}
  - id: second
    action: search
    args: {query: {from: inputs.query}}
    acceptance_criteria:
      - {from: result.results, empty: false}
"""


def test_a_failure_lists_the_declared_undo_of_what_finished_and_runs_none(vault, monkeypatch):
    save(vault, UNDONE)
    calls = []
    real = REGISTRY.call

    def counting(name, arguments, ctx):
        calls.append((name, dict(arguments)))
        return real(name, arguments, ctx)

    monkeypatch.setattr(REGISTRY, "call", counting)
    out = real("run_workflow", {"name": "undo-shown", "inputs": {"query": "zzqx none"}},
               person(vault))
    assert out["status"] == "failed" and out["result"]["error"] == "not_accepted"
    assert out["compensations"] == [{"step": "first", "action": "staging_list",
                                     "args": {"kind": "folder"}}]
    assert ("staging_list", {"kind": "folder"}) not in calls      # shown, never run


@pytest.mark.parametrize("step, why", [
    ("    depends_on: [later]\n", "names no earlier step"),
    ("    side_effects: none\n", "declares side_effects 'none' but staging_list is 'local_read'"),
    ("    side_effects: sometimes\n", "side_effects is one of"),
    ("    acceptance_criteria: [{from: steps.x, is: 1}]\n", "from: result.<field>"),
    ("    acceptance_criteria: [{from: result.count, at_least: lots}]\n", "at_least is a number"),
    ("    compensation: {action: no_such_tool}\n", "not a registered action"),
    ("    compensation: {action: staging_decide, args: {}}\n", "needs 'item_ids'"),
])
def test_a_step_field_that_cannot_mean_anything_is_refused(vault, step, why):
    text = ("workflow: probe-steps\npurpose: probe\nsteps:\n  - id: only\n    action: staging_list\n"
            "    args: {kind: source}\n" + step)
    errors = workflows.validate(workflows.parse(text), workflows.Library(vault))["errors"]
    assert any(why in e for e in errors), errors


def test_validation_reports_each_steps_side_effects(vault):
    library = workflows.Library(vault)
    report = workflows.validate(library.get("deep-read-staged"), library)
    assert report["side_effects"] == {"waiting": "local_read", "read": "external_write"}
    assert report["side_effects_max"] == "external_write"
    text = ("workflow: probe-steps\npurpose: probe\nsteps:\n  - id: only\n    action: staging_list\n"
            "    args: {kind: source}\n    side_effects: local_write\n")
    report = workflows.validate(workflows.parse(text), library)
    assert report["valid"] and report["side_effects"] == {"only": "local_write"}   # may overstate
