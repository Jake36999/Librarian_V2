"""The open web as a place to look (2026-09-28): which backend a search uses, results
as candidates with their backend named, and ingest as the only way to keep one."""
import pytest

from resource_librarian import intake, tools, websearch  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import render_config

WIKI = {"query": {"search": [{"title": "Agile software development",
                              "snippet": "<span>Agile</span> is a set of practices"}]}}
OPENALEX = {"results": [{"display_name": "Self-Organizing Roles on Agile Teams",
                         "doi": "https://doi.org/10.1109/tse.2012.30", "publication_year": 2013,
                         "cited_by_count": 200,
                         "primary_location": {"source": {"display_name": "IEEE TSE"}}}]}


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for name in ("BRAVE_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def ctx(vault, responses):
    return Context(tier="consult", vault=vault,
                   extras={"fetcher": intake.Replay({f"{k}*": v for k, v in responses.items()})})


def test_the_backend_is_the_first_one_set_up(vault, monkeypatch):
    assert websearch.backend(vault) == "wikipedia"
    config = vault.config()
    config["search"] = {"searxng_url": "http://127.0.0.1:8888"}
    vault.config_path.write_text(render_config(config))
    assert websearch.backend(vault) == "searxng"
    monkeypatch.setenv("TAVILY_API_KEY", "t")
    assert websearch.backend(vault) == "tavily"
    monkeypatch.setenv("BRAVE_API_KEY", "b")
    assert websearch.backend(vault) == "brave"


def test_without_a_web_backend_it_says_so_and_searches_wikipedia(vault):
    out = REGISTRY.call("web_search", {"query": "agile"},
                        ctx(vault, {"https://en.wikipedia.org/w/api.php": WIKI}))
    assert out["backend"] == "wikipedia" and "BRAVE_API_KEY" in out["note"]
    assert out["results"][0] == {"url": "https://en.wikipedia.org/wiki/Agile_software_development",
                                 "title": "Agile software development",
                                 "snippet": "Agile is a set of practices"}


def test_scholarly_asks_openalex_and_links_the_doi(vault):
    out = REGISTRY.call("web_search", {"query": "agile teams", "kind": "scholarly"},
                        ctx(vault, {"https://api.openalex.org/works": OPENALEX}))
    assert out["backend"] == "openalex"
    assert out["results"][0]["url"] == "https://doi.org/10.1109/tse.2012.30"
    assert "IEEE TSE" in out["results"][0]["snippet"]


def test_an_unreachable_search_is_said_not_raised(vault):
    out = REGISTRY.call("web_search", {"query": "agile"}, ctx(vault, {}))
    assert out["results"] == [] and "could not be reached" in out["note"]


def test_a_searxng_instance_is_asked_for_json(vault):
    config = vault.config()
    config["search"] = {"searxng_url": "http://127.0.0.1:8888/"}
    vault.config_path.write_text(render_config(config))
    out = REGISTRY.call("web_search", {"query": "thunkable"}, ctx(vault, {
        "http://127.0.0.1:8888/search": {"results": [
            {"url": "https://docs.thunkable.com/", "title": "Thunkable Docs",
             "content": "Build native mobile apps"}]}}))
    assert out["backend"] == "searxng" and out["results"][0]["url"] == "https://docs.thunkable.com/"
