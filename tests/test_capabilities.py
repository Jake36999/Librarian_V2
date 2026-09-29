"""Adding a capability (Co-work Roadmap §4 F2): an outside server is found,
read and assessed as a source, proposed exactly, and installed - in this
library only - on the person's word, never the model's."""
import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.init import init
from resource_librarian.mcp_client import McpManager
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault

from test_mcp_client import fake_definition


@pytest.fixture
def walk(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox" / "server-readme.md").write_text(
        "# fake-server\nAn MCP server that echoes its input. MIT licence. Released 2026-09.\n",
        encoding="utf-8")
    model = Context(tier="contribute", vault=vault)
    person = lambda: Context(tier="curate", vault=vault, session=model.session)  # noqa: E731

    def m(_tool, **arguments):
        return REGISTRY.call(_tool, arguments, model)
    m("open_session", purpose="add_capability", question="add an echo server")
    return m, person, model


def _to_propose(m):
    assert m("advance")["moved"] is False                           # no candidate yet
    m("update_plan", fields={"candidate": "https://example.org/fake-server"})
    assert m("advance")["moved"] == "assess"
    assert m("advance")["moved"] is False                           # not read yet
    m("ingest", ref="Inbox/server-readme.md")
    assert m("advance")["moved"] is False                           # read, not assessed
    m("update_plan", fields={"assessment": "MIT, released this month, echo only, no network"})
    out = m("record_assumptions", assumptions=[{"assumption": "the README describes the server",
                                                "settled_by": "ingest", "how": "read as a source"}])
    assert "error" not in out, out
    assert m("advance")["moved"] == "propose"


def test_the_walk_installs_only_on_the_persons_yes_and_only_here(walk, vault, tmp_path):
    m, person, model = walk
    _to_propose(m)
    fake = fake_definition()
    out = m("capability_propose", name="fake", command=fake["command"], args=fake["args"],
            why="echo for testing")
    assert out["proposed"] == "fake"
    assert m("advance")["moved"] == "install"
    asked = m("capability_install", name="fake")
    assert asked["installed"] is False and asked["needs_person"]
    assert REGISTRY.call("capability_install", {"name": "fake"}, model)["waiting_for"]
    refused = m("answer", question_id=asked["question_id"], answer="yes")
    assert refused["refused"] == "TIER_REFUSED"                      # the model cannot say yes
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "yes"}, person())
    done = m("capability_install", name="fake")
    assert done["installed"] == "fake"
    manager = McpManager(tmp_path / "config")
    assert "fake" in manager.servers() and manager.is_accepted("fake", manager.servers()["fake"])
    manager.use_library(vault.librarian)
    assert manager.enabled_here("fake")
    init(tmp_path / "Other", name="Other")                           # every other library: off
    manager.use_library(Vault(tmp_path / "Other").librarian)
    assert not manager.enabled_here("fake")
    assert m("advance")["moved"] == "check_out"


def test_a_no_is_a_finished_outcome(walk, tmp_path):
    m, person, model = walk
    _to_propose(m)
    fake = fake_definition()
    m("capability_propose", name="fake", command=fake["command"], args=fake["args"], why="w")
    m("advance")
    asked = m("capability_install", name="fake")
    REGISTRY.call("answer", {"question_id": asked["question_id"], "answer": "no"}, person())
    assert m("capability_install", name="fake")["declined_by_person"]
    assert "fake" not in McpManager(tmp_path / "config").servers()
    assert m("advance")["moved"] == "check_out"


@pytest.mark.parametrize("command,args,env,problem", [
    ("uvx", ["s2-mcp-server"], {}, "not pinned"),
    ("uvx", ["s2-mcp-server==1.7.4"], {"KEY": "sk-live-abc123456789"}, "literal value"),
    ("uvx", ["tool==1.0", "--api-key", "abc"], {}, "looks like a secret"),
    ("curl", ["https://x"], {}, "not a launcher"),
    ("npx", ["-y", "@modelcontextprotocol/server-filesystem@1.0.0"], {}, "excluded outright"),
])
def test_a_proposal_that_weakens_the_trust_boundary_is_refused(walk, command, args, env, problem):
    m, person, model = walk
    _to_propose(m)
    out = m("capability_propose", name="x", command=command, args=args, env=env, why="w")
    assert out["proposed"] is False and any(problem in p for p in out["problems"]), out
    assert m("advance")["moved"] is False                            # nothing proposed


def test_install_is_gated_to_its_phase(walk):
    m, person, model = walk
    assert m("capability_install", name="fake")["refused"] == "PHASE_GATE"


def test_the_candidates_are_the_curated_list(walk):
    m, person, model = walk
    out = m("capability_candidates")
    assert any(c["server"] == "Semantic Scholar" and "==1.7.4" in c["command"]
               for c in out["curated"])
